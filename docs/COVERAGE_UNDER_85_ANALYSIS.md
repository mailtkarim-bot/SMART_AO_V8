# Plan détaillé de remontée de couverture sous 85 %

**Branche de référence :** `ops/vps-deploy-health-digests-01`
**Dernière campagne analysée :** 19 août 2026, rapport `/tmp/smart-ao-coverage-86-final/coverage.json`
**État de référence :** 522 tests réussis, couverture globale avec branches à **86,12 %**, gate CI à **85,50 %** avec précision à deux décimales.

## 1. Décision de pilotage

Le jalon global de 86 % est atteint, mais la marge par rapport au gate strict n’est que de 0,62 point. La couverture globale ne prouve donc pas que chaque couche est suffisamment testée. Le dernier rapport révèle notamment des interfaces HTTP entre 29,31 % et 65,62 %, alors que plusieurs services métier se situent entre 76 % et 85 %. Les tests de routes doivent prouver le contrat HTTP et l’isolation serveur, tandis que les tests applicatifs doivent prouver les transitions, l’idempotence, la révision optimiste et les invariants de confidentialité.

Le plan ne recommande pas d’ajouter des tests artificiels pour faire monter un pourcentage. Chaque cas doit correspondre à un comportement observable, une erreur attendue ou un invariant de sécurité. Un lot n’est terminé que si ses tests passent localement, si Ruff et le scan de secrets passent, si la couverture globale reste au moins à 86,00 %, et si la CI est verte.

> **Règle de livraison :** aucun nouveau code métier ne doit être fusionné sans ses tests de branches et sans preuve que les contrats tenant, confidentialité financière, append-only, révision optimiste et idempotence restent valides.

## 2. Inventaire exact du dernier rapport

Les valeurs ci-dessous proviennent du rapport JSON de couverture avec `branch_coverage=true`. Les lignes indiquées sont les lignes déclarées manquantes par Coverage.py ; elles servent à construire les tests, et non à modifier les exclusions de couverture.

| Niveau | Module | Couverture | Diagnostic |
|---|---|---:|---|
| P0 | `bootstrap/production.py` | 0,00 % | Factory de production et variables obligatoires non exercées. |
| P0 | `interfaces/http/routes/patron_submission.py` | 29,31 % | Contrat HTTP de dépôt patronal largement non testé. |
| P0 | `interfaces/http/routes/patron_actions.py` | 35,48 % | Actions et erreurs HTTP patronales insuffisamment vérifiées. |
| P0 | `interfaces/http/routes/preparation_transmission.py` | 37,50 % | Contrat de transmission non couvert au niveau HTTP. |
| P0 | `interfaces/http/routes/patron_enterprise_library.py` | 37,58 % | Upload, vérification et accès à la bibliothèque patronale. |
| P0 | `interfaces/http/routes/patron_pricing.py` | 40,98 % | Sélection et archivage pricing peu couverts. |
| P0 | `interfaces/http/routes/collaborator_capabilities.py` | 44,30 % | Propositions de capacités et gaps côté collaborateur. |
| P0 | `interfaces/http/routes/patron_enterprise_capabilities.py` | 49,40 % | Contrôle patronal des qualifications et références. |
| P0 | `interfaces/http/routes/patron_decisions.py` | 50,00 % | Décisions patronales presque uniquement nominales. |
| P0 | `interfaces/http/routes/patron_submission_evidence.py` | 50,00 % | Preuves de dépôt et réponses d’erreur. |
| P0 | `interfaces/http/routes/preparation.py` | 52,58 % | Route centrale du wizard et branches de validation. |
| P0 | `interfaces/http/routes/collaborator_work_tasks.py` | 59,32 % | Création, mise à jour et résultats des tâches. |
| P0 | `platform/observability/logging.py` | 59,38 % | Exception JSON et configuration idempotente absentes. |
| P0 | `interfaces/http/routes/patron_financial_reports.py` | 61,40 % | Route sensible : refus et erreurs à prouver. |
| P0 | `modules/dce/infrastructure/quarantine.py` | 65,56 % | Quarantaine, scan et nettoyage incomplets. |
| P0 | `interfaces/http/routes/collaborator_info_blockers.py` | 65,62 % | Blocages et demandes d’information HTTP. |
| P1 | `modules/dce/infrastructure/case_dce_reading_reader.py` | 71,84 % | Lecture tenant-scoped et états DCE. |
| P1 | `platform/persistence/repository.py` | 75,86 % | Absence, concurrence et chemins repository. |
| P1 | `modules/dce/application/handlers.py` | 76,43 % | Nombreuses branches DCE à découper par sous-domaine. |
| P1 | `modules/preparation/infrastructure/document_storage.py` | 76,60 % | Collision, nettoyage temporaire et traversal. |
| P1 | `modules/preparation/application/transmission.py` | 76,64 % | Scope, révision et append-only. |
| P1 | `modules/membership/application/collab_work_task.py` | 77,06 % | Transitions et résultats manquants. |
| P1 | `modules/membership/application/collab_info_blockers.py` | 77,09 % | Demandes d’information et clôture. |
| P1 | `interfaces/http/error_mapping.py` | 77,78 % | Dernière branche d’erreur générique. |
| P1 | `modules/preparation/application/review.py` | 78,11 % | Revue humaine et correction append-only. |
| P1 | `modules/case/domain/case.py` | 78,33 % | Règles de transition du domaine case. |
| P1 | `modules/dce/application/upload.py` | 78,38 % | Upload DCE et erreurs de stockage/scanner. |
| P1 | `modules/dce/domain/dce_version.py` | 79,27 % | Validité temporelle et transitions DCE. |
| P1 | `modules/membership/application/financial_report_publication.py` | 79,31 % | Publication/refus des snapshots financiers. |
| P1 | `modules/pricing/application/import_service.py` | 79,78 % | Import DPGF/BPU, idempotence et formats. |
| P1 | `modules/preparation/application/service.py` | 79,86 % | Orchestrateur readiness et génération. |
| P1 | `modules/submission/application/evidence_service.py` | 80,95 % | Erreurs de preuve et matérialisation. |
| P1 | `modules/patron_action/application/service.py` | 81,00 % | Actions patronales et fermeture. |
| P1 | `modules/membership/application/assignment.py` | 81,08 % | Affectations, scope, révision et absence. |
| P1 | `modules/membership/application/patron_assignment.py` | 81,13 % | Service volumineux à découper par commande. |
| P1 | `platform/security/authenticated_context.py` | 81,93 % | Expiration, identité et tenant. |
| P1 | `interfaces/http/routes/consultations.py` | 82,09 % | Accès aux consultations et erreurs de contexte. |
| P1 | `modules/membership/application/collab_capability.py` | 83,44 % | Preuves, propositions et gaps proches du seuil. |
| P1 | `modules/patron_action/application/transition_service.py` | 83,56 % | Transitions patronales restantes. |
| P2 | `interfaces/http/routes/dce_versions.py` | 84,29 % | Cas HTTP de version DCE. |
| P2 | `modules/dce/application/commands.py` | 84,87 % | Branches de validation de commandes. |
| P2 | `modules/membership/application/financial_report_draft.py` | 84,91 % | Quatre branches d’erreur du brouillon financier. |

