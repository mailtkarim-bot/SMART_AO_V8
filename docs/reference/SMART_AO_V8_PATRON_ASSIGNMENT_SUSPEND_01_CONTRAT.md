# SMART_AO V8 — PATRON-ASSIGNMENT-SUSPEND-01 — Contrat normatif

**Statut : FIGÉ avant code.**

Ce contrat limite strictement le prochain incrément à la suspension manuelle, révisionnée et auditée d’une affectation collaborateur existante. Il complète `PATRON-ASSIGNMENT-MANAGEMENT-01` sans modifier la création, l’amendement de scope, les historiques collaborateur, la réactivation, la fin d’affectation ou le cockpit patron.

## 1. Finalité métier et frontière

Le patron suspend une affectation lorsqu’un collaborateur ne doit plus disposer temporairement de son accès opérationnel à une affaire. La suspension bloque la capacité opérationnelle de l’affectation, mais ne détruit ni l’affectation, ni son scope, ni les accusés, demandes de clarification ou signalements d’indisponibilité déjà conservés.

> Une suspension n’est pas une fin d’affectation, une décision Go/No-Go, une réallocation automatique, une modification de prix, un retrait de document ni une mesure disciplinaire. Elle représente uniquement une interruption temporaire et traçable de l’autorisation opérationnelle.

| Inclus | Explicitement exclu |
|---|---|
| Transition `ACTIVE → SUSPENDED` initiée par le patron. | Réactivation, fin, expiration, suppression ou modification de fenêtre. |
| Motif fermé sans texte libre. | Création de tâche, notification, mail, automatisation de réaffectation ou calcul d’impact. |
| Révision optimiste, idempotence, journal patron, événement, outbox, receipt et audit SEC-01. | Modification de scope, Case, cible, auteur, dates, données financières ou historiques collaborateur. |
| Route HTTP patron et projection de receipt fermée. | Vue patron globale, cockpit, export ou lecture de journal patron. |

## 2. Commande fermée

La commande applicative stable est `SuspendCaseAssignment`. Elle emploie l’enveloppe V8 standard et refuse tout champ inconnu.

| Champ | Règle |
|---|---|
| `command_id` | UUID unique de la tentative métier. |
| `idempotency_key` | UUID, évalué dans `(tenant_id, actor_id, command_type, idempotency_key)`. |
| `correlation_id?` | UUID de corrélation facultatif, jamais une donnée d’autorité. |
| `assignment_id` | UUID de l’affectation mutée, fourni par le chemin HTTP. |
| `expected_revision` | Entier supérieur ou égal à zéro, obligatoirement égal à la révision courante. |
| `suspension_reason_code` | Enum fermé : `PATRON_SUSPENDED`, `WORKLOAD_REALLOCATION`, `CASE_PAUSED`, `ACCESS_REVIEW`. |

Le navigateur ne fournit jamais tenant, membership patron, rôle, capability, état courant, scope, classification, Case, cible, date effective, motif libre, données financières ou instruction d’audit.

## 3. Autorisation, neutralité et audit

L’acteur doit être résolu par le bearer réel SEC-01, être `PATRON_ADMIN`, disposer de `assignment.manage` et d’une membership active du tenant. Les acteurs `SYSTEM`, `COLLABORATEUR` et `PATRON_DELEGATE` sont interdits.

| Situation | Réponse HTTP publique | Effet durable |
|---|---|---|
| Bearer absent, invalide ou révoqué | `401` | Aucun changement métier. |
| Affectation absente ou hors tenant | `404 NOT_FOUND_OR_FORBIDDEN` | Audit minimal `AUTHZ_DENIED`; aucune existence révélée. |
| Acteur non patron ou capability insuffisante | `403 FORBIDDEN` | Audit `AUTHZ_DENIED`, action `assignment.manage`. |
| Révision obsolète, clé divergente ou commande en cours | `409` | Receipt/dispatcher uniquement ; aucune mutation de l’affectation. |
| État différent de `ACTIVE` ou payload/motif fermé invalide | `422 COMMAND_REJECTED` ou validation FastAPI | Aucun journal patron, événement ou outbox métier. |
| Suspension initiale autorisée | `201` | Mutation atomique et audit réussi. |
| Rejeu strictement identique | `200` | Retour du receipt antérieur, sans deuxième écriture. |

La résolution tenant-scopée précède la policy. Toute absence hors tenant reste neutre. Les refus de rôle avant policy sont eux-mêmes audités par le service, conformément à SEC-01.

## 4. Transition d’état et invariants

