"""Évaluation de l'assistant énergie sur 25 questions dont la réponse est connue.

La vérité terrain est calculée par les outils VoltEye eux-mêmes ; une réponse est juste si elle contient la
bonne valeur (tolérance de 1 %, formats français ou anglais) ou le bon élément de documentation. En mode LLM,
seule une réponse rédigée par le modèle compte (une réponse de repli hors ligne est comptée fausse).
Ancrage : part des nombres de la réponse présents, à 1 % près, dans un résultat d'outil, la question ou la
consigne du modèle.

Usage : python -m agent.evaluate                    (LLM si identifiants disponibles, sinon hors ligne)
        python -m agent.evaluate --offline          (force le mode hors ligne)
        python -m agent.evaluate --questions 1,6,9  (sous-ensemble, numéros de 1 à 25)
"""
import json
import re
import sys
import time

from volteye import config as C

from . import assistant, tools

T = tools


def _top_machine_share():
    return T.indicateurs()["machines"][0]["part_%"]


CASES = [
    ("Combien la fuite d'air de février nous a-t-elle coûté, et que faut-il faire ?", "anomalies", lambda: T.anomalies("compresseur", "février")["cout_total_TND"]),
    ("Combien de jours le compresseur a-t-il été en alerte en août ?", "anomalies", lambda: T.anomalies("compresseur", "août")["jours_en_alerte"]),
    ("Combien a coûté la veille de la CNC en septembre ?", "anomalies", lambda: T.anomalies("cnc", "septembre")["cout_total_TND"]),
    ("Combien de jours d'alerte sur l'éclairage en octobre ?", "anomalies", lambda: T.anomalies("eclairage", "octobre")["jours_en_alerte"]),
    ("Combien de jours d'alerte pour le four en juin ?", "anomalies", lambda: T.anomalies("four", "juin")["jours_en_alerte"]),
    ("Quel est l'état de santé du convoyeur ?", "sante", lambda: T.sante("convoyeur")["machines"][0]["sante_sur_100"]),
    ("Combien de jours à l'avance la panne du convoyeur a-t-elle été annoncée ?", "sante", lambda: T.sante()["panne_convoyeur_anticipee_jours"]),
    ("Quelle est la santé du compresseur ?", "sante", lambda: T.sante("compresseur")["machines"][0]["sante_sur_100"]),
    ("Quelle machine consomme le plus, et quelle part de l'énergie ?", "indicateurs", _top_machine_share),
    ("Combien d'énergie l'atelier a-t-il consommée sur les 30 derniers jours ?", "indicateurs", lambda: T.indicateurs()["energie_kWh"]),
    ("Combien d'énergie est consommée hors production sur 30 jours ?", "hors_production", lambda: T.hors_production()["hors_production_kWh"]),
    ("Combien le compresseur consomme-t-il la nuit et le week-end ?", "hors_production", lambda: T.hors_production(machine="compresseur")["hors_production_kWh"]),
    ("Combien de mégawatts VoltEye Grid efface-t-il pendant la pointe d'été ?", "voltEye_grid", lambda: T.voltEye_grid()["effacement_MW"]),
    ("Pour le réseau STEG, que gagne la coordination face à une réponse au tarif seul, en MW ?", "voltEye_grid", lambda: T.voltEye_grid()["effacement_vs_tarif_seul_MW"]),
    ("Combien de MWh VoltEye Grid déplace-t-il chaque jour ?", "voltEye_grid", lambda: T.voltEye_grid()["energie_deplacee_MWh_par_jour"]),
    ("Quelle est l'erreur de la prévision du lendemain ?", "prevision", lambda: T.prevision()["erreur_moyenne_%"]),
    ("Quelle part des heures réelles tombe dans la fourchette de prévision ?", "prevision", lambda: T.prevision().get("fourchette_P10_P90_couverture_%")),
    ("Combien le planning optimisé fait-il économiser par an ?", "planning", lambda: T.planning()["gain_annuel_estime_TND"]),
    ("De combien le planning optimisé réduit-il la facture ?", "planning", lambda: T.planning()["gain_moyen_%"]),
    ("Quelle est l'exactitude de la reconnaissance des machines ?", "evaluation", lambda: T.evaluation()["reconnaissance_exactitude_%"]),
    ("Quel est le F1 de la détection des gaspillages ?", "evaluation", lambda: T.evaluation()["anomalies_F1_test"]),
    ("Quel tarif est appliqué à l'heure de pointe ?", "recherche_documentation", lambda: C.TARIFFS["pointe"]),
    ("Comment réparer une fuite d'air comprimé ?", "recherche_documentation", lambda: "ultrasons"),
    ("Comment VoltEye reconnaît-il une machine avec un seul compteur ?", "recherche_documentation", lambda: "40 ms"),
    ("Pourquoi la pointe se reforme-t-elle quand chaque usine suit le tarif ?", "recherche_documentation", lambda: "rebond"),
]


