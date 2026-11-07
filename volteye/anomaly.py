"""Détection d'anomalies énergétiques et maintenance prédictive.

Anomalies (non supervisé, les étiquettes ne servent qu'à l'évaluation) :
  1. un modèle de « consommation attendue » par machine (gradient boosting sur
     calendrier + température), réentraîné chaque mois sur le seul passé
     (backtest glissant : chaque journée est prédite par un modèle qui ne l'a jamais vue) ;
  2. des indicateurs journaliers sur les résidus (excès en production, hors
     production, pic horaire) ;
  3. un score robuste (écart à la médiane en unités de MAD), normalisé sur les
     60 jours précédents uniquement.
Comparés : une Isolation Forest sur les mêmes indicateurs, et une baseline
z-score de l'énergie journalière par jour de la semaine.

Protocole d'évaluation temporel : rodage (nov.-janv.), réglage des seuils de
chaque méthode sur la validation (fév.-juin), score publié sur le test
(juil.-oct.), période jamais utilisée pour régler quoi que ce soit.

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
FEATS = ["exces_production", "exces_hors_production", "pic_residu", "creux_residu"]
FIRST_FORECAST = "2026-01-01"                 # premier mois prédit hors échantillon (rodage : nov.-déc.)
VALIDATION = ("2026-02-01", "2026-07-01")     # réglage des seuils
TEST = ("2026-07-01", "2026-11-01")           # évaluation finale
SCALE_WINDOW, SCALE_MIN = 60, 28              # normalisation robuste sur le passé récent (jours)
GRIDS = {"alerte": np.arange(2.0, 12.01, 0.25),
         "alerte_iforest": np.arange(0.40, 0.80, 0.01),
         "alerte_baseline": np.arange(1.0, 5.01, 0.25)}


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


def expected_walk_forward(y, x, first=FIRST_FORECAST):
    """Consommation attendue hors échantillon : chaque mois est prédit par un modèle entraîné sur les mois précédents."""
    expected = pd.Series(np.nan, index=y.index)
    for start in pd.date_range(first, y.index.max(), freq="MS"):
        past, month = y.index < start, (y.index >= start) & (y.index < start + pd.offsets.MonthBegin(1))
        model = HistGradientBoostingRegressor(max_iter=300, random_state=C.SEED)
        model.fit(x[past], y[past])
        expected[month] = model.predict(x[month]).clip(0)
    return expected


def causal_robust_z(feats, daily_energy):
    """Écart à la médiane en unités de MAD, calculé sur les SCALE_WINDOW jours précédents uniquement.
    Plancher d'échelle : 2 % de l'énergie journalière pour les cumuls, 5 % d'une heure de production
    pour les indicateurs horaires (évite les fausses alertes quand les résidus sont presque nuls)."""
    past = feats.shift(1).rolling(SCALE_WINDOW, min_periods=SCALE_MIN)
    med = past.median()
    mad = feats.shift(1).rolling(SCALE_WINDOW, min_periods=SCALE_MIN).apply(
        lambda w: np.nanmedian(np.abs(w - np.nanmedian(w))), raw=True)
    daily = daily_energy.shift(1).rolling(SCALE_WINDOW, min_periods=SCALE_MIN).mean()
    floor = pd.concat([0.02 * daily, 0.02 * daily, 0.05 * daily / 16, 0.05 * daily / 16], axis=1)
    floor.columns = FEATS
    z = (feats - med) / (1.4826 * mad + floor + 1e-6)
    z["creux_residu"] = -z["creux_residu"]                 # un creux est anormal vers le bas
    return z


def daily_features(hist, m, x, price):
    y = hist[f"E_{m}"]
    expected = expected_walk_forward(y, x)
    res = y - expected
    prod = hist["production"].astype(bool)
    d = pd.DataFrame({
        "energie_kWh": y.resample("D").sum(),
        "attendu_kWh": expected.resample("D").sum(min_count=1),
        "exces_production": res.where(prod, 0).resample("D").sum(min_count=1),
        "exces_hors_production": res.where(~prod, 0).resample("D").sum(min_count=1),
        "pic_residu": res.resample("D").max(),
        "creux_residu": res.resample("D").min(),
        "cout_exces_TND": (res.clip(lower=0) * price).resample("D").sum(min_count=1),
    })
    lab = hist[f"anomalie_{m}"].resample("D").agg(lambda s: next((v for v in s if v), ""))
    d["verite"] = lab
    return d


def explain(row):
    cand = {"hors_production": row["exces_hors_production"], "production": row["exces_production"],
            "pic": row["pic_residu"], "sous_consommation": -row["creux_residu"]}
    return max(cand, key=cand.get)


METHODS = {  # colonne d'alerte -> (nom publié, colonne de score)
    "alerte": ("VoltEye - résidus + score robuste (MAD)", "score"),
    "alerte_iforest": ("Variante - résidus + Isolation Forest", "score_iforest"),
    "alerte_baseline": ("Baseline - z-score énergie journalière", "score_baseline"),
}


def _in(index, bounds):
    return (index >= bounds[0]) & (index < bounds[1])


def _prf(truth, pred):
    return {"precision": float(precision_score(truth, pred, zero_division=0)),
            "rappel": float(recall_score(truth, pred, zero_division=0)),
            "f1": float(f1_score(truth, pred, zero_division=0))}


def choose_threshold(score, truth, grid):
    """Seuil qui maximise le F1 de validation ; à égalité, le plus élevé (moins de fausses alertes)."""
    best_t, best_f1 = float(grid[-1]), -1.0
    for t in grid:
        f1 = f1_score(truth, score > t, zero_division=0)
        if f1 >= best_f1:
            best_t, best_f1 = float(t), f1
    return best_t


def score_machine(hist, m, x, price):
    """Journées d'une machine avec les scores des trois méthodes (NaN pendant le rodage)."""
    d = daily_features(hist, m, x, price)
    feats = d[FEATS]
    ok = feats.notna().all(axis=1)
    d["score"] = causal_robust_z(feats, d["energie_kWh"]).max(axis=1)
    # Isolation Forest : ajustée sans étiquettes sur les journées antérieures au test
    iso = IsolationForest(n_estimators=300, random_state=C.SEED).fit(feats[ok & (d.index < TEST[0])])
    d["score_iforest"] = np.nan
    d.loc[ok, "score_iforest"] = -iso.score_samples(feats[ok])
    # baseline : z-score de l'énergie journalière par jour de la semaine, statistiques du passé uniquement
    e = d["energie_kWh"]
    by_dow = e.groupby(d.index.dayofweek)
    mu = by_dow.transform(lambda s: s.shift(1).expanding(4).mean())
    sd = by_dow.transform(lambda s: s.shift(1).expanding(4).std())
    d["score_baseline"] = ((e - mu) / (sd + 1e-9)).abs()
    d["cause"] = ""
    d.loc[ok, "cause"] = d.loc[ok].apply(explain, axis=1)
    d["machine"] = m
    return d


