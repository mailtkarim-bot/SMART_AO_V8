# SMART_AO V8 — Plan PATRON-ASSIGNMENT-MANAGEMENT-01

## Finalité

Ce plan prépare le futur périmètre patron de création et de pilotage des
affectations collaborateur. Il ne constitue pas une implémentation et ne doit
pas être branché tant que son contrat normatif, son catalogue de capabilities
et sa migration ne sont pas figés.

Le patron décide **qui** prépare une affaire et **avec quel périmètre
opérationnel**. Le collaborateur accuse réception, demande une clarification ou
signale une indisponibilité ; il ne modifie jamais lui-même son affectation.

## Commandes proposées

| Commande | Auteur | Transition durable | Non-effet obligatoire |
|---|---|---|---|
| `CreateCaseAssignment` | `PATRON_ADMIN` | Crée une affectation `ACTIVE` ou planifiée, avec scope fermé et révision `0`. | Ne révèle ni ne délègue prix, marge, décision ou dépôt. |
| `AmendCaseAssignmentScope` | `PATRON_ADMIN` | Crée une nouvelle révision de scope documentée et incrémente la révision d’agrégat. | N’écrase aucun accusé, clarification ou signalement antérieur. |
| `SuspendCaseAssignment` | `PATRON_ADMIN` | Rend l’affectation non utilisable par les commandes collaborateur. | Ne supprime ni historique ni audit. |
| `ReactivateCaseAssignment` | `PATRON_ADMIN` | Réactive une affectation suspendue dans une fenêtre temporelle valide. | Ne restaure pas des droits hors scope explicite. |
| `EndCaseAssignment` | `PATRON_ADMIN` | Termine définitivement l’affectation, avec motif fermé et horodatage. | Ne réutilise jamais une affectation terminée comme active. |

## Frontières non négociables

| Sujet | Décision de conception à figer |
|---|---|
| Tenant | Toute FK reste composite `(tenant_id, id)` ; aucun `assignment_id` sans tenant dans une query métier. |
| Finance | Les scopes patron ne peuvent jamais contenir `pricing.read`, `pricing.write`, `decision.finalize` ou `submission.authorize`. |
| Scope | Le catalogue de scopes collaborateur doit être fermé et validé côté serveur. Il devra inclure les interactions Assignment si elles sont explicitement déléguables, ou les maintenir hors délégation par décision documentée. |
| Historique | Les interactions COLLAB-ASSIGNMENT-01 restent append-only. Les modifications patron d’affectation doivent produire leur propre journal immutable. |
| Révision | Toute commande patron porte `expected_revision`; un conflit ne doit produire aucune écriture partielle. |
| Affaire | Une Case archivée, hors tenant ou arrêtée ne reçoit pas de nouvelle affectation active. |
| Décision humaine | Une affectation ne vaut ni validation technique, ni conformité, ni Go/No-Go, ni autorisation de dépôt. |

## Persistance attendue

Le slice devra étendre `CaseAssignmentRecord` sans rendre ses historiques
mutables. Une table append-only `case_assignment_change_events` est recommandée
pour stocker le type de transition, l’ancienne et la nouvelle révision, le motif
fermé, l’auteur patron, la membership cible et un manifeste de scope sans texte
libre non nécessaire.

La migration devra ajouter des contraintes d’état et de fenêtre temporelle,
conserver les FKs composites et créer des triggers interdisant `UPDATE` et
`DELETE` sur le journal de changements.

## Décisions à transformer en contrat normatif avant le code

