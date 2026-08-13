# SMART_AO V8 — TEST-01
## Plan de tests de domaine et d’architecture — Premier slice

**Version :** 1.0  
**Statut :** contrat de qualité obligatoire avant la première implémentation V8  
**Auteur :** Manus AI  
**Périmètre :** `Case`, `Consultation`, `DceVersion`, `Decision`, leurs commandes APP-01, idempotence, tenant isolation et Process Managers associés  
**Hors périmètre :** analyse ANA détaillée, collaboration, prix, dépôt réel, OCR, IA, e-mail, navigateur et déploiement VPS

---

## 1. Objet et décision de test

TEST-01 ne décrit pas des tests décoratifs ni un objectif de couverture abstrait. Il définit les preuves automatisées minimales pour démontrer que le premier slice respecte DOMAIN-01, DOMAIN-03 et APP-01 avant d’être présenté comme fiable.

> **Décision TEST-01 :** aucune fonctionnalité du premier slice n’est considérée terminée tant que son invariant, sa transition heureuse, son refus métier, sa concurrence et son isolement tenant ne sont pas couverts au niveau approprié.

| Ce que le test doit démontrer | Ce qu’il ne doit pas faire |
|---|---|
| Que la règle métier est vraie, même sans FastAPI ou PostgreSQL. | Dépendre d’un écran, d’un navigateur ou d’un service externe. |
| Que le handler respecte la transaction, l’idempotence et les erreurs APP-01. | Rejouer la logique métier dans le test. |
| Que la base impose les unicités et les révisions réellement nécessaires. | Masquer une règle métier dans une assertion SQL opaque. |
| Que l’architecture interdit les écritures/cascades inter-aggregate. | Tester les détails privés de chaque classe. |

---

## 2. Pyramide de test et règles de vitesse

| Niveau | Nom / marqueur pytest | Dépendances | Ce qui est prouvé | Exécution attendue |
|---|---|---|---|---|
| L0 | `schema` | Pydantic seul | Formats, bornes, champs inconnus, validateurs locaux. | À chaque sauvegarde. |
| L1 | `domain` | Python pur, fake clock | Transitions, invariants, événements internes et immutabilité. | À chaque sauvegarde. |
| L2 | `application` | Handlers + repositories mémoire/fakes | Autorisation, références, idempotence et réponses APP-01. | À chaque sauvegarde. |
| L3 | `db` | PostgreSQL éphémère, SQLAlchemy, Alembic | Contraintes uniques, revision, transactions et rollback. | À chaque commit. |
| L4 | `api` | FastAPI + base isolée | HTTP, modèles Pydantic, réponse neutre et RYOW. | À chaque commit. |
| L5 | `architecture` | Analyse imports / metadata ORM | Un root par repository, pas de cascades ni handlers directs. | À chaque commit et CI. |
| L6 | `concurrency` | PostgreSQL, deux sessions | Conflits optimistes, doublons, retry et résultats rejouables. | À chaque commit du slice. |
| L7 | `process` | Outbox fake + Process Manager | Corrélation, reprise et absence de double effet aval. | À chaque commit du slice. |

Les tests L0–L2 ne doivent pas demander PostgreSQL. Les tests L3–L7 sont isolés, sans base de développement partagée et sans réseau public. Un test lent ou instable est un défaut de conception à corriger, pas un prétexte pour le désactiver.

---

## 3. Arborescence de tests à créer dans le dépôt V8

```text
tests/
├── conftest.py
├── factories/
│   ├── case_factory.py
│   ├── consultation_factory.py
│   ├── dce_version_factory.py
│   └── decision_factory.py
├── domain/
│   ├── test_case_transitions.py
│   ├── test_case_invariants.py
│   ├── test_consultation_transitions.py
│   ├── test_dce_version_transitions.py
│   ├── test_dce_version_invariants.py
│   └── test_decision_transitions.py
├── application/
│   ├── test_command_schemas.py
│   ├── test_case_handlers.py
│   ├── test_dce_handlers.py
│   ├── test_decision_handlers.py
│   └── test_idempotency_dispatch.py
├── integration/
│   ├── test_postgres_constraints.py
│   ├── test_optimistic_concurrency.py
│   ├── test_outbox_atomicity.py
│   └── test_process_managers.py
├── api/
│   ├── test_case_commands.py
│   ├── test_consultation_dce_commands.py
│   └── test_decision_commands.py
├── architecture/
│   ├── test_repository_boundaries.py
│   ├── test_handler_boundaries.py
│   ├── test_import_boundaries.py
│   └── test_orm_cascades.py
└── security/
    ├── test_tenant_isolation.py
    └── test_private_data_absence.py
```