def run(hist, out_dir=C.ARTIFACTS, log=print):
    log("Anomalies : backtest glissant mensuel, seuils réglés sur la validation (fév.-juin), test juil.-oct.…")
    x = _calendar_features(hist)
    price = _hour_price(hist.index)
    days = pd.concat([score_machine(hist, m, x, price) for m in CLASSES])
    scored = days["score"].notna()
    labelled = days["verite"] != "degradation"           # la dégradation relève de la maintenance prédictive
    truth = days["verite"].isin(DETECTED)
    val = scored & labelled & _in(days.index, VALIDATION)
    test = scored & labelled & _in(days.index, TEST)
    days["periode"] = np.select([_in(days.index, VALIDATION), _in(days.index, TEST)], ["validation", "test"], "rodage")

    results, validation, thresholds = {}, {}, {}
    for col, (name, src) in METHODS.items():
        thresholds[name] = choose_threshold(days.loc[val, src], truth[val], GRIDS[col])
        days[col] = scored & (days[src] > thresholds[name])
        validation[name] = _prf(truth[val], days.loc[val, col])
        results[name] = _prf(truth[test], days.loc[test, col])
        log(f"  {name}: seuil {thresholds[name]:.2f} | test : précision={results[name]['precision']:.2f} "
            f"rappel={results[name]['rappel']:.2f} F1={results[name]['f1']:.2f}")

    by_type = {}
    for a in sorted(DETECTED):
        sel = scored & labelled & (days["verite"] == a)
        if sel.any():
            by_type[a] = {"jours": int(sel.sum()), **{f"rappel_{k}": float(days.loc[sel, col].mean()) for k, col in
                                                       [("volteye", "alerte"), ("iforest", "alerte_iforest"),
                                                        ("baseline", "alerte_baseline")]}}

    detected = days[days["alerte"] & truth]
    excess_kwh = float(detected[["exces_production", "exces_hors_production"]].clip(lower=0).sum().sum())
    impact = {"kWh_gaspilles_detectes": excess_kwh, "TND": float(detected["cout_exces_TND"].sum()),
              "kg_CO2": excess_kwh * C.EMISSION_FACTOR, "periode": "journées notées, fév.-oct. 2026"}
    protocol = {"rodage": ["2025-11-01", VALIDATION[0]], "validation": list(VALIDATION), "test": list(TEST),
                "reentrainement": "mensuel, sur le passé uniquement",
                "normalisation": f"médiane et MAD des {SCALE_WINDOW} jours précédents",
                "jours_test": int(test.sum()), "jours_anormaux_test": int(truth[test].sum()),
                "jours_validation": int(val.sum()), "jours_anormaux_validation": int(truth[val].sum())}

    health, maint = maintenance(hist)
    days.to_parquet(out_dir / "anomalies_daily.parquet")
    health.to_parquet(out_dir / "health_daily.parquet")
    (out_dir / "anomaly_metrics.json").write_text(json.dumps(
        {"models": results, "validation": validation, "seuils": thresholds, "protocole": protocol,
         "rappel_par_type": by_type, "impact_anomalies_detectees": impact,
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
