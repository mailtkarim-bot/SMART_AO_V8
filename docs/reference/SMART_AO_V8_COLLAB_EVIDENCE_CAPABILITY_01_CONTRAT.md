# SMART AO V8 — COLLAB-EVIDENCE-CAPABILITY-01

## Objet

Ce slice permet à un collaborateur affecté à une affaire de proposer l’usage d’une capacité entreprise versionnée et de signaler un écart de capacité ou de preuve. Il ne modifie jamais le catalogue patronal et ne transforme pas une proposition en conformité automatique.

## Commandes

| Commande | Effet | État |
|---|---|---|
| `ProposeCapabilityForCase` | Ajoute une proposition Case × capacité × version, liée à une exigence et/ou une tâche visible. | `PROPOSED`, avec validité calculée côté serveur : `CURRENT`, `EXPIRED` ou `UNKNOWN`. |
| `ReportCapabilityGap` | Ajoute un constat d’écart `MISSING`, `EXPIRED`, `UNAUTHORIZED` ou `INSUFFICIENT`, avec sévérité et action recommandée. | Append-only, sans résolution automatique. |

Les identifiants de tenant, acteur, membership et portée Case sont résolus ou vérifiés côté serveur. Le client ne peut pas fournir `tenant_id`, `proposed_by_membership_id`, `reported_by_membership_id`, `state` ou `validity_state`.

## ReBAC et scope d’affectation

Le collaborateur doit avoir un membership actif, une affectation active sur la Case, une fenêtre temporelle valide et l’action correspondante dans `scope_actions_json` : `preparation.capability.propose` pour une proposition et `preparation.capability.gap.report` pour un écart. La policy vérifie également l’appartenance Case, la classification `INTERNAL_OPERATIONAL` et les capabilities du rôle.

Une Case, une exigence et une tâche doivent appartenir au tenant. Une tâche doit appartenir à la Case et à la même affectation. Une capacité et sa version doivent appartenir au tenant ; la version doit référencer la capacité indiquée. Les ressources étrangères et les affectations absentes restent neutres côté HTTP.

## Validité et append-only

La validité d’une proposition est calculée à partir de l’état serveur de la capacité et des dates de sa version au moment de la commande. Une version expirée peut être proposée pour permettre de documenter le problème, mais elle est marquée `EXPIRED` et ne débloque aucune readiness. Les propositions et gaps sont immuables en base : aucune mise à jour ni suppression n’est autorisée par les triggers PostgreSQL.

Les functional keys empêchent les doublons métier d’une même proposition ou d’un même gap. Le dispatcher commun assure le rejeu idempotent par `command_id` et `idempotency_key`, ainsi que les receipts, événements et outbox transactionnels.

## Confidentialité

Les contrats collaborateur n’acceptent ni prix, coût, marge, trésorerie, finance, chiffrage, soumission ou termes équivalents. Les textes justification, raison, source et action recommandée sont filtrés. Les événements et projections ne contiennent jamais le contenu complet d’une preuve, son hash, son storage key, son filename ou les métadonnées privées de la bibliothèque entreprise.

## API

- `POST /api/v1/collaborator/cases/{case_id}/capability-proposals`
- `POST /api/v1/collaborator/cases/{case_id}/capability-gaps`
- `GET /api/v1/collaborator/cases/{case_id}/capability-assessments?assignment_id={assignment_id}`

Les DTO publics sont fermés avec `extra=forbid`. La lecture ne retourne que les identifiants métier nécessaires, les états, les textes collaborateur bornés et les références de source explicitement saisies.

## Critères de fermeture

Le slice est fermé avec des tests démontrant le succès, le rejeu idempotent, le refus sans scope, l’isolation inter-tenant, la neutralité des ressources étrangères, le contrôle de capacité/version, le filtrage financier, la provenance Case/requirement/task, l’append-only PostgreSQL, les événements/outbox et le parcours API JWT.
