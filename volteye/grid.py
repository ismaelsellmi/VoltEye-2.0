"""VoltEye Grid : la flexibilité industrielle agrégée au service de la pointe d'été du réseau.

Chaque usine équipée de VoltEye connaît ses charges décalables (cuissons, air comprimé, recharges…).
VoltEye Grid agrège ces flexibilités sur 10 zones industrielles tunisiennes, prévoit la demande de chaque
zone pour le lendemain, puis répartit les démarrages pour abaisser la pointe agrégée vue par le réseau.

Modèle :
  - chaque zone regroupe n usines du profil de référence, pondéré selon son secteur ; une part des usines
    (PARTICIPATION) inscrit ses charges flexibles au programme ;
  - prévision J+1 de chaque zone (même modèle que pour une usine, entraîné sur l'historique de la zone
    jusqu'au 30 juin, jamais sur les jours évalués) ;
  - programme linéaire (HiGHS) : pour chaque zone et chaque type de tâche, part des usines qui démarre à
    chaque heure de la fenêtre autorisée. À l'échelle d'une population d'usines, ces parts sont continues.
    Objectif : pointe agrégée minimale, puis coût tarifaire minimal.
Trois stratégies sont rejouées sur la demande réelle des 10 jours ouvrés les plus chargés de l'été :
pratique actuelle (démarrage en début de poste), réponse au tarif seul (chaque usine choisit l'heure la
moins chère, sans coordination) et VoltEye Grid.
"""
import json

import numpy as np
import pandas as pd
import pulp

from . import config as C
from . import forecasting, history
from .anomaly import maintenance
from .optimization import TASKS, tariff_aware_starts
from .signals import CLASSES

# nom, lat, lon, secteur, nombre d'usines équipées (HYPOTHÈSE de déploiement)
ZONES = [
    ("ZI Ben Arous", 36.745, 10.235, "Mécanique", 120),
    ("ZI Mghira", 36.683, 10.152, "Plasturgie", 90),
    ("ZI Charguia", 36.842, 10.203, "Agroalimentaire", 80),
    ("ZI Bizerte - Menzel Bourguiba", 37.155, 9.788, "Métallurgie", 60),
    ("ZI Sousse - Sidi Abdelhamid", 35.792, 10.636, "Textile", 110),
    ("ZI Monastir", 35.765, 10.808, "Textile", 100),
    ("ZI Sfax - Poudrière", 34.760, 10.745, "Agroalimentaire", 90),
    ("ZI Gabès", 33.905, 10.103, "Chimie", 40),
    ("ZI Nabeul - Grombalia", 36.598, 10.497, "Agroalimentaire", 70),
    ("ZI Béja", 36.735, 9.200, "Mécanique", 50),
]
# poids des machines par secteur (HYPOTHÈSE : profils typiques de consommation)
SECTOR_MIX = {
    "Mécanique": {"cnc": 1.8, "soudage": 1.5, "compresseur": 1.2},
    "Plasturgie": {"four": 1.5, "compresseur": 1.3, "cvc": 1.1},
    "Agroalimentaire": {"cvc": 2.5, "four": 1.4, "compresseur": 1.1},
    "Métallurgie": {"four": 2.0, "soudage": 1.6, "convoyeur": 1.3},
    "Textile": {"convoyeur": 1.6, "cnc": 1.3, "cvc": 1.3},
    "Chimie": {"compresseur": 2.0, "four": 1.5, "cvc": 1.2},
}
PARTICIPATION = 0.3          # part des usines inscrites au programme d'effacement (HYPOTHÈSE)
FORECAST_FROM = "2026-07-01"
N_DAYS = 10


def zone_history(k, sector):
    """Historique horaire d'une usine type de la zone (kW), pondéré par le secteur."""
    h = history.simulate(np.random.default_rng(C.SEED + 100 + k))
    for m, w in SECTOR_MIX[sector].items():
        h[f"E_{m}"] *= w
    h["E_total"] = sum(h[f"E_{m}"] for m in CLASSES)
    return h


