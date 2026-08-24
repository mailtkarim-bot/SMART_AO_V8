# SMART_AO V8 — Checklist durable

Cette checklist est la source de vérité opérationnelle après réconciliation des deux audits. Les anciennes entrées historiques détaillées ont été remplacées par le journal des slices publiés et les seules frontières encore ouvertes.

## Corrections d’audit publiées

- [x] **Protection anti-brute-force progressive** — `LoginRateLimiter` injectable, buckets SHA-256, throttling `/login` et `/refresh`, audit des refus `429` et `Retry-After`. Commit `025c36d`, CI `32076462140` verte.
- [x] **Fixtures PostgreSQL de tests centralisées** — `backend/tests/conftest.py`, `tests.support.database`, URL unique `SMART_AO_TEST_DATABASE_URL` avec fallback par concaténation, 43 modules nettoyés. Commit `aac4de0`, CI `32078237301` verte.
- [x] **Observabilité et durcissement runtime** — `request_id`, logs JSON opérationnels, compteurs `/metrics` sans données métier, image backend digest-pinnée et utilisateur non-root avec quarantaine privée contrôlée. Commits `0ecb24c` et `0ab3cbc`, CI finale `32080763983` verte.
- [x] **Dépendances frontend reproductibles** — suppression de `latest` dans `web/package.json`, alignement des spécificateurs avec `web/pnpm-lock.yaml`, installation `--frozen-lockfile` et build TypeScript strict. Commit `d4b33fe`, CI `32081102590` verte.
- [x] **Couverture et concurrence déterministes** — seuil initial `85 %` dans `pyproject.toml` et la CI, scénarios PostgreSQL couvrant révision optimiste et receipt `PROCESSING` avant outbox. L’ancien jalon `89,32 %` est historique et ne constitue pas la mesure de la branche actuelle.

## État technique publié

- [x] Healthchecks live/ready, factory de production, scripts de déploiement, sauvegarde/restauration isolée, rotation bornée des logs/secrets et pinning des images sont publiés.
- [x] Les slices métier DCE, sécurité, affectations patron/collaborateur, préparation, capacités/preuves, revues/brouillons techniques et fondation financière déjà publiés restent couverts par la suite backend et ne doivent pas être réouverts comme tâches historiques.
- [x] Les invariants de sécurité restent obligatoires : tenant résolu serveur, confidentialité financière absolue, append-only des registres immuables, révision optimiste et idempotence par `command_id`/`idempotency_key`.

## Tâches réellement restantes

- [x] **PRICING-IMPORT-HTTP-PERSISTENCE-01** — preview patronale DPGF/BPU/Excel persistée en lot normalisé `PREVIEWED`, lecture patronale tenant-scoped et commit atomique des lignes valides vers `DRAFT`. Le parcours HTTP, l’idempotence, la policy auditée, la classification `FINANCIAL_PRIVATE`, le hook frontend et les tests locaux sont livrés sur la PR #49 ; la CI GitHub reste à exécuter sur un runner disponible.
- [x] **SUBMISSION-SIGNATURE-HTTP-01** — routes patronales authentifiées, callback hash-only HMAC, projection minimale, audit, idempotence et séparation stricte d’avec la preuve de dépôt publiés par `a7c0d58`. Le provider de test local déterministe et sans réseau est publié par `9bb8c90`; aucun fournisseur réel ni dépôt externe n’est simulé.
- [x] **OPPORTUNITY-WATCH-PROFILE-01 / persistence + HTTP** — profil patronal versionné, migration `0052`, idempotence/outbox, révision optimiste, versions append-only et routes create/version/read publiés sur la branche courante.
- [x] **OPPORTUNITY-INGESTION-01 / staging + persistence + scoring** — service BOAMP derrière `PublicNoticeSearchPort`, script `scripts/ingest_boamp_opportunities.py`, migration `0053`, observations fingerprintées, runs/liens append-only, scoring explicable `BOAMP_PUBLIC_V1` et script `scripts/persist_boamp_opportunities.py` publiés. La recette PostgreSQL/BOAMP réelle et la conversion en Case restent ouvertes.
- [x] **OPPORTUNITY-QUALIFICATION-01 / lecture patronale** — lecture tenant-scoped réservée à un `PATRON_ADMIN` actif, décisions fermées `QUALIFIED`/`REJECTED`/`SNOOZED`, motifs compatibles, migration `0054`, qualification append-only, idempotence/outbox et script `scripts/read_qualify_boamp_opportunities.py` publiés. Aucune conversion automatique en Case.
- [ ] **Gate VPS réel**, lorsque l’utilisateur disposera d’un VPS : builder les images digest-pinnées, lancer PostgreSQL/ClamAV/Caddy, exécuter le test EICAR, vérifier HTTPS et `/healthz/ready`, installer les timers systemd, tester la sauvegarde hors VPS, la restauration isolée et la supervision externe.
- [ ] **Raccordement frontend à l’API publiée**, uniquement après réception et vérification d’une URL HTTPS backend réelle ; ne pas fixer `VITE_API_BASE_URL` avant cette preuve.
- [ ] **Rapport opérateur de restauration**, à produire pendant le gate VPS réel avec hashes, échantillon documentaire, contrôle tenant, état outbox, logs, backup hors hôte et preuve de rotation des secrets.

