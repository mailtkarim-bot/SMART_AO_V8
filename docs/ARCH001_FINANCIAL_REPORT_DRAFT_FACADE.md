# ARCH-001 — Façade de création des brouillons financiers

Ce lot sépare la façade patronale de création d’un brouillon financier de son handler transactionnel SQLAlchemy, sans modifier le contrat métier ni le périmètre financier existant.

## Frontière livrée

`PatronFinancialReportDraftCreationService` reste responsable du contrôle préalable de l’acteur patron, de l’autorisation sur la Case financière, de la lecture tenant-scoped via `FinancialDraftCaseReader` et de la construction du `CommandContext`. La façade ne contient plus d’import SQLAlchemy, de modèle de persistance ou de logique de mutation.

`CreateFinancialReportDraftHandler`, déplacé dans `financial_report_draft_handler.py`, conserve l’accès transactionnel à la Case et au snapshot financier. Il verrouille la Case, refuse une Case inexistante, empêche l’ouverture d’un second brouillon actif, initialise le snapshot en `DRAFT` et publie l’événement correspondant via le dispatcher.

Le bootstrap continue d’enregistrer le handler sous `CreateFinancialReportDraft` grâce à la réexportation conservée par le module façade. Aucun câblage frontend ni nouveau contrat financier n’a été ajouté.

## Invariants conservés

- Uniquement un `PATRON_ADMIN` avec membership peut atteindre la lecture financière.
- La décision d’autorisation intervient avant la résolution de la Case et avant toute exposition de données financières.
- La Case est bornée par `tenant_id` et `case_id`.
- La création reste atomique dans la transaction du dispatcher et protégée par verrou de ligne.
- Un seul brouillon `DRAFT` ouvert est autorisé par Case.
- Le snapshot initial reste en unités mineures, sans calcul inventé ni publication implicite.
- L’événement `FinancialReportDraftCreated` et le résultat applicatif restent inchangés.

Deux tests purs de frontière couvrent le garde-fou patronal avant lecture, l’autorisation et le `case_id` propagé au dispatcher. Les tests PostgreSQL, migrations et couverture complète sont vérifiés par la CI GitHub ; ils ne sont pas revendiqués localement sans PostgreSQL disponible.
