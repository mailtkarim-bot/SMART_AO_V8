# SMART_AO V8 — PATRON-ASSIGNMENT-END-01 — Contrat normatif

**Statut : implémenté localement, publication en attente de CI GitHub.**

Ce contrat ouvre exclusivement la fin manuelle, révisionnée, irréversible et auditée d’une affectation collaborateur. Il succède aux frontières de création, d’amendement, de suspension et de réactivation ; il ne modifie ni leur historique ni leur sémantique.

## 1. Finalité métier et frontière

Le patron met définitivement fin à une affectation lorsqu’un collaborateur ne doit plus être habilité à préparer ou transmettre des éléments sur une affaire. La fin arrête durablement l’accès opérationnel de cette affectation, sans effacer les travaux, accusations, demandes de clarification, indisponibilités ni journaux déjà constitués.

> Une fin d’affectation n’est ni une suppression, ni un archivage de l’affaire, ni une sanction disciplinaire, ni une décision Go/No-Go, ni une réallocation automatique. Elle retire définitivement une autorisation opérationnelle précise dans l’historique de l’affaire.

| Inclus | Explicitement exclu |
|---|---|
| Transition patron `ACTIVE → ENDED` ou `SUSPENDED → ENDED`. | Réactivation d’une affectation terminée, suppression, archivage, expiration automatique ou réaffectation. |
| Motif fermé, révision optimiste, idempotence, journal, événement, outbox et receipt. | Motif libre, note RH, notification, tâche, mail, calcul d’impact ou décision automatique. |
| Route HTTP patron et réponse fermée. | Changement de scope, cible, Case, auteur, fenêtre, données financières ou historiques collaborateur. |
| Neutre vis-à-vis d’une Case déjà arrêtée ou d’une cible devenue inactive. | Cockpit patron, export du journal ou lecture publique des raisons. |

## 2. Commande fermée

La commande stable est `EndCaseAssignment`. Elle emploie l’enveloppe V8 et refuse tout champ inconnu.

| Champ | Règle |
|---|---|
| `command_id` | UUID de la tentative métier. |
| `idempotency_key` | UUID évalué dans `(tenant_id, actor_id, command_type, idempotency_key)`. |
| `correlation_id?` | UUID facultatif de corrélation, sans autorité métier. |
| `assignment_id` | UUID de l’affectation, fourni uniquement par le chemin HTTP. |
| `expected_revision` | Entier supérieur ou égal à zéro, identique à la révision courante verrouillée. |
| `end_reason_code` | Enum fermé : `PATRON_ENDED`, `CASE_STOPPED`, `CASE_ARCHIVED`, `COLLABORATOR_UNAVAILABLE`, `MEMBERSHIP_REVOKED`. |

Le navigateur ne fournit jamais tenant, membership, rôle, capability, état, scope, classifications, Case, cible, dates, horodatage effectif, texte libre, données RH, prix, marge, décision, audit ni instruction de notification.

## 3. Autorisation, neutralité et audit

Le bearer réel SEC-01 résout l’acteur. Il doit être `PATRON_ADMIN`, membre actif du tenant et titulaire de `assignment.manage`. Les acteurs `SYSTEM`, `COLLABORATEUR` et `PATRON_DELEGATE` sont interdits.

| Situation | Réponse HTTP publique | Effet durable |
|---|---|---|
| Bearer absent, invalide ou révoqué | `401` | Aucun effet métier. |
| Affectation absente ou hors tenant | `404 NOT_FOUND_OR_FORBIDDEN` | Audit minimal de refus, sans existence révélée. |
| Acteur non patron ou capability insuffisante | `403 FORBIDDEN` | Audit `AUTHZ_DENIED`, action `assignment.manage`. |
| Rejeu divergent, commande en cours ou révision obsolète | `409` | Aucune mutation. |
| État déjà `ENDED`/`EXPIRED` ou motif invalide | `422 COMMAND_REJECTED` ou validation FastAPI | Aucun journal, événement ou outbox métier. |
| Fin initiale autorisée | `201` | Mutation atomique irréversible. |
| Rejeu strictement identique | `200` | Receipt existant, sans seconde écriture. |

La résolution est tenant-scopée avant policy. Tout refus de rôle est audité avant dispatch. Une affectation étrangère reste indistinguable d’une ressource inexistante.

## 4. Transitions et invariants

Les seules transitions admises sont :

```text
ACTIVE    --EndCaseAssignment--> ENDED
SUSPENDED --EndCaseAssignment--> ENDED
```

Les invariants suivants sont non négociables :

