"""Génère le pitch (livrables/VoltEye_Pitch.pptx), avec les notes de l'orateur pour 3 minutes.

Usage : python livrables/generer_pitch.py
"""
import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
A, F, CAP = ROOT / "artifacts", ROOT / "docs" / "figures", ROOT / "docs" / "captures"
OUT = ROOT / "livrables" / "VoltEye_Pitch.pptx"

NAVY, BLUE, YELLOW = RGBColor(0x0E, 0x1B, 0x33), RGBColor(0x2A, 0x6F, 0xDB), RGBColor(0xF2, 0xC1, 0x4E)
WHITE, GREY, DARK, GREEN = RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x6B, 0x72, 0x80), RGBColor(0x1F, 0x29, 0x37), RGBColor(0x29, 0xA3, 0x6A)


def J(n):
    return json.loads((A / n).read_text(encoding="utf-8"))


rm, sm, fm, am, om, city = (J("recognition_metrics.json"), J("stream_metrics.json"), J("forecast_metrics.json"),
                            J("anomaly_metrics.json"), J("optimization.json")["resume"], J("city_sites.json"))
D = rm["models"]["D - VoltEye : fusion CNN GAF + spectre FFT"]
A_ = rm["models"]["A - Mesures classiques + forêt aléatoire"]
fV, fW = fm["models"]["VoltEye - gradient boosting"], fm["models"]["Baseline - même heure semaine précédente"]
aV, aZ = am["models"]["VoltEye - résidus + score robuste (MAD)"], am["models"]["Baseline - z-score énergie journalière"]
lead = am["maintenance"]["anticipation_panne_convoyeur_jours"]
fr = lambda x, d=1: f"{x:,.{d}f}".replace(",", " ").replace(".", ",")

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
W, H = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


def text(slide, x, y, w, h, s, size=18, color=DARK, bold=False, align=PP_ALIGN.LEFT, font="Calibri"):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold, color, font
        p.space_after = Pt(6)
    return tb


