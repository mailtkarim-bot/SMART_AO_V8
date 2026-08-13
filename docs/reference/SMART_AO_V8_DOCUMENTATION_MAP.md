# SMART_AO V8 — Carte documentaire et point de bascule vers le code

**Version :** 1.0  
**Statut :** index directeur de la documentation V8  
**Objectif :** permettre au fondateur et aux développeurs de savoir ce qui est déjà figé, ce qui sert de référence, ce qui est historique, et quels sont les rares documents réellement nécessaires avant le premier code.

---

## 1. Décision de pilotage

SMART_AO a franchi la phase de découverte métier : la vision produit, les parcours patron/collaborateur, les frontières de domaine, l’ownership, les commandes collaborateur et les machines d’état du premier slice sont documentés.

> **Décision proposée :** nous ne produisons plus de grands documents généralistes. Avant de coder le premier slice, il reste seulement **trois contrats courts et directement codables** : `APP-01`, `TEST-01` et `DATA-01`. Ensuite, le travail bascule vers le dépôt, les tests de domaine et le code. Les documents suivants sont écrits **au fil des slices**, jamais par anticipation massive.

| État | Signification |
|---|---|
| **Gel candidat** | Référence de conception à valider avant le code correspondant. |
| **Actif** | Document qui pilote encore une décision ou une implémentation. |
| **Référence** | Source utile à consulter, sans être un contrat d’implémentation direct. |
| **Recherche / preuve** | Matériau source ayant alimenté les contrats ; ne doit pas être recopié dans le code. |
| **Historique V7** | Analyse de l’existant, utile pour éviter une régression ; non normative pour V8. |
| **Brouillon / à consolider** | Utile, mais à intégrer ou remplacer avant toute utilisation normative. |

---

## 2. Vue macro : où nous en sommes

```text
Vision métier BTP                         ██████████  Terminé
Parcours et écrans patron/collaborateur   ██████████  Terminé
Architecture et sécurité de référence     ██████████  Terminé
Domain ownership / transactions           ██████████  Terminé
Commandes collaborateur                   ██████████  Terminé
State machines premier slice              ██████████  Terminé
Contrats Pydantic/API premier slice       ░░░░░░░░░░  À faire, court et ciblé
Tests de domaine/architecture             ░░░░░░░░░░  À faire, avec le code
Mapping persistance / migration initiale  ░░░░░░░░░░  À faire, avec le code
Implémentation premier slice              ░░░░░░░░░░  Démarre juste après les trois contrats ciblés
```

Le ralentissement ressenti vient du fait que nous avons fait les documents de fond nécessaires à une V8 fiable. **La bonne réponse n’est pas de continuer à produire une documentation exhaustive de tout le logiciel** : c’est d’arrêter la documentation large et de produire uniquement les contrats qui alimentent le prochain commit.

---

# Partie I — Documents V8 actifs et normatifs

## 3. Fondations produit, métier et expérience utilisateur

| # | Fichier | Rôle | Statut | Utilisation maintenant |
|---:|---|---|---|---|
| 1 | `CHARTE_RECONSTRUCTION_SMART_AO_V8.md` | Constitution de collaboration : invariants, méthode, interdits et qualité. | **Actif** | À relire au début de chaque nouvelle phase majeure. |
| 2 | `SMART_AO_VISION_METIER_PARCOURS_UTILISATEUR.md` | Vision BTP complète : valeur client, avant DCE, DCE, réponse et continuité. | **Référence** | Produit, UX et arbitrages métier. |
| 3 | `SMART_AO_V8_CAHIER_FONCTIONNEL_ECRANS.md` | Parcours SaaS et principes d’écrans. | **Référence** | Navigation globale et critères UX. |
| 4 | `SMART_AO_V8_CAHIER_ESPACE_PATRON.md` | Cockpit patron, décisions, bibliothèque, prix privé, dépôt et confidentialité. | **Actif** | Tout slice patron et tout écran confidentiel. |
| 5 | `SMART_AO_V8_CAHIER_CHARGES_COCKPIT_PATRON.md` | Spécification détaillée du Cockpit Patron. | **Référence** | Implémentation future du Cockpit. |
| 6 | `SMART_AO_V8_CAHIER_ESPACE_COLLABORATEUR.md` | Parcours collaborateur : analyse, tâches, preuves, préparation et transmission. | **Actif** | Implémentation des slices collaboration. |
| 7 | `SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE.md` | Contrat patron : vues, sources, fraîcheur, actions et erreurs. | **Actif** | Endpoints et projections patron. |
| 8 | `SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE_COLLABORATEUR.md` | Contrat collaborateur : droits contextualisés, vues, boutons et états. | **Actif** | Endpoints et projections collaborateur. |
| 9 | `SMART_AO_V8_MATRICE_TRANSITIONS_METIER.md` | Patron : vue → action → transition → résultat → événement. | **Actif** | Commandes patron et tests de transition. |
| 10 | `SMART_AO_V8_MATRICE_VUE_ACTION_COLLABORATEUR.md` | Collaborateur : intention → commande → autorisation → transition. | **Actif** | Commandes et UX collaborateur. |

