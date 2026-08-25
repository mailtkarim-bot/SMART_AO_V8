# Rapport d'audit exhaustif — SMART_AO V8

> **Auditeur** : ox-alpha (audit indépendant, niveau production, sans complaisance)
> **Date d'audit** : 2026-08-24
> **Prompt suivi** : `rapports/Prompt d'audit exhaustif — SMART_AO V8.md`
> **Mode** : lecture seule du dépôt ; vérifications destructrices uniquement sur bases/conteneurs isolés et jetables ; aucune donnée du développeur détruite (volumes Compose conservés, tests de triggers en transaction ROLLBACK).

---

## 0. Identité exacte de la version auditée

| Élément | Valeur | Preuve |
|---|---|---|
| Dépôt | `github.com/mailtkarim-bot/SMART_AO_V8` | `git remote -v` |
| Branche auditée | **HEAD détaché** sur le tip de `docs/pricing-http-next-lot-28` (`git status` : `## HEAD (no branch)`) ; `origin/main` = `970c9ff` (merge PR #48) ; PR #49 non fusionnée | `git status --short --branch`, `git rev-parse` |
| Commit exact | `0eb82a0f4ee67c67c85e2b7f63a962dbd636348e` (« docs: add exhaustive SMART AO audit prompt ») | `git rev-parse HEAD` |
| Working tree | Propre hors 4 éléments non trackés : `RAPPORT_AUDIT_04_VERIFICATION.md`, `RAPPORT_AUDIT_05_VERIFICATION.md`, `RAPPORT_AUDIT_SYSTEME_BTP.md`, `rapports/` | `git status --short` |
| 5 derniers commits | `0eb82a0`, `cd0060f`, `b00aad0`, `537c835`, `0071301` (tous docs) | `git log -5 --oneline` |
| Python / Node / pnpm / uv | 3.12.3 / v22.23.1 / 11.21.0 / 0.11.21 | exécution locale |
| PostgreSQL / Docker / Compose | pas de CLI psql locale / Docker 29.1.3 / Compose v5.5.0 — **Docker disponible et utilisé pour les recettes isolées** | exécution locale |
| Variables d'environnement | Aucune variable secrète exportée dans le shell d'audit ; seul `.env.example` présent (aucun `.env` committé) | `env | grep -i …` (vide), `ls .env*` |

⚠️ **Constat immédiat (SEC-001)** : l'URL du remote contient un token GitHub personnel (`https://ghp_…@github.com/…`). Sa valeur n'est pas recopiée ici conformément aux règles de l'audit. Voir finding SEC-001.

---

## A. Résumé exécutif

### Méthode de notation

Chaque axe est noté /20 selon trois pondérations : preuves d'exécution obtenues pendant l'audit (50 %), qualité structurelle confirmée par inspection (30 %), écarts vs exigences production documentés au chapitre B (20 %). Un axe dont la validation dépend d'un environnement externe inaccessible est plafonné à 10/20 tant que la preuve manque (**jamais crédité sur promesse ou code seul**).

### Tableau de notes

| Axe | Note /20 | Verdict | Justification condensée |
|---|---:|---|---|
| Architecture | 14 | **GO conditionnel** | Domaine 100 % pur (0 violation AST sur 35 imports externes), 0 cycle inter-contextes, ORM confiné, composition root exemplaire ; mais 64 arêtes application→infrastructure hors ports dont 19 inter-contextes (§B ARCH-001). |
| Backend/API | 15 | **GO conditionnel** | 888 tests non-DB verts en 13 s ; DTOs fermés, idempotence, mapping 404 unifié anti-énumération, erreurs typées ; routes globalement minces avec 3 exceptions documentées. |
| Données/PostgreSQL | 16 | **GO conditionnel** | 458 tests DB verts sur base isolée ; chaîne Alembic linéaire 0001→0056 tête unique ; **trigger append-only prouvé par exécution** (UPDATE rejeté par PostgreSQL) ; SQL offline 3 830 lignes généré. |
| Sécurité | 13 | **GO conditionnel** | Argon2id OWASP, JWT HS256 épinglé + rotation `kid`, refresh rotation avec destruction de lignée sur rejeu, uploads fail-closed ClamAV, token jamais persisté navigateur ; mais MFA inopérant, rate-limit process-local, SSRF webhook contournable via redirections, **token GitHub dans l'URL remote**. |
| Frontend | 12 | **GO conditionnel** | Typecheck/lint/build verts, bundle 294 KB (83 KB gzip), token en mémoire seule testé, ErrorBoundary testé ; suite Vitest petite (98 tests), premier run instable sous charge, aucun E2E navigateur réel, warnings hooks résiduels sur `App.tsx`. |
| Docker/CI/Ops | 10 | **NO-GO** | Stack dev démarrée et healthy pendant l'audit (backend/postgres/clamav healthy, migrate exit 0 jusqu'à 0056, readiness fail-closed vérifiée) ; **mais CI distante morte depuis le 21/08 : 60 échecs consécutifs sans aucune étape exécutée**, préprod jamais recettée, worker retention observé en Exited(1) au démarrage de l'audit. |
| Intégrations externes | 9 | **NON VÉRIFIABLE** | Toutes derrière flags désactivés par défaut ; aucune appelée en réel pendant l'audit (BOAMP/INSEE/SMTP/S3/signature). OR-Tools complet mais **non câblé au runtime** ; ICS jamais invoqué ; signature = intention seulement. |
| Métier BTP | 6 | **NO-GO** | Socle documentaire DCE solide (upload/quarantaine/versioning/exigences/pricing-import réels) mais **aucune création d'affaire HTTP**, aucun moteur CCTP–DPGF–BPU–CCAP, aucun prix plancher/coût de revient/pénalités/RG/cautionnement (grep = 0 hit), pas d'OCR, pas de DC1/DC2/DC4, décision GO/NO-GO sans commande de finalisation. |
| Observabilité/Performance | 11 | **GO conditionnel** | `/healthz/live` et `/healthz/ready` vérifiés par exécution (distinction process/db/clamav, fail-closed prouvé en panne ClamAV) ; logs structurés minimisés confirmés par inspection ; aucun benchmark ni test de charge rejoué ici → volet performance NON VÉRIFIABLE. |
| Documentation/Gouvernance | 11 | **GO conditionnel** | Honnêteté remarquable sur les frontières (preuves externes déclarées ouvertes plutôt que revendiquées) ; mais `PROJECT_STATE.md` périmé de ~3 lots (862 tests vs 1346 ; 67,45 % vs 90,96 % mesuré ; tête 0055 vs 0056), contradictions internes non arbitrées, rapports racine non versionnés. |
| **Moyenne pondérée** | **11,7** | — | Socle technique sérieux, produit métier incomplet, chaîne de validation distante rompue. |

### Les quatre questions de cadrage

