# Revue consolidée des audits SMART_AO V8

**Date de mise à jour :** 22 août 2026
**Branche :** `docs/pricing-http-next-lot-28`
**HEAD vérifié :** `295fde8` — merge de `audit/consolidated-remediation` avec conservation du flux d’authentification navigateur
**Périmètre :** six audits déjà consolidés, le rapport système BTP et le rapport de gate Docker fournis le 22 août 2026, désormais archivés dans [`docs/operator-reports/`](operator-reports/). Les deux rapports ont été lus intégralement et confrontés au HEAD `295fde8`.
**Méthode :** confrontation de chaque constat avec le code, les migrations, les tests, la configuration et les résultats locaux. Un finding n’est déclaré corrigé que lorsqu’il est reproduit ou directement démontré, puis couvert par un test ou un contrôle adapté.

## 1. Verdict exécutif

Les six rapports sont utiles, mais ils décrivent plusieurs HEAD historiques et répètent certains constats. Les rapports joints 4 à 6 ont été lus intégralement et fusionnés avec la première matrice. Leurs affirmations sur Alembic, Trivy, Caddy, le webhook non signé, le frontend sans tests et le token en `localStorage` n’étaient plus toutes valables au HEAD actuel : plusieurs avaient déjà été corrigées dans `d2d1701` ou étaient fondées sur un état antérieur.

Les nouveaux risques effectivement confirmés des audits précédents ont été corrigés dans `ce0154f`, puis le nouveau rapport BTP a conduit à des corrections supplémentaires dans `0db2eff` : egress réseau de ClamAV et du worker webhook, lecture HTTP pricing bornée en chunks, exclusion des démonstrations/tests des images et audit pnpm frontend ; garde de taille décompressée pour DOCX, observabilité des erreurs ClamAV et d’extraction, parsing strict des verdicts ClamAV, arrondi monétaire commercial déterministe, normalisation des nombres européens, rejet des totaux pricing incohérents, protection PostgreSQL des snapshots financiers publiés, séparation des variables d’environnement Compose, contrôle d’alignement `PGPASSWORD`/`POSTGRES_PASSWORD` et verrouillage explicite de pnpm.

Les sujets qui exigent une décision d’architecture ou un environnement réel ne sont pas artificiellement déclarés résolus. Cela concerne notamment la validation HTTPS réelle du flux navigateur, le consommateur de projection `cockpit_projection`, la limitation de concurrence d’extraction, le stockage objet externe, le filtrage SSRF/DNS du webhook, la récupération de receipts distribués et la validation Docker/VPS.

> **Conclusion :** le code local a été durci sur les findings reproductibles. La PR #49 ne doit toujours pas être fusionnée tant qu’un run GitHub n’a pas réellement exécuté ses étapes avec un runner attribué. L’absence de Docker/VPS dans cet environnement interdit également de déclarer le gate opérationnel terminé.

## 2. Matrice fusionnée des constats

### 2.1 Findings confirmés et corrigés avant ce lot

