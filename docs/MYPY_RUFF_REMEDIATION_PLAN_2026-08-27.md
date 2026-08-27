# Plan d’action — mypy et formatage Ruff global

## Baseline mesurée

La baseline a été recalculée sur le dépôt après le lot Pricing Import.

| Indicateur | Valeur | Statut |
|---|---:|---|
| Mypy global | **230 erreurs dans 78 fichiers**, 680 sources analysées | Non vert globalement |
| `arg-type` | **171** | Première priorité |
| `attr-defined` | **23** | Deuxième priorité |
| `index` | **13** | Troisième priorité |
| `misc` | 7 | À traiter avec les contrats concernés |
| `var-annotated` | 5 | Annotations de fixtures et collections |
| `unused-ignore` | 4 | Nettoyage après correction de la cause |
| `assignment` | 4 | Typage de valeurs de test et retours |
| `operator` | 2 | Vérification des types numériques/union |
| `return-value` | 1 | Correction ciblée |
| Format Ruff global | **209 fichiers à reformater**, 669 déjà conformes | Dette historique |

Toutes les erreurs mypy recensées se trouvent actuellement sous `backend/tests`. Les fichiers les plus chargés sont `test_submission_package.py` avec 19 erreurs, `test_enterprise_upload_handlers.py` avec 18, `test_controlled_btp_documents.py` avec 10, `test_patron_submission_signature_routes.py` avec 8, puis `test_p0_remediation.py` et `test_case_assigned_api.py` avec 7 chacun.

## Ordre de traitement mypy

### 1. Stabiliser les fixtures communes

Identifier les fixtures qui renvoient `SimpleNamespace`, `Mock` non paramétrés ou des dictionnaires non annotés, puis les remplacer progressivement par des factories conformes aux Protocols des services. Cette étape doit réduire les `arg-type` sans masquer les erreurs par des exclusions.

### 2. Traiter les groupes de tests à forte concentration

Commencer par `test_submission_package.py` et `test_enterprise_upload_handlers.py`, puis poursuivre par les tests de documents contrôlés et les routes de signature. Chaque lot doit conserver les assertions existantes et être validé par les tests ciblés, Ruff et mypy ciblé.

### 3. Donner des contrats explicites aux workers et adaptateurs

Les erreurs de types liées à `AppRuntime`, au stockage de quarantaine et aux lecteurs doivent être résolues avec des Protocols ou des types d’implémentation documentés. Les faux objets de test ne doivent plus prétendre implicitement implémenter une classe concrète.

### 4. Corriger `attr-defined`, `index` et `assignment`

Après réduction des incompatibilités d’arguments, corriger les attributs optionnels, les indexations de collections insuffisamment typées et les affectations de types incompatibles. Les `unused-ignore` seront supprimés en dernier, une fois leurs erreurs sources éliminées.

### 5. Installer un gate différentiel

Le gate global peut rester temporairement non nul, mais aucun nouveau fichier ou lot ne doit ajouter d’erreur. Une comparaison de la baseline mypy dans la CI doit bloquer les régressions, puis viser une baisse monotone jusqu’à zéro.

## Ordre de traitement Ruff format

La dette Ruff doit rester séparée des refactorings métier et architecturaux. Le premier sous-ensemble a déjà été traité sur quatre fichiers directement impliqués dans Pricing Import, avec un fichier effectivement reformatté et quatre fichiers conformes.

| Lot | Périmètre | Validation obligatoire |
|---|---|---|
| A | `backend/app/platform` | Ruff, mypy ciblé, tests plateforme |
| B | `backend/app/modules/pricing` | Tests pricing et diff-check |
| C | `backend/app/modules/membership` | Tests membership et diff-check |
| D | `backend/app/modules/decision` et `dce` | Tests décision/DCE et revue des imports |
| E | `backend/tests` par bounded context | Tests ciblés, sans modifier les assertions |
| F | `backend/app/interfaces`, `bootstrap`, `workers` | Validation composition root et workers |
| G | `scripts`, `ops` et fichiers auxiliaires | Vérifications shell propres au périmètre |

Chaque lot Ruff doit être formatage-only autant que possible. Les changements fonctionnels doivent avoir leur propre commit ou leur propre PR afin de conserver une revue lisible et une attribution fiable des régressions.

## Critères de sortie

Le plan sera considéré comme terminé lorsque `mypy backend` sera sans erreur, `ruff format --check .` sera entièrement conforme, le lint Ruff restera vert, la suite backend PostgreSQL et le gate de couverture de 85,50 % seront verts dans la CI, et les validations frontend resteront vertes.

La baseline actuelle ne revendique aucun déploiement VPS/staging/production, aucune disponibilité Docker locale ni aucune validation de fournisseurs externes.
