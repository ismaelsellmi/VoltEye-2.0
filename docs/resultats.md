# Résultats et évaluation

Toutes les valeurs proviennent de `artifacts/*.json`, produits par `python -m volteye.pipeline`
(graine aléatoire fixée : les résultats sont reproductibles).

## 1. Reconnaissance des machines (2 100 événements de test, 7 classes)

| Approche | Exactitude | F1 macro | Exactitude bruit x3 | ms / événement |
|---|---|---|---|---|
| A. Mesures classiques (P, Q, S, FP, I, THD) + forêt aléatoire | 90,8 % | 0,908 | 79,4 % | 0,07 |
| B. Spectre FFT + forêt aléatoire | 97,7 % | 0,977 | 86,1 % | 0,08 |
| C. Ondelettes + GAF + CNN | 97,4 % | 0,974 | 88,2 % | 0,34 |
| **D. VoltEye : fusion C + B** | **97,9 %** | **0,979** | **88,5 %** | 0,42 |

Lecture : les mesures classiques ne suffisent pas (des machines de même puissance se confondent). Le
spectre harmonique apporte l'essentiel. Le CNN sur images GAF est **plus robuste au bruit** et la fusion des
deux donne le meilleur résultat dans les deux conditions. Le F1 par classe va de 0,94 (compresseur,
convoyeur : deux moteurs aux signatures proches) à 1,00.

## 2. Désagrégation d'un flux de 4 h

| Indicateur | Valeur |
|---|---|
| Événements détectés / réels | 190 / 194 (précision 1,00, rappel 0,98, F1 0,99) |
| Événements correctement attribués | 98,9 % |
| Précision énergétique (1 − Σ|écart| / 2·Σénergie) | 99,2 % |
| Erreur d'énergie par machine | de 0 % à 6,3 % |

**Scénario dense** (1 h, cycles cinq fois plus courts, événements espacés d'une seconde seulement :
241 événements dont 37 à moins de 4 s d'écart) : détection F1 0,961, reconnaissance 96,8 %.

## 3. Prévision J+1 (60 derniers jours, jamais vus à l'entraînement)

| Modèle | MAE (kWh/h) | RMSE | MAPE (heures actives) |
|---|---|---|---|
| **VoltEye : gradient boosting** | **1,52** | **2,22** | **7,7 %** |
| Baseline : même heure la semaine précédente | 3,82 | 10,57 | 12,3 % |
| Baseline : même heure la veille | 15,17 | 30,35 | 55,4 % |

## 4. Détection d'anomalies : backtest glissant sur 4 mois jamais vus

Protocole temporel, sans aucune information du futur :

- **Rodage** (nov. 2025 → janv. 2026) : premiers modèles, aucune alerte notée.
- **Réentraînement mensuel** : chaque mois est prédit par un modèle entraîné sur les mois précédents
  uniquement ; le score robuste est normalisé sur les 60 jours précédents.
- **Validation** (fév. → juin 2026) : le seuil de chaque méthode est réglé ici.
- **Test** (juil. → oct. 2026, 861 jours-machine dont 26 anormaux) : score publié, période jamais
  utilisée pour régler quoi que ce soit.

| Approche (test juil.-oct.) | Seuil | Précision | Rappel | F1 |
|---|---|---|---|---|
| **VoltEye : résidus + score robuste (MAD)** | 5,75 | **0,87** | **0,77** | **0,82** |
| Variante : résidus + Isolation Forest | 0,62 | 0,36 | 0,50 | 0,42 |
| Baseline : z-score de l'énergie journalière | 4,00 | 0,22 | 0,15 | 0,18 |

Rappel par type (février à octobre) : veille 100 %, panne 100 %, éclairage du week-end 100 %, pic 75 %,
fuite d'air 73 % (la fuite est signalée pendant sa montée en puissance). Gaspillage détecté de février à
octobre : 3 080 kWh, soit environ 910 TND et 1,5 t de CO₂ pour un seul site.

## 5. Maintenance prédictive

La dérive du THD du moteur de convoyeur déclenche une alerte le 21/04/2026, soit **27 jours avant la
panne** (18/05/2026), sans aucune fausse alerte sur les 6 autres machines pendant l'année.

## 6. Optimisation du planning (51 jours ouvrés de test)

| Indicateur | Valeur |
|---|---|
| Gain moyen | 55 TND par jour (-12,6 % sur la facture du jour) |
| Pointe journalière évitée | 77 kW en moyenne |
| Gain annuel estimé (290 jours ouvrés) | ≈ 16 000 TND pour le site de référence |

Référence : toutes les tâches flexibles sont lancées en début de poste (7 h), la pratique la plus courante.

Seconde référence, **opérateur averti** : chaque tâche démarre à l'heure la moins chère de sa fenêtre selon
le tarif, sans coordination entre tâches. Face à lui, l'optimiseur gagne encore 3,9 TND par jour (-1,1 %)
et 6,5 kW de pointe : c'est l'apport propre de la coordination des tâches sous contrainte de puissance,
qui prend toute son ampleur à l'échelle de plusieurs sites (module VoltEye Grid).

## 7. Validation sur données industrielles réelles (HIPE, KIT)

Une semaine de mesures réelles au pas de 5 s (23-29/10/2017) : l'arrivée générale d'une usine
d'électronique de puissance et 10 machines suivies individuellement (sources et prétraitement :
[donnees.md](donnees.md), section 5).

