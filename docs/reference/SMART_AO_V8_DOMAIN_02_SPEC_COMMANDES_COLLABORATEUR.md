# SMART_AO V8 — DOMAIN-02
## Spécification normalisée des commandes collaborateur

**Version :** 1.0  
**Statut :** contrat applicatif et domaine à valider avant les endpoints d’écriture collaborateur  
**Auteur :** Manus AI  
**Périmètre :** commandes de préparation DCE, affectation, tâches, demandes, revues, réponse technique, préparation, instantané, transmission, partage externe et impact DCE  
**Hors périmètre :** prix, marge, trésorerie, Go/No-Go, décision de risque, autorisation de dépôt et dépôt effectif

---

## 1. Objet et position dans la documentation V8

DOMAIN-01 a fixé les aggregates, leurs ownerships et les frontières de cohérence. Le présent document normalise désormais les **intentions d’écriture collaborateur** : ce que l’interface peut demander, les droits nécessaires, le root qui reçoit la mutation, les préconditions, l’idempotence, la concurrence, les événements et les erreurs visibles.

> **Règle de positionnement :** DOMAIN-02 ne redéfinit ni les ownerships ni les invariants de DOMAIN-01. Il traduit ces décisions en contrats de commandes. Les détails de transport, stockage des messages, workers, file d’attente, schémas SQL et mécanismes de livraison seront isolés dans des documents `ENGINE-*` et `INFRA-*` ultérieurs.

| Document | Responsabilité | Ne doit pas devenir |
|---|---|---|
| `DOMAIN-01` | Aggregates, entities, objets-valeur, ownership, invariants et relations interdites. | Un manuel PostgreSQL ou un catalogue d’API. |
| **`DOMAIN-02`** | Commandes collaborateur, autorisation, préconditions, transitions, erreurs et garanties utilisateur. | Un ensemble de boutons React ou de handlers qui s’appellent entre eux. |
| `ENGINE-01` ultérieur | Domain events, integration events, outbox, process managers, reprise et livraison. | Le propriétaire de l’état métier. |
| `READ-01` ultérieur | Projections, fraîcheur et read-your-own-write. | Une source de vérité transactionnelle. |
| `INFRA-01` ultérieur | PostgreSQL, ORM, stockage, jobs, monitoring et déploiement. | Une règle métier cachée. |

---

## 2. Définitions normatives

| Terme | Définition obligatoire |
|---|---|
| **Aggregate** | Propriétaire d’une mutation atomique et de ses invariants locaux. |
| **Repository** | Porte de persistance d’un seul aggregate racine à la fois. Un repository ne sauvegarde jamais un autre root. |
| **Commande** | Intention immuable d’un acteur ou d’un processus ; elle porte une clé d’idempotence et un contexte d’autorisation contrôlé. |
| **Domain Event** | Changement métier durable et observable produit par une commande acceptée. Une mutation purement technique ne justifie pas à elle seule un événement métier. |
| **Integration Event** | Publication minimale et versionnée dérivée d’un Domain Event lorsque la conséquence traverse un bounded context, une projection ou un effet asynchrone. |
| **Process Manager** | Orchestrateur nommé qui séquence plusieurs commandes entre aggregates avec corrélation, reprise et compensation. Il ne possède aucune vérité métier des aggregates qu’il orchestre. |
| **Projection** | Situation de lecture reconstruisible ; elle ne crée ni ne modifie un aggregate. |
| **FunctionalIdentity** | Clé métier stable utilisée pour empêcher un doublon fonctionnel dans un tenant. Elle est distincte de l’UUID technique et de la clé d’idempotence. |
| **ExpectedRevision** | Révision optimiste attendue d’un aggregate cible. Elle n’est jamais une version métier de document ou de DCE. |

### 2.1. Lexique des faits et événements

| Terme | Sens précis | Exemple |
|---|---|---|
| **SourceAssertion** | Ce qu’une version de document permet d’affirmer, avec localisation et confidence ; peut rester candidate ou à vérifier. | « Le RC mentionne une visite ». |
| **BusinessFact** | Assertion métier confirmée et sourcée, distincte d’une commande ou d’un changement système. | « Visite obligatoire pour le lot 03 ». |
| **Domain Event** | Changement métier accepté. | `RequirementConfirmed`, `TaskCompleted`. |
| **Integration Event** | Version publiable, minimale et déduite du Domain Event. | `task.completed.v1` pour les projections autorisées. |

Un moteur IA, une extraction ou un collaborateur peut produire une **CandidateAssertion**. Il ne peut jamais créer directement un BusinessFact confirmé, une exigence validée, une décision patron ou un montant financier.

---

## 3. Contrat commun de toute commande collaborateur

### 3.1. Enveloppe logique

L’interface ne fournit jamais de valeur de confiance pour le tenant, l’identité, le rôle ou les permissions. Ces données sont résolues par le serveur avant la validation du payload.

| Champ | Origine | Règle |
|---|---|---|
| `command_id` | Client ou serveur | Identifiant UUID d’une intention précise. |
| `command_type` | Client, catalogue fermé | Doit appartenir au catalogue de la section 8. |
| `idempotency_key` | Client | Obligatoire pour toute commande qui crée, modifie, rattache, envoie, invalide ou termine une réalité durable. |
| `correlation_id` | Client ou serveur | Lie un parcours métier, par exemple rectificatif → impacts → corrections. |
| `caused_by_event_id` | Serveur / Process Manager | Obligatoire pour une commande aval déclenchée par événement ; absent pour l’intention initiale d’un collaborateur. |
| `expected_revision` | Client | Révision du root cible lu par l’utilisateur ; obligatoire pour toute mutation d’un root existant. |
| `payload` | Client | Données strictement validées par le schéma de la commande. |
| `tenant_context` | Serveur | Résolu depuis la session authentifiée et l’instance autorisée ; jamais fourni librement par le navigateur. |
| `actor_context` | Serveur | Acteur, membership, affectations actives et droits délégués, réévalués au moment du traitement. |
| `received_at` | Serveur | Date/heure de réception fiable. |

