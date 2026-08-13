# SMART_AO V8 — DOMAIN-03
## State Machines & Invariant Catalog — Premier slice `Case + Consultation/DceVersion + Decision`

**Version :** 1.0  
**Statut :** contrat de domaine exécutable à valider avant modèles Pydantic, SQLAlchemy, repositories et endpoints d’écriture  
**Auteur :** Manus AI  
**Périmètre :** `AFF/Case`, `DCE/Consultation`, `DCE/DceVersion` et `DEC/Decision`  
**Hors périmètre :** collaboration détaillée, preuve, exigences, analyse, prix, dépôt, exécution de marché, mécanismes de workers et persistance technique

---

## 1. Objet et décision de gel

DOMAIN-01 a fixé les owners et les frontières de transaction. DOMAIN-02 a normalisé les commandes collaborateur. DOMAIN-03 rend le premier slice **directement testable** : pour chaque aggregate, il définit les axes d’état, les transitions autorisées, les préconditions, les invariants, les événements, les conflits et les échecs explicites.

> **Décision de gel DOMAIN-03 :** une machine d’état ne remplace jamais les autres axes de réalité. Le cycle de vie, la validité, la fraîcheur, l’issue et la readiness sont indépendants. Aucun `status` unique ne doit masquer ces différences.

| Aggregate | Propriétaire | Finalité du slice | N’écrit jamais |
|---|---|---|---|
| `Case` | `AFF` | Continuité commerciale, périmètre choisi et stade métier de l’affaire. | DCE, prix, décision, tâches, preuves ou dépôt. |
| `Consultation` | `DCE` | Identité pérenne de la consultation acheteur, ses lots et tranches sources. | Affaire, version DCE, exigence, décision ou prix. |
| `DceVersion` | `DCE` | Version immuable des pièces DCE admises, documents et assertions source. | Case, Requirement, Decision, Pricing, Submission ou ImpactAssessment. |
| `Decision` | `DEC` | Choix humain patron, contexte figé, conditions et supersession. | Case, DceVersion, Task, prix, dépôt ou action patron. |

---

## 2. Règles communes de lecture des machines d’état

### 2.1. Axes orthogonaux obligatoires

| Axe | Question à laquelle il répond | Exemples |
|---|---|---|
| **Lifecycle** | Où en est cette réalité dans son cycle principal ? | `ACTIVE`, `ARCHIVED`, `PREPARED`, `FINALIZED`. |
| **Disposition / outcome** | Quel choix ou résultat s’applique ? | `GO`, `CONDITIONAL_GO`, `NO_GO`, `NOT_APPLICABLE`. |
| **Validity** | Cette réalité peut-elle encore fonder une action ? | `CURRENT`, `STALE`, `SUPERSEDED`, `INVALIDATED`. |
| **Freshness** | Les sources de référence ont-elles évolué ? | `CURRENT`, `REVIEW_REQUIRED`, `OBSOLETE`. |
| **Readiness** | Les conditions sont-elles satisfaites pour l’étape suivante ? | `NOT_READY`, `READY`, `READY_WITH_WARNINGS`, `BLOCKED`. |
| **Integrity** | La conservation de la source est-elle fiable ? | `VERIFIED`, `PARTIAL`, `UNUSABLE`. |

Un seul champ ne doit jamais porter plusieurs de ces significations. Par exemple, une décision peut être `FINALIZED` tout en étant `STALE` ; une version DCE peut être `ADMITTED` mais d’intégrité `PARTIAL` ; une affaire peut rester `ACTIVE` alors que sa readiness de décision est `NOT_READY`.

### 2.2. Règles transactionnelles du premier slice

| Règle | Contrat |
|---|---|
| **Un root par écriture** | Une commande ne modifie qu’un root et ses entités internes. |
| **Références en lecture** | Les autres roots sont lus comme références versionnées ; ils ne sont jamais réécrits dans le même commit. |
| **Concurrence** | Toute mutation d’un root existant exige `expected_revision`. |
| **Idempotence** | Toute commande de création, transition, finalisation, supersession ou archivage porte une `idempotency_key`. |
| **Contexte** | Les commandes patron engageantes vérifient le tenant, l’habilitation, les révisions de références critiques et l’empreinte de contexte. |
| **Historique** | Une réalité finalisée ne change pas de contenu : elle est supersédée, marquée à revoir ou archivée. |
| **Propagation** | Toute conséquence inter-aggregate passe par Domain Event, Integration Event minimal et commande aval corrélée. |

### 2.3. Convention de transition

```text
État avant + Commande acceptée + Invariants
    → mutation du root propriétaire
    → aggregate_revision + 1
    → Domain Event métier
    → résultat idempotent mémorisé
    → conséquences aval éventuelles, après commit
```

Une commande refusée ne modifie ni revision, ni état, ni événement métier. Un retry avec la même clé et la même empreinte retourne le résultat initial sans produire un second événement.

---

# Partie I — `AFF/Case`

## 3. Fiche d’aggregate : Case

### 3.1. Responsabilité, frontières et contenu minimal

`Case` représente l’affaire commerciale choisie par l’entreprise : l’objet de réponse, le périmètre, la consultation, l’origine, le stade de cycle et l’historique de continuité. Il n’est pas le dossier entier.

| Élément | Décision |
|---|---|
| **Root** | `Case` |
| **Entités internes** | Lien d’origine, `CasePartnerApproval`, responsabilité commerciale historique. |
| **Objets-valeur** | `CaseScope`, origine, motif d’arrêt, motif d’archivage, responsabilité courante projetée. |
| **Références** | `Consultation`, `DceVersion` applicable, Opportunity, Assignment, Decision, Preparation, Pricing, Submission et ImpactAssessment. |
| **FunctionalIdentity** | `CaseKey = tenant_id + consultation_id + normalized_scope_fingerprint + business_origin`, sauf affaire manuelle explicitement justifiée. |
| **Interdit** | Ne possède aucun document, assertion source, exigence, tâche, prix, décision ou accusé. |

### 3.2. Axes d’état `Case`

