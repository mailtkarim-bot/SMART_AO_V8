# ARCH-001 — Façade des lignes de rapport financier

Ce lot sépare la façade patronale d’ajout de lignes financières de son handler transactionnel SQLAlchemy, sans changer le contrat métier ni les règles de calcul existantes.

## Frontière livrée

`PatronFinancialReportLineService` conserve le garde-fou patronal, l’autorisation sur la ressource financière, la vérification tenant-scoped du snapshot via `FinancialReportSnapshotExistenceReader` et la construction du `CommandContext`. La façade ne contient plus d’import ORM ni de mutation de snapshot.

`AddFinancialReportLineHandler`, déplacé dans `financial_report_lines_handler.py`, conserve le verrou du snapshot, le contrôle de l’état `DRAFT`, la révision attendue, l’écriture de la ligne, la mise à jour du total de la catégorie et l’événement append-only `FinancialReportLineAdded`.

La factory `financial_report_line_handlers()` reste réexportée par le module façade afin de préserver le câblage existant du dispatcher, les routes et les tests de concurrence.

## Invariants conservés

- Seul un `PATRON_ADMIN` avec membership peut atteindre le périmètre financier.
- La lecture d’existence du snapshot intervient après l’autorisation et reste bornée par tenant, affaire et rapport.
- Une ligne ne peut être ajoutée qu’à un snapshot `DRAFT` verrouillé dans la transaction du dispatcher.
- Une révision obsolète provoque toujours `VERSION_CONFLICT`.
- Les catégories autorisées et leurs champs de total restent inchangés.
- La ligne et la nouvelle révision sont écrites atomiquement avec l’événement correspondant.
- Aucun montant financier n’est exposé au collaborateur ni inventé par la façade.

Le test de frontière existant continue de vérifier l’autorisation et le dispatch applicatif ; les tests DB et de concurrence restent nécessaires pour la preuve PostgreSQL complète.

## Limites de validation locale

PostgreSQL n’est pas disponible localement. Les tests marqués `db`, les migrations, la concurrence réelle et la couverture complète sont validés par la CI GitHub uniquement.
