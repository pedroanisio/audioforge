/* AudioForge native kernel: streaming DSP loops.
 *
 * Single-pass C versions of recursions and tap loops that numpy can only
 * express as many full-buffer passes or as thousands of tiny lfilter calls:
 *   true_peak4    4x-oversampled stereo-linked |peak| per base sample, fused
 *                 (polyphase FIR + abs + max; no 4n intermediate buffers)
 *   freeverb      lowpass-feedback combs + series allpasses (fx.hall_fx)
 *   biquad_tv     time-varying biquad, coefficients per block (fx.filter_auto_fx)
 *   delay_taps    bounded feedback-echo tap sum (fx.delay_fx)
 * Plain IEEE-754 doubles, fixed evaluation order, no FMA contraction and no
 * fast-math, so a given build renders identically run to run.
 * Compile: cc -O3 -march=native -ffp-contract=off -fno-fast-math -fPIC -shared dsp.c -o dsp.so -lm
 */
#if defined(__clang__)
#pragma clang fp contract(off)
#endif

#include <stdlib.h>
#include <string.h>
#include <math.h>


#define BLK 64

/* ---- register-blocked FIR over pointer-per-tap sources ------------------
 * out[i] = sum_{j=0}^{ntap-1} src[j][i] * h[j]   for i in [0, n)
 * Each output accumulates from 0.0 with its taps in ascending j -- the order
 * scipy's upfirdn uses -- so results are identical to the scalar loop; the
 * speed comes from holding 4 vectors of outputs in registers across the tap
 * loop (compiler auto-vectorization kept falling back to a scalar path
 * behind runtime alias checks). GCC/Clang vector extensions: AVX-512, AVX
 * or SSE2 lanes as the build target allows; lanes never interact. */
#if defined(__AVX512F__)
#define AF_VW 8
#elif defined(__AVX__)
#define AF_VW 4
#else
#define AF_VW 2
#endif
typedef double af_vec __attribute__((vector_size(AF_VW * sizeof(double))));

static inline af_vec af_load(const double *p) {
    af_vec v;
    memcpy(&v, p, sizeof v);
    return v;
}

static inline void af_store(double *p, af_vec v) { memcpy(p, &v, sizeof v); }

static void fir_rows(const double *const *src, const double *h, long ntap,
                     long n, double *out) {
    const long W = 4 * AF_VW;
    long i = 0;
    for (; i + W <= n; i += W) {
        af_vec a0 = {0}, a1 = {0}, a2 = {0}, a3 = {0};
        for (long j = 0; j < ntap; j++) {
            const double *p = src[j] + i;
            af_vec c = {0};
            c += h[j];                                  /* broadcast       */
            a0 = a0 + af_load(p) * c;
            a1 = a1 + af_load(p + AF_VW) * c;
            a2 = a2 + af_load(p + 2 * AF_VW) * c;
            a3 = a3 + af_load(p + 3 * AF_VW) * c;
        }
        af_store(out + i, a0);
        af_store(out + i + AF_VW, a1);
        af_store(out + i + 2 * AF_VW, a2);
        af_store(out + i + 3 * AF_VW, a3);
    }
    for (; i < n; i++) {
        double a = 0.0;
        for (long j = 0; j < ntap; j++) a = a + src[j][i] * h[j];
        out[i] = a;
    }
}

/* Recursive states decaying through silence reach IEEE subnormals, where
 * every operation costs ~100x (measured: a 10-min hall with a silent tail ran
 * 15 s instead of 0.1 s). Values below 1e-290 (~ -5800 dBFS) are flushed to
 * exactly zero in software -- portable, so every CPU renders the same bits,
 * unlike FTZ/DAZ mode flags. Products of flushed-range values with the
 * coefficients used here stay normal, so no subnormal is ever formed. */
#define AF_TINY 1e-290
#define FLUSH(v) (fabs(v) < AF_TINY ? 0.0 : (v))

/* xl, xr: inputs zero-padded by hpp-1 on both sides (upfirdn layout, see
 * upfirdn.c); hf: resample_poly(4, 1) coefficient table, hpp taps/phase;
 * y0: first kept upfirdn output (n_pre_remove). out[b] = max over the four
 * oversampled outputs y0+4b..y0+4b+3 of max(|L|, |R|). Each FIR output uses
 * scipy's exact summation order, so the peaks equal the numpy path's. */
