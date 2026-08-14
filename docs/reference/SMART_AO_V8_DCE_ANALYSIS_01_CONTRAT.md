# SMART_AO V8 — DCE-ANALYSIS-01 : registre d’analyse déterministe du règlement de consultation

**Statut :** normatif.
**Périmètre :** lecture interne de fragments extraits déjà persistés afin de relever, avec leurs preuves, les consignes explicites d’un règlement de consultation (RC).
**Dépendances :** SEC-01, DCE-ADMIT-01, DCE-STAGING-01, DCE-UPLOAD-01, DCE-RETENTION-01 et DCE-DOCUMENT-EXTRACTION-01.

## 1. But et frontière

DCE-ANALYSIS-01 fournit au collaborateur et au cockpit patron un premier relevé **reproductible, sourcé et non décisionnel** des règles de réponse exprimées dans un règlement de consultation. Il ne lit aucun original : son unique entrée est le registre append-only des fragments de `DCE-DOCUMENT-EXTRACTION-01`.

> Une observation DCE-ANALYSIS-01 signifie seulement qu’une règle déterministe a trouvé une formulation dans un fragment précis. Elle ne signifie ni qu’une pièce est juridiquement exigible, ni que le dossier est complet, ni que l’entreprise est admissible, ni qu’il faut répondre au marché.

Le RC est le mode d’emploi de la réponse : il peut notamment indiquer les pièces de candidature, les contraintes de dépôt, la visite, le contenu attendu de l’offre, la date limite, la validité, les critères et pondérations, ainsi que la possibilité de négocier. Ces catégories structurent le catalogue fermé du présent slice, sans se substituer à la lecture humaine du DCE. [1]

## 2. Préconditions non négociables

L’analyse ne peut être demandée que par un service interne avec `actor_kind = SYSTEM`. Aucun endpoint HTTP, utilisateur, collaborateur, patron, jeton navigateur, webhook ou contenu du DCE ne peut fabriquer une commande d’analyse.

| Fait relu côté serveur | Condition obligatoire | Refus neutre ou terminal sinon |
|---|---|---|
| DCE | appartient au tenant ; son cycle est `ADMITTED` ou `SUPERSEDED` ; son intégrité est `VERIFIED` | `DCE_VERSION_NOT_ANALYSABLE` |
| Extraction source | appartient au même tenant et au DCE ; son état est `COMPLETED` | `DCE_EXTRACTION_COMPLETED_REQUIRED` |
| Fragment source | appartient à l’extraction relue ; texte, hash et ordinal cohérents | `DCE_ANALYSIS_SOURCE_FRAGMENT_REQUIRED` |
| Manifest d’entrée | hash SHA-256 canonique des fragments effectivement analysés | `DCE_ANALYSIS_INPUT_MANIFEST_REQUIRED` |
| Commande | acteur `SYSTEM`, IDs uniques, statuts et catalogue fermé | `DCE_ANALYSIS_SYSTEM_ACTOR_REQUIRED` ou erreur de contrat |

Une DCE retirée, intègre seulement partiellement, non admise ou sans extraction terminée ne produit aucune analyse. Une erreur de lecture du registre, une limite dépassée ou une incohérence de source produit un résultat terminal sûr, sans observation.

## 3. Unité d’analyse et ordre canonique

Une analyse couvre une `DceVersion` entière. Elle réunit exclusivement les fragments des extractions `COMPLETED` de ses documents. Les fragments sont ordonnés canoniquement par `(dce_document_id, extraction_id, ordinal)` sous leur représentation UUID normalisée, puis par `id` de fragment si nécessaire.

Le `input_manifest_sha256` est le SHA-256 UTF-8 de lignes séparées par un LF réel, une ligne par fragment :

```text
<dce_document_id>|<extraction_id>|<fragment_id>|<ordinal>|<text_sha256>
```

Le manifest ne contient jamais le texte, le nom de fichier, la clé privée, le hash de l’original ni une donnée financière. Une nouvelle version d’analyse est indispensable si le catalogue de règles, l’algorithme ou la normalisation changent ; un résultat existant n’est jamais modifié.

## 4. Catalogue fermé des observations RC

Les règles sont déterministes, versionnées et fondées sur des expressions normalisées. Elles ne font ni modèle probabiliste, ni appel LLM, ni OCR, ni inférence juridique. Une même formulation peut produire plusieurs observations lorsqu’elle correspond explicitement à plusieurs catégories.

