/* AudioForge native kernel: polyphase upsample-FIR-downsample (upfirdn).
 *
 * Computes a window of scipy.signal.upfirdn's output bit-for-bit. For each
 * output y (upsampled position p = y*down, input index x_idx = p / up, phase
 * t = p % up) scipy accumulates, starting from 0.0 and in ascending input
 * order,
 *     out[y] += x[k] * hf[t*hpp + j],   k = x_idx - hpp + 1 + j,  j = 0..hpp-1
 * where hf is scipy's transposed/flipped coefficient table and taps outside
 * the signal are skipped. Here the caller zero-pads x by hpp-1 on each side,
 * so every term is evaluated; an out-of-range term is +-0 and adding a signed
 * zero never changes the accumulator (which starts at +0.0), so the result is
 * identical. Speed comes from vectorizing ACROSS outputs (independent
 * accumulators) while each output keeps scipy's exact summation order.
 * Plain IEEE-754 doubles: no FMA contraction, no reassociation, no fast-math.
 * Compile: cc -O3 -march=native -ffp-contract=off -fno-fast-math -fPIC -shared upfirdn.c -o upfirdn.so -lm
 */
#if defined(__clang__)
#pragma clang fp contract(off)
#endif

#define BLK 64


/* xp: zero-padded input (hpp-1 zeros before x[0] and after x[nx-1]);
 * out[i] = upfirdn output at index y0 + i, for i in [0, ny). */
int upfirdn_range(const double *xp, const double *hf, long hpp, long up,
                  long down, long y0, long ny, double *out) {
    double acc[BLK];
    if (hpp < 1 || up < 1 || down < 1 || ny < 0) return 1;
    if (down == 1) {
        /* y = m*up + t: fixed phase t, consecutive m -> contiguous inputs */
        long y1 = y0 + ny;
        for (long t = 0; t < up; t++) {
            const double *h = hf + t * hpp;
            long m0 = (y0 - t + up - 1) / up;           /* first m, y >= y0 */
            if (y0 - t <= 0) m0 = 0;
            long m1 = (y1 - t + up - 1) / up;           /* one past last m  */
            if (y1 - t <= 0) m1 = 0;
            for (long mb = m0; mb < m1; mb += BLK) {
                long nb = m1 - mb < BLK ? m1 - mb : BLK;
                for (long i = 0; i < nb; i++) acc[i] = 0.0;
                for (long j = 0; j < hpp; j++) {
                    const double c = h[j];
                    const double *xs = xp + mb + j;
                    for (long i = 0; i < nb; i++) acc[i] = acc[i] + xs[i] * c;
                }
                for (long i = 0; i < nb; i++)
                    out[(mb + i) * up + t - y0] = acc[i];
            }
        }
        return 0;
    }
    if (up == 1) {
        /* t = 0, x_idx = y*down: consecutive y -> inputs at stride down */
        for (long yb = 0; yb < ny; yb += BLK) {
            long nb = ny - yb < BLK ? ny - yb : BLK;
            const double *base = xp + (y0 + yb) * down;
            for (long i = 0; i < nb; i++) acc[i] = 0.0;
            for (long j = 0; j < hpp; j++) {
                const double c = hf[j];
                const double *xs = base + j;
                for (long i = 0; i < nb; i++)
                    acc[i] = acc[i] + xs[i * down] * c;
            }
            for (long i = 0; i < nb; i++) out[yb + i] = acc[i];
        }
        return 0;
    }
    for (long i = 0; i < ny; i++) {                     /* general ratio */
        long p = (y0 + i) * down;
        const double *xs = xp + p / up;
        const double *h = hf + (p % up) * hpp;
        double a = 0.0;
        for (long j = 0; j < hpp; j++) a = a + xs[j] * h[j];
        out[i] = a;
    }
    return 0;
}
