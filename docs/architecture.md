# Architecture de VoltEye

## Vue en couches

| Couche | Rôle | Dans le MVP | Cible de déploiement |
|---|---|---|---|
| **Charge** | Machines d'un site industriel | 7 types de machines simulées | Machines réelles, sans modification |
| **Terminal** | Mesure V/I au point de raccordement, détection d'événements, reconnaissance IA en local (edge) | `volteye/stream.py` sur PC | Capteur de puissance triphasé + Raspberry Pi 5 (moins de 100 $ par site) |
| **Réseau** | Remontée des événements et indicateurs (quelques ko par heure) | — | NB-IoT, 4G/5G ou Ethernet du site |
| **Cloud** | Historique, prévision, anomalies, maintenance, optimisation, agrégation multi-sites | `volteye/*.py` + fichiers Parquet | Serveur + base MongoDB |
| **Présentation** | Tableau de bord, alertes, rapports | Streamlit (`app/streamlit_app.py`) | Application web + notifications |

Seuls les événements et les indicateurs agrégés quittent le site : les formes d'onde brutes restent sur la
passerelle. Cela limite la bande passante et protège les données de production.

## Flux de données

```
capteur (3,2 kHz) ──► mesures 1/s (P, Q, FP, THD) ──► détection de marches de puissance
                                                         │
                         forme d'onde « après − avant » ◄┘
                                     │
               ondelette db4 (approximation, détail) + spectre FFT
                                     │
                      3 images GAF 32×32 ──► fusion RVB
                                     │
          CNN (3 blocs conv.) + P, Q, FP, THD ──┐
          forêt aléatoire sur le spectre FFT ───┴─► fusion des probabilités ──► machine reconnue
                                     │
                 état et énergie estimés de chaque machine (désagrégation)
                                     │
      ┌──────────────────────┬───────┴──────────────┬───────────────────────┐
 prévision J+1          anomalies               santé (THD)          optimisation du planning
 (gradient boosting)    (résidus + MAD)         (dérive, jours restants)   (MILP, HiGHS)
                                     │
                     tableau de bord site / vue ville
```

## Choix techniques et justification

| Choix | Pourquoi |
|---|---|
| **Point de mesure unique (NILM)** | Coût d'installation divisé par le nombre de machines, aucune intervention sur des équipements certifiés, aucun arrêt. |
| **Signature harmonique** | Chaque technologie (résistance, moteur, variateur, alimentation à découpage, onduleur) produit un spectre différent : c'est l'information la plus discriminante, comme le confirme la baseline B. |
| **Images GAF + CNN** | Le GAF encode les relations temporelles de tout le signal dans une image ; le CNN exploite la forme d'onde complète et reste plus robuste au bruit (88,5 % contre 86,2 % avec un bruit triplé). |
| **Fusion CNN + forêt aléatoire** | Les deux modèles se trompent sur des cas différents : la fusion donne le meilleur score (98,1 %) et la meilleure robustesse (89,0 %). |
| **Gradient boosting pour la prévision** | Variables hétérogènes (calendrier, météo, retards), peu de données, entraînement en quelques secondes, interprétable. |
| **Score robuste sur les résidus** | Non supervisé (pas besoin d'anomalies étiquetées) et explicable : chaque alerte dit *quand* (en production ou non) et *combien* (kWh, TND, CO₂). |
| **Programme linéaire en nombres entiers** | Les contraintes (fenêtres, durées, puissance souscrite) sont exactes et la solution est optimale, avec un solveur libre (HiGHS) résolu en moins d'une seconde. |
| **Raspberry Pi 5 plutôt qu'un GPU** | Le CNN fait moins de 100 000 paramètres : l'inférence prend moins d'une milliseconde par événement sur CPU. Un accélérateur (Jetson Orin Nano) ne se justifie que pour un flux continu à haute fréquence sur de nombreuses lignes. |

## Performances d'inférence (PC portable, CPU)

| Étape | Temps |
|---|---|
| Reconnaissance d'un événement (fusion, traitement par lot) | ≈ 0,4 ms |
| Désagrégation de 4 h de flux (190 événements) | quelques secondes |
| Optimisation d'une journée | < 1 s |
