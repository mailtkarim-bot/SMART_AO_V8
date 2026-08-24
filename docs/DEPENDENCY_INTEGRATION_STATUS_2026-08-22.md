# SMART_AO V8 — État réel des dépendances et intégrations

**Date de vérification :** 23 août 2026
**Branche vérifiée :** `docs/pricing-http-next-lot-28`
**Dernier commit fonctionnel de référence :** `7d91b0a` (remédiation ORM métier, migration append-only pricing `0055`, durcissement webhook SSRF/DNS et codec JWT avec `kid`, après le lot DCE/RAG/benchmark).
**Objet :** distinguer les dépendances réellement installées et utilisées, les adaptateurs préparés, les services Docker configurés et les intégrations encore seulement prévues par la documentation.

## 1. Conclusion exécutive

SMART_AO V8 possède aujourd’hui un **socle logiciel codé et testable**, mais il ne possède pas encore toute la panoplie d’intégrations décrite dans la spécification d’architecture initiale. Cette spécification mélange volontairement quatre catégories différentes : dépendances du noyau, composants optionnels, composants futurs et exigences d’exploitation. Une mention dans `SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md` ne constitue donc pas une preuve d’installation ou de raccordement.

Le produit est aujourd’hui dans la situation suivante : le noyau métier, la sécurité tenant-scoped, PostgreSQL/Alembic, l’upload privé, le scan ClamAV, le parsing déterministe de base, la génération documentaire contrôlée, le pricing en prévisualisation, le cockpit initial, le paquet de dépôt et le webhook HMAC sont codés dans le dépôt. Un premier adaptateur **OR-Tools CP-SAT**, un socle **RAG local avec provider BGE optionnel**, le parsing avancé Docling/PyMuPDF et un stockage objet privé S3-compatible viennent d’être ajoutés. L’antenne RAG one-shot est maintenant sécurisée par un opt-in d’indexation séparé et un wrapper opérateur tenant/Case/version-scoped. Un adaptateur INSEE Sirene read-only est maintenant câblé derrière un port enterprise et désactivé par défaut. En revanche, HiGHS/PuLP, l’activation opérationnelle du modèle BGE, pgvector/Qdrant, la recette Docling/MinerU/OCR, la recette MinIO/S3, BOAMP/URSSAF, l’e-mail SMTP, Playwright E2E et les services Redis/n8n ne sont pas intégrés au runtime par défaut.

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
| Stockage courant | Adaptateurs locaux privés par filesystem, permissions et hash ; adaptateur S3-compatible optionnel | Local par défaut ; S3/MinIO est greffé derrière `GeneratedDocumentStorage`, mais la recette Docker/bucket/backup réelle reste ouverte. |
| Frontend | React, React DOM, TypeScript, Vite, Vitest, Testing Library | Cockpit BOAMP, lecture DCE/RAG et features métier présents ; 93 tests frontend et le build Vite passent localement. |
| Qualité Python | pytest, pytest-cov, Ruff, Bandit, detect-secrets, pip-audit | Présents et utilisés par les contrôles locaux/CI prévus. |

La preuve de ces éléments vient des manifests `pyproject.toml`, `uv.lock`, `web/package.json`, `web/pnpm-lock.yaml`, des imports du backend, des adaptateurs sous `backend/app/modules/*/infrastructure` et des fichiers Compose. La validation locale actuelle exécute sans PostgreSQL **862 tests non-DB avec succès** ; **458 tests DB** sont correctement identifiés mais nécessitent le service PostgreSQL. La couverture complète hors DB est mesurée à **67,45 %**, sous le seuil strict de 85,50 % ; elle reste un travail de qualité ouvert et ne doit pas être masquée par des exclusions artificielles.

## 4. Dépendances documentées mais non greffées au runtime

### 4.1 Calcul, optimisation et pricing avancé

