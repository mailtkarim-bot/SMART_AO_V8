# 🏗️ RAPPORT D'AUDIT SYSTÈME SUPRÊME — SMART_AO V8

| | |
|---|---|
| **Date de l'audit** | 22 août 2026 |
| **Auditeur** | Inspecteur Système Suprême — Tech, Sécurité & Valeur Métier BTP |
| **Périmètre** | 690 fichiers — backend FastAPI (414 fichiers Python / ~35 400 LOC applicatives), frontend React/Vite (36 fichiers TS/TSX / ~5 830 LOC), 48 migrations Alembic, 127 fichiers de tests backend, infra Docker/Caddy/ops |
| **Méthode** | Autopsie chirurgicale à 360° en 5 axes parallèles : architecture, sécurité/RBAC, logique métier BTP, frontend, infra/CI/tests — chaque constat vérifié par lecture directe du code source (preuves `fichier:ligne`) |

---

## 1. EXECUTIVE SUMMARY — Bilan de santé général (Tech + Business)

### Note globale : **56 / 100**

| Pilier d'audit | Note | Appréciation sans filtre |
|---|---:|---|
| **1. Architecture & Ingénierie logicielle** | **74/100** | Discipline de haut vol (DDD, outbox, idempotence, tests d'architecture à dents) mais migration de persistance **inachevée** : un god-file de 2 481 lignes couple 5 modules. Le monolithe modulaire est encore une *aspiration*, pas une réalité. |
| **2. Sécurité & Étanchéité absolue** | **82/100** | **Le meilleur point du projet.** Aucune faille critique trouvée : isolation tenant étanche, RBAC serveur deny-by-default, murs de confidentialité financière multicouches. Retenues : JWT en `localStorage` côté SPA, rate-limiter contournable, absence de CSP. |
| **3. Pertinence métier BTP** | **32/100** | **Le talon d'Achille.** Le logiciel ne lit pas les PDF scannés (pas d'OCR), n'analyse ni CCAP ni CCTP, n'extrait aucune échéance/pénalité/caution, n'importe que le côté *ventes* de la DPGF. C'est aujourd'hui un excellent back-office de confidentialité — **pas encore une arme pour gagner des AO**. |
| **4. Performance & Solveur numérique** | **68/100** | Math déterministe propre (entiers en centimes + bps + `Decimal`), zéro composant génératif = zéro hallucination dans le chiffrage. Mais les totaux importés ne sont **jamais réconciliés** contre les lignes (qty×PU ≠ total accepté en silence) et le coût de revient est absent. |
| **Readiness production** | **25/100** | **NO-GO auto-déclaré** (`docs/STAGING_GATE_STATUS_2026-08-21.md:5`). La stack n'a **jamais été exécutée** : aucun build d'image, aucun test EICAR, aucune restauration réelle. Deux défauts réseau bloquants dorment dans le compose preprod. |

> **Verdict en une phrase :** un coffre-fort bancaire d'une ingénierie remarquable, construit autour d'un atelier d'analyse d'appels d'offres encore vide de ses machines-outils, et qui **n'a jamais été branché sur le courant** (aucun déploiement réel exécuté).

### Résumé des risques critiques — points de rupture immédiats

1. **💥 Déploiement garanti en échec tel quel** : ClamAV et le worker webhook siègent sur un réseau Docker `internal: true` (`ops/docker-compose.preprod.yml:194-196`) → impossible de mettre à jour les signatures virales, impossible de joindre l'URL externe du portail de dépôt.
2. **💥 Le produit ne résout pas encore le problème qu'il vend** : un DCE municipal scanné (majorité du parc réel) termine en `FAILED_SAFE` — pas d'OCR, pas d'analyse CCTP/CCAP, pas d'extraction des pièges mortels (pénalités, cautions, décennale).
3. **💥 Chiffrage unilatéral et non réconcilié** : import forcé `category="SALES"` (`import_service.py:170`), aucun coût de revient, totaux jamais revalidés post-écriture → risque direct sur la survie marginale de l'entrepreneur.
4. **💥 Parcours décisionnel inopérant** : les machines à états Decision et Case existent en domaine pur mais **aucune route HTTP ne permet de finaliser une décision ou d'avancer le stade** — le cockpit patron s'arrête avant la décision.
5. **⚠️ Dette structurelle active** : `platform/security/models.py` (2 481 lignes) porte l'ORM de ~5 modules ; chaque nouvelle ligne de code accroît le coût du pivot.

