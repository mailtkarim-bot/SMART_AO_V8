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


## Réponse au rapport d’audit légendaire — 24 août 2026

Le rapport `docs/operator-reports/AUDIT_LEGENDAIRE_SMART_AO_V8_2026-08-24.md` est archivé. La réponse développeur est `docs/AUDIT_RECONCILIATION_2026-08-24_7_LEGENDAIRE.md`. Les sections historiques ne doivent pas être utilisées pour contredire cette mise à jour.

### Corrections ajoutées après ce rapport

- [x] **OPS-L-001** — mettre à jour `test_dev_compose_is_loopback_bound_and_not_repurposable_as_preprod` pour accepter `SMART_AO_POSTGRES_HOST_PORT` tout en conservant le binding loopback et l’override local.
- [x] **OPS-L-002** — remplacer le fallback JWT `dev-only-*` du Compose development par une clé explicitement locale cohérente avec la garde production et l’exemple `.env.example`; maintenir l’exigence stricte des secrets en préproduction.
- [x] **DOC-L-001** — corriger la mesure de suite backend : 906 passés et 458 désélectionnés après le fix du contrat Compose ; ne pas reprendre sans qualification les 1 363 tests/90,95 % exécutés dans l’environnement externe de l’auditeur.

### Validations et blocages restant canoniques

- [ ] Rejouer `cp .env.example .env; make up` sur un hôte Docker réel et conserver les preuves health/readiness/logs ; le sandbox courant ne fournit pas Docker.
- [ ] Rétablir des runners GitHub Actions et obtenir un run avec steps, conclusions et artifacts ; le run `32728988801` reste un échec avant steps.
- [ ] Révoquer le PAT exposé dans le clone audité et vérifier le journal de sécurité GitHub ; le remote du clone développeur est sans credential, mais cela ne prouve pas la révocation historique.
- [ ] Exécuter PostgreSQL online, les tests DB/CreateCase et les triggers append-only sur une base isolée.
- [ ] Définir l’alerte/rétention outbox et le contrat `cockpit_projection` sans purge ou consumer spéculatif.
- [ ] Livrer l’écran frontend CreateCase et un E2E navigateur HTTPS.
- [ ] Coder les fonctions métier centrales COST-BASIS, CCAP-RISK, croisement documentaire, OCR, DC1/DC2/DC4 et décision finalisable.

**Mesure locale de sortie du correctif :** 906 tests backend hors `db` passent ; 458 sont désélectionnés ; 98 tests frontend passent ; typecheck, lint et build passent ; Ruff, lock UV et scripts shell passent. Les preuves Docker/PostgreSQL online, EICAR, HTTPS public, backup/restore, fournisseur réel et CI avec steps exécutés restent externes ou non obtenues.


## Priorité ARCH-001 et cœur métier BTP — 24 août 2026

### Livré dans la tranche courante

- [x] Extraire `PatronAssignmentCockpitService` vers `PatronAssignmentCockpitReader`, assemblé depuis la composition root.
- [x] Extraire `AssignmentHistoryService` vers `AssignmentHistoryReader`, assemblé depuis la composition root.
- [x] Ajouter un test d’architecture empêchant SQLAlchemy et `.infrastructure` dans ces deux services application.
- [x] Corriger le narrowing mypy de l’ID d’affectation collaborateur.
- [x] Livrer `COST-BASIS-01` : calcul pur exact des coûts complets, réserves BTP, marge, seuil de rentabilité, prix plancher et prix cible.
- [x] Persister les sorties COST-BASIS avec migration `20260824_0057`, contraintes PostgreSQL et DTOs patronaux fermés.

### Tranches de code suivantes

