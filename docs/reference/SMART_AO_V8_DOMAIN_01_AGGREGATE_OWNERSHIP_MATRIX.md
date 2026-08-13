# SMART_AO V8 — DOMAIN-01
## Aggregate / Ownership / Consistency Matrix

**Version :** 1.1 — clarification métier/exécution et corrections d’ownership  
**Statut :** contrat de conception à valider avant modèles Pydantic, SQLAlchemy, repositories et API d’écriture  
**Auteur :** Manus AI  
**Périmètre :** noyau V8 patron, collaborateur et chaîne analytique DCE  

---

## 1. Objet et décision de gel

Cette matrice transforme le Contrat de domaine V8 en décisions de conception exploitables. Elle ne redessine pas les écrans et n’ajoute pas de fonctionnalité. Elle répond à une seule question : **quelle réalité possède réellement une mutation, quelles données peut-elle changer atomiquement, et lesquelles doit-elle seulement référencer ?**

> **Décision DOMAIN-01 :** une transaction d’écriture V8 modifie **un seul aggregate racine** et ses entités internes. Elle peut lire et vérifier d’autres aggregates, mais ne les modifie pas dans le même commit métier. Les conséquences inter-frontières passent par un événement, une outbox transactionnelle, puis une commande aval idempotente.

Cette règle interdit explicitement les faux raccourcis suivants : modifier une affaire, une tâche, une décision et un prix dans une même méthode ; stocker les preuves comme enfants mutables de l’affaire ; ou laisser une projection Cockpit devenir propriétaire de l’état métier.

| Décision de structure | Règle figée |
|---|---|
| **Frontière ≠ aggregate** | Les 19 frontières ci-dessous sont des bounded contexts ou des responsabilités. Certaines contiennent plusieurs aggregates. |
| **Affaire minimale** | `Case` conserve identité, périmètre, cycle et responsabilité courante ; elle référence les autres réalités. |
| **Source ≠ interprétation** | `DceVersion` possède les originaux et `SourceStatement` localisés ; `SourceAssertion` et `Requirement` portent les interprétations sourcées dans `ANA`. |
| **Fait ≠ événement** | Un `SourceAssertion` décrit le monde métier ; un `DomainEvent` décrit un changement accepté. Aucun modèle ne fusionne les deux. |
| **Historique non destructif** | Les versions, décisions, prix officiels, snapshots et dépôts validés sont créés ou supersédés ; ils ne sont jamais écrasés. |
| **Prix privé isolé** | Aucun aggregate, événement, projection ou résultat de commande non financier ne peut transporter coût, marge, devis ou trésorerie. |
| **Projections reconstruisibles** | Cockpit, Journal, listes, compteurs et wizard sont alimentés par événements ; ils ne mutent jamais un aggregate. |

---

## 2. Légende de lecture

| Terme | Signification dans cette matrice |
|---|---|
| **Aggregate racine** | Objet qui garantit ses invariants dans une transaction atomique et porte `aggregate_revision`. |
| **Entité interne** | Objet identifié dont le cycle dépend du root. Il est modifié seulement via ce root. |
| **Objet-valeur (VO)** | Valeur sans identité autonome ; remplacée comme un tout. |
| **OWNS** | Propriété atomique : même cycle de conservation et même transaction. |
| **REFERENCES** | Lien par identifiant vers un autre aggregate ; aucune permission de le modifier. |
| **DERIVED_FROM** | Résultat interprété ou calculé à partir d’une source versionnée. |
| **COVERS** | Lien explicite entre preuve versionnée et exigence, avec un état de couverture. |
| **AFFECTS** | Impact qui rend un autre objet à revoir sans le modifier directement. |
| **EMITS** | Émet un Domain Event après une mutation métier durable et observable. |
| **CONSUMES** | Réagit à un Integration Event uniquement via une commande ou un Process Manager déclaré ; jamais par écriture directe du root externe. |
| **Outbox** | Ligne écrite dans la même transaction que la mutation, l’événement et le résultat d’idempotence. |
| **RYOW** | *Read-your-own-write* : le demandeur voit immédiatement le résultat durable ou un statut de traitement explicite. |

Les écritures indiquées comme **critiques** doivent obligatoirement utiliser : contexte tenant résolu côté serveur, autorisation, `expected_revision` lorsque le root existe déjà, clé d’idempotence, empreinte canonique de requête et résultat mémorisé.

---

## 3. Carte des 19 bounded contexts et de leurs aggregates

Les 19 contextes correspondent au périmètre convenu : 9 patron, 9 collaborateur et 1 contexte analytique. Les lignes analytiques détaillées de la section 5 ne créent pas de nouveaux bounded contexts : elles précisent les aggregates du contexte `ANA`.

| Code | Bounded Context | Aggregate(s) racine(s) retenu(s) | Décision |
|---|---|---|---|
| `ORG` | Entreprise et bibliothèque métier | `CompanyProfile`, `CompanyCapability`, `CompanyReference`, `PartnerProfile`, `CompanyPolicy` | Plusieurs roots légers ; aucun objet `Entreprise` géant. |
| `OPP` | Veille et opportunités | `OpportunityProfile`, `Opportunity` | L’opportunité n’est jamais mutée en affaire. |
| `AFF` | Continuité commerciale de l’affaire | `Case` | Aggregate minimal ; références croisées seulement. |
| `DCE` | Consultation et pièces acheteur | `Consultation`, `DceVersion` | Consultation stable ; version DCE immuable et versionnée. |
| `ANA` | Analyse, exigences, conformité et risques | `SourceAssertion`, `Requirement`, `Coverage`, `Assessment`, `Finding`, `Risk`, `ProtectionPlan` | Chaîne analytique explicite ; aucun aggregate `Analysis` fourre-tout. |
| `ACT` | Action patron | `PatronAction` | Work item de gouvernance, distinct d’une tâche et d’une décision. |
| `DEC` | Décision humaine | `Decision` | Contexte figé et conditions internes ; patron uniquement. |
| `PRF` | Preuves et documents d’entreprise | `EvidenceRecord` | Original/version/droits d’usage ; preuve distincte de sa couverture. |
| `PRX` | Prix privé | `PricingScenario`, `OfficialPricingVersion` | Scénario mutable séparé de la version officielle immuable. |
| `DEP` | Paquet et dépôt | `SubmissionPackage` | Contrôle, manifest, autorisation, dépôt déclaré et accusé restent cohérents autour du même paquet versionné. |
| `ASN` | Affectation, compte métier et délégation | `CollaboratorMembership`, `Assignment`, `DelegationGrant` | Identité technique hors périmètre ; droits métier versionnés ici. |
| `TSK` | Travail préparatoire | `Task` | Porte résultats, blocages et dépendances sortantes. |
| `DMD` | Demandes et réponses | `Request` | Réponses versionnées, jamais assimilées automatiquement à une preuve. |
| `REV` | Revue humaine | `Review` | Porte uniquement le jugement sur une version précise. |
| `PRE` | Préparation et réponse technique vivantes | `PreparationPackage`, `ResponseDraft` | Paquet vivant séparé des brouillons rédactionnels versionnés. |
| `SNP` | Instantané de préparation | `PreparationSnapshot` | Append-only, immuable, hashé. |
| `TRN` | Transmission au patron | `PreparationTransmission` | Réception, retour et acceptation sans devenir une décision. |
| `SHR` | Partage externe | `ExternalShare` | Accès ponctuel et limité à des versions précises. |
| `IMP` | Impact de rectificatif DCE | `ImpactAssessment` | Relie les versions DCE et les objets affectés sans modifier ceux-ci directement. |

---

## 4. Règles transverses de propriété et de transaction

### 4.1. Ce qui peut être atomique