Convention de nommage obligatoire :

```text
test_<aggregate>__when_<command_or_condition>__then_<observable_result>
```

Exemple : `test_decision__when_context_fingerprint_changed__then_rejects_stale_context`.

---

## 4. Fixtures, factories et doubles de test

### 4.1. Fixtures immuables obligatoires

| Fixture | Contenu | Règle |
|---|---|---|
| `frozen_clock` | Instant fixe timezone-aware. | Aucun test domaine ne dépend de `now()` réel. |
| `tenant_a`, `tenant_b` | Deux UUID d’entreprises différentes. | Chaque test d’isolement utilise les deux tenants. |
| `patron_a`, `collaborator_a` | Acteurs tenant A avec rôles distincts. | L’autorisation patron est testée explicitement. |
| `other_patron_b` | Patron du tenant B. | Sert aux accès interdits sans fuite. |
| `open_consultation` | Consultation A ouverte, lots/tranches source. | Construction sans persistance possible. |
| `admitted_dce_v1` | DceVersion A admise, hash, document, `SourceStatement` localisé. | Original/hash immuables. |
| `rectifying_dce_v2` | Nouvelle version avec prédécesseur v1. | Utilisée dans les tests de supersession. |
| `case_in_intake` | Case A active, scope de lot non ambigu. | Base de cycle Case. |
| `case_in_analysis` | Case A active avec DCE applicable. | Base décision/readiness. |
| `pending_go_decision` | Decision `GO_NO_GO`, contexte frozen et fingerprint connu. | Base tests de finalisation. |
| `conditional_go_decision` | Decision Go conditionnel, conditions ouvertes. | Base tests conditions. |
| `command_meta` | UUID déterministes, clé d’idempotence et corrélation. | Réutilisable pour les replays. |

### 4.2. Doubles autorisés et interdits

| Double | Autorisé ? | Usage |
|---|---|---|
| `FakeClock` | Oui | Temps stable dans les règles de domaine. |
| `InMemoryRepository` | Oui, L1/L2 | Vérifier les handlers sans SQLAlchemy. |
| `FakeIdempotencyStore` | Oui, L2 | Simuler `PROCESSING`, replay, mismatch et résultat mémorisé. |
| `FakeOutbox` | Oui, L2/L7 | Vérifier événements attendus, jamais la livraison réseau. |
| `FakeAuthorizationPolicy` | Oui, L2 | Cas autorisé/refusé de manière explicite. |
| `Mock` d’aggregate | Non | Le domaine doit être construit avec de vraies instances. |
| `Mock` de repository PostgreSQL dans L3/L6 | Non | Ces tests doivent exercer les contraintes réelles. |
| Réseau, LLM, OCR, MinIO réel | Non | Hors premier slice ; remplacer par références stables/fakes. |

### 4.3. Données de test et confidentialité

Les fixtures contiennent uniquement des exemples synthétiques : consultation fictive ou DCE Gold anonymisé. Aucun secret, identifiant client réel, prix, devis, RIB, pièce d’identité ou document de production ne doit entrer dans pytest.

---

# Partie I — Tests de schéma et de domaine pur

## 5. Tests Pydantic APP-01 — marqueur `schema`

| ID | GIVEN | WHEN | THEN | Source |
|---|---|---|---|---|
| `SCH-01` | `CreateCaseRequest` valide. | Champ inconnu ajouté. | Rejet Pydantic `extra_forbidden`. | APP-01 §2.1. |
| `SCH-02` | Métadonnées publiques. | `tenant_id`, `actor_id`, rôle ou permission envoyés. | Rejet : ces champs ne figurent dans aucun modèle public. | APP-01 §16. |
| `SCH-03` | `CaseScopeInput(SINGLE_LOT)`. | Zéro ou deux lots fournis. | Erreur locale explicite. | APP-01 §6 / `CASE-INV-02`. |
| `SCH-04` | `CaseScopeInput(MULTI_LOT)`. | Moins de deux lots. | Erreur locale explicite. | APP-01 §6. |
| `SCH-05` | `CaseScopeInput(TRANCHE|VARIANT|CUSTOM_SOURCED_SCOPE)`. | Référence ou justification absente. | Erreur locale explicite. | APP-01 §6. |
| `SCH-06` | `SourceLocator(TEXT_SPAN)`. | `text_end < text_start`. | Rejet Pydantic. | APP-01 §3.3. |
| `SCH-07` | `DceDocumentInput`. | Hash non SHA-256, taille nulle ou type absent. | Rejet Pydantic avant handler. | APP-01 §8. |
| `SCH-08` | `DecisionConditionInput`. | `due_at` et motif d’absence tous deux absents. | Rejet Pydantic. | APP-01 §11 / `DEC-INV-05`. |
| `SCH-09` | `DecisionContextInput`. | Liste de références vide. | Rejet Pydantic. | APP-01 §11. |
| `SCH-10` | `ExistingAggregateCommandMeta`. | Révision négative ou absente. | Rejet Pydantic. | APP-01 §3.1. |
| `SCH-11` | `PublicCommandMeta`. | Clé d’idempotence absente ou UUID invalide. | Rejet Pydantic. | APP-01 §3.1. |
| `SCH-12` | Tout modèle public du slice. | Sérialisation réponse/erreur. | Aucun champ financier, secret ou `ServerResolvedContext` n’apparaît. | APP-01 §16. |

