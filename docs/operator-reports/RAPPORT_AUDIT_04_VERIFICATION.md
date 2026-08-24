# RAPPORT D'AUDIT N°4 — VÉRIFICATION DE LA REMÉDIATION & PREUVES ONLINE

**Date** : 24 août 2026 · **Branche** : `docs/pricing-http-next-lot-28` @ `4114438`
**Méthode** : lecture des rapports devs (`rapports/`) → vérification ligne à ligne des 6 correctifs revendiqués → **exécution des preuves jamais faites** (PostgreSQL réel port 5433, suite complète 1 343 tests ×2 runs, couverture avec DB active, stack Docker déployé inspecté en live).
**Fait nouveau majeur** : contrairement au sandbox des devs, **cet environnement dispose de Docker et d'un stack V8 actif depuis 30 h**. Toutes les preuves « différées faute d'environnement » ont été exécutées en une session.

---

## 1. EXECUTIVE SUMMARY

### Note globale révisée : **58 / 100** (+7 vs audit n°3) — « Le coffre-fort a été renforcé ; l'atelier est toujours vide ; et la remédiation a introduit une bombe à retardement en production »

| Axe | n°3 | n°4 | Évolution |
|---|---|---|---|
| 🔐 Sécurité | 88 | **89** | Clé dev blacklistée en prod, rotation JWT câblée, compose dev verrouillé. |
| 🏗️ Ingénierie backend | 66 | **71** | Auth centralisée, machine à états réelle, savepoint idempotence : conformes. **Mais 1 régression production introduite** et couplage inter-modules quasi intact (35 imports). |
| 🖥️ Frontend | 42 | **58** | RBAC UI réel vérifié, session 401→refresh→retry complète y compris FormData, ErrorBoundary, nginx non-root. Restent : pas de routeur, ESLint cosmétique, timer proactif absent. |
| ⚙️ Opérations | 36 | **55** | Actions CI pinnées SHA, Trivy double image, image backend depuis `uv.lock`, workers en restart-policy. Restent : CI sans runner, extras hors périmètre CVE, object-storage mort dans l'image. |
| 💼 Valeur métier BTP | 26 | **26** | Aucun slice métier livré (assumé par les devs). CCAP/pénalités/prix plancher/DC1-DC4 toujours absents. |

### Les 5 découvertes de cette session (par ordre de gravité)

1. 🔴 **RÉGRESSION PRODUCTION introduite par la remédiation n°3** — prouvée par A/B test git : les transitions patronales passaient sur `bbf4fa9` (2 passed), échouent sur `4114438` (2 failed, `patron actions are append-only`). Cause : le fix « synchronisation de projection » (`transition_service.py:166-167`) fait un UPDATE du root sur une table protégée par un trigger append-only PostgreSQL (migration `20260818_0038:99-103`). **En production réelle, toute transition d'action patronale = HTTP 500.**
2. 🔴 **Le stack déployé tourne sur une base vide et se déclare healthy** — `alembic_version` à 0 lignes, zéro table métier, backend « healthy » depuis 30 h, login réel = HTTP 500, worker retention crashé (`Exited(1)`, `relation "dce_staged_objects" does not exist`). Le readiness check n'est qu'un `SELECT 1` (`bootstrap/application.py:648`). **Un statut « ready » ne garantit plus rien.**
3. 🟢 **La « dette de couverture » était un artefact de mesure** — couverture réelle avec PostgreSQL actif : **89,10 % > seuil 85,50 %** (mesuré sur 15 350 statements). Modules « nus » de l'audit n°3 : `handlers.py` 9,34 %→**87,59 %**, `preparation/service.py` 13,56 %→81,36 %, `authentication.py` 34 %→87,50 %, `production.py` 0 %→90,16 %. Les semaines de travail estimées sur ce sujet étaient fondées sur une mesure biaisée.
4. 🟠 **8 bugs de tests DB jamais détectés** — 100 % TEST-BUGS, causes racines établies (§4) : seeds sans flush triés alphabétiquement par l'UOW SQLAlchemy → FK violations ; assertion outbox sur chemin JSON erroné ; regex d'exception erronée.
5. 🟠 **Deux trous fonctionnels dans le durcissement** — extra `object-storage` ininstallable dans l'image backend (fonctionnalité vendue = crash garanti à l'activation) ; extras (torch, docling, boto3…) hors périmètre pip-audit ET Trivy.