La clé de rejet ou de replay est :

```text
(tenant_id, actor_id, command_type, idempotency_key)
```

L’empreinte canonique doit couvrir au minimum `command_type`, `payload`, `expected_revision`, `correlation_id` et, lorsqu’il existe, `caused_by_event_id`. Une même clé avec une empreinte différente produit `IDEMPOTENCY_KEY_REUSED` ; elle ne déclenche aucune mutation.

### 3.2. Autorisation contextualisée

La visibilité d’un bouton ne donne aucun droit. Avant de charger les données détaillées et avant tout traitement, le serveur évalue le contexte complet :

```text
Autorisé ?
= acteur authentifié
  × tenant résolu
  × membership actif
  × affectation active
  × affaire et périmètre autorisés
  × classe de ressource
  × verbe demandé
  × état du root cible
  × préconditions métier
```

| Classe | Ressources collaborateur autorisables | Interdit absolu |
|---|---|---|
| `DocumentClass` | Pièces DCE, annexes, plans, brouillons techniques autorisés. | Originaux ou contenu hors périmètre de l’affaire. |
| `EvidenceClass` | Références, qualifications, attestations et preuves explicitement autorisées. | Preuve expirée présentée comme actuelle ; preuve non autorisée. |
| `OperationalClass` | Exigences, tâches, demandes, revues, préparation, impact. | Contourner une affectation ou modifier une décision patron. |
| `PartnerClass` | Demandes partenaire, réponses et partages explicitement autorisés. | Partage global, version non listée ou accès sans expiration. |
| `FinancialClass` | Aucune ressource dans le périmètre collaborateur standard. | Coûts, prix, marge, devis privé, trésorerie. |
| `StrategicClass` | Retours patron explicitement partagés, demandes de décision. | Go/No-Go, acceptation de risque, stratégie commerciale, autorisation de dépôt. |

Les verbes `DISCOVER`, `READ_METADATA`, `READ_CONTENT`, `DOWNLOAD`, `COMMENT`, `EDIT_DRAFT`, `SUBMIT`, `SHARE` et `VALIDATE` sont contrôlés séparément. Le droit `READ_METADATA` ne donne pas `READ_CONTENT` ; le droit de lire une pièce ne donne pas le droit de la partager.

### 3.3. Garanties de traitement et résultat utilisateur

| Situation | Réponse obligatoire |
|---|---|
| Commande acceptée et commit réalisé | `SUCCEEDED`, `aggregate_ref`, révision finale, `event_ids`, état de projection et prochaine action. |
| Même clé, même contenu, résultat final | Rejouer exactement le résultat mémorisé ; aucun deuxième événement. |
| Même clé, traitement non finalisé | `202 IDEMPOTENCY_IN_PROGRESS` avec `correlation_id`, état lisible et délai de reprise. |
| Échec de validation / droit / invariant | `REJECTED`, code explicable, ressource concernée sans fuite inter-tenant, action de correction. |
| Conflit de révision | `409 VERSION_CONFLICT`, révision actuelle et instruction de recharger. |
| Contexte devenu non applicable | `409 STALE_CONTEXT`, changement identifié et cycle à reprendre. |
| Projection non terminée | La mutation reste réussie ; `projection_status = REFRESH_PENDING` et RYOW affiche le résultat root ou un statut de traitement. |

> **Read-your-own-write collaborateur :** après une mutation réussie, l’auteur voit immédiatement le root mis à jour ou un état de processus explicite. Il ne voit jamais un faux succès suivi d’une tâche, demande ou transmission qui semblerait inchangée.

---

## 4. Identités fonctionnelles et déduplication métier

Les contraintes de déduplication sont toujours scellées par le tenant : `UNIQUE(tenant_id, functional_key)`. Elles complètent l’idempotence réseau ; elles ne la remplacent pas.

| Aggregate | FunctionalIdentity minimale | Politique |
|---|---|---|
| `Assignment` | `AssignmentKey = case_id + actor_id + role + scope_fingerprint + active_period`. | Une affectation active identique ne peut être créée deux fois. |
| `Task` | `TaskDedupKey = case_id + purpose + source_object_ref + responsibility_scope`. | Deux tâches actives de même finalité exigent une justification de parallélisation. |
| `Request` | `RequestKey = case_id + recipient + requested_object + source_ref + active_cycle`. | Une relance reste une entité enfant de la demande ; elle ne crée pas une seconde demande. |
| `Review` | `ReviewTargetKey = target_version_ref + review_level + reviewer_scope + active_cycle`. | Une seconde revue active du même objet doit être explicitement distincte. |
| `PreparationSnapshot` | `SnapshotKey = preparation_id + canonical_content_hash`. | Même contenu canonique : même snapshot réutilisé au retry. |
| `PreparationTransmission` | `TransmissionIdentity = snapshot_id + recipient_id`. | Au plus une transmission active identique. |
| `ExternalShare` | `ShareGrantKey = recipient_id + resource_version_refs_hash + verbs + expires_at`. | Nouvelle version de document = nouveau grant explicite. |
| `ImpactAssessment` | `ImpactKey = source_dce_version_id + target_dce_version_id + case_id`. | Une évaluation en cours ou terminée est réutilisée, reprise ou supersédée, jamais dupliquée silencieusement. |

---

## 5. Règles de handlers, repositories et processus

