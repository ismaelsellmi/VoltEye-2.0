"""Solaire en toiture : production photovoltaïque, charge nette et effet sur la pointe d'été.

Modèle physique hors ligne (aucun service extérieur) :
  1. position du soleil heure par heure à Ben Arous (déclinaison, équation du temps, angle horaire) ;
  2. rayonnement par ciel clair (modèle de Haurwitz), corrigé d'un indice de clarté mensuel pour Tunis et
     d'une variabilité journalière des nuages (processus autorégressif) ;
  3. rayonnement sur le plan des panneaux (inclinaison 30°, plein sud, modèle isotrope de Liu et Jordan) ;
  4. production = puissance crête x rayonnement / 1 000 x ratio de performance, avec perte thermique.
Le résultat est calé sur un productible d'environ 1 650 kWh/kWc/an, ordre de grandeur d'une installation
à Tunis (HYPOTHÈSE à remplacer par les mesures d'un onduleur réel).

La prévision J+1 de la production combine le ciel clair (connu à l'avance) et l'indice de clarté de la
veille ; elle est comparée à la persistance (production de la veille à la même heure).
"""
import json

import numpy as np
import pandas as pd

from . import config as C

LAT, LON, TZ_OFFSET = 36.75, 10.23, 1.0           # Ben Arous, heure légale UTC+1
KWC = 60.0                                        # puissance crête installée (HYPOTHÈSE : ~350 m² de toiture)
TILT, AZIMUTH = 30.0, 180.0
PR = 0.82                                         # ratio de performance (onduleur, câbles, poussière)
# indice de clarté mensuel moyen (rayonnement réel / ciel clair), HYPOTHÈSE climatologique pour Tunis
CLEARNESS = {1: 0.72, 2: 0.75, 3: 0.79, 4: 0.83, 5: 0.88, 6: 0.93, 7: 0.96, 8: 0.94, 9: 0.87, 10: 0.80, 11: 0.73, 12: 0.70}


def sun(idx):
    """cos de l'angle zénithal et vecteurs utiles pour chaque heure (milieu d'heure, heure légale)."""
    doy = idx.dayofyear.to_numpy()
    hour = idx.hour.to_numpy() + 0.5
    b = 2 * np.pi * (doy - 81) / 364
    eot = 9.87 * np.sin(2 * b) - 7.53 * np.cos(b) - 1.5 * np.sin(b)          # équation du temps (min)
    solar_time = hour + (4 * (LON - 15 * TZ_OFFSET) + eot) / 60
    omega = np.radians(15 * (solar_time - 12))
    decl = np.radians(23.45 * np.sin(2 * np.pi * (284 + doy) / 365))
    phi = np.radians(LAT)
    cosz = np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(omega)
    return np.clip(cosz, 0, 1), decl, omega, phi


def poa(idx, ghi):
    """Rayonnement sur le plan incliné (modèle isotrope), panneaux plein sud."""
    cosz, decl, omega, phi = sun(idx)
    beta = np.radians(TILT)
    cos_inc = (np.sin(decl) * np.sin(phi - beta) + np.cos(decl) * np.cos(phi - beta) * np.cos(omega))   # plein sud
    cos_inc = np.clip(cos_inc, 0, 1)
    kt_diffuse = 0.25
    beam = (1 - kt_diffuse) * ghi
    ratio = np.where(cosz > 0.05, np.minimum(cos_inc / np.maximum(cosz, 1e-6), 4.0), 0.0)
    return beam * ratio + kt_diffuse * ghi * (1 + np.cos(beta)) / 2 + 0.2 * ghi * (1 - np.cos(beta)) / 2


def clear_sky(idx):
    cosz, *_ = sun(idx)
    return np.where(cosz > 0, 1098 * cosz * np.exp(-0.057 / np.maximum(cosz, 1e-3)), 0.0)


def simulate(idx, temperature, rng=None):
    """Production horaire (kW) et rayonnement par ciel clair sur le plan des panneaux."""
    rng = rng or np.random.default_rng(C.SEED + 30)
    days = pd.DatetimeIndex(idx.normalize().unique())
    noise = np.zeros(len(days))
    for t in range(1, len(days)):
        noise[t] = 0.6 * noise[t - 1] + rng.normal(0, 0.12)
    daily_k = pd.Series(np.clip(np.array([CLEARNESS[d.month] for d in days]) + noise, 0.15, 1.0), index=days)
    k = daily_k.reindex(idx.normalize()).to_numpy()
    ghi_clear = clear_sky(idx)
    plane_clear = poa(idx, ghi_clear)
    plane = poa(idx, ghi_clear * k)
    t_cell = temperature + 25 * plane / 1000
    derate = 1 - 0.004 * np.maximum(t_cell - 25, 0)
    pv = KWC * plane / 1000 * PR * derate
    return pd.DataFrame({"pv_kW": pv, "poa_ciel_clair": plane_clear, "clarte": k}, index=idx)