int true_peak4(const double *xl, const double *xr, long n, const double *hf,
               long hpp, long y0, double *out) {
    double al[BLK], ar[BLK];
    const double *sl[256], *sr[256];
    if (hpp > 256) return 1;
    for (long bb = 0; bb < n; bb += BLK) {
        long nb = n - bb < BLK ? n - bb : BLK;
        for (long i = 0; i < nb; i++) out[bb + i] = 0.0;
        for (long k = 0; k < 4; k++) {
            long y = y0 + 4 * bb + k;         /* y + 4i for lane i       */
            long t = y % 4;                   /* phase fixed per k       */
            for (long j = 0; j < hpp; j++) {
                sl[j] = xl + y / 4 + j;
                sr[j] = xr + y / 4 + j;
            }
            fir_rows(sl, hf + t * hpp, hpp, nb, al);
            fir_rows(sr, hf + t * hpp, hpp, nb, ar);
            for (long i = 0; i < nb; i++) {
                double a = fabs(al[i]), b = fabs(ar[i]);
                double m = a > b ? a : b;
                if (m > out[bb + i]) out[bb + i] = m;
            }
        }
    }
    return 0;
}

/* Freeverb hall on a mono signal: ncomb parallel lowpass-feedback combs
 *   y[n] = x[n] + g * f[n],  f[n] = (1-d) * y[n-L] + d * f[n-1]
 * averaged, then nap series Schroeder allpasses
 *   y[n] = -ga * x[n] + x[n-L] + ga * y[n-L].  wet receives the result. */
int freeverb(const double *x, long n, const long *cl, const double *cg,
             long ncomb, double damp, const long *al, long nap, double ga,
             double *wet) {
    enum { MAXC = 16 };
    if (ncomb < 1 || ncomb > MAXC || nap < 0) return 1;
    /* each comb keeps its own output history in a ring of length L */
    double *ring[MAXC] = {0};
    long pos[MAXC] = {0};
    double f[MAXC] = {0};
    int ok = 1;
    for (long c = 0; c < ncomb; c++) {
        ring[c] = calloc((size_t)cl[c], sizeof(double));
        if (!ring[c]) ok = 0;
    }
    double *tmp = malloc((size_t)(n > 0 ? n : 1) * sizeof(double));
    if (!tmp) ok = 0;
    if (!ok) {
        for (long c = 0; c < ncomb; c++) free(ring[c]);
        free(tmp);
        return 1;
    }
    const double b = 1.0 - damp;
    const double inv = 1.0 / (double)ncomb;
    /* all combs advance together: their feedback chains are independent, so
     * interleaving them overlaps the latencies instead of serializing them */
    for (long i = 0; i < n; i++) {
        double acc = 0.0;
        const double xi = x[i];
        for (long c = 0; c < ncomb; c++) {
            double yd = ring[c][pos[c]];              /* y[i - L], 0 early  */
            f[c] = b * yd + damp * f[c];
            double y = FLUSH(xi + cg[c] * f[c]);      /* ring stays normal */
            ring[c][pos[c]] = y;
            pos[c] = pos[c] + 1 == cl[c] ? 0 : pos[c] + 1;
            acc += y;
        }
        wet[i] = acc * inv;
        if ((i & 63) == 63)                           /* subnormal guard   */
            for (long c = 0; c < ncomb; c++) f[c] = FLUSH(f[c]);
    }
    for (long c = 0; c < ncomb; c++) free(ring[c]);
    for (long a = 0; a < nap; a++) {
        const long L = al[a];
        memcpy(tmp, wet, (size_t)n * sizeof(double));
        for (long i = 0; i < n; i++) {
            double xd = i >= L ? tmp[i - L] : 0.0;
            double yd = i >= L ? wet[i - L] : 0.0;
            wet[i] = FLUSH(-ga * tmp[i] + xd + ga * yd);
        }
    }
    free(tmp);
    return 0;
}

/* Transposed direct-form-II biquad whose coefficients change every `block`
 * samples (coef: nblocks x 5 = b0 b1 b2 a1 a2, a0 == 1). State carries
 * across blocks. Same per-sample update order as scipy.signal.lfilter. */