---

## 2. VERDICT SUR LES CORRECTIFS REVENDIQUÉS PAR LES DEVS (réconciliation n°3)

| Correctif revendiqué | Verdict audit | Preuve |
|---|---|---|
| Helper auth centralisé `dependencies/auth.py` | ✅ **CONFORME** | 33/33 routes migrées ; zéro import route→route de privé ; 3 wrappers locaux résiduels = purement cosmétiques (`consultations.py:153` etc.) |
| Port storage inversé dans platform | ⚠️ **PARTIEL** | `platform/storage/ports.py:8` conforme, adaptateurs branchés — MAIS `submission/application/service.py:20` importe encore le port depuis `preparation.infrastructure` : l'inversion s'arrête aux adaptateurs, pas aux consommateurs |
| Machine à états patron_action | ⚠️ **CONFORME EN CODE, CASSÉE EN BASE** | Graphe pur `domain/state.py` + garde avant écriture + projection synchronisée même transaction + 13 tests domaine : tout est correct… sauf que l'UPDATE du root viole le trigger append-only → **régression production** (cf. §3) |
| Savepoint anti-race idempotence | ✅ CONFORME (non testé) | `dispatcher.py:170-189` correct ; aucun test n'exerce le chemin concurrent |
| Image backend depuis `uv.lock` | ⚠️ PARTIEL | `uv sync --frozen` réel (`backend.Dockerfile:19-41`) MAIS **l'extra `object-storage` est absent des ARG/install** alors que la preprod expose sa config (`docker-compose.preprod.yml:94`) → `RuntimeError("object-storage extra is not installed")` garanti |
| Actions SHA-pinnées + Trivy frontend | ✅ **CONFORME** | 6 références SHA complet vérifiées ; scan double image CRITICAL/HIGH exit-code 1 |
| Compose dev verrouillé | ✅ CONFORME (réserve) | Loopback 127.0.0.1:5432/8000, `development` immuable, no-new-privileges ×4 — MAIS `compose.local-dev.yml:6-7` publie 5433 sur 0.0.0.0 sans loopback : contournement livré dans le dépôt |
| Bootstrap refuse clé dev | ✅ **CONFORME** | `production.py:28-29` préfixe `dev-only-` refusé + test dédié avec la valeur exacte |
| JWT kid/rotation câblés preprod | ✅ **CONFORME** | `.env.preprod.example:99-100`, compose `:77-78`, consommation réelle `production.py:33-95` |
| RBAC UI frontend | ✅ **CONFORME** | Nav + sections conditionnées `isPatron` (`App.tsx:320-507`) ; plus aucun appel `/patron/*` collaborateur (test dédié `App.test.tsx:137-146`) ; union TS stricte |
| Session/retry/timeout | ✅ **CONFORME (réserve)** | Pipeline 401→refresh→retry couvre FormData/binaire, timeout 30s, logout purge en `finally` — MAIS `expires_in` toujours ignoré : aucun renouvellement proactif |
| ESLint/typecheck | ⚠️ **COSMÉTIQUE** | `eslint.config.js` utilise le parser Babel sur du TS, `typescript-eslint` absent du package.json, `no-unused-vars: off` sans remplaçant TS-aware |
| ErrorBoundary | ⚠️ PARTIEL | Présente, testée, loguée — mais « Réessayer » reset sans re-montage du sous-arbre : si l'erreur est déterministe, boucle de re-catch immédiate |
| README frontend corrigé | ✅ CONFORME | Token mémoire documenté, contradictions levées |

**Bilan : 8 conformes, 5 partiels, 0 non-conforme déclaré — mais 1 régression cachée derrière un « conforme ».**

### Corrections apportées aux affirmations de la réconciliation n°3

| Affirmation devs | Réalité vérifiée |
|---|---|
| « Le renderer ICS local ne dépend pas d'un import absent » | **Inexact** : `ics_calendar.py:62` importe `icalendar` et lève `RuntimeError("calendar extra is not installed")` sans l'extra. Le test ne passe qu'avec `--extra calendar`. Les 2 échecs ICS de cette session le prouvent. |
| « Tests DB restent dépendants de PostgreSQL » (présenté comme blocage externe) | PostgreSQL était disponible : la preuve a pris 7 minutes de run. Le blocage était méthodologique, pas environnemental. |
| « Remonter la couverture à 85,50 % » listée comme chantier ouvert prioritaire | **Obsolète** : atteinte à 89,10 % dès que les tests DB tournent. À retirer des tâches ouvertes. |

