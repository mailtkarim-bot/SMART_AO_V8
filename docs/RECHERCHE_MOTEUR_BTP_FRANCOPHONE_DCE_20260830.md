# Recherche — moteur BTP francophone pour la phase DCE

**Projet :** SMART_AO_V8
**Date :** 30 août 2026
**Auteur :** Manus AI
**Périmètre :** modèles Hugging Face, OCR/VLM, compréhension des pièces DCE, plans, tableaux et jargon BTP français.

## 1. Conclusion exécutive

La recherche ne révèle pas de modèle Hugging Face qui réunisse actuellement, de manière démontrée, les cinq compétences nécessaires à SMART_AO_V8 : lecture fiable des plans, extraction structurée des pièces écrites, maîtrise du jargon BTP français, compréhension des clauses de commande publique et production de preuves auditables. **Horama-BTP v2 est spécialisé BTP, mais sa fiche décrit principalement l’analyse d’images de chantier et de sécurité. BuildEng est spécialisé en raisonnement civil et structurel, mais il est textuel, orienté anglais et ne comprend pas nativement les plans ou PDF.**

La voie techniquement et juridiquement la plus solide est donc un **moteur composé**, et non un modèle unique :

1. extraction native déterministe quand le PDF/DOCX/XLSX contient déjà du texte ;
2. OCR documentaire local pour les scans et tableaux ;
3. VLM généraliste multilingue pour les plans, diagrammes et mises en page complexes ;
4. RAG privé sur les documents du DCE et sur un corpus normatif autorisé ;
5. modèle métier BTP utilisé comme générateur de suggestions, jamais comme autorité ;
6. validation déterministe, conservation des extraits, coordonnées et hash, puis revue humaine.

**Recommandation immédiate :** ne pas intégrer Horama-BTP v2 ou BuildEng dans le chemin commercial de production avant clarification de licence, corpus et qualité. Construire d’abord un POC local derrière le port d’extraction DCE existant, avec Qwen2.5-VL-7B-Instruct pour les pages visuelles et LightOnOCR-2-1B pour l’OCR, puis mesurer sur 20 à 30 DCE français autorisés.

## 2. Ce que le DCE impose au système

Les documents de la consultation comprennent notamment le règlement de consultation, le CCAP, le CCTP ou cahier des charges, les documents financiers et l’acte d’engagement. Le CCTP peut contenir des spécifications techniques, des normes et des plans ; le CCAP porte notamment les dispositions juridiques et financières, les délais, la sous-traitance, les garanties, les paiements et les pénalités [1]. Les CCAG ne sont pas nécessairement joints au DCE et ne s’appliquent que si le marché s’y réfère expressément [2].

| Capacité attendue | Preuve exigée dans SMART_AO_V8 | Risque si elle est confiée au seul LLM |
|---|---|---|
| Identifier la pièce et sa version | type de document, page/feuillet, hash, révision | confusion entre ancienne et nouvelle pièce |
| Lire les clauses | extrait exact, offsets ou coordonnées, page | hallucination ou paraphrase non vérifiable |
| Lire les tableaux | cellule, ligne/colonne, unité, valeur brute | perte d’unité, décimale ou alignement |
| Comprendre un plan | page, zone, bbox, légende, échelle si lisible | interprétation d’un symbole ou d’une cote erronée |
| Relier CCTP–DPGF–BPU | identifiant de poste, unité, quantité, clause source | faux rapprochement lexical |
| Détecter une contradiction | deux extraits indépendants et qualification | conclusion juridique sans preuve |
| Suggérer un risque | catégorie, sévérité, confiance, justification | conseil présenté comme décision |
| Appliquer le droit français | source normative datée et versionnée | mélange de régimes ou de clauses types |

Le système doit donc distinguer **extraction**, **interprétation**, **règle déterministe** et **décision humaine**. Une réponse sans source localisable ne doit pas alimenter une décision GO/NO-GO.

## 3. Vérification des candidats Hugging Face

