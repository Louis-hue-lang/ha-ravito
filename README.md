# Ravito pour Home Assistant

Intégration Home Assistant pour [Ravito](https://ravito.fitoune.fr), l'app de stock, de liste de courses et de recettes du foyer. Pensée pour un écran de cuisine (Echo Show 8, ~960×600).

- **Carte `custom:ravito-card`**, chargée automatiquement :
  - **Liste** de courses, rangée par rayon, en lecture seule (elle se modifie dans l'app) ;
  - **Menu** de la semaine : ajouter un plat à un jour, le déplacer, le retirer ; état du stock de chaque plat ;
  - **Recettes** : recherche, filtres par tag, fiche (ingrédients avec leur état de stock, étapes), « Ajouter au menu ».
  La carte n'intercepte aucun geste : le balayage entre les vues du tableau de bord reste libre.
- **Liste de tâches** `todo.ravito_liste_de_courses` en lecture seule.
- **Capteurs** : à acheter, stock bas, péremptions (≤ 3 jours, périmés compris), menu du jour (la semaine en attribut).

## Installation

1. HACS › Dépôts personnalisés › `https://github.com/Louis-hue-lang/ha-ravito` (catégorie Intégration), puis télécharger **Ravito** et redémarrer.
2. Dans Ravito : Réglages › Administration › Home Assistant › créer un jeton de portée `cuisine` (nécessaire pour modifier le menu ; `lecture` suffit pour tout consulter).
3. Paramètres › Appareils et services › Ajouter › **Ravito** : adresse et jeton.
4. Tableau de bord : une vue de type **Panneau** avec la carte

```yaml
type: custom:ravito-card
```

Le résumé est relu chaque minute, le menu toutes les minutes quand l'onglet est ouvert, les recettes toutes les 10 minutes (Ravito limite chaque jeton à 60 requêtes/min).

Une nouvelle version se déclare dans `manifest.json` et dans `VERSION` de `__init__.py` (qui force le rechargement de la carte).
