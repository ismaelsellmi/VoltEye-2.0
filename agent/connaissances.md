# Fiches de connaissances VoltEye

## Tarifs et hypothèses économiques utilisés par VoltEye

VoltEye calcule les coûts avec une grille horaire indicative pour un client industriel moyenne tension :
0,210 TND/kWh la nuit (22 h - 6 h), 0,295 TND/kWh le jour et 0,430 TND/kWh à l'heure de pointe. La pointe
tarifaire est placée le soir en hiver (18 h - 22 h) et en journée en été (9 h - 14 h, de juin à août). Une
pénalité de 0,60 TND par kW de pointe journalière représente le coût de la puissance appelée. Le facteur
d'émission du réseau tunisien est pris à 0,50 kg de CO₂ par kWh. Ces valeurs sont des hypothèses de travail,
à remplacer par la grille STEG en vigueur et le facteur ANME lors d'un déploiement.

## Que faire face à une alerte de consommation hors production

Une consommation hors production signifie qu'une machine reste sous tension la nuit, le week-end ou un jour
férié. Actions : programmer un arrêt automatique (horloge, automate), vérifier la mise en veille des machines
à commande numérique, couper les auxiliaires (ventilation, pompes) en fin de poste, et sensibiliser les
équipes à la procédure de fermeture. Le gain se mesure directement dans VoltEye le lendemain.

## Que faire face à une fuite d'air comprimé

Une fuite d'air comprimé fait tourner le compresseur plus longtemps, surtout hors production quand aucun
outil ne consomme d'air. Actions : lancer une campagne de recherche de fuites (détecteur à ultrasons ou eau
savonneuse sur raccords, flexibles et purgeurs), réparer les fuites les plus importantes en premier, couper
le compresseur ou isoler le réseau hors production, et vérifier la pression de consigne (chaque bar inutile
coûte environ 7 % d'énergie au compresseur).

## Que faire face à un pic de consommation anormal

Un pic horaire anormal sur un four ou une étuve indique en général une régulation défaillante : thermostat
déréglé, sonde de température défectueuse ou contacteur collé. Actions : contrôler la régulation et la
sonde, comparer la consigne à la température réelle, et vérifier l'isolation et les joints de porte.

## Que faire face à une surconsommation en production

Une machine qui consomme plus que prévu en production signale un réglage dégradé, une usure mécanique ou une
charge plus lourde. Actions : vérifier les réglages, l'état des outils, la lubrification et l'alignement ;
comparer avec un autre poste identique si possible.

## Lire le score de santé d'une machine

VoltEye suit la distorsion harmonique du courant (THD) de chaque moteur et électronique de puissance. Un
moteur qui s'use (roulements, désalignement, isolement) déforme davantage le courant : son THD monte. Le
score de santé vaut 100 quand le THD est à sa valeur de référence (médiane des deux premiers mois) et baisse
avec la dérive. Une alerte part quand la dérive atteint +25 %. VoltEye estime aussi le nombre de jours avant
le seuil critique (+100 %). Action conseillée sur alerte : planifier une inspection (vibrations, roulements,
isolement, échauffement) avant la panne.

## Pourquoi décaler des tâches flexibles

Certaines tâches peuvent attendre quelques heures sans gêner la production : cuissons, remplissage du
réservoir d'air comprimé, recharge des chariots élévateurs, chauffe-eau de process, étuvage. Les lancer hors
des heures de pointe réduit la facture et la pointe de puissance. L'optimiseur VoltEye choisit l'heure de
démarrage de chaque tâche en respectant sa fenêtre autorisée et la puissance souscrite.

## La pointe d'été du réseau et VoltEye Grid

En été, la demande d'électricité en Tunisie atteint son maximum l'après-midi (climatisation). Des
déclarations relayées par la presse en 2026 évoquent une demande de pointe proche de 6 000 MW et un déficit de
1 500 à 2 000 MW aux heures de pointe, avec des délestages préventifs (chiffres de presse, pas un bilan
officiel). VoltEye Grid agrège la flexibilité des usines équipées sur plusieurs zones industrielles, prévoit
la demande du lendemain et répartit les démarrages pour abaisser la pointe agrégée sans changer l'énergie
consommée. Quand chaque usine réagit seule au tarif, toutes basculent à la même heure et la pointe se reforme
plus tard (effet rebond) : la coordination évite ce rebond.

## Comment VoltEye voit chaque machine avec un seul compteur

VoltEye mesure le courant et la tension à l'arrivée générale (3 200 échantillons par seconde). À chaque
démarrage ou arrêt, il isole la variation du courant sur 40 ms, la décompose (ondelette db4 et spectre
harmonique), la transforme en image (Gramian Angular Field) et un réseau de neurones convolutif, fusionné
avec une forêt aléatoire sur le spectre, reconnaît la machine. En additionnant les machines reconnues, VoltEye
reconstitue la consommation de chacune : c'est la désagrégation (NILM, suivi non intrusif des charges).
