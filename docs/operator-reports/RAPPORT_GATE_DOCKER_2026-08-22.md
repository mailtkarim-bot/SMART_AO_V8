# 🐳 RAPPORT DE GATE DOCKER — Exécution réelle du 22 août 2026

**Branche :** `audit/consolidated-remediation` (base `origin/docs/pricing-http-next-lot-28` @ `8e840a3`)
**Contexte :** le contre-rapport consolidé et l'audit système BTP s'accordaient sur un point — aucun build Compose, EICAR ou healthcheck réel n'avait jamais été exécuté (« NO-GO » auto-déclaré). Ce gate a maintenant été **exécuté sur une machine dotée de Docker** (29.1.3 + Compose v5.5.0).

## 1. Résultats du gate

| # | Contrôle | Résultat | Preuve |
|---|---|---|---|
| 1 | Build image backend (digest-pinnée, non-root) | ✅ PASS | `docker compose build backend` → `24125d5efd29`, reconstruite après scoping dockerignore → `c38c48b7aacd` |
| 2 | Build image frontend | ✅ PASS **après correctif** | Échouait : `.dockerignore` racine excluait `web/` pour tous les builds (régression introduite par l'endurcissement, jamais détectée faute de build). Corrigé via dockerignore par-Dockerfile → `2366263569ed` |
| 3 | Validation `compose config` preprod | ✅ PASS | `docker compose -f ops/docker-compose.preprod.yml config --quiet` vert avec allowlist d'environnement complète |
| 4 | Stack dev complète up + healthy | ✅ PASS | postgres/clamav/backend *healthy*, retention-worker actif ; zéro erreur logs sur 10 min |
| 5 | Migrations Alembic sur la base Dockerisée | ✅ PASS | `upgrade head` → `20260822_0049` (trigger immutabilité snapshots financiers inclus) |
| 6 | Healthchecks JSON applicatifs | ✅ PASS | `/healthz/ready` 200 `{"database":"ok","clamav":"ok"}` ; `/healthz/live` 200 |
| 7 | **Egress ClamAV (C-02)** | ✅ PASS **preuve directe** | Logs clamd : `daily.cvd version 28100, sigs: 355621` téléchargées via réseau `edge` ajouté |
| 8 | **Détection EICAR INSTREAM (fail-closed)** | ✅ PASS | Depuis le conteneur backend, protocole `zINSTREAM` réel : clean → `stream: OK` ; EICAR → `stream: Eicar-Test-Signature FOUND` |
| 9 | Flux d'authentification HTTP complet | ✅ PASS | Provisionnement tenant+patron (administration locale) → `POST /api/v1/auth/login` 200 (Argon2id + JWT ≥32 chars) → `GET /api/v1/cases/assigned` 200 `[]` avec Bearer |
| 10 | Worker rétention opérationnel post-migrations | ✅ PASS | Boucle SKIP LOCKED active sans erreur |

## 2. Défauts trouvés et corrigés pendant le gate (la valeur du test réel)

| Défaut | Cause racine | Correctif appliqué |
|---|---|---|
| Backend crash au démarrage (`SMART_AO_JWT_SIGNING_KEY` manquant) | Le compose dev n'a jamais été exécuté ; le bootstrap exige les 3 variables JWT | Valeurs de dev par défaut dans `docker-compose.yml` (surchargeables par `.env`) |
| Clé JWT < 32 caractères rejetée | Seuil de sécurité non anticipé dans les défauts dev | Défaut dev allongé (`…change-me-0123456789`) |
| **Image frontend inconstruisible** | `.dockerignore` racine exclut `web/` pour tous les contextes de build | Split en `ops/docker/*.Dockerfile.dockerignore` par-Dockerfile + contrat ops mis à jour (`test_backend_docker_context_excludes_demonstrations_and_tests`) qui interdit désormais toute régression (root ignore ne doit plus contenir `web/`) |
| Port hôte 5432 occupé par la base V7 legacy | Environnement local partagé | `compose.local-dev.yml` (override `!override` ports 5433→5432), V7 intact |
| Worker crash faute de schéma | Migrations jamais jouées sur base fraîche avant workers | Séquence documentée : `migrate` avant `up` des workers |

## 3. Correctifs audit intégrés à ce lot (tests verts)

- **C-02/C-03** — egress : `clamav` et `submission-export-webhook-worker` rejoignent `internal + edge` dans `ops/docker-compose.preprod.yml` (commentaires in-file, aucun port publié).
- **H-03** — `patron_pricing_import.py` : lecture par chunks de 1 MiB, rejet `413 IMPORT_FILE_TOO_LARGE` au-delà de `MAX_UPLOAD_BYTES` **avant** tout buffering ; nouveau test route (service jamais appelé).
- **H-09** — `App.tsx` : les trois `catch` muets affichent désormais l'erreur (bannière) ; le 404 « pas encore de dossier de décision » reste silencieux (état normal). 3 tests de régression ajoutés (`App.test.tsx`).

## 4. Certification locale finale

| Suite | Résultat |
|---|---|
| Backend pytest complet (127 fichiers) | **1 072 passed**, 7 warnings tiers, ~7 min 47 |
| Frontend Vitest | **68 passed / 68** (65 préexistants + 3 nouveaux) |
| Build frontend (`tsc -b && vite build`) | Vert |
| Ruff | Vert |

## 5. Ce qui reste ouvert (honnêteté d'gate)

1. **HTTPS/ACME réel + domaine public** : Caddy validé en config seulement ; Let's Encrypt exige un hôte joignable publiquement.
2. **Webhook sortant** : l'egress est ouvert côté réseau ; il faut un récepteur HTTPS externe de test pour un aller-retour signé HMAC complet.
3. **Charge/concurrence** (10→100 utilisateurs, courses SKIP LOCKED multi-workers) : scripts prêts (`scripts/run_vps_load_campaign.py`), à jouer sur le VPS cible.
4. **Lots métier structurants** (non prétendus résolus par quiconque) : OCR DCE scannés, analyse clauses CCAP/CCTP, import coût de revient + BT01, surfaces HTTP Decision/Case en écriture, auth navigateur complète (cookies déjà câblés côté backend).