int biquad_tv(const double *x, long n, const double *coef, long block,
              double *out) {
    double z0 = 0.0, z1 = 0.0;
    for (long s = 0, k = 0; s < n; s += block, k++) {
        const double *c = coef + 5 * k;
        const double b0 = c[0], b1 = c[1], b2 = c[2], a1 = c[3], a2 = c[4];
        long e = s + block < n ? s + block : n;
        for (long i = s; i < e; i++) {
            double xi = x[i];
            double yi = z0 + b0 * xi;
            z0 = z1 + xi * b1 - yi * a1;
            z1 = xi * b2 - yi * a2;
            out[i] = yi;
        }
        z0 = FLUSH(z0);                  /* once per block: off the feedback */
        z1 = FLUSH(z1);                  /* path, still no subnormal runs    */
    }
    return 0;
}

/* wet[i] = sum over taps k=1..ntaps of gain_k * x[i - k*d] (x zero outside),
 * accumulated in tap order; gains precomputed by the caller. */
int delay_taps(const double *x, long n, long d, const double *gains,
               long ntaps, double *wet) {
    memset(wet, 0, (size_t)n * sizeof(double));
    for (long k = 1; k <= ntaps; k++) {
        long off = k * d;
        if (off >= n) break;
        const double gk = gains[k - 1];
        for (long i = off; i < n; i++) wet[i] += gk * x[i - off];
    }
    return 0;
}

/* Linear-interpolated single-cycle wavetable oscillator, accumulated:
 *   ph  = (2*pi*f) * (i / sr) + phase0
 *   pos = ph / (2*pi) * size;  i0 = floor(pos) mod size;  fr = pos - floor(pos)
 *   out[i] += amp * (table[i0] * (1 - fr) + table[(i0+1) mod size] * fr)
 * The same operations in the same order as synth.osc's numpy expression. */
int wavetable_acc(const double *table, long size, double w, double phase0,
                  double sr, long n, double amp, double *out) {
    const double two_pi = 6.283185307179586;
    const double dsize = (double)size;
    if (size > 0 && (size & (size - 1)) == 0) {
        /* power-of-two table (every classic table): the index wrap is a
         * mask, which equals Python's non-negative modulo, so the loop
         * vectorizes (gathers) with the identical arithmetic */
        const long mask = size - 1;
        for (long i = 0; i < n; i++) {
            double t = (double)i / sr;
            double ph = w * t + phase0;
            double pos = ph / two_pi * dsize;
            double fl = floor(pos);
            long i0 = (long)fl & mask;
            double fr = pos - fl;
            double v = table[i0] * (1.0 - fr) + table[(i0 + 1) & mask] * fr;
            out[i] = out[i] + amp * v;
        }
        return 0;
    }
    for (long i = 0; i < n; i++) {
        double t = (double)i / sr;
        double ph = w * t + phase0;
        double pos = ph / two_pi * dsize;
        double fl = floor(pos);
        long i0 = (long)fl % size;
        if (i0 < 0) i0 += size;
        double fr = pos - fl;
        long i1 = (i0 + 1) % size;
        double v = table[i0] * (1.0 - fr) + table[i1] * fr;
        out[i] = out[i] + amp * v;
    }
    return 0;
}

/* Impulse response of spaces._fdn_irs' 8-line Householder FDN (raw, before
 * energy normalization): the Python reference loop transcribed operation for
 * operation, so the IR is bit-identical. Ls: 8 line lengths; b0/b1: per-line
 * shelving loss coefficients; p: loss-filter pole; apl/apg: 2 input
 * allpasses. Returns 1 on allocation failure. */
int fdn_ir(long ir_len, const long *Ls, const double *b0, const double *b1,
           double p, const long *apl, const double *apg, double inj,
           double two_over_n, double *irL, double *irR) {
    enum { N = 8 };
    double *bufs[N], *ap[2];
    long idx[N] = {0}, api[2] = {0, 0};
    double x1[N] = {0}, y1[N] = {0}, outs[N], filt[N];
    int ok = 1;
    for (int i = 0; i < N; i++) {
        bufs[i] = calloc((size_t)Ls[i], sizeof(double));
        if (!bufs[i]) ok = 0;
    }
    for (int k = 0; k < 2; k++) {
        ap[k] = calloc((size_t)apl[k], sizeof(double));
        if (!ap[k]) ok = 0;
    }
    if (ok) {
        for (long n = 0; n < ir_len; n++) {
            double x = n == 0 ? 1.0 : 0.0;
            for (int k = 0; k < 2; k++) {
                double z = ap[k][api[k]];
                double v = x + apg[k] * z;
                ap[k][api[k]] = v;
                api[k] = (api[k] + 1) % apl[k];
                x = z - apg[k] * v;
            }
            for (int i = 0; i < N; i++) outs[i] = bufs[i][idx[i]];
            double s = 0.0;
            for (int i = 0; i < N; i++) {
                double yi = b0[i] * outs[i] + b1[i] * x1[i] + p * y1[i];
                x1[i] = outs[i];
                y1[i] = yi;
                filt[i] = yi;
                s = s + yi;
            }
            s = s * two_over_n;
            for (int i = 0; i < N; i++) {
                bufs[i][idx[i]] = inj * x + (filt[i] - s);
                idx[i] = (idx[i] + 1) % Ls[i];
            }
            irL[n] = 0.5 * (outs[0] - outs[2] + outs[4] - outs[6]);
            irR[n] = 0.5 * (outs[1] - outs[3] + outs[5] - outs[7]);
        }
    }
    for (int i = 0; i < N; i++) free(bufs[i]);
    for (int k = 0; k < 2; k++) free(ap[k]);
    return ok ? 0 : 1;
}