| Finding | Vérification au HEAD actuel | Décision |
|---|---|---|
| Alembic ignore `SMART_AO_DATABASE_URL` | `backend/alembic/env.py` utilise déjà `resolve_database_url()` pour les modes online/offline. | Faux au HEAD actuel ; aucune modification supplémentaire. |
| Trivy cible un Dockerfile racine inexistant | Le workflow vérifie, construit et scanne `ops/docker/backend.Dockerfile`. | Obsolète ; le scan n’est plus un no-op structurel. |
| `/healthz/live` et `/healthz/ready` tombent sur le SPA | Le matcher Caddy exact de l’ancien HEAD ne couvrait pas les sous-chemins. | Corrigé dans `d2d1701` par reverse proxy du bloc `/healthz /healthz/*` vers `backend:8000`. |
| IP client et rate limiting derrière Caddy | Uvicorn fait confiance uniquement au CIDR interne Compose `172.30.0.0/24`. | Corrigé dans `d2d1701`, avec test de contrat ops. |
| Webhook d’export sans signature | Le worker actuel exige un secret si l’URL existe et signe le JSON en HMAC-SHA256 dans `X-SMART-AO-Signature`. | Corrigé dans `d2d1701`; le finding du rapport 6 est obsolète au HEAD actuel. |
| Timing oracle de login | Le chemin identité inconnue exécute un hash Argon2id factice avant le refus neutre. | Corrigé dans `d2d1701`. |
| Import pricing chargé et contrôles ZIP incomplets | La preview pricing limite les lignes, vérifie les octets réellement décompressés et ne matérialise plus toutes les lignes avant la borne. | Corrigé dans `d2d1701`; le nouveau contrôle monétaire est ajouté dans `ce0154f`. |
| Token et URL API frontend persistés | Le token est mémoire seulement et l’URL n’est plus lue depuis un stockage persistant ; HTTPS same-origin est imposé hors localhost. | Corrigé dans `d2d1701`; l’affirmation `localStorage` des rapports 5 et 6 est historique. |
| Frontend sans tests et `App.tsx` de 803 lignes | Le HEAD actuel contient 18 fichiers de tests, `App.tsx` est réduit et les features pricing/submission sont extraites. | Faux/obsolète ; 74 tests frontend passent. |
| OpenAPI actif en production | Le bootstrap de production désactive OpenAPI, Swagger et ReDoc tout en les conservant en développement/tests. | Corrigé dans `d2d1701`. |
| CSP edge absente | Le Caddyfile actuel contient une CSP same-origin et une limite de corps de 150 MiB. | Corrigé dans `d2d1701`. |
| Packaging frontend runtime/build mélangé | Vite, TypeScript et le plugin React sont sous `devDependencies`. | Corrigé dans `d2d1701`. |
| Panne de suite globale liée au benchmark Alembic | Le benchmark n’effectue plus de downgrade global pendant les tests. | Corrigé dans `d2d1701`; la suite complète passe. |

### 2.2 Findings DCE confirmés et corrigés dans ce lot

| Finding | Preuve et correction |
|---|---|
| DOCX potentiellement gonflé avant le contrôle de paragraphes | `python-docx` pouvait ouvrir l’archive avant la borne métier. `extraction.py` vérifie désormais les tailles déclarées et les octets effectivement lus dans l’archive, avec un plafond décompressé de 50 MiB avant l’appel à `Document`. |
| Texte d’une page ou d’un paragraphe trop grand avant fragmentation | `_fragmentize()` rejette maintenant une entrée dépassant `MAX_TOTAL_CHARS` avant de produire une liste de fragments. Le buffering de la chaîne produite par la bibliothèque reste borné par les limites du format et fait partie de la dette de concurrence ci-dessous. |
| Erreurs ClamAV silencieuses | Les deux niveaux de capture produisent désormais des événements de log bornés par type d’erreur, sans chemin privé, payload, nom de fichier ou message sensible. Le comportement fail-closed reste inchangé. |
| Erreurs d’extraction silencieuses | Les erreurs `ValueError` de parsing et exceptions inattendues sont journalisées par type et `media_type`, tandis que la réponse persistée reste `FAILED_SAFE` ou `EXTRACTION_PARSE_FAILED` sans détail parser. |
| Parsing ClamAV par suffixe trop permissif | Le parseur exige désormais le préfixe `stream:` et accepte exactement `ok` ou un verdict se terminant par ` found`; les réponses ressemblantes mais non conformes deviennent `ERROR`. |
| Absence de fraîcheur minimale de signature ClamAV | La version ClamAV est capturée, mais aucune politique de version minimale n’est spécifiée par le contrat. Ce point reste une décision d’exploitation et n’a pas été inventé dans le code. |
| MIME, chemin et fail-closed ClamAV | `libmagic`, les clés serveur, la défense anti-traversal, le flux INSTREAM réel et le rejet lorsque le scanner est indisponible ont été vérifiés comme déjà corrects. Aucun correctif spéculatif n’a été ajouté. |
| Isolation tenant DCE | Les repositories, handlers, lecteurs, FKs composites et routes ont été vérifiés tenant-scoped. Aucun accès inter-tenant reproductible n’a été trouvé. |
| LLM ou prompt injection dans DCE | Le module est déterministe, sans LLM, réseau d’IA, embeddings ou inférence ; les regex sont bornées et les extraits sont revalidés. Le finding est faux pour ce périmètre. |
| TODO/stubs dans le module DCE | Le scan ne montre pas de TODO/FIXME ou scanner mocké dans ce module. Les méthodes `NotImplementedError` identifiées ailleurs sont des ports hexagonaux, pas des endpoints actifs. |

