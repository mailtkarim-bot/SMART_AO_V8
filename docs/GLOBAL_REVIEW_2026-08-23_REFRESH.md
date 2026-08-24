# SMART_AO V8 — Revue globale actualisée

**Date : 23 août 2026**  
**Branche : `docs/pricing-http-next-lot-28`**  
**Dernier commit poussé : [`7d91b0a`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/7d91b0a)**
**Auteur : Manus AI**

## 1. Verdict exécutif

Le projet possède désormais un noyau métier substantiel et structuré autour de frontières hexagonales : domaine/application indépendants de FastAPI et SQLAlchemy, résolution serveur du tenant et de l’acteur, contrôles d’autorisation, idempotence, révision optimiste, événements/outbox et append-only PostgreSQL. Les surfaces BOAMP sont disponibles jusqu’au cockpit patronal frontend. La lecture DCE et la recherche knowledge/RAG sont maintenant exposées depuis le cockpit sur les affaires sélectionnées, avec des projections minimales et une recherche bornée côté serveur.

Le produit n’est toutefois pas encore **opérationnel de bout en bout**. Les dépendances externes sont à plusieurs niveaux de maturité et ne doivent pas être confondues avec des intégrations activées. PostgreSQL réel, un fournisseur bus réel, une URL HTTPS backend, Docker/ClamAV/Caddy, les poids BGE et un corpus DCE réel restent des frontières de recette. La CI GitHub ne fournit toujours pas une preuve exploitable lorsque les jobs échouent avant toute étape de runner.

## 2. État du code livré dans ce lot

Le lot précédent étend `web/src/features/dce/` avec `DceKnowledgePanel.tsx` et `useDceKnowledge.ts`. Le nouveau lot ajoute le value object pur `backend/app/modules/knowledge/application/benchmark.py`, le contrat `docs/reference/SMART_AO_V8_KNOWLEDGE_BENCHMARK_01_CONTRAT.md` et la commande `scripts/validate_knowledge_benchmark.py` pour valider un manifeste Golden DCE/RAG et scorer un rapport d’identifiants externe. Le retrieval est également durci pour filtrer la version DCE applicable dès le scope domaine, le service, la route et la requête SQLAlchemy. Ce correctif est poussé dans `93ba239` avec une régression dédiée sur les versions supersédées. Le lot `DCE-ANALYSIS-OPS-01`, poussé dans `fe488f5`, ajoute les runners one-shot Compose profilés `dce-analysis` et `dce-requirements` ainsi que leurs wrappers opérateur ; ils exposent uniquement des reçus techniques et ne démarrent pas avec le stack standard. Les tests worker et contrats opérateur passent ; l’exécution PostgreSQL/Docker réelle reste ouverte. La réconciliation documentaire correspondante est publiée dans `9457703`.

La lecture affiche uniquement les champs prévus par le contrat public : fraîcheur, cycle de vie, intégrité, compteurs, exigences structurées et localisation source. La recherche envoie une requête bornée à 500 caractères et un `top_k` fixé à 5 côté client. La vue affiche le score, le modèle d’embedding et un libellé de localisation ; elle n’affiche pas le contenu intégral du fragment ni de données financières.

| Surface | État | Preuve |
|---|---|---|
| Cockpit BOAMP | Codé et intégré | Panel, hook, routes API frontend, qualification humaine fermée. |
| Lecture DCE | Codée dans le backend et raccordée au frontend | DTO `CaseDceReadingResponse`, route `/api/v1/cases/{case_id}/dce-reading`, panel frontend. |
| Recherche knowledge/RAG | Codée derrière une route existante et raccordée au frontend | DTO fermé, route `/api/v1/cases/{case_id}/knowledge/search`, recherche `q`/`top_k`, version DCE applicable résolue côté serveur et filtrée en SQL. |
| DCE exigences | Projection, matérialisation et compteurs disponibles | Exigences limitées à la projection serveur, matérialisation hors HTTP par acteur SYSTEM, confirmation humaine non remplacée par une décision IA. |
| RAG/BGE | Antenne activable, pas activation production | Provider optionnel, retrieval, worker et benchmark de manifeste existants ; poids et corpus réels non chargés. |

## 3. Dépendances et intégrations