| Candidat | Entrée native | Français documenté | Spécialisation BTP | Licence affichée | Classement |
|---|---|---:|---:|---|---|
| `Horama/Horama_BTP_v2` | image | tag French, mais exemples image chantier | très forte pour sécurité et avancement visuel | AGPL-3.0, accès conditionné | photo chantier, pas DCE principal |
| `Horama/Horama_BTP` | image | tag French, mais même limite | forte pour inspection et JSON métier | AGPL-3.0 | expérimentation photo uniquement |
| `Irfanuruchi/qwen2.5-1.5b-buildeng` | texte | fiche English | raisonnement civil/structurel | Apache-2.0 affichée | petit expert texte à tester |
| `Irfanuruchi/qwen2.5-3b-buildeng` | texte | fiche English | raisonnement civil/structurel | `qwen-research` ; usage commercial à clarifier auprès d’Alibaba Cloud | non retenu pour production commerciale |
| `Qwen/Qwen2.5-VL-7B-Instruct` | image + texte | Qwen annonce le français parmi plus de 29 langues | généraliste, documents, tableaux, graphiques, layouts | Apache-2.0 affichée | VLM principal à tester |
| `lightonai/LightOnOCR-2-1B` | image de page | 11 langues, couverture française annoncée | OCR, PDF, scans, tableaux, formulaires | Apache-2.0 affichée | OCR documentaire principal à tester |
| `cstr/nanonets-ocr-s-crispembed-GGUF` | image | français annoncé parmi 12+ langues | OCR documentaire léger et local | Apache-2.0 affichée, sous réserve amont | solution de repli locale |
| `nvidia/nemotron-ocr-v2` | image | variante documentée sans français | OCR/layout multilingue | NVIDIA Open Model License | écarté du POC français initial |

### Horama-BTP v1 et v2

Les fiches officielles décrivent une transformation **image vers JSON** de photographies de chantier. Les sorties annoncées couvrent progression, EPI, dangers, qualité, matériaux, équipements, logistique, environnement, preuves et confiance. La v2 ajoute une adaptation orientée sécurité sur plus de 10 000 images et conserve le schéma structuré. Cependant, les exemples, les modalités d’entrée et les capacités explicites portent sur des photos de chantier, pas sur les CCTP, CCAP, DPGF, BPU, DQE ou plans PDF [3] [4].

La présence des tags `French` et `btp` ne prouve pas une maîtrise du français contractuel, des DTU, NF DTU, Eurocodes, CCAG Travaux ou du vocabulaire des marchés publics. La licence AGPL-3.0 doit en outre faire l’objet d’une revue juridique avant tout usage dans un produit propriétaire. **Horama peut rester une brique optionnelle d’analyse de photos chantier, isolée du chemin DCE commercial.**

### BuildEng 1.5B et 3B

BuildEng 1.5B est un causal language model spécialisé en génie civil, structure et construction. La fiche mentionne poutres, poteaux, dalles, fondations, murs de soutènement, séquençage, étaiement, excavation et inspection. Elle précise toutefois que les données sont synthétiques et simplifiées, que les workflows Eurocode ne sont pas pleinement implémentés et que le modèle peut commettre des erreurs de raisonnement, d’arithmétique ou de routage [5].

BuildEng 3B apporte davantage de profondeur attendue, mais sa fiche indique explicitement `qwen-research` et rappelle que la licence amont Qwen2.5-3B-Instruct limite par défaut l’usage à la recherche et à l’évaluation non commerciales ; un usage commercial requiert une licence appropriée d’Alibaba Cloud [6]. Les deux variantes sont textuelles et ne peuvent pas lire directement les plans ou les scans.

### Qwen2.5-VL, LightOnOCR et alternatives

Qwen2.5-VL-7B-Instruct est le meilleur candidat généraliste pour le POC visuel : la fiche annonce l’analyse de textes, graphiques, icônes et layouts, ainsi que des sorties structurées pour scans, formulaires et tableaux. Elle rapporte notamment DocVQA 95,7, InfoVQA 82,6, ChartQA 87,3 et OCRBench 864 ; ces scores restent des benchmarks généraux, non une validation sur le DCE français [7].

LightOnOCR-2-1B est mieux positionné pour l’étape OCR : il traite PDF, scans, images, tableaux, formulaires et mises en page complexes, annonce une couverture française renforcée et propose des variantes bbox ainsi que le fine-tuning LoRA [8]. Il doit être utilisé pour transcrire et localiser, pas pour décider si une clause est juridiquement acceptable.

Nanonets-OCR-s en GGUF constitue une option locale légère avec français annoncé, mais sa fiche signale une documentation incomplète du corpus d’entraînement amont [9]. Nemotron OCR v2 fournit une architecture intéressante de détection, reconnaissance et relations de layout, mais la liste multilingue explicitement documentée ne comprend pas le français et le déploiement suppose une pile NVIDIA/CUDA plus lourde [10].

## 4. Architecture cible pour SMART_AO_V8

Le dépôt possède déjà une frontière utile : `DceDocumentExtractionService` lit le document depuis le stockage privé, vérifie taille, taille réelle et SHA-256, puis transmet une projection bornée au dispatcher. Le port `AdvancedDocumentExtractionPort` impose une sortie `ExtractionProjection` composée de fragments avec `locator_json`, texte, statut, code d’échec et version d’extracteur. L’adaptateur OCR existant retourne déjà un statut `REVIEW_REQUIRED` et conserve les boîtes lorsque le moteur les fournit.

La prochaine architecture doit réutiliser cette frontière au lieu d’introduire une route HTTP qui appellerait directement un modèle :

