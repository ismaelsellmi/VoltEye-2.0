"""Optimisation du planning des charges flexibles selon le tarif horaire STEG.

Programme linéaire en nombres entiers (PuLP / solveur HiGHS) :
  - variables : heure de démarrage de chaque tâche flexible ;
  - contraintes : fenêtre autorisée, durée d'exécution, puissance maximale souscrite ;
  - objectif : coût de l'énergie (tarif horaire) + pénalité sur la pointe journalière.
La charge de base est la prévision J+1 du site, moins les tâches flexibles.
Deux références :
  - pratique actuelle : chaque tâche est lancée en début de poste (7 h) ;
  - opérateur averti : chaque tâche démarre à l'heure la moins chère de sa fenêtre
    selon le tarif, sans coordination entre tâches ni prise en compte de la pointe.
"""
import json

import numpy as np
import pulp

from . import config as C

TASKS = [
    # nom, puissance (kW), durée (h), fenêtre de démarrage [début, fin) en heures
    {"nom": "Cuisson four - lot 1", "kW": 30, "duree": 2, "fenetre": (6, 14)},
    {"nom": "Cuisson four - lot 2", "kW": 30, "duree": 2, "fenetre": (8, 20)},
    {"nom": "Remplissage réservoir d'air", "kW": 18, "duree": 2, "fenetre": (0, 22)},
    {"nom": "Recharge des chariots élévateurs", "kW": 12, "duree": 4, "fenetre": (0, 20)},
    {"nom": "Chauffe-eau process / nettoyage", "kW": 9, "duree": 3, "fenetre": (0, 21)},
    {"nom": "Prétraitement soudage (étuvage)", "kW": 8, "duree": 2, "fenetre": (6, 20)},
]


def schedule_profile(starts):
    prof = np.zeros(24)
    for task, s in zip(TASKS, starts):
        prof[s:s + task["duree"]] += task["kW"]
    return prof


def cost(base, starts, prices):
    total = base + schedule_profile(starts)
    return float(total @ prices), float(total.max())


def tariff_aware_starts(prices):
    """Référence « opérateur averti » : heure de démarrage la moins chère de chaque fenêtre (à égalité, la plus tôt)."""
    starts = []
    for t in TASKS:
        cands = range(t["fenetre"][0], min(t["fenetre"][1], 24 - t["duree"] + 1))
        starts.append(min(cands, key=lambda s: (float(np.sum(prices[s:s + t["duree"]])), s)))
    return starts


def _bill(base, starts, prices):
    c, p = cost(base, starts, prices)
    return c + C.PEAK_DEMAND_CHARGE * p, p


def optimize(base, prices, p_max=None):
    p_max = p_max or float(base.max() + 60)
    prob = pulp.LpProblem("volteye_planning", pulp.LpMinimize)
    x = {(k, s): prob.add_variable(f"x_{k}_{s}", cat="Binary")
         for k, t in enumerate(TASKS) for s in range(t["fenetre"][0], min(t["fenetre"][1], 24 - t["duree"] + 1))}
    peak = prob.add_variable("pointe", lowBound=0)
    load = {h: base[h] + pulp.lpSum(TASKS[k]["kW"] * v for (k, s), v in x.items() if s <= h < s + TASKS[k]["duree"])
            for h in range(24)}
    prob += pulp.lpSum(load[h] * prices[h] for h in range(24)) + C.PEAK_DEMAND_CHARGE * peak
    for k in range(len(TASKS)):
        prob += pulp.lpSum(v for (kk, _), v in x.items() if kk == k) == 1
    for h in range(24):
        prob += load[h] <= peak
        prob += load[h] <= p_max
    status = prob.solve(pulp.HiGHS(msg=False))
    starts = [next(s for (kk, s), v in x.items() if kk == k and v.value() > 0.5) for k in range(len(TASKS))]
    return starts, str(status)


def run(forecast, out_dir=C.ARTIFACTS, log=print):
    """Optimise chaque jour ouvré de la période de test et résume les gains."""
    log("Optimisation : planification des charges flexibles sur la période de test…")
    days = []
    flex_energy = sum(t["kW"] * t["duree"] for t in TASKS)
    for day, g in forecast.groupby(forecast.index.date):
        if len(g) != 24 or g["reel"].sum() < 500:
            continue
        idx = g.index
        prices = np.array([C.tariff(h, m) for h, m in zip(idx.hour, idx.month)])
        base = np.clip(g["prevision"].to_numpy() - flex_energy / 24, 0, None)
        ref_starts = [max(t["fenetre"][0], 7) for t in TASKS]      # pratique actuelle : lancement en début de poste
        op_starts = tariff_aware_starts(prices)
        opt_starts, status = optimize(base, prices)
        c_ref, p_ref = cost(base, ref_starts, prices)
        c_opt, p_opt = cost(base, opt_starts, prices)
        f_op, p_op = _bill(base, op_starts, prices)
        days.append({"jour": str(day), "statut": status, "cout_ref_TND": c_ref, "cout_opt_TND": c_opt,
                     "pointe_ref_kW": p_ref, "pointe_opt_kW": p_opt, "pointe_operateur_kW": p_op,
                     "facture_ref_TND": c_ref + C.PEAK_DEMAND_CHARGE * p_ref,
                     "facture_opt_TND": c_opt + C.PEAK_DEMAND_CHARGE * p_opt, "facture_operateur_TND": f_op,
                     "base": base.tolist(), "prix": prices.tolist(), "ref": ref_starts, "opt": opt_starts,
                     "operateur": op_starts})

    def gains(ref_key, peak_key):
        g = np.array([d[ref_key] - d["facture_opt_TND"] for d in days])
        return {"gain_moyen_TND_par_jour": float(g.mean()),
                "gain_moyen_%": float(100 * np.mean([1 - d["facture_opt_TND"] / d[ref_key] for d in days])),
                "reduction_pointe_moyenne_kW": float(np.mean([d[peak_key] - d["pointe_opt_kW"] for d in days])),
                "gain_annuel_estime_TND": float(g.mean() * 290)}      # environ 290 jours ouvrés par an

    summary = {"jours_optimises": len(days), **gains("facture_ref_TND", "pointe_ref_kW"),
               "reference_operateur_averti": gains("facture_operateur_TND", "pointe_operateur_kW"),
               "taches": TASKS}
    op = summary["reference_operateur_averti"]
    log(f"  face à la pratique actuelle : {summary['gain_moyen_TND_par_jour']:.1f} TND/jour "
        f"({summary['gain_moyen_%']:.1f} %), pointe -{summary['reduction_pointe_moyenne_kW']:.1f} kW")
    log(f"  face à un opérateur averti du tarif : {op['gain_moyen_TND_par_jour']:.1f} TND/jour "
        f"({op['gain_moyen_%']:.1f} %), pointe -{op['reduction_pointe_moyenne_kW']:.1f} kW")
    (out_dir / "optimization.json").write_text(json.dumps({"resume": summary, "jours": days}, ensure_ascii=False),
                                               encoding="utf-8")
    return summary