## Slices BOAMP publiés le 23 août 2026

- [x] **HTTP lecture/qualification patronale** — commit `4a189ea` : routes FastAPI tenant-scoped, bearer et acteur résolus serveur, capabilities patronales, DTOs `extra=forbid`, projection minimale et qualification humaine append-only.
- [x] **Notification outbox vers bus externe** — commits `e2526d2` et `793b334` : `ExternalEventBusPort`, adaptateur HTTPS générique opt-in, adapter mémoire de test et worker borné aux topics BOAMP d’ingestion et de qualification ; aucun `PUBLISHED` sans accusé externe `2xx`, aucun polling Manus et aucun fournisseur inventé.
- [x] **Recette PostgreSQL 0053/0054** — commit `798bbec` : `scripts/recipe_boamp_postgres.py`, validation d’URL, application Alembic optionnelle, contrôle de la révision `20260823_0054`, des tables/triggers append-only et lancement des tests ciblés ; aucune URL/secret dans la sortie.
- [x] **Durcissement qualification BOAMP** — commits `394c3c4` et `cc27f85` : exception applicative typée pour les conflits d’idempotence, suppression du catch-all `RuntimeError` dans la route, alignement du script CLI et test PostgreSQL couvrant qualification, rejeu, unicité event/outbox et trigger append-only ; l’exécution online reste dépendante d’un PostgreSQL disponible.
- [x] **Harnais PostgreSQL local** — `scripts/start_local_postgres.sh`, image PostgreSQL 16 digest-pinnée, volume local isolé, port hôte `5433`, healthcheck, réutilisation sûre et tests CLI sans fuite du mot de passe. La validation online reste à exécuter sur la machine Docker de l’utilisateur.
- [x] **Revue globale et activation contrôlée du bus** — `docs/GLOBAL_REVIEW_2026-08-23.md`, `docs/EXTERNAL_EVENT_BUS_CONTRACT.md`, worker bus désactivé par défaut, opt-in explicite, configuration HTTPS obligatoire, profil Compose préproduction `external-bus` et tests de configuration. Aucun fournisseur réel n’est simulé.
- [x] **Gate PostgreSQL du worker outbox** — `backend/tests/process/test_opportunity_event_bus_persistence.py`, recette étendue aux tests observations `0053`, qualification `0054` et worker outbox, plus `docs/NEXT_LOT_POSTGRES_OUTBOX_GATE.md`. Les tests sont codés et collectables ; leur exécution online reste ouverte tant que Docker/PostgreSQL n’est pas accessible.
- [x] **Cockpit frontend BOAMP** — feature `web/src/features/opportunities`, méthodes API de lecture/qualification, sélection patronale, décisions et motifs fermés, message de rejeu idempotent et navigation intégrée à `App.tsx`. Les tests frontend et le build Vite passent ; l’appel réel attend une URL HTTPS backend vérifiée.
- [x] **Lecture DCE/RAG frontend** — feature `web/src/features/dce`, projections `/dce-reading`, recherche `/knowledge/search`, compteurs de complétude, exigences structurées et localisations sources. Les 93 tests frontend et le build Vite passent ; PostgreSQL online, poids BGE et corpus Golden DCE restent à valider.
- [x] **KNOWLEDGE-BENCHMARK-01** — value objects purs et `scripts/validate_knowledge_benchmark.py` pour valider un manifeste Golden DCE/RAG anonymisé, tenant-scoped et sans contenu sensible, puis calculer `recall_at_k`, moyenne et p95 à partir d’un rapport d’identifiants externe. Aucun corpus, modèle BGE ou résultat réel n’est fabriqué.
- [x] **KNOWLEDGE-VERSION-SCOPE-01** — retrieval DCE limité à la version applicable : `RetrievalScope`, service, route HTTP et requête SQLAlchemy portent et filtrent `dce_version_id` résolu côté serveur ; régression ajoutée contre les versions supersédées, sans exposition de contenu ni données financières. Publié dans `93ba239`.
- [x] **DCE-ANALYSIS-OPS-01** — worker one-shot `app.workers.dce_analysis`, wrapper `ops/run-dce-analysis-preprod.sh` et service Compose isolé dans le profil `dce-analysis`. L’acteur SYSTEM, le tenant, la version DCE et la sortie sans extrait sont testés ; l’exécution réelle reste dépendante de Docker/PostgreSQL et d’une DCE admise. Le même lot ajoute `app.workers.dce_requirements`, `ops/run-dce-requirements-preprod.sh` et le profil `dce-requirements` pour matérialiser les exigences après l’analyse. Publié dans `fe488f5`.
- [x] **ARC-01 / extraction ORM métier** — modèles pricing, preparation, submission, patron_action et enterprise déplacés hors de `platform/security/models.py`, exports de compatibilité conservés, imports applicatifs migrés et test d’ownership ajouté. La registry Alembic est explicitement chargée par bounded context.
- [x] **PRICING-SCENARIO-IMMUTABILITY-01** — migration `20260823_0055` ajoutant le trigger append-only de `pricing_scenarios`; les transitions restent la seule surface de changement d’état.
- [x] **WEBHOOK-SSRF-01** — webhook d’export limité à HTTPS, résolution DNS obligatoire et refus des adresses privées, loopback, link-local, multicast, réservées et non spécifiées ; 27 tests ciblés passent.
- [x] **JWT-KID-01** — codec JWT émet un `kid`, accepte un jeu de clés de vérification pour rotation et conserve la compatibilité des tokens sans `kid`. Le raccordement des clés de rotation à l’environnement de production reste externe.