Dans une transaction, un handler peut modifier le root visé, ses entités internes, sa révision, ses événements internes, son outbox et l’entrée de résultat idempotent. Il peut aussi vérifier des références externes dans une lecture cohérente ou sous verrou court lorsque la décision est critique. Il ne peut pas écrire le root externe lui-même.

| Exemple | Écriture atomique autorisée | Conséquence interdite dans la même transaction | Propagation correcte |
|---|---|---|---|
| `ApproveConditionalGoDecision` | `Decision` + `DecisionContext` + conditions internes + événement + outbox. | Créer directement les `Task` et `PatronAction` de suivi. | `ConditionalGoDecisionApproved` déclenche des commandes `OpenPatronAction` et `CreateTask`. |
| `AssignCaseResponsibility` | `Assignment` et son périmètre. | Modifier directement `Case.current_responsible_assignment_id`. | `AssignmentActivated` fait recalculer la responsabilité courante dans la projection ou via commande `RefreshCaseResponsibility`. |
| `RegisterDceVersion` | `DceVersion`, documents et énoncés sources internes. | Marquer directement prix, décision, tâche ou snapshot comme obsolètes. | `DceVersionRegistered` déclenche `EvaluateDceChangeImpact`. |
| `SubmitPreparationForPatronReview` | `PreparationSnapshot` **ou** `PreparationTransmission`, selon la commande scindée indiquée ci-dessous. | Créer directement une `PatronAction`. | L’événement publié déclenche `OpenPatronAction`. |
| `ArchiveSubmissionReceipt` | `SubmissionPackage` et reçu interne rattaché au paquet. | Modifier le cycle `Case` comme « gagné » ou « terminé ». | `SubmissionAcknowledgementArchived` alimente l’affaire et le cockpit. |

### 4.2. Séquence obligatoirement scindée : transmission de préparation

La fonctionnalité visible « Transmettre au patron » correspond à trois roots, donc à trois mutations indépendantes :

```text
1. CreatePreparationSnapshot
   → PreparationSnapshotCreated
2. CreatePreparationTransmission(snapshot_id)
   → PreparationSubmittedToPatron
3. OpenPatronAction(cause=PREPARATION_TO_REVIEW)
   → PatronActionOpened ou PatronActionCauseAdded
```

L’orchestrateur conserve le même `correlation_id`. Chaque étape est idempotente. En cas de reprise réseau après l’étape 1, il ne crée pas un second snapshot ; en cas d’échec après l’étape 2, l’action patron peut être rattrapée par l’outbox.

Les autres intentions visibles qui touchent plusieurs réalités suivent la même discipline. Le nom affiché au patron ou au collaborateur reste simple ; le traitement durable est scindé sans ambiguïté.

| Intention visible | Mutation propriétaire initiale | Événement | Commande(s) aval indépendante(s) |
|---|---|---|---|
| Déléguer la préparation d’une action patron | `PatronAction` enregistre la délégation attendue. | `ActionPreparationDelegated` | `CreateTaskForActionPreparation` sur `Task`. |
| Transmettre une opportunité pour qualification | `Opportunity` enregistre la demande de qualification. | `OpportunityQualificationDelegated` | `CreateOpportunityQualificationTask` sur `Task`, puis affectation si nécessaire. |
| Créer une demande partenaire avec pièces | `Request` crée l’attente et son objet demandé. | `PartnerRequestCreated` | `GrantExternalShare` sur `ExternalShare` pour les seules versions autorisées. |
| Demander un devis fournisseur | `PricingScenario` enregistre le besoin de coût et son périmètre. | `SupplierQuoteRequested` | `CreateSupplierQuoteRequest` sur `Request`, puis partage éventuel. |
| Retourner une revue avec corrections | `Review` enregistre verdict et corrections. | `ReviewReturnedWithCorrections` | `CreateCorrectionTask` ou `ReopenTaskForCorrections` sur `Task`. |
| Go sous conditions | `Decision` fige la décision et ses conditions. | `ConditionalGoDecisionApproved` | `OpenPatronAction` et/ou `CreateTaskForDecisionCondition`, selon chaque condition. |
| Nouveau DCE ou impact appliqué | `DceVersion` ou `ImpactAssessment` conserve la source/impact. | `DceVersionRegistered` ou `DceImpactApplied` | Évaluations, marquages à revoir, actions, invalidations et recalculs, un root à la fois. |

### 4.3. Mise en œuvre pragmatique : monolithe modulaire, pas architecture distribuée

DOMAIN-01 fixe des **frontières de cohérence métier**. Il ne prescrit ni microservices, ni bases séparées, ni bus distribué. Le premier produit V8 reste un monolithe modulaire sur une PostgreSQL unique : modules séparés, schémas et repositories par aggregate, transactions courtes, handlers explicites, événements locaux et outbox seulement lorsqu’une projection, un worker ou une intégration doit réagir après le commit.

La règle « un aggregate propriétaire par transaction métier » est la règle par défaut V8. Les écritures techniques cohérentes avec ce root — registre d’idempotence, événement, outbox, audit et artefact versionné interne — font partie de la même transaction et **ne sont pas des aggregates métier co-propriétaires**.

Une exception future autorisant une écriture business multi-roots n’est recevable que si elle est ajoutée à DOMAIN-01 avec : la commande normalisée, les roots écrits, l’invariant impossible à garantir par orchestration, l’ordre de verrouillage, le niveau d’isolation, la reprise de transaction et un test de concurrence dédié. **Aucune exception business de ce type n’est autorisée dans le catalogue V8 initial.**

| Périmètre de mise en œuvre | Décision |
|---|---|
| **Premier slice de code** | `Case`, `Consultation/DceVersion`, `Decision` et leurs événements/projections minimales ; tests de tenant, versions, idempotence et absence d’écrasement. |
| **Slice analytique suivant** | `EvidenceRecord`, `SourceAssertion`, `Requirement`, `Finding` puis `Coverage`/`Assessment` selon les tests DCE réels. |
| **Slice collaboration** | `Assignment`, `Task`, `PreparationPackage`, `PreparationSnapshot`, `PreparationTransmission`, avec autorisation contextualisée. |
| **Slice patron engageant** | `PatronAction`, `PricingScenario`, `OfficialPricingVersion`, `SubmissionPackage`, avec confidentialité financière et outbox robuste. |
| **Différé jusqu’à preuve métier** | Enrichissements persistants de calcul, évaluation riche, opérations IA, workers spécialisés et projections avancées, sans remettre en cause les ownerships déjà figés. |

### 4.4. Politique commune de concurrence

| Catégorie | `expected_revision` | Cohérence requise | Réponse au conflit |
|---|---|---|---|
| Création pure, identifiant nouveau | Non, sauf déduplication métier. | Strong commit + clé d’idempotence. | `IDEMPOTENCY_KEY_REUSED` ou `BUSINESS_RULE_VIOLATION`. |
| Mutation d’un root existant | Oui. | Strong consistency sur le root. | `VERSION_CONFLICT`, jamais dernier-écrit-gagne. |
| Décision, prix, autorisation, dépôt | Oui pour le root et références critiques. | Transaction renforcée ; `decision_context_hash` ou fingerprint exigé. | `STALE_CONTEXT` ou `VERSION_CONFLICT`. |
| Projection, compteur, cockpit | Non pour l’interface. | Eventual consistency, fraîcheur affichée. | `PROJECTION_PENDING`, pas de seconde commande. |
| Effet asynchrone externe | Non dans la transaction métier. | Outbox après commit. | Reprise par worker avec déduplication. |

---

# Partie I — Matrice structurelle : ownership, entités et relations

## 5. Contextes patron et socle documentaire

