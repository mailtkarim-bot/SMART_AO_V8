# SMART_AO V8 — Registre OpenAPI Assignment

**Statut :** référence générée et vérifiée.

**Périmètre :** les trois commandes collaborateur `COLLAB-ASSIGNMENT-HTTP-01`, la lecture fermée `CASE-ASSIGNMENT-HISTORY-01` et les deux commandes patron implémentées de `PATRON-ASSIGNMENT-MANAGEMENT-01`.
**Source de vérité exécutable :** `scripts/export_assignment_openapi.py`, qui produit le snapshot [`SMART_AO_V8_ASSIGNMENT_OPENAPI.json`](SMART_AO_V8_ASSIGNMENT_OPENAPI.json) depuis `create_app()` et ses dépendances SEC-01 réelles.

Ce registre décrit les routes HTTP sous les préfixes `/api/v1/assignments` et `/api/v1/patron`. Elles résolvent toujours l’acteur depuis le bearer serveur : aucun tenant, membership d’auteur, scope d’autorité, acteur ou contexte de test n’est accepté depuis le corps client.

| Méthode | Route | Capability et scope ReBAC | Réponse métier |
|---|---|---|---|
| `POST` | `/{assignment_id}/acknowledgement` | `assignment.acknowledge` | Accusé de réception append-only de l’affectation. |
| `POST` | `/{assignment_id}/clarification-requests` | `assignment.clarify` | Demande de clarification append-only transmise au patron. |
| `POST` | `/{assignment_id}/unavailability-reports` | `assignment.unavailability` | Signalement append-only d’indisponibilité. |
| `GET` | `/{assignment_id}/history?limit=1..200` | `assignment.history.read` | Vue fermée, chronologique et bornée des trois historiques. |
| `POST` | `/api/v1/patron/cases/{case_id}/assignments` | `assignment.manage`, `PATRON_ADMIN` | Création transactionnelle d’une affectation opérationnelle. |
| `POST` | `/api/v1/patron/assignments/{assignment_id}/scope-amendments` | `assignment.manage`, `PATRON_ADMIN` | Amendement révisionné du scope opérationnel fermé. |

## Conventions transverses

L’en-tête `Authorization: Bearer <access-token>` est obligatoire dans l’exécution. Le schéma OpenAPI conserve un paramètre optionnel uniquement parce que la dépendance HTTP effectue elle-même la distinction entre son absence et un bearer valide. En pratique, un bearer absent, invalide ou expiré donne `401`.

Les commandes demandent un `command_id`, une `idempotency_key` et une révision attendue. Elles renvoient `201` à la première application et `200` pour le rejeu strictement identique. Une réutilisation conflictuelle de clé ou une commande en cours retourne `409`.

| Code | Signification publique | Exposition de détails |
|---|---|---|
| `401` | Bearer absent, invalide ou expiré. | Aucun détail d’identité ou de session. |
| `403` | Capability ou scope ReBAC insuffisant sur une affectation connue dans le tenant. | `FORBIDDEN` uniquement. |
| `404` | Affectation absente ou hors tenant. | `NOT_FOUND_OR_FORBIDDEN` : aucune existence inter-tenant n’est révélée. |
| `409` | Rejeu d’idempotence incompatible ou commande encore en cours. | `IDEMPOTENCY_KEY_REUSED` ou `COMMAND_IN_PROGRESS`. |
| `422` | Entrée invalide ou commande rejetée par un invariant métier. | Erreur de validation ou `COMMAND_REJECTED`, sans donnée de l’affectation. |

## Commandes collaborateur

Les trois commandes ont une réponse commune `AssignmentCommandResponse`, strictement fermée : elle contient le statut, les identifiants de commande et d’idempotence, le code résultat, les références d’agrégats, les identifiants d’événements et l’indicateur `replayed`. Elle n’expose ni informations financières, ni notes privées, ni détail de scope.

| Opération | Corps JSON principal | Codes résultat possibles |
|---|---|---|
| Accusé de réception | `command_id`, `idempotency_key`, `expected_revision`, `correlation_id?`, `note?` | `ASSIGNMENT_ACKNOWLEDGED` |
| Demande de clarification | `command_id`, `idempotency_key`, `expected_revision`, `clarification_kind`, `subject`, `question`, `requested_scope?`, `priority` | `ASSIGNMENT_CLARIFICATION_REQUESTED` |
| Signalement d’indisponibilité | `command_id`, `idempotency_key`, `expected_revision`, `reason_kind`, `reason`, `unavailable_from`, `unavailable_until?`, `known_deadline_impact`, `impact_note?` | `ASSIGNMENT_UNAVAILABILITY_REPORTED` |