---

## 3. LA RÉGRESSION PATRON_ACTION — ANALYSE COMPLÈTE ET CORRECTIF EXACT

### Chaîne causale prouvée

```
Audit n°3 (constat R-06) : machine à états cosmétique
    ↓ remédiation 5f2aabf
transition_service.py:166-167 : action.state = target; action.aggregate_revision = rev   [ORM UPDATE]
    ↓ conflit avec
migration 20260818_0038_patron_actions.py:99-103 : trigger "patron actions are append-only"
    ↓ observé
psycopg.errors.RaiseException: patron actions are append-only → HTTP 500 sur TOUTE transition
    ↓ preuve A/B
bbf4fa9 : 2 passed · 4114438 : 2 failed  (mêmes tests, même base)
```

Pourquoi personne ne l'a vu : la validation de la réconciliation n'a exercé que les tests non-DB (« 885 passés, 458 désélectionnés »). La réconciliation le dit elle-même — mais présente ensuite le correctif comme validé.

### Correctif chirurgical recommandé (Option B — garde colonne-scopée)

Remplacer le trigger aveugle par une migration additive `0056` autorisant uniquement la mutation des colonnes de projection :

```sql
-- 0056_patron_actions_projection_sync.py
CREATE OR REPLACE FUNCTION patron_actions_projection_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.id            IS DISTINCT FROM NEW.id
        OR OLD.tenant_id     IS DISTINCT FROM NEW.tenant_id
        OR OLD.created_at    IS DISTINCT FROM NEW.created_at
        -- toute colonne historique non-projection doit être inchangée :
        OR OLD.actor_id      IS DISTINCT FROM NEW.actor_id
        OR OLD.case_id       IS DISTINCT FROM NEW.case_id
        THEN
            RAISE EXCEPTION 'patron actions are append-only';
        END IF;
        RETURN NEW;   -- seuls state / aggregate_revision / updated_at peuvent bouger
    END IF;
    RAISE EXCEPTION 'patron actions are append-only';
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS patron_actions_append_only ON patron_actions;
CREATE TRIGGER patron_actions_append_only
    BEFORE UPDATE OR DELETE ON patron_actions
    FOR EACH ROW EXECUTE FUNCTION patron_actions_projection_guard();
```

Alternative plus propre (Option C) : table de projection mutable séparée `patron_action_current` alimentée dans la même transaction, root strictement append-only. À préférer si un autre root subira le même besoin.

**Régression test obligatoire** : réactiver `test_patron_action_transitions.py` en gate bloquant — il vient de prouver sa valeur.

---

## 4. LES 8 BUGS DE TESTS DB — CAUSES RACINES ET CORRECTIFS

Verdict global : **100 % TEST-BUG, zéro défaut production** dans ces 8 cas. Ils dormaient depuis leur création car aucun run n'avait jamais activé les marqueurs DB contre PostgreSQL réel.

| Famille | Cause racine (fichier:ligne) | Correctif |
|---|---|---|
| BOAMP observation ×2, qualification ×1, event_bus worker ×2 | Seed multi-tables dans UNE transaction **sans flush** : l'UOW SQLAlchemy trie les INSERT par nom de classe (`app.modules…` < `app.platform…`), donc `INSERT opportunity_watch_profiles/domain_events` part AVANT `INSERT tenants` → FK violation | Ajouter `session.flush()` après l'insert du `TenantRecord` dans `_seed()` (`test_boamp_observation_persistence.py:55-110`, `test_opportunity_event_bus_persistence.py:26-70`) — pattern déjà utilisé par les tests qui passent |
| Capacity run ×1 | `pytest.raises(ValueError, match="idempotency")` mais l'exception lève *"optimization run key was reused with a different request"* (`run_repository.py:76`) | Corriger la regex : `match="reused"` ou aligner le message de l'exception |
| Watch profile ×1 | Assertion outbox filtre sur `payload_json["profile_id"].astext` alors que le dispatcher écrit sous `payload_json["data"]["profile_id"]` (`dispatcher.py:266-273`) | Requêter `payload_json["data"]["profile_id"].astext` |
| ICS ×2 (env, pas bug) | Extra `calendar` absent du venv local ; `ics_calendar.py:62` fail-closed | Installer `--extra calendar` localement ; ajouter l'extra au job CI backend |

