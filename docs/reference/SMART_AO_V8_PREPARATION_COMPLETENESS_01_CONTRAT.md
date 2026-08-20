# SMART_AO V8 — PREPARATION-COMPLETENESS-01

## 1. Objet

`PREPARATION-COMPLETENESS-01` introduit le premier root de préparation documentaire collaborateur. Il évalue la complétude opérationnelle d’une affaire à partir des exigences DCE confirmées, des tâches et blockers visibles, puis génère un document technique versionné uniquement lorsque le contrôle courant l’autorise.

Ce slice ne prend aucune décision Go/No-Go, ne publie aucun prix, ne chiffre aucune offre et ne transmet rien au patron. Une génération réussie est un artefact de préparation, pas une conformité automatique ni une autorisation de dépôt.

## 2. Commandes fermées

| Commande | Root propriétaire | Effet |
|---|---|---|
| `EvaluatePreparationReadiness` | `PreparationPackage` | Crée ou révise la préparation et enregistre un contrôle explicable `READY`, `READY_WITH_WARNINGS` ou `BLOCKED`. |
| `GenerateTechnicalDocument` | `GeneratedDocument` | Produit une version immutable du document technique à partir du dernier readiness admissible. |

Le serveur résout tenant, acteur, membership, affaire, affectation et version DCE. Le client ne choisit ni tenant, ni propriétaire, ni état de conformité.

## 3. Contrat de complétude

Le calcul est déterministe et sourcé. Une exigence actuelle avec confirmation `CONFIRMED` ou `NOT_APPLICABLE` est admissible. Une exigence `PENDING_HUMAN_CONFIRMATION` ou une confirmation `REVIEW_REQUIRED` ajoute un blocker. Une tâche `BLOCKED` ajoute un blocker. Une tâche opérationnelle active sans résultat admissible ajoute un warning; elle ne rend pas automatiquement la préparation conforme.

Le résultat contient des codes fermés : `REQUIREMENT_UNCONFIRMED`, `TASK_BLOCKED`, `TASK_RESULT_MISSING`, `DCE_NOT_READY`, `CAPABILITY_PROOF_MISSING`, `CAPABILITY_PROOF_EXPIRED`, `CAPABILITY_PROOF_UNAUTHORIZED`, `CAPABILITY_GAP_BLOCKING`, `CAPABILITY_GAP_IMPORTANT`, `NO_BLOCKER`. Une preuve liée à une capacité doit appartenir à la même société, être vérifiée `VALIDATED`, être dans sa période de validité et provenir d’un lien serveur tenant-scoped ; sinon elle est respectivement manquante, expirée ou non autorisée. Un gap `BLOCKING` bloque la préparation ; un gap `IMPORTANT` reste un warning. Les listes sont triées et persistées avec l’empreinte des entrées contrôlées. Le système ne prétend jamais qu’un corpus incomplet est complet.

| État | Génération technique |
|---|---|
| `READY` | Autorisée. |
| `READY_WITH_WARNINGS` | Autorisée avec warnings explicitement projetés. |
| `BLOCKED` | Refusée avec `PREPARATION_BLOCKED`; aucune écriture d’artefact. |

## 4. Document versionné

Chaque génération possède un `document_id`, une version monotone par package, un type fermé `TECHNICAL_RESPONSE`, un hash calculé côté serveur, un locator de stockage privé opaque et la révision de readiness utilisée. Les versions précédentes ne sont jamais modifiées ou supprimées. La projection publique retourne l’identifiant, la version, l’état, le hash tronqué interdit; le hash complet, locator et contenu restent privés.

Le contenu est canonique, textuel et borné : affaire, version DCE, sections opérationnelles, exigences confirmées et warnings/blockers autorisés. Il ne contient jamais prix, coûts, marge, trésorerie, chiffrage, Go/No-Go, décision stratégique, chemin système ou URL privée.

## 5. Concurrence, idempotence et sécurité

Toute mutation porte `command_id`, `idempotency_key`, `expected_revision` et une corrélation. Un rejeu identique retourne le receipt sans deuxième readiness ni deuxième document. Une clé réutilisée avec un contenu différent est rejetée. Une révision obsolète retourne `VERSION_CONFLICT`.

L’autorisation exige un collaborateur authentifié, une affectation active dans l’affaire, la capability `preparation.readiness.write` ou `preparation.document.write` et la classification `INTERNAL_OPERATIONAL`. Les lectures sont ReBAC et tenant-scoped. Les contrats Pydantic sont `extra=forbid`.

## 6. Événements

Les événements minimaux sont `PreparationReadinessEvaluated` et `TechnicalDocumentGenerated`. Les payloads d’événements ne contiennent que des identifiants opaques, états, codes de complétude et versions; aucune donnée financière ou contenu documentaire privé n’y transite.
