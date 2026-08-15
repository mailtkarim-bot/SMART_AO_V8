# SMART_AO V8 — Registre OpenAPI Assignment

**Statut :** référence générée et vérifiée.

**Périmètre :** seize opérations : les trois commandes collaborateur `COLLAB-ASSIGNMENT-HTTP-01`, la lecture fermée `CASE-ASSIGNMENT-HISTORY-01`, les cinq commandes patron de `PATRON-ASSIGNMENT-MANAGEMENT-01`, les deux lectures `PATRON-ASSIGNMENT-READ-01`, la lecture `PATRON-ASSIGNMENT-INTERACTIONS-READ-01`, la validation `PATRON-ASSIGNMENT-INTERACTION-VALIDATION-01`, la lecture financière patron, la publication financière `FINANCIAL-REPORT-PUBLICATION-01` et la création de brouillon `FINANCIAL-REPORT-DRAFT-CREATION-01`.
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
| `POST` | `/api/v1/patron/assignments/{assignment_id}/suspensions` | `assignment.manage`, `PATRON_ADMIN` | Suspension révisionnée et temporaire d’une affectation active. |
| `POST` | `/api/v1/patron/assignments/{assignment_id}/reactivations` | `assignment.manage`, `PATRON_ADMIN` | Réactivation révisionnée d’une affectation suspendue dans sa fenêtre valide. |
| `POST` | `/api/v1/patron/assignments/{assignment_id}/end` | `assignment.manage`, `PATRON_ADMIN` | Fin révisionnée et irréversible d’une affectation ouverte. |
| `POST` | `/api/v1/patron/assignments/{assignment_id}/interaction-validations` | `assignment.manage`, `PATRON_ADMIN` | Prise en compte patron append-only d’une interaction collaborateur. |
| `GET` | `/api/v1/patron/cases/{case_id}/financial-reports/{report_id}` | `financial.report.read`, `PATRON_ADMIN` | Lecture `no-store` d’un snapshot financier publié et tenant-scopé. |
| `POST` | `/api/v1/patron/cases/{case_id}/financial-reports/drafts` | `financial.report.create`, `PATRON_ADMIN` | Création atomique d’un unique brouillon financier vide, tenant-scopé et confidentiel. |
| `POST` | `/api/v1/patron/cases/{case_id}/financial-reports/{report_id}/publications` | `financial.report.publish`, `PATRON_ADMIN` | Publication atomique `DRAFT → PUBLISHED`, acte immutable, receipt sans montant. |
| `GET` | `/api/v1/patron/assignments?case_id?&state?&limit=1..200` | `assignment.manage`, `PATRON_ADMIN` | Liste tenant-scopée, fermée et bornée des affectations d’autorité. |
| `GET` | `/api/v1/patron/assignments/{assignment_id}/journal?limit=1..200` | `assignment.manage`, `PATRON_ADMIN` | Journal patron append-only fermé, tenant-scopé et borné. |
| `GET` | `/api/v1/patron/assignments/{assignment_id}/interactions?kind?&limit=1..200` | `assignment.manage`, `PATRON_ADMIN` | Interactions collaborateur fermées, tenant-scopées et bornées. |

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

Les cinq routes patron utilisent `PATRON_ADMIN` et la capability serveur `assignment.manage`. Elles ne reçoivent jamais `tenant_id`, auteur, rôle, capability, état, prix, marge, donnée de trésorerie, décision, scope libre ni date d’écriture. Le tenant, le patron et la date effective sont résolus par SEC-01 et par l’horloge serveur.

