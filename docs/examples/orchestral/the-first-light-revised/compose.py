"""The First Light: an original 116-bar orchestral overture, exactly 300 seconds.

Run from the repository root with PYTHONPATH=. .venv/bin/python <this file>.
The pitches, harmony, themes and orchestration below are authored explicitly;
AudioForge supplies sample playback, expression, mixing and deterministic output.
"""
from __future__ import annotations

import argparse
import copy
import itertools
import json
from pathlib import Path

import numpy as np

from audioforge import Composer
from audioforge.catalog import note_name
from audioforge.decompile import spec_to_dsl
from audioforge.dsl import compile_dsl
from audioforge.schema import validate_spec
from audioforge.sequencer import TempoMap

HERE = Path(__file__).resolve().parent
LIBRARY = "FirstLight-Orchestra"
PIN = json.loads((HERE.parents[3] / 'libraries' / LIBRARY / 'library.manifest.json').read_text())['manifest_sha256']
ID = "the_first_light"
SECTIONS = [
    (0, 8, "Before dawn", "Adagio", "D minor"),
    (8, 32, "The road awakens", "Allegro con moto", "D minor"),
    (32, 56, "A window of light", "Andante cantabile", "F major"),
    (56, 80, "Passing shadows", "Allegro agitato", "D minor; sequential modulations"),
    (80, 104, "The returning road", "Allegro maestoso", "D major"),
    (104, 116, "First light", "Tranquillo, allargando", "D major"),
]

# Written chords, including inversions; the bass uses concert/sounding pitches.
CHORDS = {
    "Dm": ([2, 5, 9], 38), "Dm/F": ([2, 5, 9], 41),
    "A7": ([9, 1, 4, 7], 33), "Gm": ([7, 10, 2], 43),
    "Bb": ([10, 2, 5], 34), "C": ([0, 4, 7], 36),
    "C/E": ([0, 4, 7], 40), "C7": ([0, 4, 7, 10], 36),
    "F": ([5, 9, 0], 41), "F/A": ([5, 9, 0], 33),
    "Am": ([9, 0, 4], 33), "Edim": ([4, 7, 10], 40),
    "E7": ([4, 8, 11, 2], 40), "F7": ([5, 9, 0, 3], 41),
    "D7": ([2, 6, 9, 0], 38), "Eb": ([3, 7, 10], 39),
    "Bb/D": ([10, 2, 5], 38), "D": ([2, 6, 9], 38),
    "D/F#": ([2, 6, 9], 42), "D/A": ([2, 6, 9], 33),
    "G": ([7, 11, 2], 43), "Bm": ([11, 2, 6], 35),
    "A/C#": ([9, 1, 4], 37), "F#m": ([6, 9, 1], 42),
    "Em": ([4, 7, 11], 40),
}
INTRO = "Dm Dm Bb Gm Dm/F Edim A7 A7".split()
H_A = "Dm A7 Gm A7 Dm/F Bb A7 Dm".split()
H_A2 = "Dm C/E F C7 Bb Gm A7 A7".split()
H_B = "F C/E Dm Am Bb F/A Gm C7".split()
H_B2 = "F C Dm Am Bb Gm C7 F".split()
H_B3 = "F Bb Gm C7 F Dm E7 A7".split()
H_DEV = ("Dm Gm C7 F Bb Edim A7 Dm "
         "Dm F7 Bb Gm E7 Am D7 Gm "
         "Eb Bb/D Gm Dm/F Edim A7 A7 A7").split()
H_RETURN = ("D A7 G A7 D/F# Bm A7 D "
            "D A/C# Bm F#m G D/F# Em A7 "
            "G D/F# Em A7 D G A7 D").split()
H_CODA = "D Bm G D/F# Em A7 D G D/A A7 D D".split()
HARMONY = INTRO + H_A + H_A2 + H_A + H_B + H_B2 + H_B3 + H_DEV + H_RETURN + H_CODA
assert len(HARMONY) == 116