| Code / Aggregate racine | Entités internes et VO | OWNS atomiquement | REFERENCES / DERIVED_FROM / COVERS / AFFECTS |
|---|---|---|---|
| `ORG` — `CompanyProfile` | Entités : signataire, adresse légale. VO : identité légale, coordonnées, préférence de notification. | Profil propre à un tenant et ses coordonnées/habilitations métier. | `REFERENCES` memberships et politiques ; n’owns ni comptes d’authentification ni prix. |
| `ORG` — `CompanyCapability` | Entités : périodes de disponibilité déclarées. VO : capacité, portée, période, statut de vérification. | Une capacité mobilisable et ses déclarations propres à l’entreprise. | `REFERENCES` preuves, partenaire éventuel ; `DERIVED_FROM` source déclarée ou preuve. La confirmation pour une affaire appartient à `Assessment` dans `ANA`. |
| `ORG` — `CompanyReference` | Entités : métadonnées de référence. VO : chantier, rôle, période, droit d’usage, comparabilité. | Référence réutilisable et droits internes associés. | `REFERENCES` EvidenceRecord pour ses justificatifs ; `DERIVED_FROM` contrats/attestations ; ne possède jamais une preuve. |
| `ORG` — `PartnerProfile` | Entités : contacts, qualifications déclarées. VO : identité, rôle potentiel, périmètre, confidentialité. | Profil partenaire et informations de vérification propres. | `REFERENCES` preuves, affaires et partages ; n’owns ni `ExternalShare` ni décision de sélection. |
| `ORG` — `CompanyPolicy` | Entités : règles actives/historiques. VO : règle, portée, période d’effet, classe de confidentialité. | Politique interne versionnée. | `REFERENCES` CompanyProfile ; `AFFECTS` politiques de readiness, réemploi et confidentialité. |
| `OPP` — `OpportunityProfile` | Entités : critères et exclusions. VO : zone, métier, rayon, source, fréquence. | Profil de veille versionné et ses critères. | `REFERENCES` CompanyCapability, CompanyPolicy ; ne possède aucune opportunité détectée. |
| `OPP` — `Opportunity` | Entités : signaux source, notes de qualification. VO : identité externe, acheteur, lieu, objet, score explicable, motif d’écartement. | Opportunité et son cycle de qualification. | `REFERENCES` OpportunityProfile/version ; `DERIVED_FROM` source de veille ; `REFERENCES` Case après conversion, sans la posséder. |
| `AFF` — `Case` | Entités : liens d’origine, `CasePartnerApproval`, responsabilité commerciale historique. VO : `CaseScope`, origine, lifecycle, responsabilité courante, motif d’arrêt. | Identité, consultation/périmètre explicite, cycle commercial et relations légères de continuité. | `REFERENCES` Consultation, DceVersion courante, Assignment, Decision, Pricing, Submission, Preparation, ImpactAssessment. N’owns jamais documents, tâches, preuves, prix ni dépôts. |
| `DCE` — `Consultation` | Entités : lots et tranches source. VO : acheteur, référence externe, objet, lieu, source initiale. | Identité stable de consultation et description de ses lots. | `REFERENCES` Opportunity et Case ; est référencée par DceVersion. |
| `DCE` — `DceVersion` | Entités : `DceDocument`, `SourceStatement`, annotation métier de classification. VO : hash, provenance, date de réception, relation de supersession. | Version DCE et pièces acheteur immuables ; ancres source localisées. Les `SourceAssertion` analytiques les référencent sans être possédées par le DCE. Les extractions, incidents de parsing et traitements techniques sont des réalités `ENGINE/INFRA` référencées, pas des enfants de domaine. | `REFERENCES` Consultation, Case(s) concernée(s) ; `DERIVED_FROM` originaux ; `AFFECTS` ImpactAssessment. N’owns ni assertions interprétées, exigences ni décisions. |
| `PRF` — `EvidenceRecord` | Entités : `EvidenceVersion`, `UsageAuthorization`. VO : provenance, dates, confidentialité, périmètre d’usage, état de validité. | Original/référence de stockage, versions, métadonnées, droits d’usage et expiration. | `REFERENCES` CompanyCapability, PartnerProfile, Case ; `COVERS` Requirement via Coverage. N’owns ni Requirement ni prix. |
| `ACT` — `PatronAction` | Entités : causes, attente, délégation de préparation, résolution. VO : priorité, échéance, motif, statut de travail. | File de travail patron, déduplication de causes, attente, clôture/remplacement. | `REFERENCES` Case, Finding, Risk, Decision, Task, Request, ImpactAssessment. N’owns ni choix de décision ni tâche aval. |
| `DEC` — `Decision` | Entités : `DecisionContext`, condition, acceptation de risque. VO : type, outcome, lifecycle, validity, justification, empreinte contexte. | Choix humain, contexte immuable, conditions et relation de supersession. | `REFERENCES` Case, Risk, PricingVersion, DceVersion, Snapshot, sources/version IDs. N’owns ni actions/tâches créées pour appliquer ses conditions. |
| `PRX` — `PricingScenario` | Entités : hypothèse, poste privé, devis retenu. VO : Money, taux, marge, règle de calcul, version de calcul. | Scénario de travail privé et hypothèses modificables. | `REFERENCES` Case, DceVersion, SupplierQuote/Request, Evidence, Requirement/Assessment. N’owns aucune version officielle. |
| `PRX` — `OfficialPricingVersion` | Entités : manifest de calcul, postes figés, sources figées. VO : Money, contexte chiffrage, fiabilité, hash de calcul, statut. | Version officielle candidate ou validée, calculs déterministes et références figées. | `REFERENCES` PricingScenario, Case, DceVersion, Requirement/Assessment snapshots, Evidence, Decision. `AFFECTS` SubmissionPackage lorsque rendue à revoir. |
| `DEP` — `SubmissionPackage` | Entités : manifest de fichiers, rapport de contrôle, autorisation, déclaration de dépôt, accusé. VO : `SubmissionFingerprint`, plateforme, date/heure, statut, hash. | Paquet versionné, contrôles, fichiers figés, autorisation, dépôt déclaré et reçu. | `REFERENCES` Case, DceVersion, OfficialPricingVersion, Decision, Evidence/Document versions. N’owns ni prix ni décision. |

## 6. Contextes collaborateur

