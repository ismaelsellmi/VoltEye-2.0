"""Détection d'anomalies énergétiques et maintenance prédictive.

Anomalies (non supervisé, les étiquettes ne servent qu'à l'évaluation) :
  1. un modèle de « consommation attendue » par machine (gradient boosting sur
     calendrier + température) ;
  2. des indicateurs journaliers sur les résidus (excès en production, hors
     production, pic horaire) ;
  3. un score robuste (écart à la médiane en unités de MAD) qui note chaque journée.
Comparés : une Isolation Forest sur les mêmes indicateurs, et une baseline
z-score de l'énergie journalière par jour de la semaine.

Maintenance prédictive : suivi du THD (signature harmonique) de chaque moteur,
score de santé et estimation du nombre de jours avant le seuil critique.
"""
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest
from sklearn.metrics import f1_score, precision_score, recall_score

from . import config as C
from .history import ANOMALY_TYPES
from .signals import CLASSES

DETECTED = {"veille", "fuite_air", "pic", "eclairage_weekend", "panne"}
RECOMMANDATIONS = {
    "hors_production": "Couper la machine hors production (programmation horaire ou arrêt automatique).",
    "production": "Vérifier les réglages et l'état de la machine : surconsommation pendant la production.",
    "pic": "Contrôler la régulation (thermostat, variateur) : pic horaire anormal.",
    "sous_consommation": "Arrêt ou sous-consommation inattendue : vérifier une éventuelle panne.",
}
CONTAMINATION = 0.03          # Isolation Forest (approche comparée)
Z_THRESHOLD = 6.0             # seuil du score robuste VoltEye
FEATS = ["exces_production", "exces_hors_production", "pic_residu", "creux_residu"]


def _calendar_features(hist):
    x = pd.DataFrame(index=hist.index)
    x["heure"] = hist.index.hour
    x["jour_semaine"] = hist.index.dayofweek
    x["production"] = hist["production"].astype(int)
    x["ferie"] = hist["ferie"].astype(int)
    x["ramadan"] = hist["ramadan"].astype(int)
    x["temperature"] = hist["temperature"]
    return x


def _hour_price(idx):
    return np.array([C.tariff(h, m) for h, m in zip(idx.hour, idx.month)])


def daily_features(hist, m, x, price):
    y = hist[f"E_{m}"]
    model = HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, random_state=C.SEED)
    model.fit(x, y)
    expected = pd.Series(model.predict(x).clip(0), index=y.index)
    res = y - expected
    prod = hist["production"].astype(bool)
    d = pd.DataFrame({
        "energie_kWh": y.resample("D").sum(),
        "attendu_kWh": expected.resample("D").sum(),
        "exces_production": res.where(prod, 0).resample("D").sum(),
        "exces_hors_production": res.where(~prod, 0).resample("D").sum(),
        "pic_residu": res.resample("D").max(),
        "creux_residu": res.resample("D").min(),
        "cout_exces_TND": (res.clip(lower=0) * price).resample("D").sum(),
    })
    lab = hist[f"anomalie_{m}"].resample("D").agg(lambda s: next((v for v in s if v), ""))
    d["verite"] = lab
    return d


def explain(row):
    cand = {"hors_production": row["exces_hors_production"], "production": row["exces_production"],
            "pic": row["pic_residu"], "sous_consommation": -row["creux_residu"]}
    return max(cand, key=cand.get)