# Each bar is a complete four-quarter phrase, with rests written as '-'.
THEME_A = [
    "D5:1 A4:.5 C#5:.5 D5:1 F5:1",
    "E5:1.5 D5:.5 C#5:1 A4:1",
    "Bb4:1 D5:1 G5:1.5 F5:.5",
    "E5:.5 F5:.5 E5:1 C#5:1 A4:1",
    "F5:1 A5:.5 G5:.5 F5:1 D5:1",
    "D5:1 F5:1 Bb5:.5 A5:.5 F5:1",
    "E5:1 G5:.5 F5:.5 E5:1 C#5:1",
    "D5:2 A4:1 D5:1",
]
THEME_A2 = [
    "A5:1 F5:.5 E5:.5 D5:1 F5:1",
    "G5:1 E5:1 D5:.5 C5:.5 G4:1",
    "A4:.5 C5:.5 F5:1 A5:1 G5:1",
    "E5:1 G5:.5 Bb5:.5 G5:1 E5:1",
    "F5:1 D5:1 Bb4:.5 C5:.5 D5:1",
    "G5:1 F5:.5 Eb5:.5 D5:1 Bb4:1",
    "C#5:.5 E5:.5 A5:1 G5:1 E5:1",
    "C#5:2 A4:1 -:1",
]
THEME_B = [
    "A4:2 C5:1 D5:.5 C5:.5",
    "G4:1 E5:1 D5:1 C5:1",
    "F5:2 E5:.5 D5:.5 A4:1",
    "C5:3 E5:.5 C5:.5",
    "D5:1 F5:1 Bb5:1 A5:1",
    "A5:1 G5:.5 F5:.5 C5:1 A4:1",
    "Bb4:1 A4:.5 G4:.5 D5:1 F5:1",
    "E5:1 G5:.5 F5:.5 E5:1 C5:1",
]
THEME_B2 = [
    "C5:1 A4:1 F4:1 A4:1",
    "G4:1 C5:1 E5:1 G5:1",
    "A5:2 F5:1 E5:.5 D5:.5",
    "E5:2 C5:1 A4:1",
    "Bb4:.5 C5:.5 D5:1 F5:1 D5:1",
    "G5:1 F5:.5 Eb5:.5 D5:1 Bb4:1",
    "C5:1 E5:1 G5:.5 F5:.5 E5:1",
    "F5:3 -:1",
]
THEME_B3 = [
    "A4:1 C5:1 F5:2",
    "F5:1 D5:1 Bb4:1 D5:1",
    "D5:1 Bb4:1 G4:1 Bb4:1",
    "C5:1 Bb4:.5 G4:.5 E4:1 G4:1",
    "A4:2 C5:1 A4:1",
    "F4:1 A4:1 D5:1 F5:1",
    "E5:1 D5:1 B4:1 G#4:1",
    "A4:1 C#5:1 E5:1 -:1",
]

# (patch, stereo position, gain dB, role). Gains informed by real-sample probes,
# then checked against stems across the complete orchestration.
PARTS = {
    "solo_viola": ("ViolaRecorded", .08, 9.0, "counterpoint"),
    "violins_1": ("ViolinEnsSusVib", -.58, 5.0, "melody"),
    "violins_2": ("ViolinEnsSusVib", -.22, -1.0, "counterpoint"),
    "violas": ("ViolaEnsSusVib", .15, -14.0, "harmony"),
    "cellos": ("CelloEnsSusVib", .42, -14.0, "bass"),
    "basses": ("ContrabassSusVB", .35, -1.0, "bass"),
    "violin_spiccato": ("ViolinEnsSpic", -.46, -4.0, "movement"),
    "viola_spiccato": ("ViolaEnsSpic", .12, -10.0, "movement"),
    "cello_spiccato": ("CelloEnsSpic", .42, -3.0, "bass"),
    "viola_pizzicato": ("ViolaEnsPizz", .10, -12.0, "harmony"),
    "cello_pizzicato": ("CelloEnsPizz", .42, -5.0, "bass"),
    "bass_pizzicato": ("ContrabassPizz", .30, -1.5, "bass"),
    "flute": ("FluteSusNV", -.26, .5, "melody"),
    "oboe": ("OboeSusNV", -.05, 5.5, "melody"),
    "clarinet": ("ClarinetSus", .17, -12.5, "melody"),
    "bassoon": ("BassoonSus", .29, -9.0, "counterpoint"),
    "horns": ("FHornSus", -.32, -10.0, "harmony"),
    "harp": ("Harp", -.68, -1.0, "color"),
    "timpani": ("Timpani", .15, 2.0, "punctuation"),
}
PITCH = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(note):
    return 12 * (int(note[-1]) + 1) + PITCH[note[0]] + note[1:-1].count("#") - note[1:-1].count("b")


def parse_bar(text):
    result, cursor = [], 0.0
    for token in text.split():
        pitch, length = token.split(":")
        dur = float(length)
        result.append((None if pitch == "-" else midi(pitch), cursor, dur))
        cursor += dur
    assert cursor == 4, text
    return result