| Brique | Présence actuelle | Ce qui manque avant raccordement |
|---|---|---|
| **Google OR-Tools** (`ortools`) | Présent dans `pyproject.toml` et `uv.lock` ; adaptateur CP-SAT, service `CaseCapacityPlanningService`, service de run, modèle et repository isolés sous `modules/optimization` | Le contrat d’affectation entière, les bornes, le statut d’infaisibilité, le déterminisme, la vérification tenant/Case, la révision optimiste, l’idempotence, le snapshot technique non financier, le hash SHA-256 et l’événement d’audit sont codés. Le repository utilise `RETURNING`, distingue `run_id`, `command_id` et `idempotency_key`, et rejette les collisions multiples. La migration `0051` est validée offline ; les six scénarios PostgreSQL online et la mesure sur un cas métier réel restent à exécuter. Il n’existe toujours pas de prix officiel, de décision patronale ni de route HTTP OR-Tools. |
| **HiGHS** (`highspy`) | Absent des manifests et du code | Un cas d’optimisation linéaire/mixte réel, une comparaison avec OR-Tools, des budgets CPU/mémoire et un résultat reproductible. |
| **PuLP** (`pulp`) | Absent des manifests et du code | Une nécessité de compatibilité démontrée ; ce n’est pas une source de vérité et ne doit pas être ajouté par simple anticipation. |
| `Decimal` | Présent via la bibliothèque standard et utilisé pour les montants | Le calcul financier de base est codé ; l’optimisation combinatoire n’est pas encore un service métier. |

La prévisualisation DPGF/BPU/Excel et la persistance de lots `PREVIEWED` ne constituent pas encore un moteur de chiffrage optimisé. Le produit peut importer, normaliser, contrôler et présenter des lignes dans son périmètre actuel ; il ne possède pas encore l’affectation optimisée de ressources, la simulation avancée ou la génération d’un prix officiel par solveur.

### 4.2 RAG, embeddings et recherche sémantique

| Brique | Présence actuelle | Verdict |
|---|---|---|
| RAG applicatif | Pipeline local présent : fragments DCE admis → BGE provider → registre JSONB append-only → retrieval case-scoped → route HTTP avec citation bornée ; worker one-shot durci par `SMART_AO_RAG_ENABLED` + `SMART_AO_RAG_INDEXING_ENABLED` et wrapper opérateur UUID-scoped | **Partiel et désactivé par défaut** : migration `0050`, service, route, commande one-shot, antenne Ops, client frontend, panel de recherche sourcée et validateur de manifeste benchmark existent ; l’indexation doit encore être exécutée sur un corpus DCE réel et benchmarkée. Aucun déclenchement automatique après admission n’est activé. |
| Modèle **BGE** éventuel | Extra Python `rag`, provider `BAAI/bge-m3`, chargement paresseux ; image Docker installable avec `SMART_AO_INSTALL_RAG=1` | **Préparé et testable avec modèle simulé** ; les poids doivent être préchargés et validés sur l’environnement cible avant activation. |
| `pgvector` | Toujours absent ; le premier bridge persistant stocke les vecteurs en JSONB et calcule la similarité côté Python | Non intégré ; JSONB est un socle de démarrage, pas la solution de performance finale pour un corpus volumineux. |
| Qdrant | Mentionné comme option conditionnelle, absent du Compose et du code | Non intégré, correctement différé. |
| Retrieval exact/structuré | Les données DCE, fragments, exigences et preuves sont persistées de façon structurée | Partiellement disponible comme base de recherche, mais ce n’est pas un RAG sémantique. |

Le contrat initial de retrieval est désormais figé : filtre tenant/affaire/version, provenance obligatoire, score borné, `top_k` borné, exclusion des chunks `FINANCIAL_PRIVATE`, idempotence par fragment/modèle/hash et échec fermé si le provider BGE est indisponible. La migration `0050`, le registre JSONB, la route protégée, le job one-shot et le wrapper opérateur existent ; le worker d’indexation exige maintenant un opt-in séparé et conserve le chargement local par défaut. Il faut encore mesurer le gain sur un corpus Golden DCE, décider si un déclenchement automatique après admission est justifié et choisir entre JSONB optimisé, `pgvector` ou Qdrant selon les résultats.

### 4.3 Parsing avancé et OCR