| Axe | Valeurs | Sens |
|---|---|---|
| `lifecycle` | `ACTIVE`, `STOPPED`, `ARCHIVED` | L’affaire travaille, est arrêtée avec motif, ou est sortie du portefeuille actif. |
| `commercial_stage` | `INTAKE`, `ANALYSIS`, `AWAITING_DECISION`, `OFFER_PREPARATION`, `READY_FOR_PRICING`, `PRICING`, `READY_FOR_FINAL_CONTROL`, `READY_FOR_SUBMISSION`, `SUBMITTED`, `OUTCOME_KNOWN`, `AWARDED`, `EXECUTION` | Étape visible de continuité. Ne contient pas l’état détaillé des tâches, prix ou dépôt. |
| `decision_readiness` | `NOT_ASSESSED`, `NOT_READY`, `READY_WITH_UNKNOWNS`, `READY` | Lecture calculée et historisée des conditions pour l’arbitrage patron. |
| `dce_freshness` | `NO_DCE`, `CURRENT`, `REVIEW_REQUIRED` | Version DCE applicable connue ou changement imposant une revue. |
| `responsibility_status` | `UNASSIGNED`, `ASSIGNED`, `ASSIGNMENT_REVIEW_REQUIRED` | Présence d’une responsabilité active autorisée, sans posséder l’Assignment. |

Le cycle `commercial_stage` est légalement pertinent pour la conduite du dossier, mais il ne fait pas preuve d’un dépôt, d’un prix ou d’une décision. Ces preuves restent dans leur aggregate propriétaire.

### 3.3. Machine de cycle `Case`

```text
                    ┌──────────────────────────────────────────┐
                    │              lifecycle = ACTIVE           │
                    │                                            │
INTAKE → ANALYSIS → AWAITING_DECISION → OFFER_PREPARATION        │
            ↑            │                 │                    │
            │            │                 └→ READY_FOR_PRICING │
            │            │                         → PRICING     │
            │            │                         → READY_FOR_FINAL_CONTROL
            │            │                         → READY_FOR_SUBMISSION
            │            │                         → SUBMITTED → OUTCOME_KNOWN
            │            │                                          → AWARDED → EXECUTION
            └────────────┴──────── Retour à préparation autorisé │
                    └──────────────────────────────────────────┘

Toute étape ACTIVE ──StopCase──> lifecycle = STOPPED
STOPPED ──ReopenCaseWithPatronDecision──> lifecycle = ACTIVE, commercial_stage déterminé explicitement
ACTIVE ou STOPPED ──ArchiveCase──> lifecycle = ARCHIVED
ARCHIVED ──RestoreArchivedCase──> lifecycle = ACTIVE, commercial_stage déterminé explicitement
```

Une flèche de retour ne modifie aucune version historique de prix, de DCE, de décision ou de dépôt. Elle déplace uniquement le stade de l’affaire après une cause explicite.

### 3.4. Commandes et transitions `Case`

| Commande | État avant autorisé | Préconditions métier | Mutation du root | État après | Domain Event |
|---|---|---|---|---|---|
| `CreateCase` | Aucun | Tenant actif ; Consultation existante ou création manuelle justifiée ; `CaseScope` non ambigu ; acteur patron habilité. | Crée Case, origine et références stables. | `ACTIVE + INTAKE`, `NO_DCE`, `UNASSIGNED`. | `CaseCreated`. |
| `RegisterCaseConsultationLink` | `ACTIVE`, hors `EXECUTION` | Consultation même tenant ; scope compatible avec ses lots/tranches ; aucun lien contradictoire. | Ajoute/révise référence de consultation documentée. | Stage inchangé ; `dce_freshness` selon DCE applicable. | `CaseConsultationLinked`. |
| `SetApplicableDceVersion` | `ACTIVE`, stage ≤ `READY_FOR_SUBMISSION` | DceVersion admise, même Consultation, même tenant ; `CaseScope` compatible ; version pas `SUPERSEDED` pour l’usage visé. | Enregistre référence DCE applicable. | `dce_freshness = CURRENT`; stage inchangé. | `CaseApplicableDceVersionSet`. |
| `StartCaseAnalysis` | `ACTIVE + INTAKE` | Consultation et scope connus ; un DCE ou une information manuelle de départ est référencé. | Avance le stage. | `ANALYSIS`. | `CaseAnalysisStarted`. |
| `RecordDecisionReadiness` | `ACTIVE + ANALYSIS` ou `AWAITING_DECISION` | Évaluation identifiée, inconnus distincts, auteur/moteur et date connus ; aucun prix requis. | Met à jour la lecture propriétaire de readiness. | `NOT_READY`, `READY_WITH_UNKNOWNS` ou `READY`. | `CaseDecisionReadinessRecorded`. |
| `MoveCaseToDecision` | `ACTIVE + ANALYSIS` ou `AWAITING_DECISION` | `decision_readiness` vaut `READY` ou `READY_WITH_UNKNOWNS`; DCE frais ; les inconnus restent visibles. | Avance le stage. | `AWAITING_DECISION`. | `CaseReadyForDecision`. |
| `StartOfferPreparation` | `ACTIVE + AWAITING_DECISION` | Référence à une Decision `GO` ou `CONDITIONAL_GO` valide ; consultation/DCE compatible. | Avance le stage ; stocke la référence de décision. | `OFFER_PREPARATION`. | `CaseOfferPreparationStarted`. |
| `MoveCaseToPricing` | `ACTIVE + OFFER_PREPARATION` | Décision Go active ; PreparationTransmission acceptée pour phase suivante ; DCE fraîche ; aucune condition patron bloquante non traitée. | Avance le stage. | `READY_FOR_PRICING`. | `CaseReadyForPricing`. |
| `StartCasePricing` | `ACTIVE + READY_FOR_PRICING` | Commande patron uniquement ; pricing workflow disponible. | Avance le stage, sans créer de scénario de prix. | `PRICING`. | `CasePricingStarted`. |
| `MarkCaseReadyForFinalControl` | `ACTIVE + PRICING` | Référence à une OfficialPricingVersion compatible, sans l’écrire ; DCE fraîche. | Avance le stage. | `READY_FOR_FINAL_CONTROL`. | `CaseReadyForFinalControl`. |
| `MarkCaseReadyForSubmission` | `ACTIVE + READY_FOR_FINAL_CONTROL` | Référence SubmissionPackage autorisée et Decision compatible ; contrôles nécessaires satisfaits. | Avance le stage. | `READY_FOR_SUBMISSION`. | `CaseReadyForSubmission`. |
| `RecordCaseSubmissionDeclared` | `ACTIVE + READY_FOR_SUBMISSION` | Référence à déclaration de dépôt existante ; acteur habilité ; sans déduire un accusé. | Avance le stage uniquement. | `SUBMITTED`. | `CaseSubmissionDeclared`. |
| `RecordCaseOutcome` | `ACTIVE + SUBMITTED` ou `OUTCOME_KNOWN` | Source acheteur/constat patron, type de résultat, date et provenance. | Enregistre outcome de continuité. | `OUTCOME_KNOWN` ou `AWARDED`. | `CaseOutcomeRecorded`. |
| `EnterExecution` | `ACTIVE + AWARDED` | Attribution confirmée et décision/contrat de continuité référencés. | Avance le stage. | `EXECUTION`. | `CaseExecutionEntered`. |
| `ReturnCaseToPreparation` | `ACTIVE`, stage postérieur à `OFFER_PREPARATION` et antérieur à `SUBMITTED` | Cause précise : retour patron, impact DCE, incohérence ou correction ; historique de l’étape précédente conservé. | Avance le stage vers correction sans altérer les artefacts. | `OFFER_PREPARATION`; `dce_freshness` actualisée. | `CaseReturnedToPreparation`. |
| `StopCase` | `ACTIVE` | Patron habilité ; motif et origine de l’arrêt ; aucune destruction d’historique. | `lifecycle = STOPPED`, motif/date/auteur. | `STOPPED`; stage conservé comme contexte historique. | `CaseStopped`. |
| `ReopenCaseWithPatronDecision` | `STOPPED` | Nouvelle Decision patron explicite de reprise ; nouveau stage cible compatible ; source de reprise. | Réactive le cycle et conserve lien de l’arrêt. | `ACTIVE + stage explicite`. | `CaseReopened`. |
| `ArchiveCase` | `ACTIVE` ou `STOPPED` | Pas d’action bloquante non arbitrée, ou justification patron ; motif. | `lifecycle = ARCHIVED`. | `ARCHIVED`. | `CaseArchived`. |
| `RestoreArchivedCase` | `ARCHIVED` | Patron habilité ; motif ; stage cible explicite ; aucune donnée historique réécrite. | `lifecycle = ACTIVE`. | `ACTIVE + stage explicite`. | `CaseRestored`. |

