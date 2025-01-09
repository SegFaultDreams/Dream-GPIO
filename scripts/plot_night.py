"""
Trace une nuit : hypnogramme, spectrogramme de C3, extrait de 30 s.

    python scripts/plot_night.py data/raw/nuit_2025-01-08_2341.csv --start 23:41 --out nights/2025-01-08

Vert sur noir parce que c'est plus joli, et parce qu'il est 3 h du matin quand je regarde.
"""

import argparse
import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

GREEN = "#39ff88"
DIM = "#1d6b43"
BG = "#0b0f0c"
ORDER = ["W", "REM", "N1", "N2", "N3"]  # l'ordre des hypnogrammes classiques, REM en haut


def _style(ax):
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_color(DIM)
    ax.tick_params(colors=GREEN, labelsize=8)
    ax.xaxis.label.set_color(GREEN)
    ax.yaxis.label.set_color(GREEN)
    ax.title.set_color(GREEN)


def clock_ticks(ax, start, total_s, every_min=60):
    ticks, labels = [], []
    first = (60 - start.minute) % every_min * 60
    for s in range(first, int(total_s) + 1, every_min * 60):
        ticks.append(s / 3600)
        labels.append((start + dt.timedelta(seconds=s)).strftime("%H:%M"))
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)


def plot_hypnogram(stages, start, out, title):
    y = [ORDER.index(s) if s in ORDER else np.nan for s in stages]
    x = np.arange(len(stages)) * 30 / 3600
    fig, ax = plt.subplots(figsize=(11, 3.2), facecolor=BG)
    _style(ax)
    ax.step(x, y, where="post", color=GREEN, lw=1.3)
    rem = np.array([s == "REM" for s in stages])
    ax.fill_between(x, -0.35, 0.35 + 1, where=rem, step="post", color=GREEN, alpha=0.12, lw=0)
    ax.set_yticks(range(len(ORDER)))
    ax.set_yticklabels(ORDER)
    ax.invert_yaxis()
    ax.set_xlim(0, x[-1] + 30 / 3600)
    clock_ticks(ax, start, len(stages) * 30)
    ax.set_title(title, loc="left", fontsize=10, color=GREEN)
    ax.grid(axis="x", color=DIM, lw=0.4, alpha=0.6)
    fig.tight_layout()
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)


def plot_spectrogram(x, fs, start, out, title):
    f, t, sxx = signal.spectrogram(x, fs=fs, nperseg=int(30 * fs), noverlap=0)
    m = f <= 30
    fig, ax = plt.subplots(figsize=(11, 3.2), facecolor=BG)
    _style(ax)
    db = 10 * np.log10(sxx[m] + 1e-6)
    lo, hi = np.percentile(db, [5, 99.5])
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("nuit", [BG, DIM, GREEN, "#e8fff0"])
    ax.pcolormesh(t / 3600, f[m], db, cmap=cmap, vmin=lo, vmax=hi, shading="auto")
    ax.set_ylabel("Hz")
    clock_ticks(ax, start, t[-1])
    ax.set_title(title, loc="left", fontsize=10, color=GREEN)
    fig.tight_layout()
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)


def plot_traces(seg, fs, names, out, title):
    t = np.arange(seg.shape[1]) / fs
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=BG)
    _style(ax)
    step = 150
    for i, (row, name) in enumerate(zip(seg, names)):
        ax.plot(t, row - i * step, color=GREEN, lw=0.6)
    ax.set_yticks([-i * step for i in range(len(names))])
    ax.set_yticklabels(names)
    ax.set_xlabel("s")
    ax.set_xlim(0, t[-1])
    ax.set_title(title, loc="left", fontsize=10, color=GREEN)
    fig.tight_layout()
    fig.savefig(out, dpi=140, facecolor=BG)
    plt.close(fig)


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from dreamgpio.acquire import load_csv, HEADER
    from dreamgpio.filters import clean
    from dreamgpio.staging import stage_night

    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--start", required=True, help="heure de début, HH:MM")
    p.add_argument("--out", required=True)
    p.add_argument("--extract", type=float, default=None, help="début de l'extrait (h depuis le début)")
    a = p.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data, fs = load_csv(a.csv)
    data = clean(data, fs)
    stages = stage_night(data, fs, preprocess=False)
    day = Path(a.csv).stem.split("_")[1]
    start = dt.datetime.strptime(f"{day} {a.start}", "%Y-%m-%d %H:%M")

    plot_hypnogram(stages, start, out / "hypnogramme.png", f"nuit du {start:%d/%m/%Y}  -  hypnogramme (heuristique)")
    plot_spectrogram(data[4], fs, start, out / "spectrogramme_C3.png", "C3  -  spectrogramme 0-30 Hz")
    if a.extract is not None:
        i0 = int(a.extract * 3600 * fs)
        plot_traces(data[:, i0:i0 + 30 * fs], fs, HEADER[1:], out / "extrait_30s.png", "30 s brutes filtrées")
    (out / "stades.txt").write_text("\n".join(stages) + "\n")


if __name__ == "__main__":
    main()
