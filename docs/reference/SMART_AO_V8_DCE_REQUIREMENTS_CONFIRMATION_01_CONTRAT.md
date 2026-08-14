# SMART_AO V8 — DCE-REQUIREMENTS-CONFIRMATION-01

**Statut :** normatif.  
**Périmètre :** confirmation humaine, invalidation prudente ou signalement à revoir d’une exigence atomique déjà matérialisée.  
**Dépendances :** SEC-01, DCE-REQUIREMENTS-01, DCE-ANALYSIS-01 et DCE-CLASSIFICATION-01.

## 1. But et frontière

DCE-REQUIREMENTS-CONFIRMATION-01 permet à un humain autorisé de traiter une exigence atomique issue du règlement de consultation. Le système conserve l’exigence source inchangée et écrit une **confirmation historisée** séparée. La confirmation est une qualification de préparation interne, non une interprétation juridique, une preuve de conformité, une décision de réponse ou une autorisation de dépôt.

> Une confirmation positive signifie seulement : « l’acteur habilité a examiné le signal sourcé et le retient pour la préparation ». Elle ne signifie jamais « l’entreprise est conforme », « la pièce est prête », « le délai est calculé » ou « le dossier peut être déposé ».

## 2. Acteurs, policy et séparation patron/collaborateur

| Acteur | Action autorisable | Conditions obligatoires | Interdits |
|---|---|---|---|
| `COLLABORATEUR` affecté | `CONFIRMED`, `REVIEW_REQUIRED` | Capability `dce.requirement.confirm`, affectation active à la `Case` de la DCE, classification `INTERNAL_OPERATIONAL`, policy serveur `ALLOW`. | `NOT_APPLICABLE`, contournement d’affectation, prix, Go/No-Go, dépôt. |
| `PATRON_ADMIN` | `CONFIRMED`, `REVIEW_REQUIRED`, `NOT_APPLICABLE` | Capability `dce.requirement.confirm`, membership actif, policy serveur `ALLOW`. | Altérer la source, supprimer l’historique ou confondre confirmation et conformité. |
| `PATRON_DELEGATE` | Même capacité que le patron seulement si grant explicite futur | Capability résolue côté serveur et policy `ALLOW`. | Droit déduit du rôle seul. |
| `SYSTEM`, support, partenaire | Aucune confirmation humaine. | Refus systématique. | Toute écriture de confirmation. |

La policy est évaluée avant le handler à partir d’un `ActorContext` résolu côté serveur. L’exigence demeure rattachée à sa DCE et non à une Case : avant la policy, le serveur recherche **l’unique** `Case` active dont `applicable_dce_version_id` vise cette DCE. Cette Case est une donnée de sécurité transitoire, jamais fournie par le client ni persistée comme propriété de la confirmation. En l’absence de Case unique — zéro Case, ou plusieurs Cases actives pour cette DCE — la commande est refusée de façon sûre avec `COMMAND_REJECTED`; le produit devra introduire des exigences Case-scopées avant d’autoriser une DCE partagée par plusieurs affaires. Une ressource hors tenant retourne `NOT_FOUND_OR_FORBIDDEN`; une capability ou affectation insuffisante retourne un refus public minimisé et un audit de sécurité. Le corps HTTP ne contient jamais tenant, acteur, rôle, capability, `case_id` ou classification de confiance.

## 3. États et transitions fermées

Le statut courant est une projection dérivée de la dernière confirmation append-only. L’exigence source reste toujours `PENDING_HUMAN_CONFIRMATION` dans son registre d’origine.

| État projeté | Signification limitée | Transition autorisée |
|---|---|---|
| `PENDING_HUMAN_CONFIRMATION` | Aucune confirmation humaine encore enregistrée. | Toute action autorisée par le §2. |
| `CONFIRMED` | L’exigence est retenue pour préparation. | `REVIEW_REQUIRED` ou `NOT_APPLICABLE` avec nouvelle confirmation justifiée. |
| `REVIEW_REQUIRED` | Le signal ou son applicabilité doit être revu. | `CONFIRMED` ou `NOT_APPLICABLE` avec nouvelle confirmation justifiée. |
| `NOT_APPLICABLE` | Le patron estime le signal non applicable à ce dossier. | Seul patron/délégataire explicitement habilité peut produire une nouvelle confirmation. |