1. L’affectation est verrouillée avant le contrôle de `expected_revision`.
2. Seuls `ACTIVE` et `SUSPENDED` sont terminables. `ENDED` et `EXPIRED` sont rejetés ; aucune future frontière ne pourra les réactiver.
3. La fin est admise même si la Case n’est plus active, la cible n’est plus active ou la fenêtre est passée : elle sert précisément à fermer durablement une autorisation résiduelle.
4. La mutation met à jour exclusivement `state`, `ended_at` avec l’instant serveur et `aggregate_revision`, qui progresse exactement de un.
5. `case_id`, cible, auteur initial, `granted_at`, fenêtre, scope et classifications ne changent jamais.
6. La fin ne modifie ni ne crée d’historique collaborateur et ne déclenche aucune action au nom du collaborateur.
7. L’unicité ouverte `(tenant_id, membership_id, case_id)` sur `ACTIVE|SUSPENDED` est libérée après commit ; une future création demeure néanmoins une nouvelle affectation et ne réécrit jamais celle terminée.

## 5. Transaction, journal, événement, migration et receipt

Dans une transaction unique, le handler verrouille l’affectation tenant-scopée, vérifie état et révision, passe à `ENDED`, renseigne `ended_at` avec l’horloge serveur, incrémente la révision, persiste le journal, l’événement/outbox via le dispatcher et le receipt idempotent.

| Élément | Valeur obligatoire |
|---|---|
| Journal | `case_assignment_change_events`, `event_type = ASSIGNMENT_ENDED`. |
| Révisions | `previous_revision = n`, `resulting_revision = n + 1`. |
| États journalisés | `previous_state = ACTIVE|SUSPENDED`, `resulting_state = ENDED`. |
| Horodatage agrégat | `ended_at = context.received_at`, obligatoire pour l’état `ENDED`. |
| Motif | `end_reason_code` fermé, sans commentaire libre. |
| Scope journalisé | Copies identiques des manifests précédents et résultants. |
| Événement | `CaseAssignmentEnded`, IDs minimaux, révisions, état précédent et motif fermé. |
| Receipt | `CASE_ASSIGNMENT_ENDED`, `201` initial ou `200` au rejeu strict. |

Aucune migration additive n’est nécessaire : `20260814_0021` couvre déjà `ASSIGNMENT_ENDED` et les cinq motifs fermés de fin, tandis que `20260814_0023` reste la tête Alembic. Le trigger PostgreSQL existant empêche tout `UPDATE` ou `DELETE` du journal. Le cycle obligatoire reste `upgrade head`, `alembic check`, `downgrade base` sur un jeu compatible avec les downgrades protégés antérieurs.

## 6. Contrat HTTP et OpenAPI

La route implémentée est :

```text
POST /api/v1/patron/assignments/{assignment_id}/end
```

Le corps fermé contient seulement `command_id`, `idempotency_key`, `correlation_id?`, `expected_revision` et `end_reason_code`. Le résultat est `AssignmentCommandResponse`, sans tenant, cible, scope, classifications, auteur, dates, motif, audit, stockage, finance, décision ou dépôt.

Le snapshot OpenAPI contient désormais neuf opérations Assignment/patron et déclare les statuts `201`, `200`, `401`, `403`, `404`, `409` et `422`. La route n’est annoncée comme disponible qu’après export depuis la composition FastAPI réelle et validation de sa suite de tests.

## 7. Matrice de fermeture

| Domaine | Cas obligatoires |
|---|---|
| Pydantic | Cinq motifs admis, motif inconnu, révision négative, UUID invalide et champ supplémentaire. |
| PostgreSQL | Fin depuis actif et suspendu, révision +1, conservation scope/fenêtre, journal, événement/outbox, rejeu, état terminé/expiré, conflit de révision et trigger append-only. |
| Sécurité | Patron autorisé, collaborateur refusé et audité, ressource étrangère neutre, bearer absent. |
| HTTP | `201`, `200` au rejeu, `403`, `404`, `409`, `422`, DTO fermé et absence de fuite. |
| Alembic | Tête `0023`, absence de migration de table supplémentaire, `check` sans dérive et rollback contrôlé. |
| Performance | Le benchmark insère et relit 1 000 journaux `ASSIGNMENT_ENDED` réels sous les budgets locaux ; ce n’est pas une promesse de capacité VPS. |

La publication du slice exige Ruff, tests Pydantic/PostgreSQL/API, benchmark, cycle Alembic, scan de secrets, `git diff --check`, OpenAPI régénérée et CI GitHub verte.
