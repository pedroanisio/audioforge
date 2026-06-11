/* AudioForge native kernel: brass lip-reed voice (waveguide + brassiness).
 *
 * Built on the same self-oscillating pressure-controlled reed waveguide as
 * the blown pipe (a delay-line bore closed by a reed/lip reflection table —
 * the sequential, nonlinear loop that cannot be an LTI impulse response),
 * made brass-distinct and made RELIABLE by measurement (540-point
 * f x pressure x brightness x lip acceptance grid):
 *
 *  1. MODE PRIMING. The delay line starts with one quiet fundamental cycle
 *     (amp 0.18) so the first bore mode wins the lock-in race. Measured:
 *     fundamental lock 62-77% unprimed -> 99.8% primed. Deterministic (no
 *     RNG; the prime is a fixed function of the line length).
 *  2. CALIBRATED IN-LOOP STEEPENING. tanh(steep*x)*(gamma/steep) has
 *     small-signal slope exactly gamma = 1.05 + 0.30*brightness*
 *     (0.4+0.6*pressure): a documented 1.05..1.35 overdrive band on top of
 *     the reed loop gain, so the blown fixed-point analysis carries over.
 *     (The 1.05 floor keeps the dark/soft corner speaking.) The previous
 *     normalization tanh(steep*x)/tanh(steep) multiplied loop gain by
 *     1.31x..7.0x — an uncalibrated overdrive that also made mode
 *     selection amplitude-dependent.
 *  3. EMPIRICAL TUNING. The bore filter a + (1-a)z^-1 adds (1-a) samples
 *     of group delay and the reed adds its own phase; the delay-line
 *     length carries a measured correction (fit residual 0.32 samples).
 *     Measured tuning: +10 +/- 19 cents across the grid (worst 66) vs
 *     +60 +/- 47 uncorrected — and no longer drifts with brightness.
 *  4. POST-LOOP BRASS COLORATION (cannot affect loop stability):
 *     saturation at the loop's natural scale steepens the odd series, and
 *     a rectifying "bell flare" term supplies the even harmonics a
 *     cylindrical reed loop cannot support (real brass gets them from the
 *     flaring bell; a clarinet does not). The rectifier first lowpasses
 *     the steepened wave back toward its fundamental (a memoryless
 *     shaper cannot add even harmonics to a near-square, two-level
 *     signal), then takes |x|, whose even series falls as 1/(4k^2-1).
 *     Measured: h2 tracks brightness into the -15..-25 dB range — then a
 *     DC blocker and a resonant brass-formant bandpass (0.4..4.5 kHz,
 *     tracking note and brightness) for the ringing, cuivre color.
 *  5. The lip parameter is a real embouchure: it stiffens the reed table
 *     a touch and bends pitch (measured ~ +/-20 cents around lip=0.5).
 *
 * Breath turbulence is seeded noise SUPPLIED BY THE CALLER (as blown.c:
 * determinism stays in Python's hands; variants re-realize the breath).
 * Pure IEEE-754 doubles, fixed constants. Completes the physical-model
 * family bowed / blown / brass.
 * Compile: cc -O2 -fPIC -shared brass.c -o brass.so -lm
 */
#include <math.h>
#include <stdlib.h>