| Dépendance ou intégration | Niveau réel | Ce qui est greffé | Ce qui reste à prouver |
|---|---|---|---|
| FastAPI, Pydantic, SQLAlchemy, Alembic, psycopg | Noyau actif | Routes, DTOs fermés, repositories et migrations | CI distante exécutable et PostgreSQL online. |
| PostgreSQL 16 | Cible codée | Chaîne Alembic `0050 → 0051 → 0052 → 0053 → 0054`, contraintes et triggers | Démarrage Docker réel, upgrade online, tests DB et preuve des invariants. |
| OR-Tools CP-SAT | Greffé | Port/adaptateur, service, audit et migration `0051` | Cas métier réel et tests online. |
| RAG/BGE | Préparé et désactivé par défaut | Embeddings optionnels, registre JSONB, retrieval, route et recherche frontend | Poids BGE, corpus Golden DCE, benchmark et décision JSONB/pgvector/Qdrant. |
| Docling/PyMuPDF/OCR | Extras/ports optionnels | Factories et fallback déterministe | Scans, tableaux, budgets et revue humaine sur corpus réel. |
| S3/MinIO | Adaptateur optionnel | Hash, non-écrasement, stockage privé et contrôles | Bucket réel, droits, lifecycle, backup et restore. |
| BOAMP | Greffé jusqu’au frontend | Ingestion staging, scoring, persistence `0053`, qualification `0054`, HTTP, cockpit et outbox | Requête réseau contrôlée et recette fournisseur bus. |
| INSEE Sirene | Adaptateur read-only optionnel | Port, route et activation runtime | Token opérateur et requête réelle non sensible. |
| SMTP/ICS | Adaptateurs optionnels | Ports, workers et activation explicite | Comptes et délivrabilité/synchronisation réels. |
| Bus externe | Contrat et worker | Allowlist, HMAC, lease, retry, `2xx` avant `PUBLISHED`, profil Compose | Fournisseur, endpoint, auth, replay et déduplication réels. |
| Playwright | Non installé | Tests Vitest composants/hooks | Parcours navigateur contre URL HTTPS réelle. |
| Docker/VPS/Caddy/ClamAV | Préparés | Compose, pinning, healthchecks et runbooks | Exécution, EICAR, HTTPS, backup/restore et supervision. |

## 4. Vérification du rapport d’audit joint

Le rapport est **pertinent sur le verdict opérationnel**, mais certaines affirmations sont obsolètes ou insuffisamment prouvées. L’écart architectural des modèles ORM était avéré : les modèles métier ont été déplacés vers `pricing`, `preparation`, `submission`, `patron_action` et `enterprise`, avec exports de compatibilité et test d’ownership. La critique sur `pricing_scenarios` mutable était également avérée : la migration `20260823_0055` ajoute désormais un trigger `BEFORE UPDATE OR DELETE`, les transitions append-only restant la seule surface de changement d’état.

La mesure de couverture du rapport était proche mais non exacte dans l’état actuel : le run local `pytest -m 'not db' --cov=backend/app` mesure **67,45 %** et échoue encore au seuil configuré de 85,50 %. Cette mesure inclut des branches de bootstrap, d’authentification et de workers qui ne sont pas entièrement exercées hors PostgreSQL. Elle ne doit pas être masquée par une exclusion artificielle ; l’objectif restant est de compléter les tests, idéalement avec les tests DB actifs.

Deux remarques doivent être corrigées. Le test ICS n’a pas besoin du paquet `icalendar` : le renderer utilise son propre format et `uv run --extra calendar pytest backend/tests/infrastructure/test_ics_calendar.py` passe. Le test OR-Tools signalé ne constitue pas un échec métier démontré : l’erreur observée est une `connection refused` PostgreSQL sur `127.0.0.1:5432`, avant l’exécution du test de persistance.

Les remarques de sécurité sont partiellement confirmées. Le step-up MFA existe dans `AuthorizationPolicy`, mais il n’est pas automatiquement imposé à toutes les routes sensibles ; ce point reste ouvert. Le rate limiter process-local est un choix explicitement documenté et doit être remplacé par un store partagé avant déploiement multi-réplique. Le codec JWT supporte maintenant un `kid` et une clé de vérification historique, mais la rotation réelle doit encore être configurée par l’environnement de production. Le webhook est durci : HTTPS obligatoire, résolution DNS et refus des adresses privées/réservées, avec 27 tests ciblés passés.

Enfin, l’absence de preuve Docker/PostgreSQL/VPS/ClamAV/HTTPS/backup, de fournisseur bus et de corpus BGE réel est correcte. Ces éléments sont préparés par des scripts, profils Compose et runbooks, mais aucune exécution réelle ne doit être inventée. Le statut reste **NO-GO opérationnel** tant que ces preuves et une CI réellement exécutée ne sont pas disponibles.

## 5. Base de données et migrations