```text
DCE admis + vérifié
        |
        v
Extraction native PDF/DOCX/XLSX
        | texte exploitable ?
        +---- oui ----> fragments déterministes + hash + page/cellule
        |
        non
        v
Rendu privé des pages PDF / images
        |
        +--> LightOnOCR-2-1B ou OCR local --> texte + bbox + confiance
        |
        +--> Qwen2.5-VL-7B -----------------> plan/tableau/layout + JSON proposé
        |
        +--> Horama-BTP (option photos) ------> sécurité/avancement visuel
        |
        v
Normalisation et validation de schéma
        |
        v
RAG privé : DCE + sources normatives autorisées
        |
        v
Extraction de clauses / rapprochement / contradictions
        |
        v
Risque proposé avec preuves
        |
        v
Revue humaine obligatoire avant décision
```

Le futur port doit rester agnostique du fournisseur, par exemple `DceMultimodalExtractionPort`, et ne retourner que des projections bornées. Il ne doit jamais exposer une clé de stockage, envoyer un document à un service externe sans décision explicite de confidentialité, ni écrire directement dans les tables de décision.

Une projection minimale devrait contenir :

```text
DocumentExtractionProjection
- extractor_id
- extractor_version
- input_sha256
- status: COMPLETED | REVIEW_REQUIRED | FAILED_SAFE | REJECTED_LIMIT
- source_language
- pages_processed
- fragments[]
  - ordinal
  - locator: page, bbox, sheet, cell, paragraph
  - text
  - text_sha256
  - confidence
  - evidence_kind
- warnings[]
- model_license_classification
```

La couche d’analyse de clauses doit ensuite retourner une proposition distincte :

```text
ClauseFindingProposal
- category: penalty | guarantee | insurance | subcontracting | variant | qualification | payment | delay | environmental | other
- document_id
- source_fragment_id
- normalized_subject
- extracted_values
- confidence
- rationale
- requires_human_review: true
- model_id
- prompt_version
```

Aucune proposition ne doit être convertie automatiquement en risque accepté, atténué ou décision GO/NO-GO. Les transitions existantes du domaine restent la seule voie d’évolution de l’état.

## 5. Corpus normatif et droit français

La ressource la plus fiable trouvée n’est pas un fine-tune Hugging Face, mais un ensemble de sources officielles à versionner dans une couche de connaissance contrôlée. La DAJ publie les CCAG et renvoie notamment à l’arrêté du 30 mars 2021 relatif au CCAG Travaux [2]. Service-Public rappelle que le CCAP regroupe les dispositions juridiques et financières et que le CCTP contient les spécifications techniques, normes et plans [1].

Les données ouvertes de la commande publique, telles que les données essentielles publiées sur data.gouv.fr, décrivent surtout les métadonnées des marchés — nature, objet, attributaire et date — et non un corpus complet de CCTP/CCAP/DPGF librement réutilisable [11]. Il ne faut donc pas considérer l’open data des marchés comme un corpus d’entraînement DCE.

Le corpus initial du POC doit être construit à partir de documents dont SMART_AO_V8 détient l’autorisation d’usage : DCE anonymisés fournis par l’utilisateur, modèles internes autorisés, textes réglementaires officiels et documents dont les licences autorisent explicitement l’indexation. Les normes NF/DTU et certains documents contractuels peuvent être protégés ; ils ne doivent pas être aspirés ou redistribués sans vérification des droits.

## 6. Protocole POC sur 20 à 30 DCE

Le POC doit utiliser 20 à 30 dossiers réels ou anonymisés, représentatifs des principaux cas de défaillance. Chaque dossier doit conserver la structure multi-pièces, les versions, les PDF natifs et scannés, les tableaux et, lorsque possible, les plans.

| Lot d’évaluation | Cas à inclure | Mesure principale |
|---|---|---|
| Pièces écrites natives | RC, CCAP, CCTP, AE, DQE | exactitude du type et extraction des sections |
| Pièces scannées | scans inclinés, qualité faible, cachets | CER/WER, rappel des clauses |
| Financier | DPGF, BPU, DQE avec unités et décimales | exactitude poste/unité/quantité |
| Plans | plans PDF raster/vectoriels, légendes, coupes | rappel des éléments et localisation bbox |
| Clauses sensibles | pénalités, garanties, assurances, sous-traitance | précision/rappel par catégorie |
| Croisements | clause–poste BPU/DPGF | précision des liens justifiés |
| Contradictions | CCAP vs CCTP vs BPU | précision des alertes avec deux preuves |
| Langage métier | abréviations, lots, variantes, VISA/DET/OPC/SPS | exactitude lexicale et normalisation |

Les annotations de référence doivent être produites par un professionnel BTP, avec une seconde revue pour les clauses juridiques. Les résultats à publier sont au minimum :

