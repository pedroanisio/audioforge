#!/usr/bin/env python3
"""Generate docs/examples/orchestral/to-be-alive/to_be_alive.af — a 120 s celebration of being alive
and making art. D major, lifting to E major at the radiant climax.

Textures that cannot sustain-gap (harp, pizzicato, spiccato, glockenspiel,
short brass) carry the energy; a seamless synth pad carries the warmth. All
sampled sustains are kept within the ~7 s non-looping sample floor, verified by
driving the engine's render_plan_sustain_gap warnings to zero.
"""
from pathlib import Path

BPM = 100          # 1 beat = 0.6 s; 120 s = 200 beats = 50 bars
LIB = ("VSCO-2-CE-1.1.0@"
       "ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e")

# (start, end, pad[4 tones], bass root, triad[3])  — harmonic timeline
D = "D major"
REGIONS = [
    # Dawn: a D pedal, waking
    (0,   24,  ["D3", "A3", "D4", "F#4"], "D2",  ["D4", "F#4", "A4"]),
    # Theme: I–V–vi–IV in D, twice
    (24,  32,  ["D3", "A3", "D4", "F#4"], "D2",  ["D4", "F#4", "A4"]),
    (32,  40,  ["A2", "E3", "A3", "C#4"], "A2",  ["A3", "C#4", "E4"]),
    (40,  48,  ["B2", "F#3", "B3", "D4"], "B2",  ["B3", "D4", "F#4"]),
    (48,  56,  ["G2", "D3", "G3", "B3"],  "G2",  ["G3", "B3", "D4"]),
    (56,  64,  ["D3", "A3", "D4", "F#4"], "D2",  ["D4", "F#4", "A4"]),
    (64,  72,  ["A2", "E3", "A3", "C#4"], "A2",  ["A3", "C#4", "E4"]),
    (72,  80,  ["B2", "F#3", "B3", "D4"], "B2",  ["B3", "D4", "F#4"]),
    (80,  88,  ["G2", "D3", "G3", "B3"],  "G2",  ["G3", "B3", "D4"]),
    # Build toward the lift
    (88,  96,  ["B2", "F#3", "B3", "D4"], "B2",  ["B3", "D4", "F#4"]),
    (96,  104, ["G2", "D3", "G3", "B3"],  "G2",  ["G3", "B3", "D4"]),
    (104, 112, ["A2", "E3", "A3", "C#4"], "A2",  ["A3", "C#4", "E4"]),
    # Climax: lift to E major, I–V–vi–IV
    (112, 120, ["E3", "B3", "E4", "G#4"], "E2",  ["E4", "G#4", "B4"]),
    (120, 128, ["B2", "F#3", "B3", "D#4"], "B2", ["B3", "D#4", "F#4"]),
    (128, 136, ["C#3", "G#3", "C#4", "E4"], "C#2", ["C#4", "E4", "G#4"]),
    (136, 144, ["A2", "E3", "A3", "C#4"], "A2",  ["A3", "C#4", "E4"]),
    (144, 152, ["E3", "B3", "E4", "G#4"], "E2",  ["E4", "G#4", "B4"]),
    (152, 160, ["B2", "F#3", "B3", "D#4"], "B2", ["B3", "D#4", "F#4"]),
    (160, 168, ["A2", "E3", "A3", "C#4"], "A2",  ["A3", "C#4", "E4"]),
    # Resolution: gratitude, settling on radiant E
    (168, 176, ["A2", "E3", "A3", "C#4"], "A2",  ["A3", "C#4", "E4"]),
    (176, 184, ["E3", "B3", "E4", "G#4"], "E2",  ["E4", "G#4", "B4"]),
    (184, 200, ["E3", "B3", "E4", "G#4"], "E2",  ["E4", "G#4", "B4"]),
]


def ev(p, s, d, v):
    return f"{p} @ {s:g}b for {d:g}b vel {v}"


def _oct(p):
    """Up an octave (note-name string)."""
    note, octv = p[:-1], int(p[-1])
    return f"{note}{octv + 1}"


