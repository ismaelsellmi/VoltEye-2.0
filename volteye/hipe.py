"""Validation de VoltEye sur des mesures industrielles réelles : jeu de données HIPE (KIT).

HIPE (High-resolution Industrial Production Energy) : une usine d'électronique de puissance du KIT
(Karlsruhe), l'arrivée générale et 10 machines mesurées toutes les 5 s environ, avec P, Q, facteur de
puissance, THD et harmoniques de courant. Sous-ensemble utilisé : la semaine du 23 au 29 octobre 2017
(licence CC BY 4.0). Téléchargement : python scripts/telecharger_hipe.py

Ce module mesure, sur ces données réelles :
  1. la détection d'événements de VoltEye sur l'arrivée générale (même détecteur que le flux simulé) ;
  2. la reconnaissance de la machine à l'origine de chaque événement, à partir de la variation de la
     signature (P, Q, facteur de puissance, harmoniques) vue au point de mesure unique ;
  3. la prévision de la charge du site à 1 h, au pas de 15 min ;
  4. la consommation hors production (nuit et week-end) de chaque machine.
HIPE fournit le spectre harmonique et non la forme d'onde : la branche « spectre » de la reconnaissance
est validée ici ; la branche images GAF reste évaluée sur formes d'onde simulées.
"""
import json
import zipfile

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score

from . import config as C
from .stream import detect_events

RAW = C.ROOT / "data" / "raw" / "hipe"
ARCHIVE = RAW / "hipe_cleaned_v1.0.1_geq_2017-10-23_lt_2017-10-30.zip"
CACHE = RAW / "hipe_5s.parquet"
STEP = "5s"
HARMONICS = [3, 5, 7, 9, 11, 13, 15]
MACHINES = {  # nom HIPE -> libellé
    "ChipPress": "Presse à puces", "ChipSaw": "Scie à puces", "HighTemperatureOven": "Four haute température",
    "PickAndPlaceUnit": "Machine de placement", "ScreenPrinter": "Sérigraphie", "SolderingOven": "Four de brasage",
    "VacuumOven": "Four sous vide", "VacuumPump1": "Pompe à vide 1", "VacuumPump2": "Pompe à vide 2",
    "WashingMachine": "Machine de lavage",
}
SITE = "MainTerminal"


def _read_sensor(z, name):
    phases = [1, 2, 3]
    cols = ["SensorDateTime", "P_kW", "Q_kvar", "S_kVA"] + [f"THD_I{p}_F" for p in phases] + \
           [f"H{h:02d}_I{p}_F" for h in HARMONICS for p in phases]
    with z.open(name) as f:
        df = pd.read_csv(f, usecols=lambda c: c in cols, dtype={c: "float32" for c in cols[1:]})
    t = pd.to_datetime(df.pop("SensorDateTime"), utc=True, format="ISO8601").dt.tz_convert("Europe/Berlin").dt.tz_localize(None)
    out = pd.DataFrame({"P_kW": df["P_kW"], "Q_kvar": df["Q_kvar"], "S_kVA": df["S_kVA"]})
    out.index = t
    out["PF"] = (out["P_kW"] / out["S_kVA"].where(out["S_kVA"] > 1e-3)).clip(-1, 1)
    thd = df[[c for c in df if c.startswith("THD_I")]]
    out["THD"] = thd.mean(axis=1).to_numpy()
    for h in HARMONICS:
        out[f"H{h}"] = df[[c for c in df if c.startswith(f"H{h:02d}_I")]].mean(axis=1).to_numpy()
    return out.resample(STEP).mean().astype("float32")


def load(archive=ARCHIVE, cache=CACHE, log=print):
    """Toutes les mesures sur une grille commune de 5 s ; colonnes « <capteur>|<grandeur> »."""
    if cache.exists():
        return pd.read_parquet(cache)
    if not archive.exists():
        raise FileNotFoundError(f"{archive} absent : lancer python scripts/telecharger_hipe.py")
    frames = {}
    with zipfile.ZipFile(archive) as z:
        for name in sorted(z.namelist()):
            sensor = name.split("_PhaseCount")[0]
            log(f"  lecture {sensor}…")
            frames[sensor] = _read_sensor(z, name)
    df = pd.concat(frames, axis=1)
    df.columns = [f"{s}|{q}" for s, q in df.columns]
    df = df.interpolate(limit=2)
    df.to_parquet(cache)
    return df