### 2.3 Findings DevOps, pricing et financier confirmés et corrigés dans ce lot

| Finding | Preuve et correction |
|---|---|
| `.env.preprod` injecté dans tous les services | Le Compose n’utilise plus `env_file` pour le backend et les workers. Chaque service reçoit une allowlist : JWT seulement au backend, paramètres de rétention seulement au worker de rétention, secret webhook seulement au worker webhook, et identifiants DB nécessaires à chaque processus. PostgreSQL ne reçoit que ses variables propres. |
| `PGPASSWORD` non aligné avec le rôle PostgreSQL | Le template documente l’égalité obligatoire et `deploy-preprod.sh` exige `PGPASSWORD`, refuse les placeholders et échoue si sa valeur diffère de `POSTGRES_PASSWORD`. |
| Toolchain pnpm non verrouillé entre CI et Docker | `web/package.json` déclare `packageManager: pnpm@11.21.0`, aligné avec le workflow. La régénération lockfile-only ne modifie pas les résolutions. |
| Arrondi bancaire half-even du pricing | Les montants sont désormais convertis en minor units avec `ROUND_HALF_UP`, conformément à l’arrondi commercial retenu pour l’import. |
| Artifacts de flottants Excel | Le parseur repasse par `Decimal`, rejette les valeurs non finies et normalise les séparateurs ; les valeurs comme `0.30000000000000004` sont ramenées à la minor unit half-up attendue. |
| Total importé non cohérent avec quantité × prix unitaire | Lorsque quantité et prix unitaire existent, le total est recalculé. Un total fourni qui diffère reçoit `TOTAL_PRICE_MISMATCH` et la ligne n’est pas valide. |
| Formats français de milliers | Les espaces, espaces insécables, virgules décimales et formats mixtes comme `1.234,56` sont normalisés de manière déterministe. |
| Snapshot financier publié modifiable par SQL direct | La migration `20260822_0049` ajoute un trigger PostgreSQL qui interdit `UPDATE` et `DELETE` lorsque l’ancien snapshot est `PUBLISHED`. La transition `DRAFT → PUBLISHED` reste autorisée. Les lignes avaient déjà un trigger append-only. |

### 2.4 Constats vrais mais différés explicitement