| Sujet à figer | Décision préparatoire | Conséquence d’implémentation |
|---|---|---|
| Capability patron | Introduire `assignment.manage`, attribuée au seul `PATRON_ADMIN`. Ne pas réutiliser `membership.manage`, qui gouverne une autre frontière métier. | Policy, audit et OpenAPI portent une action dédiée et lisible. |
| Cible | La membership cible doit être `COLLABORATEUR`, `ACTIVE`, appartenir au même tenant et exister au moment de la commande. | Aucune affectation à un patron, à un système ou à une membership révoquée. |
| Scope d’actions | Le manifeste autorisé est une liste non vide déduite du catalogue collaborateur : `case.dce.read`, `dce.requirement.confirm`, `document.administrative.read`, `preparation.transmit`, `assignment.acknowledge`, `assignment.clarify`, `assignment.history.read`, `assignment.unavailability`. | Toute action financière, de décision finale, de dépôt, d’export sensible ou inconnue est rejetée avant écriture. |
| Classification | La seule classification déléguable dans ce slice est `INTERNAL_OPERATIONAL`. | Un scope ne peut pas élargir la visibilité des données métier sensibles. |
| Fenêtre d’effet | Une affectation créée avec `starts_at` futur reste `ACTIVE` mais non utilisable avant son début ; `ends_at`, si présent, doit être strictement postérieur. | Aucun état persistant « planifié » supplémentaire : le comportement reste compatible avec le garde d’exécution déjà publié. |
| Concurrence | Toute mutation porte `expected_revision` et verrouille l’affectation. | Conflit de révision : aucune mutation, aucun événement, aucun receipt ni outbox partiel. |
| Historique patron | Chaque création, scope amendé, suspension, réactivation et fin écrit un changement append-only distinct. | Les tables d’accusés, demandes et indisponibilités déjà publiées restent intactes. |

> Le futur contrat devra distinguer explicitement les données de commande éventuellement libres des champs durablement enregistrés. Aucun motif libre ne doit être projeté vers le collaborateur par défaut ; seuls les motifs fermés nécessaires au pilotage sont conservés dans le journal patron.

## Découpage d’implémentation proposé

| Étape | Livrable fermé | Critère de sortie |
|---|---|---|
| 1. Contrat | `PATRON-ASSIGNMENT-MANAGEMENT-01_CONTRAT.md`, matrice capabilities × rôles × states et schémas de commandes/erreurs. | Tous les enum, transitions, scopes autorisés, erreurs neutres et non-effets sont signés avant code. |
| 2. Domaine | Commandes Pydantic fermées, validateurs de scope/fenêtre/motif et événements de changement nominaux. | Les tests de domaine passent sans SQL ni FastAPI. |
| 3. Persistance | Migration suivante, extension minimale de `case_assignments` si indispensable, table `case_assignment_change_events`, FKs composites, index, checks et triggers append-only. | Cycle Alembic `upgrade head`, `check`, `downgrade base` vert ; contraintes prouvées sur PostgreSQL. |
| 4. Application | Service patron autorisé, handlers transactionnels, verrou optimiste, receipts d’idempotence, outbox et audit SEC-01. | Chaque commande réussie écrit de façon atomique l’agrégat, le changement patron, l’événement et le receipt. |
| 5. Contrôles intégrés | Tests PostgreSQL tenant-scopés, audits de refus et contrôle immédiat des commandes collaborateur après transition. | Une suspension ou fin bloque sans délai les interactions collaborateur existantes. |
| 6. HTTP patron | DTO publics fermés, routes bearer réelles et projections patron uniquement, après revue explicite du cockpit. | Les erreurs 401/403/404/409/422 sont documentées et les réponses ne divulguent aucune finance à un collaborateur. |
| 7. Livraison | OpenAPI, `PROJECT_STATE.md`, `todo.md`, validations globales, commit et CI GitHub. | Aucun écart SEC-01 et CI verte sur le commit publié. |

## Matrice de tests détaillée

Les tests doivent rester séparés par couche. Les données de test couvrent deux tenants, un patron, deux collaborateurs (un actif et un inactif), une Case active, une Case arrêtée, une Case archivée et une affectation en cours de validité.