| Code / Aggregate racine | Entités internes et VO | OWNS atomiquement | REFERENCES / DERIVED_FROM / COVERS / AFFECTS |
|---|---|---|---|
| `ASN` — `CollaboratorMembership` | Entités : invitation, statut de membre. VO : fonction, période, motif de suspension. | Adhésion métier du collaborateur au tenant, invitation et suspension. | `REFERENCES` identité d’authentification externe. N’owns pas les affectations d’affaire. |
| `ASN` — `Assignment` | Entités : reconnaissance, indisponibilité déclarée, règles de périmètre. VO : rôle, `ResourceScope`, `CommandScope`, dates, classes de ressources. | Relation acteur × affaire × rôle × portée × durée. | `REFERENCES` CollaboratorMembership, Case, ressources autorisées. `AFFECTS` droits de Task/Request/Review/Preparation mais ne les modifie pas. |
| `ASN` — `DelegationGrant` | Entités : historique d’utilisation métier si requis. VO : délégant, bénéficiaire, verbes, ressource, période, motif. | Délégation ponctuelle et révocation/expiration. | `REFERENCES` Assignment ou patron, Case/ressource visée. N’owns pas le contenu partagé. |
| `TSK` — `Task` | Entités : résultat versionné, blocage, dépendance sortante, assignation, dérogation, commentaire métier. VO : finalité, état de travail, échéance, criticité. | Travail préparatoire, preuve de fin, dépendances et blocages. | `REFERENCES` Case, Assignment, Requirement, Finding, Request, Review, ImpactAssessment, Draft. N’owns jamais une réponse de demande ni une revue. |
| `DMD` — `Request` | Entités : réponses versionnées, relances, clarification. VO : demandeur, destinataire, objet, raison, délai, priorité, état. | Cycle demande/réponse et relances sur la même demande. | `REFERENCES` Case, Assignment, Task, PartnerProfile, ExternalShare, Evidence/Document. Une réponse `REFERENCES` seulement une preuve potentielle. |
| `REV` — `Review` | Entités : corrections demandées, décision de revue. VO : cible versionnée, niveau de revue, verdict, motif, auteur/date. | Revue d’une version précise et son verdict. | `REFERENCES` Task, RequestResponse, EvidenceVersion, ResponseDraftVersion, CandidateCommitment, DceVersion. `AFFECTS` des tâches via événements ; ne modifie jamais directement l’objet revu. |
| `PRE` — `PreparationPackage` | Entités : candidats documentaires, dérogations de readiness, résultats de contrôle. VO : readiness, blocages, avertissements, règles appliquées, version DCE de référence. | Contenu vivant de préparation, état de préparation et évaluation de disponibilité. | `REFERENCES` Case, DceVersion, Requirement, Coverage, Assessment, Finding, Risk, Task, Request, Review, EvidenceRecord, ResponseDraft. N’owns aucun prix ni decision patron. |
| `PRE` — `ResponseDraft` | Entités : versions de brouillon, `CandidateCommitment`, proposition de réemploi. VO : section, contenu, provenance, statut de rédaction. | Brouillon technique et engagements candidats identifiés dans ce brouillon. | `REFERENCES` Case, Assignment, Capability, Evidence, Requirement, PreparationPackage. `DERIVED_FROM` bibliothèque/version source ; n’owns pas une preuve ni une décision. |
| `SNP` — `PreparationSnapshot` | Entités : manifest canonique de références figées, statut d’applicabilité. VO : hash, auteur, date, readiness, contenu canonique. | Contenu append-only de préparation ; seul le statut d’applicabilité peut évoluer, par commande déclenchée après impact. | `REFERENCES` PreparationPackage, Case, Assignment, DceVersion, Requirement/Coverage/Assessment/Finding/Risk, EvidenceVersions, DraftVersions, Task/Request/Review states. `AFFECTS` Transmission uniquement par référence. |
| `TRN` — `PreparationTransmission` | Entités : accusé de réception, retour ciblé, motif de retrait. VO : destinataire, état, dates, motif. | Cycle de transmission d’un seul snapshot à un destinataire. | `REFERENCES` PreparationSnapshot, Case, patron/délégataire. `AFFECTS` Task et PatronAction par événements ; n’owns pas le snapshot. |
| `SHR` — `ExternalShare` | Entités : ressources partagées versionnées, traces d’accès métier si requises. VO : destinataire, verbes, expiration, confidentialité. | Autorisation externe ciblée et révocation/expiration. | `REFERENCES` PartnerProfile, Case, EvidenceVersion, DceDocument, Request. N’owns aucun document ni nouvelle version automatique. |
| `IMP` — `ImpactAssessment` | Entités : `ImpactItem`, revue humaine de l’impact. VO : source/cible DCE, confidence, type de changement, conséquence proposée, état. | Évaluation version DCE A → B et objets affectés avec justifications. | `REFERENCES` DceVersion source/cible, Case, Requirement, Coverage, Assessment, Finding, Task, Draft, PreparationPackage, Snapshot, Transmission, PricingVersion, SubmissionPackage, Decision. `AFFECTS` ces objets exclusivement par événements. |

## 7. Chaîne analytique : frontières d’aggregate explicites

| Aggregate racine analytique | Entités et VO | OWNS atomiquement | Relations et limite de responsabilité |
|---|---|---|---|
| `SourceAssertion` | Entités : observations/confirmations humaines. VO : assertion, provenance source, confidence, validity, temporalité. | Une interprétation structurée d’une ou plusieurs ancres `SourceStatement` ou EvidenceVersion, son niveau de certitude et ses confirmations/supersessions. | `DERIVED_FROM` SourceStatement/DceVersion ou EvidenceVersion ; `REFERENCES` Case/Scope. Ne décide pas qu’une obligation est satisfaite. |
| `Requirement` | Entités : liens aux faits, critères d’applicabilité, interprétations successives. VO : type, portée, échéance, mandatory flag, état, provenance. | Exigence interprétée et ses liens de provenance. | `DERIVED_FROM` SourceAssertion(s) ; `REFERENCES` Case, Scope, DceVersion. `COVERS` reçoit des Coverage, mais ne les possède pas. |
| `Coverage` | Entités : contributions de preuve/version. VO : état de couverture, portée, justification, validité. | Relation Requirement ↔ EvidenceVersion(s), état explicite et justification. | `REFERENCES` Requirement, EvidenceRecord/version, Case/Scope. N’évalue pas la capacité globale ; une version de preuve ne peut être changée ici. |
| `Assessment` | Entités : critères évalués, explications. VO : résultat, confidence, validité, règle/moteur, date de référence. | Évaluation Requirement × Capability × Coverage sur un contexte figé. | `REFERENCES` Requirement, CompanyCapability, Coverage, Case, DceVersion. `DERIVED_FROM` ces versions ; n’owns pas Finding. |
| `Finding` | Entités : observations détaillées, objets affectés, `FindingEvidenceLink`. VO : constat, sévérité, confidence, disposition, provenance. | Constat durable, son état et ses liens explicites vers les preuves/assertions qui le justifient. | `DERIVED_FROM` Assessment/SourceAssertion/ImpactAssessment ; `REFERENCES` Requirement, Coverage, Evidence, Case. `FindingEvidenceLink` référence une EvidenceVersion ou SourceAssertion, avec rôle et confidence. Peut `AFFECTS` Risk/Task/PatronAction sans les écrire. |
| `Risk` | Entités : facteurs, acceptations de suivi. VO : impact, probabilité, criticité, état, propriétaire de traitement. | Risque et ses facteurs/état de traitement. | `DERIVED_FROM` Finding/Requirement ; `REFERENCES` Case, Decision, ProtectionPlan. N’owns pas l’acceptation patron finale : elle appartient à Decision. |
| `ProtectionPlan` | Entités : mesures, jalons, liens de suivi. VO : stratégie, échéance, efficacité attendue, état. | Plan de réduction d’un risque et ses mesures abstraites. | `REFERENCES` Risk, Task, PatronAction, Request. Ne remplace jamais une tâche ni une action patron concrète. |

---

# Partie II — Matrice de cohérence : commandes, événements et projections

## 8. Patron, socle et DCE

