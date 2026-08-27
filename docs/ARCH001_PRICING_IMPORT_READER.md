# ARCH-001 — Lecteur de preview d’import pricing

## Objet

Ce micro-lot extrait la lecture d’une preview pricing normalisée de `PricingImportReadService` vers le port applicatif `ImportPreviewReader`. Le service conserve la vérification de l’acteur patronal et la politique de confidentialité financière, tandis que l’adaptateur SQLAlchemy construit la projection à partir des tables de batch, de lignes et de transitions.

Le service applicatif ne dépend plus directement des modèles SQLAlchemy pricing pour ce parcours de lecture. `SqlAlchemyImportPreviewReader` est construit dans la composition root et injecté dans le service.

## Contrat

Le contrat applicatif est défini dans `backend/app/modules/pricing/application/ports.py` :

```python
class ImportPreviewReader(Protocol):
    def get(
        self, *, tenant_id: UUID, case_id: UUID, batch_id: UUID
    ) -> PricingImportBatchProjection | None: ...
```

L’absence de batch est traitée par le service avec `NOT_FOUND_OR_FORBIDDEN`. Le lecteur ne prend pas de décision d’autorisation et ne renvoie pas de colonnes de stockage ou de hash source dans la projection.

## Invariants préservés

| Invariant | Mise en œuvre |
|---|---|
| Tenant | Batch, transition et lignes filtrés par `tenant_id` |
| Dossier | Batch filtré par `case_id` |
| Batch | Batch filtré par `batch_id` |
| État actuel | Dernière transition append-only prioritaire sur l’état figé du batch |
| Révision actuelle | Version de la dernière transition, sinon révision du batch |
| Ordre des lignes | `row_number` croissant |
| Confidentialité | L’autorisation `FINANCIAL_REPORT_LINE_WRITE` et la classification financière restent dans le service |

Cette séparation conserve le correctif antérieur qui fait des transitions append-only la source de vérité pour l’état courant d’une preview.

## Validation

Un test sans DB vérifie que le service appelle le port avec le tenant, le dossier et le batch complets, puis autorise la ressource `PRICING_IMPORT`. Les tests existants de lecture et de commit pricing utilisent l’adaptateur concret en validation DB.

| Contrôle | Résultat |
|---|---|
| Ruff ciblé | Réussi |
| Mypy ciblé sur port, service, adaptateur et bootstrap | Réussi |
| Test unitaire pur du service | `1 passed` |
| Suite backend hors DB | À exécuter avant publication de la PR |
| Tests DB locaux | Dépendants de PostgreSQL ; non revendiqués sans service disponible sur `127.0.0.1:5432` |
| CI PostgreSQL, couverture, Trivy et image-security | Attendues après push |

## Limites

Ce lot ne change ni les calculs pricing, ni les transitions métier, ni les routes publiques. Il n’ajoute ni cache, ni pagination, ni profilage. Il ne revendique aucune validation de corpus DCE, de fournisseur externe, de staging, de production ou de VPS.
