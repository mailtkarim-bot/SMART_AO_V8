# SMART_AO V8 — ROADMAP-01
## Plan global de codage par slices verticales

**Version :** 1.0  
**Statut :** feuille de route directrice de développement  
**Auteur :** Manus AI  
**Périmètre :** du dépôt initial au pilote préproduction sur VPS dédié  
**Sources normatives :** Charte V8, Vision métier, contrats Patron/Collaborateur, DOMAIN-01, DOMAIN-02, DOMAIN-03, APP-01, TEST-01, DATA-01 et ARC-01

---

## 1. Objet et règle de lecture

Cette roadmap répond à une question simple : **dans quel ordre coder SMART_AO V8 pour obtenir un produit vendable sans transformer le dépôt en chantier incontrôlable ?**

Elle donne la vue complète de l’application, mais n’autorise pas à tout développer simultanément. Chaque ligne est un **slice vertical** : un morceau de valeur métier qui traverse domaine, persistance, commandes, événements, lecture, API, interface et tests. Un slice n’est terminé que lorsqu’il est démontrable sur un scénario BTP et que sa non-régression est prouvée par la suite de tests.

> **Règle ROADMAP-01 :** nous ne passons jamais au slice suivant parce que les fichiers existent. Nous y passons quand le précédent a un comportement métier démontrable, une migration reproductible, des tests verts et un état de projet documenté.

Cette roadmap ne contient pas de dates artificielles. La vitesse réelle dépendra des essais DCE, des corrections, des validations patron et du niveau de finition UX. Les jalons sont donc des **preuves de maturité**, pas des promesses de calendrier.

---

## 2. Image globale du produit final

```text
Trouver une opportunité
        ↓
Comprendre la consultation et verrouiller le DCE source
        ↓
Qualifier l’affaire et décider humainement Go / No-Go
        ↓
Analyser exigences, preuves, risques et protections
        ↓
Faire préparer la réponse par les collaborateurs
        ↓
Contrôler, chiffrer et autoriser côté patron
        ↓
Construire le paquet, déposer et archiver l’accusé
        ↓
Assurer le suivi après attribution, exécution et facturation
```

| Zone produit | Utilisateur principal | Promesse SMART_AO |
|---|---|---|
| Veille / opportunités | Patron ou chargé d’affaires habilité | Ne plus manquer les consultations pertinentes et expliquer pourquoi elles le sont. |
| DCE / analyse | Collaborateur préparateur et patron | Transformer un corpus hétérogène en informations sourcées, lisibles et contrôlables. |
| Préparation | Collaborateur | Avancer pas à pas sans perdre le dossier, sans accéder aux données financières. |
| Décision / cockpit | Patron | Voir les inconnus, risques, échéances et preuves avant de s’engager. |
| Prix privé | Patron uniquement | Chiffrer avec les prix de l’entreprise, de manière déterministe et confidentielle. |
| Dépôt | Patron habilité | Construire un paquet cohérent, traçable et prouvé par un accusé. |
| Exécution | Patron et équipe autorisée | Préserver le lien entre réponse, marché obtenu, chantier, avenants et facturation. |

---

## 3. Invariants transversaux à respecter dans tous les slices

