# SMART_AO V8 — Décision sur les state machines, agrégats et transactions

**Statut :** proposition à valider avant toute implémentation V8.  
**Principe :** le domaine définit les transitions et les invariants ; l’infrastructure les persiste et les vérifie. Le premier vertical slice conserve uniquement les états et transactions nécessaires à une analyse de DCE traçable.

## 1. Évaluation du PASS 8.1

La méthode proposée est saine : partir de l’identité, de la propriété, du cycle de vie, des invariants, de la provenance et de l’autorisation avant de choisir Pydantic, SQLAlchemy ou une API. Les trois catégories — preuve immuable, connaissance/décision versionnée, exécution/projection — sont également utiles.

La prudence nécessaire consiste à ne pas transformer immédiatement chaque concept en machine à états longue, en table ou en service. Une state machine n’apporte de valeur que lorsqu’une transition interdite créerait une incohérence, une perte de traçabilité ou une erreur métier visible.

> **Décision : V8 utilisera des transitions de domaine explicites et testées, mais le pilote démarrera avec des cycles de vie minimaux.**

## 2. Noyau d’invariants à appliquer dès le pilote

| ID | Invariant | Priorité | Test attendu |
|---|---|---:|---|
| `INV-001` | Une `DocumentVersion` prête à analyser est immuable et hashée. | P0 | Modifier le contenu ou le hash après publication échoue. |
| `INV-002` | Toute `Evidence` référence une `DocumentVersion` existante et un locator cohérent. | P0 | Une evidence avec version/chunk incompatibles est rejetée. |
| `INV-003` | Tout `Fact` important possède une evidence, ou est explicitement `USER_ASSERTED`/`DERIVED`. | P0 | Un fait financier sans origine est rejeté. |
| `INV-004` | Tout `Requirement` est distinct de l’évaluation de conformité de l’entreprise. | P0 | L’obligation DCE et la capacité entreprise ne partagent pas le même objet. |
| `INV-005` | Un `Finding` affichable porte des evidence refs et la justification de sa règle/évaluation. | P0 | Un finding sans preuve ne peut pas être restitué comme conclusion. |
| `INV-006` | Tout montant ou ratio financier utilise `Decimal`, une unité/devise et une politique d’arrondi. | P0 | Un `float` franchissant la frontière du Math Engine est rejeté. |
| `INV-007` | Une `Calculation` référence les faits, la règle et la version de solveur utilisés. | P0 | Un calcul non rejouable est rejeté. |
| `INV-008` | Un `ReportSnapshot` ne fait que projeter des artefacts persistés. | P0 | La génération de rapport ne lance aucun calcul ni extraction. |
| `INV-009` | Le score de retrieval n’est pas une confiance d’extraction ou d’évaluation. | P1 | Les trois métriques ne partagent pas un même champ. |
| `INV-010` | Les événements sont émis après le commit du domaine, jamais comme source de vérité. | P1 | Un échec de publication ne corrompt pas la transaction métier. |

## 3. State machines minimales

Les états détaillés de PASS 8.1 sont une bonne cible de maturité. Pour le premier vertical slice, les cycles suivants suffisent.

