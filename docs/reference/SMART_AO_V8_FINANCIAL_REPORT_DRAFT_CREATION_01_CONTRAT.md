# SMART_AO V8 — FINANCIAL-REPORT-DRAFT-CREATION-01

**Statut : FIGÉ avant code.**

## 1. Finalité métier

Cette frontière permet au **patron** d’ouvrir un brouillon de chiffrage pour une affaire (`Case`). Elle crée le contenant sécurisé d’un futur chiffrage ; elle ne saisit aucun prix, ne calcule aucune marge, ne propose aucun montant et ne prend aucune décision Go/No-Go.

Le brouillon est indispensable parce que la frontière déjà publiée `FINANCIAL-REPORT-PUBLICATION-01` sait publier un snapshot `DRAFT`, mais ne crée pas ce snapshot. Après ce slice, la chaîne financière devient cohérente : le patron ouvre un brouillon, les frontières suivantes y ajoutent des lignes et des totaux contrôlés, puis le patron le publie explicitement.

> Un brouillon financier ne doit jamais être visible, résolu ou déduit par un collaborateur. Le refus `403 FORBIDDEN` intervient avant toute lecture de la Case ou du snapshot.

## 2. Périmètre strict

| Inclus | Exclu explicitement |
|---|---|
| Création patron d’un snapshot `DRAFT` vide et tenant-scopé. | Saisie, import ou modification de montants. |
| Verrouillage de la Case, unicité du brouillon ouvert et idempotence. | Calcul automatique de prix, marge, trésorerie ou provision. |
| Receipt fermé, événement minimal et outbox transactionnelle. | Lecture ou écriture par un collaborateur, un délégué ou `SYSTEM`. |
| Devise et version de règles déclarées par le patron, sans données monétaires. | Go/No-Go, dépôt, document de réponse, Excel, fournisseur, devis ou note libre. |

## 3. Commande normalisée

```text
CreateFinancialReportDraftCommand
```

| Champ | Type | Règle |
|---|---|---|
| `command_id` | UUID | Identifiant technique client de la commande ; unique dans le tenant via le dispatcher. |
| `idempotency_key` | UUID | Rejeu strictement identique : receipt initial et HTTP `200`. |
| `correlation_id` | UUID nullable | Liaison technique optionnelle ; jamais exposée dans le receipt. |
| `case_id` | UUID | Résolu depuis le chemin ; la Case doit appartenir au tenant du patron. |
| `currency_code` | chaîne ISO 4217, 3 majuscules | Devise de travail déclarée à la création ; `EUR` est la valeur par défaut HTTP. |
| `ruleset_version` | entier ≥ 1 | Version métier déclarée ; aucune formule n’est exécutée dans ce slice. |

Le client ne fournit jamais : `report_id`, `tenant_id`, `membership_id`, `state`, `aggregate_revision`, date, montant, total, ligne, marge, trésorerie, source, fournisseur, formule, note ou règle de calcul. Le `report_id`, l’horodatage et la révision sont alloués côté serveur.

## 4. Route HTTP

```text
POST /api/v1/patron/cases/{case_id}/financial-reports/drafts
```

La route utilise exclusivement le résolveur de bearer réel SEC-01. Aucun tenant, rôle, capability ou contexte de test ne peut provenir du corps JSON.

### Requête publique fermée

```json
{
  "command_id": "uuid",
  "idempotency_key": "uuid",
  "correlation_id": "uuid optionnel",
  "currency_code": "EUR",
  "ruleset_version": 1
}
```

Les DTO Pydantic doivent définir `extra = "forbid"`.

### Receipt public fermé

La réponse contient seulement le statut d’exécution, les identifiants de commande et d’idempotence, le code résultat `FINANCIAL_REPORT_DRAFT_CREATED`, les références d’agrégat, les identifiants d’événements et `replayed`.

Elle ne contient aucun montant, total, taux, ligne, libellé, devise détaillée, source, hash, règle, auteur, tenant, membership, date de calcul, formule ou note libre.

## 5. Sécurité et autorisation

| Sujet | Règle non négociable |
|---|---|
| Acteur admis | Membership active `PATRON_ADMIN` uniquement. |
| Capability | Nouvelle capability fermée `financial.report.create`, attribuée seulement à `PATRON_ADMIN`. |
| Acteurs interdits | Collaborateur, délégataire, acteur `SYSTEM`, identité inactive ou membership inactive. |
| Ordre de contrôle | `_require_patron()` et capability avant toute résolution de la Case ou du snapshot. |
| Ressource | La Case est résolue tenant-scopée seulement après le contrôle patron ; son espace financier est `FINANCIAL_PRIVATE`. |
| Refus hors tenant | Case absente ou étrangère : `404 NOT_FOUND_OR_FORBIDDEN` sans révéler son existence. |
| Audit | Autorisation et refus SEC-01 minimisés : jamais de montant, libellé, règle, source ou donnée bancaire. |

