# SMART_AO V8 — PATRON-ASSIGNMENT-INTERACTION-VALIDATION-01 — Contrat normatif

**Statut : FIGÉ avant code.**

Cette frontière autorise le patron à enregistrer qu’il a pris en compte une interaction collaborateur déjà durable. Elle ne constitue ni une réponse au collaborateur, ni une décision Go/No-Go, ni une validation de prix, ni une approbation de contenu DCE, ni une modification de l’affectation.

## 1. Finalité métier et limite de décision

Après lecture d’un accusé de réception, d’une demande de clarification ou d’une indisponibilité, le patron peut faire passer ce signal dans son propre journal de suivi par un acte explicite et traçable. Le résultat est une **validation de prise en compte patron**, et non une résolution métier de la demande.

> « Validée » signifie exclusivement : « le patron a constaté ce signal ». Le système ne prétend pas que la clarification est répondue, que l’indisponibilité est réglée, que le travail est accepté ou qu’une décision est prise.

| Inclus | Explicitement exclu |
|---|---|
| Un fait append-only patron lié à une interaction source existante et du même tenant. | Réponse, commentaire, note, message, question, texte libre, délégation, notification ou tâche automatique. |
| Validation fermée d’un accusé, d’une clarification ou d’une indisponibilité. | Changement de l’état source, de l’affectation, de son scope, de sa révision, de sa fenêtre, de la Case ou d’un prix. |
| Idempotence, audit, événement/outbox, receipt fermé et trace de prise en compte. | Décision Go/No-Go, approbation de chiffrage, validation financière, dépôt ou action au nom du collaborateur. |

## 2. Commande fermée et correspondance obligatoire

La commande stable est `ValidateAssignmentInteraction`. Elle hérite de l’enveloppe V8, interdit les champs inconnus et n’accepte aucun texte libre.

| Champ | Règle |
|---|---|
| `command_id` | UUID de l’intention patron. |
| `idempotency_key` | UUID évalué dans `(tenant_id, actor_id, command_type, idempotency_key)`. |
| `correlation_id?` | UUID de corrélation facultatif, sans autorité métier. |
| `assignment_id` | UUID résolu exclusivement depuis le chemin HTTP. |
| `interaction_id` | UUID de l’interaction source, résolu dans le tenant et l’affectation. |
| `interaction_kind` | `ACKNOWLEDGEMENT`, `CLARIFICATION_REQUEST` ou `UNAVAILABILITY_REPORT`. |
| `validation_code` | Code fermé cohérent avec le type source. |

Les seules paires admises sont :

| `interaction_kind` | `validation_code` |
|---|---|
| `ACKNOWLEDGEMENT` | `ACKNOWLEDGEMENT_NOTED` |
| `CLARIFICATION_REQUEST` | `CLARIFICATION_NOTED` |
| `UNAVAILABILITY_REPORT` | `UNAVAILABILITY_NOTED` |

Le navigateur ne fournit jamais tenant, membership, rôle, capability, Case effective, auteur source, cible, état, révision, scope, fenêtre, date effective, prix, marge, texte libre, décision, audit ou instruction de notification.

## 3. Route HTTP et réponse publique

```text
POST /api/v1/patron/assignments/{assignment_id}/interaction-validations
```

Le corps contient seulement `command_id`, `idempotency_key`, `correlation_id?`, `interaction_id`, `interaction_kind` et `validation_code`. Le résultat est `AssignmentCommandResponse` : `INTERACTION_VALIDATED`, `201` lors de la première écriture ou `200` lors du rejeu strict. Le receipt n’expose ni le code de validation, ni le type/ID source, ni l’auteur, ni le patron, ni un texte libre.

## 4. Autorisation, résolution et invariants

Le bearer SEC-01 résout l’acteur. Il doit être `PATRON_ADMIN`, disposer d’une membership active et de `assignment.manage`. Les collaborateurs, délégués patron et systèmes sont refusés. La recherche source est tenant-scopée avant la policy.