| Brique | Présence actuelle | Verdict |
|---|---|---|
| PyMuPDF / `fitz` | Extra `document-advanced` verrouillé ; adaptateur PDF par blocs avec page/bbox et smoke test réel validé | **Greffé derrière un port optionnel** ; non activé par défaut, et le fallback `pypdf` reste inchangé. |
| `pdfplumber` | Absent des manifests et du code | Non intégré. |
| `pypdfium2` | Absent | Non intégré. |
| **Docling** | Extra `document-advanced` verrouillé ; adaptateur `DocumentConverter` + export Markdown, factory d’activation et test simulé de provenance | **Greffé derrière un port optionnel** ; l’image peut l’installer avec `SMART_AO_INSTALL_DOCUMENT_ADVANCED=1`, mais les modèles/recettes doivent être validés avant activation. |
| **MinerU** | Toujours absent du manifest et du runtime | Différé correctement : aucun besoin démontré après le premier slice Docling/PyMuPDF ; comparaison seulement sur un corpus Golden DCE. |
| Tesseract / OCR français | Docling annonce un support OCR, mais aucun binaire Tesseract autonome ni recette OCR n’est encore activé dans Compose | **Préparé indirectement via Docling, non validé opérationnellement** ; il faut un corpus de scans, budgets CPU/RAM et revue humaine. |
| OCR cloud premium | Aucun provider, secret, adaptateur ou politique d’envoi configuré | Non greffé. |
| Extraction déterministe actuelle | `pypdf`, `python-docx`, `openpyxl`, limites anti-bombes et fragments sourcés ; fallback conservé même avec l’extra avancé | Codée et non régressée ; les adaptateurs avancés restent candidats à revue humaine. |

Le pipeline actuel traite certains PDF, DOCX, XLSX et TXT de manière bornée et déterministe. Le port avancé peut utiliser PyMuPDF pour des blocs PDF localisés et Docling pour des formats complexes ; la factory est désormais appelée par le worker one-shot `app.workers.dce_extraction`, déclenchable par le wrapper `ops/run-dce-extraction-preprod.sh`. Cela ne constitue pas encore une preuve de lecture robuste de scans/plans/tableaux ni un OCR métier validé. L’image peut installer l’extra séparément ; l’activation nécessite des plafonds CPU/RAM, un corpus Golden DCE, une exécution hors requête HTTP et une politique de revue humaine.

### 4.4 Stockage objet et infrastructure de recherche

| Brique | Présence actuelle | Verdict |
|---|---|---|
| MinIO | Endpoint S3-compatible supporté par l’adaptateur privé ; aucun serveur MinIO n’est ajouté au Compose de production | **Préparé et greffé derrière un port**, mais recette Docker MinIO encore ouverte. |
| S3 / `boto3` | Extra `object-storage` verrouillé ; adaptateur privé avec `IfNoneMatch="*"`, hash SHA-256, `head`, lecture bornée, suppression serveur et chiffrement SSE configurable ; script opérateur `scripts/verify_object_storage.py` avec confirmation explicite | **Greffé et sélectionnable par AppRuntime** avec `SMART_AO_OBJECT_STORAGE_ENABLED=1`; bucket, credentials, permissions, lifecycle, restauration et recette réelle restent à valider. Le script n’écrit rien sans `--confirm-write` et n’affiche ni endpoint, ni bucket, ni secret. |
| Stockage local privé | Adaptateurs locaux de quarantaine et de documents générés, anti-traversal, permissions et hash ; fallback AppRuntime par défaut | Implémenté et conservé comme solution courante contrôlée. |
| PostgreSQL full-text / pgvector | Tables métier et recherche structurée présentes, mais pas de pile vectorielle activée | Partiel : source de vérité présente, recherche sémantique absente. |

Le passage à MinIO/S3 est maintenant câblé derrière un slice d’infrastructure : contrat de clé privé, écriture conditionnelle non-écrasante, hash, chiffrement configurable et lecture serveur bornée. Il reste à exercer sur Docker réel le bucket privé, les credentials, les permissions minimales, le lifecycle, la migration des objets, le backup/restore et les tests de non-fuite. Aucun serveur MinIO n’a été ajouté artificiellement au Compose de production.

### 4.5 Services externes métier et automatisation

