"""Synthesis primitives. All functions are pure: same args -> same samples.

Internal processing is float64 mono; stereo is decided at mixdown.
"""
from __future__ import annotations

import numpy as np

from .curves import PHYSICAL_MODEL_OSCILLATORS

TWO_PI = 2.0 * np.pi

NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_to_freq(note: str) -> float:
    """'A4' -> 440.0, 'C#3' -> 138.59..., 'Eb5' supported."""
    name = note[0].upper()
    rest = note[1:]
    semitone = NOTE_OFFSETS[name]
    if rest and rest[0] in "#b":
        semitone += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    octave = int(rest)
    midi = (octave + 1) * 12 + semitone
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def freq_to_midi(freq: float) -> float:
    """Inverse of the 12-TET A4=440 mapping used by note_to_freq (one definition)."""
    return 69.0 + 12.0 * np.log2(freq / 440.0)


def _phase(freq: float, n: int, sr: int, phase0: float = 0.0) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sr
    return TWO_PI * freq * t + phase0


def osc(shape: str, freq: float, n: int, sr: int, *,
        detune_cents: float = 0.0, phase0: float = 0.0,
        fm_ratio: float = 2.0, fm_index: float = 0.0,
        rng=None, voice: dict | None = None) -> np.ndarray:
    """Oscillators, bandlimited to Nyquist.

    shapes: sine | saw | square | triangle | fm | organ | pad | pluck | modal
    `rng`   seeded Generator (required by pad/pluck/modal).
    `voice` instrument parameters (unison, spread_cents, bandwidth_cents,
            damping, brightness, pluck_pos, material, mode_decay_s).
    """
    from .plugins import OSCILLATORS
    f = freq * 2.0 ** (detune_cents / 1200.0)
    v = voice or {}
    if shape in ("pad", "pluck", "modal") and rng is None:
        raise ValueError(f"oscillator '{shape}' needs a seeded rng")
    if v.get("unison", 1) > 1 and shape in ("sine", "saw", "square",
                                            "triangle", "organ", "fm"):
        vv = dict(v); vv["unison"] = 1
        return unison(shape, freq, n, sr, int(v["unison"]),
                      float(v.get("spread_cents", 18.0)), phase0,
                      detune_cents=detune_cents, fm_ratio=fm_ratio,
                      fm_index=fm_index, rng=rng, voice=vv)
    if shape == "pad":
        return padsynth(f, n, sr, rng,
                        harmonics=int(v.get("harmonics", 48)),
                        bandwidth_cents=float(v.get("bandwidth_cents", 40.0)),
                        phase0=phase0)
    if shape == "pluck":
        return pluck(f, n, sr, rng,
                     damping=float(v.get("damping", 0.5)),
                     brightness=float(v.get("brightness", 0.6)),
                     pluck_pos=float(v.get("pluck_pos", 0.28)))
    if shape == "modal":
        return modal(f, n, sr, rng,
                     material=v.get("material", "bell"),
                     mode_decay_s=v.get("mode_decay_s"),
                     modes=v.get("modes"))
    if shape == "morph":
        scan = v["_scan_env"] if "_scan_env" in v else v.get("scan", 0.0)
        return morph_osc(f, n, sr, scan, phase0=phase0)
    if shape == "bowed":
        from ._native import bowed_native
        return bowed_native(f, n, sr,
                            pressure=float(v.get("pressure", 0.6)),
                            position=float(v.get("bow_position", 0.13)),
                            brightness=float(v.get("brightness", 0.6)))
    if shape in ("struck", "sympathetic"):
        if rng is None:
            raise ValueError(f"oscillator '{shape}' needs a seeded rng "
                             "(strike excitation)")
        from ._native import biquad
        L = max(int(sr / f), 4)
        b_c = 0.15 + 0.85 * float(np.clip(v.get("brightness", 0.6), 0.0, 1.0))
        # seeded strike burst, brightness-colored (as pluck) and amplitude-
        # scaled by `strike` (the played string's hit)
        exc = rng.uniform(-1.0, 1.0, n)
        exc = biquad(exc, [b_c], [1.0, -(1.0 - b_c)])
        exc[L + 2:] = 0.0                                  # burst at the front
        exc *= 0.4 + 0.6 * float(np.clip(v.get("strike", 0.7), 0.0, 1.0))
        if shape == "struck":
            from ._native import struck_native
            return struck_native(exc, n, sr, f,
                                 damping=float(v.get("damping", 0.5)),
                                 brightness=float(v.get("brightness", 0.6)),
                                 tension=float(v.get("tension", 0.5)))
        from ._native import sympathetic_native
        return sympathetic_native(exc, n, sr, f,
                                  coupling=float(v.get("coupling", 0.5)),
                                  buzz=float(v.get("buzz", 0.2)),
                                  damping=float(v.get("damping", 0.4)),
                                  brightness=float(v.get("brightness", 0.6)))
    if shape == "brass":
        from ._native import brass_native
        if rng is None:
            raise ValueError("oscillator 'brass' needs a seeded rng "
                             "(breath turbulence)")
        return brass_native(f, n, sr,
                            pressure=float(v.get("pressure", 0.6)),
                            brightness=float(v.get("brightness", 0.6)),
                            lip=float(v.get("lip", 0.5)),
                            noise=rng.standard_normal(n))
    if shape == "blown":
        from ._native import blown_native
        if rng is None:
            raise ValueError("oscillator 'blown' needs a seeded rng "
                             "(breath turbulence)")
        return blown_native(f, n, sr,
                            pressure=float(v.get("pressure", 0.6)),
                            brightness=float(v.get("brightness", 0.6)),
                            noise=rng.standard_normal(n))
    if shape in OSCILLATORS:
        return OSCILLATORS[shape](f, n, sr)
    if shape in ("saw", "square", "triangle"):
        return _classic_acc(shape, f, n, sr, phase0, 1.0, np.zeros(n))
    ph = _phase(f, n, sr, phase0)
    if shape == "organ":
        return organ(f, n, sr, phase0)
    if shape == "sine":
        return np.sin(ph)
    if shape == "fm":
        mod = np.sin(_phase(f * fm_ratio, n, sr))
        return np.sin(ph + fm_index * mod)
    raise ValueError(f"unknown oscillator shape: {shape!r}")