## Vérifications et travaux encore ouverts

- [ ] **Couverture applicative** — la mesure locale complète hors DB est de **67,45 %** avec le seuil strict à `85.50 %`. Ajouter des tests utiles pour bootstrap/authentification/workers et exécuter la couverture complète avec PostgreSQL ; ne pas contourner le seuil par exclusions artificielles.

- [ ] Exécuter la recette avec PostgreSQL 16 réellement accessible, puis conserver le verdict, les hashes de migration et la preuve des triggers append-only. Le sandbox actuel répond `connection refused` sur `127.0.0.1:5432`.
- [ ] Exécuter sur un corpus DCE anonymisé le worker d’indexation, `verify_bge_model_cache.py`, le worker `run-dce-analysis-preprod.sh` et le validateur `validate_knowledge_benchmark.py`, puis conserver uniquement les métriques et identifiants autorisés.
- [ ] Définir avec le fournisseur réel le contrat de bus, l’URL HTTPS, le mode d’authentification, les garanties de livraison et la stratégie de replay ; injecter ensuite ces paramètres hors Git et exécuter une recette contrôlée. Aucun bus réel n’est configuré dans le dépôt.
- [ ] Rétablir des runners GitHub Actions exécutants avant de considérer une CI distante comme verte ou de fusionner la PR #49/main. Les derniers runs échouent avant toute étape avec `runnerName` absent et `steps: []` pour les trois jobs.

