# SMART_AO V8 — PATRON-ASSIGNMENT-INTERACTIONS-READ-01 — Contrat normatif

**Statut : implémenté localement, publication en attente de CI GitHub.**

Cette frontière permet au patron de lire les trois faits opérationnels produits par les collaborateurs sur une affectation : accusé de réception, demande de clarification et indisponibilité. Elle ne crée, ne répond, ne modifie et ne clôture aucune interaction ; elle ne calcule ni priorité, ni action patron, ni impact, ni réaffectation.

## 1. Finalité métier et frontière

Le patron doit pouvoir vérifier qu’un collaborateur a pris connaissance d’une affectation, identifier le type d’éclaircissement demandé et voir qu’une indisponibilité a été signalée, sans ouvrir une fiche RH, un espace de messagerie libre ou des données financières. La lecture s’inscrit dans le cockpit des affectations déjà publié et n’est pas un cockpit global.

> Le patron lit un signal opérationnel structuré. Il ne lit pas les messages libres du collaborateur et le système ne prend aucune décision à partir de ce signal.

| Inclus | Explicitement exclu |
|---|---|
| Registres append-only d’accusé, clarification et indisponibilité d’une affectation tenant-scopée. | Écriture, réponse patron, clôture de demande, changement de scope, réaffectation, tâche, notification ou Process Manager. |
| Types, dates, révisions, priorité/type de clarification et période/motif fermé d’indisponibilité. | Note d’accusé, sujet, question, scope demandé, raison, note d’impact ou tout autre texte libre. |
| Bearer réel, `PATRON_ADMIN`, `assignment.manage`, policy auditée, tri et limite déterministes. | Prix, marge, devis, trésorerie, documents DCE, identités, memberships, commandes, corrélation, audit ou logs techniques. |

## 2. Route HTTP fermée

```text
GET /api/v1/patron/assignments/{assignment_id}/interactions?kind={ACKNOWLEDGEMENT|CLARIFICATION_REQUEST|UNAVAILABILITY_REPORT?}&limit={1..200}
```

| Paramètre | Règle |
|---|---|
| `assignment_id` | UUID de chemin ; il ne confère aucune autorité et reste résolu dans le tenant du bearer. |
| `kind?` | Filtre fermé facultatif parmi les trois types d’interaction. |
| `limit` | Entier borné `1..200`, défaut `100`, appliqué à la lecture SQL finale. |

Le corps est absent. Le navigateur ne fournit jamais tenant, rôle, membership, identité, état de l’affectation, Case effective, dates, auteur, scope, texte libre, motif non fermé, commande, corrélation ni règle d’autorisation.

## 3. Projection publique fermée

La réponse `PatronAssignmentInteractionsResponse` contient un en-tête minimal `assignment_id`, `case_id`, `case_lifecycle`, puis `items`.

| Type `kind` | Champs autorisés |
|---|---|
| `ACKNOWLEDGEMENT` | `record_id`, `recorded_at`, `assignment_revision`, `operational_state = RECORDED`. |
| `CLARIFICATION_REQUEST` | `record_id`, `recorded_at`, `clarification_kind`, `priority`, `operational_state = OPEN`. |
| `UNAVAILABILITY_REPORT` | `record_id`, `recorded_at`, `assignment_revision`, `reason_kind`, `unavailable_from`, `unavailable_until`, `known_deadline_impact`, `operational_state = RECORDED`. |

Sont interdits dans toute réponse : `note`, `subject`, `question`, `requested_scope`, `reason`, `impact_note`, `tenant_id`, `actor_id`, `membership_id`, auteur, cible, `command_id`, `correlation_id`, clé fonctionnelle, audit, prix, marge, devis, hash, stockage, documents, décision, dépôt et tout champ futur non explicitement listé.

Les trois registres sont fusionnés, triés par `recorded_at DESC` puis `record_id ASC`, avant la coupe à `limit`. Une affectation connue sans interaction retourne `200` avec `items = []`.

## 4. Autorisation, neutralité et audit

La route est exclusivement patron. L’acteur est résolu depuis le bearer SEC-01 et doit être `PATRON_ADMIN`, disposer d’une membership active et de `assignment.manage`. Le collaborateur, le délégué patron et le système sont refusés ; les conditions d’activité actuelles de l’affectation, de la Case, de la cible et de la fenêtre ne sont pas exigées, car la lecture porte sur l’historique déjà durable.

| Situation | Réponse publique | Effet durable |
|---|---|---|
| Bearer absent, invalide ou révoqué | `401` | Aucune lecture. |
| Collaborateur standard ou rôle/capability insuffisant | `403 FORBIDDEN` | `AUTHZ_DENIED` audité avec `assignment.manage`. |
| Affectation absente ou d’un autre tenant | `404 NOT_FOUND_OR_FORBIDDEN` | Refus minimal audité, sans existence révélée. |
| UUID, type ou limite invalide | `422` | Validation FastAPI, aucune lecture métier. |
| Lecture patron admise | `200` | Projection fermée seulement, sans outbox, receipt ni mutation. |

La ressource policy est `CASE_ASSIGNMENT_INTERACTIONS`, tenant-scopée, avec `case_id` de l’affectation résolue. Une lecture inter-tenant ne devient jamais une erreur distinguable d’une absence.

## 5. Persistance, migration et OpenAPI

Le lecteur SQLAlchemy sélectionne explicitement les colonnes autorisées de `case_assignment_acknowledgements`, `assignment_clarification_requests` et `case_assignment_unavailabilities`. Aucune migration n’est nécessaire : les registres append-only, leurs index tenant/assignment/date et leurs triggers existent déjà.

Après implémentation, le snapshot OpenAPI Assignment/patron passe de onze à **douze opérations**. L’opération GET déclare `200`, `401`, `403`, `404` et `422`, sans schéma de texte libre, d’identité, d’audit ou de finance.

## 6. Matrice de fermeture

| Domaine | Cas obligatoires |
|---|---|
| Query | Trois types, filtre fermé, affectation sans interaction, tri global déterministe, borne SQL et lecture d’affectation terminée/inactive. |
| Sécurité | Patron autorisé ; collaborateur standard refusé/audité ; bearer absent ; affectation étrangère neutre. |
| HTTP | `200`, `401`, `403`, `404`, `422`, DTO strict et absence de champs interdits. |
| Persistance | Aucun UPDATE/DELETE/INSERT sur les trois registres pendant une lecture ; aucune migration nouvelle. |
| OpenAPI | Snapshot à douze opérations et registre Markdown détaillant paramètres, réponses et exclusions. |

Le slice est prêt à être publié après Ruff, tests API/PostgreSQL, suite backend complète, cycle Alembic, scan de secrets, `git diff --check` et OpenAPI régénérée. La CI GitHub verte reste la condition de clôture.
