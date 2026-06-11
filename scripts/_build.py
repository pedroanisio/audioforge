import json
d=json.load(open("/tmp/chopin_notes.json")); ev=d["events"]; bpm=44.0
NAMES={0:"C",1:"C#",2:"D",3:"D#",4:"E",5:"F",6:"F#",7:"G",8:"G#",9:"A",10:"A#",11:"B"}
def nm(m): return f"{NAMES[m%12]}{m//12-1}"
def fmt(notes): return ",\n           ".join(f"{nm(p)} @ {s}b for {max(d2,0.05)}b vel {v}" for s,d2,p,v in notes)
AF=f"""# Chopin - Prelude Op.28 No.4 in E minor — accurate recreation from the score.
# warm triangle body + sine sub + bright pluck 'hammer' attack (piano realism).
asset chopin_em_accurate {{
  kind: signature
  duration: 150s
  samplerate: 48000
  bitdepth: 24
  tempo: {bpm}bpm
  key: E minor
  bus piano_bus {{ gain: 0db
    fx: reverb(decay=2.2, mix=0.18) }}
  layer body : notes {{
    osc: triangle
    gain: -7db
    env: a=0.006s d=3.2s s=0.0 r=1.1s
    humanize: time=0.008s vel=0.05
    bus: piano_bus
    fx: lowpass(4200hz, q=0.6)
    notes: {fmt(ev)}
  }}
  layer attack : notes {{
    osc: pluck
    damping: 0.5
    brightness: 0.6
    pluckpos: 0.13
    gain: -14db
    env: a=0.001s d=0.25s s=0.0 r=0.1s
    bus: piano_bus
    notes: {fmt(ev)}
  }}
  layer sub : notes {{
    osc: sine
    gain: -15db
    env: a=0.006s d=3.5s s=0.0 r=1.2s
    notes: {fmt([(s,d2,p-12,round(v*0.8,2)) for s,d2,p,v in ev if p-12>=28])}
  }}
  master {{ width: 0.5
    lufs: -18
    peak: -1db
    fadein: 0.1s
    fadeout: 3s
    fx: comp(threshold=-18, ratio=1.6, attack=0.01, release=0.25, knee=8),
        highpass(32hz), lowshelf(150hz, gain=1.2) }}
}}
"""
open("/tmp/chopin_em.af","w").write(AF)
print(f"{len(ev)} notes x3 layers, {bpm}bpm")
