# SMART_AO V8 — Contrat normatif `PATRON-ASSIGNMENT-MANAGEMENT-01`

**Statut : FIGÉ avant code, amendé une fois pour résoudre la fenêtre future.**

> **Amendement normatif A — fenêtre future.** La phrase de l’invariant 3 qui imposait
> `starts_at <= granted_at` contredisait la machine d’état des sections 4 et 5, qui autorise
> explicitement une affectation `ACTIVE` avec démarrage futur. La machine d’état prévaut :
> `starts_at` peut être antérieur, égal ou postérieur à `granted_at`; seule la règle
> `ends_at IS NULL OR ends_at > starts_at` reste une contrainte temporelle de persistance.
> La migration additive `20260814_0022` retire le check PostgreSQL contradictoire sans réécrire
> les affectations ni leurs journaux.

Ce contrat définit la prochaine frontière d’écriture permettant au patron de créer et de piloter des affectations collaborateur sur une affaire. Il est la source de vérité pour le domaine, les commandes, la migration, les handlers, les routes HTTP futures, les projections et les tests. Toute divergence ultérieure exige un amendement explicite du présent contrat avant modification de code.

## 1. Objet, finalité et limites métier

Une **affectation** désigne l’autorisation opérationnelle, bornée dans le temps et dans son périmètre, accordée par le patron à un collaborateur pour préparer une affaire. Elle ne confère jamais une délégation de décision, de chiffrage, de prix, de marge, de trésorerie, de validation finale ou de dépôt.

Le patron décide qui intervient sur une affaire, avec quelles actions opérationnelles et durant quelle période. Le collaborateur peut ensuite uniquement utiliser les frontières déjà publiées : lire son DCE affecté, confirmer selon son scope, reconnaître l’affectation, demander une clarification, signaler une indisponibilité et relire son propre historique fermé. Il ne peut ni créer, ni modifier, ni suspendre, ni réactiver, ni terminer une affectation.

| Inclus dans le slice | Exclu du slice |
|---|---|
| Création, amendement de scope, suspension, réactivation et fin d’une affectation. | Décision Go/No-Go, chiffrage, prix, marge, devis, dépôt, signature, transmission finale. |
| Journal patron append-only des changements. | Réaffectation automatique, création de tâche, modification d’échéance ou calcul d’impact automatique. |
| Idempotence, révision optimiste, audit SEC-01, outbox et FKs tenant-scopées. | Réponse patron à une clarification, messagerie, cockpit UI, export ou lecture globale de l’historique. |
| Contrat de persistance et critères de tests. | Modification ou suppression des trois historiques collaborateur publiés. |

> Une affectation est un acte de délégation opérationnelle contrôlée. Elle ne vaut ni confirmation de conformité, ni acceptation de charge, ni acceptation de prix, ni décision humaine sur l’appel d’offres.

## 2. Ownership et autorité serveur

`CaseAssignmentRecord` reste l’agrégat racine de l’affectation. La Case reste propriétaire de son cycle de vie commercial ; elle n’est jamais mutée par une commande d’affectation. La membership cible est une référence d’autorité et de destinataire ; elle n’est pas modifiée par ce slice.

| Fait | Propriétaire / source | Règle non négociable |
|---|---|---|
| Tenant, identité, rôle, membership et session | Résolveur bearer SEC-01 | Ne viennent jamais du payload HTTP. |
| Capability patron | Catalogue fermé serveur | Nouvelle capability `assignment.manage`, accordée à `PATRON_ADMIN` uniquement. |
| Case et cycle de vie | Agrégat / table `cases` | Une Case hors tenant, absente ou archivée ne reçoit aucune affectation nouvelle ni mutation patron. |
| Destinataire | `tenant_memberships` | La cible est une membership `COLLABORATEUR`, `ACTIVE`, du même tenant. |
| Scope et classification | Payload fermé validé par le serveur | Seuls les éléments du catalogue de la section 4 sont persistés. |
| Horodatage effectif | Horloge serveur | `granted_at`, `ended_at` et la date de journalisation ne sont jamais pilotés par le navigateur. |