- [ ] Extraire progressivement les autres services membership mutationnels vers des ports/snapshots applicatifs, sans déplacer le dispatcher transactionnel.
- [ ] Introduire les repositories/snapshots pricing nécessaires pour retirer les accès ORM directs de `pricing/application`.
- [ ] Implémenter le registre structuré des risques et exigences CCAP/CCTP, avec sources, criticité, propriétaire et état de traitement.
- [ ] Implémenter le croisement DPGF/BPU avec détection des incohérences et provenance de chaque résultat.
- [ ] Ajouter l’OCR/corpus Golden et la qualification humaine avant toute décision automatique.
- [ ] Finaliser la génération contrôlée DC1/DC2/DC4 et la décision GO/NO-GO patronale.
- [ ] Ajouter l’E2E navigateur du parcours pricing/COST-BASIS et les contrôles de non-fuite financière.

### Preuves requises

- [ ] Rejouer migration `0057`, contraintes, idempotence et concurrence avec PostgreSQL online.
- [ ] Rejouer le quickstart Docker et le parcours complet sur un hôte Docker réel.
- [ ] Obtenir un run GitHub Actions attribué avec steps et artifacts ; ne pas fusionner PR #49 avant ce résultat.

## Tranche readers mutationnels et registre CCAP/CCTP — 24 août 2026

### Livré

- [x] Introduire `AssignmentManagementReader` et faire passer les lectures préparatoires membership par un port applicatif.
- [x] Introduire `PricingScenarioReader` et faire passer les lectures patronales pricing/scénarios-transition par un port applicatif, en conservant l’état et la version de la dernière transition.
- [x] Ajouter la capability dédiée `decision.risk.write`, réservée au patron administrateur.
- [x] Ajouter la commande et les DTOs fermés `RegisterStructuredRisk`.
- [x] Ajouter le domaine pur CCAP/CCTP avec sévérité, vraisemblance, traitement, bornes et provenance.
- [x] Ajouter la route patronale `POST /api/v1/patron/cases/{case_id}/risks`.
- [x] Vérifier tenant, case, version DCE applicable, analyse `COMPLETED`, fragment, extrait et offsets avant persistence.
- [x] Ajouter la migration PostgreSQL `20260824_0058` avec FKs composites, contraintes et identités tenant-scoped.
- [x] Émettre un événement sparse sans énoncé ni extrait source.

### À recetter sur PostgreSQL réel

- [ ] Exécuter `20260824_0058` sur une base jetable et vérifier les FKs composites.
- [ ] Tester l’isolation tenant et le refus d’un fragment appartenant à une autre version ou un autre tenant.
- [ ] Tester la concurrence sur `functional_key`, la clé de commande et la clé d’idempotence.
- [ ] Vérifier la transaction unique persistence + event + outbox + receipt.
- [ ] Ajouter ensuite la lecture patronale des risques avec pagination bornée et DTO sans fuite financière.

### Prochaine valeur métier BTP

- [ ] Relier le risque à une exigence DCE et à une action de traitement patronale.
- [ ] Croiser CCAP/CCTP avec DPGF/BPU et conserver la provenance de chaque résultat.
- [ ] Ajouter le corpus Golden et la qualification humaine avant toute automatisation OCR/RAG.
- [ ] Finaliser DC1/DC2/DC4 et GO/NO-GO.


## Tranche Decision — croisement risques/exigences et GO/NO-GO — 24 août 2026

### Livré

- [x] Choisir explicitement le bounded context `decision` pour la prochaine extraction ARCH-001.
- [x] Ajouter le garde AST interdisant SQLAlchemy/infrastructure dans `PatronDecisionDossierService`.
- [x] Relier un risque structuré à une exigence DCE uniquement lorsque la confirmation humaine courante est `CONFIRMED`.
- [x] Vérifier tenant, Case, version DCE applicable, appartenance du risque et idempotence fonctionnelle.
- [x] Générer une action patronale `DECIDE_GO_NO_GO` dans le même root transactionnel avec références sûres.
- [x] Ajouter la finalisation humaine `GO`/`NO_GO` avec contexte gelé, fingerprint affiché et révision optimiste.
- [x] Refuser toute finalisation lorsqu’une référence `DCE_REQUIREMENT` n’est pas confirmée ou n’appartient pas à la version DCE applicable.
- [x] Ne pas placer de justification, extrait documentaire ou montant financier dans les DTOs/événements.

