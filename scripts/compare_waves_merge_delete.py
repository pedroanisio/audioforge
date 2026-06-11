"""Compare two WAVs: a reference recording vs an AudioForge recreation.

Reports the comparisons that are actually meaningful between a real acoustic
recording and a synthesis (they will NOT match sample-for-sample):
  * CHROMA similarity      — did we play the right notes/harmony? (can be high)
  * spectral-envelope dist — how far is the TIMBRE? (the synthesis-realism gap)
  * RMS-envelope corr      — did we phrase the dynamics alike?
  * tempo/length           — structural alignment
Usage: python3 compare_waves.py reference.wav recreation.wav
"""
import sys, wave, numpy as np

def load(p, target_sr=22050):
    w = wave.open(p, "rb"); n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
    raw = w.readframes(n); w.close()
    if sw == 2:
        x = np.frombuffer(raw, "<i2").astype(np.float64) / 2**15
    elif sw == 3:
        a = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = (a[:,0] | a[:,1]<<8 | (a[:,2].astype(np.int8).astype(np.int32))<<16) / 2**23
    else:
        x = np.frombuffer(raw, "<i4").astype(np.float64) / 2**31
    x = x.reshape(-1, ch).mean(1)
    if sr != target_sr:                       # cheap linear resample
        t = np.linspace(0, len(x), int(len(x)*target_sr/sr), endpoint=False)
        x = np.interp(t, np.arange(len(x)), x)
    return x / (np.abs(x).max() + 1e-9), target_sr

def chroma(x, sr, hop=2048):
    pcs = np.zeros(12)
    for i in range(0, len(x)-hop, hop):
        X = np.abs(np.fft.rfft(x[i:i+hop]*np.hanning(hop)))
        f = np.fft.rfftfreq(hop, 1/sr)
        m = f > 50
        midi = 69 + 12*np.log2((f[m]+1e-9)/440)
        pc = np.round(midi).astype(int) % 12
        for k in range(12): pcs[k] += X[m][pc == k].sum()
    return pcs / (pcs.sum() + 1e-9)

def mel_env(x, sr, hop=2048, nb=24):
    X = np.abs(np.fft.rfft(x[:hop*((len(x))//hop)].reshape(-1, hop)*np.hanning(hop), axis=1)).mean(0)
    f = np.fft.rfftfreq(hop, 1/sr)
    edges = np.logspace(np.log10(60), np.log10(sr/2), nb+1)
    return np.array([X[(f>=edges[i])&(f<edges[i+1])].mean() for i in range(nb)])

def rms_env(x, sr, win=0.1):
    w = int(win*sr); return np.array([np.sqrt((x[i:i+w]**2).mean()) for i in range(0, len(x)-w, w)])

def cos(a, b): return float(a@b/((np.linalg.norm(a)*np.linalg.norm(b))+1e-9))

if __name__ == "__main__":
    ref, rec = load(sys.argv[1]), load(sys.argv[2])
    (xr, sr), (xc, _) = ref, rec
    cr, cc = chroma(xr, sr), chroma(xc, sr)
    mr, mc = np.log(mel_env(xr, sr)+1e-9), np.log(mel_env(xc, sr)+1e-9)
    er, ec = rms_env(xr, sr), rms_env(xc, sr)
    L = min(len(er), len(ec)); env_corr = np.corrcoef(er[:L], ec[:L])[0,1]
    print(f"length:    ref {len(xr)/sr:.1f}s   recreation {len(xc)/sr:.1f}s")
    print(f"CHROMA similarity (notes/harmony):  {cos(cr,cc):.3f}   (1.0 = same pitch content)")
    print(f"  ref top pitch-classes: {[ 'C C# D D# E F F# G G# A A# B'.split()[k] for k in cr.argsort()[::-1][:4] ]}")
    print(f"  rec top pitch-classes: {[ 'C C# D D# E F F# G G# A A# B'.split()[k] for k in cc.argsort()[::-1][:4] ]}")
    print(f"TIMBRE distance (mel-env, lower=closer): {np.linalg.norm(mr-mc)/len(mr):.3f}  cos {cos(np.exp(mr),np.exp(mc)):.3f}")
    print(f"DYNAMICS envelope correlation:           {env_corr:.3f}   (1.0 = same phrasing)")
