"""Générateur de faux EEG par stade, pour tester le staging sans dormir."""

import numpy as np

FS = 250


def _pink(n, rng):
    white = rng.standard_normal(n)
    f = np.fft.rfftfreq(n, 1 / FS)
    spec = np.fft.rfft(white)
    spec[1:] /= np.sqrt(f[1:])
    spec[0] = 0
    x = np.fft.irfft(spec, n)
    return x / x.std()


def _smooth_noise(n, rng, tau_s):
    """Bruit lent, positif, moyenne ~1 (pour moduler les amplitudes)."""
    k = max(1, int(tau_s * FS))
    x = np.convolve(rng.standard_normal(n + k), np.ones(k) / k, mode="valid")[:n]
    x = x / (x.std() + 1e-12)
    return np.clip(1 + 0.45 * x, 0.1, None)


def _osc(n, freq, amp, rng, bursty=False):
    # fréquence qui dérive un peu + amplitude qui respire : le cerveau n'est pas un GBF
    f_inst = freq * (1 + 0.08 * (_smooth_noise(n, rng, 2.0) - 1)) + 0.2 * rng.standard_normal()
    phase = 2 * np.pi * np.cumsum(f_inst) / FS + rng.uniform(0, 6.28)
    x = amp * _smooth_noise(n, rng, 0.8) * np.sin(phase)
    if bursty:  # fuseaux : bouffées de ~1 s
        env = np.zeros(n)
        for _ in range(rng.integers(2, 5)):
            c = rng.integers(FS, n - FS)
            env += np.exp(-0.5 * ((np.arange(n) - c) / (0.25 * FS)) ** 2)
        x *= env
    return x


def epoch(stage, rng, seconds=30):
    """Retourne un array (8, seconds*FS) en uV."""
    n = seconds * FS
    # une source commune (le cortex ne fait pas 8 choses différentes) + bruit par voie
    if stage == "W":
        common = _osc(n, 20, 6, rng)
        alpha = _osc(n, 10, 25, rng)
    else:
        alpha = np.zeros(n)
        common = {
            "N1": lambda: _osc(n, 6, 18, rng),
            "N2": lambda: _osc(n, 1.5, 12, rng) + _osc(n, 13.5, 30, rng, bursty=True) + _osc(n, 6, 6, rng),
            "N3": lambda: _osc(n, 1.0, 70, rng),
            "REM": lambda: _osc(n, 6, 20, rng),
        }[stage]()
    out = np.zeros((8, n))
    for ch in range(8):
        gain = 1.0 + 0.05 * rng.standard_normal()
        out[ch] = 11 * _pink(n, rng) + gain * common + (alpha if ch >= 6 else 0.3 * alpha)
    if stage == "REM":  # yeux qui roulent : déflexions lentes en opposition de phase
        t = np.arange(n) / FS
        saccades = np.zeros(n)
        for c in rng.uniform(1, seconds - 1, rng.integers(6, 12)):
            saccades += 80 * np.tanh((t - c) * 8) * np.exp(-((t - c) / 1.5) ** 2)
        out[0] += saccades
        out[1] -= saccades
    return out


def night(hypnogram, seed=0):
    rng = np.random.default_rng(seed)
    return np.concatenate([epoch(s, rng) for s in hypnogram], axis=1)
