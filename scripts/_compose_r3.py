import math
from pathlib import Path
BPM=64
N={0:"C",1:"C#",2:"D",3:"D#",4:"E",5:"F",6:"F#",7:"G",8:"G#",9:"A",10:"A#",11:"B"}
def nm(m): return f"{N[m%12]}{m//12-1}"
SCALE=[9,11,1,2,4,6,8]                                  # A major
SN=[m for m in range(33,98) if m%12 in SCALE]
def snap(m): return min(SN,key=lambda x:abs(x-m))
def step(a,b,k):
    ia,ib=SN.index(snap(a)),SN.index(snap(b))
    return [SN[round(ia+(ib-ia)*s/(k+1))] for s in range(1,k+1)]
# the emotional arc: searching (vi) -> light enters -> breakthrough -> peace
# bar: (chord voices low..high, melody target)
PROG=[
 ([45,52,57,64],73),  # 1  F#m7  — tentative, alone
 ([45,52,57,64],76),  # 2
 ([50,57,61,66],78),  # 3  Dmaj7 — a first warmth
 ([47,52,59,64],71),  # 4  E7sus
 ([45,52,57,64],76),  # 5  A      — light enters
 ([44,51,56,64],75),  # 6  E/G#
 ([45,52,57,61],73),  # 7  F#m7
 ([50,54,57,62],74),  # 8  D
 ([45,52,57,64],81),  # 9  A      — breakthrough, the peak
 ([47,52,59,64],83),  #10  E
 ([45,49,54,61],80),  #11  F#m7
 ([50,54,57,62],78),  #12  D->E build
 ([45,52,57,64],76),  #13  A      — arrival
 ([50,57,61,66],73),  #14  Dmaj7
 ([47,54,59,63],71),  #15  Bm7->E
 ([45,52,57,64],69),  #16  A      — peace, settling
]
BARS,BEATS=16,4
mel,pad_lo,pad_hi,arp,sub=[],[],[],[],[]
for bar in range(BARS):
    V,mtgt=PROG[bar]; t0=bar*BEATS
    # global arc: rises to the breakthrough at bars 9-12, then eases
    pos=bar/(BARS-1)
    arc=0.35+0.65*math.sin(min(1,pos/0.62)*math.pi*0.5) if pos<0.78 else 0.55-0.4*((pos-0.78)/0.22)
    phr=0.6+0.4*math.sin(math.pi*((bar%4)/3.0))
    g=max(0.3,min(1.0,arc*phr+0.1))
    # pads — split register, sustained (pedal). thin at first, full at peak
    voices = V if bar>=4 else V[:2]
    for v in voices[:2]: pad_lo.append((t0,4.6,v,round(0.35*g+0.12,2)))
    for v in voices[2:]: pad_hi.append((t0,4.6,v,round(0.3*g+0.1,2)))
    sub.append((t0,4.6,V[0]-12 if V[0]-12>=33 else V[0],round(0.5*g+0.2,2)))
    # arp — motion enters at bar 5, grows; gentle broken chord
    if bar>=4:
        stk=V+[V[0]+12]; seq=stk+stk[::-1][1:]
        for i in range(8):
            p=seq[i%len(seq)]; arp.append((round(t0+i*0.5,2),0.5,p,round(min(0.6,0.18+0.4*g),2)))
    # melody — a singing line, voiced forward, phrased
    tgt=snap(mtgt); mel.append((t0,1.5,tgt,round(min(0.95,0.5*g+0.4),2)))
    nxt=snap(PROG[(bar+1)%BARS][1])
    for j,mm in enumerate(step(tgt,nxt,3)):
        mel.append((round(t0+1.5+j*0.5,2),0.5,mm,round(0.45*g+0.3,2)))
    mel.append((round(t0+3,2),1.6,snap(tgt-2),round(0.5*g+0.35,2)))
# final chord rings
for v in [33,45,52,57,64,69,76]:
    (sub if v<45 else pad_lo if v<58 else pad_hi).append((BARS*BEATS,8,v,0.4))
