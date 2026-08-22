# SMART_AO V8 — État réel des dépendances et intégrations

**Date de vérification :** 22 août 2026
**Branche vérifiée :** `docs/pricing-http-next-lot-28`
**HEAD de référence :** `9de9ab4` (slice knowledge/optimization en cours de validation)
**Objet :** distinguer les dépendances réellement installées et utilisées, les adaptateurs préparés, les services Docker configurés et les intégrations encore seulement prévues par la documentation.

## 1. Conclusion exécutive

SMART_AO V8 possède aujourd’hui un **socle logiciel codé et testable**, mais il ne possède pas encore toute la panoplie d’intégrations décrite dans la spécification d’architecture initiale. Cette spécification mélange volontairement quatre catégories différentes : dépendances du noyau, composants optionnels, composants futurs et exigences d’exploitation. Une mention dans `SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md` ne constitue donc pas une preuve d’installation ou de raccordement.

Le produit est aujourd’hui dans la situation suivante : le noyau métier, la sécurité tenant-scoped, PostgreSQL/Alembic, l’upload privé, le scan ClamAV, le parsing déterministe de base, la génération documentaire contrôlée, le pricing en prévisualisation, le cockpit initial, le paquet de dépôt et le webhook HMAC sont codés dans le dépôt. Un premier adaptateur **OR-Tools CP-SAT** et un socle **RAG local avec provider BGE optionnel, index JSONB et route de recherche protégée** viennent d’être ajoutés. En revanche, HiGHS/PuLP, l’activation opérationnelle du modèle BGE, pgvector/Qdrant, Docling/MinerU/OCR, MinIO/S3, les connecteurs BOAMP/URSSAF/INSEE, l’e-mail SMTP, Playwright E2E et les services Redis/n8n ne sont pas intégrés au runtime par défaut.

> **Verdict :** on peut commencer à greffer ces briques par slices contrôlés, mais on ne peut pas dire que tout est codé ni que le produit est opérationnel de bout en bout. Le premier raccordement doit porter sur une dépendance ayant un contrat métier et un critère de recette précis ; il ne faut pas installer toute la pile cible en bloc.

## 2. Ce que la documentation dit réellement

Le document [`SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md`](reference/SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md) est une **architecture cible**, pas un inventaire d’installation. Il classe `ortools`, `highspy`, `pulp`, `boto3`, Docling, les moteurs OCR, MinIO, `pgvector`, Qdrant et les providers cognitifs parmi des composants obligatoires, recommandés, optionnels ou conditionnels selon les sections. Il indique également que Redis, Celery, n8n, Qdrant et un serveur GPU/LLM local sont différés ou soumis à une preuve de besoin.

La roadmap [`ROADMAP_01_PLAN_GLOBAL_CODAGE.md`](ROADMAP_01_PLAN_GLOBAL_CODAGE.md) place le noyau documentaire et métier avant les assistants IA et le retrieval avancé. Elle réserve le sous-slice d’IA contrôlée à une étape ultérieure, avec un résultat candidat sourcé et validé humainement. La checklist [`todo.md`](../todo.md) ne comporte pas aujourd’hui de tâche ouverte d’installation générale de ces outils : elle conserve surtout la validation CI, le gate VPS et le raccordement à une URL HTTPS réelle.

La documentation doit donc être lue ainsi : **“Obligatoire” dans l’architecture signifie obligatoire pour la cible fonctionnelle qui en aura besoin, pas nécessairement déjà installé dans le commit actuel.** Ce document rend cette distinction explicite.

## 3. Dépendances réellement présentes aujourd’hui

| Domaine | Présent dans les manifests / runtime | État réel |
|---|---|---|
| API et contrats | FastAPI, Pydantic, pydantic-settings, Uvicorn, python-multipart | Déclarés et utilisés dans les routes et contrats HTTP. |
| Persistance | SQLAlchemy, psycopg, Alembic, PostgreSQL | Codés, migrés et testés ; PostgreSQL est le registre canonique. |
| Identité et sécurité | Argon2, PyJWT, python-magic, audit et policy applicative | Codés ; tenant, acteur, membership, CSRF et refresh cookie sont résolus côté serveur. |
| Documents de base | `pypdf`, `python-docx`, `openpyxl` | Utilisés par l’extraction déterministe et l’import pricing borné. |
| Antivirus | Adaptateur ClamAV TCP `INSTREAM`, quarantaine locale privée | Codé et fail-closed ; l’exécution réelle EICAR reste à prouver sur Docker. |
| Stockage courant | Adaptateurs locaux privés par filesystem, permissions et hash | Codé pour le sandbox et le premier déploiement contrôlé ; pas encore un stockage objet S3/MinIO. |
| Frontend | React, React DOM, TypeScript, Vite, Vitest, Testing Library | Cockpit initial et features métier présents ; 74 tests frontend ont passé localement. |
| Qualité Python | pytest, pytest-cov, Ruff, Bandit, detect-secrets, pip-audit | Présents et utilisés par les contrôles locaux/CI prévus. |