def build():
    notes = {name: [] for name in PARTS}
    ledger = []
    phrase_tempo = [
        (0, 74), (24, 76), (28, 68), (31, 68), (32, 110),
        (60, 105), (64, 113), (92, 105), (96, 112), (120, 108),
        (127, 85), (128, 86), (152, 88), (159, 80), (160, 88),
        (184, 91), (191, 81), (192, 86), (216, 91), (223, 99),
        (224, 124), (252, 129), (256, 121), (284, 127), (288, 128),
        (308, 133), (316, 117), (319, 110), (320, 114),
        (348, 108), (352, 115), (380, 108), (384, 119),
        (408, 112), (415, 97), (416, 92), (432, 89), (444, 85),
        (448, 81), (452, 76), (456, 68), (460, 61), (464, 57),
    ]
    factor = TempoMap(phrase_tempo).sec(464) / 294.0
    tempo = [[float(b), float(v * factor)] for b, v in phrase_tempo]
    tm = TempoMap(tempo)
    assert abs(tm.sec(464) - 294) < 1e-9

    def put(part, pitch, beat, dur, vel=.72, function="melody", gate=.90):
        if pitch is None:
            return
        assert part in notes and 0 <= beat < 464
        # Keep the horn writing out of this library's sparsely sampled E4-A4
        # interval, and use its closely recorded D3 timpani rather than D2.
        if part == "horns" and 64 <= pitch <= 69:
            pitch -= 12
        if part == "timpani" and pitch == 38:
            pitch = 50
        # A written bow/breath change for prolonged final tones. No fake legato.
        max_gate = 3.75 if part in ("clarinet", "horns", "bassoon") else 5.8
        seconds = tm.sec(beat + dur * gate) - tm.sec(beat)
        if seconds > max_gate:
            first = dur / 2
            put(part, pitch, beat, first, vel, function, gate=.985)
            put(part, pitch, beat + first, dur - first, vel * .94, function, gate=gate)
            return
        ev = {"note": note_name(int(pitch)), "start_beat": float(beat),
              "dur_beats": round(dur * gate, 8), "vel": round(float(vel), 6),
              "id": f"{part}_{len(notes[part]):04d}"}
        notes[part].append(ev)
        ledger.append({"id": ev["id"], "part": part, "midi": int(pitch),
                       "beat": beat, "bar": int(beat // 4), "function": function})

    def melody(part, start_bar, bars, transpose=0, major=False, strength=.80):
        for index, bar in enumerate(bars):
            for pitch, offset, dur in parse_bar(bar):
                if pitch is not None:
                    if major and pitch % 12 in (5, 10, 0):
                        pitch += 1
                    pitch += transpose
                # Phrase-end space for woodwind breath and string lift.
                gate = .86 if offset + dur == 4 and index % 4 == 3 else .945
                arc = 1 + .06 * np.sin(np.pi * (index % 4) / 3)
                accent = 1.03 if offset in (0, 2) else .95
                put(part, pitch, (start_bar + index) * 4 + offset, dur,
                    min(.96, strength * arc * accent), "theme", gate)

    # Introduction: separated motives, answering bassoon, a dominant preparation.
    intro_lines = ["-:1 D5:1 A4:1 F4:1", "E4:1 F4:1 D4:2",
                   "-:1 F4:1 Bb4:1 D5:1", "D5:1 Bb4:1 G4:2",
                   "A4:1 D5:1 F5:1 E5:1", "D5:1 Bb4:1 G4:1 E4:1",
                   "E5:1 C#5:1 A4:1 G4:1", "E4:1 A4:2 -:1"]
    melody("oboe", 0, intro_lines[:4], strength=.68)
    melody("violins_1", 4, intro_lines[4:], strength=.74)
    melody("bassoon", 1, ["A3:1 F3:1 D3:2"], strength=.59)
    melody("bassoon", 3, ["Bb3:1 A3:.5 G3:.5 D3:2"], strength=.60)

    melody("violins_1", 8, THEME_A)
    melody("violins_1", 16, THEME_A2, strength=.84)
    melody("violins_1", 24, THEME_A, strength=.87)
    melody("flute", 28, THEME_A[4:], strength=.65)
    melody("oboe", 20, THEME_A2[4:], strength=.60)

    melody("oboe", 32, THEME_B, strength=.84)
    melody("flute", 40, THEME_B2, strength=.83)
    melody("clarinet", 48, THEME_B3, strength=.78)
    # Cello sings an answering phrase when the first wind phrase releases.
    melody("cellos", 39, ["G3:1 E3:1 C3:2"], strength=.77)
    melody("cellos", 47, ["A3:1 G3:.5 F3:.5 C3:1 F3:1"], strength=.77)

    # Development: the opening's dotted response is sequenced through the
    # circle of fifths, then compressed into exchanges between winds/strings.
    for bar in range(56, 80):
        pcs, _ = CHORDS[HARMONY[bar]]
        root, third, fifth = pcs[:3]
        tones = [60 + root, 60 + third, 60 + fifth]
        tones = [x + 12 if x < 67 else x for x in tones]
        if bar < 64:
            lead = "violins_1" if bar % 2 == 0 else "clarinet"
            figure = [(tones[0], 0, .75), (tones[2], .75, .25),
                      (tones[1], 1, .5), (tones[0], 1.5, .5)]
            for p, o, d in figure:
                put(lead, p, bar * 4 + o, d, .84, "development")
                put("cellos", p - 24, bar * 4 + o + 2, d, .73, "development")
        elif bar < 72:
            for i, p in enumerate([tones[1], tones[0], tones[2], tones[1]]):
                put("violins_1", p + (12 if p < 73 else 0), bar * 4 + i,
                    1, .83, "development")
            for i, p in enumerate([tones[0], tones[1], tones[2], tones[0]]):
                put("bassoon", p - 24, bar * 4 + i + .25, .65, .70, "development")
        else:
            for i, idx in enumerate([0, 2, 1, 2, 0, 1, 2, 1]):
                pitch = tones[idx] + (12 if tones[idx] < 73 else 0)
                put("violins_1", pitch, bar * 4 + i * .5, .5,
                    .9 if i % 4 == 0 else .82, "development", .88)
                if bar >= 76:
                    put("flute", pitch, bar * 4 + i * .5, .5, .72, "development", .85)
        if bar % 4 in (1, 3):
            put("oboe", tones[1], bar * 4 + 2, 1.7, .74, "development")

    melody("violins_1", 80, THEME_A, major=True, strength=.91)
    melody("flute", 80, THEME_A, major=True, strength=.70)
    melody("violins_1", 88, THEME_B, transpose=-3, strength=.87)
    melody("oboe", 88, THEME_B, transpose=-3, strength=.76)
    final_theme = [
        "G5:1 D5:.5 F#5:.5 G5:1 B5:1",
        "A5:1.5 G5:.5 F#5:1 D5:1",
        "E5:1 G5:1 B5:1 A5:1",
        "G5:.5 A5:.5 G5:1 E5:1 C#5:1",
        "D6:1 A5:.5 G5:.5 F#5:1 D5:1",
        "B5:1 G5:.5 F#5:.5 E5:1 D5:1",
        "E5:1 G5:.5 F#5:.5 E5:1 C#5:1",
        "D5:2 A4:1 D5:1",
    ]
    melody("violins_1", 96, final_theme, strength=.94)
    melody("flute", 100, final_theme[4:], strength=.76)

    melody("oboe", 104, ["F#5:2 E5:1 D5:1", "D5:2 B4:2",
                           "B4:1 D5:1 G5:1 F#5:1", "A4:2 F#4:2"], strength=.72)
    melody("clarinet", 108, ["G4:1 B4:1 E5:2", "E5:1 C#5:1 A4:2"], strength=.70)
    melody("violins_1", 110, ["D5:1 A4:.5 C#5:.5 D5:1 F#5:1",
                               "G5:1 D5:1 B4:1 G4:1",
                               "F#5:1 A5:1 D6:2", "C#6:1 B5:1 G5:1 E5:1"], strength=.78)
    put("violins_1", 86, 456, 7.75, .73, "final_tonic", .995)
    put("flute", 78, 456, 3.75, .62, "final_tonic", .92)

    previous = (57, 62, 69)
    previous_bass = 38
    voicings = []
    for bar, symbol in enumerate(HARMONY):
        pcs, bass = CHORDS[symbol]
        candidates = [[p for p in range(lo, hi + 1) if p % 12 in pcs]
                      for lo, hi in [(52, 64), (57, 69), (62, 77)]]
        best, best_cost = None, float("inf")
        for trial in itertools.product(*candidates):
            if not trial[0] < trial[1] < trial[2] or trial[2] - trial[0] > 19:
                continue
            present = {p % 12 for p in trial} | {bass % 12}
            missing = set(pcs) - present
            cost = sum(abs(a - b) for a, b in zip(trial, previous)) + 7 * len(missing)
            cost += 1.5 * (3 - len({p % 12 for p in trial}))
            cost += .15 * sum(abs(a - b) for a, b in zip(trial, (57, 63, 69)))
            for a, b in zip(trial, previous):
                if ((a - bass) % 12 in (0, 7) and (b - previous_bass) % 12 == (a - bass) % 12
                        and (a - b) * (bass - previous_bass) > 0):
                    cost += 9
            if cost < best_cost:
                best, best_cost = trial, cost
        assert best
        previous, previous_bass = best, bass
        low, mid, high = best
        voicings.append({"bar": bar, "chord": symbol, "bass_midi": bass, "upper_midi": best})
        beat = bar * 4
        cellobass = bass + 12
        fifthbass = bass + 7
        if fifthbass % 12 not in pcs:
            fifthbass = next(n for n in range(bass + 3, bass + 13) if n % 12 in pcs)

        if bar < 8:
            for part, p in (("cellos", cellobass), ("basses", bass), ("violas", mid)):
                put(part, p, beat, 3.8, .57, "harmony", .96)
            if bar >= 4:
                put("violins_2", high, beat, 3.8, .60, "harmony", .96)
            if bar in (0, 2, 4, 6):
                put("harp", bass + 24, beat, 1, .60, "harmony")
                put("harp", high + 12, beat + .15, 1, .54, "harmony")
            if bar >= 6:
                put("horns", low, beat + .1, 3.5, .53, "harmony")
        elif bar < 32 or 80 <= bar < 104:
            majestic = bar >= 80
            # A phrase has a question, an answer and space at its cadence.
            # The return broadens the theme instead of copying its first backing.
            local = bar - (80 if majestic else 8)
            figures = [
                [(0,0,.7),(1.5,1,.35),(2,2,.7)],
                [(.5,2,.3),(1,1,.6),(2.5,0,.3),(3,1,.6)],
                [(0,1,1.3),(2,2,.6),(3.5,0,.3)],
                [(0,2,1.7),(2.5,1,.5)],
                [],
                [(1,0,.3),(1.5,1,.3),(2,2,.3),(2.5,1,.3),(3,0,.6)],
                [(.5,1,.6),(2,2,.65),(3,1,.3)],
                [(0,0,.65)],
                [(0,2,.3),(.5,1,.3),(1.5,0,.3),(2.5,1,.6)],
                [(1,1,.6),(2,0,.6)],
                [(0,0,.65),(1,2,.3),(2.5,1,.3),(3.5,2,.3)],
                [],
                [(0,2,1.1),(1.5,0,.6),(3,1,.6)],
                [(.5,0,.3),(1.5,2,.3),(2,1,.65),(3,0,.65)],
                [(0,1,.65),(2,2,.65)],
                [(0,0,.4),(1.5,1,.4)],
                [(0,0,.3),(.5,1,.3),(1,2,.6),(2.5,1,.3),(3,2,.6)],
                [(.5,2,.3),(1,0,.6),(2.5,1,.3),(3.5,2,.3)],
                [(0,1,1.4),(2,2,.3),(2.5,1,.3),(3,0,.6)],
                [(0,2,.65),(2,0,.65)],
                [(1,0,.3),(1.5,1,.3),(2,2,.6),(3.5,1,.3)],
                [(.5,2,.65),(2,1,.65),(3,0,.65)],
                [(0,0,.65),(1.5,1,.3),(2,2,.65)],
                [(0,0,.6)],
            ]
            figure = figures[local]
            if majestic:
                figure = ([(0, 0, .5), (2.5, 2, .5)] if local in (0,4,8,12,16,20)
                          else [] if local % 4 in (1,3)
                          else [(1,1,.5),(2,2,.5),(3.5,0,.25)])
            for offset, idx, duration in figure:
                backing_part = 'violins_2' if duration > .75 else 'violin_spiccato'
                put(backing_part, [low+12,mid,high][idx], beat+offset,
                    duration, .68 if offset else .77, 'harmony')
            if local % 4 == 3 or majestic:
                put('cellos', cellobass, beat, 3.6, .69, 'harmony', .97)
                put('basses', bass, beat, 3.5, .67, 'harmony', .97)
            else:
                bass_rhythm = [(0, cellobass, 1.2), (2.5, fifthbass+12, .7)] if local % 3 == 0 else [(0, cellobass,.7),(1.5,fifthbass+12,.45),(3,cellobass,.6)] if local % 3 == 1 else [(0,cellobass,2.5)]
                for offset, p, length in bass_rhythm:
                    put('cello_spiccato', p, beat+offset, min(.5,length), .77, 'harmony')
                    put('basses', p-12, beat+offset, length, .68, 'harmony')
            if local % 4 in (1,2):
                for offset in ((1,2.5) if local % 4 == 1 else (.5,3)):
                    put('viola_spiccato', mid, beat+offset, .32, .62, 'harmony')
            if bar % 8 >= 4 or majestic:
                put("violins_2", high, beat, 1.85, .68, "harmony")
                put("violins_2", mid + 12 if mid < 63 else mid, beat + 2, 1.82, .65, "harmony")
                put("violas", low, beat, 3.7, .63, "harmony")
            if majestic or bar % 8 in (0, 6, 7):
                put("horns", low, beat, 1.8, .70 if majestic else .63, "harmony")
                put("horns", mid, beat + 2, 1.7, .68 if majestic else .60, "harmony")
            if bar % 8 in (2, 3, 6, 7):
                put("bassoon", cellobass, beat + .15, 1.65, .61, "harmony")
            if bar in (8, 24, 30, 31, 80, 86, 87, 96, 100, 102, 103):
                drum = 38 if symbol in ("Dm", "D", "D/F#", "Dm/F") else 45
                put("timpani", drum, beat, .45, .79 if majestic else .65, "timpani")
                if bar in (31, 87, 103):
                    put("timpani", drum, beat + 2, .45, .68, "timpani")
            if bar % 8 == 0:
                for i, p in enumerate([bass + 24, low + 12, mid + 12, high + 12]):
                    put("harp", p, beat + .125 * i, .8, .66, "harmony")
        elif bar < 56:
            # Leave a whole beat between questions; change the bass answer and
            # let the harp enter after the woodwind, rather than on every beat.
            bass_pattern = [(0,cellobass)] if bar % 4 in (0,3) else [(0,cellobass),(2.5,fifthbass+12)]
            for offset, p in bass_pattern:
                put("cello_pizzicato", p, beat + offset, .45, .67, "harmony")
                put("bass_pizzicato", p - 12, beat + offset, .5, .66, "harmony")
            for offset in ((1.5,) if bar % 4 in (0,2) else (1,3)):
                put("viola_pizzicato", mid, beat + offset, .38, .58, "harmony")
            if bar % 4 != 3:
                for part, p in [("violins_2", high), ("violas", low)]:
                    put(part, p, beat + (1 if bar % 4 == 1 else 0), 2.65, .59, "harmony", .98)
            pattern = [low + 12, mid + 12, high, mid + 12]
            if bar % 2:
                pattern = [mid + 12, high + 12, mid + 12, low + 12]
            harp_rhythm = [(1.5,0),(2.5,2)] if bar % 4 == 0 else [(0,0),(.5,1),(1,2),(2.5,3)] if bar % 4 == 1 else [(2,2),(2.5,1),(3,0)] if bar % 4 == 2 else [(0,0)]
            for offset, idx in harp_rhythm:
                put("harp", pattern[idx], beat + offset, .85, .60, "harmony")
            if bar % 8 in (4, 5, 6):
                put("horns", low, beat, 3.45, .48, "harmony")
            if 40 <= bar < 48:
                # A separate, low countermelody remains within the harmony.
                for i, p in enumerate([low, mid, low, high - 12]):
                    put("clarinet", p, beat + i, .86, .53, "counterpoint")
        elif bar < 80:
            # The development answers its fragment in a different register.
            # Motion intensifies in the final eight bars instead of running
            # a constant eighth-note motor through all twenty-four.
            bass_steps = [0,2] if bar < 64 else [0,1.5,3] if bar < 72 else [0,1,2,3]
            for i in bass_steps:
                p = cellobass if i in (0,2,3) else fifthbass+12
                put("cello_spiccato", p, beat + i, .33, .80, "harmony")
                if i in (0, 2):
                    put("basses", cellobass - 12, beat + i, 1.60, .71, "harmony")
            dev_rhythms = [[2,2.5,3.5],[.5,1,1.5],[],[0,1.5,2.5],
                           [0,.5,1.5,2,3],[1,2,2.5],[0,1,3,3.5],[0,2]]
            offsets = dev_rhythms[(bar-56)%8]
            if bar >= 72 and bar % 4 < 2:
                offsets = [0,.5,1,1.5,2,2.5,3] if bar % 2 == 0 else [.5,1.5,2,3,3.5]
            for i, offset in enumerate(offsets):
                put("violin_spiccato", [high, mid, low + 12, mid][i%4], beat + offset,
                    .29, .73 if i % 2 else .79, "harmony")
            for offset in ([1,3] if bar % 2 else [2.5]):
                put("viola_spiccato", mid, beat + offset, .3, .68, "harmony")
            if bar >= 72:
                put("horns", low, beat, 1.8, .77, "harmony")
                put("horns", mid, beat + 2, 1.7, .75, "harmony")
            if bar in (56, 60, 64, 68, 72, 76, 78, 79):
                drum = 38 if bar % 4 == 0 else 45
                put("timpani", drum, beat, .42, .75, "timpani")
            if bar in (78, 79):
                # Measured crescendo roll, physically alternate strokes.
                for i in range(1, 16):
                    put("timpani", 45, beat + i * .25, .20,
                        .42 + i * .018, "timpani", .95)
        else:
            for part, p in [("cellos", cellobass), ("basses", bass),
                            ("violas", mid), ("violins_2", high)]:
                if bar == 115:
                    continue
                dur = 7.7 if bar == 114 else 3.8
                put(part, p, beat, dur, .65 if bar < 110 else .69, "final_tonic" if bar == 114 else "harmony", .98)
            if bar in (104, 108, 110, 112, 114):
                for i, p in enumerate([bass + 24, low + 12, mid + 12, high + 12]):
                    put("harp", p, beat + i * .20, .9, .66, "harmony")
            if bar in (110, 112, 113, 114):
                put("horns", low, beat, 3.55, .59, "harmony")
            if bar == 114:
                put("timpani", 38, beat, .6, .55, "timpani")

    # Three exposed viola replies use the recorded rising intervals. These are
    # passing notes over D minor: D and F occupy the stronger beats, A resolves
    # the climb. Each phrase releases before the next bar and bows anew.
    for phrase, bar in enumerate((1,34,63), 1):
        for pitch, offset, length in [(50,0,1.5),(52,1.5,.5),(53,2,.75),(55,2.75,.25),(57,3,.85)]:
            put('solo_viola', pitch, bar*4+offset, length, .69 + .025*(pitch-50),
                'diatonic_passing_reply', 1)
            notes['solo_viola'][-1].update(slur=phrase, voice='viola_solo')

    # Macro dynamics plus gentle four-bar arches; melody velocities articulate
    # local detail. Recorded legato is explicitly restricted to the solo replies.
    dynamics = [(0, .42), (16, .47), (24, .60), (31, .58),
                (32, .71), (60, .63), (64, .73), (96, .78), (120, .70),
                (127, .53), (128, .52), (152, .63), (159, .53),
                (160, .56), (184, .68), (191, .55), (192, .54),
                (216, .66), (223, .70), (224, .74), (252, .83),
                (256, .63), (284, .80), (288, .78), (308, .90),
                (319, .76), (320, .83), (348, .75), (352, .78),
                (380, .82), (384, .91), (404, .93), (415, .67),
                (416, .57), (436, .50), (440, .59), (452, .66),
                (456, .60), (461, .48), (464, .39)]
    extra_beats = sorted(set([b for b, _ in dynamics] + list(range(0, 465, 4))))
    xp, fp = zip(*dynamics)
    dyn = [[b, float(np.interp(b, xp, fp)) * (1 + .025 * np.sin(2 * np.pi * b / 16))]
           for b in extra_beats]
    c = Composer(ID, tempo=tempo[0][1], duration=300, key="D minor", performance_seed=2026090501)
    c.library(LIBRARY, PIN).tempo_map(tempo)
    for part, (patch, pan, gain, role) in PARTS.items():
        # Explicit note-seconds curves are canonical IR and include the release.
        # Rebase the shared conductor curve; no legacy-field lowering is needed.
        global_seconds = np.array([tm.sec(b) for b, _ in dyn])
        global_values = np.array([v for _, v in dyn])
        for event in notes[part]:
            start = tm.sec(event["start_beat"])
            end = tm.sec(event["start_beat"] + event["dur_beats"]) + 1.5
            times = [start] + [float(t) for t in global_seconds if start < t < end] + [end]
            event["curves"] = [{"target": "dynamic", "time_basis": "note_seconds",
                                "points": [[float(t - start), float(np.interp(t, global_seconds, global_values))]
                                           for t in times]}]
        c.instrument(part, instrument=patch, events=sorted(notes[part], key=lambda e: (e["start_beat"], e["note"])),
                     gain_db=gain - 9.0, humanize=(.006, .023))
        c.spec["layers"][-1].update(pan=pan, role=role)
    c.master(target_lufs=-20.0, peak_db=-1.2, fade_in_s=.035, fade_out_s=2.0,
             fx=[{"type": "filter", "mode": "highpass", "cutoff_hz": 28.0},
                 {"type": "hall", "rt60": 2.3, "damp": .43, "mix": .20}])
    spec = c.to_dsl_spec()
    spec.update(sample_rate=48000, bit_depth=24, loop_safe=False,
                routing={"fallbacks": "forbid", "sustain_gaps": "forbid", "stretch_warn_semitones": 3.0})
    spec["score"] = {"meter": {"beats": 4, "unit": 4}, "sections": [
        {"name": title.replace(" ", "_"), "start_beat": a * 4, "dur_beats": (b - a) * 4}
        for a, b, title, _, _ in SECTIONS]}
    spec["markers"] = [{"name": title.replace(" ", "_"), "time_s": float(tm.sec(a * 4))} for a, _, title, _, _ in SECTIONS]
    spec["key_map"] = [[0, "D", "minor"], [128, "F", "major"], [224, "D", "minor"], [320, "D", "major"]]
    validate_spec(spec)
    # The delivered .af is authoritative; compile it before writing the IR.
    source = spec_to_dsl(spec)
    if 'library:' not in source:
        source = source.replace(f"asset {ID} {{\n", f'asset {ID} {{\n  library: "{LIBRARY}@{PIN}"\n', 1)
    compiled, warnings = compile_dsl(source)
    assert len(compiled) == 1 and not warnings, warnings
    resolved = validate_spec(compiled[0])
    for before, after in zip(spec["layers"], resolved["layers"]):
        assert before["notes"] == after["notes"], before["name"]
    program = {
        "title": "The First Light", "subtitle": "Overture in D minor and D major",
        "duration_s": 300, "authored_bars": 116, "quarter_beats": 464,
        "score_end_s": 294, "tail_budget_s": 6, "performance_seed": 2026090501,
        "sections": [{"name": title, "character": character, "key": key,
                      "start_bar": a + 1, "end_bar": b,
                      "start_s": float(tm.sec(a * 4)), "end_s": float(tm.sec(b * 4))}
                     for a, b, title, character, key in SECTIONS],
        "notes": len(ledger), "parts": {k: {"patch": v[0], "role": v[3], "notes": len(notes[k])} for k, v in PARTS.items()},
        "harmony": voicings, "note_ledger": ledger,
        "themes": {"A": THEME_A, "B": THEME_B},
        "sample_source": {"name": LIBRARY, "pin": PIN, "credit": "Versilian Studios VSCO 2 Community Edition; David Hilowitz educational viola legato demo",
                          "license_file": "libraries/VSCO-2-CE-1.1.0/LICENSE"},
        "interpretation": "Native stereo recordings; 12 recorded viola transitions in three exposed replies. Written breath/bow changes elsewhere. Accompaniment uses rests, varied figures and a broader reprise. No synthesized articulation fallbacks or multiplied sample ensembles.",
    }
    return resolved, source, program


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", type=Path, help="Render the validated composition to this output directory")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    spec, source, program = build()
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / f"{ID}.af").write_text(source)
    (HERE / f"{ID}.ir.json").write_text(json.dumps(spec, indent=2) + "\n")
    (HERE / "program.json").write_text(json.dumps(program, indent=2) + "\n")
    from audioforge.sdk import AudioAsset
    from audioforge.plan import build_render_plan
    issues = AudioAsset(spec).validate()
    assert not issues, [d.as_dict() for d in issues]
    plan = build_render_plan(spec)
    print(json.dumps({"notes": program["notes"], "layers": len(spec["layers"]),
                      "diagnostics": plan.diagnostics, "sections": program["sections"]}, indent=2), flush=True)
    if args.render:
        from audioforge.render import render_to_wav
        meta = render_to_wav(spec, args.render, stems=True, jobs=args.jobs, render_plan=plan.plan)
        print(json.dumps({"file": meta["file"], "sha256": meta["output_sha256"],
                          "loudness": meta.get("loudness")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
