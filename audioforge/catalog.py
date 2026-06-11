"""Instrument-catalog SDK — a queryable surface over the SFZ libraries.

The render side has a spec/asset SDK (`audioforge.sdk`); this is its counterpart
for the *instrument* side. It discovers every SFZ patch across the library
search paths, parses each with AudioForge's own SFZ interpreter, and exposes
them as queryable `Instrument` records with a `renderable` verdict (the engine
plays a patch only if its SFZ parses — no `#include`/`$define` — and its samples
are present in a decodable format: WAV always, plus FLAC/Ogg/MP3/AIFF when
libsndfile is available).

    from audioforge import Catalog
    cat = Catalog.build()                       # scan libraries/
    harps = cat.find("harpsichord", renderable=True)
    h = cat.instrument("Harpsichord, Italian")
    print(h.key_range, h.articulations, cat.pin(h.library))

The same object backs `scripts/catalog_instruments.py` (machine-readable JSON)
and `AudioForge().catalog()`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import _sndfile
from .sampler import parse_sfz

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_MISSING_CAP = 12
_AUDIO_EXTS = (".wav", ".flac", ".ogg", ".oga", ".mp3", ".aif", ".aiff")
_ARTIC_TOKENS = [
    "susvib", "susnv", "sustain", "sus", "staccato", "stac", "spiccato",
    "spic", "pizzicato", "pizz", "tremolo", "trem", "vibrato", "vib",
    "legato", "rolls", "roll", "mute", "muted", "harmon", "straight",
    "keyswitch", "-ks", "ks", "normal", "quiet", "loud", "pedal",
    "non-vibrato", "expvib",
]

SCHEMA = "audioforge.instrument-catalog/2"


def playable_exts() -> set[str]:
    """Extensions AudioForge can decode right now (WAV always; the rest need
    libsndfile)."""
    return {"wav"} | ({"flac", "ogg", "oga", "mp3", "aif", "aiff"}
                      if _sndfile.available() else set())


def note_name(midi: int) -> str:
    return f"{_NAMES[midi % 12]}{midi // 12 - 1}"


def _ext(path: str) -> str:
    return path.rsplit(".", 1)[-1].lower() if "." in path else ""


def _articulation(stem: str, category: str, sample_rel: str) -> str:
    if " - " in stem:                                   # VCSL: "Name - Artic"
        return stem.split(" - ", 1)[1].strip().lower()
    folders = [p.lower() for p in
               (sample_rel.replace("\\", "/").split("/")[:-1]
                + category.split("/"))]
    for p in reversed(folders):
        if any(tok in p for tok in _ARTIC_TOKENS):
            return p
    low = stem.lower()
    for tok in _ARTIC_TOKENS:
        if tok in low:
            return tok.lstrip("-")
    return "default"


@dataclass
class Instrument:
    """One SFZ patch, as the engine sees it."""
    library: str
    id: str
    sfz: str
    category: str | None = None
    renderable: bool = False
    render_blockers: list[str] = field(default_factory=list)
    articulation: str = "default"
    uses_include: bool = False
    regions: int = 0
    key_range: dict = field(default_factory=dict)
    pitch_keycenters: list[int] = field(default_factory=list)
    velocity_layers: list[list[int]] = field(default_factory=list)
    round_robin_max: int = 1
    samples: dict = field(default_factory=dict)
    missing_samples: list[str] = field(default_factory=list)
    ignored_opcodes: list[str] = field(default_factory=list)
    parse_error: str | None = None

    def covers(self, midi: int) -> bool:
        kr = self.key_range
        return bool(kr) and kr["low_midi"] <= midi <= kr["high_midi"]

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        if d.get("parse_error") is None:
            d.pop("parse_error", None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Instrument":
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in known})


def _scan_instrument(sfz_path: Path, libdir: Path):
    text = sfz_path.read_text(encoding="utf-8", errors="replace")
    rel_sfz = sfz_path.relative_to(libdir).as_posix()
    rel_parent = sfz_path.parent.relative_to(libdir).as_posix()
    uses_include = "#include" in text or "$" in text
    try:
        regions, ignored = parse_sfz(text)
    except Exception as e:                      # $vars / #include / #define …
        inst = Instrument(
            library=libdir.name, id=sfz_path.stem, sfz=rel_sfz,
            category=rel_parent if rel_parent != "." else None,
            renderable=False, render_blockers=["parse_error"],
            parse_error=f"{type(e).__name__}: {str(e).splitlines()[0][:80]}",
            samples={"unique": 0, "present": 0, "missing": 0, "formats": []})
        return inst, []

    sdir = sfz_path.parent
    samples = sorted({r.sample for r in regions if r.sample})
    resolved = {s: (sdir / s) for s in samples}
    present = {s: p for s, p in resolved.items() if p.is_file()}
    missing = sorted(set(samples) - set(present))
    formats = sorted({_ext(s) for s in samples if _ext(s)})
    total_bytes = sum(p.stat().st_size for p in present.values())

    keycenters = sorted({r.pitch_keycenter for r in regions})
    vel_bands = sorted({(r.lovel, r.hivel) for r in regions})
    lo = min((r.lokey for r in regions), default=0)
    hi = max((r.hikey for r in regions), default=127)
    category = (rel_parent if rel_parent != "." else
                (samples[0].split("/")[0] if samples and "/" in samples[0]
                 else "Unknown"))

    blockers = []
    if uses_include:
        blockers.append("uses_include")
    if not regions:
        blockers.append("no_regions")
    if any(f not in playable_exts() for f in formats):
        blockers.append("unsupported_format")
    if missing and not uses_include:
        blockers.append("missing_samples")

    inst = Instrument(
        library=libdir.name, id=sfz_path.stem, sfz=rel_sfz, category=category,
        renderable=not blockers, render_blockers=blockers,
        articulation=_articulation(sfz_path.stem, category,
                                   samples[0] if samples else ""),
        uses_include=uses_include, regions=len(regions),
        key_range={"low_midi": lo, "high_midi": hi,
                   "low_note": note_name(lo), "high_note": note_name(hi)},
        pitch_keycenters=keycenters,
        velocity_layers=[[a, b] for a, b in vel_bands],
        round_robin_max=max((r.seq_length for r in regions), default=1),
        samples={"unique": len(samples), "present": len(present),
                 "missing": len(missing), "formats": formats,
                 "total_bytes": total_bytes},
        missing_samples=([] if uses_include else missing[:_MISSING_CAP]),
        ignored_opcodes=sorted(ignored))
    return inst, [str(p) for p in present.values()]


@dataclass
class Library:
    name: str                       # directory name (catalog identity)
    instrument_count: int
    renderable_count: int
    parse_errors: int
    sample_formats: list[str]
    audio_files_on_disk: int
    audio_files_referenced: int
    audio_files_orphan: int
    pin: str | None
    categories: dict[str, list[str]]
    manifest_name: str | None = None   # the name the resolver matches on

    def matches(self, key: str) -> bool:
        return key in (self.name, self.manifest_name)


def _scan_library(libdir: Path):
    pairs = [_scan_instrument(p, libdir)
             for p in sorted(libdir.rglob("*.sfz"))]
    insts = [i for i, _ in pairs]
    referenced: set[str] = set()
    for _, res in pairs:
        referenced.update(res)
    on_disk = {str(p) for p in libdir.rglob("*")
               if p.suffix.lower() in _AUDIO_EXTS}
    cats: dict[str, list[str]] = {}
    fmts: set[str] = set()
    for i in insts:
        cats.setdefault(i.category or "Unknown", []).append(i.id)
        fmts.update(i.samples.get("formats", []))
    mp = libdir / "library.manifest.json"
    pin = manifest_name = None
    if mp.is_file():
        try:
            man = json.loads(mp.read_text())
            pin = man.get("manifest_sha256")
            manifest_name = man.get("name")
        except (ValueError, OSError):
            pin = manifest_name = None
    lib = Library(
        name=libdir.name, instrument_count=len(insts),
        renderable_count=sum(1 for i in insts if i.renderable),
        parse_errors=sum(1 for i in insts if i.parse_error),
        sample_formats=sorted(fmts), audio_files_on_disk=len(on_disk),
        audio_files_referenced=len(referenced & on_disk),
        audio_files_orphan=len(on_disk - referenced),
        pin=pin, categories={k: sorted(v) for k, v in sorted(cats.items())},
        manifest_name=manifest_name)
    return lib, insts


class Catalog:
    """A queryable view of every instrument across the library search paths."""

    def __init__(self, root: Path, libraries: list[Library],
                 instruments: list[Instrument]):
        self.root = Path(root)
        self.libraries: list[Library] = libraries
        self.instruments: list[Instrument] = instruments

    # -- construction ----------------------------------------------------
    @classmethod
    def build(cls, root: str | Path = "libraries") -> "Catalog":
        root = Path(root)
        if not root.is_dir():
            raise NotADirectoryError(root)
        # so libraries discovered here are also resolvable at render time
        from .library import add_library_path
        add_library_path(root)
        libs = sorted(c for c in root.iterdir()
                      if c.is_dir() and any(c.rglob("*.sfz")))
        if not libs and any(root.rglob("*.sfz")):
            libs = [root]
        reports, instruments = [], []
        for d in libs:
            lib, insts = _scan_library(d)
            reports.append(lib)
            instruments.extend(insts)
        return cls(root, reports, instruments)

    @classmethod
    def load(cls, path: str | Path) -> "Catalog":
        d = json.loads(Path(path).read_text())
        libs = [Library(**{k: v for k, v in l.items()
                           if k in Library.__dataclass_fields__})
                for l in d.get("libraries", [])]
        insts = [Instrument.from_dict(i) for i in d.get("instruments", [])]
        return cls(d.get("root", "libraries"), libs, insts)

    # -- serialization ---------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "root": str(self.root),
            "generated_by": "audioforge.catalog.Catalog",
            "engine_sfz_subset": "audioforge.sampler.parse_sfz",
            "libsndfile_available": _sndfile.available(),
            "renderable_note": "renderable = SFZ parses (no #include/$define) "
                               "AND all samples present on disk in a decodable "
                               f"format ({'/'.join(sorted(playable_exts()))})",
            "library_count": len(self.libraries),
            "instrument_count": len(self.instruments),
            "renderable_count": sum(1 for i in self.instruments if i.renderable),
            "parse_errors_total": sum(l.parse_errors for l in self.libraries),
            "libraries": [l.__dict__ for l in self.libraries],
            "instruments": [i.to_dict() for i in self.instruments],
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        return path

    # -- queries ---------------------------------------------------------
    def find(self, text: str | None = None, *, library: str | None = None,
             family: str | None = None, articulation: str | None = None,
             renderable: bool | None = None,
             covers: int | None = None) -> list[Instrument]:
        """Filter instruments. `text` matches id/category (case-insensitive);
        `family` matches the first category segment; `covers` keeps only
        patches whose key range includes that MIDI note."""
        out = self.instruments
        if text:
            t = text.lower()
            out = [i for i in out
                   if t in i.id.lower() or t in (i.category or "").lower()]
        if library:
            libs = {l.name for l in self.libraries if l.matches(library)}
            out = [i for i in out if i.library in (libs or {library})]
        if family:
            f = family.lower()
            out = [i for i in out
                   if (i.category or "").split("/")[0].lower() == f]
        if articulation:
            a = articulation.lower()
            out = [i for i in out if a in i.articulation.lower()]
        if renderable is not None:
            out = [i for i in out if i.renderable == renderable]
        if covers is not None:
            out = [i for i in out if i.covers(covers)]
        return out

    def instrument(self, id: str, library: str | None = None) -> Instrument:
        """The first instrument matching `id` (exact, then case-insensitive),
        optionally pinned to a library (directory or manifest name). Raises
        KeyError if none."""
        libs = ({l.name for l in self.libraries if l.matches(library)}
                if library else None)
        cands = [i for i in self.instruments
                 if (libs is None or i.library in (libs or {library}))]
        for i in cands:
            if i.id == id:
                return i
        for i in cands:
            if i.id.lower() == id.lower():
                return i
        raise KeyError(f"no instrument {id!r}"
                       + (f" in library {library!r}" if library else ""))

    def library(self, name: str) -> Library:
        for l in self.libraries:
            if l.matches(name):
                return l
        raise KeyError(f"no library {name!r}")

    def pin(self, library: str) -> str | None:
        """The library's manifest pin (None if it has no manifest yet —
        run `audioforge libgen <dir>` to create one)."""
        return self.library(library).pin

    def renderable(self) -> list[Instrument]:
        return [i for i in self.instruments if i.renderable]

    def __len__(self) -> int:
        return len(self.instruments)

    def __iter__(self):
        return iter(self.instruments)