## 4. Fondations de domaine, sécurité et implémentation

| # | Fichier | Rôle | Statut | Utilisation maintenant |
|---:|---|---|---|---|
| 11 | `SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md` | Stack, VPS, stockage, parsing, calcul, sécurité, déploiement et sauvegarde. | **Actif** | Création du dépôt et environnement Docker. |
| 12 | `SMART_AO_V8_CONTRAT_DE_DOMAINE.md` | Vocabulaire et règles domaine V8 fondatrices. | **Référence** | Contrat de niveau supérieur ; ne pas coder directement sans DOMAIN-01/03. |
| 13 | `SMART_AO_V8_SPEC_COMMANDES_IDEMPOTENCE.md` | Convention des commandes patron : idempotence, outbox, conflits et réponses. | **Actif** | Modèle de l’enveloppe d’écriture patron. |
| 14 | `SMART_AO_V8_DOMAIN_01_AGGREGATE_OWNERSHIP_MATRIX.md` | Ownership, aggregates, relations, transactions et interdits de dépendance. | **Gel candidat** | Référence principale de découpage code/repositories. |
| 15 | `SMART_AO_V8_DOMAIN_02_SPEC_COMMANDES_COLLABORATEUR.md` | Commandes collaborateur : droits, erreurs, idempotence, processus et tests. | **Gel candidat** | Slices collaborateur, après le premier slice patron/DCE. |
| 16 | `SMART_AO_V8_DOMAIN_03_STATE_MACHINES_INVARIANTS_FIRST_SLICE.md` | Machines d’état et invariants de `Case`, `Consultation/DceVersion`, `Decision`. | **Gel candidat** | Référence directe du premier code domaine. |
| 17 | `SMART_AO_V8_DOMAIN_CORE_SCOPE.md` | Périmètre du premier vertical slice et noyau de domaine. | **Référence** | Garde-fou contre l’élargissement du premier développement. |
| 18 | `SMART_AO_V8_STATE_AGGREGATES_DECISION.md` | Décisions préparatoires sur state machines, aggregates et transactions. | **Référence historique V8** | À consulter si une décision de DOMAIN-01/03 paraît surprenante. |
| 19 | `SMART_AO_V8_AGGREGATES_EVENTS_PRAGMATIC_REVIEW.md` | Revue pragmatique : monolithe modulaire, événements et slice pilote. | **Référence** | Éviter la sur-conception, microservices et bus prématurés. |

## 5. Produits de validation métier et jeux de preuve

| # | Fichier | Rôle | Statut | Utilisation maintenant |
|---:|---|---|---|---|
| 20 | `V8_PRODUCT_CONTRACT_DRAFT.md` | Contrat produit provisoire du pilote. | **Brouillon / à consolider** | Source de contrôle ; ne pas rendre normatif sans arbitrage. |
| 21 | `V8_GOLDEN_DCE_CATALOG_DRAFT.md` | Catalogue des DCE de référence pour tests métier. | **Brouillon prioritaire** | À compléter avant les tests de traitement DCE réels. |
| 22 | `DCE_GOLD_001_INVENTORY_NOTES.md` | Inventaire du DCE de référence CANSSM/Filieris. | **Référence** | Première donnée de test métier. |