| Sujet | Pourquoi il reste ouvert |
|---|---|
| Validation navigateur HTTPS réelle | Le backend et le cockpit possèdent désormais login/refresh/logout avec cookie HttpOnly, CSRF, profil `/auth/me`, token mémoire et renouvellement contrôlé sur 401. Les tests locaux passent, mais le parcours doit encore être exercé sur une URL HTTPS réelle avec cookies Secure. |
| Couverture endpoint frontend | Plusieurs opérations DCE, créations/archives pricing, workflows de blocage, publications et écritures patronales ne sont pas encore consommées par le cockpit. Le chiffre exact des rapports dépend de leur HEAD ; la lacune fonctionnelle est réelle mais ne se corrige pas par un simple alias d’API. |
| Topic `cockpit_projection` sans consommateur | Le dispatcher et certains handlers produisent ce topic alors que les workers visibles consomment surtout `submission.package.exported` et `dce_staging_retention`. Le finding structurel est confirmé ; supprimer les messages ou les marquer publiés sans projection métier serait dangereux. Il faut d’abord définir le projection builder et sa reconstruction. |
| Recovery de receipts PROCESSING | Les statuts et index de recovery existent, mais le dispatcher crée le receipt et le handler dans une même transaction : un crash avant commit annule le receipt plutôt que de laisser durablement `PROCESSING`. Le besoin de recovery distribué peut exister pour d’autres modes d’exécution, mais le scénario décrit n’est pas démontré avec ce dispatcher. Il est donc différé, pas présenté comme corrigé. |
| Mémoire et concurrence d’extraction | La source est bornée à 128 MiB, mais chaque extraction peut encore bufferiser la source et les structures parser ; une limite de workers ou une file dédiée doit être choisie avec des mesures de charge. |
| Stockage local versus S3/MinIO | Le stockage disque privé est réel, atomique, non-écrasant, `0600`, anti-traversal et tenant-scoped par clé résolue par DB. Le passage à un backend objet est une décision d’exploitation/VPS, pas une vulnérabilité démontrée dans l’adaptateur actuel. |
| Clé tenant au niveau du port de stockage généré | Les appelants résolvent la ligne DB tenant-scoped avant `read()`, et le port rejette la traversée. Un contrôle tenant explicite dans le port peut être ajouté lors d’une future abstraction de stockage, mais aucun accès public direct à une clé n’est exposé actuellement. |
| SSRF/DNS du webhook | Le secret HMAC est maintenant obligatoire, mais la validation destination/IP/DNS et la protection contre rebinding doivent faire l’objet d’un lot séparé avant toute URL contrôlée par un opérateur non totalement fiable. |
| Dead-letter et plafond de retries | Les workers possèdent leases, backoff et statuts retry, mais la politique finale de dead-letter et d’alerte doit être spécifiée avant implémentation. |
| Fraîcheur ClamAV | La capture de version est présente ; le seuil de fraîcheur doit être défini avec l’image et la politique d’exploitation réelles. |
| Demo `app/demonstrations/m1.py` | Les clés historiques de démonstration ne représentent pas le chemin de production. Le nouveau `.dockerignore` exclut désormais `backend/app/demonstrations/` et `backend/tests/` de l’image backend. Le harness reste disponible dans le dépôt pour les tests. |
| Monitoring externe et backups hors VPS | Les scripts de backup/restore et la rotation existent, mais aucune preuve de chiffrement, transfert hors hôte, restauration isolée réelle ou supervision externe ne peut être produite sans Docker/VPS. |
| MFA step-up effectif | Les modèles et capabilities représentent la fraîcheur MFA, mais le branchement sur les opérations sensibles reste un lot de sécurité dédié. |
| Extraction des modèles ORM et réorganisation tests | Les dettes d’architecture sont réelles, mais un déplacement mécanique risquerait de casser les frontières sans bénéfice comportemental immédiat. |

### 2.5 Constats faux, obsolètes ou non démontrés

| Constat | Verdict |
|---|---|
| Alembic cassé en préproduction | Faux au HEAD vérifié : l’URL runtime est résolue par l’environnement applicatif. |
| Trivy complètement no-op par absence de Dockerfile racine | Obsolète : le workflow vise le vrai Dockerfile `ops/docker/backend.Dockerfile` et construit l’image. |
| Caddy `/healthz/*` répond encore au HTML SPA | Obsolète après `d2d1701`; le contrat ops verrouille le reverse proxy backend. |
| Frontend sans tests, sans features extraites et `App.tsx` à 803 lignes | Obsolète ; 17 fichiers de tests sont présents et passent. |
| Token frontend encore dans `localStorage` | Obsolète après `d2d1701`; le token est en mémoire d’onglet. |
| Webhook sans HMAC au HEAD actuel | Obsolète après `d2d1701`. |
| Absence totale de protection DB sur les lignes financières | Faux : `financial_report_lines` possède déjà un trigger append-only ; la nouvelle migration complète la protection du snapshot publié. |
| Evidence submission nécessairement financière car sa classification est `INTERNAL_OPERATIONAL` | Non démontré : le record contient des hashes, une référence externe et des notes déjà redacted ; l’autorisation reste patronale et aucun montant n’est exposé. À revoir si le contrat métier élargit le contenu. |
| Deux tests de concurrence seulement, couverture `.coverage` racine ou compteurs LOC comme preuve de qualité | Non démontré de manière reproductible et insuffisant comme critère isolé. Les tests sont répartis dans plusieurs suites et les métriques doivent être produites par le pipeline courant. |
| LLM, prompt injection, path traversal ou défaut d’isolation tenant dans DCE | Non reproduits ; les contrôles vérifiés sont présents. |

### 2.6 Nouveau rapport système BTP : findings revérifiés au HEAD `295fde8`

