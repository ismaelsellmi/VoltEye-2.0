"""Assistant énergie VoltEye : questions en langage naturel, réponses chiffrées par les outils VoltEye.

Mode LLM : un modèle Claude (API Anthropic) choisit et appelle les outils de `agent/tools.py`, puis rédige la
réponse en ne citant que les chiffres renvoyés par les outils. Activé quand des identifiants Anthropic sont
disponibles (variable ANTHROPIC_API_KEY ou profil `ant auth login`) ; modèle : VOLTEYE_LLM_MODEL.
Mode hors ligne : un aiguillage par mots-clés appelle les mêmes outils et met en forme leurs résultats ; il
garantit une démonstration sans réseau.
"""
import json
import os
import re

from . import tools

MODEL = os.environ.get("VOLTEYE_LLM_MODEL", "claude-opus-5-5")
MAX_STEPS = 8
SYSTEM = """Tu es l'assistant énergie de VoltEye, plateforme de suivi énergétique non intrusif d'un atelier industriel
tunisien (7 machines suivies depuis un seul compteur) et de 10 zones industrielles (VoltEye Grid, pointe d'été du
réseau STEG). Réponds en français, de façon brève et concrète.

Règles :
- Chaque chiffre de ta réponse doit venir d'un outil appelé pendant cette conversation. N'invente aucune valeur.
- Pour les méthodes, hypothèses, tarifs et actions recommandées, appelle recherche_documentation.
- Utilise requete_sql seulement si aucun autre outil ne répond à la question.
- Donne les unités (kWh, TND, kg CO₂, MW, %) et la période concernée.
- Termine par l'action recommandée quand la question porte sur un problème.
- Si les données ne permettent pas de répondre, dis-le simplement.
L'historique couvre novembre 2025 à octobre 2026."""


def llm_available():
    if os.environ.get("VOLTEYE_LLM", "auto") == "off":
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_PROFILE"))


def _sources(result):
    if isinstance(result, dict):
        if "passages" in result:
            return [p["source"] for p in result["passages"]]
        if "source" in result:
            return [result["source"]]
    return []


def _run_tool(name, args):
    try:
        result = tools.call(name, args)
        return result, False
    except Exception as e:                        # erreur renvoyée au modèle, qui peut corriger son appel
        return {"erreur": str(e)}, True