| Règle | Contrat |
|---|---|
| **Un repository, un root** | `TaskRepository` ne sauvegarde que `Task`; il ne persiste jamais `Request`, `Pricing`, `Case` ou `Decision`. |
| **Un handler, une mutation propriétaire** | Un handler modifie son root, ses entités internes, sa révision, son Domain Event et son résultat idempotent. |
| **Pas de handler direct → handler direct** | Un handler métier n’appelle pas un autre handler métier. La seule exception est un Process Manager déclaré, observable et testé. |
| **Pas de cascade inter-aggregate** | Pas de cascade ORM ni de `ON DELETE CASCADE` entre aggregates. Les relations externes sont `tenant_id + aggregate_id`, jamais une arborescence de suppression. |
| **Lecture inter-context autorisée, écriture interdite** | Un handler peut vérifier des références autorisées ; il ne les modifie pas. |
| **Domain Event sélectif** | Une mutation qui change une réalité métier durable et observable émet un Domain Event. Les opérations techniques internes n’émettent pas mécaniquement d’événement métier. |
| **Integration Event dérivé** | Un Integration Event est dérivé d’un Domain Event après commit et ne transporte que le minimum autorisé au consommateur. |

### 5.1. Process Manager déclaré : transmission patron

`SubmitPreparationForPatronReview` est une **intention de workflow**, pas la mutation d’un aggregate unique. Elle est traitée par `PreparationReviewProcess` avec un seul `correlation_id`.

```text
Intention collaborateur : SubmitPreparationForPatronReview
  ↓
1. CreatePreparationSnapshot
  → PreparationSnapshotCreated
2. CreatePreparationTransmission
  → PreparationSubmittedToPatron
3. OpenPatronAction(cause = PREPARATION_TO_REVIEW)
  → PatronActionOpened | PatronActionCauseAdded
```

| Étape obtenue | État que le collaborateur doit voir | Ce que SMART_AO ne doit jamais prétendre |
|---|---|---|
| Snapshot non créé | `NON_TRANSMIS` ; explication et reprise possible. | Que le patron a reçu une préparation. |
| Snapshot créé, transmission en cours | `PREPARATION_FIGEE__TRANSMISSION_EN_COURS_DE_TRAITEMENT`. | Que la transmission est terminée. |
| Transmission créée, action patron en cours de création | `TRANSMISE__REVUE_PATRON_EN_COURS_DE_CREATION`. | Que le patron a déjà pris connaissance. |
| Transmission créée, action patron créée ou regroupée | `TRANSMISE`. | Que la préparation est approuvée ou chiffrée. |
| Échec aval récupérable | Statut lisible et même `correlation_id`; aucun nouveau clic ne crée de second snapshot/transmission. | Un succès complet si l’étape annoncée n’est pas faite. |

Le Process Manager ne possède ni Snapshot, ni Transmission, ni Action patron. Il conserve uniquement l’état d’exécution, la corrélation, les tentatives et la compensation nécessaire à la reprise. Son détail de persistance appartient à `ENGINE-01`.

---

# Partie I — Catalogue fermé des commandes collaborateur

## 6. Affectation, travail et DCE

| Commande | Aggregate propriétaire | Autorisation contextualisée | Préconditions et invariants | Mutation atomique / événement | Révision, idempotence et erreurs principales |
|---|---|---|---|---|---|
| `AcknowledgeAssignment` | `Assignment` | Acteur destinataire ; affectation active ; `OperationalClass:READ_METADATA`. | L’acteur correspond à l’affectation ; reconnaissance non falsifiable. | Ajoute l’entité de reconnaissance ; `AssignmentAcknowledged`. | `expected_revision` requis ; clé requise. Erreurs : `ASSIGNMENT_INACTIVE`, `FORBIDDEN`, `VERSION_CONFLICT`. |
| `RequestAssignmentClarification` | `Request` | Affectation active ; droit `SUBMIT` sur `OperationalClass`. | Question, objet de périmètre et destinataire patron/autorisé présents. N’élargit aucun scope. | Crée une demande liée à `assignment_id`; `AssignmentClarificationRequested`. | Création idempotente ; `RequestKey`. Erreurs : `SCOPE_NOT_DEFINED`, `FORBIDDEN`, `DUPLICATE_FUNCTIONAL_IDENTITY`. |
| `ReportAssignmentUnavailability` | `Assignment` | Acteur affecté ; droit `COMMENT`/`SUBMIT`. | Période ou motif ; impact échéance/tâche si connu. | Ajoute indisponibilité ; `AssignmentUnavailabilityReported`. | `expected_revision`; clé requise. Event aval possible vers Action patron ; pas de tâche modifiée directement. |
| `ConfirmDocumentClassification` | `DceVersion` | Affectation active ; document dans scope ; `DocumentClass:VALIDATE` ou délégation. | Document/version existe ; type de pièce valide ; original inchangé. | Ajoute classification humaine ; `DceDocumentClassificationConfirmed`. | Révision DceVersion ; clé requise. Erreurs : `DOCUMENT_NOT_IN_SCOPE`, `VERSION_CONFLICT`, `INVALID_CLASSIFICATION`. |
| `DeclareMissingDocument` | `DceVersion` | Affectation active ; `DocumentClass:COMMENT`. | Famille attendue et source de l’attente renseignées. « Manquant » ≠ inexistant chez l’acheteur. | Ajoute signalement de manque ; `DceDocumentMissingDeclared`. | Création idempotente avec clé fonctionnelle `case + expected_family + source`. Erreurs : `SOURCE_REQUIRED`, `DCE_VERSION_STALE`. |
| `ReportUnreadableDocument` | `DceVersion` | Affectation active ; document lisible dans le scope minimal. | Version précise, zone/page ou motif de lecture renseigné. | Ajoute incident de lecture ; `DceDocumentReadabilityIssueReported`. | Création idempotente ; erreur `DOCUMENT_NOT_FOUND_OR_FORBIDDEN` neutre inter-tenant. |
| `ConfirmRequirement` | `Requirement` | Affectation active ; Requirement dans CaseScope ; `OperationalClass:VALIDATE` ou délégation. | Au moins une SourceAssertion localisée ; type, portée et statut explicités. | Requirement confirmée ou interprétation versionnée ; `RequirementConfirmed`. | `expected_revision`; clé requise. Erreurs : `PROVENANCE_REQUIRED`, `SOURCE_VERSION_UNAVAILABLE`, `VERSION_CONFLICT`. |
| `MarkRequirementUnverified` | `Requirement` | Affectation active ; `OperationalClass:COMMENT`. | Motif d’incertitude obligatoire. | Marque l’état à vérifier, sans effacer source ; `RequirementMarkedUnverified`. | `expected_revision`; clé. Peut déclencher tâche/revue par événement. |
| `DeclareRequirementConflict` | `Finding` | Affectation active ; `OperationalClass:COMMENT`. | Deux SourceAssertions incompatibles ou une source et une version contradictoire. | Crée Finding de contradiction lié aux sources ; `RequirementConflictDeclared`. | Création idempotente ; erreurs : `TWO_SOURCES_REQUIRED`, `FORBIDDEN`. Ne modifie pas Requirement directement. |
| `CreateTaskFromRequirement` | `Task` | Affectation active ; `OperationalClass:SUBMIT` dans le scope ; futur propriétaire/exécutant autorisé. | Requirement visible ; finalité, responsable/état « à attribuer », échéance ou raison et source de travail définies. | Crée Task + liens internes ; `TaskCreatedFromRequirement`. | Clé obligatoire ; `TaskDedupKey`; erreur `DUPLICATE_FUNCTIONAL_IDENTITY` ou `ASSIGNMENT_INACTIVE`. |