La persistence BOAMP est tenant-scoped. Les observations, liens, qualifications, événements et messages outbox utilisent les chemins transactionnels du projet. La migration `0053` porte les observations et fingerprints SHA-256 ; la migration `0054` porte les qualifications append-only et leurs contraintes. Les tests PostgreSQL du worker couvrent l’accusé fournisseur avant `PUBLISHED`, le retry après rejet et l’absence de publication lors d’une panne.

La migration offline jusqu’à `20260823_0055` est générable. La migration `0055` protège maintenant la table `pricing_scenarios` contre les mutations directes. La tentative online demandée dans cette session n’a pas été exécutée, car le script `scripts/start_local_postgres.sh` a constaté l’absence du binaire Docker et s’est arrêté avec `POSTGRES_LOCAL_STATUS=BLOCKED_DOCKER_OR_SERVICE_UNAVAILABLE`. Il n’existe donc pas de preuve que `0054` a été appliquée sur une instance réelle dans cet environnement.

Lorsque Docker sera disponible, le runbook est :

```bash
scripts/start_local_postgres.sh
export SMART_AO_TEST_DATABASE_URL='postgresql+psycopg://<user>:<password>@127.0.0.1:5433/<database>'
export SMART_AO_DATABASE_URL="$SMART_AO_TEST_DATABASE_URL"
uv run alembic -c backend/alembic.ini upgrade 20260823_0054
uv run pytest -q backend/tests/infrastructure/test_boamp_observation_persistence.py \
  backend/tests/infrastructure/test_boamp_qualification_persistence.py \
  backend/tests/process/test_opportunity_event_bus_persistence.py
uv run python scripts/recipe_boamp_postgres.py --apply
```

## 5. Preuves de validation disponibles

| Contrôle | Résultat |
|---|---:|
| Tests frontend après BOAMP + DCE/RAG | **93 passed** |
| Build TypeScript/Vite | **Passé** |
| Tests du hook DCE/RAG | **4 passed** |
| Tests du panel DCE/RAG | **3 passed** |
| Tests du client API | **5 passed** |
| Tests d’intégration App | **4 passed** |
| Tests knowledge version-scoped | **9 passed** |
| Workers DCE analyse/matérialisation et contrats opérateur | **28 passed** |
| Test SQLAlchemy de filtre versionné | **Passé** |
| Migration offline Alembic jusqu’à `0055` | **Passée** |
| Migration online et tests PostgreSQL | **Non prouvés dans le sandbox** |
| Docker réel | **Indisponible dans le sandbox** |
| Fournisseur bus réel | **Non configuré et non appelé** |

Le lot DCE/RAG frontend a été poussé dans `238868f`, la documentation a été réconciliée dans `e5c4d05`, KNOWLEDGE-BENCHMARK-01 a été poussé dans `fa48c02`, puis les runners DCE ont été publiés dans `fe488f5`. Le code de remédiation est publié dans `7d91b0a`; la présente réconciliation documentaire sera publiée séparément. Le code est validé localement ; seul le corpus réel, le cache BGE et la recette d’exécution restent externes. L’absence de preuve PostgreSQL online est indépendante des tests locaux.

## 6. Tâches ouvertes et ordre recommandé

Les tâches restantes dans `todo.md` concernent principalement des preuves externes : recette PostgreSQL réelle, contrat fournisseur bus réel, runners GitHub Actions fonctionnels, gate VPS, URL HTTPS frontend et rapport opérateur de restauration. Il reste également à exécuter une recette DCE/RAG sur un corpus contrôlé avec poids BGE réels avant de choisir une infrastructure vectorielle supplémentaire.

L’ordre recommandé est le suivant :

1. faire passer le gate frontend et backend local après les lots DCE/RAG et benchmark ;
2. commit/push du lot KNOWLEDGE-BENCHMARK-01 et mise à jour des documents canoniques — **réalisé dans `fa48c02`** ;
3. filtrer le retrieval par version DCE applicable dans le domaine, le service et SQL — **réalisé dans `93ba239`** ;
4. ajouter les runners opérateur DCE analyse et matérialisation, profilés et sans sortie sensible — **réalisé dans `fe488f5`** ;
5. exécuter PostgreSQL 16 et Alembic `0051`–`0055` sur Docker réel ;
6. lancer les tests de persistence BOAMP et du worker outbox ;
7. charger un corpus DCE non financier contrôlé et mesurer retrieval/fraîcheur/localisation ;
8. définir ensuite le fournisseur bus réel et sa recette contrôlée ;
9. ne lancer le gate VPS et le raccordement frontend HTTPS qu’après preuve d’une URL backend réelle.

## 7. Conclusion

