"""Tests de cohérence : python -m pytest tests  (ou python tests/test_volteye.py)"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from volteye import config as C  # noqa: E402
from volteye.gaf import gasf, rgb_image  # noqa: E402
from volteye.signals import CLASSES, current, measurements, sample_instance  # noqa: E402
from volteye.stream import detect_events  # noqa: E402


def test_power_matches_rating():
    rng = np.random.default_rng(0)
    for m in CLASSES:
        inst = sample_instance(m, rng)
        p = measurements(current(inst, 0.8))["P_kW"]
        assert abs(p - 0.8 * inst.p_rated) / (0.8 * inst.p_rated) < 0.05, m


def test_signatures_differ():
    rng = np.random.default_rng(1)
    thd = {m: measurements(current(sample_instance(m, rng), 1.0))["THD"] for m in CLASSES}
    assert thd["four"] < 0.05 and thd["soudage"] > 0.3 and thd["cnc"] > 0.25


def test_gaf_shape_and_range():
    g = gasf(np.sin(np.linspace(0, 6, C.GAF_SIZE)))
    assert g.shape == (C.GAF_SIZE, C.GAF_SIZE) and g.min() >= -1 - 1e-9 and g.max() <= 1 + 1e-9
    img = rgb_image(current(sample_instance("cnc", np.random.default_rng(2)), 0.7))
    assert img.shape == (3, C.GAF_SIZE, C.GAF_SIZE)


def test_event_detection():
    p = np.r_[np.zeros(50), np.full(50, 20.0), np.full(50, 5.0)]
    events, delta = detect_events(p)
    assert len(events) == 2 and abs(events[0] - 50) <= 3 and delta[events[1]] < 0


def test_tariff_periods():
    assert C.tariff_period(3, 1) == "nuit" and C.tariff_period(19, 1) == "pointe" and C.tariff_period(10, 7) == "pointe"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
