"""Determinism primitives.

Every stochastic element in the engine draws from an RNG whose seed is
derived from (a) the canonical hash of the asset spec and (b) a stable
string path identifying the component asking for randomness. Identical
spec => identical bytes, on any machine, any run.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

ENGINE_VERSION = "2.14.0"  # bump on any change that alters rendered output


def canonical_json(obj: Any) -> str:
    """Serialize with sorted keys, no whitespace ambiguity, stable floats."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def spec_hash(spec: dict) -> str:
    """Stable content hash of a spec (engine version included so output
    hashes change when the engine semantics change). Top-level `_meta`
    (source line numbers and other non-musical sidecar data) is excluded:
    the same music reformatted must hash identically."""
    if "_meta" in spec:
        spec = {k: v for k, v in spec.items() if k != "_meta"}
    payload = ENGINE_VERSION + "\x00" + canonical_json(spec)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_seed(root_hash: str, *path: str) -> int:
    """Derive a 64-bit seed for a named component, e.g.
    derive_seed(h, 'layer:noise_bed', 'dither')."""
    msg = root_hash + "\x00" + "\x00".join(path)
    digest = hashlib.sha256(msg.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def rng_for(root_hash: str, *path: str) -> np.random.Generator:
    """Seeded PCG64 generator for a component path."""
    return np.random.Generator(np.random.PCG64(derive_seed(root_hash, *path)))