### 3.5. Invariants `Case`

| ID | Invariant non négociable | Vérification au moment de |
|---|---|---|
| `CASE-INV-01` | Une Case appartient à un seul tenant pendant toute sa vie. | Toute commande et lecture. |
| `CASE-INV-02` | `CaseScope` est explicite : lot unique, ensemble autorisé, tranche, variante ou périmètre sourcé. Un mélange non justifié est refusé. | `CreateCase`, lien Consultation, changement de scope. |
| `CASE-INV-03` | Une Case ne référence que des aggregates du même tenant. | Toute création/modification de référence. |
| `CASE-INV-04` | Une Case ne possède ni prix, ni décision, ni tâche, ni document, ni preuve, ni dépôt. | Test d’architecture et repository. |
| `CASE-INV-05` | `READY_FOR_PRICING` nécessite Decision Go/Go conditionnel valide, préparation transmise/acceptée et DCE fraîche. | `MoveCaseToPricing`. |
| `CASE-INV-06` | `SUBMITTED` signifie uniquement qu’un dépôt est déclaré ; la preuve d’accusé n’est jamais inférée. | `RecordCaseSubmissionDeclared`. |
| `CASE-INV-07` | `STOPPED` et `ARCHIVED` interdisent toute progression commerciale jusqu’à commande de reprise/restauration autorisée. | Toute commande de stage. |
| `CASE-INV-08` | Un rectificatif DCE ne déplace pas seul le stage ; il rend `dce_freshness = REVIEW_REQUIRED` par commande corrélée. | Process aval `DceVersion`/Impact. |
| `CASE-INV-09` | Une Case en `EXECUTION` reste historiquement liée à ses décisions, DCE et soumissions ; aucun lien ne peut être supprimé. | Entrée exécution et archivage. |

### 3.6. Concurrence, idempotence et erreurs `Case`

| Catégorie | Contrat |
|---|---|
| `expected_revision` | Obligatoire sur toute commande hors `CreateCase`. |
| Idempotence | Obligatoire pour create, stage change, stop, reopen, archive et restore. |
| Références critiques | `SetApplicableDceVersion`, `MoveCaseToPricing`, `MarkCaseReadyForSubmission` vérifient révision/validité des références. |
| Erreurs | `CASE_SCOPE_AMBIGUOUS`, `CASE_LIFECYCLE_FORBIDS_ACTION`, `DCE_VERSION_NOT_APPLICABLE`, `DECISION_REQUIRED`, `PREPARATION_NOT_ACCEPTED`, `SUBMISSION_PACKAGE_NOT_AUTHORIZED`, `STALE_CONTEXT`, `VERSION_CONFLICT`. |
| RYOW | Réponse retourne le stage, lifecycle, freshness, revision et la projection éventuelle en attente. |

---

# Partie II — `DCE/Consultation` et `DCE/DceVersion`

## 4. Fiche d’aggregate : Consultation

### 4.1. Responsabilité et axes d’état

`Consultation` est l’identité durable de l’appel d’offres côté acheteur. Elle survit aux rectificatifs et référence les lots/tranches source. Elle n’est ni un dossier de réponse ni une affaire.

| Élément | Décision |
|---|---|
| **Root** | `Consultation` |
| **Entités internes** | Lots, tranches et références d’origine acheteur. |
| **Objets-valeur** | Acheteur, référence externe, objet, lieu, source initiale. |
| **FunctionalIdentity** | `ConsultationKey = tenant_id + buyer_normalized_id + external_reference`, sinon source + objet + date de détection + empreinte. |
| **Lifecycle** | `OPEN`, `CLOSED`, `ARCHIVED`. |
| **Freshness** | `UNKNOWN`, `CURRENT`, `REVIEW_REQUIRED` à titre de lecture de version connue ; ne remplace pas l’applicabilité Case. |

### 4.2. Machine d’état `Consultation`

