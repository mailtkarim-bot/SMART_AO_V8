# Revue de pertinence de l’audit SMART_AO V8

**Date :** 22 août 2026  
**Périmètre :** HEAD de la branche `docs/pricing-http-next-lot-28` et fichiers présents dans le dépôt  
**Méthode :** confrontation des affirmations de l’audit avec le code, la configuration, les tests et les contrôles locaux ; aucune correction n’est retenue sans reproduction ou preuve directe.

## 1. Verdict exécutif

Les trois rapports sont **partiellement pertinents** et doivent être lus comme des photographies prises à des HEAD différents. Les deux premiers P0 sont déjà corrigés dans le dépôt : Alembic résout bien `SMART_AO_DATABASE_URL` et Trivy cible déjà `ops/docker/backend.Dockerfile`. Le troisième P0 est confirmé : le matcher Caddy `/healthz` ne couvrait pas `/healthz/live` ni `/healthz/ready`, qui pouvaient donc tomber sur le frontend.

Les risques confirmés ont été corrigés sans abandonner les autres rapports : rate limiting derrière Caddy, timing oracle login, webhook non authentifié, import XLSX matérialisant toutes les lignes, parsing JSON frontend non défensif, token frontend persisté en `localStorage`, URL API arbitrairement persistable, classement des dépendances de build et interférence de fixture PostgreSQL dans la suite globale. La limite Caddy de 150 MiB et la signature HMAC réduisent également les risques opérationnels d’upload et de notification.

Les critiques d’architecture restent pour l’essentiel des **dettes de structuration réelles mais non bloquantes pour le comportement corrigé**. Plusieurs affirmations chiffrées sont obsolètes : le fichier `platform/security/models.py` mesure 2 481 lignes et contient 47 déclarations `__tablename__`, et non 2 687 lignes/51 tables ; les markers pytest sont déclarés en mode strict et deux tests `schema/domain` sont collectés ; le frontend compte 17 fichiers de tests, `App.tsx` mesure 420 lignes, et plusieurs features sont déjà extraites.

> **Conclusion :** l’audit a correctement identifié une faiblesse Caddy et plusieurs durcissements utiles, mais son verdict « trois P0 confirmés » était excessif au moment de la revue. Après les correctifs ci-dessous, le code local est plus sûr ; la validation Docker/Caddy réelle et la CI GitHub restent nécessaires avant toute décision de déploiement.

## 2. Matrice des constats

