# VoltEye : script de la vidéo (2 min) et du pitch (3 min)

## A. Vidéo de démonstration : 2 minutes

**Enregistrement** : OBS Studio (gratuit) ou l'enregistreur d'écran de Windows (Win + Alt + R), en
1080p. Lancer l'application avant : `streamlit run app/streamlit_app.py`, navigateur en plein écran (F11).
Voix off posée, enregistrée à part si besoin, et sous-titres conseillés.

| Temps | Écran | Voix off |
|---|---|---|
| 0:00–0:12 | Slide 2 (« Cette usine gaspille de l'énergie ») | « Dans une usine, rien n'a l'air cassé. Pourtant l'énergie fuit : machines en veille la nuit, fuites d'air, moteurs qui s'usent. Et personne ne le voit. » |
| 0:12–0:25 | Slide 3 (architecture) | « VoltEye mesure le courant en un seul point de l'atelier. Sans capteur sur les machines, l'IA reconnaît chaque machine à sa signature électrique. » |
| 0:25–0:50 | App · **Surveillance en direct** · cliquer ▶ Lecture | « Voici le signal unique mesuré chaque seconde. En dessous, VoltEye reconstitue la consommation de chaque machine. Quand une machine démarre, sa signature est isolée, transformée en image, et le réseau de neurones la reconnaît : ici un poste de soudage, à 100 % de confiance. » |
| 0:50–1:10 | App · **Reconnaissance IA** · choisir « Machine CNC », puis monter le bruit à 3 | « Chaque machine a son empreinte : ondelettes et harmoniques deviennent trois images GAF fusionnées en couleur. Même avec un bruit de mesure triplé, le modèle reconnaît la machine. » |
| 1:10–1:30 | App · **Anomalies** · Compresseur, puis l'onglet Santé au 01/05/2026 | « VoltEye détecte une fuite d'air comprimé et la chiffre en dinars et en CO₂. L'onglet santé signale la dérive harmonique du moteur de convoyeur 27 jours avant sa panne. » |
| 1:30–1:45 | App · **Prévision & optimisation** · onglet Optimisation | « La consommation du lendemain est prévue à 7,5 % près, et le planning optimisé selon le tarif horaire réduit la facture de 12 %. » |
| 1:45–1:55 | App · **Vue ville** | « Déployé sur les zones industrielles, VoltEye donne à la ville et au distributeur une vue de toute la charge industrielle. » |
| 1:55–2:00 | Slide 9 | « VoltEye. See the invisible energy of smart cities. » |

## B. Pitch : 3 minutes + démo en direct

Le texte de chaque slide est dans les **notes de l'orateur** de `VoltEye_Pitch.pptx`.

| Slide | Durée | Message clé |
|---|---|---|
| 1. Titre | 10 s | Équipe, slogan |
| 2. Problème | 25 s | L'énergie invisible : 4 pertes, un compteur par machine est impossible |
| 3. Solution | 20 s | Un capteur, l'IA, cinq services |
| 4. Approche technique | 25 s | Signature, ondelettes et FFT, GAF, CNN |
| 5. Démo en direct | 45 s | Surveillance, reconnaissance, anomalie |
| 6. Résultats | 25 s | Six chiffres, tous comparés à une baseline |
| 7. Impact | 20 s | Site, ville, réseau |
| 8 et 9. Suite et fin | 10 s | Pilote réel, slogan |

**Conseils**
- Répéter avec un chronomètre, au moins 3 fois. La démo ne doit pas dépasser 45 s.
- Ouvrir l'application **avant** de monter sur scène, sur la page Surveillance en direct.
- **Plan B** : si la démo plante, lancer la vidéo de 2 minutes.
- Une personne parle, une autre manipule la démo.

## C. Questions probables du jury

| Question | Réponse |
|---|---|
| Pourquoi des données simulées ? | Le règlement les autorise. Aucune donnée industrielle par machine n'était disponible. Notre simulateur est physique (formes d'onde à 3,2 kHz, signatures harmoniques par technologie) et documenté. Le passage au réel consiste à remplacer le simulateur par le flux du capteur. Le pilote réel est notre étape 1. |
| Pourquoi le GAF et un CNN plutôt que des caractéristiques classiques ? | Nous l'avons mesuré : les caractéristiques classiques donnent 90,8 % et le spectre seul 97,8 %. Le CNN GAF est le plus robuste au bruit (88,5 % contre 86,2 % avec un bruit triplé), et la fusion des deux donne le meilleur résultat dans les deux cas (98,1 % et 89,0 %). |
| Et si deux machines démarrent en même temps ? | Limite du MVP. Avec une mesure à 1 seconde, c'est rare ; la solution est une fenêtre plus courte ou la séparation de sources. |
| Deux machines identiques ? | Même signature : on les distingue par le contexte de production ou un second point de mesure. |
| Combien coûte un site ? | Capteur triphasé et Raspberry Pi 5 : moins de 1 000 TND, pour environ 17 000 TND d'économies par an sur le site de référence. |
| Pourquoi pas un GPU (Jetson) ? | Le CNN fait moins de 30 000 paramètres : l'inférence prend moins d'une milliseconde sur CPU. |
| Les tarifs sont-ils réels ? | Ce sont des hypothèses indicatives, paramétrables dans `config.py`. Nous demandons les grilles officielles STEG. |
| Où est l'IA, au-delà d'un appel à une API ? | Toute l'IA est entraînée et évaluée par nous : CNN, forêts aléatoires, gradient boosting, détection robuste, optimisation MILP. Aucun appel à un LLM. |