| Aggregate | Transaction atomique et invariants | Commandes critiques, révision et idempotence | Événements, outbox et projections | Dépendances interdites |
|---|---|---|---|---|
| `CompanyProfile` | Profil + entités internes ; identité tenant immuable. | Mise à jour : `expected_revision` ; idempotence requise pour invitation liée. | `CompanyProfileUpdated`; outbox si vue entreprise/équipe concernée. Projections : Entreprise, santé. | Ne dépend pas de Case, Price ou Deposit. |
| `CompanyCapability` | Capacité + disponibilité interne ; aucune confirmation d’affaire cachée. | `CreateCompanyCapability`, `ConfirmCaseCapability` ; révision obligatoire après création ; clé pour création/confirmation. | `CompanyCapabilityCreated`, `CaseCapabilityConfirmed`; outbox oui. Projections : Entreprise, Affaire, préparation, santé. | Ne modifie ni Requirement, Coverage, Evidence, Decision ni Pricing. |
| `CompanyReference` | Référence + droit d’usage ; conservation de la source. | `CreateCompanyReference`, archive/version ; clé à la création. | `CompanyReferenceCreated`, `CompanyReferenceArchived`; outbox oui. Projections : Bibliothèque, réemploi. | Ne possède aucune réponse technique ni partage. |
| `PartnerProfile` | Profil + contacts + vérification interne. | `CreatePartnerProfile`, mise à jour contrôlée ; clé création ; revision mutation. | `PartnerProfileCreated`, `PartnerProfileUpdated`; outbox oui. Projections : Partenaires, demandes. | Ne sélectionne pas seul le partenaire pour une affaire et ne crée pas de partage. |
| `CompanyPolicy` | Une politique/version active par portée ; ancienne conservée. | Créer/activer/superséder politique ; clé sur activation ; revision. | `CompanyPolicyActivated`; outbox oui. Projections : readiness, confidentialité, réemploi. | Ne recalcule pas directement Task, Case ou Price. |
| `OpportunityProfile` | Profil + critères ; aucune opportunité enfant. | `CreateOpportunityProfile`, versionner critères ; clé création ; revision mutation. | `OpportunityProfileCreated`, `OpportunityProfileVersioned`; outbox oui. Projections : Radar, santé. | Ne crée pas directement des Case. |
| `Opportunity` | Cycle opportunité + notes ; conversion conserve le lien immuable. | `AcknowledgeOpportunity`, `DelegateOpportunityQualification`, `RejectOpportunity`; clé obligatoire pour délégation/rejet ; revision. | `OpportunityAcknowledged`, `OpportunityQualificationDelegated`, `OpportunityRejected`; outbox oui. Projections : Radar, journal. | Ne mute jamais en Case ; ne décide pas le Go/No-Go. |
| `Case` | Identité, scope, lifecycle, origine et liens internes ; périmètre non ambigu. | `CreateCase`, `StopCase`, `ArchiveCase`, `MoveCaseToDecision`, `MoveCaseToPricing`; clé création/arrêt/archivage ; revision pour mutation. | `CaseCreated`, `CaseStopped`, `CaseArchived`, `CaseReadyForDecision`, `CaseReadyForPricing`; outbox oui. Projections : portefeuille, cockpit, journal. | Ne possède pas Tâches, DCE docs, preuve, prix, dépôt, décision, snapshot. |
| `Consultation` | Lots/tranches internes ; identifiant acheteur stable. | Création/complément de consultation ; clé création ; revision mutation. | `ConsultationCreated`, `ConsultationLotRegistered`; outbox si radar/case impacté. | Ne modifie pas DceVersion, Case ou Requirement. |
| `DceVersion` | Version + documents + SourceStatements ; original et hash immuables après réception. | `RegisterDceVersion`, `ConfirmDocumentClassification`, `DeclareMissingDocument`, `ReportUnreadableDocument`; clé pour réception/incident ; revision pour classification. | `DceVersionRegistered`, `DceDocumentClassified`, `DceDocumentIssueReported`; outbox obligatoire. Projections : documents, affaire, analyse, impact. | Ne crée pas/valide pas Requirement, Price, Decision, Submission ou ImpactAssessment. |
| `EvidenceRecord` | Original/version + autorisations d’usage ; aucune suppression d’une version utilisée. | `AddEvidenceVersion`, `ReplaceEvidenceVersion`, `AuthorizeEvidenceForCase`, `ArchiveEvidence`; clé obligatoire ; revision sur record. | `EvidenceVersionAdded`, `EvidenceAuthorizedForCase`, `EvidenceArchived`; outbox obligatoire. Projections : bibliothèque, santé, affaire, préparation. | Ne confirme pas seule une couverture, une capacité ou une conformité. |
| `PatronAction` | Causes, attente, délégation interne, résolution et déduplication `cause + case + type + contexte`. | `OpenPatronAction`, acknowledge/await/resolve/close/cancel/replace ; clé ouverture/remplacement ; revision mutation. | `PatronActionOpened`, `PatronActionCauseAdded`, `PatronActionResolved`, `PatronActionClosed`; outbox oui. Projections : Action Center, cockpit, journal. | Ne crée pas de Decision, ne ferme pas de Task, ne valide pas Price. |
| `Decision` | Décision + contexte hashé + conditions ; outcome/lifecycle/validity séparés ; contexte final immuable. | `PrepareDecision`, `ApproveGoDecision`, `ApproveConditionalGoDecision`, `ApproveNoGoDecision`, `AcceptRiskWithRationale`, `SupersedeDecision`; clé obligatoire ; expected revisions des références critiques + hash. | `GoDecisionApproved`, `ConditionalGoDecisionApproved`, `NoGoDecisionApproved`, `RiskAcceptedWithRationale`, `DecisionSuperseded`; outbox obligatoire. Projections : dossier décision, portefeuille, actions, journal. | Ne calcule pas le prix, ne modifie pas Case/Task/Action directement, ne dépose pas. |
| `PricingScenario` | Scénario, hypothèses et calculs privés ; Money Decimal uniquement. | `CreatePricingScenario`, `ChangePricingScenarioAssumption`, `RequestSupplierQuote`; clé création/demande ; revision mutation. | `PricingScenarioCreated`, `PricingScenarioAssumptionChanged`, `SupplierQuoteRequested`; outbox oui, sans montant dans les topics non financiers. Projections : Prix privé uniquement, fiabilité. | Ne modifie aucune OfficialPricingVersion, Case, Decision ou SubmissionPackage. |
| `OfficialPricingVersion` | Version candidate/officielle, manifest de calcul, contexte et références de coûts immuables après validation. | `PrepareOfficialPricingVersion`, `ApprovePricingVersion`, `MarkPricingForReview`; clé obligatoire ; expected revisions `PRX`, `AFF`, `DCE` et sources critiques. | `OfficialPricingVersionPrepared`, `PricingVersionApproved`, `PricingMarkedForReview`; outbox obligatoire avec payload minimisé. Projections : Prix privé, affaire patron, coffre, action, journal. | Ne modifie ni Decision ni SubmissionPackage ; jamais visible au collaborateur. |
| `SubmissionPackage` | Manifest, contrôle, autorisation, déclaration et accusé ; package autorisé immuable. | `RunSubmissionControl`, `PrepareSubmissionPackage`, `AuthorizeSubmission`, `RecordSubmission`, `ArchiveSubmissionAcknowledgement`, `OpenNewResponseVersion`; clé obligatoire ; revision + fingerprint DCE/prix/décision. | `SubmissionControlCompleted`, `SubmissionPackagePrepared`, `SubmissionAuthorized`, `SubmissionRecorded`, `SubmissionAcknowledgementArchived`; outbox obligatoire. Projections : coffre, affaire, cockpit, journal. | Ne calcule pas le prix, ne crée pas de décision, ne déclare jamais « dépôt prouvé » sans accusé. |

## 9. Collaboration, préparation et impact

