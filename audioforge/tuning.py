"""n-EDO tuning resolution (ADR-0010; AF-M05 slice 1).

``tuning: edo divisions=N base=A4 hz=440`` (``spec.notation.tuning``) maps note
names to frequencies in N equal divisions of the octave. Letters and accidentals
are spelled along the chain of fifths — the regular mapping every EDO shares:
the fifth is ``round(N·log2(3/2))`` steps, a sharp raises by seven fifths minus
four octaves, and C D E F G A B sit at ``k·P mod N`` steps for their fifths
index k = 0 2 4 −1 1 3 5 (P = the fifth). In 12-EDO this *is* 12-TET, and the
default path calls ``synth.note_to_freq`` unchanged, so specs without a directive
render byte-identically (HARNESS-NTUN-002). Explicit ``freq_hz`` values are
never retuned.

Layers reach their tuning through the ``_tuning`` sidecar the renderer injects
next to ``_score`` (only when a non-default tuning is declared), so the IR and
its hash are untouched.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache

from . import synth

_NOTE = re.compile(r"^([A-Ga-g])([#b]*)(-?\d+)$")
_FIFTHS_FROM_C = {"C": 0, "D": 2, "E": 4, "F": -1, "G": 1, "A": 3, "B": 5}


@dataclass(frozen=True)
class Tuning:
    divisions: int = 12
    base_note: str = "A4"
    base_hz: float = 440.0

    def __post_init__(self):
        if self.divisions < 1:
            raise ValueError(f"tuning: divisions must be >= 1, got {self.divisions}")
        if not (self.base_hz > 0):
            raise ValueError(f"tuning: base hz must be positive, got {self.base_hz}")
        if not _NOTE.match(self.base_note):
            raise ValueError(f"tuning: base must be a note name, got {self.base_note!r}")

    # ----------------------------------------------------------- factories --
    @classmethod
    def from_directive(cls, directive: dict | None) -> "Tuning":
        if not directive:
            return cls()
        if directive.get("system", "edo") != "edo":
            raise ValueError(f"tuning: unsupported system {directive.get('system')!r}; only edo")
        return cls(int(directive.get("divisions", 12)), str(directive.get("base_note", "A4")),
                   float(directive.get("base_hz", 440.0)))

    @classmethod
    def from_spec(cls, spec: dict) -> "Tuning":
        return cls.from_directive((spec.get("notation") or {}).get("tuning"))

    @classmethod
    def from_layer(cls, layer: dict) -> "Tuning":
        return cls.from_directive(layer.get("_tuning"))

    def sidecar(self) -> dict | None:
        """The ``_tuning`` value the renderer injects into layers (None when default)."""
        if self.is_default:
            return None
        return {"system": "edo", "divisions": self.divisions,
                "base_note": self.base_note, "base_hz": self.base_hz}

    # ------------------------------------------------------------ mapping --
    @property
    def is_default(self) -> bool:
        return self.divisions == 12 and self.base_note.upper() == "A4" and self.base_hz == 440.0

    @property
    def fifth(self) -> int:
        return round(self.divisions * math.log2(1.5))

    @property
    def sharp(self) -> int:
        return 7 * self.fifth - 4 * self.divisions

    @property
    def step_cents(self) -> float:
        return 1200.0 / self.divisions

    def steps(self, note: str) -> int:
        """Absolute step index of a note name (octave · N + letter + accidentals)."""
        m = _NOTE.match(note)
        if not m:
            raise ValueError(f"tuning: not a note name: {note!r}")
        letter, acc, octave = m.group(1).upper(), m.group(2), int(m.group(3))
        letter_steps = (_FIFTHS_FROM_C[letter] * self.fifth) % self.divisions
        return octave * self.divisions + letter_steps + (acc.count("#") - acc.count("b")) * self.sharp

    def note_to_freq(self, note: str) -> float:
        if self.is_default:
            return synth.note_to_freq(note)          # the one 12-TET definition, unchanged
        return self.base_hz * 2.0 ** ((self.steps(note) - self.steps(self.base_note)) / self.divisions)

    def cents_from_a440(self, note: str) -> float:
        return 1200.0 * math.log2(self.note_to_freq(note) / 440.0)

    def xml_alter(self, note: str) -> float:
        """MusicXML ``<alter>`` in (decimal) semitones: this tuning's pitch relative to
        the 12-TET natural of the same letter and octave."""
        m = _NOTE.match(note)
        natural = f"{m.group(1).upper()}{m.group(3)}"
        return round((self.cents_from_a440(note) - 1200.0 * math.log2(synth.note_to_freq(natural) / 440.0)) / 100.0, 4)


@lru_cache(maxsize=None)
def _cached(divisions: int, base_note: str, base_hz: float) -> Tuning:
    return Tuning(divisions, base_note, base_hz)


def tuning_for(layer: dict) -> Tuning:
    """The tuning a layer renders in (from its ``_tuning`` sidecar; default otherwise)."""
    t = layer.get("_tuning")
    if not t:
        return _cached(12, "A4", 440.0)
    return _cached(int(t.get("divisions", 12)), str(t.get("base_note", "A4")), float(t.get("base_hz", 440.0)))


def freq_for(event: dict, layer: dict) -> float:
    """An event's frequency: explicit ``freq_hz`` wins; a note name follows the layer's tuning."""
    return event.get("freq_hz") or tuning_for(layer).note_to_freq(event["note"])


def with_tuning(layer: dict, spec: dict) -> dict:
    """Return the layer with the spec's tuning sidecar attached (unchanged when default)."""
    sidecar = Tuning.from_spec(spec).sidecar()
    return {**layer, "_tuning": sidecar} if sidecar else layer
