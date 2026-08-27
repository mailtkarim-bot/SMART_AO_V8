# ARCH-001 — Lecteur de dossier pour la création de brouillons financiers

## Objet

Ce micro-lot extrait du service `PatronFinancialReportDraftCreationService` le contrôle d’existence du dossier avant le dispatch de la commande de création d’un brouillon financier. Le service conserve la garde d’acteur patronal, l’autorisation financière et le dispatch. Le handler transactionnel conserve la création du snapshot DRAFT, le verrouillage du dossier et le contrôle d’unicité du brouillon ouvert.

Le contrat `FinancialDraftCaseReader` est placé dans `membership/application/queries.py`. La réalisation `SqlAlchemyFinancialDraftCaseReader`, située dans `membership/infrastructure`, effectue un lookup tenant-scoped sur `CaseRecord`. La composition root est la seule zone qui construit l’adaptateur.

## Contrat et invariants

```python
class FinancialDraftCaseReader(Protocol):
    def exists(self, *, tenant_id: UUID, case_id: UUID) -> bool: ...
```

| Invariant | Vérification |
|---|---|
| Isolation tenant | Le lecteur filtre `CaseRecord.tenant_id` |
| Dossier ciblé | Le lecteur filtre `CaseRecord.id` |
| Confidentialité financière | L’acteur patronal est contrôlé avant le lecteur |
| Autorisation | `FINANCIAL_REPORT_CREATE` est évaluée avant le lookup |
| Absence du dossier | Le service retourne `NOT_FOUND_OR_FORBIDDEN` |
| Mutation | Le dispatcher et le handler existants restent responsables de la transaction |

Le refactoring ne change ni le contrat HTTP, ni les commandes, ni les tables, ni les événements/outbox. Le handler continue de vérifier le dossier sous verrou et d’empêcher un second brouillon DRAFT ouvert.

## Couverture du code refactorisé

La mesure a été réalisée avec `coverage run --branch` sur les tests unitaires purs du lot, puis avec un rapport ciblé sur les modules applicatifs et l’adaptateur. Les cinq tests purs sont passés.

| Fichier | Statements | Branches | Couverture ciblée | Interprétation |
|---|---:|---:|---:|---|
| `financial_report_draft.py` | 40 | 12 | 67,31 % | La façade refactorisée est exercée ; les lignes 103–147 du handler DB transactionnel restent hors de ce test pur |
| `queries.py` | 76 | 0 | 100 % | Contrats et types importés dans le périmètre |
| `financial_draft_case_reader.py` | 11 | 0 | 100 % | Adaptateur exercé avec session mockée ; recette PostgreSQL réelle réservée à la CI |
| **Total ciblé** | **127** | **12** | **87,77 %** | Rapport ciblé, sans inclure le fichier de test lui-même |

La couverture de la façade de service est complétée par les scénarios d’acteur non patronal, de politique refusée, de dossier absent et de résolution positive. La couverture du handler transactionnel demeure portée par les tests DB existants et par la CI PostgreSQL ; elle n’est pas artificiellement déduite du test pur.

## Métriques de qualité

| Contrôle | Résultat |
|---|---|
| Ruff ciblé | Réussi |
| Format Ruff des fichiers touchés | Les cinq fichiers touchés sont formatés |
| Mypy ciblé | Aucun problème sur quatre fichiers source |
| Tests unitaires purs | `5 passed` |
| Suite backend hors DB | À exécuter avant publication de la PR |
| Frontend typecheck/lint/Vitest/build | À exécuter avant publication de la PR |
| CI PostgreSQL, migrations, couverture globale, Trivy et image-security | Validation attendue après push |

Une tentative de rapport de couverture sur toute la suite hors DB est informative seulement : le gate global de couverture à 85,50 % ne peut pas être conclu avec cette sélection partielle, car les handlers DB et les tests d’intégration PostgreSQL sont alors exclus ou sous-exercés. La valeur de référence de décision reste celle produite par la CI complète.

## Limites explicites

Ce lot ne revendique aucun accès à PostgreSQL cible hors CI, aucune validation Docker locale, aucun déploiement VPS/staging/production et aucune recette de fournisseur externe. Il ne traite pas la couverture globale historique, le profilage N+1, la performance ou la validation juridique des sorties financières.
