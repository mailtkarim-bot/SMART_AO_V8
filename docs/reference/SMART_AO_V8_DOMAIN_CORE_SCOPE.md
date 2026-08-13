# SMART_AO V8 — Noyau de domaine et périmètre du premier vertical slice

**Statut :** proposition de cadrage, à valider avant tout code V8.  
**But :** remplacer le transport implicite par `mission.context` par un graphe de données traçable, sans construire prématurément une plateforme complète.

## 1. Décision de conception

Le blueprint proposé dans la passe d’autopsie est **correct dans son axe central** : le système doit être organisé autour de la preuve, des faits et des décisions, et non autour d’agents ou d’étapes de workflow. Il faut toutefois éviter de créer immédiatement une douzaine de tables, un Event Bus durable, un runtime d’agents et un graphe complet de microservices.

> **V8 démarre par un monolithe modulaire. Son premier vertical slice rend une analyse de DCE traçable de bout en bout, sans agent LLM obligatoire.**

La responsabilité de l’IA sera introduite après démonstration du flux déterministe et de la provenance. La sortie initiale est une analyse relisible et sourcée, non une décision autonome.

## 2. Objets de domaine : indispensables et différables

| Objet | Rôle métier | Premier vertical slice | Décision |
|---|---|---:|---|
| `TenderCase` | Dossier d’appel d’offres analysé pour une entreprise. | Oui | Entité racine métier. Le nom évite l’ambiguïté de `Mission`, actuellement technique dans V7.1. |
| `AnalysisRun` | Exécution versionnée d’une analyse sur un instantané de documents et de règles. | Oui | Persisté ; il rend la reproductibilité possible. |
| `Document` | Identité logique d’une pièce du DCE. | Oui | Persisté. |
| `DocumentVersion` | Contenu immuable d’une pièce à un moment donné. | Oui | Persisté et hashé. |
| `ArtifactRef` | Référence neutre au stockage du binaire ou d’un export. | Oui | Value object ou table légère ; le domaine ne dépend pas de S3, disque ou MinIO. |
| `Chunk` | Segment technique destiné au parsing, retrieval ou contexte modèle. | Oui, minimal | Persisté seulement si nécessaire pour la recherche ; ce n’est pas une vérité métier. |
| `Evidence` | Extrait localisable d’une version de document qui soutient une affirmation. | Oui | Pivot de traçabilité. |
| `Fact` | Donnée normalisée dérivée d’une ou plusieurs evidences. | Oui | Ex. montant HT, délai, taux de pénalité. |
| `Requirement` | Obligation explicitement imposée par le DCE. | Oui | Indispensable à la valeur AO : « le DCE exige X » est distinct de « l’entreprise satisfait X ». |
| `Rule` | Règle métier/réglementaire identifiée et versionnée. | Oui, minimal | Code, version, référence, date d’effet et implémentation référencée. |
| `Assessment` | Évaluation intermédiaire de faits, exigences et règles. | Non, comme entité autonome | Commence comme value object typé dans un `Finding`; devient entité persistée lorsqu’un agent cognitif ou une revue humaine le justifie. |
| `Finding` | Conclusion métier normalisée, justifiée et soumise à revue. | Oui | Objet affiché dans le rapport et l’interface. |
| `Calculation` | Résultat de calcul déterministe avec inputs, formule et trace. | Oui, si le cas pilote l’exige | Objet séparé du `Finding`. |
| `ReportSnapshot` | Projection versionnée de findings et calculs approuvés. | Oui, minimal | Ne recalcule jamais la connaissance. |
| `AgentRun` | Trace d’une exécution IA ou d’un handler piloté. | Non, sauf agent cognitif pilote | À introduire avec le premier composant modèle. |
| `SubjectRef` | Référence polymorphe contrôlée vers clause, lot, exigence ou pièce. | Oui, value object | Évite un fourre-tout `target/object/type`. |

## 3. Graphe canonique V8

```text
TenderCase
   ├── Document
   │      └── DocumentVersion ──→ ArtifactRef
   │               └── Chunk (technique)
   │
   └── AnalysisRun
           ├── Evidence ──→ DocumentVersion / Chunk
           ├── Fact ──→ Evidence
           ├── Requirement ──→ Evidence
           ├── Finding ──→ Evidence + Fact + Requirement + Rule + Calculation?
           ├── Calculation ──→ Fact + Rule version
           └── ReportSnapshot ──→ Finding + Calculation snapshots
```

La règle structurante est la suivante : **un `Finding` ne contient pas une nouvelle vérité. Il référence et synthétise des vérités déjà persistées.**

## 4. Invariants du noyau

