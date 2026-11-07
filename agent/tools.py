"""Outils VoltEye partagés par l'assistant énergie et le serveur MCP.

Chaque outil lit la base TimescaleDB (les mêmes données que l'application) et renvoie un dictionnaire
sérialisable en JSON, accompagné de sa source. L'assistant ne cite que des chiffres renvoyés par ces outils.
"""
import json
import unicodedata
from datetime import date

from api import db
from volteye import config as C
from volteye.signals import CLASSES, MACHINE_TYPES

SITE = "usine-ref"
ALIASES = {
    "four": "four", "etuve": "four", "compresseur": "compresseur", "air comprime": "compresseur",
    "cnc": "cnc", "usinage": "cnc", "convoyeur": "convoyeur", "eclairage": "eclairage", "lumiere": "eclairage",
    "led": "eclairage", "soudage": "soudage", "poste a souder": "soudage", "cvc": "cvc", "climatisation": "cvc", "clim": "cvc",
}
MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
          "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
CAUSES = {"hors_production": "consommation hors production", "production": "surconsommation en production",
          "pic": "pic horaire anormal", "sous_consommation": "arrêt ou sous-consommation"}


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def machine_key(name):
    if not name:
        return None
    n = plain(name)
    if n in CLASSES:
        return n
    for alias, key in sorted(ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in n:
            return key
    raise ValueError(f"machine inconnue : {name}. Machines suivies : {', '.join(CLASSES)}")


def month_key(mois):
    """« février », « 2026-02 » ou « 02/2026 » vers « AAAA-MM » (l'historique couvre nov. 2025 à oct. 2026)."""
    if not mois:
        return None
    m = plain(str(mois)).strip()
    if len(m) == 7 and m[4] == "-":
        return m
    for name, k in MONTHS.items():
        if name in m:
            year = 2025 if k >= 11 else 2026
            return f"{year}-{k:02d}"
    raise ValueError(f"mois non reconnu : {mois}")


def _label(m):
    return MACHINE_TYPES[m].label


def _sid():
    return db.scalar("SELECT id FROM site WHERE code = :c", c=SITE)


def _r(x, d=1):
    return None if x is None else round(float(x), d)


# --- Outils ---------------------------------------------------------------------------

def indicateurs(jours: int = 30):
    """Énergie, coût et CO₂ de l'atelier sur les derniers jours, et répartition par machine."""
    sid = _sid()
    end = db.scalar("SELECT max(time) FROM machine_load WHERE site_id = :s", s=sid)
    rows = db.rows("""SELECT mtype, sum(kwh) AS kwh FROM machine_load WHERE site_id = :s
                      AND time > :end - make_interval(days => :d) GROUP BY mtype ORDER BY kwh DESC""", s=sid, end=end, d=jours)
    total = sum(r["kwh"] for r in rows)
    return {"periode": f"{jours} jours jusqu'au {end.date()}", "energie_kWh": _r(total, 0),
            "cout_estime_TND": _r(total * C.TARIFFS["jour"], 0), "co2_kg": _r(total * C.EMISSION_FACTOR, 0),
            "machines": [{"machine": _label(r["mtype"]), "cle": r["mtype"], "energie_kWh": _r(r["kwh"], 0),
                          "part_%": _r(100 * r["kwh"] / total, 1)} for r in rows],
            "source": "base VoltEye, énergie horaire désagrégée"}


def hors_production(jours: int = 30, machine: str | None = None):
    """Énergie consommée hors des heures de production (nuits, week-ends, jours fériés), par machine."""
    sid, m = _sid(), machine_key(machine)
    end = db.scalar("SELECT max(time) FROM machine_load WHERE site_id = :s", s=sid)
    sql = """SELECT l.mtype, sum(l.kwh) FILTER (WHERE NOT c.production) AS hors, sum(l.kwh) AS total
             FROM machine_load l JOIN context_hourly c ON c.time = l.time AND c.site_id = l.site_id
             WHERE l.site_id = :s AND l.time > :end - make_interval(days => :d)"""
    if m:
        sql += " AND l.mtype = :m"
    rows = db.rows(sql + " GROUP BY l.mtype ORDER BY hors DESC", s=sid, end=end, d=jours, m=m)
    hors = sum(r["hors"] or 0 for r in rows)
    return {"periode": f"{jours} jours jusqu'au {end.date()}", "hors_production_kWh": _r(hors, 0),
            "cout_estime_TND": _r(hors * C.TARIFFS["nuit"], 0),
            "machines": [{"machine": _label(r["mtype"]), "hors_production_kWh": _r(r["hors"], 0),
                          "part_hors_production_%": _r(100 * (r["hors"] or 0) / r["total"], 1) if r["total"] else None} for r in rows],
            "source": "base VoltEye, énergie horaire désagrégée et calendrier de production"}


def anomalies(machine: str | None = None, mois: str | None = None):
    """Gaspillages détectés (jours en alerte) avec cause, coût de l'excès et action recommandée."""
    m, mk = machine_key(machine), month_key(mois)
    sql = """SELECT day, mtype, score, cause, excess_cost_tnd, energy_kwh - coalesce(expected_kwh, energy_kwh) AS exces
             FROM anomaly WHERE site_id = :s AND alert"""
    if m:
        sql += " AND mtype = :m"
    if mk:
        sql += " AND to_char(day, 'YYYY-MM') = :mk"
    rows = db.rows(sql + " ORDER BY day", s=_sid(), m=m, mk=mk)
    recos = (db.scalar("SELECT data FROM metric WHERE name = 'anomalies'") or {}).get("recommandations", {})
    causes = sorted({r["cause"] for r in rows if r["cause"]})
    return {"filtre": {"machine": _label(m) if m else "toutes", "mois": mk or "toute la période"},
            "jours_en_alerte": len(rows), "cout_total_TND": _r(sum(r["excess_cost_tnd"] or 0 for r in rows), 1),
            "exces_total_kWh": _r(sum(max(r["exces"] or 0, 0) for r in rows), 0),
            "premier_jour": str(rows[0]["day"]) if rows else None, "dernier_jour": str(rows[-1]["day"]) if rows else None,
            "causes": {c: CAUSES.get(c, c) for c in causes}, "actions": {CAUSES.get(c, c): recos.get(c) for c in causes},
            "detail": [{"jour": str(r["day"]), "machine": _label(r["mtype"]), "cause": CAUSES.get(r["cause"], r["cause"]),
                        "cout_TND": _r(r["excess_cost_tnd"], 1)} for r in rows[:15]],
            "source": "détection d'anomalies VoltEye (consommation attendue réentraînée chaque mois, score robuste)"}


def sante(machine: str | None = None):
    """État de santé des machines : score sur 100, dérive de la distorsion harmonique (THD), alerte, première alerte."""
    m = machine_key(machine)
    sql = "SELECT DISTINCT ON (mtype) mtype, day, health, drift, alert, days_left FROM health WHERE site_id = :s"
    if m:
        sql += " AND mtype = :m"
    rows = db.rows(sql + " ORDER BY mtype, day DESC", s=_sid(), m=m)
    maint = (db.scalar("SELECT data FROM metric WHERE name = 'anomalies'") or {}).get("maintenance", {})
    return {"machines": [{"machine": _label(r["mtype"]), "date": str(r["day"]), "sante_sur_100": _r(r["health"], 0),
                          "derive_THD_%": _r(100 * (r["drift"] or 0), 1), "alerte": bool(r["alert"]),
                          "premiere_alerte_annee": maint.get(r["mtype"], {}).get("premiere_alerte")} for r in rows],
            "panne_convoyeur_anticipee_jours": maint.get("anticipation_panne_convoyeur_jours"),
            "seuil_alerte": "dérive du THD de +25 % par rapport à la référence de la machine",
            "source": "maintenance prédictive VoltEye (suivi du THD)"}


def prevision(jour: str | None = None):
    """Prévision de la consommation horaire du lendemain : qualité du modèle, ou détail d'un jour de la période de test."""
    fm = db.scalar("SELECT data FROM metric WHERE name = 'prevision'") or {}
    out = {"erreur_moyenne_%": _r(fm["models"]["VoltEye - gradient boosting"]["MAPE_%_heures_actives"], 1),
           "reference_semaine_precedente_%": _r(fm["models"]["Baseline - même heure semaine précédente"]["MAPE_%_heures_actives"], 1),
           "periode_test": fm.get("periode_test"), "source": "prévision J+1 VoltEye (gradient boosting)"}
    if fm.get("quantiles"):
        out["fourchette_P10_P90_couverture_%"] = _r(100 * fm["quantiles"]["couverture_P10_P90"], 1)
    if jour:
        r = db.rows("""SELECT sum(p50) AS p50, sum(actual) AS reel, sum(p10) AS p10, sum(p90) AS p90, max(p50) AS pic
                       FROM forecast WHERE site_id = :s AND (time AT TIME ZONE 'Africa/Tunis')::date = :d""", s=_sid(), d=jour)[0]
        if r["p50"] is None:
            raise ValueError(f"pas de prévision pour le {jour} (période de test : {fm.get('periode_test')})")
        out["jour"] = {"date": jour, "prevision_kWh": _r(r["p50"], 0), "reel_kWh": _r(r["reel"], 0),
                       "fourchette_kWh": [_r(r["p10"], 0), _r(r["p90"], 0)], "pic_horaire_prevu_kWh": _r(r["pic"], 1)}
    return out


def planning(jour: str | None = None):
    """Planning optimisé des tâches flexibles : gains sur la facture face à la pratique actuelle et à un opérateur averti."""
    res = db.scalar("SELECT data FROM metric WHERE name = 'optimisation'") or {}
    out = {"jours_optimises": res.get("jours_optimises"), "gain_moyen_%": _r(res.get("gain_moyen_%"), 1),
           "gain_moyen_TND_par_jour": _r(res.get("gain_moyen_TND_par_jour"), 1),
           "gain_annuel_estime_TND": _r(res.get("gain_annuel_estime_TND"), 0),
           "pointe_evitee_kW": _r(res.get("reduction_pointe_moyenne_kW"), 0),
           "face_a_un_operateur_averti_%": _r((res.get("reference_operateur_averti") or {}).get("gain_moyen_%"), 1),
           "source": "optimiseur VoltEye (programme linéaire en nombres entiers, HiGHS)"}
    if jour:
        d = db.scalar("SELECT data FROM schedule_day WHERE day = :d", d=jour)
        if d is None:
            raise ValueError(f"pas de planning pour le {jour}")
        out["jour"] = {"date": jour, "facture_actuelle_TND": _r(d["facture_ref_TND"], 0), "facture_optimisee_TND": _r(d["facture_opt_TND"], 0),
                       "pointe_actuelle_kW": _r(d["pointe_ref_kW"], 0), "pointe_optimisee_kW": _r(d["pointe_opt_kW"], 0),
                       "demarrages_optimises_h": d["opt"]}
    return out


def voltEye_grid():
    """VoltEye Grid : réduction de la pointe d'été agrégée de 10 zones industrielles grâce à la flexibilité coordonnée."""
    g = db.scalar("SELECT data FROM metric WHERE name = 'grid'") or {}
    zones = db.scalar("SELECT data FROM metric WHERE name = 'zones'") or []
    pm = g.get("pointe_moyenne_MW", {})
    return {"zones": g.get("zones"), "usines": g.get("usines"), "participation_%": _r(100 * g.get("participation", 0), 0),
            "pointe_pratique_actuelle_MW": _r(pm.get("pratique_actuelle")), "pointe_tarif_seul_MW": _r(pm.get("tarif_seul")),
            "pointe_voltEye_grid_MW": _r(pm.get("voltEye_grid")), "effacement_MW": _r(g.get("effacement_MW_vs_pratique")),
            "effacement_%": _r(g.get("effacement_%_vs_pratique")), "effacement_vs_tarif_seul_MW": _r(g.get("effacement_MW_vs_tarif_seul")),
            "energie_deplacee_MWh_par_jour": _r(g.get("energie_deplacee_MWh_jour"), 0), "jours_evalues": g.get("jours_evalues"),
            "zones_les_plus_flexibles": [{"zone": z["site"], "flexibilite_MW": _r(z["flexibilite_MW"])}
                                         for z in sorted(zones, key=lambda z: -z["flexibilite_MW"])[:3]],
            "source": "module VoltEye Grid (prévision J+1 par zone et programme linéaire)"}


def solaire():
    """Solaire en toiture du site : production annuelle, autoconsommation, économies, CO₂ évité, effet sur la pointe d'été."""
    s = db.scalar("SELECT data FROM metric WHERE name = 'solaire'") or {}
    if not s:
        raise ValueError("résultats solaires absents")
    return {"puissance_kWc": s["installation"]["kWc"], "production_MWh_an": _r(s["production_MWh_an"], 0),
            "productible_kWh_par_kWc": _r(s["productible_kWh_kWc"], 0), "autoconsommation_%": _r(s["autoconsommation_%"], 0),
            "part_des_besoins_couverte_%": _r(s["autoproduction_%"], 0), "economie_TND_an": _r(s["economie_TND_an"], 0),
            "co2_evite_t_an": _r(s["co2_evite_t_an"], 1),
            "achat_reseau_en_pointe_ete_kW": [_r(s["pointe_tarifaire_ete"]["achat_moyen_sans_pv_kW"], 0), _r(s["pointe_tarifaire_ete"]["achat_moyen_avec_pv_kW"], 0)],
            "source": "modèle photovoltaïque VoltEye (position du soleil, ciel clair, clarté mensuelle de Tunis)"}


def evaluation():
    """Résultats d'évaluation des modèles d'IA (données jamais vues, comparés à des références simples)."""
    e = {r["name"]: r["data"] for r in db.rows("SELECT name, data FROM metric WHERE name IN ('reconnaissance','anomalies','prevision','hipe')")}
    out = {"reconnaissance_exactitude_%": _r(100 * e["reconnaissance"]["models"]["D - VoltEye : fusion CNN GAF + spectre FFT"]["accuracy"], 1),
           "anomalies_F1_test": _r(e["anomalies"]["models"]["VoltEye - résidus + score robuste (MAD)"]["f1"], 2),
           "anomalies_F1_reference": _r(e["anomalies"]["models"]["Baseline - z-score énergie journalière"]["f1"], 2),
           "prevision_erreur_%": _r(e["prevision"]["models"]["VoltEye - gradient boosting"]["MAPE_%_heures_actives"], 1),
           "source": "évaluation VoltEye (docs/resultats.md)"}
    if "hipe" in e:
        out["donnees_reelles_HIPE_reconnaissance_%"] = _r(100 * e["hipe"]["signatures"]["VoltEye - + THD et harmoniques + forêt aléatoire"]["exactitude"], 1)
    return out


def recherche_documentation(question: str, k: int = 4):
    """Recherche dans la documentation approuvée de VoltEye (méthodes, hypothèses, tarifs, recommandations)."""
    from .rag import search
    hits = search(question, k)
    return {"passages": hits, "source": "documentation VoltEye"}


def requete_sql(requete: str):
    """Requête SELECT en lecture seule sur la base VoltEye (50 lignes au plus)."""
    rows = db.safe_select(requete, limit=50)
    return {"lignes": json.loads(json.dumps(rows, default=str)), "source": "base VoltEye (lecture seule)"}


TOOLS = {f.__name__: f for f in [indicateurs, hors_production, anomalies, sante, prevision, planning, voltEye_grid,
                                  solaire, evaluation, recherche_documentation, requete_sql]}

_machine = {"type": "string", "description": "machine : four, compresseur, cnc, convoyeur, eclairage, soudage ou cvc (climatisation)"}
SPECS = [
    {"name": "indicateurs", "description": indicateurs.__doc__,
     "input_schema": {"type": "object", "properties": {"jours": {"type": "integer", "description": "nombre de jours (30 par défaut)"}}}},
    {"name": "hors_production", "description": hors_production.__doc__,
     "input_schema": {"type": "object", "properties": {"jours": {"type": "integer"}, "machine": _machine}}},
    {"name": "anomalies", "description": anomalies.__doc__,
     "input_schema": {"type": "object", "properties": {"machine": _machine, "mois": {"type": "string", "description": "mois, par exemple « février » ou « 2026-02 » (historique : novembre 2025 à octobre 2026)"}}}},
    {"name": "sante", "description": sante.__doc__, "input_schema": {"type": "object", "properties": {"machine": _machine}}},
    {"name": "prevision", "description": prevision.__doc__,
     "input_schema": {"type": "object", "properties": {"jour": {"type": "string", "description": "date AAAA-MM-JJ dans la période de test"}}}},
    {"name": "planning", "description": planning.__doc__,
     "input_schema": {"type": "object", "properties": {"jour": {"type": "string", "description": "date AAAA-MM-JJ d'un jour ouvré optimisé"}}}},
    {"name": "voltEye_grid", "description": voltEye_grid.__doc__, "input_schema": {"type": "object", "properties": {}}},
    {"name": "solaire", "description": solaire.__doc__, "input_schema": {"type": "object", "properties": {}}},
    {"name": "evaluation", "description": evaluation.__doc__, "input_schema": {"type": "object", "properties": {}}},
    {"name": "recherche_documentation", "description": recherche_documentation.__doc__,
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    {"name": "requete_sql", "description": requete_sql.__doc__ + " Tables : site, machine, machine_load (time, site_id, mtype, kwh, thd), "
     "context_hourly (time, site_id, temperature, production, holiday, ramadan), anomaly (day, site_id, mtype, energy_kwh, expected_kwh, "
     "score, alert, cause, excess_cost_tnd), health (day, site_id, mtype, thd, drift, health, alert), forecast (time, site_id, p10, p50, p90, actual), "
     "measurement, event. Le site de référence a site_id = 1.",
     "input_schema": {"type": "object", "properties": {"requete": {"type": "string"}}, "required": ["requete"]}},
]


def call(name, args):
    if name not in TOOLS:
        raise ValueError(f"outil inconnu : {name}")
    return TOOLS[name](**(args or {}))


def today():
    return date.today().isoformat()