Les motifs sont un catalogue fermé : `SOURCE_REVIEWED`, `AMBIGUOUS_SOURCE`, `CONTRADICTORY_DCE`, `PATRON_NOT_APPLICABLE`, `NEEDS_EXTERNAL_CLARIFICATION`. Aucun texte libre, prix, montant, identifiant personnel, document complet, date calculée ou avis juridique n’est persisté dans ce slice.

## 4. Commande, idempotence et transaction

La commande normalisée `RecordDceRequirementConfirmation` porte : `confirmation_id`, `requirement_id`, `expected_confirmation_revision`, `outcome`, `reason_code`, `idempotency_key` et `correlation_id`. Le handler relit et verrouille le requirement tenant-scopé, son run et sa DCE, puis revalide tenant, état, révision et policy.

L’unicité idempotente est assurée par le dispatcher sur `(tenant_id, actor_id, command_type, idempotency_key)`. Une collision avec le même payload rejoue le receipt sans écriture; une révision obsolète est refusée avant tout effet durable. Une confirmation est écrite avec sa révision `n + 1` et un lien vers la confirmation immédiatement précédente, dans la même transaction que receipt, event et outbox.

## 5. Persistance append-only et preuves

| Table | Grain | Invariants |
|---|---|---|
| `dce_requirement_confirmations` | Une action humaine sur une exigence DCE-scopée. | `tenant_id`, FK composite vers exigence, révision unique par exigence, auteur/acteur, statut et motif fermés, parent historique facultatif. La Case n’est pas stockée : elle est résolue uniquement pour la policy. |
| `dce_requirement_confirmation_current` | Projection de l’état courant. | Une ligne par exigence; mise à jour transactionnelle exclusivement par le handler. Elle ne remplace jamais une confirmation. |

Le registre de confirmations interdit `UPDATE` et `DELETE` par trigger PostgreSQL. La projection courante est reconstruisible depuis la dernière révision append-only. Le handler ne modifie ni DCE, ni extraction, ni analyse, ni classification, ni exigence source.

## 6. Événements, audit et confidentialité

L’événement métier `DCE_REQUIREMENT_CONFIRMED` et l’outbox incluent seulement IDs, outcome, reason code, révision et compteurs; ils n’incluent ni extrait, ni texte source, ni document, ni montant. Chaque autorisation refusée ou réussie est auditée via SEC-01 avec l’action `dce.requirement.confirm`, resource type `DCE_REQUIREMENT` et les identifiants de corrélation.

La confirmation est `INTERNAL_OPERATIONAL`. Elle ne peut ouvrir aucun accès à `FINANCIAL_PRIVATE`; les DTO collaborateur futurs ne devront jamais inclure prix, marge, devis, trésorerie, credentials, token, audit brut ou contenu de document.

## 7. Critères de sortie

Le slice doit prouver : isolation tenant; résolution serveur d’une Case active **unique** et refus du périmètre ambigu; refus sans capability ou affectation; interdiction SYSTEM; transition fermée; contrôle de révision; replay idempotent; append-only PostgreSQL; projection courante cohérente; event/outbox minimisés; audit succès/refus; et absence de données financières ou de contenu documentaire dans toute sortie.

## 8. Non-objectifs

Ce slice n’expose pas encore de route HTTP, n’implémente pas les écrans wizard, n’envoie pas de notification, ne crée pas de tâche, ne calcule pas de délai, ne vérifie pas de document, ne produit pas de conformité juridique, ne génère pas de mémoire, ne détermine pas de prix, ne finalise pas Go/No-Go et ne dépose rien.