**Enseignement transverse** : la suite DB n'est pas sûre pour exécution multi-processus sur une seule base (TRUNCATE/downgrade par module + second process = courses). Isoler par base template ou verrou fichier avant de paralléliser.

---

## 5. AUTOPSIE DU STACK DÉPLOYÉ (constaté en live)

| Observation | Preuve | Signification |
|---|---|---|
| Base totalement vide | `alembic_version` 0 lignes, 1 seule table | Le compose dev n'applique JAMAIS les migrations automatiquement ; `deploy-preprod.sh:104-105` est procédural et contournable |
| Backend « healthy » 30 h | `/healthz/ready` = `{"database":"ok"}` via simple `SELECT 1` (`application.py:648`) | Le readiness gate valide la connectivité, pas l'état fonctionnel — un déploiement vide passe vert |
| Login réel = 500 | curl POST `/api/v1/auth/login` payload valide → 500 | Le système déployé ne peut traiter aucune opération métier |
| Worker retention crashé sans redémarrage | Container `Exited(1)` il y a 5 h, logs = `UndefinedTable` | En dev, aucune restart policy (`docker-compose.yml:58-75`) ; en preprod `restart: unless-stopped` présent mais postgres-healthy ≠ schéma-migré : le scénario reste possible |
| Conflit de ports hérité V7 | Postgres V7 occupe 5432 (`smart_ao_postgres`), V8 sur 5433 | Explique les échecs historiques « password authentication failed » des tentatives de test : les tests par défaut visaient la base V7 |

**Correctifs structurels** : service `migrate` one-shot en `depends_on: service_completed_successfully` des workers+backend dans les deux composes ; readiness check étendu d'un `SELECT count(*) FROM alembic_version WHERE version_num = '<head>'` ; restart policy sur le worker dev.

---

## 6. FAILLES RESTANTES NON TRAITÉES (héritées + nouvelles)

| ID | Gravité | Constat | Statut vs audit n°3 |
|---|---|---|---|
| N-01 | 🔴 | Régression patron_action (§3) | NOUVEAU — introduit par le fix |
| N-02 | 🔴 | Readiness gate = SELECT 1 ; stack vide = healthy (§5) | NOUVEAU — révélé par l'exécution live |
| N-03 | 🟠 | Extras (torch, docling, boto3, aiosmtplib) hors pip-audit (`ci.yml:48-50` exporte sans `--extra`) et hors build Trivy (`ci.yml:108` sans args) | NOUVEAU — angle mort CVE sur les dépendances les plus lourdes |
| N-04 | 🟠 | Extra `object-storage` ininstallable dans l'image ; activation runtime = RuntimeError garanti | CONFIRMÉ |
| N-05 | 🟠 | Couplage inter-modules : 35 imports croisés subsistent dont 20× `X.application → Y.infrastructure` (~45→35 : traitement cosmétique) ; membership→`dce.application.commands` ×5 malgré le shared kernel | QUASI INTACT |
| N-06 | 🟠 | Outbox : topic `cockpit_projection` sans consommateur ni politique de rétention — assumé ouvert par les devs, rien n'a bougé | HÉRITÉ |
| N-07 | 🟡 | CI GitHub toujours morte (run `32673495930` : 3 jobs, `steps: []`, ~5 s) — tous les durcissements CI de ce lot sont **statiquement vrais mais jamais exécutés** | HÉRITÉ |
| N-08 | 🟡 | MFA/TOTP : cérémonie absente, `mfa_required=True` jamais activé | HÉRITÉ (assumé) |
| N-09 | 🟡 | Import XLSX pricing toujours sans ClamAV/libmagic | HÉRITÉ (assumé) |
| N-10 | 🟡 | Frontend : pas de routeur (deep-links impossibles), App.tsx 536 lignes / panels à 26 props, bus message unique last-wins, UUIDs manuels ×39 sites, montants centimes non documentés, listes tronquées silencieuses (scénarios pricing plafonnés à 4 !) | HÉRITÉ |
| N-11 | 🟡 | `compose.local-dev.yml` publie PostgreSQL sur 0.0.0.0:5433 sans loopback — contournement du verrou livré dans le dépôt | NOUVEAU |
| N-12 | 🟢 | Types morts (`DecisionDossierItem`, `BoampOpportunity`), 2 warnings exhaustive-deps (`App.tsx:202,211`) | HÉRITÉ |
| N-13 | 🟢 | Code mort persistant : `watch_profile_service.py` module fantôme, `ProcessInboxRecord`, adaptateur fake en prod, ligne morte `transition_service.list_open:105-115` | HÉRITÉ |

