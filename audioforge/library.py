"""Content-addressed instrument libraries ("orchestra manifests").

A library is a directory of WAV + SFZ files plus one `library.manifest.json`
pinning every byte:

    {"name": "...", "version": "...", "license": "...",
     "files": [{"path": "...", "sha256": "..."}, ...],
     "instruments": {"violins_1": {"sfz": "...",            # default map
                                   "articulations": {"sustain": "...sfz"}}},
     "manifest_sha256": "<hash, see below>"}

`manifest_sha256` covers the canonical JSON of name+version+license+files+
instruments. This deliberately extends the architecture doc (which hashed
only the file list): remapping an instrument to a different SFZ changes the
rendered audio, so it must change the hash — same doctrine as everywhere
else. Specs reference `library: "name@manifest_sha256"`; the pin folds into
the spec hash, and every sample file is byte-verified at first load.
"""
from __future__ import annotations

import hashlib
import io
import json
import wave
from pathlib import Path

import numpy as np

from .sampler import parse_sfz

_LIBRARY_PATHS: list[Path] = [Path("libraries")]
DEFAULT_APPROVED_CATALOG_PATH = Path("_catalog/approved")


def add_library_path(path) -> None:
    p = Path(path)
    if p not in _LIBRARY_PATHS:
        _LIBRARY_PATHS.insert(0, p)


def add_approved_catalog_path(
    path: str | Path = DEFAULT_APPROVED_CATALOG_PATH,
) -> Path:
    """Register the reviewed sample-catalog root and return it as a Path."""
    p = Path(path)
    add_library_path(p)
    return p


def _library_candidates(base: Path, name: str) -> list[Path]:
    """Candidate manifest roots under a search path.

    Standard libraries live at ``base/name``. Reviewed sample catalogs use
    ``base/<instrument>/<version>`` so registering ``_catalog/approved`` must
    also inspect one bounded level below each instrument directory.
    """
    out: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if path not in seen:
            seen.add(path)
            out.append(path)

    named = base / name
    add(named)
    if named.is_dir():
        for child in sorted(named.iterdir()):
            if child.is_dir():
                add(child)
    if base.is_dir():
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            add(child)
            for grandchild in sorted(child.iterdir()):
                if grandchild.is_dir():
                    add(grandchild)
    return out


def _canonical_manifest_hash(m: dict) -> str:
    from .sample_catalog.constants import SAMPLE_CATALOG_BUILDER_VERSION

    def hash_region(region: dict) -> dict:
        out = dict(region)
        out.pop("library_pin", None)
        return out

    core = {"name": m["name"], "version": m.get("version", ""),
            "license": m.get("license", ""),
            "files": sorted([[f["path"], f["sha256"]] for f in m["files"]]),
            "instruments": m["instruments"]}
    if m.get("builder_version") == SAMPLE_CATALOG_BUILDER_VERSION:
        core.update({
            "builder_version": m.get("builder_version"),
            "catalog_state": m.get("catalog_state"),
            "license_evidence_hash": m.get("license_evidence_hash"),
            "analysis_summary": m.get("analysis_summary", {}),
            "catalog_diagnostics": m.get("catalog_diagnostics", {}),
            "review": m.get("review", {}),
            "regions": [hash_region(r) for r in m.get("regions", [])],
        })
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def generate_manifest(directory, name: str | None = None,
                      version: str = "0.0.0", license_str: str = "UNKNOWN",
                      instruments: dict | None = None) -> dict:
    """Scan a library directory: hash every sample/sfz, build the manifest.
    Sample formats are WAV plus the libsndfile-decoded ones (FLAC/Ogg/MP3/
    AIFF). Without an explicit instruments mapping, every top-level .sfz
    becomes an instrument (stem as name) with a single 'sustain' articulation."""
    base = Path(directory)
    audio_exts = (".wav", ".sfz", ".flac", ".ogg", ".oga", ".mp3",
                  ".aif", ".aiff")
    files = []
    for p in sorted(base.rglob("*")):
        if p.suffix.lower() in audio_exts and p.is_file():
            files.append({"path": p.relative_to(base).as_posix(),
                          "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    if instruments is None:
        instruments = {}
        for f in files:
            if f["path"].endswith(".sfz") and "/" not in f["path"]:
                stem = f["path"][:-4]
                instruments[stem] = {"sfz": f["path"],
                                     "articulations": {"sustain": f["path"]}}
    m = {"name": name or base.name, "version": version,
         "license": license_str, "files": files, "instruments": instruments}
    m["manifest_sha256"] = _canonical_manifest_hash(m)
    (base / "library.manifest.json").write_text(json.dumps(m, indent=1))
    return m


def _decode_wav_bytes(data: bytes, ext: str = "") -> tuple[np.ndarray, int]:
    """Decode to native mono (N,) or stereo (N, 2) float64 and sample rate.
    WAV is read in pure
    Python; FLAC / Ogg / AIFF are routed through libsndfile (see _sndfile)."""
    if not data[:4] == b"RIFF" and (ext.lower().lstrip(".") != "wav"):
        from . import _sndfile
        x, sr = _sndfile.decode(data, ext)          # [frames, channels]
        if x.ndim == 2 and x.shape[1] > 2:
            raise ValueError("instrument samples must be mono or stereo")
        return (x[:, 0] if x.ndim == 2 and x.shape[1] == 1 else x), sr
    with wave.open(io.BytesIO(data)) as w:
        sr, ch, sw, n = (w.getframerate(), w.getnchannels(),
                         w.getsampwidth(), w.getnframes())
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8)
             | (b[:, 2].astype(np.int32) << 16))
        x = (v - ((v >> 23) & 1) * (1 << 24)) / float(1 << 23)
    elif sw == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float64) / (2.0 ** 31)
    else:
        raise ValueError(f"unsupported WAV sample width {sw * 8}-bit")
    if ch > 1:
        if ch > 2:
            raise ValueError("instrument samples must be mono or stereo")
        x = x.reshape(-1, ch)
    return x, sr


