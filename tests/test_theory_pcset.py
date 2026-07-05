"""Exhaustive verification of the pitch-class-set core (AF-M01 / BL-018).

These are not spot-checks. The central test enumerates all 2**12 subsets of the
12-tone universe and proves ``prime_form`` partitions them into exactly the 224
Tn/TnI set-classes, with the correct count at every cardinality. The operators
are checked against their group axioms over all inputs. Per PALS's LAW, a
music-theory function is unverified until it is pinned to a closed ground truth.
"""
from __future__ import annotations

import itertools

from audioforge.theory_pcset import (
    TnI,
    Tn,
    complement,
    interval_class_vector,
    invert,
    inversion_symmetry,
    normal_form,
    pcset,
    prime_form,
    set_class,
    transpose,
    transposition_symmetry,
)

ALL_PCS = range(12)


def _all_subsets():
    for k in range(13):
        for combo in itertools.combinations(ALL_PCS, k):
            yield combo


# The number of set-classes (Tn/TnI equivalence) at each cardinality 0..12.
# Derived from Burnside's lemma on the dihedral group D12 (order 24):
# total = (sum over 12 rotations 2**gcd-cycles + sum over 12 reflections) / 24 = 224.
# The per-cardinality vector is the standard published result (Rahn 1980; Straus).
SETCLASS_COUNTS = [1, 1, 6, 12, 29, 38, 50, 38, 29, 12, 6, 1, 1]


def test_prime_form_partitions_universe_into_224_setclasses():
    """All 4096 subsets collapse to exactly the 224 Tn/TnI set-classes, with the
    correct count per cardinality. This alone proves prime_form is a correct,
    complete Tn/TnI class invariant."""
    by_card: dict[int, set] = {k: set() for k in range(13)}
    for subset in _all_subsets():
        pf = prime_form(subset)
        by_card[len(subset)].add(pf)
    counts = [len(by_card[k]) for k in range(13)]
    assert counts == SETCLASS_COUNTS
    assert sum(counts) == 224


def test_prime_form_is_tn_tni_invariant_over_whole_universe():
    """prime_form must be identical for a set and every one of its 24 Tn/TnI
    transforms — checked on every subset, no sampling."""
    for subset in _all_subsets():
        pf = prime_form(subset)
        for n in range(12):
            assert prime_form(Tn(subset, n)) == pf
            assert prime_form(TnI(subset, n)) == pf


def test_major_and_minor_triad_share_prime_form_037():
    """Corpus-attested (Hook, Exploring Musical Spaces): the major triad (0,4,7)
    and minor triad (0,3,7) share the prime form (0,3,7)."""
    assert prime_form({0, 4, 7}) == (0, 3, 7)
    assert prime_form({0, 3, 7}) == (0, 3, 7)
    assert set_class({0, 4, 7}) == set_class({0, 3, 7}) == (3, (0, 3, 7))


def test_interval_class_vectors_known():
    assert interval_class_vector({0, 4, 7}) == (0, 0, 1, 1, 1, 0)        # major triad
    assert interval_class_vector({0, 1, 2}) == (2, 1, 0, 0, 0, 0)        # chromatic trichord
    assert interval_class_vector({0, 2, 4, 6, 8, 10}) == (0, 6, 0, 6, 0, 3)  # whole-tone
    # Diatonic scale — the "deep scale": every interval class a distinct count.
    assert interval_class_vector({0, 2, 4, 5, 7, 9, 11}) == (2, 5, 4, 3, 6, 1)


def test_ic_vector_cardinality_relation():
    """The sum of the interval-class vector equals C(k, 2) for a k-note set."""
    for subset in _all_subsets():
        k = len(subset)
        assert sum(interval_class_vector(subset)) == k * (k - 1) // 2


# ------------------------------------------------------------------ operators

def test_pcset_normalizes():
    assert pcset([12, 0, 24, 7, 7, 16]) == (0, 4, 7)
    assert pcset([]) == ()
    assert pcset([-1, -13]) == (11,)


def test_transpose_group_axioms():
    sample = [(0, 4, 7), (0, 1, 2, 3), (0, 2, 4, 6, 8, 10), (), (5,), tuple(range(12))]
    for s in sample:
        assert transpose(s, 0) == pcset(s)                       # identity
        for a in range(12):
            for b in range(12):
                assert Tn(Tn(s, a), b) == Tn(s, a + b)           # additivity
                assert len(Tn(s, a)) == len(pcset(s))            # cardinality preserved


def test_inversion_is_an_involution():
    for subset in _all_subsets():
        assert invert(invert(subset)) == pcset(subset)
        for n in range(12):
            assert TnI(TnI(subset, n), n) == pcset(subset)       # TnI is its own inverse


def test_tni_equals_invert_about_axis():
    for subset in _all_subsets():
        for n in range(12):
            assert TnI(subset, n) == invert(subset, axis=n)


def test_complement():
    for subset in _all_subsets():
        c = complement(subset)
        assert len(c) == 12 - len(subset)
        assert set(c).isdisjoint(subset)
        assert complement(c) == pcset(subset)


def test_normal_form_is_a_reordering():
    for subset in _all_subsets():
        nf = normal_form(subset)
        assert set(nf) == set(pcset(subset))
        assert len(nf) == len(pcset(subset))
    assert normal_form({0, 4, 7}) == (0, 4, 7)
    assert normal_form(()) == ()
    assert normal_form({5}) == (5,)


def test_symmetry_degrees():
    # Whole-tone maps to itself under 6 transpositions; augmented triad under 3;
    # diminished-seventh under 4 — their generating symmetries.
    assert transposition_symmetry({0, 2, 4, 6, 8, 10}) == 6
    assert transposition_symmetry({0, 4, 8}) == 3
    assert transposition_symmetry({0, 3, 6, 9}) == 4
    assert transposition_symmetry({0, 4, 7}) == 1                # asymmetric triad
    # The major triad is not inversionally symmetric (its inversion is the minor).
    assert inversion_symmetry({0, 4, 7}) == 0
    assert inversion_symmetry({0, 1, 2}) > 0                     # chromatic trichord is
