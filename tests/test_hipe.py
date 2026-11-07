"""Tests de la validation sur données réelles HIPE (les tests d'intégration exigent l'archive locale)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from volteye import config as C  # noqa: E402
from volteye import hipe  # noqa: E402


def test_label_events_matches_nearest_machine():
    truth = pd.DataFrame({"t": [100, 200], "machine": ["SolderingOven", "VacuumPump1"], "dP_machine": [3.5, 0.9]})
    labels = hipe.label_events([99, 150, 203], truth)
    assert list(labels) == ["SolderingOven", "autre", "VacuumPump1"]


def test_chronological_split_keeps_order_per_class():
    labels = np.array(["a"] * 20 + ["b"] * 10 + ["c"] * 3)
    tr, te, classes = hipe.chronological_split(labels, share=0.7, min_events=5)
    assert classes == ["a", "b"]
    assert tr[:14].all() and te[14:20].all()          # les premiers événements de « a » apprennent
    assert not (tr | te)[30:].any()                   # « c » : trop peu d'événements, écarté


def test_delta_features_oriented_as_start():
    idx = pd.date_range("2017-10-23", periods=20, freq="5s")
    p = np.r_[np.full(10, 10.0), np.full(10, 6.0)]     # arrêt d'une charge de 4 kW
    df = pd.DataFrame({f"{hipe.SITE}|P_kW": p, f"{hipe.SITE}|Q_kvar": p / 2, f"{hipe.SITE}|S_kVA": p * 1.1,
                       f"{hipe.SITE}|THD": 5.0, **{f"{hipe.SITE}|H{h}": 2.0 for h in hipe.HARMONICS}}, index=idx)
    f = hipe.delta_features(df, [9])
    assert f.loc[0, "dP"] == pytest.approx(4.0) and f.loc[0, "dQ"] == pytest.approx(2.0)


@pytest.mark.skipif(not (C.ARTIFACTS / "hipe_metrics.json").exists(), reason="validation HIPE non exécutée")
def test_hipe_metrics_are_consistent():
    m = json.loads((C.ARTIFACTS / "hipe_metrics.json").read_text(encoding="utf-8"))
    assert 0 < m["detection"]["rappel"] <= 1
    sig = m["signatures"]
    assert sig["VoltEye - + THD et harmoniques + forêt aléatoire"]["exactitude"] >= \
        sig["A - P, Q, facteur de puissance + forêt aléatoire"]["exactitude"]
    fc = m["prevision_1h"]
    assert fc["VoltEye - gradient boosting"]["MAE_kW"] < fc["Baseline - valeur d'il y a 1 h"]["MAE_kW"]
    assert (C.ARTIFACTS / "hipe_replay.parquet").exists()