| Commande | État avant | Préconditions | Mutation / état après | Domain Event |
|---|---|---|---|---|
| `CreateConsultation` | Aucun | Tenant actif ; identité acheteur ou source minimale ; objet initial. | Crée `OPEN`; lots/tranches éventuellement vides mais signalés incomplets. | `ConsultationCreated`. |
| `RegisterConsultationLot` | `OPEN` | Numéro/libellé source non ambigu ; aucun doublon fonctionnel. | Ajoute/complète un lot source ; lifecycle inchangé. | `ConsultationLotRegistered`. |
| `RegisterConsultationTranche` | `OPEN` | Identité de tranche, type et source identifiés. | Ajoute/complète tranche source. | `ConsultationTrancheRegistered`. |
| `CorrectConsultationMetadata` | `OPEN` | Correction sourcée ; ne modifie pas l’identité fonctionnelle sans procédure de fusion. | Métadonnées corrigées avec historique de provenance. | `ConsultationMetadataCorrected`. |
| `CloseConsultation` | `OPEN` | Source ou motif patron : échéance expirée, attribution, retrait ou clôture. | `OPEN → CLOSED`. | `ConsultationClosed`. |
| `ArchiveConsultation` | `CLOSED` | Rétention/historique préservés. | `CLOSED → ARCHIVED`. | `ConsultationArchived`. |

### 4.3. Invariants `Consultation`

| ID | Invariant |
|---|---|
| `CONS-INV-01` | Une Consultation est tenant-scoped et ne change jamais de tenant. |
| `CONS-INV-02` | Une identité acheteur/externe est unique dans le tenant ou une fusion explicite est requise. |
| `CONS-INV-03` | Un lot/tranche conserve son libellé/numéro source et ne devient jamais un `CaseScope` propriétaire. |
| `CONS-INV-04` | La fermeture n’efface ni DceVersion, ni Case, ni décision liée. |
| `CONS-INV-05` | Une Consultation ne définit pas elle-même le DCE applicable à une Case : cette référence appartient à Case. |

---

## 5. Fiche d’aggregate : DceVersion

### 5.1. Responsabilité et contenu

`DceVersion` représente un corpus DCE admis pour une Consultation : originaux acheteur, hash, provenance, documents classés et ancres `SourceStatement` localisées. Son contenu documentaire est **immutable après admission**. Les opérations de lecture technique, extraction, indexation ou worker ne lui appartiennent pas ; elles sont des mécanismes `ENGINE/INFRA` qui peuvent alimenter des CandidateAssertions à vérifier.

| Élément | Décision |
|---|---|
| **Root** | `DceVersion` |
| **Entités internes** | `DceDocument`, `SourceStatement`, annotation métier de classification. |
| **Objets-valeur** | `DceVersionIdentity`, hash corpus, provenance, réception, supersession, intégrité métier. |
| **FunctionalIdentity** | `DceVersionKey = tenant_id + consultation_id + corpus_hash`. |
| **Lifecycle** | `ADMITTED`, `SUPERSEDED`, `WITHDRAWN` ; `WITHDRAWN` est exceptionnel et nécessite une source explicite. |
| **Integrity** | `VERIFIED`, `PARTIAL`, `UNUSABLE`. |
| **ClassificationReadiness** | `UNCLASSIFIED`, `PARTIALLY_CLASSIFIED`, `CLASSIFIED`. |
| **AnalysisReadiness** | `NOT_READY`, `READY_FOR_ANALYSIS`, `REVIEW_REQUIRED`. |

`RECTIFICATIF` n’est pas un état exclusif : c’est une provenance de la nouvelle version qui porte une relation de supersession vers une version précédente.

### 5.2. Machine d’état `DceVersion`

```text
RegisterDceVersion
  → lifecycle = ADMITTED
  → integrity = VERIFIED | PARTIAL | UNUSABLE
  → classification_readiness = UNCLASSIFIED
  → analysis_readiness = NOT_READY

Admitted DceDocument(s)
  ├─ ConfirmDocumentClassification
  │    → PARTIALLY_CLASSIFIED / CLASSIFIED
  ├─ DeclareMissingDocument / ReportDocumentIntegrityIssue
  │    → integrity = PARTIAL ou UNUSABLE, selon gravité
  ├─ RegisterSourceStatement
  │    → analysis_readiness = READY_FOR_ANALYSIS si intégrité et classification suffisantes
  │    → les `SourceAssertion` analytiques sont créées ultérieurement dans `ANA`
  └─ RegisterSupersedingDceVersion
       → version antérieure lifecycle = SUPERSEDED
       → aucune suppression du contenu antérieur
```

### 5.3. Commandes et transitions `DceVersion`