def run(hist, out_dir=C.ARTIFACTS, log=print):
    log("Anomalies : modèles de consommation attendue + score robuste par machine…")
    x = _calendar_features(hist)
    price = _hour_price(hist.index)
    frames, per_machine = [], {}
    for m in CLASSES:
        d = daily_features(hist, m, x, price)
        feats = d[FEATS]
        iso = IsolationForest(n_estimators=300, contamination=CONTAMINATION, random_state=C.SEED).fit(feats)
        d["alerte_iforest"] = iso.predict(feats) == -1
        # score VoltEye : écart robuste (médiane / MAD) de chaque indicateur de résidu
        # plancher d'échelle : évite les fausses alertes sur les machines dont les résidus
        # sont presque nuls une partie de l'année (CVC). 2 % de l'énergie journalière pour
        # les cumuls, 5 % d'une heure de production moyenne pour les indicateurs horaires.
        daily = d["energie_kWh"].mean()
        floor = pd.Series([0.02 * daily, 0.02 * daily, 0.05 * daily / 16, 0.05 * daily / 16], index=FEATS)
        scale = 1.4826 * (feats - feats.median()).abs().median() + floor + 1e-6
        z = (feats - feats.median()) / scale
        z["creux_residu"] = -z["creux_residu"]                 # un creux est anormal vers le bas
        d["score"] = z.max(axis=1)
        d["alerte"] = d["score"] > Z_THRESHOLD
        # baseline : z-score de l'énergie journalière par jour de la semaine
        g = d.groupby(d.index.dayofweek)["energie_kWh"]
        z = (d["energie_kWh"] - g.transform("mean")) / (g.transform("std") + 1e-9)
        d["alerte_baseline"] = z.abs() > 2.5
        d["cause"] = d.apply(explain, axis=1)
        d["machine"] = m
        frames.append(d)
    days = pd.concat(frames)
    truth = days["verite"].isin(DETECTED)
    evald = days[days["verite"] != "degradation"]           # la dégradation est traitée par la maintenance
    t_eval = evald["verite"].isin(DETECTED)

    def scores(pred):
        return {"precision": float(precision_score(t_eval, pred)), "rappel": float(recall_score(t_eval, pred)),
                "f1": float(f1_score(t_eval, pred))}

    results = {"VoltEye - résidus + score robuste (MAD)": scores(evald["alerte"]),
               "Variante - résidus + Isolation Forest": scores(evald["alerte_iforest"]),
               "Baseline - z-score énergie journalière": scores(evald["alerte_baseline"])}
    by_type = {}
    for a in sorted(DETECTED):
        sel = evald["verite"] == a
        if sel.any():
            by_type[a] = {"jours": int(sel.sum()), "rappel_volteye": float(evald.loc[sel, "alerte"].mean()),
                          "rappel_iforest": float(evald.loc[sel, "alerte_iforest"].mean()),
                          "rappel_baseline": float(evald.loc[sel, "alerte_baseline"].mean())}
    for k, v in results.items():
        log(f"  {k}: précision={v['precision']:.2f} rappel={v['rappel']:.2f} F1={v['f1']:.2f}")

    detected = days[days["alerte"] & truth]
    excess_kwh = float(detected[["exces_production", "exces_hors_production"]].clip(lower=0).sum().sum())
    impact = {"kWh_gaspilles_detectes": excess_kwh, "TND": float(detected["cout_exces_TND"].sum()),
              "kg_CO2": excess_kwh * C.EMISSION_FACTOR}

    health, maint = maintenance(hist)
    days.to_parquet(out_dir / "anomalies_daily.parquet")
    health.to_parquet(out_dir / "health_daily.parquet")
    (out_dir / "anomaly_metrics.json").write_text(json.dumps(
        {"models": results, "rappel_par_type": by_type, "impact_anomalies_detectees": impact,
         "maintenance": maint, "types": ANOMALY_TYPES, "recommandations": RECOMMANDATIONS},
        indent=2, ensure_ascii=False), encoding="utf-8")
    return days, results


def maintenance(hist, rise_alert=0.25, rise_critical=1.0):
    """Score de santé à partir de la dérive du THD par rapport à la référence de la machine."""
    rows = []
    out = {}
    for m in CLASSES:
        thd = hist[f"THD_{m}"].resample("D").mean()
        ref = thd.iloc[:60].median()
        rel = thd.rolling(7, min_periods=3).mean() / ref - 1
        slope = rel.rolling(21, min_periods=10).apply(lambda s: np.polyfit(np.arange(len(s)), s, 1)[0], raw=True)
        days_left = ((rise_critical - rel) / slope).where(slope > 1e-4).clip(0, 365)
        score = (100 * (1 - rel.clip(lower=0) / rise_critical)).clip(0, 100)
        alert = rel > rise_alert
        rows.append(pd.DataFrame({"machine": m, "thd": thd, "derive": rel, "sante": score,
                                  "jours_avant_seuil": days_left, "alerte": alert}))
        first = alert[alert].index.min() if alert.any() else None
        out[m] = {"premiere_alerte": str(first.date()) if first is not None else None,
                  "jours_en_alerte": int(alert.sum())}
    failure = hist.index[hist["anomalie_convoyeur"] == "panne"].min()
    first = out["convoyeur"]["premiere_alerte"]
    out["anticipation_panne_convoyeur_jours"] = (failure.normalize() - pd.Timestamp(first)).days if first else None
    out["fausses_alertes_autres_machines_jours"] = sum(out[m]["jours_en_alerte"] for m in CLASSES if m != "convoyeur")
    return pd.concat(rows), out