pad, harp, pizz, spic, glock, horns = [], [], [], [], [], []
for s, e, ptones, root, triad in REGIONS:
    span = e - s
    for p in ptones:
        pad.append(ev(p, s, span, 0.6))
    dawn = e <= 24
    theme = 24 <= s < 88
    build = 88 <= s < 112
    climax = 112 <= s < 168
    reso = s >= 168
    if not dawn:
        pool = [ptones[0], triad[0], triad[1], triad[2],
                _oct(triad[0]), _oct(triad[1])]
        pat = pool + pool[-2:0:-1]
        b, i = s, 0
        while b < e - 1e-6:
            harp.append(ev(pat[i % len(pat)], b, 0.5, 0.5 if (i % 2) else 0.62))
            b += 0.5
            i += 1
    if not dawn:
        b = s
        while b < e - 1e-6:
            harder = (b - s) % 4 == 0
            pizz.append(ev(root, b, 0.9, 0.72 if harder else 0.55))
            b += 1
    if build or climax:
        b = s + 0.5
        while b < e - 1e-6:
            for t in triad:
                spic.append(ev(t, b, 0.4, 0.6))
            b += 1
    if climax or reso or (theme and s % 16 == 8):
        glock.append(ev(_oct(triad[2]), s, 1.0, 0.55 if reso else 0.6))
        if climax:
            glock.append(ev(_oct(triad[1]), s + 2, 0.75, 0.5))
    if climax or reso:
        for t in (ptones[1], triad[0], triad[2]):
            horns.append(ev(t, s, min(span, 6), 0.62 if climax else 0.5))


def block(evs, indent=11):
    return (",\n" + " " * indent).join(evs)