## Frontières explicitement non retenues par les audits

MinIO sans contrat de stockage établi, sharding/Redis/tracing distribué spéculatifs, DAST/Semgrep déjà couvert par Bandit/Trivy, et tests de charge nécessitant un environnement dédié ne sont pas des tâches ouvertes de cette remédiation.

## Réconciliation audit 2 — 23 août 2026

- [x] Corriger les neuf faux positifs detect-secrets des fixtures de test avec des allowlists locales explicites ; le scan canonique passe.
- [x] Ajouter le contrôle mypy borné du noyau de sécurité (`authorization`, `context`, `rate_limit`, `tokens`) et verrouiller la dépendance.
- [x] Corriger la résolution de l’IP client derrière proxy : `X-Forwarded-For` accepté seulement depuis `SMART_AO_TRUSTED_PROXY_CIDRS`, avec réseau Caddy préproduction déclaré.
- [ ] Remonter honnêtement la couverture de 67,62 % vers 85,50 % par tests utiles, sans exclusions artificielles.
- [ ] Implémenter puis tester la cérémonie TOTP complète avant d’activer le step-up MFA sur publication financière, export/signature et autres actions sensibles.
- [ ] Décider le bounded context propriétaire puis extraire prudemment les modèles `CaseAssignment*` et `CollaboratorTask*` restants de `platform/security/models.py`, avec registry Alembic et régression d’imports.
- [ ] Exécuter PostgreSQL online, Docker/ClamAV/EICAR, HTTPS, sauvegarde/restauration, corpus BGE/DCE et bus externe sur les environnements correspondants.
- [ ] Rétablir des runners GitHub Actions exécutants ; ne pas fusionner PR #49 ou `main` avant une CI réellement exécutée et l’analyse de ses résultats.

Le détail de qualification se trouve dans `docs/AUDIT_RECONCILIATION_2026-08-23_2.md`.


## Réconciliation audit 3 — 23 août 2026

- [x] Centraliser les routes sur `interfaces/http/dependencies/auth.py` et éliminer les imports de helper privé d’une route vers une autre.
- [x] Inverser la dépendance de stockage : port dans `platform/storage`, adaptateurs hors dépendance vers preparation.
- [x] Rendre la machine à états patron_action explicite dans le domaine et synchroniser sa projection persistée.
- [x] Installer l’image backend depuis `uv.lock` avec `uv sync --frozen`; ajouter le scan frontend Trivy et pinner les actions CI par SHA.
- [x] Durcir le frontend : Nginx non-root/healthcheck, ErrorBoundary, RBAC UI patron/collaborateur, session/retry/timeout, ESLint et typecheck.
- [x] Câbler `SMART_AO_JWT_KEY_ID` et `SMART_AO_JWT_VERIFICATION_KEYS_JSON` dans le runtime preprod sans secret dans Git; verrouiller le Compose dev au loopback et à `development`.
- [ ] Définir le contrat `cockpit_projection` et une politique de rétention outbox/domain events avant d’ajouter un worker ou de publier vers un bus externe.
- [ ] Raccorder ClamAV/libmagic à l’import pricing XLSX avec stockage temporaire privé et fail-closed.
- [ ] Implémenter la cérémonie TOTP d’enrôlement/vérification puis activer le step-up MFA sur les opérations réellement sensibles.
- [ ] Traiter les N+1 après mesure PostgreSQL et benchmark de requêtes; ne pas optimiser à l’aveugle.
- [ ] Développer les slices métier CCAP-RISK, COST-BASIS/prix plancher, croisement CCTP–DPGF–CCAP, génération DC1/DC2/DC4 et boucle de décision GO/NO-GO.
- [ ] Ajouter les preuves externes : PostgreSQL online, Docker/ClamAV-EICAR, HTTPS, backup/restore, corpus DCE/BGE, bus et runners GitHub Actions.

Réconciliation détaillée : `docs/AUDIT_RECONCILIATION_2026-08-23_3.md`.


## Source de vérité canonique après l’audit exhaustif — 24 août 2026