| Aggregate | Transaction atomique et invariants | Commandes critiques, révision et idempotence | Événements, outbox et projections | Dépendances interdites |
|---|---|---|---|---|
| `CollaboratorMembership` | Invitation/suspension ; historique conservé, accès futur coupé. | `InviteCollaborator`, `SuspendCollaborator`; clé obligatoire ; revision mutation. | `CollaboratorInvited`, `CollaboratorSuspended`; outbox oui. Projections : équipe, alertes de réattribution. | Ne révoque pas directement Assignment/Task ; événements aval déclenchent le traitement. |
| `Assignment` | Acteur × Case × role × scopes × période ; absence de droit = refus. | `AssignCaseResponsibility`, `ReassignCaseResponsibility`, `AcknowledgeAssignment`, `ReportAssignmentUnavailability`, revoke/expire; clé obligatoire ; revision. | `AssignmentActivated`, `AssignmentScopeChanged`, `AssignmentRevoked`, `AssignmentAcknowledged`; outbox obligatoire. Projections : mes affaires, équipe, mon travail, cockpit limité. | Ne contient pas des prix et ne modifie pas Task, Request, Case ou Membership. |
| `DelegationGrant` | Délégation limitée, révoquable, avec expiration. | grant/revoke ; clé obligatoire ; revision. | `TemporaryDelegationGranted`, `TemporaryDelegationRevoked`; outbox oui. Projections : équipe, ressource concernée. | Ne devient jamais une affectation globale et n’ajoute aucun partage externe implicite. |
| `Task` | Tâche, résultats, blocages, dépendances sortantes ; aucune boucle ; fin seulement avec preuve/dérogation. | `CreateTaskFromRequirement`, `ClaimTask`, `RecordTaskResult`, blocker/dependency add-remove, `CompleteTask`, replace/abandon ; clé obligatoire ; revision. | `TaskCreated`, `TaskResultRecorded`, `TaskBlockerDeclared`, `TaskCompleted`, `TaskReplaced`; outbox obligatoire. Projections : mon travail, wizard, préparation, Action Center si critique. | Ne modifie pas Requirement, Request, Review, Snapshot, Decision ni Price. |
| `Request` | Demande, réponses, relances ; réponse ne clôt jamais une tâche critique. | create/internal/partner request, record response, reminder, clarify/cancel ; clé obligatoire ; revision. | `RequestCreated`, `RequestSent`, `RequestResponseReceived`, `RequestClarificationRequested`; outbox oui. Projections : demandes, tâches liées, partenaires. | Ne crée pas seule une Evidence, une Review, un ExternalShare ou une Decision. |
| `Review` | Cible versionnée + verdict + corrections ; aucune mutation de cible. | open/start/accept/return/reject/cancel ; clé obligatoire ; revision. | `ReviewOpened`, `ReviewAccepted`, `ReviewReturnedWithCorrections`, `ReviewRejected`; outbox oui. Projections : revues, tâche, préparation, documents. | Ne modifie jamais directement Task, Evidence, Draft ou Requirement ; déclenche des commandes aval. |
| `PreparationPackage` | Contenu vivant, readiness et dérogations ; aucun prix ni décision stratégique. | `EvaluatePreparationReadiness`, `RequestReadinessWaiver`, `DeclarePreparationReady`, open new cycle ; clé obligatoire ; revision. | `PreparationReadinessEvaluated`, `PreparationDeclaredReady`, `PreparationMarkedForRework`; outbox obligatoire. Projections : contrôle préparation, wizard, affaire, transmission. | Ne crée ni Snapshot ni Transmission directement ; ne possède ni Task ni Evidence. |
| `ResponseDraft` | Brouillon et versions, engagements candidats/reemploi ; aucun engagement contractuel automatique. | save draft, declare commitment, request commitment review, propose/decide reuse; clé sur création/version/revue ; revision. | `ResponseDraftSaved`, `CandidateCommitmentDeclared`, `CommitmentReviewRequested`, `ReusableItemCompatibilityDecided`; outbox oui. Projections : réponse technique, revues, préparation. | Ne devient pas EvidenceRecord, Decision ou SubmissionPackage. |
| `PreparationSnapshot` | Manifest canonique, hash, auteur et références de versions ; contenu append-only, applicabilité mutable et historisée. | `CreatePreparationSnapshot`, integrity verification, mark stale/supersede ; clé création/invalidation ; aucune mutation de contenu. | `PreparationSnapshotCreated`, `PreparationSnapshotMarkedStale`, `PreparationSnapshotSuperseded`; outbox obligatoire. Projections : transmission, dossier patron, journal. | Ne modifie jamais PreparationPackage, Task, Requirement ou Transmission. |
| `PreparationTransmission` | Lien snapshot-destinataire, réception, retour, retrait avant réception ; un seul envoi actif identique. | create/submit, receive, return, withdraw, accept next phase, invalidate ; clé obligatoire ; revision. | `PreparationSubmittedToPatron`, `PreparationReceivedByPatron`, `PreparationReturnedByPatron`, `PreparationAcceptedForPricing`, `PreparationTransmissionInvalidated`; outbox obligatoire. Projections : Command Center, tâches, affaire, journal. | Ne crée ni Decision ni Price ; ne modifie jamais Snapshot. |
| `ExternalShare` | Destinataire, ressources versionnées, verbes, expiration/révocation. | prepare/grant/revoke/expire/replace; clé obligatoire ; revision. | `ExternalShareGranted`, `ExternalShareRevoked`, `ExternalShareExpired`; outbox oui. Projections : partenaires, demandes, journal. | Ne partage ni prix privé ni version nouvelle sans nouvelle commande ; ne modifie pas Evidence/DCE. |
| `ImpactAssessment` | Version DCE source/cible, ImpactItems, confidence, application de résultat ; impact ne supprime rien. | `EvaluateDceChangeImpact`, confirm impact, apply, `MarkAffectedItemNeedsReview`, `ConfirmPostAmendmentCompatibility`, invalidate snapshot; clé obligatoire ; revision. | `DceImpactAssessmentStarted`, `DceImpactIdentified`, `DceImpactApplied`, `DceImpactRequiresHumanReview`; outbox obligatoire. Projections : impact, tâches, préparation, actions patron, prix/coffre invalidés. | Ne modifie pas directement les aggregates affectés ; ne décide jamais qu’un impact financier est acceptable. |

## 10. Chaîne analytique

| Aggregate | Transaction atomique et invariants | Commandes critiques, révision et idempotence | Événements, outbox et projections | Dépendances interdites |
|---|---|---|---|---|
| `SourceAssertion` | Assertion, provenance, confidence et confirmation/supersession. Une assertion sans source est `A_VERIFIER`, jamais confirmée. | record/confirm/supersede sourced fact ; clé à création/confirmation ; revision. | `SourceAssertionRecorded`, `SourceAssertionConfirmed`, `SourceAssertionSuperseded`; outbox oui. Projections : analyse, provenance, exigence. | Ne transforme pas un extrait source en Requirement sans commande dédiée ; ne décide pas. |
| `Requirement` | Interprétation, portée, sources et état ; une exigence confirmée référence DCE/version/localisation. | `ConfirmRequirement`, `MarkRequirementUnverified`, `DeclareRequirementConflict`; clé obligatoire ; revision. | `RequirementConfirmed`, `RequirementMarkedUnverified`, `RequirementConflictDeclared`; outbox obligatoire. Projections : exigences, tâches, préparation, dossier patron. | Ne possède ni Coverage, Evidence, Task, Price ni Decision. |
| `Coverage` | Lien Requirement ↔ EvidenceVersion(s), portée et état. Une preuve expirée/non autorisée ne peut devenir couverture complète sans validation humaine. | create/update/confirm coverage; clé obligatoire ; revision. | `EvidenceCoverageRecorded`, `EvidenceCoverageChanged`; outbox oui. Projections : conformité, préparation, décision. | Ne modifie jamais EvidenceRecord ou Requirement ; ne produit pas d’Assessment final. |
| `Assessment` | Résultat sur contexte Requirement × Capability × Coverage, règle/moteur et confidence ; une nouvelle source crée une nouvelle évaluation ou la rend stale. | evaluate/confirm/revoke assessment; clé pour évaluation asynchrone ; revision. | `RequirementAssessmentCompleted`, `RequirementAssessmentMarkedStale`; outbox oui. Projections : analyse, préparation, risques, dossier patron. | Ne possède ni Finding, Risk, Task, Decision ni prix. |
| `Finding` | Constat, objets affectés, sévérité, confidence et disposition ; toute contradiction reste sourcée. | record/confirm/resolve/supersede finding; clé obligatoire ; revision. | `FindingRecorded`, `FindingConfirmed`, `FindingResolved`; outbox oui. Projections : analyse, risques, actions, préparation. | Ne ferme pas directement Task/Action et ne prend aucune décision. |
| `Risk` | Risque et facteurs ; l’acceptation humaine reste une Decision distincte. | open/update/reassess/close risk; clé création/fermeture ; revision. | `RiskOpened`, `RiskReassessed`, `RiskClosed`; outbox oui. Projections : registre risques, Action Center, dossier décision. | Ne stocke pas une décision patron ni une tâche comme enfant mutable. |
| `ProtectionPlan` | Plan, mesures et jalons abstraits ; tâches/actions reliées par références. | create/update/close protection plan; clé création/fermeture ; revision. | `ProtectionPlanCreated`, `ProtectionPlanUpdated`, `ProtectionPlanClosed`; outbox oui. Projections : risques, actions, préparation. | Ne modifie jamais Task ou PatronAction directement ; ne masque pas le risque. |

