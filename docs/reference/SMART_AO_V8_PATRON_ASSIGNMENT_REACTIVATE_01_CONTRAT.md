# SMART_AO V8 — PATRON-ASSIGNMENT-REACTIVATE-01 — Contrat normatif

**Statut : FIGÉ avant code.**

Ce contrat ouvre exclusivement la réactivation manuelle, révisionnée et auditée d’une affectation collaborateur suspendue. Il succède à `PATRON-ASSIGNMENT-SUSPEND-01`, sans réinterpréter sa suspension, modifier le scope, déplacer la fenêtre, réaffecter l’affaire ni achever l’affectation.

## 1. Finalité métier et frontière

Le patron réactive une affectation temporairement suspendue lorsqu’un collaborateur peut à nouveau reprendre la préparation opérationnelle du DCE. La réactivation restaure uniquement l’état opérationnel de l’affectation existante ; elle ne valide pas le dossier, ne décide pas de répondre, ne relance pas automatiquement le collaborateur et ne produit aucun travail au nom de ce dernier.

> Une réactivation n’est ni une nouvelle affectation, ni une décision Go/No-Go, ni un rétablissement automatique d’un accès expiré ou terminé. Elle est une transition patron explicite de `SUSPENDED` vers `ACTIVE` pendant une fenêtre encore utilisable.

| Inclus | Explicitement exclu |
|---|---|
| Transition `SUSPENDED → ACTIVE` initiée par le patron. | Création, amendement de scope, suspension, fin, expiration, suppression ou changement de période. |
| Motif fermé, fenêtre d’accès et cible active contrôlés côté serveur. | Motif libre, commentaire, notification, tâche, mail, réaffectation automatique ou calcul d’impact. |
| Révision optimiste, idempotence, journal, événement, outbox, receipt et audit SEC-01. | Modification de Case, cible, scope, classifications, auteur, dates, données financières ou historiques collaborateur. |
| Route HTTP patron et projection de receipt fermée. | Cockpit patron, export du journal, lecture publique de motif ou délégation à un collaborateur. |

## 2. Commande fermée

La commande stable est `ReactivateCaseAssignment`. Elle utilise l’enveloppe V8 standard et interdit les champs inconnus.

| Champ | Règle |
|---|---|
| `command_id` | UUID de la tentative métier. |
| `idempotency_key` | UUID évalué dans `(tenant_id, actor_id, command_type, idempotency_key)`. |
| `correlation_id?` | UUID optionnel de corrélation, sans autorité métier. |
| `assignment_id` | UUID de l’affectation, issu du chemin HTTP. |
| `expected_revision` | Entier supérieur ou égal à zéro, égal à la révision courante verrouillée. |
| `reactivation_reason_code` | Enum fermé : `PATRON_REACTIVATED`, `CASE_RESUMED`, `ACCESS_REVIEW_CLEARED`. |

Le navigateur ne fournit jamais tenant, patron, rôle, capability, état, scope, classifications, Case, cible, fenêtre, horodatage effectif, texte libre, prix, marge, décision, audit ni consigne de notification.

## 3. Autorisation, neutralité et audit

L’acteur est résolu exclusivement par bearer réel SEC-01. Il doit être `PATRON_ADMIN`, appartenir activement au tenant et disposer de `assignment.manage`. Les acteurs `SYSTEM`, `COLLABORATEUR` et `PATRON_DELEGATE` sont interdits.

| Situation | Réponse HTTP publique | Effet durable |
|---|---|---|
| Bearer absent, invalide ou révoqué | `401` | Aucun effet métier. |
| Affectation absente ou hors tenant | `404 NOT_FOUND_OR_FORBIDDEN` | Audit minimal de refus, sans révélation d’existence. |
| Acteur non patron ou capability insuffisante | `403 FORBIDDEN` | Audit `AUTHZ_DENIED`, action `assignment.manage`. |
| Requête divergente sous même clé, commande en cours ou révision obsolète | `409` | Aucun changement de l’affectation. |
| État, fenêtre, cible, Case ou motif invalide | `422 COMMAND_REJECTED` ou validation FastAPI | Aucun journal, événement ni outbox métier. |
| Réactivation initiale autorisée | `201` | Mutation atomique. |
| Rejeu strictement identique | `200` | Receipt antérieur, sans seconde écriture. |

La recherche tenant-scopée précède la policy. Les refus de rôle sont audités avant dispatch. La route ne distingue jamais une affectation étrangère d’une affectation inexistante.

## 4. Transition et invariants de fenêtre

La seule transition admise est :

```text
SUSPENDED --ReactivateCaseAssignment--> ACTIVE
```

Les invariants non négociables sont les suivants :