Les acteurs `SYSTEM`, `COLLABORATEUR` et `PATRON_DELEGATE` sont interdits pour les cinq commandes de ce contrat. Une membership patron inactive ou une session révoquée est refusée par SEC-01 avant toute écriture.

## 3. Capability, classifications et scopes fermés

### 3.1 Capability de gestion

Le catalogue `Capability` reçoit la valeur stable suivante :

```text
ASSIGNMENT_MANAGE = "assignment.manage"
```

Elle est ajoutée à `_PATRON_ADMIN_CAPABILITIES` et n’est ajoutée ni aux capabilities collaborateur ni à `_DELEGABLE_CAPABILITIES`. La gestion d’une affectation ne s’appuie pas sur `membership.manage`, `tenant.manage`, `decision.finalize` ou une capability financière : ces frontières restent distinctes.

### 3.2 Catalogue du scope collaborateur

Une affectation porte une liste d’actions et une liste de classifications. Les deux listes sont non vides, dédupliquées, triées canoniquement avant empreinte et stockées sans action inconnue.

| Type | Valeurs autorisées |
|---|---|
| `scope_actions` | `case.dce.read`, `dce.requirement.confirm`, `document.administrative.read`, `preparation.transmit`, `assignment.acknowledge`, `assignment.clarify`, `assignment.history.read`, `assignment.unavailability` |
| `scope_classifications` | `INTERNAL_OPERATIONAL` uniquement |

Les valeurs `pricing.read`, `pricing.write`, `decision.finalize`, `submission.authorize`, `export.sensitive`, une capability inconnue, une classification financière ou une classification de sécurité sont toujours refusées. Une liste vide, un doublon, une valeur hors catalogue ou une tentative de contournement par casse, préfixe ou JSON non tableau est un rejet de validation sans écriture.

## 4. Commandes fermées et effets durables

Chaque commande est portée par l’enveloppe standard `command_id`, `idempotency_key`, `correlation_id?`. L’empreinte idempotente est établie par le dispatcher sur le type de commande, le payload canonique et les faits pertinents de révision. La clé est toujours évaluée dans le tuple :

```text
(tenant_id, actor_id, command_type, idempotency_key)
```

| Commande | Entrée spécifique obligatoire | Préconditions métier | Mutation atomique |
|---|---|---|---|
| `CreateCaseAssignment` | `assignment_id`, `case_id`, `target_membership_id`, `expected_case_revision`, `scope_actions`, `scope_classifications`, `starts_at`, `ends_at?` | Case active du tenant, membership cible active collaborateur, révision de Case exacte, absence d’affectation active ou suspendue pour le couple cible/Case. | Crée l’affectation `ACTIVE` à révision `0`, écrit `ASSIGNMENT_CREATED`, receipt, événement et outbox. |
| `AmendCaseAssignmentScope` | `assignment_id`, `expected_revision`, nouvelles listes fermées `scope_actions` et `scope_classifications` | Affectation active ou suspendue, même tenant, scope réellement différent. | Remplace seulement le scope, incrémente la révision, écrit `ASSIGNMENT_SCOPE_AMENDED`. |
| `SuspendCaseAssignment` | `assignment_id`, `expected_revision`, `suspension_reason_code` fermé | Affectation `ACTIVE`. | Passe à `SUSPENDED`, incrémente la révision et écrit `ASSIGNMENT_SUSPENDED`. |
| `ReactivateCaseAssignment` | `assignment_id`, `expected_revision` | Affectation `SUSPENDED`, fenêtre temporelle encore valable, Case et cible toujours actives, aucune autre affectation active pour le même couple cible/Case. | Passe à `ACTIVE`, incrémente la révision et écrit `ASSIGNMENT_REACTIVATED`. |
| `EndCaseAssignment` | `assignment_id`, `expected_revision`, `end_reason_code` fermé | Affectation `ACTIVE` ou `SUSPENDED`. | Passe à `ENDED`, renseigne `ended_at` serveur, incrémente la révision et écrit `ASSIGNMENT_ENDED`. |