AF = f"""# to_be_alive — a 120 s celebration of being alive and making art.
# D major, lifting to E major at the climax. Plucky, life-affirming textures
# (harp, pizzicato, spiccato, glockenspiel) over a seamless synth pad; violins,
# horns and trumpet soar at the peak. Verified: zero render_plan_sustain_gap.

asset to_be_alive {{
  kind: soundtrack
  duration: 120s
  tempo: {BPM}bpm
  key: {D}, 112b=E major
  library: "{LIB}"
  emotion: wonder=0.7, awe=0.55, triumph=0.6, calm=0.4, intimacy=0.35, cinematic_intensity=0.3
  intensity: 0s=0.28, 14s=0.5, 34s=0.62, 53s=0.72, 67s=0.95, 91s=1.0, 101s=0.8, 116s=0.62

  marker dawn        @ 0s
  marker theme       @ 14.4s
  marker build       @ 52.8s
  marker climax      @ 67.2s
  marker resolution  @ 100.8s

  # the joy motif — an arch that opens upward and settles home
  motif joy {{
    D4  @ 0b   for 1b   vel 0.7
    F#4 @ 1b   for 1b   vel 0.75
    A4  @ 2b   for 1b   vel 0.8
    B4  @ 3b   for 1b   vel 0.82
    A4  @ 4b   for 2b   vel 0.85
    F#4 @ 6b   for 1.5b vel 0.75
  }}

  # seamless warmth — the harmonic ground that never drops
  layer bed : notes {{
    osc: pad
    bandwidth: 50c
    gain: -15db
    env: a=2.5s d=2s s=0.85 r=5s
    notes: {block(pad)}
    fx: lowpass(2200hz), reverb(decay=4.5s, mix=0.28)
    auto cutoff: 0s=700, 24s=1600, 112s=3200, 168s=2400
  }}

  # the making of art — flowing harp arpeggios, humanized so they breathe
  layer harp : instrument {{
    instrument: Harp
    gain: -14db
    humanize: 0.14
    notes: {block(harp)}
    pan: 0.22
  }}

  # the singing voice — violins carry the joy theme, brighter each return
  layer melody : instrument {{
    instrument: ViolinEnsSusVib
    section: size=2 spread=0.6
    gain: -12db
    phrasing: 0.4
    humanize: 0.08
    dynamic: 24b=mp, 56b=mf, 112b=f, 160b=ff, 176b=mp
    play joy @ 24b
    play joy @ 32b diatonic 1
    play joy @ 40b diatonic -1
    play joy @ 48b
    play joy @ 56b transpose +12st vel 0.85
    play joy @ 64b diatonic 1 transpose +12st
    play joy @ 72b diatonic -1 transpose +12st
    play joy @ 80b diatonic 1 transpose +12st
    play joy @ 88b transpose +12st vel 0.9
    play joy @ 96b diatonic 1 transpose +12st
    play joy @ 104b diatonic 1 transpose +12st
    play joy @ 112b transpose +14st vel 0.95
    play joy @ 120b transpose +2st
    play joy @ 128b transpose +14st
    play joy @ 136b transpose +2st
    play joy @ 144b transpose +14st
    play joy @ 152b transpose +2st vel 0.95
    play joy @ 160b transpose +14st vel 1.0
    play joy @ 168b transpose +2st vel 0.7
    play joy @ 176b transpose +2st vel 0.65
    play joy @ 184b stretch 1.5 transpose +2st vel 0.6
    fx: reverb(decay=3.5s, mix=0.22)
    pan: -0.12
  }}

  # first breath at dawn, and a gentle counter-voice — flute
  layer flute : instrument {{
    instrument: FluteSusVib
    gain: -15db
    play joy @ 4b transpose +12st vel 0.5
    play joy @ 14b diatonic 1 transpose +12st vel 0.55
    play joy @ 64b diatonic 2 transpose +12st vel 0.5
    play joy @ 128b transpose +14st vel 0.6
    fx: reverb(decay=3s, mix=0.25)
    pan: 0.3
  }}

  # dancing feet — spiccato violins on the offbeats
  layer dance : instrument {{
    instrument: ViolinEnsSpic
    section: size=2 spread=0.55
    gain: -18db
    humanize: 0.16
    notes: {block(spic)}
    pan: 0.14
  }}

  # bouncing pulse — pizzicato contrabass
  layer pizzbass : instrument {{
    instrument: ContrabassPizz
    gain: -12db
    humanize: 0.12
    notes: {block(pizz)}
    pan: -0.06
  }}

  # sparkle of wonder — glockenspiel
  layer glock : instrument {{
    instrument: Glockenspiel
    gain: -19db
    notes: {block(glock)}
    pan: 0.26
  }}

  # the soaring — french-horn warmth through the climax
  layer horns : instrument {{
    instrument: FHornSus
    section: size=2 spread=0.5
    gain: -14db
    start: 66s
    notes: {block(horns)}
    pan: -0.2
  }}

  # the fanfare — trumpet joins the theme at the peak
  layer trumpet : instrument {{
    instrument: TrumpetSusVib
    gain: -15db
    start: 66s
    dynamic: 112b=mf, 152b=ff
    play joy @ 112b transpose +2st vel 0.8
    play joy @ 128b invert transpose +2st
    play joy @ 144b transpose +2st vel 0.9
    play joy @ 160b transpose +2st vel 0.95
    fx: reverb(decay=3s, mix=0.2)
    pan: 0.1
  }}

  # the lift — timpani rolls swell into each arrival
  layer timproll : instrument {{
    instrument: TimpaniRolls
    gain: -16db
    dynamic: 106b=pp, 111b=f, 158b=mp, 160b=ff
    notes: A2 @ 106b for 6b vel 0.6,
           E2 @ 158b for 3b vel 0.7
    pan: 0.0
  }}

  # celebration — timpani at the arrivals
  layer timp : instrument {{
    instrument: Timpani
    gain: -13db
    humanize: 0.05
    notes: D2 @ 88b for 1b vel 0.5,
           A2 @ 104b for 1b vel 0.55,
           E2 @ 112b for 1b vel 0.8,
           E2 @ 120b for 1b vel 0.5,
           C#2 @ 128b for 1b vel 0.5,
           A2 @ 136b for 1b vel 0.6,
           E2 @ 144b for 1b vel 0.75,
           E2 @ 152b for 1b vel 0.8,
           A2 @ 160b for 1b vel 0.7,
           E2 @ 176b for 1b vel 0.6,
           E2 @ 184b for 1b vel 0.7
    pan: 0.0
  }}

  master {{
    width: 1.0
    lufs: -15
    peak: -1db
    fadein: 1.5s
    fadeout: 4s
    fx: lowshelf(140hz, 2.5), peak(320hz, gain=-1.2, q=1.0), comp(threshold=-18, ratio=1.8, attack=0.02, release=0.22, knee=6), fdn(rt60=3.4, rt60_high=1.4, mix=0.22), saturate(amount=0.1, warmth=0.35)
  }}
}}
"""

Path("docs/examples/orchestral/to-be-alive/to_be_alive.af").write_text(AF)
print("wrote docs/examples/orchestral/to-be-alive/to_be_alive.af",
      f"(pad {len(pad)}, harp {len(harp)}, pizz {len(pizz)}, "
      f"spic {len(spic)}, glock {len(glock)}, horns {len(horns)})")
