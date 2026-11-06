"""Prévision de la consommation horaire du site à J+1 (24 heures à l'avance).

Modèle : gradient boosting (HistGradientBoostingRegressor) sur le calendrier
(heure, jour, poste, jour férié, Ramadan), la température prévue et des
retards d'au moins 24 h (seules informations disponibles la veille).
Comparé à deux baselines de persistance : « même heure la veille » et « même
heure la semaine précédente ». Test : les 60 derniers jours, jamais vus à
l'entraînement.
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from . import config as C

FEATURES = ["heure", "jour_semaine", "mois", "production", "ferie", "ramadan", "temperature",
            "lag_24h", "lag_168h", "moyenne_veille", "max_veille"]


def make_features(df, rng=None):
    rng = rng or np.random.default_rng(C.SEED + 3)
    y = df["E_total"]
    x = pd.DataFrame(index=df.index)
    x["heure"] = df.index.hour
    x["jour_semaine"] = df.index.dayofweek
    x["mois"] = df.index.month
    x["production"] = df["production"].astype(int)       # planning de production connu à l'avance
    x["ferie"] = df["ferie"].astype(int)
    x["ramadan"] = df["ramadan"].astype(int)
    x["temperature"] = df["temperature"] + rng.normal(0, 1.0, len(df))   # prévision météo imparfaite
    x["lag_24h"] = y.shift(24)
    x["lag_168h"] = y.shift(168)
    daily = y.resample("D").agg(["mean", "max"]).shift(1)
    x["moyenne_veille"] = daily["mean"].reindex(df.index, method="ffill")
    x["max_veille"] = daily["max"].reindex(df.index, method="ffill")
    return x, y


def _metrics(y, p):
    mask = y > 5
    return {"MAE_kWh": float(mean_absolute_error(y, p)), "RMSE_kWh": float(np.sqrt(mean_squared_error(y, p))),
            "MAPE_%_heures_actives": float(100 * np.mean(np.abs((y[mask] - p[mask]) / y[mask])))}


def run(hist, out_dir=C.ARTIFACTS, log=print):
    log("Prévision : entraînement du modèle J+1…")
    x, y = make_features(hist)
    ok = x.notna().all(axis=1)
    x, y = x[ok], y[ok]
    split = y.index.max() - pd.Timedelta(days=60)
    tr, te = y.index <= split, y.index > split
    model = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, random_state=C.SEED)
    model.fit(x[tr], y[tr])
    pred = pd.Series(model.predict(x[te]).clip(0), index=y[te].index)
    results = {
        "VoltEye - gradient boosting": _metrics(y[te], pred),
        "Baseline - même heure la veille": _metrics(y[te], x.loc[te, "lag_24h"]),
        "Baseline - même heure semaine précédente": _metrics(y[te], x.loc[te, "lag_168h"]),
    }
    for k, v in results.items():
        log(f"  {k}: MAE={v['MAE_kWh']:.2f} kWh  MAPE={v['MAPE_%_heures_actives']:.1f} %")
    out = pd.DataFrame({"reel": y[te], "prevision": pred, "baseline_veille": x.loc[te, "lag_24h"],
                        "baseline_semaine": x.loc[te, "lag_168h"]})
    out.to_parquet(out_dir / "forecast_test.parquet")
    joblib.dump(model, out_dir / "forecast_model.joblib")
    (out_dir / "forecast_metrics.json").write_text(json.dumps(
        {"periode_test": [str(y[te].index.min()), str(y[te].index.max())], "models": results},
        indent=2, ensure_ascii=False), encoding="utf-8")
    return out, results
