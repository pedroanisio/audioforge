import math
from pathlib import Path
BPM=112
NAMES={0:"C",1:"C#",2:"D",3:"D#",4:"E",5:"F",6:"F#",7:"G",8:"G#",9:"A",10:"A#",11:"B"}
def nm(m): return f"{NAMES[m%12]}{m//12-1}"
# E major ritornello of La Primavera (stylistic recreation): triadic "birdsong"
# theme, forte then piano echo, then a B7->E cadence. Vln1 melody (MIDI):
E5,Gs5,B5,A5,Fs5,Ds5,Cs5,B4,E4,Gs4=76,80,83,81,78,75,73,71,64,68
THEME=[ (0,1,E5),(1,1,Gs5),(2,1,B5),(3,1,B5),
        (4,.5,A5),(4.5,.5,Gs5),(5,.5,A5),(5.5,.5,Gs5),(6,1,Fs5),(7,1,E5) ]
def shift(theme,beat,oct=0): return [(b+beat,d,p+12*oct) for b,d,p in theme]
vln1=[]
vln1+=[(b,d,p,0.85) for b,d,p in shift(THEME,0)]          # forte
vln1+=[(b,d,p,0.5)  for b,d,p in shift(THEME,8)]          # piano echo
# cadence phrase (B7 -> E): a scalar flourish + trill, bars 5-8 (beats16-31)
cad=[(16,.5,Fs5),(16.5,.5,Gs5),(17,.5,A5),(17.5,.5,B5),(18,1,A5),(19,1,Gs5),
     (20,.5,Fs5),(20.5,.5,Ds5),(21,.5,Fs5),(21.5,.5,A5),(22,2,Gs5),
     (24,1,E5),(25,1,Gs5),(26,2,B5),(28,1,A5),(29,1,Fs5),(30,2,E5)]
vln1+=[(b,d,p,0.8) for b,d,p in cad]
# harmony chords per 2-beat region (E=I, B7=V).  (root, [triad tones])
def chordbeats():
    plan={0:[64,68,71],2:[64,68,71],4:[64,68,71],6:[59,64,68], # E .. E .. E .. (E/B)
          8:[64,68,71],10:[64,68,71],12:[64,68,71],14:[59,64,68],
          16:[59,63,66],18:[59,63,66],20:[59,63,66],22:[59,63,66], # B7
          24:[64,68,71],26:[64,68,71],28:[59,63,66],30:[64,68,71]} # E .. B7 E
    return plan
vln2,viola,bass=[],[],[]
plan=chordbeats()
for b in sorted(plan):
    t=plan[b]; vel=0.6 if (8<=b<16) else 0.72
    vln2.append((b,2,t[1],round(vel,2)))     # middle voice
    viola.append((b,2,t[0],round(vel-0.05,2)))
    root=40 if b in (16,18,20,22,28) else 40  # E2 default
    root=35 if b in (16,18,20,22,28) else 40   # B1 under B7, else E2
    bass.append((b,2,root,round(0.7,2)))
def fmt(ns): return ",\n           ".join(f"{nm(m)} @ {b}b for {d}b vel {v}" for b,d,m,v in ns)
DUR=round((32)*60/BPM)+3
AF=f"""# Vivaldi - La Primavera (Spring) RV269 mvt I — ritornello, stylistic recreation.
# Synth string ensemble (saw+filter) — approximation of the theme for A/B vs a
# real orchestral recording. Composition public domain; recreation original.
asset vivaldi_spring_recreation {{
  kind: cue
  duration: {DUR}s
  samplerate: 48000
  bitdepth: 24
  tempo: {BPM}bpm
  key: E major
  bus strings {{
    gain: 0db
    fx: reverb(decay=1.8, mix=0.22), peak(2500hz, gain=1.5, q=0.7)
  }}
  layer vln1 : notes {{
    osc: saw
    detune: 7c
    gain: -7db
    pan: -0.1
    env: a=0.04s d=0.1s s=0.85 r=0.35s
    vibrato: rate=5.5 depth=12c delay=0.25s
    bus: strings
    humanize: time=0.01s vel=0.06
    fx: lowpass(4200hz, q=0.7)
    notes: {fmt(vln1)}
  }}
  layer vln2 : notes {{
    osc: saw
    detune: 6c
    gain: -12db
    pan: 0.18
    env: a=0.08s d=0.1s s=0.85 r=0.4s
    bus: strings
    humanize: time=0.012s vel=0.07
    fx: lowpass(3400hz)
    notes: {fmt(vln2)}
  }}
  layer viola : notes {{
    osc: saw
    detune: 5c
    gain: -13db
    pan: -0.2
    env: a=0.1s d=0.1s s=0.85 r=0.4s
    bus: strings
    fx: lowpass(2600hz)
    notes: {fmt(viola)}
  }}
  layer bass : notes {{
    osc: saw
    gain: -10db
    pan: 0.05
    env: a=0.06s d=0.1s s=0.8 r=0.3s
    bus: strings
    fx: lowpass(1400hz), saturate(amount=0.1, warmth=0.5)
    notes: {fmt(bass)}
  }}
  master {{
    width: 0.7
    lufs: -16
    peak: -1db
    fadein: 0.1s
    fadeout: 1.5s
    fx: fdn(rt60=2.0, rt60_high=0.9, crossover=2200, size=0.8, mix=0.14),
        comp(threshold=-16, ratio=1.8, attack=0.01, release=0.18, knee=8),
        highpass(40hz), highshelf(9000hz, gain=1.0)
  }}
}}
"""
Path("/tmp/vivaldi_spring.af").write_text(AF)
print(f"vln1={len(vln1)} notes, dur {DUR}s, E major @ {BPM}bpm")
