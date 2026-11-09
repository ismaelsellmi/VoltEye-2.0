"""API VoltEye.

Lancement local : uvicorn api.main:app --reload   (documentation interactive : http://localhost:8000/docs)
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from volteye import __version__
from volteye import config as C
from volteye.optimization import TASKS, cost, optimize, tariff_aware_starts

from . import db
from .live import hub

logging.basicConfig(level=logging.INFO)
REF = "usine-ref"


@asynccontextmanager
async def lifespan(app):
    if os.environ.get("AUTO_SEED", "1") == "1":
        from .seed import seed
        await asyncio.to_thread(seed)
        try:                                       # index du RAG aligné sur la documentation embarquée
            from agent.rag import sync
            await asyncio.to_thread(sync)
        except Exception as e:
            logging.warning("Index documentaire non synchronisé : %s", e)
    hub.start(asyncio.get_running_loop())
    yield
    hub.stop()


app = FastAPI(title="VoltEye API", version=__version__, lifespan=lifespan,
              description="Suivi énergétique non intrusif : mesures temps réel, reconnaissance des machines, "
                          "prévision, anomalies, maintenance, optimisation et VoltEye Grid.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def metric(name):
    data = db.scalar("SELECT data FROM metric WHERE name = :n", n=name)
    if data is None:
        raise HTTPException(404, f"métrique « {name} » absente")
    return data


def site_id(code):
    sid = db.scalar("SELECT id FROM site WHERE code = :c", c=code)
    if sid is None:
        raise HTTPException(404, f"site « {code} » inconnu")
    return sid


# --- État -------------------------------------------------------------------------

@app.get("/api/sante-service", tags=["service"])
def service_health():
    return {"api": "ok", "version": __version__, "base": db.scalar("SELECT count(*) FROM site") is not None,
            "mqtt": hub.connected, "messages_recus": hub.received}


@app.get("/api/sites", tags=["référentiel"])
def sites():
    return db.rows("SELECT id, code, name, kind, sector, factories, lat, lon FROM site ORDER BY id")


@app.get("/api/machines", tags=["référentiel"])
def machines(site: str = REF):
    meta = metric("machines")
    out = db.rows("SELECT mtype, name, label, p_rated_kw, pf FROM machine WHERE site_id = :s ORDER BY id", s=site_id(site))
    for m in out:
        m["color"] = meta.get(m["mtype"], {}).get("color")
    return out


# --- Vue d'ensemble -----------------------------------------------------------------

@app.get("/api/kpis", tags=["vue d'ensemble"])
def kpis(site: str = REF, days: int = 30):
    sid = site_id(site)
    end = db.scalar("SELECT max(time) FROM machine_load WHERE site_id = :s", s=sid)
    by_machine = db.rows("""SELECT mtype, sum(kwh) AS kwh FROM machine_load
                            WHERE site_id = :s AND time > :end - make_interval(days => :d) GROUP BY mtype ORDER BY kwh DESC""",
                         s=sid, end=end, d=days)
    total = float(sum(r["kwh"] for r in by_machine))
    alerts = db.rows("""SELECT day, mtype, score, cause, excess_cost_tnd FROM anomaly
                        WHERE site_id = :s AND alert ORDER BY day DESC LIMIT 8""", s=sid)
    health = db.rows("""SELECT DISTINCT ON (mtype) mtype, health, drift, alert, days_left FROM health
                        WHERE site_id = :s ORDER BY mtype, day DESC""", s=sid)
    am, rm, fm = metric("anomalies"), metric("reconnaissance"), metric("prevision")
    opt, grid = metric("optimisation"), metric("grid")
    return {
        "periode": {"fin": end, "jours": days},
        "energie_kWh": total, "cout_TND": total * C.TARIFFS["jour"], "co2_kg": total * C.EMISSION_FACTOR,
        "repartition": by_machine, "alertes_recentes": alerts, "sante": health,
        "modeles": {
            "reconnaissance_exactitude": rm["models"]["D - VoltEye : fusion CNN GAF + spectre FFT"]["accuracy"],
            "anomalies_f1_test": am["models"]["VoltEye - résidus + score robuste (MAD)"]["f1"],
            "prevision_mape": fm["models"]["VoltEye - gradient boosting"]["MAPE_%_heures_actives"],
            "anticipation_panne_jours": am["maintenance"]["anticipation_panne_convoyeur_jours"],
        },
        "planning": {k: opt[k] for k in ("gain_moyen_%", "gain_annuel_estime_TND", "reduction_pointe_moyenne_kW")},
        "grid": {k: grid[k] for k in ("effacement_MW_vs_pratique", "effacement_%_vs_pratique", "usines", "zones")},
    }


@app.get("/api/consommation", tags=["historique"])
def consumption(site: str = REF, debut: date | None = None, fin: date | None = None, pas: str = "jour"):
    """Énergie par machine, au pas horaire ou journalier (agrégat continu TimescaleDB)."""
    sid = site_id(site)
    if pas == "jour":
        sql = "SELECT day AS time, mtype, kwh FROM machine_load_daily WHERE site_id = :s"
        col = "day"
    elif pas == "heure":
        sql = "SELECT time, mtype, kwh FROM machine_load WHERE site_id = :s"
        col = "time"
    else:
        raise HTTPException(422, "pas : « jour » ou « heure »")
    if debut:
        sql += f" AND {col} >= :debut"
    if fin:
        sql += f" AND {col} < :fin"
    return db.rows(sql + " ORDER BY 1, 2", s=sid, debut=debut, fin=fin)


# --- Anomalies et maintenance -----------------------------------------------------------

@app.get("/api/anomalies", tags=["anomalies"])
def anomalies(site: str = REF, machine: str | None = None, alertes_seules: bool = False, mois: str | None = None):
    sql = "SELECT day, mtype, energy_kwh, expected_kwh, score, alert, cause, excess_cost_tnd, period FROM anomaly WHERE site_id = :s"
    if machine:
        sql += " AND mtype = :m"
    if alertes_seules:
        sql += " AND alert"
    if mois:
        sql += " AND to_char(day, 'YYYY-MM') = :mois"
    recos = metric("anomalies")["recommandations"]
    out = db.rows(sql + " ORDER BY day, mtype", s=site_id(site), m=machine, mois=mois)
    for r in out:
        r["recommandation"] = recos.get(r["cause"]) if r["alert"] else None
    return out


@app.get("/api/sante", tags=["anomalies"])
def health(site: str = REF, machine: str | None = None):
    sql = "SELECT day, mtype, thd, drift, health, days_left, alert FROM health WHERE site_id = :s"
    if machine:
        sql += " AND mtype = :m"
    return db.rows(sql + " ORDER BY day, mtype", s=site_id(site), m=machine)


# --- Prévision et planning ----------------------------------------------------------------

@app.get("/api/prevision", tags=["prévision et planning"])
def forecast(site: str = REF):
    return {"serie": db.rows("SELECT time, p10, p50, p90, actual, baseline FROM forecast WHERE site_id = :s ORDER BY time",
                             s=site_id(site)),
            "metriques": metric("prevision")}


@app.get("/api/planning", tags=["prévision et planning"])
def schedule(jour: date | None = None):
    days = [r["day"] for r in db.rows("SELECT day FROM schedule_day ORDER BY day")]
    if not days:
        raise HTTPException(404, "aucun planning")
    jour = jour or days[len(days) // 2]
    data = db.scalar("SELECT data FROM schedule_day WHERE day = :d", d=jour)
    if data is None:
        raise HTTPException(404, f"pas de planning pour {jour}")
    return {"jours": days, "jour": data, "taches": TASKS, "resume": metric("optimisation")}


class PlanRequest(BaseModel):
    base_kw: list[float] = Field(..., min_length=24, max_length=24, description="charge de base prévue, 24 valeurs (kW)")
    mois: int = Field(7, ge=1, le=12)
    p_max_kw: float | None = None


@app.post("/api/optimiser", tags=["prévision et planning"])
def plan(req: PlanRequest):
    """Optimise le planning des tâches flexibles pour une charge de base donnée (MILP HiGHS)."""
    base = np.array(req.base_kw, dtype=float)
    prices = np.array([C.tariff(h, req.mois) for h in range(24)])
    starts, status = optimize(base, prices, req.p_max_kw)
    out = {"statut": status, "taches": []}
    refs = {"pratique_actuelle": [max(t["fenetre"][0], 7) for t in TASKS], "operateur_averti": tariff_aware_starts(prices),
            "voltEye": starts}
    for name, st in refs.items():
        c, p = cost(base, st, prices)
        out[name] = {"demarrages": st, "facture_TND": c + C.PEAK_DEMAND_CHARGE * p, "pointe_kW": p}
    out["taches"] = [{**t, "demarrage": s} for t, s in zip(TASKS, starts)]
    return out


# --- VoltEye Grid -------------------------------------------------------------------------

@app.get("/api/grid", tags=["VoltEye Grid"])
def grid():
    return {"resume": metric("grid"), "zones": metric("zones"),
            "jours": [r["day"] for r in db.rows("SELECT day FROM grid_day ORDER BY day")]}


@app.get("/api/grid/{jour}", tags=["VoltEye Grid"])
def grid_day(jour: date):
    data = db.scalar("SELECT data FROM grid_day WHERE day = :d", d=jour)
    if data is None:
        raise HTTPException(404, f"pas de résultat VoltEye Grid pour {jour}")
    return data


# --- Évaluation ---------------------------------------------------------------------------

@app.get("/api/evaluation", tags=["évaluation"])
def evaluation():
    return {r["name"]: r["data"] for r in db.rows("SELECT name, data FROM metric WHERE name NOT IN ('zones', 'assistant', 'assistant_llm', 'solaire')")}


# --- Temps réel ---------------------------------------------------------------------------

@app.get("/api/direct", tags=["temps réel"])
def live(site: str = REF, secondes: int = Query(900, le=86400)):
    """Dernières mesures du compteur unique (1 par seconde), avec la désagrégation par machine."""
    sid = site_id(site)
    return db.rows("""SELECT time, p_kw, q_kvar, pf, thd, estimated FROM measurement m
                      JOIN meter t ON t.id = m.meter_id
                      WHERE t.site_id = :s AND time > now() - make_interval(secs => :n) ORDER BY time""",
                   s=sid, n=secondes)


@app.get("/api/evenements", tags=["temps réel"])
def events(site: str = REF, limite: int = Query(20, le=500), formes_onde: bool = False):
    cols = "time, direction, delta_kw, mtype, confidence, proba" + (", waveform, gradcam" if formes_onde else "")
    return db.rows(f"""SELECT {cols} FROM event e JOIN meter t ON t.id = e.meter_id
                       WHERE t.site_id = :s ORDER BY time DESC LIMIT :n""", s=site_id(site), n=limite)


class WaveRequest(BaseModel):
    waveform: list[float] = Field(..., min_length=128, max_length=128, description="forme d'onde de 40 ms (128 points)")


@app.post("/api/gaf", tags=["temps réel"])
def gaf(req: WaveRequest):
    """Chaîne de reconnaissance d'un événement : séquences ondelette et harmoniques, puis image GAF RVB."""
    from volteye.gaf import gasf
    from volteye.signals import feature_sequences, harmonic_spectrum
    w = np.array(req.waveform, dtype=float)
    seq = feature_sequences(w)
    h = harmonic_spectrum(w)
    return {"sequences": {k: v.round(4).tolist() for k, v in seq.items()},
            "image": [gasf(seq[k]).round(3).tolist() for k in ("approximation", "detail", "harmoniques")],
            "harmoniques": (h / h[0] if h[0] > 1e-9 else h)[:15].round(4).tolist()}