def rect(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line:
        s.line.color.rgb = line
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def header(slide, title, kicker, n):
    rect(slide, 0, 0, W, Inches(1.15), NAVY)
    rect(slide, 0, Inches(1.15), W, Inches(0.06), YELLOW)
    text(slide, Inches(0.6), Inches(0.12), Inches(9), Inches(0.4), kicker.upper(), 12, YELLOW, True)
    text(slide, Inches(0.6), Inches(0.42), Inches(11.5), Inches(0.7), title, 28, WHITE, True)
    text(slide, Inches(11.6), Inches(0.42), Inches(1.3), Inches(0.5), f"⚡ {n}/9", 14, YELLOW, True, PP_ALIGN.RIGHT)


def card(slide, x, y, w, h, big, small, color=BLUE):
    rect(slide, x, y, w, h, RGBColor(0xF3, 0xF6, 0xFB), shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.08
    rect(slide, x, y, Inches(0.09), h, color)
    text(slide, x + Inches(0.25), y + Inches(0.12), w - Inches(0.35), Inches(0.75), big, 30, color, True)
    text(slide, x + Inches(0.25), y + Inches(0.85), w - Inches(0.35), h - Inches(0.9), small, 13, DARK)


def picture(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(str(path), x, y, w, h)


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


# 1. Titre ----------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, W, H, NAVY)
rect(s, 0, Inches(5.05), W, Inches(0.06), YELLOW)
text(s, Inches(0.8), Inches(1.3), Inches(11), Inches(0.5), "SMART CITY CHALLENGE 2026 · TRACK 2 : INTELLIGENT ENERGY", 14, YELLOW, True)
text(s, Inches(0.8), Inches(1.9), Inches(11), Inches(1.4), "⚡👁️ VoltEye", 72, WHITE, True)
text(s, Inches(0.8), Inches(3.35), Inches(11.5), Inches(0.7), "See the invisible energy of smart cities.", 30, YELLOW)
text(s, Inches(0.8), Inches(4.15), Inches(11.5), Inches(0.6), "Un seul capteur. Toutes les machines. Des villes plus intelligentes.", 20, WHITE)
text(s, Inches(0.8), Inches(5.5), Inches(11.5), Inches(1), ["Équipe VoltEye · [noms des membres]", "Partenaire industriel : STEG"], 16, RGBColor(0xC8, 0xD3, 0xE6))
notes(s, "[0:00 - 0:10] Bonjour, nous sommes l'équipe VoltEye. Notre slogan : See the invisible energy of smart cities.")

# 2. Problème ------------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
header(s, "Cette usine gaspille de l'énergie. Personne ne le voit.", "Le problème", 2)
items = [("🌙", "Veille hors production", "machines et éclairage restés sous tension la nuit et le week-end"),
         ("💨", "Fuites d'air comprimé", "le compresseur tourne pour rien, jour et nuit"),
         ("⚙️", "Dégradation silencieuse", "un moteur usé consomme plus… jusqu'à la panne"),
         ("⏰", "Mauvais horaires", "charges lancées aux heures chères, pointes de puissance")]
for k, (ico, t, d) in enumerate(items):
    x = Inches(0.6 + (k % 2) * 6.15)
    y = Inches(1.6 + (k // 2) * 1.75)
    rect(s, x, y, Inches(5.9), Inches(1.5), RGBColor(0xF3, 0xF6, 0xFB), shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + Inches(0.2), y + Inches(0.25), Inches(0.9), Inches(0.9), ico, 34)
    text(s, x + Inches(1.1), y + Inches(0.2), Inches(4.7), Inches(0.5), t, 20, NAVY, True)
    text(s, x + Inches(1.1), y + Inches(0.7), Inches(4.7), Inches(0.8), d, 14, GREY)
rect(s, Inches(0.6), Inches(5.3), Inches(12.1), Inches(1.6), NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, Inches(0.9), Inches(5.45), Inches(11.6), Inches(1.4),
     ["Aujourd'hui : une seule facture mensuelle pour des dizaines de machines.",
      "Un compteur par machine ? Coûteux, arrêts de production, équipements certifiés à modifier."], 18, WHITE)
notes(s, "[0:10 - 0:35] Dans une usine, rien n'a l'air cassé, et pourtant l'énergie fuit : machines en veille la nuit, "
         "fuites d'air comprimé, moteurs qui s'usent, cuissons lancées à l'heure de pointe. Le responsable ne voit qu'une "
         "facture mensuelle. Et poser un compteur sur chaque machine coûte cher et impose des arrêts.")

# 3. Solution ------------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
header(s, "Un seul point de mesure. L'IA reconnaît chaque machine.", "La solution", 3)
steps = [("🏭", "Machines", "aucune modification"), ("🔌", "1 capteur", "arrivée électrique"),
         ("🧠", "Edge IA", "Raspberry Pi 5 < 100 $"), ("☁️", "Cloud", "NB-IoT / 5G"), ("📊", "Décisions", "usine · ville · STEG")]
for k, (ico, t, d) in enumerate(steps):
    x = Inches(0.6 + k * 2.5)
    rect(s, x, Inches(1.65), Inches(2.15), Inches(1.9), RGBColor(0xF3, 0xF6, 0xFB), BLUE, MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x, Inches(1.75), Inches(2.15), Inches(0.7), ico, 32, align=PP_ALIGN.CENTER)
    text(s, x, Inches(2.5), Inches(2.15), Inches(0.5), t, 18, NAVY, True, PP_ALIGN.CENTER)
    text(s, x, Inches(2.95), Inches(2.15), Inches(0.5), d, 12, GREY, align=PP_ALIGN.CENTER)
    if k < 4:
        text(s, x + Inches(2.13), Inches(2.25), Inches(0.4), Inches(0.6), "➜", 24, YELLOW, True)
services = [("VOIR", "kW, TND, CO₂ par machine"), ("DÉTECTER", "gaspillages expliqués"), ("ANTICIPER", "pannes moteur"),
            ("PRÉVOIR", "consommation J+1"), ("OPTIMISER", "planning × tarif horaire")]
for k, (t, d) in enumerate(services):
    x = Inches(0.6 + k * 2.5)
    rect(s, x, Inches(4.1), Inches(2.15), Inches(1.4), NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x, Inches(4.25), Inches(2.15), Inches(0.5), t, 18, YELLOW, True, PP_ALIGN.CENTER)
    text(s, x + Inches(0.1), Inches(4.75), Inches(1.95), Inches(0.7), d, 13, WHITE, align=PP_ALIGN.CENTER)
text(s, Inches(0.6), Inches(5.9), Inches(12), Inches(1), "Sans capteur sur les machines · sans arrêt de production · déployable dans toute la ville", 18, BLUE, True, PP_ALIGN.CENTER)
notes(s, "[0:35 - 0:55] VoltEye mesure le courant en un seul point, à l'arrivée électrique. Une passerelle à moins de 100 dollars "
         "fait tourner l'IA sur place. Résultat : on voit chaque machine, on détecte, on anticipe, on prévoit et on optimise.")

# 4. IA --------------------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
header(s, "Chaque machine a une empreinte : l'IA la transforme en image", "Approche technique", 4)
picture(s, F / "fig_gaf_pipeline.png", Inches(0.4), Inches(1.45), w=Inches(8.3))
for k, (t, d) in enumerate([("1. Événement", "une machine démarre : on isole le courant « après − avant »"),
                            ("2. Signal", "ondelette db4 (forme, transitoires) + spectre harmonique (FFT)"),
                            ("3. Image", "Gramian Angular Field : 3 images fusionnées en RVB"),
                            ("4. Décision", "CNN + grandeurs électriques, fusionné avec une forêt aléatoire")]):
    y = Inches(1.5 + k * 1.3)
    rect(s, Inches(8.95), y, Inches(4.0), Inches(1.15), RGBColor(0xF3, 0xF6, 0xFB), shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(9.1), y + Inches(0.08), Inches(3.8), Inches(0.4), t, 16, BLUE, True)
    text(s, Inches(9.1), y + Inches(0.45), Inches(3.8), Inches(0.7), d, 12, DARK)
text(s, Inches(0.5), Inches(6.75), Inches(12.3), Inches(0.5),
     "+ prévision J+1 (gradient boosting) · anomalies (résidus + score robuste) · santé moteur (dérive du THD) · optimisation (MILP HiGHS)", 13, GREY)
notes(s, "[0:55 - 1:20] Chaque technologie déforme le courant à sa manière : un four est une sinusoïde pure, un variateur de CNC "
         "crée des harmoniques 5 et 7. Quand une machine démarre, on isole sa signature, on la décompose en ondelettes et en "
         "harmoniques, on la transforme en image avec le Gramian Angular Field, et un réseau convolutif la reconnaît.")

# 5. Démo --------------------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
header(s, "Démo : un capteur, toutes les machines, en temps réel", "Prototype fonctionnel", 5)
picture(s, CAP / "surveillance.jpg", Inches(0.4), Inches(1.45), w=Inches(6.3))
picture(s, CAP / "reconnaissance.jpg", Inches(6.85), Inches(1.45), w=Inches(6.1))
rect(s, Inches(4.4), Inches(5.65), Inches(4.5), Inches(0.8), YELLOW, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, Inches(4.4), Inches(5.75), Inches(4.5), Inches(0.6), "▶  DÉMO EN DIRECT", 24, NAVY, True, PP_ALIGN.CENTER)
text(s, Inches(0.5), Inches(6.6), Inches(12.3), Inches(0.6),
     "Tableau de bord Streamlit : 8 pages · surveillance · reconnaissance · anomalies · prévision · optimisation · vue ville · évaluation", 13, GREY, align=PP_ALIGN.CENTER)
notes(s, "[1:20 - 2:05] DÉMO EN DIRECT (45 s). 1) Surveillance en direct : lancer la lecture ; montrer le signal unique et la "
         "désagrégation par machine ; un événement apparaît, avec son image GAF et la machine reconnue. 2) Page Reconnaissance : "
         "choisir « Machine CNC », montrer la chaîne signal → images → décision ; monter le bruit, le modèle tient. "
         "3) Anomalies : la fuite d'air du compresseur, chiffrée en TND et CO₂. Plan B : vidéo de démonstration.")

# 6. Résultats ---------------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
header(s, "Des résultats mesurés, comparés à des baselines", "Évaluation", 6)
cards = [(fr(100 * D["accuracy"]) + " %", f"reconnaissance de 7 types de machines (baseline : {fr(100 * A_['accuracy'])} %)", BLUE),
         (fr(100 * sm["precision_energetique"]) + " %", "précision énergétique de la désagrégation (4 h de flux)", BLUE),
         ("MAPE " + fr(fV["MAPE_%_heures_actives"]) + " %", f"prévision J+1 (baseline : {fr(fW['MAPE_%_heures_actives'])} %)", BLUE),
         ("F1 " + fr(aV["f1"], 2), f"détection d'anomalies, précision {fr(aV['precision'], 2)} (baseline : F1 {fr(aZ['f1'], 2)})", GREEN),
         (f"{lead} jours", "d'avance sur une panne moteur, 0 fausse alerte", GREEN),
         ("−" + fr(om["gain_moyen_%"]) + " %", f"sur la facture des jours ouvrés, −{fr(om['reduction_pointe_moyenne_kW'], 0)} kW de pointe", GREEN)]
for k, (big, small, c) in enumerate(cards):
    card(s, Inches(0.6 + (k % 3) * 4.1), Inches(1.6 + (k // 3) * 2.35), Inches(3.85), Inches(2.1), big, small, c)
text(s, Inches(0.6), Inches(6.45), Inches(12.2), Inches(0.8),
     "Données de test jamais vues à l'entraînement · simulateur physique documenté (règlement : données simulées autorisées) · résultats reproductibles",
     13, GREY, align=PP_ALIGN.CENTER)
notes(s, "[2:05 - 2:30] Tous nos résultats sont mesurés sur des données de test et comparés à des baselines : 98 % de "
         "reconnaissance contre 91 % avec les mesures classiques ; une prévision deux fois plus précise que la baseline ; "
         "des alertes fiables à 98 % ; une panne anticipée près d'un mois à l'avance ; et 12 % d'économie sur la facture "
         "grâce au planning optimisé.")

# 7. Impact ------------------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
header(s, "De l'usine à la ville intelligente", "Impact", 7)
picture(s, F / "fig_anomalies.png", Inches(0.4), Inches(1.45), w=Inches(6.6))
tot = lambda k: sum(c[k] for c in city)
imp = am["impact_anomalies_detectees"]
rows = [("Par site", f"≈ {fr(imp['TND'] + om['gain_annuel_estime_TND'], 0)} TND/an économisés", "matériel < 1 000 TND"),
        ("10 sites de zones industrielles", f"{fr(tot('gaspillage_detecte_MWh_an'), 0)} MWh de gaspillage détectés", f"{fr(tot('co2_evitable_t_an'))} t CO₂ évitables/an"),
        ("Pour le réseau (STEG)", "vue de la charge industrielle", "pointes réduites, effacement possible")]
for k, (t, a, b) in enumerate(rows):
    y = Inches(1.55 + k * 1.6)
    rect(s, Inches(7.25), y, Inches(5.7), Inches(1.4), NAVY if k == 1 else RGBColor(0xF3, 0xF6, 0xFB), shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    col = WHITE if k == 1 else DARK
    text(s, Inches(7.45), y + Inches(0.1), Inches(5.4), Inches(0.4), t, 15, YELLOW if k == 1 else BLUE, True)
    text(s, Inches(7.45), y + Inches(0.48), Inches(5.4), Inches(0.9), [a, b], 14, col)
text(s, Inches(0.5), Inches(6.55), Inches(12.3), Inches(0.6),
     "Chaque alerte est chiffrée en kWh, TND et CO₂, avec une recommandation d'action", 15, BLUE, True, PP_ALIGN.CENTER)
notes(s, "[2:30 - 2:50] Pour un site, ce sont des milliers de dinars par an, pour moins de 1 000 dinars de matériel. "
         "Déployé sur les zones industrielles de la ville, VoltEye donne au distributeur une vue de la charge industrielle "
         "et des tonnes de CO2 évitables.")

# 8. Feuille de route --------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
header(s, "Prochaines étapes", "Feuille de route", 8)
road = [("Mois 1", "Pilote sur un atelier", "capteur triphasé réel + Raspberry Pi 5, validation avec compteurs de référence"),
        ("Mois 2-3", "Industrialisation", "apprentissage des nouvelles machines, alertes mobiles, tarifs STEG officiels"),
        ("Mois 4-6", "Zone industrielle", "10 sites connectés, vue ville, partenariat avec le distributeur"),
        ("Ensuite", "Pilotage", "effacement automatique aux heures de pointe, assistant IA sur les données du site")]
for k, (when, t, d) in enumerate(road):
    x = Inches(0.6 + k * 3.1)
    rect(s, x, Inches(1.8), Inches(2.85), Inches(0.6), YELLOW if k == 0 else BLUE, shape=MSO_SHAPE.CHEVRON)
    text(s, x, Inches(1.85), Inches(2.85), Inches(0.5), when, 16, NAVY if k == 0 else WHITE, True, PP_ALIGN.CENTER)
    text(s, x, Inches(2.65), Inches(2.85), Inches(0.5), t, 18, NAVY, True)
    text(s, x, Inches(3.2), Inches(2.85), Inches(1.6), d, 14, GREY)
rect(s, Inches(0.6), Inches(5.1), Inches(12.1), Inches(1.5), RGBColor(0xF3, 0xF6, 0xFB), shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, Inches(0.9), Inches(5.25), Inches(11.6), Inches(1.3),
     ["Limites assumées : données simulées (pilote réel = étape 1), machines identiques en parallèle, événements simultanés.",
      "Ce que nous demandons : un site pilote et l'accès aux grilles tarifaires et facteurs d'émission officiels."], 15, DARK)
notes(s, "[2:50 - 2:58] Prochaine étape : un pilote réel d'un mois sur un atelier, puis une zone industrielle complète.")

# 9. Fin -----------------------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, W, H, NAVY)
text(s, Inches(0.8), Inches(1.8), Inches(11.7), Inches(1.3), "If you can't see it, you can't control it.", 40, WHITE, True, PP_ALIGN.CENTER)
text(s, Inches(0.8), Inches(3.2), Inches(11.7), Inches(1.2), "⚡👁️ VoltEye", 60, YELLOW, True, PP_ALIGN.CENTER)
text(s, Inches(0.8), Inches(4.5), Inches(11.7), Inches(0.7), "See the invisible energy of smart cities.", 26, WHITE, align=PP_ALIGN.CENTER)
text(s, Inches(0.8), Inches(5.8), Inches(11.7), Inches(0.6), "Merci · Questions ?", 20, RGBColor(0xC8, 0xD3, 0xE6), align=PP_ALIGN.CENTER)
notes(s, "[2:58 - 3:00] If you can't see it, you can't control it. VoltEye : See the invisible energy of smart cities. Merci !")

prs.save(OUT)
print(f"Pitch enregistré : {OUT}")
