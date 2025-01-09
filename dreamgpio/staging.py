"""
Estimation des stades de sommeil par époques de 30 s.

Soyons clairs : c'est une heuristique, pas une polysomnographie.
Pas d'EMG du menton, pas de vrai EOG, des électrodes sèches.
Je m'en sers pour savoir grosso modo QUAND je suis en paradoxal,
pas pour faire un diagnostic. Si tu veux du sérieux, regarde YASA.

Montage (voir hardware/bonnet.md) :
    0 Fp1  1 Fp2  2 F3  3 F4  4 C3  5 C4  6 O1  7 O2
"""

import numpy as np
from scipy import signal
from scipy.integrate import trapezoid

from .filters import clean, flat_or_saturated

EPOCH_S = 30
CH = {"Fp1": 0, "Fp2": 1, "F3": 2, "F4": 3, "C3": 4, "C4": 5, "O1": 6, "O2": 7}

BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 12.0),
    "sigma": (12.0, 15.0),
    "beta": (15.0, 30.0),
}

# seuils réglés à la main sur mes nuits. donc sur MA tête. à adapter
THRESHOLDS = {
    "wake_alpha": 0.28,
    "wake_beta": 0.22,
    "n3_delta": 0.75,
    "n2_sigma": 0.10,
    "rem_theta": 0.24,
    "rem_eye": 2.0,
}

STAGES = ["W", "N1", "N2", "N3", "REM", "?"]


def band_powers(x, fs):
    """Puissances relatives par bande (somme des bandes = 1)."""
    f, pxx = signal.welch(x, fs=fs, nperseg=int(4 * fs))
    abs_p = {}
    for name, (lo, hi) in BANDS.items():
        m = (f >= lo) & (f < hi)
        abs_p[name] = trapezoid(pxx[m], f[m])
    total = sum(abs_p.values()) or 1e-12
    return {k: v / total for k, v in abs_p.items()}


def eye_index(fp1, fp2, fs):
    """Proxy de mouvements oculaires : énergie lente de Fp1-Fp2
    rapportée au bruit de fond. Les yeux qui roulent en REM font
    des grosses déflexions en opposition de phase sur les deux frontales."""
    d = fp1 - fp2
    f, pxx = signal.welch(d, fs=fs, nperseg=int(4 * fs))
    slow = pxx[(f >= 0.3) & (f < 4.0)].mean()
    ref = pxx[(f >= 15.0) & (f < 30.0)].mean() or 1e-12
    return float(np.log10(slow / ref))


def features(epoch, fs):
    """epoch : array (8, n). Retourne un dict de features."""
    central = (epoch[CH["C3"]] + epoch[CH["C4"]]) / 2
    occipital = (epoch[CH["O1"]] + epoch[CH["O2"]]) / 2
    bp_c = band_powers(central, fs)
    bp_o = band_powers(occipital, fs)
    return {
        "delta": bp_c["delta"],
        "theta": bp_c["theta"],
        "sigma": bp_c["sigma"],
        "beta": bp_c["beta"],
        "alpha_occ": bp_o["alpha"],
        "eye": eye_index(epoch[CH["Fp1"]], epoch[CH["Fp2"]], fs),
        "bad": sum(flat_or_saturated(epoch[c], fs) for c in (CH["C3"], CH["C4"])) == 2,
    }


def classify(ft, th=THRESHOLDS):
    if ft["bad"]:
        return "?"
    if ft["alpha_occ"] > th["wake_alpha"] or ft["beta"] > th["wake_beta"]:
        return "W"
    if ft["delta"] > th["n3_delta"]:
        return "N3"
    if ft["theta"] > th["rem_theta"] and ft["eye"] > th["rem_eye"]:
        return "REM"
    if ft["sigma"] > th["n2_sigma"]:
        return "N2"
    if ft["theta"] > th["rem_theta"]:
        return "N1"
    return "N2"


def smooth(stages):
    """Une époque isolée entre deux voisines identiques prend leur valeur.
    Évite les REM d'une seule époque au milieu du N2 (ça arrive jamais en vrai)."""
    out = list(stages)
    for i in range(1, len(out) - 1):
        if out[i - 1] == out[i + 1] != out[i]:
            out[i] = out[i - 1]
    return out


def stage_night(data, fs, preprocess=True):
    """data : array (8, n_samples) en uV. Retourne une liste de stades, un par 30 s."""
    data = np.asarray(data, dtype=float)
    if preprocess:
        data = clean(data, fs)
    n = int(EPOCH_S * fs)
    n_epochs = data.shape[1] // n
    raw = [classify(features(data[:, i * n:(i + 1) * n], fs)) for i in range(n_epochs)]
    return smooth(raw)


def summary(stages):
    """Minutes par stade + latence du premier REM."""
    counts = {s: stages.count(s) * EPOCH_S / 60 for s in STAGES}
    first_rem = next((i for i, s in enumerate(stages) if s == "REM"), None)
    counts["rem_latency_min"] = None if first_rem is None else first_rem * EPOCH_S / 60
    return counts