def _verify_approved_sample_catalog(root: Path, manifest: dict) -> None:
    from .sample_catalog.constants import (
        LICENSE_BUNDLE_SCHEMA,
        LICENSE_EVIDENCE_SCHEMA,
        SAMPLE_CATALOG_BUILDER_VERSION,
    )

    if manifest.get("builder_version") != SAMPLE_CATALOG_BUILDER_VERSION:
        raise ValueError(
            f"library '{manifest['name']}': unsupported sample catalog "
            f"builder version {manifest.get('builder_version')!r}")
    from .sample_catalog.licenses import (
        decide_license,
        evidence_hash,
        validate_evidence_hash,
        validate_final_evidence_source,
    )
    from .sample_catalog.manifest import (
        audit_region_mechanics,
        validate_catalog_diagnostics,
        validate_region_coverages,
        validate_region_library_pins,
        validate_region_sample_identities,
        validate_approved_review_metadata,
    )

    licenses = root / "LICENSES.json"
    if not licenses.is_file():
        raise ValueError(
            f"library '{manifest['name']}': approved catalog is missing "
            "LICENSES.json")
    bundle = json.loads(licenses.read_text())
    if (bundle.get("schema") != LICENSE_BUNDLE_SCHEMA
            or not isinstance(bundle.get("evidence"), list)
            or not bundle["evidence"]):
        raise ValueError(
            f"library '{manifest['name']}': approved catalog license "
            "evidence bundle is malformed")
    actual_bundle_hash = evidence_hash({
        "schema": bundle["schema"],
        "evidence": bundle["evidence"],
    })
    if actual_bundle_hash != manifest.get("license_evidence_hash"):
        raise ValueError(
            f"library '{manifest['name']}': approved catalog license "
            "evidence hash mismatch")
    for item in manifest.get("files", []):
        rel = item.get("path")
        sha = item.get("sha256")
        if not rel or not sha:
            raise ValueError(
                f"library '{manifest['name']}': approved catalog has "
                "malformed file hash entry")
        path = root / rel
        if not path.is_file():
            raise ValueError(
                f"library '{manifest['name']}': approved catalog is missing "
                f"pinned file '{rel}'")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != sha:
            raise ValueError(
                f"library '{manifest['name']}': hash mismatch for '{rel}'\n"
                f"  pinned:  {sha}\n  on disk: {actual}\n"
                "The file changed since the manifest was generated.")
    evidence_ids = set()
    for item in bundle["evidence"]:
        if item.get("schema") != LICENSE_EVIDENCE_SCHEMA:
            raise ValueError(
                f"library '{manifest['name']}': approved catalog has "
                f"unsupported license evidence schema "
                f"{item.get('schema')!r}")
        validate_evidence_hash(item)
        validate_final_evidence_source(item)
        decision = decide_license(
            license_name=item.get("license_name", ""),
            license_url=item.get("license_url", ""),
            rights_text=item.get("rights_text", ""),
            source_url=item.get("source_url", ""),
            source_id=item.get("source_id", ""),
        )
        if not decision.accepted:
            raise ValueError(
                f"library '{manifest['name']}': approved catalog has "
                f"unsupported or unclear license evidence "
                f"{item.get('evidence_hash', '')}")
        evidence_ids.add(item["evidence_hash"])
    for region in manifest.get("regions", []):
        sample = region.get("sample")
        if not sample:
            raise ValueError(
                f"library '{manifest['name']}': approved catalog region "
                "is missing sample path")
        pinned_sha = next(
            (item.get("sha256") for item in manifest.get("files", [])
             if item.get("path") == sample),
            None,
        )
        if not pinned_sha:
            raise ValueError(
                f"library '{manifest['name']}': approved catalog region "
                f"{sample} is not pinned in manifest files")
        if region.get("sample_sha256") != pinned_sha:
            raise ValueError(
                f"library '{manifest['name']}': approved catalog region "
                f"{sample} sample_sha256 does not match manifest files")
        evidence_id = region.get("source_evidence_id")
        if not evidence_id:
            raise ValueError(
                f"library '{manifest['name']}': approved catalog region "
                f"{sample} is missing "
                "source_evidence_id")
        if evidence_id not in evidence_ids:
            raise ValueError(
                f"library '{manifest['name']}': approved catalog region "
                f"{sample} references unknown "
                "source evidence")
    audit_region_mechanics(manifest)
    validate_region_coverages(manifest)
    validate_catalog_diagnostics(manifest, root)
    validate_approved_review_metadata(manifest)
    try:
        validate_region_sample_identities(manifest, root)
        validate_region_library_pins(manifest)
    except ValueError as e:
        raise ValueError(f"library '{manifest['name']}': {e}") from e


