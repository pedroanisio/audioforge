"""Prebuilt cues: parameterized compositions ready to drop into a video.

A cue is a named, versioned composition — a music bed, a sting, a transition, a UI
or foley sound, an ambience — that compiles to ordinary `.af` DSL from a small set
of typed parameters (duration, tempo, key, intensity, seed, ...). Nothing is hidden:
`cue_dsl()` returns the exact source that renders, so every cue can be inspected,
copied and edited like any other composition, and it renders through the same
deterministic engine (same parameters + seed + engine version → same bytes).

    from audioforge.cues import list_cues, render_cue
    meta = render_cue("bed/documentary-airy", {"duration": 34, "bpm": 96}, "bed.wav")

Loudness standard (so scene gains are predictable across cues):

    bed          -18 LUFS integrated, true peak <= -1 dBFS
    sting        -16 LUFS integrated, true peak <= -1 dBFS
    ambience     -30 LUFS integrated (room tone, weather beds sit low)
    transition, ui, foley   peak-normalized to -3 dBFS

Video integration (the scene-render `<generated provider="audioforge">` resolve
step) lives in `audioforge.scene`.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

CUE_SCHEMA_VERSION = "audioforge.cue/1"
CUE_COMMANDS = ("list", "show", "dsl", "render", "gallery")      # `audioforge cue <cmd>`

KINDS = ("music", "sound-effect")          # scene-render generated@kind values
CATEGORIES = ("bed", "sting", "transition", "ui", "foley", "ambience")

LOUDNESS = {
    "bed": {"lufs": -18.0, "peak": -1.0},
    "sting": {"lufs": -16.0, "peak": -1.0},
    "ambience": {"lufs": -30.0, "peak": -1.0},
    "transition": {"normalize": "peak", "peak": -3.0},
    "ui": {"normalize": "peak", "peak": -3.0},
    "foley": {"normalize": "peak", "peak": -3.0},
}


class CueError(ValueError):
    """Unknown cue or invalid cue parameters."""


@dataclass(frozen=True)
class Param:
    name: str
    kind: str                       # "float" | "int" | "key" | "choice"
    default: object
    doc: str
    min: float | None = None
    max: float | None = None
    choices: tuple[str, ...] = ()

    def coerce(self, value):
        try:
            if self.kind == "float":
                v = float(value)
            elif self.kind == "int":
                v = int(float(value))
                if float(value) != v:
                    raise ValueError
            elif self.kind == "key":
                v = normalize_key(str(value))
            elif self.kind == "choice":
                v = str(value)
                if v not in self.choices:
                    raise CueError(f"{self.name}: {v!r} is not one of {', '.join(self.choices)}")
            else:                               # pragma: no cover - registry bug
                raise CueError(f"{self.name}: unknown parameter kind {self.kind!r}")
        except CueError:
            raise
        except (TypeError, ValueError):
            raise CueError(f"{self.name}: {value!r} is not a valid {self.kind}") from None
        if self.min is not None and v < self.min:
            raise CueError(f"{self.name}: {v} is below the minimum {self.min}")
        if self.max is not None and v > self.max:
            raise CueError(f"{self.name}: {v} is above the maximum {self.max}")
        return v

    def describe(self) -> dict:
        d = {"name": self.name, "type": self.kind, "default": self.default, "doc": self.doc}
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        if self.choices:
            d["choices"] = list(self.choices)
        return d


@dataclass(frozen=True)
class Cue:
    id: str                         # "<category>/<name>"
    kind: str                       # "music" | "sound-effect"
    category: str
    title: str
    description: str
    params: tuple[Param, ...]
    build: Callable[[dict], str] = field(repr=False, compare=False)
    tags: tuple[str, ...] = ()
    version: int = 1                # bump when the composition changes

    @property
    def param_map(self) -> dict[str, Param]:
        return {p.name: p for p in self.params}

    def describe(self) -> dict:
        return {"id": self.id, "kind": self.kind, "category": self.category,
                "title": self.title, "description": self.description,
                "tags": list(self.tags), "version": self.version,
                "loudness": LOUDNESS[self.category],
                "params": [p.describe() for p in self.params]}


_REGISTRY: dict[str, Cue] = {}


def register(cue: Cue) -> Cue:
    if cue.kind not in KINDS:
        raise CueError(f"{cue.id}: kind must be one of {KINDS}")
    if cue.category not in CATEGORIES or not cue.id.startswith(cue.category + "/"):
        raise CueError(f"{cue.id}: id must be '<category>/<name>' with a known category")
    if cue.id in _REGISTRY:
        raise CueError(f"{cue.id}: already registered")
    if not any(p.name == "duration" for p in cue.params) or \
            not any(p.name == "seed" for p in cue.params):
        raise CueError(f"{cue.id}: every cue takes 'duration' and 'seed'")
    _REGISTRY[cue.id] = cue
    return cue


def _load_library() -> None:
    if not _REGISTRY:
        from . import library  # noqa: F401  (registers on import)


def list_cues(kind: str | None = None, category: str | None = None,
              tag: str | None = None) -> list[Cue]:
    _load_library()
    return [c for c in sorted(_REGISTRY.values(), key=lambda c: c.id)
            if (kind is None or c.kind == kind)
            and (category is None or c.category == category)
            and (tag is None or tag in c.tags)]


def get_cue(cue_id: str) -> Cue:
    _load_library()
    try:
        return _REGISTRY[cue_id]
    except KeyError:
        near = [c for c in _REGISTRY if cue_id.split("/")[-1] in c]
        hint = f" (did you mean {', '.join(near[:3])}?)" if near else ""
        raise CueError(f"unknown cue {cue_id!r}{hint}; `audioforge cue list` shows all") from None


# ------------------------------------------------------------------ parameters
_KEY_RE = re.compile(r"^\s*([A-Ga-g])([#b]?)\s*(maj|major|min|minor|m)?\s*$")


def normalize_key(text: str) -> str:
    """'A minor', 'Am', 'f# major', 'Eb' -> canonical 'A minor' / 'F# major' / 'Eb major'."""
    m = _KEY_RE.match(text.replace("-", " "))
    if not m:
        raise CueError(f"key: {text!r} is not a key such as 'A minor' or 'C major'")
    mode = "minor" if m.group(3) in ("min", "minor", "m") else "major"
    return f"{m.group(1).upper()}{m.group(2)} {mode}"


def parse_params(spec: str | dict | None) -> dict:
    """`"duration=34 bpm=96 key='A minor'"` (spaces, commas or semicolons) -> dict."""
    if spec is None:
        return {}
    if isinstance(spec, dict):
        return dict(spec)
    out: dict = {}
    for token in shlex.split(spec.replace(",", " ").replace(";", " ")):
        if "=" not in token:
            raise CueError(f"parameter {token!r} must be name=value")
        k, v = token.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def resolve_params(cue: Cue, params: str | dict | None = None) -> dict:
    """Defaults + validated overrides. Unknown names are an error (no silent typos)."""
    given = parse_params(params)
    pmap = cue.param_map
    unknown = sorted(set(given) - set(pmap))
    if unknown:
        raise CueError(f"{cue.id}: unknown parameter(s) {', '.join(unknown)}; "
                       f"known: {', '.join(pmap)}")
    return {name: p.coerce(given.get(name, p.default)) for name, p in pmap.items()}


# ------------------------------------------------------------------- building
def cue_dsl(cue_id: str, params: str | dict | None = None) -> str:
    """The exact `.af` source this cue renders for these parameters."""
    cue = get_cue(cue_id)
    return cue.build(resolve_params(cue, params))


def params_hash(cue: Cue, resolved: dict) -> str:
    """Identity of a cue request (cue id + version + resolved parameters)."""
    blob = json.dumps({"id": cue.id, "version": cue.version, "params": resolved},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def render_cue(cue_id: str, params: str | dict | None, out_path: str | Path, *,
               sample_rate: int = 48000, bit_depth: int = 24) -> dict:
    """Render a cue to one WAV at `out_path`; returns provenance metadata.

    The metadata (also written next to the WAV as `<name>.audioforge.json`)
    records the cue id/version, resolved parameters, spec hash, engine version and
    the WAV's SHA-256 — everything needed to verify or re-create the file."""
    from ..determinism import performance_hash
    from ..dsl import compile_dsl
    from ..render import _write_wav, render
    from ..version import ENGINE_VERSION

    cue = get_cue(cue_id)
    resolved = resolve_params(cue, params)
    src = cue.build(resolved)
    specs, _diagnostics = compile_dsl(src)
    if len(specs) != 1:                      # pragma: no cover - builder bug
        raise CueError(f"{cue.id}: builder produced {len(specs)} assets")
    spec = dict(specs[0])
    spec["sample_rate"] = int(sample_rate)
    spec["bit_depth"] = int(bit_depth)
    stereo, sr, meta = render(spec)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    # the engine's own writer: seeded TPDF dither on the performance path, so
    # the bytes equal what `audioforge render` writes for the same spec
    _write_wav(tmp, stereo, sr, int(bit_depth), performance_hash(spec), "dither")
    tmp.replace(out_path)
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    info = {
        "schema": CUE_SCHEMA_VERSION,
        "cue": cue.id, "cue_version": cue.version, "kind": cue.kind,
        "category": cue.category, "params": resolved,
        "params_hash": params_hash(cue, resolved),
        "engine_version": ENGINE_VERSION, "spec_hash": meta["spec_hash"],
        "sample_rate": sr, "bit_depth": bit_depth, "channels": 2,
        "duration_s": round(stereo.shape[0] / sr, 6),
        "loudness": meta.get("loudness"), "markers": meta.get("markers", []),
        "file": out_path.name, "sha256": digest,
    }
    sidecar_path(out_path).write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return info


