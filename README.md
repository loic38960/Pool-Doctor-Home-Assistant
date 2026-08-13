# Pool Doctor — Home Assistant

Intégration Home Assistant officielle de **Pool Doctor**.

## Installation avec HACS

1. Ouvrir **HACS → Intégrations**.
2. Ouvrir le menu **⋮ → Dépôts personnalisés**.
3. Ajouter le dépôt `loic38960/Pool-Doctor-Home-Assistant` avec la catégorie **Intégration**.
4. Installer **Pool Doctor**.
5. Redémarrer Home Assistant.
6. Dans Home Assistant : **Paramètres → Appareils et services → Ajouter une intégration → Pool Doctor**.
7. Générer le code d’association depuis Pool Doctor puis l’utiliser dans Home Assistant.

## Mise à jour

Une fois installé par HACS, les nouvelles versions de Pool Doctor apparaissent dans les mises à jour Home Assistant/HACS. Après mise à jour de l’intégration, un redémarrage de Home Assistant peut être nécessaire.

## Version 0.23.0 — fiabilité des mesures

Pool Doctor considère désormais l’état de la pompe avant d’utiliser la chimie de l’eau :

- **pompe arrêtée** : pH, ORP, chlore, TAC, stabilisant et sel ne sont pas envoyés comme valeurs actuelles ;
- **0 à 10 min après démarrage** : chimie masquée pendant le premier brassage ;
- **10 à 30 min** : chimie live disponible pour observation mais non exploitable pour une analyse automatique ;
- **après 30 min** : une analyse n’est créée que si la fenêtre de relevés est suffisante et si au moins une mesure chimique est jugée exploitable.

L’intégration calcule également des indicateurs de stabilité. Une mesure très instable ou potentiellement figée est écartée de l’analyse représentative. La détection « potentiellement figée » s’appuie sur une fenêtre longue afin de ne pas confondre une sonde normalement stable avec une sonde réellement bloquée.

La dernière chimie jugée fiable peut être transmise comme **historique explicite**, mais elle ne remplace jamais la valeur actuelle lorsque la pompe est arrêtée.

## Durée de filtration

Les formats courants restent pris en charge : `02 h 39 m`, `2h39`, `02:39`, `159 min`, `9540 s`, `2.65 h` et `PT2H39M`.

Pool Doctor reste en **lecture seule** : aucune commande physique de pompe, PAC, électrolyseur ou dosage n’est envoyée par cette intégration.
