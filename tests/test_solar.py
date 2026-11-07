"""Tests du modèle solaire : géométrie du soleil, productible annuel, prévision J+1 sans fuite."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from volteye import solar  # noqa: E402


def test_sun_geometry():
    idx = pd.DatetimeIndex(["2026-06-21 12:00", "2026-12-21 12:00", "2026-06-21 01:00"])
    cosz, *_ = solar.sun(idx)
    assert cosz[0] > cosz[1] > 0 and cosz[2] == 0          # midi d'été plus haut que midi d'hiver, nuit nulle


def test_annual_yield_in_tunis_range():
    idx = pd.date_range("2025-11-01", "2026-11-01", freq="h", inclusive="left")
    temp = 19 + 8 * np.cos(2 * np.pi * (idx.dayofyear - 215) / 365)
    pv = solar.simulate(idx, temp)
    yield_kwh_kwc = pv["pv_kW"].sum() / solar.KWC
    assert 1300 < yield_kwh_kwc < 1900
    assert (pv["pv_kW"][idx.hour < 5] == 0).all()


def test_forecast_uses_only_training_period():
    idx = pd.date_range("2025-11-01", "2026-11-01", freq="h", inclusive="left")
    hist = pd.DataFrame({"temperature": 20.0}, index=idx)
    pv = solar.simulate(idx, hist["temperature"].to_numpy())
    r1 = solar.forecast_eval(pv, hist)
    pv2 = pv.copy()
    pv2.loc[pv2.index >= "2026-10-20", "pv_kW"] *= 0.1               # on modifie la fin du test
    r2 = solar.forecast_eval(pv2, hist)
    assert r1["coefficient_autoregressif"] == r2["coefficient_autoregressif"]
