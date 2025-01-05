"""
Enregistre une nuit : ADS1299 -> CSV (une ligne par échantillon).
Staging en direct toutes les 30 s si demandé, pour les cues et MQTT.

CSV parce que c'est lisible partout. Une nuit à 250 Hz = ~400 Mo.
Oui c'est gros. Non je n'ai pas encore fait l'export EDF. PR bienvenue.
"""

import csv
import signal as os_signal
import time
from collections import deque
from pathlib import Path

import numpy as np

from .ads1299 import ADS1299, N_CHANNELS
from .staging import EPOCH_S, classify, features
from .filters import clean

HEADER = ["t", "Fp1", "Fp2", "F3", "F4", "C3", "C4", "O1", "O2"]


def record(out_dir, sample_rate=250, gain=24, live=False, cue=None, publisher=None,
           max_hours=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / time.strftime("nuit_%Y-%m-%d_%H%M.csv")

    adc = ADS1299(sample_rate=sample_rate, gain=gain)
    adc.configure()

    stop = {"now": False}
    os_signal.signal(os_signal.SIGINT, lambda *_: stop.update(now=True))
    os_signal.signal(os_signal.SIGTERM, lambda *_: stop.update(now=True))

    n_epoch = EPOCH_S * sample_rate
    buf = deque(maxlen=n_epoch)
    epoch_idx = 0
    t0 = time.time()

    print(f"[dreamgpio] enregistrement -> {out_file}")
    print("[dreamgpio] Ctrl+C pour arrêter. Bonne nuit.")

    adc.start()
    try:
        with open(out_file, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(HEADER)
            i = 0
            while not stop["now"]:
                _, values = adc.read_frame()
                t = i / sample_rate
                w.writerow([f"{t:.4f}"] + [f"{v:.2f}" for v in values])
                i += 1
                if live:
                    buf.append(values)
                    if len(buf) == n_epoch and i % n_epoch == 0:
                        epoch = clean(np.array(buf).T, sample_rate)
                        stage = classify(features(epoch, sample_rate))
                        if cue:
                            cue.update(stage)
                        if publisher:
                            publisher.publish(stage, epoch_idx)
                        epoch_idx += 1
                if max_hours and time.time() - t0 > max_hours * 3600:
                    break
    finally:
        adc.close()
        if cue:
            cue.close()
        if publisher:
            publisher.close()
    print(f"[dreamgpio] fini. {i} échantillons, {i / sample_rate / 3600:.2f} h")
    return out_file


def load_csv(path):
    """Relit un CSV d'enregistrement. Retourne (data (8, n), fs)."""
    arr = np.loadtxt(path, delimiter=",", skiprows=1)
    t = arr[:, 0]
    fs = round(1 / np.median(np.diff(t)))
    return arr[:, 1:1 + N_CHANNELS].T, fs
