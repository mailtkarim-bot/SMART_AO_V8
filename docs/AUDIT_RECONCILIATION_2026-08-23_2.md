# Réconciliation du nouvel audit — 23 août 2026

## Objet et périmètre

Ce document confronte le rapport fourni dans `pasted_content_2.txt` à l’état réel de la branche `docs/pricing-http-next-lot-28`. Il distingue les faits démontrés, les faux positifs, les corrections applicables dans le dépôt et les preuves qui nécessitent encore PostgreSQL, Docker, un VPS, un fournisseur externe ou des runners GitHub Actions réellement attribués.

La remédiation reste volontairement conservatrice. Elle ne modifie ni la résolution serveur du tenant et de l’acteur, ni les transactions append-only, ni l’idempotence, ni la révision optimiste, ni la classification `FINANCIAL_PRIVATE`, ni les contrats publics sans test correspondant.

## Verdict remarque par remarque

| Remarque du rapport | Vérification | Action et état |
|---|---|---|
| Couverture hors DB à 67,41 %, seuil 85,50 % | **Avérée.** La nouvelle mesure locale atteint 67,62 % avec 867 tests passés et 458 tests DB désélectionnés. | Aucun contournement. Le seuil reste 85,50 %. Le déficit doit être réduit par des tests utiles, notamment bootstrap, authentification, workers et branches PostgreSQL lorsque l’environnement sera disponible. |
| Tests DB non exécutables | **Avérée dans le sandbox.** PostgreSQL n’est pas accessible sur `127.0.0.1:5432`; les tests DB ne fournissent donc pas de preuve locale de triggers, isolation ou concurrence. | Non simulé et non revendiqué. Alembic offline jusqu’à `20260823_0055` passe, mais cela ne remplace pas une exécution online. |
| `detect-secrets` échoue sur neuf fixtures | **Avérée.** Le scan CI détectait neuf valeurs synthétiques dans des tests. Aucun secret de production n’a été découvert. | Corrigée. Les fixtures sont explicitement marquées `# pragma: allowlist secret` sur les littéraux concernés; le scan canonique passe désormais sans exclusion globale supplémentaire. |
| MFA step-up non branché | **Partiellement avérée.** `AuthorizationPolicy` sait émettre `STEP_UP_REQUIRED` et ses tests passent, mais aucun appel applicatif ne demande actuellement `mfa_required=True`. Le service d’authentification ne possède pas encore de cérémonie TOTP/enrôlement/vérification ni de mise à niveau de session. | Non activé artificiellement. Rendre MFA obligatoire sans parcours utilisateur fonctionnel bloquerait les opérations sensibles. Le flux TOTP et le branchement contrôlé aux actions sensibles restent un lot de sécurité distinct. |
| Rate limiter process-local et adresse source incorrecte derrière Caddy | **Avérée avec deux dimensions.** Le limiter reste process-local en multi-réplique; l’ancienne résolution utilisait uniquement `request.client.host`. | Corrigée pour la frontière proxy : `X-Forwarded-For` n’est accepté que si le pair direct appartient à `SMART_AO_TRUSTED_PROXY_CIDRS`; le défaut refuse tout proxy implicite. Compose préproduction injecte le réseau interne Caddy `172.30.0.0/24`. Le stockage partagé multi-réplique reste une décision d’exploitation ouverte. |
| CI sans runner | **Avérée.** Les runs récents échouent avant exécution exploitable; `runnerName` est absent et les étapes ne démarrent pas. | Aucune modification destinée à masquer le gate. La branche et la PR #49 ne sont pas fusionnées. |
| Extra `calendar` manquant et tests ICS cassés | **Faux positif.** `icalendar 7.3.0` est disponible avec l’extra `calendar`, et le renderer ICS local n’en dépend pas pour produire son résultat. | Aucune correction de dépendance nécessaire. |
| Aucun vérificateur de types | **Avérée avant ce lot.** Le projet ne déclarait ni mypy ni pyright. | Correction prudente : `mypy>=1.15,<2.0` est ajouté au groupe dev, verrouillé dans `uv.lock`, et le workflow CI contrôle le noyau de sécurité (`authorization`, `context`, `rate_limit`, `tokens`). Le périmètre est volontairement borné; cela ne constitue pas encore une certification mypy de toute l’application. |
| Modèles d’assignation et de collaboration encore dans `platform/security/models.py` | **Partiellement avérée.** Les modèles ORM métier précédemment ciblés ont été extraits, mais `CaseAssignment*` et `CollaboratorTask*` restent encore dans la plateforme sécurité, car ils sont utilisés par le résolveur ReBAC et plusieurs flux de collaboration. | Non déplacé à l’aveugle. Une extraction supplémentaire nécessite un bounded context propriétaire, une stratégie d’import, la registry Alembic et une régression complète. Le point reste ouvert et documenté plutôt que corrigé de façon risquée. |
| Aucune route MFA TOTP | **Avérée.** Les tables et contraintes existent, mais aucune route d’enrôlement, de vérification ou de récupération n’est publiée. | Reste ouvert. Ajouter seulement `mfa_required=True` sans cérémonie TOTP active serait une régression fonctionnelle et de disponibilité. |
| Gate VPS non exécuté | **Avérée et externe.** Docker, ClamAV/EICAR, HTTPS, backup/restauration et supervision externe ne sont pas prouvés dans ce sandbox. | Aucun résultat fabriqué. Les contrats Compose, scripts et healthchecks restent des antennes opératoires à exécuter sur l’ordinateur ou le VPS réel. |
| Gaps métier : OCR, analyse financière des ventes, clauses CCAP/CCTP | **Pertinents comme produit, mais non assimilables à un bug de ce lot.** Le DCE actuel fournit des projections déterministes et bornées; il ne prétend pas produire une conformité automatique, une analyse OCR ou une décision financière complète. | À traiter comme lots métier explicites avec corpus, règles et validation humaine. Aucun faux support n’est ajouté. |