1. **Le logiciel est-il architecturalement cohérent ?** Oui dans son squelette (domaine pur, DAG des contextes, composition root), non dans sa couche application qui court-circuite massivement ses propres ports (§ARCH-001).
2. **Les invariants sécurité/données/métier sont-ils respectés ?** Sécurité et données : oui sur tout ce qui a pu être exécuté (tenant isolation, append-only, idempotence, fail-closed) — preuves au chapitre D. Métier : les invariants financiers existent (snapshot publié figé, centimes entiers, trigger 0055) mais la valeur d'analyse attendue n'est pas codée.
3. **Le stack démarre-t-il de bout en bout ?** Localement oui — prouvé par exécution pendant cet audit. En préproduction/VPS : non prouvé, et la CI qui devrait le prouver est morte.
4. **Valeur métier BTP exploitable aujourd'hui ?** Non comme produit de bout en bout. Le cycle ne peut même pas démarrer sans écriture ORM hors produit (absence de `POST /api/v1/cases`). C'est un back-office documentaire DCE défendable, pas encore une plateforme d'appels d'offres.

---

## B. Matrice exhaustive des findings

Gravités : Bloquant > Critique > Élevé > Moyen > Faible > Information. Statuts conformes au prompt (Confirmé par exécution / Confirmé par inspection / Partiellement confirmé / Non vérifiable / Faux positif / Risque ouvert).

### B.1 Sécurité (SEC)

| ID | Gravité | Statut | Localisation | Preuve | Impact | Reproduction | Correction proposée | Priorité | Régression possible | Validation attendue |
|---|---|---|---|---|---|---|---|---|---|---|
| SEC-001 | **Critique** | Confirmé par inspection | Configuration git locale, `git remote -v` | L'URL d'origine contient `https://<token ghp_…>@github.com/mailtkarim-bot/SMART_AO_V8.git` (valeur volontairement non recopiée) | Quiconque voit un terminal, une capture, un script shell ou `~/.gitconfig` partagé obtient un PAT avec accès repo (lecture/écriture potentielle) ; fuite possible via logs CI, dotfiles, screenshots | `git remote -v` | Retirer le token de l'URL (`git remote set-url origin https://github.com/mailtkarim-bot/SMART_AO_V8.git`), passer par `git credential-store`/`libsecret` ou SSH deploy key, **révoquer puis régénérer le token côté GitHub**, auditer son historique d'usage (Settings → Security log) | **P0** | Aucune (opération locale) | `git remote -v` ne montre plus aucun credential ; ancien token refusé par l'API GitHub |
| SEC-002 | Moyen | Confirmé par inspection | `backend/app/platform/security/models.py:842-919` (tables MFA), `authentication.py:338-344` (login crée toujours `auth_strength="PASSWORD"`, `mfa_verified_at=None`), `authorization.py:126-130` (step-up décision) | Schéma TOTP + recovery codes migrés, décision STEP_UP_REQUIRED codée, **mais aucun service d'enrôlement/vérification TOTP ni route** ; grep exhaustif : zéro appelant renseignant `mfa_verified_at` | La policy « step-up sur actions sensibles » est inopérante : jamais déclenchable. Risque si vendu comme MFA-ready | Inspecter `grep -rn mfa_verified_at backend/app` → toujours None à l'écriture | Soit implémenter l'enrôlement/vérification TOTP (cérémonie complète + tests), soit retirer toute mention MFA des contrats/docs pour éviter une fausse promesse commerciale | P1 | Tables MFA déjà migrées (pas de migration à annuler) | Test d'intégration : enrôlement TOTP → login → action sensible sans step-up → 403 → step-up → 200 |
| SEC-003 | Moyen | Confirmé par inspection | `platform/security/rate_limit.py:24-118` (docstring admet « must replace for multi-replica »), branché uniquement `routes/authentication.py:149-161,209-221` | Limite exponentielle 30 s→900 s après 5 échecs/15 min sur login/refresh seulement ; état dict mémoire + Lock process-local ; **aucune limite sur routes métier** (recherche, upload, export) | Multi-réplicas = comptage fragmenté (contournement brute force) ; énumération/DoS applicatif possible sur endpoints non limités (partiellement compensé par plafond 150 MB Caddy) | Inspection + absence de middleware global | Rate limiter distribué (Redis/PG) ou admission par reverse-proxy ; étendre aux routes coûteuses (extraction, knowledge search) | P1 | Latence ajoutée par hop Redis | Test charge : N requêtes/s depuis K sources → 429 cohérents multi-instances |
| SEC-004 | Moyen | Confirmé par inspection | `workers/submission_export_webhook.py:151-175` (garde DNS/IP privées correct) vs `:203` (`urlopen` suit les redirections par défaut) | Garde SSRF valide à la résolution initiale, mais une cible malveillante peut répondre 30x vers une IP interne ou rebinder son DNS (TOCTOU) — `urlopen` ne re-valide pas | Le worker sortant peut être pivoté vers le réseau interne (metadata services, PG si topologie permissive) | Simuler un webhook 302 → http://169.254.169.254 (hors production, réseau isolé) | Désactiver les redirects et re-valider chaque hop (opener custom `HTTPRedirectHandler` refusant private/reserved), ou épingler l'IP validée pour la connexion | P1 | Clients exigeant des redirects légitimes devront les déclarer | Test unitaire : destination 302 vers loopback → envoi refusé + retry borné |
| SEC-005 | Faible | Confirmé par inspection | `platform/security/authenticated_context.py:122` appelle `capabilities_for(actor_kind)` **sans** `delegated_capabilities` ; `capabilities.py:161-162` exige l'intersection pour PATRON_DELEGATE ; grep : aucune délégation jamais chargée | Tout PATRON_DELEGATE reçoit l'ensemble vide → toutes ses demandes 403. Fail-closed (sûr) mais rôle mort : la séparation PATRON_ADMIN/PATRON_DELEGATE/COLLABORATEUR n'est réelle que pour 2 des 3 rôles | Fonctionnalité annoncée inutilisable ; risque de contournement improvisé dangereux si quelqu'un « corrige » en accordant trop | Créer un compte DELEGATE → chaque appel capability-gated renvoie 403 | Charger les délégations persistées dans le contexte OU retirer le rôle du catalogue jusqu'à implémentation | P2 | Tests RBAC à mettre à jour | Test : délégation persistée active → capability intersection accordée ; sans délégation → 403 |
| SEC-006 | Faible | Confirmé par inspection | Backend : aucun header sécurité (seul middleware = observabilité, `bootstrap/application.py:628`) ; headers uniquement dans `ops/Caddyfile:17-24` ; CSP avec `style-src 'unsafe-inline'`, pas de Permissions-Policy | Si le backend est exposé directement (erreur ops, port publié), aucun HSTS/X-Frame-Options/CSP ; defense-in-depth dépendante d'un seul fichier edge | Clickjacking/MITM actif uniquement en scénario de mauvaise config | `curl -I http://127.0.0.1:8000/api/v1/...` → aucun header sécurité | Ajouter middleware headers côté FastAPI (au minimum nosniff/frame-deny/referrer-policy) ; durcir CSP progressivement | P2 | CSS inline frontend à migrer avant CSP strict | `curl -I` montre les headers mêmes hors proxy |
| SEC-007 | Information | Confirmé par inspection | `modules/dce/application/upload.py:78` (`max_bytes=2_000_000_000`) vs `ops/Caddyfile:13-15` (150 MB) | Incohérence de défense en profondeur : l'app accepte théoriquement 2 Go si exposée sans edge | DoS disque/mémoire si exposition directe | Lecture des deux fichiers | Aligner la borne app sur la politique edge réelle (ou justifier l'écart) | P3 | Refus de gros DCE légitimes si trop bas | Test limite : upload > borne → 413 |
| SEC-008 | Information | Confirmé par inspection | `/metrics` (`routes/observability.py:12-17`), `/healthz/ready` (`bootstrap/application.py:639-687`) sans auth, routés publiquement par Caddy (`Caddyfile:31-34`) | Métriques et état des dépendances lisibles anonymement | Énumération d'infra (versions, état clamav/db) ; faible mais inutilement public | `curl http://<host>/metrics` | Restreindre /metrics au réseau interne ; garder /healthz/ready minimal public si requis par le LB | P3 | Supervision externe à re-configurer | Accès anonyme /metrics → 401/404 |
| SEC-009 | Faible | Confirmé par inspection | `.secrets.baseline` (detect-secrets) : 585 entrées dont 569 (97 %) dans `.venv/` (gitigné) + caches pytest/ruff | Baseline gonflée (181 Ko) noyant les vraies entrées ; les 16 entrées hors `.venv` sont des creds factices de tests/dev (faux positifs) | Le scan anti-secret perd sa valeur d'alerte (bruit) | `python3 -c "import json;d=json.load(open('.secrets.baseline'));print(len(d['results']))"` | Régénérer la baseline avec exclusion `.venv/`, caches ; annoter les creds dev factices | P3 | Aucune | Nouvelle baseline < 50 entrées, toutes qualifiées |
| SEC-010 | Élevé (potentiel) | Non vérifiable | Chaîne JWT/refresh : rotation one-time + détection de rejeu destructrice de lignée (`authentication.py:419-495,548-562`), tokens hashés SHA-256, cookies HttpOnly/Secure/SameSite=Lax + CSRF double-submit (`routes/authentication.py:416-450`) — **code conforme, jamais attaqué en réel** | — | Pentest réel non réalisé | Recette pentest avant vente | — | P2 | — | Rapport pentest externe |

