# SMART_AO V8 — DCE-CLASSIFICATION-01 : classification déterministe et sourcée des pièces DCE

**Statut :** normatif.
**Périmètre :** classement interne, reproductible et révisable des documents admis d’un DCE, à partir des fragments immuables déjà extraits.
**Dépendances :** SEC-01, DCE-ADMIT-01, DCE-DOCUMENT-EXTRACTION-01 et DCE-ANALYSIS-01.

## 1. But et frontière

DCE-CLASSIFICATION-01 permet à SMART_AO d’ordonner un DCE avant les étapes métier suivantes. Il détermine uniquement la **famille documentaire candidate** d’une pièce — règlement de consultation, cahier administratif, cahier technique, acte d’engagement, BPU, DPGF, plan, annexe ou rectificatif — et conserve les fragments qui justifient ce classement.

> Une classification est un repère documentaire pour organiser le travail du collaborateur. Elle n’est ni une interprétation juridique, ni une vérification de complétude, ni une preuve de conformité, ni une décision de répondre ou de ne pas répondre.

Les documents de consultation peuvent notamment comprendre un avis, un RC, un CCAP, un CCTP, des documents financiers et un acte d’engagement. Le présent catalogue reprend ces familles pour les identifier dans le DCE, mais ne prétend pas qu’elles sont toutes exigées ou présentes dans chaque consultation. [1]

## 2. Préconditions non négociables

La classification est une commande interne. Seul un `actor_kind = SYSTEM` peut la produire. Aucun navigateur, collaborateur, patron, jeton JWT, contenu DCE ou route HTTP ne peut fabriquer une exécution de classement.

| Fait relu côté serveur | Condition requise | Refus ou résultat sûr sinon |
|---|---|---|
| DCE | même tenant, cycle `ADMITTED` ou `SUPERSEDED`, intégrité `VERIFIED` | `DCE_VERSION_NOT_CLASSIFIABLE` |
| Documents | relus exclusivement depuis cette DCE | `DCE_DOCUMENT_REQUIRED` |
| Extraction | seuls les registres `COMPLETED` du même document sont utilisables | Aucun original lu. |
| Fragment | même tenant, extraction reliée au document, hash et ordinal relus | `DCE_CLASSIFICATION_SOURCE_FRAGMENT_REQUIRED` |
| Révision DCE | la révision attendue correspond à la racine verrouillée | `DCE_VERSION_STALE` |

Un document sans extraction `COMPLETED`, une image sans OCR, un plan graphique, un archive ou un contenu sans règle reconnue ne reçoit pas de faux classement. Il demeure dans l’état de résultat adapté (`NOT_EXTRACTED`, `UNCLASSIFIED` ou `REVIEW_REQUIRED`).

## 3. Catalogue fermé des familles documentaires

La première version applique uniquement des règles lexicales versionnées. Les règles examinent des fragments textuels ; le nom de fichier, le chemin de quarantaine, la clé privée, le MIME déclaré par un client et les métadonnées externes ne sont pas des preuves de classification.

| `classification` | Famille repérée | Signaux textuels déterministes initiaux | Limite explicite |
|---|---|---|---|
| `RC` | Règlement de consultation | `règlement de la consultation`, `règlement de consultation` | Ne prouve pas l’exhaustivité des consignes. |
| `CCAP` | Cahier des clauses administratives particulières | `CCAP`, `cahier des clauses administratives particulières` | Ne valide pas les clauses financières ou contractuelles. |
| `CCTP` | Cahier des clauses techniques particulières | `CCTP`, `cahier des clauses techniques particulières` | Ne confirme pas une solution technique. |
| `AE` | Acte d’engagement | `acte d'engagement`, `acte d’engagement` | Ne vaut ni signature ni engagement. |
| `BPU` | Bordereau des prix unitaires | `BPU`, `bordereau de prix unitaires` | Ne lit ni ne calcule les prix. |
| `DPGF` | Décomposition du prix global et forfaitaire | `DPGF`, `décomposition du prix global et forfaitaire` | Ne valide ni quantités ni chiffrage. |
| `PLAN` | Pièce graphique ou plan textuellement désignée | `plan de situation`, `plan d'installation`, `plan d’implantation` | Les plans images/DWG sans texte ne sont pas classés. |
| `ANNEX` | Annexe textuellement identifiée | `annexe`, `annexes` | Ne détermine pas la valeur métier de l’annexe. |
| `RECTIFICATION` | Rectificatif ou pièce modifiée | `rectificatif`, `modification de la consultation` | Ne calcule pas les impacts entre versions. |
| `OTHER` | Réservé aux futures corrections humaines explicites | Aucun déclencheur système dans ce slice | Le système ne transforme jamais un manque de signal en `OTHER`. |

