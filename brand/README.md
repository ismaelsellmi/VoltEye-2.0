# Marque VoltEye

**Le symbole « œil-onde ».** Une seule période du courant à 50 Hz dessine l'œil : l'alternance positive forme
la paupière du haut, l'alternance négative celle du bas, qui porte une ondulation discrète (la signature
harmonique qui permet de reconnaître une machine). L'axe du temps traverse l'œil comme une trace
d'oscilloscope. La pupille jaune est le point de mesure unique.

## Fichiers

| Fichier | Usage |
|---|---|
| `volteye-logo-horizontal.svg` / `-inverse.svg` | Logo principal sur fond clair / sombre |
| `volteye-logo-empile.svg` | Formats carrés, couvertures |
| `volteye-symbole.svg` / `-inverse.svg` | Symbole seul |
| `volteye-symbole-simple.svg` | Petites tailles (sans ondulation, traits épais) |
| `volteye-icone.svg`, `volteye-icone-masquable.svg` | Icônes d'application (fond bleu) |
| `volteye-favicon.svg` | Favicon (tracé simplifié, lisible à 16 px) |
| `png/` | Exports PNG prêts à l'emploi (présentations, documents) |

Le mot VOLTEYE est vectorisé depuis Barlow Condensed Bold (licence SIL OFL) : les fichiers ne dépendent
d'aucune police installée.

## Couleurs

| Nom | Valeur | Rôle |
|---|---|---|
| Encre | `#1B201E` | Texte, symbole |
| Bleu neutre | `#1D5FA6` | Actions, icône d'application, aurore du fond |
| Jaune signal | `#F2C200` | Pupille, direct, alertes : à garder rare |
| Fond clair | `#EEF3F9` | Fond de l'application, thème clair |
| Fond nuit | `#050A14` | Fond de l'application, thème sombre |

Les machines gardent leur spectre catégoriel (validé pour les daltonismes), réservé aux données.

## Interface

L'application est un écran de mesure : des panneaux de verre dépoli (blanc à 60 % en clair, bleu glacier
à 6 % en sombre, flou de 18 px, liseré clair) posés sur une aurore bleue et jaune, un graticule
d'oscilloscope et les trois phases du courant en filigrane, parcourues par un point de mesure jaune.

| Rôle | Police |
|---|---|
| Interface et titres | Manrope (variable) |
| Chiffres mesurés, logotype | Barlow Condensed Bold |
| Valeurs de tableau, horodatages | IBM Plex Mono |

Mouvement : apparition en cascade des panneaux, chiffres qui se comptent, curseurs qui glissent ; tout
s'arrête si le système demande de réduire les animations, et les panneaux deviennent opaques si la
transparence est réduite.

## Règles

- Zone de protection : un diamètre de pupille autour du symbole.
- Tailles minimales : 16 px pour le favicon simplifié, 96 px de large pour le logo horizontal.
- La pupille reste jaune signal ; sur fond jaune, elle passe en encre.
- Ne pas déformer, incliner ni recolorer le symbole ; pas d'ombre, de reflet ni de dégradé.
- VOLTEYE en capitales condensées dans le logo ; VoltEye dans un texte.

## Régénérer

```bash
python brand/generer_marque.py      # SVG et tracés de l'application (web/src/data/logo.json)
cd web && npm run marque            # PNG : icônes de l'application, favicon, logos
```
