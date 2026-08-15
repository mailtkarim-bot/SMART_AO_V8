# SMART_AO V8 — PATRON-ASSIGNMENT-READ-01 — Contrat normatif

**Statut : publié par `6df4c55`, CI `31855776751` verte.**

Ce contrat ouvre la première lecture patron des affectations collaborateur et de leur journal de gestion append-only. Il succède à `PATRON-ASSIGNMENT-END-01` et n’ajoute aucune commande, aucune mutation, aucune décision, aucun chiffrage, aucune notification et aucune automatisation métier.

## 1. Finalité métier et frontière

Le patron dispose d’une vue de direction pour savoir quelles affectations opérationnelles existent sur les affaires de son entreprise, dans quel état elles se trouvent et quelles décisions patron les ont modifiées. Le résultat aide à contrôler les habilitations de préparation d’un DCE ; il ne remplace ni le futur cockpit global, ni la gestion des prix, ni une fiche RH du collaborateur.

> Cette frontière lit des faits d’autorité déjà durables. Elle ne produit ni une recommandation, ni une alerte, ni une priorisation, ni une décision automatique.

| Inclus | Explicitement exclu |
|---|---|
| Liste tenant-scopée et bornée des affectations, avec état, fenêtre, scope opérationnel et révision. | Prix, marge, devis, trésorerie, décision Go/No-Go, dépôt, document DCE, données de stockage ou hash. |
| Lecture bornée du journal patron `case_assignment_change_events`. | Écriture, modification ou suppression du journal, de l’affectation ou des interactions collaborateur. |
| Motifs fermés, transitions et manifests de scope nécessaires à l’explication des changements d’autorité. | Texte libre d’accusé, question, indisponibilité, note, raison détaillée, auteur/membership, commande, corrélation ou audit de sécurité. |
| Bearer réel, `PATRON_ADMIN`, `assignment.manage`, policy auditée et neutralité inter-tenant. | Délégation, accès collaborateur, export, recherche globale, statistiques, pagination cursive ou cockpit global CP-01 à CP-08. |

## 2. Routes HTTP fermées

Les deux routes de lecture sont exclusivement patron :

```text
GET /api/v1/patron/assignments?case_id={uuid?}&state={ACTIVE|SUSPENDED|ENDED|EXPIRED?}&limit={1..200}
GET /api/v1/patron/assignments/{assignment_id}/journal?limit={1..200}
```

| Route | Paramètres acceptés | Résultat fermé |
|---|---|---|
| Liste | `case_id?`, `state?`, `limit` (défaut 100, `1..200`). | `PatronAssignmentCockpitListResponse`, avec zéro à `limit` lignes tenant-scopées. |
| Journal | `assignment_id` de chemin, `limit` (défaut 100, `1..200`). | `PatronAssignmentJournalResponse`, avec une seule affectation et zéro à `limit` faits patron. |

Aucun corps n’est admis. Le client ne fournit jamais tenant, auteur, rôle, capability, scope, Case effective, identité cible, dates effectives, état, motif, commande, corrélation, audit ou filtre libre.

## 3. Projection de liste

Chaque ligne `PatronAssignmentCockpitItem` contient uniquement :

| Champ | Règle |
|---|---|
| `assignment_id`, `case_id` | Références fonctionnelles UUID de l’affectation et de l’affaire. |
| `case_title`, `case_lifecycle` | Libellé opérationnel et cycle de vie de l’affaire. |
| `state`, `aggregate_revision` | État actuel et révision de l’affectation. |
| `starts_at`, `ends_at`, `ended_at` | Fenêtre et date de fin factuelles, sans dériver une disponibilité. |
| `scope_actions`, `scope_classifications` | Manifest opérationnel fermé actuellement appliqué. |

La liste est triée de manière déterministe par `case_title ASC`, puis `assignment_id ASC`. Le `limit` borne le résultat SQL. Une liste vide est un succès `200`, jamais une erreur ni un zéro artificiel de cockpit global.

## 4. Projection du journal patron

La réponse de journal réutilise l’en-tête fermé de l’affectation, puis expose uniquement les changements d’autorité patron.