`CreateCaseAssignment` ne porte pas de révision d’affectation car la racine n’existe pas encore ; elle porte obligatoirement `expected_case_revision` afin de verrouiller la Case et d’empêcher une création sur un contexte Case devenu obsolète. Les quatre commandes sur une affectation existante portent obligatoirement `expected_revision`.

Les raisons sont des enum fermés. `suspension_reason_code` accepte `PATRON_SUSPENDED`, `WORKLOAD_REALLOCATION`, `CASE_PAUSED` et `ACCESS_REVIEW`. `end_reason_code` accepte `PATRON_ENDED`, `CASE_STOPPED`, `CASE_ARCHIVED`, `COLLABORATOR_UNAVAILABLE` et `MEMBERSHIP_REVOKED`. Aucun texte libre de justification n’est enregistré dans ce slice.

## 5. Machine d’état et invariants

La création produit l’état `ACTIVE`, y compris lorsque `starts_at` est futur : l’affectation reste alors persistée mais est inutilisable par le collaborateur avant son début. `EXPIRED` reste un état réservé à un futur processus déterministe de maintenance ; aucune commande patron de ce slice ne l’écrit.

| État source | Commande admise | État résultat | Interdictions associées |
|---|---|---|---|
| Inexistant | `CreateCaseAssignment` | `ACTIVE` | Aucun écrasement d’un identifiant existant. |
| `ACTIVE` | `AmendCaseAssignmentScope` | `ACTIVE` | Ne change ni Case, ni membership cible, ni fenêtre, ni historiques collaborateur. |
| `ACTIVE` | `SuspendCaseAssignment` | `SUSPENDED` | Ne termine pas l’affectation et ne supprime rien. |
| `ACTIVE` | `EndCaseAssignment` | `ENDED` | Ne peut pas être réactivée ultérieurement. |
| `SUSPENDED` | `AmendCaseAssignmentScope` | `SUSPENDED` | Ne rend pas l’accès collaborateur utilisable. |
| `SUSPENDED` | `ReactivateCaseAssignment` | `ACTIVE` | Rejet si la fenêtre, la Case, la cible ou l’unicité ne sont plus valides. |
| `SUSPENDED` | `EndCaseAssignment` | `ENDED` | Ne restaure aucun scope ni historique. |
| `ENDED` ou `EXPIRED` | Aucune commande patron du slice | inchangé | Aucun retour vers `ACTIVE` ou `SUSPENDED`. |

Les invariants suivants sont obligatoires :

1. Une commande ne change jamais `case_id`, `membership_id`, `granted_by_membership_id`, `granted_at`, `starts_at` ou `ends_at` après création. Une nouvelle période ou un nouveau destinataire exige la fin de l’affectation existante puis la création d’une nouvelle affectation et d’un nouvel identifiant.
2. Une même membership ne possède jamais plus d’une affectation `ACTIVE` **ou** `SUSPENDED` pour la même Case. La migration remplace l’index partiel existant par une contrainte équivalente sur `state IN ('ACTIVE', 'SUSPENDED')`.
3. `starts_at` peut être antérieur, égal ou postérieur à `granted_at`; `ends_at` est absente ou strictement postérieure à `starts_at`, et une réactivation est refusée si `ends_at <= received_at`.
4. Une suspension, une fin ou un scope amendé n’écrit aucune ligne dans `case_assignment_acknowledgements`, `assignment_clarification_requests` ou `case_assignment_unavailabilities`.
5. Toute mutation réussie fait progresser `aggregate_revision` d’exactement une unité, sauf la création qui initialise la révision à `0`.
6. L’absence d’effet est totale sur conflit de révision, idempotence divergente, scope invalide, actor invalide, Case interdite ou tenant différent.

## 6. Autorisation, confidentialité et audit

L’ordre d’exécution est strict : résolution bearer SEC-01, résolution tenant-scopée de la ressource, vérifications métier minimales, `AuditedAuthorizationPolicy`, verrou transactionnel, vérifications d’invariants, mutation atomique. Les identifiants de tenant, membership, Case, scope, classification, rôle et auteur ne sont jamais reçus comme faits d’autorité depuis le navigateur.

