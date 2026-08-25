# Réconciliation du quatrième audit — SMART_AO V8

**Date de vérification :** 24 août 2026
**Branche examinée :** `docs/pricing-http-next-lot-28` à `4114438` avant ce lot
**Source :** [`docs/operator-reports/RAPPORT_AUDIT_04_VERIFICATION.md`](operator-reports/RAPPORT_AUDIT_04_VERIFICATION.md)
**Méthode :** confrontation des constats au code, aux migrations, aux tests et aux Compose. Les preuves Docker/PostgreSQL « live » du rapport sont conservées comme éléments fournis par l’audit, mais n’ont pas été reproduites dans le sandbox courant, qui ne possède ni Docker ni PostgreSQL accessible.

## Verdict exécutif

Le quatrième audit est **largement pertinent**. Il révèle une régression réelle dans la synchronisation de projection `patron_action`, plusieurs défauts de tests PostgreSQL qui avaient été masqués par l’exclusion des marqueurs `db`, une readiness trop faible, l’absence de migration automatique dans Compose, un extra Docker non raccordé et une couverture de vulnérabilités Python qui excluait les extras optionnelles. Ces écarts ont été corrigés dans ce lot lorsque la correction était sûre et compatible avec l’architecture.

Les affirmations concernant l’état live d’un stack Docker précis — base vide, login HTTP 500, worker arrêté et couverture PostgreSQL à 89,10 % — ne sont pas une preuve nouvellement produite par ce sandbox. Elles restent documentées comme **preuves fournies par le rapport** et doivent être rejouées sur la machine qui héberge ce stack avant toute conclusion de production.

| Domaine | Verdict | Action dans ce lot |
|---|---|---|
| Régression `patron_action` | **Confirmée par le code et la migration** | Migration additive `20260824_0056` : seuls `state`, `aggregate_revision` et `updated_at` peuvent changer ; les colonnes historiques et les suppressions restent bloquées. Test DB renforcé. |
| Readiness | **Confirmée** | `/healthz/ready` vérifie maintenant la connexion DB et la tête Alembic `20260824_0056`, en plus de ClamAV. |
| Migrations Compose | **Confirmée** | Service one-shot `migrate` ajouté aux Compose local et préproduction ; backend et workers attendent `service_completed_successfully`. Worker de rétention local redémarrable. |
| Seeds/assertions DB | **Confirmée** | Flush explicite des tenants, chemin JSON outbox corrigé, regex d’idempotence corrigée. |
| Extras / supply chain | **Confirmée** | `object-storage` raccordé au Dockerfile et au Compose ; `uv export --all-extras` pour pip-audit ; image CI construite avec toutes les extras optionnelles. |
| Exposition locale | **Confirmée** | `compose.local-dev.yml` écoute désormais sur `127.0.0.1:5433`. |
| Couplage storage | **Confirmée partiellement** | Les consommateurs application preparation/submission utilisent désormais le port `platform.storage`. Les autres couplages métier restent un lot séparé. |
| ErrorBoundary | **Partiellement confirmée** | Re-montage du sous-arbre lors de « Réessayer » ajouté ; le comportement est testé de façon stable avec le scénario existant React 19. |
| Timer proactif, routeur, MFA, outbox cockpit et métier BTP | **Ouverts** | Non ajoutés artificiellement dans ce lot. Ils exigent des contrats produit ou une décision d’architecture. |

## 1. Régression `patron_action`

Le finding est avéré. Le service de transition mettait à jour `patron_actions.state` et `patron_actions.aggregate_revision`, alors que la migration `20260818_0038` installait un trigger qui refusait tout `UPDATE` sur cette table. La synchronisation de projection était donc incompatible avec le schéma réellement déployé.

La correction choisie est l’option additive recommandée par l’audit. La migration `20260824_0056` remplace le trigger aveugle par un garde colonne-scopée : `id`, tenant, identité de l’action, contenu métier, références, acteur, commande et idempotence restent immuables ; seules les colonnes de projection `state`, `aggregate_revision` et `updated_at` sont mutables. `DELETE` reste interdit. Ainsi, l’historique des transitions demeure append-only, tandis que la projection courante peut être synchronisée transactionnellement.

Le test `backend/tests/application/test_patron_action_transitions.py` vérifie désormais la mutation contrôlée de la projection et le refus d’une modification de titre. Le test PostgreSQL n’a pas été exécuté dans le sandbox actuel, car aucun serveur PostgreSQL n’est accessible ; la chaîne Alembic offline jusqu’à `20260824_0056` a été générée avec succès.

## 2. Readiness et démarrage Compose

Le contrôle précédent `SELECT 1` démontrait uniquement que PostgreSQL acceptait une connexion. Il pouvait donc déclarer l’application prête avec une base vide. Le endpoint `/healthz/ready` vérifie maintenant `alembic_version` et exige la tête `20260824_0056`. Une table absente, une version différente ou une base sans migration rendent le contrôle `schema` non prêt. Le script `ops/healthcheck-preprod.sh` exige lui aussi `database: ok`, `schema: ok` et `clamav: ok`.

Les Compose contiennent maintenant un service `migrate` exécutant `alembic upgrade head`. Le backend et les workers attendent sa réussite avec `condition: service_completed_successfully`. Le Compose de développement ajoute en outre `restart: unless-stopped` au worker de rétention. Cette configuration ne remplace pas une recette opérationnelle : elle doit encore être exécutée sur l’ordinateur ou l’environnement cible avec les secrets runtime appropriés.

## 3. Tests PostgreSQL corrigés

