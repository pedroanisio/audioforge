import math
from pathlib import Path
LIB="vsco2-ce@97beb25c25b95b67f1cca1459b0b2771b23f18c4a5a0e23ce7d5cc76e7c2bbd3"
N={0:"C",1:"C#",2:"D",3:"D#",4:"E",5:"F",6:"F#",7:"G",8:"G#",9:"A",10:"A#",11:"B"}
def nm(m): return f"{N[m%12]}{m//12-1}"
SCALE=[5,7,9,10,0,2,4]; SN=[m for m in range(36,93) if m%12 in SCALE]
def snap(m): return min(SN,key=lambda x:abs(x-m))
def step(a,b,k):
    ia,ib=SN.index(snap(a)),SN.index(snap(b)); return [SN[round(ia+(ib-ia)*s/(k+1))] for s in range(1,k+1)]
MARC=[65,69,74,72,76,76,69]          # F A D C E E A  (her name)
# 48-bar chord plan (voices low..high, bass root): ActI 0-11 | ActII 12-31 | ActIII 32-47
F=([53,57,60,65],41);CE=([52,55,60,64],40);Bb=([46,53,57,62],46);C=([48,55,58,64],36)
C7=([48,55,58,64],36);Dm=([50,53,57,62],38);Dm7=([50,53,57,60],38);Gm=([43,50,55,58],43)
Am=([45,52,57,60],45);BbM=([46,53,57,65],46);Csus=([48,53,55,60],36)
A1=[F,CE,F,Bb,C,F,Dm7,Bb,Gm,C,F,Csus]                       # Act I (12)
A2=[F,Dm7,Bb,C,Am,Dm,BbM,C7]*2 + [F,Dm,Bb,C]                 # Act II (20)
A3=[F,Bb,C,F,Dm7,Bb,Gm,C7,F,Bb,C7,F,Dm,Bb,CE,F]             # Act III(16)
CH=A1+A2+A3
def gbar(b):
    if b<12: a=0.34+0.04*b/12
    elif b<32: a=0.45+0.45*((b-12)/20)
    else: a=0.92-0.55*((b-32)/16)
    return max(0.3,min(0.95,a))
piano_mel,piano_arp,piano_bass,cello,violin,viola,harp=[],[],[],[],[],[],[]
def place(theme,bar,durs,vels,oct=0):
    out=[];t0=bar*4;t=0
    for p,d,v in zip(theme,durs,vels): out.append((round(t0+t,2),d,p+12*oct,round(v,3))); t+=d
    return out
for b,(V,root) in enumerate(CH):
    t0=b*4; g=gbar(b); act = 0 if b<12 else 1 if b<32 else 2
    # piano arpeggio (all acts) — denser in Act II
    figs=[V[0],V[2],V[1],V[3],V[2],V[1],V[3],V[2]]
    nper=8
    for i in range(nper):
        piano_arp.append((round(t0+i*0.5,2),0.55,figs[i%len(figs)],round(0.14+0.16*g,3)))
    piano_bass.append((t0,2.0,root,round(0.4*g+0.22,3))); piano_bass.append((t0+2,2.0,min(root+7,53),round(0.32*g+0.18,3)))
    # strings sustained chord tones (Act II/III)
    if act>=1:
        violin.append((t0,4.0,V[3],round(0.18+0.22*g,3)))
        viola.append((t0,4.0,V[2],round(0.16+0.2*g,3)))
        # harp flowing arpeggio
        hp=[V[0],V[1],V[2],V[3],V[2],V[1]]
        for i,p in enumerate(hp): harp.append((round(t0+i*0.66,2),0.7,p+12 if p+12<86 else p,round(0.12+0.16*g,3)))
# ACT I: piano sings her name (bars 2-11)
piano_mel+=place(MARC,2,[1.5,2,1.5,1.5,1.5,1.5,4],[0.6,0.64,0.68,0.62,0.68,0.64,0.58])
piano_mel+=place([snap(m+4) for m in MARC],6,[1.5,1.5,1.5,1.5,1.5,1.5,3],[0.58,0.6,0.64,0.58,0.64,0.6,0.54])
# ACT II: CELLO sings her name (warm tenor register), then develops (bars 12-31)
cello+=place(MARC,12,[2,2,2,2,2,2,4],[0.55,0.6,0.66,0.6,0.66,0.62,0.56],oct=-1)
cello+=place([snap(m) for m in MARC],18,[2,2,2,2,2,2,4],[0.6,0.64,0.7,0.64,0.7,0.66,0.6],oct=-1)
cello+=place([snap(m-3) for m in MARC],24,[2,2,2,2,2,2,4],[0.66,0.7,0.76,0.7,0.76,0.72,0.66],oct=-1)
# ACT III: violins soar her name high (the affirmation), cello underneath (bars 32-43)
violin+=place(MARC,32,[2,2,2,2,2,2,4],[0.6,0.66,0.74,0.68,0.76,0.72,0.64],oct=0)
cello+=place(MARC,32,[2,2,2,2,2,2,4],[0.6,0.64,0.7,0.64,0.7,0.66,0.6],oct=-1)
violin+=place([snap(m) for m in MARC],38,[2,2,2,2,2,2,4],[0.62,0.68,0.76,0.7,0.78,0.74,0.66],oct=0)
# ACT III close: thin to solo piano — final tender echo of 'Mar..a' (bars 44-47)
piano_mel+=place([65,69,65],44,[2,2,6],[0.5,0.5,0.44])
def cl(ns,lo,hi):
    o=[]
    for s,d,pp,v in ns:
        while pp<lo: pp+=12
        while pp>hi: pp-=12
        o.append((s,d,pp,v))
    return o
