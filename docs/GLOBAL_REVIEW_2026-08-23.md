# Revue globale SMART_AO V8 — 23 août 2026

## Verdict exécutif

Le dépôt possède un **noyau métier sécurisé et largement codé**, mais il ne constitue pas encore une plateforme opérationnelle intégralement raccordée. Les frontières hexagonales, la résolution serveur du tenant et de l’acteur, l’idempotence, l’append-only, la révision optimiste et la confidentialité financière sont présentes dans les slices livrés. En revanche, une dépendance déclarée dans l’architecture cible ne doit pas être confondue avec une intégration active : plusieurs composants sont optionnels, désactivés par défaut ou attendent une recette Docker, PostgreSQL, fournisseur ou VPS réelle.

La branche auditée est `docs/pricing-http-next-lot-28`, propre au moment de la revue, avec le dernier commit poussé `23efe31`. La chaîne Alembic comporte les migrations `0051` OR-Tools, `0052` profils de veille, `0053` observations BOAMP et `0054` qualifications BOAMP. Le code SQL offline est disponible ; aucune preuve PostgreSQL online n’est revendiquée dans le sandbox, qui ne dispose ni de Docker ni de PostgreSQL local.

## Niveau réel des dépendances

| Brique | Niveau actuel | Ce qui est effectivement prouvé | Ce qui reste à faire |
|---|---|---|---|
| FastAPI/Pydantic/SQLAlchemy/Alembic/psycopg | Greffé au noyau | Routes, contrats, persistence et tests locaux | Recette PostgreSQL online et CI distante exécutable. |
| PostgreSQL | Registre canonique codé | Migrations jusqu’à `0054`, tests DB collectés, recette opérateur | Démarrer PostgreSQL 16 sur Docker réel, appliquer `0051`–`0054`, vérifier triggers et tests. |
| OR-Tools CP-SAT | Greffé derrière un module isolé | Adaptateur, service, audit append-only et migration `0051` | Mesurer sur un cas métier non financier et exécuter les tests online. |
| RAG/BGE | Préparé, désactivé | Migration `0050`, provider optionnel, registre JSONB, retrieval et worker one-shot | Précharger les poids, corpus Golden DCE, benchmark, puis décider JSONB/pgvector/Qdrant. |
| Docling/PyMuPDF/OCR | Ports et extras optionnels | Factories et fallback déterministe | Corpus scans/tableaux, budgets CPU/RAM et revue humaine. |
| S3/MinIO | Adaptateur optionnel | Stockage privé, hash, écriture non écrasante et script de vérification | Bucket réel, permissions, lifecycle, backup/restore et recette Docker. |
| BOAMP | Greffé jusqu’à la frontière applicative | Staging borné, persistence `0053`, scoring, lecture/qualification `0054`, outbox | PostgreSQL online, recette réseau contrôlée et fournisseur bus réel. |
| INSEE Sirene | Adaptateur read-only optionnel | Port, route et activation runtime | Token opérateur hors Git et recette réelle non sensible. |
| SMTP/ICS | Adaptateurs optionnels | Workers, ports et activation explicite | Compte SMTP/agenda réel, délivrabilité et synchronisation distante. |
| Bus externe | Contrat générique et worker codés | Allowlist, HMAC, lease, retry, `2xx` avant `PUBLISHED`, activation désormais explicite | Contrat fournisseur, endpoint, auth, déduplication et replay réels. |
| Playwright | Non installé | Tests frontend composant/hook | Parcours navigateur contre URL HTTPS réelle. |
| VPS/Caddy/ClamAV réel | Préparé par Compose et scripts | Manifests, healthchecks, pinning et procédures | Exécution sur VPS, EICAR, HTTPS, backup/restore et supervision. |

Les extras Python sont correctement séparés dans `pyproject.toml` : `rag`, `document-advanced`, `object-storage`, `connectors`, `notifications` et `calendar`. Cette séparation est saine : elle évite de gonfler ou d’activer silencieusement la production, mais implique une procédure d’installation et de recette par brique.

## Base de données et invariants

