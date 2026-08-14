# SMART_AO V8 — Spécification technique et plan SQL
## `PATRON-ASSIGNMENT-MANAGEMENT-01` — incrément 1 : création d’affectation

**Statut : FIGÉ avant implémentation.**

Ce document raffine le contrat normatif `SMART_AO_V8_PATRON_ASSIGNMENT_MANAGEMENT_01_CONTRAT.md` pour le premier incrément exécutable. Cet incrément livre seulement la création patron d’une affectation, les contrats Pydantic de création et d’amendement de scope, le journal append-only requis par ces commandes et les tests PostgreSQL. La mutation `AmendCaseAssignmentScope` est validée par schéma dans l’incrément 1, mais son handler est reporté à l’incrément 2.

## 1. Frontière exacte de l’incrément 1

| Livré | Reporté explicitement |
|---|---|
| `CreateCaseAssignmentCommand` fermé et handler transactionnel. | Handler `AmendCaseAssignmentScope`. |
| `AmendCaseAssignmentScopeCommand` fermé et testé en validation pure. | Suspension, réactivation et fin. |
| Capability patron `assignment.manage`. | Routes HTTP, DTO de réponse, cockpit et projections patron. |
| Migration `20260814_0021`, table append-only `case_assignment_change_events`, index d’unicité renforcé. | Lecture patron du journal et pagination. |
| Événement `CaseAssignmentCreated`, outbox et receipt idempotent. | Notifications, tâches, réaffectation automatique et réponse aux clarifications. |

> Aucun acteur système ne peut créer une affectation humaine. Le handler ne crée ni tâche, ni échéance, ni décision, ni document, ni prix, ni marge, ni donnée de dépôt.

## 2. Contrats Pydantic du premier incrément

Les deux schémas vivent dans `backend/app/modules/dce/application/commands.py`, héritent de `ApplicationCommand` et conservent donc `extra="forbid"`, `str_strip_whitespace=True`, `command_id`, `idempotency_key` et `correlation_id?`.

### 2.1 `CreateCaseAssignmentCommand`

| Champ | Type et validation | Autorité |
|---|---|---|
| `assignment_id` | UUID non nul | Identifiant d’affectation choisi par le client, unique dans le tenant. |
| `case_id` | UUID non nul | Résolu tenant-scopé et verrouillé par le handler. |
| `target_membership_id` | UUID non nul | Résolu tenant-scopé et vérifié `COLLABORATEUR` / `ACTIVE`. |
| `expected_case_revision` | entier `>= 0` | Doit être égal à `CaseRecord.aggregate_revision` sous verrou. |
| `scope_actions` | liste de 1 à 8 chaînes | Dédupliquée ; valeurs strictement dans le catalogue fermé. |
| `scope_classifications` | liste de 1 chaîne | Valeur unique `INTERNAL_OPERATIONAL`. |
| `starts_at` | datetime timezone-aware | Doit être `<= received_at` pour l’incrément 1. |
| `ends_at` | datetime timezone-aware optionnel | Si présent, doit être strictement postérieur à `starts_at`. |

Une affectation créée avec un démarrage futur reste `ACTIVE`, conformément au contrat normatif. Elle est néanmoins inutilisable par le collaborateur avant `starts_at`, car les frontières collaborateur contrôlent déjà la fenêtre d’accès à l’exécution. La création ne réécrit jamais cette fenêtre après son commit.

### 2.2 `AmendCaseAssignmentScopeCommand`

| Champ | Type et validation | Effet dans l’incrément 1 |
|---|---|---|
| `assignment_id` | UUID non nul | Contrat validé ; handler reporté. |
| `expected_revision` | entier `>= 0` | Contrat validé ; handler reporté. |
| `scope_actions` | liste de 1 à 8 chaînes | Même catalogue fermé et déduplication que la création. |
| `scope_classifications` | liste de 1 chaîne | Même classification fermée que la création. |

Les commandes ne transportent jamais `tenant_id`, `actor_id`, `membership_id` patron, rôle, capability, `granted_at`, état, révision cible, Case calculée, texte de justification ni prix. Ces valeurs sont toutes résolues ou générées par le serveur.

## 3. Service d’autorisation et handler transactionnel

### 3.1 Ordre d’exécution de `CreateCaseAssignment`

