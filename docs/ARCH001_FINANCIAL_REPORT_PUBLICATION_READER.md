# ARCH-001 — Lecteur du snapshot pour la publication financière

## Objet

Ce micro-lot extrait le lookup préalable du snapshot financier de `PatronFinancialReportPublicationService`. La façade Membership conserve la garde patronale, l’autorisation `FINANCIAL_REPORT_PUBLISH` et le dispatch de la commande. Elle dépend désormais de `FinancialReportSnapshotExistenceReader`, déjà défini dans les contrats applicatifs Membership.

L’adaptateur `SqlAlchemyFinancialReportReader` expose maintenant une méthode `exists` tenant-scoped en plus de sa lecture de projection. La composition root injecte une instance de cet adaptateur dans le service de publication. Le handler reste responsable de la transaction DRAFT → PUBLISHED, du verrouillage du snapshot et de l’écriture de l’acte append-only de publication.

## Invariants préservés

| Invariant | Mise en œuvre |
|---|---|
| Acteur | Seul `PATRON_ADMIN` avec membership est accepté |
| Autorisation | `FINANCIAL_REPORT_PUBLISH` est évaluée avant le lookup |
| Isolation | L’existence est filtrée par tenant, dossier et rapport |
| Ressource absente | Le service retourne `NOT_FOUND_OR_FORBIDDEN` |
| Mutation | Le dispatcher et le handler transactionnel restent inchangés |
| Publication | Le handler conserve verrou, état DRAFT, révision et publication append-only |

Le lot ne modifie ni les calculs financiers, ni le contrat HTTP, ni les transitions métier.

## Couverture

Une mesure locale branchée sur les deux tests purs de frontière donne le résultat suivant :

| Périmètre | Statements | Branches | Couverture |
|---|---:|---:|---:|
| Service de publication, incluant son handler DB | 43 | 14 | 49,12 % |
| Contrats applicatifs `queries.py` | 76 | 0 | 100 % |
| Adaptateur financier, incluant la projection complète | 19 | 2 | 61,90 % |
| **Total ciblé local** | **138** | **16** | **75,97 %** |

Cette valeur est volontairement présentée avec son périmètre : le test pur exerce la façade et `exists`, mais pas l’ensemble du handler transactionnel ni la construction complète de projection. Les tests DB existants et la CI PostgreSQL restent nécessaires pour la couverture du chemin de publication et de lecture complet.

Le dernier rapport complet récupéré depuis la CI verte de `main` avant ce micro-lot indique **88,77 %** de couverture globale, soit 17 621 lignes couvertes sur 19 213 et 2 585 branches couvertes sur 3 550. Le gate configuré est de 85,50 %. Le rapport de la branche courante sera confirmé par la CI PR puis par la CI post-merge.

## Qualité

| Contrôle | Résultat |
|---|---|
| Ruff ciblé | Réussi |
| Mypy ciblé | Réussi |
| Tests purs de frontière | `2 passed` |
| Suite backend hors DB | À confirmer avant publication |
| Frontend typecheck/lint/Vitest/build | À confirmer avant publication |
| PostgreSQL, migrations, couverture globale, Trivy et image-security | À confirmer par CI |

## Limites externes

Aucune validation PostgreSQL locale n’est revendiquée sans daemon/instance disponible. Aucun déploiement VPS, staging ou production, aucune recette Docker/ClamAV/EICAR, aucun fournisseur externe, eIDAS, corpus DCE/OCR/RAG ou validation juridique n’est couvert par ce lot.