1. L’affectation est verrouillée avant le contrôle de révision et doit être exactement `SUSPENDED`.
2. La Case tenant-scopée doit exister et avoir `lifecycle = ACTIVE`.
3. La cible reste une membership `COLLABORATEUR` dans l’état `ACTIVE` du même tenant.
4. À l’instant serveur `now`, la fenêtre doit être ouverte : `starts_at <= now` et, si `ends_at` existe, `now < ends_at`.
5. La mutation ne modifie que `state` et `aggregate_revision`, qui progresse exactement de un.
6. `case_id`, cible, auteur initial, `granted_at`, fenêtre, scope et classifications restent invariants.
7. Les historiques collaborateur ne sont ni créés ni modifiés ; aucune action collaborateur n’est exécutée automatiquement.
8. `ENDED` et `EXPIRED` ne sont jamais réactivables par ce slice. La réactivation ne contourne aucune future frontière de fin ou d’expiration.

## 5. Transaction, journal, événement et migration

Dans la même transaction, le handler verrouille l’affectation, vérifie l’état, la révision, la Case, la cible et la fenêtre ; il passe ensuite l’état à `ACTIVE`, incrémente la révision, insère le journal, persiste l’événement/outbox via le dispatcher et finalise le receipt.

| Élément | Valeur obligatoire |
|---|---|
| Journal | `case_assignment_change_events`, `event_type = ASSIGNMENT_REACTIVATED`. |
| Révisions | `previous_revision = n`, `resulting_revision = n + 1`. |
| États journalisés | `previous_state = SUSPENDED`, `resulting_state = ACTIVE`. |
| Motif | `reactivation_reason_code` fermé, sans commentaire libre. |
| Scope journalisé | Copies identiques des deux manifests précédents et résultants. |
| Événement | `CaseAssignmentReactivated`, avec IDs minimaux, révisions et motif fermé. |
| Receipt | `CASE_ASSIGNMENT_REACTIVATED`, `201` initial ou `200` au rejeu strict. |

La migration `20260814_0021` accepte déjà l’événement `ASSIGNMENT_REACTIVATED`, mais son check `reason_code` n’accepte pas les trois motifs de réactivation. Une migration additive **`20260814_0023`** est donc obligatoire : elle remplace uniquement le check fermé `reason` par la même liste enrichie de `PATRON_REACTIVATED`, `CASE_RESUMED` et `ACCESS_REVIEW_CLEARED`. Elle ne réécrit aucune ligne de journal, ne touche ni aux FKs, ni aux indexes, ni au trigger append-only. Son downgrade restaure le catalogue précédent et doit échouer naturellement si des raisons nouvelles persistent, afin d’éviter toute perte de données durable.

## 6. Contrat HTTP et OpenAPI

La seule route ajoutée est :

```text
POST /api/v1/patron/assignments/{assignment_id}/reactivations
```

Le corps fermé contient exclusivement `command_id`, `idempotency_key`, `correlation_id?`, `expected_revision` et `reactivation_reason_code`. Le résultat emploie `AssignmentCommandResponse` : IDs de commande et d’idempotence, code résultat, références agrégat, IDs d’événements et drapeau de rejeu. Il exclut tenant, cible, scope, classifications, auteur, dates, motif, audit, stockage, finance, décision et dépôt.

Le snapshot OpenAPI passe de sept à huit opérations Assignment/patron. Il doit documenter `201`, `200`, `401`, `403`, `404`, `409` et `422` sans révéler les détails de policy, de fenêtre ou de la cible.

## 7. Matrice de fermeture

| Domaine | Cas obligatoires |
|---|---|
| Pydantic | Trois motifs admis, motif inconnu, révision négative, UUID invalide et champ supplémentaire. |
| PostgreSQL | Transition, révision +1, conservation scope/fenêtre, journal, événement/outbox, rejeu, état non suspendu, révision obsolète, Case/cible/fenêtre invalides et trigger append-only. |
| Sécurité | Patron autorisé, collaborateur refusé et audité, ressource étrangère neutre, bearer absent. |
| HTTP | `201`, `200` au rejeu, `403`, `404`, `409`, `422`, requête fermée et absence de fuite. |
| Alembic | `0021`, `0022` puis `0023` atteignent `head`; `alembic check` ne détecte aucune dérive; le downgrade est contrôlé sur un jeu sans motif de réactivation persistant. |
| Performance | Le benchmark insère et relit 1 000 journaux `ASSIGNMENT_REACTIVATED` réels sous les budgets locaux documentés; ce n’est pas une promesse de capacité VPS. |

Le slice ne peut être publié qu’après Ruff, tests Pydantic/PostgreSQL/API, benchmark, cycle Alembic, scan de secrets, `git diff --check`, OpenAPI régénérée et CI GitHub verte.