---

# Partie III — Politique d’événements, outbox et dépendances

## 11. Contrat commun des événements

Chaque aggregate qui reçoit une écriture durable produit au moins un événement interne. Tout événement consommé hors de son context est transformé en événement publié minimal, versionné et stable.

| Élément d’enveloppe | Règle |
|---|---|
| `event_id` | UUID immuable, unique et dédupliqué par les projecteurs. |
| `tenant_id` | Résolu depuis l’identité authentifiée et l’instance autorisée ; jamais choisi par le navigateur. |
| `aggregate_type`, `aggregate_id`, `aggregate_revision` | Identifient exactement la mutation propriétaire. |
| `event_type`, `event_contract_version` | Nommage au passé et contrat public versionné si l’événement franchit une frontière. |
| `occurred_at`, `recorded_at` | Séparent moment métier et persistance durable. |
| `actor`, `correlation_id`, `causation_id` | Permettent de reconstruire le parcours sans dépendre d’une projection. |
| `payload` | Minimal, sans secret, document binaire, prix privé ou données de confidentialité supérieure au consommateur. |

### 11.1. Règle d’outbox

**Outbox requise : oui** pour toutes les lignes de la section 8 à 10 qui produisent un événement alimentant une projection, un worker, une notification ou une autre frontière. Dans la même transaction PostgreSQL doivent être conservés : mutation root, `DomainEvent`, ligne(s) outbox et résultat terminal du registre d’idempotence.

Les projecteurs utilisent une contrainte unique `(projector_name, event_id)`. Une livraison multiple ne crée donc ni deuxième action patron, ni deuxième transmission, ni deuxième ligne du Journal.

### 11.2. Process managers autorisés

| Événement publié | Processus autorisé | Commande aval idempotente |
|---|---|---|
| `DceVersionRegistered` | Lancer ou réclamer une analyse d’impact. | `EvaluateDceChangeImpact`. |
| `DceImpactApplied` | Demander les travaux de correction nécessaires. | `MarkAffectedItemNeedsReview`, `OpenPatronAction`, `MarkPricingForReview`, `InvalidatePreparationSnapshot`. |
| `ConditionalGoDecisionApproved` | Créer le suivi de conditions sans modifier la décision. | `OpenPatronAction`, `CreateTaskFromRequirement` ou commande de tâche dédiée. |
| `PreparationSnapshotCreated` | Créer une transmission seulement si elle n’existe pas déjà pour ce snapshot/destinataire. | `CreatePreparationTransmission`. |
| `PreparationSubmittedToPatron` | Ouvrir/regrouper l’action de revue patron. | `OpenPatronAction`. |
| `ReviewReturnedWithCorrections` | Créer/réouvrir le travail ciblé. | `CreateCorrectionTask` ou `ReopenTaskForCorrections`. |
| `EvidenceArchived` ou `EvidenceVersionReplaced` | Évaluer les utilisations dépendantes. | `ReassessCoverage`, `ReassessAssessment`, `OpenPatronAction` si critique. |
| `CollaboratorSuspended` | Traiter les responsabilités devenues orphelines. | `OpenPatronAction`, `ReassignCaseResponsibility` si le patron le décide. |

---

## 12. Projections obligatoires et cohérence de lecture

| Projection / vue | Sources principales | Consistance | Interdits |
|---|---|---|---|
| **Portefeuille et vue Affaire patron** | Case, Decision, Pricing, Submission, Impact, PatronAction. | Eventual pour agrégats ; RYOW du résultat de la commande. | Ne calcule ni risque, ni prix, ni impact. |
| **Command Center / File d’actions** | PatronAction, Decision, Risk, Transmission, Impact. | Eventual avec fraîcheur visible. | Ne crée ou clôture jamais une action. |
| **Prix privé** | PricingScenario, OfficialPricingVersion, sources autorisées. | Strong/RyOW pour le patron après commande ; aucun accès collaborateur. | Ne reçoit pas des projections collaborateur en clair financier. |
| **Coffre de dépôt** | SubmissionPackage, DceVersion, OfficialPricingVersion, Decision. | RYOW après contrôle/autorisation/dépôt ; contenu strict à la commande. | Ne déduit pas « dépôt prouvé » sans reçu archivé. |
| **Mes affaires / Mon travail aujourd’hui** | Assignment, Task, Request, Review, Preparation, Impact. | Eventual autorisée ; RYOW après mutation de tâche/demande. | Ne retourne aucune donnée financière/stratégique. |
| **Wizard de préparation** | DceVersion, Requirement, Coverage, Assessment, Task, Request, Review, PreparationPackage. | Forte avant readiness/snapshot/transmission ; sinon fraîcheur explicitée. | Ne détient aucun workflow métier dans React. |
| **Dossier de décision** | DecisionContext, Case, Risk, Finding, Pricing, Snapshot, DCE. | Strong au moment d’une décision ; hash de contexte contrôlé. | Ne prend jamais une décision automatique. |
| **Journal de vérité** | Événements publiés sélectionnés. | Eventual, reconstruisible ; provenance affichée. | Ne devient ni event store universel ni source de mutation. |
| **Timeline collaborateur** | Événements de Task/Request/Review/Transmission dans le périmètre autorisé. | Eventual, filtrée par affectation active. | Ne révèle pas les décisions/prix non autorisés. |

---

## 13. Dépendances interdites globales

| Source | Dépendances strictement interdites |
|---|---|
| `AFF / Case` | Importer ou persister l’intérieur de `PRX`, `DEP`, `PRF`, `TSK`, `DEC`, `SNP` comme enfants mutables. |
| `DCE` | Décider, chiffrer, déposer ou modifier des exigences interprétées. |
| `ANA` | Déclencher une décision humaine, modifier un prix ou masquer une incertitude. |
| `ACT` | Produire un choix de décision, valider un prix, terminer une tâche à la place de son propriétaire. |
| `DEC` | Calculer un montant, altérer un DCE, créer directement des tasks/actions. |
| `PRF` | Déclarer que la preuve couvre une exigence sans `Coverage` et validation adaptée. |
| `PRX` | Exposer montants/marges hors classe financière, modifier dépôt ou décision. |
| `DEP` | Déclarer un dépôt réussi sans accusé, modifier le prix ou la décision attachée. |
| `ASN` | Conférer des droits financiers implicites, modifier des tâches ou l’état Case. |
| `TSK` | Changer une preuve, demande, revue ou exigence par effet de bord. |
| `DMD` | Faire d’une réponse une preuve valide ou une tâche terminée automatiquement. |
| `REV` | Modifier silencieusement l’objet revu. |
| `PRE/SNP/TRN` | Produire un prix, une décision ou un dépôt. |
| `SHR` | Donner accès à une version nouvelle sans commande, ou élargir vers une classe financière. |
| `IMP` | Modifier les objets affectés au lieu d’émettre leur nécessité de revue. |
| **Tout frontend/projection** | Écrire en base métier, appliquer une transition ou contourner le contrôle serveur de tenant/autorisation. |

---

# Partie IV — Tests de gel DOMAIN-01

## 14. Critères indispensables avant génération des modèles