| Finding | Verdict au HEAD actuel | Action |
|---|---|---|
| C-01 — stack jamais exécutée sur Docker/VPS | Confirmé. Les validations statiques et locales existent, mais aucun build Compose, EICAR, HTTPS ou restore réel n’est démontrable sans hôte équipé. | Bloquant opérationnel externe ; aucun faux PASS ne sera déclaré. À exécuter sur VPS/ordinateur avec Docker. |
| C-02/C-03 — ClamAV et worker webhook sur réseau `internal` sans egress | Confirmé au HEAD précédent et corrigé dans `0db2eff` : les deux services rejoignent désormais `internal` et `edge`; PostgreSQL et backend restent internal-only. | Couvert par contrat Compose. Le gate réel reste à exécuter. |
| C-04 — absence OCR et formats CSV/XML | Confirmé. Aucun OCR ni parser CSV/XML n’est présent dans le backend actuel. | Vrai manque produit, non corrigeable par un patch ops ; à traiter dans un lot métier OCR/échanges. |
| C-05 — import ventes uniquement, coûts/BT01 absents | Partiellement confirmé. `import_service.py` force encore `SALES` et le coût de revient/BT01 n’existent pas ; en revanche qty×PU et le total importé sont maintenant réconciliés dans `import_preview.py`. | Réconciliation déjà corrigée ; coût, coefficients et BT01 restent un lot métier dédié. |
| C-06 — aucune écriture HTTP Decision/Case | Confirmé pour la surface actuelle : la route patron décision est en lecture seule et les transitions write ne sont pas exposées par cette surface. | À traiter dans le lot métier “décision opérable”, avec permissions, idempotence et audit. |
| H-01 — `platform/security/models.py` monolithique | Dette structurelle confirmée, sans faille démontrée. | Refactor incrémental après stabilisation produit ; pas de déplacement mécanique avant couverture de frontières. |
| H-02 — JWT en `localStorage` | Faux au HEAD actuel : le token n’est pas persisté. Le login, la restauration par cookie refresh + CSRF, le logout et le profil `/auth/me` sont maintenant raccordés côté navigateur. | Corrigé localement dans `448382f`; valider encore sur HTTPS réel avec cookies Secure. |
| H-03 — upload pricing lu intégralement avant limite | Partiellement corrigé dans `0db2eff` : la route lit par chunks et rejette au-delà de 10 MiB avant d’appeler le service ; la preview reste volontairement bornée en mémoire pour son hash et son parsing. | Test HTTP 413 ajouté ; un passage streaming disque complet peut rester une optimisation ultérieure. |
| H-04 — rate limiter process-local et rotation JWT mono-clé | Confirmé comme limite de scale-out. La confiance IP derrière Caddy est déjà bornée au CIDR interne. | Redis/PG partagé et rotation `kid` à spécifier avant multi-réplique ; pas de correction spéculative locale. |
| H-05 — CSP absente et métriques publiquement exposées | Partiellement obsolète : CSP présente depuis `d2d1701`, et `/metrics` n’est pas routé par Caddy vers le backend public. L’absence de throttling global et le health public sont des choix à revoir. | Pas de duplication de correctif ; revue d’exposition et throttling à intégrer au gate ops. |
| H-06 — mypy/pyright absent | Confirmé comme écart documentaire si le noyau exige une vérification statique obligatoire ; ce n’est pas une faille runtime reproduite. | Ajouter progressivement le typage dans un lot qualité séparé, après le vertical slice produit. |
| H-07 — E2E multi-modules, concurrence réelle et charge absents | Confirmé comme couverture manquante ; les tests unitaires et DB existants ne constituent pas une preuve de charge réelle. | À exécuter sur PostgreSQL/Docker réel avec critères d’arrêt, sans gonfler artificiellement la couverture. |
| H-08 — dead-letter/alerting webhook absents | Confirmé et déjà classé dette. | À traiter avec plafond de retries, état terminal, alerte et runbook. |
| H-09 — erreurs frontend silencieuses | Confirmé puis corrigé pour les trois chargements du cockpit concernés. | `refreshActions` et `refreshScenarios` affichent maintenant l’erreur sans effacer silencieusement l’état utile ; `refreshDecisionDossier` traite 404 comme absence normale et expose les autres erreurs. Tests App dédiés ajoutés. |
| H-10 — classification RC naïve | Risque plausible mais non mesuré comme défaut universel ; le classifieur est déterministe et borné, mais les négations/portées sont limitées. | Ajouter un corpus de cas BTP et une politique de confirmation humaine avant toute réécriture. |
| M-11 — garde lexicale financière incomplète | Risque confirmé en théorie, mais aucune fuite reproductible démontrée dans les contrats actuels ; le système bloque déjà plusieurs motifs et filtre les contrats collaborateur. | Renforcer par tests de montants/devise et classification, sans regex destructrice non validée. |
| M-12/M-13/M-14 — scaffolding, router/linter et drift documentaire | Plusieurs éléments sont vrais comme dette ; les démonstrations/tests sont désormais exclus des images, mais le router et l’outillage frontend restent incomplets et les chiffres historiques doivent rester datés. | Nettoyage documentaire et frontend à planifier ; aucun impact immédiat à masquer comme “prod ready”. |

