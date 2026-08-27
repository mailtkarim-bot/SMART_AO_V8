# ARCH-001 — Façade de publication du rapport financier

Ce lot sépare la façade patronale de publication d’un snapshot financier de son handler transactionnel SQLAlchemy, sans modifier la publication immuable existante.

## Frontière livrée

`PatronFinancialReportPublicationService` reste responsable du garde-fou patronal, de l’autorisation financière, de la vérification tenant-scoped du snapshot via `FinancialReportSnapshotExistenceReader` et de la construction du `CommandContext`. La façade ne contient plus d’import ORM ni de mutation directe.

`PublishFinancialReportHandler`, déplacé dans `financial_report_publication_handler.py`, conserve le verrou du snapshot, le contrôle de l’état `DRAFT`, la révision attendue, le passage à `PUBLISHED`, l’acte append-only `FinancialReportPublicationRecord` et l’événement `FinancialReportPublished`.

Le handler reste réexporté par le module façade afin de préserver l’enregistrement existant du dispatcher, les routes et les tests de publication.

## Invariants conservés

- Seul un `PATRON_ADMIN` avec membership peut atteindre la ressource financière.
- L’autorisation intervient avant la résolution du snapshot et reste bornée par tenant, affaire et rapport.
- Un snapshot inexistant, déjà publié ou avec une révision obsolète reste refusé.
- La publication est atomique dans la transaction du dispatcher et protégée par verrou de ligne.
- L’acte de publication est append-only et l’événement conserve le rapport, l’affaire et la révision résultante.
- Aucun montant financier n’est exposé ou recalculé par la façade.

Le test de frontière existant couvre le garde-fou patronal, l’autorisation et le dispatch. Les tests PostgreSQL, migrations et couverture complète restent validés par la CI GitHub.

## Limites de validation locale

PostgreSQL n’est pas disponible dans la sandbox. Les tests DB et la couverture complète ne sont donc pas revendiqués localement ; aucune preuve de staging ou de production n’est déduite de ce refactoring.
