"""Content-addressed sample layer support.

The synthesis-only ceiling ends here, without breaking determinism: a spec
never embeds audio — it names a file and pins its SHA-256. At render time
the engine locates the file (search paths or in-memory registry), verifies
the hash byte-for-byte, and fails loudly on any mismatch. Same spec + same
sample bytes = same output, forever; a swapped or corrupted sample can
never silently change a render. The pinned hash participates in the spec
hash, so sample identity is part of asset identity.

Supported: WAV PCM 16/24/32-bit, any channel count (mono-mixed), any rate
(deterministically resampled with polyphase filtering).
"""
from __future__ import annotations

import hashlib
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from .schema import SpecError

SAMPLE_PATHS: list[Path] = [Path("samples")]
_REGISTRY: dict[str, bytes] = {}
_CACHE: dict = {}


def add_sample_path(path) -> None:
    p = Path(path)
    if p not in SAMPLE_PATHS:
        SAMPLE_PATHS.insert(0, p)


def register_sample(name: str, data: bytes) -> str:
    """In-memory sample (pipelines, tests). Returns its sha256."""
    _REGISTRY[name] = data
    return hashlib.sha256(data).hexdigest()


def _find_bytes(name: str) -> bytes:
    if name in _REGISTRY:
        return _REGISTRY[name]
    for base in SAMPLE_PATHS:
        p = Path(base) / name
        if p.exists():
            return p.read_bytes()
    raise SpecError(
        f"sample '{name}' not found (searched registry + "
        f"{[str(p) for p in SAMPLE_PATHS]}); add its directory with "
        f"audioforge.samples.add_sample_path(...)")


def _decode_wav(data: bytes) -> tuple[np.ndarray, int]:
    import io
    with wave.open(io.BytesIO(data)) as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        width = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        a = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (a[:, 0].astype(np.int32) | (a[:, 1].astype(np.int32) << 8)
             | (a[:, 2].astype(np.int32) << 16))
        v = v - ((v >> 23) & 1) * (1 << 24)
        x = v.astype(np.float64) / float(1 << 23)
    elif width == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float64) / float(1 << 31)
    else:
        raise SpecError(f"sample: unsupported bit width {width * 8}")
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def load_sample_multi(name: str, sha256: str, target_sr: int):
    """Like load_sample but preserves channels: returns (n,) mono or
    (n, ch). Same content-addressing discipline: bytes verified, mismatch
    refuses naming both hashes."""
    data = _find_bytes(name)
    sha = hashlib.sha256(data).hexdigest()
    if sha != sha256.lower():
        raise SpecError(
            f"sample '{name}': content hash mismatch — spec pins "
            f"{sha256[:16]}…, file is {sha[:16]}…. Deterministic "
            f"rendering refuses to guess.")
    key = ("multi", sha, target_sr)
    if key in _CACHE:
        return _CACHE[key]
    x, sr, ch = _decode_wav_keep_channels(data)
    if sr != target_sr:
        from .sampler import _sinc_read
        ratio = sr / target_sr
        n_out = int(x.shape[0] / ratio)
        pos = np.arange(n_out) * ratio
        if x.ndim == 1:
            x = _sinc_read(x, pos)
        else:
            x = np.stack([_sinc_read(x[:, c], pos)
                          for c in range(x.shape[1])], axis=1)
    _CACHE[key] = x
    return x


def _decode_wav_keep_channels(data: bytes):
    import io as _io
    import wave as _wave
    with _wave.open(_io.BytesIO(data)) as w:
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
        x = x.reshape(-1, ch)
    return x, sr, ch


def load_sample(name: str, expected_sha256: str, target_sr: int,
                pitch_st: float = 0.0) -> np.ndarray:
    """Locate, hash-verify, decode, resample. Cached per (sha, sr, pitch)."""
    data = _find_bytes(name)
    sha = hashlib.sha256(data).hexdigest()
    if sha != expected_sha256.lower():
        raise SpecError(
            f"sample '{name}': content hash mismatch — spec pins "
            f"{expected_sha256[:16]}…, file is {sha[:16]}…. The sample on "
            f"disk is not the one this asset was authored against; "
            f"deterministic rendering refuses to guess.")
    key = (sha, target_sr, round(pitch_st, 4))
    if key in _CACHE:
        return _CACHE[key]
    x, sr = _decode_wav(data)
    ratio = (sr / target_sr) * 2.0 ** (pitch_st / 12.0)
    frac = Fraction(ratio).limit_denominator(2000)
    if frac != 1:
        x = resample_poly(x, frac.denominator, frac.numerator)
    _CACHE[key] = x
    return x


def ingest(directory, recursive: bool = True) -> list[dict]:
    """Catalog a folder of WAVs: hash, decode stats, a one-shot/loop guess,
    and a ready-to-paste DSL snippet per file. Registers the directory as a
    sample search path so the snippets work immediately."""
    base = Path(directory)
    add_sample_path(base)
    pattern = "**/*.wav" if recursive else "*.wav"
    out = []
    for p in sorted(base.glob(pattern)):
        data = p.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        try:
            x, sr = _decode_wav(data)
        except Exception as e:
            out.append({"file": p.name, "sha256": sha,
                        "error": f"undecodable: {e}"})
            continue
        dur = x.size / sr
        peak_db = 20.0 * np.log10(max(np.max(np.abs(x)), 1e-9))
        spec = np.abs(np.fft.rfft(x[:min(x.size, sr * 4)]))
        freqs = np.fft.rfftfreq(min(x.size, sr * 4), 1 / sr)
        centroid = float((spec * freqs).sum() / max(spec.sum(), 1e-12))
        tail = np.sqrt(np.mean(x[-max(1, x.size // 10):] ** 2))
        head = np.sqrt(np.mean(x[:max(1, x.size // 10)] ** 2))
        guess = "loop" if (dur > 1.5 and tail > 0.3 * head) else "one_shot"
        name = p.stem.replace("-", "_").replace(" ", "_")
        snippet = (
            f'layer {name} : sample {{\n'
            f'  file: "{p.name}"\n'
            f'  sha256: "{sha}"\n'
            + ('  pattern: X.......X.......\n' if guess == "one_shot"
               else '  start: 0s\n')
            + f'  gain: -6db\n}}')
        out.append({"file": p.name, "sha256": sha, "duration_s": round(dur, 3),
                    "sample_rate": sr, "peak_dbfs": round(peak_db, 1),
                    "spectral_centroid_hz": round(centroid),
                    "guess": guess, "snippet": snippet})
    return out