| Constat de l’audit | Pertinence | Preuve vérifiée | Décision |
|---|---|---|---|
| Alembic ignore `SMART_AO_DATABASE_URL` | **Faux / déjà corrigé** | `backend/alembic/env.py` appelle `resolve_database_url()` pour offline et online. | Aucun changement supplémentaire. |
| Trivy scanne un Dockerfile racine inexistant | **Faux / déjà corrigé** | `.github/workflows/ci.yml` vérifie, construit et scanne `ops/docker/backend.Dockerfile`. | Aucun changement supplémentaire. |
| `/healthz/live` et `/healthz/ready` tombent sur le SPA | **Vrai** | `ops/Caddyfile` ne traitait que le chemin exact `/healthz`. | Corrigé par un matcher `/healthz /healthz/*` reverse-proxy vers `backend:8000`, avec test de contrat ops. |
| Rate limiter aveugle derrière Caddy | **Vrai** | `authentication.py` utilisait `request.client.host`, tandis que l’image Uvicorn n’activait pas les proxy headers ; le refresh pouvait partager l’IP du proxy. | Corrigé par `--proxy-headers`, CIDR interne fixe `172.30.0.0/24` et réseau Compose préproduction correspondant. |
| JWT `verify_exp/verify_iat` désactivés | **Partiellement vrai** | PyJWT est configuré avec ces vérifications désactivées, mais l’application compare ensuite `iat` et `exp` avec son horloge injectée, indispensable aux tests et au contrôle temporel déterministe. | Pas de suppression mécanique : conserver le contrôle applicatif et documenter ce choix ; une refonte devra fournir une horloge à la bibliothèque JWT avant modification. |
| Webhook d’export sans HMAC | **Vrai** | `_post_json()` envoyait le JSON sans signature lorsqu’une URL était configurée. | Corrigé : secret obligatoire pour livrer, HMAC-SHA256 dans `X-SMART-AO-Signature`, secret documenté hors Git, tests adaptés. |
| Timing oracle login | **Vrai** | Une identité inconnue quittait `AuthenticationService.login()` avant tout appel au vérificateur de mot de passe. | Corrigé par une vérification Argon2id factice constante et un test d’intégration dédié. |
| Import XLSX pricing matérialisant toutes les lignes | **Vrai** | `list(sheet.iter_rows(...))` chargeait la feuille avant la borne `MAX_ROWS` ; la somme du central directory ne suffisait pas comme preuve de taille réelle. | Corrigé par itération bornée et lecture cumulée des octets réellement décompressés. |
| Uploads quasi illimités | **Partiellement vrai** | Le service applicatif conserve une borne historique de 2 000 000 000 octets ; le backend de préproduction n’est toutefois pas publié et aucun plafond Caddy n’existait. | Réduction de la surface externe : Caddy limite désormais le corps à 150 MiB. La politique métier d’une limite applicative configurable reste à cadrer séparément. |
| Backups non chiffrés et jamais externalisés | **Non démontré comme bug de code ; risque opérationnel réel** | Les scripts et exemples exigent un répertoire de backup et documentent le transfert hors VPS, mais aucun VPS réel ni stockage externe n’est disponible dans cet environnement. | Maintenu comme gate VPS bloquant, sans prétendre l’avoir validé. |
| MFA « schema-only » | **Partiellement vrai** | Le modèle et la policy savent représenter la fraîcheur MFA, mais aucun appel applicatif `mfa_required=True` n’est actuellement branché sur une opération sensible. | Dette de périmètre à traiter dans un lot step-up dédié ; pas de correction spéculative ici. |
| `platform/security/models.py` trop monolithique | **Vrai comme dette d’architecture, chiffres obsolètes** | Le fichier compte 2 481 lignes et 47 tables déclarées. | À planifier en extraction progressive ; non bloquant pour les correctifs présents. |
| Suite globale non isolée par le benchmark de performance | **Vrai et reproduit** | Le benchmark créait puis détruisait lui-même le schéma avec `downgrade(base)`, provoquant des erreurs `UndefinedTable` ou des collisions selon l’ordre global. | Corrigé : le benchmark utilise désormais la fixture `database_engine` et ne gère plus le cycle Alembic. La suite globale passe. |
| Six modules sans `domain/` | **Vrai** | `enterprise`, `membership`, `patron_action`, `preparation` et `submission` n’ont pas encore de couche `domain/` dédiée ; `__pycache__` est ignoré. | Dette ARC-01 à traiter par bounded context, sans déplacement mécanique non testé. |
| Imports directs d’infrastructure inter-modules | **Partiellement vrai** | Des imports historiques existent encore ; les tests d’architecture couvrent déjà plusieurs frontières, mais pas une interdiction exhaustive de toute dépendance future. | Ajouter progressivement des tests AST et remplacer les dépendances au fil des slices. |
| `cockpit_projection` sans consommateur / `ProcessInboxRecord` mort | **Non confirmé dans cette revue** | L’affirmation n’a pas été établie par un scénario de régression reproductible pendant ce correctif. | Ne pas supprimer sans cartographie runtime et test de reconstruction. |
| Markers pytest fantômes | **Faux / obsolète** | `pyproject.toml` déclare `schema`, `domain`, `application`, `integration`, `db`, `api`, `architecture`, `concurrency`, `security`, `process`, `e2e`, avec `strict-markers`. | Aucun changement ; mesurer l’usage réel séparément si nécessaire. |
| Dossier `process/` vide | **Vrai mais non bloquant** | Seul `__init__.py` est présent. Les tests de workers/outbox existent cependant dans `backend/tests/application`. | Réorganiser les tests process dans un lot qualité dédié, sans déplacer à l’aveugle. |
| Seulement deux tests de concurrence | **Non confirmé comme chiffre actuel** | Le dépôt contient des tests de concurrence et d’idempotence répartis dans plusieurs suites ; le chiffre de l’audit ne correspond pas à une mesure reproduite ici. | Produire une cartographie de couverture process/concurrency avant toute conclusion. |
| `.coverage` racine à 68 % | **Non démontré** | Aucun contrôle de couverture comparable n’a été produit dans cette revue. | Ne pas utiliser cet artefact isolé comme indicateur de qualité. |
| Documentation de couverture obsolète | **Vraisemblable mais non bloquant** | Des compteurs historiques subsistent dans des documents antérieurs aux derniers slices. | Réconcilier les métriques dans une mise à jour documentaire dédiée. |
| Frontend JWT en `localStorage` et URL API persistable | **Vrai pour le HEAD audité, corrigé** | `App.tsx` lisait et écrivait `smart-ao-token` et `smart-ao-api-url`; `runtimeConfig` acceptait une destination distante persistée. | Token supprimé du stockage persistant ; URL non relue depuis le stockage et origine HTTPS imposée hors localhost. |
| App.tsx monolithique et zéro test frontend | **Faux / obsolète** | `App.tsx` compte 420 lignes, les comportements sont séparés sous `web/src/features/`, 17 fichiers de tests sont présents et Vitest passe. | Aucun refactoring mécanique supplémentaire. |
| Parsing JSON frontend sans garde | **Vrai comme défaut de robustesse** | Plusieurs appels `JSON.parse` directs pouvaient transformer une réponse HTML de proxy en exception non maîtrisée. | Corrigé par `parseResponseBody()` et test d’une réponse non JSON. |
| Dépendances Vite/TypeScript classées en runtime | **Vrai comme nettoyage packaging** | Les outils de build étaient sous `dependencies` malgré une image finale Nginx statique. | Déplacés vers `devDependencies` et lockfile régénéré sans changement de versions. |
| Documentation OpenAPI active dans le backend | **Vrai en accès interne, faible en exposition edge** | FastAPI activait les routes par défaut ; Caddy ne les routait pas, mais une exposition directe du backend les rendrait accessibles. | Corrigé pour le bootstrap production avec `openapi_url`, `docs_url` et `redoc_url` à `None`; le développement conserve les docs. |
| Headers sécurité incomplets côté edge | **Vrai partiellement** | Caddy avait déjà HSTS, nosniff, X-Frame-Options et Referrer-Policy mais pas de CSP. | CSP restrictive same-origin ajoutée au Caddyfile ; les headers applicatifs indépendants de l’edge restent un durcissement ultérieur. |