def forecast_eval(pv, hist, test_days=60):
    """Prévision J+1 de la production : profil par ciel clair (calculable à l'avance) x clarté prévue.
    Clarté prévue = tendance saisonnière + correction autorégressive à partir de la clarté de la veille ; les
    deux sont ajustées par moindres carrés sur la période d'apprentissage uniquement. Référence : persistance
    (production de la veille à la même heure)."""
    clear = KWC * pv["poa_ciel_clair"] / 1000 * PR
    k = (pv["pv_kW"].resample("D").sum() / (clear.resample("D").sum() + 1e-9)).clip(0, 1.2)
    split = k.index.max() - pd.Timedelta(days=test_days)
    doy = k.index.dayofyear.to_numpy()
    season = np.column_stack([np.ones(len(k)), np.cos(2 * np.pi * doy / 365), np.sin(2 * np.pi * doy / 365)])
    tr = (k.index <= split).nonzero()[0][1:]
    coef, *_ = np.linalg.lstsq(season[tr], k.to_numpy()[tr], rcond=None)
    trend = season @ coef
    resid = k.to_numpy() - trend
    a = float(np.dot(resid[tr - 1], resid[tr]) / np.dot(resid[tr - 1], resid[tr - 1]))
    k_hat = pd.Series(trend + a * np.r_[0.0, resid[:-1]], index=k.index)
    pred = pd.Series(clear.to_numpy() * k_hat.reindex(pv.index.normalize()).to_numpy(), index=pv.index)
    persist = pv["pv_kW"].shift(24)
    test = (pv.index > split + pd.Timedelta(days=1)) & (pv["poa_ciel_clair"] > 50)

    def mae(p_):
        return float(np.mean(np.abs(pv.loc[test, "pv_kW"] - p_[test])))

    return {"VoltEye - ciel clair x clarté prévue": {"MAE_kW": mae(pred)},
            "Baseline - production de la veille": {"MAE_kW": mae(persist)},
            "periode_test": f"{test_days} derniers jours, heures de jour", "coefficient_autoregressif": round(a, 3)}


def run(hist, out_dir=C.ARTIFACTS, log=print):
    log(f"Solaire : {KWC:.0f} kWc en toiture, production, charge nette et pointe d'été…")
    pv = simulate(hist.index, hist["temperature"].to_numpy())
    load = hist["E_total"]
    p = pv["pv_kW"]
    self_used = np.minimum(p, load)
    surplus = (p - load).clip(lower=0)
    prices = np.array([C.tariff(h, m) for h, m in zip(hist.index.hour, hist.index.month)])
    summer = hist.index.month.isin([6, 7, 8]) & (hist.index.dayofweek < 5)
    peak_hours = summer & np.array([C.tariff_period(h, m) == "pointe" for h, m in zip(hist.index.hour, hist.index.month)])
    net = load - self_used
    daily_peak = load[summer].resample("D").max().dropna()
    daily_peak_net = net[summer].resample("D").max().dropna()
    res = {
        "installation": {"kWc": KWC, "inclinaison_deg": TILT, "orientation": "plein sud", "ratio_performance": PR},
        "production_MWh_an": float(p.sum() / 1000), "productible_kWh_kWc": float(p.sum() / KWC),
        "autoconsommation_%": float(100 * self_used.sum() / p.sum()), "autoproduction_%": float(100 * self_used.sum() / load.sum()),
        "surplus_MWh": float(surplus.sum() / 1000),
        "economie_TND_an": float((self_used.to_numpy() * prices).sum()),
        "co2_evite_t_an": float(self_used.sum() * C.EMISSION_FACTOR / 1000),
        "pointe_tarifaire_ete": {"achat_moyen_sans_pv_kW": float(load[peak_hours].mean()), "achat_moyen_avec_pv_kW": float(net[peak_hours].mean())},
        "pointe_journaliere_ete": {"sans_pv_kW": float(daily_peak.mean()), "avec_pv_kW": float(daily_peak_net.mean())},
        "prevision_J+1": forecast_eval(pv, hist),
    }
    week = slice("2026-07-13", "2026-07-19")
    res["semaine_ete"] = {"time": [str(t) for t in hist.loc[week].index], "charge_kW": load.loc[week].round(2).tolist(),
                          "pv_kW": p.loc[week].round(2).tolist(), "achat_reseau_kW": net.loc[week].round(2).tolist()}
    log(f"  {res['production_MWh_an']:.0f} MWh/an ({res['productible_kWh_kWc']:.0f} kWh/kWc), autoconsommation "
        f"{res['autoconsommation_%']:.0f} %, {res['economie_TND_an']:.0f} TND/an, achat en pointe d'été "
        f"{res['pointe_tarifaire_ete']['achat_moyen_sans_pv_kW']:.0f} → {res['pointe_tarifaire_ete']['achat_moyen_avec_pv_kW']:.0f} kW")
    (out_dir / "solar.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return res