## 6. Tests de domaine `Case` — marqueur `domain`

| ID | GIVEN | WHEN | THEN | Invariant / commande |
|---|---|---|---|---|
| `CASE-01` | Scope un lot source valide. | `CreateCase`. | Case `ACTIVE + INTAKE`, revision initiale, `CaseCreated`. | `CASE-INV-01/02`. |
| `CASE-02` | Scope multi-lots non justifié. | `CreateCase`. | Refus `CASE_SCOPE_AMBIGUOUS`, aucun événement. | `CASE-INV-02`. |
| `CASE-03` | Case active + Consultation même tenant. | `RegisterCaseConsultationLink`. | Référence enregistrée, stage inchangé. | Case §3.4. |
| `CASE-04` | Case et Consultation d’autres tenants. | Lier la Consultation. | Refus neutre ; Case inchangée. | `CASE-INV-03`. |
| `CASE-05` | Case active + DceVersion admise même Consultation. | `SetApplicableDceVersion`. | Freshness `CURRENT`, événement émis. | Case §3.4. |
| `CASE-06` | DceVersion retirée, supersédée ou d’autre Consultation. | `SetApplicableDceVersion`. | Refus `DCE_VERSION_NOT_APPLICABLE`. | `CASE-INV-03/08`. |
| `CASE-07` | Case `INTAKE`, source valide. | `StartCaseAnalysis`. | Stage `ANALYSIS`. | Case §3.4. |
| `CASE-08` | Case `ANALYSIS`, readiness `READY_WITH_UNKNOWNS`, DCE fraîche. | `MoveCaseToDecision`. | Stage `AWAITING_DECISION`, inconnus préservés. | Case §3.4. |
| `CASE-09` | Case `ANALYSIS`, readiness `NOT_READY`. | `MoveCaseToDecision`. | Refus sans changement. | Case §3.4. |
| `CASE-10` | Case `AWAITING_DECISION`, Decision Go `CURRENT`. | `StartOfferPreparation`. | Stage `OFFER_PREPARATION`; Decision seulement référencée. | `CASE-INV-04`. |
| `CASE-11` | Case `OFFER_PREPARATION`, DCE fraîche, Decision Go, transmission acceptée. | `MoveCaseToPricing`. | Stage `READY_FOR_PRICING`. | `CASE-INV-05`. |
| `CASE-12` | Même Case, Decision absente / DCE review required / transmission absente. | `MoveCaseToPricing`. | Refus explicite, aucun prix créé. | `CASE-INV-05`. |
| `CASE-13` | Case `READY_FOR_SUBMISSION`, déclaration réelle de dépôt référencée. | `RecordCaseSubmissionDeclared`. | Stage `SUBMITTED`, pas de preuve d’accusé. | `CASE-INV-06`. |
| `CASE-14` | Case `ACTIVE`. | `StopCase`. | Lifecycle `STOPPED`, motif/auteur/date conservés. | `CASE-INV-07`. |
| `CASE-15` | Case `STOPPED`. | Toute progression stage sauf reprise. | Refus `CASE_LIFECYCLE_FORBIDS_ACTION`. | `CASE-INV-07`. |
| `CASE-16` | Case `STOPPED`, nouvelle Decision patron de reprise. | `ReopenCaseWithPatronDecision`. | Lifecycle `ACTIVE`, target stage explicite. | Case §3.4. |
| `CASE-17` | Case `ARCHIVED`. | `RestoreArchivedCase`. | Historique intact ; lifecycle active seulement avec motif. | `CASE-INV-09`. |
| `CASE-18` | Rectificatif DCE reçu pour Case en readiness/pricing. | Commande aval fraîcheur. | Stage inchangé ; freshness `REVIEW_REQUIRED`. | `CASE-INV-08`. |
| `CASE-19` | Case en exécution. | Suppression d’un lien DCE/Decision/Submission. | Refus de domaine. | `CASE-INV-09`. |