**Oui, les antennes sont maintenant suffisamment structurées pour être greffées progressivement. Non, toutes les dépendances ne sont pas encore opérationnelles aujourd’hui.** Le code applicatif et les contrats sont en place pour BOAMP, DCE et la recherche RAG ; les environnements et fournisseurs nécessaires à la preuve de production ne le sont pas encore. Toute déclaration de mise en production devrait attendre la validation PostgreSQL online, la recette du bus, les tests d’intégration Docker et une CI GitHub réellement exécutée.

## Références internes

- [`docs/PROJECT_STATE.md`](PROJECT_STATE.md)
- [`docs/DEPENDENCY_INTEGRATION_STATUS_2026-08-22.md`](DEPENDENCY_INTEGRATION_STATUS_2026-08-22.md)
- [`docs/EXTERNAL_EVENT_BUS_CONTRACT.md`](EXTERNAL_EVENT_BUS_CONTRACT.md)
- [`docs/NEXT_LOT_POSTGRES_OUTBOX_GATE.md`](NEXT_LOT_POSTGRES_OUTBOX_GATE.md)
- [`docs/LOCAL_POSTGRES_TESTING.md`](LOCAL_POSTGRES_TESTING.md)
- [`docs/reference/SMART_AO_V8_DCE_DOCUMENT_EXTRACTION_01_CONTRAT.md`](reference/SMART_AO_V8_DCE_DOCUMENT_EXTRACTION_01_CONTRAT.md)
- [`docs/reference/SMART_AO_V8_KNOWLEDGE_INDEXING_OPS_01_CONTRAT.md`](reference/SMART_AO_V8_KNOWLEDGE_INDEXING_OPS_01_CONTRAT.md)
- [`docs/reference/SMART_AO_V8_KNOWLEDGE_BENCHMARK_01_CONTRAT.md`](reference/SMART_AO_V8_KNOWLEDGE_BENCHMARK_01_CONTRAT.md)
- [`backend/alembic/versions/20260823_0055_pricing_scenarios_immutability.py`](../backend/alembic/versions/20260823_0055_pricing_scenarios_immutability.py)


## Réconciliation du nouvel audit — 23 août 2026

Le nouvel audit est globalement pertinent sur les blocages opérationnels, mais deux remarques sont des faux positifs : l’extra `calendar` est bien déclaré (`icalendar 7.3.0`) et le renderer ICS local ne dépend pas d’un import absent. Les neuf détections detect-secrets étaient des fixtures synthétiques de tests, non des secrets de production ; elles sont maintenant annotées localement et le scan canonique passe.

Les corrections de ce lot ajoutent un contrôle mypy borné et reproductible sur le noyau de sécurité, verrouillé dans `uv.lock`, ainsi qu’une résolution sûre de l’IP derrière proxy : `X-Forwarded-For` n’est accepté que lorsque le pair direct appartient à `SMART_AO_TRUSTED_PROXY_CIDRS`, vide par défaut et configuré sur `172.30.0.0/24` dans Compose préproduction. Les tests couvrent les pairs approuvés et non approuvés, les adresses invalides et les CIDR invalides. Le rate limiter demeure process-local et nécessite toujours un store partagé avant un déploiement horizontal.

Le MFA step-up reste un point réellement ouvert : la policy et les tests de décision existent, mais aucune cérémonie TOTP d’enrôlement/vérification ni aucun appel `mfa_required=True` n’est encore publié. Il serait dangereux d’imposer la policy avant de fournir le parcours utilisateur complet. Les modèles `CaseAssignment*` et `CollaboratorTask*` restent également dans `platform/security/models.py`; une extraction supplémentaire nécessite une décision de bounded context et une régression Alembic complète.

La validation locale du lot donne : 867 tests backend non-DB passés, 458 DB désélectionnés, couverture 67,62 % sous le seuil 85,50 %, Ruff passé, mypy sécurité passé, detect-secrets passé, 93 tests frontend et build passés, Alembic offline jusqu’à `0055` passé. PostgreSQL online, Docker/VPS/ClamAV/HTTPS, corpus BGE/DCE, bus externe et runners GitHub Actions restent non prouvés. Le verdict opérationnel demeure **NO-GO** et la PR #49 ne doit pas être fusionnée vers `main`.

Le détail ligne par ligne est dans [`AUDIT_RECONCILIATION_2026-08-23_2.md`](AUDIT_RECONCILIATION_2026-08-23_2.md).


## Réconciliation du troisième audit — 23 août 2026