| Opération | Corps JSON principal | Codes résultat possibles | Mutation durable |
|---|---|---|---|
| Création d’affectation | `command_id`, `idempotency_key`, `assignment_id`, `target_membership_id`, `expected_case_revision`, scope fermé, fenêtre | `CASE_ASSIGNMENT_CREATED` | Racine `ACTIVE` révision `0`, journal patron, événement, outbox, receipt. |
| Amendement de scope | `command_id`, `idempotency_key`, `expected_revision`, scope fermé | `CASE_ASSIGNMENT_SCOPE_AMENDED` | Scope remplacé, révision +1, journal patron, événement, outbox, receipt. |
| Suspension | `command_id`, `idempotency_key`, `expected_revision`, `suspension_reason_code` fermé | `CASE_ASSIGNMENT_SUSPENDED` | État `SUSPENDED`, révision +1, journal patron, événement, outbox, receipt. |
| Réactivation | `command_id`, `idempotency_key`, `expected_revision`, `reactivation_reason_code` fermé | `CASE_ASSIGNMENT_REACTIVATED` | État `ACTIVE`, révision +1, journal patron, événement, outbox, receipt. |
| Fin | `command_id`, `idempotency_key`, `expected_revision`, `end_reason_code` fermé | `CASE_ASSIGNMENT_ENDED` | État `ENDED`, `ended_at` serveur, révision +1, journal patron, événement, outbox, receipt. |
| Validation d’interaction | `command_id`, `idempotency_key`, `interaction_id`, `interaction_kind`, `validation_code` fermé | `INTERACTION_VALIDATED` | Registre patron append-only, événement, outbox, receipt ; aucune mutation de la source ou de l’affectation. |

Les listes de scope n’acceptent que les actions collaborateur opérationnelles et `INTERNAL_OPERATIONAL`. Une action financière, une action de décision/dépôt, une valeur inconnue, une classification interdite, un doublon ou un champ supplémentaire échoue avant la transaction. L’amendement sur une affectation absente ou hors tenant est neutre ; une révision obsolète retourne `409 VERSION_CONFLICT`; un scope identique, une affectation fermée ou un invariant métier retourne `422`.

La suspension n’accepte que `PATRON_SUSPENDED`, `WORKLOAD_REALLOCATION`, `CASE_PAUSED` ou `ACCESS_REVIEW`. Elle est admise exclusivement depuis `ACTIVE`; un état déjà suspendu, terminé ou expiré retourne `422` sans deuxième journal. Le motif fermé est présent dans le journal patron et l’événement domaine, mais il n’est pas renvoyé dans le receipt HTTP.

La réactivation n’accepte que `PATRON_REACTIVATED`, `CASE_RESUMED` ou `ACCESS_REVIEW_CLEARED`. Elle est admise exclusivement depuis `SUSPENDED`, pendant une fenêtre ouverte et si la Case ainsi que la cible collaborateur sont encore actives dans le tenant. Un état actif, terminé ou expiré, une fenêtre future/fermée ou une cible inactive retourne `422` sans modifier le journal. Le motif fermé reste absent du receipt HTTP.

La fin n’accepte que `PATRON_ENDED`, `CASE_STOPPED`, `CASE_ARCHIVED`, `COLLABORATOR_UNAVAILABLE` ou `MEMBERSHIP_REVOKED`. Elle est admise depuis `ACTIVE` ou `SUSPENDED`, y compris lorsque la Case est arrêtée, la cible inactive ou la fenêtre passée, afin de retirer une autorisation résiduelle. Les états `ENDED` et `EXPIRED` retournent `422` sans second journal. Le motif fermé est conservé dans le journal et l’événement domaine, mais reste absent du receipt HTTP.

La validation d’interaction n’accepte que les paires `ACKNOWLEDGEMENT/ACKNOWLEDGEMENT_NOTED`, `CLARIFICATION_REQUEST/CLARIFICATION_NOTED` et `UNAVAILABILITY_REPORT/UNAVAILABILITY_NOTED`. Elle est admise sur une interaction durable de la même affectation même si cette dernière est terminée, hors fenêtre ou si sa cible est inactive. Elle ne répond pas à la clarification, ne résout pas l’indisponibilité et ne modifie jamais la source. Le receipt masque l’interaction, le type et le code de validation ; une seconde validation de la même source retourne `422`.

La lecture financière ne retourne qu’un snapshot `PUBLISHED` et ferme tenant, auteur, source, audit, stockage, hash et formule. Les rubriques autorisées sont chiffre d’affaires, coûts directs, frais généraux, sous-traitance, provision d’aléas, marge brute et trésorerie prévisionnelle ; chaque montant est un entier `*_minor` et la réponse porte `Cache-Control: no-store`.