| Situation | Réponse publique | Écriture d’audit |
|---|---|---|
| Bearer absent, expiré, révoqué ou non résoluble | `401` | Selon le mécanisme d’authentification existant, sans révélation de ressource. |
| Affectation ou Case hors tenant, absente, ou cible non résoluble hors frontière visible | `404 NOT_FOUND_OR_FORBIDDEN` | `AUTHZ_DENIED`, métadonnées minimisées. |
| Acteur non patron, capability absente, membership inactive ou scope patron interdit | `403 FORBIDDEN` | `AUTHZ_DENIED`, action `assignment.manage`. |
| Révision obsolète, idempotency key divergente ou commande concurrente | `409` | Receipt/dispatcher conservé selon le cas, sans mutation métier supplémentaire. |
| Payload fermé invalide, transition d’état invalide ou invariant métier rompu | `422` | Aucun journal de changement patron ni événement métier. |
| Mutation autorisée et committée | `201` initial, `200` pour rejeu identique | `AUTHZ_SUCCEEDED` dans la même transaction logique. |

Le journal d’audit ne contient pas de prix, marge, devis, contenu DCE, texte libre de clarification, secret, token, hash de credential ou scope libre non contrôlé. L’événement de domaine et l’outbox ne contiennent que les identifiants, l’ancien et le nouveau statut, les révisions, le motif fermé et une empreinte ou manifeste fermé du scope.

## 7. Persistance et immutabilité

La migration du slice est additive. Elle ne réécrit aucune donnée des migrations `0001` à `0020` et ne modifie pas les trois historiques collaborateur publiés.

| Élément | Décision de persistance obligatoire |
|---|---|
| `case_assignments` | Conservation de `tenant_id`, FKs composites, checks de fenêtre/révision et de l’état. L’index d’unicité est remplacé pour couvrir `ACTIVE` et `SUSPENDED`. |
| `case_assignment_change_events` | Nouveau journal append-only tenant-scopé : `id`, `tenant_id`, `assignment_id`, `case_id`, `target_membership_id`, `author_membership_id`, `event_type`, `previous_revision?`, `resulting_revision`, `previous_state?`, `resulting_state`, `reason_code?`, manifests fermés d’actions/classifications, `command_id`, `correlation_id?`, `created_at`. |
| FKs | Contraintes composites vers `tenants`, `case_assignments`, `cases`, membership cible et membership auteur. Aucun `ON DELETE CASCADE`. |
| Constraints | Enum fermé d’événement et de motif, révisions non négatives, cohérence `previous_revision/resulting_revision`, JSONB tableaux non vides et validation de la fenêtre. |
| Immutabilité | Triggers PostgreSQL interdisant `UPDATE` et `DELETE` sur `case_assignment_change_events`. |
| Index | Index tenant/affectation/horodatage pour relecture patron future, index tenant/Case/cible/état pour les contrôles de création et réactivation. |

`case_assignment_change_events` constitue le journal patron de vérité des changements d’autorité. Il est distinct du journal de sécurité SEC-01 et des observations collaborateur. Il ne remplace ni ne synthétise les historiques collaborateurs.

## 8. Événements, outbox et idempotence

Une mutation autorisée écrit dans une seule transaction : la racine `CaseAssignmentRecord`, un `case_assignment_change_events`, l’événement de domaine minimal, l’outbox et le receipt idempotent. L’ordre logique reste compatible avec le dispatcher V8 ; aucun processus asynchrone ne peut observer un changement patron sans que son journal et son receipt soient déjà durables.

| Commande | Événement minimal | Données d’événement admises |
|---|---|---|
| Création | `CaseAssignmentCreated` | IDs tenant/Case/affectation/cible, révision `0`, fenêtre, manifeste fermé du scope. |
| Amendement | `CaseAssignmentScopeAmended` | IDs, ancienne/nouvelle révision, empreintes de scope. |
| Suspension | `CaseAssignmentSuspended` | IDs, révision, motif fermé. |
| Réactivation | `CaseAssignmentReactivated` | IDs, révision. |
| Fin | `CaseAssignmentEnded` | IDs, révision, motif fermé, `ended_at` serveur. |