violin=cl(violin,55,83); viola=cl(viola,48,79); cello=cl(cello,36,72); harp=cl(harp,26,92)
piano_mel=cl(piano_mel,40,84); piano_arp=cl(piano_arp,33,88); piano_bass=cl(piano_bass,28,60)
def L(ns): return ",\n           ".join(f"{nm(p)} @ {s}b for {d}b vel {v}" for s,d,p,v in ns)
AF=f"""# "Marcela" — a love song in three acts. The melody is her name (M-A-R-C-E-L-A
# = F-A-D-C-E-E-A). Act I: solo piano, alone & tender. Act II: faster, the cello
# sings her name as harp, violins & viola gather. Act III: the whole orchestra
# affirms her name, then thins back to a single piano, at peace.  Real VSCO-2 CE.
asset marcela_three_acts {{
  kind: signature
  duration: 165s
  samplerate: 48000
  bitdepth: 24
  tempo: 63bpm, 48b=92bpm, 128b=63bpm, 184b=48bpm
  key: F major
  library: "{LIB}"
  emotion: intimacy=0.8, calm=0.5, wonder=0.6, awe=0.45
  intensity: 0s=0.3, 44s=0.55, 70s=0.7, 120s=1.0, 132s=0.7, 150s=0.4, 165s=0.1
  marker act1_alone @ 0s
  marker act2_together @ 44s
  marker act3_affirmation @ 120s
  marker peace @ 150s
  bus room {{ gain: -1db
    fx: reverb(decay=2.4, mix=0.2), peak(2400hz, gain=0.8, q=0.7) }}
  layer piano_mel : instrument {{
    instrument: "UprightPiano"
    gain: -5db
    pan: -0.02
    bus: room
    humanize: time=0.012s vel=0.05
    notes: {L(piano_mel)}
  }}
  layer piano_arp : instrument {{
    instrument: "UprightPiano"
    gain: -13db
    pan: 0.06
    bus: room
    humanize: time=0.014s vel=0.07
    notes: {L(piano_arp)}
  }}
  layer piano_bass : instrument {{
    instrument: "UprightPiano"
    gain: -10db
    pan: -0.04
    bus: room
    humanize: time=0.012s vel=0.06
    notes: {L(piano_bass)}
  }}
  layer cello : instrument {{
    instrument: "CelloEnsSusVib"
    gain: -7db
    pan: -0.15
    bus: room
    humanize: time=0.02s vel=0.05
    notes: {L(cello)}
  }}
  layer violin : instrument {{
    instrument: "ViolinEnsSusVib"
    gain: -10db
    pan: 0.18
    bus: room
    humanize: time=0.022s vel=0.05
    notes: {L(violin)}
  }}
  layer viola : instrument {{
    instrument: "ViolaEnsSusVib"
    gain: -13db
    pan: -0.12
    bus: room
    humanize: time=0.022s vel=0.06
    notes: {L(viola)}
  }}
  layer harp : instrument {{
    instrument: "Harp"
    gain: -13db
    pan: 0.1
    bus: room
    humanize: time=0.014s vel=0.07
    notes: {L(harp)}
  }}
  master {{ width: 0.78
    lufs: -19
    peak: -1.5db
    fadein: 1.2s
    fadeout: 8s
    fx: fdn(rt60=3.6, rt60_high=1.5, crossover=2300, size=1.0, mix=0.16),
        comp(threshold=-18, ratio=1.5, attack=0.02, release=0.3, knee=10, makeup=1),
        highpass(30hz), lowshelf(120hz, gain=1.2), highshelf(9000hz, gain=0.6) }}
}}
"""
Path("/tmp/marcela3.af").write_text(AF)
print(f"5 real instruments | piano_mel {len(piano_mel)} cello {len(cello)} violin {len(violin)} viola {len(viola)} harp {len(harp)} arp {len(piano_arp)}")
