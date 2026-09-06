#!/usr/bin/env python3
"""Tile the 10-minute lullaby loop body into a 20-minute sleep file.

Supply a rendered, seamless, grid-aligned 10-minute *body* (no fades). Here we lay two copies
end to end with a short equal-power crossfade at the seam (to smooth the
reverb tail into the next loop), then apply one 6 s fade-in at the very start
and a long 30 s fade-out at the very end. Output is 16-bit (ample for a sleep
track and half the size).

    python3 scripts/build_lullaby_20min.py \
        INPUT.wav OUTPUT.wav
"""
import argparse
import sys
import wave
from pathlib import Path

import numpy as np

XFADE_S = 3.0
FADE_IN_S = 6.0
FADE_OUT_S = 30.0


def read_wav(path: str):
    with wave.open(path) as w:
        sr, ch, sw, n = (w.getframerate(), w.getnchannels(),
                         w.getsampwidth(), w.getnframes())
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8)
             | (b[:, 2].astype(np.int32) << 16))
        v = v - ((v >> 23) & 1) * (1 << 24)
        x = v / float(1 << 23)
    elif sw == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float64) / (2.0 ** 31)
    else:
        raise ValueError(f"sample width {sw*8}-bit unsupported")
    return x.reshape(-1, ch), sr


def write_wav16(path: str, x: np.ndarray, sr: int):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    src, dst = args.source, args.output
    body, sr = read_wav(src)
    xf = int(XFADE_S * sr)
    t = np.linspace(0, 1, xf)[:, None]
    ep_in, ep_out = np.sin(t * np.pi / 2), np.cos(t * np.pi / 2)
    seam = body[-xf:] * ep_out + body[:xf] * ep_in     # loop-point crossfade
    out = np.concatenate([body[:-xf], seam, body[xf:]])  # = 2*len(body) - xf
    fi, fo = int(FADE_IN_S * sr), int(FADE_OUT_S * sr)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    write_wav16(dst, out, sr)
    dur = len(out) / sr
    print(f"wrote {dst}: {dur/60:.1f} min ({dur:.0f}s), {sr} Hz, "
          f"peak {np.abs(out).max():.3f}, "
          f"{Path(dst).stat().st_size/1e6:.0f} MB")


if __name__ == "__main__":
    main(sys.argv[1:])
