/* AudioForge native kernel: sympathetic / coupled-string resonator.
 *
 * One struck "played" string plus a bank of un-struck strings tuned to its
 * near-harmonics, all sharing a single bridge. The played string's energy
 * radiates through the bridge into the others, which ring at their own pitches
 * and feed back — the emergent, input-coupled "halo" of a sitar's tarab
 * strings or a piano soundboard. The bridge is NONLINEAR (the sitar's jawari
 * buzz), which both colours the tone and, being a limiter, keeps the coupled
 * feedback bounded. Several recursive delay loops joined at a shared nonlinear
 * junction, evolving per sample: this is the case NumPy most plainly cannot
 * vectorize — coupled feedback is not an LTI convolution, and the coupling is
 * input-dependent, so no fixed IR exists.
 *
 * coupling=0 reduces to a single Karplus-Strong string (osc: pluck/struck).
 * Seeded strike excitation supplied by the caller (determinism in Python's
 * hands). Pure IEEE-754 doubles, fixed constants. Closes the string family
 * pluck / struck / sympathetic.
 * Compile: cc -O2 -fPIC -shared sympathetic.c -o sympathetic.so -lm
 */
#include <math.h>
#include <stdlib.h>

#define NS 6

int sympathetic(const double *exc, long n, int sr, double freq,
                double coupling, double buzz, double damping,
                double brightness, double *out) {
    if (!exc || !out || n <= 0 || sr <= 0 || freq <= 0.0)
        return 1;
    if (coupling < 0.0) coupling = 0.0;
    if (coupling > 1.0) coupling = 1.0;
    if (buzz < 0.0) buzz = 0.0;
    if (buzz > 1.0) buzz = 1.0;
    if (damping < 0.0) damping = 0.0;
    if (damping > 1.0) damping = 1.0;
    if (brightness < 0.0) brightness = 0.0;
    if (brightness > 1.0) brightness = 1.0;

    /* string 0 is played; 1..5 are sympathetic, near-harmonics lightly
     * detuned (cents) so the halo shimmers (beating) rather than reinforces */
    static const double ratio[NS]  = {1.0, 2.0, 3.0, 4.0, 5.0, 6.0};
    static const double det_c[NS]  = {0.0, 4.0, -5.0, 7.0, -6.0, 9.0};
    /* bridge mix: the played string radiates most, partials less */
    static const double mix[NS]    = {0.9, 0.55, 0.45, 0.4, 0.32, 0.26};

    double *buf[NS];
    int len[NS], w[NS];
    double frac[NS], lpst[NS];
    double L0 = (double)sr / freq;
    for (int k = 0; k < NS; k++) {
        double r = ratio[k] * pow(2.0, det_c[k] / 1200.0);
        double L = L0 / r;
        if (L < 4.0) L = 4.0;
        len[k] = (int)L;
        frac[k] = L - (double)len[k];
        buf[k] = calloc((size_t)(len[k] + 2), sizeof(double));
        if (!buf[k]) {
            for (int j = 0; j < k; j++) free(buf[j]);
            return 2;
        }
        w[k] = 0;
        lpst[k] = 0.0;
    }
    /* prime the played string with the strike burst (KS) */
    for (int j = 0; j < len[0] + 2; j++)
        buf[0][j] = (j < n) ? exc[j] : 0.0;

    double rho = 0.992 + 0.0078 * (1.0 - damping);   /* long sustain */
    double lp = 0.5 + 0.48 * brightness;             /* loss-filter brightness */
    double bdrive = 2.0 + 7.0 * buzz;                /* bridge buzz hardness */
    double coup = coupling * 0.5;                    /* drive into the tarab bank */
    double wsum = 0.0;
    for (int k = 0; k < NS; k++) wsum += mix[k];

    for (long i = 0; i < n; i++) {
        double s[NS], bsum = 0.0;
        double filt0 = 0.0;
        for (int k = 0; k < NS; k++) {
            double delay = (double)len[k] + frac[k];
            double rpos = (double)w[k] - delay;
            int N = len[k] + 2;
            while (rpos < 0.0) rpos += (double)N;
            int i0 = (int)rpos;
            double fr = rpos - (double)i0;
            int i1 = (i0 + 1) % N;
            s[k] = buf[k][i0] * (1.0 - fr) + buf[k][i1] * fr;
            bsum += mix[k] * s[k];
        }
        double bavg = bsum / wsum;                   /* radiated bridge motion */
        /* nonlinear bridge: the sitar's jawari buzz. tanh(bdrive*x)/bdrive has
         * UNITY small-signal slope (never amplifies — only compresses the peaks,
         * adding harmonics) so it colours without destabilising. */
        double shaped = tanh(bdrive * bavg) / bdrive;
        double bz = (1.0 - buzz) * bavg + buzz * shaped;

        for (int k = 0; k < NS; k++) {
            double filt = lp * s[k] + (1.0 - lp) * lpst[k];
            lpst[k] = filt;
            int N = len[k] + 2;
            if (k == 0) {
                buf[0][w[0]] = rho * filt;           /* played string: pure KS */
                filt0 = filt;
            } else {
                /* tarab strings: each an independently-stable resonator driven
                 * one-way by the played string (its own rho gives the long ring
                 * that outlasts the strike — the halo). No inter-string feedback,
                 * so the coupled bank cannot run away. */
                buf[k][w[k]] = rho * filt + coup * filt0;
            }
            w[k] = (w[k] + 1) % N;
        }
        out[i] = bz;                                 /* radiated bridge */
    }
    for (int k = 0; k < NS; k++)
        free(buf[k]);
    return 0;
}