La preuve de ces éléments vient des manifests `pyproject.toml`, `uv.lock`, `web/package.json`, `web/pnpm-lock.yaml`, des imports du backend, des adaptateurs sous `backend/app/modules/*/infrastructure` et des fichiers Compose. La suite backend complète a produit 1 074 tests verts et 92,87 % de couverture lors de la dernière validation locale ; cette couverture ne prouve cependant pas l’existence des intégrations absentes.

## 4. Dépendances documentées mais non greffées au runtime

### 4.1 Calcul, optimisation et pricing avancé

| Brique | Présence actuelle | Ce qui manque avant raccordement |
|---|---|---|
| **Google OR-Tools** (`ortools`) | Présent dans `pyproject.toml` et `uv.lock` ; adaptateur CP-SAT isolé sous `modules/optimization` | Le contrat d’affectation entière, les bornes, le statut d’infaisabilité, le déterminisme et les tests sont codés. Il reste à relier le résultat à un vrai cas pricing/capacité, avec validation métier patronale, persistance d’un run et budget CPU/mémoire. |
| **HiGHS** (`highspy`) | Absent des manifests et du code | Un cas d’optimisation linéaire/mixte réel, une comparaison avec OR-Tools, des budgets CPU/mémoire et un résultat reproductible. |
| **PuLP** (`pulp`) | Absent des manifests et du code | Une nécessité de compatibilité démontrée ; ce n’est pas une source de vérité et ne doit pas être ajouté par simple anticipation. |
| `Decimal` | Présent via la bibliothèque standard et utilisé pour les montants | Le calcul financier de base est codé ; l’optimisation combinatoire n’est pas encore un service métier. |

La prévisualisation DPGF/BPU/Excel et la persistance de lots `PREVIEWED` ne constituent pas encore un moteur de chiffrage optimisé. Le produit peut importer, normaliser, contrôler et présenter des lignes dans son périmètre actuel ; il ne possède pas encore l’affectation optimisée de ressources, la simulation avancée ou la génération d’un prix officiel par solveur.

### 4.2 RAG, embeddings et recherche sémantique

| Brique | Présence actuelle | Verdict |
|---|---|---|
| RAG applicatif | Pipeline local présent : fragments DCE admis → BGE provider → registre JSONB append-only → retrieval case-scoped → route HTTP avec citation bornée | **Partiel et désactivé par défaut** : migration `0050`, service, route et commande one-shot existent ; l’indexation doit encore être déclenchée sur un corpus DCE réel et benchmarkée. |
| Modèle **BGE** éventuel | Extra Python `rag`, provider `BAAI/bge-m3`, chargement paresseux ; image Docker installable avec `SMART_AO_INSTALL_RAG=1` | **Préparé et testable avec modèle simulé** ; les poids doivent être préchargés et validés sur l’environnement cible avant activation. |
| `pgvector` | Toujours absent ; le premier bridge persistant stocke les vecteurs en JSONB et calcule la similarité côté Python | Non intégré ; JSONB est un socle de démarrage, pas la solution de performance finale pour un corpus volumineux. |
| Qdrant | Mentionné comme option conditionnelle, absent du Compose et du code | Non intégré, correctement différé. |
| Retrieval exact/structuré | Les données DCE, fragments, exigences et preuves sont persistées de façon structurée | Partiellement disponible comme base de recherche, mais ce n’est pas un RAG sémantique. |

Le contrat initial de retrieval est désormais figé : filtre tenant/affaire/version, provenance obligatoire, score borné, `top_k` borné, exclusion des chunks `FINANCIAL_PRIVATE`, idempotence par fragment/modèle/hash et échec fermé si le provider BGE est indisponible. La migration `0050`, le registre JSONB, la route protégée et le job one-shot existent ; il faut encore mesurer le gain sur un corpus Golden DCE, automatiser le déclenchement après admission d’une version et choisir entre JSONB optimisé, `pgvector` ou Qdrant selon les résultats.

### 4.3 Parsing avancé et OCR