int brass_lip(double freq, long n, int sr, double pressure,
              double brightness, double lip, const double *noise,
              double *out) {
    if (!out || !noise || n <= 0 || freq <= 0.0 || sr <= 0)
        return 1;
    if (pressure < 0.2) pressure = 0.2;
    if (pressure > 1.0) pressure = 1.0;
    if (brightness < 0.0) brightness = 0.0;
    if (brightness > 1.0) brightness = 1.0;
    if (lip < 0.0) lip = 0.0;
    if (lip > 1.0) lip = 1.0;

    /* embouchure pitch bend around lip = 0.5 */
    double f_eff = freq * pow(2.0, (lip - 0.5) * 24.0 / 1200.0);

    /* bore losses: two-tap average, blended toward unfiltered by
     * brightness (unity at DC so the loop self-oscillates) */
    double a = 0.5 + 0.5 * brightness;

    /* half-period cylinder with the MEASURED loop-phase correction
     * (see header, point 3) */
    double L = (double)sr / f_eff / 2.0
        - (2.0 - (2.559 - 0.940 * (1.0 - a) - 0.007 * pressure));
    if (L < 4.0) L = 4.0;
    int len = (int)L;
    double frac = L - len;
    double *dl = calloc((size_t)(len + 2), sizeof(double));
    if (!dl)
        return 2;
    int idx = 0;
    /* mode priming: one quiet fundamental cycle (see header, point 1) */
    for (int k = 0; k < len + 2; k++)
        dl[k] = 0.18 * sin(2.0 * M_PI * (double)k / L);

    double prev = 0.0;
    double breath_target = 0.5 + 0.22 * pressure;
    /* embouchure: a tighter lip closes the reed table a touch (narrow
     * range — wider lip influence destabilizes mode selection; measured) */
    double reed_base = 0.71 + 0.02 * lip;
    double reed_slope = -(0.24 + 0.10 * pressure);
    /* calibrated steepening (see header, point 2) */
    double steep = 1.0 + 6.0 * brightness * (0.4 + 0.6 * pressure);
    double gamma = 1.05 + 0.30 * brightness * (0.4 + 0.6 * pressure);
    double shape_gain = gamma / steep;
    long ramp = (long)(0.04 * sr);

    /* post-loop brass formant (0.4..4.5 kHz, note/brightness tracking) */
    double fcent = freq * (3.0 + 3.0 * brightness);
    if (fcent < 400.0) fcent = 400.0;
    double fhi = 4500.0 < 0.45 * (double)sr ? 4500.0 : 0.45 * (double)sr;
    if (fcent > fhi) fcent = fhi;
    double radius = 0.96;
    double fa1 = -2.0 * radius * cos(2.0 * M_PI * fcent / (double)sr);
    double fa2 = radius * radius;
    double fb0 = 1.0 - radius;
    double fy1 = 0.0, fy2 = 0.0, fx1 = 0.0;
    double dc_x = 0.0, dc_y = 0.0;

    /* post-loop asymmetric saturation (see header, point 4) */
    double pdrv = 1.0 + 5.0 * brightness * (0.3 + 0.7 * pressure);
    double bell = 0.25 + 0.45 * brightness;   /* even-harmonic "flare" mix */
    double pnorm = tanh(pdrv);
    /* re-sinusoidizer for the flare rectifier: one-pole LP keyed to the
     * note (a memoryless shaper cannot add evens to a square wave) */
    double csm = 1.0 - exp(-2.0 * M_PI * 1.2 * freq / (double)sr);
    double sm = 0.0;

    for (long i = 0; i < n; i++) {
        double breath = breath_target
            * (i < ramp ? (double)i / (double)ramp : 1.0);
        breath *= 1.0 + 0.06 * noise[i];          /* seeded turbulence */

        int j0 = idx, j1 = (idx + 1) % (len + 2);
        double dout = dl[j0] * (1.0 - frac) + dl[j1] * frac;
        double filt = a * dout + (1.0 - a) * prev;
        prev = dout;
        double shaped = tanh(steep * filt) * shape_gain;
        double bore = -0.98 * shaped;

        double pd = bore - breath;
        double refl = reed_base + reed_slope * pd;
        if (refl > 1.0) refl = 1.0;
        if (refl < -1.0) refl = -1.0;
        double in = breath + pd * refl;
        dl[(idx + len) % (len + 2)] = in;
        idx = (idx + 1) % (len + 2);

        /* --- post-loop coloration (cannot affect loop stability) --- */
        double bnorm = bore / shape_gain;       /* loop-natural scale */
        double bz = tanh(pdrv * bnorm) / pnorm; /* odd-series steepening */
        /* bell flare: lowpass bz back toward its fundamental, then
         * rectify — |near-sine| carries the even series at 1/(4k^2-1) */
        sm += csm * (bz - sm);
        double col = bz + 0.9 * bell * fabs(sm) + 1e-24;
        dc_y = col - dc_x + 0.999 * dc_y;       /* DC blocker, R=0.999 */
        dc_x = col;
        double fout = fb0 * (dc_y - fx1) - fa1 * fy1 - fa2 * fy2;
        fx1 = dc_y; fy2 = fy1; fy1 = fout;
        out[i] = 0.7 * dc_y + 1.3 * fout;
    }
    free(dl);
    return 0;
}