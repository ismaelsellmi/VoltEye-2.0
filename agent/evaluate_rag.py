"""Évaluation de la recherche documentaire (RAG) sur 31 questions annotées.

Chaque question est associée aux sections de la documentation qui contiennent la réponse. Le jeu est distinct
des 4 questions documentaires de agent/evaluate.py. Trois recherches sont comparées : hybride (celle de
l'assistant), sémantique seule (pgvector) et plein texte seul (PostgreSQL, dictionnaire français).
Métriques : Recall@1, Recall@4 (une section attendue parmi les k premiers passages) et MRR.

Usage : python -m agent.evaluate_rag      (base VoltEye démarrée)
"""
import json
import re
import sys
import time

from api import db
from volteye import config as C

from . import rag

GOLD = [
    ("Quel est le prix du kWh en heure de pointe ?", ["Tarifs et hypothèses", "4. Hypothèses économiques"]),
    ("Une machine reste allumée la nuit, que dois-je faire ?", ["alerte de consommation hors production"]),
    ("Comment localiser une fuite dans le réseau d'air comprimé ?", ["fuite d'air comprimé"]),
    ("Le four a consommé beaucoup trop pendant trois heures, quelle action ?", ["pic de consommation anormal"]),
    ("La machine consomme plus que prévu pendant la production : que vérifier ?", ["surconsommation en production"]),
    ("Comment interpréter un score de santé de 70 sur 100 ?", ["Lire le score de santé"]),
    ("Quel intérêt de déplacer les cuissons vers d'autres heures ?", ["Pourquoi décaler des tâches flexibles", "6. Optimisation du planning"]),
    ("Pourquoi le réseau STEG sature-t-il l'après-midi en été ?", ["La pointe d'été du réseau"]),
    ("Comment un seul compteur permet-il d'identifier chaque équipement ?", ["avec un seul compteur"]),
    ("Quelle fréquence d'échantillonnage utilise le capteur ?", ["1. Signatures électriques", "Flux de données", "Plateforme temps réel"]),
    ("Quel est le spectre harmonique typique d'un poste de soudure ?", ["1. Signatures électriques"]),
    ("Combien d'heures dure le flux simulé de l'atelier ?", ["2. Flux temps réel", "2. Désagrégation"]),
    ("Quelles anomalies ont été injectées dans l'historique ?", ["3. Historique horaire"]),
    ("Quel facteur d'émission de CO2 est retenu ?", ["4. Hypothèses économiques", "Tarifs et hypothèses"]),
    ("D'où viennent les mesures industrielles réelles utilisées ?", ["5. Données industrielles réelles", "7. Validation sur données industrielles"]),
    ("Quelles sont les limites et le périmètre du prototype ?", ["6. Hypothèses et périmètre"]),
    ("Quelle exactitude obtient la fusion du CNN et de la forêt aléatoire ?", ["1. Reconnaissance des machines"]),
    ("Combien d'événements le détecteur a-t-il retrouvés sur le flux de 4 heures ?", ["2. Désagrégation"]),
    ("Quelle est la MAPE de la prévision du lendemain face aux références ?", ["3. Prévision J+1"]),
    ("Comment le seuil des alertes de gaspillage a-t-il été réglé ?", ["4. Détection d'anomalies"]),
    ("Combien de jours avant la panne du convoyeur l'alerte a-t-elle été donnée ?", ["5. Maintenance prédictive"]),
    ("Quel gain annuel apporte l'optimisation du planning ?", ["6. Optimisation du planning"]),
    ("Quelle part de l'énergie de l'usine HIPE est consommée hors production ?", ["7. Validation sur données industrielles"]),
    ("De combien de mégawatts la pointe agrégée baisse-t-elle avec la coordination ?", ["8. VoltEye Grid", "La pointe d'été du réseau"]),
    ("Comment la fourchette d'incertitude de la prévision est-elle calibrée ?", ["9. IA avancée"]),
    ("Combien produit l'installation photovoltaïque en toiture par an ?", ["10. Solaire en toiture"]),
    ("Quel matériel est prévu sur le site pour la passerelle ?", ["Vue en couches", "Choix techniques"]),
    ("Quelles données quittent le site et lesquelles restent sur la passerelle ?", ["Vue en couches", "Plateforme temps réel"]),
    ("Pourquoi avoir choisi MQTT et TimescaleDB ?", ["Choix techniques"]),
    ("Combien de temps prend la reconnaissance d'un événement sur processeur ?", ["Performances d'inférence"]),
    ("Faut-il un GPU pour faire tourner le réseau de neurones ?", ["Choix techniques", "Performances d'inférence"]),
]
K = 4


def _titles(rows):
    titles = {r["id"]: r["title"] for r in db.rows("SELECT id, title FROM doc_chunk")}
    return [titles[r["id"]] for r in rows]


def semantic(question, n=K):
    q = rag._vec(next(iter(rag.embedder().embed([question]))))
    return _titles(db.rows("SELECT id FROM doc_chunk ORDER BY embedding <=> CAST(:q AS vector) LIMIT :n", q=q, n=n))


def fulltext(question, n=K):
    words = " | ".join(re.findall(r"\w{4,}", question.lower()))
    return _titles(db.rows("""SELECT id FROM doc_chunk WHERE to_tsvector('french', title || ' ' || content)
                              @@ to_tsquery('french', :q)
                              ORDER BY ts_rank(to_tsvector('french', title || ' ' || content), to_tsquery('french', :q)) DESC
                              LIMIT :n""", q=words, n=n))


def hybrid(question, n=K):
    return [h["source"].split(" › ", 1)[1] for h in rag.search(question, n)]


def score(fn):
    r1 = rk = rr = 0
    misses, times = [], []
    for question, expected in GOLD:
        t0 = time.perf_counter()
        titles = fn(question)[:K]
        times.append(time.perf_counter() - t0)
        ranks = [i for i, t in enumerate(titles) if any(e.lower() in t.lower() for e in expected)]
        if ranks:
            rk += 1
            r1 += ranks[0] == 0
            rr += 1 / (ranks[0] + 1)
        else:
            misses.append(question)
    n = len(GOLD)
    times.sort()
    return {"Recall@1": round(r1 / n, 3), f"Recall@{K}": round(rk / n, 3), "MRR": round(rr / n, 3),
            "latence_mediane_ms": round(1000 * times[n // 2], 1), "manquees": misses}


def run(log=print):
    rag.sync(log=lambda *a: None)
    results = {"questions": len(GOLD), "passages_indexes": db.scalar("SELECT count(*) FROM doc_chunk"),
               "methodes": {"VoltEye - hybride (sémantique + plein texte + couverture)": score(hybrid),
                            "Variante - sémantique seule (pgvector)": score(semantic),
                            "Baseline - plein texte seul (PostgreSQL)": score(fulltext)}}
    for name, m in results["methodes"].items():
        log(f"{name} : Recall@1 {m['Recall@1']:.3f} · Recall@{K} {m[f'Recall@{K}']:.3f} · MRR {m['MRR']:.3f} · {m['latence_mediane_ms']} ms")
    (C.ARTIFACTS / "rag_eval.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run()