| Invariant | Traduction dans le code |
|---|---|
| **Confidentialité financière** | Les contrats, projections et routes collaborateur ne contiennent jamais prix, marge, coût, devis ou trésorerie. |
| **Décision humaine** | Aucun LLM, worker, projection ou automatisation ne finalise une Decision, un prix officiel ou un dépôt. |
| **Historique non destructif** | Les DCE, preuves, snapshots, prix officiels, décisions et accusés sont créés, archivés ou supersédés ; ils ne sont pas écrasés. |
| **Un root par transaction métier** | Un handler écrit son aggregate, ses entités internes, receipt, event et outbox ; jamais un second root métier. |
| **Tenant P0** | `tenant_id` est résolu serveur, filtré à chaque lecture/écriture et renforcé par contraintes DB. |
| **Concurrence explicite** | Les mutations portent `expected_revision`; aucun dernier-écrit-gagne silencieux. |
| **Idempotence** | Toute commande exposée a `command_id`, `idempotency_key`, hash de requête et résultat rejouable. |
| **Source distincte de l’interprétation** | `DceVersion/SourceStatement` ne se confond jamais avec `SourceAssertion`, `Requirement`, `Finding` ou Decision. |
| **IA contrôlée** | IA et agents produisent un candidat structuré, jamais une mutation de domaine directe. |
| **Anti-ERP** | Chaque écran guide une tâche métier courte ; le parcours est progressif et reprenable. |

---

# Partie I — Jalons de produit et ordre de codage

## 4. Carte complète des slices

| Ordre | Slice | Valeur métier prouvée | Modules principaux | Dépendances strictes |
|---:|---|---|---|---|
| `S00` | Socle dépôt et qualité | Dépôt clonable, testé, versionné et reprenable. | bootstrap, platform, docs, CI | **Terminé** : commit initial. |
| `S01` | Noyau Affaire + DCE + Décision | Une consultation devient une affaire, un DCE est versionné, le patron statue sans écraser l’historique. | case, dce, decision | DOMAIN-03, APP-01, TEST-01, DATA-01. |
| `S02` | Identité, tenant et premier patron | Un patron crée/ouvre son entreprise et accède à ses seules données. | platform/security, enterprise minimal | S01 persistance/API. |
| `S03` | Bibliothèque entreprise et preuves | L’entreprise conserve pièces, capacités, références et dates de validité. | enterprise, evidence, storage | S02. |
| `S04` | Ingestion et analyse DCE sourcée | Un DCE réel est importé, lu, localisé, classé, analysé et contrôlé contre un Golden DCE. | dce, analysis, knowledge, cognitive contrôlé | S01, S03. |
| `S05` | Espace collaborateur et travail préparatoire | Le patron affecte ; le collaborateur prépare, demande, révise et ne voit aucun prix. | membership, work, preparation | S02, S03, S04. |
| `S06` | Réponse technique et transmission patron | Le collaborateur produit une préparation versionnée et la transmet sans pouvoir finaliser. | preparation, work, sharing | S05. |
| `S07` | Cockpit patron, actions et projections | Le patron voit la situation réelle, traite les actions et décide avec fraîcheur/provenance. | decision, case, read models, patron actions | S01, S04, S06. |
| `S08` | Prix privé déterministe | Le patron chiffre avec ses propres données, scénarios et versions officielles confidentielles. | pricing | S03, S04, S07. |
| `S09` | Paquet de réponse et dépôt contrôlé | Le paquet est contrôlé, autorisé, déposé et relié à son accusé. | submission, generation, storage | S06, S08. |
| `S10` | Veille et qualification d’opportunités | Le logiciel détecte, déduplique, qualifie et convertit une opportunité en affaire. | opportunity, enterprise, case | S01, S03. |
| `S11` | Continuité marché obtenu / exécution | La réponse gagnante devient le point de départ de suivi, réserves, avenants et facturation. | execution | S09 et cadrage dédié. |
| `S12` | Préproduction et exploitation VPS | Un pilote client peut être déployé, sauvegardé, monitoré et restauré. | ops, security, observability | S01 à S09 au minimum. |

Les slices `S01` à `S09` constituent le **MVP commercial de réponse aux appels d’offres**. `S10` améliore l’amont commercial ; `S11` étend SMART_AO vers la gestion post-attribution.

---

## 5. Jalons de décision pour le fondateur

