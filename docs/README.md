# Documentation SMART_AO V8

`docs/reference/` contient les contrats normatifs importés avant le premier code. Ils ne sont pas de simples notes : ils sont la référence pour les invariants, commandes, tests et schéma de données.

`PROJECT_STATE.md` est le premier fichier à lire pour reprendre le projet. Il doit être actualisé à chaque fin de session ou commit significatif.

`DECISION_LOG.md` consigne les petits arbitrages. Une décision coûteuse, durable ou difficile devient une ADR dans `docs/adr/`.

`ROADMAP_01_PLAN_GLOBAL_CODAGE.md` donne l’ordre global des slices, leurs critères de sortie et les jalons vers la préproduction. Il est lu après `PROJECT_STATE.md`, qui reste la source de l’action immédiate.

`DEPENDENCY_INTEGRATION_STATUS_2026-08-22.md` distingue les dépendances réellement installées des composants seulement prévus par l’architecture cible. Il doit être lu avant tout greffage d’un solveur, moteur OCR, index vectoriel, stockage objet ou connecteur externe.

`DOCUMENTATION_CATALOG.md` relie les sources Markdown aux PDF classés par rôle ; il permet d’explorer l’ensemble du patrimoine documentaire sans chercher dans les dossiers.
