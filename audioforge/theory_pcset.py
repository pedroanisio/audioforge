"""Pitch-class-set theory core (roadmap item AF-M01 / backlog BL-018).

Formal, derivable operations on pitch-class sets in the 12-tone universe:
normal form, prime form (Rahn), interval-class vector, the transposition and
inversion operators ``Tn``/``TnI``, complement, and symmetry degrees.

This is the foundation the rest of Track M builds on (AF-M02 transformation
networks, AF-M03 neo-Riemannian operators, AF-M04 scales, AF-M06 voice leading).
It replaces the ad-hoc ``{s % 12}`` pitch-class arithmetic previously scattered
through ``dsl.py`` with a single, exhaustively tested source.

Grounding: J. Rahn, *Basic Atonal Theory* (Longman, 1980) for the normal-/prime-
form selection algorithm; A. Forte, *The Structure of Atonal Music* (Yale, 1973)
for the interval-class vector and the set-class catalogue. The corpus text
J. Hook, *Exploring Musical Spaces* (Oxford, 2022,
DOI 10.1093/oso/9780190246013.001.0001) attests the canonical result exercised
in the tests: the major and minor triads share the prime form ``(0, 3, 7)``.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW) — this module is LLM-adjacent surface an
agent will call. Every operation here is validated in ``tests/test_theory_pcset.py``
against a *closed, enumerable* ground truth (all 2**12 subsets → the 224 Tn/TnI
set-classes, plus the group axioms), not spot-checks. A "probably correct"
transformation is unverified output; do not weaken the exhaustive tests.
"""
from __future__ import annotations

from typing import Iterable

# A pitch-class set is represented as a sorted tuple of distinct ints in 0..11.
Pcs = tuple[int, ...]

MODULUS = 12


def pcset(notes: Iterable[int]) -> Pcs:
    """Normalize any iterable of integers to a canonical pitch-class set.

    Reduces mod 12, removes duplicates, and sorts ascending. This is the single
    entry point other modules should use instead of open-coding ``{n % 12}``.
    """
    return tuple(sorted({n % MODULUS for n in notes}))


def transpose(pcs: Iterable[int], n: int) -> Pcs:
    """``Tn``: transpose every pitch class up by ``n`` semitones (mod 12)."""
    return tuple(sorted((p + n) % MODULUS for p in {q % MODULUS for q in pcs}))


# Conventional alias matching the theory literature.
def Tn(pcs: Iterable[int], n: int) -> Pcs:  # noqa: N802 - operator name from theory
    """``Tn`` transposition operator (alias of :func:`transpose`)."""
    return transpose(pcs, n)


def invert(pcs: Iterable[int], axis: int = 0) -> Pcs:
    """Invert about ``axis`` (default 0): each pc ``p`` maps to ``axis - p`` (mod 12).

    With ``axis = 0`` this is plain pitch-class inversion ``I``; ``TnI`` composes
    inversion with transposition (see :func:`TnI`).
    """
    return tuple(sorted((axis - p) % MODULUS for p in {q % MODULUS for q in pcs}))


def TnI(pcs: Iterable[int], n: int) -> Pcs:  # noqa: N802 - operator name from theory
    """``TnI``: invert then transpose by ``n``, i.e. ``p -> (n - p) mod 12``.

    Equivalent to inversion about the axis ``n`` (:func:`invert` with ``axis=n``).
    """
    return invert(pcs, axis=n)


def complement(pcs: Iterable[int]) -> Pcs:
    """The pitch classes NOT in ``pcs`` (the literal/absolute complement)."""
    present = {p % MODULUS for p in pcs}
    return tuple(p for p in range(MODULUS) if p not in present)