| Jalon | Démonstration attendue | Décision à prendre |
|---|---|---|
| `M0 — Socle` | Dépôt privé, CI, documentation de reprise, tests de fumée. | Déjà atteint. |
| `M1 — Vérité DCE` | Consultation + DCE versionné + affaire + décision Go/No-Go, avec rectificatif et concurrence. | Valider que le noyau représente correctement une réponse AO. |
| `M2 — Travail équipe` | Collaborateur affecté, préparation guidée, preuves, tâches, revue et transmission. | Valider l’ergonomie wizard et l’étanchéité patron/collaborateur. |
| `M3 — Dossier commercial` | Réponse technique, prix privé, contrôles et paquet autorisé. | Valider le positionnement commercial « le patron garde la main ». |
| `M4 — Dépôt pilote` | Dossier complet + accusé archivé sur un DCE réel. | Autoriser les essais de vente/pilote. |
| `M5 — Préproduction` | Sauvegarde, restauration, supervision, sécurité, déploiement VPS et exploitation prouvés. | Autoriser le premier vrai client payant. |

---

# Partie II — Détail de chaque slice

## 6. `S00` — Socle de dépôt et qualité

**État : terminé.** Le dépôt privé existe, l’arborescence ARC-01 est posée, les contrats sont importés dans `docs/reference/`, la CI backend est préparée, le linter et les tests de fumée sont verts.

| Éléments livrés | Contrôle de sortie |
|---|---|
| GitHub privé, `main`, `README`, `PROJECT_STATE`, `DECISION_LOG`. | Un développeur peut cloner et comprendre le prochain travail en moins de dix minutes. |
| FastAPI minimal, Docker Compose PostgreSQL, UV, Ruff, pytest, Alembic configuré. | `uv run ruff check .` et `uv run pytest backend/tests -q` verts. |
| Modules vides autorisés `case`, `dce`, `decision`. | Test d’architecture sur les couches minimales. |

**Interdit dans S00 :** fausse migration, modèle ORM non spécifié, endpoint métier, IA, worker ou frontend cosmétique.

---

## 7. `S01` — Noyau Affaire + Consultation/DceVersion + Decision

### 7.1. But métier

Le premier démonstrateur doit prouver qu’une entreprise peut enregistrer une consultation, admettre un DCE source, ouvrir une affaire avec périmètre explicite, puis laisser le patron préparer et finaliser une décision Go, Go conditionnel ou No-Go. Un rectificatif DCE doit rendre la décision à revoir sans modifier le choix historique.

### 7.2. Sous-slices de réalisation

| Sous-slice | Travail concret | Critère de sortie |
|---|---|---|
| `S01-A` | Types kernel, erreurs de domaine, `CaseScope`, aggregate `Case` et tests `CASE-INV-01..04`. | Le domaine Case est pur, sans SQLAlchemy/FastAPI. |
| `S01-B` | `Consultation`, lots/tranches, `DceVersion`, DceDocument et SourceStatement ; tests d’immuabilité. | Un corpus ne peut être remplacé ; un rectificatif crée une nouvelle version. |
| `S01-C` | `Decision`, `DecisionContext`, conditions, fingerprint, supersession ; tests concurrence Go/No-Go. | Une seule finalisation concurrente est possible ; le contexte final est immuable. |
| `S01-D` | Modèles SQLAlchemy, repositories un-root et migrations DATA-01. | `alembic upgrade head` sur PostgreSQL propre et tests DB verts. |
| `S01-E` | Dispatcher command, receipts idempotents, Domain Events, Outbox, `DecisionOutcomeProcess` et `DceSupersessionProcess`. | Double clic, retry et réception d’événement double n’ont aucun double effet. |
| `S01-F` | Routes FastAPI APP-01, RYOW, read models minimaux et interface React de démonstration. | Scénario M1 réalisable de bout en bout. |

### 7.3. Documents et tests déclenchés

