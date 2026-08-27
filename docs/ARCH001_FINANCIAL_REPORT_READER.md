# ARCH-001 — Lecteur de rapports financiers patronaux

## Objet

Ce micro-lot extrait la lecture des rapports financiers du service applicatif Membership vers un port `FinancialReportReader`. `PatronFinancialReportService` conserve les contrôles d’acteur patronal et d’autorisation financière, puis demande au port une projection bornée correspondant au tenant, au dossier, au rapport et à l’état demandé.

Le service applicatif ne dépend plus des modèles SQLAlchemy du module pricing pour construire cette projection. L’adaptateur `SqlAlchemyFinancialReportReader`, situé dans `membership.infrastructure`, porte la requête sur les tables de snapshots et de lignes financières.

## Contrat applicatif

Le contrat est défini dans `backend/app/modules/membership/application/queries.py` :

```python
class FinancialReportReader(Protocol):
    def get(
        self, *, tenant_id: UUID, case_id: UUID, report_id: UUID, state: str
    ) -> FinancialReportProjection | None: ...
```

Le retour `None` est traduit par le service en `NOT_FOUND_OR_FORBIDDEN`. L’autorisation intervient après résolution de la projection, comme dans le comportement préexistant, et la ressource autorisée reprend l’identifiant du rapport, le tenant et le dossier.

## Responsabilités de l’adaptateur

`SqlAlchemyFinancialReportReader` applique les invariants suivants :

| Invariant | Mise en œuvre |
|---|---|
| Isolation tenant | Snapshot et lignes filtrés par `tenant_id` |
| Contexte de dossier | Snapshot filtré par `case_id` |
| Rapport ciblé | Snapshot filtré par `report_id` |
| État explicite | Snapshot filtré par `state` (`DRAFT` ou `PUBLISHED`) |
| Lignes cohérentes | Lignes filtrées par tenant et `snapshot_id` |
| Ordre déterministe | Lignes triées par création puis identifiant |
| Projection financière bornée | Seuls résumé, lignes et métadonnées prévues sont retournés |

Les montants et quantités restent dans la projection applicative existante. Le lot ne modifie ni les calculs, ni les transitions DRAFT/PUBLISHED, ni les handlers d’ajout de ligne.

## Composition root et couverture

La composition root construit `SqlAlchemyFinancialReportReader(runtime.session_factory)` et l’injecte dans `PatronFinancialReportService`. Le test DB de lecture de brouillon utilise le même adaptateur concret. Un test sans DB vérifie indépendamment que le service appelle le port avec le contexte complet et conserve l’action `FINANCIAL_REPORT_READ`.

Le service reçoit désormais directement le port et n’ouvre plus de session ORM pour sa lecture. Les services de mutation financière voisins restent hors du périmètre de cette PR.

## Validation effectuée

| Contrôle | Résultat |
|---|---|
| Ruff ciblé et global | Réussi |
| Mypy ciblé sur port, service, adaptateur et bootstrap | Réussi |
| Test unitaire pur du service | `1 passed` |
| Tests DB locaux | Non exécutables dans le sandbox courant sans PostgreSQL sur `127.0.0.1:5432` ; les tests concernés restent marqués `db` |
| Suite backend hors DB | À exécuter avant publication de la PR |
| CI PostgreSQL, couverture, Trivy et image-security | Validation complète attendue sur GitHub après push |
| VPS, staging, production et fournisseurs externes | Non concernés et non revendiqués |

## Limites

Ce lot ne revendique aucune mesure de performance, absence de N+1 en environnement cible, recette PostgreSQL externe, déploiement ou validation commerciale. Il n’ajoute pas de cache distribué ni de pagination. Ces sujets restent séparés afin de préserver un périmètre de revue et de rollback réduit.