## 3. Correctifs appliqués

### Routage santé Caddy

`ops/Caddyfile` traite maintenant `/healthz` et tous ses sous-chemins dans un bloc dédié reverse-proxy vers le backend. Les endpoints backend `/healthz/live` et `/healthz/ready` ne peuvent plus être satisfaits par le HTML du SPA. Un test de contrat vérifie le matcher, l’upstream backend et l’absence de réponse statique `200` dans le bloc santé.

### IP réelle et rate limiting

L’image backend démarre Uvicorn avec `--proxy-headers` et `--forwarded-allow-ips=172.30.0.0/24`. Le réseau `internal` du Compose préproduction est fixé à ce CIDR, et seul Caddy rejoint ce réseau avec le backend. Le backend n’est pas publié dans le Compose préproduction ; la confiance n’est donc pas ouverte à Internet. Le test ops verrouille la correspondance entre la commande et le CIDR.

### Signature des notifications webhook

Lorsque `SMART_AO_EXPORT_WEBHOOK_URL` est configurée, le worker exige `SMART_AO_EXPORT_WEBHOOK_SECRET` avant toute livraison. Le corps JSON est signé en HMAC-SHA256 et transmis dans `X-SMART-AO-Signature: sha256=<hex>`. En l’absence de secret, le message est placé en retry avec un code de configuration fermé ; aucune notification non authentifiée n’est envoyée. Le secret reste hors Git et la commande webhook conserve son payload sans données financières.

### Égalisation du login