| Brique | Présence actuelle | Verdict |
|---|---|---|
| PyMuPDF / `fitz` | Non présent dans le manifest actuel | Non intégré ; l’extraction PDF utilise `pypdf`. |
| `pdfplumber` | Absent des manifests et du code | Non intégré. |
| `pypdfium2` | Absent | Non intégré. |
| **Docling** | Mentionné dans l’architecture cible, absent de `pyproject.toml`, `uv.lock`, Dockerfile et imports | Non greffé. |
| **MinerU** | Prévu comme exception lourde CPU/GPU, absent du runtime | Non greffé. |
| Tesseract / OCR français | Aucun binaire ou binding présent dans le dépôt et aucune étape Compose | Non greffé. |
| OCR cloud premium | Aucun provider, secret, adaptateur ou politique d’envoi configuré | Non greffé. |
| Extraction déterministe actuelle | `pypdf`, `python-docx`, `openpyxl`, limites anti-bombes et fragments sourcés | Codée dans un périmètre volontairement limité ; pas une couverture de tous les DCE scannés. |

Le pipeline actuel sait traiter certains PDF, DOCX, XLSX et TXT de manière bornée et déterministe. Il ne sait pas encore assurer la lecture robuste de scans, plans, tableaux complexes et documents nécessitant OCR. L’ajout de Docling ou MinerU n’est donc pas un simple `pip install` : il nécessite une image worker dédiée, des plafonds CPU/RAM, un corpus de tests et une politique de revue humaine.

### 4.4 Stockage objet et infrastructure de recherche

| Brique | Présence actuelle | Verdict |
|---|---|---|
| MinIO | Mentionné dans l’architecture initiale, absent de `docker-compose.yml` et `ops/docker-compose.preprod.yml` | Non intégré. |
| S3 / `boto3` | Absent des manifests et du code | Non intégré. |
| Stockage local privé | Adaptateurs locaux de quarantaine et de documents générés, anti-traversal, permissions et hash | Implémenté comme solution courante contrôlée. |
| PostgreSQL full-text / pgvector | Tables métier et recherche structurée présentes, mais pas de pile vectorielle activée | Partiel : source de vérité présente, recherche sémantique absente. |

Le passage à MinIO/S3 est possible, mais doit être traité comme un slice d’infrastructure : contrat de clé opaque, tenant-scoping, chiffrement, URL temporaires, migration des objets, backup/restore et tests de non-fuite. Tant que ce contrat n’est pas décidé, la documentation a raison de ne pas ajouter MinIO artificiellement.

### 4.5 Services externes métier et automatisation

| Brique | Présence actuelle | Verdict |
|---|---|---|
| Provider LLM/cognitif externe | Aucun SDK, endpoint, secret ou adaptateur | Absent ; aucune donnée DCE n’est envoyée à une IA. |
| BOAMP | Mention documentaire seulement | Aucun connecteur d’import ou de déduplication. |
| URSSAF / INSEE | Mention documentaire seulement | Aucun connecteur de vérification ou de référentiel. |
| SMTP / `aiosmtplib` | Absent du manifest et du code | Pas d’e-mail transactionnel intégré. |
| ICS / `icalendar` | Absent | Pas d’export calendrier intégré. |
| n8n | Documenté comme intégration future | Aucun workflow connecté. |
| Webhook d’export | Worker Python et signature HMAC du payload | La capacité technique sortante est codée ; aucune destination réelle n’est configurée ou validée dans ce sandbox. |
| Redis / Celery / APScheduler | Absents, explicitement différés ou optionnels | Aucun besoin démontré pour le noyau mono-VPS actuel. |

Le webhook HMAC ne doit pas être confondu avec un connecteur métier complet : il sécurise une notification sortante lorsqu’une URL et un secret sont configurés, mais il ne réalise ni dépôt électronique, ni accusé juridiquement vérifié, ni synchronisation avec un portail externe.

## 5. Frontend et tests navigateur

Le frontend actuel est volontairement plus petit que la cible décrite dans l’architecture. Il utilise React, TypeScript, Vite, Vitest et Testing Library. Il ne déclare pas React Router, TanStack Query, Zustand, `react-pdf`, Recharts/ECharts ou Playwright dans son manifest actuel. La navigation du cockpit est aujourd’hui portée par l’application existante et ses features extraites, mais elle ne constitue pas encore une implémentation complète de toutes les zones fonctionnelles prévues dans le cahier patron.

Les tests composants et hooks sont présents et passent. En revanche, **Playwright n’est pas encore installé ni exécuté** : le login, le cookie Secure, le refresh sur HTTPS, le parcours patron/collaborateur et la protection d’une route doivent encore être validés dans un vrai navigateur contre une URL HTTPS réelle.

## 6. Ce qui peut être greffé maintenant

Il est techniquement possible de commencer un raccordement maintenant, à condition de choisir une seule brique et de respecter les frontières du projet.

