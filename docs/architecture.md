# Architecture de VoltEye

## Vue en couches

| Couche | Rôle | Dans le prototype 2.0 | Cible de déploiement |
|---|---|---|---|
| **Charge** | Machines d'un site industriel | 7 types de machines simulées ; usine réelle HIPE (KIT) rejouée | Machines réelles, sans modification |
| **Terminal (edge)** | Mesure V/I au point de raccordement, détection d'événements, reconnaissance IA en local | `edge/gateway.py` (conteneur Docker) | Capteur de puissance triphasé + Raspberry Pi 5 (moins de 100 $ par site) |
| **Réseau** | Remontée des indicateurs (1 message/s) et des événements | MQTT (Mosquitto) | NB-IoT, 4G/5G ou Ethernet du site, MQTT sur TLS |
| **Plateforme** | Ingestion, historique, prévision, anomalies, maintenance, optimisation, VoltEye Grid | API FastAPI (`api/`) + PostgreSQL / TimescaleDB + pgvector | Même pile, hébergée |
| **Présentation** | Tableau de bord, direct, alertes, carte des zones, assistant | Application web React installable (PWA) | Application web et mobile + notifications |

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
                     tableau de bord site / VoltEye Grid
```

## Plateforme temps réel

```
 passerelle edge ──MQTT──► Mosquitto ──► API FastAPI ──► PostgreSQL + TimescaleDB (+ pgvector)
 (détection + CNN)          volteye/<site>/mesures          │  ingestion, REST, WebSocket /ws/direct
                            volteye/<site>/evenements       ▼
                                            application web (PWA) · assistant IA
```

- **Une mesure par seconde** et les événements reconnus (avec un extrait de 40 ms de forme d'onde) : le
  signal brut à 3,2 kHz (environ 2,2 Go par jour et par compteur) reste sur la passerelle.
- **TimescaleDB** : tables temporelles (`measurement`, `event`, `machine_load`, `forecast`), agrégats
  continus (`measurement_15min`, `machine_load_daily`) et compression automatique des mesures de plus de
  7 jours. **pgvector** range les documents de l'assistant (RAG) dans la même base.
- **Rôle en lecture seule** (`volteye_lecture`) pour l'outil SQL de l'assistant.
- **Assistant énergie** (`agent/`) : boucle d'outils sur un grand modèle de langage configurable (repli automatique en
  cas de refus), onze outils VoltEye, recherche hybride dans la documentation (pgvector + plein texte) ; un
  mode hors ligne appelle les mêmes outils sans réseau. **Serveur MCP** (`agent/mcp_server.py`, transports
  stdio et HTTP) : les mêmes outils pour tout assistant IA compatible.
- **Explicabilité** : Grad-CAM calculé sur la passerelle pour chaque événement ; valeurs SHAP de chaque heure
  prévue servies par l'API.
- **Chargement initial** : `python -m api.seed` remplit la base à partir des artefacts du pipeline (démo
  hors ligne reproductible) ; l'API le fait automatiquement au premier démarrage.

## Choix techniques et justification

| Choix | Pourquoi |
|---|---|
| **Point de mesure unique (NILM)** | Coût d'installation divisé par le nombre de machines, aucune intervention sur des équipements certifiés, aucun arrêt. |
| **Signature harmonique** | Chaque technologie (résistance, moteur, variateur, alimentation à découpage, onduleur) produit un spectre différent : c'est l'information la plus discriminante, comme le confirme la baseline B. |
| **Images GAF + CNN** | Le GAF encode les relations temporelles de tout le signal dans une image ; le CNN exploite la forme d'onde complète et reste plus robuste au bruit (88,2 % contre 86,1 % avec un bruit triplé). |
| **Fusion CNN + forêt aléatoire** | Les deux modèles se trompent sur des cas différents : la fusion donne le meilleur score (97,9 %) et la meilleure robustesse (88,5 %). |
| **Gradient boosting pour la prévision** | Variables hétérogènes (calendrier, météo, retards), peu de données, entraînement en quelques secondes, interprétable. |
| **Score robuste sur les résidus** | Non supervisé (pas besoin d'anomalies étiquetées) et explicable : chaque alerte dit *quand* (en production ou non) et *combien* (kWh, TND, CO₂). |
| **PostgreSQL + TimescaleDB** | Données presque toutes datées : hypertables, agrégats continus et compression ; SQL standard interrogeable par l'assistant ; relationnel, séries temporelles et vecteurs (pgvector) dans une seule base. |
| **MQTT** | Protocole standard de l'internet des objets : messages légers, reconnexion automatique, découplage entre passerelles et plateforme. |
| **Programme linéaire en nombres entiers** | Les contraintes (fenêtres, durées, puissance souscrite) sont exactes et la solution est optimale, avec un solveur libre (HiGHS) résolu en moins d'une seconde. |
| **Raspberry Pi 5 plutôt qu'un GPU** | Le CNN compte 28 679 paramètres : l'inférence prend moins d'une milliseconde par événement sur CPU. Un accélérateur (Jetson Orin Nano) ne se justifie que pour un flux continu à haute fréquence sur de nombreuses lignes. |

## Performances d'inférence (PC portable, CPU)

| Étape | Temps |
|---|---|
| Reconnaissance d'un événement (fusion, traitement par lot) | ≈ 0,4 ms |
| Désagrégation de 4 h de flux (190 événements) | quelques secondes |
| Optimisation d'une journée | < 1 s |
