# Données : sources, hypothèses et limites

Le règlement autorise les données « publiques, fournies, simulées ou synthétiques » à condition de
documenter sources, hypothèses, prétraitements et limites. VoltEye repose sur un **simulateur physique**
dont tous les paramètres sont dans le code (`volteye/signals.py`, `stream.py`, `history.py`, `config.py`),
et il est validé sur une semaine de **mesures industrielles réelles** (jeu public HIPE, section 5).

## 1. Signatures électriques des machines (`signals.py`)

- Réseau 400 V triphasé, 50 Hz, tension légèrement déformée (2 % de rang 5).
- Échantillonnage 3,2 kHz (64 points par période), fenêtre d'analyse de 2 périodes (40 ms).
- 7 types de machines, chacun défini par une plage de puissance, un facteur de puissance de déplacement et
  un spectre harmonique typique de sa technologie :

| Type | Puissance | FP | Harmoniques dominants |
|---|---|---|---|
| Four / étuve résistif | 15–40 kW | 0,98–1,00 | quasi aucun |
| Compresseur d'air (moteur asynchrone) | 11–30 kW | 0,78–0,87 | faibles (3, 5, 7) |
| Machine CNC (variateur de vitesse) | 5–25 kW | 0,92–0,97 | 5 et 7 forts, 11, 13 (redresseur 6 pulses) |
| Convoyeur (moteur direct) | 3–11 kW | 0,72–0,84 | faibles |
| Éclairage LED | 2–8 kW | 0,90–0,96 | 3 et 5 (alimentations à découpage) |
| Poste de soudage (onduleur) | 5–20 kW | 0,66–0,80 | 3 très fort, 5, 7, 9 |
| CVC (compresseur inverter) | 8–25 kW | 0,93–0,98 | 5 et 7 |

- **Variabilité** : chaque machine tire ses paramètres autour de ceux de sa classe (amplitudes harmoniques
  ±40 %, phases ±0,35 rad), et les harmoniques augmentent à faible charge pour les électroniques de puissance.
- **Imperfections de mesure** : bruit capteur (2 % du crête), soustraction imparfaite du fond (2 à 12 % du
  courant d'une autre machine), gigue de synchronisation d'un échantillon.
- Jeux : 4 900 événements d'entraînement, 1 050 de validation, 2 100 de test, 1 050 de test « bruit x3 ».

## 2. Flux temps réel d'un atelier (`stream.py`)

- 7 machines (une par type), 4 heures, 1 mesure par seconde, cycles marche/arrêt propres à chaque machine
  (par exemple soudage : 1–4 min de marche, 2–8 min d'arrêt).
- 194 changements d'état réels ; les machines restent à charge constante pendant un cycle.
- Bruit de mesure de puissance : 0,15 kW.

## 3. Historique horaire d'un an (`history.py`)

- Du 1er novembre 2025 au 31 octobre 2026, soit 8 760 heures.
- Production : du lundi au vendredi de 6 h à 22 h (2 postes), le samedi de 6 h à 14 h ; le Ramadan réduit le
  travail jusqu'à 16 h ; arrêt les jours fériés tunisiens (les fêtes religieuses sont à des dates approximatives).
- Température de Tunis : cycle saisonnier (moyenne 19 °C, ±8 °C), cycle journalier (±5 °C) et aléas.
- La consommation de chaque machine dépend de la production, de la température (CVC, compresseur) et d'un bruit.

**Anomalies injectées (vérité terrain)**

| Anomalie | Machine | Occurrences |
|---|---|---|
| Veille excessive la nuit | CNC | 3 épisodes (18 jours) |
| Fuite d'air comprimé (progressive) | Compresseur | 2 épisodes (33 jours) |
| Dégradation du moteur (THD +160 %, énergie +15 %), puis panne | Convoyeur | 42 jours puis 2 jours d'arrêt |
| Pic de consommation (régulation défaillante) | Four | 10 épisodes de 3 h |
| Éclairage allumé tout le week-end | Éclairage | 2 week-ends |

## 4. Hypothèses économiques et environnementales (`config.py`)

| Paramètre | Valeur utilisée | Statut |
|---|---|---|
| Facteur d'émission du réseau | 0,50 kg CO₂/kWh | Indicatif, à confirmer (ANME / STEG) |
| Tarif horaire industriel | nuit 0,210 · jour 0,295 · pointe 0,430 TND/kWh | Indicatif, à remplacer par la grille STEG en vigueur |
| Plages de pointe | soir 18 h–22 h (hiver), 9 h–14 h (été) | Hypothèse |
| Pénalité de pointe | 0,60 TND par kW de pointe journalière | Hypothèse |

## 5. Données industrielles réelles : HIPE (`hipe.py`)

- **Source** : *High-resolution Industrial Production Energy*, Karlsruher Institut für Technologie (KIT),
  usine d'électronique de puissance. Licence CC BY 4.0. Sous-ensemble : semaine du 23 au 29 octobre 2017.
- **Contenu** : arrivée générale et 10 machines (fours, pompes à vide, sérigraphie, machine de placement,
  scie, presse, lavage), une mesure toutes les 5 s environ : P, Q, S, THD et taux harmoniques de courant
  (rangs 3 à 15) par phase.
- **Téléchargement** : `python scripts/telecharger_hipe.py` (archive de 109 Mo, lue sans extraction).
- **Prétraitement** : horodatage converti en heure locale, moyenne sur une grille régulière de 5 s,
  moyenne des phases pour le THD et les harmoniques, courants harmoniques en ampères à partir des taux
  (en %) et du courant fondamental, interpolation des trous d'au plus 10 s.
- **Vérité terrain** : les marches de puissance mesurées directement sur chaque machine. Un événement vu à
  l'arrivée générale prend le nom de la machine qui a basculé au même instant (± 15 s), sinon « autre ».
- **Découpage** : pour chaque classe, les 70 % premiers événements (dans le temps) servent à
  l'apprentissage et les suivants au test ; prévision : lundi-mercredi pour apprendre, jeudi-vendredi pour
  tester.
- **Rejeu** : la journée réelle du jeudi 26/10/2017 au pas de 5 s (`artifacts/hipe_replay.parquet`)
  alimente la passerelle edge simulée.

## 6. Hypothèses et périmètre

- **Validation** : simulateur physique paramétré, complété par une semaine de mesures industrielles
  réelles (HIPE). L'étape suivante est un pilote sur un site tunisien, avec la grille tarifaire STEG en
  vigueur.
- **Reconnaissance** : une machine de chaque type par atelier ; plusieurs machines identiques en
  parallèle sont suivies comme un groupe.
- **Événements rapprochés** : évalués jusqu'à une seconde d'écart (scénario dense, `stream.py`).
- **HIPE** : la forme d'onde brute n'est pas publiée ; la branche spectre harmonique de la reconnaissance
  est validée sur ces données, la branche images GAF sur formes d'onde simulées.
- **VoltEye Grid** : 10 zones simulées, placées dans des zones industrielles tunisiennes réelles ; nombre
  d'usines par zone, profils sectoriels et participation de 30 % au programme : hypothèses de déploiement
  (`grid.py`).
