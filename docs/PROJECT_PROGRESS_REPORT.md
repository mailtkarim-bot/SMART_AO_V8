# SMART_AO V8 — Rapport global d’avancement

**Date de mise à jour :** 18 août 2026
**Branche de référence :** `ops/vps-deploy-health-digests-01`
**Dernier commit publié :** [`9b8b7c1`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/9b8b7c14723df7c4b80cb240b78ceb0760624154)
**Dernière CI verte :** [workflow `32150099196`](https://github.com/mailtkarim-bot/SMART_AO_V8/actions/runs/32150099196)
**Validation intégrée courante :** 435 tests backend verts, couverture branchée **85,04 %** avec seuil CI à 85 %, Ruff, Alembic, detect-secrets, SAST, audit de dépendances et build frontend TypeScript strict verts.

## 1. Position honnête du produit

SMART_AO V8 est un **socle SaaS BTP sécurisé, multi-tenant et fortement audité**, auquel s’ajoutent désormais les parcours de préparation documentaire, cockpit patron initial et paquet de dépôt contrôlé. Il ne faut toutefois pas le présenter comme une application commerciale achevée de bout en bout. Les frontières restantes sont l’extension des modèles et pièces documentaires finales, l’unification complète du cockpit, l’extension des contrôles de dépôt et le dépôt électronique lui-même, qui ne sera jamais déclaré réussi sans preuve externe.

La séparation fondamentale reste obligatoire : le collaborateur prépare et remonte des informations opérationnelles ; le patron conserve la décision, le chiffrage, la marge, la trésorerie et l’action de dépôt. Aucun contrat collaborateur ne doit transporter de données financières.

## 2. État par domaine

| Domaine | État | Fonctionnalités réellement présentes | Limite actuelle |
|---|---|---|---|
| Noyau métier | Livré et stable | `Case`, Consultation, DCE, Decision, révisions, événements, outbox, receipts et idempotence. | Le parcours utilisateur complet reste à assembler. |
| Sécurité et tenants | Livré et durci | Authentification, sessions, refresh rotatif, MFA, RBAC/ABAC/ReBAC, audit append-only, limitation anti-brute-force progressive. | La preuve d’exploitation réelle sur VPS reste ouverte. |
| Admission DCE | Livrée côté code | Staging privé, upload binaire, limites, hash serveur, MIME détecté, ClamAV fail-closed, rétention et extraction déterministe. | Scan ClamAV, HTTPS, stockage privé et sauvegardes doivent être éprouvés sur un hôte réel. |
| Analyse DCE | Livrée dans un périmètre déterministe | Analyse lexicale RC, classification, exigences atomiques, preuves sourcées, confirmations humaines et impact de rectificatif. | OCR, plans, formats supplémentaires et analyse IA complète restent hors périmètre. |
| Entreprise | Livrée dans son premier incrément | Société, assurances/Kbis/RIB, uploads privés, vérification humaine, qualifications, références, capacités et preuves versionnées. | Les workflows métier plus riches de bibliothèque et d’usage des preuves restent à étendre. |
| Collaboration | Fondations avancées | Affectations, interactions, tâches, demandes d’information, blocages, readiness, revues, corrections et brouillons techniques. | Le parcours complet de production de l’offre technique n’est pas encore assemblé. |
| Finance patronale | Fondation sécurisée étendue | Snapshots, lignes en unités mineures, publication contrôlée, lecture patronale, scénarios privés versionnés, sélection/archivage et prévisualisation d’import DPGF/BPU/Excel sécurisé. | L’import ne persiste encore qu’une prévisualisation ; rapprochement métier complet, calcul opérationnel et écriture durable des lignes importées restent à étendre. |
| Génération documentaire | Livrée dans un périmètre contrôlé | Assembleur déterministe avec `TechnicalDocumentFacts`, exigences DCE structurées, versions append-only, readiness et stockage privé. | Les modèles métier finaux et l’assemblage exhaustif des pièces RC restent à étendre. |
| Cockpit patron | Unifié dans le périmètre courant | React/Vite consomme les API d’affectations, journaux, interactions, Actions patron, Dossier décision, scénarios privés, paquet, preuve de dépôt et navigation métier. | Les écrans finaux de bibliothèque et la profondeur complète du workspace patron restent à enrichir. |
| Dépôt | Préparation et preuve manuelle livrées | `submission` produit un paquet tenant-scoped idempotent, manifest JSONB hashé, contrôles de versions publiées, preuve manuelle hashée append-only et `external_submission` permanent `NOT_PERFORMED`. | Transmission électronique réelle, accusé externe vérifié et intégration portail restent hors code et ne doivent pas être simulés. |
| Déploiement | Préparé, non exécuté sur VPS | Factory production, Caddy, healthchecks, pinning digest, sauvegarde/restauration isolée, timers et rotation des secrets. | Gate VPS réel, HTTPS, EICAR, supervision externe et rapport opérateur. |

## 3. Corrections de socle publiées

Les corrections confirmées par les audits sont maintenant intégrées : limitation anti-brute-force sur login/refresh, fixtures PostgreSQL centralisées, logs JSON et `request_id`, endpoint `/metrics` sans données métier, runtime backend non-root, dépendances frontend figées, seuil de couverture et scénarios de concurrence déterministes.

Le durcissement architectural a ensuite isolé la lecture DCE de l’application préparation derrière un port et un adaptateur, déplacé la détection de contenu sensible vers un contrat public, extrait les ports de quarantaine vers `platform.storage` et déplacé le bounded context `enterprise` hors de `membership`. Les tests d’architecture vérifient désormais ces nouvelles frontières.

| Slice | Commit | Preuve distante |
|---|---:|---:|
| Anti-brute-force | `025c36d` | CI `32076462140` verte |
| Fixtures PostgreSQL centralisées | `aac4de0` | CI `32078237301` verte |
| Observabilité et runtime non-root | `0ecb24c` puis `0ab3cbc` | CI corrective `32080763983` verte |
| Dépendances frontend reproductibles | `d4b33fe` | CI `32081102590` verte |
| Couverture et concurrence | `e3eafc7` | CI `32083322693` verte |
| Documentation consolidée | `cff4302` | CI `32083816529` verte |
| Frontières préparation | `bdce65a` | CI `32104138038` verte |
| Arborescence enterprise et ports platform | `4c995d2` | CI `32104886313` verte |

## 4. Architecture et arborescence

Le dépôt respecte la stratégie de **monolithe modulaire incrémental** : les modules réels ont des couches séparées, les routes HTTP ne portent pas les transitions métier, les tests d’architecture sont bloquants et les bounded contexts nouvellement réels sont maintenant rangés dans `backend/app/modules/enterprise`.

Cette conformité doit être lue comme une conformité vérifiée sur les frontières couvertes, non comme une preuve mathématique que chaque règle future ARC-01 est déjà exhaustive. Toute nouvelle dépendance inter-module doit passer par un contrat public, un port, un événement ou une commande aval corrélée, puis recevoir un test d’architecture.

## 5. Parcours métier restant à construire

Le parcours cible est : **DCE reçu → DCE sécurisé → lecture/confirmation → préparation collaborative → revue patronale → chiffrage → génération des pièces → paquet de dépôt → transmission**.

Les étapes DCE, préparation collaborative, génération technique, cockpit patron, navigation unifiée, wizard collaborateur, scénarios pricing, import sécurisé et préparation contrôlée du paquet sont codées et validées par CI. La suite immédiate est le gate VPS, désormais seule frontière opérationnelle ouverte. Un éventuel connecteur de transmission restera ultérieur et le dépôt électronique ne devra jamais être simulé comme réussi sans preuve externe.

## 6. Ordre de travail avant VPS

| Ordre | Slice | Résultat attendu |
|---:|---|---|
| 1 | Génération documentaire contrôlée | Livrée dans le périmètre actuel ; étendre ultérieurement les modèles et pièces RC finales. |
| 2 | Cockpit patron | Première tranche livrée ; réunir progressivement préparation, revue, bibliothèque et paquet. |
| 3 | Préparation du dépôt et preuve | Livrée : paquet immutable, manifest hashé, contrôles de versions, preuve manuelle append-only et `NOT_PERFORMED`. |
| 4 | Frontend patron et parcours intégrés | Livrés dans le périmètre courant : navigation métier, Dossier décision, preuve de dépôt, wizard collaborateur et actions de préparation. |
| 5 | Import pricing sécurisé | Livré en prévisualisation patronale : DPGF/BPU/Excel `.xlsx`, contrôles anti-macro/anti-bombe, colonnes normalisées, centimes déterministes et erreurs par ligne. |
| 6 | Réconciliation finale | Livrée : 435 tests, couverture 85,04 %, architecture, documentation, secrets, audit, SAST et build strict validés par CI. |
| 7 | Gate VPS | Après disponibilité d’un VPS : Docker, Caddy, ClamAV réel, EICAR, HTTPS, backups hors hôte, restauration isolée, supervision et rapport opérateur. |

## 7. Limites explicitement conservées

MinIO sans contrat de stockage stabilisé, Redis/sharding/tracing distribué spéculatifs, DAST/Semgrep déjà couverts par les contrôles existants et tests de charge nécessitant un environnement dédié ne sont pas ajoutés artificiellement. L’import métier actuel reste une prévisualisation contrôlée ; les fichiers non `.xlsx`, les macros, les archives surdimensionnées et les classeurs malformés sont rejetés plutôt que traités implicitement. Les formats documentaires non pris en charge restent explicitement `UNSUPPORTED` plutôt que de produire une fausse analyse.

## 8. Références internes

| Document | Rôle |
|---|---|
| [`docs/PROJECT_STATE.md`](PROJECT_STATE.md) | Reprise technique, slices, migrations, validations et risques courants. |
| [`todo.md`](../todo.md) | Checklist durable des frontières restantes. |
| [`docs/reference/SMART_AO_V8_ARC_01_CONTRAT_ARBORESCENCE_MODULES.md`](reference/SMART_AO_V8_ARC_01_CONTRAT_ARBORESCENCE_MODULES.md) | Contrat d’arborescence, couches et dépendances. |
| [`docs/reference/SMART_AO_V8_PREPARATION_COMPLETENESS_01_CONTRAT.md`](reference/SMART_AO_V8_PREPARATION_COMPLETENESS_01_CONTRAT.md) | Contrat de readiness et génération technique contrôlée. |
| [`docs/AUDIT_REMEDIATION_MATRIX.md`](AUDIT_REMEDIATION_MATRIX.md) | Réconciliation du premier audit. |
| [`docs/AUDIT2_RELEVANCE_MATRIX.md`](AUDIT2_RELEVANCE_MATRIX.md) | Pertinence du second audit et corrections retenues. |