Le troisième audit backend/frontend/DevOps/métier confirme le verdict opérationnel NO-GO, tout en distinguant les défauts déjà corrigés des gaps métier et des preuves externes. Les corrections codables ajoutées depuis la dernière revue sont : helper d’authentification HTTP partagé, port de stockage dans platform, graphe patron_action avec projection synchronisée, installation Docker backend depuis `uv.lock`, actions CI par SHA, Trivy frontend, Nginx non-root/healthcheck, Compose dev borné au loopback, câblage JWT `kid`, ErrorBoundary, RBAC UI et outillage frontend.

Restent valides : couverture sous 85,50 %, absence de preuve CI exécutée faute de runner, dépendance aux environnements PostgreSQL/Docker/VPS, absence de cérémonie TOTP active, N+1 non benchmarkés, projection/rétention outbox à définir et incomplétude du moteur métier CCAP/coût/DC1-DC4. Les affirmations `icalendar` manquant, token frontend en localStorage, shared kernel encore dans DCE et frontend non-root sont obsolètes ou fausses après vérification. Le détail complet est conservé dans `docs/AUDIT_RECONCILIATION_2026-08-23_3.md`.


## Réconciliation du quatrième audit — 24 août 2026

Le quatrième rapport confirme une régression réelle de `patron_action` : le trigger 0038 refusait les mises à jour de projection que le service 5f2aabf effectuait. La migration additive `20260824_0056` conserve l’append-only historique et autorise uniquement `state`, `aggregate_revision` et `updated_at`. Le readiness exige désormais la tête Alembic `20260824_0056`; les Compose local et préproduction exécutent un service `migrate` avant backend et workers. Les seeds DB, le chemin JSON outbox, la regex d’idempotence, l’extra object-storage, l’audit des extras et le bind PostgreSQL local ont été corrigés.

Les consommateurs application preparation/submission utilisent le port storage platform, et ErrorBoundary force un re-montage après retry. La validation finale locale donne 885 tests backend non-DB passés, 458 DB désélectionnés, 98 tests frontend passés sur 23 fichiers, typecheck/build passés, Ruff/mypy/lockfile/shell/detect-secrets passés et Alembic offline jusqu’à 0056 passé. Le sandbox courant ne possède ni Docker ni PostgreSQL accessible ; les preuves online annoncées dans le rapport source sont conservées comme preuves fournies mais non reproduites ici. Le verdict reste **NO-GO production** jusqu’à une recette online, une CI avec runners actifs et une validation métier/infra complète.

Le détail ligne par ligne est dans [`AUDIT_RECONCILIATION_2026-08-24_4.md`](AUDIT_RECONCILIATION_2026-08-24_4.md).


## Retour sur l’audit n°5 — 24 août 2026

Le cinquième audit a été vérifié et est pertinent. Il a détecté un défaut réel dans le service `migrate` du Compose de développement : `/app/alembic.ini` ne correspondait pas au chemin réel `/app/backend/alembic.ini` de l’image backend. Le chemin est corrigé. Les autres findings confirmés sont traités par une constante de tête Alembic partagée et un test anti-dérive, un diagnostic readiness séparant `database` et `schema`, une assertion event-bus isolée par tenant, une couverture élargie de la garde 0056, l’installation explicite de l’extra `calendar` dans les commandes canoniques et des timeouts Vitest adaptés aux runners CPU-contraints.

Validation locale après le lot : 888 tests backend non-DB passés, 458 tests DB désélectionnés, 98 tests frontend passés, typecheck/build passés, Ruff/mypy/lockfile/syntaxe shell passés et 31 tests ciblés architecture/ops/readiness passés. La preuve PostgreSQL réelle annoncée dans le rapport source n’est pas reproduite dans le sandbox courant ; Docker et PostgreSQL restent indisponibles ici. Le verdict de production reste NO-GO jusqu’aux preuves online, à une CI réellement exécutée et aux lots métier BTP.

Le détail complet est conservé dans [`AUDIT_RECONCILIATION_2026-08-24_5.md`](AUDIT_RECONCILIATION_2026-08-24_5.md).


## 11. Réconciliation de l’audit exhaustif — 24 août 2026

Le rapport exhaustif a été archivé et confronté au code. Cette section est la mise à jour la plus récente ; les mesures historiques précédentes sont conservées pour traçabilité mais ne doivent pas être interprétées comme l’état courant. L’auditeur a exécuté Docker/PostgreSQL et rapporté 1 346 tests avec 90,96 % ; cette preuve reste externe. Dans le sandbox courant, Docker est indisponible et les tests PostgreSQL n’ont pas été exécutés online.

