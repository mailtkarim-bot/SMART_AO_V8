# SMART_AO V8 — Revue globale actualisée

**Date : 23 août 2026**  
**Branche : `docs/pricing-http-next-lot-28`**  
**Dernier commit poussé : [`fa48c02`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/fa48c02)**
**Auteur : Manus AI**

## 1. Verdict exécutif

Le projet possède désormais un noyau métier substantiel et structuré autour de frontières hexagonales : domaine/application indépendants de FastAPI et SQLAlchemy, résolution serveur du tenant et de l’acteur, contrôles d’autorisation, idempotence, révision optimiste, événements/outbox et append-only PostgreSQL. Les surfaces BOAMP sont disponibles jusqu’au cockpit patronal frontend. La lecture DCE et la recherche knowledge/RAG sont maintenant exposées depuis le cockpit sur les affaires sélectionnées, avec des projections minimales et une recherche bornée côté serveur.

Le produit n’est toutefois pas encore **opérationnel de bout en bout**. Les dépendances externes sont à plusieurs niveaux de maturité et ne doivent pas être confondues avec des intégrations activées. PostgreSQL réel, un fournisseur bus réel, une URL HTTPS backend, Docker/ClamAV/Caddy, les poids BGE et un corpus DCE réel restent des frontières de recette. La CI GitHub ne fournit toujours pas une preuve exploitable lorsque les jobs échouent avant toute étape de runner.

## 2. État du code livré dans ce lot

Le lot précédent étend `web/src/features/dce/` avec `DceKnowledgePanel.tsx` et `useDceKnowledge.ts`. Le nouveau lot ajoute le value object pur `backend/app/modules/knowledge/application/benchmark.py`, le contrat `docs/reference/SMART_AO_V8_KNOWLEDGE_BENCHMARK_01_CONTRAT.md` et la commande `scripts/validate_knowledge_benchmark.py` pour valider un manifeste Golden DCE/RAG et scorer un rapport d’identifiants externe.

La lecture affiche uniquement les champs prévus par le contrat public : fraîcheur, cycle de vie, intégrité, compteurs, exigences structurées et localisation source. La recherche envoie une requête bornée à 500 caractères et un `top_k` fixé à 5 côté client. La vue affiche le score, le modèle d’embedding et un libellé de localisation ; elle n’affiche pas le contenu intégral du fragment ni de données financières.

| Surface | État | Preuve |
|---|---|---|
| Cockpit BOAMP | Codé et intégré | Panel, hook, routes API frontend, qualification humaine fermée. |
| Lecture DCE | Codée dans le backend et raccordée au frontend | DTO `CaseDceReadingResponse`, route `/api/v1/cases/{case_id}/dce-reading`, panel frontend. |
| Recherche knowledge/RAG | Codée derrière une route existante et raccordée au frontend | DTO fermé, route `/api/v1/cases/{case_id}/knowledge/search`, recherche `q`/`top_k`. |
| DCE exigences | Projection et compteurs disponibles | Exigences limitées à la projection serveur, confirmation humaine non remplacée par une décision IA. |
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

## 4. Base de données et migrations

La persistence BOAMP est tenant-scoped. Les observations, liens, qualifications, événements et messages outbox utilisent les chemins transactionnels du projet. La migration `0053` porte les observations et fingerprints SHA-256 ; la migration `0054` porte les qualifications append-only et leurs contraintes. Les tests PostgreSQL du worker couvrent l’accusé fournisseur avant `PUBLISHED`, le retry après rejet et l’absence de publication lors d’une panne.

La migration offline jusqu’à `20260823_0054` est générable. La tentative online demandée dans cette session n’a pas été exécutée, car le script `scripts/start_local_postgres.sh` a constaté l’absence du binaire Docker et s’est arrêté avec `POSTGRES_LOCAL_STATUS=BLOCKED_DOCKER_OR_SERVICE_UNAVAILABLE`. Il n’existe donc pas de preuve que `0054` a été appliquée sur une instance réelle dans cet environnement.

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
| Migration offline Alembic jusqu’à `0054` | **Passée** |
| Migration online et tests PostgreSQL | **Non prouvés dans le sandbox** |
| Docker réel | **Indisponible dans le sandbox** |
| Fournisseur bus réel | **Non configuré et non appelé** |

Le lot DCE/RAG frontend a été poussé dans `238868f`, la documentation a été réconciliée dans `e5c4d05`, puis KNOWLEDGE-BENCHMARK-01 a été poussé dans `fa48c02`. Le code est validé localement ; seul le corpus réel, le cache BGE et la recette d’exécution restent externes. L’absence de preuve PostgreSQL online est indépendante des tests locaux.

## 6. Tâches ouvertes et ordre recommandé

Les tâches restantes dans `todo.md` concernent principalement des preuves externes : recette PostgreSQL réelle, contrat fournisseur bus réel, runners GitHub Actions fonctionnels, gate VPS, URL HTTPS frontend et rapport opérateur de restauration. Il reste également à exécuter une recette DCE/RAG sur un corpus contrôlé avec poids BGE réels avant de choisir une infrastructure vectorielle supplémentaire.

L’ordre recommandé est le suivant :

1. faire passer le gate frontend et backend local après les lots DCE/RAG et benchmark ;
2. commit/push du lot KNOWLEDGE-BENCHMARK-01 et mise à jour des documents canoniques — **réalisé dans `fa48c02`** ;
3. exécuter PostgreSQL 16 et Alembic `0051`–`0054` sur Docker réel ;
4. lancer les tests de persistence BOAMP et du worker outbox ;
5. charger un corpus DCE non financier contrôlé et mesurer retrieval/fraîcheur/localisation ;
6. définir ensuite le fournisseur bus réel et sa recette contrôlée ;
7. ne lancer le gate VPS et le raccordement frontend HTTPS qu’après preuve d’une URL backend réelle.

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
