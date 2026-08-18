# SMART_AO V8 — Rapport global d’avancement

**Date de mise à jour :** 18 août 2026
**Branche de référence :** `ops/vps-deploy-health-digests-01`
**Dernier commit publié :** `4c995d2`
**Dernière CI verte :** [workflow `32104886313`](https://github.com/mailtkarim-bot/SMART_AO_V8/actions/runs/32104886313)
**Référence de validation fonctionnelle précédente :** 402 tests backend verts et 89,32 % de couverture branchée avec seuil CI à 85 %.

## 1. Position honnête du produit

SMART_AO V8 est un **socle SaaS BTP sécurisé, multi-tenant et fortement audité**, auquel s’ajoutent déjà plusieurs parcours métier réels. Il ne faut toutefois pas le présenter comme une application commerciale achevée de bout en bout. Les quatre frontières encore à construire avant une déclaration produit complète sont la fabrication finale des documents de réponse, le cockpit patron couvrant tout le cycle métier, la préparation contrôlée d’un paquet de dépôt et le dépôt électronique lui-même.

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
| Finance patronale | Fondation sécurisée | Snapshots, lignes en unités mineures, publication contrôlée, lecture patronale et confidentialité financière. | Import Excel/DPGF/BPU, calcul opérationnel, scénarios de marge et trésorerie restent à construire. |
| Génération documentaire | Partielle mais fonctionnelle | Génération versionnée d’un document technique contrôlé et brouillons de réponse avec readiness, stockage privé et hash serveur. | Il manque les modèles métier finaux, l’assemblage des pièces demandées et le paquet de remise. |
| Cockpit patron | Partiel | API de lecture d’affectations, journaux, interactions et finance ; premier cockpit React connecté aux affaires et brouillons financiers. | Navigation métier complète, décisions, bibliothèque, préparation, revue et dépôt ne sont pas encore réunis dans une expérience cohérente. |
| Dépôt | Non livré | Aucun paquet final de transmission ni connecteur de dépôt électronique revendiqué. | Préparer, verrouiller, contrôler, transmettre et conserver un accusé de réception. |
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

Les quatre premières étapes sont largement codées. La prochaine séquence doit donc compléter la génération documentaire avec des sections et pièces explicitement contractualisées, construire le cockpit patron sur les API réelles, préparer un paquet de dépôt immutable et contrôlable, puis seulement ouvrir un éventuel connecteur de transmission. Le dépôt électronique ne doit jamais être simulé comme réussi sans preuve externe.

## 6. Ordre de travail avant VPS

| Ordre | Slice | Résultat attendu |
|---:|---|---|
| 1 | Génération documentaire contrôlée | Contrat des pièces, assembleur déterministe, versions append-only, complétude et absence de finance dans les contrats collaborateurs. |
| 2 | Cockpit patron | Dashboard, affectations, préparation, revues, finance confidentielle, bibliothèque entreprise et états d’action réunis dans React. |
| 3 | Préparation du dépôt | Paquet immutable, manifest, contrôles de complétude, verrouillage, empreinte et receipt interne sans prétendre à un dépôt externe. |
| 4 | Réconciliation finale | Suite complète, architecture, documentation, OpenAPI, secrets, couverture et parcours E2E. |
| 5 | Gate VPS | Docker, Caddy, ClamAV réel, EICAR, HTTPS, backups hors hôte, restauration isolée, supervision et rapport opérateur. |

## 7. Limites explicitement conservées

MinIO sans contrat de stockage stabilisé, Redis/sharding/tracing distribué spéculatifs, DAST/Semgrep déjà couverts par les contrôles existants et tests de charge nécessitant un environnement dédié ne sont pas ajoutés artificiellement. Les formats documentaires non pris en charge restent explicitement `UNSUPPORTED` plutôt que de produire une fausse analyse.

## 8. Références internes

| Document | Rôle |
|---|---|
| [`docs/PROJECT_STATE.md`](PROJECT_STATE.md) | Reprise technique, slices, migrations, validations et risques courants. |
| [`todo.md`](../todo.md) | Checklist durable des frontières restantes. |
| [`docs/reference/SMART_AO_V8_ARC_01_CONTRAT_ARBORESCENCE_MODULES.md`](reference/SMART_AO_V8_ARC_01_CONTRAT_ARBORESCENCE_MODULES.md) | Contrat d’arborescence, couches et dépendances. |
| [`docs/reference/SMART_AO_V8_PREPARATION_COMPLETENESS_01_CONTRAT.md`](reference/SMART_AO_V8_PREPARATION_COMPLETENESS_01_CONTRAT.md) | Contrat de readiness et génération technique contrôlée. |
| [`docs/AUDIT_REMEDIATION_MATRIX.md`](AUDIT_REMEDIATION_MATRIX.md) | Réconciliation du premier audit. |
| [`docs/AUDIT2_RELEVANCE_MATRIX.md`](AUDIT2_RELEVANCE_MATRIX.md) | Pertinence du second audit et corrections retenues. |