| Priorité | Raccordement | Pourquoi maintenant / condition de sortie |
|---:|---|---|
| 1 | **OR-Tools ou HiGHS pour un cas d’optimisation concret** | Possible après figer le contrat pricing/capacité, les données autorisées, le solveur choisi, les budgets et les tests de reproductibilité. Ne pas installer les trois solveurs en même temps. |
| 2 | **Docling ou OCR local** | Possible après constituer un corpus DCE anonymisé, mesurer CPU/RAM, séparer le worker documentaire et définir le statut “candidat à revue humaine”. |
| 3 | **RAG local avec pgvector** | Possible après définir retrieval, citations, tenant filter, version d’index et benchmark Golden DCE. Il est préférable de commencer par pgvector plutôt que Qdrant si le besoin n’est pas encore mesuré. |
| 4 | **MinIO/S3** | Possible lorsque le contrat de stockage objet et la stratégie de migration/backup sont validés. C’est le raccordement le plus important pour une exploitation documentaire durable, mais il touche l’infrastructure et la restauration. |
| 5 | **Connecteurs BOAMP/URSSAF/INSEE/SMTP** | Possible séparément, avec secrets hors Git, idempotence, limites d’usage, audit et tests sandbox. Aucun ne doit être ajouté comme dépendance obligatoire du cœur sans cas métier validé. |
| 6 | **Playwright E2E** | Peut être ajouté dès maintenant comme outil de preuve, mais il ne remplacera pas l’absence de VPS/Docker et d’URL HTTPS réelle. |

## 7. Ce qui empêche aujourd’hui de dire « tout est codé »

Il reste des manques fonctionnels et opérationnels importants : l’OCR et le parsing avancé, la mise en production du modèle BGE et l’indexation automatique du RAG, le passage éventuel à pgvector/Qdrant, le raccordement métier complet d’OR-Tools, le stockage objet MinIO/S3, les connecteurs de veille et de vérification, les notifications e-mail/calendrier, les tests navigateur Playwright, la preuve Docker/ClamAV/HTTPS sur une machine réelle, la sauvegarde hors hôte et la restauration isolée. Le dépôt électronique externe lui-même reste volontairement non effectué et ne doit jamais être simulé comme réussi.

Ces manques ne signifient pas que le code existant est un simple squelette. Ils signifient que **le noyau sécurisé et plusieurs slices métier sont codés, tandis que la plateforme complète décrite par la vision cible ne l’est pas encore**. Une couverture de tests élevée ne transforme pas une dépendance absente en fonctionnalité disponible.

## 8. Séquence recommandée

La séquence raisonnable est la suivante :

1. Obtenir une CI GitHub qui exécute réellement ses étapes et valider la PR #49 ; le dernier run connu a échoué avant toute étape faute de runner.
2. Valider localement la migration 0050, le retrieval persistant et le contrat HTTP avec un corpus Golden DCE non sensible ; cette validation de contrat est désormais faite, mais pas encore le benchmark métier Golden DCE.
3. Précharger et vérifier BGE-M3 sur une machine dédiée, puis exécuter le job one-shot d’indexation sur une version DCE admise.
4. Raccorder l’affectation OR-Tools à un cas pricing/capacité réel, avec validation patronale et mesure du temps de résolution.
5. Comparer le bridge JSONB à pgvector seulement après le benchmark ; ne pas introduire Qdrant sans besoin mesuré.
6. Ajouter ensuite OCR/Docling, MinIO/S3 et les connecteurs externes un par un, derrière des ports et des adaptateurs, avec secrets, budgets, rate limits, audit et possibilité de désactivation.

## Références locales

- [`SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md`](reference/SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md), sections 4 à 17 : architecture cible et classification des dépendances.
- [`ROADMAP_01_PLAN_GLOBAL_CODAGE.md`](ROADMAP_01_PLAN_GLOBAL_CODAGE.md), slices S04 à S12 : ordre de construction et IA contrôlée.
- [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md) : état métier et limites déclarées.
- [`todo.md`](../todo.md) : frontières opérationnelles réellement restantes.
- [`pyproject.toml`](../pyproject.toml) et [`uv.lock`](../uv.lock) : dépendances Python effectivement déclarées et résolues.
- [`web/package.json`](../web/package.json) et [`web/pnpm-lock.yaml`](../web/pnpm-lock.yaml) : dépendances frontend effectivement déclarées et verrouillées.
- [`ops/docker-compose.preprod.yml`](../ops/docker-compose.preprod.yml) : services réellement préparés pour la préproduction.
- [`backend/app/modules/dce/application/extraction.py`](../backend/app/modules/dce/application/extraction.py) : extraction déterministe actuellement implémentée.
- [`backend/app/modules/dce/infrastructure/quarantine.py`](../backend/app/modules/dce/infrastructure/quarantine.py) : stockage local privé et ClamAV actuellement implémentés.
- [`backend/app/modules/preparation/infrastructure/document_storage.py`](../backend/app/modules/preparation/infrastructure/document_storage.py) : stockage local des documents générés.