/* tanh without libm, written so loops over it vectorize (no integer bit
 * tricks, no branches, no fmin): E = e^{2|y|} = (e^{2|y|/64})^64 with e^r from
 * its degree-16 Taylor polynomial (truncation < 1e-18 for |y| <= 20) and six
 * squarings (relative error <= ~1e-15); tanh = sign(y) * (1 - 2 / (E + 1)).
 * For |y| > 20 the polynomial is monotone, so E >= e^40 > 2^54 (or inf) and
 * the result rounds to exactly +-1. Absolute error ~2e-16 (tested against
 * numpy over [-1000, 1000]); identical on every platform. */
static inline double af_tanh(double y) {
    double r = fabs(y) * (2.0 / 64.0);
    double e = 1.0 / 20922789888000.0;                 /* 1/16!            */
    e = e * r + 1.0 / 1307674368000.0;
    e = e * r + 1.0 / 87178291200.0;
    e = e * r + 1.0 / 6227020800.0;
    e = e * r + 1.0 / 479001600.0;
    e = e * r + 1.0 / 39916800.0;
    e = e * r + 1.0 / 3628800.0;
    e = e * r + 1.0 / 362880.0;
    e = e * r + 1.0 / 40320.0;
    e = e * r + 1.0 / 5040.0;
    e = e * r + 1.0 / 720.0;
    e = e * r + 1.0 / 120.0;
    e = e * r + 1.0 / 24.0;
    e = e * r + 1.0 / 6.0;
    e = e * r + 0.5;
    e = e * r + 1.0;
    e = e * r + 1.0;
    e = e * e; e = e * e; e = e * e; e = e * e; e = e * e; e = e * e;
    return copysign(1.0 - 2.0 / (e + 1.0), y);
}

#define SAT_B 256

static inline void sat_shape(double *restrict v, const double *restrict u,
                             long n, double bias, double d, double c0,
                             double inv) {
    for (long i = 0; i < n; i++)
        v[i] = (af_tanh((u[i] + bias) * d) - c0) * inv;
}

/* fx.saturate_fx's wet path fused: u = resample_poly(x, 4, 1);
 * v = (tanh((u + bias) * d) - c0) * inv;  out = resample_poly(v, 1, 4)[:n].
 * xp points at logical x[-(hpu-1)] of an input zero-padded far enough that
 * every read below stays in bounds (the caller adds a margin); hu/hpu/y0u:
 * 4x-up filter table (upfirdn layout) and first kept output; hd/hpd/y0d:
 * 4x-down filter. Blocks keep the oversampled signal in cache; the four
 * oversampled phases live in separate arrays so every loop is contiguous. */
