# SMART_AO V8 — Catalogue documentaire du dépôt

**Version :** 1.0  
**Statut :** index de navigation et de reprise  
**Objet :** localiser toute la documentation importée dans le dépôt V8 et distinguer les sources de travail des rendus PDF.

---

## 1. Règle de lecture

Le dépôt contient deux formes de documentation complémentaires.

> Les fichiers **Markdown** de `docs/reference/` sont les sources de travail versionnables, recherchables et modifiables. Les fichiers **PDF** de `docs/pdf/` sont les rendus de lecture, de partage et d’archivage fournis par le fondateur.

En cas de différence entre un PDF et son Markdown correspondant, le Markdown dont la version est indiquée dans `PROJECT_STATE.md` est la référence de codage ; toute divergence importante doit être portée dans `DECISION_LOG.md` avant implémentation.

| Emplacement | Contenu | Usage |
|---|---|---|
| `docs/PROJECT_STATE.md` | État actuel, dernier commit vert, prochaine action. | **Premier fichier à lire** lors d’une reprise. |
| `docs/ROADMAP_01_PLAN_GLOBAL_CODAGE.md` | Ordre global des slices et jalons produit. | Lire après PROJECT_STATE pour comprendre la trajectoire entière. |
| `docs/reference/` | Sources Markdown de vision, domaine, API, tests, persistance et architecture. | Référence de conception et de code. |
| `docs/pdf/` | PDF de consultation, partage et archivage. | Lecture humaine et comparaison avec les sources Markdown. |
| `docs/DECISION_LOG.md` | Arbitrages courts et datés. | Comprendre une décision locale. |
| `docs/adr/` | Décisions d’architecture majeures. | À créer lorsqu’une décision est coûteuse à inverser. |

---

## 2. Parcours de lecture selon le besoin

| Besoin | Lire dans cet ordre |
|---|---|
| Reprendre le code demain | `PROJECT_STATE.md` → ROADMAP-01 → README racine → contrat du slice courant → tests du slice. |
| Comprendre le produit BTP | Vision fonctionnelle → Cahier Patron → Cahier Collaborateur → contrats métier vers interface. |
| Coder le premier slice | DOMAIN-01 → DOMAIN-03 → APP-01 → TEST-01 → DATA-01 → ARC-01. |
| Coder une commande collaborateur | Contrat Collaborateur → Matrice vue/action collaborateur → DOMAIN-02 → tests du slice. |
| Coder une commande patron | Cahier Patron → Contrat patron → Matrice transitions patron → Spécification idempotence. |
| Préparer la préproduction VPS | Architecture infrastructure → ARC-01 → futurs `SEC-01`, `OPS-01`, `BACKUP-01`, `DEPLOY-01`. |

---

# Partie I — Documentation produit et expérience utilisateur

## 3. Vision métier et parcours global

| Document | Markdown source | PDF de consultation | Rôle |
|---|---|---|---|
| Vision fonctionnelle et parcours utilisateur | [Source Markdown](reference/SMART_AO_VISION_METIER_PARCOURS_UTILISATEUR.md) | [PDF](pdf/01_vision_metier/SMART_AO_VISION_FONCTIONNELLE_PARCOURS_UTILISATEUR.pdf) | Vision de valeur BTP : veille, DCE, réponse, décision et continuité. |
| Cahier fonctionnel des écrans SaaS | [Source Markdown](reference/SMART_AO_V8_CAHIER_FONCTIONNEL_ECRANS.md) | Pas de PDF joint distinct. | Navigation globale et principes anti-ERP. |
| Charte de reconstruction | [Source Markdown](reference/CHARTE_RECONSTRUCTION_SMART_AO_V8.md) | Pas de PDF joint distinct. | Constitution technique et métier V8. |

## 4. Espace patron

| Document | Markdown source | PDF de consultation | Rôle |
|---|---|---|---|
| Cahier métier espace patron | [Source Markdown](reference/SMART_AO_V8_CAHIER_ESPACE_PATRON.md) | [PDF](pdf/03_patron/SMART_AO_V8_CAHIER_ESPACE_PATRON.pdf) | Cockpit, bibliothèque, décisions, prix privé, dépôt et confidentialité. |
| Cahier des charges Cockpit Patron | [Source Markdown](reference/SMART_AO_V8_CAHIER_CHARGES_COCKPIT_PATRON.md) | [PDF](pdf/03_patron/SMART_AO_V8_CAHIER_CHARGES_COCKPIT_PATRON.pdf) | Détails UI, zones, états, filtres et recette du cockpit. |
| Contrat métier vers interface patron | [Source Markdown](reference/SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE.md) | [PDF](pdf/03_patron/SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE_PATRON.pdf) | Read models, commandes, erreurs, fraîcheur et provenance patron. |
| Matrice transitions patron | [Source Markdown](reference/SMART_AO_V8_MATRICE_TRANSITIONS_METIER.md) | [PDF](pdf/03_patron/SMART_AO_V8_MATRICE_TRANSITIONS_METIER_PATRON.pdf) | Vue → action → préconditions → transition → résultat → événement → vue. |
| Commandes et idempotence patron | [Source Markdown](reference/SMART_AO_V8_SPEC_COMMANDES_IDEMPOTENCE.md) | [PDF](pdf/03_patron/SMART_AO_V8_SPEC_COMMANDES_IDEMPOTENCE.pdf) | Enveloppe, conflits, outbox, retry et réponses d’écriture patron. |