Le rejeu avec la même clé et le même contenu retourne le receipt antérieur sans créer de deuxième changement, événement ou message outbox. La même clé avec un contenu, une révision ou une corrélation différente retourne `IDEMPOTENCY_KEY_REUSED` et ne modifie rien.

## 9. Contrat HTTP futur et projections

Ce contrat ne demande pas encore de route HTTP ni de cockpit patron. Lorsqu’une façade HTTP sera ouverte, elle utilisera uniquement le runtime bearer réel SEC-01 et adoptera les cinq routes suivantes, sans changer le contrat applicatif :

| Méthode prévue | Route prévue | Réponse fermée |
|---|---|---|
| `POST` | `/api/v1/patron/cases/{case_id}/assignments` | Receipt idempotent patron. |
| `POST` | `/api/v1/patron/assignments/{assignment_id}/scope-amendments` | Receipt idempotent patron. |
| `POST` | `/api/v1/patron/assignments/{assignment_id}/suspensions` | Receipt idempotent patron. |
| `POST` | `/api/v1/patron/assignments/{assignment_id}/reactivations` | Receipt idempotent patron. |
| `POST` | `/api/v1/patron/assignments/{assignment_id}/endings` | Receipt idempotent patron. |

Le patron ne reçoit dans ce slice que des receipts fermés. Une future vue patron pourra exposer le statut, la révision, les dates et le manifeste de scope strictement nécessaire, après son propre contrat de projection. Une réponse consommée par un collaborateur ne doit jamais inclure l’auteur patron, les raisons internes, le scope brut, les journaux de sécurité ou des données financières.

## 10. Matrice de tests de fermeture

| Domaine | Cas requis |
|---|---|
| Validation de commandes | UUID, listes vides/doublons/inconnues, action financière, classification interdite, fenêtre invalide, reason code inconnu, révision négative, corps avec champ supplémentaire. |
| Création | Patron du tenant, Case active, collaborateur actif, démarrage immédiat et futur, conflit de Case revision, couple cible/Case déjà actif ou suspendu, tenant et membership étrangers. |
| Scope | Amendement valide actif et suspendu, scope inchangé, action retirée, action ajoutée, conflit de révision, révision exactement incrémentée et journal conservé. |
| États | `ACTIVE → SUSPENDED → ACTIVE`, `ACTIVE → ENDED`, `SUSPENDED → ENDED`, interdictions depuis `ENDED` et `EXPIRED`, réactivation expirée ou avec Case/cible inactive. |
| Régression collaborateur | Suspension, fin ou retrait du verbe bloquent immédiatement les commandes et la lecture collaborateur ; réactivation rétablit seulement le scope explicite ; les anciens historiques restent identiques. |
| Idempotence et atomicité | Rejeu identique des cinq commandes, conflit de clé, concurrence/révision obsolète, rollback sans racine/journal/événement/outbox/receipt partiel. |
| PostgreSQL | FKs composites, nouvel index partiel, checks, trigger append-only, rejet SQL `UPDATE`/`DELETE` sur le journal patron, upgrade/head/check/downgrade/base. |
| HTTP futur | Bearer réel, 401/403/404/409/422, ReBAC auditée, absence de fuite inter-tenant, DTO `extra='forbid'`, snapshot OpenAPI. |

Le slice ne peut être déclaré implémenté qu’après Ruff, tests de domaine et PostgreSQL, harnais API, cycle Alembic complet, `detect-secrets`, export OpenAPI, revue de `git diff --check` et CI GitHub verte.

## 11. Hors périmètre explicite

Ce contrat ne crée aucun mécanisme de pricing, catalogue de prix, chiffrage, marge, trésorerie, décision Go/No-Go, dépôt, signature ou automatisation qui agirait sans le patron. Il ne traite pas non plus le routage automatique d’une indisponibilité, la réponse aux demandes de clarification, les tâches, les notifications, les mails, les exports, le cockpit web ou une pagination d’historique. Ces sujets exigent chacun un contrat propre et ne peuvent pas être inférés d’une affectation.