Les corrections sûres confirmées sont maintenant appliquées. Le webhook et le bus HTTP passent par `platform/security/public_http.py`, qui impose HTTPS, rejette les credentials/fragments, filtre les DNS privés/réservés et refuse les redirections. Les réponses API bénéficient de headers de défense en profondeur. Les quatre workers outbox concernés ont une politique de tentatives bornées et un état terminal `FAILED`. La limite runtime d’upload DCE est alignée sur 150 MB, le port PostgreSQL du Compose dev est configurable, le workflow CI est renforcé et la baseline de secrets est assainie.

Le finding métier BTP-1a est traité au niveau backend par `POST /api/v1/cases`. La route résout l’acteur et le tenant côté serveur, limite la capability au patron admin, construit une commande fermée et idempotente, et retourne seulement une référence `AFF`. Le handler vérifie la portée, la cohérence de l’origine et, lorsqu’elle est fournie, l’existence de la Consultation dans le tenant avec sa révision exacte. La persistence est derrière des ports applicatifs et crée le lien Case–Consultation sans importer l’ORM dans l’application. L’écran frontend de création et la validation PostgreSQL online restent à faire.

La dette ARCH-001, le MFA/TOTP complet, le rate limiter distribué, le contrat et la rétention `cockpit_projection`, les recettes Docker/ClamAV/EICAR/HTTPS/backup-restore, le fournisseur bus réel, les poids BGE/corpus Golden, l’OCR métier et les fonctions BTP centrales restent ouverts. Aucun rôle délégué ne reçoit de capabilities globales par raccourci. Aucun provider réel, prix, décision, signature qualifiée ou dépôt externe n’est simulé.

| Validation locale après ce lot | Résultat |
|---|---|
| Backend hors `db` | 906 tests passés ; 458 tests DB désélectionnés. |
| Frontend | 98 tests dans 23 fichiers, typecheck, lint et build passés ; deux warnings hooks connus. |
| Qualité et migrations | Ruff, mypy ciblé, lock UV, detect-secrets, scripts shell, diff et Alembic offline jusqu’à `20260824_0056` passés. |
| Docker/PostgreSQL/VPS/CI externe | Non exécutés ici ; aucune preuve locale ou distante verte ne doit être déduite du code statique. |

Le verdict demeure **NO-GO opérationnel** pour une vente ou une mise en production revendiquée tant que la CI n’exécute pas réellement ses étapes, que la recette PostgreSQL/Docker/VPS n’est pas produite et que les capacités métier centrales ne sont pas livrées.


## 12. Réponse au rapport d’audit légendaire — 24 août 2026

Le rapport `docs/operator-reports/AUDIT_LEGENDAIRE_SMART_AO_V8_2026-08-24.md` confirme globalement le verdict NO-GO et apporte deux constats nouveaux correctement étayés. Le premier est une régression de contrat : le test attendait encore le port littéral `127.0.0.1:5432:5432` après que le Compose eut été sécurisé par `SMART_AO_POSTGRES_HOST_PORT`. Le second est une incohérence cold-start : le fallback `dev-only-signing-key-change-me-0123456789` était refusé par la garde du runtime production.

Ces deux points sont corrigés. Le test accepte désormais le mapping paramétrable tout en conservant le binding loopback et contrôle la présence d’une clé explicitement locale dans `.env.example`. Le Compose development utilise `local-development-signing-key-change-me-0123456789`; la garde production, les exigences préproduction et les placeholders restent inchangés. Docker n’étant pas disponible dans le sandbox courant, le démarrage à froid n’est pas revendiqué comme rejoué localement ; il doit être vérifié sur l’hôte Docker de l’auditeur ou du propriétaire.

La suite backend locale hors `db` est maintenant verte : **906 passed, 458 deselected**. Le frontend reste vert avec **98 tests dans 23 fichiers**, typecheck et build passés, lint sans erreur mais avec deux warnings hooks connus. Le rapport auditeur indiquait 905+1 failed au commit `33986fb`; cette observation est confirmée et corrigée. La baseline locale contient 14 entrées qualifiées ; le nombre 10 donné par l’auditeur est une mesure de son clone et n’est pas substitué sans analyse supplémentaire.

La CI reste non exploitable : le run post-push `32728988801` a échoué avant toute étape, avec `runnerName` nul pour `backend`, `frontend` et `image-security`. Les résultats Docker/PostgreSQL/ClamAV live de l’auditeur sont conservés comme preuves externes. Le verdict ne change pas : socle renforcé, mais **NO-GO opérationnel** jusqu’à rétablissement de la CI, recette Docker/PostgreSQL/HTTPS/backup-restore et livraison des fonctions métier centrales.


