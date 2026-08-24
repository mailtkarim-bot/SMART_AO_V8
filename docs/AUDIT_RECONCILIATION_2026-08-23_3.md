# Réconciliation du troisième audit — SMART_AO V8

**Date de vérification :** 23 août 2026
**Périmètre :** `pasted_content_3.txt` et `RAPPORT_AUDIT_SYSTEME_BTP.md`, confrontés à la branche `docs/pricing-http-next-lot-28`.
**Posture :** corriger les écarts avérés sans affaiblir l’architecture hexagonale, l’isolation tenant, l’append-only, l’idempotence, la révision optimiste ni la confidentialité financière.

## Verdict exécutif

Les deux rapports sont globalement utiles et confirment trois réalités distinctes. Le socle backend est effectivement durci et multi-tenant ; plusieurs faiblesses de structure et d’exploitation étaient toutefois réelles. Enfin, la valeur métier BTP reste incomplète : les rapports ont raison de distinguer un coffre-fort technique d’un moteur complet d’analyse d’appel d’offres.

Les corrections de ce lot traitent les écarts codables et confirmés. Elles ne transforment pas artificiellement une preuve de configuration en preuve d’exécution : PostgreSQL online, Docker, ClamAV/EICAR, HTTPS, restauration, bus externe, corpus BGE/DCE et runners GitHub restent des gates d’environnement.

## Remédiations livrées

| Constat vérifié | Remédiation | Validation |
|---|---|---|
| `ApplicationCommand` importé depuis DCE par membership et helper d’authentification importé depuis une route privée | Shared kernel de commandes déjà extrait ; helper Bearer centralisé dans `interfaces/http/dependencies/auth.py` ; routes migrées vers ce module, avec alias locaux uniquement pour préserver les tests/callers historiques. | Ruff et tests API non-DB passés. |
| Dépendance inversée `platform/storage` vers préparation | Port de stockage déplacé dans `platform/storage/ports.py`; adaptateurs local et objet branchés sur le port platform. | Tests d’architecture et Ruff passés. |
| Transition patronale acceptant des paires arbitraires et projection courante non synchronisée | Graphe pur `patron_action/domain/state.py`; contrôle effectué avant écriture ; `PatronActionRecord.state` et `aggregate_revision` synchronisés dans la même transaction que la transition append-only. Le graphe respecte le CHECK SQL existant et ne promet pas de réouverture vers `OPEN`. | Tests de domaine, architecture et intégration ciblée passés ; les tests DB restent dépendants de PostgreSQL. |
| Risque de course d’idempotence signalé sur le dispatcher | Protection par savepoint et relecture de receipt après collision, sans supprimer la détection de hash canonique ni l’isolation tenant. | Couverture par les tests existants ; concurrence PostgreSQL réelle à exécuter sur DB disponible. |
| Image backend installée par plages alors que `uv.lock` existe | Dockerfile backend copié avec `uv.lock` et utilise `uv sync --frozen --no-dev --no-editable`; les extras sont également installés par lock. | Contrat d’architecture Docker et validation statique passés ; build Docker réel non disponible dans le sandbox. |
| Actions CI taguées et Trivy limité au backend | Actions référencées par SHA immuable ; image frontend buildée et scannée par Trivy comme l’image backend. | Workflow vérifié statiquement ; aucun runner GitHub attribué pour l’exécuter. |
| Frontend final Nginx root et sans healthcheck | Nginx passe sur port interne 8080, utilisateur `nginx`, PID/cache accessibles et healthcheck `/healthz`; Caddy et Compose sont alignés. | Contrats ops passés ; build d’image Docker à exécuter dans un environnement Docker. |
| Compose dev réutilisable avec exposition réseau trop large | Bind PostgreSQL/backend sur loopback, `SMART_AO_ENV: development` immuable et `no-new-privileges` sur les services locaux. | Contrat ops passé. |
| Clé JWT dev connue et rotation non câblée dans preprod | La clé dev connue est refusée par le bootstrap production ; `SMART_AO_JWT_KEY_ID` et `SMART_AO_JWT_VERIFICATION_KEYS_JSON` sont câblés depuis l’environnement, sans secret dans Git. | Tests bootstrap passés ; les vraies clés restent à fournir par le gestionnaire de secrets. |
| Absence de fallback de rendu, RBAC UI faible et outillage frontend incomplet | `ErrorBoundary` récupérable ajouté ; navigation, chargements et surfaces patronales conditionnés au rôle serveur ; union TypeScript stricte pour l’acteur ; ESLint, typecheck et peer dependency DOM ajoutés. | 98 tests Vitest, build, lint et typecheck passés. |
| Documentation frontend contradictoire | README corrigé : token en mémoire, cookie HttpOnly/CSRF et URL API explicite ; commandes de validation complètes documentées. | Relecture et tests frontend passés. |

## Remarques confirmées mais non corrigées dans ce lot

Le topic outbox par défaut `cockpit_projection` n’a toujours pas de projection métier définie ni de politique de rétention validée. Il serait dangereux de le supprimer, de le marquer publié ou de l’envoyer vers un bus externe sans contrat explicite, car les payloads pourraient contenir des informations sensibles. Un prochain slice doit définir le projection builder, son schéma minimal et la rétention des `outbox_messages` et `domain_events` avant d’ajouter un worker.