---

# Partie II — Documents historiques, recherches et notes : à conserver, mais ne pas relire systématiquement

## 6. Compréhension V7 et migration

| # | Fichier | Rôle | Statut | Quand le consulter |
|---:|---|---|---|---|
| 23 | `SMART_AO_V7_1_REALITY_MATRIX_PRE_V8.md` | Cartographie de la réalité V7.1 avant reconstruction. | **Historique V7** | Lorsqu’un ancien composant doit être repris ou remplacé. |
| 24 | `SMART_AO_V7_TO_V8_COMMAND_EVENT_MATRIX.md` | Translation des comportements V7 vers commandes/événements V8. | **Historique V7** | Pendant la migration sélective de fonctionnalités. |
| 25 | `autopsy_v7_1_notes.md` | Notes d’autopsie : erreurs, risques et enseignements V7.1. | **Historique V7** | Avant de réutiliser du code V7. |
| 26 | `revue_architecture_SMART_AO_V7_1.md` | Revue technique de l’architecture V7.1. | **Historique V7** | Avant tout portage de module. |
| 27 | `methodologie_prise_en_main_SMART_AO_V7_1.md` | Méthode de prise en main inter-session de V7.1. | **Historique V7** | Pour auditer l’ancien dépôt, pas pour coder V8. |

## 7. Recherche métier, valeur commerciale et innovation

| # | Fichier | Rôle | Statut | Quand le consulter |
|---:|---|---|---|---|
| 28 | `etude_metier_valeur_commerciale_SMART_AO.md` | Valeur métier, douleur entrepreneur et feuille de route commerciale. | **Recherche / preuve** | Marketing, roadmap, pitch et priorisation valeur. |
| 29 | `recherche_vision_metier_smart_ao_2026.md` | Notes de recherche sur la vision produit. | **Recherche / preuve** | Si la vision doit évoluer. |
| 30 | `recherche_metier_smartao_notes.md` | Notes métier brutes. | **Recherche / preuve** | Vérifier l’origine d’une idée, pas pour implémenter directement. |
| 31 | `recherche_catalogue_documents_smart_ao_2026.md` | Recherche sur les pièces attendues dans les réponses. | **Recherche / preuve** | Compléter générateurs documentaires. |
| 32 | `recherche_cockpit_patron_btp_2026.md` | Recherche sur le besoin patron et cockpit. | **Recherche / preuve** | Faire évoluer l’espace patron. |
| 33 | `recherche_espace_collaborateur_btp_2026.md` | Recherche sur le travail collaborateur BTP. | **Recherche / preuve** | Faire évoluer le wizard collaborateur. |
| 34 | `verification_innovations_metier_smart_ao_2026.md` | Vérification des innovations métier et limites. | **Recherche / preuve** | Roadmap différenciante, pas le slice pilote. |
| 35 | `recherche_idempotence_postgres_v8.md` | Notes de recherche technique sur l’idempotence. | **Recherche / preuve** | APP-01 / DATA-01 ; à remplacer par conventions V8 validées. |

## 8. Extraits, avis externes et notes de réflexion

| # | Fichier | Rôle | Statut | Quand le consulter |
|---:|---|---|---|---|
| 36 | `extraits_constitution_metier_proposee_v8.md` | Extraits ayant nourri les principes V8. | **Archive de conception** | En cas de révision fondatrice. |
| 37 | `extraits_etude_metier_pdf_apports_v8_notes.md` | Notes extraites d’une étude métier. | **Archive de conception** | Recherche approfondie future. |
| 38 | `extraits_metier_v7_1_pour_vision_v8.md` | Fonctionnalités métier V7 retenues. | **Archive de conception** | Vérifier une omission fonctionnelle. |
| 39 | `extraits_rapport_dependances_super_puissantes_notes.md` | Idées issues d’une revue de dépendances. | **Archive de conception** | Architecture/infrastructure future. |
| 40 | `extraits_rapport_imbattable_legendaire_notes.md` | Idées de différenciation produit. | **Archive de conception** | Roadmap produit future. |
| 41 | `evaluation_remarques_espace_patron_v8_1.md` | Revue critique de l’espace patron. | **Archive de conception** | Si le Cockpit est remis en question. |
| 42 | `evaluation_avis_grok_collaboration_SMART_AO.md` | Analyse d’un avis externe sur la collaboration IA/projet. | **Archive de réflexion** | Sans impact direct sur le code V8. |