## 7. Tâches et dépendances

| Commande | Aggregate propriétaire | Autorisation contextualisée | Préconditions et invariants | Mutation atomique / événement | Révision, idempotence et erreurs principales |
|---|---|---|---|---|---|
| `ClaimTask` | `Task` | Affectation active ; droit `EDIT_DRAFT`/`SUBMIT`; tâche prenable ou assignée. | Tâche non terminale ; aucun exécutant incompatible ; actor dans scope. | `A_FAIRE → EN_COURS`, exécutant/date ; `TaskClaimed`. | `expected_revision`; clé requise. Erreurs : `TASK_ALREADY_CLAIMED`, `ASSIGNMENT_INACTIVE`, `VERSION_CONFLICT`. |
| `RecordTaskResult` | `Task` | Affectation active ; acteur exécutant ou délégation. | Tâche active ; contenu, SourceAssertion, document versionné ou motif de résultat déclaré. | Ajoute `TaskResult` versionné ; `TaskResultRecorded`. | `expected_revision`; clé obligatoire. RYOW : résultat et sauvegarde visibles immédiatement. |
| `DeclareTaskBlocker` | `Task` | Affectation active ; acteur concerné ; `COMMENT`/`SUBMIT`. | Type, objet bloquant ou manque, source, raison, propriétaire de résolution. | Ajoute Blocker et état `BLOQUEE`/`EN_ATTENTE`; `TaskBlockerDeclared`. | `expected_revision`; clé. N’ouvre pas directement une demande/action ; événement aval possible. |
| `AddTaskDependency` | `Task` | Affectation active ; droit `SUBMIT` sur les deux tâches visibles. | Deux Task distinctes ; justification ; pas de boucle ; type de dépendance. | Ajoute dépendance sortante ; `TaskDependencyAdded`. | `expected_revision` target ; clé obligatoire. Erreurs : `TASK_DEPENDENCY_CYCLE`, `DEPENDENCY_ALREADY_EXISTS`, `FOREIGN_TASK_FORBIDDEN`. |
| `RemoveTaskDependency` | `Task` | Affectation active ; droit sur target ; justification. | Dépendance existe et n’est pas imposée par une politique active ; tâche non terminale irréversible. | Retrait historisé ; `TaskDependencyRemoved`. | Révision + clé. Erreurs : `DEPENDENCY_POLICY_REQUIRED`, `VERSION_CONFLICT`. |
| `RequestReview` | `Review` | Affectation active ; droit `SUBMIT`; relecteur autorisé et cible visible. | Cible versionnée, niveau de revue, relecteur et motif. | Crée Review ouverte ; `ReviewOpened`. | Création idempotente ; `ReviewTargetKey`. Ne modifie pas Task ; événement peut la faire passer à `PRETE_A_RELIRE`. |
| `CompleteTask` | `Task` | Affectation active ; exécutant/propriétaire autorisé ; `VALIDATE` si requis. | Résultat final ; dépendances fortes satisfaites ou dérogation référencée ; revue/approbation requise satisfaite. | `→ TERMINEE`, résultat final figé ; `TaskCompleted`. | `expected_revision`; clé obligatoire. Erreurs : `STRONG_DEPENDENCY_UNSATISFIED`, `REVIEW_REQUIRED`, `EVIDENCE_OF_COMPLETION_REQUIRED`, `VERSION_CONFLICT`. |
| `ReplaceTask` | `Task` | Affectation active ; autorisation de remplacement. | Motif, nouvelle tâche fonctionnellement identifiée et lien de remplacement. | Ancienne Task `REMPLACEE`; référence nouvelle Task créée par commande aval corrélée ; `TaskReplacementRequested`. | Handler ne crée pas la seconde Task. Process Manager/commande `CreateReplacementTask` suit l’événement. Clé obligatoire. |
| `AbandonTaskWithReason` | `Task` | Affectation active ; rôle suffisant ou délégation. | Motif, impact et traitement de conséquence documentés ; pas de blocage critique contourné. | `→ ABANDONNEE_AVEC_MOTIF`; `TaskAbandoned`. | Révision + clé. Erreurs : `PATRON_WAIVER_REQUIRED`, `TASK_ALREADY_TERMINAL`. |