### 2.7 Priorité de mise en production issue des rapports BTP et gate Docker

Le projet ne sera déclaré **prod ready** qu’après quatre preuves indépendantes : (1) CI GitHub réellement exécutée et verte, (2) déploiement Docker/VPS avec egress, migration, HTTPS, health JSON, EICAR et backups/restauration, (3) authentification navigateur exercée sur HTTPS réel sans bearer manuel, et (4) parcours métier validé sur un DCE réel. Le flux auth est maintenant implémenté et testé localement, mais sa preuve navigateur sur HTTPS réel reste ouverte. Le nouveau rapport a raison de recommander de geler les optimisations de couverture non critiques, mais les invariants de confidentialité financière, d’idempotence, d’append-only et de fail-closed restent non négociables.

## 3. Corrections et tests des commits `ce0154f`, `0db2eff`, `448382f` et `295fde8`

Le commit `ce0154f` ajoute la migration `20260822_0049_financial_snapshot_immutability.py`, les protections d’extraction DOCX, les logs bornés, le parseur monétaire, la séparation Compose et les contrats de non-régression associés. Le commit `42839b5` ajoute ensuite la validation JSON des healthchecks, l’horodatage réel `completed_at` des receipts, l’exclusion Docker des démonstrations/tests et l’audit pnpm frontend en CI. Le commit `0db2eff` corrige l’egress Compose de ClamAV et du worker webhook, borne la lecture HTTP pricing par chunks et ajoute les tests de rejet 413. Le commit `448382f` ajoute le profil serveur `/api/v1/auth/me`, le hook frontend login/refresh/logout, la restauration par cookie CSRF, le rejeu contrôlé après 401 et le retrait complet du bearer manuel de la modale. Le merge `295fde8` ajoute les ignores Docker spécifiques aux Dockerfiles, l’override PostgreSQL local, les defaults JWT strictement dev-only, archive les deux rapports fournis et rend visibles les erreurs des trois chargements cockpit sans réintroduire de bearer manuel. Les tests couvrent notamment : archive DOCX au-delà de la limite décompressée, alerte ClamAV sans fuite de message, réponse ClamAV non conforme, arrondi half-up, nombres européens, total incohérent, trigger DB de snapshot publié, allowlists Compose et validation des mots de passe préproduction.

## 4. Validation locale finale

| Contrôle | Résultat |
|---|---|
| Backend complet | **1 074 passed, 7 warnings tiers**, couverture **92,87 %** avec seuil strict 85,50 % atteint. |
| Tests ciblés nouveaux/impactés | **41 passed** sur pricing et contrats ops ; les tests auth backend existants restent verts. |
| Frontend Vitest | **74 passed dans 18 fichiers**. |
| Build frontend | `tsc -b` et `vite build` verts. |
| Ruff | Vert sur le dépôt. |
| Bandit | Vert sur `backend/app`. |
| detect-secrets | Vert avec les exclusions et la baseline prévues ; warnings de commentaires non bloquants. |
| Alembic | La base locale initialement en retard a été mise à niveau par `upgrade head`, puis `alembic check` a confirmé **No new upgrade operations detected** ; head `20260822_0049`. Après une suite pytest, l’upgrade doit précéder `alembic check` car certaines fixtures nettoient le schéma. |
| Diff | `git diff --check` vert. |
| Docker/Caddy/HTTPS/ClamAV réel | Docker est indisponible dans le sandbox et aucun VPS n’est disponible. Le rapport opérateur fourni affirme un gate externe, mais ses logs/artifacts ne sont pas présents ici : preuve archivée, non revalidée. |