def _classic_acc(shape: str, f: float, n: int, sr: int, phase0: float,
                 amp: float, out: np.ndarray) -> np.ndarray:
    """out += amp * bandlimited saw/square/triangle; returns out.

    Bandlimited-to-Nyquist via single-cycle wavetable built by inverse FFT
    (exact Fourier series, every harmonic below Nyquist), played back with
    linear interpolation by a native loop (one pass instead of ~10 numpy
    passes). A C1 saw carries its full ~700 harmonics."""
    from ._native import wavetable_acc
    k_max = max(1, int((sr / 2.0) / max(f, 1e-9)))
    return wavetable_acc(_classic_table(shape, k_max), TWO_PI * f, phase0,
                         sr, n, amp, out)


ORGAN_DRAWBARS = [(0.5, 0.55), (1.0, 1.0), (1.5, 0.35), (2.0, 0.6),
                  (3.0, 0.25), (4.0, 0.3), (5.0, 0.12), (6.0, 0.15),
                  (8.0, 0.1)]


def organ(freq: float, n: int, sr: int, phase0: float = 0.0) -> np.ndarray:
    """Drawbar-style additive organ — the sustained, churchy timbre used by
    the cinematic presets. Pure sums of sines: fully deterministic."""
    out = np.zeros(n, dtype=np.float64)
    nyq = sr / 2.0
    for ratio, amp in ORGAN_DRAWBARS:
        f = freq * ratio
        if f >= nyq:
            continue
        out += amp * np.sin(_phase(f, n, sr, phase0 * ratio))
    peak = np.max(np.abs(out)) or 1.0
    return out / peak


def breakpoints(points: list[list[float]], n: int, sr: int,
                log_domain: bool = False) -> np.ndarray:
    """Sample-accurate breakpoint envelope. points = [[time_s, value], ...].
    Linear interpolation (in log domain for frequencies). Holds edges."""
    pts = sorted(points, key=lambda p: p[0])
    times = np.array([p[0] for p in pts], dtype=np.float64) * sr
    vals = np.array([p[1] for p in pts], dtype=np.float64)
    x = np.arange(n, dtype=np.float64)
    if log_domain:
        vals = np.log(np.maximum(vals, 1e-9))
        return np.exp(np.interp(x, times, vals))
    return np.interp(x, times, vals)