| Niveau et fichier cible | Scénarios impératifs | Invariant vérifié |
|---|---|---|
| Domaine — `backend/tests/modules/membership/test_patron_assignment_commands.py` | Scope vide, action inconnue, action financière, classification hors catalogue, fenêtre inversée, motif de fin inconnu, cible non-collaborateur, révision négative. | Entrée rejetée avant toute persistance ou événement. |
| Handler — `backend/tests/modules/membership/test_patron_assignment_handlers.py` | Création active, début futur, amendement à la révision courante, conflit de révision, suspension, réactivation valide, fin, tentative de réactivation après fin. | Machine d’état : `ACTIVE → SUSPENDED → ACTIVE`, `ACTIVE → ENDED`, et aucun retour depuis `ENDED`. |
| Idempotence — même fichier handler | Rejeu identique des cinq commandes, clé identique avec charge divergente, commande en cours. | Un seul changement durable par commande ; réponse stable au rejeu ; `409` sans écriture pour le conflit. |
| PostgreSQL — `backend/tests/integration/test_patron_assignment_persistence.py` | FK cross-tenant, cible hors tenant, contrainte de fenêtre, contrainte d’état, index d’unicité d’affectation active, tentative SQL `UPDATE` ou `DELETE` du journal patron. | Tenant P0, intégrité référentielle et append-only sont appliqués par la base. |
| Régression collaborateur — extension de `backend/tests/api/test_assignment_interactions_api.py` | Accusé, clarification, indisponibilité et historique avant/après suspension, réactivation et fin. | Les transitions patron changent immédiatement l’éligibilité ; les historiques existants ne changent pas. |
| Service et route patron — futur `backend/tests/api/test_patron_assignment_api.py` | Bearer absent, collaborateur refusé, patron du tenant autorisé, tenant étranger neutre, scope supprimé, conflit, idempotence et audit. | `401`, `403`, `404`, `409`, `422` et audit append-only respectent SEC-01. |
| Non-fuite — tests DTO/OpenAPI | Inspection des réponses patron/collaborateur et du snapshot OpenAPI. | Aucun prix, marge, devis, trésorerie, texte libre sensible, identifiant d’audit ou scope interne dans les projections collaborateur. |

## Gates de démarrage et de publication

Le code du slice ne peut démarrer que lorsque le contrat normatif tranche les points de la première table, notamment la valeur de la nouvelle capability, la liste fermée des scopes et les codes de refus. Avant publication, il faudra exécuter `git diff --check`, Ruff, tous les tests backend, le cycle Alembic complet, `detect-secrets`, l’export OpenAPI puis la CI GitHub. La migration ne devra jamais réécrire les historiques collaborateur existants.

## Matrice de tests unitaires et intégration

| Domaine de test | Cas minimum |
|---|---|
| Validation | Scope vide, capability financière, classification interdite, période inversée, motif de fin inconnu, révision négative. |
| Création | Patron du tenant crée une affectation Case active ; collaborateur et tenant étranger refusés. |
| Scope | Ajout/retrait d’action valide ; double application ou révision obsolète refusée ; le scope précédent reste prouvable. |
| Lifecycle | `ACTIVE → SUSPENDED → ACTIVE`, `ACTIVE → ENDED`, et interdiction de réactiver une affectation terminée. |
| ReBAC | Une suspension ou fin bloque immédiatement lecture/commandes collaborateur ; un scope modifié contrôle la capability suivante. |
| Immutabilité | Accusés, clarifications, indisponibilités et journal patron ne sont ni modifiés ni supprimés. |
| Durabilité | Command receipts, événements et outbox sont atomiques ; replay identique sans doublon ; réemploi divergent de clé rejeté. |
| HTTP futur | Bearer réel, policy auditée, erreurs neutres inter-tenant, projection fermée et non-fuite financière. |

## Ordre d’implémentation recommandé

1. Figer le catalogue de scopes collaborateur et la capability patron dédiée.
2. Écrire le contrat de domaine et la migration append-only de changements.
3. Implémenter les commandes et handlers avec révision optimiste.
4. Exécuter les tests de domaine, PostgreSQL et SEC-01 avant toute route HTTP.
5. Ouvrir seulement ensuite le cockpit patron et ses routes auditables.