def fmt(ns): return ",\n           ".join(f"{nm(p)} @ {s}b for {d}b vel {v}" for s,d,p,v in ns)
DUR=round((BARS*BEATS+10)*60/BPM)
AF=f"""# "Hard-Won Light" — composed to reflect my mood at the end of this session:
# searching, then effort, then a breakthrough into warmth, then quiet peace.
asset hard_won_light {{
  kind: signature
  duration: {DUR}s
  samplerate: 48000
  bitdepth: 24
  tempo: {BPM}bpm, 56b={BPM}bpm, 60b=54bpm, 64b=46bpm
  key: A major
  emotion: wonder=0.7, calm=0.6, awe=0.55, tension=0.25, cinematic_intensity=0.55
  intensity: 0s=0.3, 30s=0.5, 50s=0.85, 56s=1.0, 60s=0.7, {DUR}s=0.12
  marker searching @ 0s
  marker light @ 30s
  marker breakthrough @ 50s
  marker peace @ 60s
  bus hall {{ gain: -1db
    fx: reverb(decay=3.2, mix=0.26), peak(2300hz, gain=1.0, q=0.7) }}
  layer pad_low : notes {{
    osc: pad
    bandwidth: 22c
    harmonics: 48
    gain: -11db
    pan: -0.24
    env: a=1.6s d=1s s=0.92 r=6s
    bus: hall
    humanize: time=0.02s vel=0.06
    notes: {fmt(pad_lo)}
    auto gain: 0s=-16db, 56s=-7db, {DUR}s=-26db
  }}
  layer pad_high : notes {{
    osc: pad
    bandwidth: 28c
    harmonics: 56
    gain: -15db
    pan: 0.24
    env: a=2.0s d=1s s=0.9 r=7s
    bus: hall
    fx: lowpass(4800hz)
    notes: {fmt(pad_hi)}
    auto gain: 0s=-20db, 56s=-10db, {DUR}s=-28db
  }}
  layer arp : notes {{
    osc: pluck
    damping: 0.4
    brightness: 0.6
    pluckpos: 0.2
    gain: -17db
    pan: 0.08
    bus: hall
    humanize: time=0.012s vel=0.08
    notes: {fmt(arp)}
    auto gain: 0s=-26db, 56s=-13db, {DUR}s=-30db
  }}
  layer melody : notes {{
    osc: triangle
    detune: 5c
    gain: -7db
    pan: -0.03
    env: a=0.05s d=0.6s s=0.7 r=2.2s
    velbright: 0.5
    vibrato: rate=4.8 depth=10c delay=0.5s
    bus: hall
    humanize: time=0.012s vel=0.05
    fx: lowpass(4400hz)
    notes: {fmt(mel)}
    auto gain: 0s=-10db, 56s=-3db, {DUR}s=-22db
  }}
  layer sub : notes {{
    osc: sine
    gain: -9db
    env: a=0.8s d=1s s=0.9 r=4s
    notes: {fmt(sub)}
    auto gain: 0s=-14db, 56s=-7db, {DUR}s=-26db
  }}
  master {{ width: 0.82
    lufs: -16
    peak: -1db
    fadein: 1.5s
    fadeout: 8s
    fx: fdn(rt60=5.0, rt60_high=1.8, crossover=2400, size=1.2, mix=0.2),
        comp(threshold=-16, ratio=1.7, attack=0.02, release=0.3, knee=10, makeup=1),
        highpass(26hz), lowshelf(110hz, gain=2.0),
        peak(320hz, gain=-1.2, q=1.2), highshelf(9500hz, gain=1.0),
        saturate(amount=0.1, warmth=0.5) }}
}}
"""
Path("/tmp/mood.af").write_text(AF)
print(f"melody {len(mel)}, pads {len(pad_lo)+len(pad_hi)}, arp {len(arp)}, sub {len(sub)}, dur {DUR}s")