| Brique | Présence actuelle | Verdict |
|---|---|---|
| Provider LLM/cognitif externe | Aucun SDK, endpoint, secret ou adaptateur | Absent ; aucune donnée DCE n’est envoyée à une IA. |
| BOAMP | Extra `connectors` optionnel ; port `PublicNoticeSearchPort`, adaptateur Explore API 2.1 read-only, ingestion staging bornée, persistence `0053`, score `BOAMP_PUBLIC_V1`, lecture/qualification patronale HTTP `0054` et outbox vers port bus externe | **Greffé derrière des ports et désactivé par défaut pour les appels externes** ; observations et qualifications sont tenant-scoped/append-only, sans retour des champs riches `donnees`/`gestion`. La recette PostgreSQL online, la recette réseau et le bus fournisseur réel restent à confirmer. |
| Profil de veille opportunité | Bounded context `opportunity` ; `WatchProfileCriteria` pur, commandes fermées, snapshot/hash canonique, models `opportunity_watch_profiles`/`opportunity_watch_profile_versions`, dispatcher/outbox, migration `0052` et routes patronales create/version/read avec capabilities `opportunity.profile.read/write` | **Persistence et HTTP codés, recette PostgreSQL online restante** ; les versions sont append-only, les projections sont tenant-scoped et l’ID initial est dérivé serveur. BOAMP est ingérable en staging puis persistable via `0053`, avec scoring public `BOAMP_PUBLIC_V1`, lecture patronale, qualification append-only via `0054`, sans conversion Case automatique. |
| URSSAF / INSEE | INSEE : extra `connectors` optionnel, port `CompanyRegistryPort`, adaptateur Sirene read-only, route authentifiée `GET /api/v1/patron/enterprise/registry/{siren}`, capability `enterprise.registry.read` et composition AppRuntime ; URSSAF toujours absent | INSEE est **câblé derrière un port et une lecture authentifiée**, activable seulement avec `SMART_AO_INSEE_ENABLED=1` et token runtime ; aucune requête réelle ni persistance automatique n’a été validée. URSSAF reste non intégré. |
| SMTP / `aiosmtplib` | Extra `notifications` optionnel verrouillé ; port `SubmissionExportNotificationPort`, adaptateur async TLS/STARTTLS, topic outbox dédié `submission.package.exported.smtp`, worker `app.workers.submission_export_smtp` avec lease/retry/idempotence et démarrage Compose explicite | **Worker greffé mais désactivé par défaut** ; payload SMTP limité à `submission_package_id`/`EXPORT_READY`, distinct du webhook et sans document, hash d’archive ou montant. Aucun serveur SMTP réel, compte, accusé de remise ou délivrabilité n’a été recetté. |
| ICS / `icalendar` | Extra `calendar` optionnel verrouillé ; port `SubmissionDeadlineCalendarPort`, renderer RFC 5545 local, dates UTC et activation AppRuntime explicite | **Export de fichier greffé mais désactivé par défaut** ; le renderer n’importe pas `icalendar` et le test passe avec l’extra ; aucun agenda distant, CalDAV, OAuth ou accusé de synchronisation n’est intégré. |
| n8n | Documenté comme intégration future | Aucun workflow connecté. |
| Webhook d’export | Worker Python et signature HMAC du payload | La capacité sortante est codée ; HTTPS est obligatoire, la résolution DNS est vérifiée et les adresses privées/réservées sont refusées. Aucune destination réelle n’est configurée ou validée dans ce sandbox. |
| Signature HTTP | DTOs fermés, capabilities patronales dédiées, routes `POST` demande/callback et `GET` lecture, provider/secret runtime, callback HMAC sur corps brut, delivery idempotente, reader tenant-scoped, panneau React de suivi et `SignatureProviderTestAdapter` local | **Backend et suivi frontend greffés mais désactivés tant que provider/secret manquent**. Le provider de test produit seulement un callback `TEST_PROVIDER` déterministe en mémoire pour les tests HMAC/replay ; aucun fournisseur réel, certificat, signature qualifiée, dépôt externe ou accusé de remise n’est intégré. |
| Redis / Celery / APScheduler | Absents, explicitement différés ou optionnels | Aucun besoin démontré pour le noyau mono-VPS actuel. |

Le webhook HMAC, le worker SMTP et le callback HMAC de signature ne doivent pas être confondus avec un connecteur métier complet : ils sécurisent une capacité de notification ou de réception lorsqu’une destination et un secret sont configurés, mais ils ne réalisent ni signature qualifiée, ni dépôt électronique, ni accusé juridiquement vérifié, ni synchronisation avec un portail externe. `SignatureProviderTestAdapter` ajoute uniquement une enveloppe de test sans transport et ne change jamais `external_submission: NOT_PERFORMED`.

## 5. Frontend et tests navigateur

Le frontend actuel est volontairement plus petit que la cible décrite dans l’architecture. Il utilise React, TypeScript, Vite, Vitest et Testing Library. Il ne déclare pas React Router, TanStack Query, Zustand, `react-pdf`, Recharts/ECharts ou Playwright dans son manifest actuel. La navigation du cockpit est aujourd’hui portée par l’application existante et ses features extraites, mais elle ne constitue pas encore une implémentation complète de toutes les zones fonctionnelles prévues dans le cahier patron.