| ID | Cas de recette structurel | Résultat impératif |
|---|---|---|
| `DOM01-01` | Un handler `Case` tente de créer une Task ou de modifier un PricingVersion. | Échec de test d’architecture ; relation inter-aggregate uniquement par commande/événement. |
| `DOM01-02` | Un rectificatif DCE V3 est reçu après Go V2, prix V1 et snapshot transmis. | DceVersion V3 créée ; anciens objets inchangés ; ImpactAssessment identifie précisément les objets à revoir. |
| `DOM01-03` | Une preuve existe mais n’est ni autorisée ni reliée à l’exigence. | Aucun état « exigence couverte » ; Coverage explicite requis. |
| `DOM01-04` | Une assessment conclut à un manque. | Finding/Risk éventuels créés par commandes/événements distincts ; Assessment ne contient pas une action patron enfant. |
| `DOM01-05` | Le patron valide un Go sous conditions. | Decision + contexte + conditions atomiques ; actions/tâches de suivi créées de manière idempotente après événement. |
| `DOM01-06` | Deux collaborateurs terminent la même tâche. | Premier succès durable ; second replay idempotent seulement si même intention, sinon `VERSION_CONFLICT`. |
| `DOM01-07` | Double clic sur transmettre au patron. | Un Snapshot, une Transmission et une Action patron de revue au maximum par identité fonctionnelle. |
| `DOM01-08` | Une nouvelle version de preuve remplace une attestation utilisée. | Ancienne version conservée ; Coverage/Assessment concernés évalués à nouveau ; aucune décision historique réécrite. |
| `DOM01-09` | Le patron valide un prix lu avant un nouveau DCE. | `STALE_CONTEXT` ; aucune validation ni événement de prix. |
| `DOM01-10` | Un partage externe est actif puis une nouvelle version du document apparaît. | Le destinataire garde seulement l’ancienne version autorisée ; une nouvelle commande de partage est nécessaire. |
| `DOM01-11` | Un collaborateur tente un appel direct sur une projection de prix ou un endpoint `PRX`. | `FORBIDDEN`/`NOT_FOUND` neutre ; aucune fuite de montant, de devis ou d’existence de ressource. |
| `DOM01-12` | Un événement outbox est livré deux fois. | Une seule entrée pour chaque projecteur et aucun doublon d’action, de transmission ou de journal. |

## 15. Décisions finales de passage au code

1. `Case`, `Decision`, `OfficialPricingVersion`, `SubmissionPackage`, `Assignment`, `Task`, `Request`, `Review`, `PreparationSnapshot`, `PreparationTransmission`, `ExternalShare` et `ImpactAssessment` sont des aggregates racines obligatoires du premier noyau V8.
2. `Consultation`, `DceVersion`, `EvidenceRecord`, `Opportunity`, `OpportunityProfile`, `PatronAction`, `PreparationPackage` et les aggregates `ORG` sont également des roots distincts ; aucun ne doit être inclus par relation ORM dans `Case`.
3. `SourceAssertion`, `Requirement`, `Coverage`, `Assessment`, `Finding`, `Risk` et `ProtectionPlan` sont des aggregates analytiques explicites. Leur mise en œuvre peut être progressive, mais leur propriété et leurs relations ne doivent pas être contournées.
4. Toute association entre deux aggregates est une référence par identifiant et tenant, protégée par validation applicative, clés étrangères adaptées et contrôles d’accès. Elle n’est jamais une cascade ORM de suppression ou d’écriture.
5. Les futures classes Pydantic, SQLAlchemy et repositories doivent être générées **par aggregate**, jamais par écran ni par module frontend.
6. Les commandes collaborateur doivent maintenant être spécifiées au même niveau que la spécification patron : enveloppe, autorisation contextualisée, `expected_revision`, idempotence, erreurs et événements publiés.

---

## 16. Clarifications V1.1 issues de la revue DOMAIN-01

Les clarifications suivantes complètent la matrice et priment sur toute formulation antérieure ambiguë.

| Sujet | Décision V1.1 |
|---|---|
| **Métier vs exécution** | DOMAIN-01 conserve les semantics métier : ownership, invariants, relations et mutations atomiques. Les mécanismes PostgreSQL, workers, projecteurs, files, tentative de retry et transport de l’outbox sont documentés dans `ENGINE-*`/`INFRA-*`; ils ne créent pas de règles métier supplémentaires. |
| **Assertion vs fait vs événement** | `SourceAssertion` est ce qu’une source permet d’affirmer, y compris si elle reste candidate. `BusinessFact` est une assertion confirmée/sourcée. `DomainEvent` est un changement métier accepté. Aucun de ces trois termes n’est synonyme. |
| **Assessment de capacité** | La question « cette capacité est-elle mobilisable pour cette affaire, ce lot et cette période ? » appartient à `Assessment` dans `ANA`. `CompanyCapability` ne possède que la vérité générale de l’entreprise. |
| **Preuve d’une référence** | `CompanyReference` référence ses `EvidenceRecord` justificatifs ; il ne les possède jamais. |
| **DCE et traitements techniques** | `DceVersion` possède l’intégrité des originaux, documents et ancres `SourceStatement`. Les `SourceAssertion` sont des realities analytiques `ANA` qui les référencent. Les extractions, chunks, erreurs de parsing, jobs et index sont hors du domaine et ne doivent pas gonfler cet aggregate. |
| **Preuve d’un constat** | `FindingEvidenceLink` est une entité interne de `Finding` qui relie explicitement un constat à une EvidenceVersion ou SourceAssertion, avec rôle et confidence. |
| **Partage externe** | `ExternalShare` reste le nom métier du root d’accès. Il possède une réalité explicite de grant (`ShareGrant`) : destinataire, versions, verbes, portée et expiration. Un événement d’accès est une conséquence, non le grant. |
| **Dépôt** | `SubmissionPackage` représente ce que SMART_AO prépare et autorise. Une future extension `SubmissionAttempt` représentera chaque tentative externe ; `SubmissionReceipt` représentera la preuve externe. Ces réalités ne modifient jamais le package historique. |
| **Événements** | Seule une mutation métier durable et observable doit émettre un Domain Event. Un Integration Event est une publication dérivée et minimale ; l’aggregate ne publie jamais directement un contrat externe sans l’étape de dérivation. |
| **Process Manager** | Un Process Manager orchestre des commandes, corrélations, reprises et compensations ; il ne possède aucun aggregate. Seul un Process Manager déclaré peut séquencer des handlers distincts. |
| **Core aggregates** | Les roots listés par DOMAIN-01 sont des aggregates de domaine valides. Les implémenter tous immédiatement est interdit : le premier slice reste limité à `Case`, `Consultation/DceVersion`, `Decision` et leurs tests fondamentaux. |
| **Relations ORM** | Toute relation inter-aggregate est une référence `tenant_id + aggregate_id`. Les cascades ORM et `ON DELETE CASCADE` entre aggregates sont interdites. |

## Références internes

- `SMART_AO_V8_CONTRAT_DE_DOMAINE.md` — version 1.2.
- `SMART_AO_V8_MATRICE_TRANSITIONS_METIER.md` — matrice patron V8.2.
- `SMART_AO_V8_MATRICE_VUE_ACTION_COLLABORATEUR.md` — matrice collaborateur V8.1.
- `SMART_AO_V8_SPEC_COMMANDES_IDEMPOTENCE.md` — contrat des commandes patron, concurrence et outbox.
- `pasted_content_33.txt` — revue de domaine, sections 51 à 57.
- `SMART_AO_V8_AGGREGATES_EVENTS_PRAGMATIC_REVIEW.md` — contraintes de mise en œuvre du monolithe modulaire et du premier slice.

---

**Fin de DOMAIN-01 — Aggregate / Ownership / Consistency Matrix — version 1.1**