1. Le service public vérifie que l’acteur est `PATRON_ADMIN`, possède une membership active et la capability `assignment.manage`. Les échecs avant policy sont audités `AUTHZ_DENIED` avec un motif fermé.
2. Le service résout la Case uniquement par `(tenant_id, case_id)`. Une Case étrangère ou absente reste `NOT_FOUND_OR_FORBIDDEN`.
3. `AuditedAuthorizationPolicy` autorise `assignment.manage` sur la ressource `CASE`, classification `INTERNAL_OPERATIONAL`, avec la Case concernée. Le patron n’est pas soumis au scope collaborateur.
4. Le dispatcher réserve ou rejoue le receipt tenant/acteur/type/clé puis appelle le handler dans la transaction unique.
5. Le handler verrouille la Case (`FOR UPDATE`) et compare `aggregate_revision` à `expected_case_revision`. Une Case non `ACTIVE` ou une révision différente est refusée avant toute écriture.
6. Le handler verrouille la membership cible dans le tenant et exige `role='COLLABORATEUR'`, `state='ACTIVE'`.
7. Le handler vérifie, sous verrou, qu’aucune affectation `ACTIVE` ou `SUSPENDED` ne relie déjà cette cible à cette Case. La contrainte partielle PostgreSQL est le filet final contre les courses.
8. Le handler persiste l’affectation `ACTIVE`, révision `0`, puis un événement patron `ASSIGNMENT_CREATED`, et retourne `CaseAssignmentCreated` au dispatcher.
9. Le dispatcher persiste l’événement de domaine, le message outbox et le receipt `SUCCEEDED` avant commit.

### 3.2 Erreurs fermées

| Code interne | Situation | Effet durable |
|---|---|---|
| `ASSIGNMENT_PATRON_REQUIRED` | Acteur non `PATRON_ADMIN`. | Audit de refus seulement. |
| `ASSIGNMENT_MEMBERSHIP_REQUIRED` | Contexte sans membership patron. | Audit de refus seulement. |
| `NOT_FOUND_OR_FORBIDDEN` | Case, membership cible ou affectation étrangère/non résoluble. | Audit de refus seulement. |
| `CASE_INACTIVE` | Case `STOPPED` ou `ARCHIVED`. | Aucune écriture métier. |
| `CASE_VERSION_CONFLICT` | `expected_case_revision` obsolète. | Aucune écriture métier. |
| `ASSIGNMENT_TARGET_NOT_COLLABORATOR` | Cible non collaborateur ou non active. | Aucune écriture métier. |
| `ASSIGNMENT_ALREADY_OPEN` | Affectation `ACTIVE` ou `SUSPENDED` existante pour cible/Case. | Aucune écriture métier. |
| `IDEMPOTENCY_KEY_REUSED` | Même clé, charge sémantiquement différente. | Aucune écriture nouvelle. |

## 4. Migration Alembic `20260814_0021`

### 4.1 Principe

La migration est additive pour les données et ne modifie aucune ligne existante. Elle crée le journal patron, remplace uniquement l’index partiel d’unicité de l’affectation par une version plus stricte et installe un trigger d’immutabilité propre au nouveau journal.

| Révision | Fichier prévu | Dépendance |
|---|---|---|
| `20260814_0021` | `backend/alembic/versions/20260814_0021_patron_assignment_management.py` | `20260814_0020` |

### 4.2 Plan SQL d’upgrade

L’implémentation Alembic doit produire l’équivalent PostgreSQL suivant. Les noms de contraintes sont normatifs afin de maintenir la lisibilité des échecs et la stabilité d’Alembic.

