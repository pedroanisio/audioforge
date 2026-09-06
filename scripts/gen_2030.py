#!/usr/bin/env python3
"""Generate docs/examples/orchestral/2030/2030.af — the "Painting with FrameGraph" theme.

Non-looping VSCO sustains cannot hold a 20 s chord, so the sustained material
is carried by a seamless synth pad while the sampled strings/basses are
re-articulated (re-bowed) every REBOW beats — well inside the shortest sample —
so the render never falls to unplanned silence. Verified by driving the
engine's render_plan_sustain_gap warnings to zero.
"""
from pathlib import Path

BPM = 90
SPB = 60.0 / BPM          # seconds per beat
REBOW = 6                 # re-bow every 6 beats (4.0 s) < ~6.9 s shortest sample
LIB = ("VSCO-2-CE-1.1.0@"
       "ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e")

# (start_beat, end_beat, pad chord tones, sampled string tones, bass root)
REGIONS = [
    (0,   30,  ["A2", "E3", "A3", "C4"],  ["A3", "C4", "E4"], "A2"),
    (30,  60,  ["F2", "C3", "A3", "E4"],  ["A3", "C4", "E4"], "F2"),
    (60,  90,  ["D2", "A2", "F3", "C4"],  ["A3", "C4", "F4"], "D2"),
    (90,  120, ["E2", "B2", "G3", "D4"],  ["B3", "D4", "G4"], "E2"),
    (120, 150, ["C3", "G3", "E4", "B4"],  ["C4", "E4", "G4"], "C3"),  # C major
    (150, 165, ["F2", "C3", "A3", "E4"],  ["A3", "C4", "E4"], "F2"),
    (165, 180, ["C3", "G3", "E4", "B4"],  ["C4", "E4", "G4"], "C3"),
]


def rebow(start, end, pitches, dur_b, vel):
    """Re-articulated events every REBOW beats across [start, end)."""
    out = []
    b = start
    while b < end - 1e-6:
        d = min(dur_b, end - b)
        for p in pitches:
            out.append(f"{p} @ {b}b for {d:.3g}b vel {vel}")
        b += REBOW
    return out


def held(start, end, pitches, vel):
    d = end - start
    return [f"{p} @ {start}b for {d:g}b vel {vel}" for p in pitches]


def notes_block(events, indent=11):
    pad = " " * indent
    return (",\n" + pad).join(events)


pad_events, string_events, bass_events = [], [], []
for s, e, pad_ch, str_ch, root in REGIONS:
    pad_events += held(s, e, pad_ch, 0.7)               # seamless synth bed
    string_events += rebow(s, e, str_ch, REBOW + 0.5, 0.55)  # re-bowed color
    bass_events += rebow(s, e, [root], REBOW + 0.5, 0.6)

# tremolo "detail" bloom — re-triggered so it never runs dry
trem = []
for b in range(36, 174, 8):
    if b < 66:
        p = "A3"
    elif b < 120:
        p = "E4"
    elif b < 160:
        p = "C4"
    else:
        p = "G4"
    trem.append(f"{p} @ {b}b for 8.5b vel 0.55")

