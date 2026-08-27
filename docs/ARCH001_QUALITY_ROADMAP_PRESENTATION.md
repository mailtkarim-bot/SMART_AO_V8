# SMART_AO V8 — ARCH-001 et feuille de route qualité

## Slide 1 — Où en sommes-nous ?

**Titre :** Réduire la dette d’architecture sans casser les invariants métier

**Message clé :** SMART_AO V8 avance par micro-lots contrôlés : ports applicatifs, adaptateurs SQLAlchemy assemblés dans la composition root, handlers transactionnels conservés, tests et CI comme preuves.

**Repères :** PR #110 fusionnée sur `main` avec le commit `81766d3`. Le lot courant poursuit la même stratégie sur la façade Pricing Scenario Transition.

![GitHub Actions](assets/github-actions-workflow.png)

## Slide 2 — ARCH-001 : principe de découplage

**Avant :** une façade applicative recevait parfois une fabrique de session et importait indirectement des préoccupations de persistance.

**Cible :** la façade dépend de ports et de contrats applicatifs ; la composition root injecte les adaptateurs ; le handler transactionnel possède les verrous, transitions, révisions et événements.

**Règle de sécurité :** ne pas déplacer artificiellement un handler ORM si cela mélange autorisation, mutation et transaction dans un même changement.

## Slide 3 — Micro-lot Pricing Scenario Transition

**Livré dans ce lot :** retrait de `session_factory` inutilisé de `PricingScenarioTransitionService`, adaptation de `bootstrap/application.py` et de la fixture d’intégration, ajout d’un test pur de frontière.

**Préservé :** autorisation `PATRON_ADMIN`, dispatch des commandes, lecture des transitions append-only, contrôle de version, sélection unique et événements transactionnels.

**Mesure ARCH-001 :** le compteur reproductible reste à **35 fichiers** : le lot retire une injection inutile mais ne sépare pas physiquement le handler ORM du module.

## Slide 4 — Trajectoire ARCH-001

| Étape | Cible | Principe |
|---|---|---|
| 1 | Lecteurs Enterprise et Financial | Ports de lecture minimaux |
| 2 | Façades Pricing Import et Scenario | Autorisation séparée du handler |
| 3 | Services Membership ciblés | Projections et contrats explicites |
| 4 | Handlers encore co-localisés | Extraction seulement si la frontière est stable |
| 5 | Contrôle continu | Métrique d’import + revue des invariants |

**Priorité suivante :** un bounded context Membership ou une façade Pricing encore porteuse d’une frontière nette, après inspection réelle des usages.

## Slide 5 — Première tranche mypy `arg-type`

**Périmètre :** `test_submission_package.py` et `test_enterprise_upload_handlers.py`, deux fichiers de tests fortement chargés.

**Méthode :** remplacer les `SimpleNamespace` utilisés comme commandes par les commandes Pydantic du domaine ; utiliser des casts locaux uniquement au point où un double de persistance est transmis à une méthode privée de handler ; ne pas ajouter d’exclusion ni de `type: ignore` global.

| Indicateur | Avant | Après |
|---|---:|---:|
| Sources analysées | 680 | 680 |
| Erreurs mypy totales | 230 | **220** |
| Erreurs `arg-type` | 171 | **141** |
| `arg-type` dans Submission Package | 17 | **0** |
| `arg-type` dans Enterprise Upload | 15 | **0** |

## Slide 6 — Feuille de route mypy

**Tranche A — terminée :** commandes et doubles des deux fichiers prioritaires.

**Tranche B — prochaine :** doubles `AuthenticationContextResolver` et `ConsultationSecurityRuntime` dans les tests API, avec Protocols minimaux compatibles.

**Tranche C :** erreurs `attr-defined`, `index` et `assignment` dans les fixtures et objets simulés.

**Gate différentiel :** aucune nouvelle erreur par rapport à la baseline, puis réduction monotone du stock. Les corrections doivent rester groupées par famille de tests et être prouvées par mypy ciblé puis CI.

## Slide 7 — Feuille de route Ruff et validation

**Ruff lint :** globalement vert.

**Ruff format :** dette historique de **209 fichiers** à reformater ; elle est traitée séparément, par bounded context et par PR de formatage dédiée, pour ne pas masquer les changements métier.

**Validation locale actuelle :** 1 113 tests backend hors DB passés, 477 tests DB désélectionnés ; frontend typecheck, lint, 119 tests Vitest et build passés.

**Validation CI requise :** PostgreSQL, migrations, couverture complète, scans de sécurité et CI post-merge. L’absence de PostgreSQL/Docker local interdit de conclure la couverture DB depuis le sandbox.

## Slide 8 — Décisions et limites

**Décisions :** petits lots réversibles, main protégée, squash-merge après contrôles verts, documentation clonable dans `docs/`, scripts mécanistes dans `ops/`.

**À ne pas surinterpréter :** le compteur ARCH-001 est une métrique d’arêtes d’import ; la couverture locale hors DB n’est pas le gate CI ; les brouillons DC1/DC2/DC4 restent des propositions serveur ; les actions Decision ne produisent pas automatiquement un outcome juridique.

**Hors preuve actuelle :** VPS, staging/production, Docker local, ClamAV/EICAR, HTTPS réel, backup/restore opéré, secrets et fournisseurs SMTP/S3/bus/eIDAS, corpus DCE autorisé, OCR/RAG, E2E authentifié et validation juridique.

**Références du dépôt :** `docs/ARCH001_GLOBAL_STATUS_2026-08-27.md`, `docs/ARCH001_PRICING_TRANSITION_FACADE_2026-08-27.md`, `docs/MYPY_ARG_TYPE_FIRST_TRANCHE_2026-08-27.md`, `docs/MYPY_RUFF_REMEDIATION_PLAN_2026-08-27.md`.
