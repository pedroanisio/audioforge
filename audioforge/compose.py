"""Programmatic composition — build a renderable spec in Python, no DSL text.

The `.af` DSL is the authoring surface for humans; this is the authoring
surface for code. A `Composer` assembles the same validated spec the DSL
compiler emits — synth layers, sampled-instrument layers, note events, master
bus — and hands back an `AudioAsset` you can render/export. It ties into the
instrument `Catalog`, so you can drop a real library instrument straight in:

    from audioforge import AudioForge, Composer
    cat = AudioForge().catalog()
    c = (Composer("sketch", tempo=92, key="C major")
         .tone("pad", osc="sine",
               events=[("C4", 0, 4), ("E4", 0, 4), ("G4", 0, 4)])
         .from_catalog("hpsi", cat, "Harpsichord, Italian",
                       events=[("C5", 0, 1), ("D5", 1, 1), ("E5", 2, 2)])
         .master(peak_db=-1.0))
    c.export("out/", preset="web_preview")

Note events are `(note, start_beat, dur_beats[, vel])` tuples — `note` is a
name like "C4" or a number read as Hz — or dicts with those keys. Advanced
musical transforms (motifs, diatonic/retrograde/invert `play`) stay in the
DSL; this builds concrete events.
"""
from __future__ import annotations

import copy
from pathlib import Path

from .schema import SpecError

_DEFAULT_ENV = {"attack": 0.01, "decay": 0.1, "sustain": 0.8, "release": 0.2}


def hall(rt60: float = 2.4, damp: float = 0.4, mix: float = 0.28) -> dict:
    """A hall-reverb fx dict (room/pedal resonance and tail)."""
    return {"type": "hall", "rt60": float(rt60), "damp": float(damp),
            "mix": float(mix)}


def reverb(decay_s: float = 1.8, mix: float = 0.25) -> dict:
    return {"type": "reverb", "decay_s": float(decay_s), "mix": float(mix)}


def _norm_event(ev) -> dict:
    if isinstance(ev, dict):
        out = dict(ev)
    else:
        ev = list(ev)
        out = {"start_beat": ev[1], "dur_beats": ev[2]}
        pitch = ev[0]
        out["note" if isinstance(pitch, str) else "freq_hz"] = pitch
        if len(ev) > 3 and ev[3] is not None:
            out["vel"] = ev[3]
    out["start_beat"] = float(out["start_beat"])
    out["dur_beats"] = float(out["dur_beats"])
    return out


def _env(env) -> dict:
    if env is None:
        return dict(_DEFAULT_ENV)
    if isinstance(env, dict):
        # accept a/d/s/r shorthand or full names
        m = {"a": "attack", "d": "decay", "s": "sustain", "r": "release"}
        return {m.get(k, k): float(v) for k, v in env.items()}
    raise SpecError("env must be a dict, e.g. {'a':0.01,'d':0.1,'s':0.8,'r':0.2}")