| Référence | Usage |
|---|---|
| DOMAIN-03 | États, préconditions, invariants et Process Managers des trois roots. |
| APP-01 | Pydantic, réponses, erreurs et headers de commande. |
| TEST-01 | Tests schema, domaine, DB, concurrence, sécurité et architecture. |
| DATA-01 | Tables, checks, index, triggers et migrations Alembic. |
| `ENGINE-01` ciblé | À écrire seulement lorsque l’outbox/Process Manager sort du pseudocode et devient exécutable. |
| `READ-01` minimal | À écrire en même temps que les premiers read models/RyOW, pas avant. |

### 7.4. Démonstration de fin de slice

```text
Créer Consultation
  → enregistrer DCE v1 et ses documents
  → ouvrir Case sur un lot/périmètre explicite
  → créer + figer + approuver une Decision Go / No-Go
  → enregistrer DCE v2 rectificatif
  → voir Decision et Case marquées « à revoir » sans perte d’historique
  → rejouer une même commande sans créer de doublon
```

---

## 8. `S02` — Identité, tenant et premier patron

### 8.1. But métier

Le pilote doit devenir utilisable par une entreprise réelle. Le patron crée ou reçoit son accès, possède son tenant, crée les premiers membres et ne peut jamais consulter une ressource d’un autre tenant.

| Travail | Preuve |
|---|---|
| Authentification, session, réinitialisation et bootstrap du premier patron. | Aucun endpoint métier n’accepte `tenant_id` ou `actor_id` depuis le JSON client. |
| TenantContext serveur, membership patron, audit des actions. | Tests cross-tenant neutres et audit minimum des commandes acceptées/refusées. |
| RBAC initial et classe de confidentialité. | Patron peut agir sur Decision ; collaborateur standard est refusé. |
| Première gestion d’entreprise. | Création/édition limitée du profil légal de l’entreprise. |

**Document déclencheur :** `SEC-01 — Threat model, identité, tenant et RBAC`, rédigé juste avant les premières routes authentifiées.

---

## 9. `S03` — Bibliothèque entreprise, preuves et documents de référence

### 9.1. But métier

L’entrepreneur dépose ses pièces administratives, assurances, qualifications, références et capacités. Le logiciel en conserve les versions, droits d’usage, expiration et périmètre, sans les confondre avec une conformité à une exigence DCE.

| Capability | Aggregate / module | Critère de sortie |
|---|---|---|
| Profil entreprise, politiques et capacités. | `enterprise`. | Une capacité est réutilisable et versionnée, mais sa confirmation pour une affaire reste une évaluation séparée. |
| Pièces, versions, expiration et droits d’usage. | `evidence`. | Une preuve utilisée n’est jamais écrasée ; une nouvelle version est ajoutée. |
| Références chantier et partenaires. | `enterprise` + `evidence`. | Référence, justificatifs et droit d’usage restent traçables. |
| Stockage objet privé et antivirus. | `platform/storage`. | Hash, accès tenant et état de scan démontrables. |

**Documents déclencheurs :** `DOMAIN-09-ORG` et la première partie de `DOMAIN-04-ANA/PRF`, limités aux aggregates réellement implémentés.

---

## 10. `S04` — Ingestion et analyse DCE sourcée

### 10.1. But métier

SMART_AO doit commencer à faire gagner du temps réel : importer un DCE complexe, conserver les originaux, extraire ce qui est lisible, signaler ce qui ne l’est pas, localiser les passages et construire une analyse contrôlable.

| Sous-slice | Travail concret | Preuve de sortie |
|---|---|---|
| `S04-A` | Upload sécurisé, stockage privé, hash, scan, extraction native, OCR local en recours. | Chaque page/extrait reste relié au document source et à la version DCE. |
| `S04-B` | Classification RC/AE/CCAP/CCTP/BPU/DPGF/plans/annexes, incidents et manques. | L’outil n’affirme pas une analyse exhaustive si le corpus est `PARTIAL` ou `UNUSABLE`. |
| `S04-C` | `SourceAssertion`, Requirement, Coverage, Assessment, Finding, Risk et ProtectionPlan. | Chaîne source → interprétation → évaluation → constat est navigable et versionnée. |
| `S04-D` | Assistants IA contrôlés : sortie structurée candidate, validation humaine, provenance. | Aucun output LLM ne crée seul Requirement, Finding ou Decision. |
| `S04-E` | Golden DCE CANSSM/Filieris et cas de régression. | Les faits attendus sont retrouvés, les échecs et incertitudes sont visibles. |