Pour une identité ou une membership inconnue, `AuthenticationService.login()` exécute désormais le même type de vérification Argon2id sur un hash factice constant, puis retourne le refus neutre `INVALID_CREDENTIALS`. Aucun token, session ou membership n’est créé. Le test dédié vérifie que le vérificateur est appelé une fois avec un hash Argon2id.

### Limite externe d’upload

Caddy rejette les corps supérieurs à 150 MiB avant l’upstream. Cette mesure réduit le risque d’épuisement de la quarantaine sur l’interface externe ; elle ne remplace pas le cadrage ultérieur d’une limite applicative par type de document et par tenant.

## 4. Validation réalisée

| Contrôle | Résultat |
|---|---|
| Tests ciblés correctifs | **40 passed** sur worker webhook, ops et authentification ; **39 passed** sur pricing import HTTP ; test frontend API ajouté. |
| Ruff global | **Passé** sur le dépôt après corrections. |
| Suite backend consolidée | **1 061 passed, 7 warnings**, après correction de l’isolation du benchmark. |
| Frontend consolidé | **65 passed dans 17 fichiers**, build TypeScript strict/Vite passé. |
| Migrations avant correctifs | `alembic upgrade head` et `alembic check` passés. |
| Docker/Caddy réels | Non exécutés dans le sandbox ; à valider sur l’ordinateur Docker de l’utilisateur ou un VPS. |

Les changements exigent une nouvelle suite backend complète et les contrôles CI avant fusion. La dernière CI GitHub connue reste inutilisable comme preuve fonctionnelle lorsque les jobs terminent avec `runnerName: null` avant exécution.

## 5. Findings conservés comme travaux ultérieurs

Les sujets suivants restent légitimes mais ne sont pas corrigés par ce patch : extraction progressive des modèles ORM hors de `platform/security/models.py`, généralisation des tests d’architecture d’imports, structuration des tests `process`, activation d’un véritable step-up MFA sur opérations sensibles, limite applicative configurable d’upload, filtrage SSRF DNS/IP du webhook, dead-letter après un nombre maximal de retries, HMAC du hash d’IP d’audit, enforcement DB de l’append-only, chiffrement et externalisation vérifiés des backups, authentification frontend de production et validation opérationnelle Docker/Caddy/ClamAV/HTTPS.

Aucun de ces sujets ne doit être déclaré résolu par une simple présence de fichiers. Ils devront suivre la Definition of Done du projet : contrat, test rouge, implémentation, persistance si nécessaire, sécurité tenant, idempotence/concurrence, API, interface, test E2E, documentation et CI réellement exécutée.

## Références

[1]: ../backend/alembic/env.py "Résolution de l’URL Alembic"
[2]: ../.github/workflows/ci.yml "Workflow CI et scan Trivy"
[3]: ../ops/Caddyfile "Configuration Caddy"
[4]: ../ops/docker/backend.Dockerfile "Commande Uvicorn du backend"
[5]: ../ops/docker-compose.preprod.yml "Compose préproduction et réseau interne"
[6]: ../backend/app/platform/security/authentication.py "Authentification et hash factice"
[7]: ../backend/app/workers/submission_export_webhook.py "Worker webhook et signature HMAC"
[8]: ../backend/tests/ops/test_preprod_ops_contract.py "Contrats de configuration ops"
[9]: ../backend/tests/security/test_authentication_services.py "Tests d’authentification"
[10]: ../backend/tests/application/test_submission_export_webhook.py "Tests du worker webhook"
[11]: ../pyproject.toml "Markers pytest et seuils de qualité"
[12]: ../web/src/app/App.tsx "Orchestrateur frontend actuel"
[13]: ../web/src/infrastructure/runtimeConfig.ts "Validation de l’origine API frontend"
[14]: ../web/src/infrastructure/api.ts "Parsing défensif des réponses API"
[15]: ../backend/app/modules/pricing/application/import_preview.py "Import XLSX borné et streaming"
[16]: ../backend/tests/db/test_assignment_change_journal_performance.py "Isolation du benchmark PostgreSQL"
[17]: https://fastapi.tiangolo.com/tutorial/metadata/ "FastAPI official documentation: OpenAPI and docs URLs"