## 7. Tests de domaine `Consultation` et `DceVersion` — marqueur `domain`

| ID | GIVEN | WHEN | THEN | Invariant / commande |
|---|---|---|---|---|
| `CONS-01` | Identité acheteur/référence disponible. | `CreateConsultation`. | Consultation `OPEN`, tenant-scoped, event. | `CONS-INV-01`. |
| `CONS-02` | Même tenant, même buyer/reference. | Deuxième création différente. | Refus doublon fonctionnel. | `CONS-INV-02`. |
| `CONS-03` | Consultation ouverte. | Enregistrer lot/tranche source. | Entité interne ajoutée, libellé source préservé. | `CONS-INV-03`. |
| `CONS-04` | Consultation avec Case/DceVersion liées. | `CloseConsultation`. | Consultation close uniquement ; aucune suppression d’objets liés. | `CONS-INV-04`. |
| `DCE-01` | Consultation ouverte + corpus hash/originaux valides. | `RegisterDceVersion`. | Version `ADMITTED`, documents internes, hash immuable, event. | `DCE-INV-01/02`. |
| `DCE-02` | DceVersion admise. | Modifier hash/original/document binaire. | Refus `DOCUMENT_ORIGINAL_IMMUTABLE`; revision inchangée. | `DCE-INV-02/03`. |
| `DCE-03` | DceVersion admise + document interne. | `ConfirmDocumentClassification`. | Annotation ajoutée, original inchangé. | DceVersion §5.3. |
| `DCE-04` | DceVersion admise. | Déclarer pièce manquante sourcée. | Integrity `PARTIAL`, limitation visible, event. | DceVersion §5.3. |
| `DCE-05` | DceVersion admise. | Déclarer manque sans source/raison. | Refus `SOURCE_LOCATION_REQUIRED`. | DceVersion §5.3. |
| `DCE-06` | DceVersion admise + anchor document/page. | `RegisterSourceStatement`. | Statement internal, localisé, aucun Requirement/Decision créé. | `DCE-INV-04`. |
| `DCE-07` | CandidateAssertion issue d’extraction. | Traitement de confirmation. | Peut produire SourceStatement ; jamais Requirement/BusinessFact/Decision automatique. | `DCE-INV-04`. |
| `DCE-08` | DceVersion integrity `UNUSABLE`. | `RegisterSourceStatement` ou ready analysis. | Rejet `DCE_VERSION_UNUSABLE`. | `DCE-INV-06`. |
| `DCE-09` | v1 admise + rectificatif v2. | `RegisterSupersedingDceVersion`. | v2 nouveau root ; v1 `SUPERSEDED`; aucun corpus écrasé. | `DCE-INV-05`. |
| `DCE-10` | DceVersion retirée avec source de retrait. | `WithdrawDceVersion`. | Lifecycle `WITHDRAWN`, contenu accessible audit uniquement. | `DCE-INV-07`. |
| `DCE-11` | DceVersion retirée. | La désigner applicable à une Case. | Refus `DCE_VERSION_NOT_APPLICABLE`. | `DCE-INV-07`. |
| `DCE-12` | DceVersion admise. | Tenter d’écrire Case/Decision/Pricing depuis son handler. | Échec test boundary ; aucune écriture externe. | `DCE-INV-08`. |

## 8. Tests de domaine `Decision` — marqueur `domain`

