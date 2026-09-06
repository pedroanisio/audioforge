/* AudioForge native kernel: phaser — a cascade of first-order allpass stages
 * whose corner frequency is swept by an LFO, with feedback from the cascade
 * output into its input.
 *
 * Each stage is the DAFX first-order allpass  y[n] = a·x[n] + x[n-1] − a·y[n-1]
 * with a = (tan(π fc/fs) − 1) / (tan(π fc/fs) + 1)  (Zölzer, DAFX 2nd ed., §2.3),
 * |a| < 1 for every fc below Nyquist. The coefficient changes every sample
 * (fc = center · 2^(spread · depth · sin(2π rate t))), so the chain is an LTV
 * recursion — per-sample + recursive -> native. Mixed with the dry signal by the
 * caller, the chain's phase turns produce `stages/2` moving notches.
 * `phase` offsets the LFO (radians): the right channel of a stereo chain runs at
 * `stereo · π` for the classic wide phaser. Pure IEEE-754 doubles, fixed constants,
 * no randomness. Returns the wet path.
 * Compile: cc -O2 -fPIC -shared phaser.c -o phaser.so -lm
 */
#include <math.h>

int phaser(const double *x, long n, int sr, double rate, double depth,
           int stages, double feedback, double center, double spread,
           double phase, double *out) {
    if (!x || !out || n <= 0 || sr <= 0)
        return 1;
    if (stages < 1) stages = 1;
    if (stages > 12) stages = 12;
    if (feedback < 0.0) feedback = 0.0;
    if (feedback > 0.95) feedback = 0.95;
    if (depth < 0.0) depth = 0.0;
    if (depth > 1.0) depth = 1.0;
    if (spread < 0.0) spread = 0.0;
    double nyq = 0.45 * (double)sr;
    if (center < 20.0) center = 20.0;
    if (center > nyq) center = nyq;
    if (rate < 0.0) rate = 0.0;

    double xs[12] = {0.0}, ys[12] = {0.0};
    double fb = 0.0;
    const double twopi = 6.283185307179586;
    const double pi = 3.141592653589793;
    for (long i = 0; i < n; i++) {
        double lfo = sin(twopi * rate * (double)i / (double)sr + phase);
        double fc = center * pow(2.0, spread * depth * lfo);
        if (fc > nyq) fc = nyq;
        if (fc < 20.0) fc = 20.0;
        double w = tan(pi * fc / (double)sr);
        double a = (w - 1.0) / (w + 1.0);
        double v = x[i] + feedback * fb;
        for (int s = 0; s < stages; s++) {
            double y = a * v + xs[s] - a * ys[s];
            xs[s] = v;
            ys[s] = y;
            v = y;
        }
        fb = v;
        out[i] = v;
    }
    return 0;
}