### À recetter sur PostgreSQL réel

- [ ] Appliquer Alembic `20260824_0059` sur une base jetable.
- [ ] Vérifier le trigger append-only et les FKs composites sous UPDATE/DELETE et accès inter-tenant.
- [ ] Tester concurrence, replay idempotent et transaction lien + action + événements/outbox.
- [ ] Tester la finalisation sur une Decision réellement préparée avec références `DCE_REQUIREMENT` confirmées.

### Prochaine valeur métier BTP

- [ ] Ajouter la lecture patronale paginée des liens et actions, sans surface collaborateur.
- [ ] Relier les risques vérifiés aux lignes DPGF/BPU sans exposer le pricing confidentiel.
- [ ] Matérialiser explicitement les références `DCE_REQUIREMENT` dans le contexte Decision.
- [ ] Ajouter conditions de GO conditionnel et contrôles de soumission.


## Tranche lecture Decision et rapprochement DPGF/BPU — 24 août 2026

### Livré

- [x] Ajouter le port et la projection patronale paginée des liens risque–exigence avec curseur stable `(created_at, link_id)` et plafond de 100 éléments.
- [x] Joindre à chaque lien l’état, la sévérité et la révision de l’action `DECIDE_GO_NO_GO` correspondante.
- [x] Ajouter une route patronale de recherche de candidats DPGF/BPU sur lots normalisés `COMMITTED` de la même Case.
- [x] Exclure de la projection de rapprochement les quantités, prix unitaires et totaux.
- [x] Réserver la lecture à `decision.risk.read`, absente des capacités collaborateur.
- [x] Consolider `CONDITIONAL_GO` avec 1 à 32 conditions structurées, responsables, échéances ou raisons d’absence et conséquences d’échec.

### Validation restante

- [ ] Exécuter la migration et les requêtes de pagination/rapprochement sur PostgreSQL réel.
- [ ] Tester en base l’isolation tenant, les lots non `COMMITTED`, la concurrence et la transaction outbox.
- [ ] Persister une décision de rapprochement patronale si la conservation de la correspondance devient nécessaire.
- [ ] Rétablir des runners GitHub Actions exécutants ; le run le plus récent `32756930349` est encore en attente avant toute étape avec `runnerName: null` et zéro étape.


## Recette GO conditionnel et garde de soumission — 24 août 2026

La tentative de recette PostgreSQL réelle n’a pas pu être lancée dans le sandbox : aucun serveur local ni cible `SMART_AO_DATABASE_URL` n’est disponible, et Docker de l’ordinateur utilisateur n’est pas accessible depuis cet environnement. Cette étape reste donc explicitement ouverte et ne doit pas être comptée comme validée.

Le garde domaine de soumission est préparé. Il bloque les Decisions non finalisées, `NO_GO`, les contextes non gelés, les exigences DCE non confirmées, les conditions ouvertes d’un `CONDITIONAL_GO` et les actions de risques non résolues. Il ne lit ni ne renvoie de montants financiers.

Le gate local courant est de **971 tests passés et 458 désélectionnés** ; 39 tests ciblés de la tranche récente passent. Ruff, mypy ciblé et detect-secrets passent. La prochaine recette nécessite PostgreSQL réellement accessible et doit couvrir la migration 0059, la persistence des conditions `OPEN`, l’outbox, l’idempotence, l’isolation tenant, l’append-only et les scénarios inter-tenant.


## Diagnostic CI et recette PostgreSQL Docker — 24 août 2026

Le run `32761180934` associé à `8798f36` a terminé en échec avant toute étape : backend, frontend et image-security ont `runnerName: null` et zéro step ; `gh run view --log-failed` retourne `log not found`. Aucun résultat de test, build ou scan CI ne peut être retenu.

La simulation Docker éphémère n’a pas été exécutée : `docker` est absent du sandbox. La recette réelle reste à jouer sur une machine équipée, avec migrations, seed contrôlé, assertions tenant/version, conditions `OPEN`, outbox, idempotence, append-only et refus inter-tenant.