**Documents déclencheurs :** `DOMAIN-04-ANA`, `APP-02-ANA`, `GOLDEN-DCE-01`, `ENGINE-02-DOCUMENT-PIPELINE`, `LLM-01-CONTROLLED-ANALYSIS`.

---

## 11. `S05` — Espace collaborateur et travail préparatoire

### 11.1. But métier

Le patron affecte un collaborateur à une affaire et à un périmètre. Le collaborateur prépare le dossier dans un wizard, peut prendre/terminer des tâches, demander une information, envoyer une revue, mais ne voit ni prix ni décision financière.

| Capability | Aggregates / modules | Preuve de sortie |
|---|---|---|
| Membership, affectation et délégation bornée. | `membership`. | Autorisation serveur acteur × tenant × affectation × scope × classe × verbe. |
| Task, dépendance, blocage et résultat. | `work`. | Une tâche critique n’est pas close sans résultat, preuve ou dérogation explicite. |
| Requests, réponses et relances. | `work`. | Une réponse de demande est versionnée et ne devient jamais automatiquement une Evidence. |
| Reviews et corrections. | `work`. | Une revue porte sur une version précise et ne modifie jamais directement sa cible. |
| Read models « Mes affaires / Mon travail ». | read models. | RYOW après commande, état de fraîcheur après événements. |

**Documents déclencheurs :** `DOMAIN-05-COLLABORATION-STATE-MACHINES`, complément ciblé de DOMAIN-02, `READ-02-COLLABORATION`.

---

## 12. `S06` — Préparation, réponse technique et transmission patron

### 12.1. But métier

Le collaborateur construit une réponse technique, vérifie sa readiness, formule des engagements candidats et transmet un snapshot figé au patron. Le patron reçoit une préparation, pas une décision automatique.

| Capability | Aggregate / module | Preuve de sortie |
|---|---|---|
| PreparationPackage vivant et readiness. | `preparation`. | Les blocages, avertissements et dérogations restent visibles. |
| ResponseDraft versionné et réemploi contrôlé. | `preparation`. | Une version de brouillon et ses engagements candidats sont traçables. |
| Snapshot immuable et hashé. | `preparation`. | Un nouveau snapshot est créé après modification ; l’ancien ne change pas. |
| Transmission patron corrélée. | `preparation` + Process Manager. | Snapshot → Transmission → Action patron, idempotent et reprenable. |
| Partage externe borné. | `sharing`. | Le partage référence des versions précises et peut expirer/révoquer. |

**Documents déclencheurs :** `DOMAIN-05-PREPARATION`, `ENGINE-03-TRANSMISSION-PROCESS`, `READ-03-WIZARD`.

---

## 13. `S07` — Cockpit patron, Action Center et projections

### 13.1. But métier

Le patron voit les affaires à traiter, les risques, échéances, inconnus, readiness, transmissions et décisions à prendre. Il ne subit pas un ERP : il reçoit une file d’actions explicables et peut ouvrir un dossier de décision sourcé.

| Capability | Modules | Preuve de sortie |
|---|---|---|
| PatronAction et causes dédupliquées. | `decision`/futur module patron-action. | Une action est ouverte/fermée/attendue avec cause et historique. |
| Cockpit portefeuille et Dossier de décision. | case, decision, read models, web. | Chaque indicateur affiche provenance, fraîcheur et action possible. |
| Journal de vérité en lecture seule. | read models + events. | Projection reconstructible, jamais propriétaire d’un état métier. |
| Alertes de délai/risque/rectificatif. | projections + runtime. | Une alerte ne décide pas ; elle rend une action nécessaire visible. |