## Corrections de code livrées dans ce lot

Le rate limiter HTTP utilise maintenant une liste de réseaux proxy explicitement approuvés. Par défaut, aucun en-tête de transfert n’est fiable. La configuration préproduction conserve la frontière interne Caddy et les tests couvrent le pair non approuvé, le proxy approuvé, l’adresse transférée invalide, les CIDR multiples et le CIDR malformé. Cette correction ne prétend pas résoudre le partage d’état entre plusieurs réplicas; un backend partagé devra être choisi et opéré avant une montée en charge horizontale.

Le workflow CI dispose maintenant d’un contrôle mypy borné sur le noyau de sécurité. La configuration est reproductible via `pyproject.toml` et `uv.lock`, et la commande passe localement. Le scan detect-secrets canonique passe après annotation de neuf fixtures synthétiques. Les annotations sont locales aux valeurs de tests et ne désactivent pas le scan des autres fichiers.

## Validation locale

| Contrôle | Résultat |
|---|---|
| Tests backend non-DB | **867 passed**, 458 deselected; l’exécution est marquée en échec uniquement parce que la couverture totale est 67,62 %, sous 85,50 %. |
| Couverture hors DB | **67,62 %**, seuil strict 85,50 % non atteint. |
| Ruff `backend scripts` | **Passé**. |
| Mypy noyau sécurité | **Passé**, 4 fichiers contrôlés. |
| Detect-secrets avec baseline CI | **Passé**. |
| Tests sécurité/rate limiter et fixtures concernées | **67 passed** sur la suite ciblée. |
| Frontend | **93 tests passés**, 22 fichiers; build Vite passé. |
| Alembic offline | **Passé** jusqu’à `20260823_0055`; le SQL inclut le trigger `pricing_scenarios_append_only`. |
| PostgreSQL online | **Non exécuté** : connexion locale refusée. |
| Docker/VPS/ClamAV/HTTPS réel | **Non exécuté** dans l’environnement disponible. |
| GitHub Actions | **Non concluant** : runs sans runner ni étapes exécutées. |

## État Git et règle de fusion

La branche de travail reste `docs/pricing-http-next-lot-28`, avec `main` à l’ancien commit et la PR #49 ouverte. Aucune fusion ne doit être réalisée tant qu’un runner GitHub Actions n’a pas exécuté les jobs backend, frontend et image-security, puis tant que le seuil de couverture et les tests PostgreSQL n’ont pas été évalués sur une exécution réelle.

## Prochains lots sûrs

Le prochain lot de sécurité doit concevoir la cérémonie TOTP complète avant de rendre obligatoires les step-up MFA sur publication financière, export/signature et autres opérations à impact. Il devra traiter l’enrôlement pending, la vérification atomique, le secret chiffré, les recovery codes hashés et consommables une seule fois, l’élévation de session bornée et les tests de rejeu.

En parallèle, la couverture doit progresser par tests fonctionnels et non par exclusions. L’extraction supplémentaire des modèles d’assignation doit être préparée par une décision de bounded context et une cartographie d’imports. Enfin, la recette PostgreSQL, Docker, ClamAV/EICAR, HTTPS, sauvegarde/restauration, corpus DCE/BGE et bus externe doit être exécutée dans les environnements correspondants avec conservation des preuves.

> **Conclusion :** le nouvel audit est globalement pertinent, mais il mélange des blocages réels, des points partiellement vrais et deux faux positifs (`calendar` et le diagnostic précédent ICS). Les corrections sûres du lot sont appliquées et testées. Le produit reste honnêtement **NO-GO opérationnel** tant que la couverture, MFA/TOTP, PostgreSQL online, les runners CI et le gate d’infrastructure réel ne sont pas validés.

## Références internes

- `pasted_content_2.txt` — rapport audité.
- `pyproject.toml` — seuil de couverture et configuration mypy.
- `.github/workflows/ci.yml` — commandes CI et contrôle de typage.
- `backend/app/interfaces/http/routes/authentication.py` — résolution de l’adresse source et configuration proxy.
- `backend/app/platform/security/authorization.py` — policy MFA existante.
- `backend/app/platform/security/authentication.py` — état actuel du flux d’authentification.
- `ops/docker-compose.preprod.yml` — réseau interne et variables runtime préproduction.
- `backend/tests/security/test_rate_limit.py` — non-régression proxy/rate limiter.
- `docs/PROJECT_STATE.md` et `docs/GLOBAL_REVIEW_2026-08-23_REFRESH.md` — état canonique du projet.


## Vérification post-push

Après publication des commits `cc61de4` et `5177ea2`, le run GitHub Actions `32668698934` a été créé pour le SHA `5177ea2` et s’est terminé en échec avant une exécution exploitable, comme les runs précédents. La PR #49 est toujours `OPEN` avec un état `UNSTABLE`; `main` reste au SHA `970c9ff`. Cette observation confirme l’interdiction de fusion, mais ne fournit toujours aucun diagnostic fonctionnel supplémentaire sur le code.