def pitch_sweep(shape: str, f_start: float, f_end: float, n: int, sr: int,
                curve: str = "exp") -> np.ndarray:
    """Oscillator with frequency glide (essential for whooshes, risers, drops)."""
    t = np.arange(n, dtype=np.float64) / sr
    dur = max(n / sr, 1e-9)
    if curve == "exp" and f_start > 0 and f_end > 0:
        freqs = f_start * (f_end / f_start) ** (t / dur)
    else:
        freqs = f_start + (f_end - f_start) * (t / dur)
    phase = TWO_PI * np.cumsum(freqs) / sr
    if shape == "sine":
        return np.sin(phase)
    if shape == "saw":
        return 2.0 * ((phase / TWO_PI) % 1.0) - 1.0
    if shape == "square":
        return np.sign(np.sin(phase))
    if shape == "triangle":
        return 2.0 * np.abs(2.0 * ((phase / TWO_PI) % 1.0) - 1.0) - 1.0
    raise ValueError(f"unsupported sweep shape: {shape!r}")


def noise(color: str, n: int, rng: np.random.Generator) -> np.ndarray:
    """white | pink | brown noise, deterministic via injected RNG."""
    w = rng.standard_normal(n)
    if color == "white":
        out = w
    elif color == "pink":
        # Voss-McCartney-ish via FFT 1/f shaping (deterministic, vectorized)
        spec = np.fft.rfft(w)
        f = np.arange(spec.size, dtype=np.float64)
        f[0] = 1.0
        spec /= np.sqrt(f)
        out = np.fft.irfft(spec, n)
    elif color == "brown":
        out = np.cumsum(w)
        out -= out.mean()
    else:
        raise ValueError(f"unknown noise color: {color!r}")
    peak = np.max(np.abs(out)) or 1.0
    return out / peak


def adsr(n: int, sr: int, attack: float, decay: float,
         sustain: float, release: float, curve: float = 3.0) -> np.ndarray:
    """Exponential-ish ADSR. Times in seconds; sustain is a level 0..1.
    Release is carved out of the tail of the n-sample window."""
    a = min(int(attack * sr), n)
    d = min(int(decay * sr), max(n - a, 0))
    r = min(int(release * sr), max(n - a - d, 0))
    s = max(n - a - d - r, 0)
    env = np.zeros(n, dtype=np.float64)
    pos = 0
    if a:
        x = np.linspace(0.0, 1.0, a, endpoint=False)
        env[pos:pos + a] = 1.0 - np.exp(-curve * x) * (1.0 - x)  # fast rise
        env[pos:pos + a] = x ** (1.0 / curve)
        pos += a
    if d:
        x = np.linspace(0.0, 1.0, d, endpoint=False)
        env[pos:pos + d] = 1.0 + (sustain - 1.0) * (x ** (1.0 / curve))
        pos += d
    if s:
        env[pos:pos + s] = sustain
        pos += s
    if r:
        x = np.linspace(0.0, 1.0, r, endpoint=True)
        start = env[pos - 1] if pos else sustain
        env[pos:pos + r] = start * (1.0 - x) ** curve
    return env


def note_adsr(gate_n: int, sr: int, attack: float, decay: float,
              sustain: float, release: float, curve: float = 3.0) -> np.ndarray:
    """Hold a note until note-off, then release from its actual current level.

    Unlike a fixed-duration effect envelope, release never consumes gate time.
    An early note-off interrupts attack/decay without accelerating either stage.
    """
    gate_n = max(0, int(gate_n))
    release_n = max(0, int(round(release * sr)))
    attack_n = max(0, int(round(attack * sr)))
    decay_n = max(0, int(round(decay * sr)))
    env = np.full(gate_n + release_n, sustain, dtype=np.float64)
    a = min(attack_n, gate_n)
    if a:
        env[:a] = (np.arange(a) / attack_n) ** (1.0 / curve)
    d = min(decay_n, max(0, gate_n - attack_n))
    if d:
        env[attack_n:attack_n + d] = (
            1.0 + (sustain - 1.0) * (np.arange(d) / decay_n) ** (1.0 / curve))
    if release_n:
        level = env[gate_n - 1] if gate_n else 0.0
        env[gate_n:] = level * (1.0 - np.linspace(0, 1, release_n)) ** curve
    return env


# ------------------------------------------------------------- v2.1 voices
_TABLE_CACHE: dict = {}
_TABLE_SIZE = 8192
_GOLDEN = 0.6180339887498949


