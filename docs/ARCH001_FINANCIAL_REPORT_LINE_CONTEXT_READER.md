# ARCH-001 — Lecteur de contexte pour l’ajout de lignes financières

## Objet

Ce micro-lot extrait du service `PatronFinancialReportLineService` le lookup préalable du snapshot financier. Le service conserve la garde d’acteur patronal, l’autorisation financière et le dispatch de la commande. La vérification d’existence est déléguée au port applicatif `FinancialReportSnapshotExistenceReader`.

L’adaptateur `SqlAlchemyFinancialReportSnapshotReader`, situé dans `membership.infrastructure`, exécute la requête tenant-scoped sur le modèle de snapshot pricing. La composition root est responsable de son instanciation et de son injection.

## Contrat applicatif

Le contrat est défini dans `backend/app/modules/membership/application/queries.py` :

```python
class FinancialReportSnapshotExistenceReader(Protocol):
    def exists(self, *, tenant_id: UUID, case_id: UUID, report_id: UUID) -> bool: ...
```

Le service traduit une absence en `NOT_FOUND_OR_FORBIDDEN`, comme avant l’extraction. La résolution reste postérieure à la garde patronale et à la décision `FINANCIAL_REPORT_LINE_WRITE`; aucune information financière n’est résolue pour un acteur non patronal.

## Invariants préservés

| Invariant | Mise en œuvre |
|---|---|
| Isolation tenant | Filtre `FinancialReportSnapshotRecord.tenant_id` |
| Contexte dossier | Filtre `case_id` |
| Ressource | Filtre `report_id` |
| Confidentialité | Garde patronale avant lookup, puis politique financière |
| Mutation métier | Toujours effectuée par le dispatcher et le handler transactionnel existant |
| Versionnement | Le handler conserve le verrou, l’état DRAFT et le contrôle de révision |

Le handler `AddFinancialReportLineHandler` reste dans le périmètre transactionnel et conserve ses contrôles de verrouillage, d’état et de version. Ce lot ne modifie ni les totaux, ni les événements, ni les messages outbox.

## Tests et validations

Le test DB existant des lignes financières utilise l’adaptateur concret. Un test sans DB vérifie que le service appelle le port avec le tenant, le dossier et le rapport, conserve la politique `FINANCIAL_REPORT_LINE_WRITE` et ne déclenche le dispatcher qu’après résolution positive.

| Contrôle | Résultat attendu |
|---|---|
| Ruff ciblé et global | Réussi |
| Mypy ciblé | Réussi |
| Test unitaire pur | `1 passed` |
| Suite backend hors DB | À exécuter avant publication |
| Tests DB PostgreSQL/migrations/couverture | Délégués à la CI GitHub |
| Frontend typecheck/lint/Vitest/build | À exécuter avant publication |

## Limites explicites

Les tests DB locaux restent dépendants d’un PostgreSQL disponible ; aucune recette locale n’est revendiquée sans ce service. Ce refactoring ne constitue ni un déploiement VPS/staging/production, ni une validation de fournisseur, de secret, d’eIDAS ou de corpus métier. Les métriques N+1 et de performance restent hors périmètre.
