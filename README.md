<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand/volteye-logo-horizontal-inverse.svg">
    <img src="brand/volteye-logo-horizontal.svg" alt="VoltEye" width="440">
  </picture>
</p>

# VoltEye 2.0

**See the invisible energy of smart cities.**
*Un seul capteur. Toutes les machines. Une pointe d'été maîtrisée.*

> Smart City Challenge 2026 · **Track 2 : Smart City for Intelligent Energy** · partenaire industriel : STEG

VoltEye est une plateforme d'**intelligence énergétique non intrusive** pour les sites industriels et le
réseau électrique. Un **point de mesure unique** à l'arrivée électrique d'un atelier suffit : l'IA reconnaît
chaque machine à sa **signature électrique** (forme d'onde et harmoniques), reconstitue sa consommation,
détecte les gaspillages, anticipe les pannes et optimise le planning selon le tarif horaire. À l'échelle de
la ville, **VoltEye Grid** agrège la flexibilité des usines équipées pour abaisser la pointe d'été du réseau.

![Application VoltEye : vue d'ensemble](docs/captures/app_accueil.png)

---

## Le problème

Dans la plupart des usines, l'énergie n'est suivie qu'à travers la facture mensuelle. On ne voit ni la
machine laissée sous tension la nuit, ni la fuite d'air comprimé, ni le moteur qui se dégrade, ni la
cuisson lancée à l'heure de pointe. Poser un compteur sur chaque machine coûte cher et impose des arrêts.
À l'échelle du pays, la pointe d'été dépasse les capacités du réseau l'après-midi : chaque mégawatt
déplacé hors de la pointe compte. **Ce qui n'est pas mesuré n'est pas maîtrisé.**

## La solution

| Fonction | Méthode IA | Résultat sur données de test |
|---|---|---|
| **Reconnaître** les machines | Ondelettes + harmoniques → images GAF → CNN, fusionné avec une forêt aléatoire sur le spectre | **97,9 %** d'exactitude (7 types de machines) |
| **Désagréger** le signal unique | Détection d'événements + reconnaissance, en continu sur la passerelle edge | **99,2 %** de précision énergétique, F1 détection 0,99 (0,96 en scénario dense) |
| **Prévoir** la consommation à J+1 | Gradient boosting (calendrier, météo, retards ≥ 24 h), fourchette conforme P10-P90, explications SHAP | **MAPE 7,7 %** (référence : 12,3 %), fourchette juste pour 88 % des heures |
| **Détecter** les gaspillages | Consommation attendue réentraînée chaque mois + score robuste des résidus | **F1 0,82** sur 4 mois jamais vus, précision 0,87 (référence z-score : F1 0,18) |
| **Anticiper** les pannes | Dérive de la distorsion harmonique (THD), score de santé | panne anticipée **27 jours** avant, 0 fausse alerte |
| **Optimiser** le planning | Programme linéaire en nombres entiers (HiGHS) sur le tarif horaire | **-12,6 %** sur la facture des jours ouvrés, -77 kW de pointe |
| **Produire** au soleil | Modèle photovoltaïque physique (60 kWc en toiture), charge nette, prévision J+1 | **80 %** d'autoconsommation, achat en pointe d'été divisé par 2 |
| **Effacer** la pointe du réseau (VoltEye Grid) | Prévision J+1 de 10 zones + programme linéaire de répartition des démarrages | **-10,3 MW** sur la pointe agrégée d'été (-10,9 %), -6,5 MW face à une réponse au tarif seul |
| **Expliquer** et **répondre** | Grad-CAM sur les images GAF ; assistant LLM outillé (11 outils VoltEye, RAG pgvector) ; serveur MCP | **25/25** réponses justes sur le jeu d'évaluation de l'assistant |

Toutes les métriques sont mesurées sur des données jamais vues à l'entraînement et comparées à des
méthodes de référence (détails : [docs/resultats.md](docs/resultats.md), page « Évaluation » de l'application).

**Validé sur mesures industrielles réelles** (jeu public HIPE du KIT, une semaine au pas de 5 s) : 7 machines
reconnues à **99,9 %** à partir de leur signature harmonique, 82 % des événements retrouvés depuis
l'arrivée générale, prévision à 1 h meilleure que la persistance (MAPE 14,8 % contre 18,7 %), et 29 % de
l'énergie consommée hors production mise en évidence.

## Architecture

```
 machines ─► capteur unique ─► passerelle edge ──MQTT──► API FastAPI ──► PostgreSQL + TimescaleDB + pgvector
             (courant,          détection d'événements,     ingestion,          séries temporelles, agrégats continus,
              tension 3,2 kHz)  CNN GAF, Grad-CAM           REST, WebSocket      documents de l'assistant
                                                                 │
                    application web installable (PWA) · assistant énergie · serveur MCP · Streamlit (secours)
```

Seuls les indicateurs (une mesure par seconde) et les événements reconnus quittent le site : le signal brut
reste sur la passerelle. Détails : [docs/architecture.md](docs/architecture.md).

![Chaîne de reconnaissance](docs/figures/fig_gaf_pipeline.png)

## Installation et lancement

Toute la plateforme (base TimescaleDB, broker MQTT, API, passerelle edge, application web) démarre avec
Docker, sans rien installer d'autre. Les données de démonstration et les modèles entraînés sont fournis dans
`artifacts/` : la base se remplit seule au premier démarrage.

### 1. Prérequis

| Outil | Version | Pour |
|---|---|---|
| [Git](https://git-scm.com/downloads) | récente | récupérer le dépôt |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, macOS) ou Docker Engine + Compose v2 (Linux) | Compose v2 | lancer la plateforme |
| Python | 3.10 à 3.12 | développement Python uniquement |
| Node.js | 22 | développement de l'application web uniquement |

Prévoir environ 10 Go d'espace disque pour les images Docker.

### 2. Récupérer le dépôt

```bash
git clone https://github.com/ismaelsellmi/VoltEye-2.0.git
cd VoltEye-2.0
```

Le dépôt est privé : acceptez d'abord l'invitation de collaborateur reçue par e-mail depuis GitHub.

### 3. Configurer l'assistant (facultatif)

```bash
cp .env.example .env            # PowerShell : Copy-Item .env.example .env
```

Renseignez `ANTHROPIC_API_KEY` dans `.env` pour activer l'assistant en mode LLM. Sans clé, l'assistant
fonctionne en mode hors ligne : il appelle les mêmes outils VoltEye et répond à partir de leurs résultats.
Le fichier `.env` n'est jamais commité.

### 4. Lancer

```bash
docker compose up --build -d
```

Le premier lancement construit les images et télécharge une fois les dépendances et le modèle de
plongements de l'assistant (10 à 15 minutes selon la connexion) ; les lancements suivants prennent quelques
secondes.

| Service | Adresse |
|---|---|
| **Application VoltEye** (installable sur téléphone et ordinateur) | http://localhost:8080 |
| API et documentation interactive | http://localhost:8000/docs |
| Direct en WebSocket | `ws://localhost:8000/ws/direct` |
| Base TimescaleDB (utilisateur, mot de passe et base : `volteye`) | `localhost:55432` |
| Broker MQTT | `localhost:11883` |

### Commandes utiles

| Commande | Rôle |
|---|---|
| `docker compose ps` | État des services |
| `docker compose logs -f api` | Journal de l'API (ou `edge`, `web`, `db`) |
| `git pull` puis `docker compose up --build -d` | Passer à la dernière version |
| `docker compose down` | Tout arrêter (les données sont conservées) |
| `docker compose down -v` | Arrêter et vider la base : elle est rechargée depuis `artifacts/` au prochain lancement |
| `docker compose --profile hipe up --build -d` | Ajouter le rejeu d'une journée réelle de l'usine HIPE |
| `docker compose --profile mcp up --build -d mcp` | Serveur MCP en HTTP sur http://localhost:8765/mcp |

### En cas de souci

- **Port déjà utilisé** (8080, 8000, 55432 ou 11883) : arrêtez le programme qui l'occupe, ou changez le port
  de gauche dans `docker-compose.yml` (par exemple `"8081:80"` pour l'application).
- **« Passerelle muette » ou « Hors ligne » dans l'en-tête** : la passerelle edge n'envoie pas de mesures.
  Vérifiez `docker compose ps`, puis `docker compose restart edge`.
- **Docker Desktop s'arrête pendant le premier build** : relancez Docker Desktop puis la même commande ; les
  étapes déjà terminées sont reprises depuis le cache.
- **L'application affiche une ancienne version** : rechargez la page deux fois (l'application est installable et
  se met à jour en arrière-plan) ou videz le cache du site.

## Développement

Pour modifier le code avec rechargement à chaud, la base et le broker restent dans Docker et le reste tourne
sur la machine.

### Environnement Python

```bash
python -m venv .venv
# Windows (PowerShell) : .venv\Scripts\Activate.ps1      Linux / macOS : source .venv/bin/activate
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt -r requirements-server.txt
```

Sous VS Code, l'interpréteur `.venv` est sélectionné automatiquement et deux configurations de lancement
sont prêtes (`VoltEye : tableau de bord`, `VoltEye : pipeline complet`).

### Lancer les briques une par une

```bash
docker compose up -d db mqtt          # base et broker
uvicorn api.main:app --reload         # API sur http://localhost:8000
python -m edge.gateway                # passerelle edge simulée (autre terminal)
cd web && npm ci && npm run dev       # application web sur http://localhost:5173 (autre terminal)
```

L'application web de développement relaie `/api` et `/ws` vers l'API locale (variable `VOLTEYE_API` pour en
viser une autre). En développement, la clé de l'assistant se passe par variable d'environnement :
`$env:ANTHROPIC_API_KEY="..."` (PowerShell) ou `export ANTHROPIC_API_KEY=...` (bash).

### Autres commandes

| Commande | Rôle |
|---|---|
| `python -m volteye.pipeline` | Tout régénérer : données, entraînement, évaluation, figures (environ 3 minutes) |
| `python scripts/telecharger_hipe.py` | Télécharger la semaine de mesures réelles HIPE (109 Mo) avant le pipeline |
| `python -m agent.evaluate` | Évaluer l'assistant énergie sur 25 questions |
| `python -m agent.mcp_server` | Serveur MCP en transport stdio |
| `streamlit run app/streamlit_app.py` | Tableau de bord Streamlit |
| `python -m pytest tests` | Tests Python (les tests de l'API utilisent la base Docker : `docker compose up -d db`) |
| `cd web && npx eslint src && npm run build` | Vérifications de l'application web |

Configuration type d'un client MCP de bureau :

```json
{ "mcpServers": { "volteye": { "command": "python", "args": ["-m", "agent.mcp_server"],
  "env": { "DATABASE_URL": "postgresql+psycopg://volteye:volteye@127.0.0.1:55432/volteye" } } } }
```

### Contribuer

`main` est la branche stable. Pour chaque modification :

```bash
git checkout main && git pull
git checkout -b ma-modification
# ... modifications, puis :
git add -A && git commit -m "Description de la modification"
git push -u origin ma-modification
```

Ouvrez ensuite une pull request vers `main` sur GitHub. L'intégration continue lance les tests Python, les
tests de l'API sur TimescaleDB et la vérification de l'application web à chaque push : la pull request se
fusionne quand les trois sont au vert.

## L'application

| Page | Contenu |
|---|---|
| Vue d'ensemble | Énergie, coût et CO₂ des 30 derniers jours, répartition par machine, alertes, santé, résultats de l'IA |
| Direct | Mesure du compteur unique seconde par seconde et désagrégation par machine, journal des événements reconnus |
| Reconnaissance | Chaîne d'un événement réel : forme d'onde, séquences, image GAF, carte Grad-CAM, décision du réseau |
| Anomalies et santé | Énergie réelle et attendue, alertes avec cause, coût et action, dérive du THD |
| Prévision et planning | Prévision J+1 avec fourchette, explications SHAP, planning optimisé et optimiseur à la demande, solaire |
| VoltEye Grid | Pointe agrégée de 10 zones selon trois stratégies, carte de la flexibilité |
| Assistant | Questions en langage naturel, réponses chiffrées par les outils VoltEye avec leurs sources |
| Évaluation | Toutes les métriques, protocoles et méthodes de référence |

La bande du compteur, en haut de chaque page, montre en permanence la mesure unique et les machines qu'elle
contient. `Ctrl K` (`⌘ K` sur Mac) ouvre la palette de commandes : aller à une page, changer de thème ou poser
directement une question à l'assistant. Interface en verre dépoli, thèmes clair et sombre, navigation mobile,
consultation hors ligne, alerte de dépassement de puissance par notification.

![Direct : la mesure unique et sa désagrégation](docs/captures/app_direct.png)

![VoltEye Grid : pointe d'été des 10 zones](docs/captures/app_grid.png)

## Structure du dépôt

```
├── volteye/                 cœur IA
│   ├── signals.py, gaf.py   machines, formes d'onde, images GAF
│   ├── recognition.py       reconnaissance (références, CNN GAF, fusion)
│   ├── stream.py            flux temps réel et désagrégation
│   ├── history.py           historique horaire d'un an avec anomalies étiquetées
│   ├── forecasting.py       prévision J+1, fourchette conforme, SHAP
│   ├── anomaly.py           anomalies (backtest glissant) et maintenance prédictive
│   ├── optimization.py      planning des tâches flexibles (MILP HiGHS)
│   ├── solar.py             solaire en toiture
│   ├── grid.py              VoltEye Grid : flexibilité multi-sites et pointe réseau
│   ├── hipe.py              validation sur mesures industrielles réelles
│   ├── explain.py           Grad-CAM
│   └── pipeline.py          exécution de bout en bout
├── edge/                    passerelle edge (détection, reconnaissance, MQTT)
├── api/                     API FastAPI, ingestion MQTT, chargement de la base
├── agent/                   assistant énergie, outils, RAG, évaluation, serveur MCP
├── db/schema.sql            schéma TimescaleDB + pgvector
├── web/                     application React + TypeScript (PWA)
├── app/streamlit_app.py     tableau de bord Streamlit
├── docker/, docker-compose.yml
├── artifacts/               modèles entraînés, métriques, données de démonstration
├── docs/                    architecture, données, résultats, figures, captures
├── brand/                   logo, symbole, icônes et leur générateur
├── scripts/                 téléchargement des données réelles
├── tests/                   tests unitaires, d'intégration et de l'application
└── livrables/               rapport technique, pitch, script vidéo
```

## Données et perspectives

Le règlement autorise les données simulées. VoltEye combine un **simulateur physique** documenté (formes
d'onde de 7 types de machines à 3,2 kHz, atelier à 1 mesure par seconde, un an d'historique horaire avec le
calendrier tunisien et la température de Tunis, anomalies étiquetées) et une **semaine de mesures réelles**
d'une usine allemande (HIPE, KIT). Sources, prétraitements et paramètres : [docs/donnees.md](docs/donnees.md).

Prochaines étapes : pilote de 4 semaines sur un atelier tunisien avec compteurs de référence, calibrage de la
grille tarifaire industrielle, du facteur d'émission et du taux de participation à l'effacement avec la STEG
et l'ANME, reconnaissance enrichie par le contexte de production, pilotage automatique des charges flexibles
en lien avec le distributeur.

## Références

- G. W. Hart, « Nonintrusive appliance load monitoring », *Proceedings of the IEEE*, 1992.
- Z. Wang, T. Oates, « Imaging time-series to improve classification and imputation », *IJCAI*, 2015 (Gramian Angular Field).
- R. R. Selvaraju *et al.*, « Grad-CAM: Visual explanations from deep networks via gradient-based localization », *ICCV*, 2017.
- S. M. Lundberg, S.-I. Lee, « A unified approach to interpreting model predictions », *NeurIPS*, 2017 (SHAP).
- Y. Romano, E. Patterson, E. Candès, « Conformalized quantile regression », *NeurIPS*, 2019.
- F. T. Liu, K. M. Ting, Z.-H. Zhou, « Isolation Forest », *IEEE ICDM*, 2008.
- Q. Huangfu, J. A. J. Hall, « Parallelizing the dual revised simplex method », *Mathematical Programming Computation*, 2018 (solveur HiGHS).
- S. Bischof *et al.*, « HIPE: An energy-status-data set from industrial production », *ACM e-Energy*, 2018.

## Équipe

Équipe VoltEye · Smart City Challenge 2026 · Track 2 : Intelligent Energy.