| ID | GIVEN | WHEN | THEN | Invariant / commande |
|---|---|---|---|---|
| `DEC-01` | Patron, type GO_NO_GO, Case/scope. | `CreateDecisionDraft`. | `DRAFT + UNDECIDED + INCOMPLETE`. | `DEC-INV-01`. |
| `DEC-02` | Collaborateur standard. | Création/approbation Decision. | Refus autorisation ; aucun root Decision finalisé. | `DEC-INV-03`. |
| `DEC-03` | Brouillon avec références minimales. | `PrepareDecisionContext`. | `PENDING_PATRON + FROZEN`, fingerprint stable. | `DEC-INV-02/06`. |
| `DEC-04` | Context incomplet selon DecisionType. | Préparation. | Refus `DECISION_CONTEXT_INCOMPLETE`. | `DEC-INV-06`. |
| `DEC-05` | Decision pending + fingerprint actuel. | `ApproveGoDecision`. | `FINALIZED + GO + CURRENT`, contexte immuable, event. | `DEC-INV-02/03/04`. |
| `DEC-06` | Fingerprint affiché différent. | `ApproveGoDecision`. | Refus `STALE_CONTEXT`; Decision reste pending. | `DEC-INV-07`. |
| `DEC-07` | Pending GO_NO_GO. | `ApproveConditionalGoDecision` avec condition sans owner. | Refus `CONDITION_OWNER_REQUIRED`. | `DEC-INV-05`. |
| `DEC-08` | Pending GO_NO_GO. | Go conditionnel sans due date ni motif / sans conséquence. | Refus explicite approprié. | `DEC-INV-05`. |
| `DEC-09` | Go conditionnel finalisé. | Satisfaire toutes les conditions avec preuves/observations. | `condition_status = SATISFIED`, outcome inchangé. | Decision §6.4. |
| `DEC-10` | Go conditionnel finalisé. | Échec d’une condition. | `FAILED`, validity review required si policy l’exige. | Decision §6.4. |
| `DEC-11` | Condition ouverte. | Waive par patron motivé. | Condition `WAIVED`, event ; aucun rewrite du choix. | Decision §6.4. |
| `DEC-12` | Decision finalisée. | Modifier outcome ou DecisionContext. | Refus `DECISION_ALREADY_FINALIZED`. | `DEC-INV-04`. |
| `DEC-13` | Dce impact confirmé sur référence Decision. | `MarkDecisionReviewRequired`. | Outcome/contexte conservés ; validity `REVIEW_REQUIRED`, context `STALE`. | `DEC-INV-08`. |
| `DEC-14` | Nouvelle Decision finalisée même sujet/type/scope. | `SupersedeDecision`. | Ancienne `SUPERSEDED`; successeure référencée ; historique conservé. | `DEC-INV-09`. |
| `DEC-15` | Decision finalisée. | Handler tente de changer Case/stage/Task/Pricing. | Échec architecture ; aucune mutation externe. | `DEC-INV-10`. |

---

# Partie II — Tests d’application, persistance et API

## 9. Tests de handlers et idempotence — marqueurs `application` et `db`

| ID | GIVEN | WHEN | THEN |
|---|---|---|---|
| `APP-01` | Commande create valide et clé nouvelle. | Dispatcher traite `CreateConsultation`. | Mutation, Domain Event, outbox et receipt `SUCCEEDED` dans même résultat. |
| `APP-02` | Même clé + même empreinte + succès terminal. | Commande rejouée. | Même `CommandSuccess`, `replayed=true`, aucun event/aggregate supplémentaire. |
| `APP-03` | Même clé + payload/expected refs différents. | Commande rejouée. | `409 IDEMPOTENCY_KEY_REUSED`, aucune mutation. |
| `APP-04` | Receipt en `PROCESSING` par autre worker. | Même commande reçue. | `202 IDEMPOTENCY_IN_PROGRESS`, même correlation, aucune double exécution. |
| `APP-05` | Rejet métier mémorisé. | Même commande même empreinte rejouée. | Même `CommandRejected`, aucun nouveau handler. |
| `APP-06` | Échec métier avant commit. | Handler refuse un invariant. | Receipt `REJECTED`, root/event/outbox inchangés. |
| `APP-07` | Crash simulé avant commit. | Dispatcher reprend même clé. | Aucun event durable initial ; nouvelle exécution possible selon lease. |
| `APP-08` | Crash simulé après commit avant réponse HTTP. | Client rejoue même clé. | Succès mémorisé retourné, aucun double event. |
| `APP-09` | Mutation root existing avec bonne revision. | Handler Case/DCE/Decision. | Revision +1, réponse contient nouvelle revision. |
| `APP-10` | Mutation avec revision dépassée. | Handler exécuté. | `409 VERSION_CONFLICT`, aucune mutation. |
| `APP-11` | Commande publique tente `caused_by_event_id`. | Validation API. | Rejet schema ; métadonnée réservée interne. |
| `APP-12` | Commande aval interne. | Process Manager la dispatch. | `caused_by_event_id` + correlation obligatoires et traçables. |
| `APP-13` | Succès durable mais projecteur indisponible. | Commande renvoie. | `SUCCEEDED + REFRESH_PENDING`; aucune fausse erreur. |

## 10. Tests PostgreSQL, contraintes et transactions — marqueur `db`