---

# Partie III — Ce qui reste à produire : priorisation stricte

## 9. Les trois seuls documents obligatoires avant le premier code

Ces documents ne sont pas de nouveaux cahiers de vision. Ce sont des contrats courts dont chaque ligne devient un modèle, un test ou une migration.

| Ordre | Document à produire | Contenu exact | Taille cible | Pourquoi il est indispensable |
|---:|---|---|---|---|
| 1 | **`APP-01 — Contrats d’écriture du premier slice`** | Schémas Pydantic des commandes/réponses/erreurs de `Case`, `Consultation`, `DceVersion`, `Decision`; en-têtes tenant/idempotence/révision/corrélation ; payloads et exemples canoniques. | 25–40 pages maximum ou 250–400 lignes. | Transforme DOMAIN-03 en endpoints sans inventer de champs. |
| 2 | **`TEST-01 — Plan de tests du premier slice`** | Tests domaine, concurrence, tenant, idempotence, architecture, Process Managers et critères Given/When/Then. | 15–25 pages maximum ou 150–250 lignes. | Empêche de coder sans preuve ; devient directement la suite pytest. |
| 3 | **`DATA-01 — Mapping persistance premier slice`** | Tables SQLAlchemy, clés, contraintes uniques tenant-scoped, indices, colonnes de révision, conventions Alembic, aucune cascade inter-root. | 15–25 pages maximum ou 150–250 lignes. | Rend la persistance explicite avant la première migration. |

> **Point de bascule :** dès que ces trois documents sont validés, nous créons le dépôt V8, le Docker Compose, les modules de domaine et les premiers tests. Nous ne créons aucun autre grand document avant le premier commit fonctionnel et testé.

## 10. Documents à écrire avec le code, pas avant

| Document / artefact | Quand | Pourquoi ne pas le faire maintenant |
|---|---|---|
| `ENGINE-01 — Contrat events, outbox et Process Managers` | Lorsque le premier Process Manager ou worker est codé. | Le besoin exact de delivery/retry dépend du code et de la première base. |
| `READ-01 — Projections et RYOW` | Lors des premières lectures API / vues Cockpit. | Les projections doivent dériver des vrais events, non d’hypothèses. |
| `SEC-01 — Threat model applicatif et RBAC` | Avant exposition Internet / premières données clientes. | À faire avant déploiement public, pas avant les domain tests locaux. |
| `API-01 — OpenAPI publique/interne` | Quand les endpoints FastAPI existent. | L’OpenAPI doit être générée à partir des vrais modèles Pydantic. |
| `OPS-01 — Exploitation, observabilité et runbooks` | Avant préproduction VPS. | Dépend du Compose réel, des jobs et des métriques disponibles. |
| `BACKUP-01 — Sauvegarde/restauration et exercice de reprise` | Avant toute donnée client. | Dépend de PostgreSQL, MinIO et volumes effectivement déployés. |
| `DEPLOY-01 — Procédure VPS client` | Avant premier déploiement client. | Dépend de l’image Docker et du pipeline de release réel. |
| `GOLDEN-DCE-01 — DCE de référence finalisé` | Avant le slice d’analyse documentaire. | Le catalogue existe en brouillon ; le compléter au moment où le pipeline DCE est codé. |

## 11. Documents à produire par slice fonctionnel, seulement lorsque ce slice commence

