# SMART_AO V8 — Plan COLLAB-EVIDENCE-CAPABILITY-01

## 1. Décision de cadrage

Le prochain incrément ne doit pas mélanger la bibliothèque entreprise patronale, la proposition collaborateur par affaire et la transmission au patron. Le modèle actuel conserve seulement une société et des documents `INSURANCE`, `KBIS` et `RIB`. Il ne possède pas encore de qualifications, références chantier, capacités structurées, droits d’usage par affaire ni propositions historisées du collaborateur.

Le prochain slice recommandé est donc **COLLAB-EVIDENCE-CAPABILITY-01**, précédé par le minimum de fondation entreprise nécessaire : un registre patronal de capacités et de preuves réutilisables, puis une proposition contextualisée par affaire. La capacité d’entreprise reste une réalité organisationnelle patronale ; la proposition pour une affaire reste une évaluation collaborateur distincte. Aucune proposition ne confirme automatiquement la capacité, la conformité DCE ou un engagement commercial.

> **Règle de frontière :** une preuve d’entreprise peut être disponible, expirée, manquante ou à confirmer. Elle ne devient jamais une preuve valide pour une affaire sans contrôle du périmètre, de la version, de la date d’usage et de l’autorité de partage.

## 2. Ce qui existe et ce qui manque

| Domaine | État actuel | Conséquence |
|---|---|---|
| Société entreprise | Livrée et tenant-scoped | Réutilisable comme parent organisationnel. |
| Documents administratifs | `INSURANCE`, `KBIS`, `RIB`, upload privé, scan ClamAV et vérification humaine | Suffisant pour les documents initiaux, insuffisant pour les qualifications et références. |
| Qualification / capacité | Absente comme aggregate structuré | À créer côté patron avant proposition collaborateur. |
| Référence chantier | Absente comme aggregate structuré | À créer avec période, périmètre, preuves et droit d’usage. |
| Preuve générique | Absente hors documents d’entreprise | À modéliser comme référence versionnée vers un objet privé ou un document vérifié. |
| Proposition pour une affaire | Absente | Nouveau root collaborateur tenant/Case-scoped. |
| Écart de capacité | Absente | Nouveau constat explicable rattaché à une exigence ou une tâche. |
| Readiness | Livrée | Doit intégrer les propositions/écarts de preuves sans conclure à une conformité automatique. |

## 3. Périmètre fermé du prochain incrément

### 3.1 Fondation entreprise minimale

La fondation introduit un catalogue fermé de capacités organisationnelles, par exemple `QUALIFICATION`, `REFERENCE`, `EQUIPMENT`, `TEAM`, `METHOD`. Chaque capacité est versionnée, possède un état de validité, un périmètre métier non financier, une période éventuelle et des références vers des preuves documentaires déjà vérifiées ou explicitement à confirmer.

Les commandes patronales de création et de versionnement seront traitées dans un ticket séparé si le propriétaire souhaite préserver la règle « un slice, un comportement ». Le collaborateur ne pourra jamais créer ou modifier la capacité d’entreprise depuis le wizard.

### 3.2 Proposition contextualisée par affaire

Le slice collaborateur expose d’abord deux commandes fermées :

| Commande | Effet durable | Autorité |
|---|---|---|
| `ProposeCapabilityForCase` | Crée une proposition versionnée reliant une capacité, une Case, une exigence ou tâche, une preuve candidate, une période d’usage et une justification. | Collaborateur affecté avec périmètre `EvidenceClass` / `SUBMIT` ou `COMMENT` selon la politique. |
| `ReportCapabilityGap` | Crée un constat d’écart reliant le besoin source, la capacité absente/expirée/non autorisée, la preuve manquante et l’action suivante. | Collaborateur affecté avec périmètre opérationnel. |

États proposés, à fermer dans le contrat définitif : `PROPOSED`, `TO_REVIEW`, `ACCEPTED_FOR_CASE`, `REJECTED`, `STALE`, `EXPIRED`. Une proposition `ACCEPTED_FOR_CASE` ne modifie pas la capacité organisationnelle ; elle signifie seulement que son usage pour cette affaire a été contrôlé par l’autorité requise.

### 3.3 Hors périmètre

Le slice ne comprend pas la génération de mémoire technique, les engagements candidats, le partage externe, la transmission patron, le calcul financier, la décision Go/No-Go, le dépôt, la validation juridique, l’OCR, l’IA de sélection ou la synchronisation de sources externes.

## 4. Invariants obligatoires