## 5. GitHub et séquencement

Le code de ce lot est poussé sur la branche de la PR #49. Le commit de merge `295fde8` intègre les changements retenus de `audit/consolidated-remediation` sans écraser le flux auth récent :

- `448382f` — `feat: connect browser authentication flow`
- `0db2eff` — `fix: unblock preprod egress and bound pricing uploads`
- `42839b5` — `ops: make health and receipt checks truthful`
- `ce0154f` — `security: harden dce pricing and preprod boundaries`
- `1264fc7` — réconciliation documentaire précédente
- `d2d1701` — première remédiation de sécurité confirmée

Le healthcheck local valide désormais le corps JSON de liveness/readiness, la CI contient un audit pnpm de production, Compose donne un egress explicite uniquement à ClamAV et au worker webhook, et le frontend possède un flux auth navigateur localement testé. La PR #49 reste ouverte et ne doit pas être fusionnée tant qu’un runner GitHub n’a pas exécuté les étapes backend, frontend et image-security. Le run `32593055484` sur `295fde8`, puis sa relance manuelle à 19:15 UTC, se sont terminés en 2–3 secondes avec `runner_name: ""` et `steps: []` pour `backend`, `frontend` et `image-security` ; les jobs n’ont donc exécuté aucun code. Comme les runs précédents, il s’agit d’un échec d’attribution de runner avant tout test, et non d’un verdict fonctionnel. Le prochain lot métier `SUBMISSION-SIGNATURE-HTTP-01` reste bloqué jusqu’à une CI réellement exécutée et verte, conformément au séquencement demandé.

## Références de code et de rapports

[1]: ../backend/app/modules/dce/application/extraction.py "Extraction DCE et limites de formats"
[2]: ../backend/app/modules/dce/application/upload.py "Orchestration upload DCE et échecs fail-closed"
[3]: ../backend/app/modules/dce/infrastructure/quarantine.py "Stockage privé, libmagic et ClamAV INSTREAM"
[4]: ../backend/app/modules/pricing/application/import_preview.py "Preview XLSX, calculs et limites pricing"
[5]: ../backend/alembic/versions/20260822_0049_financial_snapshot_immutability.py "Trigger DB d’immutabilité des snapshots publiés"
[6]: ../ops/docker-compose.preprod.yml "Allowlist d’environnement Compose préproduction"
[7]: ../ops/deploy-preprod.sh "Validation de configuration et alignement PostgreSQL"
[8]: ../web/package.json "Toolchain pnpm frontend"
[9]: ../.github/workflows/ci.yml "Workflow CI courant"
[10]: ../backend/tests/application/test_dce_document_extraction.py "Tests extraction DCE"
[11]: ../backend/tests/application/test_pricing_import.py "Tests pricing import"
[12]: ../backend/tests/application/test_financial_report_draft_lines.py "Tests PostgreSQL financier"
[13]: ../backend/tests/infrastructure/test_quarantine.py "Tests ClamAV et quarantaine"
[14]: ../backend/tests/ops/test_preprod_ops_contract.py "Contrats ops préproduction"
[15]: /home/ubuntu/upload/pasted_content.txt "Première pièce jointe d’audit consolidée précédemment"
[16]: /home/ubuntu/upload/pasted_content_2.txt "Deuxième pièce jointe d’audit consolidée précédemment"
[17]: /home/ubuntu/upload/pasted_content_3.txt "Troisième pièce jointe d’audit consolidée précédemment"
[18]: /home/ubuntu/upload/pasted_content_4.txt "Audit DCE joint dans cette itération"
[19]: /home/ubuntu/upload/pasted_content_5.txt "Audit DevOps/frontend joint dans cette itération"
[20]: /home/ubuntu/upload/pasted_content_6.txt "Audit backend/finance/outbox joint dans cette itération"
[21]: operator-reports/RAPPORT_AUDIT_SYSTEME_BTP.md "Rapport système BTP fourni le 22 août 2026, archivé comme preuve opérateur non reproduite localement"
[22]: operator-reports/RAPPORT_GATE_DOCKER_2026-08-22.md "Rapport de gate Docker fourni le 22 août 2026, non revalidable dans le sandbox sans Docker"
