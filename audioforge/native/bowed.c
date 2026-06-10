/* AudioForge native kernel: bowed-string digital waveguide
 * (McIntyre-Woodhouse / STK-Bowed lineage).
 *
 * Two delay lines split at the bow point; the bow-string interaction is the
 * classic friction-curve nonlinearity rho = (|dv * slope| + 0.75)^-4 acting
 * on the velocity difference between bow and string; bridge reflection is
 * lowpass-damped, nut reflection inverts. Sequential by nature -> native.
 * Pure IEEE-754 doubles, no randomness: deterministic per environment.
 * Compile: cc -O2 -fPIC -shared bowed.c -o bowed.so -lm
 */
#include <math.h>
#include <stdlib.h>

int bowed_string(double freq, long n, int sr, double pressure,
                 double position, double brightness, double *out) {
    double L = (double)sr / freq - 4.0;
    if (L < 8.0) L = 8.0;
    int len_b = (int)(L * position);     /* bridge side */
    if (len_b < 2) len_b = 2;
    int len_n = (int)(L - len_b);        /* nut side */
    if (len_n < 2) len_n = 2;

    double *db = calloc((size_t)len_b, sizeof(double));
    double *dn = calloc((size_t)len_n, sizeof(double));
    int ib = 0, in_ = 0;

    double slope = 5.0 - 4.0 * pressure;          /* harder bow = wider grip */
    double lp = 0.0;                              /* bridge damping state    */
    double damp_c = 0.25 + 0.55 * (1.0 - brightness);
    double bow_target = 0.25 + 0.45 * pressure;
    long ramp = (long)(0.06 * sr);

    for (long i = 0; i < n; i++) {
        double bow_v = bow_target * (i < ramp ? (double)i / (double)ramp : 1.0);

        double sb = db[ib];                       /* arriving at bridge */
        double sn = dn[in_];                      /* arriving at nut    */

        lp = (1.0 - damp_c) * (-0.95 * sb) + damp_c * lp;   /* bridge refl */
        double rb = lp;
        double rn = -sn;                                     /* nut refl    */

        double v_string = rb + rn;
        double dv = bow_v - v_string;
        double rho = pow(fabs(dv * slope) + 0.75, -4.0);
        if (rho > 0.98) rho = 0.98;
        double f = dv * rho;

        db[ib] = rn + f;                          /* toward bridge */
        dn[in_] = rb + f;                         /* toward nut    */
        ib = (ib + 1) % len_b;
        in_ = (in_ + 1) % len_n;

        out[i] = sb;
    }
    free(db);
    free(dn);
    return 0;
}