Les tests composants et hooks sont présents et passent. En revanche, **Playwright n’est pas encore installé ni exécuté** : le login, le cookie Secure, le refresh sur HTTPS, le parcours patron/collaborateur et la protection d’une route doivent encore être validés dans un vrai navigateur contre une URL HTTPS réelle.

## 6. Ce qui peut être greffé maintenant

Il est techniquement possible de commencer un raccordement maintenant, à condition de choisir une seule brique et de respecter les frontières du projet.

| Priorité | Raccordement | Pourquoi maintenant / condition de sortie |
|---:|---|---|
| 1 | **OR-Tools ou HiGHS pour un cas d’optimisation concret** | Le raccordement OR-Tools case-scoped, la persistence/audit append-only et la migration `0051` sont codés sans données financières. La validation PostgreSQL online, un input métier réel, le budget CPU/mémoire et la valeur sur un cas pricing restent à prouver avant toute exposition HTTP. Ne pas installer les trois solveurs en même temps. |
| 2 | **Docling ou OCR local** | Le worker documentaire one-shot et la factory optionnelle sont maintenant câblés ; il faut encore constituer un corpus DCE anonymisé, mesurer CPU/RAM, tester les scans/OCR et définir le statut “candidat à revue humaine”. |
| 3 | **RAG local avec pgvector** | Le contrat BGE/JSONB et l’antenne one-shot sont codés. Une migration pgvector ne sera envisagée qu’après corpus Golden, mesure de précision/latence/taille et comparaison avec le bridge JSONB actuel. |
| 4 | **MinIO/S3** | Adaptateur S3-compatible et composition AppRuntime désormais codés ; reste la recette Docker réelle, l’exécution contrôlée de `scripts/verify_object_storage.py`, la stratégie de migration/backup et la restauration isolée. |
| 5 | **Connecteurs BOAMP/URSSAF** | BOAMP possède un adaptateur HTTPS read-only, un script staging borné, une persistence `0053`, un scoring explicable, une lecture/qualification patronale HTTP, une qualification append-only `0054` et un worker outbox vers port bus ; les recettes réseau/PostgreSQL/bus réels restent à faire. INSEE read-only, SMTP optionnel et export ICS local sont également des premiers slices ; URSSAF reste à traiter séparément avec secrets hors Git, idempotence, limites d’usage, audit et tests sandbox. |
| 6 | **Playwright E2E** | Peut être ajouté dès maintenant comme outil de preuve, mais il ne remplacera pas l’absence de VPS/Docker et d’URL HTTPS réelle. |

## 7. Vérification complémentaire du rapport d’audit

Le déplacement des modèles métier et le trigger append-only `pricing_scenarios` sont maintenant codés dans `7d91b0a`. La remarque ICS du rapport est un faux positif : le test utilise le renderer local RFC 5545 et passe avec l’extra `calendar`. La remarque OR-Tools n’est pas un échec fonctionnel démontré ; les tests DB échouent ici par `connection refused` avant leur exécution. Le MFA step-up existe au niveau de la policy mais son obligation sur chaque action sensible reste à vérifier séparément. La rotation JWT par `kid` est disponible dans le codec, sans clés historiques configurées dans cet environnement. Les preuves Docker/PostgreSQL/VPS, fournisseur bus, corpus BGE et runners CI restent externes.

## 8. Ce qui empêche aujourd’hui de dire « tout est codé »

Il reste des manques fonctionnels et opérationnels importants : la validation OCR et parsing avancé sur scans, la mise en production du modèle BGE et l’indexation automatique du RAG, le passage éventuel à pgvector/Qdrant, le raccordement métier complet d’OR-Tools, la recette réelle du stockage objet S3/MinIO, la délivrabilité SMTP réelle et la preuve de remise du process outbox, le connecteur URSSAF et les recettes réseau stables des lectures INSEE/BOAMP authentifiées, la synchronisation d’agenda distante, les tests navigateur Playwright, la preuve Docker/ClamAV/HTTPS sur une machine réelle, la sauvegarde hors hôte et la restauration isolée. Le dépôt électronique externe lui-même reste volontairement non effectué et ne doit jamais être simulé comme réussi.

Ces manques ne signifient pas que le code existant est un simple squelette. Ils signifient que **le noyau sécurisé et plusieurs slices métier sont codés, tandis que la plateforme complète décrite par la vision cible ne l’est pas encore**. Une couverture de tests élevée ne transforme pas une dépendance absente en fonctionnalité disponible.