def answer_llm(question, history=()):
    import anthropic
    client = anthropic.Anthropic()
    messages = [{"role": m["role"], "content": m["content"]} for m in history if m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": question})
    steps, sources = [], []
    for _ in range(MAX_STEPS):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            tools=tools.SPECS,
            messages=messages,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            return {"reponse": "Je ne peux pas répondre à cette demande. Posez une question sur l'énergie du site.",
                    "etapes": steps, "sources": sources, "mode": "llm"}
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        calls = [b for b in response.content if b.type == "tool_use"]
        if not calls:
            text = "\n".join(b.text for b in response.content if b.type == "text").strip()
            return {"reponse": text, "etapes": steps, "sources": sorted(set(sources)), "mode": "llm", "modele": response.model}
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for call in calls:
            result, is_error = _run_tool(call.name, call.input)
            steps.append({"outil": call.name, "arguments": call.input})
            sources += _sources(result)
            results.append({"type": "tool_result", "tool_use_id": call.id, "is_error": is_error,
                            "content": json.dumps(result, ensure_ascii=False, default=str)})
        messages.append({"role": "user", "content": results})
    return {"reponse": "La question demande trop d'étapes ; reformulez-la plus précisément.", "etapes": steps,
            "sources": sorted(set(sources)), "mode": "llm"}


# --- Mode hors ligne ---------------------------------------------------------------------

def _fr(x, d=0):
    if x is None:
        return "–"
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


def _machine_in(q):
    for alias, key in sorted(tools.ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in q:
            return key
    return None


def _month_in(q):
    for name in tools.MONTHS:
        if name in q:
            return name
    return None


def route(question):
    """Choisit l'outil et ses arguments à partir de mots-clés (mode hors ligne)."""
    q = tools.plain(question)
    m, month = _machine_in(q), _month_in(q)
    asks_how = re.match(r"\s*(comment|que faire|pourquoi|quel tarif|quel facteur|qu'est-ce)", q) and "combien" not in q
    if asks_how:
        return "recherche_documentation", {"question": question}
    if "fuite" in q:
        return "anomalies", {"machine": m or "compresseur", "mois": month}
    if m and month and any(w in q for w in ("cout", "alerte", "anomal", "gaspill", "veille", "combien")):
        return "anomalies", {"machine": m, "mois": month}
    if any(w in q for w in ("solaire", "photovolta", "panneau", " pv", "toiture")):
        return "solaire", {}
    if any(w in q for w in ("grid", "steg", "delestage", "mw", "megawatt", "pointe d'ete", "effac", "reseau")):
        return "voltEye_grid", {}
    if any(w in q for w in ("hors production", "la nuit", "week-end", "weekend", "veille")):
        return "hors_production", {"machine": m}
    if any(w in q for w in ("sante", "usure", "panne", "thd", "maintenance", "degrad")):
        return "sante", {"machine": m}
    if any(w in q for w in ("anomal", "gaspill", "alerte", "surconsomm", "cout")) and (m or month):
        return "anomalies", {"machine": m, "mois": month}
    if any(w in q for w in ("prevision", "demain", "lendemain", "prevoir")):
        return "prevision", {}
    if any(w in q for w in ("planning", "optimis", "facture", "econom", "decaler", "tarif horaire")):
        return "planning", {}
    if any(w in q for w in ("precision", "exactitude", "f1", "evaluation", "fiable", "performance")):
        return "evaluation", {}
    if any(w in q for w in ("consomme le plus", "repartition", "ou part", "combien consomme", "energie", "co2", "kwh")):
        return "indicateurs", {}
    return "recherche_documentation", {"question": question}


def render(name, r):
    if name == "anomalies":
        f = r["filtre"]
        if not r["jours_en_alerte"]:
            return f"{f['machine']}, {f['mois']} : 0 jour en alerte, consommation restée dans la plage attendue."
        actions = " ".join(a for a in r["actions"].values() if a)
        return (f"{f['machine']}, {f['mois']} : {r['jours_en_alerte']} jours en alerte, du {r['premier_jour']} au {r['dernier_jour']}. "
                f"Excès estimé : {_fr(r['exces_total_kWh'])} kWh, soit {_fr(r['cout_total_TND'], 1)} TND. "
                f"Causes : {', '.join(r['causes'].values())}.\nAction recommandée : {actions}")
    if name == "hors_production":
        top = r["machines"][0] if r["machines"] else None
        s = f"Sur {r['periode']}, {_fr(r['hors_production_kWh'])} kWh ont été consommés hors production (≈ {_fr(r['cout_estime_TND'])} TND)."
        if top and len(r["machines"]) > 1:
            s += f" Premier poste : {top['machine'].lower()}, {_fr(top['hors_production_kWh'])} kWh ({_fr(top['part_hors_production_%'], 1)} % de sa consommation)."
        elif top:
            s += f" {top['machine']} : {_fr(top['part_hors_production_%'], 1)} % de sa consommation."
        return s
    if name == "sante":
        lines = [f"{x['machine']} : santé {_fr(x['sante_sur_100'])}/100, dérive du THD {_fr(x['derive_THD_%'], 1)} %"
                 + (" — en alerte" if x["alerte"] else "")
                 + (f" (alerte cette année le {x['premiere_alerte_annee']})" if x["premiere_alerte_annee"] else "") for x in r["machines"]]
        return "\n".join(lines) + f"\nLa panne du convoyeur a été annoncée {r['panne_convoyeur_anticipee_jours']} jours à l'avance. Seuil : {r['seuil_alerte']}."
    if name == "voltEye_grid":
        return (f"VoltEye Grid ({r['zones']} zones, {_fr(r['usines'])} usines, {r['participation_%']:.0f} % de participation) abaisse la pointe "
                f"d'été agrégée de {_fr(r['pointe_pratique_actuelle_MW'], 1)} MW à {_fr(r['pointe_voltEye_grid_MW'], 1)} MW : "
                f"-{_fr(r['effacement_MW'], 1)} MW ({_fr(r['effacement_%'], 1)} %), et -{_fr(r['effacement_vs_tarif_seul_MW'], 1)} MW face à une "
                f"réponse au tarif non coordonnée. {_fr(r['energie_deplacee_MWh_par_jour'])} MWh sont déplacés chaque jour, sans changer l'énergie consommée.")
    if name == "prevision":
        return (f"La prévision du lendemain se trompe en moyenne de {_fr(r['erreur_moyenne_%'], 1)} % (référence : {_fr(r['reference_semaine_precedente_%'], 1)} %). "
                + (f"La fourchette P10-P90 contient {_fr(r['fourchette_P10_P90_couverture_%'], 1)} % des heures réelles." if r.get("fourchette_P10_P90_couverture_%") else ""))
    if name == "planning":
        return (f"Le planning optimisé réduit la facture des jours ouvrés de {_fr(r['gain_moyen_%'], 1)} % ({_fr(r['gain_moyen_TND_par_jour'], 1)} TND par jour, "
                f"≈ {_fr(r['gain_annuel_estime_TND'])} TND par an) et la pointe de {_fr(r['pointe_evitee_kW'])} kW. Face à un opérateur qui suit déjà "
                f"le tarif, il gagne encore {_fr(r['face_a_un_operateur_averti_%'], 1)} %.")
    if name == "solaire":
        a, b = r["achat_reseau_en_pointe_ete_kW"]
        return (f"Les {_fr(r['puissance_kWc'])} kWc en toiture produiraient {_fr(r['production_MWh_an'])} MWh par an "
                f"({_fr(r['productible_kWh_par_kWc'])} kWh/kWc), autoconsommés à {_fr(r['autoconsommation_%'])} % : ≈ {_fr(r['economie_TND_an'])} TND "
                f"économisés et {_fr(r['co2_evite_t_an'], 1)} t de CO₂ évitées par an. En pointe tarifaire d'été, l'achat au réseau passe "
                f"de {_fr(a)} kW à {_fr(b)} kW en moyenne.")
    if name == "evaluation":
        return (f"Reconnaissance des machines : {_fr(r['reconnaissance_exactitude_%'], 1)} %. Détection des gaspillages sur 4 mois jamais vus : "
                f"F1 {_fr(r['anomalies_F1_test'], 2)} (référence {_fr(r['anomalies_F1_reference'], 2)}). Prévision : {_fr(r['prevision_erreur_%'], 1)} % d'erreur."
                + (f" Sur données réelles (HIPE), signatures reconnues à {_fr(r['donnees_reelles_HIPE_reconnaissance_%'], 1)} %." if r.get("donnees_reelles_HIPE_reconnaissance_%") else ""))
    if name == "indicateurs":
        top = r["machines"][0]
        return (f"Sur {r['periode']} : {_fr(r['energie_kWh'])} kWh, ≈ {_fr(r['cout_estime_TND'])} TND et {_fr(r['co2_kg'] / 1000, 1)} t de CO₂. "
                f"Premier poste : {top['machine'].lower()} ({_fr(top['part_%'], 1)} %), puis "
                + ", ".join(f"{x['machine'].lower()} ({_fr(x['part_%'], 1)} %)" for x in r["machines"][1:3]) + ".")
    if name == "recherche_documentation":
        if not r["passages"]:
            return "Je n'ai rien trouvé dans la documentation VoltEye sur ce sujet."
        words = {w for w in re.findall(r"\w{4,}", tools.plain(r.get("question", "")))}
        text = re.sub(r"\s+", " ", r["passages"][0]["extrait"])
        sentences = re.split(r"(?<=[.:;])\s+", text)
        ranked = sorted(range(len(sentences)), key=lambda i: -len(words & set(re.findall(r"\w{4,}", tools.plain(sentences[i])))))
        keep = sorted(ranked[:3])
        return " ".join(sentences[i] for i in keep)
    return json.dumps(r, ensure_ascii=False)[:800]


def answer_offline(question):
    name, args = route(question)
    args = {k: v for k, v in args.items() if v is not None}
    result, is_error = _run_tool(name, args)
    if not is_error and name == "recherche_documentation":
        result["question"] = question
    if is_error:
        return {"reponse": f"Je n'ai pas pu répondre : {result['erreur']}", "etapes": [{"outil": name, "arguments": args}],
                "sources": [], "mode": "hors ligne"}
    return {"reponse": render(name, result), "etapes": [{"outil": name, "arguments": args}],
            "sources": _sources(result), "mode": "hors ligne"}


def answer(question, history=()):
    if llm_available():
        try:
            return answer_llm(question, history)
        except Exception as e:                    # réseau, quota ou identifiants : la démonstration continue hors ligne
            out = answer_offline(question)
            out["avertissement"] = f"LLM indisponible ({e.__class__.__name__}), réponse hors ligne."
            return out
    return answer_offline(question)