| Commande | État avant autorisé | Préconditions métier | Mutation du root | État après | Domain Event |
|---|---|---|---|---|---|
| `RegisterDceVersion` | Aucun | Consultation existante même tenant ; original(s) admis ; hash corpus ; provenance/réception ; nouvelle `DceVersionKey`. | Crée DceVersion, DceDocuments et identité de corpus. | `ADMITTED`, intégrité évaluée, `UNCLASSIFIED`, `NOT_READY`. | `DceVersionRegistered`. |
| `RegisterSupersedingDceVersion` | Version source `ADMITTED` ou `SUPERSEDED` | Nouvelle version complète et lien officiel/source de rectificatif ; lien vers version précédente. | Crée **nouveau** root via `RegisterDceVersion`; commande aval distincte marque l’ancien `SUPERSEDED`. | Nouvelle `ADMITTED`; ancienne `SUPERSEDED`. | `DceVersionRegistered`, puis `DceVersionSuperseded`. |
| `ConfirmDocumentClassification` | `ADMITTED`, hors `WITHDRAWN` | Document interne existe ; classe métier autorisée ; annotateur habilité. | Ajoute annotation de classification. | `PARTIALLY_CLASSIFIED` ou `CLASSIFIED`. | `DceDocumentClassificationConfirmed`. |
| `CorrectDocumentClassification` | `ADMITTED` | Classification précédente identifiable ; motif/source ; aucune modification de l’original. | Ajoute annotation corrective avec prédécesseur. | Readiness recalculée. | `DceDocumentClassificationCorrected`. |
| `DeclareMissingDocument` | `ADMITTED` | Famille attendue, motif et source de l’attente. | Ajoute signalement de manque métier. | `integrity = PARTIAL`; analysis readiness peut rester ou devenir review required. | `DceDocumentMissingDeclared`. |
| `ReportDocumentIntegrityIssue` | `ADMITTED` | Document/version, type d’incident, localisation et impact connus. | Ajoute incident métier de fiabilité. | `PARTIAL` ou `UNUSABLE`. | `DceDocumentIntegrityIssueReported`. |
| `RegisterSourceStatement` | `ADMITTED`, integrity ≠ `UNUSABLE` | Localisation dans DceDocument/version, contenu/extrait et provenance ; pas de conclusion d’obligation. | Ajoute une ancre source interne, éventuellement issue d’une extraction confirmée. | analysis readiness recalculée. | `DceSourceStatementRegistered`. |
| `MarkDceVersionReadyForAnalysis` | `ADMITTED` | Intégrité `VERIFIED` ou `PARTIAL` explicitement acceptée ; classification/annexes suffisantes ; manques connus visibles. | Marque readiness sans affirmer l’exhaustivité. | `READY_FOR_ANALYSIS`. | `DceVersionReadyForAnalysis`. |
| `MarkDceVersionReviewRequired` | `ADMITTED` ou `SUPERSEDED` | Nouveau signal, rectificatif, incident ou correction de classification. | Marque le besoin de revue avec cause. | `REVIEW_REQUIRED`. | `DceVersionReviewRequired`. |
| `WithdrawDceVersion` | `ADMITTED` | Retrait acheteur ou erreur d’admission prouvée ; patron/administrateur habilité ; motif. | `lifecycle = WITHDRAWN`; contenu conservé. | `WITHDRAWN`. | `DceVersionWithdrawn`. |

### 5.4. Invariants `DceVersion`

| ID | Invariant non négociable | Vérification au moment de |
|---|---|---|
| `DCE-INV-01` | Toute DceVersion appartient à un seul tenant et une seule Consultation. | Création et toute référence. |
| `DCE-INV-02` | `corpus_hash` et originaux admis sont immuables après `RegisterDceVersion`. | Toute tentative de modification de contenu. |
| `DCE-INV-03` | Toute DceDocument appartient à une seule DceVersion ; son original n’est jamais écrasé. | Admission et annotations. |
| `DCE-INV-04` | Un SourceStatement référence une DceDocument/version et une localisation. Une `SourceAssertion` analytique peut le référencer, mais n’est pas possédée par DceVersion et ne devient jamais automatiquement Requirement ou BusinessFact. | `RegisterSourceStatement`. |
| `DCE-INV-05` | Une version rectificative crée un nouveau root et un lien de supersession ; elle ne remplace jamais le corpus antérieur. | `RegisterSupersedingDceVersion`. |
| `DCE-INV-06` | `PARTIAL` ou `UNUSABLE` interdit de présenter l’analyse comme exhaustive. | Read models et `MarkDceVersionReadyForAnalysis`. |
| `DCE-INV-07` | Une DceVersion `WITHDRAWN` reste lisible à des fins d’audit mais ne peut pas être nouvelle version applicable d’une Case. | `SetApplicableDceVersion`. |
| `DCE-INV-08` | `DceVersion` n’écrit jamais Case, Requirement, Decision, Pricing, Submission ou ImpactAssessment. | Handlers/repositories/tests d’architecture. |

### 5.5. Concurrence, idempotence et erreurs `DceVersion`

| Catégorie | Contrat |
|---|---|
| `expected_revision` | Obligatoire pour classification, incidents, source statements, readiness, retrait et supersession de la version existante. |
| Idempotence | Obligatoire pour admission, déclaration de manque, incident, source statement, readiness, supersession et retrait. |
| Concurrence corpus | La même `DceVersionKey` retourne le résultat du premier enregistrement ou `DCE_VERSION_DUPLICATE` si le payload diverge. |
| Erreurs | `CONSULTATION_REQUIRED`, `DCE_CORPUS_HASH_REQUIRED`, `DCE_VERSION_DUPLICATE`, `DOCUMENT_NOT_IN_VERSION`, `DOCUMENT_ORIGINAL_IMMUTABLE`, `SOURCE_LOCATION_REQUIRED`, `DCE_VERSION_UNUSABLE`, `DCE_VERSION_WITHDRAWN`, `VERSION_CONFLICT`, `STALE_CONTEXT`. |
| RYOW | Après admission, l’auteur voit la version, son hash, ses pièces et l’intégrité ; si l’analyse est différée, son statut reste explicitement `NOT_READY` ou `EVALUATION_EN_COURS`. |

---

# Partie III — `DEC/Decision`

## 6. Fiche d’aggregate : Decision

### 6.1. Responsabilité et contenu

`Decision` est le seul root du slice qui transforme un arbitrage patron en réalité engageante. Il fige exactement ce qui a été considéré ; il ne calcule pas, n’applique pas et ne modifie pas la Case ou les autres aggregates.

| Élément | Décision |
|---|---|
| **Root** | `Decision` |
| **Entités internes** | `DecisionContext`, `DecisionCondition`, acceptation de risque de suivi. |
| **Objets-valeur** | DecisionType, outcome, justification, `ContextFingerprint`, validity, dispositions de condition. |
| **FunctionalIdentity** | `DecisionKey = tenant_id + decision_type + subject_ref + scope_fingerprint + active_cycle`. |
| **Références** | Case, DceVersion, risks, SourceAssertions/Requirements, PreparationSnapshot, PricingVersion, SubmissionPackage selon type. |
| **Interdit** | Ne possède pas les artefacts référencés et n’écrit aucun autre root après sa finalisation. |

### 6.2. Axes d’état `Decision`

| Axe | Valeurs | Sens |
|---|---|---|
| `lifecycle` | `DRAFT`, `PENDING_PATRON`, `FINALIZED`, `SUPERSEDED`, `CANCELLED` | Cycle de préparation et d’existence de la décision. |
| `outcome` | `UNDECIDED`, `GO`, `CONDITIONAL_GO`, `NO_GO`, `ACCEPTED`, `REJECTED`, `AUTHORIZED`, `NOT_AUTHORIZED` | Choix selon le type de décision. |
| `validity` | `CURRENT`, `REVIEW_REQUIRED`, `SUPERSEDED`, `INVALIDATED` | Applicabilité du contexte finalisé. |
| `condition_status` | `NOT_APPLICABLE`, `OPEN`, `SATISFIED`, `FAILED`, `WAIVED` | État agrégé des conditions d’un Go conditionnel. |
| `context_status` | `INCOMPLETE`, `FROZEN`, `STALE` | Préparation du contexte et cohérence actuelle de ses références. |

