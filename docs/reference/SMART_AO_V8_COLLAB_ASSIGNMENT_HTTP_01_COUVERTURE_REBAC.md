# SMART_AO V8 — Couverture et exigences ReBAC

## Périmètre vérifié

Ce document couvre la façade `COLLAB-ASSIGNMENT-HTTP-01`. Elle expose trois
interactions d’un collaborateur sur une affectation existante : accusé de
réception, demande de clarification et signalement d’indisponibilité. Elle ne
crée jamais une affectation, ne modifie jamais son scope ni son état, et ne
rend accessible aucune donnée financière.

| Route | Commande | Résultat attendu |
|---|---|---|
| `POST /api/v1/assignments/{assignment_id}/acknowledgement` | `AcknowledgeAssignment` | `ASSIGNMENT_ACKNOWLEDGED` |
| `POST /api/v1/assignments/{assignment_id}/clarification-requests` | `RequestAssignmentClarification` | `ASSIGNMENT_CLARIFICATION_REQUESTED` |
| `POST /api/v1/assignments/{assignment_id}/unavailability-reports` | `ReportAssignmentUnavailability` | `ASSIGNMENT_UNAVAILABILITY_REPORTED` |

Toutes les routes acceptent exclusivement un bearer résolu côté serveur. Le
corps ne contient pas `tenant_id`, `membership_id`, `actor_id`, `case_id`, rôle,
classification ou scope ; ces faits sont détenus par le serveur.

## Exigences ReBAC appliquées

| Contrôle | Source de vérité | Effet en cas d’échec |
|---|---|---|
| Authentification | Résolveur bearer SEC-01 | `401` avant toute commande |
| Nature de l’acteur | `ActorContext.actor_kind` | Collaborateur obligatoire ; autre acteur refusé et audité |
| Membership | Contexte authentifié et `CaseAssignmentRecord.membership_id` | L’affectation doit appartenir à la membership courante |
| Tenant | Requête tenant-scoped sur `CaseAssignmentRecord` | Ressource absente ou étrangère : `404 NOT_FOUND_OR_FORBIDDEN` |
| État d’affectation | `state`, `starts_at`, `ends_at` | Affectation inactive : commande rejetée |
| Affaire | `CaseRecord` de même tenant et `lifecycle=ACTIVE` | Case absente/archivée : commande rejetée sans fuite |
| Capability | Catalogue fermé `Capability` | `assignment.acknowledge`, `assignment.clarify` ou `assignment.unavailability` obligatoire |
| Scope relationnel | `AssignmentScope.allowed_actions` | L’action doit être explicitement accordée sur la Case |
| Classification | `AssignmentScope.allowed_classifications` | `INTERNAL_OPERATIONAL` obligatoire ; jamais de classification financière |
| Révision | `CaseAssignmentRecord.aggregate_revision` | Désaccord : `422 COMMAND_REJECTED`, sans écriture durable |
| Idempotence | Receipt transactionnel et hash canonique | Replay identique : `200`; clé réutilisée avec contenu différent : `409` |

> Une autorisation d’interaction Assignment ne constitue ni une délégation de
> chiffrage, ni une validation de conformité, ni une décision Go/No-Go, ni une
> autorisation de dépôt.

## Audit et réponses publiques

Les décisions de policy négatives ou de step-up sont append-only via
`AuditedAuthorizationPolicy`. Les refus avant policy — acteur non collaborateur,
absence de membership ou affectation non résoluble dans le tenant — sont eux
aussi audités par la façade applicative avec une action fermée et des métadonnées
minimisées. Les réponses HTTP ne retournent que les détails publics suivants :

| Situation | Réponse publique |
|---|---|
| Ressource étrangère ou inexistante | `404 NOT_FOUND_OR_FORBIDDEN` |
| Capability ou scope absent | `403 FORBIDDEN` |
| Idempotency key réemployée avec une autre requête | `409 IDEMPOTENCY_KEY_REUSED` |
| Rejet d’invariant métier ou révision obsolète | `422 COMMAND_REJECTED` |
| Première exécution durable | `201` avec reçu fermé |
| Replay identique | `200` avec le même reçu fermé et `replayed=true` |

Le reçu fermé exclut toute preuve textuelle de clarification, tout motif détaillé
d’indisponibilité, tout scope, toute donnée de tenant, tout audit, tout prix,
toute marge et toute information de stockage.

## Matrice de couverture ciblée

| Niveau | Fichier | Scénarios couverts |
|---|---|---|
| Validation de commande | `backend/tests/application/test_collab_assignment.py` | Période d’indisponibilité invalide ; note d’impact obligatoire ; révision Assignment |
| Application/PostgreSQL | `backend/tests/application/test_collab_assignment.py` | Accusé, indisponibilité, clarification fonctionnellement idempotente, outbox/événement, append-only PostgreSQL, refus scope et tenant |
| HTTP/API | `backend/tests/api/test_assignment_interactions_api.py` | Bearer absent, accusé + replay, clarification, indisponibilité, conflit d’idempotence, refus de scope `403` audité, ressource inter-tenant `404` auditée |
| Régression globale | `backend/tests` | À rejouer avant publication pour inclure la façade HTTP dans le décompte global |

Le harnais API ciblé de la façade comporte **7 cas pytest verts**. La validation
complète exécutée après ces scénarios compte **251 tests verts** et 4
avertissements non bloquants. Ruff, le scan de secrets, `alembic upgrade head`,
`alembic check` et `alembic downgrade base` sont également verts ; ces résultats
forment le niveau local requis avant publication et CI.

## Limites assumées

La frontière actuelle ne permet pas au patron de créer, modifier, suspendre ou
retirer une affectation. Elle ne fournit pas encore de lecture publique des
historiques d’interaction. Ces décisions devront faire l’objet de contrats
distincts, avec projections fermées et règles d’audit dédiées.
