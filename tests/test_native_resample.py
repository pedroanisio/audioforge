"""Native resampling / oversampling kernels against scipy (bit-exact where the
kernel promises it, bounded where it computes a waveshaper)."""
import numpy as np
import pytest
from scipy.signal import firwin, resample_poly
from scipy.signal._upfirdn import _output_len, _pad_h

from audioforge import _native as N


def test_frozen_filter_taps_equal_firwin():
    h = firwin(81, 0.25, window=("kaiser", 5.0))
    assert N._KAISER5_LP81.tobytes() == np.asarray(h, np.float64).tobytes()


def test_upfirdn_helpers_match_scipy():
    for lh in range(1, 100, 9):
        for n in range(1, 300, 17):
            for up, dn in ((1, 1), (4, 1), (1, 4), (3, 2), (147, 160)):
                assert N._upfirdn_output_len(lh, n, up, dn) == _output_len(lh, n, up, dn)
    h = np.arange(1.0, 12.0)
    for up in (1, 2, 3, 4):
        assert np.array_equal(N._pad_h(h, up), _pad_h(h, up))


@pytest.mark.parametrize("up,down", [(4, 1), (1, 4), (2, 1), (3, 2), (147, 160)])
@pytest.mark.parametrize("n", [1, 7, 300, 4801])
def test_resample_poly_bit_identical(up, down, n):
    rng = np.random.default_rng(n * 31 + up)
    x = rng.standard_normal(n)
    assert N.resample_poly(x, up, down).tobytes() == resample_poly(x, up, down).tobytes()
    st = rng.standard_normal((n, 2))
    assert N.resample_poly(st, up, down).tobytes() == resample_poly(st, up, down, axis=0).tobytes()


@pytest.mark.parametrize("n", [1, 5, 1000, 48000])
def test_true_peak4_equals_oversampled_max(n):
    st = np.random.default_rng(n).standard_normal((n, 2))
    up = np.abs(resample_poly(st, 4, 1, axis=0)).max(axis=1)
    ref = up[: (up.size // 4) * 4].reshape(-1, 4).max(axis=1)
    assert N.true_peak4(st).tobytes() == ref.tobytes()


@pytest.mark.parametrize("scale", [0.3, 3.0, 300.0])
def test_saturate4_matches_numpy_reference(scale):
    x = np.random.default_rng(5).standard_normal(20000) * scale
    bias, d = 0.036, 3.0
    up = resample_poly(x, 4, 1)
    up = (np.tanh((up + bias) * d) - np.tanh(bias * d)) / np.tanh(d)
    ref = resample_poly(up, 1, 4)[: x.size]
    assert np.max(np.abs(N.saturate4(x, bias, d) - ref)) < 1e-13


@pytest.mark.parametrize("L", [1, 2, 8, 240, 1001])
def test_running_min_matches_ndimage(L):
    from scipy.ndimage import minimum_filter1d
    x = np.random.default_rng(L).standard_normal(5000)
    ref = minimum_filter1d(x, size=L, mode="nearest", origin=-(L // 2))
    assert N.running_min_fwd(x, L).tobytes() == ref.tobytes()


@pytest.mark.parametrize("n,m", [(300, 240), (48000, 1440), (200000, 7200)])
def test_convolve_same_matches_scipy(n, m):
    from scipy.signal import fftconvolve
    from audioforge.convolution import convolve_same
    rng = np.random.default_rng(m)
    x, h = rng.standard_normal(n), np.hanning(m)
    ref = fftconvolve(x, h, mode="same")
    assert np.max(np.abs(convolve_same(x, h) - ref)) < 1e-12 * np.max(np.abs(ref))
