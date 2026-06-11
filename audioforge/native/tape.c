/* AudioForge native kernel: analog tape — wow/flutter + saturation/hysteresis.
 *
 * Two effects that are each out of NumPy's reach, and together doubly so:
 *
 *   1. WOW & FLUTTER — a fractional delay line whose read position is swept by
 *      a composite of LFOs (slow "wow" + two faster "flutter" partials). The
 *      delay is *time-varying*, so the wet path is an LTV system: it cannot be
 *      one fixed convolution. The derivative of the sweep is the audible pitch
 *      warble.
 *   2. SATURATION with light MAGNETIC HYSTERESIS — a tanh soft-clip whose
 *      operating point is shifted by a smoothed image of the previous output,
 *      so the transfer curve has a small history-dependent loop (the tape's
 *      "memory"). A slight asymmetry adds the even-order warmth of a DC-biased
 *      head. Per-sample recursive + nonlinear -> native.
 *
 * Plus a one-pole HF loss (`tone`) for the characteristic tape dullness.
 * Pure IEEE-754 doubles, fixed constants, no randomness: deterministic per
 * environment. Returns the wet signal; the caller blends dry/wet.
 * Compile: cc -O2 -fPIC -shared tape.c -o tape.so -lm
 */
#include <math.h>
#include <stdlib.h>

int tape(const double *x, long n, int sr, double drive, double flutter,
         double tone, double *out) {
    if (!x || !out || n <= 0 || sr <= 0)
        return 1;
    if (drive < 0.0) drive = 0.0;
    if (drive > 1.0) drive = 1.0;
    if (flutter < 0.0) flutter = 0.0;
    if (flutter > 1.0) flutter = 1.0;
    if (tone < 0.0) tone = 0.0;
    if (tone > 1.0) tone = 1.0;

    /* delay line: 4 ms nominal, room for +/- a few ms of sweep */
    int maxd = (int)(0.02 * (double)sr) + 4;
    double *dl = calloc((size_t)maxd, sizeof(double));
    if (!dl)
        return 2;
    int widx = 0;
    double base_delay = 0.004 * (double)sr;          /* 4 ms */
    double depth = flutter * 0.0022 * (double)sr;    /* sweep depth (samples) */

    /* LFO increments: wow ~0.6 Hz, flutter ~6.3 and ~11 Hz (incommensurate) */
    double w_wow = 2.0 * M_PI * 0.6 / (double)sr;
    double w_f1  = 2.0 * M_PI * 6.3 / (double)sr;
    double w_f2  = 2.0 * M_PI * 11.0 / (double)sr;

    double g = 1.0 + 6.0 * drive;                    /* saturation drive */
    double gn = tanh(g);                             /* unity-ish normalize */
    double hyst = 0.0;                               /* hysteresis memory */

    /* HF loss: brighter (low tone) -> coeff near 1; dull -> heavier lowpass */
    double lp = 0.0;
    double lp_c = 0.15 + 0.80 * (1.0 - tone);        /* lowpass amount */

    for (long i = 0; i < n; i++) {
        dl[widx] = x[i];

        /* composite sweep, normalized so the partials sum to <= depth */
        double mod = depth * (0.6 * sin(w_wow * (double)i)
                            + 0.3 * sin(w_f1  * (double)i)
                            + 0.1 * sin(w_f2  * (double)i));
        double rpos = (double)widx - (base_delay + mod);
        while (rpos < 0.0) rpos += (double)maxd;
        int i0 = (int)rpos;
        double fr = rpos - (double)i0;
        int i1 = (i0 + 1) % maxd;
        double delayed = dl[i0] * (1.0 - fr) + dl[i1] * fr;

        /* saturation with history-shifted curve + slight asymmetry */
        double driven = g * delayed + 0.18 * hyst + 0.02 * drive;
        double sat = tanh(driven) / gn;
        hyst = 0.5 * hyst + 0.5 * sat;               /* smoothed memory */

        /* HF loss */
        lp = (1.0 - lp_c) * sat + lp_c * lp;
        out[i] = lp;

        widx = (widx + 1) % maxd;
    }
    free(dl);
    return 0;
}
