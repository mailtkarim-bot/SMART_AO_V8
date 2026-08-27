# Brouillons contrôlés DC1/DC2/DC4

## Objet

Les documents DC1, DC2 et DC4 sont générés comme **brouillons non contractuels**, versionnés et append-only. Le serveur ne déduit aucune conformité juridique, ne signe aucun document et ne transmet rien à un fournisseur externe. Toute validation humaine et toute signature externe restent obligatoires.

## DTO de commande public

Le endpoint collaborateur est `POST /api/v1/collaborator/preparation/{package_id}/documents`.

| Champ | Type | Règle |
|---|---|---|
| `command_id` | UUID | Identifiant de commande ; devient aussi l’identifiant du document généré. |
| `idempotency_key` | UUID | Clé d’idempotence obligatoire. |
| `correlation_id` | UUID ou `null` | Corrélation facultative. |
| `expected_revision` | entier `>= 0` | Révision attendue du package de préparation. |
| `readiness_revision` | entier `>= 1` | Révision de readiness utilisée comme entrée immuable. |
| `document_kind` | `TECHNICAL_RESPONSE \| DC1 \| DC2 \| DC4` | Union fermée ; aucune valeur libre n’est acceptée. |

Le contrat de réponse expose uniquement le reçu de commande : statut, identifiants de commande et d’idempotence, code résultat, références d’agrégats, événements et indicateur de rejeu. Pour une génération DC1/DC2/DC4, `result_code` vaut `CONTROLLED_DRAFT_GENERATED`.

## DTO de projection publique

Chaque élément de `generated_documents` expose :

| Champ | Type | Règle |
|---|---|---|
| `document_id` | UUID | Identifiant public du brouillon. |
| `version` | entier `>= 1` | Version append-only dans le package. |
| `document_kind` | `TECHNICAL_RESPONSE \| DC1 \| DC2 \| DC4` | Type autorisé. |
| `state` | `GENERATED \| FAILED_SAFE` | État technique de génération. |
| `readiness_revision` | entier `>= 1` | Readiness source utilisée. |

Le `storage_key`, le hash du contenu, les secrets, le contenu privé et les fournisseurs ne sont pas exposés par la projection HTTP.

## Faits serveur allowlistés

Les faits sont construits à partir de la projection DCE et de la readiness déjà évaluée. Le générateur ne reçoit pas de dictionnaire libre fourni par le client.

### Faits communs aux trois types

| Clé | Source serveur | Sens |
|---|---|---|
| `case_id` | Package de préparation | Affaire du périmètre autorisé. |
| `dce_version_id` | Package de préparation | Version DCE utilisée. |
| `readiness_state` | Readiness append-only | `READY` ou `READY_WITH_WARNINGS` au moment accepté par le handler. |
| `readiness_revision` | Readiness append-only | Révision de l’évaluation de complétude. |
| `blocker_codes` | Readiness append-only | Codes de blocage déterministes ; une génération est refusée si l’état est `BLOCKED`. |
| `warning_codes` | Readiness append-only | Avertissements déterministes. |

### Extension spécifique par type

| Type | Fait additionnel | Limite volontaire |
|---|---|---|
| DC1 | `confirmed_requirement_count` | Seul le nombre d’exigences confirmées est fourni ; aucune affirmation juridique n’est produite. |
| DC2 | `confirmed_requirement_ids` | Seuls les identifiants d’exigences dont l’issue serveur est `CONFIRMED` sont listés. |
| DC4 | `scope_policy = DCE_REQUIREMENTS_ONLY` | Le périmètre est explicitement limité aux exigences DCE ; aucune attestation d’aptitude n’est inférée. |

Les clés liées à des prix, marges, coûts, chiffre d’affaires, signatures, assurances validées juridiquement ou conformité réglementaire ne font pas partie de l’allowlist.

## Versioning et sécurité

La table existante `generated_technical_documents` reste le stockage append-only compatible avec l’historique. La migration `20260826_0064` remplace la contrainte de type documentaire pour autoriser `TECHNICAL_RESPONSE`, `DC1`, `DC2` et `DC4`, tout en conservant l’unicité `(tenant_id, package_id, version)`, la readiness source, le trigger append-only et les filtres tenant/membership.

La génération de chaque type est idempotente au niveau commande et incrémente la version du package. Le contenu est écrit dans le stockage privé ; la réponse HTTP ne renvoie jamais le chemin privé ni le hash de contenu. Le filtre anti-données financières est appliqué avant l’écriture.

## Cockpit Decision déjà livré

Le cockpit frontend est composé de :

- `DecisionRiskRequirementsPanel.tsx`, qui affiche les liens risque–exigence et les candidats DPGF/BPU sans montants, prix ni quantités ;
- `useDecisionRiskRequirements.ts`, qui gère la sélection, la pagination par curseur et la recherche bornée ;
- `web/src/infrastructure/api.ts`, qui transporte les deux endpoints Decision avec encodage des identifiants et paramètres ;
- `web/src/shared/types.ts`, qui verrouille les DTOs TypeScript ;
- les tests de composant, de hook et de transport API, intégrés à la suite frontend.

La surface est branchée dans `App.tsx` uniquement pour les acteurs patronaux et l’affaire sélectionnée. Les collaborateurs ne reçoivent pas cette surface.

## Limites de validation

Les tests unitaires, les tests API et la CI peuvent vérifier le contrat, la migration et les invariants locaux. Ils ne remplacent pas la validation juridique, le corpus DCE autorisé, la recette des secrets/fournisseurs, l’opération HTTPS/VPS, ni la signature ou transmission réelles.

## Parcours frontend livré

Le wizard collaborateur propose désormais un sélecteur fermé `TECHNICAL_RESPONSE`, `DC1`, `DC2` ou `DC4` avant l’action de génération. Le type choisi est transmis au serveur avec la révision du package et la révision de readiness ; le serveur reste l’autorité pour accepter ou refuser la génération. Les documents produits apparaissent ensuite dans la projection versionnée et peuvent être relus ou téléchargés via le parcours d’accès documentaire contrôlé décrit dans `docs/PREPARATION_GENERATED_DOCUMENT_ACCESS.md`.