## 6. État créé et invariants

Le handler verrouille la Case avec `FOR UPDATE` avant de vérifier l’absence de brouillon `DRAFT` ouvert. Dans la même transaction, il crée le snapshot suivant :

| Champ serveur | Valeur à la création |
|---|---|
| `id` | UUID opaque généré serveur. |
| `tenant_id`, `case_id` | Valeurs tenant-scopées de la Case résolue. |
| `state` | `DRAFT`. |
| `currency_code`, `ruleset_version` | Valeurs de commande validées. |
| `aggregate_revision` | `0`. |
| `calculated_at` | Horodatage serveur de création technique ; aucune formule n’a été exécutée. |
| `published_at` | `NULL`. |
| Tous les totaux mineurs et taux | `0`, sans valeur monétaire fournie par le client. |

La base doit imposer **au plus un** snapshot `DRAFT` par couple `(tenant_id, case_id)`, au moyen d’un index unique partiel. Une Case peut conserver plusieurs snapshots `PUBLISHED` historiques ; ce slice ne les modifie jamais.

L’état `DRAFT` est mutable uniquement par les frontières financières patron ultérieures, révisionnées et explicitement contractées. L’état `PUBLISHED` demeure définitif dans le périmètre de publication actuel : aucune écriture en place n’est admise.

## 7. Atomicité, événement et idempotence

Le dispatcher existant crée le receipt de commande, puis le handler écrit dans une transaction unique :

1. verrou Case tenant-scopée ;
2. contrôle de l’absence d’un autre `DRAFT` ouvert ;
3. création du snapshot vide ;
4. création de l’événement minimal `FinancialReportDraftCreated` ;
5. création de l’outbox ;
6. finalisation du receipt.

L’événement ne porte que les identifiants d’agrégat, l’état `DRAFT`, la révision `0` et des métadonnées non financières. Il exclut tous totaux, devises, montants, lignes et règles.

| Situation | Réponse publique |
|---|---|
| Première création admise | `201` et `FINANCIAL_REPORT_DRAFT_CREATED`. |
| Rejeu strict de même commande | `200`, même receipt et aucune seconde création. |
| Même clé avec autre payload | `409 IDEMPOTENCY_KEY_REUSED`. |
| Commande encore en traitement | `409 COMMAND_IN_PROGRESS`. |
| Case étrangère ou absente | `404 NOT_FOUND_OR_FORBIDDEN`. |
| Collaborateur / capability absente | `403 FORBIDDEN`, avant lecture de Case. |
| Brouillon déjà ouvert pour la Case | `422 COMMAND_REJECTED`. |
| Payload invalide | `422` Pydantic. |

## 8. Migration attendue

La migration additive suivante doit créer l’index unique partiel de brouillon ouvert. Elle ne réécrit aucune donnée existante et ne modifie ni `financial_report_publications` ni les snapshots `PUBLISHED`.

```sql
UNIQUE (tenant_id, case_id) WHERE state = 'DRAFT'
```

Les clés composites tenant/Case, les checks `DRAFT|PUBLISHED` et l’invariant `published_at` existants restent les sources d’autorité. La migration doit être validée par `upgrade head`, `alembic check` et `downgrade base`.

## 9. Matrice minimale de tests

| Scénario | Preuve attendue |
|---|---|
| Patron crée un brouillon | `201`, état `DRAFT`, révision `0`, totaux à zéro, aucun montant dans receipt. |
| Rejeu strict | `200`, même `report_id`, une seule ligne snapshot. |
| Deuxième brouillon de même Case | `422`, aucun second snapshot. |
| Collaborateur | `403` avant toute résolution de Case/snapshot, aucune écriture. |
| Tenant étranger | `404` neutre, aucune écriture. |
| Clé idempotence incompatible | `409`. |
| Payload enrichi ou invalide | `422`, aucune écriture. |
| Concurrence | L’unicité partielle et le verrou Case empêchent deux `DRAFT`. |
| Non-fuite | Receipt, audit, événement et OpenAPI sans montant, total, ligne, source, formule ou note. |
| Migration | Upgrade/check/downgrade sans dérive. |

## 10. Condition de fermeture du slice

Le slice est fermé seulement après contrat, commande Pydantic, capability, handler transactionnel, migration, route HTTP, tests PostgreSQL/API, OpenAPI, Ruff, detect-secrets, suite backend, CI GitHub et mise à jour du point de reprise. Il prépare directement le slice suivant : **écriture révisionnée et historisée des lignes financières d’un brouillon `DRAFT`**.