def _rotation_key(rotation: Pcs) -> tuple[int, ...]:
    """Rahn compactness key for one rotation of a normal-order candidate.

    The rotation is zero-based (first element 0, ascending mod 12). Rahn selects
    the most compact ordering: minimize the span (last interval), then break ties
    by the next-largest interval reading inward from the right, then by the
    smallest starting pitch class. Returning the reversed interval tuple makes a
    plain ``min`` implement exactly that comparison; the caller appends the start
    pc as a final tie-break.
    """
    return tuple(reversed(rotation[1:]))


def normal_form(pcs: Iterable[int]) -> Pcs:
    """Rahn normal order: the most left-/right-compact rotation of the set.

    Returns the actual pitch classes (not zero-based). Empty and singleton sets
    are returned as-is.
    """
    s = pcset(pcs)
    n = len(s)
    if n <= 1:
        return s
    best: Pcs | None = None
    best_key: tuple | None = None
    for i in range(n):
        rot = tuple(s[(i + j) % n] for j in range(n))
        zero = tuple((x - rot[0]) % MODULUS for x in rot)
        key = (_rotation_key(zero), rot[0])  # compactness, then lowest start pc
        if best_key is None or key < best_key:
            best_key = key
            best = rot
    assert best is not None
    return best


def _zero_based(order: Pcs) -> Pcs:
    if not order:
        return order
    return tuple((x - order[0]) % MODULUS for x in order)


def prime_form(pcs: Iterable[int]) -> Pcs:
    """Rahn prime form: the canonical Tn/TnI representative of the set-class.

    Zero-bases the normal orders of the set and its inversion and returns the
    lexicographically smaller (most packed to the left). Inversionally related
    sets therefore share a prime form — e.g. the major triad ``(0, 4, 7)`` and
    the minor triad ``(0, 3, 7)`` both reduce to ``(0, 3, 7)``.
    """
    s = pcset(pcs)
    if len(s) == 0:
        return ()
    if len(s) == 1:
        return (0,)  # every singleton is the same set-class, zero-based
    a = _zero_based(normal_form(s))
    b = _zero_based(normal_form(invert(s)))
    return min(a, b)


def interval_class_vector(pcs: Iterable[int]) -> tuple[int, int, int, int, int, int]:
    """The interval-class vector ``<ic1 ic2 ic3 ic4 ic5 ic6>``.

    Counts, over every unordered pair in the set, the interval class
    ``min(d, 12 - d)`` for pitch-class difference ``d``. E.g. the major/minor
    triad yields ``(0, 0, 1, 1, 1, 0)``.
    """
    s = pcset(pcs)
    counts = [0, 0, 0, 0, 0, 0]
    for i in range(len(s)):
        for j in range(i + 1, len(s)):
            d = (s[j] - s[i]) % MODULUS
            ic = min(d, MODULUS - d)
            counts[ic - 1] += 1
    return tuple(counts)  # type: ignore[return-value]


def set_class(pcs: Iterable[int]) -> tuple[int, Pcs]:
    """Canonical, derivable set-class identity: ``(cardinality, prime_form)``.

    Two sets share a ``set_class`` iff they are related by transposition and/or
    inversion. This is the unambiguous identity; Forte ordinal numbers are a
    historical label over the same classes and are intentionally not fabricated
    here (they require the verified catalogue).
    """
    p = prime_form(pcs)
    return (len(p), p)


def transposition_symmetry(pcs: Iterable[int]) -> int:
    """Number of transpositions ``Tn`` (n in 0..11) that map the set to itself."""
    s = pcset(pcs)
    return sum(1 for n in range(MODULUS) if transpose(s, n) == s)


def inversion_symmetry(pcs: Iterable[int]) -> int:
    """Number of inversions ``TnI`` (n in 0..11) that map the set to itself."""
    s = pcset(pcs)
    return sum(1 for n in range(MODULUS) if TnI(s, n) == s)


__all__ = [
    "Pcs",
    "pcset",
    "transpose",
    "Tn",
    "invert",
    "TnI",
    "complement",
    "normal_form",
    "prime_form",
    "interval_class_vector",
    "set_class",
    "transposition_symmetry",
    "inversion_symmetry",
]