## 3. Lots de travail et ordre recommandé

### Lot A — Fondations techniques à haut rendement

Traiter `logging.py`, `document_storage.py`, `repository.py`, `error_mapping.py`, `authenticated_context.py` et `bootstrap/production.py`. Ces modules sont transversaux et relativement petits.

Le logging doit couvrir la sérialisation d’une exception, l’absence des métadonnées HTTP optionnelles, les valeurs `0` et chaînes vides, le JSON stable et l’absence de payload métier arbitraire. La configuration doit être testée avec un handler déjà structuré, un handler non structuré et plusieurs appels consécutifs afin de prouver l’idempotence.

Le stockage doit tester les interfaces abstraites qui lèvent `NotImplementedError`, la collision de clé, le nettoyage temporaire après échec d’écriture ou de remplacement, les permissions `0700`/`0600`, la lecture, les clés absolues, `.`, `..`, segments vides et l’évasion du root. Le hash retourné doit correspondre exactement aux octets écrits.

La factory de production doit être testée sans serveur réel : variables absentes ou placeholders, construction valide, live/readiness et échec contrôlé d’une dépendance. Aucune clé JWT réelle ne doit apparaître dans les tests ou les logs.

**Sortie attendue :** chaque module du lot à plus de 90 % avec branches et campagne globale à au moins 86 %.

### Lot B — Contrats HTTP du wizard et du cockpit patron

Pour chaque route sous 65 %, tester acteur absent ou invalide, tenant différent, ressource absente, capability refusée, révision incorrecte, commande rejouée, validation de schéma et succès nominal. Les réponses collaborateur ne doivent contenir ni montant, ni ligne de prix, ni snapshot financier.

Les routes de préparation, transmission, tâches et blocages doivent partager des fixtures de contexte, mais chaque test doit contrôler le tenant résolu côté serveur. Les routes patronales de dépôt, actions, décisions, preuves, bibliothèque entreprise, capacités et pricing doivent prouver la séparation patron/collaborateur au niveau HTTP et au niveau handler.

La route financière patronale doit couvrir snapshot publié, révision incorrecte, refus et publication déjà effectuée. Les erreurs financières ne doivent jamais être rendues dans un contrat collaborateur ou un webhook.

**Sortie attendue :** succès et branches de refus couverts pour chaque route touchée, avec preuve de non-fuite.

### Lot C — DCE, quarantaine et stockage intégré

Regrouper `quarantine.py`, `case_dce_reading_reader.py`, `dce/application/upload.py`, `dce/application/handlers.py`, `dce/domain/dce_version.py`, `dce/application/commands.py` et `dce_versions.py` par comportement : scan propre, rejet EICAR, MIME refusé, taille dépassée, cible inexistante, expiration, version publiée, tenant différent, collision d’idempotence et suppression idempotente.