# --- Évaluation ------------------------------------------------------------------

SIGNIFICANT_KW = 0.8              # même seuil que la détection VoltEye sur le flux simulé
TOL = 3                           # tolérance d'appariement d'un événement (pas de 5 s)
HALF = 3


def _series(df, sensor, q="P_kW"):
    return df[f"{sensor}|{q}"].ffill().fillna(0).to_numpy(dtype=float)


def production_mask(index):
    """Heures de production observées sur l'arrivée générale : jours ouvrés, 7 h - 21 h."""
    return (index.dayofweek < 5) & (index.hour >= 7) & (index.hour < 21)


def machine_events(df, threshold=SIGNIFICANT_KW):
    """Vérité terrain : marches de puissance mesurées directement sur chaque machine."""
    rows = []
    for m in MACHINES:
        ev, d = detect_events(_series(df, m), threshold=threshold, half=HALF)
        rows += [{"t": int(t), "machine": m, "dP_machine": float(d[t])} for t in ev]
    return pd.DataFrame(rows, columns=["t", "machine", "dP_machine"]).sort_values("t").reset_index(drop=True)


def _harmonic_currents(df, sensor):
    """Courants harmoniques efficaces (A) à partir des taux mesurés (en %) et du courant fondamental."""
    s = _series(df, sensor, "S_kVA")
    thd = _series(df, sensor, "THD") / 100
    i_fund = s * 1000 / (3 * C.V_PHASE) / np.sqrt(1 + thd ** 2)
    return {h: _series(df, sensor, f"H{h}") / 100 * i_fund for h in HARMONICS}


def delta_features(df, events, sensor=SITE, half=HALF):
    """Variation de signature vue au point de mesure : après - avant, orientée comme un démarrage."""
    sig = {"dP": _series(df, sensor), "dQ": _series(df, sensor, "Q_kvar")}
    sig.update({f"dH{h}": v for h, v in _harmonic_currents(df, sensor).items()})
    rows = []
    for t in events:
        r = {k: float(np.median(v[t + 1:t + 1 + half]) - np.median(v[t - half:t])) for k, v in sig.items()}
        sign = 1.0 if r["dP"] >= 0 else -1.0
        rows.append({k: sign * v for k, v in r.items()})
    return pd.DataFrame(rows)


def label_events(site_events, truth, tol=TOL):
    """Chaque événement du site prend le nom de la machine suivie qui a basculé au même instant, sinon « autre »."""
    labels = []
    for t in site_events:
        near = truth[(truth["t"] - t).abs() <= tol]
        labels.append(near.iloc[(near["t"] - t).abs().argmin()]["machine"] if len(near) else "autre")
    return np.array(labels)


def detection_eval(df, site_events, truth):
    found = [bool(np.any(np.abs(np.asarray(site_events) - t) <= TOL)) for t in truth["t"]]
    truth = truth.assign(trouve=found)
    per = truth.groupby("machine")["trouve"].agg(["size", "mean"])
    return {"evenements_site": len(site_events), "evenements_machines_suivies": int(len(truth)),
            "rappel": float(truth["trouve"].mean()),
            "par_machine": {m: {"evenements": int(r["size"]), "rappel": float(r["mean"])} for m, r in per.iterrows()}}


def chronological_split(labels, share=0.7, min_events=10):
    """Pour chaque classe, les 70 % premiers événements (dans le temps) servent à l'apprentissage, les suivants au test.
    Les machines ne tournent pas tous les jours : un découpage par date laisserait des classes sans test."""
    tr = np.zeros(len(labels), dtype=bool)
    classes = [c for c in np.unique(labels) if (labels == c).sum() >= min_events]
    for c in classes:
        idx = np.flatnonzero(labels == c)                    # événements déjà triés dans le temps
        tr[idx[:int(share * len(idx))]] = True
    keep = np.isin(labels, classes)
    return tr & keep, ~tr & keep, classes