def zone_forecast(h):
    """Prévision J+1 (kW par usine) des mois d'été, par un modèle entraîné sur le passé de la zone."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    x, y = forecasting.make_features(h)
    ok = x.notna().all(axis=1)
    tr, te = ok & (x.index < FORECAST_FROM), ok & (x.index >= FORECAST_FROM)
    model = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, random_state=C.SEED)
    model.fit(x[tr], y[tr])
    return pd.Series(model.predict(x[te]).clip(0), index=x.index[te])


def _windows():
    return [range(t["fenetre"][0], min(t["fenetre"][1], 24 - t["duree"] + 1)) for t in TASKS]


def flex_profile(shares, kw):
    """Profil (24 h) d'une zone : shares[k][s] = part des usines qui lancent la tâche k à l'heure s."""
    prof = np.zeros(24)
    for k, t in enumerate(TASKS):
        for s, f in shares[k].items():
            prof[s:s + t["duree"]] += f * kw * t["kW"]
    return prof


def fixed_shares(starts):
    return [{s: 1.0} for s in starts]


def plan_grid(bases, kws, prices):
    """Programme linéaire : répartition des démarrages de chaque zone minimisant la pointe agrégée (kW)."""
    prob = pulp.LpProblem("volteye_grid", pulp.LpMinimize)
    win = _windows()
    x = {(z, k, s): prob.add_variable(f"x_{z}_{k}_{s}", lowBound=0, upBound=1)
         for z in range(len(bases)) for k in range(len(TASKS)) for s in win[k]}
    peak = prob.add_variable("pointe", lowBound=0)
    total = {h: float(sum(b[h] for b in bases)) + pulp.lpSum(
        kws[z] * TASKS[k]["kW"] * v for (z, k, s), v in x.items() if s <= h < s + TASKS[k]["duree"])
        for h in range(24)}
    cost = pulp.lpSum(prices[h] * total[h] for h in range(24))
    prob += peak + 1e-4 * cost
    for z in range(len(bases)):
        for k in range(len(TASKS)):
            prob += pulp.lpSum(x[z, k, s] for s in win[k]) == 1
    for h in range(24):
        prob += total[h] <= peak
    prob.solve(pulp.HiGHS(msg=False))
    shares = [[{s: x[z, k, s].value() for s in win[k] if x[z, k, s].value() > 1e-6}
               for k in range(len(TASKS))] for z in range(len(bases))]
    return shares, pulp.LpStatus[prob.status]


def run(out_dir=C.ARTIFACTS, opt_summary=None, anomaly_metrics=None, log=print):
    log("VoltEye Grid : 10 zones industrielles, prévision J+1 et répartition de l'effacement…")
    flex_kwh = sum(t["kW"] * t["duree"] for t in TASKS)
    zones, actual, fcst = [], [], []
    for k, (name, lat, lon, sector, n) in enumerate(ZONES):
        h = zone_history(k, sector)
        zones.append({"site": name, "lat": lat, "lon": lon, "secteur": sector, "usines": n, "hist": h})
        actual.append(h["E_total"] * n)
        fcst.append(zone_forecast(h) * n)
    actual, fcst = pd.concat(actual, axis=1), pd.concat(fcst, axis=1)
    agg = actual.sum(axis=1)
    summer = agg[(agg.index >= FORECAST_FROM) & (agg.index < "2026-09-01")]
    workdays = summer[summer.index.dayofweek < 5].groupby(summer[summer.index.dayofweek < 5].index.date).max()
    days = sorted(workdays.nlargest(N_DAYS).index)

    kws = [PARTICIPATION * z["usines"] for z in zones]
    res_days = []
    for day in days:
        sl = slice(pd.Timestamp(day), pd.Timestamp(day) + pd.Timedelta(hours=23))
        prices = np.array([C.tariff(hh, pd.Timestamp(day).month) for hh in range(24)])
        b_fc = [np.clip(fcst.loc[sl].iloc[:, z].to_numpy() - kws[z] * flex_kwh / 24, 0, None) for z in range(len(zones))]
        b_re = [np.clip(actual.loc[sl].iloc[:, z].to_numpy() - kws[z] * flex_kwh / 24, 0, None) for z in range(len(zones))]
        strategies = {
            "pratique_actuelle": [fixed_shares([max(t["fenetre"][0], 7) for t in TASKS])] * len(zones),
            "tarif_seul": [fixed_shares(tariff_aware_starts(prices))] * len(zones),
        }
        strategies["voltEye_grid"], status = plan_grid(b_fc, kws, prices)
        row = {"jour": str(day), "statut": status}
        for name, shares in strategies.items():
            load = sum(b_re[z] + flex_profile(shares[z], kws[z]) for z in range(len(zones)))
            row[name] = {"profil_MW": (load / 1000).round(3).tolist(), "pointe_MW": float(load.max() / 1000),
                         "heure_pointe": int(load.argmax()), "cout_kTND": float(load @ prices / 1000)}
        row["base_MW"] = (sum(b_re) / 1000).round(3).tolist()
        res_days.append(row)

    def mean(key, strat):
        return float(np.mean([d[strat][key] for d in res_days]))

    peak_ref, peak_tar, peak_grid = (mean("pointe_MW", s) for s in ["pratique_actuelle", "tarif_seul", "voltEye_grid"])
    summary = {
        "zones": len(zones), "usines": int(sum(z["usines"] for z in zones)), "participation": PARTICIPATION,
        "jours_evalues": len(res_days), "flexibilite_MW": float(sum(kws) * sum(t["kW"] for t in TASKS) / 1000),
        "pointe_moyenne_MW": {"pratique_actuelle": peak_ref, "tarif_seul": peak_tar, "voltEye_grid": peak_grid},
        "effacement_MW_vs_pratique": peak_ref - peak_grid, "effacement_%_vs_pratique": 100 * (1 - peak_grid / peak_ref),
        "effacement_MW_vs_tarif_seul": peak_tar - peak_grid, "effacement_%_vs_tarif_seul": 100 * (1 - peak_grid / peak_tar),
        "energie_deplacee_MWh_jour": float(sum(kws) * flex_kwh / 1000),
    }
    log(f"  pointe agrégée moyenne : {peak_ref:.1f} MW (pratique actuelle), {peak_tar:.1f} MW (tarif seul), "
        f"{peak_grid:.1f} MW (VoltEye Grid) → -{summary['effacement_MW_vs_pratique']:.1f} MW "
        f"({summary['effacement_%_vs_pratique']:.1f} %)")

    # vue ville : indicateurs calculés pour chaque zone
    waste_share = 0.0
    if anomaly_metrics:
        ref = history.simulate()
        scored = ref.loc["2026-02-01":]
        waste_share = anomaly_metrics["impact_anomalies_detectees"]["kWh_gaspilles_detectes"] / scored["E_total"].sum()
    gain_site = (opt_summary or {}).get("gain_annuel_estime_TND", 0.0)
    sites = []
    for z, zone in enumerate(zones):
        h, n = zone.pop("hist"), zone["usines"]
        mwh = float(h["E_total"].sum() * n / 1000)
        off = ~h["production"].astype(bool)
        health, _ = maintenance(h)
        last = health[health.index >= health.index.max() - pd.Timedelta(days=6)]
        sites.append({**zone,
                      "consommation_MWh_an": mwh, "pointe_MW": float(actual.iloc[:, z].max() / 1000),
                      "flexibilite_MW": float(kws[z] * sum(t["kW"] for t in TASKS) / 1000),
                      "part_hors_production_%": float(100 * h.loc[off, "E_total"].sum() / h["E_total"].sum()),
                      "gaspillage_detecte_MWh_an": mwh * waste_share,
                      "co2_t_an": mwh * C.EMISSION_FACTOR, "co2_evitable_t_an": mwh * waste_share * C.EMISSION_FACTOR,
                      "gain_planification_TND_an": gain_site * kws[z],
                      "sante_moyenne": float(last["sante"].mean()), "alertes_actives": int(last.groupby("machine")["alerte"].any().sum())})
    (out_dir / "grid.json").write_text(json.dumps({"resume": summary, "jours": res_days,
                                                   "zones": [{k: v for k, v in s.items()} for s in sites]},
                                                  ensure_ascii=False), encoding="utf-8")
    (out_dir / "city_sites.json").write_text(json.dumps(sites, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary
