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

## Version 0.20.1

Cette version accepte notamment les durées de filtration Home Assistant sous les formats `02 h 39 m`, `2h39`, `02:39`, `159 min`, `9540 s`, `2.65 h` et `PT2H39M`.

Pool Doctor reste en lecture seule : aucune commande physique de pompe, PAC, électrolyseur ou dosage n’est envoyée par cette intégration.