Les sections antérieures restent conservées comme journal historique. La checklist ci-dessous est la référence de pilotage la plus récente ; elle ne transforme aucune recette externe en preuve locale.

### Remédiations appliquées dans le lot courant

- [x] Archiver le rapport exhaustif dans `docs/operator-reports/AUDIT_EXHAUSTIF_SMART_AO_V8_2026-08-24.md` et publier `docs/AUDIT_RECONCILIATION_2026-08-24_6.md`.
- [x] Bloquer les redirections et destinations HTTP privées pour le webhook et le bus externe via un helper partagé HTTPS/DNS.
- [x] Ajouter les headers de sécurité FastAPI de défense en profondeur.
- [x] Borner les retries des workers retention, webhook, SMTP et bus avec terminal `FAILED`; conserver `cockpit_projection` ouvert jusqu’à décision de contrat/rétention.
- [x] Aligner la limite d’admission DCE runtime sur 150 MB et paramétrer le port PostgreSQL hôte du Compose dev.
- [x] Renforcer le workflow CI par permissions minimales, concurrency, timeouts, digest PostgreSQL, installation de toutes les extras et rapports SARIF Trivy backend/frontend.
- [x] Nettoyer la baseline detect-secrets des environnements/caches et faire passer le hook canonique.
- [x] Livrer le backend BTP-1a `POST /api/v1/cases` avec DTOs fermés, capability patronale, idempotence, scopes/origines validés, référence Consultation tenant/révision vérifiée, ports applicatifs et événement sparse.

### Travaux de code prioritaires restant

- [ ] Ajouter l’écran frontend de création d’affaire et son parcours de navigation `CASE_OVERVIEW`.
- [ ] Définir et coder la cérémonie MFA/TOTP complète : enrôlement, confirmation, recovery, step-up et tests d’intégration.
- [ ] Concevoir un rate limiter distribué ou une admission edge avant tout scale-out multi-réplique.
- [ ] Définir le contrat, le consumer, l’alerte et la rétention de `cockpit_projection`; conserver les messages `FAILED` consultables.
- [ ] Refactoriser progressivement les arêtes application→infrastructure par bounded context, en commençant par les lectures membership, avec tests d’architecture, DB et concurrence.
- [ ] Implémenter l’analyse métier CCAP–CCTP–DPGF–BPU, l’OCR/corpus Golden, le coût de revient, le prix plancher, pénalités/RG/cautionnement, DC1/DC2/DC4 et la commande de décision GO/NO-GO.
- [ ] Implémenter la conversion contrôlée observation BOAMP qualifiée → Case, sans créer de scheduler ou d’appel fournisseur par défaut.

### Preuves externes obligatoires avant production

- [ ] Obtenir un runner GitHub réellement attribué et exécuter la CI complète de la branche ; ne pas fusionner PR #49 ou `main` avant un verdict avec steps et artifacts.
- [ ] Exécuter PostgreSQL 16 online sur base jetable : migrations head `0056`, tests DB, isolation tenant, append-only et parcours CreateCase.
- [ ] Exécuter Docker/Compose/Caddy/ClamAV réel, test EICAR, health/readiness et vérification des logs persistants.
- [ ] Vérifier une URL HTTPS backend réelle, le login/refresh/CSRF et un E2E navigateur Playwright.
- [ ] Recetter backup hors hôte et restauration isolée avec hashes, contrôle tenant et état outbox.
- [ ] Recetter séparément BGE/RAG, Docling/OCR, S3/MinIO, BOAMP/INSEE, SMTP/ICS, signature et bus avec credentials runtime hors Git.

**État de preuve local au 24 août :** 906 tests backend hors `db` passent ; 458 tests DB sont désélectionnés ; 98 tests frontend passent ; typecheck, lint, build, Ruff, mypy ciblé, lock UV, detect-secrets, scripts shell et Alembic offline `0056` passent. Docker, PostgreSQL online, VPS, HTTPS public, EICAR, backup/restore, fournisseur réel et CI avec steps exécutés ne sont pas prouvés dans le sandbox.