**Documents déclencheurs :** `READ-01`, `APP-03-PATRON-VIEWS`, actualisation ciblée du cahier Cockpit.

---

## 14. `S08` — Prix privé déterministe et confidentialité totale

### 14.1. But métier

Le patron importe ses propres tableaux de prix, compare des scénarios, demande des devis, calcule des montants avec `Decimal`, fige une version de prix officielle et décide s’il l’autorise. Aucun collaborateur ne peut lire, deviner ou recevoir ces valeurs par événement, cache, logs ou API.

| Capability | Aggregate / module | Preuve de sortie |
|---|---|---|
| Import/version de données de prix entreprise. | pricing + enterprise. | Les fichiers internes sont traçables ; erreurs et colonnes ambiguës sont visibles. |
| Scénario et hypothèses. | `PricingScenario`. | Les montants utilisent `Decimal`, jamais `float`; toute hypothèse est versionnée. |
| Calcul déterministe/optimisation. | pricing calculators, OR-Tools/HiGHS selon besoin. | Même inputs = mêmes outputs/version/hash. |
| Version officielle et autorisation prix. | `OfficialPricingVersion` + `Decision`. | La version validée est immuable et ne fuit pas dans une projection collaborateur. |
| Tests d’isolation financière. | security + API + events. | Recherche automatisée d’interdits `price/cost/margin/...` dans contrats non patron. |

**Documents déclencheurs :** `DOMAIN-06-PRICING`, `CALC-01-DETERMINISTIC-PRICING`, `SEC-02-FINANCIAL-ISOLATION`.

---

## 15. `S09` — Paquet de réponse, contrôle et dépôt

### 15.1. But métier

Le patron assemble la réponse à partir de versions autorisées : DCE, pièces, mémoire technique, prix officiel et décisions. SMART_AO contrôle la cohérence, demande l’autorisation de dépôt, archive le manifeste et n’affirme jamais qu’un dépôt est prouvé sans accusé.

| Capability | Aggregate / module | Preuve de sortie |
|---|---|---|
| Génération des pièces requises selon RC. | generation + submission. | Les documents générés affichent leur source, version et statut de contrôle. |
| SubmissionPackage et manifest. | `submission`. | Toute pièce est versionnée et le fingerprint est reproductible. |
| Contrôle de complétude et de cohérence. | `submission`. | Blocage explicite si DCE/prix/décision/preuve obligatoire est obsolète ou absent. |
| Autorisation patron et tentative de dépôt. | `submission` + `decision`. | Aucun dépôt sans autorisation valide, fingerprints vérifiés. |
| Accusé de réception et coffre de dépôt. | `submission` + storage. | L’accusé est archivé ; `SUBMITTED` ne devient jamais « prouvé » par inférence. |

**Documents déclencheurs :** `DOMAIN-07-SUBMISSION`, `GEN-01-DOCUMENT-GENERATION`, `DEPLOYMENT-PORTAL-ADAPTERS` si une plateforme de dépôt est intégrée.

---

## 16. `S10` — Veille et qualification des opportunités

### 16.1. But métier

L’entreprise renseigne son métier, zone, rayon, capacités, exclusions et préférences. SMART_AO recherche ou reçoit des opportunités, les déduplique, explique leur score et permet leur qualification avant conversion en Case.

| Capability | Aggregate / module | Preuve de sortie |
|---|---|---|
| Profil de veille versionné. | opportunity. | Critères, exclusions et source restent explicables. |
| Collecteurs et normalisation. | opportunity + runtime. | Toute donnée externe porte sa provenance et date de collecte. |
| Déduplication / scoring explicable. | opportunity. | Le patron sait pourquoi une opportunité est proposée ou écartée. |
| Conversion contrôlée en Case. | opportunity → case public command. | L’opportunité reste historique ; elle ne se transforme pas par mutation directe. |

