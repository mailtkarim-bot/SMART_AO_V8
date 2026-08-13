# SMART_AO V8 — DCE-ADMIT-HTTP-01 : Contrat HTTP d’admission d’une version DCE

**Statut :** normatif.  
**Périmètre :** frontière HTTP authentifiée qui déclenche `RegisterDceVersion` défini par DCE-ADMIT-01. Elle admet exclusivement les métadonnées et références de pièces **pré-stagées** ; elle ne reçoit ni octet, ni flux multipart, ni secret de stockage.

## 1. Intention métier

Le patron ou utilisateur expressément autorisé transmet un corpus DCE déjà pré-stagé afin de l’enregistrer durablement dans la consultation concernée. L’endpoint ne prend aucune décision de réponse, de chiffrage ou de dépôt. Il transforme seulement une intention HTTP autorisée en commande transactionnelle, puis délègue les invariants métier au dispatcher.

> L’URL ne valide pas l’existence effective de l’objet de stockage, son antivirus ni ses droits d’accès. Ces contrôles appartiendront au flux sécurisé de staging/upload. Une `storage_key` reste une référence technique confidentielle : elle peut être acceptée dans la requête, mais n’est jamais retournée par la réponse.

## 2. Ressource et méthode

| Élément | Contrat |
|---|---|
| Méthode et URL | `POST /api/v1/dce-versions` |
| Authentification | En-tête `Authorization: Bearer <access_token>` obligatoire. Le JWT est résolu côté serveur ; aucun tenant, rôle, capability ou acteur ne provient du corps HTTP. |
| Action autorisée | Capability serveur `dce.prepare`. |
| Ressource de policy | `CONSULTATION`, identifiée par `consultation_id`, classifiée `PUBLIC_TENDER`, appartenant au tenant réel de cette consultation. |
| Policy | Le contexte authentifié, la capability et la policy tenant-scoped sont évalués et les refus sont écrits dans le journal append-only par la policy auditée. |
| Effet durable | Délégation au dispatcher de `RegisterDceVersion`, qui garantit l’atomicité `DceVersion + documents + DomainEvent + OutboxMessage + CommandReceipt`. |

## 3. Requête

Le body est le contrat fermé `RegisterDceVersionCommand`. Il contient les identifiants de commande et d’idempotence, la consultation et sa révision attendue, le hash du corpus, la provenance, la date de réception et les documents pré-stagés. Les faits d’autorisation ne sont pas sérialisables dans ce body.

| Donnée | Règle de transport |
|---|---|
| `command_id`, `idempotency_key`, `correlation_id` | UUID ; la clé d’idempotence est évaluée tenant + acteur + type de commande côté serveur. |
| `consultation_id`, `consultation_revision` | Référence et révision que le serveur autorise avant dispatch. Le handler les revalide de façon transactionnelle. |
| `dce_version_id`, `corpus_hash`, `documents` | Validés par Pydantic puis par les invariants DCE-ADMIT-01. Le corpus contient au moins une pièce. |
| Références de stockage | `storage_object_id` et `storage_key` doivent déjà exister dans le staging futur ; l’endpoint ne téléverse rien. |
| Tenant et acteur | Exclus du payload. Le `CommandContext` est créé uniquement depuis le `ActorContext` résolu du bearer. |

## 4. Réponse de succès

La réponse est volontairement minimale et ne contient aucune pièce, hash, provenance, `storage_object_id` ou `storage_key`.

| Situation | Statut | Corps |
|---|---:|---|
| Première admission | `201 Created` | `status`, `command_id`, `idempotency_key`, `result_code`, `aggregate_refs`, `event_ids`, `replayed: false`. |
| Rejeu strict de la même intention | `200 OK` | Même receipt durable avec `replayed: true`. |

`aggregate_refs` expose uniquement l’identifiant et la révision de la `DceVersion` créée. Toute lecture ultérieure passe par DCE-READ-01, dont la réponse de métadonnées exclut également les données documentaires et de stockage.

## 5. Refus et confidentialité

| Cas | Statut | Code public | Audit |
|---|---:|---|---|
| Bearer absent, invalide, expiré, session ou membership inactive | `401` | `UNAUTHENTICATED` | Selon le flux d’authentification applicable ; aucun contexte client ne remplace le contrôle serveur. |
| Capability absente ou policy métier refusée dans le tenant propriétaire | `403` | Code de policy neutre | `AUTHZ_DENIED` append-only. |
| Consultation absente | `404` | `NOT_FOUND_OR_FORBIDDEN` | Aucun audit de policy : aucun tenant propriétaire ne peut être résolu. |
| Consultation appartenant à un autre tenant | `404` | `NOT_FOUND_OR_FORBIDDEN` | `AUTHZ_DENIED` append-only, sans divulguer l’existence de la consultation. |
| Rejeu avec même clé mais intention différente | `409` | `IDEMPOTENCY_KEY_REUSED` | Receipt existant conservé. |
| Commande syntaxiquement valide mais invariant DCE-ADMIT-01 refusé | `422` | `COMMAND_REJECTED` | Aucune `DceVersion`, pièce, outbox ou receipt ne survit. |
| Body invalide | `422` | Erreur de validation FastAPI/Pydantic | Aucun dispatch. |

## 6. Interdictions explicites

La route ne doit jamais accepter un `tenant_id`, `actor_id`, rôle, capability, décision de policy ou identifiant de membership dans le payload. Elle ne doit pas produire de lien de téléchargement, de hash de pièce, de chemin de stockage, de prix, de marge, de document source, de décision Go/No-Go ou d’action de dépôt.

## 7. Critères de sortie

Les tests API contre PostgreSQL réel prouvent au minimum : l’exigence bearer, l’admission par patron autorisé, le replay HTTP `201 → 200` sans doublon, le refus collaborateur sans scope avec audit, l’isolation inter-tenant en `404` avec audit, la non-divulgation des références de stockage et le rollback en cas de commande rejetée. Les tests existants du dispatcher DCE-ADMIT-01 restent obligatoires et constituent la preuve du noyau transactionnel.
