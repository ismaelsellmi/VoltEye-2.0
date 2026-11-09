"""Chargement initial de la base à partir des artefacts du pipeline (démo hors ligne reproductible).

Usage : python -m api.seed [--force]
"""
import json
import sys

import numpy as np
import pandas as pd
from sqlalchemy import text

from volteye import config as C
from volteye.signals import CLASSES, MACHINE_TYPES

from . import db

TZ = "Africa/Tunis"
REF = {"code": "usine-ref", "name": "Atelier de référence (Ben Arous)", "kind": "usine", "sector": "Mécanique",
       "factories": 1, "lat": 36.75, "lon": 10.23}
HIPE = {"code": "hipe-kit", "name": "Usine HIPE (KIT, mesures réelles)", "kind": "usine", "sector": "Électronique",
        "factories": 1, "lat": 49.01, "lon": 8.42}
TABLES = ["doc_chunk", "metric", "grid_day", "schedule_day", "health", "anomaly", "forecast", "context_hourly",
          "machine_load", "event", "measurement", "machine", "meter", "site"]


def _load(name):
    return json.loads((C.ARTIFACTS / name).read_text(encoding="utf-8"))


def _ts(index):
    return pd.DatetimeIndex(index).tz_localize(TZ, nonexistent="shift_forward", ambiguous="NaT")


def _insert(cx, table, records):
    if not records:
        return
    cols = list(records[0])
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})"
    for i in range(0, len(records), 5000):
        cx.execute(text(sql), records[i:i + 5000])


def _clean(v):
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


METRICS = {"reconnaissance": "recognition_metrics.json", "flux": "stream_metrics.json",
           "prevision": "forecast_metrics.json", "anomalies": "anomaly_metrics.json", "hipe": "hipe_metrics.json",
           "assistant": "assistant_eval.json", "assistant_llm": "assistant_eval_llm.json", "solaire": "solar.json",
           "rag": "rag_eval.json"}


def refresh_metrics(cx):
    """Met à jour les résultats d'évaluation à partir des artefacts (nouvelles évaluations sans réinitialiser la base)."""
    for name, file in METRICS.items():
        if (C.ARTIFACTS / file).exists():
            cx.execute(text("INSERT INTO metric (name, data) VALUES (:n, :d) ON CONFLICT (name) DO UPDATE SET data = EXCLUDED.data"),
                       {"n": name, "d": json.dumps(_load(file))})


def seed(force=False, log=print):
    db.wait_for_db()
    db.ensure_schema()
    db.migrate()
    eng = db.engine()
    with eng.begin() as cx:
        if not force and cx.execute(text("SELECT count(*) FROM site")).scalar():
            refresh_metrics(cx)
            log("Base déjà initialisée.")
            return False
        cx.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        log("Chargement : sites, compteurs et machines…")
        zones = _load("city_sites.json")
        sites = [REF, HIPE] + [{"code": f"zone-{k + 1:02d}", "name": z["site"], "kind": "zone", "sector": z["secteur"],
                                "factories": z["usines"], "lat": z["lat"], "lon": z["lon"]} for k, z in enumerate(zones)]
        _insert(cx, "site", sites)
        ids = {r.code: r.id for r in cx.execute(text("SELECT id, code FROM site"))}
        ref = ids["usine-ref"]
        _insert(cx, "meter", [{"site_id": ids[c], "name": "Compteur général"} for c in ("usine-ref", "hipe-kit")])
        sm = _load("stream_metrics.json")
        _insert(cx, "machine", [{"site_id": ref, "mtype": m["type"], "name": m["nom"], "label": m["libelle"],
                                 "p_rated_kw": m["p_nominale_kW"], "pf": m["fp"]} for m in sm["site"]])

        log("Chargement : historique horaire désagrégé (1 an)…")
        hist = pd.read_parquet(C.ARTIFACTS / "history.parquet")
        t = _ts(hist.index)
        recs = []
        for m in CLASSES:
            e, thd = hist[f"E_{m}"].to_numpy(), hist[f"THD_{m}"].to_numpy()
            recs += [{"time": ti, "site_id": ref, "mtype": m, "kwh": float(a), "thd": float(b)}
                     for ti, a, b in zip(t, e, thd) if ti is not pd.NaT]
        _insert(cx, "machine_load", recs)
        _insert(cx, "context_hourly", [{"time": ti, "site_id": ref, "temperature": float(r.temperature),
                                        "production": bool(r.production), "holiday": bool(r.ferie),
                                        "ramadan": bool(r.ramadan)}
                                       for ti, r in zip(t, hist.itertuples()) if ti is not pd.NaT])

        log("Chargement : prévisions, anomalies, santé, plannings, VoltEye Grid…")
        fc = pd.read_parquet(C.ARTIFACTS / "forecast_test.parquet")
        q = fc if "p10" in fc else fc.assign(p10=np.nan, p90=np.nan)
        _insert(cx, "forecast", [{"time": ti, "site_id": ref, "p10": _clean(r.p10), "p50": _clean(r.prevision),
                                  "p90": _clean(r.p90), "actual": _clean(r.reel), "baseline": _clean(r.baseline_semaine)}
                                 for ti, r in zip(_ts(q.index), q.itertuples())])
        an = pd.read_parquet(C.ARTIFACTS / "anomalies_daily.parquet")
        _insert(cx, "anomaly", [{"day": d.date(), "site_id": ref, "mtype": r.machine, "energy_kwh": _clean(r.energie_kWh),
                                 "expected_kwh": _clean(r.attendu_kWh), "score": _clean(r.score), "alert": bool(r.alerte),
                                 "cause": r.cause or None, "excess_cost_tnd": _clean(r.cout_exces_TND),
                                 "period": getattr(r, "periode", None)} for d, r in zip(an.index, an.itertuples())])
        he = pd.read_parquet(C.ARTIFACTS / "health_daily.parquet")
        _insert(cx, "health", [{"day": d.date(), "site_id": ref, "mtype": r.machine, "thd": _clean(r.thd),
                                "drift": _clean(r.derive), "health": _clean(r.sante),
                                "days_left": _clean(r.jours_avant_seuil), "alert": bool(r.alerte)}
                               for d, r in zip(he.index, he.itertuples())])
        opt = _load("optimization.json")
        _insert(cx, "schedule_day", [{"day": d["jour"], "data": json.dumps(d)} for d in opt["jours"]])
        grid = _load("grid.json")
        _insert(cx, "grid_day", [{"day": d["jour"], "data": json.dumps(d)} for d in grid["jours"]])
        refresh_metrics(cx)
        docs = [{"name": "optimisation", "data": json.dumps(opt["resume"])},
                 {"name": "grid", "data": json.dumps(grid["resume"])},
                 {"name": "zones", "data": json.dumps(grid["zones"])},
                 {"name": "machines", "data": json.dumps({m: {"label": MACHINE_TYPES[m].label,
                                                              "color": MACHINE_TYPES[m].color} for m in CLASSES})}]
        _insert(cx, "metric", docs)
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as cx:
        cx.execute(text("CALL refresh_continuous_aggregate('machine_load_daily', NULL, NULL)"))
    log("Base initialisée.")
    return True


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    seed(force="--force" in sys.argv)