class Library:
    """A verified, loaded library: SFZ region sets and byte-checked audio,
    cached per instance. Fails loudly on any divergence from the pin."""

    def __init__(self, root: Path, manifest: dict):
        self.root = root
        self.manifest = manifest
        self._by_path = {f["path"]: f["sha256"] for f in manifest["files"]}
        self._audio_cache: dict[str, tuple[np.ndarray, int]] = {}
        self._region_cache: dict[tuple, list] = {}
        self.ignored_opcodes: set[str] = set()

    def _verified_bytes(self, rel: str) -> bytes:
        sha = self._by_path.get(rel)
        if sha is None:
            raise ValueError(
                f"library '{self.manifest['name']}': '{rel}' is not in the "
                f"manifest — every byte that can affect output must be pinned")
        data = (self.root / rel).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != sha:
            raise ValueError(
                f"library '{self.manifest['name']}': hash mismatch for "
                f"'{rel}'\n  pinned:  {sha}\n  on disk: {actual}\n"
                f"The file changed since the manifest was generated.")
        return data

    def regions(self, instrument: str, articulation: str = "sustain"):
        key = (instrument, articulation)
        if key in self._region_cache:
            return self._region_cache[key]
        inst = self.manifest["instruments"].get(instrument)
        if inst is None:
            raise ValueError(
                f"library '{self.manifest['name']}' has no instrument "
                f"'{instrument}' (available: "
                f"{sorted(self.manifest['instruments'])})")
        arts = inst.get("articulations", {})
        sfz_rel = arts.get(articulation) or (
            inst.get("sfz") if articulation == "sustain" else None)
        if sfz_rel is None:
            raise ValueError(
                f"instrument '{instrument}': no articulation "
                f"'{articulation}' (available: {sorted(arts)})")
        text = self._verified_bytes(sfz_rel).decode("utf-8", "replace")
        regions, ignored = parse_sfz(text)
        self.ignored_opcodes |= ignored
        # sample paths are relative to the .sfz file's directory
        sfz_dir = str(Path(sfz_rel).parent.as_posix())
        prefix = "" if sfz_dir == "." else sfz_dir + "/"
        for r in regions:
            r.sample = (prefix + r.sample).replace("//", "/")
        self._region_cache[key] = regions
        return regions

    def audio(self, rel: str) -> tuple[np.ndarray, int]:
        if rel not in self._audio_cache:
            ext = rel.rsplit(".", 1)[-1] if "." in rel else ""
            self._audio_cache[rel] = _decode_wav_bytes(
                self._verified_bytes(rel), ext)
        return self._audio_cache[rel]


def load_library(ref, *, require_approved: bool = False) -> Library:
    """Resolve `"name@manifest_hash"` (or a {name, manifest_sha256} dict)
    against the library search paths. The manifest is re-hashed on load —
    a tampered manifest cannot pass — and must match the pinned hash."""
    if isinstance(ref, str):
        if "@" not in ref:
            raise ValueError("library reference must be 'name@manifest_hash'")
        name, pin = ref.split("@", 1)
    else:
        name, pin = ref["name"], ref["manifest_sha256"]
    tried = []
    for base in _LIBRARY_PATHS:
        for cand in _library_candidates(base, name):
            mp = Path(cand) / "library.manifest.json"
            if not mp.is_file():
                continue
            m = json.loads(mp.read_text())
            if m.get("name") != name:
                continue
            tried.append(str(mp))
            actual = _canonical_manifest_hash(m)
            if actual != m.get("manifest_sha256"):
                raise ValueError(
                    f"library '{name}': manifest self-hash invalid "
                    f"(file edited without regeneration?)")
            if not actual.startswith(pin):
                continue                  # allow short pins, full preferred
            if require_approved:
                state = m.get("catalog_state")
                evidence = m.get("license_evidence_hash")
                if state != "approved":
                    raise ValueError(
                        f"library '{name}': approved catalog required "
                        f"(catalog_state={state!r})")
                if not evidence:
                    raise ValueError(
                        f"library '{name}': approved catalog is missing "
                        "license_evidence_hash")
                _verify_approved_sample_catalog(Path(cand), m)
            return Library(Path(cand), m)
    raise ValueError(
        f"library '{name}@{pin[:12]}…' not found in "
        f"{[str(p) for p in _LIBRARY_PATHS]}"
        + (f"; candidates with that name had different hashes: {tried}"
           if tried else " — add its directory with add_library_path()"))