int saturate4(const double *xp, long n, const double *hu, long hpu, long y0u,
              const double *hd, long hpd, long y0d, double bias, double d,
              double c0, double inv, double *out) {
    const long n4 = 4 * n;
    const long qmax = SAT_B + hpd / 4 + 2;
    double *V = malloc((size_t)(4 * qmax) * sizeof(double));
    if (!V) return 1;
    double acc[SAT_B + 64];
    if (qmax > SAT_B + 64) { free(V); return 1; }
    for (long m0 = 0; m0 < n; m0 += SAT_B) {
        long nb = n - m0 < SAT_B ? n - m0 : SAT_B;
        long len = (nb - 1) * 4 + hpd;                 /* v samples used   */
        long ys = (y0d + m0) * 4 - (hpd - 1);          /* v index of v[0]  */
        for (long r = 0; r < 4; r++) {                 /* V[r][q] = v[4q+r] */
            double *Vr = V + r * qmax;
            long y_first = ys + r;
            long qn = (len - r + 3) / 4;
            long p = y0u + y_first;                    /* up=4, down=1     */
            long t = ((p % 4) + 4) % 4;
            long xi = (p - t) / 4;                     /* floor(p / 4)     */
            const double *h = hu + t * hpu;
            const double *xs = xp + xi;
            const double *srcs[256];
            if (hpu > 256) { free(V); return 1; }
            for (long j = 0; j < hpu; j++) srcs[j] = xs + j;
            fir_rows(srcs, h, hpu, qn, acc);
            sat_shape(Vr, acc, qn, bias, d, c0, inv);
            /* v is zero outside [0, 4n) (resample_poly's zero padding) */
            for (long q = 0; q < qn && y_first + 4 * q < 0; q++) Vr[q] = 0.0;
            for (long q = qn - 1; q >= 0 && y_first + 4 * q >= n4; q--) Vr[q] = 0.0;
        }
        /* decimate: out[m0+i] = sum_j v[4i + j] * hd[j], j ascending */
        const double *dsrc[512];
        if (hpd > 512) { free(V); return 1; }
        for (long j = 0; j < hpd; j++) dsrc[j] = V + (j & 3) * qmax + (j >> 2);
        fir_rows(dsrc, hd, hpd, nb, out + m0);
    }
    free(V);
    return 0;
}

/* nch independent channels, each through the same cascade of nsec biquads
 * (coef: nsec x 5 = b0 b1 b2 a1 a2, a0 == 1), transposed direct form II with
 * scipy.signal.lfilter's per-sample update order. A single biquad chain is
 * latency-bound (~12 cycles/sample on its feedback path); advancing all
 * channel x section chains in one loop lets them overlap in the pipeline.
 * Subnormal flushing is applied to the states every 64 samples, off the
 * feedback path. x/out: nch pointers to contiguous rows of n samples. */
#define IIR_MAXCH 8
#define IIR_MAXSEC 8
int iir_multi(const double *const *x, long nch, long n, const double *coef,
              long nsec, double *const *out) {
    if (nch < 1 || nch > IIR_MAXCH || nsec < 1 || nsec > IIR_MAXSEC) return 1;
    double z0[IIR_MAXCH][IIR_MAXSEC] = {{0}}, z1[IIR_MAXCH][IIR_MAXSEC] = {{0}};
    for (long s0 = 0; s0 < n; s0 += 64) {
        long e = s0 + 64 < n ? s0 + 64 : n;
        for (long i = s0; i < e; i++) {
            for (long c = 0; c < nch; c++) {
                double v = x[c][i];
                for (long s = 0; s < nsec; s++) {
                    const double *k = coef + 5 * s;
                    double yi = z0[c][s] + k[0] * v;
                    z0[c][s] = z1[c][s] + v * k[1] - yi * k[3];
                    z1[c][s] = v * k[2] - yi * k[4];
                    v = yi;
                }
                out[c][i] = v;
            }
        }
        for (long c = 0; c < nch; c++)
            for (long s = 0; s < nsec; s++) {
                z0[c][s] = FLUSH(z0[c][s]);
                z1[c][s] = FLUSH(z1[c][s]);
            }
    }
    return 0;
}

/* Forward running minimum: out[i] = min(x[i .. min(i+L, n)-1]) -- what
 * scipy.ndimage.minimum_filter1d(x, L, mode="nearest", origin=-(L//2))
 * computes (the window looks ahead; "nearest" padding repeats x[n-1], which
 * is already inside every window). Monotonic deque: O(n), exact. */
int running_min_fwd(const double *x, long n, long L, double *out) {
    if (L < 1) return 1;
    long *dq = malloc((size_t)(n > 0 ? n : 1) * sizeof(long));
    if (!dq) return 1;
    long head = 0, tail = 0;                 /* dq[head..tail): indices    */
    /* sweep from the end so each window [i, i+L) is a suffix-anchored max */
    for (long i = n - 1; i >= 0; i--) {
        while (tail > head && x[dq[tail - 1]] >= x[i]) tail--;
        dq[tail++] = i;
        while (dq[head] >= i + L) head++;
        out[i] = x[dq[head]];
    }
    free(dq);
    return 0;
}