Une décision `FINALIZED + GO + REVIEW_REQUIRED` reste historiquement vraie : elle n’est ni modifiée ni automatiquement annulée. Une nouvelle décision peut la superséder après examen du nouveau contexte.

### 6.3. Machine de cycle `Decision`

```text
CreateDecisionDraft
  → lifecycle = DRAFT, outcome = UNDECIDED, context_status = INCOMPLETE

PrepareDecisionContext
  → lifecycle = PENDING_PATRON, context_status = FROZEN

ApproveGoDecision
  → lifecycle = FINALIZED, outcome = GO, validity = CURRENT

ApproveConditionalGoDecision
  → lifecycle = FINALIZED, outcome = CONDITIONAL_GO, condition_status = OPEN, validity = CURRENT

ApproveNoGoDecision
  → lifecycle = FINALIZED, outcome = NO_GO, validity = CURRENT

Référence critique change / impact confirmé
  → validity = REVIEW_REQUIRED, context_status = STALE
  → contenu final intact

SupersedeDecision
  → lifecycle = SUPERSEDED, validity = SUPERSEDED
  → nouvelle Decision créée par commande distincte et référencée
```

### 6.4. Commandes et transitions `Decision`

| Commande | État avant autorisé | Préconditions métier | Mutation du root | État après | Domain Event |
|---|---|---|---|---|---|
| `CreateDecisionDraft` | Aucun | Patron/délégataire habilité ; type de décision, sujet et scope précisés ; `DecisionKey` libre. | Crée Decision et contexte incomplet. | `DRAFT + UNDECIDED + INCOMPLETE`. | `DecisionDraftCreated`. |
| `PrepareDecisionContext` | `DRAFT` ou `PENDING_PATRON` | Références exigées par DecisionType ; versions exactes, inconnus, risques et sources présents ; fingerprint calculé. | Fige `DecisionContext` interne pour soumission patron. | `PENDING_PATRON + FROZEN`. | `DecisionContextPrepared`. |
| `RefreshDecisionContextBeforeFinalization` | `DRAFT` ou `PENDING_PATRON` | Uniquement avant finalisation ; référence mise à jour avec provenance. | Crée contexte interne suivant/remplace contexte de travail non final. | `PENDING_PATRON + FROZEN`. | `DecisionContextRefreshed`. |
| `ApproveGoDecision` | `PENDING_PATRON` | Acteur patron habilité ; context fingerprint présenté = fingerprint courant ; DCE/preparation/risk requis compatibles ; aucune condition obligatoire ouverte. | Fige choix et signature patron. | `FINALIZED + GO + CURRENT`; `NOT_APPLICABLE`. | `GoDecisionApproved`. |
| `ApproveConditionalGoDecision` | `PENDING_PATRON` | Patron habilité ; contexte actuel ; une ou plusieurs conditions avec libellé, owner, échéance ou raison, conséquence de non-réalisation. | Fige choix et conditions internes. | `FINALIZED + CONDITIONAL_GO + CURRENT + OPEN`. | `ConditionalGoDecisionApproved`. |
| `ApproveNoGoDecision` | `PENDING_PATRON` | Patron habilité ; contexte frozen ; justification de refus. | Fige non-poursuite. | `FINALIZED + NO_GO + CURRENT`. | `NoGoDecisionApproved`. |
| `RecordDecisionConditionSatisfied` | `FINALIZED + CONDITIONAL_GO + OPEN` | Preuve/constat référencé ; acteur autorisé ; condition existante. | Marque condition satisfaite. | `condition_status = SATISFIED` si toutes satisfaites, sinon `OPEN`. | `DecisionConditionSatisfied`. |
| `RecordDecisionConditionFailed` | `FINALIZED + CONDITIONAL_GO + OPEN` | Motif, source et conséquence de non-réalisation. | Marque condition échouée. | `condition_status = FAILED`; validity peut devenir `REVIEW_REQUIRED`. | `DecisionConditionFailed`. |
| `WaiveDecisionCondition` | `FINALIZED + CONDITIONAL_GO + OPEN` | Patron habilité ; motif explicite ; contrôle de politique. | Marque condition waived. | `WAIVED` ou agrégat `SATISFIED` si toutes closes. | `DecisionConditionWaived`. |
| `MarkDecisionReviewRequired` | `FINALIZED + CURRENT` | Impact/rectificatif/référence critique identifié(e), corrélé(e) et pertinent(e). | Marque applicability à revoir sans toucher choix ni contexte. | `validity = REVIEW_REQUIRED`; `context_status = STALE`. | `DecisionMarkedReviewRequired`. |
| `SupersedeDecision` | `FINALIZED`, `REVIEW_REQUIRED` ou `CURRENT` selon politique | Nouvelle Decision finalisée du même type/sujet/scope ; justification de remplacement. | Marque ancienne Decision supersédée ; référence successor. | `SUPERSEDED + validity SUPERSEDED`. | `DecisionSuperseded`. |
| `CancelDecisionDraft` | `DRAFT` ou `PENDING_PATRON` | Motif ; aucune finalisation. | Annule la préparation, contexte conservé pour audit. | `CANCELLED`. | `DecisionDraftCancelled`. |

### 6.5. Matrice `DecisionType` et contexte minimal