| Identifiant | Invariant | Conséquence pratique |
|---|---|---|
| `INV-001` | Une `DocumentVersion` publiée est immuable et porte un hash de contenu. | Une nouvelle pièce ou une pièce modifiée crée une nouvelle version. |
| `INV-002` | Toute `Evidence` référence une version précise de document et une localisation. | Page seule insuffisante ; locator, offsets ou cellule doivent être disponibles selon le format. |
| `INV-003` | Tout `Fact` métier porte au moins une evidence, ou le statut explicite `USER_ASSERTED` / `SYSTEM_DERIVED`. | Aucune donnée financière silencieusement injectée dans un contexte global. |
| `INV-004` | Tout `Requirement` est distingué d’un fait sur l’entreprise. | L’obligation du DCE et la conformité de l’entreprise ne se confondent jamais. |
| `INV-005` | Tout `Finding` porte ses sources, son statut et la règle ou l’évaluation qui le justifie. | Le rapport peut remonter vers une pièce et une version exactes. |
| `INV-006` | Toute `Calculation` monétaire utilise `Decimal`/NUMERIC, une devise et une politique d’arrondi explicite. | Aucun `float` ne traverse la frontière de calcul. |
| `INV-007` | Une `AnalysisRun` lie le jeu de documents, les versions de règles et les versions techniques utilisées. | Un résultat peut être rejoué ou comparé. |
| `INV-008` | Un `ReportSnapshot` est une projection ; il ne réextrait, ne déduit et ne recalcule pas. | Un rapport reste cohérent avec l’analyse qui l’a produit. |
| `INV-009` | Le RAG ne produit que des candidats à evidence. | Un score de similarité n’est jamais une confiance métier. |
| `INV-010` | Un LLM ne crée pas directement une valeur financière faisant foi. | Il propose une évaluation ou une extraction à valider ; le Math Engine calcule. |

## 5. États minimaux

Les state machines doivent rester courtes dans le premier vertical slice.

| Entité | États initiaux | Transitions autorisées |
|---|---|---|
| `DocumentVersion` | `UPLOADED`, `PROCESSING`, `READY`, `FAILED`, `QUARANTINED` | `UPLOADED → PROCESSING → READY/FAILED`; `QUARANTINED` est terminal pour cette version. |
| `AnalysisRun` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` | Les artefacts finaux sont immuables après `SUCCEEDED`. |
| `Fact` | `CANDIDATE`, `VERIFIED`, `CONFLICTING`, `REJECTED`, `SUPERSEDED` | Une correction crée un nouveau fait ou une supersession, pas l’écrasement du fait ancien. |
| `Finding` | `DRAFT`, `NEEDS_REVIEW`, `ACCEPTED`, `REJECTED`, `SUPERSEDED` | Une conclusion publiée est remplacée par une nouvelle version, non modifiée in place. |
| `Calculation` | `REQUESTED`, `COMPLETED`, `FAILED`, `INVALIDATED` | `INVALIDATED` lorsqu’une entrée ou règle source est supersédée. |
| `ReportSnapshot` | `DRAFT`, `PUBLISHED`, `SUPERSEDED` | Publication sur snapshot de findings et calculs approuvés. |

## 6. Ce qui est explicitement différé

Le premier vertical slice ne doit pas implémenter : un broker durable, un Event Sourcing complet, un système de plugins, une marketplace de tools, un runtime multi-agent, la gestion de flotte, plusieurs LLM, des boucles autonomes, la synchronisation multi-client ou une ontologie exhaustive du bâtiment.

Ces capacités deviennent admissibles seulement après démonstration du flux central, de l’isolation client, des contrôles de sécurité et des DCE Golden.

## 7. Premier vertical slice recommandé

Le cas pilote est : **un CCAP/RC et une pièce financière de référence, analysés pour produire une exigence, un fait, une règle de pénalité, un calcul et un finding sourcé.**

| Étape | Entrée | Sortie persistée | Test d’acceptation |
|---|---|---|---|
| Ingestion | DCE Golden anonymisé | `TenderCase`, `Document`, `DocumentVersion` | Le hash et la version sont reproductibles. |
| Parsing | Version PDF/DOCX | Chunks avec localisation | La citation mène à la page et l’extrait corrects. |
| Extraction | Sections pertinentes | `Evidence`, `Fact`, `Requirement` | Les faits et obligations sont reliés à la preuve. |
| Évaluation | Faits, exigence, règle versionnée | `Finding` draft / review | La conclusion explique la règle et les sources. |
| Calcul | Facts validés | `Calculation` | Montants en Decimal, politique d’arrondi documentée. |
| Restitution | Findings/calculs approuvés | `ReportSnapshot` | Chaque phrase affichée est navigable vers ses sources. |

## 8. Documents à produire avant le code

Les quatre documents initiaux suffisent. Ils doivent rester courts et réellement utilisés.

| Fichier | Fonction |
|---|---|
| `V8_PRODUCT_CONTRACT.md` | Définit le client pilote, son résultat attendu, les non-objectifs et les critères de succès. |
| `V8_DOMAIN_CORE.md` | Contient les objets ci-dessus, invariants, cardinalités et états. |
| `V8_GOLDEN_DCE_CATALOG.md` | Répertorie les dossiers anonymisés, droits d’usage, faits attendus et scénarios de régression. |
| `V8_MASTER_REBUILD_PLAN.md` | Définit l’ordre des vertical slices, gates et conditions de migration sélective depuis V7.1. |

Un ADR est ajouté uniquement lorsqu’une décision difficile à inverser est validée, par exemple la stratégie de stockage des artefacts, l’isolation multi-client ou la politique de modèles.

## 9. Prochaine décision

La prochaine spécification à produire est `V8_DOMAIN_CORE.md`. Elle doit traduire ce cadrage en contrats précis, mais elle ne doit pas encore contenir d’ORM, d’API, de technologie de recherche ou d’intégration LLM.

L’ordre recommandé est : valider le Product Contract et un Golden DCE ; valider ce noyau de domaine ; définir les contrats d’entrée/sortie du Document Engine et du Math Engine ; puis seulement écrire le premier code V8.

---

*Cette proposition reprend les constats statiques de V7.1. Elle n’est pas une garantie réglementaire, financière ou juridique ; les règles métier et juridiques doivent être versionnées, testées et validées par un responsable compétent avant toute utilisation client.*