## 13. Priorité ARCH-001 et cœur métier BTP — 24 août 2026

Une première tranche de réduction ARCH-001 est livrée : les services de lecture `PatronAssignmentCockpitService` et `AssignmentHistoryService` consomment leurs Protocols applicatifs et reçoivent les readers SQLAlchemy depuis la composition root. Les règles de frontière sont verrouillées par test. Cette approche préserve l’isolation tenant, les projections fermées et les audits de refus ; elle n’est pas une prétention de suppression immédiate des 64 arêtes historiques.

Le premier vertical slice métier ciblé est `COST-BASIS-01`. Le domaine pricing calcule désormais en centimes et points de base les coûts complets, réserves BTP, marge, seuil de rentabilité, prix plancher et prix cible. Les résultats sont persistés de façon additive sur `pricing_scenarios` par le head Alembic `20260824_0057`, avec contraintes de cohérence. La route de création de scénario reste patronale et financière privée.

Après ce lot, la suite backend hors DB est à **914 passed, 458 deselected** ; Ruff, mypy ciblé et les scripts shell passent. Le SQL offline de la migration 0057 est généré. La persistence PostgreSQL online et le parcours Docker restent à exécuter dans un environnement disponible.

Le cœur BTP est donc renforcé mais non finalisé : le croisement documentaire CCAP–CCTP–DPGF–BPU, les risques structurés, l’OCR/corpus Golden, la génération DC1/DC2/DC4, la décision finalisable et le dépôt restent des slices de production à coder et recetter. Le verdict opérationnel demeure NO-GO.


## Tranche mutationnelle et registre CCAP/CCTP — 24 août 2026

Les lectures préparatoires des services mutationnels membership et pricing passent maintenant par des ports applicatifs : `AssignmentManagementReader` pour les contrôles de case/affectation et `PricingScenarioReader` pour les projections de scénarios. Les adaptateurs SQLAlchemy sont assemblés dans la composition root. Les handlers d’écriture restent raccordés au dispatcher transactionnel afin de préserver event/outbox/receipt, idempotence et révision ; ARCH-001 est donc réduit par tranches, non supprimé en une seule opération.

Le registre structuré des risques CCAP/CCTP est codé derrière la capability patronale dédiée `decision.risk.write`. Chaque risque doit référencer une affaire tenant-scoped, sa version DCE applicable, une analyse d’extraction terminée et un fragment dont l’extrait et les offsets concordent avec le texte source. La migration `20260824_0058` ajoute la persistence, les FKs composites et les contraintes de catégorie, sévérité, vraisemblance, traitement et provenance. L’événement est sparse et ne contient pas le texte financier ou documentaire sensible.

La validation locale de cette tranche est de **929 tests backend hors `db` passés**, avec **458 désélectionnés**, Ruff et mypy ciblé passés, scripts shell validés et Alembic offline généré jusqu’à `20260824_0058`. PostgreSQL online, Docker, CI avec runner, VPS et fournisseurs externes ne sont pas revendiqués. Le registre n’est pas encore un moteur complet d’analyse AO : DPGF/BPU, OCR/corpus Golden, DC1/DC2/DC4 et GO/NO-GO restent à implémenter et recetter.


## Mise à jour du 24 août 2026 — bounded context Decision et décision patronale contrôlée

Le bounded context explicitement choisi pour la prochaine extraction ARCH-001 est désormais **Decision**. Le `PatronDecisionDossierService` lit via un port `DecisionDossierReader`; son adaptateur SQLAlchemy reste en infrastructure et un test de frontière empêche le retour d’imports ORM dans le service applicatif.

Le premier croisement risques–exigences est codé par une liaison tenant-scoped append-only. Il ne s’exécute que contre une exigence dont la confirmation humaine courante est `CONFIRMED`, avec concordance affaire/version et risque/version contrôlée côté serveur. Les documents simplement extraits, non confirmés ou ambigus ne peuvent pas produire cette liaison. La liaison génère une action patronale `DECIDE_GO_NO_GO` dans la même transaction et conserve uniquement des références d’identifiants sûres.

La finalisation `GO` ou `NO_GO` est une décision patronale explicite, non une qualification automatique. Le handler impose un contexte Decision `FROZEN`, un fingerprint affiché, des références de contexte, la confirmation humaine des références `DCE_REQUIREMENT` et une révision optimiste. Aucun montant financier, extrait, justification ou détail `FINANCIAL_PRIVATE` n’entre dans les DTO ou événements de cette surface.

