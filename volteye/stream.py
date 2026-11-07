"""Flux temps réel d'un atelier et désagrégation non intrusive par événements.

Le simulateur reproduit ce que reçoit la passerelle du capteur unique : une
mesure par seconde du courant total de l'atelier. La désagrégation :
  1. détecter les marches de puissance (démarrage ou arrêt d'une machine) ;
  2. isoler la forme d'onde « après - avant » de l'événement ;
  3. reconnaître la machine avec le CNN GAF ;
  4. tenir à jour l'état estimé et l'énergie de chaque machine.
La vérité terrain du simulateur sert à mesurer la qualité de chaque étape.
"""
import json

import numpy as np
import pandas as pd

from . import config as C
from .signals import CLASSES, MACHINE_TYPES, current, measurements, sample_instance

SITE_NAMES = {
    "four": "Four F1", "compresseur": "Compresseur C1", "cnc": "CNC-01", "convoyeur": "Convoyeur L1",
    "eclairage": "Éclairage atelier", "soudage": "Soudage S1", "cvc": "CVC atelier",
}
# durées marche / arrêt (minutes) par type de machine
CYCLES = {
    "four": ((20, 40), (10, 20)), "compresseur": ((3, 8), (2, 6)), "cnc": ((5, 15), (1, 5)),
    "convoyeur": ((20, 60), (5, 10)), "eclairage": ((90, 200), (5, 15)), "soudage": ((1, 4), (2, 8)),
    "cvc": ((10, 20), (5, 10)),
}


def build_site(rng):
    return [sample_instance(m, rng, SITE_NAMES[m]) for m in CLASSES]


def simulate(site, seconds, rng, min_gap=4, cycle_scale=1.0):
    """États (charge 0..1) de chaque machine seconde par seconde, sans événements simultanés.
    `cycle_scale` < 1 raccourcit les cycles marche / arrêt (scénario dense)."""
    n = len(site)
    load = np.zeros((seconds, n))
    next_change = [int(rng.integers(0, 600)) for _ in range(n)]
    state = [0.0] * n
    last_event = -min_gap
    for t in range(seconds):
        for k, inst in enumerate(site):
            if t >= next_change[k]:
                if t - last_event < min_gap:            # deux événements trop proches : on décale
                    next_change[k] = t + min_gap
                    continue
                on, off = CYCLES[inst.mtype]
                if state[k] > 0:
                    state[k] = 0.0
                    next_change[k] = t + max(int(60 * cycle_scale * rng.uniform(*off)), 1)
                else:
                    state[k] = float(rng.uniform(0.5, 1.0))
                    next_change[k] = t + max(int(60 * cycle_scale * rng.uniform(*on)), 1)
                last_event = t
        load[t] = state
    return load


def aggregate_waveform(site, loads):
    return sum(current(inst, l) for inst, l in zip(site, loads))


def measure_stream(site, load, rng, start="2026-11-05 08:00:00"):
    rows = []
    cache = {}
    for t in range(len(load)):
        key = tuple(load[t])
        if key not in cache:
            cache[key] = measurements(aggregate_waveform(site, load[t]))
        m = dict(cache[key])
        m["P_kW"] += rng.normal(0, 0.15)
        rows.append(m)
    df = pd.DataFrame(rows)
    df.insert(0, "time", pd.date_range(start, periods=len(load), freq="s"))
    for k, inst in enumerate(site):
        df[f"vrai_{inst.mtype}_kW"] = inst.p_rated * load[:, k]
    return df


def detect_events(p, threshold=0.8, half=3):
    """Marches de puissance : écart entre médianes avant/après, avec suppression des non-maxima."""
    n = len(p)
    delta = np.zeros(n)
    for t in range(half, n - half):
        delta[t] = np.median(p[t + 1:t + 1 + half]) - np.median(p[t - half:t])
    events = []
    for t in range(half, n - half):
        if abs(delta[t]) >= threshold and abs(delta[t]) == np.abs(delta[max(0, t - half):t + half + 1]).max():
            if not events or t - events[-1] > half:
                events.append(t)
    return events, delta


