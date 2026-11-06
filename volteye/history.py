"""Historique horaire d'un an pour un site industriel tunisien (données simulées).

Ce sont les sorties agrégées de la désagrégation (énergie horaire et THD par
machine), qui alimentent la prévision, la détection d'anomalies et la
maintenance prédictive. Le simulateur tient compte des postes de travail, des
week-ends, des jours fériés, du Ramadan et de la température de Tunis, et
injecte des anomalies étiquetées (vérité terrain pour l'évaluation).
"""
import numpy as np
import pandas as pd

from . import config as C
from .signals import CLASSES, MACHINE_TYPES

START, END = "2025-11-01", "2026-11-01"

# Jours fériés tunisiens (les fêtes religieuses sont des dates approximatives : HYPOTHÈSE)
HOLIDAYS = {"2025-12-17", "2026-01-01", "2026-01-14", "2026-03-20", "2026-03-21", "2026-04-09",
            "2026-05-01", "2026-05-27", "2026-05-28", "2026-06-16", "2026-07-25", "2026-08-13",
            "2026-08-25", "2026-10-15"}
RAMADAN = ("2026-02-18", "2026-03-19")

# Puissance nominale (kW) des machines du site de référence
P_NOM = {"four": 32, "compresseur": 22, "cnc": 18, "convoyeur": 7, "eclairage": 5, "soudage": 12, "cvc": 16}
THD_NOMINAL = {m: float(np.sqrt(sum(r ** 2 for r, _ in MACHINE_TYPES[m].harmonics.values()))) for m in CLASSES}

ANOMALY_TYPES = {
    "veille": "Veille excessive (machine laissée sous tension hors production)",
    "fuite_air": "Fuite d'air comprimé (compresseur en surcharge)",
    "degradation": "Dégradation progressive (THD et consommation en hausse)",
    "panne": "Arrêt sur panne",
    "pic": "Pic de consommation anormal",
    "eclairage_weekend": "Éclairage resté allumé le week-end",
}


def temperature(idx, rng):
    doy = idx.dayofyear.to_numpy()
    hour = idx.hour.to_numpy()
    seasonal = 19 + 8 * np.cos(2 * np.pi * (doy - 215) / 365)
    daily = 5 * np.cos(2 * np.pi * (hour - 15) / 24)
    noise = np.zeros(len(idx))
    for t in range(1, len(idx)):
        noise[t] = 0.97 * noise[t - 1] + rng.normal(0, 0.4)
    return seasonal + daily + noise


def calendar(idx):
    day = idx.strftime("%Y-%m-%d")
    holiday = np.isin(day, list(HOLIDAYS))
    ramadan = (idx >= RAMADAN[0]) & (idx < pd.Timestamp(RAMADAN[1]) + pd.Timedelta(days=1))
    dow, hour = idx.dayofweek.to_numpy(), idx.hour.to_numpy()
    prod = np.where(dow < 5, (hour >= 6) & (hour < 22), (dow == 5) & (hour >= 6) & (hour < 14))
    prod = np.where(ramadan, prod & (hour < 16), prod)
    prod = prod & ~holiday
    return pd.DataFrame({"production": prod, "ferie": holiday, "ramadan": ramadan}, index=idx)


def simulate(rng=None):
    rng = rng or np.random.default_rng(C.SEED + 2)
    idx = pd.date_range(START, END, freq="h", inclusive="left")
    n = len(idx)
    cal = calendar(idx)
    temp = temperature(idx, rng)
    prod = cal["production"].to_numpy().astype(float)
    hour = idx.hour.to_numpy()
    noise = lambda s=0.06: rng.normal(1, s, n).clip(0.7, 1.3)

    e = {
        "four": P_NOM["four"] * 0.70 * prod * noise(),
        "compresseur": P_NOM["compresseur"] * (0.60 * prod + 0.06 * (1 - prod)) * (1 + 0.004 * (temp - 19)) * noise(),
        "cnc": P_NOM["cnc"] * rng.uniform(0.55, 0.85, n) * prod,
        "convoyeur": P_NOM["convoyeur"] * 0.80 * prod * noise(0.03),
        "eclairage": P_NOM["eclairage"] * (prod + 0.2 * (1 - prod) * ((hour >= 19) | (hour < 6))) * noise(0.02),
        "soudage": P_NOM["soudage"] * 0.40 * prod * noise(0.15),
        "cvc": (np.maximum(temp - 22, 0) * 1.6 + np.maximum(14 - temp, 0) * 0.8) * (prod + 0.1 * (1 - prod)) * noise(),
    }
    e = {m: np.clip(v, 0, None) for m, v in e.items()}
    thd = {m: THD_NOMINAL[m] * rng.normal(1, 0.04, n) for m in CLASSES}
    labels = {m: np.array([""] * n, dtype=object) for m in CLASSES}

    def period(start, days):
        a = idx.get_indexer([pd.Timestamp(start)])[0]
        return slice(a, min(a + 24 * days, n))

    # 1) veille excessive de la CNC (laissée sous tension la nuit)
    for start, days in [("2026-01-12", 6), ("2026-06-08", 5), ("2026-09-21", 7)]:
        s = period(start, days)
        off = prod[s] == 0
        e["cnc"][s] = np.where(off, P_NOM["cnc"] * 0.25 * rng.normal(1, 0.05, off.size), e["cnc"][s])
        labels["cnc"][s] = "veille"
    # 2) fuite d'air comprimé : le compresseur tourne plus, surtout hors production
    for start, days in [("2026-02-02", 18), ("2026-08-03", 15)]:
        s = period(start, days)
        ramp = np.linspace(0.3, 1.0, s.stop - s.start)
        e["compresseur"][s] += P_NOM["compresseur"] * ramp * (0.22 * (1 - prod[s]) + 0.12 * prod[s])
        labels["compresseur"][s] = "fuite_air"
    # 3) dégradation progressive du moteur de convoyeur puis panne
    s = period("2026-04-06", 42)
    k = np.linspace(0, 1, s.stop - s.start)
    thd["convoyeur"][s] *= 1 + 1.6 * k ** 1.5
    e["convoyeur"][s] *= 1 + 0.15 * k ** 1.5
    labels["convoyeur"][s] = "degradation"
    s = period("2026-05-18", 2)
    e["convoyeur"][s] = 0
    labels["convoyeur"][s] = "panne"
    # 4) pics anormaux du four (régulation thermique défaillante)
    prod_hours = np.flatnonzero(prod > 0)
    for t in rng.choice(prod_hours, 10, replace=False):
        e["four"][t:t + 3] *= 1.6
        labels["four"][t:t + 3] = "pic"
    # 5) éclairage resté allumé tout le week-end
    for start in ["2026-03-07", "2026-10-03"]:
        s = period(start, 2)
        e["eclairage"][s] = P_NOM["eclairage"] * rng.normal(1, 0.02, s.stop - s.start)
        labels["eclairage"][s] = "eclairage_weekend"

    df = pd.DataFrame(index=idx)
    df.index.name = "time"
    df["temperature"] = temp
    df = df.join(cal)
    for m in CLASSES:
        df[f"E_{m}"] = e[m]
        df[f"THD_{m}"] = thd[m]
        df[f"anomalie_{m}"] = labels[m]
    df["E_total"] = sum(e[m] for m in CLASSES)
    return df
