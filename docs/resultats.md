# Résultats et évaluation

Toutes les valeurs proviennent de `artifacts/*.json`, produits par `python -m volteye.pipeline`
(graine aléatoire fixée : les résultats sont reproductibles).

## 1. Reconnaissance des machines (2 100 événements de test, 7 classes)

| Approche | Exactitude | F1 macro | Exactitude bruit x3 | ms / événement |
|---|---|---|---|---|
| A. Mesures classiques (P, Q, S, FP, I, THD) + forêt aléatoire | 90,8 % | 0,908 | 79,4 % | 0,06 |
| B. Spectre FFT + forêt aléatoire | 97,8 % | 0,978 | 86,2 % | 0,07 |
| C. Ondelettes + GAF + CNN | 97,4 % | 0,974 | 88,5 % | 0,32 |
| **D. VoltEye : fusion C + B** | **98,1 %** | **0,981** | **89,0 %** | 0,41 |

Lecture : les mesures classiques ne suffisent pas (des machines de même puissance se confondent). Le
spectre harmonique apporte l'essentiel. Le CNN sur images GAF est **plus robuste au bruit** et la fusion des
deux donne le meilleur résultat dans les deux conditions. Le F1 par classe va de 0,94 (compresseur,
convoyeur : deux moteurs aux signatures proches) à 1,00.

## 2. Désagrégation d'un flux de 4 h

| Indicateur | Valeur |
|---|---|
| Événements détectés / réels | 190 / 194 (précision 1,00, rappel 0,98, F1 0,99) |
| Événements correctement attribués | 98,4 % |
| Précision énergétique (1 − Σ|écart| / 2·Σénergie) | 99,4 % |
| Erreur d'énergie par machine | de 0 % à 5,1 % |

## 3. Prévision J+1 (60 derniers jours, jamais vus à l'entraînement)

| Modèle | MAE (kWh/h) | RMSE | MAPE (heures actives) |
|---|---|---|---|
| **VoltEye : gradient boosting** | **1,51** | **2,20** | **7,5 %** |
| Baseline : même heure la semaine précédente | 3,82 | 10,57 | 12,3 % |
| Baseline : même heure la veille | 15,17 | 30,35 | 55,4 % |

## 4. Détection d'anomalies (2 555 jours-machine)

| Approche | Précision | Rappel | F1 |
|---|---|---|---|
| **VoltEye : résidus + score robuste (MAD)** | **0,98** | **0,79** | **0,88** |
| Variante : résidus + Isolation Forest | 0,52 | 0,54 | 0,53 |
| Baseline : z-score de l'énergie journalière | 0,14 | 0,24 | 0,17 |

Rappel par type : veille 94 %, pic 90 %, panne 100 %, éclairage du week-end 100 %, fuite d'air 64 % (les
premiers jours d'une fuite naissante, encore faible, ne sont pas signalés : la fuite est détectée
pendant sa montée). Gaspillage détecté : 2 790 kWh, soit environ 830 TND et 1,4 t de CO₂ sur un an pour un
seul site.

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