def disaggregate(site, load, df, recognizer, rng):
    """Désagrégation complète du flux ; renvoie les événements et la puissance estimée par machine."""
    p = df["P_kW"].to_numpy()
    events, delta = detect_events(p)
    est_state = {m: 0.0 for m in CLASSES}
    est_power = np.zeros((len(p), len(CLASSES)))
    records, waves = [], []
    for t in events:
        before = aggregate_waveform(site, load[max(t - 2, 0)])
        after = aggregate_waveform(site, load[min(t + 2, len(load) - 1)])
        diff = after - before
        diff = diff + rng.normal(0, 0.02 * np.abs(diff).max() + 1e-6, size=diff.shape)
        direction = "marche" if delta[t] > 0 else "arrêt"
        wave = diff if delta[t] > 0 else -diff
        proba = recognizer.predict_proba([wave])[0]
        pred = CLASSES[int(proba.argmax())]
        changed = np.flatnonzero(np.abs(load[min(t + 2, len(load) - 1)] - load[max(t - 2, 0)]) > 1e-9)
        truth = CLASSES[changed[0]] if len(changed) else "aucune"
        est_state[pred] = abs(delta[t]) if direction == "marche" else 0.0
        records.append({"t": int(t), "time": str(df["time"].iloc[t]), "direction": direction,
                        "delta_kW": float(delta[t]), "prediction": pred, "confiance": float(proba.max()),
                        "verite": truth, "correct": pred == truth,
                        "proba": {c: float(x) for c, x in zip(CLASSES, proba)}})
        waves.append(wave)
        est_power[t:] = [est_state[m] for m in CLASSES]
    return records, np.array(waves), est_power


def evaluate(load, site, records, est_power, tol=3):
    true_events = [t for t in range(1, len(load)) if np.any(np.abs(load[t] - load[t - 1]) > 1e-9)]
    det = [r["t"] for r in records]
    matched = sum(any(abs(d - te) <= tol for d in det) for te in true_events)
    tp = sum(any(abs(d - te) <= tol for te in true_events) for d in det)
    precision = tp / max(len(det), 1)
    recall = matched / max(len(true_events), 1)
    true_power = np.column_stack([inst.p_rated * load[:, k] for k, inst in enumerate(site)])
    e_true = true_power.sum(0) / 3600
    e_est = est_power.sum(0) / 3600
    per_machine = {m: {"energie_vraie_kWh": float(a), "energie_estimee_kWh": float(b),
                       "erreur_relative": float(abs(b - a) / max(a, 1e-9))}
                   for m, a, b in zip(CLASSES, e_true, e_est)}
    return {
        "evenements_reels": len(true_events), "evenements_detectes": len(det),
        "detection_precision": precision, "detection_rappel": recall,
        "detection_f1": 2 * precision * recall / max(precision + recall, 1e-9),
        "classification_exactitude": float(np.mean([r["correct"] for r in records])),
        # métrique NILM standard : 1 - somme des écarts d'énergie / (2 x énergie totale)
        "precision_energetique": float(1 - np.abs(e_est - e_true).sum() / (2 * e_true.sum())),
        "par_machine": per_machine,
    }


def dense_scenario(recognizer, minutes=60, log=print):
    """Scénario dense : cycles cinq fois plus courts et événements espacés d'une seconde seulement."""
    rng = np.random.default_rng(C.SEED + 11)
    site = build_site(rng)
    load = simulate(site, minutes * 60, rng, min_gap=1, cycle_scale=0.2)
    df = measure_stream(site, load, rng)
    records, _, est_power = disaggregate(site, load, df, recognizer, rng)
    m = evaluate(load, site, records, est_power)
    starts = [t for t in range(1, len(load)) if np.any(np.abs(load[t] - load[t - 1]) > 1e-9)]
    gaps = np.diff(starts)
    m["evenements_a_moins_de_4_s"] = int((gaps < 4).sum())
    m["duree_min"] = minutes
    m.pop("par_machine")
    log(f"  scénario dense ({minutes} min, {m['evenements_reels']} événements dont "
        f"{m['evenements_a_moins_de_4_s']} à moins de 4 s) : détection F1 {m['detection_f1']:.3f}, "
        f"classification {m['classification_exactitude']:.3f}")
    return m


def run(recognizer, hours=4, out_dir=C.ARTIFACTS, log=print):
    rng = np.random.default_rng(C.SEED + 1)
    site = build_site(rng)
    log(f"Flux temps réel : simulation de {hours} h d'atelier à 1 mesure/s…")
    load = simulate(site, hours * 3600, rng)
    df = measure_stream(site, load, rng)
    records, waves, est_power = disaggregate(site, load, df, recognizer, rng)
    for k, m in enumerate(CLASSES):
        df[f"estime_{m}_kW"] = est_power[:, k]
    metrics = evaluate(load, site, records, est_power)
    log(f"  événements : {metrics['evenements_detectes']} détectés / {metrics['evenements_reels']} réels, "
        f"classification {metrics['classification_exactitude']:.3f}, "
        f"précision énergétique {metrics['precision_energetique']:.3f}")
    df.to_parquet(out_dir / "stream.parquet")
    np.save(out_dir / "stream_event_waves.npy", waves)
    site_info = [{"nom": i.name, "type": i.mtype, "libelle": MACHINE_TYPES[i.mtype].label,
                  "p_nominale_kW": i.p_rated, "fp": i.pf} for i in site]
    (out_dir / "stream_events.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    metrics["scenario_dense"] = dense_scenario(recognizer, log=log)
    (out_dir / "stream_metrics.json").write_text(json.dumps({"site": site_info, **metrics}, indent=2, ensure_ascii=False), encoding="utf-8")
    return metrics