| Situation | Réponse publique | Effet durable |
|---|---|---|
| Bearer absent, invalide ou révoqué | `401` | Aucun effet. |
| Rôle/capability insuffisant | `403 FORBIDDEN` | `AUTHZ_DENIED` audité. |
| Affectation ou interaction absente, étrangère ou de type incohérent | `404 NOT_FOUND_OR_FORBIDDEN` | Refus minimal audité, sans existence révélée. |
| Paires type/code invalides ou UUID mal formé | `422` | Validation Pydantic/FastAPI, aucune écriture. |
| Interaction déjà validée par une autre commande | `422 INTERACTION_ALREADY_VALIDATED` | Aucun second fait. |
| Rejeu strict de la même commande | `200` | Receipt existant, aucune seconde écriture. |
| Validation initiale autorisée | `201` | Un fait patron append-only, événement, outbox et receipt. |

La validation est admise même lorsque l’affectation est suspendue, terminée, expirée, hors fenêtre, lorsque la Case est arrêtée ou que la cible est inactive : elle lit un signal historique et ne rend aucun accès. Les registres source restent inchangés.

## 5. Persistance append-only et migration `0024`

La migration additive `20260815_0024` crée `assignment_interaction_patron_validations` avec les colonnes : `id`, `tenant_id`, `assignment_id`, `case_id`, `interaction_id`, `interaction_kind`, `validation_code`, `patron_membership_id`, `command_id`, `correlation_id`, timestamps. Elle porte :

1. des FKs composites vers tenant, affectation, Case et membership patron ;
2. un check fermé sur les trois types, les trois codes et leur correspondance ;
3. l’unicité `(tenant_id, interaction_kind, interaction_id)` ;
4. l’unicité `(tenant_id, id)` ;
5. un index `(tenant_id, assignment_id, created_at)` ;
6. un trigger `BEFORE UPDATE OR DELETE` utilisant la fonction append-only déjà publiée par `0020`.

Une FK SQL unique vers `interaction_id` n’est pas possible, car la source est l’une de trois tables hétérogènes. Le handler verrouille l’affectation et vérifie le type, le tenant et l’appartenance de la source à cette affectation avant tout insert. Cette vérification applicative est donc une invariance non négociable, testée sur chaque type et en inter-tenant.

## 6. Handler, événement et audit

Dans une transaction, le handler verrouille l’affectation tenant-scopée, résout l’interaction du type annoncé, vérifie la paire de validation, vérifie l’absence de validation existante, écrit le registre et produit `AssignmentInteractionValidated`. L’événement/outbox ne contient que les IDs de validation, d’affectation, de Case, le type et le code fermé ; aucun texte libre ni identité source n’est propagé.

L’acteur patron, les commandes et corrélations restent dans le registre/audit, hors projections publiques. La policy utilise la ressource `CASE_ASSIGNMENT_INTERACTION_VALIDATION`, classification `INTERNAL_OPERATIONAL`, Case résolue et action `assignment.manage`.

## 7. OpenAPI et matrice de fermeture

Après implémentation, le snapshot Assignment/patron passe de douze à **treize opérations**. La route annonce `201`, `200`, `401`, `403`, `404`, `409` et `422` ; le `409` reste réservé aux règles génériques du dispatcher d’idempotence concurrente, sans révéler l’interaction.

| Domaine | Cas obligatoires |
|---|---|
| Pydantic | Paires type/code admises, mismatch, UUID invalides, champ supplémentaire. |
| PostgreSQL | Une validation de chaque type, unicité source, trigger append-only, migration/downgrade. |
| Sécurité | Patron admis ; collaborateur/délégué refusés et audités ; source/affectation inter-tenant neutre. |
| Idempotence | Première écriture `201`, rejeu strict `200`, clé divergente `409`, interaction déjà validée `422`. |
| Confidentialité | Receipt et erreur sans texte libre, auteur, cible, membership, source, finance, audit ni stockage. |
| OpenAPI | Snapshot à treize opérations et documentation détaillée de la route. |

La publication exige Ruff, tests Pydantic/PostgreSQL/API, cycle Alembic, scan de secrets, `git diff --check`, OpenAPI régénérée et CI GitHub verte.