## 9. Séquence recommandée

La séquence raisonnable est la suivante :

1. Obtenir une CI GitHub qui exécute réellement ses étapes et valider la PR #49 ; les runs `32636557842` ont échoué avant toute étape faute de runner.
2. Appliquer la migration OR-Tools `0051` et exécuter les tests de persistence/append-only contre PostgreSQL réel dès qu’un service est disponible ; aucune exécution online n’est revendiquée dans le sandbox.
3. Raccorder le service OR-Tools case-scoped à un cas capacité réel non financier, avec validation d’input, mesure du temps de résolution et revue de l’utilité métier ; ne pas en déduire un prix ou une décision.
4. Utiliser `SignatureProviderTestAdapter` uniquement pour tests HMAC/replay locaux ; définir séparément un contrat fournisseur réel avant tout SDK, credential, certificat ou dépôt externe.
5. Précharger et vérifier BGE-M3 sur une machine dédiée, puis exécuter le job one-shot d’indexation sur une version DCE admise.
6. Comparer le bridge JSONB à pgvector seulement après le benchmark ; ne pas introduire Qdrant sans besoin mesuré.
7. Recetter sur Docker réel le parsing avancé et S3/MinIO ; exécuter ensuite une recette INSEE avec token opérateur et données non sensibles, puis ajouter BOAMP/URSSAF/SMTP un par un derrière des ports et adaptateurs, avec secrets, budgets, rate limits, audit et possibilité de désactivation.

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

## 10. Mise à jour BOAMP HTTP et bus externe — 23 août 2026

Le slice BOAMP est désormais greffé jusqu’à la frontière HTTP et outbox, sans prétendre à une intégration fournisseur réelle. Le routeur patronal `GET /api/v1/patron/boamp-opportunities` expose une projection minimale tenant-scoped ; `POST /api/v1/patron/boamp-opportunities/{observation_id}/qualification` accepte seulement les décisions et motifs fermés du contrat humain. Les capacités `opportunity.observation.read` et `opportunity.observation.qualify` restent réservées au patron, et l’acteur comme le tenant sont résolus côté serveur.

Le worker `app.workers.opportunity_event_bus` ne consomme que `opportunity.boamp.ingestion.recorded` et `opportunity.boamp.qualification.recorded`. Il réclame les messages avec `FOR UPDATE SKIP LOCKED`, pose une lease, applique un payload exact limité à quatre identifiants/décisions, puis marque `PUBLISHED` uniquement après un accusé `2xx` du port `ExternalEventBusPort`. L’activation runtime exige désormais `SMART_AO_EXTERNAL_EVENT_BUS_ENABLED=1`, une URL HTTPS et un token ; en mode par défaut, le worker quitte proprement sans ouvrir de connexion. Le service Compose préproduction est derrière le profil `external-bus`. Aucun SDK Kafka/RabbitMQ, endpoint inventé ou appel réseau réel n’est inclus. En l’absence de configuration, la notification reste en retry et n’est pas déclarée publiée. Le contrat opérateur complet est dans `docs/EXTERNAL_EVENT_BUS_CONTRACT.md`.

La recette `scripts/recipe_boamp_postgres.py` est une antenne opérateur : `--apply` lance Alembic `head`, puis la vérification exige la révision `20260823_0054`, les quatre tables BOAMP et les quatre triggers append-only avant les tests de persistence. Le nouveau test DB qualification couvre création, rejeu, unicité event/outbox et mutation interdite. Le lanceur local `scripts/start_local_postgres.sh` utilise l’image PostgreSQL 16 digest-pinnée, un volume isolé et le port hôte `5433`; ses tests CLI couvrent l’aide, les validations et l’absence de fuite du mot de passe. La sortie est un verdict JSON sans URL ni secret. Dans le sandbox, `--help`, les tests CLI, les tests applicatifs et la collecte du test DB passent ; l’exécution online reste **BLOCKED** par l’absence de daemon Docker/PostgreSQL local. La recette réseau BOAMP, le bus réel et la preuve de migration online doivent être exécutés sur un environnement contrôlé disposant des services et credentials hors Git.


## Réconciliation du nouvel audit — 23 août 2026

