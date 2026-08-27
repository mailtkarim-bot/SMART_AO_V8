# ARCH-001 — Découplage de la façade Pricing Import

## Objet

`PricingImportService` autorise et dispatch la commande `CommitPricingImport`. Sa façade applicative ne réalisait aucune lecture via sa session SQLAlchemy : le `session_factory` était une dépendance directe d’infrastructure inutilisée, tandis que les lectures et mutations transactionnelles appartiennent au handler du dispatcher.

Le micro-lot supprime cette dépendance de la façade et met à jour la composition root ainsi que la fixture de test. Le handler `CommitPricingImportHandler` conserve ses accès ORM, ses verrous et toute la mutation atomique du batch, du snapshot financier, des lignes et de la transition append-only.

## Invariants préservés

| Invariant | Preuve |
|---|---|
| Acteur | `PATRON_ADMIN` et membership obligatoire |
| Autorisation | `FINANCIAL_REPORT_LINE_WRITE` évaluée avant dispatch |
| Isolation | Le contexte dispatch conserve tenant, dossier, identité et membership |
| Mutation | Le handler garde les lectures verrouillées et les écritures SQLAlchemy |
| Import | Les états `PREVIEWED` → `COMMITTED` et les versions restent inchangés |
| Architecture | La façade ne reçoit plus de `session_factory` inutile |

## Test ajouté

`backend/tests/architecture/test_pricing_import_facade.py` vérifie sans base de données que la façade autorise la commande, transmet le contexte tenant/dossier au dispatcher et fonctionne sans paramètre `session_factory`.

## Formatage Ruff — premier sous-ensemble

Le premier sous-ensemble couvre les quatre fichiers impliqués dans ce lot : le service, la composition root, la fixture de commit et le test de frontière. Un fichier de test préexistant a été reformatté ; les quatre fichiers sont maintenant conformes à `ruff format --check`. Le changement de formatage est resté limité au fichier de test directement touché.

## Validations locales

| Contrôle | Résultat |
|---|---|
| Suite backend hors DB | `1111 passed`, `477 deselected` |
| Ruff lint global | Réussi |
| Format Ruff du sous-ensemble | Réussi, quatre fichiers conformes |
| Mypy ciblé | Réussi sur service et composition root |
| Frontend typecheck/lint | Réussi |
| Tests frontend | `119 passed` |
| Build frontend | Réussi |
| PostgreSQL/migrations/couverture complète | À confirmer par CI |

Aucun changement n’a été committé directement sur `main`. Le lot doit rester sur sa branche dédiée jusqu’à la validation PR.