## 8. Demandes, réponses et partage externe

| Commande | Aggregate propriétaire | Autorisation contextualisée | Préconditions et invariants | Mutation atomique / événement | Révision, idempotence et erreurs principales |
|---|---|---|---|---|---|
| `CreateRequest` | `Request` | Affectation active ; `OperationalClass:SUBMIT`; destinataire autorisé. | Affaire, objet demandé, raison, destinataire, priorité/échéance. | Crée Request `PREPAREE` ou `ENVOYEE`; `RequestCreated` ou `RequestSent`. | Clé obligatoire ; `RequestKey`. Erreurs : `RECIPIENT_NOT_ALLOWED`, `REQUEST_SOURCE_REQUIRED`, `DUPLICATE_FUNCTIONAL_IDENTITY`. |
| `CreatePartnerRequest` | `Request` | Affectation active ; droit `SUBMIT` sur `PartnerClass`; partenaire autorisé. | Besoin partenaire, périmètre, échéance, ressource(s) visées et justification. | Crée Request partenaire ; `PartnerRequestCreated`. | Ne crée pas de partage dans le handler. `PartnerRequestCreated` peut déclencher `GrantExternalShare` si le scope est déjà autorisé. |
| `RecordRequestResponse` | `Request` | Destinataire de la demande ou acteur explicitement autorisé ; réponse dans scope. | Request active ; réponse versionnée ou ressource autorisée ; date observée. | Ajoute réponse ; `RequestResponseReceived`. | `expected_revision`; clé. La réponse ne termine ni Task ni EvidenceRecord. |
| `CreateReviewFromResponse` | `Review` | Affectation active ; réponse visible ; relecteur autorisé. | Réponse précise, cible de contrôle, niveau et relecteur. | Crée Review ; `RequestResponseReviewRequested`. | Création idempotente. N’accepte pas la réponse comme preuve. |
| `SendRequestReminder` | `Request` | Auteur/destinataire autorisé ; Request active. | Échéance atteinte ou délai de relance respecté. | Ajoute relance interne ; `RequestReminderSent`. | `expected_revision`; clé. Erreurs : `REQUEST_TERMINAL`, `REMINDER_TOO_EARLY`. |
| `WithdrawRequest` | `Request` | Demandeur ou délégation ; Request non terminale. | Motif obligatoire ; impact sur tâche lié visible. | `→ ANNULEE`; `RequestWithdrawn`. | Révision + clé. Ne supprime aucune réponse historique. |
| `GrantExternalShare` | `ExternalShare` | Affectation active ; droit `SHARE`; ressources et versions présentes dans le scope partageable. | Destinataire, versions exactes, verbes, expiration et confidentialité validés ; FinancialClass/StrategicClass interdits. | Crée ShareGrant ; `ExternalShareGranted`. | Création idempotente ; `ShareGrantKey`. Erreurs : `RESOURCE_NOT_SHAREABLE`, `SHARE_SCOPE_DENIED`, `EXPIRY_REQUIRED`. |
| `RevokeExternalShare` | `ExternalShare` | Droit `SHARE`/révocation ; grant actif visible. | Motif si exigé par politique. | `→ REVOQUE`; `ExternalShareRevoked`. | `expected_revision`; clé. L’accès futur est coupé, historique conservé. |

## 9. Revue, capacité et réponse technique

| Commande | Aggregate propriétaire | Autorisation contextualisée | Préconditions et invariants | Mutation atomique / événement | Révision, idempotence et erreurs principales |
|---|---|---|---|---|---|
| `AcceptReview` | `Review` | Relecteur désigné ; affectation/délégation active ; droit `VALIDATE`. | Review ouverte ; cible exactement identique à la version revue ; verdict explicite. | `→ ACCEPTEE`; `ReviewAccepted`. | `expected_revision`; clé. Ne modifie pas l’objet revu directement. |
| `ReturnReviewWithCorrections` | `Review` | Relecteur désigné ; droit `VALIDATE`. | Corrections précises, motif et objet versionné. | `→ RETOURNEE`; `ReviewReturnedWithCorrections`. | Révision + clé. Process Manager crée/réouvre Task de correction ; réponse RYOW indique que la correction est en cours de création si nécessaire. |
| `RejectReview` | `Review` | Relecteur désigné ; droit `VALIDATE`. | Motif requis ; cible versionnée inchangée. | `→ REJETEE`; `ReviewRejected`. | Révision + clé. L’objet historique reste intact. |
| `ProposeCapabilityForCase` | `Assessment` | Affectation active ; Capability et CaseScope visibles ; droit `COMMENT`/`SUBMIT`. | Capacité, période, scope, source/preuve et justification identifiés. | Crée une Assessment candidate `Requirement? × Capability × Coverage?`, sans confirmer la capacité d’entreprise. | Création idempotente. Cette commande ne modifie pas `CompanyCapability`; elle respecte la séparation ORG/ANA. |
| `ReportCapabilityGap` | `Finding` | Affectation active ; besoin source ou task/requirement indiqué. | Écart, objet concerné, provenance et niveau de confidence. | Crée Finding ; `CapabilityGapReported`. | Création idempotente. Événement peut ouvrir Risk/Task/PatronAction via commandes aval. |
| `SaveResponseDraft` | `ResponseDraft` | Affectation active ; droit `EDIT_DRAFT` sur la section. | Section, contenu, sources référencées et base versionnelle connus. | Ajoute nouvelle version de brouillon ; `ResponseDraftSaved`. | `expected_revision` du draft ; clé obligatoire. RYOW montre version sauvegardée. |
| `DeclareCandidateCommitment` | `ResponseDraft` | Affectation active ; droit `EDIT_DRAFT`. | Phrase/section, type d’engagement, responsable/capacité/hypothèse et sources. | Ajoute CandidateCommitment au draft ; `CandidateCommitmentDeclared`. | Révision + clé. N’est ni une promesse validée ni une décision patron. |
| `RequestCommitmentReview` | `Review` | Affectation active ; CandidateCommitment visible ; relecteur autorisé. | Engagement complet, cible versionnée, niveau de revue. | Crée Review ciblée ; `CommitmentReviewRequested`. | Création idempotente. |
| `ProposeReusableItem` | `ResponseDraft` | Affectation active ; élément source visible ; droit `EDIT_DRAFT`. | Version/origine de l’élément et contexte du DCE actuel. | Ajoute proposition de réemploi ; `ReusableItemProposed`. | Révision + clé. Aucune copie automatique. |
| `DecideReusableItemCompatibility` | `ResponseDraft` | Relecteur/acteur avec droit `VALIDATE`; compatibilité dans scope. | Contrôle de la version DCE active, sources et motif. | Proposition `ACCEPTEE`, `REJETEE` ou `A_REVOIR`; `ReusableItemCompatibilityDecided`. | Révision + clé. Ne valide pas une décision patron ni le dépôt. |

