# Ravito pour Home Assistant

Intégration Home Assistant pour [Ravito](https://ravito.fitoune.fr), l'app de stock, de liste de courses et de recettes du foyer.

- **Liste de courses** en liste de tâches native (`todo`) : carte « Liste de tâches », ajout et coche depuis Home Assistant ou Assist. Les lignes sont rangées par rayon. Cocher une ligne la coche dans la course en cours ; le stock n'est crédité qu'à la validation de la course dans l'app.
- **Capteurs** : à acheter, stock bas, péremptions (≤ 3 jours, périmés compris), menu du jour (la semaine en attribut).
- **Service `ravito.chef`** : une phrase dite à Chef, qui répond par un texte à lire (`speech`). Rien n'est modifié sans « oui ».

## Installation

1. HACS › Dépôts personnalisés › `https://github.com/Louis-hue-lang/ha-ravito` (catégorie Intégration), puis télécharger **Ravito** et redémarrer.
2. Dans Ravito : Réglages › Administration › Home Assistant › créer un jeton. Portée `liste` pour ajouter et cocher, `cuisine` pour Chef.
3. Paramètres › Appareils et services › Ajouter › **Ravito** : adresse et jeton.

Le résumé est relu chaque minute (Ravito limite chaque jeton à 60 requêtes/min).

## Chef à la voix

```yaml
alias: Ravito · Chef
triggers:
  - trigger: conversation
    command: ["Chef {texte}", "Dis Chef {texte}"]
  - trigger: conversation
    command: ["oui Chef", "non Chef"]
actions:
  - action: ravito.chef
    data:
      texte: "{{ trigger.slots.texte if trigger.slots.texte is defined else trigger.sentence }}"
    response_variable: ravito
  - set_conversation_response: "{{ ravito.speech }}"
```

`{texte}` est du texte libre : il faut un moteur de reconnaissance vocale qui transcrit tout (Whisper, cloud), pas Speech-to-Phrase.