| ID | GIVEN | WHEN | THEN |
|---|---|---|---|
| `DB-01` | Deux créations Consultation même tenant/buyer/reference. | Insertion concurrente. | Contrainte fonctionnelle / résultat idempotent empêche le doublon. |
| `DB-02` | Même référence acheteur dans tenants A et B. | Créations. | Deux lignes autorisées, chacune isolée par tenant. |
| `DB-03` | Deux commandes même `(tenant, actor, type, idempotency_key)`. | Insertion receipt. | Contrainte unique durable. |
| `DB-04` | Même idempotency key mais actor ou tenant différent. | Insertion. | Ne se collisionne pas indûment. |
| `DB-05` | DceVersion admise. | Tentative update `corpus_hash`. | Repository/domain refuse ; hash initial toujours présent. |
| `DB-06` | Case/Decision/DceVersion relationnées. | Suppression root. | Aucun `ON DELETE CASCADE` inter-aggregate ; suppression refusée ou archivage fonctionnel. |
| `DB-07` | Handler succès. | Inspection transaction. | Root, domain event, outbox et receipt sont tous présents ou tous absents. |
| `DB-08` | Handler déclenche exception après root avant commit. | Rollback. | Root, event, outbox et receipt succès absents. |
| `DB-09` | Revision 4 persistée. | `UPDATE ... WHERE revision=3`. | Zéro ligne touchée ; application retourne conflit. |
| `DB-10` | Migration initiale appliquée à base vierge. | Upgrade Alembic. | Toutes tables/indices/contraintes du slice sont créés ; downgrade contrôlé ou explicitement refusé selon politique. |

## 11. Tests d’API FastAPI et RYOW — marqueur `api`

| ID | GIVEN | WHEN | THEN |
|---|---|---|---|
| `API-01` | Patron authentifié tenant A. | `POST /consultations` body APP-01 valide. | `201`, `CommandSuccess`, référence DCE, aucune donnée privée. |
| `API-02` | Commande avec champ inconnu/UUID invalide. | POST. | `422` au contrat `CommandRejected`/validation ; aucune réservation métier. |
| `API-03` | Patron A vise ressource B. | Commande mutation/lire. | `404 NOT_FOUND_OR_FORBIDDEN`, aucune fuite d’existence. |
| `API-04` | Patron valide DceVersion. | POST register + GET read-your-own-write. | Hash, référence et integrity disponibles immédiatement. |
| `API-05` | Patron approbation Go réussie, Process Manager Case en attente. | POST approve. | `200 SUCCEEDED`, Decision finale visible, Case indique traitement aval plutôt qu’état fictif. |
| `API-06` | Double POST exact même idempotency key. | Deux appels successifs. | Deuxième réponse replayée ; mêmes refs/event ids. |
| `API-07` | Même clé, body différent. | Second POST. | `409 IDEMPOTENCY_KEY_REUSED`. |
| `API-08` | Collaborateur standard. | POST approve-go / withdraw-DCE. | `403 PATRON_AUTHORIZATION_REQUIRED`; aucune donnée stratégique renvoyée. |
| `API-09` | Context fingerprint périmé. | POST approve-go. | `409 STALE_CONTEXT`, changed resources minimales. |
| `API-10` | Projection indisponible. | Commande durable réussie. | `200/201` avec `projection.status=REFRESH_PENDING`; pas de retry client forcé. |

---

# Partie III — Concurrence, sécurité et architecture

## 12. Tests de concurrence et de reprise — marqueur `concurrency`

| ID | GIVEN | WHEN | THEN |
|---|---|---|---|
| `CONC-01` | Deux sessions lisent Case revision N. | Stages incompatibles soumis simultanément. | Une réussite revision N+1 ; l’autre `VERSION_CONFLICT`. |
| `CONC-02` | Deux sessions lisent Decision pending revision N. | Approve Go et No-Go simultanés. | Une seule Decision finalisée ; autre conflit, jamais deux outcomes. |
| `CONC-03` | Deux requêtes identiques même clé arrivent en parallèle. | Dispatcher réserve receipt. | Une exécution, une réponse processing/replay, un event. |
| `CONC-04` | Deux requêtes CreateCase même FunctionalIdentity, clés différentes. | Transactions simultanées. | Une Case active ; seconde doublon fonctionnel ou référence au résultat conforme. |
| `CONC-05` | DceVersion v1 est rectifiée durant préparation Decision. | Approval après impact. | Rejet `STALE_CONTEXT`; Decision non finalisée. |
| `CONC-06` | Transaction PostgreSQL reçoit échec de sérialisation/lock simulé. | Dispatcher retry technique borné. | Aucun double event ; après épuisement `CONCURRENT_CHANGE_RETRY_REQUIRED`. |
| `CONC-07` | Receipt lease expirée après arrêt worker avant commit. | Même clé reçue après lease. | Reprise autorisée sans doublon. |

## 13. Tests d’isolement, confidentialité et audit — marqueurs `security` et `api`