| Type de décision | Sujet obligatoire | Références minimales du contexte | Outcome autorisés | Conséquence aval possible |
|---|---|---|---|---|
| `GO_NO_GO` | Case + CaseScope | DceVersion applicable, readiness, inconnus, risques, capacities/preuves disponibles, échéance. | `GO`, `CONDITIONAL_GO`, `NO_GO`. | Mise à jour de stage Case par commande aval ; Action patron/Task si conditions. |
| `RISK_ACCEPTANCE` | Risk + Case | Risk, Finding/SourceAssertion, conséquences, protections possibles, owner. | `ACCEPTED`, `REJECTED`. | Action/plan de protection par commande aval. |
| `PARTNER_SELECTION` | Partner + CaseScope | Profil partenaire, réponse/revue, preuves/qualifications, inconnus. | `ACCEPTED`, `REJECTED`. | Demande/partage ou préparation, jamais prix implicite. |
| `PRICING_APPROVAL` | OfficialPricingVersion + Case | Version prix, version DCE, calcul déterministe, hypothèses et risques ; patron seul. | `AUTHORIZED`, `NOT_AUTHORIZED`. | Stage Case / SubmissionPackage par commandes aval. |
| `SUBMISSION_AUTHORIZATION` | SubmissionPackage + Case | Package fingerprint, DCE, prix officiel, décision de prix, contrôles, autorisation patron. | `AUTHORIZED`, `NOT_AUTHORIZED`. | Autorisation de SubmissionPackage via commande aval. |

### 6.6. Invariants `Decision`

| ID | Invariant non négociable | Vérification au moment de |
|---|---|---|
| `DEC-INV-01` | Une Decision appartient à un seul tenant, type, sujet et scope explicites. | Création et finalisation. |
| `DEC-INV-02` | Une Decision finalisée sélectionne exactement un `DecisionContext` immuable et son `ContextFingerprint`; les contextes de travail antérieurs restent archivés mais ne sont plus modifiables. | Toute approbation. |
| `DEC-INV-03` | Seul un patron ou délégataire explicitement autorisé peut finaliser une Decision. Une IA, projection ou collaborateur standard ne le peut jamais. | Approbations/finalisation. |
| `DEC-INV-04` | Une Decision finalisée ne change ni outcome ni contexte ; une nouvelle décision doit la superséder. | Toute mutation post-finalisation. |
| `DEC-INV-05` | Un `CONDITIONAL_GO` possède au moins une condition avec libellé, owner, échéance ou raison, et conséquence de non-réalisation. | `ApproveConditionalGoDecision`. |
| `DEC-INV-06` | Toute référence du contexte appartient au tenant, à la Case/scope visé(e) ou est explicitement autorisée par sa relation métier. | `PrepareDecisionContext`. |
| `DEC-INV-07` | Un fingerprint de contexte différent entre prévisualisation et approbation produit `STALE_CONTEXT`. | Toutes approbations. |
| `DEC-INV-08` | `MarkDecisionReviewRequired` n’annule ni ne réécrit une décision ; il modifie seulement sa validity. | Réaction à un impact. |
| `DEC-INV-09` | Une décision supersédée reste lisible et pointe vers sa successeure ; le contexte initial demeure reconstructible. | `SupersedeDecision`. |
| `DEC-INV-10` | Une Decision ne calcule pas de prix, ne crée pas de tâche, ne modifie pas Case ni ne dépose. | Test d’architecture. |

### 6.7. Concurrence, idempotence et erreurs `Decision`

| Catégorie | Contrat |
|---|---|
| `expected_revision` | Obligatoire pour toute mutation hors création de brouillon. |
| Révisions de références | À la finalisation, commandes vérifient les références critiques et `ContextFingerprint`; elles ne se contentent pas de l’`aggregate_revision` Decision. |
| Idempotence | Obligatoire pour create, prepare, approve, condition, review-required, supersede et cancel. |
| Erreurs | `DECISION_TYPE_REQUIRED`, `DECISION_SUBJECT_REQUIRED`, `PATRON_AUTHORIZATION_REQUIRED`, `DECISION_CONTEXT_INCOMPLETE`, `DECISION_CONTEXT_FINGERPRINT_MISMATCH`, `CONDITION_OWNER_REQUIRED`, `CONDITION_CONSEQUENCE_REQUIRED`, `DECISION_ALREADY_FINALIZED`, `STALE_CONTEXT`, `VERSION_CONFLICT`. |
| RYOW | Après approbation, le patron voit immédiatement outcome, validity, context fingerprint, conditions et effets de processus « en cours » sans attendre les projections. |

---

# Partie IV — Processus inter-aggregates du premier slice

## 7. Process Managers autorisés

Les processus suivants sont explicitement autorisés. Aucun handler `Case`, `DceVersion` ou `Decision` ne peut appeler directement le handler d’un autre root.

| Process Manager | Événement déclencheur | Commande(s) aval | Garantie utilisateur |
|---|---|---|---|
| `DecisionOutcomeProcess` | `GoDecisionApproved`, `ConditionalGoDecisionApproved`, `NoGoDecisionApproved` | `StartOfferPreparation`, `ReturnCaseToPreparation` ou `StopCase` selon outcome et policy. | La Decision est immédiatement finalisée ; la Case affiche `MISE_A_JOUR_DU_CYCLE_EN_COURS` jusqu’au commit aval. |
| `DceSupersessionProcess` | `DceVersionRegistered` avec prédécesseur | `MarkDceVersionReviewRequired` sur ancienne version, `EvaluateDceChangeImpact` hors slice, marquage de Case/Decision à revoir via commandes distinctes. | Nouvelle version visible immédiatement ; impacts et fraîcheur affichent traitement en cours, jamais « tout est à jour » par défaut. |
| `DecisionStalenessProcess` | `DceImpactApplied` ou référence critique modifiée | `MarkDecisionReviewRequired`. | Décision historique reste visible avec badge `A_REVOIR`, sans disparition ni annulation cachée. |
| `CaseDceApplicabilityProcess` | `DceVersionWithdrawn` ou version cible rendue applicable | `SetApplicableDceVersion` ou `MarkCaseDceReviewRequired` par commande patron/policy explicitée. | Case affiche DCE applicable ou `REVUE_DCE_REQUISE`, jamais une version déduite silencieusement. |

Toutes les commandes aval portent le même `correlation_id` et un `caused_by_event_id`. Le Process Manager conserve l’état de séquencement et de reprise, pas les données métier du root.

---

# Partie V — Tests de gel DOMAIN-03

## 8. Tests de transition et d’invariant