class Composer:
    """Fluent builder for a single audio asset. Every adder returns self."""

    def __init__(self, id: str, kind: str = "cue", tempo: float = 120,
                 duration: float | None = None, key: str | None = None,
                 swing: float | None = None, performance_seed: int = 0):
        self.spec: dict = {"id": id, "kind": kind, "bpm": float(tempo),
                           "layers": [], "master": {}, "markers": []}
        self.spec["performance_seed"] = performance_seed
        if key:
            self.spec["key"] = key
        if swing is not None:
            self.spec["swing"] = float(swing)
        self._duration = duration

    def tempo_map(self, points) -> "Composer":
        """Rubato: a list of (beat, bpm) breakpoints; the first must be beat 0.
        Tempo eases linearly between points, so phrase-end ritardandos read as
        human rather than metronomic."""
        pts = [[float(b), float(v)] for b, v in points]
        if not pts or pts[0][0] != 0.0:
            raise SpecError("tempo_map: first breakpoint must be at beat 0")
        self.spec["tempo_map"] = pts
        return self

    # -- performance shaping (humanize / dynamics / legato / fx) ----------
    @staticmethod
    def _perf(humanize=None, dynamic=None, legato_s=None, phrasing=None,
              fx=None) -> dict:
        out: dict = {}
        if humanize is not None:
            if isinstance(humanize, (tuple, list)):
                out["humanize"] = {"timing_s": float(humanize[0]),
                                   "vel": float(humanize[1])}
            else:
                out["humanize"] = {k: float(v) for k, v in humanize.items()}
        if dynamic is not None:
            out["dynamic"] = [[float(b), float(v)] for b, v in dynamic]
        if legato_s is not None:
            out["legato_s"] = float(legato_s)
        if phrasing is not None:
            out["phrasing"] = float(phrasing)
        if fx is not None:
            out["fx"] = list(fx)
        return out

    # -- shared library (the schema pins one library per spec) -----------
    def library(self, name: str, pin: str) -> "Composer":
        self.spec["library"] = {"name": name, "manifest_sha256": pin}
        return self

    def _ensure_library(self, name: str, pin: str):
        cur = self.spec.get("library")
        if cur and cur["name"] != name:
            raise SpecError(
                f"a spec pins one library; '{cur['name']}' already set, "
                f"cannot also use '{name}'. Compose per-library assets.")
        self.spec["library"] = {"name": name, "manifest_sha256": pin}

    # -- layers ----------------------------------------------------------
    def tone(self, name: str, *, osc: str = "sine", events,
             env=None, gain_db: float | None = None, **perf) -> "Composer":
        """A synth layer (oscillator + envelope) playing concrete notes.
        Accepts humanize/dynamic/fx performance kwargs (see ._perf)."""
        layer = {"name": name, "type": "notes", "osc": osc,
                 "env": _env(env),
                 "notes": [_norm_event(e) for e in events]}
        if gain_db is not None:
            layer["gain_db"] = float(gain_db)
        layer.update(self._perf(**perf))
        self.spec["layers"].append(layer)
        return self

    def instrument(self, name: str, *, instrument: str, events,
                   articulation: str = "sustain",
                   library: tuple[str, str] | None = None,
                   gain_db: float | None = None, **perf) -> "Composer":
        """A sampled-instrument layer. `library=(name, pin)` sets the spec's
        library if not already set. Performance kwargs: humanize=(timing_s,
        vel), dynamic=[(beat, 0..1)], legato_s, phrasing, fx=[hall(...)]."""
        if library:
            self._ensure_library(*library)
        if "library" not in self.spec:
            raise SpecError("instrument layer needs a library: call "
                            ".library(name, pin) or pass library=(name, pin)")
        layer = {"name": name, "type": "instrument", "instrument": instrument,
                 "articulation": articulation,
                 "notes": [_norm_event(e) for e in events]}
        if gain_db is not None:
            layer["gain_db"] = float(gain_db)
        layer.update(self._perf(**perf))
        self.spec["layers"].append(layer)
        return self

    def from_catalog(self, name: str, catalog, instrument_id: str, *, events,
                     library: str | None = None, articulation: str = "sustain",
                     gain_db: float | None = None, **perf) -> "Composer":
        """Add an instrument layer resolved from a `Catalog`: checks the patch
        is renderable, reads its library pin, and wires it up. Performance
        kwargs are forwarded to .instrument()."""
        inst = catalog.instrument(instrument_id, library)
        if not inst.renderable:
            raise SpecError(f"instrument '{inst.id}' is not renderable: "
                            f"{inst.render_blockers}")
        lib = catalog.library(inst.library)
        if not lib.pin:
            raise SpecError(f"library '{inst.library}' has no manifest pin — "
                            f"run `audioforge libgen libraries/{inst.library}`")
        # the spec must reference the library by its manifest name (what the
        # resolver matches), which can differ from the directory name
        self._ensure_library(lib.manifest_name or lib.name, lib.pin)
        return self.instrument(name, instrument=inst.id, events=events,
                               articulation=articulation, gain_db=gain_db,
                               **perf)

    # -- annotations / output --------------------------------------------
    def marker(self, name: str, time_s: float) -> "Composer":
        self.spec["markers"].append({"name": name, "time_s": float(time_s)})
        return self

    def master(self, *, peak_db: float | None = -1.0,
               target_lufs: float | None = None, fx=None,
               fade_in_s: float | None = None,
               fade_out_s: float | None = None,
               normalization: str = "none") -> "Composer":
        """Set delivery levels; peak_db is a ceiling unless normalization=peak."""
        m = self.spec["master"]
        m["normalization"] = normalization
        if peak_db is not None:
            m["target_peak_dbfs"] = float(peak_db)
        if target_lufs is not None:
            m["target_lufs"] = float(target_lufs)
        if fx is not None:
            m["fx"] = list(fx)
        if fade_in_s is not None:
            m["fade_in_s"] = float(fade_in_s)
        if fade_out_s is not None:
            m["fade_out_s"] = float(fade_out_s)
        return self

    def _finish(self) -> dict:
        spec = copy.deepcopy(self.spec)
        if self._duration is not None:
            spec["duration_s"] = float(self._duration)
        else:                                   # auto: last note end + tail
            end_beats = max(
                (e["start_beat"] + e["dur_beats"]
                 for L in spec["layers"] for e in L["notes"]), default=0.0)
            tail = max((L["env"]["release"] for L in spec["layers"]
                        if "env" in L), default=0.3)
            spec["duration_s"] = round(end_beats * 60.0 / spec["bpm"]
                                       + tail + 0.2, 4) or 0.5
        if not spec["markers"]:
            spec.pop("markers")
        return spec

    def asset(self):
        """Validate and return an `AudioAsset` (raises SpecError if invalid)."""
        from .sdk import AudioForge
        return AudioForge().load_spec(self._finish())

    def render(self, return_stems: bool = False):
        return self.asset().render(return_stems=return_stems)

    def export(self, out_dir: str | Path, **kw) -> dict:
        return self.asset().export(out_dir, **kw)

    def to_dsl_spec(self) -> dict:
        """The finished, validated spec dict (e.g. to inspect or serialize)."""
        return self._finish()