Les libellés suivent le contrat APP-01 historique de la V8. Une règle est identifiée par `rule_id` et `rule_version`; modifier son vocabulaire, son ordre de priorité ou sa normalisation impose une nouvelle version d’analyseur.

## 4. Résultat par document et absence de faux positif

Une exécution couvre toute une `DceVersion` et produit un résultat append-only par document admis.

| `result_status` | Signification | Classification courante créée ? |
|---|---|---|
| `CLASSIFIED` | Une famille unique est sélectionnée avec au moins un fragment de preuve. | Oui, si elle diffère de la classification courante. |
| `UNCLASSIFIED` | Des fragments existent, mais aucune règle du catalogue n’a reconnu une famille. | Non. |
| `REVIEW_REQUIRED` | Plusieurs familles concurrentes arrivent au même niveau de preuve ou la règle est contradictoire. | Non. |
| `NOT_EXTRACTED` | Aucun fragment d’extraction `COMPLETED` n’est disponible pour ce document. | Non. |

Le système compte les occurrences exactes de chaque règle dans le document. Une famille est sélectionnée seulement si son score est strictement supérieur aux autres familles candidates. En cas d’égalité entre familles, le résultat est `REVIEW_REQUIRED`. Il n’existe aucun seuil de confiance probabiliste et aucune sortie LLM.

L’absence de `CLASSIFIED` ne signifie jamais que la pièce n’est pas un RC, un CCAP, un plan ou une annexe. Elle signifie seulement que les fragments disponibles n’ont pas permis à ce catalogue déterministe de conclure sans ambiguïté.

## 5. Manifest canonique et versionnement

Le manifest capture la totalité de l’entrée documentaire, y compris l’absence d’extraction pour un document. Les lignes UTF-8 sont séparées par un caractère LF réel et ordonnées par UUID normalisé de document, extraction et fragment.

```text
D|<dce_document_id>|<extraction_id>|<fragment_id>|<ordinal>|<text_sha256>
N|<dce_document_id>
```

`D` représente un fragment d’une extraction `COMPLETED`; `N` représente un document admis sans fragment utilisable. Le `input_manifest_sha256` est le SHA-256 de ce manifeste. Une exécution est fonctionnellement unique par `(tenant_id, dce_version_id, input_manifest_sha256, classifier_id, classifier_version)`.

Une nouvelle extraction achevée, une nouvelle version du classifieur ou une nouvelle DCE conduisent donc à une nouvelle exécution. Aucun résultat antérieur, aucune preuve ni aucune classification d’origine n’est écrasé.

## 6. Registre immuable et projection courante

Le slice ajoute les registres append-only suivants et réutilise `dce_document_classifications` comme projection courante et historique de classement.

| Table | Rôle | Éléments conservés |
|---|---|---|
| `dce_document_classification_runs` | Une exécution déterministe sur un manifest DCE. | Manifest, version du classifieur, statut, compteurs et code d’échec fermé. |
| `dce_document_classification_results` | Un résultat par document pour une exécution. | Statut, famille éventuelle, score, classification courante créée ou réutilisée. |
| `dce_document_classification_evidence` | Une preuve de fragment pour un résultat `CLASSIFIED`. | Fragment, règle/version, offsets UTF-8 et extrait borné. |
| `dce_document_classifications` | Projection courante et historique révisable. | Famille, source système, classification précédente et `is_current`. |

Les trois nouveaux registres refusent `UPDATE` et `DELETE` via triggers PostgreSQL. Une preuve ne peut être insérée que pour un résultat `CLASSIFIED` du même tenant, relié à une exécution `COMPLETED`, à un fragment du même document et à une classification de la même famille.