/* y[i] = x[i] + sum_k c[k] * y[i - lag[k]]  (y = 0 before the start), taps
 * accumulated in the given order -- synth._sparse_feedback's recurrence
 * (Karplus-Strong loop) without its Python block loop; same bits. */
int sparse_feedback(const double *x, long n, const long *lag,
                    const double *c, long ntaps, double *y) {
    for (long i = 0; i < n; i++) {
        double acc = x[i];
        for (long k = 0; k < ntaps; k++) {
            long j = i - lag[k];
            acc = acc + c[k] * (j >= 0 ? y[j] : 0.0);
        }
        y[i] = FLUSH(acc);               /* decaying string: no subnormals */
    }
    return 0;
}

/* Up to 8 independent single biquads, each with its own coefficients (coef:
 * nch x 5 = b0 b1 b2 a1 a2) and length, advanced together so their feedback
 * latencies overlap (per-note filters are short, many, and independent).
 * Per chain: exactly lfilter's DF2T update order -- same bits as one call
 * each. Subnormal guard every 64 samples, as in iir_multi. */
int iir_ragged(const double *const *x, const long *len, long nch,
               const double *coef, double *const *out) {
    if (nch < 1 || nch > IIR_MAXCH) return 1;
    double z0[IIR_MAXCH] = {0}, z1[IIR_MAXCH] = {0};
    long nmin = len[0], nmax = len[0];
    for (long c = 1; c < nch; c++) {
        if (len[c] < nmin) nmin = len[c];
        if (len[c] > nmax) nmax = len[c];
    }
    for (long i = 0; i < nmax; i++) {
        if (i < nmin) {                           /* all chains active     */
            for (long c = 0; c < nch; c++) {
                const double *k = coef + 5 * c;
                double v = x[c][i];
                double yi = z0[c] + k[0] * v;
                z0[c] = z1[c] + v * k[1] - yi * k[3];
                z1[c] = v * k[2] - yi * k[4];
                out[c][i] = yi;
            }
        } else {
            for (long c = 0; c < nch; c++) {
                if (i >= len[c]) continue;
                const double *k = coef + 5 * c;
                double v = x[c][i];
                double yi = z0[c] + k[0] * v;
                z0[c] = z1[c] + v * k[1] - yi * k[3];
                z1[c] = v * k[2] - yi * k[4];
                out[c][i] = yi;
            }
        }
        if ((i & 63) == 63)
            for (long c = 0; c < nch; c++) { z0[c] = FLUSH(z0[c]); z1[c] = FLUSH(z1[c]); }
    }
    return 0;
}

/* Automation curve over a seconds timeline, one pass (curves.evaluate_curve
 * with times = i / sr + offset, which are sorted): x <= t[0] -> v[0];
 * x >= t[np-1] -> v[np-1] (last wins); otherwise segment k with
 * t[k-1] <= x < t[k], u = (x - t0) / (t1 - t0), and by kind[k]
 * (0 linear, 1 hold, 2 pow with ex[k]): v0 + (v1 - v0) * shape(u), hold ->
 * (u < 1 ? v0 : v1). mode 0: value; 1: exp(value * scale) (dB -> gain with
 * scale = ln(10)/20); 2: value clipped to [0, 1]. */
int curve_seconds(long n, double sr, double offset, const double *t,
                  const double *v, const long *kind, const double *ex,
                  long np_, long mode, double scale, double *out) {
    if (np_ < 1) return 1;
    long k = 1;
    for (long i = 0; i < n; i++) {
        double x = (double)i / sr + offset;
        double val;
        if (np_ == 1) {
            val = v[0];
        } else if (x >= t[np_ - 1]) {
            val = v[np_ - 1];
        } else if (x <= t[0]) {
            val = v[0];
        } else {
            while (k < np_ - 1 && t[k] <= x) k++;       /* x sorted: advance */
            double t0 = t[k - 1], t1 = t[k], v0 = v[k - 1], v1 = v[k];
            double u = (x - t0) / (t1 - t0);
            if (kind[k] == 1) {
                val = u < 1.0 ? v0 : v1;
            } else {
                if (kind[k] == 2) u = pow(u, ex[k]);
                val = u * (v1 - v0) + v0;
            }
        }
        if (mode == 1) val = exp(val * scale);
        else if (mode == 2) val = val < 0.0 ? 0.0 : (val > 1.0 ? 1.0 : val);
        out[i] = val;
    }
    return 0;
}