**Documents déclencheurs :** `DOMAIN-08-OPPORTUNITY`, `CONNECTOR-01-SOURCES-VEILLE`, règles de conformité commerciale avant automatisation externe.

---

## 17. `S11` — Marché obtenu, exécution et facturation

### 17.1. But métier

Cette extension intervient après validation du MVP de réponse AO. Elle exploite l’historique de la réponse obtenue pour préparer le chantier, suivre les engagements, avenants, situations et facturation, sans réécrire le dossier de réponse.

| Capability | Condition avant code |
|---|---|
| Création du dossier marché depuis une soumission/attribution. | Cadrage dédié des événements d’attribution et droits d’accès. |
| Planning, réserves, avenants, documents d’exécution. | Nouveau contrat de domaine de chantier. |
| Situations, factures, paiements et trésorerie. | Domaine financier séparé, exigences légales et confidentialité renforcée. |

**Décision actuelle :** ce slice est volontairement hors MVP de réponse AO. Il ne doit pas retarder la capacité à analyser, préparer, chiffrer et déposer un dossier.

---

## 18. `S12` — Préproduction, sécurité et exploitation VPS

### 18.1. But métier et opérationnel

Avant le premier client, l’application doit être installable et récupérable sur un VPS dédié, avec données chiffrées en transit, sauvegardes vérifiées, supervision, journalisation, procédures de mise à jour et exercice de restauration.

| Domaine | Livrable de sortie |
|---|---|
| Sécurité | Threat model, secrets hors Git, TLS, séparation réseau, analyse de contenu, audit et revue des droits. |
| PostgreSQL / MinIO | Sauvegarde automatisée, rétention, restauration testée sur environnement isolé. |
| Observabilité | Logs corrélés, métriques essentielles, health checks, alertes de capacité et d’échec jobs. |
| Déploiement | Image versionnée, Compose/Ansible ou pipeline choisi, rollback documenté, migrations sûres. |
| Données sensibles | Vérification des exports, logs, backups, stockage objet et isolation prix. |
| Pilote | Jeu de DCE réels contrôlé, parcours E2E, correction des anomalies, validation fondateur. |

**Documents déclencheurs :** `SEC-01`, `OPS-01`, `BACKUP-01`, `DEPLOY-01`, puis exercice de reprise réel.

---

# Partie III — Rythme de développement et contrôle qualité

## 19. Cycle obligatoire d’un item de code

```text
Invariance / besoin métier identifié
  ↓
Contrat ciblé ou référence existante relue
  ↓
Test rouge (schéma + domaine + refus invariant)
  ↓
Domaine pur
  ↓
Persistance et migration, si nécessaire
  ↓
Commande / idempotence / event / outbox
  ↓
Read model et API
  ↓
Interface minimaliste utile
  ↓
Test E2E ou Golden DCE
  ↓
Commit, CI verte, PROJECT_STATE mis à jour
```

| Échelle de travail | Règle |
|---|---|
| Une session | Une action de code clairement finie : par exemple une transition Case ou une règle DceVersion. |
| Un commit | Un comportement cohérent + tests associés ; pas un mélange de refactor, dépendances et fonctionnalité. |
| Une pull request | Un incrément démontrable, revu avec tests et mise à jour de `PROJECT_STATE.md`. |
| Un slice | Une capacité BTP visible de bout en bout, avec preuves de sécurité, concurrence et historique. |

## 20. Definition of Done commune à chaque slice