| Dépendance ou contrôle | État vérifié après ce lot |
|---|---|
| Extra `calendar` / ICS | Déclaré dans `pyproject.toml`; `icalendar 7.3.0` est installable avec l’extra. Le renderer ICS local ne dépend pas de ce paquet pour fonctionner. |
| Detect-secrets | Le scan canonique CI passe après allowlist locale de neuf fixtures de tests synthétiques. Aucune exclusion globale des tests ou de `backend/app` n’a été ajoutée. |
| Mypy | Ajouté au groupe dev et à `uv.lock`; CI contrôle les quatre modules du noyau de sécurité. Le reste de l’application n’est pas encore couvert par ce contrôle. |
| Proxy/Caddy et rate limiter | `SMART_AO_TRUSTED_PROXY_CIDRS` est configurable ; Compose préproduction fournit le réseau interne Caddy `172.30.0.0/24`. Les en-têtes de transfert restent ignorés depuis un pair non approuvé. Le store partagé multi-réplique reste externe. |
| MFA/TOTP | Les tables et la policy de step-up existent, mais aucune cérémonie TOTP ni configuration sensible n’est activée. Le flux complet reste à coder avant activation. |
| PostgreSQL/Docker/VPS | Aucun résultat online réel ajouté. Alembic offline `0055` passe ; la recette PostgreSQL, le trigger online, Docker, ClamAV/EICAR, HTTPS et backup/restauration restent à exécuter sur l’environnement correspondant. |
| BGE/RAG/OCR/CCAP-CCTP | Les antennes optionnelles et contrats existent ; aucun corpus, poids ou résultat métier réel n’est fabriqué. Les gaps OCR et analyse métier restent des lots distincts. |

Le rapport détaillé est [`AUDIT_RECONCILIATION_2026-08-23_2.md`](AUDIT_RECONCILIATION_2026-08-23_2.md).


## Réconciliation du troisième audit — 23 août 2026

- **Shared kernel et frontières HTTP** : `ApplicationCommand` est fourni par `platform/events/command_contracts.py`; les routes utilisent désormais `interfaces/http/dependencies/auth.py` pour la résolution Bearer. Les aliases `_resolve_context` conservés dans quelques modules sont uniquement des compatibilités contrôlées.
- **Stockage** : le port est situé dans `platform/storage/ports.py`; les adaptateurs local et objet ne dépendent plus du module preparation.
- **Docker/CI** : backend installé depuis `uv.lock` avec `uv sync --frozen`; frontend non-root sur 8080 avec healthcheck; actions CI par SHA; Trivy couvre backend et frontend. Le code et les contrats sont testés statiquement, mais l’exécution distante reste bloquée par l’absence de runner/Docker disponible.
- **Sécurité frontend** : session mémoire, retry 401 contrôlé avec timeout, logout résilient, ErrorBoundary et masquage UI des surfaces patronales pour `COLLABORATEUR`. Ces contrôles complètent, mais ne remplacent pas, les contrôles backend et tenant.
- **JWT** : `SMART_AO_JWT_KEY_ID` et `SMART_AO_JWT_VERIFICATION_KEYS_JSON` sont câblés en préproduction; les clés réelles doivent venir d’un gestionnaire de secrets et ne sont pas commitées.
- **Reste externe ou volontairement ouvert** : TOTP/MFA actif, rate limiter distribué, scan ClamAV/libmagic de l’import pricing, projection/rétention outbox, N+1, OCR/corpus BGE, fournisseur bus, PostgreSQL online, Docker/ClamAV-EICAR, HTTPS, sauvegarde/restauration et CI avec runner exécutant.

Le rapport détaillé est `docs/AUDIT_RECONCILIATION_2026-08-23_3.md`.


## Actualisation audit n°4 — 24 août 2026

Le quatrième audit a confirmé une incompatibilité entre la projection mutable `patron_actions` et son ancien trigger append-only. La migration `20260824_0056` sépare désormais les colonnes de projection autorisées des colonnes historiques immuables. Le readiness vérifie la tête Alembic `20260824_0056` au lieu de se limiter à `SELECT 1`, et les Compose local/préproduction utilisent un service `migrate` one-shot avant le backend et les workers.

L’extra `object-storage` est désormais raccordé au Dockerfile backend et au build préproduction. Le pipeline CI exporte toutes les extras pour pip-audit et construit l’image backend de scan avec les flags optionnels. Cela prouve le câblage de la supply chain, pas l’absence de CVE ni une exécution CI verte. Docker, PostgreSQL online, ClamAV réel, bucket S3/MinIO, fournisseurs externes et runners GitHub restent des preuves environnementales à exécuter sur leurs cibles.