- taux de transcription exact ou acceptable par type de document ;
- précision, rappel et F1 par catégorie de clause ;
- exactitude des valeurs et unités dans les tableaux ;
- précision et rappel des rapprochements CCTP–DPGF–BPU ;
- précision des contradictions inter-documents ;
- taux de sorties sans preuve ;
- taux d’hallucination ;
- latence, mémoire et coût par dossier ;
- taux de cas nécessitant une revue humaine.

Seuils de décision proposés pour le prototype : une alerte juridique ou financière ne peut être considérée exploitable que si elle possède une preuve localisable et atteint au moins 0,90 de précision sur l’échantillon de validation. Le rappel peut être inférieur au départ, mais les éléments non détectés doivent être signalés comme limite. **Ces seuils sont des critères de produit proposés, pas des résultats observés.**

## 7. Décision d’intégration

| Décision | Modèle ou composant | Justification |
|---|---|---|
| À tester immédiatement | LightOnOCR-2-1B | OCR français/document, tableaux, local, Apache-2.0 affichée |
| À tester immédiatement | Qwen2.5-VL-7B-Instruct | plans, layouts, tableaux et français général, Apache-2.0 affichée |
| À isoler en expérimentation | Horama-BTP v2 | très bon signal photo chantier, AGPL-3.0, pas de preuve DCE |
| À isoler en expérimentation texte | BuildEng 1.5B | raisonnement BTP, mais anglais/synthétique et non multimodal |
| À ne pas brancher commercialement sans licence | BuildEng 3B | restriction amont Qwen Research explicitement signalée |
| À garder comme repli OCR | Nanonets-OCR-s GGUF | français annoncé, local léger, documentation amont à auditer |
| À écarter du POC français | Nemotron OCR v2 | français non documenté dans la variante multilingue et pile GPU lourde |

La réponse à la question initiale est donc la suivante : **le meilleur “modèle” pour SMART_AO_V8 n’est pas Horama ou BuildEng seuls. Le meilleur premier assemblage est extraction native + LightOnOCR-2-1B + Qwen2.5-VL-7B + RAG DCE/normatif privé + règles déterministes + revue humaine.** Horama et BuildEng pourront être évalués comme experts auxiliaires sur leurs sous-domaines, après revue de licence et mesure sur les données de l’application.

## 8. Prochain micro-lot de code recommandé

Le prochain lot sécurisé doit être un lot d’infrastructure applicative, sans changement de décision métier :

1. introduire un port `DceMultimodalExtractionPort` et ses DTOs immuables ;
2. ajouter un adaptateur local de rendu de pages et un adaptateur OCR/VLM derrière feature flag ;
3. réutiliser la vérification d’intégrité et les limites existantes ;
4. normaliser les localisateurs page/bbox/cellule ;
5. produire exclusivement `REVIEW_REQUIRED` pour toute sortie IA ;
6. ajouter tests unitaires de schéma, limites, intégrité, absence de réseau et tenant-scoping ;
7. ajouter un test d’intégration avec un faux modèle déterministe ;
8. réserver les appels aux vrais modèles et le benchmark réel à une recette séparée, sur corpus autorisé.

Ce découpage permet d’avancer dans le code sans engager SMART_AO_V8 sur une licence, un fournisseur ou une capacité non démontrée.

## Références

[1]: https://entreprendre.service-public.gouv.fr/vosdroits/F32130 "Service-Public Entreprendre — Examiner les documents de la consultation d'un marché public"

[2]: https://www.economie.gouv.fr/daj/commande-publique/reglementation-de-la-commande-publique/cahiers-des-clauses-administratives "Direction des Affaires juridiques — Cahiers des clauses administratives générales et techniques"

[3]: https://huggingface.co/Horama/Horama_BTP "Hugging Face — Horama/Horama_BTP"

[4]: https://huggingface.co/Horama/Horama_BTP_v2 "Hugging Face — Horama/Horama_BTP_v2"

[5]: https://huggingface.co/Irfanuruchi/qwen2.5-1.5b-buildeng "Hugging Face — Qwen2.5-1.5B BuildEng"

[6]: https://huggingface.co/Irfanuruchi/qwen2.5-3b-buildeng "Hugging Face — BuildEng V8 3B"

[7]: https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct "Hugging Face — Qwen2.5-VL-7B-Instruct"

[8]: https://huggingface.co/lightonai/LightOnOCR-2-1B "Hugging Face — LightOnOCR-2-1B"

[9]: https://huggingface.co/cstr/nanonets-ocr-s-crispembed-GGUF "Hugging Face — Nanonets-OCR-s CrispEmbed GGUF"

[10]: https://huggingface.co/nvidia/nemotron-ocr-v2 "Hugging Face — NVIDIA Nemotron OCR v2"

[11]: https://www.data.gouv.fr/datasets/marches-publics "data.gouv.fr — Marchés publics"