## 10. Préparation, instantané, transmission et impact DCE

| Commande | Aggregate propriétaire ou processus | Autorisation contextualisée | Préconditions et invariants | Mutation atomique / événement | Révision, idempotence et erreurs principales |
|---|---|---|---|---|---|
| `EvaluatePreparationReadiness` | `PreparationPackage` | Affectation active ; droit `READ_CONTENT`/`SUBMIT` ; affaire dans scope. | DCE applicable et règles disponibles ; références autorisées seulement. | Enregistre résultat `READY`, `READY_WITH_WARNINGS` ou `BLOCKED`, listes `blockers/warnings/informational`; `PreparationReadinessEvaluated`. | `expected_revision`; clé. Calcul explicable ; aucun prix chargé dans le payload collaborateur. |
| `RequestReadinessWaiver` | `Request` | Affectation active ; droit `SUBMIT`; blocage précis visible. | Blocage, impact, destinataire patron et motif présents. | Crée demande de dérogation ; `ReadinessWaiverRequested`. | Création idempotente. Ne modifie ni readiness ni Task. |
| `DeclarePreparationReady` | `PreparationPackage` | Affectation active ; autorisation de préparation. | Dernier readiness `READY` ou `READY_WITH_WARNINGS`, ou dérogation patron applicable ; aucune donnée FinancialClass dans le paquet. | `EN_PREPARATION/A_REVOIR → PRET_POUR_REVUE`; `PreparationDeclaredReady`. | `expected_revision`; clé. Erreurs : `PREPARATION_BLOCKED`, `READINESS_STALE`, `PRIVATE_DATA_DETECTED`. |
| `PreviewPreparationSnapshot` | Lecture sans mutation | Affectation active ; préparation prête ; contrôle récent. | N/A : prévisualisation non durable. | Aucun Domain Event requis. | Pas de clé obligatoire ; erreur `READINESS_STALE` si le calcul doit être relancé. |
| `SubmitPreparationForPatronReview` | `PreparationReviewProcess` | Affectation active ; droit `SUBMIT` transmission ; PreparationPackage prête. | Readiness actuel ; aucun blocage non dérogé ; aucune donnée financière ; destinataire patron autorisé. | Lance le processus de section 5.1 ; résultat visible de workflow. | Clé obligatoire, `correlation_id` obligatoire ou généré. Réponses : `IDEMPOTENCY_IN_PROGRESS`, `PREPARATION_BLOCKED`, `TRANSMISSION_ALREADY_ACTIVE`. |
| `CreatePreparationSnapshot` | `PreparationSnapshot` | Commande aval interne autorisée seulement au Process Manager. | PreparationPackage prête, readiness hash/revision valide. | Crée manifest canonique immuable ; `PreparationSnapshotCreated`. | `SnapshotKey`; idempotente par corrélation. Aucun collaborateur ne peut modifier le contenu après création. |
| `CreatePreparationTransmission` | `PreparationTransmission` | Commande aval interne du Process Manager. | Snapshot existant, destinataire patron autorisé, `TransmissionIdentity` libre. | Crée transmission `TRANSMISE`; `PreparationSubmittedToPatron`. | Idempotente par `snapshot_id + recipient_id`; peut retourner transmission existante. |
| `WithdrawUnreceivedTransmission` | `PreparationTransmission` | Auteur ou délégation ; transmission non reçue. | État `TRANSMISE`, aucune réception patron. | `→ RETIREE_AVANT_RECEPTION`; `PreparationWithdrawnBeforeReceipt`. | `expected_revision`; clé. Snapshot reste archivé. |
| `AcknowledgePatronReturn` | `PreparationTransmission` | Affectation active ; retour ciblé accessible. | Transmission `RETOURNEE`; corrections listées. | Enregistre prise en compte ; `PatronReturnAcknowledged`. | Révision + clé. Les Task de correction sont créées par Process Manager, pas par ce handler. |
| `OpenNewPreparationCycle` | `PreparationPackage` | Affectation active ; retour patron, rectificatif ou nouveau périmètre justifié. | Ancien snapshot/transmission conservés ; cause de nouveau cycle. | Ouvre cycle vivant ; `PreparationNewCycleOpened`. | Révision + clé. Ne modifie pas snapshot ou transmission historiques. |
| `EvaluateDceChangeImpact` | `ImpactAssessment` | Affectation active ; source/cible DCE visibles ; droit `SUBMIT`. | Version cible active ; source antérieure ou motif d’absence ; contexte Case. | Crée/reprend l’assessment d’impact ; `DceImpactAssessmentStarted` puis résultats. | `ImpactKey`; clé obligatoire. Affiche `EVALUATION_EN_COURS` si worker/traitement différé. |
| `MarkAffectedItemNeedsReview` | Aggregate de l’objet affecté | Commande aval seulement, déclenchée par ImpactAssessment ; acteur système corrélé. | ImpactItem confirmé/qualifié ; root affecté identifié. | Marque Task/Draft/Preparation/Snapshot applicable `A_REVOIR` ou stale ; événement propre au root cible. | `caused_by_event_id` obligatoire ; expected revision du root cible. Ne modifie pas Case en masse. |
| `ConfirmPostAmendmentCompatibility` | `Review` | Relecteur autorisé ; objet affecté dans scope. | Version DCE active contrôlée ; impact source et motif de compatibilité. | Review de compatibilité ; `PostAmendmentCompatibilityConfirmed`. | Révision + clé. Ne supprime aucun ImpactItem historique. |
| `InvalidatePreparationSnapshot` | `PreparationSnapshot` | Commande aval process/system autorisée ; ImpactItem bloquant. | Snapshot dépend de l’objet impacté ; source/cible DCE identifiées. | Contenu inchangé ; applicabilité `CURRENT → STALE`; `PreparationSnapshotMarkedStale`. | `caused_by_event_id` obligatoire ; expected revision. Ne modifie pas Transmission ; celle-ci reçoit sa propre commande d’invalidation si nécessaire. |