| ID | Scénario | Résultat attendu |
|---|---|---|
| `DOM03-CASE-01` | Création Case avec deux lots sans `CaseScope` justifié. | Refus `CASE_SCOPE_AMBIGUOUS`; aucune Case. |
| `DOM03-CASE-02` | Case `STOPPED` reçoit `StartCasePricing`. | Refus `CASE_LIFECYCLE_FORBIDS_ACTION`; stage historique inchangé. |
| `DOM03-CASE-03` | `MoveCaseToPricing` sans Decision Go, transmission acceptée ou DCE fraîche. | Refus explicite avec conditions manquantes ; aucune écriture prix. |
| `DOM03-CASE-04` | Rectificatif DCE reçu après une Case prête à chiffrer. | Case conserve son stage jusqu’à commande ciblée ; `dce_freshness = REVIEW_REQUIRED`; aucun prix/décision supprimé. |
| `DOM03-CASE-05` | `RecordCaseSubmissionDeclared` sans accusé. | Case devient éventuellement `SUBMITTED`, jamais « dépôt prouvé ». |
| `DOM03-CONS-01` | Création d’une Consultation avec même acheteur/référence externe dans le même tenant. | Retourne la Consultation existante par idempotence ou `DUPLICATE_FUNCTIONAL_IDENTITY`; aucun doublon. |
| `DOM03-CONS-02` | Fermeture Consultation avec Case active. | Consultation se ferme sans supprimer Case/DceVersion ; Case conserve l’historique et reçoit un traitement explicite si nécessaire. |
| `DOM03-DCE-01` | Admission d’un corpus DCE puis tentative de modification du hash/original. | Refus `DOCUMENT_ORIGINAL_IMMUTABLE`; revision et hash inchangés. |
| `DOM03-DCE-02` | Déclaration de rectificatif. | Nouvelle DceVersion créée, prédécesseur relié/supersédé ; aucun document antérieur remplacé. |
| `DOM03-DCE-03` | Extraction IA produit une CandidateAssertion. | Elle peut être reliée à un SourceStatement confirmé, mais ne devient pas automatiquement SourceAssertion analytique, Requirement, BusinessFact ou Decision. |
| `DOM03-DCE-04` | DceVersion integrity `UNUSABLE` est utilisée pour présenter une analyse complète. | Refus du read model/commande avec état explicite de non-fiabilité. |
| `DOM03-DEC-01` | Collaborateur standard appelle `ApproveGoDecision`. | Refus `PATRON_AUTHORIZATION_REQUIRED`; aucune Decision finalisée. |
| `DOM03-DEC-02` | Patron approuve avec fingerprint différent de la prévisualisation. | Refus `STALE_CONTEXT`; Decision reste `PENDING_PATRON`. |
| `DOM03-DEC-03` | Go conditionnel sans owner ou conséquence de condition. | Refus `CONDITION_OWNER_REQUIRED` ou `CONDITION_CONSEQUENCE_REQUIRED`. |
| `DOM03-DEC-04` | Tentative de modifier outcome ou contexte d’une Decision finalisée. | Refus `DECISION_ALREADY_FINALIZED`; seule `SupersedeDecision` est possible. |
| `DOM03-DEC-05` | Rectificatif DCE touche une référence d’une Decision Go. | Choice/context historique inchangés ; `validity = REVIEW_REQUIRED` via commande aval corrélée. |
| `DOM03-CONC-01` | Deux demandes concurrentes déplacent la même Case d’`ANALYSIS` à des stages incompatibles. | Une réussite ; seconde `VERSION_CONFLICT`, aucune fusion dernier-écrit-gagne. |
| `DOM03-CONC-02` | Double clic même clé sur `ApproveNoGoDecision`. | Un outcome finalisé, un Domain Event, même résultat rejoué au second appel. |
| `DOM03-ARCH-01` | `CaseHandler` sauvegarde DceVersion ou Decision dans sa transaction. | Échec de test d’architecture. |
| `DOM03-ARCH-02` | `DecisionHandler` change directement le stage Case après Go. | Échec de test d’architecture ; seul `DecisionOutcomeProcess` peut l’orchestrer. |
| `DOM03-ARCH-03` | Relation ORM Case → Decision/DceVersion comporte cascade de suppression. | Échec de test d’architecture et de migration. |
| `DOM03-TENANT-01` | Commande référence Consultation/DceVersion/Decision d’un autre tenant. | Réponse neutre `NOT_FOUND_OR_FORBIDDEN`; aucune fuite d’existence. |

## 9. Prérequis de passage aux modèles Pydantic et SQLAlchemy

Le premier slice ne peut entrer en implémentation que lorsque les conditions suivantes sont réunies.

| Condition de passage | Preuve attendue |
|---|---|
| Fiches `Case`, `Consultation`, `DceVersion`, `Decision` validées | Validation explicite du fondateur sur les états, transitions et interdits. |
| Contrats de commande | Schémas Pydantic dérivés des champs et erreurs DOMAIN-03, sans champs de confiance côté client. |
| Repositories | Un repository par root, révision optimiste, tenant obligatoire et aucune cascade inter-root. |
| Tests de domaine | Les scénarios de la section 8 exécutent les transitions sans FastAPI, SQLAlchemy ou UI. |
| Tests d’architecture | Cross-write, handler-to-handler, import circulaire et cascade inter-aggregate sont bloqués automatiquement. |
| Process Managers | `DecisionOutcomeProcess` et `DceSupersessionProcess` sont explicitement enregistrés, idempotents et corrélés avant usage. |

---

## Références internes

- `SMART_AO_V8_CONTRAT_DE_DOMAINE.md` — contrat de domaine V8 v1.2.
- `SMART_AO_V8_DOMAIN_01_AGGREGATE_OWNERSHIP_MATRIX.md` — DOMAIN-01 v1.1.
- `SMART_AO_V8_DOMAIN_02_SPEC_COMMANDES_COLLABORATEUR.md` — DOMAIN-02 v1.0.
- `SMART_AO_V8_MATRICE_TRANSITIONS_METIER.md` — transitions patron.
- `SMART_AO_V8_MATRICE_VUE_ACTION_COLLABORATEUR.md` — transitions collaborateur.
- `SMART_AO_V8_SPEC_COMMANDES_IDEMPOTENCE.md` — conventions de commande et idempotence patron.

---

**Fin de DOMAIN-03 — State Machines & Invariant Catalog — Premier slice — version 1.0**