> Les notes, questions, raisons, demandes de périmètre et textes d’impact sont des entrées nécessaires aux commandes ; ils ne sont jamais repris dans la vue publique d’historique.

## Commandes patron disponibles

Les deux routes patron utilisent `PATRON_ADMIN` et la capability serveur `assignment.manage`. Elles ne reçoivent jamais `tenant_id`, auteur, rôle, capability, état, prix, marge, donnée de trésorerie, décision, scope libre ni date d’écriture. Le tenant, le patron et la date effective sont résolus par SEC-01 et par l’horloge serveur.

| Opération | Corps JSON principal | Codes résultat possibles | Mutation durable |
|---|---|---|---|
| Création d’affectation | `command_id`, `idempotency_key`, `assignment_id`, `target_membership_id`, `expected_case_revision`, scope fermé, fenêtre | `CASE_ASSIGNMENT_CREATED` | Racine `ACTIVE` révision `0`, journal patron, événement, outbox, receipt. |
| Amendement de scope | `command_id`, `idempotency_key`, `expected_revision`, scope fermé | `CASE_ASSIGNMENT_SCOPE_AMENDED` | Scope remplacé, révision +1, journal patron, événement, outbox, receipt. |

Les listes de scope n’acceptent que les actions collaborateur opérationnelles et `INTERNAL_OPERATIONAL`. Une action financière, une action de décision/dépôt, une valeur inconnue, une classification interdite, un doublon ou un champ supplémentaire échoue avant la transaction. L’amendement sur une affectation absente ou hors tenant est neutre ; une révision obsolète retourne `409 VERSION_CONFLICT`; un scope identique, une affectation fermée ou un invariant métier retourne `422`.

## Lecture fermée d’historique

`GET /api/v1/assignments/{assignment_id}/history` retourne `AssignmentHistoryResponse` avec l’identifiant de l’affectation, l’identifiant de l’affaire, son cycle de vie et une liste `items`. La borne `limit` est optionnelle, vaut `100` par défaut et est comprise entre `1` et `200`.

Chaque source est d’abord bornée à la valeur demandée, ordonnée par `recorded_at DESC`, puis `record_id ASC`. Les trois sources sont ensuite fusionnées, réordonnées avec la même clé déterministe et coupées à nouveau à la limite globale. Ainsi, le client obtient au plus `limit` éléments sans lecture non bornée de table.

| Champ d’un item d’historique | Usage | Confidentialité |
|---|---|---|
| `record_id`, `recorded_at`, `kind`, `operational_state` | Identification et chronologie opérationnelle. | Public pour le collaborateur affecté. |
| `assignment_revision` | Révision utile au suivi de l’affectation. | Public pour le collaborateur affecté. |
| `clarification_kind`, `priority` | Catégorie et priorité d’une clarification. | Public pour le collaborateur affecté. |
| `reason_kind`, `unavailable_from`, `unavailable_until`, `known_deadline_impact` | Signal opérationnel d’indisponibilité sans justification libre. | Public pour le collaborateur affecté. |
| `note`, `question`, `reason`, `impact_note`, `requested_scope` | Texte libre potentiellement sensible. | Délibérément absent. |
| `tenant_id`, `membership_id`, `actor_id`, `command_id`, `correlation_id`, `functional_key` | Métadonnées de sécurité, audit ou déduplication. | Délibérément absentes. |

## Reproduction et contrôle de dérive

Le snapshot doit être régénéré dès qu’une route, un DTO ou un code public Assignment change :

```bash
uv run python scripts/export_assignment_openapi.py
```

La validation du slice comprend le contrôle Ruff du script, la régénération du JSON et le harnais API `test_assignment_interactions_api.py`. Celui-ci couvre notamment la liste vide, les trois types d’historique, la borne globale, le refus ReBAC audité, la neutralité inter-tenant, l’absence de bearer et l’absence de champs sensibles dans la projection.
