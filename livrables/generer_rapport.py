"""Génère le rapport technique (livrables/VoltEye_Rapport_Technique.docx) à partir des résultats.

Usage : python livrables/generer_rapport.py
"""
import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
A, F = ROOT / "artifacts", ROOT / "docs" / "figures"
OUT = ROOT / "livrables" / "VoltEye_Rapport_Technique.docx"
BLUE = RGBColor(0x1F, 0x4E, 0xA8)


def J(name):
    return json.loads((A / name).read_text(encoding="utf-8"))


rm, sm, fm, am = J("recognition_metrics.json"), J("stream_metrics.json"), J("forecast_metrics.json"), J("anomaly_metrics.json")
om = J("optimization.json")["resume"]
city = J("city_sites.json")
pct = lambda x, d=1: f"{100 * x:.{d}f}".replace(".", ",") + " %"
num = lambda x, d=0: f"{x:,.{d}f}".replace(",", " ").replace(".", ",")

doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21)
sec.left_margin = sec.right_margin = Cm(2.0)
sec.top_margin = sec.bottom_margin = Cm(1.8)

st = doc.styles["Normal"]
st.font.name, st.font.size = "Calibri", Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
st.paragraph_format.space_after = Pt(4)
st.paragraph_format.line_spacing = 1.1
for lvl, size in [(1, 15), (2, 12)]:
    h = doc.styles[f"Heading {lvl}"]
    h.font.name, h.font.size, h.font.bold, h.font.color.rgb = "Calibri", Pt(size), True, BLUE
    h.element.rPr.rFonts.set(qn("w:asciiTheme"), "")
    h.paragraph_format.space_before, h.paragraph_format.space_after = Pt(10 if lvl == 1 else 6), Pt(4)
    h.paragraph_format.keep_with_next = True


def P(text, bold_prefix=None, italic=False, align=None, size=None):
    p = doc.add_paragraph()
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    r = p.add_run(text)
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    if align:
        p.alignment = align
    return p