def _classic_table(shape: str, k_max: int) -> np.ndarray:
    """Single-cycle wavetable: exact Fourier series of saw/square/triangle
    with harmonics 1..k_max (capped by table resolution). Deterministic,
    cached per (shape, k_max)."""
    k_max = min(k_max, _TABLE_SIZE // 2 - 1)
    key = (shape, k_max)
    if key in _TABLE_CACHE:
        return _TABLE_CACHE[key]
    spec = np.zeros(_TABLE_SIZE // 2 + 1, dtype=np.complex128)
    if shape == "saw":
        k = np.arange(1, k_max + 1)
        spec[k] = -0.5j * (2.0 / np.pi) / k * _TABLE_SIZE
    elif shape == "square":
        k = np.arange(1, k_max + 1, 2)
        spec[k] = -0.5j * (4.0 / np.pi) / k * _TABLE_SIZE
    else:  # triangle
        k = np.arange(1, k_max + 1, 2)
        signs = np.where((np.arange(k.size) % 2) == 0, 1.0, -1.0)
        spec[k] = -0.5j * (8.0 / np.pi ** 2) * signs / (k * k) * _TABLE_SIZE
    table = np.fft.irfft(spec)
    _TABLE_CACHE[key] = table
    return table


def unison(shape: str, freq: float, n: int, sr: int, voices: int,
           spread_cents: float, phase0: float = 0.0, **osc_kw) -> np.ndarray:
    """Supersaw-style unison: `voices` detuned copies, golden-ratio phase
    offsets (decorrelated, fully deterministic — no RNG needed), center
    voice dominant. Works for any classic shape."""
    if voices <= 1:
        return osc(shape, freq, n, sr, phase0=phase0, **osc_kw)
    from .plugins import OSCILLATORS
    out = np.zeros(n, dtype=np.float64)
    norm = 0.0
    for i in range(voices):
        x = 2.0 * i / (voices - 1) - 1.0          # -1 .. +1
        det = spread_cents * (0.6 * x + 0.4 * x ** 3)
        amp = 1.0 if abs(x) < 1e-9 else 0.72
        ph_i = phase0 + 2.0 * np.pi * ((i * _GOLDEN) % 1.0)
        kw = dict(osc_kw)
        kw["detune_cents"] = kw.get("detune_cents", 0.0) + det
        if (shape in ("saw", "square", "triangle") and shape not in OSCILLATORS
                and kw.get("voice", {}).get("unison", 1) <= 1):
            f_i = freq * 2.0 ** (kw["detune_cents"] / 1200.0)
            _classic_acc(shape, f_i, n, sr, ph_i, amp, out)
        else:
            out += amp * osc(shape, freq, n, sr, phase0=ph_i, **kw)
        norm += amp * amp
    return out / np.sqrt(norm)


_PAD_AMP_CACHE: dict = {}


def _pad_amplitudes(freq: float, sr: int, harmonics: int,
                    bandwidth_cents: float, profile_exp: float, N: int):
    """PADsynth magnitude spectrum and its nonzero bins, cached: every note of
    a pad track at the same pitch shares it (only the phases are per-note)."""
    key = (freq, sr, harmonics, bandwidth_cents, profile_exp, N)
    hit = _PAD_AMP_CACHE.get(key)
    if hit is not None:
        return hit
    nyq = sr / 2.0
    amp = np.zeros(N // 2 + 1)
    bins = np.arange(N // 2 + 1)
    bw_ratio = 2.0 ** (bandwidth_cents / 1200.0) - 1.0
    for i in range(1, harmonics + 1):
        fi = freq * i
        if fi >= nyq * 0.95:
            break
        a_i = 1.0 / (i ** profile_exp)
        bw_hz = max(bw_ratio * fi, 1e-3)
        center = fi * N / sr
        sigma = (bw_hz * N / sr) / 2.0
        lo = max(0, int(center - 5 * sigma))
        hi = min(N // 2, int(center + 5 * sigma) + 1)
        x = (bins[lo:hi] - center) / sigma
        amp[lo:hi] += a_i * np.exp(-x * x)
    nz = np.flatnonzero(amp[1:]) + 1           # bin 0 is zeroed anyway
    if len(_PAD_AMP_CACHE) > 256:
        _PAD_AMP_CACHE.clear()
    _PAD_AMP_CACHE[key] = (nz, amp[nz])
    return _PAD_AMP_CACHE[key]


def padsynth(freq: float, n: int, sr: int, rng, harmonics: int = 48,
             bandwidth_cents: float = 40.0, profile_exp: float = 1.0,
             phase0: float = 0.0) -> np.ndarray:
    """PADsynth (Nasca, public domain): each harmonic is a Gaussian-widened
    band in a long spectrum; one inverse FFT yields a perfectly looping
    wavetable with a lush ensemble character. The random bin phases come
    from the injected seeded RNG, so output is fully deterministic."""
    N = 1 << 18                                   # ~5.5 s table at 48 kHz
    nz, amp_nz = _pad_amplitudes(freq, sr, harmonics, bandwidth_cents,
                                 profile_exp, N)
    phases = rng.uniform(0.0, 2.0 * np.pi, N // 2 + 1)   # full draw: the
    spec = np.zeros(N // 2 + 1, dtype=np.complex64)      # RNG stream is
    spec[nz] = amp_nz * np.exp(1j * phases[nz])          # unchanged
    # float32 inverse FFT: half the cost of the per-note 2^18-point
    # transform; the table is peak-normalized, so the error is ~1e-7
    # absolute (about -140 dB)
    import scipy.fft as sfft
    table = sfft.irfft(spec, N).astype(np.float64)
    table /= max(np.max(np.abs(table)), 1e-12)
    start = int((phase0 / (2.0 * np.pi)) * N) % N
    if start + n <= N:
        return table[start:start + n].copy()
    reps = int(np.ceil((start + n) / N)) + 1
    return np.tile(table, reps)[start:start + n]


def _sparse_feedback(x: np.ndarray, taps: dict[int, float]) -> np.ndarray:
    """y[n] = x[n] + sum_l taps[l] * y[n-l] (taps summed in dict order):
    one native pass over the recurrence."""
    from ._native import sparse_feedback
    return sparse_feedback(x, taps)


def pluck(freq: float, n: int, sr: int, rng, damping: float = 0.5,
          brightness: float = 0.6, pluck_pos: float = 0.28) -> np.ndarray:
    """Extended Karplus-Strong plucked string: seeded noise burst excitation
    -> pick-position comb -> brightness lowpass -> fractionally tuned
    recirculating delay with two-tap loss filter (Jaffe/Smith lineage)."""
    from ._native import biquad
    L_f = max(sr / freq - 0.5, 3.0)
    L = int(L_f)
    fr = L_f - L
    exc = rng.uniform(-1.0, 1.0, L + 2)
    b_c = 0.15 + 0.85 * np.clip(brightness, 0.0, 1.0)
    exc = biquad(exc, [b_c], [1.0, -(1.0 - b_c)])          # excitation color
    pp = max(1, int(np.clip(pluck_pos, 0.02, 0.5) * L))
    exc = exc - np.concatenate([np.zeros(pp), exc[:-pp]])  # pick position
    rho = 0.985 + 0.0149 * np.clip(damping, 0.0, 1.0)
    x = np.zeros(n)
    x[:min(exc.size, n)] = exc[:n]
    y = _sparse_feedback(x, {L: rho * (1 - fr) / 2.0,
                             L + 1: rho / 2.0,
                             L + 2: rho * fr / 2.0})
    return y / max(np.max(np.abs(y)), 1e-12)


# (ratio, amplitude, t60 share) — higher partials decay faster, as in the
# modal-analysis literature. 'bell' follows the classic minor-third church
# bell profile (hum/prime/tierce/quint/nominal...).
MODAL_MATERIALS = {
    "bell":    [(0.5, 0.55, 1.6), (1.0, 1.0, 1.0), (1.2, 0.8, 0.65),
                (1.5, 0.5, 0.5), (2.0, 0.65, 0.4), (2.67, 0.32, 0.3),
                (3.01, 0.22, 0.22), (4.07, 0.14, 0.16), (5.43, 0.07, 0.1)],
    "glass":   [(1.0, 1.0, 1.0), (2.32, 0.55, 0.6), (4.25, 0.3, 0.35),
                (6.63, 0.18, 0.22), (9.38, 0.1, 0.14)],
    "marimba": [(1.0, 1.0, 1.0), (3.93, 0.42, 0.25), (9.94, 0.16, 0.1)],
    "gong":    [(1.0, 0.8, 1.0), (1.52, 1.0, 0.9), (2.36, 0.7, 0.72),
                (2.71, 0.55, 0.6), (3.46, 0.45, 0.5), (4.18, 0.3, 0.4),
                (5.05, 0.2, 0.3), (6.27, 0.12, 0.22)],
    "steel":   [(1.0, 1.0, 0.8), (2.76, 0.7, 0.5), (5.4, 0.45, 0.3),
                (8.93, 0.3, 0.18), (13.3, 0.18, 0.1)],
}


def modal(freq: float, n: int, sr: int, rng, material: str = "bell",
          mode_decay_s: float | None = None, strike: float = 0.35,
          modes: list | None = None) -> np.ndarray:
    """Modal synthesis: bank of exponentially decaying sinusoids (frequency,
    amplitude, decay triplets) plus a short seeded strike transient.
    `modes` overrides the material table: [[ratio, amp, t60_share], ...] —
    user-defined materials, bespoke percussion from a list of numbers."""
    modes = modes if modes is not None else MODAL_MATERIALS[material]
    t = np.arange(n) / sr
    base_t60 = mode_decay_s if mode_decay_s else min(n / sr, 6.0)
    out = np.zeros(n)
    for j, (ratio, a, t60f) in enumerate(modes):
        fi = freq * ratio
        if fi >= sr * 0.45:
            continue
        tau = max(base_t60 * t60f, 0.01) / 6.91
        ph = 2.0 * np.pi * ((j * _GOLDEN) % 1.0)
        out += a * np.exp(-t / tau) * np.sin(2.0 * np.pi * fi * t + ph)
    ns = max(8, int(0.004 * sr))
    if ns < n and strike > 0:
        burst = rng.uniform(-1.0, 1.0, ns) * np.linspace(1.0, 0.0, ns) ** 2
        out[:ns] += strike * burst
    return out / max(np.max(np.abs(out)), 1e-12)


# ------------------------------------------------- v2.4 performance realism
def glide_ratio_env(f_prev: float, f_target: float, n: int, sr: int,
                    glide_s: float) -> np.ndarray:
    """Pitch ratio envelope for portamento: exponential (constant cents/s)
    slide from the previous note's pitch to this one, then steady."""
    g = max(1, min(int(glide_s * sr), n))
    env = np.ones(n)
    if f_prev and f_prev > 0 and abs(f_prev - f_target) > 1e-9:
        start_ratio = f_prev / f_target
        env[:g] = start_ratio ** (1.0 - np.arange(g) / g)
    return env


def vibrato_ratio_env(n: int, sr: int, rate_hz: float, depth_cents: float,
                      delay_s: float = 0.25, fade_s: float = 0.35) -> np.ndarray:
    """Pitch ratio envelope for vibrato: sinusoidal, entering after a delay
    with a fade-in (the way played vibrato behaves, not LFO-from-zero)."""
    t = np.arange(n) / sr
    amount = np.clip((t - delay_s) / max(fade_s, 1e-3), 0.0, 1.0)
    cents = depth_cents * amount * np.sin(2.0 * np.pi * rate_hz * t)
    return 2.0 ** (cents / 1200.0)


def osc_dynamic(shape: str, freq_env: np.ndarray, n: int, sr: int, *,
                f_nominal: float, phase0: float = 0.0, fm_ratio: float = 2.0,
                fm_index: float = 0.0, rng=None,
                voice: dict | None = None) -> np.ndarray:
    """Time-varying-pitch rendering (glide/vibrato) via phase integration
    or variable-rate table reads. Supports the oscillator voices; the
    physical models (pluck/modal) ignore pitch envelopes by design."""
    v = voice or {}
    if v.get("unison", 1) > 1 and shape in ("sine", "saw", "square",
                                            "triangle", "organ", "fm"):
        # unison survives pitch envelopes: detuned copies of the envelope,
        # golden-ratio phase offsets, center voice dominant (mirrors unison())
        voices = int(v["unison"])
        spread = float(v.get("spread_cents", 18.0))
        vv = dict(v); vv["unison"] = 1
        out = np.zeros(n)
        norm = 0.0
        for i in range(voices):
            x = 2.0 * i / (voices - 1) - 1.0
            det = 2.0 ** ((spread * (0.6 * x + 0.4 * x ** 3)) / 1200.0)
            amp = 1.0 if abs(x) < 1e-9 else 0.72
            ph_i = phase0 + 2.0 * np.pi * ((i * _GOLDEN) % 1.0)
            out += amp * osc_dynamic(shape, freq_env * det, n, sr,
                                     f_nominal=f_nominal * det, phase0=ph_i,
                                     fm_ratio=fm_ratio, fm_index=fm_index,
                                     rng=rng, voice=vv)
            norm += amp * amp
        return out / np.sqrt(norm)
    if shape == "morph":
        scan = v["_scan_env"] if "_scan_env" in v else v.get("scan", 0.0)
        return morph_osc(f_nominal, n, sr, scan, phase0=phase0,
                         freq_env=freq_env)
    phase = phase0 + 2.0 * np.pi * np.cumsum(freq_env) / sr
    if shape == "sine":
        return np.sin(phase)
    if shape == "fm":
        mod = np.sin(phase * fm_ratio) * fm_index
        return np.sin(phase + mod)
    if shape == "organ":
        out = np.zeros(n)
        nyq = sr / 2.0
        fmax = float(np.max(freq_env))
        for ratio, amp in ORGAN_DRAWBARS:
            if fmax * ratio >= nyq:
                continue
            out += amp * np.sin(phase * ratio)
        return out / max(np.max(np.abs(out)), 1e-12)
    if shape in ("saw", "square", "triangle"):
        k_max = max(1, int((sr / 2.0) / max(float(np.max(freq_env)), 1e-9)))
        table = _classic_table(shape, k_max)
        pos = (phase / (2.0 * np.pi)) * table.size
        i0 = np.floor(pos).astype(np.int64) % table.size
        fr = pos - np.floor(pos)
        return table[i0] * (1.0 - fr) + table[(i0 + 1) % table.size] * fr
    if shape == "pad":
        N = 1 << 18
        table = padsynth(f_nominal, N, sr, rng,
                         harmonics=int(v.get("harmonics", 48)),
                         bandwidth_cents=float(v.get("bandwidth_cents", 40.0)))
        pos = np.cumsum(freq_env / f_nominal)
        i0 = np.floor(pos).astype(np.int64) % N
        fr = pos - np.floor(pos)
        return table[i0] * (1.0 - fr) + table[(i0 + 1) % N] * fr
    if shape in PHYSICAL_MODEL_OSCILLATORS:
        # Physical models cannot retune their resonators mid-note. The pitch
        # envelope is realised by deterministic variable-rate (varispeed)
        # reading of the statically rendered voice — tape semantics: the
        # scheduled duration is preserved and the instantaneous rate follows
        # freq_env / f_nominal. Linear-interpolated reads keep it exact and
        # byte-reproducible.
        rate = freq_env / max(float(f_nominal), 1e-9)
        pos = np.empty(n)
        if n:
            pos[0] = 0.0
            np.cumsum(rate[:-1], out=pos[1:])
        src_n = int(np.ceil(pos[-1] if n else 0.0)) + 2
        src = osc(shape, f_nominal, src_n, sr, phase0=phase0,
                  fm_ratio=fm_ratio, fm_index=fm_index, rng=rng, voice=voice)
        i0 = np.clip(np.floor(pos).astype(np.int64), 0, src_n - 2)
        fr = pos - i0
        return src[i0] * (1.0 - fr) + src[i0 + 1] * fr
    # remaining non-oscillator voices (pluck/modal): pitch envelopes not
    # applicable; render static
    return osc(shape, f_nominal, n, sr, phase0=phase0, fm_ratio=fm_ratio,
               fm_index=fm_index, rng=rng, voice=voice)


def vel_brightness_cutoff(vel: float, f0: float, sr: int,
                          amount: float) -> float | None:
    """Velocity -> timbre: softer notes are duller, not just quieter.
    Returns a lowpass cutoff, or None when fully open. Mapping: at vel=1
    the filter is essentially open; lower velocities pull the cutoff
    toward a few harmonics above the fundamental, scaled by `amount`."""
    if amount <= 0.0:
        return None
    v = float(np.clip(vel, 0.05, 1.2))
    played = f0 * 2.0 ** (1.0 + 5.0 * min(v, 1.0))   # dull..bright
    open_hz = sr * 0.45
    cutoff = open_hz - amount * (open_hz - min(played, open_hz))
    return None if cutoff >= open_hz * 0.98 else float(cutoff)


# --------------------------------------------------- v2.5 instrument classes
MORPH_BANK = ("sine", "triangle", "pulse", "saw", "square")


def _pulse_table(k_max: int) -> np.ndarray:
    """25%-duty pulse spectrum frame for the morph bank."""
    k_max = min(k_max, _TABLE_SIZE // 2 - 1)
    key = ("pulse", k_max)
    if key in _TABLE_CACHE:
        return _TABLE_CACHE[key]
    spec = np.zeros(_TABLE_SIZE // 2 + 1, dtype=np.complex128)
    k = np.arange(1, k_max + 1)
    amps = (2.0 / np.pi) * np.abs(np.sin(np.pi * k * 0.25)) / k
    spec[k] = -0.5j * amps * _TABLE_SIZE
    table = np.fft.irfft(spec)
    table /= max(np.max(np.abs(table)), 1e-12)
    _TABLE_CACHE[key] = table
    return table


def _morph_frames(k_max: int) -> list[np.ndarray]:
    out = []
    for name in MORPH_BANK:
        if name == "sine":
            t = _classic_table("saw", 1)            # single harmonic = sine
            out.append(t / max(np.max(np.abs(t)), 1e-12))
        elif name == "pulse":
            out.append(_pulse_table(k_max))
        else:
            t = _classic_table(name, k_max)
            out.append(t / max(np.max(np.abs(t)), 1e-12))
    return out


def morph_osc(freq: float, n: int, sr: int, scan, phase0: float = 0.0,
              freq_env: np.ndarray | None = None) -> np.ndarray:
    """Wavetable-morphing oscillator: `scan` (scalar or per-sample array,
    0..1) sweeps sine -> triangle -> pulse -> saw -> square, linearly
    interpolating between adjacent bandlimited frames."""
    fmax = float(np.max(freq_env)) if freq_env is not None else freq
    k_max = max(1, int((sr / 2.0) / max(fmax, 1e-9)))
    frames = _morph_frames(k_max)
    F = len(frames)
    if freq_env is not None:
        phase = phase0 + 2.0 * np.pi * np.cumsum(freq_env) / sr
    else:
        phase = _phase(freq, n, sr, phase0)
    pos = (phase / (2.0 * np.pi)) * _TABLE_SIZE
    i0 = np.floor(pos).astype(np.int64) % _TABLE_SIZE
    fr = pos - np.floor(pos)
    i1 = (i0 + 1) % _TABLE_SIZE
    s = np.clip(np.asarray(scan, dtype=np.float64), 0.0, 1.0) * (F - 1)
    a = np.minimum(s.astype(np.int64), F - 2)
    fb = s - a
    stack = np.stack(frames)                     # [F, table]
    wA = stack[a, i0] * (1 - fr) + stack[a, i1] * fr
    wB = stack[a + 1, i0] * (1 - fr) + stack[a + 1, i1] * fr
    return wA * (1 - fb) + wB * fb


def granular(src: np.ndarray, n: int, sr: int, rng, grain_s: float = 0.09,
             density: float = 35.0, pitch_spread_cents: float = 30.0,
             scatter: float = 0.5) -> np.ndarray:
    """Seeded grain cloud over a source buffer. Grain onset times, source
    positions, and per-grain pitch all come from one seeded stream drawn in
    a fixed order — a texture that shimmers but never changes between
    renders. scatter 0 = scan strictly through the source (time-stretch
    feel); 1 = grains anywhere."""
    g_n = max(64, int(grain_s * sr))
    win = np.hanning(g_n)
    num = max(1, int(density * n / sr))
    onsets = np.sort(rng.uniform(0, max(1, n - g_n), num)).astype(np.int64)
    out = np.zeros(n)
    span = max(1, src.size - 2 * g_n)
    for t0 in onsets:
        center = (t0 / max(1, n)) * span + g_n * 0.5
        pos = center + (rng.uniform(-1.0, 1.0)) * scatter * span * 0.5
        pos = float(np.clip(pos, 0.0, src.size - 2.0 * g_n - 2.0))
        rate = 2.0 ** (rng.uniform(-1.0, 1.0) * pitch_spread_cents / 1200.0)
        idx = pos + np.arange(g_n) * rate
        i0 = idx.astype(np.int64)
        frv = idx - i0
        grain = src[i0] * (1 - frv) + src[i0 + 1] * frv
        out[t0:t0 + g_n] += grain * win
    overlap = max(1.0, density * grain_s)
    out /= np.sqrt(overlap)
    peak = np.max(np.abs(out))
    return out / peak if peak > 1.0 else out
