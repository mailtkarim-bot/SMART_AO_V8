# SMART_AO V8 — Revue pragmatique des agrégats, transactions et événements

**Statut :** décision d’architecture proposée avant l’implémentation.  
**Objectif :** conserver la traçabilité forte du blueprint V8 tout en gardant un monolithe modulaire réalisable pour le premier vertical slice.

## 1. Ce que le PASS 8.2 établit correctement

Le principe est bon : un agrégat est une frontière de cohérence transactionnelle, non une simple entité ORM ou une arborescence de classes. Le système ne doit jamais reproduire `mission.context` sous la forme d’un grand `AnalysisRun` contenant tout le dossier, toutes les preuves, tous les calculs et tous les rapports.

La séparation suivante est saine : document/version, evidence, connaissance, règles, évaluation/findings, exécution, calcul et rapport. Une base PostgreSQL unique, avec ownership logique par modules, est la meilleure option initiale. La séparation en bases, microservices ou bus inter-services ne se justifie pas pour le pilote.

Le principe de sécurité est aussi correct : une sortie LLM est une **proposition** ; elle ne devient jamais directement une vérité métier publiée. Les proposions doivent être reliées à des evidences, évaluées par une règle/politique et soumises aux transitions de domaine.

## 2. Ajustements indispensables

| Proposition initiale | Décision pragmatique | Justification |
|---|---|---|
| Sept agrégats complets dès le départ | Conserver les frontières conceptuelles ; n’implémenter que les agrégats du pilote. | Éviter une implémentation massive avant la preuve métier. |
| `Document` possède toutes ses versions dans une transaction | Oui pour la numérotation et la publication d’une version ; non pour parsing, chunking et evidence. | L’ingestion et l’analyse sont potentiellement longues et doivent être asynchrones. |
| `Assessment` possède des findings | Possible à terme ; dans le pilote, `Finding` peut être indépendant avec `assessment_id` optionnel. | Le pilote déterministe n’a pas encore besoin d’une entité Assessment persistante riche. |
| `AnalysisRun` possède `AgentRun` | Différer `AgentRun` jusqu’au premier composant cognitif ou worker piloté. | Aucun runtime agentique LLM V7.1 n’est actuellement démontré. |
| Deux agrégats impliqués = événement obligatoire | **Trop strict.** Une application service peut modifier plusieurs agrégats dans une transaction PostgreSQL courte lorsqu’une cohérence immédiate est réellement requise. | Les événements servent à la propagation et aux processus asynchrones, pas à interdire toute transaction locale multi-objets. |
| Outbox obligatoire dès J1 | Prévoir son contrat maintenant ; l’implémenter dès qu’un effet de bord asynchrone ou externe existe. | Un publisher in-process suffit tant qu’il n’y a ni worker externe, ni webhook, ni bus distribué. |
| `UNIQUE(aggregate_id, aggregate_version)` pour tous les événements | Utiliser `event_id` et une clé d’idempotence ; ajouter `event_sequence` si plusieurs événements sont émis pour une même mutation. | Une version d’agrégat peut légitimement produire plusieurs événements. |
| `DocumentVersionPublished` déclenche parsing | Nommer l’événement selon son sens : `DocumentVersionReadyForProcessing` puis `DocumentVersionProcessed`. | « Published » doit signifier qu’un artefact stabilisé est utilisable, pas seulement qu’il vient d’être uploadé. |

## 3. Agrégats à implémenter dans le premier vertical slice

| Agrégat / module | Racine | Responsabilité atomique | Implémenter maintenant ? |
|---|---|---|---:|
| `TenderCase` | `TenderCase` | Isolation tenant, métadonnées du dossier, références de documents. | Oui |
| `Document` | `Document` | Identité logique et création/versionnement des pièces. | Oui |
| `DocumentVersion` | `DocumentVersion` | Hash, artefact, statut d’ingestion et immuabilité après `READY`. | Oui |
| `Evidence` | `Evidence` | Localisation fiable et contenu/source d’un extrait. | Oui |
| `Fact` | `Fact` | Valeur normalisée, provenance et conflit explicite. | Oui |
| `Requirement` | `Requirement` | Obligation extraite du DCE et sa provenance. | Oui |
| `RuleVersion` | `RuleVersion` | Règle de calcul/évaluation, version et date d’effet. | Oui |
| `Finding` | `Finding` | Conclusion sourcée, statut de revue et références de calcul. | Oui |
| `Calculation` | `Calculation` | Snapshot d’inputs typés et résultat `Decimal`. | Oui, si le scénario pilote contient une pénalité ou autre calcul. |
| `AnalysisRun` | `AnalysisRun` | Snapshot, statut et corrélation des artefacts de l’analyse. | Oui |
| `ReportSnapshot` | `ReportSnapshot` | Vue versionnée des artefacts acceptés. | Oui |
| `Assessment` riche | `Assessment` | Snapshot d’évaluation et coordination de plusieurs findings. | Différé ou value object initial. |
| `AgentRun` | `AgentRun` | Traçabilité de modèle/prompt/tools et propositions IA. | Différé. |
| `AnalysisAttempt` | `AnalysisAttempt` | Retries distribués. | Différé. |