Le step-up MFA est représenté par `mfa_verified_at` et la policy, mais la cérémonie TOTP/enrôlement/vérification n’est pas encore implémentée et aucune opération sensible n’est activée en `mfa_required=True`. L’activation arbitraire aurait créé un blocage utilisateur ; ce point reste donc ouvert avec un design et une migration à réaliser.

Les N+1 signalés dans l’évaluation de préparation, la soumission et certains lecteurs restent un chantier de performance à mesurer avec PostgreSQL. Il n’est pas corrigé par une réécriture spéculative sans plan de requêtes et benchmark.

L’import XLSX pricing conserve une validation de format, macro et anti-zip-bomb, mais n’est pas encore raccordé au port ClamAV/libmagic des uploads DCE. Cette amélioration doit être conçue avec un stockage temporaire privé et un comportement fail-closed ; elle n’est pas déclarée corrigée ici.

Les erreurs applicatives ne sont pas encore toutes portées par une hiérarchie d’exceptions machine-readable avec handler global. Les routes existantes conservent leurs mappings neutres ; une migration globale précipitée risquerait de modifier les statuts API historiques.

## Remarques métier correctement maintenues ouvertes

Les rapports ont raison sur l’état métier : l’analyse CCAP clause par clause, les risques de pénalités/retenue/avance/cautionnement, le coût de revient par ligne, le prix plancher, le croisement CCTP–DPGF–CCAP, les DC1/DC2/DC4, le groupement, la sous-traitance et l’OCR opérationnel ne sont pas encore un produit complet. Le domaine et les rails de provenance/confirmation existent, mais ces fonctionnalités doivent être développées comme des slices métier séparés avec données de référence et validations humaines.

La décision GO/NO-GO possède un domaine et une lecture, mais la boucle d’écriture et l’alimentation automatique depuis les signaux DCE/pricing restent à compléter. De même, la veille BOAMP dispose d’un adaptateur et d’un scoring borné, mais une ingestion planifiée et une conversion vers Case exigent un environnement et un contrat opérationnels.

## Constats faux, obsolètes ou à nuancer

| Remarque du rapport | Qualification actuelle |
|---|---|
| `icalendar` absent | Faux : l’extra `calendar` déclare `icalendar`; le renderer ICS local et son test passent. |
| Tous les runners/CI prouvent un échec de code | Non démontré : les runs terminent sans runner attribué et avec étapes vides. Le workflow est contrôlé statiquement mais non exécuté. |
| RBAC serveur absent | Faux : catalogue de capabilities, policy ABAC, contrôles de service et FK tenant existent. Le finding concernait surtout l’interface, désormais conditionnée par rôle. |
| Token conservé en localStorage | Obsolète/faux : le token d’accès est conservé en mémoire ; le README a été aligné. |
| Proxy frontend Vite garanti en production | À nuancer : l’URL API est configurée explicitement ; la production doit rester same-origin/HTTPS ou fournir une API HTTPS autorisée. |
| `ApplicationCommand` encore détenu par DCE | Obsolète : les contrats concernés utilisent le shared kernel platform. |
| Frontend non-root et sans scan | Corrigé dans le code/configuration ; l’exécution Docker et le scan de l’image restent à prouver par runner. |

## Validation locale disponible

La validation complète réalisée sur le lot est la suivante :

- backend non-DB : **885 tests passés, 458 tests DB désélectionnés**, avec PostgreSQL non accessible dans le sandbox ;
- Ruff backend/scripts : passé ;
- mypy borné du noyau sécurité : passé ;
- detect-secrets strict avec baseline : passé ; la baseline a été régénérée uniquement pour maintenir les positions des faux positifs explicitement allowlistés ;
- tests ciblés auth/architecture/ops/domain : passés ;
- frontend : **98 tests passés**, build Vite passé, ESLint passé avec deux avertissements React `exhaustive-deps` existants, typecheck passé ;
- Alembic offline jusqu’à `20260823_0055` : passé, sans preuve d’exécution online ;
- `git diff --check` : passé après la mise à jour documentaire ;
- Docker, PostgreSQL online, VPS et CI GitHub : non disponibles dans l’environnement de vérification.

## Verdict

Les rapports sont suffisamment pertinents pour maintenir un **NO-GO opérationnel** et pour prioriser le prochain développement métier. Les corrections sûres du socle sont appliquées sans désactiver le seuil de couverture ni contourner les protections financières. Il serait inexact d’affirmer que l’application est déjà un produit BTP complet ou que la production est validée : le prochain travail prioritaire est désormais, dans cet ordre, le raccordement sécurisé de l’antivirus pricing, le contrat outbox/projection/rétention, le parcours MFA, puis les slices métier CCAP-RISK et COST-BASIS.


## Preuve CI après publication

Le push des commits `5f2aabf` et `234e367` a déclenché le run GitHub Actions `32673495930` sur le SHA `234e367`. Le run est terminé en échec en environ cinq secondes. Les trois jobs (`backend`, `frontend`, `image-security`) ont `steps: []`; aucune étape Ruff, mypy, detect-secrets, pytest, build ou Trivy n’a donc été exécutée. Ce résultat confirme le blocage de provisioning/runner déjà documenté et ne démontre pas un défaut fonctionnel du code.
