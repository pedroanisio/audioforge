/* AudioForge native kernel: blown (reed) waveguide, STK-Clarinet lineage.
 * Cylindrical-bore delay line with a reed-table nonlinearity at the mouth:
 * refl = 0.7 + slope*(pd), clipped; breath carries seeded turbulence noise
 * supplied by the caller so determinism stays in Python's hands.
 * Compile: cc -O2 -fPIC -shared blown.c -o blown.so -lm
 */
#include <math.h>
#include <stdlib.h>

int blown_pipe(double freq, long n, int sr, double pressure,
               double brightness, const double *noise, double *out) {
    /* cylindrical bore sounds an octave below its length -> half period */
    double L = (double)sr / freq / 2.0 - 2.0;
    if (L < 4.0) L = 4.0;
    int len = (int)L;
    double frac = L - len;

    double *dl = calloc((size_t)(len + 2), sizeof(double));
    int idx = 0;

    /* bore losses: gentle two-tap average (unity at DC so the loop can
     * self-oscillate), blended toward unfiltered by brightness */
    double prev = 0.0;
    double a = 0.5 + 0.5 * brightness;
    /* constants solved from the reed fixed-point equation so the
     * small-signal loop gain stays in 1.02..1.22 across pressure 0.2..1
     * without driving the table into its clip region */
    double breath_target = 0.5 + 0.22 * pressure;
    double reed_slope = -(0.26 + 0.10 * pressure);
    long ramp = (long)(0.04 * sr);

    for (long i = 0; i < n; i++) {
        double breath = breath_target
            * (i < ramp ? (double)i / (double)ramp : 1.0);
        breath *= 1.0 + 0.06 * noise[i];          /* seeded turbulence */

        int j0 = idx, j1 = (idx + 1) % (len + 2);
        double dout = dl[j0] * (1.0 - frac) + dl[j1] * frac;

        double filt = a * dout + (1.0 - a) * prev;
        prev = dout;
        double bore = -0.98 * filt;

        double pd = bore - breath;                 /* pressure difference */
        double refl = 0.72 + reed_slope * pd;
        if (refl > 1.0) refl = 1.0;
        if (refl < -1.0) refl = -1.0;

        double in = breath + pd * refl;
        dl[(idx + len) % (len + 2)] = in;
        idx = (idx + 1) % (len + 2);

        out[i] = bore;
    }
    free(dl);
    return 0;
}