---

## 7. PLAN D'ACTION PRIORITISÉ (lot suivant)

### Lot A — Stop the bleeding (immédiat, < 1 jour)
1. **Corriger la régression patron_action** : migration 0056 garde colonne-scopée (SQL §3) OU bascule table de projection. Gate : `test_patron_action_transitions.py` vert sur DB.
2. **Corriger les 4 seeds/assertions de tests DB** (flush tenant, regex capacity, chemin JSON outbox) — 30 min de travail, 8 tests récupérés.
3. **Readiness check fonctionnel** : vérifier la présence du schéma head dans `/healthz/ready`.
4. Ajouter `service migrate` + `depends_on: service_completed_successfully` dans docker-compose.yml et preprod ; restart policy sur le worker dev.
5. Ajouter `--extra` correspondants au pip-audit CI et passer les build args au build Trivy ; ajouter l'ARG `object-storage` au Dockerfile (ou retirer la config preprod morte).

### Lot B — Consolider la preuve (semaine 1)
6. **Script de preuve locale reproductible** (`scripts/prove_online.sh`) : start_local_postgres → pytest full → coverage → verdict horodaté. La valeur de cette session entière tient dans un script de 20 lignes qui n'existe pas encore.
7. Réparer les runners GitHub Actions (self-hosted si nécessaire) — condition de fusion PR #49.
8. Définir le contrat `cockpit_projection` + rétention outbox/domain_events (assumé ouvert, bloquant croissance DB).
9. Nettoyer le couplage inter-modules par vagues : d'abord les 20 `application→infrastructure` croisés (mécanique), puis membership→dce.commands.

### Lot C — Valeur métier (la vraie priorité produit, semaines 2-8)
10. **CCAP-RISK-01** : pénalités/retene de garantie/avance/cautionnement/délais → fiches de risque confirmables (rails existants).
11. **COST-BASIS-01** : coûts par ligne + prix plancher + alerte anti-ruine (les totaux coûts sont à zéro aujourd'hui : la marge affichée est fictive — c'est LE risque utilisateur n°1).
12. **DOC-GEN-01** : DC1/DC2/DC4 générés depuis la bibliothèque entreprise.
13. Boucle décisionnelle GO/NO-GO fermée (routes d'écriture DEC manquantes).
14. Frontend : routeur, chaînage des agrégats (fin des UUIDs manuels), euros à la frappe, pagination.

---

## 8. CONCLUSION

Cette session a démontré trois choses :

1. **Les devs ont honnêtement réconcilié** : les verdicts de leur rapport sont largement exacts, les correctifs livrés sont réels et propres (8 conformes), et ils assument explicitement ce qu'ils n'ont pas fait. La qualité de documentation de ce projet est remarquable.
2. **Mais leur méthode de validation a une faille structurelle** : valider « hors DB » a masqué pendant des semaines la vraie couverture (89,10 %, gate déjà passé), laissé dormir 8 bugs de tests, et surtout laissé passer une régression production dans le lot précisément censé corriger l'audit. **Le correctif de l'audit n°3 a cassé la fonctionnalité qu'il réparait — et seul un run de 7 minutes contre PostgreSQL réel pouvait le voir.**
3. **Le goulot d'étranglement du projet n'est plus le code, c'est la preuve** : chaque élément « différé faute d'environnement » s'est exécuté ici en minutes. Le prochain lot doit installer la preuve continue (script online + runners vivants) comme précondition de merge — sinon la quatrième réconciliation répétera la troisième.

**Verdict opérationnel maintenu : NO-GO production** — mais pour la première fois, avec une cartographie complète, mesurée et exécutable de ce qui sépare le projet du GO.