---

## 2. MATRICE DES RISQUES CRITIQUES

*Ce qui va faire exploser le logiciel en production ou ruiner l'utilisateur BTP.*

| ID | Sévérité | Axe | Risque | Preuve (`fichier:ligne`) | Impact si non traité |
|---|---|---|---|---|---|
| **C-01** | 🔴 CRITIQUE | Infra | Stack **jamais exécutée** : aucun build image, EICAR, HTTPS, backup/restauration réalisés. Décision NO-GO auto-documentée. | `docs/STAGING_GATE_STATUS_2026-08-21.md:5` — « Aucun build d'image… n'est déclaré réalisé » | Mise en production = terrain de jeu d'imprévus ; toute qualité statique s'évapore au premier contact réel. |
| **C-02** | 🔴 CRITIQUE | Infra | **ClamAV sans egress** sur réseau `internal: true` → base de signatures jamais mise à jour → antivirus opérationnellement aveugle (fail-open déguisé). | `ops/docker-compose.preprod.yml:194-196` | Un malware déposé dans un DCE passe l'analyse AV. Ruine la promesse « fail-closed ». |
| **C-03** | 🔴 CRITIQUE | Infra | **Worker webhook sans egress** : même réseau interne → URL externe du portail de dépôt injoignable → accusés de réception jamais obtenus. | `ops/docker-compose.preprod.yml` (réseau internal) + `docs/SUBMISSION_ZIP_WEBHOOK_BENCHMARK_REPORT.md:51` | Le système ne pourra jamais confirmer un dépôt — cœur de la promesse produit. |
| **C-04** | 🔴 CRITIQUE | Métier | **Pas d'OCR** : tout PDF scanné (part massive des DCE municipaux) finit `FAILED_SAFE`. Pas de parsers CSV/XML bordereau. | Grep `tesseract\|ocrmypdf\|csv.reader\|xml.etree\|lxml` dans `backend/app` → **0 résultat** | L'utilisateur cible ne peut pas traiter ses vrais dossiers. Produit inutilisable en conditions réelles. |
| **C-05** | 🔴 CRITIQUE | Métier | Chiffrage **vente seule** et non réconcilié : `category="SALES"` forcé ; qty×PU vs total fourni divergents **acceptés silencieusement** ; pas de coût de revient, pas de BT01/coefficient. | `backend/app/modules/pricing/application/import_service.py:170` ; `import_preview.py:187-190` | Marge fictive validée par le patron sur la foi d'un total jamais recalculé. Risque de ruine sur l'AO remporté à perte. |
| **C-06** | 🔴 CRITIQUE | Métier | **Aucune surface HTTP** pour finaliser une Decision ou avancer le stade d'un Case → machines à état du domaine inopérables depuis l'interface. | Absence de routes write confirmée (grep) ; `docs/PROJECT_STATE.md` | Le parcours client s'arrête avant l'instant de décision — la valeur centrale du produit n'est pas atteignable. |
| **H-01** | 🟠 MAJEUR | Archi | God-file `platform/security/models.py` (**2 481 lignes**) portant l'ORM de ~5 modules + re-export de compatibilité L1052 → couplage transverse, risque de cycles. | `platform/security/models.py` (2481 lignes, vérifié) | Toute évolution de schéma devient transversale ; frontière modulaire fictionnelle. |
| **H-02** | 🟠 MAJEUR | Sécurité | JWT brut stocké en `localStorage` + saisie manuelle du token dans une textarea ; endpoints `/api/v1/auth/*` **non utilisés** par le SPA ; identité codée en dur (« Patron administrateur »). | `web/src/app/App.tsx:62,237,266,410` | Vol de session par moindre XSS tiers ; collaborateurs et patron indifférenciés côté UI. |
| **H-03** | 🟠 MAJEUR | Sécurité | Import pricing lit **tout le body en RAM** avant tout contrôle de taille → DoS mémoire par un utilisateur authentifié ; garde ZIP-bomb fondée sur le central directory falsifiable ; openpyxl sans durcissement defusedxml. | `routes/patron_pricing_import.py:22-23` ; `import_preview.py:87-89` | OOM d'un worker = déni de service multi-tenant sur un VPS dimensionné petit. |
| **H-04** | 🟠 MAJEUR | Sécurité | Rate limiter **process-local**, contournable par rotation d'IP, s'effondre derrière Caddy (pas de confiance aux headers proxy). | `rate_limit.py:135` ; `routes/authentication.py:266-267` | Brute-force de credentials viable dès la première réplique ou via edge. |
| **H-05** | 🟠 MAJEUR | Sécurité | **Aucun header CSP** nulle part ; pas de throttling global au-delà de login/refresh ; `/metrics` + `/healthz/ready` exposés sans auth (divulgation de dépendances). | `ops/Caddyfile:13-19` ; `observability.py:12-17` | Surface de reconnaissance offerte ; amplification de toute XSS future. |
| **H-06** | 🟠 MAJEUR | Qualité | **Aucun mypy/pyright** configuré alors que la référence d'architecture déclare la vérification de types « Obligatoire sur le noyau métier ». | Grep `mypy\|pyright` dans `pyproject.toml`, `Makefile`, `ruff.toml` → 0 résultat ; `docs/reference/SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md:127` | Le code grossit (+10k LOC prévues) sans filet statique ; régressions de types invisibles jusqu'à l'exécution. |
| **H-07** | 🟠 MAJEUR | Tests | Asymétrie de profondeur : **1 seul test E2E**, 2 tests de concurrence, 0 test de charge exécuté ; course SKIP LOCKED entre workers jamais validée sur PostgreSQL réel. | `tests/e2e/test_collaborator_capability_workflow.py:26` ; `test_concurrency_invariants.py:73,125` ; `todo.md:28` | Perte/silence outbox sous charge concurrentielle réelle = événements métier perdus. |
| **H-08** | 🟠 MAJEUR | Métier | Webhook sortant **sans dead-letter ni politique d'alerting** (risque auto-documenté). | `SUBMISSION_ZIP_WEBHOOK_BENCHMARK_REPORT.md:51` | Échec d'accusé de dépôt invisible → faux sentiment de sécurité chez le patron. |
| **H-09** | 🟠 MAJEUR | Frontend | Erreurs de chargement **avalées en silence** (reset à vide sans message) sur actions, scénarios pricing et dossier de décision ; `JSON.parse` non gardé. | `App.tsx:205-207,213-215,221-223` ; `api.ts:45` | L'utilisateur croit avoir zéro donnée alors que l'appel a échoué — défiance immédiate. |
| **H-10** | 🟠 MAJEUR | Métier | Polarité RC (requis/optionnel) par simple matching de marqueurs naïfs → signaux inversés sur négations et portées longues ; classification générique (`\bannexe(?:s)?\b`) gonflant `REVIEW_REQUIRED`. | Modules `dce/application/classification.py` (constats d'inspection) | Fausse qualification réglementaire d'un document obligatoire = disqualification de l'offre. |
| **M-11** | 🟡 MINEUR | Sécurité | Garde lexicale `text_safety.py` bloque des mots mais pas les chiffres → un montant financier peut fuiter dans un texte visible collaborateur par formulation. | `platform/security/text_safety.py` | Fuite ponctuelle de donnée confidentielle (ex. « budget de 450 000 € HT »). |
| **M-12** | 🟡 MINEUR | Archi | Scaffolding mensonger : `container.py`, `module_registry.py`, `configuration.py` quasi vides ; `demonstrations/m1.py` (438 LOC) dans l'arbre de prod ; markers de tests `schema`/`application` déclarés jamais utilisés. | `bootstrap/*` ; `app/demonstrations/m1.py` ; `pyproject.toml:48,50` | Trompe le lecteur/mainteneur ; dette conceptuelle qui pourrit les onboarding. |
| **M-13** | 🟡 MINEUR | Frontend | Pas d'ESLint/Biome/Prettier ; `typescript` en `dependencies` runtime ; pas de router (nav par `scrollIntoView`, deep-links impossibles) ; labels divergents (« Provision » vs « Aléas ») ; EUR + ruleset hardcodés. | `web/package.json:13,16` ; `App.tsx:31-39,226-229` ; `FinancialDraftPanel.tsx:170-175` ; `api.ts:359-360` | Incohérences UX et dette qui interdiront le scale au-delà de ~4k LOC. |
| **M-14** | 🟡 MINEUR | Docs | Drift docs/code : `todo.md` liste un lot déjà livré (PRs #44–#48) ; comptes de tests contradictoires entre documents (402→435→522→558→756). | `todo.md:21` vs `git log d43d621,51bc3e6,0246b99` | Confiance érodée dans toute métrique auto-déclarée du projet. |

---

## 3. AUTOPSIE TECHNIQUE (Code & Archi)

### 3.1 Architecture — chiffres et forme réelle

Répartition mesurée de `backend/app` (~35 361 LOC / 222 fichiers) :

| Couche | LOC | Part |
|---|---:|---:|
| `modules/` (9 modules métier) | 23 469 | 66,4 % |
| `platform/` (transversal) | 5 313 | 15,0 % |
| `interfaces/http/` (75 endpoints) | 4 768 | 13,5 % |
| `bootstrap/` + `workers/` + `demonstrations/` | 1 811 | 5,1 % |

**Constat central** : le domaine pur ne représente que **~6,5 %** de la logique des modules (≈1 530 LOC). Les couches application concentrent ~68 % et font persister directement dans cinq modules dont la « vraie » infrastructure vit dans `platform/security/models.py`. Le gradient de maturité est net : `case/dce/decision` suivent la forme hexagonale visée (dépôts non câblés), `enterprise` est le citoyen modèle post-migration, `membership/dce` portent le poids legacy.

#### Fautes majeures
1. **Migration de persistance inachevée (H-01)** — `models.py` agrège les ORM de case, dce, membership, etc., avec re-export de compatibilité ligne 1052. Les tests `tests/architecture/test_post_slice_boundaries.py:38-56` valident déjà le pattern cible (enterprise) : il faut le généraliser.
2. **Commandes étrangères hébergées par dce** — assignment et rapports financiers sont commandés depuis `dce/application/commands.py` alors qu'ils appartiennent à `membership`. Violation frontière qui crée un risque de cycle d'imports.
3. **Routes épaisses** — `ConsultationSecurityRuntime` + `_resolve_context` sont dupliqués/appelés manuellement par ~30 builders de routes (`patron_pricing_import.py:7-8` en est un exemple flagrant : imports croisés entre fichiers de routes) au lieu de vivre dans `interfaces/http/dependencies/` qui est **vide**.
4. **Plomberie workers dupliquée** — deux workers réimplémentent claim/lease/retry au lieu d'un `OutboxConsumer` partagé ; routage de topic `cockpit_projection` implicite.

#### Incohérences structurelles
- **Scaffolding mensonger** (M-12) : trois fichiers de bootstrap quasi vides laissent croire à un conteneur DI fonctionnel.
- **Erreurs stringly-typed** : `PermissionError("CODE")` / `ValueError("CODE")` traduites à la main au lieu d'exceptions typées à codes machine lisibles par `error_mapping.py`.
- **Triggers d'immutabilité SQL bruts dans ~25 migrations** (ex. `20260813_0002:400-441`, `protect_admitted_dce_content`) : excellents pour l'intégrité, **invisibles à autogenerate** → risque de drift schéma ORM/SQL si maintenance manuelle oubliée.

#### Points d'excellence (à préserver absolument)
Dispatcher de commandes transactionnel, outbox, idempotence généralisée, révisions optimistes, audit des refus d'autorisation, tests d'architecture à dents, discipline de nommage et docstrings au-dessus de la moyenne FastAPI.

### 3.2 Sécurité & Étanchéité

**Verdict : aucune voie d'accès inter-tenant, aucun sink d'injection SQL/commande/XSS, aucune fuite de données financières vers les collaborateurs détectée.** C'est rare et remarquable.

Ce qui est fait de manière exemplaire :
- Cycle refresh-token irréprochable : jetons opaques hachés, rotation one-time, replay ⇒ révocation familiale, timeouts idle+absolu, rôles privilégiés à fenêtres réduites (`authentication.py:437-455`).
- Autorisation ReBAC deny-by-default, contexte acteur reconstruit depuis la DB à chaque requête, catalogues de capacités fermés intersectés serveur (`capabilities.py:128-146` : *« Caller-provided roles, JWT claims and request payloads must never reach this function as authority »*).
- Confidentialité financière multicouche : gate rôle + gate classification + gate capacité + requêtes tenant-scoped + écrans `contains_forbidden_text` + `Cache-Control: no-store`.
- Pipeline upload robuste : caps de streaming chunk-par-chunk, sniffing libmagic, ClamAV fail-closed, défense path-traversal double, permissions 0600/0700, machine à états single-use, worker de rétention.

Les retenues (H-02 à H-05, M-11) sont toutes côté périmètre (SPA, edge, limites process-local) — corrigeables sans toucher au noyau.

### 3.3 Données & migrations

48 révisions Alembic en chaîne linéaire (`20260813_0001` → `20260821_0048`), **toutes avec downgrade()**, aucune opération destructive en upgrade. La conftest exécute un vrai cycle `upgrade head → downgrade base` par module de tests — pratique au-dessus de la norme qui a déjà attrapé un vrai défaut (downgrade `0023`). Deux bémols : credentials dev embarqués dans les deux `alembic.ini`, et pas d'isolation par rollback transactionnel par test (nettoyage `TRUNCATE ... CASCADE` manuel).

### 3.4 Tests — ce que les 127 fichiers couvrent (et ne couvrent pas)

Couvert solide : isolation tenant/confidentialité, Argon2id, révocation famille refresh, enforcement append-only par trigger, rejet stale-writer, replay idempotent, rate limiter (horloge injectée), métriques sans payload métier (`test_observability.py:20-33` assert `"tenant_id" not in response.text`). Seuil CI : branche ≥ 85,50 %.

Manques criants (H-07) : parcours multi-modules de bout en bout (consultation → admission DCE → assignation → préparation → paquet de dépôt) inexistant ; concurrence SKIP LOCKED sur connexions parallèles réelles non testée ; charge jamais exécutée hors scripts manuels ; `tests/process/` et `tests/factories/` **vides** ; seeds ad-hoc via hacks `sys.path.insert`.

### 3.5 Frontend (web/)

20 fichiers sources / 3 762 LOC + 16 fichiers de tests (ratio ~1:1, discipline louable). Zéro sink XSS, guards runtime d'URL API bien pensés (`runtimeConfig.ts:17-43`), TypeScript strict. Verdict : **7/10 — cockpit interne bien taillé qui ne passera pas l'échelle** sans router, sans couche data/cache et sans linter (H-09, M-13).

### 3.6 Infra & ops

Digest-pinning validé par tests unitaires, image non-root imposée par test d'architecture, réseaux privés, backups avec vérification de restauration isolée **écrits avant tout déploiement** — mais jamais exécutés. Scripts `ops/*.sh` complets (backup, deploy, healthcheck, restore, rotate-jwt) attendant leur premier hôte réel. Pas de resource limits, healthchecks absents sur edge/workers, alertes sans transport défini.

---

## 4. VERDICT MÉTIER — Le regard du Patron BTP

> *« On me vend un logiciel qui analyse mes appels d'offres. Aujourd'hui, s'il ne sait pas lire mon DCE scanné, qu'il ne voit pas la pénalité de retard planquée au CCAP, qu'il ne calcule pas mon prix de revient et qu'il ne me dit pas quand je dois déposer — il me sert un café pendant que je joue ma trésorerie. Beau coffre-fort, mais l'atelier est vide. »*

### Ce que SMART_AO V8 fait DÉJÀ mieux que la concurrence (fondations rares)

| Capacité | État |
|---|---|
| Étanchéité patron/collaborateur (marges invisibles côté études) | ✅ Mur multicouche prouvé par tests |
| Traçabilité append-only des versions DCE | ✅ Enforcement au niveau PostgreSQL |
| Paquet de dépôt immutable + refus honnête de revendiquer un dépôt externe | ✅ Philosophie « accusé vérifiable » |
| Idempotence, outbox, audit des décisions | ✅ Niveau SaaS bancaire |

### Ce qui lui manque pour être une ARME DE GUERRE (et pas un gadget)

| Piège mortel de l'AO | Couverture actuelle |
|---|---|
| 📄 DCE scanné (PDF image) | ❌ `FAILED_SAFE` — pas d'OCR |
| ⚖️ Clauses abusives CCAP (pénalités, limitation de responsabilité, retenue de garantie) | ❌ Aucune analyse clause-level |
| 📅 Échéances (remise des offres, validité, caution définitive, attestation décennale) | ❌ Aucune extraction calendrier |
| 🔢 Incohérences CCTP ↔ DPGF | ❌ Non implémenté |
| 💰 Prix de revient, coefficients, BT01/inflation | ❌ Import ventes uniquement, pas de réconciliation totaux |
| 🤝 Co-traitance / sous-traitance DC4 | ⚠️ Partiel (workflow oui, chiffrage non) |
| 📝 Mémoire technique / variantes gagnants | ❌ Aucune génération assistée |
| 🚚 Dépôt effectif + accusé | ⚠️ Paquet prêt, webhook non joignable en l'état (C-03) |

**ROI actuel : négatif** (l'entrepreneur saisit manuellement ce que le logiciel devrait extraire). **ROI potentiel : très élevé** — l'ossature de confiance existe, il manque les machines-outils. La boucle de provenance/confirmation humaine déjà construite (confirmations d'exigences DCE) est précisément le rail sûr sur lequel brancher un premier assistant LLM contrôlé **sans** contaminer le chiffrage déterministe : l'IA propose, l'humain confirme, le solveur calcule.

---

## 5. PLAN DE REMÉDIATION CHIRURGICAL

### Phase 0 — Débloquer la mise en service (Semaine 1, bloquant absolu)

**0.1 Corriger l'egress réseau (C-02, C-03)** — `ops/docker-compose.preprod.yml` :
```yaml
networks:
  edge:
    driver: bridge
  internal:
    driver: bridge
    internal: true

services:
  clamav:            # ← clamav doit AUSSI rejoindre "edge" (sortie seule)
    networks: [internal, edge]
  export-webhook-worker:
    networks: [internal, edge]   # ← doit joindre l'URL externe du portail
```
Puis exécuter le **gate VPS 7-preuves** déjà spécifié par le projet (build digest-pinné, `docker compose config`, Postgres+ClamAV+Caddy, migration, EICAR, HTTPS, backup→restore isolé).

**0.2 Streamer l'upload pricing (H-03)** — remplacer `routes/patron_pricing_import.py:22-23` :
```python
async def _read_upload(upload: UploadFile, *, max_bytes: int = MAX_IMPORT_BYTES) -> bytes:
    buf = bytearray()
    while chunk := await upload.read(1024 * 1024):
        buf += chunk
        if len(buf) > max_bytes:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail="pricing_import_too_large")
    return bytes(buf)
```
Et extraire le XLSX vers disque avec limite cumulée (ne plus faire confiance au central directory ZIP).

**0.3 CSP + throttling au bord (H-05)** — `ops/Caddyfile` :
```
header {
    Content-Security-Policy "default-src 'self'; frame-ancestors 'none'; object-src 'none'"
    X-Content-Type-Options nosniff
    Referrer-Policy strict-origin
}
rate_limit {
    zone login { key {remote_host} events 10 window 1m }
}
```

**0.4 Session httpOnly (H-02)** — câbler le SPA sur `/api/v1/auth/*` existant (cookie httpOnly + CSRF), supprimer la textarea de token (`App.tsx:410`) et l'identité codée en dur (`App.tsx:266`) ; afficher le rôle réel issu du contexte serveur.

**0.5 Authentification structurelle (anti-oubli)** — transformer `_resolve_context` + policy en dependency FastAPI unique appliquée par router builder, rendant une route non protégée impossible à écrire.

### Phase 1 — Résorber la dette structurelle (Sprints 2–4)

1. **Finir la migration de persistance** : sortir chaque ORM de `platform/security/models.py` vers son module (`infrastructure/models/`), supprimer le re-export L1052 — le pattern enterprise fait foi (`test_post_slice_boundaries.py:38-56`).
2. **Re-homer les commandes étrangères** : assignment + financial reports quittent `dce/application/commands.py` pour `membership` ; base commune → `platform/events/command_contracts.py`.
3. **Éclaircir les routes** : `ConsultationSecurityRuntime`/`_resolve_context` → `interfaces/http/dependencies/` ; traduction centrale des erreurs dispatcher dans `error_mapping.py`.
4. **Unifier la plomberie workers** : classe de base `OutboxConsumer` (claim/lease/publish/retry/backoff) + relay explicite pour `cockpit_projection`.
5. **Typage et erreurs** : introduire mypy incrémentalement strict (noyau d'abord) ; exceptions typées à codes machine traduites une fois par `error_mapping.py`. Purger `container.py`/`module_registry.py`/`configuration.py` et `demonstrations/m1.py`.
6. **Tests** : 1er E2E multi-modules complet ; concurrence SKIP LOCKED sur connexions parallèles réelles ; isolation par rollback transactionnel dans conftest.

### Phase 2 — Le lot métier décisif : transformer le coffre-fort en arme (lots 5–10)

7. **Extraction calendrier** : dates limites, visite, validité de l'offre, caution définitive, décennale — sortie structurée + confirmation humaine (rail existant des confirmations d'exigences).
8. **Premier slice LLM contrôlé CCAP/CCTP** : analyse clause-level (pénalités, abus, résiliation, responsabilité) sous le pattern S04-D déjà planifié — l'IA propose sourcé-page, le patron confirme, rien n'entre dans le solveur sans validation.
9. **Import coût de revient + réconciliation (C-05)** — code de contrôle obligatoire post-parse :
```python
def reconcile(line: NormalizedRow) -> None:
    computed = line.quantity_int * line.unit_price_minor  # entiers, pas de float
    if line.provided_total_minor is not None and computed != line.provided_total_minor:
        raise PricingReconciliationError(
            row=line.row_number,
            expected=computed,
            provided=line.provided_total_minor,   # rejet explicite, jamais silencieux
        )
```
   Ajouter `category="COST"` (`import_service.py:170`), coefficients, index BT01 paramétré par date d'effet.
10. **OCR + formats d'échange** : worker ocrmypdf/tesseract sur la quarantaine, support CSV/XML bordereaux (formats standards DPGF/BPU).
11. **Surfaces HTTP Decision & Case** : commandes `FinalizeDecision` et `AdvanceCaseStage` exposées, testées, auditées — rendre les machines à états opérables (C-06).
12. **Assemblage réponse** : DPGF remplie depuis les lignes importées + squelette mémoire technique versionné.
13. **Fiabiliser le webhook** : dead-letter table + alerte transport définie + politique de retry plafonnée (H-08).

### Phase 3 — Industrialiser (continu)

14. Charge 10→50→100 séquentiel puis 10 concurrent avec critères d'arrêt (déjà spécifiés dans les slides VPS) exécutés sur hôte réel.
15. Resource limits compose + healthchecks edge/workers + transport d'alertes (email/webhook ops).
16. Frontend : ESLint (typescript-eslint + react-hooks), router (deep-links), couche data (TanStack Query), suppression des swallows d'erreurs (`App.tsx:205-223`), harmonisation « Aléas », coverage Vitest activé.
17. Docs : régénérer `todo.md` depuis git, figer UNE source de vérité pour les métriques, déplacer les decks de présentation vers `docs/presentations/`.

### Feuille de route synthétique

| Horizon | Objectif | Critère GO |
|---|---|---|
| Semaine 1 | Gate VPS 7-preuves vert (réseau corrigé, upload streamé, CSP, cookies) | EICAR bloqué + HTTPS + restauration isolée OK |
| Sprint 2–4 | Dette structurelle résorbée, mypy noyau vert | `models.py` < 300 lignes, CI mypy obligatoire |
| Lots 5–10 | Cœur analytique (OCR, échéances, CCAP, coûts réconciliés, Decision opérable) | Un DCE réel scanné → fiche de risques complète + chiffrage deux côtés réconcilié |
| Continu | Industrialisation | p95 stable à 10 concurrents, zéro perte outbox, alertes livrées |

---

*Rapport généré automatiquement à partir d'une inspection exhaustive du code source. Chaque constat est re-vérifiable via les références `fichier:ligne` citées.*