## 5. Espace collaborateur

| Document | Markdown source | PDF de consultation | Rôle |
|---|---|---|---|
| Cahier métier collaborateur | [Source Markdown](reference/SMART_AO_V8_CAHIER_ESPACE_COLLABORATEUR.md) | [PDF](pdf/04_collaborateur/SMART_AO_V8_CAHIER_ESPACE_COLLABORATEUR.pdf) | Wizard DCE, tâches, preuves, demandes et transmission. |
| Contrat métier vers interface collaborateur | [Source Markdown](reference/SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE_COLLABORATEUR.md) | [PDF](pdf/04_collaborateur/SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE_COLLABORATEUR.pdf) | Droits contextualisés, états, vues et commandes collaborateur. |
| Matrice vue/action collaborateur | [Source Markdown](reference/SMART_AO_V8_MATRICE_VUE_ACTION_COLLABORATEUR.md) | [PDF](pdf/04_collaborateur/SMART_AO_V8_MATRICE_VUE_ACTION_COLLABORATEUR.pdf) | Intention → commande → autorisation → transition → retour utilisateur. |
| DOMAIN-02 commandes collaborateur | [Source Markdown](reference/SMART_AO_V8_DOMAIN_02_SPEC_COMMANDES_COLLABORATEUR.md) | [PDF](pdf/05_domaine/SMART_AO_V8_DOMAIN_02_SPEC_COMMANDES_COLLABORATEUR.pdf) | Contrat normalisé d’écriture, processus, erreurs et idempotence. |

---

# Partie II — Domaine, application, qualité et persistance

## 6. Domaine V8

| Document | Markdown source | PDF de consultation | Rôle |
|---|---|---|---|
| Contrat de domaine V8 | [Source Markdown](reference/SMART_AO_V8_CONTRAT_DE_DOMAINE.md) | [PDF](pdf/05_domaine/SMART_AO_V8_CONTRAT_DE_DOMAINE.pdf) | Vocabulaire, frontières, réalité métier, sécurité tenant et règles transverses. |
| DOMAIN-01 Aggregate / Ownership / Consistency Matrix | [Source Markdown](reference/SMART_AO_V8_DOMAIN_01_AGGREGATE_OWNERSHIP_MATRIX.md) | [PDF](pdf/05_domaine/SMART_AO_V8_DOMAIN_01_AGGREGATE_OWNERSHIP_MATRIX.pdf) | Roots, ownership, transactions, événements, projections et dépendances interdites. |
| DOMAIN-03 State Machines & Invariants — premier slice | [Source Markdown](reference/SMART_AO_V8_DOMAIN_03_STATE_MACHINES_INVARIANTS_FIRST_SLICE.md) | [PDF](pdf/05_domaine/SMART_AO_V8_DOMAIN_03_STATE_MACHINES_INVARIANTS_FIRST_SLICE.pdf) | Case, Consultation/DceVersion et Decision : états, invariants, erreurs et Process Managers. |
| Domain Core Scope | [Source Markdown](reference/SMART_AO_V8_DOMAIN_CORE_SCOPE.md) | Pas de PDF joint distinct. | Garde-fou de périmètre du premier vertical slice. |
| Revue pragmatic aggregates/events | [Source Markdown](reference/SMART_AO_V8_AGGREGATES_EVENTS_PRAGMATIC_REVIEW.md) | Pas de PDF joint distinct. | Référence de non-surconception avant code. |
| Notes d’état/aggregates historiques | [Source Markdown](reference/SMART_AO_V8_STATE_AGGREGATES_DECISION.md) | Pas de PDF joint distinct. | Contexte historique V8, non prioritaire pour implémenter. |

## 7. Contrats d’implémentation du premier slice

