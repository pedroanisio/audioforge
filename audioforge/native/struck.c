/* AudioForge native kernel: tension-modulated struck string.
 *
 * A Karplus-Strong recirculating delay (the linear case is osc: pluck, which
 * the engine vectorizes in NumPy) made NONLINEAR by tension modulation: the
 * effective loop length is shortened in proportion to the instantaneous string
 * energy. A hard strike raises the tension, so the pitch starts sharp and
 * glides back down as the note decays toward the nominal length — the audible
 * "boing"/pitch-droop of a hard-struck or detuned string. Because the delay
 * length is driven by the signal's own amplitude, the loop is both time-varying
 * and nonlinear: it cannot be the LTI recurrence the vectorized pluck uses.
 * (Tolonen/Valimaki/Karjalainen lineage.)
 *
 * The seeded strike excitation is built BY THE CALLER (as blown/brass) so
 * determinism stays in Python's hands; the kernel just recirculates it.
 * Pure IEEE-754 doubles, fixed constants. Completes the string family
 * pluck (linear) / struck (tension-modulated).
 * Compile: cc -O2 -fPIC -shared struck.c -o struck.so -lm
 */
#include <math.h>
#include <stdlib.h>

int struck(const double *exc, long n, int sr, double freq, double damping,
           double brightness, double tension, double *out) {
    if (!exc || !out || n <= 0 || sr <= 0 || freq <= 0.0)
        return 1;
    if (damping < 0.0) damping = 0.0;
    if (damping > 1.0) damping = 1.0;
    if (brightness < 0.0) brightness = 0.0;
    if (brightness > 1.0) brightness = 1.0;
    if (tension < 0.0) tension = 0.0;
    if (tension > 1.0) tension = 1.0;

    double L0 = (double)sr / freq;            /* nominal loop length */
    if (L0 < 4.0) L0 = 4.0;
    int N = (int)ceil(L0) + 4;                /* buffer (read never exceeds L0) */
    double *buf = calloc((size_t)N, sizeof(double));
    if (!buf)
        return 2;
    /* prime the loop with the strike (KS initial burst) */
    for (int k = 0; k < N; k++)
        buf[k] = (k < n) ? exc[k] : 0.0;

    int w = 0;
    /* longer sustain with lower damping; stays < 1 so the note decays */
    double rho = 0.990 + 0.0094 * (1.0 - damping);
    /* loss filter: one-pole lowpass, brighter = less damping of highs */
    double lp = 0.5 + 0.48 * brightness;
    double lp_state = 0.0;
    /* energy follower (~10 ms) drives the tension/length modulation */
    double e = 0.0;
    double e_coef = exp(-1.0 / (0.010 * (double)sr));
    /* max fractional shortening of the loop at full tension & energy
     * (tuned so full tension gives a clearly audible downward glide while the
     * shortened loop stays well inside its stable range) */
    double mod_depth = tension * 0.80 * L0;

    for (long i = 0; i < n; i++) {
        double delay = L0 - mod_depth * e;    /* sharpen with energy */
        if (delay < 4.0) delay = 4.0;
        if (delay > (double)(N - 2)) delay = (double)(N - 2);

        double rpos = (double)w - delay;
        while (rpos < 0.0) rpos += (double)N;
        int i0 = (int)rpos;
        double fr = rpos - (double)i0;
        int i1 = (i0 + 1) % N;
        double s = buf[i0] * (1.0 - fr) + buf[i1] * fr;

        lp_state = lp * s + (1.0 - lp) * lp_state;   /* brightness loss */
        buf[w] = rho * lp_state;                     /* recirculate, decay */
        out[i] = s;

        e = e_coef * e + (1.0 - e_coef) * (s * s);   /* track energy */
        w = (w + 1) % N;
    }
    free(buf);
    return 0;
}