| Entité | États du pilote | Remarques |
|---|---|---|
| `Document` | `ACTIVE`, `ARCHIVED` | Identité logique stable ; la version porte le détail d’ingestion. |
| `DocumentVersion` | `PROCESSING`, `READY`, `FAILED`, `QUARANTINED` | `READY` est immuable. Une modification crée une nouvelle version. |
| `Evidence` | `VALID`, `RETRACTED` | Créée valide seulement après contrôle de localisation et de hash. |
| `Fact` | `CANDIDATE`, `VERIFIED`, `CONFLICTING`, `REJECTED`, `SUPERSEDED` | Ne pas introduire `ACTIVE` avant qu’un cas de sélection de fait canonique l’exige. |
| `Requirement` | `DETECTED`, `VERIFIED`, `REJECTED`, `SUPERSEDED` | Suffisant pour le pilote ; la sémantique normative est une propriété, pas un statut. |
| `RuleVersion` | `DRAFT`, `ACTIVE`, `RETIRED` | Une règle active ne change jamais in place. |
| `Finding` | `DRAFT`, `SUPPORTED`, `ACCEPTED`, `REJECTED`, `SUPERSEDED` | Le statut `PUBLISHED` appartient au rapport, pas obligatoirement à chaque finding. |
| `Calculation` | `COMPLETED`, `FAILED`, `INVALIDATED` | Les états `REQUESTED` et `RUNNING` sont ajoutés seulement si l’exécution devient asynchrone. |
| `AnalysisRun` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` | Une nouvelle tentative est une nouvelle exécution ou, plus tard, une `AnalysisAttempt`. |
| `ReportSnapshot` | `DRAFT`, `PUBLISHED`, `SUPERSEDED` | Le PDF/DOCX est un artefact immutable lié à un snapshot. |

### Mécanismes différés

`Assessment` persistant avec `INPUTS_LOCKED`, `AgentRun`, `AnalysisAttempt`, `CalculationRun`, les boucles de retry, un Event Bus durable et une state machine riche de publication deviennent nécessaires lorsque V8 introduira le calcul asynchrone, le LLM, le travail distribué ou la revue multi-utilisateur. Les ajouter maintenant ne rendrait pas le premier DCE plus juste ni plus traçable.

## 4. Frontières d’agrégats recommandées

Un agrégat est une frontière transactionnelle, pas un simple groupe de classes voisines. Aucun agrégat V8 ne doit contenir tout un DCE ni toute une analyse dans une unique transaction.

| Agrégat | Racine | Responsabilités atomiques | Ne possède pas |
|---|---|---|---|
| **TenderCase** | `TenderCase` | Métadonnées du dossier, client/tenant, état fonctionnel, références de documents. | Contenu de toutes les versions de documents, résultats de toutes les analyses. |
| **Document** | `Document` | Identité de pièce, classification, création d’une nouvelle version. | Analyse et findings. |
| **DocumentVersion** | `DocumentVersion` | Hash, artefact, statut d’ingestion et publication de la version. Les chunks sont ses enfants techniques. | Les evidences et faits de toutes les analyses. |
| **RuleSet** | `RuleSet` / `RuleVersion` | Publication et retraite de règles versionnées. | Exécutions de calcul et findings. |
| **AnalysisRun** | `AnalysisRun` | Snapshot des entrées, état d’exécution, corrélation des artefacts dérivés. | Toutes les écritures de facts/findings dans une seule transaction. |
| **Fact** | `Fact` | Provenance, valeur normalisée, statut et résolution explicite de conflit. | Rapport et calculs consommateurs. |
| **Finding** | `Finding` | Conclusion, sources, statut de revue et références de calcul. | Contenu du rapport. |
| **Calculation** | `Calculation` | Snapshot d’inputs, règle/solveur, résultat, précision et invalidation. | Documents bruts ou logique de retrieval. |
| **ReportSnapshot** | `ReportSnapshot` | Snapshot des findings/calculs, version de template et artefacts publiés. | Réextraction ou recalcul. |

Cette structure est compatible avec un monolithe modulaire et PostgreSQL. Chaque agrégat peut être stocké dans des tables relationnelles simples avec clés étrangères et verrous optimistes ; elle ne nécessite ni microservices ni Event Sourcing.

## 5. Transactions et concurrence

Les transactions importantes sont courtes et orientées command.

| Commande | Agrégat cible | Préconditions | Transaction atomique | Effet différé possible |
|---|---|---|---|---|
| `RegisterDocumentVersion` | `DocumentVersion` | Tenant autorisé, artefact vérifié, hash calculé. | Création de la version + référence d’artefact. | Demande de parsing. |
| `MarkDocumentVersionReady` | `DocumentVersion` | Parsing terminé, données minimales valides. | Passage `PROCESSING → READY`. | `DocumentVersionReady`. |
| `ProposeFact` | `Fact` | Evidence valide et type connu. | Création du fait candidat + liens de preuve. | Détection de conflit. |
| `VerifyFact` | `Fact` | Provenance complète et acteur/politique autorisé. | Passage à `VERIFIED` ou `CONFLICTING`. | `FactVerified`. |
| `EvaluateRule` | `Finding` (+ `Calculation` si nécessaire) | Faits/règles de la même analyse, inputs disponibles. | Création d’un finding draft et d’un calcul immuable, chacun avec références. | Notification/revue. |
| `AcceptFinding` | `Finding` | Evidence et calcul requis présents ; revue autorisée. | Passage `SUPPORTED → ACCEPTED`. | `FindingAccepted`. |
| `PublishReport` | `ReportSnapshot` | Findings/calculs acceptés, snapshot cohérent. | Création du snapshot et de l’artefact rapport. | `ReportPublished`. |

Les commandes doivent accepter une clé d’idempotence. Les tables doivent porter une colonne de version ou un verrou optimiste sur les agrégats mutables. Une outbox transactionnelle peut être ajoutée lorsque les événements ont des consommateurs asynchrones ; avant cela, un publisher in-process testé suffit.

## 6. Prochaine spécification obligatoire : agrégats, commandes et événements

La prochaine documentation V8 ne doit pas encore être un schéma SQLAlchemy. Elle doit être un unique document nommé :

```text
V8_AGGREGATES_COMMANDS_EVENTS.md
```

Pour chaque commande du premier vertical slice, il définira : le déclencheur, l’acteur autorisé, l’agrégat modifié, les préconditions, la transition, les invariants contrôlés, les effets de bord, l’événement émis, la clé d’idempotence et les tests d’acceptation. Ce document résout les frontières transactionnelles avant que des migrations, repositories ou workers ne soient écrits.

## 7. Verdict

PASS 8.1 apporte un cadre précieux : publication immuable, fermeture de provenance, règles versionnées, calcul déterministe, rapport comme projection et transitions explicites. Nous devons l’adopter, mais de façon graduelle.

> **Le pilote V8 doit d’abord prouver six choses : une version de document immuable, une evidence localisable, un fait sourcé, une règle versionnée, un calcul Decimal traçable et un finding/rapport navigable vers la source.**

Les agents cognitifs, les états de retry détaillés, les workers distribués et le bus durable ne deviendront obligatoires qu’après cette preuve.