| `requirement_kind` | Objet métier signalé | Exemples de déclencheurs recherchés | Ce que le slice ne conclut jamais |
|---|---|---|---|
| `RC_DOCUMENT_CANDIDATURE` | Pièce ou modalité de candidature | `DC1`, `DC2`, `DUME`, `eDUME`, `DC4`, `candidature` | Que la pièce est disponible, valide ou suffisante. |
| `RC_CONTENT_OFFER` | Pièce attendue dans l’offre | `mémoire technique`, `acte d'engagement`, `BPU`, `DPGF`, `offre` | Que le document doit être généré, signé ou chiffré. |
| `RC_SUBMISSION_DEADLINE` | Date ou heure de remise signalée | `date limite`, `date de remise`, `avant le`, `heure limite` | Une échéance calculée, un fuseau, un rappel ou la recevabilité du dépôt. |
| `RC_RESPONSE_CHANNEL` | Canal ou modalité de dépôt | `profil d'acheteur`, `plateforme`, `dépôt électronique`, `dématérialisé` | Que le canal identifié est disponible ou obligatoire en droit. |
| `RC_FILE_CONSTRAINT` | Format, taille ou signature évoqués | `format`, `taille`, `signature électronique`, `PDF` | La conformité d’un fichier ou d’une signature. |
| `RC_SITE_VISIT` | Visite de site ou de lieux évoquée | `visite`, `visite des lieux`, `rendez-vous sur site` | Qu’elle est obligatoire, planifiée ou accomplie, sauf signal lexical explicite. |
| `RC_AWARD_CRITERION` | Critère d’attribution ou pondération évoqué | `critère`, `pondération`, `valeur technique`, `prix` | Un calcul de note, une pondération numérique fiable ou une stratégie de prix. |
| `RC_NEGOTIATION` | Négociation mentionnée | `négociation`, `négocier`, `sans négociation` | Que l’acheteur négociera effectivement. |
| `RC_OFFER_VALIDITY` | Durée ou validité d’offre évoquée | `validité de l'offre`, `délai de validité` | Une date d’expiration calculée ou une obligation juridique. |

Les règles retiennent une fenêtre de texte minimale qui comprend le déclencheur, bornée à 1 000 caractères. Toute observation contient cette fenêtre, son `rule_id` fermé, sa version et au moins une source de fragment. Les données non textuelles extraites ultérieurement, les tableaux financiers, plans et pièces graphiques sont hors périmètre.

## 5. Posture lexicale et absence d’automatisme

Une observation porte une `directive` fermée : `REQUIRED_SIGNAL`, `OPTIONAL_SIGNAL` ou `UNSPECIFIED`. Cette posture est une lecture lexicale limitée de marqueurs tels que « obligatoire », « doit », « exigé », « facultatif », « peut » ou « possible ». Elle ne vaut pas interprétation de la clause, ne résout pas les négations complexes et n’est jamais utilisée pour bloquer une étape utilisateur.

L’absence d’observation ne démontre jamais l’absence d’exigence. Le DCE peut être incomplet, la clause peut être dans une image, un plan, un scan non OCRisé, un format non pris en charge ou une formulation que ce catalogue ne reconnaît pas. SMART_AO doit donc afficher ultérieurement « non détecté par le catalogue » et non « non exigé ».

## 6. Registre immuable

Le slice crée trois tables tenant-scopées et append-only.

| Table | Grain | Contenu autorisé |
|---|---|---|
| `dce_rc_analysis_runs` | Une exécution déterministe par DCE, manifest, analyseur et version. | Statut terminal, compteurs, manifest, analyseur et code d’échec fermé. |
| `dce_rc_requirement_observations` | Un constat d’une règle sur une exécution terminée. | Type fermé, directive lexicale, règle/version et fenêtre textuelle bornée. |
| `dce_rc_requirement_sources` | Une preuve de fragment par observation. | Référence de fragment et offsets UTF-8 de la fenêtre dans ce fragment. |

L’unicité fonctionnelle d’une exécution est `(tenant_id, dce_version_id, input_manifest_sha256, analyzer_id, analyzer_version)`. Les trois tables refusent `UPDATE` et `DELETE` par triggers PostgreSQL. Les observations et sources ne peuvent être insérées que pour une exécution `COMPLETED`, du même tenant et de la même DCE ; ces relations sont vérifiées par FK composites, contrôle applicatif et trigger parent.

