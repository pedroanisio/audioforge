import hashlib, math
from pathlib import Path
REPO = Path("/home/administrator/Downloads/audioforge_v2_13/audioforge")
IR_SHA = hashlib.sha256((REPO / "audioforge/data/samples/stalbans_ortf_ir.wav").read_bytes()).hexdigest()
BPM=60
NAMES={0:"C",1:"C#",2:"D",3:"D#",4:"E",5:"F",6:"F#",7:"G",8:"G#",9:"A",10:"A#",11:"B"}
def nm(m): return f"{NAMES[m%12]}{m//12-1}"
SCALE=[9,11,1,2,4,6,8]
def snap(m): return min(range(m-2,m+3), key=lambda x:(x%12 not in SCALE, abs(x-m)))
SN=[m for m in range(33,98) if m%12 in SCALE]
def step(a,b,k):
    ia=SN.index(min(SN,key=lambda x:abs(x-a))); ib=SN.index(min(SN,key=lambda x:abs(x-b)))
    return [SN[round(ia+(ib-ia)*s/(k+1))] for s in range(1,k+1)]
PROG=[("Amaj7",33,[45,52,57,61,64,68],76),("F#m7",30,[42,49,54,57,61,64],73),
 ("Bm7",35,[47,54,59,62,66,69],74),("E7",28,[40,47,52,56,59,62],71),
 ("Amaj7",33,[45,52,57,61,64,68],73),("Dmaj7",26,[38,45,50,54,57,61],78),
 ("E7sus",28,[40,47,52,57,59,64],71),("A6/9",33,[45,52,57,61,64,71],81)]
BARS,BEATS=16,4
def metric(b): return [0.10,-0.04,0.04,-0.06][int(b)%4]
pad_lo,pad_hi,organ,sub,bass,arp,lead=[],[],[],[],[],[],[]
OVR=4.7   # pad note length > 4 beats -> overlaps into next bar (no gaps)
for bar in range(BARS):
    _,root,V,mtgt=PROG[bar%8]; t0=bar*BEATS; seg=bar//8
    swell=0.5+0.45*math.sin(math.pi*((bar%4)/3.0)); base=(0.42 if seg==0 else 0.58)+0.12*swell
    for v in V[:3]: pad_lo.append((t0,OVR,v,round(base-0.06,2)))
    for v in V[3:]: pad_hi.append((t0,OVR,v,round(base-0.02,2)))
    organ+=[(t0,OVR,V[1],round(base-0.12,2)),(t0,OVR,V[3],round(base-0.12,2))]
    sub.append((t0,OVR,root,round(0.62+0.08*seg,2)))
    fifth=root+7
    bass+=[(t0,2.4,root+12,round(0.6+0.06*seg,2)),(t0+2,2.0,fifth+12,round(0.5+0.05*seg,2))]
    stack=V+[V[0]+12]; seq=stack+stack[::-1][1:]
    for i in range(16):
        p=seq[i%len(seq)]; b=i*0.25
        vel=max(0.26,min(0.82,base-0.08+metric(b)+0.03*((p-52)/12)+0.04*swell))
        arp.append((round(t0+b,3),0.5,p,round(vel,2)))   # 0.5b dur -> rings/overlaps
    tgt=snap(mtgt+(12 if seg==1 else 0)); lead.append((t0,1.4,tgt,round(min(0.92,base+0.12+0.1*swell),2)))
    nxt=snap(PROG[(bar+1)%8][3]+(12 if seg==1 else 0))
    for j,mm in enumerate(step(tgt,nxt,3)): lead.append((round(t0+1+j*0.5,3),0.75,mm,round(base,2)))
    lead.append((round(t0+2.5,3),(2.2 if bar%4==3 else 1.8),snap(tgt-2),round(base+0.08+0.12*swell,2)))