```sql
DROP INDEX ux_assignments__active_member_case;

CREATE UNIQUE INDEX ux_assignments__open_member_case
    ON case_assignments (tenant_id, membership_id, case_id)
    WHERE state IN ('ACTIVE', 'SUSPENDED');

CREATE TABLE case_assignment_change_events (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    assignment_id UUID NOT NULL,
    case_id UUID NOT NULL,
    target_membership_id UUID NOT NULL,
    author_membership_id UUID NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    previous_revision INTEGER NULL,
    resulting_revision INTEGER NOT NULL,
    previous_state VARCHAR(16) NULL,
    resulting_state VARCHAR(16) NOT NULL,
    reason_code VARCHAR(40) NULL,
    previous_scope_actions_json JSONB NULL,
    previous_scope_classifications_json JSONB NULL,
    resulting_scope_actions_json JSONB NOT NULL,
    resulting_scope_classifications_json JSONB NOT NULL,
    command_id UUID NOT NULL,
    correlation_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_assignment_change__tenant FOREIGN KEY (tenant_id)
        REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_assignment_change__assignment FOREIGN KEY (tenant_id, assignment_id)
        REFERENCES case_assignments(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_assignment_change__case FOREIGN KEY (tenant_id, case_id)
        REFERENCES cases(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_assignment_change__target_membership FOREIGN KEY (tenant_id, target_membership_id)
        REFERENCES tenant_memberships(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_assignment_change__author_membership FOREIGN KEY (tenant_id, author_membership_id)
        REFERENCES tenant_memberships(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT uq_assignment_change__tenant_id UNIQUE (tenant_id, id),
    CONSTRAINT ck_assignment_change__event_type CHECK (
        event_type IN ('ASSIGNMENT_CREATED', 'ASSIGNMENT_SCOPE_AMENDED',
                       'ASSIGNMENT_SUSPENDED', 'ASSIGNMENT_REACTIVATED',
                       'ASSIGNMENT_ENDED')
    ),
    CONSTRAINT ck_assignment_change__revision CHECK (
        resulting_revision >= 0
        AND (previous_revision IS NULL OR previous_revision >= 0)
        AND (
            (event_type = 'ASSIGNMENT_CREATED' AND previous_revision IS NULL
             AND resulting_revision = 0)
            OR
            (event_type <> 'ASSIGNMENT_CREATED' AND previous_revision IS NOT NULL
             AND resulting_revision = previous_revision + 1)
        )
    ),
    CONSTRAINT ck_assignment_change__state CHECK (
        previous_state IS NULL OR previous_state IN ('ACTIVE', 'SUSPENDED', 'ENDED', 'EXPIRED')
        AND resulting_state IN ('ACTIVE', 'SUSPENDED', 'ENDED', 'EXPIRED')
    ),
    CONSTRAINT ck_assignment_change__scope_result CHECK (
        jsonb_typeof(resulting_scope_actions_json) = 'array'
        AND jsonb_array_length(resulting_scope_actions_json) > 0
        AND jsonb_typeof(resulting_scope_classifications_json) = 'array'
        AND jsonb_array_length(resulting_scope_classifications_json) > 0
    ),
    CONSTRAINT ck_assignment_change__scope_previous CHECK (
        (previous_scope_actions_json IS NULL AND previous_scope_classifications_json IS NULL)
        OR (
            jsonb_typeof(previous_scope_actions_json) = 'array'
            AND jsonb_array_length(previous_scope_actions_json) > 0
            AND jsonb_typeof(previous_scope_classifications_json) = 'array'
            AND jsonb_array_length(previous_scope_classifications_json) > 0
        )
    ),
    CONSTRAINT ck_assignment_change__reason CHECK (
        reason_code IS NULL OR reason_code IN (
            'PATRON_SUSPENDED', 'WORKLOAD_REALLOCATION', 'CASE_PAUSED', 'ACCESS_REVIEW',
            'PATRON_ENDED', 'CASE_STOPPED', 'CASE_ARCHIVED',
            'COLLABORATOR_UNAVAILABLE', 'MEMBERSHIP_REVOKED'
        )
    )
);

CREATE INDEX ix_assignment_change__tenant_assignment
    ON case_assignment_change_events (tenant_id, assignment_id, created_at);
CREATE INDEX ix_assignment_change__tenant_case_target
    ON case_assignment_change_events (tenant_id, case_id, target_membership_id, created_at);

CREATE FUNCTION prevent_case_assignment_change_event_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'CASE_ASSIGNMENT_CHANGE_EVENT_APPEND_ONLY';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_case_assignment_change_events_append_only
BEFORE UPDATE OR DELETE ON case_assignment_change_events
FOR EACH ROW EXECUTE FUNCTION prevent_case_assignment_change_event_mutation();
```

La migration Alembic utilise `postgresql.JSONB`, `_timestamps()` et les FKs composites de la migration `0020`. Elle doit créer les index secondaires explicites sur `tenant_id` afin de rester compatible avec les conventions d’indexation du dépôt.

### 4.3 Plan de downgrade

Le rollback applique l’ordre exact suivant : suppression du trigger, suppression de la fonction, suppression des index du journal, suppression de `case_assignment_change_events`, suppression de `ux_assignments__open_member_case`, puis recréation de `ux_assignments__active_member_case`. Aucun historique collaborateur, audit, outbox, receipt ou Case n’est touché.