Les statuts fermés sont : `COMPLETED`, `NO_RC_MARKER`, `REJECTED_LIMIT` et `FAILED_SAFE`. Seul `COMPLETED` peut contenir des observations. `NO_RC_MARKER` est un résultat utile mais n’affirme pas qu’il n’y a aucun RC dans le DCE.

## 7. Transaction, idempotence et événements

Le service de calcul relit les fragments, applique les règles, construit le manifest puis transmet au dispatcher une commande `RecordDceRcAnalysisCommand`. Dans une transaction PostgreSQL unique, le handler verrouille le DCE et les sources, revalide le manifest, ajoute l’exécution, les observations et leurs preuves, puis le dispatcher ajoute événement, outbox et receipt.

| Élément | Règle |
|---|---|
| Commande | `RecordDceRcAnalysis`, identifiant et clé d’idempotence déterministes depuis `(dce_version_id, input_manifest_sha256, analyzer_id, analyzer_version)`. |
| Replay | Même tenant, acteur système, type et clé : receipt existant, sans doublon. |
| Collision fonctionnelle | Résultat terminal identique relu ; jamais réécrit. |
| Événement | `DCE_RC_ANALYSIS_RECORDED`, agrégat `DCE_RC_ANALYSIS`. |
| Outbox | Sujet `cockpit_projection`, contenant uniquement IDs, statut et compteurs. |
| Contenu interdit | Texte, extrait, offsets, locators détaillés, hashes de document, nom de fichier, prix, clé ou binaire. |

Le slice n’altère ni le corpus admis, ni les fragments d’extraction, ni les classifications documentaires existantes, ni `analysis_readiness`. La projection de readiness et la classification réglementaire globale feront l’objet d’un contrat ultérieur après validation métier des observations.

## 8. Limites, sécurité et confidentialité

| Contrôle | Limite | Effet au dépassement |
|---|---:|---|
| Fragments `COMPLETED` par analyse | 100 000 | `REJECTED_LIMIT`, zéro observation. |
| Caractères analysés | 10 000 000 | `REJECTED_LIMIT`, zéro observation. |
| Observations persistées | 20 000 | `REJECTED_LIMIT`, zéro observation. |
| Sources par observation | 1 dans ce slice | Toute future agrégation multi-source requiert un nouveau contrat. |
| Fenêtre d’extrait | 1 000 caractères | Fenêtre tronquée de façon déterministe ; offsets conservés. |

Le service n’accède ni à la quarantaine privée ni aux octets d’origine. Aucune route HTTP de lecture ou d’écriture n’est ajoutée. L’accès patron ou collaborateur aux futures vues devra suivre un contrat spécifique SEC-01, une policy de classification et une pagination qui ne divulgue pas le texte brut du DCE par défaut.

## 9. Critères de sortie

DCE-ANALYSIS-01 doit démontrer :

1. la détection reproductible des familles RC fermées sur des fragments persistés ;
2. le rattachement de chaque constat à un fragment, des offsets cohérents et un extrait borné ;
3. l’absence d’accès aux originaux, de LLM, d’OCR, de calcul financier et de décision humaine automatisée ;
4. l’acteur `SYSTEM` obligatoire, l’isolation tenant et la révalidation transactionnelle de chaque source ;
5. un replay sans doublon, une unicité fonctionnelle et des tables append-only PostgreSQL ;
6. un résultat terminal sûr pour une DCE non analysable, un manifest incohérent ou une limite dépassée ;
7. un événement/outbox sans texte ni donnée confidentielle ;
8. l’absence d’affirmation « non exigé » lorsqu’aucun signal n’est trouvé.

## 10. Non-objectifs

Ce slice ne réalise ni qualification juridique, ni conseil de dépôt, ni vérification de conformité, ni calcul d’échéance, ni pondération, ni score, ni choix Go/No-Go, ni prix, ni génération de pièces, ni soumission. Il ne classe pas définitivement tous les documents du DCE, ne traite pas l’OCR, les plans, images, DWG, tableaux complexes ou fichiers non extraits, et ne rend aucun fragment disponible en HTTP.

## Références

[1]: https://entreprendre.service-public.gouv.fr/vosdroits/F32130 "Service Public Entreprendre — Examiner les documents de la consultation d’un marché public, vérifié le 1er avril 2026"
[2]: https://entreprendre.service-public.gouv.fr/vosdroits/F32106 "Service Public Entreprendre — Remettre la réponse à un marché public et échanger avec l’acheteur public, vérifié le 1er avril 2026"
