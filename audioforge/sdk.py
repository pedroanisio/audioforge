"""AudioForge SDK — the integration surface for applications and AI agents.

Design:
  * `AudioAsset` wraps one spec with validate/render/export/preview/mutate.
  * All operations return data, never print; diagnostics are structured so
    agents can consume them programmatically.
  * Export presets capture delivery targets (sample rate / bit depth /
    loudness) without touching the creative content of the spec — they
    produce a derived spec with a derived id, so every delivery variant is
    itself reproducible and hash-tracked.
  * Plugins register through audioforge.plugins; the SDK exposes them.

Typical agent loop:
    sdk = AudioForge()
    result = sdk.compile(dsl_text)          # -> CompileResult
    if result.errors: ...fix and retry...
    asset = result.assets[0]
    issues = asset.validate()               # structured diagnostics
    asset.set("layers.0.gain_db", -8)       # schema-checked mutation
    meta = asset.export("out/", preset="social_video", stems=True)
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

from .determinism import spec_hash
from .dsl import DSLError, compile_dsl
from .plugins import (EXPORTERS, run_extra_validators,  # noqa: F401
                      register_drum_voice, register_exporter, register_fx,
                      register_oscillator, register_validator)
from .render import render, render_to_wav
from .schema import SpecError, validate_spec

EXPORT_PRESETS = {
    "social_video":     {"sample_rate": 48000, "bit_depth": 16, "target_lufs": -14.0},
    "broadcast":        {"sample_rate": 48000, "bit_depth": 24, "target_lufs": -23.0},
    "cinematic_master": {"sample_rate": 96000, "bit_depth": 24, "target_lufs": -16.0},
    "web_preview":      {"sample_rate": 22050, "bit_depth": 16, "target_lufs": -16.0},
}


@dataclass
class Diagnostic:
    severity: str   # "error" | "warning"
    message: str
    path: str | None = None

    def as_dict(self):
        return {"severity": self.severity, "message": self.message,
                "path": self.path}


class AudioAsset:
    """One audio asset = one spec. Mutable until you render; every render
    is keyed to the spec content hash at that moment."""

    def __init__(self, spec: dict):
        self.spec = copy.deepcopy(spec)

    # -- identity ------------------------------------------------------
    @property
    def id(self) -> str:
        return self.spec["id"]

    @property
    def hash(self) -> str:
        return spec_hash(self.spec)

    # -- variation -------------------------------------------------------
    def variant(self, tag) -> "AudioAsset":
        """A sibling asset: identical composition, every seeded path
        (textures, humanize, grains, dither) re-realized. Note: vary()
        choice sets resolve at compile time — use forge.compile(src,
        variant=...) for structural variation."""
        spec = copy.deepcopy(self.spec)
        spec["variant"] = str(tag)
        return AudioAsset(spec)

    def with_intensity(self, scale: float) -> "AudioAsset":
        """The same cue at a different dramatic temperature: scales the
        intensity-curve-derived master automation (0..1.5)."""
        spec = copy.deepcopy(self.spec)
        spec["intensity_scale"] = float(scale)
        return AudioAsset(spec)

    def export_cutdowns(self, out_dir: str | Path,
                        preset: str | None = None) -> list[dict]:
        """Render every declared cutdown: <id>_<N>s.wav + manifest each,
        with parent lineage (spec hash, keep windows) recorded."""
        from .render import render_cutdowns, _write_wav
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        spec = copy.deepcopy(self._resolved(self.spec))
        if preset:
            if preset not in EXPORT_PRESETS:
                raise SpecError(f"unknown export preset '{preset}' "
                                f"(available: {sorted(EXPORT_PRESETS)})")
            cfg = EXPORT_PRESETS[preset]
            spec["sample_rate"] = cfg["sample_rate"]
            spec["bit_depth"] = cfg["bit_depth"]
            spec.setdefault("master", {})["target_lufs"] = cfg["target_lufs"]
        metas = []
        for length, stereo, sr, meta in render_cutdowns(spec):
            stem = f"{self.id}_{int(length)}s"
            p = out_dir / f"{stem}.wav"
            meta["output_sha256"] = _write_wav(
                p, stereo, sr, meta["bit_depth"], meta["spec_hash"],
                f"dither:cutdown:{int(length)}")
            meta["file"] = p.name
            (out_dir / f"{stem}.manifest.json").write_text(
                json.dumps(meta, indent=1))
            metas.append(meta)
        return metas

    # -- validation ------------------------------------------------------
    def validate(self, resolve: bool = True) -> list[Diagnostic]:
        """Structural schema check plus (by default) the resource-binding
        resolve pass, so an empty error list means "this will render".
        Pass resolve=False for the pure structural check."""
        out: list[Diagnostic] = []
        try:
            validate_spec(self.spec)
        except SpecError as e:
            out.append(Diagnostic("error", str(e)))
            return out
        out.extend(_timeline_warnings(self.spec))
        out.extend(Diagnostic("warning", m)
                   for m in run_extra_validators(self.spec))
        if resolve:
            from .resolve import resolve_spec
            out.extend(Diagnostic("error", m)
                       for m in resolve_spec(self.spec))
        return out

    # -- mutation (agent-friendly) ----------------------------------------
    def set(self, path: str, value) -> "AudioAsset":
        """Dotted-path mutation, e.g. set('layers.0.gain_db', -6).
        Re-validates; raises SpecError (with the path) on invalid results."""
        node = self.spec
        keys = path.split(".")
        for k in keys[:-1]:
            node = node[int(k)] if isinstance(node, list) else node[k]
        last = keys[-1]
        if isinstance(node, list):
            node[int(last)] = value
        else:
            node[last] = value
        validate_spec(self.spec)
        return self

    def mutated(self, path: str, value, new_id: str | None = None) -> "AudioAsset":
        """Non-destructive variant: returns a new asset (optionally re-id'd)."""
        a = AudioAsset(self.spec)
        a.set(path, value)
        if new_id:
            a.spec["id"] = new_id
        return a

    # -- rendering ---------------------------------------------------------
    @staticmethod
    def _resolved(spec: dict) -> dict:
        """Eager resource binding: raise one structured SpecError listing
        every unresolved resource, instead of a raw mid-render traceback."""
        from .resolve import resolve_spec
        problems = resolve_spec(spec)
        if problems:
            raise SpecError("unresolved resources:\n  - "
                            + "\n  - ".join(problems))
        return spec

    def render(self, return_stems: bool = False):
        try:
            return render(self._resolved(self.spec),
                          return_stems=return_stems)
        except (ValueError, RuntimeError) as e:
            if isinstance(e, SpecError):
                raise
            raise SpecError(f"render failed: {e}") from e

    def plan(self) -> dict:
        """Return the deterministic render-plan artifact and hash."""
        from .plan import build_render_plan
        result = build_render_plan(self._resolved(self.spec))
        return {
            "plan": result.plan,
            "plan_hash": result.plan_hash,
            "diagnostics": result.diagnostics,
        }

    def preview(self, out_dir: str | Path) -> dict:
        """Fast low-resolution render for iterative listening."""
        return self.export(out_dir, preset="web_preview", id_suffix="__preview")

    def export(self, out_dir: str | Path, preset: str | None = None,
               stems: bool = False, id_suffix: str | None = None,
               analyze: bool = False,
               plan_path: str | Path | None = None) -> dict:
        spec = copy.deepcopy(self.spec)
        if preset:
            if preset not in EXPORT_PRESETS:
                raise SpecError(f"unknown export preset '{preset}' "
                                f"(available: {sorted(EXPORT_PRESETS)})")
            cfg = EXPORT_PRESETS[preset]
            spec["sample_rate"] = cfg["sample_rate"]
            spec["bit_depth"] = cfg["bit_depth"]
            spec.setdefault("master", {})["target_lufs"] = cfg["target_lufs"]
            spec["id"] = spec["id"] + (id_suffix or f"__{preset}")
        elif id_suffix:
            spec["id"] = spec["id"] + id_suffix
        try:
            render_plan = None
            if plan_path is not None:
                from .plan import load_plan_json
                render_plan = load_plan_json(Path(plan_path).read_text())
            if render_plan is None:
                meta = render_to_wav(self._resolved(spec), out_dir,
                                     stems=stems)
            else:
                meta = render_to_wav(self._resolved(spec), out_dir,
                                     stems=stems, render_plan=render_plan)
        except (ValueError, RuntimeError) as e:
            if isinstance(e, SpecError):
                raise
            raise SpecError(f"render failed: {e}") from e
        if analyze:
            from .analysis import analyze_audio
            stereo, sr, _ = render(self._resolved(spec))
            meta["analysis"] = analyze_audio(stereo, sr)
            manifest = Path(out_dir) / f"{spec['id']}.manifest.json"
            if manifest.exists():
                manifest.write_text(json.dumps(meta, indent=2,
                                               sort_keys=True))
        for name, exporter in sorted(EXPORTERS.items()):
            meta.setdefault("extra_exports", {})[name] = exporter(
                spec, meta, Path(out_dir))
        return meta

    def analyze(self) -> dict:
        """Render in memory and return deterministic analysis features."""
        from .analysis import analyze_audio
        stereo, sr, _ = self.render()
        return analyze_audio(stereo, sr)

    # -- serialization -----------------------------------------------------
    def to_json(self) -> str:
        return json.dumps(self.spec, indent=2, sort_keys=True)

    def to_dsl(self) -> str:
        from .decompile import spec_to_dsl
        return spec_to_dsl(self.spec)

    def to_midi(self) -> bytes:
        from .interop import export_midi_bytes
        return export_midi_bytes(self.spec)

    def to_musicxml(self) -> str:
        from .interop import export_musicxml
        return export_musicxml(self.spec)

    @classmethod
    def from_json(cls, text: str) -> "AudioAsset":
        return cls(validate_spec(json.loads(text)))


@dataclass
class CompileResult:
    assets: list[AudioAsset] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors


def _timeline_warnings(spec: dict) -> list[Diagnostic]:
    bpm = float(spec.get("bpm", 120.0))
    beat_s = 60.0 / bpm
    duration_s = float(spec["duration_s"])
    out: list[Diagnostic] = []
    for i, layer in enumerate(spec.get("layers", [])):
        if layer.get("type") not in ("notes", "instrument"):
            continue
        for j, ev in enumerate(layer.get("notes", [])):
            end_s = (float(ev["start_beat"]) + float(ev["dur_beats"])) * beat_s
            if end_s > duration_s:
                out.append(Diagnostic(
                    "warning",
                    "note event extends past asset duration and will be "
                    "truncated or skipped at render",
                    f"layers.{i}.notes.{j}"))
    return out


class AudioForge:
    """SDK entry point."""

    export_presets = EXPORT_PRESETS

    def compile(self, dsl_text: str, variant=None,
                base_dir: str | Path | None = None) -> CompileResult:
        """DSL -> assets. Never raises on user input: errors become
        diagnostics an agent can read and act on. `variant` resolves
        vary() choice sets and reseeds every stochastic path. `base_dir`
        is the directory `import` directives resolve against (set
        automatically by `load_file`)."""
        from .includes import has_imports, resolve_includes
        result = CompileResult()
        imports_manifest: list = []
        try:
            if has_imports(dsl_text):
                resolved = resolve_includes(dsl_text, base_dir)
                dsl_text = resolved.source
                imports_manifest = resolved.imports
            specs, warns = compile_dsl(dsl_text, variant=variant)
        except DSLError as e:
            result.diagnostics.append(Diagnostic("error", str(e)))
            return result
        result.diagnostics.extend(Diagnostic("warning", w) for w in warns)
        for spec in specs:
            if imports_manifest:
                spec.setdefault("_meta", {})["imports"] = imports_manifest
            try:
                validate_spec(spec)
                result.assets.append(AudioAsset(spec))
            except SpecError as e:
                result.diagnostics.append(
                    Diagnostic("error", f"{spec.get('id', '?')}: {e}"))
        return result

    def export_pack(self, dsl_text: str, out_dir: str | Path, n: int = 8,
                    tags: list | None = None, preset: str | None = None,
                    out_subdir_per_asset: bool = False) -> dict:
        """One spec -> a pack: N variant renders per asset, each with its
        own hash-tracked manifest, plus a pack manifest tying them to the
        source. vary() choice sets and all seeded paths re-realize per
        variant tag."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        tags = tags if tags is not None else [f"v{i+1}" for i in range(n)]
        pack = {"variants": [], "preset": preset}
        for tag in tags:
            res = self.compile(dsl_text, variant=tag)
            errs = [d for d in res.diagnostics if d.severity == "error"]
            if errs:
                raise SpecError(f"variant {tag}: {errs[0].message}")
            for asset in res.assets:
                meta = asset.export(out_dir, preset=preset,
                                    id_suffix=f"__{tag}")
                pack["variants"].append({
                    "asset": asset.id, "variant": tag,
                    "spec_hash": meta["spec_hash"],
                    "output_sha256": meta["output_sha256"],
                    "file": meta["file"]})
        (out_dir / "pack.manifest.json").write_text(
            json.dumps(pack, indent=1))
        return pack

    def catalog(self, root: str | Path = "libraries"):
        """Discover the installed instrument libraries and return a queryable
        `Catalog` (see audioforge.catalog). Pairs with the spec/asset SDK:
        find an instrument, read its key range/articulations, and get its
        library pin to author `library:`/`instrument:` references."""
        from .catalog import Catalog
        return Catalog.build(root)

    def load_spec(self, spec: dict) -> AudioAsset:
        return AudioAsset(validate_spec(spec))

    def load_file(self, path: str | Path) -> CompileResult:
        path = Path(path)
        if path.suffix == ".af":
            return self.compile(path.read_text(), base_dir=path.parent)
        asset = AudioAsset(validate_spec(json.loads(path.read_text())))
        return CompileResult(assets=[asset])

    def import_midi(self, data: bytes, asset_id: str = "imported_midi") -> AudioAsset:
        from .interop import import_midi_bytes
        return self.load_spec(import_midi_bytes(data, asset_id=asset_id))

    def import_musicxml(self, text: str,
                        asset_id: str = "imported_musicxml") -> AudioAsset:
        from .interop import import_musicxml
        return self.load_spec(import_musicxml(text, asset_id=asset_id))