def recognition_eval(df, site_events, labels):
    """Forêt aléatoire, découpage chronologique par classe ; A : ΔP, ΔQ ; VoltEye : + harmoniques."""
    feats = delta_features(df, site_events)
    tr, te, classes = chronological_split(labels)
    keep = tr | te
    out = {"classes": {c: {"apprentissage": int((labels[tr] == c).sum()), "test": int((labels[te] == c).sum())}
                       for c in classes}}
    for name, cols in [("A - ΔP, ΔQ + forêt aléatoire", ["dP", "dQ"]),
                       ("VoltEye - ΔP, ΔQ + harmoniques + forêt aléatoire", list(feats.columns))]:
        rf = RandomForestClassifier(300, random_state=C.SEED, class_weight="balanced", n_jobs=-1)
        rf.fit(feats.loc[tr & keep, cols], labels[tr & keep])
        pred = rf.predict(feats.loc[te & keep, cols])
        y = labels[te & keep]
        out[name] = {"exactitude": float(accuracy_score(y, pred)),
                     "f1_macro": float(f1_score(y, pred, average="macro")),
                     "f1_par_classe": dict(zip(classes, f1_score(y, pred, labels=classes, average=None).round(3).tolist()))}
    return out


def signature_eval(df, on_kw=0.1, per_machine=3000):
    """Reconnaissance d'une signature isolée réelle (l'entrée de l'étape de reconnaissance VoltEye) :
    mesures à 5 s de chaque machine en marche ; A : P, Q, facteur de puissance ; VoltEye : + THD et harmoniques."""
    rows, labels = [], []
    for m in MACHINES:
        d = df[[f"{m}|{q}" for q in ["P_kW", "Q_kvar", "PF", "THD"] + [f"H{h}" for h in HARMONICS]]].dropna()
        d = d[d[f"{m}|P_kW"] > on_kw]
        if len(d) < 50:
            continue
        d = d.iloc[np.linspace(0, len(d) - 1, min(per_machine, len(d))).astype(int)]   # sous-échantillon régulier
        d.columns = [c.split("|")[1] for c in d.columns]
        rows.append(d)
        labels += [m] * len(d)
    x = pd.concat(rows).reset_index(drop=True)
    labels = np.array(labels)
    tr, te, classes = chronological_split(labels, min_events=50)
    out = {"machines": {c: {"apprentissage": int((labels[tr] == c).sum()), "test": int((labels[te] == c).sum())}
                        for c in classes}}
    for name, cols in [("A - P, Q, facteur de puissance + forêt aléatoire", ["P_kW", "Q_kvar", "PF"]),
                       ("VoltEye - + THD et harmoniques + forêt aléatoire", list(x.columns))]:
        rf = RandomForestClassifier(300, random_state=C.SEED, n_jobs=-1).fit(x.loc[tr, cols], labels[tr])
        pred = rf.predict(x.loc[te, cols])
        out[name] = {"exactitude": float(accuracy_score(labels[te], pred)),
                     "f1_macro": float(f1_score(labels[te], pred, average="macro")),
                     "f1_par_classe": dict(zip(classes, f1_score(labels[te], pred, labels=classes,
                                                                 average=None).round(3).tolist()))}
    return out


