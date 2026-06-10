/* AudioForge native kernel: Dattorro plate tank with delay-line modulation.
 * Same topology/constants/taps as audioforge/spaces.py; adds the original
 * design's swept first-allpass read (linear-interpolated fractional delay)
 * for the chorus shimmer an LTI rendering cannot reproduce.
 * Pure IEEE-754 double math, fixed constants, no fast-math: deterministic.
 * Compile: cc -O2 -fPIC -shared plate_mod.c -o plate_mod.so -lm
 */
#include <math.h>
#include <stdlib.h>

typedef struct { double *buf; int n; int i; double g; int base; } APF;
typedef struct { double *buf; int n; int i; } DLY;

static double tap_at(const double *buf, int n, int i, double d) {
    double rpos = (double)i - d;
    while (rpos < 0.0) rpos += (double)n;
    int i0 = (int)rpos;
    double fr = rpos - (double)i0;
    int i1 = (i0 + 1) % n;
    return buf[i0] * (1.0 - fr) + buf[i1] * fr;
}

static double apf_tick(APF *a, double x, double exc) {
    double z = tap_at(a->buf, a->n, a->i, (double)a->base + exc);
    double v = x + a->g * z;
    a->buf[a->i] = v;
    a->i = (a->i + 1) % a->n;
    return z - a->g * v;
}

static double dly_tick(DLY *d, double x) {
    double out = d->buf[d->i];
    d->buf[d->i] = x;
    d->i = (d->i + 1) % d->n;
    return out;
}

static double dly_tap(const DLY *d, int t) {
    int idx = d->i - 1 - t;
    while (idx < 0) idx += d->n;
    return d->buf[idx];
}

static double apf_tap(const APF *a, int t) {
    int idx = a->i - 1 - t;
    while (idx < 0) idx += a->n;
    return a->buf[idx];
}

static int SC(double ref, double R) {
    int v = (int)floor(ref * R + 0.5);
    return v < 2 ? 2 : v;
}

static APF mk_apf(double ref, double R, double g, int headroom) {
    APF a;
    a.base = SC(ref, R);
    a.n = a.base + headroom;
    a.buf = calloc((size_t)a.n, sizeof(double));
    a.i = 0; a.g = g;
    return a;
}

static DLY mk_dly(double ref, double R) {
    DLY d;
    d.n = SC(ref, R);
    d.buf = calloc((size_t)d.n, sizeof(double));
    d.i = 0;
    return d;
}

int plate_mod(const double *x, long n, int sr, double decay, double damp,
              double mod_depth, double mod_rate, double *wetL, double *wetR) {
    double R = (double)sr / 29761.0;
    double bw = 0.9995;
    int head = (int)(12.0 * R) + 8;

    APF in0 = mk_apf(142, R, 0.750, 2), in1 = mk_apf(107, R, 0.750, 2);
    APF in2 = mk_apf(379, R, 0.625, 2), in3 = mk_apf(277, R, 0.625, 2);
    APF a1 = mk_apf(672, R, 0.70, head), a2 = mk_apf(1800, R, 0.50, 2);
    APF b1 = mk_apf(908, R, 0.70, head), b2 = mk_apf(2656, R, 0.50, 2);
    DLY ad1 = mk_dly(4453, R), ad2 = mk_dly(3720, R);
    DLY bd1 = mk_dly(4217, R), bd2 = mk_dly(3163, R);

    int tL0 = SC(266, R), tL1 = SC(2974, R), tL2 = SC(1913, R);
    int tL3 = SC(1996, R), tL4 = SC(1990, R), tL5 = SC(187, R), tL6 = SC(1066, R);
    int tR0 = SC(353, R), tR1 = SC(3627, R), tR2 = SC(1228, R);
    int tR3 = SC(2673, R), tR4 = SC(2111, R), tR5 = SC(335, R), tR6 = SC(121, R);

    double lp_in = 0.0, lp_a = 0.0, lp_b = 0.0, fb_a = 0.0, fb_b = 0.0;
    double exc_max = mod_depth * 12.0 * R;
    double w1 = 2.0 * M_PI * mod_rate / (double)sr;
    double w2 = 2.0 * M_PI * (mod_rate * 0.93) / (double)sr;

    for (long i = 0; i < n; i++) {
        lp_in = bw * x[i] + (1.0 - bw) * lp_in;
        double v = lp_in;
        v = apf_tick(&in0, v, 0.0);
        v = apf_tick(&in1, v, 0.0);
        v = apf_tick(&in2, v, 0.0);
        v = apf_tick(&in3, v, 0.0);

        double e1 = exc_max * (0.5 + 0.5 * sin(w1 * (double)i));
        double e2 = exc_max * (0.5 + 0.5 * sin(w2 * (double)i + 1.7));

        double ua = apf_tick(&a1, v + decay * fb_b, e1);
        double oa = dly_tick(&ad1, ua);
        lp_a = (1.0 - damp) * oa + damp * lp_a;
        double fa = dly_tick(&ad2, apf_tick(&a2, decay * lp_a, 0.0));

        double ub = apf_tick(&b1, v + decay * fb_a, e2);
        double ob = dly_tick(&bd1, ub);
        lp_b = (1.0 - damp) * ob + damp * lp_b;
        double fb = dly_tick(&bd2, apf_tick(&b2, decay * lp_b, 0.0));

        fb_a = fa; fb_b = fb;

        wetL[i] = 0.6 * ( dly_tap(&bd1, tL0) + dly_tap(&bd1, tL1)
                        - apf_tap(&b2, tL2) + dly_tap(&bd2, tL3)
                        - dly_tap(&ad1, tL4) - apf_tap(&a2, tL5)
                        - dly_tap(&ad2, tL6) );
        wetR[i] = 0.6 * ( dly_tap(&ad1, tR0) + dly_tap(&ad1, tR1)
                        - apf_tap(&a2, tR2) + dly_tap(&ad2, tR3)
                        - dly_tap(&bd1, tR4) - apf_tap(&b2, tR5)
                        - dly_tap(&bd2, tR6) );
    }
    free(in0.buf); free(in1.buf); free(in2.buf); free(in3.buf);
    free(a1.buf); free(a2.buf); free(b1.buf); free(b2.buf);
    free(ad1.buf); free(ad2.buf); free(bd1.buf); free(bd2.buf);
    return 0;
}
