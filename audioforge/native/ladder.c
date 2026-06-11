/* AudioForge native kernel: nonlinear Moog-style transistor-ladder lowpass.
 *
 * Four cascaded one-pole stages with a tanh saturation inside every stage and
 * inside the resonance feedback path. That in-loop nonlinearity is the whole
 * reason this is native: an LTI biquad (fx.py filter) is linear by definition
 * and cannot produce a ladder's self-oscillating resonance peak or its
 * drive-dependent "squelch" — the resonance softening as the signal pushes the
 * transistors. Run at 2x oversampling so the tanh loop stays stable up to the
 * audio band. Pure IEEE-754 doubles, fixed constants, no fast-math: the same
 * spec renders identically across machines (the engine's determinism policy).
 *
 * Reference: Huovilainen, "Non-Linear Digital Implementation of the Moog
 * Ladder Filter" (DAFx-04), simplified to the explicit semi-implicit form.
 * Compile: cc -O2 -fPIC -shared ladder.c -o ladder.so -lm
 */
#include <math.h>

int ladder(const double *x, long n, int sr, double cutoff_hz,
           double resonance, double drive, double *out) {
    double sr_os = 2.0 * (double)sr;                  /* 2x oversampling   */
    double fc = cutoff_hz;
    if (fc < 20.0) fc = 20.0;
    double nyq = 0.49 * sr_os;
    if (fc > nyq) fc = nyq;

    /* one-pole stage coefficient in (0,1); exact pole mapping, no approx */
    double g = 1.0 - exp(-2.0 * M_PI * fc / sr_os);
    /* feedback depth: k~4 reaches self-oscillation, matching the 4-pole loop */
    double k = 4.0 * resonance;
    if (k > 4.4) k = 4.4;                              /* keep the loop bounded */
    double dr = 1.0 + 3.0 * drive;                    /* push into the tanh    */

    double s0 = 0.0, s1 = 0.0, s2 = 0.0, s3 = 0.0;    /* stage states          */

    for (long i = 0; i < n; i++) {
        double xi = dr * x[i];
        double y = 0.0;
        for (int os = 0; os < 2; os++) {              /* oversample, keep 2nd  */
            double u = tanh(xi - k * s3);             /* saturated feedback in */
            s0 += g * (u        - tanh(s0));
            s1 += g * (tanh(s0) - tanh(s1));
            s2 += g * (tanh(s1) - tanh(s2));
            s3 += g * (tanh(s2) - tanh(s3));
            y = s3;
        }
        out[i] = y;
    }
    return 0;
}