La validation ciblée est de **41 tests passés et 2 désélectionnés**, avec Ruff passé, et le gate backend complet hors `db` compte **964 tests passés et 458 désélectionnés**. SQL Alembic offline a été généré jusqu’à `20260824_0059`. Cette validation ne remplace pas une exécution PostgreSQL online. Le GO/NO-GO ne doit pas être présenté comme un moteur automatique BTP : le croisement CCAP/CCTP avec DPGF/BPU, l’OCR/RAG qualifiant, la génération DC1/DC2/DC4 et la recette opérationnelle restent ouverts.


## Mise à jour du 24 août 2026 — lecture Decision et rapprochement pricing contrôlé

La surface patronale Decision expose désormais une lecture paginée des liens risque–exigence, ordonnée par `(created_at, link_id)` et plafonnée à 100 éléments. L’action `DECIDE_GO_NO_GO` associée est jointe à la projection sous forme d’état, sévérité et révision. Le filtre tenant/Case est appliqué côté adaptateur et la capability dédiée `decision.risk.read` n’est pas accordée au collaborateur.

Le rapprochement DPGF/BPU est volontairement limité à des candidats issus de lots normalisés `COMMITTED` de la même Case et de type `DPGF` ou `BPU`. La recherche porte sur le code ou la désignation, tandis que la projection exclut quantité, prix unitaire et total. Aucun résultat n’est présenté comme une qualification ou un calcul financier ; la confirmation patronale et la provenance restent nécessaires.

Le contrat GO conditionnel est consolidé : l’issue `CONDITIONAL_GO` exige au moins une et au plus 32 conditions structurées, avec responsable, échéance ou justification de son absence et conséquence d’échec. Les conditions sont validées par les invariants domaine, persistées à l’état `OPEN` dans la transaction Decision et comptées dans le receipt. `GO` et `NO_GO` refusent les conditions excédentaires.

Les nouveaux tests ciblés portent le total intermédiaire à **32 tests passés**, avec Ruff et mypy passés sur 38 fichiers. Le run CI le plus récent `32756930349`, déclenché par `ea103d1`, est encore `queued` avant toute étape de runner (`runnerName: null`, zéro étape pour backend, frontend et image-security). La CI n’est donc pas une preuve distante ; PostgreSQL online, Docker, VPS, fournisseurs externes et corpus réel restent non exécutés.


## Mise à jour du 24 août 2026 — recette PostgreSQL et contrôle de soumission

La recette PostgreSQL réelle n’a pas été exécutée dans le sandbox : aucun exécutable `pg_isready`, aucun listener sur `:5432`, aucune variable `SMART_AO_DATABASE_URL` et aucun socket Docker n’étaient présents. Cette limitation empêche de revendiquer une migration online, une persistence effective du GO conditionnel, une vérification des triggers append-only, une isolation inter-tenant ou une transaction outbox validée.

Un garde domaine de soumission est néanmoins préparé. Il accepte uniquement une Decision finalisée `GO` ou `CONDITIONAL_GO`, sur contexte `FROZEN`, avec exigences DCE confirmées, conditions satisfaites pour un GO conditionnel et actions de risques résolues. Il renvoie des raisons de blocage non financières, ne publie aucun dossier et ne calcule aucun montant.

Le gate local compte **971 tests passés et 458 désélectionnés**, avec 39 tests ciblés sur la tranche récente. Ruff, mypy ciblé et detect-secrets sont passés. La recette PostgreSQL online, Docker, VPS, fournisseurs externes et la CI avec runner effectif demeurent non démontrés.


## Mise à jour du 24 août 2026 — diagnostic CI et recette Docker/PostgreSQL

Le dernier run CI `32761180934`, associé au commit `8798f36`, est terminé en échec avant exécution : les trois jobs `backend`, `frontend` et `image-security` ont `runnerName: null` et zéro étape. La récupération des journaux renvoie `log not found`. Aucun test, build ou scan distant ne peut donc être analysé comme un résultat de code.

La simulation PostgreSQL Docker n’a pas démarré car l’exécutable `docker` est absent du sandbox. Le Docker de l’ordinateur utilisateur n’est pas accessible depuis cet environnement. La migration 0059 reste contrôlée offline uniquement ; il n’existe pas de preuve PostgreSQL online, de seed, d’outbox, de FKs ou de trigger exercé.

Le rapport associé décrit la recette à rejouer sur une machine équipée, avec tenant, Case, DCE applicable, exigence confirmée, risque sourcé, Decision gelée et `CONDITIONAL_GO`. Le seed doit vérifier l’état `OPEN` des conditions et refuser toute ressource étrangère ou document non vérifié. Le gate local reste à **971 tests passés et 458 désélectionnés**.
