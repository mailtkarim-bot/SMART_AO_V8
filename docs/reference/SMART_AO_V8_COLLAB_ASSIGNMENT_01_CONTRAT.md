# SMART_AO V8 — COLLAB-ASSIGNMENT-01

## 1. Objet du slice

`COLLAB-ASSIGNMENT-01` ouvre la première frontière d’écriture de l’espace collaborateur autour d’une affectation Case déjà créée et résolue par le serveur. Il couvre trois intentions prévues par `DOMAIN-02` et la matrice collaborateur : `AcknowledgeAssignment`, `RequestAssignmentClarification` et `ReportAssignmentUnavailability`.

Le slice ne crée pas d’affectation, ne modifie pas son périmètre, ne change pas les droits ReBAC, ne réaffecte pas une Case et n’expose aucune donnée financière. La création, la suspension, l’extension ou la révocation d’une affectation restent des actes patron/administrateur séparés.

## 2. Principes non négociables

L’affectation est toujours résolue depuis le tenant, la membership et la session authentifiée. Le navigateur ne fournit jamais `tenant_id`, `membership_id`, `actor_id`, rôle, scope, classification ou décision d’autorisation comme donnée de confiance.

Une affectation active est une condition d’accès, pas une preuve d’acceptation du travail. La reconnaissance confirme seulement que le collaborateur a pris connaissance de l’affectation. Une indisponibilité signale une contrainte humaine ; elle ne modifie directement ni une tâche, ni une échéance, ni l’affectation. Une demande de clarification ouvre une demande opérationnelle adressée au patron ou au destinataire autorisé ; elle n’élargit aucun scope.

## 3. Commandes et ownership

| Commande | Agrégat propriétaire | Acteur autorisé | Effet durable |
|---|---|---|---|
| `AcknowledgeAssignment` | `Assignment` | Acteur destinataire de l’affectation active, généralement `COLLABORATEUR` | Ajoute une reconnaissance append-only et émet `AssignmentAcknowledged`. |
| `RequestAssignmentClarification` | `Request` lié à l’affectation | Acteur couvert par l’affectation active avec droit `SUBMIT` opérationnel | Crée une demande idempotente et émet `AssignmentClarificationRequested`. |
| `ReportAssignmentUnavailability` | `Assignment` | Acteur affecté avec droit `COMMENT` ou `SUBMIT` | Ajoute une indisponibilité append-only et émet `AssignmentUnavailabilityReported`. |

Un handler ne modifie jamais directement un autre agrégat. Une conséquence éventuelle sur une Action patron, une tâche ou une relance est produite par un événement et un Process Manager documenté ultérieurement.

## 4. Enveloppe commune

Chaque commande porte `command_id`, `idempotency_key`, `correlation_id`, `assignment_id` et `expected_revision`. Pour la demande de clarification, le payload ajoute une clé fonctionnelle vérifiable par le serveur. La clé d’idempotence du dispatcher reste :

```text
(tenant_id, actor_id, command_type, idempotency_key)
```

L’empreinte couvre le type, le payload, la révision attendue, la corrélation et, le cas échéant, l’événement causal. Une même clé avec un contenu différent produit `IDEMPOTENCY_KEY_REUSED` et aucune mutation.

L’affectation existante ne possède pas encore de révision métier explicite. Ce slice ajoute `aggregate_revision` à `case_assignments`, initialisé à `0`, et incrémente cette révision dans la même transaction pour `AcknowledgeAssignment` et `ReportAssignmentUnavailability`. Les lignes historiques ne sont jamais modifiées ni supprimées.

## 5. Préconditions communes

Avant toute écriture, le serveur verrouille l’affectation dans son tenant et vérifie :

1. la Case et la membership référencées existent dans le même tenant ;
2. l’affectation est `ACTIVE` au moment du traitement ;
3. `starts_at <= received_at` et `ends_at` est absente ou postérieure à `received_at` ;
4. l’acteur courant correspond à la membership affectée ;
5. le scope de l’affectation autorise le verbe et la classe opérationnelle demandés ;
6. `expected_revision` correspond à la révision courante ;
7. la Case n’est pas `ARCHIVED` et son contexte ne rend pas l’affectation obsolète.

Une affectation suspendue, terminée ou expirée est refusée. Le refus inter-tenant reste neutre et ne révèle pas si une affectation existe.

## 6. Payloads fermés

### 6.1 `AcknowledgeAssignment`

Le payload contient uniquement `assignment_id`, `expected_revision`, `acknowledged_at` optionnel contrôlé par le serveur et une note courte optionnelle non financière. Le serveur utilise `received_at` comme date de référence ; une date client ne peut pas être antérieure à l’émission serveur ni être utilisée pour contourner une période d’affectation.

