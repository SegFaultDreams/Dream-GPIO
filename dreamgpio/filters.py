"""Filtrage. Rien d'exotique : notch secteur + passe-bande."""

import numpy as np
from scipy import signal


def notch(x, fs, f0=50.0, q=30.0):
    """Coupe le 50 Hz. (En France c'est 50. Si tu habites aux US, 60.)"""
    b, a = signal.iirnotch(f0, q, fs)
    return signal.filtfilt(b, a, x, axis=-1)


def bandpass(x, fs, low=0.5, high=35.0, order=4):
    sos = signal.butter(order, [low, high], btype="bandpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x, axis=-1)


def clean(x, fs):
    """Chaîne par défaut pour le sommeil."""
    return bandpass(notch(x, fs), fs)


def flat_or_saturated(x, fs, flat_uv=0.5, sat_uv=500.0):
    """True si le segment ressemble à une électrode qui a bougé.
    Les électrodes sèches bougent. Beaucoup. Surtout quand tu te retournes."""
    x = np.asarray(x)
    return bool(np.std(x) < flat_uv or np.max(np.abs(x)) > sat_uv)
