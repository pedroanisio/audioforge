#!/usr/bin/env python3
"""Sound match: a target sample -> an editable AudioForge `.af` patch.

Offline analysis-by-synthesis (see `audioforge.match`): renders candidate
patches, scores each against the target's timbre and envelope, and emits the
best as a `.af` you can open and edit — then re-renders it to report a
*verified* fidelity, not an asserted one.

    python3 scripts/sound_match.py TARGET.wav [-o out/name]

Writes <out>.af (the patch) and <out>.match.json (pitch, ADSR, ranked
shortlist, verified distance, confidence). Pitched single-voice timbres are the
supported case; drums/noise report low confidence honestly.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audioforge.match import match_patch  # noqa: E402


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(path.read_bytes())) as w:
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
        raise SystemExit(f"unsupported WAV sample width {sw * 8}-bit")
    return (x.reshape(-1, ch) if ch > 1 else x), sr


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("-o", "--out", default="compare/match")
    a = ap.parse_args(argv)
    target, sr = load_wav(Path(a.target))
    res = match_patch(target, sr)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".af").write_text(res["dsl"])
    report = {k: v for k, v in res.items() if k != "spec"}
    report["target"] = str(a.target)
    out.with_suffix(".match.json").write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps({
        "target": a.target,
        "note": res["note"], "f0_hz": res["f0_hz"],
        "harmonicity": res["harmonicity"],
        "best": res["ranking"][0],
        "verified_distance": res["verified_distance"],
        "confidence": res["confidence"],
    }, indent=2))
    print(f"\nwrote {out.with_suffix('.af')} and {out.with_suffix('.match.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