## 4. Transactions du pilote

Le pilote utilise une seule PostgreSQL et des transactions courtes. L’ORM est une infrastructure : les commandes et les invariants sont définis dans l’application/domaine.

| Commande | Cohérence nécessaire | Transaction locale | Effet asynchrone éventuel |
|---|---|---|---|
| `RegisterDocumentVersion` | Une version a un hash, un artefact et un numéro uniques. | Créer document/version + clé d’idempotence. | Demande de parsing. |
| `StoreEvidence` | Evidence et locator sont cohérents avec la version du document. | Créer evidence, contrôler version/chunk. | Indexation/retrieval ultérieur. |
| `ProposeOrVerifyFact` | Fact lié à ses evidences, type et valeur normalisée. | Créer/mettre à jour le statut du fact. | Détection de conflit. |
| `CreateRequirement` | Obligation reliée à une evidence et une sémantique normalisée. | Créer requirement. | Évaluation future. |
| `EvaluatePenaltyRule` | Faits, règle et calcul d’une même analyse sont cohérents. | Créer calculation + finding draft dans la même transaction si nécessaire. | Notification de revue. |
| `AcceptFinding` | Source, règle et calcul requis sont présents. | Transition du finding. | Actualiser un read model. |
| `PublishReport` | Le snapshot référence uniquement des artefacts acceptés. | Créer report snapshot + artefact. | Notification ou export. |

Une commande reçoit une **idempotency key**. Les agrégats mutables portent une version optimiste. Les `SELECT … FOR UPDATE` restent exceptionnels, par exemple pour réserver un numéro de version séquentiel d’un même document.

## 5. Événements : contrat initial sans bus prématuré

Le pilote définit des événements de domaine, même si leur premier consommateur est local. Ils deviennent des messages outbox dès qu’un consommateur asynchrone, externe ou critique est introduit.

| Événement | Producteur | Émet quand | Consommateur pilote |
|---|---|---|---|
| `DocumentVersionReady` | Document module | Une version immuable est prête au parsing. | Document processing. |
| `EvidenceStored` | Evidence module | Une preuve localisable a été créée. | Extraction / audit. |
| `FactVerified` | Knowledge module | Un fait satisfait provenance et validation. | Rule evaluation. |
| `FactConflictDetected` | Knowledge module | Deux faits incompatibles sont présents. | UI / revue humaine. |
| `RequirementVerified` | Knowledge module | Une obligation est normalisée et sourcée. | Rule evaluation. |
| `CalculationCompleted` | Math module | Le calcul déterministe est figé. | Finding/report projection. |
| `FindingAccepted` | Analysis module | Le finding satisfait les guards. | Report projection. |
| `ReportPublished` | Report module | Le snapshot et l’artefact sont publiés. | Audit / notification. |

Le schéma commun contient au minimum `event_id`, `event_type`, `schema_version`, `aggregate_id`, `aggregate_version`, `occurred_at`, `correlation_id`, `causation_id` et `idempotency_key`. La règle d’unicité doit être adaptée au nombre d’événements émis par transition ; `event_id` suffit au départ.

## 6. Prochaine spécification à produire

Le document suivant doit être `V8_AGGREGATES_COMMANDS_EVENTS.md`. Pour **chaque commande du pilote**, il contiendra :

1. L’acteur autorisé et le tenant concerné ;
2. L’agrégat racine et la version attendue ;
3. Le payload typé ;
4. Les préconditions et invariants ;
5. La mutation permise ;
6. Les artefacts créés ou référencés ;
7. L’événement éventuel et son consommateur ;
8. La sémantique d’idempotence ;
9. Les échecs explicites ;
10. Les tests d’acceptation.

## 7. Verdict

Le PASS 8.2 est une base solide, à condition de ne pas le transformer immédiatement en architecture distribuée. Nous retenons son apport essentiel : **la vérité est détenue par de petits agrégats versionnés, et les LLM/agents ne produisent que des propositions soumises à ce domaine.**

Le pilote V8 reste un monolithe modulaire, une PostgreSQL, une transaction locale courte quand la cohérence immédiate l’exige, et des événements uniquement pour les processus réellement différés. Cela donne une base robuste, testable et maintenable sans recréer la lourdeur de V7.1.