La publication financière exige `financial.report.publish`, détenue uniquement par le `PATRON_ADMIN`. Le contrôle patron intervient avant toute résolution du snapshot : un collaborateur reçoit donc `403 FORBIDDEN` sans lecture ni fuite financière. Sous verrou `FOR UPDATE`, seul un snapshot `DRAFT` à la révision attendue peut devenir `PUBLISHED`; l’acte `financial_report_publications`, l’événement et le receipt idempotent sont écrits dans la même transaction. Le receipt expose uniquement les références d’agrégat, les identifiants de commande et d’événements ainsi que `FINANCIAL_REPORT_PUBLISHED`; il exclut tout montant, libellé, source, hash et règle de calcul.

La création de brouillon financier exige `financial.report.create`, détenue uniquement par le `PATRON_ADMIN`. Le contrôle patron intervient avant toute résolution de la Case : un collaborateur reçoit donc `403 FORBIDDEN` sans lecture ni fuite financière. Sous verrou `FOR UPDATE` sur la Case, la frontière crée un snapshot `DRAFT` vide, révision `0`, totaux nuls et publication absente ; l’index unique partiel interdit un second brouillon ouvert pour la même affaire. L’événement, l’outbox et le receipt idempotent sont écrits dans la même transaction. Le receipt `FINANCIAL_REPORT_DRAFT_CREATED` exclut tout montant, total, ligne, libellé, source, hash, formule ou note.

## Lectures du cockpit patron

Les trois lectures sont réservées au `PATRON_ADMIN` disposant de `assignment.manage`, avec bearer résolu côté serveur. Elles ne renvoient ni prix, ni marge, ni devis, ni identité cible, ni membership, ni auteur, ni audit, ni commande, ni corrélation, ni texte libre de collaborateur.

| Opération | Paramètres | Réponse `200` | Erreurs publiques |
|---|---|---|---|
| `GET /api/v1/patron/assignments` | `case_id?`, `state? = ACTIVE|SUSPENDED|ENDED|EXPIRED`, `limit = 1..200` (100 par défaut). | `PatronAssignmentCockpitListResponse` : lignes avec affaire, état, révision, fenêtre, fin et scope opérationnel fermé. Tri : `case_title ASC`, `assignment_id ASC`. | `401`, `403`, `422`. Une liste sans résultat retourne `items: []`. |
| `GET /api/v1/patron/assignments/{assignment_id}/journal` | `limit = 1..200` (100 par défaut). | `PatronAssignmentJournalResponse` : en-tête fermé d’affectation et changements `ASSIGNMENT_CREATED`, `ASSIGNMENT_SCOPE_AMENDED`, `ASSIGNMENT_SUSPENDED`, `ASSIGNMENT_REACTIVATED`, `ASSIGNMENT_ENDED`, triés par date décroissante puis ID. | `401`, `403`, `404 NOT_FOUND_OR_FORBIDDEN`, `422`. |
| `GET /api/v1/patron/assignments/{assignment_id}/interactions` | `kind? = ACKNOWLEDGEMENT|CLARIFICATION_REQUEST|UNAVAILABILITY_REPORT`, `limit = 1..200` (100 par défaut). | `PatronAssignmentInteractionsResponse` : accusés, catégories/priorités de clarification et périodes/motifs fermés d’indisponibilité, triés par date décroissante puis ID. | `401`, `403`, `404 NOT_FOUND_OR_FORBIDDEN`, `422`. |

Le journal expose les états, révisions, motifs fermés et manifests de scope précédents/résultants nécessaires à la direction. Il exclut l’auteur, la cible, les IDs de commande/corrélation, les clés d’idempotence, les données d’audit et tout texte libre. Ces lectures n’écrivent aucun receipt, événement ou outbox.

La lecture des interactions ne reprend jamais la note d’accusé, le sujet, la question, le périmètre demandé, la raison ou la note d’impact. Elle ne donne ni identité, ni membership, ni auteur, ni métadonnée de commande. Le patron lit exclusivement les signaux structurés nécessaires au suivi opérationnel ; un collaborateur standard est refusé avec `403 FORBIDDEN` et ce refus est audité.

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

La validation du slice comprend le contrôle Ruff du script, la régénération du JSON et le harnais API `test_assignment_interactions_api.py`. Celui-ci couvre notamment la liste vide, les trois types d’historique, la borne globale, le refus ReBAC audité, la neutralité inter-tenant, l’absence de bearer, l’absence de champs sensibles dans la projection, ainsi que les receipts, rejeux, motifs fermés, fenêtres de réactivation, fin irréversible, lecture des interactions patron et refus d’un collaborateur standard.
