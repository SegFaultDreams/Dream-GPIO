import numpy as np

from dreamgpio.ads1299 import parse_frame, counts_to_uv
from dreamgpio.cues import RemCue
from dreamgpio.staging import stage_night, summary

from synth import FS, night


def test_parse_frame_signe():
    frame = bytes([0xC0, 0x00, 0x00]) + bytes([0xFF, 0xFF, 0xFF]) + bytes([0x00, 0x00, 0x01]) + bytes(18)
    status, v = parse_frame(frame, gain=24)
    assert status == 0xC00000
    assert np.isclose(v[0], counts_to_uv(-1, 24))
    assert np.isclose(v[1], counts_to_uv(1, 24))
    assert v[2] == 0


def test_parse_frame_desynchro():
    try:
        parse_frame(bytes(27))
    except ValueError:
        return
    raise AssertionError("aurait dû lever")


def test_stades_purs():
    for s in ("W", "N2", "N3", "REM"):
        stages = stage_night(night([s] * 6, seed=1), FS)
        majority = max(set(stages), key=stages.count)
        assert majority == s, (s, stages)


def test_summary_latence():
    hyp = ["W"] * 4 + ["N2"] * 10 + ["N3"] * 10 + ["N2"] * 6 + ["REM"] * 6
    stages = stage_night(night(hyp, seed=2), FS)
    s = summary(stages)
    assert s["rem_latency_min"] is not None
    assert 10 <= s["rem_latency_min"] <= 20


def test_cue_cooldown():
    cue = RemCue(enabled=False, min_rem_epochs=3, cooldown_s=600)
    fired = [cue.update("REM", now=30 * i) for i in range(30)]
    assert fired.count(True) == 2  # une fois à 3 époques, puis après 600 s