Une seule reconnaissance active est admise par révision d’affectation et par acteur. Un retry restitue le résultat existant. Une seconde reconnaissance volontaire après une nouvelle révision pourra devenir une nouvelle entrée historique, mais ne sera jamais interprétée comme une nouvelle affectation.

### 6.2 `RequestAssignmentClarification`

Le payload contient `assignment_id`, `expected_revision`, `subject`, `question`, `requested_scope` borné, `priority` fermée et, si nécessaire, une référence Case/DCE déjà résolue par le serveur. Le demandeur ne peut pas adresser la demande à une identité arbitraire ni ajouter une membership au scope.

La clé fonctionnelle minimale est `case_id + assignment_id + clarification_kind + active_cycle`. Une demande identique encore ouverte est réutilisée. Le patron pourra y répondre dans un slice `Request` ultérieur ; ce slice ne fabrique pas de réponse ni d’action patron.

### 6.3 `ReportAssignmentUnavailability`

Le payload contient `assignment_id`, `expected_revision`, `reason_kind` fermé, `reason`, `unavailable_from`, `unavailable_until` optionnel et `known_deadline_impact` optionnel. Les motifs sont limités à `SICKNESS`, `LEAVE`, `CAPACITY_CONFLICT`, `SKILL_GAP`, `ACCESS_PROBLEM`, `OTHER`.

La déclaration est une observation historisée. Elle peut être visible au patron et déclencher ultérieurement une action de réaffectation, mais elle ne suspend pas l’affectation, ne modifie pas une tâche et ne change pas une échéance dans ce slice.

## 7. Persistance prévue

Le slice ajoute un historique append-only tenant-scoped, protégé par triggers PostgreSQL :

| Table | Contenu minimal |
|---|---|
| `case_assignment_acknowledgements` | `tenant_id`, `id`, `assignment_id`, acteur, `assignment_revision`, date serveur, note bornée, `command_id`, `correlation_id`. |
| `assignment_clarification_requests` | `tenant_id`, `id`, `assignment_id`, `case_id`, créateur, type, sujet, question, scope demandé borné, statut, clé fonctionnelle, `command_id`, dates. |
| `case_assignment_unavailabilities` | `tenant_id`, `id`, `assignment_id`, acteur, motif, raison, période, impact d’échéance observé, `assignment_revision`, `command_id`, dates. |

Les tables utilisent des FKs composites `(tenant_id, id)` vers `case_assignments`, `cases` et les memberships nécessaires. Aucune relation n’utilise `ON DELETE CASCADE`. Les événements ne contiennent ni mot de passe, ni token, ni prix, ni marge, ni contenu de DCE.

## 8. Autorisation et audit

Les commandes passent par le contexte bearer serveur et `AuditedAuthorizationPolicy`. Les checks sont séparés : membership active, affectation active, Case scope, action autorisée, classification `INTERNAL_OPERATIONAL` et état de la Case. Les refus sont auditables sans divulguer l’existence d’une affectation étrangère.

Les succès de mutation portent `AUTHZ_SUCCEEDED` lorsque la policy est évaluée dans une transaction qui aboutit. Les refus portent `AUTHZ_DENIED` avec les motifs fermés `ASSIGNMENT_INACTIVE`, `ASSIGNMENT_SCOPE_FORBIDDEN`, `ASSIGNMENT_ACTOR_MISMATCH`, `CASE_NOT_FOUND_OR_FORBIDDEN`, `VERSION_CONFLICT` ou `IDEMPOTENCY_KEY_REUSED`.

## 9. Critères de fermeture

Le slice sera fermé lorsque les tests prouveront : collaborateur affecté autorisé ; patron non destinataire refusé pour la reconnaissance ; affectation suspendue/expirée/terminée refusée ; Case et membership inter-tenant neutres ; scope sans le verbe requis refusé ; révision obsolète rejetée ; replay sans doublon ; même clé avec payload différent rejetée ; reconnaissance et indisponibilité append-only ; demande de clarification idempotente ; aucun changement direct de tâche, échéance, scope, rôle, décision ou prix ; événements et audit minimisés ; et cycle Alembic `upgrade head/check/downgrade base` sans écart.

## 10. Hors périmètre explicite

Le slice ne comprend pas la création d’une affectation par le patron, la liste des tâches, l’exécution d’une tâche, la réponse du patron, la réaffectation automatique, le calcul d’impact DCE, les documents techniques, la préparation, le snapshot, la transmission, les partages externes ou toute donnée financière.