| Domaine de qualité | Preuve obligatoire |
|---|---|
| Métier | Les invariants sont testés en domaine pur et les transitions interdites sont refusées. |
| API | Les payloads, succès et erreurs respectent le contrat Pydantic fermé. |
| Tenant / droits | Test positif et test négatif cross-tenant / rôle insuffisant. |
| Concurrence | `expected_revision`, idempotence et comportement de retry prouvés lorsque le slice écrit. |
| Persistance | Migration propre, contraintes DB réelles et absence de cascade inter-root. |
| Événements | Event/outbox/process idempotent si un effet doit traverser une frontière. |
| Frontend | L’écran n’affiche que les droits/données du rôle et rend la fraîcheur/erreur compréhensible. |
| Reprise | `PROJECT_STATE.md`, documentation ciblée et tests mis à jour. |
| CI | Lint, tests du slice et suite de régression verte sans `xfail` permanent. |

---

## 21. Ce que nous ne ferons pas

| Anti-pattern | Décision V8 |
|---|---|
| Coder tous les modèles SQLAlchemy avant le métier. | Interdit : domaine et tests d’abord. |
| Construire toute l’interface avant les commandes durables. | Interdit : une UI suit une capacité réellement testée. |
| Ajouter un agent IA pour « aller vite » avant la traçabilité source. | Interdit : source, règles et validation humaine précèdent l’IA. |
| Mélanger prix, dossier collaborateur et décision patron dans des tables ou payloads partagés. | Interdit : confidentialité et ownership sont structurels. |
| Reprendre V7 fichier par fichier. | Interdit : réutilisation sélective seulement, après lecture de l’historique V7 concerné. |
| Créer les 17 modules cibles et leurs workers vides. | Interdit : un module existe quand un slice le rend nécessaire. |
| Déployer chez un client avant restauration, sécurité et DCE Golden. | Interdit : S12 est une porte de mise en production. |

---

## 22. Prochaine action exacte

Les slices métier prioritaires de préparation documentaire, cockpit patron initial et paquet de dépôt contrôlé sont publiés sur `ops/vps-deploy-health-digests-01`, avec CI verte. La prochaine action de développement est la réconciliation finale : conserver la suite backend complète verte, vérifier les tests d’architecture et d’import, le build frontend strict, les contrats OpenAPI, les secrets et la documentation. Les documents de reprise à maintenir sont `docs/PROJECT_STATE.md`, `docs/PROJECT_PROGRESS_REPORT.md` et `todo.md`.

> **Prochaine frontière opérationnelle :** lorsque l’utilisateur disposera d’un VPS, exécuter le runbook de préproduction avec images digest-pinnées, PostgreSQL, ClamAV/EICAR, Caddy/HTTPS, sauvegarde hors hôte, restauration isolée, timers systemd, supervision externe et rapport opérateur.

Le dépôt électronique reste hors simulation : le paquet préparé porte `external_submission: NOT_PERFORMED` tant qu’aucun accusé externe vérifiable n’est archivé.

---

## Références internes

- `docs/reference/SMART_AO_V8_DOCUMENTATION_MAP.md`.
- `docs/reference/SMART_AO_V8_DOMAIN_01_AGGREGATE_OWNERSHIP_MATRIX.md`.
- `docs/reference/SMART_AO_V8_DOMAIN_02_SPEC_COMMANDES_COLLABORATEUR.md`.
- `docs/reference/SMART_AO_V8_DOMAIN_03_STATE_MACHINES_INVARIANTS_FIRST_SLICE.md`.
- `docs/reference/SMART_AO_V8_APP_01_CONTRATS_PYDANTIC_PREMIER_SLICE.md`.
- `docs/reference/SMART_AO_V8_TEST_01_PLAN_TESTS_PREMIER_SLICE.md`.
- `docs/reference/SMART_AO_V8_DATA_01_MAPPING_PERSISTANCE_ALEMBIC_PREMIER_SLICE.md`.
- `docs/reference/SMART_AO_V8_ARC_01_CONTRAT_ARBORESCENCE_MODULES.md`.

---

**Fin de ROADMAP-01 — Plan global de codage SMART_AO V8 — version 1.0**
