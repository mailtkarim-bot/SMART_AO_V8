# SMART_AO V8 — CASE-DCE-IMPACT-01

## 1. Objet et justification

`CASE-DCE-IMPACT-01` persiste l’impact observable d’un rectificatif DCE sur une Case active. Il constitue une frontière de sécurité entre la DCE globale et le travail propre à l’affaire. Il ne recalcule pas silencieusement les confirmations, ne réutilise pas une validation ancienne et ne déclare ni conformité, ni pièce manquante, ni Go/No-Go.

Le contrat est volontairement conservateur. Les exigences matérialisées des deux versions ne possèdent pas encore de clé sémantique inter-version suffisamment prouvée pour affirmer qu’une exigence est « identique » ou « modifiée ». Le slice ne fabriquera donc aucune correspondance. Il produira un registre de revue obligatoire : les exigences de la version précédente restent à revoir et les signaux de la nouvelle version deviennent des candidats à examiner.

## 2. Déclenchement et acteur

Le service est déclenché par un traitement `SYSTEM` explicite et idempotent, après admission, classification et matérialisation des exigences de la version rectificative. Aucun patron ou collaborateur ne peut usurper cet acteur système par HTTP. Une future route de supervision ne fera que demander l’exécution ; elle ne fournira ni tenant, ni Case, ni statut d’autorisation faisant foi en dehors du contexte serveur.

## 3. Entrée applicative

L’intention interne contient : `tenant_id`, `case_id`, `predecessor_dce_version_id`, `successor_dce_version_id`, `command_id`, `idempotency_key`, `correlation_id` et l’instant de réception. Le système résout le tenant depuis la Case et vérifie les liens composites ; aucune valeur d’autorisation ne provient d’un champ JSON libre.

## 4. Préconditions strictes

L’exécution est rejetée sans écriture durable si l’une des conditions suivantes échoue :

1. la Case existe dans le tenant demandé et son cycle de vie est `ACTIVE` ou `STOPPED`, jamais `ARCHIVED` ;
2. `Case.applicable_dce_version_id` désigne exactement la version précédente ;
3. la version successorale appartient au même tenant et à la même Consultation ;
4. `successor.predecessor_dce_version_id` désigne exactement la version précédente ;
5. la version successorale est `ADMITTED`, `VERIFIED` et n’est pas retirée ;
6. les matérialisations d’exigences précédentes et successorales ont un état terminal sûr : `COMPLETED` ou `NO_SIGNAL` ;
7. les entrées et la version de l’algorithme produisent un manifeste canonique déterministe.

Une version absente, étrangère, sans lien rectificatif, non vérifiée ou non matérialisée produit un refus technique neutre et aucun registre partiel.

## 5. Registre durable append-only

Le slice ajoute deux registres tenant-scoped, sans modifier les exigences DCE ni les confirmations existantes.

| Registre | Rôle | Champs normatifs principaux |
|---|---|---|
| `case_dce_impact_runs` | Une exécution immuable pour une Case et un couple de versions | `tenant_id`, `id`, `case_id`, `predecessor_dce_version_id`, `successor_dce_version_id`, manifest d’entrée, identifiant/version d’algorithme, statut, compteurs, acteur système, dates |
| `case_dce_impact_items` | Une ligne de travail produite par l’exécution | `tenant_id`, `id`, `impact_run_id`, `case_id`, type d’impact, ancienne exigence éventuelle, nouvelle exigence éventuelle, état de revue, code de prudence, preuve bornée |

Les FKs composites `(tenant_id, id)` empêchent les références inter-tenant. Les deux tables sont protégées par des triggers PostgreSQL interdisant `UPDATE` et `DELETE`. Une unicité d’identité d’exécution sur tenant, Case, prédécesseur, successeur, manifest, algorithme et version rend le replay idempotent.

## 6. Algorithme déterministe et conservateur

L’algorithme calcule un manifest canonique ordonné contenant les identifiants et attributs approuvés des exigences des deux versions, sans stocker ni renvoyer le texte source. Il écrit ensuite :

| Situation | Ligne produite | État durable |
|---|---|---|
| Exigence de la version précédente | `PREVIOUS_REQUIREMENT_REQUIRES_REVIEW` avec `previous_requirement_id` | `REVIEW_REQUIRED` |
| Exigence de la version successorale | `SUCCESSOR_REQUIREMENT_CANDIDATE` avec `successor_requirement_id` | `PENDING_HUMAN_REVIEW` |
| Version précédente ou successorale sans exigence matérialisée | `VERSION_HAS_NO_MATERIALIZED_SIGNAL` | `REVIEW_REQUIRED` |
| Couple de versions rectificatif valide | `DCE_VERSION_REPLACED` sans décision de conformité | `REVIEW_REQUIRED` |

Le service ne produit jamais `UNCHANGED`, `REMOVED`, `MODIFIED`, `COMPLIANT` ou `MISSING` tant qu’une clé sémantique inter-version et une règle de preuve dédiées n’ont pas été validées dans un slice ultérieur. L’absence de correspondance n’est pas interprétée comme une suppression.

## 7. Consistance avec la Case et la lecture DCE

Le registre ne change pas `Case.applicable_dce_version_id`, ne change pas le cycle de vie de la Case et ne touche pas aux confirmations DCE globales. Après succès, la lecture Case doit pouvoir signaler qu’un impact rectificatif existe et bloquer toute action qui supposerait que les anciennes confirmations restent applicables. La mise à jour de cette projection de lecture sera incluse dans le même périmètre transactionnel uniquement si elle peut rester append-only et idempotente ; sinon elle fera l’objet du slice de lecture suivant.

## 8. Contrat public différé

Ce slice ne publie pas encore de route publique et ne renvoie aucun document, locator, texte, hash, stockage, prix, marge, audit ou décision patron. Une future lecture Case-scopée exposera seulement des états et compteurs issus du registre, après résolution bearer, tenant et policy `case.dce.read`.

## 9. Erreurs et idempotence

Les erreurs internes sont fermées : `CASE_NOT_FOUND_OR_FORBIDDEN`, `CASE_DCE_PREDECESSOR_MISMATCH`, `DCE_SUCCESSOR_INVALID`, `DCE_REQUIREMENTS_NOT_READY`, `IMPACT_INPUT_INVALID` et `IDEMPOTENCY_KEY_REUSED`. Une répétition avec la même identité d’entrée rejoue le receipt sans nouvelle ligne ; la même clé avec une empreinte différente est rejetée. Toute erreur pendant la transaction annule le run, ses items, l’événement, l’outbox et le receipt.

## 10. Critères de fermeture

Le slice sera fermé lorsque les tests prouveront : isolation tenant et FKs composites ; Case archivée refusée ; prédécesseur incorrect refusé ; successeur étranger ou non admis refusé ; matérialisation incomplète refusée ; run `COMPLETED` et run `NO_SIGNAL` déterministes ; absence de correspondance sémantique inventée ; aucune mutation des DCE, exigences ou confirmations ; replay idempotent ; mismatch de clé ; append-only PostgreSQL ; aucun acteur humain ni montant dans les sorties ou l’audit ; et rollback atomique sans run partiel.
