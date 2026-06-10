"""Tier-2 spaces: Dattorro plate and a per-band-decay FDN hall.

Both are classic sample-sequential feedback topologies. Implementation
approach: with delay modulation omitted, each network is linear and
time-invariant, so its stereo impulse response is computed once by a tight
sequential loop (cost bounded by the tail length, cached per parameter set)
and then applied with FFT convolution. That preserves the published
topologies exactly while keeping rendering vectorized and dependency-free.

Plate: Dattorro 1997 ("in the style of Griesinger"), the published delay
lengths, diffusion coefficients, and output-tap tables, scaled from the
paper's 29761 Hz reference rate. The original's small delay-line modulation
is omitted (the LTI requirement); noted in the docs.

FDN: 8 coprime delay lines, Householder feedback matrix, per-line two-point
shelving loss filters that hit independent low-band and high-band RT60
targets — frequency-dependent decay, the signature of expensive halls.

Determinism: no randomness anywhere; fixed constants, fixed iteration order.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve

_IR_CACHE: dict = {}
_REF_SR = 29761.0

# Dattorro published constants (samples @ 29761 Hz)
_IN_APF = ((142, 0.750), (107, 0.750), (379, 0.625), (277, 0.625))
_TANK = {  # branch: (apf1_len, apf1_g, delay1, apf2_len, apf2_g, delay2)
    "a": (672, 0.70, 4453, 1800, 0.50, 3720),
    "b": (908, 0.70, 4217, 2656, 0.50, 3163),
}
# output taps: (buffer key, tap delay, sign); 0.6 overall factor
_TAPS_L = (("b_d1", 266, +1), ("b_d1", 2974, +1), ("b_ap2", 1913, -1),
           ("b_d2", 1996, +1), ("a_d1", 1990, -1), ("a_ap2", 187, -1),
           ("a_d2", 1066, -1))
_TAPS_R = (("a_d1", 353, +1), ("a_d1", 3627, +1), ("a_ap2", 1228, -1),
           ("a_d2", 2673, +1), ("b_d1", 2111, -1), ("b_ap2", 335, -1),
           ("b_d2", 121, -1))


def _plate_irs(sr: int, decay: float, damp: float, n_max: int):
    """Stereo impulse responses of the Dattorro tank. Sequential but only
    as long as the audible tail (capped), then cached."""
    decay = float(np.clip(decay, 0.1, 0.97))
    damp = float(np.clip(damp, 0.0, 0.95))
    # tail length: one branch traversal applies one `decay`; size for -80 dB
    R = sr / _REF_SR
    branch_s = (4453 + 3720) * R / sr
    t80 = 80.0 * branch_s / max(-20.0 * np.log10(decay), 0.4)
    ir_len = int(min(t80, 12.0) * sr)
    ir_len = min(ir_len, n_max)
    key = ("plate", sr, decay, damp, ir_len)
    if key in _IR_CACHE:
        return _IR_CACHE[key]

    def L(x):  # scale a reference-rate length to this sample rate
        return max(2, int(round(x * R)))

    bw = 0.9995  # input bandwidth (paper's example setting)

    in_apf = [{"buf": [0.0] * L(d), "i": 0, "g": g, "n": L(d)}
              for d, g in _IN_APF]
    tank = {}
    for br, (a1, g1, d1, a2, g2, d2) in _TANK.items():
        tank[br] = {
            "ap1": {"buf": [0.0] * L(a1), "i": 0, "g": g1, "n": L(a1)},
            "d1":  {"buf": [0.0] * L(d1), "i": 0, "n": L(d1)},
            "ap2": {"buf": [0.0] * L(a2), "i": 0, "g": g2, "n": L(a2)},
            "d2":  {"buf": [0.0] * L(d2), "i": 0, "n": L(d2)},
            "lp": 0.0,
        }

    def apf(st, x):
        # Schroeder allpass: v = x + g*z ; y = z - g*v  (unity magnitude)
        buf, i, g = st["buf"], st["i"], st["g"]
        z = buf[i]
        v = x + g * z
        buf[i] = v
        st["i"] = (i + 1) % st["n"]
        return z - g * v

    def push(st, x):
        buf, i = st["buf"], st["i"]
        out = buf[i]
        buf[i] = x
        st["i"] = (i + 1) % st["n"]
        return out

    def tap(st, d):
        return st["buf"][(st["i"] - 1 - d) % st["n"]]

    taps_l = [(br_key, L(d), s) for br_key, d, s in _TAPS_L]
    taps_r = [(br_key, L(d), s) for br_key, d, s in _TAPS_R]
    irL = np.zeros(ir_len)
    irR = np.zeros(ir_len)
    lp_in = 0.0
    fb_a = fb_b = 0.0  # cross-feedback (output of opposite branch delay2)
    A, B = tank["a"], tank["b"]
    for n in range(ir_len):
        x = 1.0 if n == 0 else 0.0
        lp_in = bw * x + (1.0 - bw) * lp_in
        v = lp_in
        for st in in_apf:
            v = apf(st, v)
        # branch a (fed by branch b's tail), branch b (fed by a's tail)
        ua = v + decay * fb_b
        ua = apf(A["ap1"], ua)
        oa = push(A["d1"], ua)
        A["lp"] = (1.0 - damp) * oa + damp * A["lp"]
        wa = apf(A["ap2"], decay * A["lp"])
        fa = push(A["d2"], wa)

        ub = v + decay * fb_a
        ub = apf(B["ap1"], ub)
        ob = push(B["d1"], ub)
        B["lp"] = (1.0 - damp) * ob + damp * B["lp"]
        wb = apf(B["ap2"], decay * B["lp"])
        fb = push(B["d2"], wb)

        fb_a, fb_b = fa, fb

        acc = 0.0
        for bk, d, s in taps_l:
            br, part = bk.split("_")
            acc += s * tap(tank[br][part], d)
        irL[n] = 0.6 * acc
        acc = 0.0
        for bk, d, s in taps_r:
            br, part = bk.split("_")
            acc += s * tap(tank[br][part], d)
        irR[n] = 0.6 * acc

    e = np.sqrt(np.sum(irL * irL) + np.sum(irR * irR))
    _IR_CACHE[("plate_raw_e", sr, ir_len)] = max(e, 1e-9)
    irL *= 1.0 / max(e, 1e-9)
    irR *= 1.0 / max(e, 1e-9)
    _IR_CACHE[key] = (irL, irR)
    return irL, irR


_FDN_DELAYS = (997, 1153, 1327, 1559, 1801, 2099, 2399, 2767)  # coprime
_FDN_IN_APF = ((113, 0.7), (167, 0.7))


def _fdn_irs(sr: int, rt60_low: float, rt60_high: float, crossover_hz: float,
             size: float, n_max: int):
    """Stereo IRs of an 8-line Householder FDN with per-line shelving loss
    filters hitting independent low/high RT60 targets."""
    rt60_low = float(np.clip(rt60_low, 0.1, 20.0))
    rt60_high = float(np.clip(rt60_high, 0.05, rt60_low))
    size = float(np.clip(size, 0.5, 2.0))
    ir_len = min(int(min(rt60_low * 1.2 + 0.2, 14.0) * sr), n_max)
    key = ("fdn", sr, rt60_low, rt60_high, crossover_hz, size, ir_len)
    if key in _IR_CACHE:
        return _IR_CACHE[key]

    scale = (sr / 44100.0) * size
    Ls = [max(8, int(round(d * scale))) for d in _FDN_DELAYS]
    N = len(Ls)
    # per-line loss filter H(z) = (b0 + b1 z^-1)/(1 - p z^-1):
    # gain at DC = rt60_low target, gain at Nyquist = rt60_high target
    p = float(np.exp(-2.0 * np.pi * crossover_hz / sr))
    coefs = []
    for Li in Ls:
        gl = 10.0 ** (-3.0 * Li / (rt60_low * sr))
        gh = 10.0 ** (-3.0 * Li / (rt60_high * sr))
        b0 = 0.5 * (gl * (1.0 - p) + gh * (1.0 + p))
        b1 = 0.5 * (gl * (1.0 - p) - gh * (1.0 + p))
        coefs.append((b0, b1))

    bufs = [[0.0] * Li for Li in Ls]
    idx = [0] * N
    x1 = [0.0] * N   # filter input memory
    y1 = [0.0] * N   # filter output memory
    in_apf = [{"buf": [0.0] * max(2, int(round(d * scale))), "i": 0, "g": g,
               "n": max(2, int(round(d * scale)))} for d, g in _FDN_IN_APF]
    irL = np.zeros(ir_len)
    irR = np.zeros(ir_len)
    two_over_n = 2.0 / N
    inj = 1.0 / np.sqrt(N)
    for n in range(ir_len):
        x = 1.0 if n == 0 else 0.0
        for st in in_apf:  # brief input diffusion
            buf, i, g = st["buf"], st["i"], st["g"]
            z = buf[i]
            v = x + g * z
            buf[i] = v
            st["i"] = (i + 1) % st["n"]
            x = z - g * v
        outs = [bufs[i][idx[i]] for i in range(N)]
        filt = []
        for i in range(N):
            b0, b1 = coefs[i]
            yi = b0 * outs[i] + b1 * x1[i] + p * y1[i]
            x1[i] = outs[i]
            y1[i] = yi
            filt.append(yi)
        s = sum(filt) * two_over_n
        for i in range(N):
            bufs[i][idx[i]] = inj * x + (filt[i] - s)   # Householder mix
            idx[i] = (idx[i] + 1) % Ls[i]
        irL[n] = 0.5 * (outs[0] - outs[2] + outs[4] - outs[6])
        irR[n] = 0.5 * (outs[1] - outs[3] + outs[5] - outs[7])

    e = np.sqrt(np.sum(irL * irL) + np.sum(irR * irR))
    irL *= 1.0 / max(e, 1e-9)
    irR *= 1.0 / max(e, 1e-9)
    _IR_CACHE[key] = (irL, irR)
    return irL, irR


def _with_predelay(ir: np.ndarray, sr: int, predelay_s: float) -> np.ndarray:
    pd = int(max(0.0, predelay_s) * sr)
    return np.concatenate([np.zeros(pd), ir]) if pd else ir


def _plate_wet(mono: np.ndarray, sr: int, fx: dict):
    """Wet L/R for the plate. mod=0: exact LTI impulse-response convolution.
    mod>0: native full-signal tank with swept-allpass modulation (validated
    to reproduce the IR path at machine epsilon when mod=0), loudness-
    calibrated by the same IR-energy factor so mix levels are comparable."""
    decay = fx.get("decay", 0.7)
    damp = fx.get("damp", 0.3)
    mod = float(fx.get("mod", 0.0))
    if mod > 0.0:
        from ._native import plate_mod_native
        wetL, wetR = plate_mod_native(mono, sr, decay, damp, mod,
                                      float(fx.get("mod_rate", 1.0)))
        ir = _plate_irs(sr, decay, damp, mono.size)  # cached calibration
        cal = _IR_CACHE[("plate_raw_e", sr, ir[0].size)]
        wetL = wetL / cal
        wetR = wetR / cal
    else:
        irL, irR = _plate_irs(sr, decay, damp, mono.size)
        wetL = fftconvolve(mono, irL, mode="full")[:mono.size]
        wetR = fftconvolve(mono, irR, mode="full")[:mono.size]
    pd = fx.get("predelay", 0.0)
    if pd:
        s = int(pd * sr)
        wetL = np.concatenate([np.zeros(s), wetL])[:mono.size]
        wetR = np.concatenate([np.zeros(s), wetR])[:mono.size]
    return wetL, wetR


def plate_stereo(left: np.ndarray, right: np.ndarray, sr: int,
                 fx: dict) -> tuple[np.ndarray, np.ndarray]:
    """True-stereo plate: mono-summed tank input, decorrelated L/R taps."""
    wetL, wetR = _plate_wet(0.5 * (left + right), sr, fx)
    mix = float(fx.get("mix", 0.3))
    return (1 - mix) * left + mix * wetL, (1 - mix) * right + mix * wetR


def fdn_stereo(left: np.ndarray, right: np.ndarray, sr: int,
               fx: dict) -> tuple[np.ndarray, np.ndarray]:
    rt = fx.get("rt60", 3.0)
    irL, irR = _fdn_irs(sr, rt, fx.get("rt60_high", rt * 0.4),
                        fx.get("crossover", 2500.0), fx.get("size", 1.0),
                        left.size)
    mono = 0.5 * (left + right)
    mix = float(fx.get("mix", 0.3))
    wetL = fftconvolve(mono, irL, mode="full")[:left.size]
    wetR = fftconvolve(mono, irR, mode="full")[:right.size]
    return (1 - mix) * left + mix * wetL, (1 - mix) * right + mix * wetR


def plate_mono(x: np.ndarray, sr: int, fx: dict) -> np.ndarray:
    """Layer-chain (mono) variant: averaged wet."""
    wetL, wetR = _plate_wet(x, sr, fx)
    mix = float(fx.get("mix", 0.3))
    return (1 - mix) * x + mix * 0.5 * (wetL + wetR)


def fdn_mono(x: np.ndarray, sr: int, fx: dict) -> np.ndarray:
    rt = fx.get("rt60", 3.0)
    irL, irR = _fdn_irs(sr, rt, fx.get("rt60_high", rt * 0.4),
                        fx.get("crossover", 2500.0), fx.get("size", 1.0),
                        x.size)
    ir = 0.5 * (irL + irR)
    mix = float(fx.get("mix", 0.3))
    return (1 - mix) * x + mix * fftconvolve(x, ir, mode="full")[:x.size]


STEREO_FX = {"plate": plate_stereo, "fdn": fdn_stereo}
MONO_FX = {"plate": plate_mono, "fdn": fdn_mono}