---

# Partie II — Événements, cohérence et échecs

## 11. Events collaborateur : production et consommation

| Domain Event produit | Aggregate émetteur | Consommation autorisée | Consommation interdite |
|---|---|---|---|
| `AssignmentUnavailabilityReported` | Assignment | Projection travail, alerte/action patron par commande. | Modifier directement Task ou Case. |
| `DceDocumentMissingDeclared` | DceVersion | Projection documents, création de tâche/demande par policy. | Déclarer automatiquement une exigence satisfaite. |
| `RequirementConflictDeclared` | Finding | Risk, Task, Request ou PatronAction via commandes aval. | Décision automatique. |
| `TaskBlockerDeclared` | Task | Projection, demande/action via policy. | Résoudre ou abandonner la tâche directement. |
| `ReviewReturnedWithCorrections` | Review | `CreateCorrectionTask` / `ReopenTaskForCorrections` via Process Manager. | Modifier le brouillon ou la tâche dans le handler Review. |
| `PartnerRequestCreated` | Request | `GrantExternalShare` si policy et scope préautorisés. | Partager FinancialClass ou toute version non listée. |
| `PreparationSnapshotCreated` | PreparationSnapshot | `CreatePreparationTransmission` via `PreparationReviewProcess`. | Créer directement une Decision, Pricing ou Submission. |
| `PreparationSubmittedToPatron` | PreparationTransmission | `OpenPatronAction` ou regroupement de cause. | Marquer la préparation acceptée. |
| `DceImpactApplied` | ImpactAssessment | Marquage ciblé, invalidation snapshot/transmission, ouverture action/revue. | Modifier directement tous les objets concernés. |

Chaque Domain Event doit pouvoir rester interne au bounded context. Seule une conséquence externe, asynchrone ou de projection autorisée conduit à un Integration Event minimal. Les payloads ne transportent ni documents binaires, ni secrets, ni montants privés, ni contenu hors classe de confidentialité du consommateur.

## 12. Sémantique de reprise par groupe de commandes

| Groupe | Reprise réseau | Conflit de version | Contexte obsolète |
|---|---|---|---|
| Affectation / tâches / demandes / revues | Même clé : replay du résultat ; sinon conflit explicite. | Recharger la Task/Request/Review ; aucune fusion automatique. | Affectation retirée = refus et brouillon conservé. |
| Brouillons techniques | Même clé : version brouillon initiale retournée. | Comparaison/reprise obligatoire. | Source DCE remplacée : Draft à revoir, pas de perte de texte. |
| Preparation readiness | Même clé : même évaluation si inputs/règle identiques. | Nouvelle révision impose nouveau calcul. | `READINESS_STALE` si tâche/DCE/preuve critique évolue. |
| Snapshot / transmission | Même clé : même snapshot/transmission/process status. | Identity fonctionnelle protège le double envoi. | Snapshot stale/invalidation explicite ; ancien contenu conservé. |
| Impact DCE | Même paire source/cible/case : reprise de même assessment. | Impact en cours : état de suivi, pas de double assessment. | Nouvelle version cible : nouvelle `ImpactKey` et nouvelle évaluation. |

## 13. Codes d’erreur collaborateur

| Code | Sens métier et réponse attendue |
|---|---|
| `FORBIDDEN` | Droit insuffisant ; ne révèle pas le détail d’une ressource hors périmètre. |
| `NOT_FOUND_OR_FORBIDDEN` | Ressource inexistante ou inaccessible ; réponse neutre pour l’isolement tenant. |
| `ASSIGNMENT_INACTIVE` | Affectation retirée, expirée ou suspendue ; brouillons/historique conservés. |
| `SCOPE_DENIED` | L’affaire, lot, ressource ou verbe n’est pas couvert par l’affectation. |
| `RESOURCE_CLASS_FORBIDDEN` | Tentative FinancialClass/StrategicClass non explicitement déléguée. |
| `IDEMPOTENCY_KEY_REQUIRED` | Intention durable sans clé de reprise. |
| `IDEMPOTENCY_KEY_REUSED` | Même clé pour payload différent ; nouvelle intention nécessaire. |
| `IDEMPOTENCY_IN_PROGRESS` | Même intention en cours ; suivre `correlation_id` au lieu de renvoyer. |
| `VERSION_CONFLICT` | Root modifié depuis la lecture ; actualiser et reprendre. |
| `STALE_CONTEXT` | DCE, impact, readiness ou référence est devenu non applicable. |
| `DUPLICATE_FUNCTIONAL_IDENTITY` | Une même réalité métier active existe déjà. |
| `PROVENANCE_REQUIRED` | Source/version/localisation manquante pour un fait ou une exigence. |
| `STRONG_DEPENDENCY_UNSATISFIED` | Une dépendance forte empêche de terminer la tâche. |
| `PREPARATION_BLOCKED` | Au moins un blocker non résolu/non dérogé ; renvoyer `blockers`, `warnings`, `informational`. |
| `SNAPSHOT_IMMUTABLE` | Tentative de modifier le contenu d’un instantané existant. |
| `TRANSMISSION_ALREADY_ACTIVE` | Une transmission active existe pour le même snapshot/destinataire. |
| `RESOURCE_NOT_SHAREABLE` | Version, classe, expiration ou droit de partage invalide. |