La réconciliation détaillée est [`AUDIT_RECONCILIATION_2026-08-24_4.md`](AUDIT_RECONCILIATION_2026-08-24_4.md).


## Actualisation audit n°5 — 24 août 2026

L’audit n°5 a confirmé un défaut de chemin dans le service `migrate` du Compose de développement ; il est corrigé vers `/app/backend/alembic.ini`, conformément à la structure de l’image backend. La tête Alembic est maintenant partagée via `EXPECTED_ALEMBIC_HEAD` et comparée au graphe réel par un test d’architecture. Le readiness distingue la connectivité database de l’état schema.

Le test event-bus est isolé par tenant, la garde 0056 est testée sur toutes ses colonnes historiques et DELETE, et les commandes canoniques de validation installent explicitement l’extra `calendar`. Les timeouts Vitest sont adaptés aux runners CPU-contraints. Ces corrections améliorent le câblage et la preuve locale ; elles ne constituent pas une exécution Docker/PostgreSQL online, un run CI vert ou une recette fournisseur.

La réponse détaillée est [`AUDIT_RECONCILIATION_2026-08-24_5.md`](AUDIT_RECONCILIATION_2026-08-24_5.md).


## 11. Réconciliation canonique de l’audit exhaustif — 24 août 2026

Cette section supersède les formulations historiques contradictoires sur les comptes de tests et le statut ICS. Le rapport exhaustif archivé dans `docs/operator-reports/` demeure la source de la mesure externe : son résultat Docker/PostgreSQL de 1 346 tests et 90,96 % n’a pas été reproduit dans le sandbox courant. La validation locale actuelle est de 906 tests backend hors `db`, 458 tests DB désélectionnés, 98 tests frontend dans 23 fichiers, typecheck/lint/build passés, et Alembic offline jusqu’à `20260824_0056`.

**Correction ICS explicite :** le renderer `backend/app/modules/submission/infrastructure/ics_calendar.py` importe bien `icalendar` et lève une erreur contrôlée si l’extra `calendar` n’est pas disponible. L’extra est donc requis pour ce renderer. Cette dépendance est câblée pour un export ICS local, désactivée par défaut et non reliée à un agenda distant ; aucune synchronisation CalDAV/OAuth n’est revendiquée. Les phrases historiques indiquant que le renderer n’importe pas `icalendar` sont obsolètes et sont conservées uniquement pour expliquer la correction.

| Brique | État vérifié au 24 août | Ce qui n’est toujours pas prouvé |
|---|---|---|
| OR-Tools | Port/adaptateur CP-SAT, persistence de run, hash, idempotence et audit codés sous `optimization`. | Migration/tests PostgreSQL online et valeur sur cas métier réel. |
| RAG/BGE | Provider local optionnel, index JSONB tenant/Case/version-scoped, retrieval et worker one-shot protégés par opt-in séparé. | Poids BGE, corpus Golden DCE, précision/latence, activation automatique et choix pgvector/Qdrant. |
| Docling/PyMuPDF/OCR | Adaptateurs optionnels et fallback déterministe existants. | Scans, OCR, tableaux complexes, budgets CPU/RAM et validation humaine sur corpus réel. |
| S3/MinIO | Port et adaptateur privé optionnels, non-écrasant et borné. | Bucket réel, permissions, lifecycle, backup/restore et recette Docker. |
| BOAMP/INSEE/SMTP/ICS | Ports, projections allowlistées et activations runtime explicites ; ICS local dépend de `icalendar`. | Credentials, réseau, fournisseurs, délivrabilité/synchronisation et preuves d’exécution. |
| Bus HTTP | HTTPS public, DNS privé/réservé et redirections refusés ; retry borné côté workers. | Endpoint fournisseur, contrat d’accusé, replay/dédoublonnage réels et recette réseau. |
| Signature | Provider de test HMAC local et routes de suivi présents. | Signature électronique qualifiée, certificat, SDK et fournisseur réel. |
| CI/Docker/VPS | Workflow, Compose, digests et runbooks améliorés statiquement. | Runner GitHub, Docker/ClamAV/EICAR, HTTPS, backup/restore et production. |

Le statut global reste **greffable par slices mais non opérationnel de bout en bout**. Ajouter une dépendance au manifest ou un adaptateur ne vaut ni installation sur cible, ni recette fournisseur, ni preuve métier. Les secrets, tokens, poids de modèle et URLs réelles doivent rester des paramètres runtime hors Git.
