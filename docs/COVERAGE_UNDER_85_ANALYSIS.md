# Analyse des modules sous 85 % de couverture

## Synthèse

La campagne globale finale a exécuté **522 tests**, tous réussis, et atteint **86,12 % de couverture globale** avec branches activées. Le worker `dce_retention.py` est à **97,45 %**, le worker `submission_export_webhook.py` à **98,62 %**, et le module `enterprise_upload.py` à **95,85 %** sur sa campagne ciblée. Les tests ajoutés ont donc atteint le jalon de 86 % sans exclusion artificielle de code.

Le seuil CI strict reste fixé à **85,50 %** avec une précision de deux décimales. La marge globale observée est de 0,62 point, ce qui constitue une marge opérationnelle raisonnable mais doit être protégée par les tests de non-régression et le suivi des lignes nouvellement introduites.

## Modules sous 85 %

| Priorité | Module | Couverture | Pourquoi il est prioritaire |
|---|---|---:|---|
| P0 | `platform/observability/logging.py` | 59,38 % | Socle transversal, peu de tests et branches de formatage/propagation encore non exercées |
| P0 | `modules/preparation/infrastructure/document_storage.py` | 76,60 % | I/O documentaire et chemins d’erreur directement liés aux uploads et à la génération |
| P0 | `modules/preparation/application/transmission.py` | 76,64 % | Transmission de préparation, erreurs et transitions de processus métier |
| P0 | `modules/preparation/application/review.py` | 78,11 % | Revue humaine et décisions de blocage, forte densité de branches métier |
| P0 | `modules/preparation/application/service.py` | 79,86 % | Orchestration centrale du wizard, readiness et génération documentaire |
| P1 | `modules/membership/application/collab_info_blockers.py` | 77,09 % | Blocages et demandes d’information du wizard collaborateur |
| P1 | `modules/membership/application/collab_work_task.py` | 77,06 % | Workflow des tâches collaborateur et transitions d’état |
| P1 | `modules/membership/application/patron_assignment.py` | 81,13 % | Affectations patron/collaborateur et contrôle de révision |
| P1 | `modules/membership/application/assignment.py` | 81,08 % | Journal et changements d’affectation |
| P1 | `modules/membership/application/collab_capability.py` | 83,44 % | Propositions de capacités et écarts de qualification |
| P1 | `modules/membership/application/financial_report_publication.py` | 79,31 % | Publication et refus des snapshots financiers |
| P1 | `modules/membership/application/financial_report_draft.py` | 84,91 % | Dernières branches d’erreur du brouillon financier |
| P1 | `modules/patron_action/application/service.py` | 81,00 % | Actions patronales et fermeture des dossiers |
| P1 | `modules/patron_action/application/transition_service.py` | 83,56 % | Transitions de workflow patronal |
| P1 | `modules/pricing/application/import_service.py` | 79,78 % | Cas d’erreur et idempotence d’import DPGF/BPU |
| P1 | `modules/submission/application/evidence_service.py` | 80,95 % | Enregistrement et contrôle des preuves de dépôt |
| P2 | `platform/persistence/repository.py` | 75,86 % | Cas génériques de lecture, absence et concurrence repository |
| P2 | `platform/security/authenticated_context.py` | 81,93 % | Expiration, identité et contexte authentifié |
| P2 | `platform/security/bootstrap.py` | 85,38 % | Légèrement sous le seuil individuel, surtout chemins de configuration |

## Plan d’optimisation

La première vague doit traiter l’observabilité et le stockage documentaire, car ces composants ont une forte portée transversale et leur couverture faible masque rapidement des régressions. Elle doit ajouter des tests de logs structurés, corrélation, erreurs de sérialisation, chemins de fichier absent, limites de taille, suppression idempotente et refus d’extensions non autorisées.

La deuxième vague doit couvrir le wizard de préparation et de collaboration. Les tests doivent être organisés par invariants : tenant résolu serveur, révision optimiste, transitions autorisées, états bloqués, demandes d’information, absence de preuves et idempotence des commandes. Les tests d’intégration PostgreSQL sont requis lorsqu’une contrainte ou une outbox participe à la décision.

La troisième vague doit renforcer les modules métier plus proches du seuil : brouillon financier, publication, pricing, preuves de dépôt et actions patronales. Chaque nouveau slice doit viser au moins 90 % sur son module principal et conserver une marge globale supérieure à 86 %.

## Critères de maintien

Un changement ne doit pas réduire la couverture globale sous 86 %. Un module métier nouveau doit atteindre au minimum 85,50 % avec branches activées, et les chemins de sécurité, confidentialité financière, tenant isolation et idempotence doivent être testés explicitement. Les rapports JSON CI doivent rester archivés afin de comparer les lignes et branches, pas seulement le pourcentage arrondi.

## Références

[1]: https://coverage.readthedocs.io/en/latest/ "Coverage.py documentation"
[2]: https://docs.pytest.org/en/stable/ "pytest documentation"
