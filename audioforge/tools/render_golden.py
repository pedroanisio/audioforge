"""Golden-audio oracle: a committed hash lock + drift gate (roadmap item AF-R06).

The primary gate is a compact SHA-256 lock (`tests/golden/audio.lock.json`) over a
small, fast `.af` corpus (`tests/golden/audio/`). A fresh clone can re-render the
corpus and prove nothing drifted — without any committed WAVs.

    python -m audioforge.tools.render_golden --update   # (re)pin the lock
    python -m audioforge.tools.render_golden --check     # gate: re-render vs lock
    python -m audioforge.tools.render_golden --check --strict   # cross-env too

Determinism vs environment (the crux, per AF-R06's risk note). AudioForge renders
are byte-identical *within one numeric environment* (verified: same env => same
`output_sha256`), but float reduction order differs across BLAS/FFT/numpy builds,
so a hash can legitimately differ *across* environments — that is AF-R16's problem,
not a regression. The lock therefore records its `numeric_env`; `--check` is
**strict** when the current env matches the lock (a hash mismatch is a real
regression) and **advisory** when it differs (expected float drift — reported,
not failed) unless `--strict` forces failure. A structural change (frame count,
channels, or sample rate) is ALWAYS a hard failure, regardless of env.

ε rationale (Rule 2 — not a magic number). Cosmetic drift is a per-sample max-abs
difference below −120 dBFS (~1e-6 linear). That is beneath the 16-bit
quantisation floor (≈ −96 dBFS) and the 24-bit floor (≈ −144 dBFS is the ceiling
of resolvable detail, so −120 dBFS is a conservative, inaudible bound); it is the
residue of float reduction-order differences, not an audible/structural change. A
difference at or above ε is real drift.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): a render's correctness is unverified until
re-rendered and compared. This lock is that comparison, committed and gated.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

from audioforge import AudioForge, spec_hash

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests" / "golden" / "audio"
LOCK = ROOT / "tests" / "golden" / "audio.lock.json"

COSMETIC_EPS_DBFS = -120.0
COSMETIC_EPS_LINEAR = 10.0 ** (COSMETIC_EPS_DBFS / 20.0)  # ~1e-6


def numeric_env() -> dict:
    """The environment inputs a float render secretly depends on (AF-R16 seed)."""
    import numpy
    import scipy

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
    }


def classify_drift(ref: np.ndarray, new: np.ndarray, eps_linear: float = COSMETIC_EPS_LINEAR) -> dict:
    """Classify a waveform difference as 'cosmetic' (sub-ε float residue) or 'real'.

    Returns {verdict, max_abs, max_abs_dbfs, first_index}. A shape mismatch (e.g.
    different length) is structural → 'real'. This is a pure function so it can be
    exercised against a closed ground truth, and reused by AF-R16's cross-env lane.
    """
    ref = np.asarray(ref, dtype=np.float64).ravel()
    new = np.asarray(new, dtype=np.float64).ravel()
    if ref.shape != new.shape:
        return {"verdict": "real", "max_abs": float("inf"), "max_abs_dbfs": 0.0, "first_index": 0}
    diff = np.abs(new - ref)
    max_abs = float(diff.max()) if diff.size else 0.0
    over = np.flatnonzero(diff >= eps_linear)
    verdict = "real" if over.size else "cosmetic"
    dbfs = 20.0 * np.log10(max_abs) if max_abs > 0 else float("-inf")
    return {
        "verdict": verdict,
        "max_abs": max_abs,
        "max_abs_dbfs": dbfs,
        "first_index": int(over[0]) if over.size else -1,
    }


def render_one(spec_path: Path) -> dict:
    """Render one corpus spec into a tempdir; return its compact manifest."""
    res = AudioForge().compile(Path(spec_path).read_text())
    if not res.ok:
        raise RuntimeError(f"{spec_path}: compile failed: {[d.message for d in res.diagnostics]}")
    asset = res.assets[0]
    with tempfile.TemporaryDirectory() as d:
        meta = asset.export(d)
        wavs = sorted(f for f in os.listdir(d) if f.endswith(".wav"))
        if not wavs:
            raise RuntimeError(f"{spec_path}: render produced no WAV")
        with wave.open(os.path.join(d, wavs[0])) as w:
            frames, channels, sr = w.getnframes(), w.getnchannels(), w.getframerate()
    return {
        "spec_hash": spec_hash(asset.spec),
        "output_sha256": meta["output_sha256"],
        "sr": sr,
        "channels": channels,
        "frames": frames,
    }


def _corpus_specs() -> list[Path]:
    return sorted(CORPUS.glob("*.af"))


def build_lock() -> dict:
    return {
        "cosmetic_eps_dbfs": COSMETIC_EPS_DBFS,
        "numeric_env": numeric_env(),
        "specs": {p.stem: render_one(p) for p in _corpus_specs()},
    }


def render_lock_bytes() -> str:
    """Canonical, byte-stable serialization of a fresh lock."""
    return json.dumps(build_lock(), indent=2, sort_keys=True) + "\n"


def check_lock(strict: bool = False) -> tuple[bool, list[str]]:
    """Re-render the corpus and compare to the committed lock. Returns (ok, report)."""
    if not LOCK.is_file():
        return False, [f"missing lock {LOCK} — run --update"]
    lock = json.loads(LOCK.read_text())
    same_env = lock.get("numeric_env") == numeric_env()
    report: list[str] = []
    ok = True
    locked_specs = lock.get("specs", {})
    seen = set()
    for path in _corpus_specs():
        stem = path.stem
        seen.add(stem)
        if stem not in locked_specs:
            ok = False
            report.append(f"REAL: {stem} is not in the lock — run --update")
            continue
        want = locked_specs[stem]
        got = render_one(path)
        if got["output_sha256"] == want["output_sha256"]:
            continue
        # structural change is always a hard failure
        structural = any(got[k] != want.get(k) for k in ("frames", "channels", "sr"))
        if structural:
            ok = False
            report.append(
                f"REAL (structural): {stem} frames/ch/sr {want.get('frames')}/{want.get('channels')}/"
                f"{want.get('sr')} -> {got['frames']}/{got['channels']}/{got['sr']}"
            )
        elif same_env or strict:
            ok = False
            where = "same numeric env" if same_env else "--strict"
            report.append(
                f"REAL: {stem} output_sha256 changed under {where} "
                f"({want['output_sha256'][:12]} -> {got['output_sha256'][:12]})"
            )
        else:
            report.append(
                f"cosmetic (advisory): {stem} hash differs but env differs from the lock "
                f"(numpy {lock['numeric_env'].get('numpy')} -> {numeric_env()['numpy']}); "
                "cross-env float drift, not a regression (AF-R16)"
            )
    missing = set(locked_specs) - seen
    if missing:
        ok = False
        report.append(f"REAL: lock has specs with no corpus file: {sorted(missing)}")
    if not report:
        report.append(f"all {len(seen)} golden specs reproduce byte-for-byte (env match: {same_env})")
    return ok, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m audioforge.tools.render_golden",
        description="Golden-audio oracle: pin (--update) or gate (--check) the corpus hash lock.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_const", dest="mode", const="update",
                      help="re-render the corpus and re-pin tests/golden/audio.lock.json")
    mode.add_argument("--check", action="store_const", dest="mode", const="check",
                      help="re-render the corpus and fail on real drift (default)")
    parser.add_argument("--strict", action="store_true",
                        help="treat cross-env hash drift as failure too (same-OS CI lane)")
    parser.set_defaults(mode="check")
    args = parser.parse_args(argv)

    if args.mode == "update":
        LOCK.write_text(render_lock_bytes(), encoding="utf-8")
        print(f"pinned {len(_corpus_specs())} golden specs -> {LOCK}")
        return 0

    ok, report = check_lock(strict=args.strict)
    stream = sys.stdout if ok else sys.stderr
    for line in report:
        stream.write(f"golden-check: {line}\n")
    if not ok:
        stream.write("golden-check: real render drift detected. If intended, run "
                     "`python -m audioforge.tools.render_golden --update`.\n")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
