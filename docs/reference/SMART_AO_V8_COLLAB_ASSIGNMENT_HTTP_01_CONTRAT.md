# SMART_AO V8 — COLLAB-ASSIGNMENT-HTTP-01

## Objet

Cette frontière expose par HTTP les trois commandes humaines déjà définies par
`COLLAB-ASSIGNMENT-01`. Elle ne crée, ne modifie et ne termine jamais une
affectation. Elle enregistre uniquement l’interaction d’un collaborateur avec
une affectation active déjà résolue côté serveur.

## Routes

| Méthode | Route | Commande |
|---|---|---|
| `POST` | `/api/v1/assignments/{assignment_id}/acknowledgement` | `AcknowledgeAssignment` |
| `POST` | `/api/v1/assignments/{assignment_id}/clarification-requests` | `RequestAssignmentClarification` |
| `POST` | `/api/v1/assignments/{assignment_id}/unavailability-reports` | `ReportAssignmentUnavailability` |

Le `assignment_id` de l’URL est la seule source d’identité de l’affectation.
Le corps HTTP ne peut pas fournir `tenant_id`, `membership_id`, `actor_id`,
`case_id`, le scope, la classification ou un rôle.

## Sécurité

Chaque route résout un bearer réel avec le résolveur SEC-01, puis délègue à la
façade applicative `AssignmentInteractionService`. La façade vérifie un acteur
`COLLABORATEUR`, une membership active, l’appartenance de l’affectation à la
membership et au tenant, l’état actif de l’affectation, la Case active liée,
la capability dédiée et le scope ReBAC Case-scopé. La classification requise
est `INTERNAL_OPERATIONAL`; aucune donnée financière n’est lisible ou
modifiable par cette frontière.

Les refus d’une ressource étrangère ou inexistante restent neutres avec
`404 NOT_FOUND_OR_FORBIDDEN`. Les refus d’autorisation explicites retournent
`403 FORBIDDEN`. Les erreurs d’invariant de commande retournent
`422 COMMAND_REJECTED`; une réutilisation d’idempotency key avec un contenu
différent retourne `409 IDEMPOTENCY_KEY_REUSED`.

## Réponse

Une réussite retourne une projection fermée contenant uniquement le reçu de
commande : identifiants de commande et d’idempotence, code de résultat, références
d’agrégat, identifiants d’événements et indicateur `replayed`. Une première
exécution retourne `201`; un replay identique retourne `200`.

## Non-objectifs

Cette façade ne permet pas de créer une affectation, de changer son scope, de
modifier ses classifications, de consulter les prix ou marges, de produire une
décision Go/No-Go, de valider une conformité ou de déposer une offre.