Les tests PostgreSQL sont requis lorsque la décision dépend d’une version, d’une outbox ou d’un verrou. Les tests filesystem utilisent `tmp_path` et vérifient les permissions. Aucun document rejeté ne doit devenir `CLEAN` ou être matérialisé.

**Sortie attendue :** parcours upload → quarantaine → vérification → matérialisation couvert, avec rejet prouvant l’absence de publication.

### Lot D — Orchestrateur de préparation et revue

Le cœur est `preparation/application/service.py`, puis `transmission.py` et `review.py`. Couvrir acteur non collaborateur, absence d’assignation, fenêtre inactive, scope sans `WORK_TASK_WRITE`, autorisation refusée, paquet absent, mismatch case/assignment/DCE, conflit de révision, DCE absent, task bloquée, résultat manquant, capacité inactive, version expirée, preuve manquante/non validée/d’un autre tenant, gap bloquant, readiness absente, préparation bloquée et texte financier interdit.

Les tests doivent démontrer l’append-only des readiness et documents, la progression monotone des révisions, le manifest hashé sans finance, l’idempotence `command_id`, la clé de stockage tenant-scoped et l’absence de matérialisation après échec du stockage.

**Sortie attendue :** readiness, génération, transmission et revue humaine testées sur PostgreSQL avec immutabilité historique.

### Lot E — Wizard collaborateur, affectations et actions patronales

Couvrir `collab_work_task.py`, `collab_info_blockers.py`, `collab_capability.py`, `assignment.py`, `patron_assignment.py`, `patron_action/application/service.py` et `transition_service.py` dans l’ordre métier : affectation, information, tâche, capacité/preuve, action patronale, clôture.

Chaque transition teste l’état précédent invalide, acteur non autorisé, tenant différent, révision obsolète, rejeu idempotent, transition interdite, résultat absent et événement append-only. Les capacités vérifient l’expiration, la cohérence entreprise/capacité et l’absence de finance dans les contrats collaborateur.

**Sortie attendue :** rejeu sans double effet et aucun événement collaborateur financier.

### Lot F — Pricing, preuves, rapports financiers et finition

Traiter `pricing/application/import_service.py`, les routes pricing, `evidence_service.py`, les preuves HTTP, la publication et le brouillon financiers, puis les commandes DCE restantes.

Les imports couvrent fichier vide, en-têtes invalides, ligne invalide, format non supporté, doublon, idempotence et rollback transactionnel. Les rapports financiers couvrent snapshot publié, révision incorrecte, refus et publication déjà réalisée. Les preuves couvrent hash, état, tenant, révision et erreur de matérialisation.

**Sortie attendue :** modules proches de 85 % à plus de 90 % individuellement, global à au moins 86 %.

## 4. Discipline d’exécution par slice

Chaque slice commence par le rapport JSON et la lecture des tests existants. Les tests sont écrits avant toute modification métier non nécessaire. Exécuter Ruff sur les fichiers touchés, tests ciblés, campagne complète avec branches et `git diff --check`. Pousser seulement avec un arbre propre et une couverture locale au seuil de maintien.

Après le push, attendre l’état terminal de la CI. Un échec de couverture doit être analysé avec `scripts/compare_coverage_reports.py`, jamais corrigé par exclusion de lignes. Un échec de sécurité ou de build reste bloquant.

## 5. Critères de maintien

| Contrôle | Exigence |
|---|---|
| Gate CI global | `fail_under = 85.50`, précision 2 décimales, branches activées |
| Marge de travail | Couverture globale maintenue à **au moins 86,00 %** |
| Module nouveau | Au moins 85,50 % avec branches, cible recommandée 90 % |
| Tenant | Résolution serveur et requêtes filtrées par tenant |
| Confidentialité | Aucun montant, snapshot, ligne de prix, storage key ou contenu dans contrats collaborateur/webhooks |
| Immutabilité | Readiness, transmissions, audits et preuves append-only selon le contrat |
| Concurrence | Révision optimiste et idempotence par rejeu |
| Qualité | Ruff, scan de secrets et CI complète verts |

## Références

[1]: ../pyproject.toml "Configuration Coverage.py et gate global"
[2]: ../.github/workflows/ci.yml "Workflow CI backend, frontend et sécurité"
[3]: ../scripts/compare_coverage_reports.py "Comparaison des rapports local et CI"
[4]: COVERAGE_GATE_PRESENTATION_SCRIPT.md "Historique du jalon 85,50 % et 86 %"
[5]: ../backend/app/platform/observability/logging.py "Logging structuré"
[6]: ../backend/app/modules/preparation/infrastructure/document_storage.py "Stockage privé des documents générés"
[7]: ../backend/app/modules/preparation/application/service.py "Orchestrateur de préparation"
[8]: VPS_OPERATIONAL_VALIDATION_SPEC.md "Spécification de validation opérationnelle VPS"