La base canonique est PostgreSQL 16. Les migrations forment une chaîne linéaire `0050 → 0051 → 0052 → 0053 → 0054`. Les tables BOAMP utilisent des clés et FK composites tenant-scoped, des checks fermés, des unicités d’idempotence et des triggers append-only. Les événements de domaine et messages outbox sont écrits dans les chemins transactionnels des repositories. Les workers utilisent `FOR UPDATE SKIP LOCKED`, des leases et des retries bornés.

La faiblesse actuelle n’est pas une absence de modèle ou de migration, mais l’absence de preuve d’exécution dans l’environnement disponible. Le script `scripts/start_local_postgres.sh` prépare un conteneur PostgreSQL 16 digest-pinné sur le port `5433`, et `scripts/recipe_boamp_postgres.py` applique/inspecte la chaîne BOAMP puis exécute les tests de persistence observations et qualifications. Ces scripts ont été testés statiquement et avec des doubles déterministes ; la validation online attend Docker réel.

## Intégrations réellement activables aujourd’hui

Il est possible de greffer progressivement les dépendances, mais pas toutes en bloc. La meilleure séquence est : PostgreSQL réel, puis une recette DCE avancée ou RAG sur corpus contrôlé, puis S3/MinIO, puis les fournisseurs métier un par un. OR-Tools est déjà la dépendance de calcul la plus avancée ; HiGHS et PuLP ne doivent pas être ajoutés sans besoin comparatif démontré.

Le worker bus externe vient d’être durci : `SMART_AO_EXTERNAL_EVENT_BUS_ENABLED` doit valoir `1`, l’URL et le token sont obligatoires, et le service préproduction est derrière le profil Compose `external-bus`. En mode par défaut, le worker quitte proprement sans ouvrir de connexion. Le contrat détaillé se trouve dans [`EXTERNAL_EVENT_BUS_CONTRACT.md`](EXTERNAL_EVENT_BUS_CONTRACT.md).

## Ce qui reste codable immédiatement et ce qui ne l’est pas

Le prochain travail codable est le durcissement des antennes d’intégration et de leurs recettes : configuration runtime explicite, contrats opérateur, tests de non-fuite, validation des transitions outbox et documentation. Ce travail peut être effectué sans fournisseur réel. En revanche, le raccordement à un endpoint bus, l’activation BGE sur des poids réels, un bucket S3 réel, l’URL HTTPS frontend et le gate VPS ne doivent pas être simulés dans le sandbox.

Les tâches actuellement ouvertes dans `todo.md` sont donc principalement des preuves externes : recette PostgreSQL réelle, contrat fournisseur bus, runners GitHub Actions fonctionnels, gate VPS, URL HTTPS frontend et rapport opérateur de restauration. Elles restent ouvertes à juste titre.

## Preuves locales de la revue

Les contrôles locaux disponibles avant la prochaine recette ont couvert Ruff, la baseline `detect-secrets`, les frontières d’architecture, les routes BOAMP, le worker outbox, les scripts de recette et la suite non-DB. La collecte sépare les tests PostgreSQL : 825 tests non-DB sont collectés et 456 tests DB sont identifiés dans la configuration courante. Ces chiffres de collecte ne sont pas une réussite PostgreSQL online.

## Références

- [`docs/DEPENDENCY_INTEGRATION_STATUS_2026-08-22.md`](DEPENDENCY_INTEGRATION_STATUS_2026-08-22.md) — matrice détaillée des dépendances et intégrations.
- [`todo.md`](../todo.md) — checklist opérationnelle restante.
- [`pyproject.toml`](../pyproject.toml) — dépendances, extras et marqueurs de tests.
- [`backend/alembic/versions/20260823_0051_optimization_runs.py`](../backend/alembic/versions/20260823_0051_optimization_runs.py) à [`20260823_0054_boamp_qualifications.py`](../backend/alembic/versions/20260823_0054_boamp_qualifications.py) — chaîne des dernières migrations.
- [`docs/LOCAL_POSTGRES_TESTING.md`](LOCAL_POSTGRES_TESTING.md) — recette PostgreSQL locale.
- [`docs/EXTERNAL_EVENT_BUS_CONTRACT.md`](EXTERNAL_EVENT_BUS_CONTRACT.md) — contrat du worker bus externe.