def sidecar_path(wav_path: str | Path) -> Path:
    wav_path = Path(wav_path)
    return wav_path.with_name(wav_path.name + ".audioforge.json")


def build_gallery(out_dir: str | Path, *, category: str | None = None) -> Path:
    """Render every cue (defaults) into `out_dir` with an `index.html` to audition
    them in a browser. WAVs stay local; nothing here is meant for version control."""
    import html
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for cue in list_cues(category=category):
        name = cue.id.replace("/", "__") + ".wav"
        info = render_cue(cue.id, None, out_dir / name)
        params = " ".join(f"{k}={v!r}" if isinstance(v, str) and " " in v else f"{k}={v}"
                          for k, v in info["params"].items())
        rows.append(
            f"<section><h2>{html.escape(cue.title)} <code>{html.escape(cue.id)}</code></h2>"
            f"<p>{html.escape(cue.description)}</p>"
            f"<audio controls preload=\"none\" src=\"{html.escape(name)}\"></audio>"
            f"<p class=meta>{cue.kind} · {cue.category} · {info['duration_s']} s · "
            f"tags: {html.escape(', '.join(cue.tags))}</p>"
            f"<pre>audioforge cue render {html.escape(cue.id)} {html.escape(params)} -o out.wav</pre>"
            f"</section>")
    page = ("<!doctype html><meta charset=utf-8><title>AudioForge cues</title>"
            "<style>body{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem}"
            "section{border-top:1px solid #ccc;padding:.6rem 0}audio{width:100%}"
            "code,pre{background:#f3f3f3;padding:.1rem .3rem}pre{white-space:pre-wrap}"
            ".meta{color:#666;font-size:13px}</style>"
            f"<h1>AudioForge cue gallery</h1><p>{len(rows)} cues rendered at their default "
            "parameters. Every cue takes duration and seed; beds also take bpm, key and "
            "intensity (see <code>audioforge cue show ID</code>).</p>" + "".join(rows))
    index = out_dir / "index.html"
    index.write_text(page, encoding="utf-8")
    return index
