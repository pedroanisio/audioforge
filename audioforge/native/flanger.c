/* AudioForge native kernel: flanger — a short fractional delay line swept by an
 * LFO with feedback (the through-zero-free classic). The delay is time-varying
 * and the feedback makes it recursive, so it is an LTV recursion — native.
 *
 *   d(t)  = delay_ms + depth_ms · ½(1 + sin(2π rate t))       (samples after scaling)
 *   w[n]  = x[n] + feedback · r[n]
 *   r[n]  = w[n − d(n)]   (linear interpolation between the two neighbours)
 *   out   = r                                                 (wet; caller mixes)
 *
 * Pure IEEE-754 doubles, fixed constants, no randomness.
 * Compile: cc -O2 -fPIC -shared flanger.c -o flanger.so -lm
 */
#include <math.h>
#include <stdlib.h>

int flanger(const double *x, long n, int sr, double rate, double depth_ms,
            double delay_ms, double feedback, double *out) {
    if (!x || !out || n <= 0 || sr <= 0)
        return 1;
    if (rate < 0.0) rate = 0.0;
    if (rate > 20.0) rate = 20.0;
    if (depth_ms < 0.0) depth_ms = 0.0;
    if (depth_ms > 50.0) depth_ms = 50.0;
    if (delay_ms < 0.0) delay_ms = 0.0;
    if (delay_ms > 100.0) delay_ms = 100.0;
    if (feedback < -0.95) feedback = -0.95;
    if (feedback > 0.95) feedback = 0.95;

    long maxd = (long)((delay_ms + depth_ms) * 0.001 * (double)sr) + 4;
    double *dl = calloc((size_t)maxd, sizeof(double));
    if (!dl)
        return 2;
    long widx = 0;
    const double twopi = 6.283185307179586;
    for (long i = 0; i < n; i++) {
        double lfo = 0.5 * (1.0 + sin(twopi * rate * (double)i / (double)sr));
        double d = (delay_ms + depth_ms * lfo) * 0.001 * (double)sr;
        if (d < 1.0) d = 1.0;
        if (d > (double)(maxd - 2)) d = (double)(maxd - 2);
        double rp = (double)widx - d;
        while (rp < 0.0) rp += (double)maxd;
        long i0 = (long)rp;
        long i1 = (i0 + 1) % maxd;
        double fr = rp - (double)i0;
        double r = dl[i0] * (1.0 - fr) + dl[i1] * fr;
        double w = x[i] + feedback * r;
        dl[widx] = w;
        widx = (widx + 1) % maxd;
        out[i] = r;
    }
    free(dl);
    return 0;
}
