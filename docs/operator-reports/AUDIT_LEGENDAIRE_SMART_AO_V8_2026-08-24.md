# Rapport d'audit légendaire — SMART_AO V8

> **Auditeur** : ox-alpha (audit indépendant, sans complaisance, sans preuve fabriquée)
> **Date** : 2026-08-24 · **Prompt suivi** : `Prompt d'audit légendaire — SMART_AO V8.md`
> **Audit précédent** : `docs/operator-reports/AUDIT_EXHAUSTIF_SMART_AO_V8_2026-08-24.md` (commit `0eb82a0`)
> **Mode** : lecture seule du dépôt ; recettes destructrices uniquement sur conteneurs/bases isolés jetables ; volumes Compose du développeur préservés ; tests de triggers en transaction ROLLBACK.

---

## 0. Identité exacte de la version auditée

| Élément | Valeur | Preuve |
|---|---|---|
| Dépôt / propriétaire | `github.com/mailtkarim-bot/SMART_AO_V8` | `git remote -v` |
| Commit audité | **`33986fb58e382a36b623055b7a0a3033f5c51ac3`** (« docs: reconcile exhaustive audit findings ») — conforme au commit attendu | `git rev-parse HEAD` |
| Branche | `docs/pricing-http-next-lot-28` (trackée sur origin, plus de HEAD détaché) | `git branch --show-current` |
| 2 nouveaux commits depuis l'audit exhaustif | `cc9726c fix: apply exhaustive audit remediations` (+1251/−4243) puis `33986fb docs:` — le commit de remédiation répond aux findings de l'audit ox-alpha du 24/08 matin | `git log --oneline -3`, `git diff --stat 0eb82a0..33986fb` |
| `origin/main` | `970c9ff` (PR #48) — PR #49 toujours non fusionnée, en retard de 358 fichiers / +30 674 lignes sur la branche | `git rev-parse origin/main`, `git diff --stat origin/main...HEAD` |
| Working tree | Propre hors non-trackés : prompt légendaire, `RAPPORT_AUDIT_0{4,5}…`, `RAPPORT_AUDIT_SYSTEME_BTP.md`, `rapports/` | `git status --short` |
| Outils | Python 3.12.3, Node v22.23.1, pnpm 11.21.0, uv 0.11.21, Docker 29.1.3, Compose v5.5.0 | exécution locale |

⚠️ **SEC-001 toujours ouvert dans CE clone** : l'URL du remote embarque encore un credential GitHub (`https://<token>@github.com/…`). Le rapport de réconciliation des devs indique que *leur* clone est propre — exact, mais le clone d'audit conserve le PAT et **la révocation du token n'est pas prouvée** (action propriétaire GitHub, non vérifiable ici).

---

## A. Résumé exécutif

### Verdict global : **NO-GO**

Le lot `cc9726c` est une **réponse sérieuse, honnête et techniquement correcte** à l'audit exhaustif : création d'affaire livrée côté backend via ports, durcissement SSRF webhook+bus, headers de sécurité backend (vérifiés live), dead-letter bornée, alignement des limites upload, Compose paramétrable, CI durcie statiquement, baseline secrets nettoyée (585→10 entrées). La réconciliation documentaire distingue correctement preuves externes (auditeur) et validations locales (sandbox devs).

Mais ce verdict reste NO-GO parce que :

1. **La suite backend est ROUGE au commit audité** : `test_dev_compose_is_loopback_bound_and_not_repurposable_as_preprod` échoue (905 passés / **1 failed**, et 1363/1 sur la suite complète avec DB). La réconciliation des devs affirme « 906 tests backend hors db **passent** » — c'est **faux** à `33986fb`. Preuve directe du coût de la CI morte : ce test de contrat aurait dû être mis à jour avec le Compose.
2. **La CI n'a toujours exécuté aucune étape** — y compris pour le commit de remédiation lui-même (run `32728988801` du 24/08 12:47Z : failure, `runner_name=""`, jobs sans steps).
3. **Le démarrage à froid du stack dev est cassé** : rebuild des images → crash uvicorn « development JWT signing key is forbidden in production ». Le quickstart documenté (`cp .env.example .env; make up`) ne fonctionne pas tel quel.

### Trois principaux risques de fuite/perte de données

1. **SEC-001** — PAT actif dans l'URL remote de ce clone : si divulgué (capture, log, script), prise de contrôle du repo possible ; révocation non prouvée.
2. **Outbox `cockpit_projection`** — toujours produit massivement sans consumer, sans contrat, sans rétention ni alerte FAILED (DB-003 partiellement traité seulement) → croissance disque non bornée.
3. **CI sans étapes** — toute régression d'isolation tenant ou d'idempotence peut merger sans filet automatisé ; la régression réelle trouvée cette session le démontre.

### Trois principaux blocages production

1. Runners GitHub jamais attribués → aucun verdict CI valide depuis le 21/08, remédiations comprises.
2. Images reconstruites ≠ stack observée saine : crash cold-start dev (voir OPS-NEW-002) et préprod jamais recettée (HTTPS/EICAR/backup-restauration).
3. Écart promesse/sécurité : MFA/step-up toujours inopérant (SEC-002), rate limiting process-local (SEC-003) — interdits de promesse commerciale en l'état.

### Trois fonctionnalités métier à plus forte valeur restant à coder

1. **COST-BASIS** : coût de revient par poste, frais généraux, déboursé sec, prix plancher, pénalités/retenue de garantie/cautionnement (grep métier = toujours 0 hit dans `backend/app`).
2. **CCAP-RISK + croisement CCTP–DPGF–BPU–CCAP** : aucune lecture clause, aucune cohérence croisée entre pièces.
3. **Finalisation décision GO/conditionnel/NO-GO + signature provider réel + OCR + génération DC1/DC2/DC4** (décision encore sans commande create/finalize ; OCR toujours inexistant).

---

## B. Matrice exhaustive des findings

Conventions : statuts conformes au prompt. Les IDs de l'audit précédent sont conservés quand l'observation est la même (traçabilité inter-audits) ; les nouveautés reçoivent des IDs `-L` (légendaire).

| ID | Axe | Gravité | Statut | Fichier/ligne | Preuve exacte | Impact | Reproduction | Correction proposée | Risque de régression | Validation attendue |
|---|---|---|---|---|---|---|---|---|---|---|
| OPS-L-001 | Ops/CI | **Élevé** | **Confirmé par exécution** | `backend/tests/ops/test_preprod_ops_contract.py:154` vs `docker-compose.yml:18` | `pytest -m 'not db'` → **1 failed, 905 passed** ; assertion `'127.0.0.1:5432:5432' in compose` échoue car le mapping est devenu `127.0.0.1:${SMART_AO_POSTGRES_HOST_PORT:-5432}:5432`. Suite complète DB : 1363 passed / 1 failed, cov 90,95 % | Suite rouge au HEAD ; contredit la réconciliation (« 906 passent ») ; prouve que la CI morte laisse passer des régressions triviales | `uv run pytest -q -m 'not db' backend/tests` | Mettre à jour le test pour accepter le paramètre tout en exigeant le préfixe loopback (`127.0.0.1:${SMART_AO_POSTGRES_HOST_PORT:-5432}:`) | Faible — test de contrat uniquement | Suite verte 906/906 puis run CI avec steps verts |
| OPS-L-002 | Ops/Docker | **Élevé** | **Confirmé par exécution** | `ops/docker/backend.Dockerfile:51` (`CMD uvicorn app.bootstrap.production:app`) × `docker-compose.yml:45` (défaut `dev-only-signing-key-change-me-0123456789`) × `bootstrap/production.py:26-29` | Rebuild images puis `up` → conteneur backend **Exited(1)** : `RuntimeError: development JWT signing key is forbidden in production`. Avec `SMART_AO_JWT_SIGNING_KEY=<clé ≥32 chars>` exportée → healthy | Le quickstart documenté (README : `cp .env.example .env; make up`) échoue à froid ; `.env.example` ne définit même pas `SMART_AO_JWT_SIGNING_KEY`. Note honnête : l'observation « stack saine 41 h » de l'audit précédent reposait sur des images périmées pré-durcissement — corrige l'interprétation antérieure | `docker compose build && SMART_AO_POSTGRES_HOST_PORT=15432 docker compose up -d` (sans clé exportée) → crash ; avec clé → healthy | Ajouter `SMART_AO_JWT_SIGNING_KEY` au `.env.example` avec une valeur dev valide non préfixée `dev-only-` ET/OU un entrypoint dev dédié qui construit `create_app()` development ; documenter dans README | Un entrypoint dual mal fait pourrait affaiblir la garde prod — garder `_required()` intacte pour la prod | `make up` fonctionne à froid sans variable exportée ; garde prod toujours testée |
| SEC-001 | Sécurité | Critique | Confirmé par inspection (partiellement remédié) | URL remote de ce clone | `git remote -v` montre `https://<credential>@github.com/…` ; réconciliation devs : leur clone est sain, révocation = action propriétaire | Vol de credential → takeover repo | `git remote get-url origin` | Nettoyer ce clone (`git remote set-url origin https://github.com/mailtkarim-bot/SMART_AO_V8.git`) + **prouver la révocation** (Security log GitHub) | Aucune | Remote sans credential + ancien token refusé par l'API |
| OPS-001 | Ops/CI | **Bloquant** | Confirmé par exécution | API GitHub runs | Run `32728988801` (12:47Z, SHA `33986fb`) : failure, runner `None`, jobs backend/frontend/image-security sans steps. Total 438 runs ; dernier succès toujours `32513616360` (21/08) | Remédiations non validées par CI ; SARIF/permissions/concurrency ajoutés **statiquement mais jamais exécutés** | API `/actions/runs?per_page=15` | Résoudre provisioning runner (billing/org/self-hosted), relancer UNE fois, vérifier steps+artifacts+SARIF | — | Run avec steps exécutés et conclusions lisibles sur `33986fb`+ |
| ARCH-001 | Architecture | Élevé | Confirmé par inspection (inchangé, assumé) | 64 arêtes application→infrastructure (AST rejoué ce jour, liste complète conservée) | AST : mêmes arêtes qu'à `0eb82a0` (membership→{case,dce,enterprise,pricing}, submission→{enterprise,preparation,pricing}, etc.) ; **le nouveau slice Case n'en ajoute aucune** (`case/application/handlers.py` passe par `CaseRepository`/`ConsultationReferenceReader`) ; seul ajout : import type-only `sqlalchemy.orm.Session` (handlers.py:10), cohérent avec le pattern dispatcher existant | Dette structurelle inchangée ; lectures court-circuitant les ports | Script AST (annexe journal C) | Refactor par bounded context (plan réconciliation étape 6) | Idempotence/concurrence — procéder par tranches testées DB | Test architecture interdisant nouvelle arête non-port |
| BTP-L-001 | Métier | — (positif) | **Confirmé par exécution (tests)** | `routes/case_creation.py` (131 lignes), `case/application/{commands,handlers,ports}.py`, `case/infrastructure/repositories.py`, montée inconditionnelle `bootstrap/application.py:913` | `POST /api/v1/cases` : capability `CASE_CREATE` (catalogue fermé, patron admin uniquement — capabilities.py:67), case_id déterministe `uuid5(idempotency_key)`, vérification Consultation tenant+révision exacte, refus `DUPLICATE_FUNCTIONAL_IDENTITY`, événement sparse non financier `CASE_CREATED`; tests API (167 l.) couvrant rejeu 200 / refus non-patron 403 / conflit idempotence 409 / scope invalide 422 | Le point d'entrée produit existe enfin côté backend ; il reste l'écran frontend et la recette PostgreSQL online | Tests : `backend/tests/api/test_case_creation_api.py`, `backend/tests/application/test_case_creation.py` (passent) | Écran frontend + E2E navigateur + validation DB online (étapes 2-3 du plan devs) | — | Parcours complet navigateur contre API réelle |
| SEC-006-L | Sécurité | — (remédié) | **Confirmé par exécution** | `platform/security/headers.py`, montage `bootstrap/application.py:638` | Live après rebuild : `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: no-referrer`, `permissions-policy: camera=(), geolocation=(), microphone=()`, `cross-origin-resource-policy: same-origin` | Defense-in-depth backend acquise (hors HSTS/CSP = edge, choix raisonnable) | `curl -I http://127.0.0.1:8000/healthz/live` après build courant | — | — | — |
| SEC-004-L | Sécurité | Moyen résiduel | Partiellement confirmé (corrigé + TOCTOU assumé) | `platform/security/public_http.py:23-56`, branché webhook (`workers/submission_export_webhook.py`) et bus (`external_bus.py:86`) | HTTPS imposé, credentials/fragments refusés, DNS toutes réponses filtrées (private/loopback/link-local/multicast/reserved/unspecified), redirections levées via opener dédié ; devs reconnaissent la fenêtre TOCTOU DNS non éliminée | Pivot interne via redirect supprimé ; reste DNS rebinding théorique entre validation et connexion | Tests `tests/security/test_public_http.py` (47 l., passent) ; recette réseau réelle externe | Épingler l'IP validée pour la connexion si exigence renforcée | Compat providers multi-A/CNAME | Recette réseau avec provider réel |
| DB-003-L | Données/Ops | Moyen résiduel | Partiellement confirmé | `platform/events/retry_policy.py` (max 10, plafond config 100, backoff min(30·2ⁿ⁻¹,3600), terminal `FAILED` sans `next_attempt_at`) branché sur retention/webhook/smtp/bus (compose preprod : `SMART_AO_OUTBOX_MAX_ATTEMPTS`) | Tests unitaires `tests/platform/test_retry_policy.py` passent ; **pas de simulation live de message empoisonné ni d'alerte FAILED jouées** ; `cockpit_projection` toujours sans consumer/contrat/rétention | Poison messages désormais bornés (fini retry infini) ; visibilité/alerte des FAILED et croissance outbox restent ouvertes | Inspection + tests unitaires ; simulation runtime non exécutée cette session | Alerte métrique sur FAILED + job rétention outbox + décision contrat cockpit_projection | Purge mal calibrée → perte diagnostic | Test intégration poison→FAILED + métrique exposée |
| SEC-002 | Sécurité | Moyen | Confirmé par inspection (ouvert, assumé) | inchangé (`models.py:842-919`, `authentication.py:338-344`) | Pas de cérémonie TOTP ; devs classent P1 avant toute activation commerciale | Step-up inopérant ; interdit de promettre MFA | — | Slice MFA dédié (étape 4 plan devs) | — | Enrôlement→vérification→step-up testés |
| SEC-003 | Sécurité | Moyen | Confirmé par inspection (ouvert) | `rate_limit.py` inchangé | Process-local, login/refresh uniquement ; plan store partagé reporté à juste titre (pas de Redis spéculatif) | Multi-réplicas non sûr | — | Store partagé avant scale-out | — | Test multi-instance 429 |
| OPS-005 | Frontend/Ops | Faible | Non reproduit cette session | Vitest | 1er run de cette session : **23 fichiers / 98 tests, 0 erreur, 9,21 s** (run unique propre ; les 10 runs consécutifs demandés n'ont pas été faits) | Instabilité antérieure non reproduite ; surveillance maintenue | `pnpm test --run` | Fixer concurrence workers si reproduit | — | 10 runs consécutifs propres |
| DOC-L-001 | Documentation | Moyen | Confirmé par inspection | `rapports/Réconciliation…md` §1 ligne 12 | Claim « **906 tests backend hors marqueur db passent** » — faux au commit audité (905+1 failed, voir OPS-L-001) ; les autres mesures locales annoncées (frontend 98, typecheck/lint/build, lock, ruff, mypy ciblé, baseline, alembic offline) sont **exactes et reproduites** cette session | Une affirmation de vert est contredite par l'exécution ; le reste de la réconciliation est fiable et honnête (verdict NO-GO maintenu, preuves externes/non-locales bien séparées) | Rejouer la suite | Corriger la phrase + publier le fix test | — | Réconciliation corrigée + suite verte |
| INT-* (toutes briques) | Intégrations | — | Non vérifiable | inchangé | Aucune brique activée par défaut ; aucun fournisseur réel appelé ; OR-Tools toujours hors runtime ; ICS toujours port mort ; signature toujours intention ; Playwright absent | Identique audit précédent | — | Recettes dédiées par brique (étape 8 plan devs) | — | Rapports de recette horodatés |
| BTP-2…15 | Métier | Bloquant produit | Confirmé par inspection (inchangé) | grep `pénalit\|retenue\|cautionn\|plancher\|deboursé` = 0 hit ; CCAP lexical seulement ; OCR absent ; DC1/DC2/DC4 absents ; décision sans commande finalize | Mêmes constats qu'à `0eb82a0`, sauf étape 1a désormais codée (BTP-L-001) | Produit non vendable de bout en bout | Greps reproduits | Slices COST-BASIS, CCAP-RISK, croisement, OCR, DC-gen, décision finalisable | — | Démo DCE réel de bout en bout |

---

## C. Journal des commandes et preuves

Environnement : Linux, Docker 29.1.3, Compose v5.5.0, Python 3.12.3 (uv 0.11.21), Node v22.23.1, pnpm 11.21.0. Durées réelles mesurées.

| # | Commande (sans secret) | Résultat | Durée |
|---|---|---|---|
| C1 | `git fetch origin && git switch docs/pricing-http-next-lot-28 && git pull --ff-only …` | fast-forward `0eb82a0`→`33986fb` (création `docs/AUDIT_RECONCILIATION_2026-08-24_6.md`, archivage rapport audit) | ~5 s |
| C2 | `uv lock --check` | Resolved 191 packages — OK | <1 s |
| C3 | `uv run ruff check backend scripts` | All checks passed | <2 s |
| C4 | `uv run mypy backend/app/platform/security backend/app/modules/case` | Success: no issues found in 27 source files | ~30 s |
| C5 | `uv run pytest -q -m 'not db' backend/tests` | **1 failed, 905 passed**, 458 deselected (OPS-L-001) | 9,17 s |
| C6 | Base isolée : `docker run postgres@sha256:cf78e766…` tmpfs, port 5437, supprimée après | pg_isready OK | — |
| C7 | `SMART_AO_TEST_DATABASE_URL=… uv run --extra calendar pytest -q backend/tests --cov=app --cov-fail-under=85.50` | **1363 passed / 1 failed** (même test ops), TOTAL 15 467 stmts **90,95 %** > gate | 342,82 s |
| C8 | `web`: `pnpm install --frozen-lockfile --ignore-scripts` | OK 35 ms | — |
| C9 | `pnpm test --run` | **23 fichiers / 98 tests passés, 0 erreur** | 9,21 s |
| C10 | `pnpm typecheck` / `pnpm lint` / `pnpm build` | tsc OK / 0 erreur + 2 warnings hooks connus (`App.tsx:202,211`) / build ✓ JS 294,03 kB (82,95 gz) en 262 ms | ~30 s |
| C11 | `bash -n ops/*.sh scripts/*.sh` (session précédente, scripts inchangés) | OK | — |
| C12 | AST imports (`python3` script lecture seule sur `backend/app`) | 64 arêtes application→infra inter-modules (inchangées), 0 ajoutée par le slice Case, platform→modules = 10 (registry Alembic, inchangée) | ~3 s |
| C13 | API GitHub `/actions/runs?per_page=15` + jobs du run `32714197692` (session 1) | 60+ runs failure sans runner/steps ; dernier succès 21/08 ; run `33986fb` identique | — |
| C14 | `.secrets.baseline` : comptage JSON | **10 entrées** (contre 585 avant nettoyage) ; hook detect-secrets lancé sur échantillon git-files sans alerte bloquante affichée | — |
| C15 | `SMART_AO_POSTGRES_HOST_PORT=15432 docker compose up -d postgres clamav migrate backend dce-retention-worker` | Tous healthy ; migrate Exited 0 ; **sans fichier override** → OPS-003 confirmé corrigé | ~40 s |
| C16 | `docker compose build backend dce-retention-worker` puis `up -d` sans clé JWT | Backend **Exited(1)** : RuntimeError dev key forbidden (OPS-L-002) | build ~2 min |
| C17 | idem + `SMART_AO_JWT_SIGNING_KEY=<32 hex>` | Backend **healthy** ; headers sécurité présents ; ready = `{database:ok, schema:ok, clamav:ok}` (nouveau check schema visible live) | ~30 s |
| C18 | `docker compose down --remove-orphans` ; `docker rm -f audit-pg-iso2` | Environnement nettoyé ; volumes développeur intacts | — |

Limites/erreurs : pas de simulation live de message outbox empoisonné ; pas d'EICAR (service ClamAV partagé du développeur non perturbé) ; pas de benchmark/performance (corpus représentatif absent) ; PR/main non touchées ; workflows jamais relancés.

---

## D. Séparation stricte des preuves

### D.1 Preuves exécutées par moi (cette session, commit `33986fb`)

C1–C18 ci-dessus : suites backend non-DB et DB+couverture (base PG 16 digest-pinnée isolée), frontend complet, mypy ciblé, AST, état CI distant par API, baseline secrets, cycle Docker complet (up→healthy→headers→ready→down), reproduction du crash cold-start puis du démarrage sain avec clé valide, paramètre de port Compose vérifié en usage réel.

### D.2 Observations d'inspection statique (code/config, sans exécution)

Contenu et câblage de `public_http.py`/`headers.py`/`retry_policy.py` dans les 4 workers ; route Case montée inconditionnellement + capability patron-admin ; absence d'arête application→infrastructure dans le nouveau code ; CI yml (permissions, concurrency, timeouts, digest PG identique au compose, SARIF+CodeQL SHA-pinnés, `--all-extras`) ; compose preprod `OUTBOX_MAX_ATTEMPTS` propagé aux 4 workers ; docs réconciliation/checklist/PROJECT_STATE (cohérence additive, historique conservé) ; SEC-002/SEC-003 inchangés ; INT-* inchangés ; `sqlalchemy.orm.Session` type-only dans le handler Case.

### D.3 Affirmations de rapports antérieurs NON reproduites par moi

| Affirmation | Source | Statut à mon niveau |
|---|---|---|
| Stack dev healthy 41 h (audit précédent §D) | Mon audit session 1 | **Corrigé/nuancé** : obtenu sur images périmées ; rebuild → crash (OPS-L-002) |
| « 906 tests backend hors db passent » | Réconciliation devs §1 | **Réfuté par exécution** (905+1) |
| Mesures locales devs : frontend 98, typecheck/lint/build, lock, ruff, mypy ciblé, baseline 10, alembic offline 0056 | Réconciliation devs §1 | **Reproduites et confirmées** |
| Triggers append-only, isolation tenant, 1346 tests, 90,96 % (audit précédent, base isolée session 1) | Mon audit session 1 | Non rejoués intégralement cette session ; couverture rejouée (1363/90,95 %) et migrations online rejouées via service migrate exit 0 jusqu'à 0056 |
| CIs historiquement vertes citées par la checklist (runs `32076462…` etc.) | Checklist durable | Antérieures à la panne runner ; non revérifiables une à une — plausible, non contesté |
| Recettes EICAR/HTTPS/backup/S3/BOAMP/INSEE/SMTP/signature réelles | Personne | Toujours NON VÉRIFIABLE (aucun acteur ne les a exécutées) |

---

## E. Remédiations prioritaires

| Priorité | Action | Responsable | Prérequis | Fichiers | Test/preuve de sortie |
|---|---|---|---|---|---|
| **P0** | Révoquer/régénérer le PAT ; nettoyer l'URL remote de tous les clones | Propriétaire GitHub | accès compte | config locale | Security log GitHub + `git remote -v` propre |
| **P0** | Rétablir runners CI ; obtenir UN run complet avec steps/artefacts/SARIF sur `33986fb`+ | Propriétaire repo | billing/org ou self-hosted | `.github/workflows/ci.yml` (déjà prêt) | Run ID avec 3 jobs green + SARIF onglet Security |
| **P0** | Corriger le test de contrat Compose (OPS-L-001) puis repasser la suite au vert | Devs | aucun | `backend/tests/ops/test_preprod_ops_contract.py` | `pytest -m 'not db'` → 906/906 |
| **P1** | Réparer le quickstart dev à froid (OPS-L-002) : entrypoint dev ou clé example valide | Devs | aucun | `ops/docker/backend.Dockerfile`, `docker-compose.yml`, `.env.example`, README | `make up` à froid → backend healthy |
| **P1** | Alerte FAILED outbox + rétention + contrat cockpit_projection (go/no-go explicite) | Devs+Ops | décision produit | `platform/events/*`, workers, compose | Métrique FAILED exposée + job rétention + test poison→FAILED |
| **P1** | Recette PostgreSQL online du parcours CreateCase (migration, isolation tenant, idempotence) sur base jetable | Devs | PG accessible | tests db existants à étendre au slice Case | Rapport d'exécution horodaté |
| **P2** | Écran frontend création d'affaire + E2E navigateur (Playwright) contre API réelle | Devs | P0 CI | `web/src/features/*` | Parcours login→create case→lecture |
| **P2** | MFA/TOTP cérémonie complète OU retrait de toute mention MFA des contrats commerciaux | Devs+Produit | décision | security module | Tests enrôlement/vérification/recovery |
| **P2** | Rate limiter distribué AVANT tout scale-out multi-réplicas | Devs | décision store | rate_limit | Test 429 cohérent multi-instance |
| **P2** | Recettes intégrations séparées (BOAMP, INSEE, SMTP, S3, BGE, Docling, bus, signature) | Ops | credentials hors Git | scripts opérateur | Rapports de recette hashés |
| **P3** | ARCH-001 par bounded context ; parité enums↔CHECK automatisée ; PATRON_DELEGATION-01 | Devs | P0 CI | modules ciblés | Tests architecture + ownership verts |

Décision de non-déploiement tant que P0 non clos : **ne pas fusionner PR #49 vers `main`, ne pas installer de client pilote.**

---

## F. Verdict par axe (au commit `33986fb`)

| Axe | Verdict | Justification courte |
|---|---|---|
| Architecture | **GO conditionnel** | Nouveau code exemplaire (ports, zéro nouvelle arête) ; dette 64 arêtes inchangée et assumée |
| Backend/API | **GO conditionnel** | Slice Case complet et testé (API/idempotence/403/409/422) ; suite globale rouge sur 1 test ops → à verdir avant tout |
| Données/PostgreSQL | **GO conditionnel** | Tête unique 0056 stable, migrate online exit 0 rejoué, cov 90,95 % > gate ; dead-letter partielle, cockpit_projection ouvert |
| Sécurité | **GO conditionnel** | Headers live prouvés, SSRF durci (TOCTOU assumé), fail-closed conservé partout ; SEC-001/MFA/rate-limit ouverts |
| Frontend | **GO conditionnel** | 98 tests verts, typecheck/lint/build OK ; pas d'écran création d'affaire, pas d'E2E navigateur |
| Docker/CI/Ops | **NO-GO** | CI sans steps (y compris sur le commit de remédiation), suite rouge, quickstart à froid cassé |
| Intégrations externes | **NON VÉRIFIABLE** | Aucune brique activée/recettée ; inchangé |
| Métier BTP | **NO-GO** | Entrée Case créée (majeur) mais cœur analytique (coût de revient/plancher/pénalités, CCAP/croisement, OCR, DC, décision finalisable) toujours absent |
| Observabilité/Performance | **GO conditionnel** | Readiness tri-partite (db/schema/clamav) vérifiée live ; performance non mesurable (pas de corpus) |
| Documentation/Gouvernance | **GO conditionnel** | Réconciliation globalement honnête et traçable ; une claim de vert réfutée (DOC-L-001) à corriger |

---

## G. Décision commerciale

- **Peut-on vendre le produit comme plateforme AO complète ?** **Non.** Le cycle démarre désormais (CreateCase) mais s'arrête vite : aucun moteur chiffrage défendable (coût de revient, prix plancher, pénalités/RG/cautionnement), aucune analyse croisée CCTP–DPGF–BPU–CCAP, pas d'OCR (DCE scannés = impasse), pas de DC1/DC2/DC4, décision non finalisable, signature sans provider, dépôt plateforme humain.
- **Peut-on le présenter comme back-office documentaire partiel ?** **Oui, sous conditions strictes** : admission DCE sécurisée (quarantaine+ClamAV fail-closed), versioning/doublons, extraction+provenance, exigences avec confirmation humaine, wizard collaborateur, bibliothèque entreprise (Kbis/RIB/assurances), readiness, import pricing XLSX contrôlé — à condition d'une instance opérée (CI verte, PG online recetté, ClamAV réel) et sans promesse financière automatisée.
- **Fonctions réellement disponibles aujourd'hui** : celles listées ci-dessus + création d'affaire HTTP (backend, en attente de recette online et d'écran), veille BOAMP en lecture (flag), lookup INSEE read-only (flag), notifications SMTP opt-in.
- **Fonctions à ne surtout pas promettre** : MFA/step-up, multi-réplicas, analyse juridique CCAP, chiffrage automatique fiable, mémoire technique générée, signature électronique qualifiée, dépôt PLACE/MPM, RAG à l'échelle, OR-Tools (« planification de capacité » non exposée), toute intégration fournisseur « intégrée ».
- **Preuves manquantes avant un premier client pilote** : run CI avec steps verts sur le SHA livré ; recette PG online du slice Case + triggers sur base jetable ; gate VPS (HTTPS, EICAR, backup→restauration isolée hashée) ; une démonstration bout-en-bout sur DCE réel anonymisé ; contrat de signature si la fonction est évoquée.

---

## Conclusion

> Au commit `33986fb58e382a36b623055b7a0a3033f5c51ac3`, le produit est **NO-GO** (en progrès tangible depuis `0eb82a0`). Les éléments réellement opérationnels sont : le socle FastAPI/PostgreSQL migré jusqu'à `0056`, l'authentification Argon2id/JWT-rotation, l'autorisation serveur fail-closed, l'admission DCE quarantaine+ClamAV, le versioning DCE, les exigences confirmées humainement, le wizard collaborateur, la bibliothèque entreprise, l'import pricing XLSX, les scénarios append-only, l'export ZIP audité, les headers de sécurité backend (vérifiés live), le transport sortant anti-SSRF, la dead-letter bornée des workers, et désormais la création d'affaire HTTP tenant-scoped et idempotente (tests verts, recette online pendante). Les éléments seulement préparés ou simulés sont : OR-Tools (déconnecté), ICS (port mort), décision GO/NO-GO (read-model sans commande), MFA (schéma sans cérémonie), signature (intention), RAG (flag + cosinus mémoire), toutes intégrations fournisseurs. Les blocages avant production sont : CI sans aucune étape exécutée (y compris sur ce commit), suite backend rouge (test de contrat Compose oublié), quickstart dev à froid cassé, préprod jamais recettée, PAT GitHub non révoqué. Les preuves que nous n'avons pas obtenues sont : un run CI avec étapes, une recette EICAR/HTTPS/backup-restauration réelle, un appel fournisseur quelconque (BOAMP/INSEE/SMTP/S3/signature), un benchmark sur corpus DCE représentatif et une cause racine au crash historique du retention worker.

*Signé : ox-alpha — toutes les commandes citées ont été exécutées le 2026-08-24 dans l'environnement décrit en section 0 ; environnement de test restauré (conteneurs isolés supprimés, volumes du développeur intacts).*