| ID | GIVEN | WHEN | THEN |
|---|---|---|---|
| `SEC-01` | Tenants A et B contenant mêmes identifiers métier. | Read/write cross-tenant. | Isolation stricte par tenant, réponse neutre. |
| `SEC-02` | Client ajoute `tenant_id`, `actor_id`, `actor_kind` dans JSON. | Validation route. | Champs refusés ; le contexte serveur reste seul source de vérité. |
| `SEC-03` | Collaborateur authentifié A. | Commande Decision finalisante. | Refus 403, audit minimal ; Decision inchangée. |
| `SEC-04` | Payload, réponse, event et receipt du slice. | Recherche récursive de mots-clés/champs financiers interdits. | Aucun champ `price`, `cost`, `margin`, `quote`, `treasury`, secret/token/binary. |
| `SEC-05` | Erreur de ressource B déclenchée par A. | Handler/API retourne erreur. | Aucun nom, hash, revision, tenant ou titre de B n’est exposé. |
| `SEC-06` | Commande acceptée ou rejetée. | Inspection journal/audit. | Actor, tenant, command id, correlation, résultat et horodatage présents ; payload sensible minimisé. |

## 14. Tests d’architecture — marqueur `architecture`

| ID | Règle vérifiée | Méthode testable | Échec attendu |
|---|---|---|---|
| `ARCH-01` | Un repository manipule un root. | Analyse imports + spies repository. | `CaseRepository` sauvegarde DceVersion/Decision. |
| `ARCH-02` | Un handler ne modifie qu’un root. | Instrumenter UnitOfWork aggregate writes. | `CaseHandler` écrit Task/Pricing/Decision. |
| `ARCH-03` | Aucun handler direct → handler direct. | Analyse AST ou registry d’appels. | `DecisionHandler` appelle `CaseHandler` directement. |
| `ARCH-04` | Seul Process Manager séquence. | Registry Process Manager déclarée. | Commande aval sans `caused_by_event_id/correlation_id`. |
| `ARCH-05` | Pas de cascade ORM inter-root. | Inspection metadata SQLAlchemy + migrations. | `cascade="all, delete"` ou `ON DELETE CASCADE` Case→Decision/DCE. |
| `ARCH-06` | Pas d’import circulaire de modèles riches. | `import-linter` ou test AST des modules. | `case.domain` et `decision.domain` s’importent mutuellement. |
| `ARCH-07` | Projection lecture seule. | Gardes runtime / analyse dépendances. | Projecteur appelle repository `save` d’un aggregate. |
| `ARCH-08` | Agrégats externes référencés par identifiant. | Inspection modèles/domain APIs. | Aggregate `Case` contient objet `Decision` riche mutable. |
| `ARCH-09` | Domain sans FastAPI/SQLAlchemy. | Import tests sur `domain/`. | Module domaine importe request, session ou ORM. |
| `ARCH-10` | Aucun float financier. | Recherche AST/types du domain financial futur ; test préventif actif. | Utilisation `float` dans un objet Money ou calcul financier. |

## 15. Tests de Process Managers et Outbox — marqueur `process`

| ID | GIVEN | WHEN | THEN |
|---|---|---|---|
| `PROC-01` | `GoDecisionApproved`. | `DecisionOutcomeProcess` consomme événement une fois. | Émet exactement une commande `StartOfferPreparation` corrélée. |
| `PROC-02` | Même event Go livré deux fois. | Process Manager redémarre/reçoit doublon. | Une seule commande aval fonctionnelle ou replay de même clé. |
| `PROC-03` | Go finalisé, commande aval Case échoue techniquement. | Reprise Process Manager. | Decision reste finale ; état Case indique traitement/retry, pas de rollback fiction. |
| `PROC-04` | DceVersion v2 avec predecessor. | `DceSupersessionProcess`. | v1 marquée à revoir/supersédée via commande, Case/Decision traitées séparément. |
| `PROC-05` | Impact critique DCE. | `DecisionStalenessProcess`. | `MarkDecisionReviewRequired` porte cause event/correlation et conserve contexte Decision. |
| `PROC-06` | Outbox contient event réussi. | Publication simulée deux fois. | Projecteur/process manager déduplique via `event_id`. |
| `PROC-07` | Transaction refuse une mutation. | Inspection outbox. | Aucun Integration Event publiable pour la mutation refusée. |

---

# Partie IV — Traçabilité et critères de sortie

## 16. Matrice de couverture minimale