| Invariant | Test requis |
|---|---|
| `tenant_id` résolu serveur | Toute lecture/écriture étrangère reste neutre et ne révèle aucune capacité. |
| Affectation active et scope | Collaborateur non affecté, affectation suspendue ou scope Evidence absent : refus avant chargement détaillé. |
| Confidentialité financière | Aucun contrat, événement, log, projection ou payload ne contient prix, coût, marge, trésorerie, devis ou chiffrage. |
| Historique | Une preuve, qualification, référence ou proposition n’est jamais écrasée ni supprimée ; une nouvelle version est ajoutée. |
| Validité | Une preuve expirée ne peut pas être proposée comme actuelle ; elle produit `EVIDENCE_EXPIRED` ou un écart. |
| Provenance | Une proposition doit référencer une Case, une exigence/tâche ou justifier explicitement son rattachement interne. |
| Version | `expected_revision` protège le root mutable ; les objets immuables utilisent une version monotone. |
| Idempotence | Rejeu identique retourne le même receipt ; clé réutilisée avec contenu différent est rejetée. |
| Non-escalation | `READ_METADATA`, `READ_CONTENT`, `DOWNLOAD`, `SUBMIT` et `VALIDATE` restent distincts. |
| Décision humaine | Une proposition ne devient ni conformité, ni engagement, ni décision patron par effet de bord. |

## 5. Découpage exécutable

| Ordre | Ticket | Livrable | Critère de fermeture |
|---:|---|---|---|
| 1 | `ENTERPRISE-CAPABILITY-FOUNDATION-01` | Modèles, migration et contrats patronaux de capacité/version/référence/preuve. | PostgreSQL append-only, validité, droits d’usage et projections patronales minimales. |
| 2 | `COLLAB-EVIDENCE-CAPABILITY-01` | `ProposeCapabilityForCase` et `ReportCapabilityGap`, service ReBAC, événements/outbox et API collaborateur. | Cycle proposition/écart, tenant, scope, expiration, idempotence, révision, non-fuite et RYOW. |
| 3 | `PREPARATION-READINESS-EVIDENCE-01` | Extension déterministe du readiness pour preuves manquantes, expirées, non autorisées et gaps bloquants. | `BLOCKED`/warning explicables sans déclaration automatique de conformité. |
| 4 | `COLLAB-REVIEW-01` | `RequestReview`, `AcceptReview`, `ReturnReviewWithCorrections`, `RejectReview` sur cibles versionnées. | Revue indépendante de sa cible, corrections ciblées, audit et transitions sans écrasement. |
| 5 | `RESPONSE-DRAFT-01` | Brouillon de réponse versionné et engagements candidats. | Aucun engagement validé automatiquement ; sources, responsables, capacités et hypothèses présents. |

## 6. Matrice de tests du slice 2

Les tests PostgreSQL doivent démontrer le succès, le rejeu, la clé réutilisée, le conflit de révision, l’expiration, l’absence de preuve, le scope insuffisant, l’isolation inter-tenant, l’append-only des propositions et l’atomicité receipt/événement/outbox. Les tests API authentifiés doivent vérifier `201`, `200`, `403`, `404`, `409` et `422`, `extra=forbid`, la neutralité des ressources étrangères et l’absence de tout vocabulaire financier.

Un test de non-escalation doit prouver qu’un collaborateur possédant seulement `READ_METADATA` ne peut ni lire le contenu privé ni télécharger la preuve. Un test de rectificatif sera réservé à `EvaluateDceChangeImpact`, car l’impact ne doit pas être réimplémenté dans la proposition de capacité.

## 7. Ordre recommandé immédiat

1. Figer le contrat `ENTERPRISE-CAPABILITY-FOUNDATION-01` et ses classifications.
2. Écrire les tests rouges de la fondation organisationnelle sans ouvrir de route collaborateur.
3. Implémenter la persistance append-only et les projections patronales minimales.
4. Figer `COLLAB-EVIDENCE-CAPABILITY-01` sur les deux commandes de proposition/écart.
5. Ajouter le service ReBAC, les handlers transactionnels, les routes et les tests PostgreSQL/API.
6. Étendre le readiness seulement après preuve durable que les propositions et gaps sont lisibles et versionnés.

## 8. Dépendances et décisions à confirmer

La décision principale est de considérer les qualifications et références comme des capacités organisationnelles patronales, et non comme des documents génériques directement « possédés » par le collaborateur. La seconde décision est de réserver `ACCEPTED_FOR_CASE` à une revue autorisée, tandis que le collaborateur ne produit que `PROPOSED`, `TO_REVIEW` ou un gap.

La transmission, le snapshot immuable et le partage externe restent des slices ultérieurs. Cette séparation évite de transformer `PREPARATION-COMPLETENESS-01` en un root universel mêlant entreprise, affaire, documents, revues et décisions.