**Reconnaissance des signatures réelles** : 7 machines en marche (fours, pompes à vide, sérigraphie,
machine de placement, scie), 14 600 mesures d'apprentissage, 6 270 de test (découpage chronologique).

| Approche | Exactitude | F1 macro |
|---|---|---|
| P, Q, facteur de puissance + forêt aléatoire | 99,4 % | 0,994 |
| **VoltEye : + THD et harmoniques** | **99,9 %** | **0,999** |

Les harmoniques réelles divisent les erreurs par sept : elles distinguent des machines de puissance
voisine (pompes à vide et four haute température autour de 0,9 kW).

**Au point de mesure unique** (arrivée générale, avec toutes les charges non suivies de l'usine) :

| Indicateur | Valeur |
|---|---|
| Événements des machines suivies retrouvés par le détecteur VoltEye | **81,9 %** de 1 792 (pompe à vide 1 : 95 %) |
| Attribution des événements (four de brasage / autres charges) | **88,6 %** avec harmoniques, 87,2 % avec ΔP et ΔQ seuls |
| Prévision de la charge du site à 1 h (pas de 15 min) | **MAPE 14,8 %** (persistance : 18,7 %, veille : 17,2 %) |

**Énergie hors production** : 29 % de l'énergie de la semaine (780 kWh sur 2 705) est consommée la nuit
et le week-end, avec un talon de 6,3 kW quand l'usine est à l'arrêt. C'est exactement le gisement que
VoltEye rend visible et chiffre pour chaque site.

## 8. VoltEye Grid : effacement coordonné de la pointe d'été

10 zones industrielles tunisiennes simulées (810 usines, profils sectoriels), 30 % d'usines inscrites au
programme, soit 26 MW de charges flexibles. La demande de chaque zone est prévue la veille (modèle
entraîné jusqu'au 30 juin) ; le programme linéaire répartit les démarrages de chaque zone pour abaisser
la pointe agrégée ; les trois stratégies sont rejouées sur la demande réelle des 10 jours ouvrés les plus
chargés de l'été 2026.

| Stratégie | Pointe agrégée moyenne | Heure de pointe |
|---|---|---|
| Pratique actuelle (démarrage en début de poste) | 94,4 MW | 8 h |
| Réponse au tarif seul (chaque usine vise l'heure la moins chère) | 90,6 MW | 15 h (effet rebond) |
| **VoltEye Grid** (démarrages coordonnés) | **84,1 MW** | étalée |

**-10,3 MW** de pointe (-10,9 %) face à la pratique actuelle et **-6,5 MW** (-7,2 %) face à une réponse au
tarif non coordonnée, à coût énergétique égal pour les usines. 60 MWh par jour sont déplacés : la même
énergie, consommée à d'autres heures.

## 9. IA avancée : fourchettes, explicabilité, assistant

**Prévision avec fourchette calibrée.** Deux modèles quantiles (10 % et 90 %) sont élargis par régression
quantile conformalisée (Romano et al., 2019), calibrée sur les 45 derniers jours d'apprentissage, séparément
pour les heures de production et les autres. Sur la période de test : **88,1 %** des heures réelles tombent
dans la fourchette P10-P90 (cible 80 %), largeur moyenne 5,2 kWh.

**Explications SHAP de la prévision.** Poids moyen des informations (valeurs SHAP, kWh) : planning de
production 32,6 ; température prévue 1,9 ; consommation de la veille à la même heure 0,36 ; moyenne de la
veille 0,32. Chaque heure prévue a son explication détaillée dans l'application (page Prévision).

**Grad-CAM sur les images GAF.** Pour chaque événement reconnu, la passerelle calcule la carte Grad-CAM du
CNN (dernier bloc convolutif) : elle montre quelles zones de l'image, donc quelles paires d'instants ou de
rangs harmoniques, ont fait décider le réseau.

**Assistant énergie.** Dix outils VoltEye (indicateurs, consommation hors production, anomalies, santé,
prévision, planning, VoltEye Grid, évaluation, documentation, SQL en lecture seule) ; documentation indexée
dans pgvector (modèle multilingue local, recherche hybride sémantique et plein texte). Évaluation sur 25
questions dont la réponse est calculée par les outils : **25/25 réponses justes** et 25/25 bons outils en
mode hors ligne (`python -m agent.evaluate`). Les mêmes outils sont exposés par un serveur MCP.