### B.2 Architecture (ARCH)

Analyse AST complète (script lecture seule, 306 fichiers, 1 987 imports résolus, 777 arêtes internes, graphe acyclique vérifié par Tarjan).

| ID | Gravité | Statut | Localisation | Preuve | Impact | Reproduction | Correction proposée | Priorité | Régression possible | Validation attendue |
|---|---|---|---|---|---|---|---|---|---|---|
| ARCH-001 | Élevé | Confirmé par inspection | 64 arêtes application→infrastructure hors ports : 19 inter-contextes (ex. `membership/application/financial_report*.py:12-17` → `pricing.infrastructure.models`, `submission/application/service.py:13,20,25` → enterprise/preparation/pricing, `dce/application/handlers.py:12` → case models) + 45 intra-module (ex. `pricing/application/service.py:6-11` importe `sqlalchemy as sa` et query `FinancialReportSnapshotRecord`) | AST + lecture : les services exécutent `sa.select(*Record)` directement ; les ports existent (`application/ports.py` × 5 modules) mais couvrent surtout l'écriture | L'« hexagonalité » tient par le domaine, pas par l'application ; refactorisations futures risquées, lectures non substituables (pgvector, read models) impossibles sans toucher N services | Rejouer l'AST (script fourni en annexe E.7) ; `grep -n "sa.select(" backend/app/modules/*/application` | Internaliser les lectures derrière ports/repositories module par module, en commençant par membership (nœud le plus dense) ; interdire via test architecture (il existe : `tests/architecture/` — l'étendre) | P1 | Risque de régression sur l'idempotence/concurrence si refactoring massif en une passe → procéder par tranches testées | Test architecture échouant sur toute nouvelle arête application→infrastructure non port |
| ARCH-002 | Moyen | Confirmé par inspection (compromis documenté) | `platform/security/models.py:943-961,1238-1263` : imports de modèles de 5 modules avec `# noqa: E402,F401` | Enregistrement des métadonnées Alembic sur le `Base` unique — dépendance inversée shared kernel→modules assumée en commentaire | Couplage structurel inversé ; toute extraction future de contexte devra déplacer cette registry | Lecture fichier | Registry Alembic déclarative (liste de modules dans bootstrap) au lieu d'imports inversés | P2 | Ordre d'import des tables | `alembic upgrade head` identique après refactor |
| ARCH-003 | Faible | Confirmé par inspection | `interfaces/http/routes/market_watch.py:12` et `patron_enterprise_registry.py:12` importent des erreurs d'adaptateurs infra ; `dce/infrastructure/advanced_extraction.py:12` importe la fonction **privée** `_fragmentize` depuis application | 2 fuites interfaces→infrastructure sur 84 imports modules ; 1 import privé infra→application | Fuite de type concret dans la couche interface ; contrat privé consommé à travers les couches | Grep imports | Ré-exporter les erreurs via `public/` ; rendre `_fragmentize` publique et documentée ou déplacer | P3 | Signature publique à figer | Imports conformes au test architecture |
| ARCH-004 | Information | Confirmé par inspection | 6 modules sans couche domain (enterprise, market_watch, membership, optimization, preparation, submission) ; `market_watch/__init__.py` absent (namespace implicite) ; `middleware/` vide | Style transaction-script assumé pour ces modules ; logique vivant en application | Inhomogénéité : 7/13 modules complets ; complexité de navigation | `find backend/app/modules -maxdepth 2 -type d` | Créer des domaines minces là où les règles durcissent (pricing transitions déjà fait) ; ajouter le `__init__.py` manquant | P3 | Effort sans bénéfice immédiat si fait cosmétiquement | Structure homogène + ownership test vert |
| ARCH-005 | Information | Confirmé par inspection | Logique métier résiduelle en interfaces : `_storage_object_id()` uuid5 dans `routes/dce_staging.py:202-205` ; HMAC webhook vérifié dans `routes/patron_submission_signature.py:146-159` ; résolution tenant SQL directe dans `bootstrap/application.py:371-398` | Trois exceptions relevées sur 36 routers, sinon routes minces | Identité d'agrégat et politique de secret webhook codées hors application | Lecture fichiers | Descendre ces règles dans les services applicatifs | P3 | Contrats HTTP inchangés | Tests existants restent verts après déplacement |

### B.3 Données/PostgreSQL (DB)

| ID | Gravité | Statut | Localisation | Preuve | Impact | Reproduction | Correction proposée | Priorité | Régression possible | Validation attendue |
|---|---|---|---|---|---|---|---|---|---|---|
| DB-001 | — (constat positif) | **Confirmé par exécution** | `backend/alembic/versions/` : 56 fichiers `20260813_0001`→`20260824_0056`, tête unique `20260824_0056` alignée sur `EXPECTED_ALEMBIC_HEAD` (`platform/persistence/schema.py:5`) + test anti-dérive (`tests/architecture/test_schema_head_contract.py:16`) | Offline : `SMART_AO_DATABASE_URL=… alembic -c backend/alembic.ini upgrade head --sql` → 3 830 lignes, 97 CREATE TABLE. Online : service migrate exit 0 appliquant 0052→0056 sur volume existant. 458 tests db verts sur PG 16 isolé (digest-pinné) en 6 min 15 s | — | Voir §C/D | — | — | — | — |
| DB-002 | — (constat positif) | **Confirmé par exécution** | Trigger `pricing_scenarios_append_only` (migration 0055) : `BEFORE DELETE OR UPDATE FOR EACH ROW` — définition lue via `pg_get_triggerdef` | Dans une transaction ROLLBACK sur la stack dev : INSERT chaîne FK complète (tenants/cases/snapshots/scenarios) puis `UPDATE pricing_scenarios SET state='ARCHIVED'` → **ERROR: pricing scenarios are immutable; use pricing scenario transitions** ; ROLLBACK sans trace | — | Script psql heredoc (annexe E.6) | — | — | — |
| DB-003 | Moyen | Confirmé par inspection | Outbox : statut `FAILED` défini en contrainte (`platform/persistence/models.py:144-147`) mais **aucun code ne l'écrit** ; workers à lease/backoff cap 3600 s sans plafond d'essais ; topic `cockpit_projection` produit par défaut partout (`dispatcher.py:65`, `dce/application/handlers.py:333,510`) **sans consumer ni purge** (`dce_retention.py:22` ne traite que le staging) | Messages empoisonnés = retry infini potentiel ; table outbox à croissance non bornée | Poison message simulable en injectant un payload invalide topic BOAMP | Politique dead-letter (max attempts → FAILED + alerte) ; job de purge/rétention outbox par topic ; décider du sort de cockpit_projection (consumer ou suppression de la production) | P1 | Perte de messages si purge mal calibrée → garder FAILED consultable | Test : poison message → FAILED après N essais + alerte métrique |
| DB-004 | Faible | Confirmé par inspection | `uq_pricing_scenario_version`, FK composites tenant-scoped systématiques (vérifiées sur `\d pricing_scenarios`, `\d cases`), CHECKs d'états alignés avec les enums domaine (comparaison migration ↔ Literal Python) | Alignement domaine↔PostgreSQL vérifié sur échantillon large (cases, pricing, tenants) — aucun désalignement trouvé | — | `\d` sur tables clés | Poursuivre l'alignement automatique (test de parité enums↔CHECK) | P3 | — | Test parité vert |

### B.4 Ops/CI/Docker (OPS)

| ID | Gravité | Statut | Localisation | Preuve | Impact | Reproduction | Correction proposée | Priorité | Régression possible | Validation expected |
|---|---|---|---|---|---|---|---|---|---|---|
| OPS-001 | **Bloquant** | **Confirmé par exécution** (API GitHub, lecture seule) | Runs 32714197692 (09:56Z) → 60 derniers runs tous `failure` ; jobs backend/frontend/image-security : `runner_name=""`, `steps: []` (0 étape exécutée) ; dernier succès : run `32513616360` du **2026-08-21T18:29Z** | API `repos/…/actions/runs?per_page=100` pages 1-5 : total 437 runs, Counter(60 derniers)= {failure: 60} ; jobs détaillés sans runner ni étape | **Aucun commit depuis le 21/08 (~15+ commits incluant les remédiations audits 4/5) n'est validé par la CI.** Badge/verdict impossible à produire ; risque de régression silencieuse accumulée | `curl api.github.com/.../actions/runs` (voir annexe E.5) | Résoudre le provisioning des runners (billing/actions minutes, file d'attente org, ou self-hosted runner), puis relancer UNE fois et vérifier jobs+artifacts ; ajouter bloc `permissions: contents: read`, `timeout-minutes`, `concurrency` | **P0** | Aucune | Run avec ≥ 3 jobs ayant steps exécutés et conclusions réelles |
| OPS-002 | Élevé | Partiellement confirmé | Worker `dce-retention-worker` : observé `Exited (1)` 15 h avant le début d'audit (`docker ps -a` initial) ; conteneur supprimé entre deux observations **par un processus externe à l'audit** → logs indisponibles | Deux `docker ps -a` espacés de ~15 min montrent la stack passée de Up(healthy) 41-42 h à supprimée ; lors du redémarrage contrôlé, le worker est resté Up toute la session | Cause racine du crash inconnue (crashloop potentiel intermittent) ; `restart: unless-stopped` l'a maintenu en échec répété | NON VÉRIFIABLE (logs perdus) | Ajouter logging persistant du worker + alerte sur restart count ; investiguer au prochain crash | P1 | — | Métrique restart_count alertée |
| OPS-003 | Moyen | Confirmé par inspection | `docker-compose.yml:18` : port hôte postgres codé en dur `127.0.0.1:5432:5432` | Conflit réel observé : stack V7 du développeur occupe déjà 0.0.0.0:5432 → `up` échoue (`port is already allocated`) ; contournement nécessaire par override externe (15432) | Impossible de cohabiter avec tout autre PG local ; friction d'onboarding | `docker compose up -d postgres` sur hôte occupant 5432 | Paramétriser `${POSTGRES_HOST_PORT:-5432}` | P2 | Docs à mettre à jour | `up` réussit sans override |
| OPS-004 | Moyen | Confirmé par inspection | `.github/workflows/ci.yml` : aucun bloc `permissions:` ; service `postgres:16` tag flottant (:13) alors que compose pinne par digest ; Trivy `format: table` (pas de SARIF) ; image scannée = variante **tous extras** (:110-115) vs déployée par défaut extras=0 (sur-ensemble prudent mais ≠ variante cible) ; pas de Dependabot/Renovate/CODEOWNERS ; mypy limité à 4 fichiers security (:36-40) ; Makefile désynchronisé (calendar extra local vs CI aucune) | Comparaison ligne à ligne ci.yml ↔ docker-compose.preprod ↔ Makefile | Supply chain : permissions héritées trop larges possibles selon réglages repo ; vulnérabilités non suivies dans le temps (pas d'historique SARIF) ; reproductibilité CI < prod | Lecture ci.yml | `permissions:` minimal, digest-pin du service PG, Trivy SARIF uploadé, matrice de scan = variantes déployées, Dependabot actions, mypy élargi progressivement | P1 | Durcissement pouvant faire passer la CI rouge (CVE unfixed) → ignorer-unfixed déjà positionné | CI verte + SARIF visible onglet Security |
| OPS-005 | Faible | Confirmé par exécution | Suite Vitest : 1er run `pnpm test --run` après install → 16 fichiers/72 tests + **7 erreurs non gérées** (exit fail, environment 262 s) ; 2e run identique → 23 fichiers/**98 tests**, 0 erreur, 21 s | Logs console des deux runs (§C.2) | Instabilité sous contrainte ressources (workers jsdom) → fausse alerte rouge possible en CI locale | Reproduire en limitant CPU puis relancer | Fixer `poolOptions.forks.singleFork` ou maxWorkers raisonnable ; investiguer les teardown jsdom | P2 | Temps de suite légèrement plus long | 10 runs consécutifs sans erreur |
| OPS-006 | Information | Confirmé par exécution | Commande du prompt d'audit `uv run alembic -c backend/alembic.ini upgrade head --sql` **échoue sans URL** (`Exception: Connection, url, or dialect_name is required`, `alembic/env.py:54-56` via `resolve_database_url`) | Trace conservée §C.4 | Mineur : le mode offline exige `SMART_AO_DATABASE_URL` (dialecte seul insuffisant) — écart avec le plan d'exécution type | Rejouer avec/sans env | Documenter la variable requise dans le runbook migrations | P3 | Aucune | Doc mise à jour |

### B.5 Intégrations externes (INT)

Niveaux constatés (détail des preuves fichier:ligne dans les sections d'analyse utilisées) :

| ID | Brique | Niveau atteint | Gravité du gap | Statut | Priorité |
|---|---|---|---|---|---|
| INT-001 | OR-Tools CP-SAT | Manifeste ✅ lock ✅ importée ✅ **chemin actif ❌ (aucune route/worker/script)** ; solveur déterministe (workers=1, tie-break stable, time cap 5 s), run audit persisté (migration 0051) mais inertie totale au runtime | Élevé (valeur promise non délivrée) | Confirmé par inspection | P2 |
| INT-002 | RAG/BGE | Activable par double flag, poids locaux only (`local_files_only=True`), hash embeddings vérifié, chunks financiers exclus en double barrière (app + CHECK SQL), filtre version DCE serveur ; **index = JSONB + cosinus Python en mémoire** (pas pgvector/Qdrant, assumé en docstring) ; route non montée par défaut (`knowledge_service=None`) ; Golden DCE absent | Moyen | Confirmé par inspection | P2 |
| INT-003 | Docling/PyMuPDF | Flag unique off par défaut, worker one-shot branché, fallback déterministe pypdf/docx/xlsx garanti ; ⚠️ aucun budget CPU/RAM propre à Docling ; OCR inexistant (PDF scanné → EMPTY_EXTRACTED_TEXT) | Moyen | Confirmé par inspection | P2 |
| INT-004 | S3/MinIO | boto3 lazy, flag off par défaut (filesystem local par défaut), SSE AES256, `IfNoneMatch:"*"` anti-écrasement ; lifecycle/backup bucket absents (backup-preprod.sh ne couvre que volumes locaux+PG) | Moyen | Confirmé par inspection | P2 |
| INT-005 | ClamAV | **Chemin actif principal**, INSTREAM chunké, timeouts configurables, fail-closed prouvé par exécution (readiness `clamav:"failed"` en arrêt du service ; verdict ERROR ⇒ REJECTED+suppression) ; EICAR jamais joué en recette réelle | — (positif) / recette manquante | Confirmé par exécution (panne) | P1 recette |
| INT-006 | BOAMP | Client Explore v2.1 réel (HTTPS imposé, no-follow redirects, texte borné), fingerprints SHA-256, scoring explicable 4 facteurs, dédup contrainte unique + on_conflict_do_nothing, tenant scope ; **ingestion/scoring/persistance = scripts opérateur one-shot seulement**, pas de scheduler, pas de conversion opportunité→Case | Élevé | Confirmé par inspection | P1 |
| INT-007 | INSEE/Sirene | Flag+token runtime obligatoires sinon RuntimeError au boot, GET read-only allowlisté, SIREN validé 9 chiffres, zéro persistance, route montée conditionnelle | — (positif) / recette réelle jamais jouée | Confirmé par inspection | P2 recette |
| INT-008 | Bus externe HMAC | HMAC sha256 canonique, HTTPS+token ≥32 imposés, ack 2xx exigé, lease `skip_locked`, backoff cap 3600 s ; ⚠️ pas de guard SSRF sur `HttpExternalEventBus` (contrairement au webhook), pas de dead-letter (voir DB-003) | Moyen | Confirmé par inspection | P1 |
| INT-009 | SMTP/ICS | SMTP : chaîne complète export→outbox→worker branchée, TLS/STARTTLS paramétrables, destinataire unique env (anti-exfiltration), anti-CRLF ; ICS : RFC 5545 conforme UTC déterministe mais **port mort — `render_deadline` sans appelant** | Faible/Moyen | Confirmé par inspection | P3 |
| INT-010 | Signature électronique | Registre d'intention append-only + callback HMAC ≥32 chars (503 sinon) solides ; **provider = label regex, aucun SDK/appel réseau** ; `external_submission: NOT_PERFORMED` gravé — honnête mais non fonctionnel pour signer | Critique pour la promesse produit | Confirmé par inspection | P1 |
| INT-011 | Playwright/Cypress | **Absents** (package.json : Vitest+Testing Library seulement) ; marqueur pytest `e2e` = parcours API backend, pas navigateur | Moyen | Confirmé par inspection | P2 |

### B.6 Métier BTP (BTP)

Tableau du parcours AO complet (statuts : opérationnelle / partielle / mockée / one-shot opérateur / désactivée par défaut / non codée / non vérifiable) :

| # | Étape | Statut | Preuve principale | Gap majeur |
|---|---|---|---|---|
| 1a | Création affaire | **NON CODÉE (prod)** | Agrégat `case/domain/case.py:234` ; unique instanciation = script démo `demonstrations/m1.py:281` ; aucun `POST /api/v1/cases` sur les 32 routers | **Le cycle ne peut pas démarrer** sans écriture ORM hors produit |
| 1b | Attribution collaborateur | Opérationnelle | `membership/application/patron_assignment.py:75-179` + routes `patron_assignment_management.py:57-167`, cockpit, historique, amend/suspend/end | Bloquée en aval de 1a |
| 2 | Admission DCE + upload + quarantaine + ClamAV | Opérationnelle (code) / non vérifiable en exploitation réelle | Chaîne staging→claim→upload streamé SHA-256→libmagic→clamd INSTREAM→admission CLEAN-only (`upload.py:87-200`, `handlers.py:1069-1221`, `quarantine.py:110-216`) | Jamais de recette EICAR/VPS documentée |
| 3 | Versionnement DCE + doublons | Opérationnelle (code) | Immuabilité + supersession (`dce/domain/dce_version.py:134-293`), unicité corpus_hash par tenant+consultation (`models/dce_version.py:45`) | Pas de diff sémantique rectificatif |
| 4 | Extraction + provenance + classification | Partielle | pypdf locators page/ligne/cellule + bbox PyMuPDF optionnelle ; classification lexicale 9 familles avec preuves offsets (`classification.py:100-161`) ; **runner de classification absent du runtime** ; DC1/DC2/DC4 non classés ; **OCR inexistant** | DCE scannés = impasse ; pièces DC non traitées |
| 5 | Exigences structurées + wizard collaborateur | Opérationnelle (amont one-shot) | Analyse RC 10 règles sourcées, matérialisation PENDING_HUMAN_CONFIRMATION, confirmation humaine RBAC, tâches/bloquants/information requests complets | Orchestration manuelle entre workers ; analyse purement lexicale |
| 6 | Qualifications/Kbis/RIB/readiness | Opérationnelle (périmètre volontairement étroit) | Types INSURANCE\|KBIS\|RIB contraints SQL, vérification humaine append-only, moteur readiness agrégé (`preparation/application/service.py:299-474`) | Pas Qualibat/URSSAF, références sans montants, pas de formulaires DC |
| 7 | Recherche DCE RAG | Partielle / désactivée par défaut | Route conditionnelle non montée par défaut ; cosinus mémoire sur JSONB | Activation, pgvector, poids validés |
| 8 | Croisement CCTP–DPGF–BPU–CCAP | **NON CODÉE** | Grep CCAP = classification lexicale uniquement ; aveu `todo.md:88` | **La promesse centrale d'analyse DCE n'existe pas** |
| 9 | Import pricing XLSX | Opérationnelle (code) | Alias FR, décimales FR, contrôle Qté×PU vs Total, anti zip-bomb, macros rejetées, preview→commit atomique | ClamAV non branché sur cet import (`todo.md:85`) |
| 10 | Scénarios prix/marges/plancher | Partielle (calcul trivial réel) | Entiers centimes, dérivé d'un snapshot PUBLISHED figé, transitions patronales réservées, trigger 0055 ; **grep `pénalit\|retenue\|garantie\|cautionn\|plancher\|deboursé` dans modules/pricing ET backend/app = 0 hit** | Prix plancher, coût de revient par poste, pénalités/RG/cautionnement : rien |
| 11 | Génération dossier de réponse | Partielle (squelette) | Markdown squelette IDs/statuts filtré financier (`document_content.py:25-58`) | Pas de mémoire technique exploitable |
| 12 | Décision GO/NO-GO | Partielle (read-model orphelin) | Domaine riche 495 lignes mais **aucune commande create/finalize au dispatcher** ; seule route lecture `GET /cases/{id}/decision-dossier` ; instanciation démo only | Boucle de décision inutilisable |
| 13 | Signature électronique | Mockée (intention) | Provider = label env, callback HMAC réel, preuves append-only ; aucun provider réel | Contrat fournisseur + credentials + accusé |
| 14 | Export ZIP + audit + dépôt | Partielle | ZIP manifest intègre SHA-256 vérifié, audit téléchargement append-only, webhook durci, SMTP opt-in ; dépôt plateforme explicitement humain (`NOT_PERFORMED`) ; accusé = saisie manuelle hashée | Automatisation PLACE/MPM hors périmètre assumé |
| 15 | Veille BOAMP → opportunité | Partielle / one-shot | Client+scoring+persistence réels mais scripts CLI ; qualification humaine OK ; **aucune conversion observation→Case** (`CaseOriginKind.OPPORTUNITY` inutilisé) | Scheduler + boucle opportunité→affaire |

### B.7 Documentation (DOC)

| ID | Gravité | Divergence | Classification |
|---|---|---|---|
| DOC-001 | Moyen | `docs/PROJECT_STATE.md` (état « actualisation 23 août ») : 862 tests non-DB, couverture 67,45 %, tête 0055, dernier commit `7d91b0a` — réalité mesurée ce jour : **1346 tests, 90,96 %, tête 0056, commit `0eb82a0`** | Obsolète (le document reste par ailleurs remarquablement honnête sur les preuves externes ouvertes : Docker, HTTPS, ClamAV/EICAR, backup, bus — toutes effectivement non prouvées) |
| DOC-002 | Moyen | `todo.md:51,67` traite la couverture comme dette bloquante ouverte (67,x %) alors que `RAPPORT_AUDIT_05_VERIFICATION.md:26` mesure 90,99 % avec DB et que la présente mesure confirme 90,96 % | Contradictoire entre documents, non arbitré |
| DOC-003 | Faible | Affirmation persistante « le renderer ICS n'importe pas icalendar » (`DEPENDENCY_INTEGRATION_STATUS_2026-08-22.md:99,174`, `GLOBAL_REVIEW_REFRESH:51,131`) contredite par `ics_calendar.py:60-65` (import réel + RuntimeError si extra absente) | Fausse (survécu à 3 réconciliations avant correction implicite) |
| DOC-004 | Faible | Comptes frontend divergents : 93 (`DEPENDENCY_INTEGRATION_STATUS:34`), 98 (`GLOBAL_REVIEW_REFRESH:162`), 89 (`RAPPORT_AUDIT_SYSTEME_BTP:111`) — mesure du jour : 98 (run propre) | Historique stratifié non purgé |
| DOC-005 | Faible | 3 rapports racine non trackés git ; `RAPPORT_AUDIT_SYSTEME_BTP.md` racine (23 août, 55 migrations) ≠ copie trackée `docs/operator-reports/` (22 août, 48 migrations) : deux éditions concurrentes du même audit | Non prouvé/partiel — gouvernance documentaire à fiabiliser |
| DOC-006 | Information | Claim CI « runnerName null / steps: [] » (`PROJECT_STATE.md:22`) — **confirmé exact par API GitHub ce jour** (OPS-001) | Exact et toujours d'actualité |

---

## C. Rapport des tests

### C.1 Backend

| Commande | Résultat | Durée |
|---|---|---|
| `uv lock --check` | Resolved 191 packages — lock à jour | <1 s |
| `uv run ruff check backend scripts` | All checks passed | <2 s |
| `uv run pytest -q -m 'not db' backend/tests` | **888 passed**, 458 deselected, 4 warnings (déprécations Starlette uniquement) | 13,34 s |
| `SMART_AO_TEST_DATABASE_URL=postgresql+psycopg://audit:***@127.0.0.1:5437/audit_db uv run --extra calendar pytest -q -m db backend/tests` (PG 16 digest-pinné, conteneur jetable tmpfs) | **458 passed**, 888 deselected | 375,04 s |
| Même URL + `pytest -q backend/tests --cov=app --cov-report=term-missing --cov-fail-under=85.50` | **1346 passed** — TOTAL 15 359 stmts, 90,96 % (> gate 85,50 %) | 629,85 s |

Écart couverture hors-DB vs avec-DB : la mesure hors-DB seule n'a pas été rejouée avec cov ce jour ; les documents historiques la situaient à 67,45 %. Avec DB (configuration du gate CI), la couverture réelle est **90,96 %** : l'écart provient des 458 tests db (triggers, contraintes, concurrence, persistance) qui n'existent qu'en présence PostgreSQL.

### C.2 Frontend

| Commande | Résultat |
|---|---|
| `pnpm install --frozen-lockfile --ignore-scripts` | Already up to date (38 ms) |
| `pnpm test --run` (1er passage post-install) | 16 fichiers / 72 tests passés + **7 erreurs non gérées → échec de suite** (environment 262 s) — voir OPS-005 |
| `pnpm test --run` (2e passage) | **23 fichiers / 98 tests passés, 0 erreur** (21,30 s) |
| `pnpm typecheck` | tsc -b sans erreur |
| `pnpm lint` | 0 erreur, 2 warnings (`react-hooks/exhaustive-deps` sur `App.tsx:202,211`) |
| `pnpm build` | ✓ 38 modules — index 0,53 kB ; CSS 28,59 kB (6,25 gz) ; JS 294,03 kB (**82,95 kB gzip**) en 498 ms |

### C.3 Scripts & configuration

- `bash -n ops/*.sh scripts/*.sh` → syntaxe OK.
- `docker compose -f docker-compose.yml config --quiet` → valide.
- `docker compose -f ops/docker-compose.preprod.yml config --quiet` → échoue sans secrets (design `${VAR:?required}` fail-fast, conforme) ; **valide** une fois 8 variables synthétiques fournies.

### C.4 Alembic offline

```
uv run alembic -c backend/alembic.ini upgrade head --sql
  → Exception: Connection, url, or dialect_name is required.   (sans env)
SMART_AO_DATABASE_URL=postgresql+psycopg://u:p@localhost/d uv run alembic -c backend/alembic.ini upgrade head --sql
  → 3 830 lignes SQL, 97 CREATE TABLE                            (avec env)
```

### C.5 CI distante (API GitHub, lecture seule)

- `GET /actions/runs?per_page=100` pages 1-5 → 437 runs ; 60 plus récents : `{failure: 60}`.
- Run 32714197692 (2026-08-24T09:56Z) : jobs backend/frontend/image-security → `conclusion: failure`, `runner_name: ""`, `steps: []`.
- Dernier succès : run `32513616360` — 2026-08-21T18:29Z, branche `fix/pricing-normalized-line-validation-27`.

---

## D. Rapport Docker/PostgreSQL

### D.1 Ce qui a été démarré et observé (par exécution)

Séquence réelle sur `docker-compose.yml` (dev) avec override externe de port hôte (5432 occupé par une autre stack du développeur — non touchée) :

1. `docker compose up -d postgres clamav migrate backend dce-retention-worker` :
   - première tentative : **échec binding 5432** (preuve OPS-003) ;
   - seconde tentative (override `127.0.0.1:15432:5432`) : succès.
2. État après 45 s :
   - `smart_ao_v8-postgres-1` : **healthy** (postgres:16-alpine@sha256:cf78e766…)
   - `smart_ao_v8-clamav-1` : **healthy** (clamav/clamav:1.4_base@sha256:1b6920e8…)
   - `smart_ao_v8-migrate-1` : Exited **exitcode=0**, logs : upgrades successifs 0052→0053→0054→0055→**0056**
   - `smart_ao_v8-backend-1` : **Up (healthy)**, port `127.0.0.1:8000`
   - `smart_ao_v8-dce-retention-worker-1` : Up, logs vides (poll silencieux)
3. Healthchecks :
   - `curl http://127.0.0.1:8000/healthz/live` → `{"status":"ok","checks":{"process":"ok"}}`
   - `curl http://127.0.0.1:8000/healthz/ready` → `{"status":"ok","checks":{"database":"ok","clamav":"ok"}}`
4. **Test de panne ClamAV** : `docker stop clamav` → 20 s → ready = `{"status":"not_ready","checks":{"database":"ok","clamav":"failed"}}` ; redémarrage → retour 200. **Readiness fail-closed prouvée par exécution.**
5. Réseau : single network bridge `smart_ao_v8_default` (la séparation internal/edge n'existe que dans `ops/docker-compose.preprod.yml:392-400`, non démarrée).
6. Images : construites localement (backend/worker `sha256:24125d5e…` pour l'image worker), bases digest-pinnées vérifiées dans le YAML.

### D.2 Tests PostgreSQL directs (stack dev, transaction ROLLBACK — zéro trace résiduelle)

- Triggers présents : `pricing_scenarios_append_only`, `patron_actions_append_only` (via `pg_trigger`).
- Chaîne FK minimale insérée (tenants→cases→financial_report_snapshots→pricing_scenarios) puis :
  - `UPDATE pricing_scenarios SET state='ARCHIVED' …` → **ERROR: pricing scenarios are immutable; use pricing scenario transitions** ✔
  - `DELETE` non atteint (transaction abortée) ; couverture DELETE assurée par la définition du trigger (`BEFORE DELETE OR UPDATE`, confirmée par `pg_get_triggerdef`) — **partiellement confirmé par exécution, confirmé par inspection pour DELETE**.
- `ROLLBACK` final : `pricing_rows=0` re-vérifié, aucune trace.

### D.3 Base isolée jetable (tests DB)

- Conteneur `audit-pg-isolated` (postgres@sha256:cf78e766…, tmpfs 1 Go, port 5437) créé pour les 458 tests db + suite coverage, puis **supprimé** après usage.
- Conftest : migrations `upgrade head`/`downgrade base` exécutées par pytest contre cette base uniquement. La base PostgreSQL du développeur n'a jamais reçu les tests.

### D.4 Ce qui n'a PAS été fait et pourquoi

| Action | Raison |
|---|---|
| Stack preprod (`ops/docker-compose.preprod.yml up`) | Exigerait des secrets réels fournis par l'opérateur et exposerait des services ; le prompt l'autorise avec secrets synthétiques mais la recette complète HTTPS/Caddy n'était pas l'objet minimal demandé ; classée NON VÉRIFIABLE |
| Scan Trivy/Grype des images locales | Binaires Trivy/Grype absents de l'environnement ; la CI (job image-security) n'a jamais exécuté ses steps (OPS-001) → **non vérifiable** |
| EICAR contre ClamAV | Possible techniquement (service healthy) mais non exécuté pour rester strictement dans un périmètre non-destructif du volume clamav partagé ; recette à jouer en préprod dédiée |
| Benchmark/charge (ZIP, XLSX volumineux, contention PG) | Corpus représentatif BTP indisponible ; tout chiffre aurait été non représentatif — classé NON VÉRIFIABLE conformément au prompt |
| Diagnostic du crash `dce-retention-worker` (OPS-002) | Conteneur et logs supprimés par un processus externe avant capture |
| Merge/relance de workflows GitHub | Interdit par le prompt (lecture seule, jamais relancer un workflow qui attend un runner) |

---

## E. Verdict de maturité

### E.1 Verdicts par axe

| Axe | Verdict |
|---|---|
| Architecture | **GO conditionnel** (condition : réduire ARCH-001 par tranches, test architecture étendu) |
| Backend/API | **GO conditionnel** |
| Données/PostgreSQL | **GO conditionnel** (chaîne + append-only prouvés ; dead-letter/rétention outbox à traiter) |
| Sécurité | **GO conditionnel** (P0 SEC-001 + SEC-004 ; MFA à implémenter ou retirer des discours) |
| Frontend | **GO conditionnel** |
| Docker/CI/Ops | **NO-GO** (CI morte 3 jours+, préprod jamais recettée) |
| Intégrations externes | **NON VÉRIFIABLE** (aucune recette fournisseur réelle disponible) |
| Métier BTP | **NO-GO** (pas de point d'entrée produit ; moteurs de valeur absents) |
| Observabilité/Performance | **GO conditionnel** (healthchecks prouvés ; performance NON VÉRIFIABLE) |
| Documentation/Gouvernance | **GO conditionnel** |

### E.2 Cinq risques pouvant causer perte de données ou fuite tenant

1. **SEC-001** — PAT GitHub dans l'URL remote : prise de contrôle potentielle du repo (force-push, fuite d'historique contenant des données DCE privées si jamais commités).
2. **SEC-004** — SSRF webhook via redirections : pivot réseau depuis le worker vers services internes.
3. **DB-003** — Absence de dead-letter + outbox `cockpit_projection` sans consumer ni purge : croissance disque non bornée → saturation → indisponibilité/perte PostgreSQL.
4. **OPS-001** — CI morte : régressions (y compris sur l'isolation tenant) peuvent merger sans aucun filet automatisé.
5. **SEC-003** — Rate limiting process-local : brute force multi-réplicas sur login si scale-out, et absence de limite sur endpoints coûteux (DoS indirect des données).

### E.3 Cinq risques empêchant une mise en production

1. CI sans étapes exécutées depuis le 21/08 (OPS-001) : aucun verdict automatisé possible.
2. PR #49 non fusionnée et non validée ; `main` en retard de ~15 commits de remédiation non éprouvés en CI.
3. Préprod jamais recettée : HTTPS/Caddy, EICAR ClamAV, backup hors hôte + restauration isolée — tous déclarés ouverts et effectivement non prouvés.
4. Produit sans `POST /cases` : aucun utilisateur réel ne peut démarrer le cycle (BTP-1a).
5. MFA/step-up annoncé mais inexistant (SEC-002) : écart contractuel de sécurité si vendu SaaS B2B.

### E.4 Cinq fonctionnalités métier à plus forte valeur

1. Slice **CreateCase** (handler + `POST /api/v1/cases` + conversion opportunité BOAMP→Case) — débloque les 14 autres étapes.
2. **COST-BASIS** : coût de revient par poste, frais généraux, déboursé sec, prix plancher, simulation pénalités/retenue de garantie/cautionnement (centimes entiers, ancré au snapshot publié existant).
3. **CCAP-RISK** : lecture clause par clause (pénalités, garanties, assurances, responsabilités) avec traçabilité source page/section — même lexical v0, avec confirmation humaine.
4. Croisement **CCTP–DPGF–BPU–CCAP** (incohérences quantités/unités/lots) — la promesse d'analyse DCE.
5. Boucle **décision GO/NO-GO finalisable + signature provider réel** (contrat, credentials, accusé, preuves).

### E.5 Corrections immédiates (P0/P1)

1. Révoquer/régénérer le token GitHub et nettoyer l'URL remote (SEC-001).
2. Rétablir les runners CI, ajouter `permissions: contents: read`, `timeout-minutes`, `concurrency` (OPS-001/OPS-004), puis faire exécuter une CI complète sur la branche courante **avant** toute fusion PR #49.
3. Webhook : désactiver le suivi de redirections ou re-valider chaque hop (SEC-004).
4. Dead-letter policy + rétention outbox + décision sur `cockpit_projection` (DB-003).
5. Corriger `capabilities_for` pour PATRON_DELEGATE ou retirer le rôle (SEC-005).

### E.6 Corrections à NE PAS faire à l'aveugle

1. Ne pas « réparer » ARCH-001 en une passe massive : les lectures directes `sa.select(Record)` sont entremêlées avec l'idempotence et la révision optimiste ; migrer par module avec tests concurrency/db.
2. Ne pas activer simultanément tous les flags externes en préprod (RAG, Docling, S3, bus, BOAMP) : un incident serait attribuable à personne ; activer un par un avec recette.
3. Ne pas introduire pgvector avant mesure (la docstring du code l'exige explicitement) : le full-scan JSONB peut suffire au volume actuel.
4. Ne pas assouplir `--cov-fail-under=85.50` ni ajouter d'exclusions pour verdir quoi que ce soit.
5. Ne pas câbler OR-Tools « vite fait » sur une route : définir d'abord le cas d'usage capacité (scope Case/tenant, entrées humaines) sinon ce sera un solver décoratif.

### E.7 Preuves nécessaires avant vente à un client

1. Run CI vert **avec steps exécutés** + artefacts de coverage sur le commit de vente.
2. Recette VPS documentée : HTTPS Caddy réel, EICAR détecté, backup hors hôte + **restauration isolée réussie** (rapport horodaté).
3. Parcours réel sur un DCE anonymisé (corpus Golden) : upload → extraction → exigences → readiness → pricing → export ZIP, avec mesures.
4. Appels réels contrôlés : BOAMP (limites/fingerprints), INSEE (token runtime), SMTP (délivrabilité), S3 (SSE/non-écrasement).
5. Contrat + intégration signature électronique qualifiée avec vérification webhook en conditions réelles.
6. Pentest externe couvrant auth/tenant isolation/uploads/webhooks.

### E.8 Séquence de développement recommandée

1. **Semaine 1** : SEC-001, OPS-001 (CI), SEC-004, OPS-004 (permissions/digest/SARIF) ; fusion PR #49 après CI verte.
2. **Semaine 2** : CreateCase slice HTTP (+ tests e2e API) ; conversion opportunité→Case minimale.
3. **Semaines 3-4** : COST-BASIS v1 (prix plancher + pénalités/RG/cautionnement sur snapshot publié) ; doc-gen dossier de réponse enrichi.
4. **Semaines 5-6** : CCAP-RISK lexical v0 + croisement CCTP-DPGF-BPU-CCAP v0 (confirmation humaine obligatoire) ; runner classification branché ; OCR (tesseract/Docling OCR) pour DCE scannés.
5. **Semaine 7** : boucle décision (create/finalize commands) + intégration signature provider réel.
6. **Semaine 8** : recettes externes complètes (BOAMP scheduler, INSEE, SMTP, S3, backup/restore drill), Playwright E2E navigateur sur le parcours critique.
7. **En parallèle continu** : ARCH-001 par tranches (membership d'abord), DB-003, SEC-002 (MFA) avant tout contrat commercial mentionnant le step-up.

### E.9 Conclusion attendue (reprise du prompt)

- **Prouvé** : socle FastAPI/PostgreSQL exécuté de bout en bout localement (1346 tests, 90,96 % cov, migrations online jusqu'à 0056, trigger append-only rejetant un UPDATE direct, readiness fail-closed en panne ClamAV), discipline sécurité réelle (Argon2id, JWT kid/rotation, refresh anti-rejeu, quarantaine fail-closed, 404 anti-énumération), domaine pur sans framework.
- **Seulement codé** : OR-Tools (déconnecté du runtime), ICS (port mort), décision GO/NO-GO (read-model orphelin), MFA/step-up (schéma sans cérémonie), signature (registre d'intention).
- **Incomplet** : création d'affaire, croisement CCTP-DPGF-BPU-CCAP, coût de revient/prix plancher/pénalités, OCR, DC1/DC2/DC4, mémoire technique, BOAMP scheduler.
- **Faux ou obsolète** : PROJECT_STATE (862 tests/67,45 %/0055), claim ICS-sans-icalendar, comptes de tests divergents, todo.md couverture.
- **Non vérifiable** : toutes les intégrations fournisseurs réelles, préprod/HTTPS/backup/restore, performance/charge, pentest, et la cause du crash du retention worker (logs perdus).
- **Risques bloquants** : token GitHub exposé, CI morte, SSRF redirect, outbox sans dead-letter, produit sans point d'entrée Case.
- **Ordre des travaux** : voir E.8 — sécuriser la chaîne de validation (P0), débloquer le flux métier (CreateCase), livrer la valeur chiffrage BTP (COST-BASIS puis CCAP-RISK), recetter les externes, alors seulement envisager un pilote client.

---

*Audit réalisé sans modification du dépôt (git working tree intact hors fichiers préexistants non trackés). Toutes les commandes citées ont été exécutées le 2026-08-24 dans l'environnement décrit en section 0 ; les sorties brutes sont reproduites dans les sections C et D.*