| Contrat source | Familles de tests obligatoires |
|---|---|
| DOMAIN-03 `CASE-INV-01..09` | `CASE-01..19`, `APP-09/10`, `CONC-01/04`, `ARCH-01/02/05/08`, `SEC-01/05`. |
| DOMAIN-03 `CONS-INV-01..05` | `CONS-01..04`, `DB-01/02/06`, `ARCH-05/08`. |
| DOMAIN-03 `DCE-INV-01..08` | `DCE-01..12`, `DB-05/06/07/08`, `CONC-05`, `PROC-04`. |
| DOMAIN-03 `DEC-INV-01..10` | `DEC-01..15`, `APP-09/10`, `CONC-02/05`, `PROC-01/03/05`, `SEC-03`. |
| APP-01 validation et réponses | `SCH-01..12`, `API-01..10`, `APP-01..13`. |
| Idempotence / replay V8 | `APP-01..08`, `DB-03/04/07/08`, `CONC-03/07`, `API-06/07`. |
| Isolation tenant et confidentialité | `SEC-01..06`, `API-03/08`, `DB-02/04`. |
| Interdits architecture DOMAIN-01 | `ARCH-01..10`, `DB-06`, `DCE-12`, `DEC-15`. |

## 17. Marqueurs et commandes pytest

```ini
# pyproject.toml
[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
markers = [
  "schema: validation Pydantic sans dépendance externe",
  "domain: règles pures et invariants",
  "application: handlers, auth, idempotence et résultats",
  "db: PostgreSQL, contraintes et migrations",
  "api: contrats FastAPI",
  "architecture: frontières, imports et ORM",
  "concurrency: deux sessions et retries",
  "security: tenant isolation et confidentialité",
  "process: Process Managers, outbox et déduplication",
]
```

| Commande développeur | Ce qu’elle doit exécuter |
|---|---|
| `pytest -m 'schema or domain'` | Boucle locale rapide avant chaque commit. |
| `pytest -m 'application or architecture'` | Handlers et interdits de conception. |
| `pytest -m 'db or api or concurrency or process or security'` | Suite PostgreSQL/HTTP avant push et en CI. |
| `pytest` | Toute la suite sur CI et avant release. |

## 18. Critères de sortie avant code de démonstration

Le premier slice est considéré prêt pour une démonstration technique seulement si toutes les conditions suivantes sont vraies.

| Critère | Preuve exigée |
|---|---|
| Schémas | `SCH-01..12` verts ; les JSON APP-01 sont validés et fermés. |
| Case | Tous scénarios `CASE-*` applicables verts ; aucune progression illégale. |
| Consultation/DCE | Tous scénarios `CONS-*` et `DCE-*` verts ; corpus non destructif prouvé. |
| Decision | Tous scénarios `DEC-*` verts ; patron, fingerprint, conditions et supersession prouvés. |
| Idempotence | Replays, mismatch, processing, crash avant/après commit et concurrence verts. |
| Tenant/security | Aucun test cross-tenant ne révèle l’existence ou le contenu de l’autre entreprise. |
| Architecture | `ARCH-01..10` verts ; aucune cascade, cross-write, import circulaire ou handler direct. |
| Process | Les doublons d’événements n’entraînent aucun double effet aval. |
| CI | Suite complète stable trois exécutions successives, sans test flaky ni `xfail` permanent. |

Aucune règle métier critique ne peut être marquée `skip`, `xfail` ou couverte uniquement par un test manuel. Un échec de test d’architecture bloque la fusion au même titre qu’un échec de test fonctionnel.

---

## 19. Décisions de gel TEST-01

1. Chaque nouvelle commande doit créer au minimum un test schema, un test de succès domaine, un test de refus invariant, un test d’idempotence et un test tenant/autorisation si elle est exposée par API.
2. Chaque invariant DOMAIN-03 doit avoir un identifiant de test traçable dans cette matrice.
3. Les tests métier purs ne dépendent ni de FastAPI, ni de SQLAlchemy, ni de PostgreSQL.
4. Les tests de DB doivent valider les contraintes réelles ; les repositories mémoire ne suffisent pas à prouver l’idempotence ou la concurrence de production.
5. Les doubles de test ne doivent jamais simuler la règle métier à la place du domaine.
6. Les Process Managers sont testés comme des séquenceurs idempotents, sans devenir des propriétaires de données métier.
7. Le code de production est écrit en petits incréments : test rouge → domaine → test vert → persistance → test vert → API → test vert.

---

## Références internes

- `SMART_AO_V8_DOMAIN_01_AGGREGATE_OWNERSHIP_MATRIX.md` — DOMAIN-01 v1.1.
- `SMART_AO_V8_DOMAIN_03_STATE_MACHINES_INVARIANTS_FIRST_SLICE.md` — DOMAIN-03 v1.0.
- `SMART_AO_V8_APP_01_CONTRATS_PYDANTIC_PREMIER_SLICE.md` — APP-01 v1.0.
- `SMART_AO_V8_SPEC_COMMANDES_IDEMPOTENCE.md` — conventions d’idempotence V8.
- `SMART_AO_V8_DOCUMENTATION_MAP.md` — roadmap documentaire et point de bascule.

---

**Fin de TEST-01 — Plan de tests du premier slice — version 1.0**
