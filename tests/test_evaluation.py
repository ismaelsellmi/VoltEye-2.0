"""Tests du protocole d'évaluation : pas de fuite d'information du futur, références d'optimisation."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from volteye import anomaly, optimization  # noqa: E402
from volteye import config as C  # noqa: E402
from volteye.stream import detect_events  # noqa: E402


def _toy_series(months=5, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-11-01", periods=24 * 30 * months, freq="h")
    x = pd.DataFrame({"heure": idx.hour, "jour_semaine": idx.dayofweek}, index=idx)
    y = pd.Series(10 + 5 * (idx.hour >= 8) + rng.normal(0, 0.5, len(idx)), index=idx)
    return x, y


def test_walk_forward_ignores_future():
    x, y = _toy_series()
    first = "2026-01-01"
    e1 = anomaly.expected_walk_forward(y, x, first)
    y2 = y.copy()
    y2[y2.index >= "2026-03-01"] *= 5                       # on modifie fortement l'avenir
    e2 = anomaly.expected_walk_forward(y2, x, first)
    past = (e1.index >= first) & (e1.index < "2026-03-01")
    assert np.allclose(e1[past], e2[past])
    assert e1[e1.index < first].isna().all()                 # rodage : aucune prévision


def test_causal_scale_ignores_future():
    idx = pd.date_range("2026-01-01", periods=120, freq="D")
    rng = np.random.default_rng(1)
    feats = pd.DataFrame(rng.normal(0, 1, (120, 4)), index=idx, columns=anomaly.FEATS)
    energy = pd.Series(100.0, index=idx)
    z1 = anomaly.causal_robust_z(feats, energy)
    f2 = feats.copy()
    f2.iloc[90:] *= 50
    z2 = anomaly.causal_robust_z(f2, energy)
    assert np.allclose(z1.iloc[:90].fillna(0), z2.iloc[:90].fillna(0))


def test_threshold_maximises_validation_f1():
    score = pd.Series([1, 2, 3, 8, 9, 10], dtype=float)
    truth = pd.Series([0, 0, 0, 1, 1, 1], dtype=bool)
    t = anomaly.choose_threshold(score, truth, np.arange(0, 12, 1.0))
    assert 3 <= t < 8 and t == 7.0                           # à F1 égal, le seuil le plus élevé


def test_milp_beats_both_references():
    base = np.r_[np.full(6, 20.0), np.full(16, 90.0), np.full(2, 20.0)]
    for month in (1, 7):
        prices = np.array([C.tariff(h, month) for h in range(24)])
        opt, status = optimization.optimize(base, prices)
        assert status == "1"
        bill_opt, _ = optimization._bill(base, opt, prices)
        bill_ref, _ = optimization._bill(base, [max(t["fenetre"][0], 7) for t in optimization.TASKS], prices)
        bill_op, _ = optimization._bill(base, optimization.tariff_aware_starts(prices), prices)
        assert bill_opt <= bill_op + 1e-6 and bill_opt <= bill_ref + 1e-6


def test_close_events_are_separated():
    p = np.r_[np.zeros(40), np.full(5, 12.0), np.full(40, 30.0)]
    events, _ = detect_events(p)
    assert len(events) == 2 and abs(events[0] - 40) <= 2 and abs(events[1] - 45) <= 2