---

# Partie III — Tests de gel DOMAIN-02

## 14. Tests de commande et d’architecture

| ID | Scénario | Résultat attendu |
|---|---|---|
| `DOM02-01` | Le navigateur envoie un `tenant_id` différent de la session. | Valeur ignorée/rejetée ; tenant résolu serveur seul. |
| `DOM02-02` | Une affectation est retirée entre affichage et `CompleteTask`. | `ASSIGNMENT_INACTIVE`; aucune mutation Task ; brouillon conservé. |
| `DOM02-03` | Deux collaborateurs terminent la même Task. | Un succès durable ; second replay seulement si même intention, sinon `VERSION_CONFLICT`. |
| `DOM02-04` | Une réponse partenaire est enregistrée. | Request reçoit une réponse ; aucune Evidence, Coverage ou Task terminée automatiquement. |
| `DOM02-05` | `ReturnReviewWithCorrections` est exécutée. | Review modifiée seule ; Task de correction créée/réouverte par Process Manager déclaré. |
| `DOM02-06` | Double clic sur `SubmitPreparationForPatronReview`. | Une seule FunctionalIdentity de Snapshot, une seule Transmission active et au plus une Action patron de revue. |
| `DOM02-07` | Snapshot créé mais Transmission non encore créée. | UI : `PREPARATION_FIGEE__TRANSMISSION_EN_COURS_DE_TRAITEMENT`, jamais « transmise ». |
| `DOM02-08` | Nouvelle version DCE impacte un snapshot transmis. | ImpactAssessment conservé ; contenu Snapshot inchangé ; applicabilité stale, Transmission invalidée par commande distincte si nécessaire. |
| `DOM02-09` | `CreatePartnerRequest` contient une pièce non partageable. | Request éventuellement refusée avant commit ou créée sans grant selon la policy ; aucun ExternalShare illégal. |
| `DOM02-10` | Collaborateur demande une classe FinancialClass. | `RESOURCE_CLASS_FORBIDDEN`; aucun montant, devis ou indice d’existence révélé. |
| `DOM02-11` | `TaskHandler` appelle directement `RequestHandler` ou `ReviewHandler`. | Échec du test d’architecture ; seul un Process Manager déclaré peut séquencer des commandes. |
| `DOM02-12` | `TaskRepository` persiste un root Request/Review ou `CaseRepository` persiste Pricing. | Échec de test d’architecture. |
| `DOM02-13` | Une relation ORM inter-aggregate comporte `ON DELETE CASCADE`. | Échec de test d’architecture et de migration. |
| `DOM02-14` | Deux bounded contexts s’importent mutuellement comme modèles riches. | Échec du test de dépendances circulaires. |
| `DOM02-15` | Une commande aval est produite après `DceImpactApplied`. | Elle porte le même `correlation_id` et `caused_by_event_id`; la chaîne Event A → Command B → Event B est reconstructible. |

## 15. Décisions de gel

1. Toutes les écritures collaborateur passent par une commande du catalogue fermé de DOMAIN-02.
2. Une commande collaborateur ne reçoit jamais un tenant, un rôle ou une permission de confiance depuis le navigateur.
3. Les commandes sensibles exigent simultanément affectation active, scope, classe de ressource, verbe, `expected_revision` et clé d’idempotence.
4. Les roots `Task`, `Request`, `Review`, `PreparationPackage`, `PreparationSnapshot`, `PreparationTransmission`, `ExternalShare` et `ImpactAssessment` restent distincts ; aucun handler ne les modifie ensemble.
5. `SubmitPreparationForPatronReview` est une intention orchestrée par `PreparationReviewProcess` ; son état de traitement est affiché honnêtement au collaborateur.
6. Une réponse reçue n’est jamais automatiquement une preuve, une couverture, une tâche terminée, une décision ou une autorisation de dépôt.
7. Les commandes collaborateur et leurs événements n’exposent aucune donnée `FinancialClass` ou `StrategicClass` non explicitement déléguée.
8. Les commandes aval portent obligatoirement `caused_by_event_id` et `correlation_id` ; les Domain Events et Integration Events restent distincts.
9. Les repositories manipulent un root à la fois ; les cascades ORM et `ON DELETE CASCADE` entre aggregates sont interdites.
10. La suite de tests DOMAIN-02 est un prérequis avant création d’endpoints d’écriture collaborateur.

---

## Références internes

- `SMART_AO_V8_DOMAIN_01_AGGREGATE_OWNERSHIP_MATRIX.md`.
- `SMART_AO_V8_CONTRAT_DE_DOMAINE.md` — version 1.2.
- `SMART_AO_V8_MATRICE_VUE_ACTION_COLLABORATEUR.md` — version 1.1.
- `SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE_COLLABORATEUR.md` — version 1.0.
- `SMART_AO_V8_SPEC_COMMANDES_IDEMPOTENCE.md` — contrat patron de référence.
- `pasted_content_34.txt` — revue critique DOMAIN-01.

---

**Fin de DOMAIN-02 — Spécification normalisée des commandes collaborateur — version 1.0**