def forecast_eval(df):
    """Charge du site au pas de 15 min, prévue 1 h à l'avance (jours ouvrés : lun.-mer. pour apprendre, jeu.-ven. pour tester)."""
    s = df[f"{SITE}|P_kW"].resample("15min").mean()
    x = pd.DataFrame({"minute_jour": s.index.hour * 60 + s.index.minute, "lag_1h": s.shift(4), "lag_2h": s.shift(8),
                      "moyenne_2h": s.shift(4).rolling(8).mean(), "ecart_1h": s.shift(4) - s.shift(8)}, index=s.index)
    weekday = s.index.dayofweek < 5
    ok = x.notna().all(axis=1) & weekday
    tr, te = ok & (s.index < "2017-10-26"), ok & (s.index >= "2017-10-26")
    model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, min_samples_leaf=10, random_state=C.SEED)
    model.fit(x[tr], s[tr])
    pred = model.predict(x[te])

    def m(p):
        y = s[te].to_numpy()
        return {"MAE_kW": float(np.mean(np.abs(y - p))), "MAPE_%": float(100 * np.mean(np.abs(y - p) / y))}

    return {"VoltEye - gradient boosting": m(pred), "Baseline - valeur d'il y a 1 h": m(x.loc[te, "lag_1h"].to_numpy()),
            "Baseline - même heure la veille": m(s.shift(96)[te].to_numpy()),
            "points_test": int(te.sum()), "periode_test": ["2017-10-26", "2017-10-27"]}


def idle_eval(df):
    """Énergie consommée hors production (nuit et week-end) : site et machines suivies."""
    prod = production_mask(df.index)
    out = {}
    for s in [SITE, *MACHINES]:
        p = df[f"{s}|P_kW"].clip(lower=0).fillna(0)
        total = float(p.sum() * 5 / 3600)
        idle = float(p[~prod].sum() * 5 / 3600)
        if total > 1:
            out[s] = {"kWh_semaine": total, "kWh_hors_production": idle, "part_hors_production": idle / total}
    p = df[f"{SITE}|P_kW"]
    out["talon_site_kW"] = float(p[~prod].median())
    out["heures_hors_production_semaine"] = float((~prod).sum() * 5 / 3600)
    return out


def replay_slice(df, day="2017-10-26"):
    """Une journée ouvrée réelle au pas de 5 s, rejouée par la passerelle edge simulée."""
    d = df.loc[day]
    cols = [f"{SITE}|{q}" for q in ["P_kW", "Q_kvar", "PF", "THD"] + [f"H{h}" for h in HARMONICS]]
    cols += [f"{m}|P_kW" for m in MACHINES]
    return d[cols].astype("float32")


def run(out_dir=C.ARTIFACTS, log=print):
    try:
        df = load(log=log)
    except FileNotFoundError as e:
        log(f"HIPE : {e}")
        return None
    log("HIPE : validation sur une semaine de mesures industrielles réelles…")
    site_events, _ = detect_events(_series(df, SITE), threshold=SIGNIFICANT_KW, half=HALF)
    truth = machine_events(df)
    labels = label_events(site_events, truth)
    res = {"source": "HIPE (KIT), semaine du 23 au 29/10/2017, pas de 5 s, licence CC BY 4.0",
           "detection": detection_eval(df, site_events, truth),
           "reconnaissance": recognition_eval(df, site_events, labels),
           "signatures": signature_eval(df),
           "prevision_1h": forecast_eval(df), "hors_production": idle_eval(df),
           "libelles": MACHINES}
    det, rec, fc = res["detection"], res["reconnaissance"], res["prevision_1h"]
    log(f"  détection : rappel {det['rappel']:.3f} sur {det['evenements_machines_suivies']} événements des machines suivies")
    for k in [k for k in rec if k != "classes"]:
        log(f"  événements au point unique, {k} : exactitude {rec[k]['exactitude']:.3f}, F1 macro {rec[k]['f1_macro']:.3f}")
    sig = res["signatures"]
    for k in [k for k in sig if k != "machines"]:
        log(f"  signatures isolées, {k} : exactitude {sig[k]['exactitude']:.3f}, F1 macro {sig[k]['f1_macro']:.3f}")
    persistence = fc["Baseline - valeur d'il y a 1 h"]["MAPE_%"]
    log(f"  prévision 1 h : MAPE {fc['VoltEye - gradient boosting']['MAPE_%']:.1f} % (persistance {persistence:.1f} %)")
    replay_slice(df).to_parquet(out_dir / "hipe_replay.parquet", compression="zstd")
    (out_dir / "hipe_metrics.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return res