def B(items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        if isinstance(it, tuple):
            p.add_run(it[0]).bold = True
            p.add_run(it[1])
        else:
            p.add_run(it)
        p.paragraph_format.space_after = Pt(1)


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    s = OxmlElement("w:shd")
    s.set(qn("w:val"), "clear")
    s.set(qn("w:color"), "auto")
    s.set(qn("w:fill"), color)
    tcPr.append(s)


def T(rows, widths, bold_last=False):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.width = Cm(widths[j])
            c.text = ""
            run = c.paragraphs[0].add_run(str(val))
            run.font.size = Pt(9)
            c.paragraphs[0].paragraph_format.space_after = Pt(0)
            if i == 0:
                run.bold = True
                shade(c, "DCE6F5")
            if bold_last and i == len(rows) - 1:
                run.bold = True
                shade(c, "EAF5EA")
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return t


def FIG(name, caption, width=16.5):
    doc.add_picture(str(F / name), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    P(caption, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=9)


models = rm["models"]
mA, mB = models["A - Mesures classiques + forêt aléatoire"], models["B - Spectre FFT + forêt aléatoire"]
mC, mD = models["C - Ondelettes + GAF + CNN"], models["D - VoltEye : fusion CNN GAF + spectre FFT"]
fV = fm["models"]["VoltEye - gradient boosting"]
fW = fm["models"]["Baseline - même heure semaine précédente"]
fD = fm["models"]["Baseline - même heure la veille"]
aV = am["models"]["VoltEye - résidus + score robuste (MAD)"]
aI = am["models"]["Variante - résidus + Isolation Forest"]
aZ = am["models"]["Baseline - z-score énergie journalière"]
mt = am["maintenance"]
imp = am["impact_anomalies_detectees"]

# --- Page de titre --------------------------------------------------------------
P("Smart City Challenge 2026 · Track 2 : Smart City for Intelligent Energy", align=WD_ALIGN_PARAGRAPH.CENTER, size=10)
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("VoltEye")
r.bold, r.font.size, r.font.color.rgb = True, Pt(34), BLUE
P("See the invisible energy of smart cities", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=13)
P("Intelligence énergétique non intrusive pour les sites industriels : un seul point de mesure, "
  "l'IA reconnaît chaque machine, détecte les gaspillages, anticipe les pannes et optimise le planning.",
  align=WD_ALIGN_PARAGRAPH.CENTER)
P("Rapport technique · Équipe VoltEye · novembre 2026", align=WD_ALIGN_PARAGRAPH.CENTER, size=9)

doc.add_heading("Résumé", 2)
P(f"Les industriels ne voient leur consommation qu'à travers la facture mensuelle : les machines laissées "
  f"sous tension, les fuites d'air comprimé, les moteurs qui se dégradent et les charges lancées à l'heure de "
  f"pointe restent invisibles. VoltEye mesure le courant en un seul point de l'atelier et utilise l'IA pour "
  f"reconstituer la consommation de chaque machine, sans capteur sur les équipements ni arrêt de production. "
  f"Le MVP, évalué sur des données simulées documentées, reconnaît 7 types de machines industrielles avec "
  f"{pct(mD['accuracy'])} d'exactitude (ondelettes, images GAF, CNN), reconstitue l'énergie par machine avec "
  f"{pct(sm['precision_energetique'])} de précision, prévoit la consommation du lendemain avec un MAPE de "
  f"{pct(fV['MAPE_%_heures_actives'] / 100)}, détecte les gaspillages avec un F1 de {num(aV['f1'], 2)}"
  f", signale une panne moteur {mt['anticipation_panne_convoyeur_jours']} jours à l'avance et réduit la facture "
  f"des jours ouvrés de {pct(om['gain_moyen_%'] / 100)} par l'optimisation du planning selon le tarif horaire.")
T([["Fonction", "Méthode", "Résultat (test)", "Baseline"],
   ["Reconnaissance", "Ondelettes + GAF + CNN, fusion avec forêt aléatoire FFT", pct(mD["accuracy"]), pct(mA["accuracy"])],
   ["Désagrégation", "Détection d'événements + reconnaissance", pct(sm["precision_energetique"]) + " énergie", "—"],
   ["Prévision J+1", "Gradient boosting", "MAPE " + pct(fV["MAPE_%_heures_actives"] / 100), "MAPE " + pct(fW["MAPE_%_heures_actives"] / 100)],
   ["Anomalies", "Résidus + score robuste (MAD)", f"F1 {aV['f1']:.2f}".replace(".", ","), f"F1 {aZ['f1']:.2f}".replace(".", ",")],
   ["Maintenance", "Dérive du THD", f"{mt['anticipation_panne_convoyeur_jours']} jours d'avance", "—"],
   ["Optimisation", "MILP (HiGHS)", "-" + pct(om["gain_moyen_%"] / 100) + " facture", "lancement à 7 h"]],
  [3, 6.5, 3.5, 3])

# --- 1. Problème --------------------------------------------------------------
doc.add_heading("1. Problème et contexte", 1)
P("L'industrie est l'un des premiers consommateurs d'électricité des villes tunisiennes. Dans un atelier, "
  "la consommation se répartit entre des dizaines d'équipements (fours, compresseurs, machines à commande "
  "numérique, convoyeurs, éclairage, soudage, climatisation), mais elle n'est connue qu'en un seul total, "
  "mensuel, sur la facture du distributeur. Il en résulte quatre pertes invisibles :")
B([("Gaspillage hors production : ", "machines laissées sous tension la nuit ou le week-end, éclairage oublié."),
   ("Pertes de ressources : ", "fuites d'air comprimé, qui font tourner le compresseur en permanence."),
   ("Dégradation silencieuse : ", "un moteur usé consomme plus et déforme le courant avant de tomber en panne."),
   ("Mauvais placement horaire : ", "des charges flexibles (cuisson, recharge, remplissage) lancées en début de "
    "poste, souvent à des heures plus chères, ce qui crée des pointes de puissance.")])
P("Pourquoi ce n'est pas résolu : poser un compteur sur chaque machine coûte cher, impose des arrêts de "
  "production et des modifications d'équipements souvent certifiés, et produit des données que personne "
  "n'analyse. La question posée par VoltEye est donc : comment rendre visible et pilotable l'énergie de "
  "chaque machine sans toucher aux machines ?")
P("Utilisateurs : le responsable énergie et maintenance du site (alertes, priorités), la direction (coûts, "
  "CO₂), et à l'échelle de la ville le distributeur d'énergie et les collectivités (vue de la charge "
  "industrielle, effacement aux heures de pointe).", bold_prefix="Pour qui ? ")

# --- 2. Solution ----------------------------------------------------------------
doc.add_heading("2. Solution proposée : VoltEye", 1)
P("VoltEye repose sur la surveillance non intrusive de la charge (NILM, Non-Intrusive Load Monitoring) : un "
  "capteur unique mesure le courant à l'arrivée électrique de l'atelier. Chaque machine a une signature "
  "électrique propre, liée à sa technologie : une résistance absorbe un courant sinusoïdal pur, un moteur "
  "un courant déphasé, un variateur de vitesse un courant riche en harmoniques de rangs 5 et 7, un poste de "
  "soudage à onduleur un courant très déformé (rang 3). Quand une machine démarre ou s'arrête, la variation "
  "du courant total porte sa signature : l'IA la reconnaît.")
FIG("fig_signatures.png", "Figure 1 : signatures des 7 types de machines du MVP (courant et spectre harmonique).", 13.5)
P("À partir de cette désagrégation, VoltEye fournit cinq services :")
B([("Voir : ", "consommation, coût et CO₂ de chaque machine en temps réel."),
   ("Détecter : ", "gaspillages et comportements anormaux, chacun expliqué et chiffré en kWh, TND et CO₂."),
   ("Anticiper : ", "score de santé des moteurs à partir de la dérive harmonique, avant la panne."),
   ("Prévoir : ", "consommation horaire du lendemain."),
   ("Optimiser : ", "planning des charges flexibles selon le tarif horaire et la puissance souscrite.")])
P("Innovation : l'association d'un point de mesure unique, de la transformation du signal en image (GAF) "
  "et d'un CNN léger, exécutable sur une passerelle à moins de 100 $, rend la sous-mesure accessible aux PME "
  "industrielles et déployable à l'échelle d'une ville.", bold_prefix="")

# --- 3. Architecture -------------------------------------------------------------
doc.add_heading("3. Architecture du système", 1)
T([["Couche", "Rôle", "MVP", "Déploiement"],
   ["Charge", "Machines du site", "7 machines simulées", "Machines réelles, non modifiées"],
   ["Terminal (edge)", "Mesure V/I, détection d'événements, reconnaissance IA", "Simulateur + PC", "Capteur triphasé + Raspberry Pi 5"],
   ["Réseau", "Remontée des événements et indicateurs", "—", "NB-IoT, 4G/5G"],
   ["Cloud", "Historique, prévision, anomalies, optimisation, vue ville", "Python + Parquet", "Serveur + MongoDB"],
   ["Présentation", "Tableau de bord, alertes", "Streamlit (8 pages)", "Web + notifications"]],
  [2.7, 5.8, 3.5, 5])
P("Les formes d'onde brutes restent sur la passerelle : seuls les événements reconnus et les indicateurs "
  "agrégés (quelques ko par heure) sont envoyés au cloud, ce qui limite la bande passante et protège les "
  "données de production. Le choix d'un Raspberry Pi 5 plutôt que d'un module GPU se justifie par la taille "
  "du modèle (moins de 30 000 paramètres) : l'inférence prend moins d'une milliseconde par événement sur CPU.")
P("Technologies : Python 3.12, NumPy, pandas, PyWavelets (ondelettes), PyTorch (CNN), scikit-learn (forêts "
  "aléatoires, gradient boosting, Isolation Forest), PuLP et HiGHS (optimisation), Streamlit et Plotly "
  "(tableau de bord). Le code est organisé en modules indépendants (signaux, GAF, reconnaissance, flux, "
  "historique, prévision, anomalies, optimisation, ville) orchestrés par un pipeline unique et reproductible.",
  bold_prefix="")

# --- 4. Données -------------------------------------------------------------------
doc.add_heading("4. Données et méthodologie de simulation", 1)
P("Le règlement autorise les données simulées. Faute de données industrielles réelles disponibles, VoltEye "
  "s'appuie sur un simulateur physique dont tous les paramètres sont documentés (docs/donnees.md) :")
B([("Signatures : ", "réseau 400 V / 50 Hz légèrement déformé, échantillonnage 3,2 kHz ; pour chaque type de "
    "machine, plage de puissance, facteur de puissance et spectre harmonique typiques de sa technologie, avec "
    "une variabilité par machine (amplitudes ±40 %, phases ±0,35 rad) et une hausse des harmoniques à faible charge."),
   ("Imperfections de mesure : ", "bruit capteur, soustraction imparfaite du fond (2 à 12 % d'une autre machine), gigue."),
   ("Flux d'atelier : ", f"4 h à 1 mesure/s, 7 machines aux cycles réalistes, {sm['evenements_reels']} changements d'état."),
   ("Historique : ", "un an horaire (8 760 h), postes de travail, jours fériés tunisiens, Ramadan, température de Tunis."),
   ("Anomalies étiquetées : ", "veille excessive (CNC), fuites d'air (compresseur), dégradation puis panne "
    "(convoyeur), pics (four), éclairage allumé le week-end : la vérité terrain permet de mesurer chaque modèle.")])
P("Hypothèses à confirmer : facteur d'émission du réseau tunisien (0,50 kg CO₂/kWh) et grille tarifaire "
  "horaire industrielle (nuit 0,210 / jour 0,295 / pointe 0,430 TND/kWh), à remplacer par les valeurs "
  "officielles STEG et ANME.")

# --- 5. Méthodologie IA ---------------------------------------------------------------
doc.add_heading("5. Méthodologie IA et justification des choix", 1)
doc.add_heading("5.1 Reconnaissance des machines : ondelettes, GAF et CNN", 2)
P("Pour chaque événement, la forme d'onde « après − avant » est décrite par trois séquences : les "
  "coefficients d'approximation et de détail d'une ondelette de Daubechies (db4), qui capturent la forme "
  "générale et les variations rapides, et le contenu harmonique (FFT, rangs 1 à 31). Chaque séquence est "
  "transformée en image par le Gramian Angular Field : normalisation dans [-1, 1], passage en coordonnées "
  "polaires (φ = arccos x), puis GASF(i, j) = cos(φi + φj). Les trois images sont fusionnées dans les canaux "
  "rouge, vert et bleu d'une image 32×32. Un CNN de trois blocs convolutifs extrait les motifs de l'image ; "
  "les grandeurs électriques (P, Q, facteur de puissance, THD) sont injectées dans sa tête de classification. "
  "Enfin, ses probabilités sont moyennées avec celles d'une forêt aléatoire entraînée sur le spectre.")
FIG("fig_gaf_pipeline.png", "Figure 2 : du courant d'une machine CNC à l'image GAF couleur analysée par le CNN.", 15)
P("Pourquoi ce choix : le GAF encode les relations entre tous les instants du signal, ce qui permet au CNN "
  "d'exploiter la forme d'onde complète plutôt que quelques indicateurs. La méthode s'inspire de travaux "
  "publiés sur la reconnaissance de charges par images GAF. Nous l'avons comparée à deux baselines plus "
  "simples, et la fusion a été retenue parce qu'elle donne le meilleur résultat (section 6).")
doc.add_heading("5.2 Désagrégation par événements", 2)
P("Une marche de puissance est détectée lorsque l'écart entre les médianes des trois secondes avant et après "
  "un instant dépasse 0,8 kW (avec suppression des non-maxima). La signature isolée est classée, l'état de la "
  "machine reconnue est mis à jour (marche ou arrêt) et sa puissance estimée par l'amplitude de la marche.")
doc.add_heading("5.3 Prévision de la consommation à J+1", 2)
P("Un modèle de gradient boosting (HistGradientBoosting) prévoit la consommation horaire du lendemain à partir "
  "du calendrier (heure, jour, poste, jours fériés, Ramadan), de la température prévue (bruitée pour simuler "
  "une prévision météo) et de retards d'au moins 24 h, seules informations disponibles la veille. Il gère "
  "nativement les interactions non linéaires et s'entraîne en quelques secondes.")
doc.add_heading("5.4 Détection d'anomalies et maintenance prédictive", 2)
P("Pour chaque machine, un modèle de « consommation attendue » (gradient boosting, perte absolue, robuste aux "
  "anomalies présentes dans l'historique) est appris sur le calendrier et la température. Quatre indicateurs "
  "journaliers sont calculés sur les résidus : excès en production, excès hors production, pic horaire et creux "
  "horaire. Chaque indicateur est exprimé en écarts robustes (médiane et MAD, avec un plancher d'échelle) et "
  "une journée est signalée au-delà de 6. L'indicateur dominant donne la cause et la recommandation. Pour la "
  "maintenance, la moyenne glissante sur 7 jours du THD de chaque machine est comparée à sa référence : une "
  "dérive de +25 % déclenche une alerte, et la pente sur 21 jours estime le nombre de jours avant le seuil "
  "critique (+100 %).")
doc.add_heading("5.5 Optimisation du planning", 2)
P("Six tâches flexibles (cuissons, remplissage du réservoir d'air, recharge des chariots, chauffe-eau, étuvage) "
  "sont planifiées par un programme linéaire en nombres entiers : une variable binaire par heure de démarrage "
  "possible, des contraintes de fenêtre, de durée et de puissance souscrite, et un objectif égal au coût de "
  "l'énergie au tarif horaire plus une pénalité sur la pointe journalière. La charge de base vient de la "
  "prévision J+1. Le solveur libre HiGHS trouve l'optimum en moins d'une seconde.")

# --- 6. Résultats --------------------------------------------------------------------
doc.add_heading("6. Tests, résultats et évaluation", 1)
P("Toutes les métriques sont calculées sur des données jamais vues à l'entraînement, avec une graine "
  "aléatoire fixée (résultats reproductibles), et chaque modèle est comparé à au moins une baseline.")
doc.add_heading("6.1 Reconnaissance des machines", 2)
P(f"{rm['n_train']} événements d'entraînement, {rm['n_val']} de validation, {rm['n_test']} de test, plus un "
  f"test de robustesse avec un bruit triplé.")
T([["Approche", "Exactitude", "F1 macro", "Bruit x3", "ms/évén."]] +
  [[k.split(" - ")[0] + " : " + k.split(" - ")[1][:38], pct(v["accuracy"]), f"{v['f1_macro']:.3f}".replace(".", ","),
    pct(v["accuracy_bruit_x3"]), f"{v['ms_par_evenement']:.2f}".replace(".", ",")] for k, v in models.items()],
  [7.8, 2.2, 2.0, 2.2, 1.8], bold_last=True)
FIG("fig_recognition.png", "Figure 3 : comparaison des approches et matrice de confusion du modèle retenu.", 16)
P(f"Les mesures classiques confondent des machines de même puissance ({pct(mA['accuracy'])}). Le spectre "
  f"harmonique apporte l'essentiel de l'information ({pct(mB['accuracy'])}). Le CNN sur images GAF obtient un "
  f"score proche ({pct(mC['accuracy'])}) mais il est plus robuste au bruit ({pct(mC['accuracy_bruit_x3'])} contre "
  f"{pct(mB['accuracy_bruit_x3'])}). La fusion cumule les deux avantages : {pct(mD['accuracy'])} en conditions "
  f"nominales et {pct(mD['accuracy_bruit_x3'])} avec un bruit triplé. Les seules confusions notables opposent "
  f"le compresseur et le convoyeur, deux moteurs asynchrones aux signatures proches.")
doc.add_heading("6.2 Désagrégation du flux", 2)
P(f"Sur 4 h de fonctionnement, {sm['evenements_detectes']} événements sont détectés pour {sm['evenements_reels']} "
  f"réels (précision {num(sm['detection_precision'], 2)}, rappel {num(sm['detection_rappel'], 2)}), "
  f"{pct(sm['classification_exactitude'])} sont attribués à la bonne machine et l'énergie de chaque machine "
  f"est reconstituée avec une précision énergétique de {pct(sm['precision_energetique'])} (métrique NILM standard).")
FIG("fig_stream.png", "Figure 4 : signal unique mesuré (haut) et consommation par machine reconstituée (bas).", 15)
doc.add_heading("6.3 Prévision J+1", 2)
T([["Modèle (60 jours de test)", "MAE (kWh/h)", "RMSE", "MAPE"],
   ["Baseline : même heure la veille", num(fD['MAE_kWh'], 2), num(fD['RMSE_kWh'], 2), pct(fD["MAPE_%_heures_actives"] / 100)],
   ["Baseline : même heure la semaine précédente", num(fW['MAE_kWh'], 2), num(fW['RMSE_kWh'], 2), pct(fW["MAPE_%_heures_actives"] / 100)],
   ["VoltEye : gradient boosting", num(fV['MAE_kWh'], 2), num(fV['RMSE_kWh'], 2), pct(fV["MAPE_%_heures_actives"] / 100)]],
  [8, 2.8, 2.5, 2.5], bold_last=True)
FIG("fig_forecast.png", "Figure 5 : prévision horaire à J+1 sur deux semaines de la période de test.", 15)
doc.add_heading("6.4 Anomalies et maintenance", 2)
T([["Approche (2 555 jours-machine)", "Précision", "Rappel", "F1"],
   ["Baseline : z-score de l'énergie journalière", num(aZ['precision'], 2), num(aZ['rappel'], 2), num(aZ['f1'], 2)],
   ["Variante : résidus + Isolation Forest", num(aI['precision'], 2), num(aI['rappel'], 2), num(aI['f1'], 2)],
   ["VoltEye : résidus + score robuste", num(aV['precision'], 2), num(aV['rappel'], 2), num(aV['f1'], 2)]],
  [8.5, 2.5, 2.5, 2.3], bold_last=True)
rt = am["rappel_par_type"]
P(f"Rappel par type : veille {pct(rt['veille']['rappel_volteye'], 0)}, pics {pct(rt['pic']['rappel_volteye'], 0)}, "
  f"panne {pct(rt['panne']['rappel_volteye'], 0)}, éclairage du week-end {pct(rt['eclairage_weekend']['rappel_volteye'], 0)}, "
  f"fuite d'air {pct(rt['fuite_air']['rappel_volteye'], 0)} (les premiers jours d'une fuite naissante ne sont pas "
  f"signalés ; elle est détectée pendant sa montée). Avec une précision de {num(aV['precision'], 2)}, presque chaque "
  f"alerte est utile, condition indispensable pour qu'un responsable de maintenance s'y fie. Les gaspillages "
  f"détectés représentent {num(imp['kWh_gaspilles_detectes'])} kWh, {num(imp['TND'])} TND et "
  f"{num(imp['kg_CO2'] / 1000, 1)} t de CO₂ par an pour un seul site. La dérive harmonique du convoyeur est "
  f"signalée le {mt['convoyeur']['premiere_alerte']}, {mt['anticipation_panne_convoyeur_jours']} jours avant "
  f"la panne, sans fausse alerte sur les autres machines.")
FIG("fig_anomalies.png", "Figure 6 : détection d'une fuite d'air comprimé (haut) et anticipation d'une panne moteur (bas).", 15)
doc.add_heading("6.5 Optimisation", 2)
P(f"Sur {om['jours_optimises']} jours ouvrés de test, le planning optimisé réduit la facture journalière de "
  f"{pct(om['gain_moyen_%'] / 100)} en moyenne ({num(om['gain_moyen_TND_par_jour'], 1)} TND par jour) et la "
  f"pointe de {num(om['reduction_pointe_moyenne_kW'])} kW par rapport à la pratique actuelle (toutes les tâches "
  f"lancées en début de poste), soit environ {num(om['gain_annuel_estime_TND'])} TND par an pour le site.")
FIG("fig_optimization.png", "Figure 7 : planning actuel et planning optimisé face au tarif horaire.", 14)
doc.add_heading("6.6 Tests logiciels", 2)
P("Des tests automatisés (tests/test_volteye.py) vérifient la cohérence physique (puissance mesurée égale à la "
  "puissance simulée à 5 % près), la différenciation des signatures, les dimensions et bornes des images GAF, "
  "la détection d'événements et les plages tarifaires. Les 8 pages du tableau de bord ont été vérifiées dans "
  "un navigateur.")

# --- 7. Impact ----------------------------------------------------------------
doc.add_heading("7. Impact attendu et pertinence pour le track", 1)
tot = lambda k: sum(s[k] for s in city)
P(f"Pour un site de référence de 7 machines (un atelier, environ 300 MWh par an), "
  f"VoltEye identifie environ {num(imp['TND'])} TND de gaspillage et {num(om['gain_annuel_estime_TND'])} TND "
  f"d'économies de planification par an, pour un matériel inférieur à 1 000 TND par site. Extrapolé à 10 sites "
  f"de zones industrielles tunisiennes (Ben Arous, Charguia, Sfax, Sousse, Bizerte…), le gisement atteint "
  f"{num(tot('gaspillage_detecte_MWh_an'))} MWh de gaspillage et {num(tot('co2_evitable_t_an'), 1)} t de CO₂ "
  f"évitables par an, plus la réduction des pointes de puissance sur le réseau.")
P("Pertinence pour le Track 2 : VoltEye couvre les objectifs du track. Il prévoit la demande (5.3), détecte "
  "les anomalies et les explique (5.4), assure la maintenance prédictive (THD), optimise sous contraintes "
  "(5.5) et transforme des données complexes en recommandations chiffrées dans un tableau de bord d'aide à la "
  "décision, dans un contexte tunisien (calendrier, tarifs horaires, zones industrielles).")
P("Indicateurs de suivi en conditions réelles : kWh et TND économisés, t de CO₂ évitées, réduction de la "
  "pointe en kW, pannes anticipées, taux d'alertes confirmées par les techniciens.")

# --- 8. Limites ----------------------------------------------------------------
doc.add_heading("8. Limites et prochaines étapes", 1)
B([("Données simulées : ", "les performances réelles seront plus faibles. Étape 1 : pilote de 4 semaines sur un "
    "atelier, avec quelques compteurs de référence temporaires pour l'étiquetage et la validation."),
   ("Machines identiques : ", "deux machines du même modèle fonctionnant en parallèle ne se distinguent pas par "
    "leur signature ; solution : contexte de production ou second point de mesure."),
   ("Événements simultanés : ", "non traités dans le MVP ; solution : séparation de sources ou fenêtres plus courtes."),
   ("Hypothèses tarifaires : ", "tarifs et facteur d'émission à remplacer par les valeurs officielles."),
   ("Prochaines étapes : ", "capteur triphasé réel et passerelle Raspberry Pi 5, apprentissage incrémental des "
    "nouvelles machines, pilotage automatique des charges (effacement), assistant conversationnel fondé sur les "
    "données du site, et intégration multi-sites avec le distributeur d'énergie.")])

doc.add_heading("Références", 2)
for ref in ["G. W. Hart, « Nonintrusive appliance load monitoring », Proceedings of the IEEE, 80(12), 1992.",
            "Z. Wang, T. Oates, « Imaging time-series to improve classification and imputation », IJCAI, 2015.",
            "F. T. Liu, K. M. Ting, Z.-H. Zhou, « Isolation Forest », IEEE ICDM, 2008.",
            "Q. Huangfu, J. A. J. Hall, « Parallelizing the dual revised simplex method », Math. Prog. Computation, 2018.",
            "Article source de la chaîne ondelettes → GAF → CNN pour la reconnaissance de charges (référence à compléter par l'équipe).",
            "Code source, données et résultats : dépôt GitHub VoltEye (README, docs/architecture.md, docs/donnees.md, docs/resultats.md)."]:
    p = doc.add_paragraph(ref, style="List Number")
    p.paragraph_format.space_after = Pt(1)
    p.runs[0].font.size = Pt(9)

# pied de page avec numéro
fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = fp.add_run("VoltEye · Rapport technique · page ")
run.font.size = Pt(8)
for kind, text in [("begin", None), (None, "PAGE"), ("end", None)]:
    r = fp.add_run()
    r.font.size = Pt(8)
    if kind:
        e = OxmlElement("w:fldChar")
        e.set(qn("w:fldCharType"), kind)
    else:
        e = OxmlElement("w:instrText")
        e.set(qn("xml:space"), "preserve")
        e.text = text
    r._r.append(e)

doc.save(OUT)
print(f"Rapport enregistré : {OUT}")
