# SMART_AO V8 — ENTERPRISE-CAPABILITY-FOUNDATION-01

## 1. Objet

Ce slice crée le catalogue patronal des capacités réutilisables de l’entreprise. Il couvre les qualifications, références, équipements, équipes et méthodes comme des roots organisationnels tenant-scoped, ainsi que leurs versions datées et leurs liens vers des documents de preuve déjà enregistrés dans la bibliothèque entreprise.

Une capacité organisationnelle n’est pas une conformité à une exigence DCE. La relation avec une Case, une exigence, une tâche ou une proposition collaborateur appartient à un slice d’évaluation distinct.

## 2. Commandes fermées

| Commande | Root propriétaire | Effet |
|---|---|---|
| `CreateEnterpriseCapability` | `EnterpriseCapability` | Crée une capacité `QUALIFICATION`, `REFERENCE`, `EQUIPMENT`, `TEAM` ou `METHOD` sous la société du tenant. |
| `AddEnterpriseCapabilityVersion` | `EnterpriseCapability` | Ajoute une version immuable datée avec périmètre d’usage et liens vers des documents de preuve de la même société. |

Le serveur résout toujours tenant, acteur, membership et société. Le client ne choisit pas `tenant_id`, `registered_by_membership_id` ou l’état d’une évaluation de Case.

## 3. Validité et preuves

Une version porte `valid_from`, un `valid_until` optionnel et une description bornée. Les liens de preuve sont append-only et référencent uniquement des documents du même tenant et de la même société. Une preuve absente, étrangère ou rejetée est refusée ; une preuve expirée ou à confirmer reste historisée mais ne constitue pas une validation automatique de la version.

Les versions utilisent un numéro monotone par capacité. Toute nouvelle version incrémente la révision optimiste du root. Les versions et liens ne sont jamais modifiés ou supprimés.

## 4. Autorisation

La lecture et l’écriture sont réservées au `PATRON_ADMIN` et aux capabilities fermées `enterprise.capability.read` et `enterprise.capability.write`. Les collaborateurs n’obtiennent aucun accès via ce slice. Les futures commandes collaborateur créeront une évaluation `Case × Capability × Evidence` séparée, sans modifier le catalogue organisationnel.

## 5. Concurrence et idempotence

Toute mutation porte `command_id`, `idempotency_key`, `correlation_id` optionnel et, pour un root existant, `expected_revision`. Le dispatcher commun mémorise le receipt et rejoue exactement le premier résultat terminal. Une révision obsolète retourne `VERSION_CONFLICT`; une clé réutilisée avec un contenu différent ne déclenche aucune mutation.

## 6. Événements et non-fuites

Les événements sont `EnterpriseCapabilityCreated` et `EnterpriseCapabilityVersionAdded`. Ils ne contiennent ni contenu complet de preuve, ni hash, ni storage key, ni filename, ni données financières. Les projections publiques retournent uniquement les identifiants, descriptions organisationnelles, dates, périmètres, états et IDs opaques des documents liés.

## 7. API patronale

Les routes publiées sont :

- `POST /api/v1/patron/enterprise/companies/{company_id}/capabilities`
- `POST /api/v1/patron/enterprise/capabilities/{capability_id}/versions`
- `GET /api/v1/patron/enterprise/companies/{company_id}/capabilities`

Les DTO sont `extra=forbid`. Les erreurs de tenant et de ressources étrangères restent neutres. Aucun endpoint collaborateur n’est créé dans cette fondation.

## 8. Critères de fermeture

Le slice est fermé lorsque les tests démontrent la création, le versionnement, la preuve même société, le rejeu idempotent, la clé réutilisée, le conflit de révision, l’append-only PostgreSQL, l’isolation tenant, le refus collaborateur, les payloads fermés, les événements/outbox minimisés, la migration upgrade/check/downgrade et la CI verte.