| Slice futur | Documents ciblés à produire alors | Ne pas produire maintenant parce que |
|---|---|---|
| **Analyse DCE / ANA** | `DOMAIN-04-ANA` : SourceAssertion, Requirement, Coverage, Assessment, Finding, Risk et ProtectionPlan ; `APP-02-ANA`; tests Golden DCE. | Le premier slice doit d’abord prouver Case/DCE/Decision. |
| **Collaboration** | `DOMAIN-05-COLLABORATION` : state machines `Assignment`, `Task`, `Request`, `Review`, `Preparation`, `Snapshot`, `Transmission`, `Share`, `Impact`. | DOMAIN-02 fixe déjà les commandes ; les détails d’état viendront avant leur code. |
| **Prix privé** | `DOMAIN-06-PRICING`; contrats déterministes Decimal/OR-Tools; tests de confidentialité. | Aucun collaborateur n’y accède et le moteur métier doit être éprouvé avant. |
| **Paquet et dépôt** | `DOMAIN-07-SUBMISSION`; `SubmissionPackage`, `SubmissionAttempt`, `SubmissionReceipt`; tests accusé obligatoire. | Dépend de prix et décisions réellement intégrés. |
| **Veille** | `DOMAIN-08-OPPORTUNITY`; sources, déduplication, qualification et conversion en Case. | Non nécessaire pour traiter un DCE importé manuellement. |
| **Entreprise/bibliothèque** | `DOMAIN-09-ORG`; preuves, capacités, références, partenaires et politiques. | À découper autour des écrans réellement implémentés. |
| **Exécution / facture** | Nouveau cadrage métier dédié. | Hors premier produit de réponse aux AO. |

---

# Partie IV — Ordre opérationnel à partir de maintenant

## 12. Plan sans lenteur documentaire

| Étape | Livrable | Règle de sortie |
|---:|---|---|
| 0 | **Valider DOMAIN-03 et ce point de bascule** | Le fondateur confirme que le premier slice est bien `Case + Consultation/DceVersion + Decision`. |
| 1 | `APP-01` | Chaque commande de DOMAIN-03 a un payload, une réponse et des erreurs typées. |
| 2 | `TEST-01` | Les cas de concurrence, tenant, idempotence et transitions sont écrits en Given/When/Then. |
| 3 | `DATA-01` | Tables, contraintes et migrations initiales sont décidées. |
| 4 | **Créer le dépôt V8 privé** | Arborescence, Docker Compose, CI, lint, pytest et conventions de commits existent. |
| 5 | **Coder le domaine pur** | Tests de `Case`, `Consultation`, `DceVersion`, `Decision` verts sans web/ORM. |
| 6 | **Coder persistance et API** | Repositories, Alembic, FastAPI et idempotence fonctionnent sur PostgreSQL. |
| 7 | **Premier démonstrateur** | Création consultation/DCE/case, décision Go/No-Go, rectificatif, conflits et audit démontrables. |

## 13. Règles anti-prolifération documentaire

1. Aucun document généraliste ne sera créé après cet index sans décision explicite du fondateur.
2. Tout nouveau document doit porter un **slice**, une **question de code** et un **critère de sortie**.
3. Une note de recherche reste une source ; elle ne concurrence jamais un contrat actif.
4. Un document d’implémentation est limité à ce qui peut être transformé en modèle, test, migration, endpoint ou runbook dans les deux étapes suivantes.
5. Les documents futurs sont créés **juste avant** le slice concerné, pas six mois avant.
6. Si une information existe déjà dans un contrat actif, elle est référencée, jamais dupliquée.

---

## 14. Conclusion pratique

Aujourd’hui, SMART_AO possède **42 documents existants**, auxquels s’ajoute cet index. Mais il ne faut pas en déduire qu’il reste une montagne équivalente de documentation à produire.

Le cœur qui conditionne le code est déjà là. Il reste **trois documents ciblés**, puis nous passons au dépôt et aux tests. Tous les autres documents sont soit historiques, soit de recherche, soit à produire au moment du slice fonctionnel correspondant.

> **Le projet ne doit plus ralentir à cause de la documentation. À partir de maintenant, chaque document restant doit directement permettre le commit suivant.**

---

**Fin de la Carte documentaire SMART_AO V8 — version 1.0**