AF = f"""# 2030 — theme for "Painting with FrameGraph"  (orchestral, gap-safe)
# A reading of framegraph-reconstruction-evolution-4k60.mp4 in sound.
# Voiced with the VSCO-2 Community Edition orchestra (content-addressed, pinned).
# Sustained bed = seamless synth pad; sampled strings/basses are re-bowed every
# {REBOW} beats (VSCO sustains are non-looping ~7 s one-shots). Verified: zero
# render_plan_sustain_gap warnings.  Foundation -> Composition -> Grind ->
# Restart at v90 (A minor -> C major) -> Refinement, over an invariant clock.

asset theme_2030 {{
  kind: cue
  duration: 120s
  tempo: {BPM}bpm
  key: A minor, 120b=C major
  library: "{LIB}"
  emotion: wonder=0.55, awe=0.4, tension=0.3, triumph=0.45, calm=0.35, intimacy=0.2
  intensity: 0s=0.15, 24s=0.32, 44s=0.55, 78s=0.6, 80s=0.34, 84s=0.42, 110s=0.9, 116s=0.86, 120s=0.7

  marker foundation  @ 0s
  marker composition @ 24s
  marker grind       @ 44s
  marker restart     @ 80s
  marker refinement  @ 84s
  marker final_frame @ 116s

  motif seed {{
    A3 @ 0b   for 1b   vel 0.6
    C4 @ 1b   for 1b   vel 0.66
    E4 @ 2b   for 1.5b vel 0.72
    D4 @ 3.5b for 1.5b vel 0.68
  }}

  # Act I underpainting: a seamless synth pad — the large, stable regions that never drop.
  layer bed : notes {{
    osc: pad
    bandwidth: 55c
    gain: -14db
    env: a=3s d=2s s=0.85 r=5s
    notes: {notes_block(pad_events)}
    fx: lowpass(1500hz), reverb(decay=5s, mix=0.3)
    auto cutoff: 0s=600, 44s=1500, 80s=850, 116s=2600
  }}

  # real string color on top, re-bowed so the non-looping samples never run out
  layer strings : instrument {{
    instrument: CelloEnsSusVib
    articulation: sustain
    section: size=3 spread=0.7
    gain: -15db
    notes: {notes_block(string_events)}
  }}

  # low weight: contrabass roots, re-bowed
  layer basses : instrument {{
    instrument: ContrabassSusVB
    gain: -15db
    notes: {notes_block(bass_events)}
  }}

  # the verification loop: a quiet, invariant synth tick, running the entire way down
  layer clock : notes {{
    osc: pluck
    damping: 0.6
    brightness: 0.45
    gain: -25db
    env: a=0.004s d=0.14s s=0.0 r=0.14s
    notes: A5 @ 0b for 0.5b vel 0.5
    loop: 1b
    pan: 0.26
  }}

  # Act II bloom: detail arrives all at once (8 -> 1,171) — tremolo strings, re-triggered
  layer detail : instrument {{
    instrument: CelloEnsTrem
    section: size=2 spread=0.6
    gain: -18db
    start: 22s
    notes: {notes_block(trem)}
    pan: 0.16
  }}

  # Act III grind: the reconstruction, trial by trial (each play is a version bump), on oboe.
  layer reconstruct : instrument {{
    instrument: OboeSusVib
    gain: -13db
    dynamic: 36b=mp, 96b=mf, 120b=mp, 160b=f
    play seed @ 36b  transpose +12st
    play seed @ 44b  invert transpose +12st vel 0.9
    play seed @ 60b  diatonic 2 transpose +12st
    play seed @ 78b  retrograde diatonic -1 transpose +12st
    play seed @ 96b  stretch 1.5 transpose +12st vel 0.85
    play seed @ 108b diatonic 1 transpose +12st
    play seed @ 120b transpose +12st vel 0.7
    play seed @ 132b diatonic 2 transpose +12st vel 0.85
    pan: -0.22
  }}

  # Act V: the same figure, drawn better — a noble French-horn statement in the C-major redo.
  layer singing : instrument {{
    instrument: FHornSus
    gain: -12db
    start: 82s
    dynamic: 120b=mp, 144b=mf, 175b=f
    play seed @ 132b diatonic 2 legato
    play seed @ 150b diatonic 4
    play seed @ 162b diatonic 2
    pan: 0.2
  }}

  # the deterministic backbone: soft timpani at structural arrivals, grounding the grid
  layer heartbeat : instrument {{
    instrument: Timpani
    gain: -12db
    humanize: 0.06
    notes: A2 @ 60b  for 1b vel 0.4,
           E2 @ 96b  for 1b vel 0.45,
           C2 @ 120b for 1b vel 0.7,
           C2 @ 136b for 1b vel 0.5,
           G2 @ 152b for 1b vel 0.55,
           C2 @ 160b for 1b vel 0.7,
           C2 @ 168b for 1b vel 0.6
    pan: -0.08
  }}

  master {{
    width: 1.0
    lufs: -16
    peak: -1db
    fadein: 1.5s
    fadeout: 3.5s
    fx: peak(220hz, gain=-1.5, q=0.9), fdn(rt60=3.2, rt60_high=1.3, mix=0.26), saturate(amount=0.1, warmth=0.3)
  }}
}}
"""

Path("docs/examples/orchestral/2030/2030.af").write_text(AF)
print("wrote docs/examples/orchestral/2030/2030.af",
      f"({len(pad_events)} pad, {len(string_events)} string, "
      f"{len(bass_events)} bass, {len(trem)} trem events)")
