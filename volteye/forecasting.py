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


FEATURE_LABELS = {
    "heure": "heure de la journée", "jour_semaine": "jour de la semaine", "mois": "mois", "production": "planning de production",
    "ferie": "jour férié", "ramadan": "Ramadan", "temperature": "température prévue", "lag_24h": "consommation de la veille, même heure",
    "lag_168h": "consommation de la semaine passée, même heure", "moyenne_veille": "moyenne de la veille", "max_veille": "pointe de la veille",
}


class ConformalInterval:
    """Fourchette P10-P90 calibrée (régression quantile conformalisée, Romano et al., 2019).

    Deux modèles quantiles (10 % et 90 %) sont entraînés sur le début de l'historique ; sur les 45 derniers
    jours d'apprentissage, jamais vus par ces modèles, on mesure de combien il faut élargir la fourchette pour
    contenir 80 % des heures réelles, séparément pour les heures de production et les autres."""

    def __init__(self, coverage=0.8, calib_days=45):
        self.coverage, self.calib_days = coverage, calib_days

    def fit(self, x, y):
        cut = y.index.max() - pd.Timedelta(days=self.calib_days)
        fit, cal = y.index <= cut, y.index > cut
        self.models = {q: HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=400, learning_rate=0.05,
                                                        max_leaf_nodes=31, random_state=C.SEED).fit(x[fit], y[fit])
                       for q in (0.1, 0.9)}
        lo, hi = self._raw(x[cal])
        score = np.maximum(lo - y[cal].to_numpy(), y[cal].to_numpy() - hi)          # dépassement de la fourchette
        self.margin = {}
        for group in (0, 1):
            s = score[x.loc[cal, "production"].to_numpy() == group]
            level = min(1.0, np.ceil((len(s) + 1) * self.coverage) / len(s))
            self.margin[group] = float(np.quantile(s, level))
        return self

    def _raw(self, x):
        return self.models[0.1].predict(x), self.models[0.9].predict(x)

    def predict(self, x):
        lo, hi = self._raw(x)
        m = np.where(x["production"].to_numpy() == 1, self.margin[1], self.margin[0])
        return np.clip(lo - m, 0, None), np.maximum(hi + m, 0)


def shap_explanations(model, x_test, y_test, log=print):
    """Contribution de chaque variable à chaque prévision (valeurs SHAP, explication additive exacte des arbres)."""
    try:
        import shap
    except ImportError:
        log("  SHAP non installé : explications ignorées")
        return None
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(x_test)
    importance = dict(sorted(((FEATURE_LABELS[c], float(np.abs(sv[:, i]).mean())) for i, c in enumerate(x_test.columns)),
                             key=lambda kv: -kv[1]))
    hours = {}
    for t, row, vals in zip(x_test.index, x_test.itertuples(index=False), sv):
        contrib = sorted(((FEATURE_LABELS[c], float(v)) for c, v in zip(x_test.columns, vals)), key=lambda kv: -abs(kv[1]))
        hours[str(t)] = {"base": float(np.ravel(explainer.expected_value)[0]), "contributions": contrib[:5]}
    log(f"  SHAP : variable la plus influente = {next(iter(importance))}")
    return {"importance_moyenne_kWh": importance, "par_heure": hours}


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
    ci = ConformalInterval().fit(x[tr], y[tr])
    lo, hi = ci.predict(x[te])
    p10, p90 = pd.Series(lo, index=pred.index), pd.Series(hi, index=pred.index)
    inside = (y[te] >= p10) & (y[te] <= p90)
    prod = x.loc[te, "production"] == 1
    coverage = {"couverture_P10_P90": float(inside.mean()), "couverture_heures_production": float(inside[prod].mean()),
                "couverture_hors_production": float(inside[~prod].mean()),
                "largeur_moyenne_kWh": float((p90 - p10).mean()), "cible": 0.8,
                "methode": "régression quantile conformalisée, calibrée sur les 45 derniers jours d'apprentissage"}
    results = {
        "VoltEye - gradient boosting": _metrics(y[te], pred),
        "Baseline - même heure la veille": _metrics(y[te], x.loc[te, "lag_24h"]),
        "Baseline - même heure semaine précédente": _metrics(y[te], x.loc[te, "lag_168h"]),
    }
    for k, v in results.items():
        log(f"  {k}: MAE={v['MAE_kWh']:.2f} kWh  MAPE={v['MAPE_%_heures_actives']:.1f} %")
    log(f"  fourchette P10-P90 : {coverage['couverture_P10_P90'] * 100:.1f} % des heures réelles couvertes (cible 80 %)")
    out = pd.DataFrame({"reel": y[te], "prevision": pred, "p10": p10, "p90": p90, "baseline_veille": x.loc[te, "lag_24h"],
                        "baseline_semaine": x.loc[te, "lag_168h"]})
    out.to_parquet(out_dir / "forecast_test.parquet")
    joblib.dump(model, out_dir / "forecast_model.joblib")
    expl = shap_explanations(model, x[te], y[te], log)
    if expl:
        (out_dir / "forecast_shap.json").write_text(json.dumps(expl, ensure_ascii=False), encoding="utf-8")
    (out_dir / "forecast_metrics.json").write_text(json.dumps(
        {"periode_test": [str(y[te].index.min()), str(y[te].index.max())], "models": results, "quantiles": coverage,
         "importance_shap": expl["importance_moyenne_kWh"] if expl else None},
        indent=2, ensure_ascii=False), encoding="utf-8")
    return out, results