## 5. Modèle ORM et journal de changement

`CaseAssignmentChangeEventRecord` est ajouté dans `app.platform.security.models`. Il hérite de `TenantScopedRecord` et reproduit toutes les colonnes, checks et FKs de la migration. Ses listes JSONB ne sont jamais exposées dans une projection collaborateur. L’ORM n’essaie pas de protéger seul l’append-only : la protection effective est le trigger PostgreSQL.

Pour une création, le journal contient :

| Champ | Valeur |
|---|---|
| `event_type` | `ASSIGNMENT_CREATED` |
| `previous_revision` / `previous_state` | `NULL` |
| `resulting_revision` / `resulting_state` | `0` / `ACTIVE` |
| Scopes précédents | `NULL` |
| Scopes résultants | Les listes canoniques validées de la commande. |
| `author_membership_id` | Membership patron résolue depuis le bearer. |
| `target_membership_id` | Collaborateur cible contrôlé par le handler. |
| `command_id`, `correlation_id` | Enveloppe de commande, jamais exposée dans une projection collaborateur. |

## 6. Tests PostgreSQL obligatoires de l’incrément 1

Le harnais est créé dans `backend/tests/application/test_patron_assignment_management.py`. Il exécute les migrations réelles vers `head`, utilise une transaction de seed par test et revient à `base` en fin de module.

| Test | Preuve attendue |
|---|---|
| Création patron autorisée | Une affectation `ACTIVE` de révision `0`, un changement `ASSIGNMENT_CREATED`, un événement domaine, un outbox et un receipt. |
| Rejeu idempotent | Même résultat, `replayed=True`, une seule affectation, un seul changement, un seul événement et un seul outbox. |
| Révision Case obsolète | `CASE_VERSION_CONFLICT`, zéro affectation, zéro changement, zéro événement, zéro outbox. |
| Cible invalide | Patron, collaborateur suspendu ou tenant étranger refusés sans écriture métier. |
| Case invalide | Case `STOPPED`, `ARCHIVED` ou tenant étranger refusée sans écriture métier. |
| Unicité ouverte | Seconde création active pour même cible/Case refusée ; insertion SQL concurrente protégée par index partiel. |
| FKs tenant | Insertion SQL de journal avec Case, cible, auteur ou affectation cross-tenant rejetée. |
| Append-only | `UPDATE` et `DELETE` SQLAlchemy sur le journal déclenchent `CASE_ASSIGNMENT_CHANGE_EVENT_APPEND_ONLY`. |
| Atomicité | Exception après réservation du receipt ou violation de contrainte ne laisse aucun receipt `SUCCEEDED`, événement, outbox, affectation ou journal partiel. |
| Schémas Pydantic | Extra field, scope vide/doublon/inconnu/financier, classification invalide et fenêtre illégale sont refusés avant SQL. |

## 7. Critère de sortie de l’incrément 1

L’incrément est livrable seulement si la migration passe `upgrade head`, `alembic check`, `downgrade base`; si les contrats Pydantic sont fermés et testés; si les tests PostgreSQL démontrent l’append-only, le tenant P0, l’idempotence, l’atomicité et le conflit de révision; et si Ruff, `detect-secrets`, la suite backend, `git diff --check` et la CI GitHub sont verts.

## 8. Mesure locale du journal append-only

Le script reproductible `scripts/benchmark_assignment_change_journal.py` insère 1 000 événements `ASSIGNMENT_SCOPE_AMENDED` réels dans PostgreSQL puis relit les 100 derniers événements d’une affectation. Il ne simule ni la base, ni le trigger, ni les contraintes de clé étrangère.

| Mesure locale contrôlée | Résultat observé | Budget de test |
|---|---:|---:|
| 1 000 insertions append-only | 102,887 ms, soit 9 719,4 événements/s | moins de 5 000 ms |
| Lecture des 100 derniers événements | 13,223 ms | moins de 500 ms |

Le test PostgreSQL `test_assignment_change_journal_performance.py` applique ces budgets volontairement prudents. Ils constituent un garde-fou de régression dans cet environnement, et non une promesse de capacité pour un VPS client : la latence disque, la charge concurrente et le volume réel devront être mesurés lors du protocole de préproduction.