def numbers(text):
    """Nombres d'un texte, en acceptant 1 234,5 / 1234.5 / 1,234.5."""
    out = []
    for raw in re.findall(r"\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?", text):
        s = raw.replace(" ", "").replace(" ", "").replace(" ", "")
        s = s.replace(",", ".") if s.count(",") == 1 and "." not in s else s.replace(",", "")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def correct(answer, expected):
    if isinstance(expected, str):
        return tools.plain(expected) in tools.plain(answer)
    if expected is None:
        return False
    return any(abs(n - expected) <= max(0.01 * abs(expected), 0.051) for n in numbers(answer))


def anchoring(answer, context):
    """Nombres de la réponse, et ceux qui figurent (à 1 % près) dans le contexte fourni au modèle."""
    pool = numbers(context)
    nums = numbers(answer)
    found = [n for n in nums if any(abs(n - p) <= max(0.01 * abs(p), 0.051) for p in pool)]
    return nums, found


def run(offline=False, questions=None, log=print):
    if offline:
        import os
        os.environ["VOLTEYE_LLM"] = "off"
    mode = "llm" if assistant.llm_available() else "hors ligne"
    cases = [CASES[i - 1] for i in questions] if questions else CASES
    outputs, run_tool = [], assistant._run_tool

    def traced(name, args):                       # résultats d'outils vus par le modèle, pour l'ancrage
        result, is_error = run_tool(name, args)
        outputs.append(json.dumps(result, ensure_ascii=False, default=str))
        return result, is_error

    assistant._run_tool = traced
    rows, t0 = [], time.time()
    try:
        for question, tool, truth in cases:
            expected = truth()
            outputs.clear()
            t1 = time.time()
            out = assistant.answer(question)
            answered_by = "hors ligne" if out.get("avertissement") else out["mode"]
            ok = correct(out["reponse"], expected) and answered_by == mode
            routed = any(s["outil"] == tool for s in out["etapes"])
            nums, found = anchoring(out["reponse"], " ".join(outputs + [question, assistant.SYSTEM]))
            rows.append({"question": question, "outil_attendu": tool, "outils": [s["outil"] for s in out["etapes"]],
                         "attendu": expected, "reponse": out["reponse"], "mode_reponse": answered_by, "juste": ok,
                         "bon_outil": routed, "nombres": len(nums), "nombres_ancres": len(found),
                         "nombres_non_ancres": [n for n in nums if n not in found], "duree_s": round(time.time() - t1, 1)})
            log(f"{'✓' if ok else '✗'} {'·' if routed else '!'} [{answered_by}] ancrage {len(found)}/{len(nums)} {question}")
    finally:
        assistant._run_tool = run_tool
    cited = sum(r["nombres"] for r in rows)
    summary = {"mode": mode, "modele": assistant.MODEL if mode == "llm" else None, "questions": len(rows),
               "reponses_justes": sum(r["juste"] for r in rows), "bon_outil": sum(r["bon_outil"] for r in rows),
               "exactitude": sum(r["juste"] for r in rows) / len(rows),
               "reponses_du_mode_evalue": sum(r["mode_reponse"] == mode for r in rows),
               "nombres_cites": cited, "nombres_ancres": sum(r["nombres_ancres"] for r in rows),
               "taux_ancrage": round(sum(r["nombres_ancres"] for r in rows) / max(cited, 1), 3),
               "numeros_questions": questions or list(range(1, len(CASES) + 1)), "duree_s": round(time.time() - t0, 1)}
    log(f"Exactitude des chiffres : {summary['reponses_justes']}/{summary['questions']} ; bon outil : {summary['bon_outil']}/{summary['questions']} ; "
        f"nombres issus des outils : {summary['nombres_ancres']}/{cited}")
    name = "assistant_eval.json" if mode == "hors ligne" else "assistant_eval_llm.json"
    (C.ARTIFACTS / name).write_text(json.dumps({"resume": summary, "details": rows}, indent=2, ensure_ascii=False, default=str),
                                    encoding="utf-8")
    return summary


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    picked = next((a.split("=", 1)[1] if "=" in a else sys.argv[i + 1] for i, a in enumerate(sys.argv) if a.startswith("--questions")), None)
    run(offline="--offline" in sys.argv, questions=[int(x) for x in picked.split(",")] if picked else None)