La seule transition admise dans ce slice est :

```text
ACTIVE --SuspendCaseAssignment--> SUSPENDED
```

Les invariants suivants sont non négociables :

1. L’affectation est verrouillée en écriture avant de contrôler `expected_revision`.
2. Seul l’état `ACTIVE` est suspendable ; `SUSPENDED`, `ENDED` et `EXPIRED` sont rejetés.
3. La mutation ne change que `state` et `aggregate_revision`, qui progresse exactement de un.
4. `case_id`, `membership_id`, `granted_by_membership_id`, `granted_at`, `starts_at`, `ends_at`, scope et classifications restent identiques.
5. La suspension ne crée ni ne modifie aucun enregistrement d’historique collaborateur.
6. Après commit, le contexte collaborateur ne peut plus employer l’affectation suspendue pour les frontières opérationnelles protégées par ReBAC.
7. La réactivation éventuelle est hors périmètre et exigera son propre contrat ; la suspension ne la pré-autorise pas.

## 5. Transaction, journal, événement et receipt

Dans une seule transaction, le handler doit : verrouiller l’affectation tenant-scopée, vérifier l’état et la révision, positionner `state = SUSPENDED`, incrémenter la révision, insérer un journal patron, persister l’événement et l’outbox via le dispatcher, puis finaliser le receipt idempotent.

| Élément | Valeur obligatoire |
|---|---|
| Journal | `case_assignment_change_events` avec `event_type = ASSIGNMENT_SUSPENDED`. |
| Révisions | `previous_revision = n`, `resulting_revision = n + 1`. |
| États journalisés | `previous_state = ACTIVE`, `resulting_state = SUSPENDED`. |
| Motif | Le `suspension_reason_code` fermé, sans commentaire libre. |
| Scope dans le journal | Copie des deux manifests existants, sans transformation ni élargissement. |
| Événement | `CaseAssignmentSuspended` avec IDs minimaux, révisions et motif fermé uniquement. |
| Receipt | `CASE_ASSIGNMENT_SUSPENDED`, `201` initial ou `200` au rejeu strict. |

Le trigger PostgreSQL existant interdit tout `UPDATE` ou `DELETE` du journal patron. Aucune migration de table n’est nécessaire : la migration `20260814_0021` contient déjà l’événement, le motif fermé, les manifests, les FKs composites et les checks nécessaires. La migration `20260814_0022` reste la tête Alembic et doit être vérifiée par `upgrade head`, `alembic check` et `downgrade base`.

## 6. Contrat HTTP et OpenAPI

La seule route ajoutée est :

```text
POST /api/v1/patron/assignments/{assignment_id}/suspensions
```

Le corps fermé contient exclusivement `command_id`, `idempotency_key`, `correlation_id?`, `expected_revision` et `suspension_reason_code`. La réponse est le `AssignmentCommandResponse` déjà publié : IDs de commande et d’idempotence, code résultat, références agrégat, IDs d’événements et drapeau de rejeu. Elle exclut tenant, cible, scope, classifications, auteur, motif interne libre, audit, prix, marge, devis, décision et données de dépôt.

Le snapshot OpenAPI doit passer de six à sept opérations Assignment/patron. Il déclare `201`, `200`, `401`, `403`, `404`, `409` et `422` avec leurs significations publiques minimisées.

## 7. Matrice de fermeture

| Domaine | Cas obligatoires |
|---|---|
| Pydantic | Motif autorisé, motif inconnu, révision négative, UUID invalide, champ HTTP supplémentaire. |
| PostgreSQL | Transition active, révision +1, conservation scope/fenêtre, journal correct, événement/outbox, refus suspendu/terminé, conflit de révision, rejeu et trigger append-only. |
| Sécurité | Patron autorisé, collaborateur refusé et audité, ressource étrangère neutre, absence de bearer. |
| HTTP | `201`, `200` rejeu, `403`, `404`, `409`, `422`, DTO fermé et absence de fuite. |
| Alembic | Migration `0021` et correctif `0022` atteignent `head`, `check` ne détecte aucune dérive et le rollback vers `base` reste possible sur un jeu sans fenêtre future persistée. |
| Performance | Le benchmark insère et relit des journaux `ASSIGNMENT_SUSPENDED` réels sous les budgets de régression locale documentés ; ce n’est pas une garantie de capacité VPS. |

Le slice est publiable seulement après Ruff, tests Pydantic/PostgreSQL/API, benchmark, cycle Alembic, scan de secrets, `git diff --check`, OpenAPI régénérée et CI GitHub verte.