| Document | Markdown source | PDF de consultation | Rôle |
|---|---|---|---|
| APP-01 contrats Pydantic | [Source Markdown](reference/SMART_AO_V8_APP_01_CONTRATS_PYDANTIC_PREMIER_SLICE.md) | [PDF](pdf/06_implementation/SMART_AO_V8_APP_01_CONTRATS_PYDANTIC_PREMIER_SLICE.pdf) | Payloads, réponses, erreurs, idempotence et corrélation. |
| TEST-01 plan de tests | [Source Markdown](reference/SMART_AO_V8_TEST_01_PLAN_TESTS_PREMIER_SLICE.md) | [PDF](pdf/06_implementation/SMART_AO_V8_TEST_01_PLAN_TESTS_PREMIER_SLICE.pdf) | Domaine, DB, concurrence, tenant, architecture et Process Managers. |
| DATA-01 persistance et Alembic | [Source Markdown](reference/SMART_AO_V8_DATA_01_MAPPING_PERSISTANCE_ALEMBIC_PREMIER_SLICE.md) | [PDF](pdf/06_implementation/SMART_AO_V8_DATA_01_MAPPING_PERSISTANCE_ALEMBIC_PREMIER_SLICE.pdf) | Tables, contraintes, index, triggers, migrations et règles SQLAlchemy. |
| ARC-01 arborescence modulaire | [Source Markdown](reference/SMART_AO_V8_ARC_01_CONTRAT_ARBORESCENCE_MODULES.md) | [PDF](pdf/06_implementation/SMART_AO_V8_ARC_01_CONTRAT_ARBORESCENCE_MODULES.pdf) | Structure de dépôt, modules, imports, tests d’architecture et création incrémentale. |
| Vérifications PostgreSQL idempotentes | Pas de Markdown V8 importé distinct. | [PDF](pdf/06_implementation/VERIFICATIONS_POSTGRESQL_COMMANDES_IDEMPOTENTES_V8.pdf) | Support de contrôle pour les tests DB et la mise en œuvre d’APP-01/DATA-01. |

## 8. Architecture et roadmap

| Document | Markdown source | PDF de consultation | Rôle |
|---|---|---|---|
| Architecture et infrastructure de référence | [Source Markdown](reference/SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md) | [PDF](pdf/02_architecture/SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.pdf) | Stack, Docker, PostgreSQL, MinIO, parsing, calcul, sécurité et VPS. |
| ROADMAP-01 plan global de codage | [Source Markdown](ROADMAP_01_PLAN_GLOBAL_CODAGE.md) | [PDF](pdf/07_roadmap/ROADMAP_01_PLAN_GLOBAL_CODAGE.pdf) | Slices S00 à S12, jalons et critères de sortie jusqu’à préproduction. |
| Carte documentaire | [Source Markdown](reference/SMART_AO_V8_DOCUMENTATION_MAP.md) | Pas de PDF joint distinct. | Index historique et règle anti-prolifération documentaire. |

---

## 9. Convention des dossiers PDF

| Dossier | Contenu |
|---|---|
| `pdf/01_vision_metier/` | Vision fonctionnelle et parcours global. |
| `pdf/02_architecture/` | Infrastructure, environnement et opérations de référence. |
| `pdf/03_patron/` | Cockpit, contrats d’interface, transitions et commandes patron. |
| `pdf/04_collaborateur/` | Wizard, contrats d’interface et matrice collaborateur. |
| `pdf/05_domaine/` | Contrat de domaine et matrices DOMAIN. |
| `pdf/06_implementation/` | APP, tests, persistance, arborescence et vérifications DB. |
| `pdf/07_roadmap/` | Plan global de codage. |

Les documents DCE de test, annexes, plans, CCTP et pièces acheteur ne sont pas classés ici : ils iront dans `fixtures/dce/` avec leur inventaire, statut de confidentialité et mode de mise à disposition lorsque le slice analyse DCE commencera.

---

## 10. Décision de gel documentaire

1. Tous les PDF joints dans cette session sont versionnés dans `docs/pdf/`, avec des noms ASCII stables pour les scripts et liens Git.
2. Toutes les sources Markdown V8 disponibles dans `reports/` et nécessaires à la compréhension des PDF joints sont présentes dans `docs/reference/`.
3. Les PDF ne remplacent pas les contrats Markdown utilisés pour coder ; ils constituent le rendu de lecture et l’archive de partage.
4. Toute évolution normative est d’abord faite dans son Markdown de référence, puis un PDF peut être régénéré ou remplacé lors d’un jalon de documentation.
5. `PROJECT_STATE.md` reste le point de reprise ; ce catalogue est le deuxième fichier à lire lorsqu’il faut explorer l’ensemble de la documentation.

---

**Fin du Catalogue documentaire SMART_AO V8 — version 1.0**