Les seeds BOAMP et event-bus ajoutent désormais un `session.flush()` après l’insertion du tenant, avant les lignes qui portent des FK vers ce tenant. L’assertion de veille interroge `payload_json.data.profile_id`, qui correspond au contrat du dispatcher, au lieu d’un chemin JSON inexistant. Le test de collision d’idempotence OR-Tools utilise le message contractuel `reused with a different request`.

Ces changements corrigent des défauts de tests, pas des défauts de production. Ils rendent toutefois la suite DB réellement exploitable lorsqu’un PostgreSQL est disponible et doivent être rejoués sur la base réelle, avec isolation de base ou verrouillage si plusieurs processus de test sont lancés en parallèle.

## 4. Packaging, extras et CI

L’image backend accepte désormais `SMART_AO_INSTALL_OBJECT_STORAGE` et installe l’extra `object-storage` lorsque le flag vaut `1`. Le service backend préproduction transmet ce flag. La CI exporte toutes les extras via `uv export --all-extras` avant `pip-audit`, et l’image backend de sécurité est construite avec les six flags optionnels activés afin que Trivy voie réellement les dépendances lourdes. Cette modification augmente le coût et la durée du job ; elle est préférable à un scan qui ignore silencieusement les variantes vendues.

La correction ne constitue pas une preuve de scan réussi : les runs GitHub Actions de cette branche restent bloqués par le provisioning des runners. Aucun résultat Trivy ou pip-audit distant ne doit être inventé.

## 5. Port de stockage et ErrorBoundary

Les services applicatifs preparation et submission importent désormais `GeneratedDocumentStorage` depuis `app.platform.storage.ports`. Les adaptateurs local et objet restent dans leurs couches d’infrastructure. Cela supprime le couplage application d’un module vers l’infrastructure d’un autre, sans déplacer les modèles ORM ni compromettre l’hexagone.

`ErrorBoundary` conserve son fallback mais incrémente une clé de re-montage lors de « Réessayer ». Un enfant dont l’erreur était transitoire peut donc être remonté proprement au lieu de recevoir seulement un changement d’état du boundary. Le test frontend existant reste stable sous React 19.

## 6. Validation réellement exécutée

| Contrôle | Résultat |
|---|---|
| Suite backend non-DB | **885 passed, 458 deselected, 4 warnings** en 12,98 s |
| Tests ciblés readiness/ops | **28 passed, 1 warning** |
| Ruff ciblé | Passé après réordonnancement des imports |
| Frontend ciblé ErrorBoundary | **1 passed** |
| Frontend | **98 passed**, typecheck et build passés ; ESLint 0 erreur et 2 avertissements `exhaustive-deps` |
| Alembic offline | Chaîne générée jusqu’à `20260824_0056` ; le SQL contient le nouveau trigger projection-scoped |
| Shell | `bash -n` passé pour `ops/healthcheck-preprod.sh` et `ops/deploy-preprod.sh` |
| detect-secrets | Scan strict passé ; baseline recalée mécaniquement pour les positions de lignes |
| Lockfile | `uv lock --check` passé |
| Docker | Non disponible dans le sandbox courant |
| PostgreSQL online | Aucun serveur accessible sur 5432 ou 5433 |
| CI GitHub | Non considérée verte ; les runs précédents ont échoué avec des étapes vides |

La suite frontend complète a été rejouée après stabilisation du test ErrorBoundary : **23 fichiers et 98 tests passés**, typecheck et build passés. ESLint ne produit aucune erreur et conserve deux avertissements `react-hooks/exhaustive-deps` dans `App.tsx`.

## 7. Éléments volontairement non corrigés

Le quatrième audit confirme des sujets qui ne doivent pas être traités par des rustines : le contrat de projection/rétention du topic `cockpit_projection`, la cérémonie TOTP/MFA complète, le raccordement ClamAV/libmagic de l’import pricing, les tests N+1 et de concurrence PostgreSQL, le routeur frontend, les deep-links, la pagination, le renouvellement proactif du JWT, la séparation complète des bounded contexts, les règles CCAP/pénalités, le coût de revient et le prix plancher, les documents DC1/DC2/DC4, l’analyse OCR et le RAG/BGE sur corpus réel.

Le rapport source annonce une couverture online de 89,10 %. Cette mesure est plausible et utile, mais elle n’est pas produite par le sandbox actuel ; elle ne remplace pas l’exécution reproductible du pipeline sur une base PostgreSQL isolée. De même, le stack Docker live mentionné dans le rapport doit être vérifié sur la machine qui le porte.

> **Verdict opérationnel :** le lot corrige une régression critique et plusieurs défauts de preuve et d’exploitation. Le projet reste **NO-GO production** jusqu’à l’exécution PostgreSQL online, Docker, CI avec runners actifs, validation des secrets/HTTPS, recette ClamAV et vérification du produit métier complet.

## Références internes

- [`RAPPORT_AUDIT_04_VERIFICATION.md`](operator-reports/RAPPORT_AUDIT_04_VERIFICATION.md) — rapport source fourni.
- [`20260824_0056_patron_action_projection_sync.py`](../backend/alembic/versions/20260824_0056_patron_action_projection_sync.py) — garde append-only colonne-scopée.
- [`application.py`](../backend/app/bootstrap/application.py) — readiness database/schema/ClamAV.
- [`docker-compose.yml`](../docker-compose.yml) et [`docker-compose.preprod.yml`](../ops/docker-compose.preprod.yml) — service migrate et dépendances.


## Preuve CI après publication

Le push vers `7be6263` a déclenché le run GitHub Actions `32680863228`. Il s’est terminé en échec après quelques secondes ; les jobs `backend`, `frontend` et `image-security` ont tous `steps: []`. Aucune étape de test, build, pip-audit ou Trivy n’a été exécutée. Ce run confirme le blocage de provisioning des runners et ne constitue pas un verdict fonctionnel du code.
