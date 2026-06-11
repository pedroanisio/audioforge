import json, wave, numpy as np
ev=json.load(open("/tmp/chopin_notes.json"))["events"]; bpm=44.0
# 1) extract the reference loudness arc (the performance's dynamic shape)
w=wave.open("/tmp/chopin_ref.wav","rb");n,ch,sw,sr=w.getnframes(),w.getnchannels(),w.getsampwidth(),w.getframerate();raw=w.readframes(n);w.close()
a=np.frombuffer(raw,np.uint8).reshape(-1,3).astype(np.int32);xr=(a[:,0]|a[:,1]<<8|(a[:,2].astype(np.int8).astype(np.int32))<<16).reshape(-1,ch).mean(1)/2**23
win=int(0.7*sr); env=np.array([np.sqrt((xr[i:i+win]**2).mean()) for i in range(0,len(xr)-win,win)])
env=np.convolve(env,np.ones(3)/3,'same'); env=(env-env.min())/(env.max()-env.min()+1e-9)  # 0..1 arc
def arc_at(tn): return float(env[min(len(env)-1,int(tn*len(env)))])
# 2) melody = highest pitch per half-beat onset group
maxb=max(s+d for s,d,p,v in ev)
groups={}
for s,d,p,v in ev: groups.setdefault(round(s*2)/2,[]).append(p)
top={k:max(v) for k,v in groups.items()}
NAMES={0:"C",1:"C#",2:"D",3:"D#",4:"E",5:"F",6:"F#",7:"G",8:"G#",9:"A",10:"A#",11:"B"}
def nm(m): return f"{NAMES[m%12]}{m//12-1}"
mel,acc=[],[]
for s,d,p,v in ev:
    tn=s/maxb; dyn=0.5+0.6*arc_at(tn)               # performance dynamic arc
    is_mel = p==top.get(round(s*2)/2,-1) and p>=64    # top voice, RH register
    vv=round(min(0.99,v*dyn*(1.18 if is_mel else 0.9)),3)
    (mel if is_mel else acc).append((s,d,p,vv))
def fmt(notes): return ",\n           ".join(f"{nm(p)} @ {s}b for {max(d,0.05)}b vel {vv}" for s,d,p,vv in notes)
sub=[(s,d,p-12,round(vv*0.8,3)) for s,d,p,vv in acc if p-12>=28]
AF=f"""# Chopin Prelude Op.28 No.4 — REFINED: voiced melody, pedal blur,
# performance dynamic-arc mapped from the reference, velocity->brightness.
asset chopin_em_refined {{
  kind: signature
  duration: 152s
  samplerate: 48000
  bitdepth: 24
  tempo: {bpm}bpm
  key: E minor
  bus hall {{ gain: 0db
    fx: reverb(decay=2.6, mix=0.2) }}
  layer accomp : notes {{
    osc: triangle
    gain: -10db
    env: a=0.01s d=3.6s s=0.0 r=1.6s
    velbright: 0.5
    humanize: time=0.012s vel=0.06
    bus: hall
    fx: lowpass(3600hz, q=0.6)
    notes: {fmt(acc)}
  }}
  layer melody : notes {{
    osc: triangle
    gain: -5db
    env: a=0.008s d=3.0s s=0.0 r=1.4s
    velbright: 0.6
    humanize: time=0.009s vel=0.04
    bus: hall
    fx: lowpass(4600hz, q=0.6)
    notes: {fmt(mel)}
  }}
  layer attack : notes {{
    osc: pluck
    damping: 0.5
    brightness: 0.55
    pluckpos: 0.13
    gain: -30db
    env: a=0.001s d=0.22s s=0.0 r=0.1s
    bus: hall
    notes: {fmt(mel+acc)}
  }}
  layer sub : notes {{
    osc: sine
    gain: -15db
    env: a=0.01s d=3.8s s=0.0 r=1.6s
    notes: {fmt(sub)}
  }}
  master {{ width: 0.5
    lufs: -18
    peak: -1db
    fadein: 0.2s
    fadeout: 4s
    fx: comp(threshold=-19, ratio=1.5, attack=0.012, release=0.28, knee=9),
        highpass(32hz), lowshelf(150hz, gain=1.2), highshelf(8500hz, gain=0.5) }}
}}
"""
open("/tmp/chopin_refined.af","w").write(AF)
print(f"melody {len(mel)} notes, accomp {len(acc)}, arc points {len(env)}")
