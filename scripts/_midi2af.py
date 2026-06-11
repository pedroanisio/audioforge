import struct, sys
def vlq(b,i):
    v=0
    while True:
        c=b[i]; i+=1; v=(v<<7)|(c&0x7f)
        if not c&0x80: break
    return v,i
def parse(path):
    b=open(path,'rb').read()
    assert b[:4]==b'MThd'; fmt,ntrk,div=struct.unpack('>HHH',b[8:14]); i=14
    tempo=500000; notes=[]
    for _ in range(ntrk):
        assert b[i:i+4]==b'MTrk'; ln=struct.unpack('>I',b[i+4:i+8])[0]; i+=8; end=i+ln
        t=0; status=0; on={}
        while i<end:
            d,i=vlq(b,i); t+=d
            ev=b[i]
            if ev&0x80: status=ev; i+=1
            else: ev=status
            if ev==0xFF:
                mt=b[i]; i+=1; l,i=vlq(b,i)
                if mt==0x51: tempo=int.from_bytes(b[i:i+3],'big')
                i+=l
            elif ev in (0xF0,0xF7):
                l,i=vlq(b,i); i+=l
            else:
                typ=ev&0xF0; ch=ev&0x0F
                if typ in (0x80,0x90,0xA0,0xB0,0xE0):
                    d1=b[i]; d2=b[i+1]; i+=2
                    if typ==0x90 and d2>0: on.setdefault((ch,d1),[]).append((t,d2))
                    elif typ==0x80 or (typ==0x90 and d2==0):
                        k=(ch,d1)
                        if on.get(k): t0,v=on[k].pop(0); notes.append((t0,t,d1,v))
                else:
                    i+=1
    return fmt,div,tempo,sorted(notes)
fmt,div,tempo,notes=parse(sys.argv[1])
bpm=round(60_000_000/tempo,2)
NAMES={0:"C",1:"C#",2:"D",3:"D#",4:"E",5:"F",6:"F#",7:"G",8:"G#",9:"A",10:"A#",11:"B"}
def nm(m): return f"{NAMES[m%12]}{m//12-1}"
print(f"format {fmt}, division {div} ticks/quarter, tempo {bpm} bpm, {len(notes)} notes")
print("span beats:", round(notes[-1][1]/div,2), " pitch range:", nm(min(n[2] for n in notes)),"-",nm(max(n[2] for n in notes)))
print("first 16 notes:", [nm(n[2]) for n in notes[:16]])
# emit AF note events
evs=[(round(t0/div,4), round((t1-t0)/div,4), p, round(v/127,2)) for t0,t1,p,v in notes]
import json; json.dump({"bpm":bpm,"events":evs}, open("/tmp/bwv846_notes.json","w"))
print("wrote /tmp/bwv846_notes.json")