@app.get("/api/solaire", tags=["prévision et planning"])
def solar():
    """Solaire en toiture : production, autoconsommation, charge nette et effet sur la pointe d'été."""
    return metric("solaire")


# --- IA avancée -------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _shap():
    path = C.ARTIFACTS / "forecast_shap.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@app.get("/api/prevision/explication", tags=["prévision et planning"])
def forecast_explanation(heure: str | None = None):
    """Explication SHAP de la prévision : poids moyen de chaque variable, et contributions pour une heure donnée."""
    data = _shap()
    if data is None:
        raise HTTPException(404, "explications SHAP absentes : relancer python -m volteye.pipeline")
    out = {"importance_moyenne_kWh": data["importance_moyenne_kWh"]}
    if heure:
        t = pd.Timestamp(heure)
        if t.tzinfo is not None:
            t = t.tz_convert("Africa/Tunis").tz_localize(None)
        h = data["par_heure"].get(str(t.floor("h")))
        if h is None:
            raise HTTPException(404, f"pas d'explication pour {heure} (période de test uniquement)")
        out["heure"] = {"time": str(t.floor("h")), **h}
    return out


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    historique: list[dict] = Field(default_factory=list, max_length=12)


@app.post("/api/assistant", tags=["assistant"])
def ask(req: AskRequest):
    """Assistant énergie : réponse en langage naturel, chaque chiffre provenant d'un outil VoltEye."""
    from agent.assistant import answer
    return answer(req.question, req.historique)


@app.get("/api/assistant/etat", tags=["assistant"])
def ask_state():
    from agent.assistant import MODEL, llm_available
    llm = llm_available()
    ev = db.scalar("SELECT data FROM metric WHERE name = :n", n="assistant_llm" if llm else "assistant")
    return {"mode": "llm" if llm else "hors ligne", "modele": MODEL if llm else None,
            "evaluation": ev["resume"] if ev else None}


@app.websocket("/ws/direct")
async def ws_live(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()                  # le client peut envoyer des « ping »
    except WebSocketDisconnect:
        hub.disconnect(ws)


@app.get("/", include_in_schema=False)
def root():
    return {"service": "VoltEye API", "documentation": "/docs", "version": __version__,
            "points_d_entree": sorted({r.path for r in app.routes if r.path.startswith("/api")})}
