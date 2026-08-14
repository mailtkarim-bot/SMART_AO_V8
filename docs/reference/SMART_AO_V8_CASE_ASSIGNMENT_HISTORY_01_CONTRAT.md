# SMART_AO V8 — CASE-ASSIGNMENT-HISTORY-01

## Objet

Cette frontière permet à un **collaborateur** de relire l’historique fermé de
ses propres interactions sur une affectation active, au sein d’une affaire qui
lui est effectivement affectée. Elle n’est pas une lecture de l’historique
global de l’entreprise, de la Case ou du collaborateur ; elle ne remplace pas le
futur cockpit patron de gestion des affectations.

## Route

`GET /api/v1/assignments/{assignment_id}/history?limit={1..200}`

Le `assignment_id` est le seul identifiant fourni par le client. Le tenant, la
membership, l’acteur, la Case et le scope sont résolus par le serveur depuis le
bearer SEC-01 et les registres persistants.

## Préconditions ReBAC

| Contrôle | Règle |
|---|---|
| Acteur | `COLLABORATEUR` uniquement ; aucun acteur `SYSTEM`, patron ou délégué ne consomme cette vue. |
| Membership | Active et identique à `CaseAssignmentRecord.membership_id`. |
| Tenant | L’affectation est cherchée avec `(tenant_id, assignment_id, membership_id)`. |
| État | Affectation `ACTIVE`, dans sa fenêtre temporelle, liée à une Case `ACTIVE`. |
| Capability | `assignment.history.read`, présente uniquement dans le catalogue collaborateur. |
| Scope Case | L’action `assignment.history.read` et la classification `INTERNAL_OPERATIONAL` doivent être présentes dans `AssignmentScope`. |

Une affectation hors tenant, inexistante ou liée à une autre membership reste
indiscernable et répond `404 NOT_FOUND_OR_FORBIDDEN`. Une affectation visible
mais sans capability/scope répond `403 FORBIDDEN`. Le contexte bearer absent ou
invalide répond `401`.

La valeur `limit` est bornée entre 1 et 200, vaut 100 par défaut et est appliquée
après le tri global déterministe. La réponse ne contient aucun curseur : la
pagination stable est un slice distinct, car elle nécessite un contrat de
curseur signé et Case-scopé.

## Projection fermée

La réponse contient les métadonnées non financières suivantes :

| Champ | Signification |
|---|---|
| `assignment_id` | Identifiant de l’affectation déjà autorisée. |
| `case_id` | Identifiant de l’affaire déjà présente dans le scope du collaborateur. |
| `case_lifecycle` | État d’affaire, sans titre, prix ni décision. |
| `items` | Historique trié par `recorded_at DESC`, puis `record_id ASC`. |
| `items[].kind` | `ACKNOWLEDGEMENT`, `CLARIFICATION_REQUEST` ou `UNAVAILABILITY_REPORT`. |
| `items[].recorded_at` | Horodatage durable de l’interaction. |
| `items[].assignment_revision` | Révision concernée ; absente pour une clarification qui ne modifie pas l’affectation. |
| `items[].operational_state` | `RECORDED` ou `OPEN`. |
| `items[].clarification_kind`, `priority` | Seulement pour une clarification. |
| `items[].reason_kind`, `unavailable_from`, `unavailable_until`, `known_deadline_impact` | Seulement pour une indisponibilité. |

La projection exclut strictement le texte de note, question, demande de scope,
motif détaillé, note d’impact, acteur, membership, tenant, command id,
correlation id, functional key, audit, scope, données de stockage, prix, marge,
chiffrage, décision et dépôt.

## Audit et invariants

La route s’appuie sur `AuditedAuthorizationPolicy` pour les refus de policy. Les
refus avant policy — acteur non collaborateur, absence de membership,
affectation non résoluble — sont ajoutés au journal append-only avec des
métadonnées minimisées. La lecture n’écrit aucun historique métier, n’altère
aucune révision et ne transforme jamais une indisponibilité en tâche ou en
décision.

## Tests de fermeture

Le slice est clos uniquement si les tests couvrent le bearer absent, la lecture
de l’affectation propre, la liste vide, le tri déterministe, le refus de scope,
la neutralité inter-tenant, l’audit des refus et l’absence de tous les champs
interdits dans le JSON.
