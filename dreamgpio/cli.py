"""
dreamgpio check     -> vérifie la puce et le signal de test interne
dreamgpio record    -> enregistre une nuit
dreamgpio stage     -> staging d'un CSV déjà enregistré
"""

import argparse
import sys

import numpy as np


def cmd_check(args):
    from .ads1299 import ADS1299
    adc = ADS1299(sample_rate=250, gain=args.gain)
    adc.configure(test_signal=True)
    adc.start()
    try:
        frames = [adc.read_frame()[1] for _ in range(500)]
    finally:
        adc.close()
    arr = np.array(frames)
    print("p2p par voie (uV) :", np.round(np.ptp(arr, axis=0), 1))
    print("Tu dois voir le même signal carré (quelques mV) sur les 8 voies.")
    print("Une voie plate = soudure. Toutes plates = SPI ou START.")


def cmd_record(args):
    from .acquire import record
    cue = None
    if args.cues:
        from .cues import RemCue
        cue = RemCue(enabled=True)
    record(args.out, sample_rate=args.rate, gain=args.gain,
           live=bool(cue), cue=cue, max_hours=args.max_hours)


def cmd_stage(args):
    from .acquire import load_csv
    from .staging import stage_night, summary
    data, fs = load_csv(args.csv)
    stages = stage_night(data, fs)
    s = summary(stages)
    for k in ("W", "N1", "N2", "N3", "REM", "?"):
        print(f"{k:>4} : {s[k]:6.1f} min")
    lat = s["rem_latency_min"]
    print(f"latence REM : {lat:.1f} min" if lat is not None else "latence REM : pas de REM (???)")
    if args.save:
        with open(args.save, "w") as fh:
            fh.write("\n".join(stages) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(prog="dreamgpio")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("--gain", type=int, default=24)
    c.set_defaults(func=cmd_check)

    r = sub.add_parser("record")
    r.add_argument("--out", default="data/raw")
    r.add_argument("--rate", type=int, default=250)
    r.add_argument("--gain", type=int, default=24)
    r.add_argument("--cues", action="store_true", help="active LED/vibreur en REM (lis cues.py avant)")
    r.add_argument("--max-hours", type=float, default=None)
    r.set_defaults(func=cmd_record)

    s = sub.add_parser("stage")
    s.add_argument("csv")
    s.add_argument("--save", help="écrit un stade par ligne dans ce fichier")
    s.set_defaults(func=cmd_stage)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