| Champ d’un item | Règle |
|---|---|
| `record_id`, `recorded_at` | Identifiant de fait et horodatage durable. |
| `event_type` | `ASSIGNMENT_CREATED`, `ASSIGNMENT_SCOPE_AMENDED`, `ASSIGNMENT_SUSPENDED`, `ASSIGNMENT_REACTIVATED` ou `ASSIGNMENT_ENDED`. |
| `previous_revision`, `resulting_revision` | Révisions d’autorité factuelles ; `previous_revision` vaut `null` seulement à la création. |
| `previous_state`, `resulting_state` | Transition durable, sans interprétation métier supplémentaire. |
| `reason_code` | Motif fermé ou `null`, jamais une raison rédigée en texte libre. |
| Manifests de scope | Scopes précédents/résultants nécessaires à la lecture d’un amendement ou d’une transition, jamais un scope calculé par le navigateur. |

Les lignes du journal sont lues par `created_at DESC`, puis `id ASC`, et coupées à `limit` directement en base. Sont délibérément exclus : `tenant_id`, `case_id`, cible, auteur, `command_id`, `correlation_id`, clés de déduplication, audit, logs techniques, texte libre et données financières.

## 5. Autorisation, neutralité et audit

L’acteur provient exclusivement du bearer SEC-01. Il doit être `PATRON_ADMIN`, disposer d’une membership active et de `assignment.manage`. `SYSTEM`, `COLLABORATEUR` et `PATRON_DELEGATE` sont refusés.

| Situation | Réponse publique | Effet durable |
|---|---|---|
| Bearer absent, invalide ou révoqué | `401` | Aucune lecture. |
| Acteur non patron, membership absente ou capability insuffisante | `403 FORBIDDEN` | Refus `AUTHZ_DENIED` audité, action `assignment.manage`. |
| Affectation de journal absente ou hors tenant | `404 NOT_FOUND_OR_FORBIDDEN` | Refus minimal audité, sans révélation d’existence. |
| `limit`, UUID ou état de filtre invalide | `422` | Validation FastAPI, aucune lecture métier. |
| Liste filtrée vide | `200` avec `items = []` | Aucun audit de refus. |
| Lecture admise | `200` | Projection fermée seulement. |

Pour la liste, l’autorisation porte sur la ressource tenant-scopée `ASSIGNMENT_COCKPIT` d’identifiant `tenant_id`. Pour un journal, la recherche tenant-scopée précède la policy ; celle-ci porte sur `CASE_ASSIGNMENT_JOURNAL` et la Case propriétaire. Aucun chemin ne permet de transformer l’identifiant d’une affectation d’un autre tenant en information exploitable.

## 6. Transaction, persistance et migration

Cette frontière est strictement en lecture : elle n’ouvre aucune transaction d’écriture, ne déclenche aucun événement/outbox et ne crée aucun receipt. Les lecteurs SQLAlchemy sélectionnent explicitement les colonnes autorisées et joignent la Case uniquement par FK composite tenant-scopée.

Aucune migration Alembic n’est nécessaire. Les tables `case_assignments` et `case_assignment_change_events` ainsi que leurs index et triggers append-only publiés par `20260814_0021` restent la source de vérité.

## 7. Contrat OpenAPI attendu

Après implémentation, l’OpenAPI Assignment/patron passe de neuf à **onze opérations**. Les deux opérations `GET` doivent annoncer exclusivement `200`, `401`, `403`, `404` pour le journal et `422` pour la validation de paramètres, sans schéma révélant audit, finance, identité d’auteur ou stockage.

## 8. Matrice de fermeture

| Domaine | Cas obligatoires |
|---|---|
| Query | Liste tenant-scopée, filtre Case, filtre état, ordre déterministe, limite SQL ; journal tenant-scopé, ordre déterministe et borne. |
| Sécurité | Patron admis ; collaborateur refusé/audité ; resource étrangère neutre ; bearer absent. |
| HTTP | Liste `200` et vide ; journal `200`, `401`, `403`, `404`, `422`; DTO fermé et paramètres invalides. |
| Confidentialité | Absence de finance, prix, marge, devis, documents, clés, hash, audit, texte libre, auteur, membership, commande et corrélation. |
| Alembic | `upgrade head`, `alembic check`, `downgrade base`, sans migration nouvelle. |
| OpenAPI | Snapshot régénéré à onze opérations et registre Markdown détaillé. |

Le slice est publié après Ruff, tests query/API PostgreSQL, suite backend complète, cycle Alembic, scan de secrets, `git diff --check`, OpenAPI régénérée et CI GitHub verte.
