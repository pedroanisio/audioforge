"""Determinism primitives.

Every stochastic element in the engine draws from an RNG whose seed is
derived from the explicit performance seed/variant and a stable component
path. The complete spec hash separately identifies the render contract.
Identical specs reproduce within a verified environment; cross-platform
floating-point/native results are checked by the golden gate, not assumed.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

import numpy as np

from .version import ENGINE_VERSION


def canonical_json(obj: Any) -> str:
    """Serialize with sorted keys, no whitespace ambiguity, stable floats."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


HASH_EXCLUDED_TOP_LEVEL = {"_meta", "intent", "notation"}


def spec_hash(spec: dict) -> str:
    """Stable content hash of a spec (engine version included so output
    hashes change when the engine semantics change). Top-level `_meta`,
    `intent`, and notation-only metadata are excluded: render-affecting
    semantics must first expand into explicit render IR before they can affect
    audio bytes."""
    spec = {k: v for k, v in spec.items() if k not in HASH_EXCLUDED_TOP_LEVEL}
    payload = ENGINE_VERSION + "\x00" + canonical_json(spec)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def performance_hash(spec: dict) -> str:
    """Identify a take independently of mix settings, labels and engine version.

    The complete spec still identifies the render. Only an explicit seed or
    variant changes the take's entropy; named layers and events subdivide it.
    """
    payload = canonical_json({
        "schema": "audioforge.performance/1",
        "seed": spec.get("performance_seed", 0),
        "variant": spec.get("variant"),
    })
    return hashlib.sha256(payload.encode()).hexdigest()


def note_seed_paths(events: list[dict]) -> list[str]:
    """Stable event identities; unrelated insertions do not renumber a take.

    Explicit event IDs survive moving a note. Otherwise onset and pitch identify
    the event, with occurrence numbers distinguishing identical unison notes.
    Velocity, gate length and expression edits preserve the random realization.
    """
    occurrences: Counter[str] = Counter()
    paths = []
    for event in events:
        identity = event.get("id") or {
            "beat": float(event["start_beat"]),
            "pitch": event.get("note", event.get("freq_hz")),
            "voice": event.get("voice"),
        }
        key = hashlib.sha256(canonical_json(identity).encode()).hexdigest()[:24]
        paths.append(f"note:{key}:{occurrences[key]}")
        occurrences[key] += 1
    return paths


def derive_seed(root_hash: str, *path: str) -> int:
    """Derive a 64-bit seed for a named component, e.g.
    derive_seed(h, 'layer:noise_bed', 'dither')."""
    msg = root_hash + "\x00" + "\x00".join(path)
    digest = hashlib.sha256(msg.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def rng_for(root_hash: str, *path: str) -> np.random.Generator:
    """Seeded PCG64 generator for a component path."""
    return np.random.Generator(np.random.PCG64(derive_seed(root_hash, *path)))