Pour un nouveau classement déterministe différent, la ligne courante précédente de `dce_document_classifications` est seulement marquée `is_current = false`; une nouvelle ligne, reliée à la précédente, devient courante. Cette transition est le seul `UPDATE` autorisé dans la projection historique. Une classification identique est réutilisée par le nouveau résultat, sans créer de doublon.

## 7. Readiness DCE et transaction

La commande interne `RecordDceDocumentClassificationRun` contient la révision DCE attendue. L’exécution immuable conserve cette révision de départ afin que le replay du même manifest conserve exactement la même requête idempotente après l’actualisation de la root. Dans une transaction unique, le handler verrouille la racine, les documents, leurs extractions et classifications courantes, revalide le manifest, écrit l’exécution, les résultats, les preuves et les éventuelles nouvelles classifications, puis actualise `classification_readiness` et la révision DCE.

| État de `classification_readiness` | Règle |
|---|---|
| `UNCLASSIFIED` | Aucun document n’a reçu de classification `CLASSIFIED`. |
| `PARTIALLY_CLASSIFIED` | Au moins un document est classé, mais au moins un document est non classé, en revue ou non extrait. |
| `CLASSIFIED` | Tous les documents admis possèdent une classification courante issue de ce classement ou d’un historique réutilisé. |

L’événement `DCE_DOCUMENT_CLASSIFICATION_RECORDED` et l’outbox `cockpit_projection` ne contiennent que l’ID d’exécution, l’ID de DCE, la readiness et les compteurs. Ils ne contiennent ni texte, ni extrait, ni offsets, ni hash d’original, ni nom de fichier, ni clé de stockage, ni prix.

Le replay du même tenant, même acteur système, même type de commande et même `idempotency_key` retourne le receipt existant. Une collision d’unicité fonctionnelle relit le résultat terminal existant : elle ne réécrit jamais un registre.

## 8. Limites, confidentialité et accès

| Contrôle | Limite | Effet au dépassement |
|---|---:|---|
| Documents par DCE classés dans une exécution | 10 000 | `REJECTED_LIMIT`, zéro résultat. |
| Fragments `COMPLETED` relus | 100 000 | `REJECTED_LIMIT`, zéro résultat. |
| Caractères relus | 10 000 000 | `REJECTED_LIMIT`, zéro résultat. |
| Preuves par document classé | 20 | `REJECTED_LIMIT`, zéro résultat. |
| Extrait conservé par preuve | 1 000 caractères | Troncature déterministe et offsets conservés. |

Le service ne lit jamais le stockage privé ni les originaux. Il ne crée aucune route HTTP. Les futures vues patron/collaborateur nécessiteront un contrat de lecture SEC-01, une policy de classification de données, une pagination et une minimisation stricte des extraits.

## 9. Critères de sortie

DCE-CLASSIFICATION-01 doit démontrer :

1. le classement déterministe et sourcé de RC, CCAP, CCTP, AE, BPU, DPGF, plan, annexe et rectificatif ;
2. l’absence de classement positif pour un document non extrait ou sans règle reconnue ;
3. le passage explicite en revue lorsque des familles concurrentes sont à égalité ;
4. l’historique de classification courante, la correction par succession et le réemploi d’une même famille sans doublon ;
5. l’isolation tenant, l’acteur `SYSTEM`, le manifest canonique, la révision optimiste et le replay idempotent ;
6. l’immutabilité PostgreSQL des exécutions, résultats et preuves ;
7. l’absence de fuite de texte ou de métadonnées sensibles dans événement, outbox ou HTTP ;
8. la mise à jour cohérente de `classification_readiness` sans modifier les originaux admis.

## 10. Non-objectifs

Ce slice ne fait ni OCR, ni reconnaissance visuelle de plans, ni analyse de tableaux complexes, ni extraction de prix, ni vérification de pièces, ni contrôle de conformité, ni avis juridique, ni calcul de délai, ni génération de réponse, ni décision Go/No-Go, ni dépôt. Il ne déclare aucune pièce manquante et ne classe pas un document sur son seul nom de fichier.

## Références

[1]: https://entreprendre.service-public.gouv.fr/vosdroits/F32130 "Service Public Entreprendre — Examiner les documents de la consultation d’un marché public, vérifié le 1er avril 2026"