for v in [33,45,57,64,69,73,81]: (pad_lo if v<60 else pad_hi).append((BARS*BEATS,9,v,0.5))
sub.append((BARS*BEATS,9,33,0.6)); bass.append((BARS*BEATS,8,45,0.5))
def fmt(ns): return ",\n           ".join(f"{nm(m)} @ {round(s,3)}b for {round(d,3)}b vel {v}" for s,d,m,v in ns)
DUR=round((BARS*BEATS+12)*60/BPM); CL=44
AF=f"""# "Music of the gods" v3 — longer releases + overlapping tones + wetter tail.
asset apotheosis {{
  kind: signature
  duration: {DUR}s
  samplerate: 48000
  bitdepth: 24
  tempo: {BPM}bpm, {(BARS-2)*BEATS}b={BPM}bpm, {(BARS-1)*BEATS}b=48bpm, {BARS*BEATS}b=40bpm
  key: A major
  emotion: awe=0.9, wonder=0.78, calm=0.5, tension=0.32, cinematic_intensity=0.7
  intensity: 0s=0.35, 32s=0.55, 40s=0.72, {CL}s=1.0, 50s=0.82, {DUR}s=0.18
  marker statement @ 0s
  marker apotheosis @ 32s
  marker resolve @ 56s
  bus cathedral {{
    gain: -1db
    fx: convolve(file="stalbans_ortf_ir.wav", sha256="{IR_SHA}", mix=0.72),
        lowshelf(180hz, gain=-3.0)
  }}
  bus present {{
    gain: -1db
    fx: reverb(decay=3.4, mix=0.4), delay(time=0.5s, feedback=0.34, mix=0.24)
  }}
  bus low {{
    gain: 0db
    fx: reverb(decay=1.4, mix=0.12), lowpass(2600hz)
  }}
  layer pad_low : notes {{
    osc: pad
    bandwidth: 22c
    harmonics: 48
    gain: -10db
    pan: -0.28
    env: a=1.0s d=1.5s s=0.95 r=7s
    bus: cathedral
    humanize: time=0.02s vel=0.06
    notes: {fmt(pad_lo)}
    auto gain: 0s=-13db, {CL}s=-7db, {DUR}s=-22db
  }}
  layer pad_high : notes {{
    osc: pad
    bandwidth: 30c
    harmonics: 56
    gain: -15db
    pan: 0.28
    env: a=1.4s d=1.5s s=0.92 r=8s
    bus: cathedral
    humanize: time=0.022s vel=0.06
    fx: lowpass(4800hz)
    notes: {fmt(pad_hi)}
    auto gain: 0s=-18db, {CL}s=-11db, {DUR}s=-26db
  }}
  layer organ_bed : notes {{
    osc: organ
    gain: -16db
    pan: -0.08
    env: a=0.8s d=0.5s s=0.96 r=5s
    bus: cathedral
    notes: {fmt(organ)}
    fx: lowpass(2400hz)
    auto cutoff: 0s=900, {CL}s=3000, {DUR}s=800
  }}
  layer sub : notes {{
    osc: sine
    gain: -5db
    env: a=0.4s d=0.6s s=0.96 r=4s
    bus: low
    notes: {fmt(sub)}
    auto gain: 0s=-7db, {CL}s=-3db, {DUR}s=-20db
  }}
  layer bass : notes {{
    osc: triangle
    gain: -7db
    env: a=0.05s d=0.5s s=0.85 r=2.5s
    bus: low
    humanize: time=0.01s vel=0.06
    notes: {fmt(bass)}
    fx: lowpass(1500hz), saturate(amount=0.12, warmth=0.5)
    auto gain: 0s=-9db, {CL}s=-5db, {DUR}s=-22db
  }}
  layer arp : notes {{
    osc: pluck
    damping: 0.28
    brightness: 0.66
    pluckpos: 0.22
    gain: -16db
    pan: 0.12
    bus: present
    humanize: time=0.012s vel=0.08
    notes: {fmt(arp)}
    auto gain: 0s=-20db, {CL}s=-12db, {DUR}s=-30db
  }}
  layer lead : notes {{
    osc: pad
    bandwidth: 14c
    harmonics: 40
    detune: 5c
    gain: -8db
    pan: -0.04
    env: a=0.35s d=0.4s s=0.9 r=3.5s
    vibrato: rate=5.0 depth=13c delay=0.45s
    bus: present
    humanize: time=0.014s vel=0.05
    notes: {fmt(lead)}
    auto gain: 0s=-11db, {CL}s=-4db, {DUR}s=-24db
  }}
  layer air : grain {{
    source: pink
    srcdur: 3s
    grainsize: 0.18s
    density: 16
    pitchspread: 40c
    scatter: 0.5
    gain: -32db
    start: 0s
    env: a=4s d=0s s=1.0 r=6s
    bus: cathedral
    fx: bandpass(3200hz, q=0.7), highpass(900hz)
    auto gain: 0s=-40db, {CL}s=-27db, {DUR}s=-44db
  }}
  master {{
    width: 0.86
    lufs: -15
    peak: -1db
    fadein: 0.6s
    fadeout: 9s
    fx: fdn(rt60=7.0, rt60_high=2.2, crossover=2400, size=1.4, mix=0.3),
        comp(threshold=-16, ratio=1.8, attack=0.02, release=0.3, knee=10, makeup=1),
        highpass(22hz),
        lowshelf(100hz, gain=2.5),
        peak(300hz, gain=-1.6, q=1.2),
        highshelf(9500hz, gain=1.0),
        saturate(amount=0.1, warmth=0.5)
  }}
}}
"""
Path("/tmp/apotheosis.af").write_text(AF)
print(f"v3: dur {DUR}s, pad release 7-8s, arp damping 0.28, convolve mix 0.72, fdn rt60 7.0, fadeout 9s")
