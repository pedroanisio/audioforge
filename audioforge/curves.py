"""Normative performance-curve helpers for AudioForge IR."""
from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np


PERFORMANCE_CURVE_TARGETS = {"pitch_cents", "dynamic"}
CURVE_SHAPES = {"linear", "hold", "pow"}
NOTE_TIME_BASES = {"note_beats", "note_seconds"}
LAYER_TIME_BASES = {"layer_seconds", "layer_beats"}
PITCH_CENTS_DEFAULT_LIMIT = 2400.0
PITCH_CENTS_HARD_LIMIT = 4800.0

PHYSICAL_MODEL_OSCILLATORS = {"bowed", "blown", "brass", "struck", "sympathetic"}
CURVE_UNSUPPORTED_VOICE_CODE = "curve_unsupported_voice"


class CurveError(ValueError):
    pass


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _shape_kind(shape: str) -> str:
    if shape == "linear" or shape == "hold":
        return shape
    if shape.startswith("pow:"):
        return "pow"
    raise CurveError(f"shape '{shape}' invalid")


def _pow_exponent(shape: str) -> float:
    try:
        exponent = float(shape.split(":", 1)[1])
    except Exception as exc:
        raise CurveError(f"shape '{shape}' invalid") from exc
    if not 0.1 <= exponent <= 10.0:
        raise CurveError(f"shape '{shape}' exponent outside 0.1..10")
    return exponent


def sampled_to_points(curve: dict) -> list[list[float]]:
    """Expand sampled encoding to linear breakpoint points."""
    t0 = curve.get("t0")
    rate = curve.get("rate_hz")
    values = curve.get("values")
    if not _is_number(t0):
        raise CurveError("t0 must be a number")
    if not _is_number(rate) or rate <= 0.0:
        raise CurveError("rate_hz must be > 0")
    if not isinstance(values, list) or not values:
        raise CurveError("values must be a non-empty list")
    out: list[list[float]] = []
    for idx, value in enumerate(values):
        if not _is_number(value):
            raise CurveError(f"values[{idx}] must be a number")
        out.append([float(t0) + idx / float(rate), float(value)])
    return out


def curve_points(curve: dict) -> list[list]:
    """Return breakpoint points for either supported curve encoding."""
    has_points = "points" in curve
    has_sampled = any(k in curve for k in ("t0", "rate_hz", "values"))
    if has_points and has_sampled:
        raise CurveError("curve must use either points or sampled encoding, not both")
    if has_sampled:
        return sampled_to_points(curve)
    points = curve.get("points")
    if not isinstance(points, list) or not points:
        raise CurveError("points must be a non-empty list")
    return points


def validate_curve(
    curve: dict,
    path: str,
    *,
    allowed_targets: Iterable[str],
    allowed_time_bases: Iterable[str],
    min_points: int = 1,
    pitch_limit_cents: float = PITCH_CENTS_DEFAULT_LIMIT,
) -> None:
    """Validate a curve object and raise ``CurveError`` with pathful messages."""
    if not isinstance(curve, dict):
        raise CurveError(f"{path}: curve must be an object")
    target = curve.get("target")
    allowed_target_set = set(allowed_targets)
    if target not in allowed_target_set:
        raise CurveError(f"{path}.target: '{target}' invalid "
                         f"(allowed: {sorted(allowed_target_set)})")
    time_basis = curve.get("time_basis")
    if time_basis is not None and time_basis not in set(allowed_time_bases):
        raise CurveError(f"{path}.time_basis: '{time_basis}' invalid")
    if pitch_limit_cents > PITCH_CENTS_HARD_LIMIT:
        raise CurveError(f"{path}: pitch_cents limit exceeds hard cap "
                         f"{PITCH_CENTS_HARD_LIMIT:g}")

    points = curve_points(curve)
    if len(points) < min_points:
        raise CurveError(f"{path}.points: need at least {min_points} point"
                         f"{'s' if min_points != 1 else ''}")
    prev_t = -math.inf
    for idx, point in enumerate(points):
        pp = f"{path}.points[{idx}]"
        if not isinstance(point, list) or len(point) not in (2, 3):
            raise CurveError(f"{pp}: must be [time, value] or "
                             "[time, value, shape]")
        t, value = point[0], point[1]
        if not _is_number(t) or not _is_number(value):
            raise CurveError(f"{pp}: time and value must be numbers")
        if t < prev_t:
            raise CurveError(f"{pp}: times must be ascending")
        prev_t = float(t)
        if len(point) == 3:
            shape = point[2]
            if idx == 0:
                raise CurveError(f"{pp}: shape on first point is invalid")
            if not isinstance(shape, str):
                raise CurveError(f"{pp}.shape: must be a string")
            kind = _shape_kind(shape)
            if kind == "pow":
                _pow_exponent(shape)
        if target == "dynamic" and not 0.0 <= float(value) <= 1.0:
            raise CurveError(f"{pp}: dynamic value {value} outside 0..1")
        if target == "pitch_cents" and abs(float(value)) > pitch_limit_cents:
            raise CurveError(f"{pp}: pitch_cents value {value} outside "
                             f"+/-{pitch_limit_cents:g}")


def _normalized_points(curve: dict) -> list[tuple[float, float, str]]:
    points = curve_points(curve)
    normalized: list[tuple[float, float, str]] = []
    for idx, point in enumerate(points):
        shape = "linear" if idx == 0 or len(point) == 2 else str(point[2])
        normalized.append((float(point[0]), float(point[1]), shape))
    return normalized


def evaluate_curve(curve: dict, times: Sequence[float] | np.ndarray) -> np.ndarray:
    """Evaluate a curve at ``times`` using AudioForge's normative semantics."""
    points = _normalized_points(curve)
    xs = np.asarray(times, dtype=float)
    out = np.empty_like(xs, dtype=float)
    if len(points) == 1:
        out.fill(points[0][1])
        return out

    first_t, first_v, _ = points[0]
    last_t, last_v, _ = points[-1]
    out[xs <= first_t] = first_v
    out[xs >= last_t] = last_v
    active = (xs > first_t) & (xs < last_t)
    if not np.any(active):
        return out

    for idx in range(1, len(points)):
        t0, v0, _ = points[idx - 1]
        t1, v1, shape = points[idx]
        mask = active & (xs >= t0) & (xs <= t1)
        if not np.any(mask):
            continue
        if t1 == t0:
            out[mask] = v1
            continue
        u = (xs[mask] - t0) / (t1 - t0)
        kind = _shape_kind(shape)
        if kind == "hold":
            values = np.where(u < 1.0, v0, v1)
        else:
            shaped = u if kind == "linear" else u ** _pow_exponent(shape)
            values = v0 + (v1 - v0) * shaped
        out[mask] = values
    return out
