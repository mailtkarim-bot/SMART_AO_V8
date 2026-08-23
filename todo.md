# SMART_AO V8 — Checklist durable

Cette checklist est la source de vérité opérationnelle après réconciliation des deux audits. Les anciennes entrées historiques détaillées ont été remplacées par le journal des slices publiés et les seules frontières encore ouvertes.

## Corrections d’audit publiées

- [x] **Protection anti-brute-force progressive** — `LoginRateLimiter` injectable, buckets SHA-256, throttling `/login` et `/refresh`, audit des refus `429` et `Retry-After`. Commit `025c36d`, CI `32076462140` verte.
- [x] **Fixtures PostgreSQL de tests centralisées** — `backend/tests/conftest.py`, `tests.support.database`, URL unique `SMART_AO_TEST_DATABASE_URL` avec fallback par concaténation, 43 modules nettoyés. Commit `aac4de0`, CI `32078237301` verte.
- [x] **Observabilité et durcissement runtime** — `request_id`, logs JSON opérationnels, compteurs `/metrics` sans données métier, image backend digest-pinnée et utilisateur non-root avec quarantaine privée contrôlée. Commits `0ecb24c` et `0ab3cbc`, CI finale `32080763983` verte.
- [x] **Dépendances frontend reproductibles** — suppression de `latest` dans `web/package.json`, alignement des spécificateurs avec `web/pnpm-lock.yaml`, installation `--frozen-lockfile` et build TypeScript strict. Commit `d4b33fe`, CI `32081102590` verte.
- [x] **Couverture et concurrence déterministes** — seuil initial `85 %` dans `pyproject.toml` et la CI, deux scénarios PostgreSQL couvrant révision optimiste et receipt `PROCESSING` avant outbox. Mesure locale : `402 passed`, couverture branchée `89,32 %`. Commit `e3eafc7`, CI `32083322693` verte.

## État technique publié

- [x] Healthchecks live/ready, factory de production, scripts de déploiement, sauvegarde/restauration isolée, rotation bornée des logs/secrets et pinning des images sont publiés.
- [x] Les slices métier DCE, sécurité, affectations patron/collaborateur, préparation, capacités/preuves, revues/brouillons techniques et fondation financière déjà publiés restent couverts par la suite backend et ne doivent pas être réouverts comme tâches historiques.
- [x] Les invariants de sécurité restent obligatoires : tenant résolu serveur, confidentialité financière absolue, append-only des registres immuables, révision optimiste et idempotence par `command_id`/`idempotency_key`.

## Tâches réellement restantes

- [x] **PRICING-IMPORT-HTTP-PERSISTENCE-01** — preview patronale DPGF/BPU/Excel persistée en lot normalisé `PREVIEWED`, lecture patronale tenant-scoped et commit atomique des lignes valides vers `DRAFT`. Le parcours HTTP, l’idempotence, la policy auditée, la classification `FINANCIAL_PRIVATE`, le hook frontend et les tests locaux sont livrés sur la PR #49 ; la CI GitHub reste à exécuter sur un runner disponible.
- [x] **SUBMISSION-SIGNATURE-HTTP-01** — routes patronales authentifiées, callback hash-only HMAC, projection minimale, audit, idempotence et séparation stricte d’avec la preuve de dépôt publiés par `a7c0d58`. Le provider de test local déterministe et sans réseau est publié par `9bb8c90`; aucun fournisseur réel ni dépôt externe n’est simulé.
- [x] **OPPORTUNITY-WATCH-PROFILE-01 / persistence + HTTP** — profil patronal versionné, migration `0052`, idempotence/outbox, révision optimiste, versions append-only et routes create/version/read publiés sur la branche courante.
- [x] **OPPORTUNITY-INGESTION-01 / staging + persistence + scoring** — service BOAMP derrière `PublicNoticeSearchPort`, script `scripts/ingest_boamp_opportunities.py`, migration `0053`, observations fingerprintées, runs/liens append-only, scoring explicable `BOAMP_PUBLIC_V1` et script `scripts/persist_boamp_opportunities.py` publiés. La recette PostgreSQL/BOAMP réelle et la conversion en Case restent ouvertes.
- [x] **OPPORTUNITY-QUALIFICATION-01 / lecture patronale** — lecture tenant-scoped réservée à un `PATRON_ADMIN` actif, décisions fermées `QUALIFIED`/`REJECTED`/`SNOOZED`, motifs compatibles, migration `0054`, qualification append-only, idempotence/outbox et script `scripts/read_qualify_boamp_opportunities.py` publiés. Aucune conversion automatique en Case.
- [ ] **Gate VPS réel**, lorsque l’utilisateur disposera d’un VPS : builder les images digest-pinnées, lancer PostgreSQL/ClamAV/Caddy, exécuter le test EICAR, vérifier HTTPS et `/healthz/ready`, installer les timers systemd, tester la sauvegarde hors VPS, la restauration isolée et la supervision externe.
- [ ] **Raccordement frontend à l’API publiée**, uniquement après réception et vérification d’une URL HTTPS backend réelle ; ne pas fixer `VITE_API_BASE_URL` avant cette preuve.
- [ ] **Rapport opérateur de restauration**, à produire pendant le gate VPS réel avec hashes, échantillon documentaire, contrôle tenant, état outbox, logs, backup hors hôte et preuve de rotation des secrets.

## Slices BOAMP publiés le 23 août 2026

- [x] **HTTP lecture/qualification patronale** — commit `4a189ea` : routes FastAPI tenant-scoped, bearer et acteur résolus serveur, capabilities patronales, DTOs `extra=forbid`, projection minimale et qualification humaine append-only.
- [x] **Notification outbox vers bus externe** — commit `e2526d2` : `ExternalEventBusPort`, adaptateur HTTPS générique opt-in, adapter mémoire de test et worker borné au topic BOAMP de qualification ; aucun `PUBLISHED` sans accusé externe `2xx`, aucun polling Manus et aucun fournisseur inventé.
- [x] **Recette PostgreSQL 0053/0054** — commit `798bbec` : `scripts/recipe_boamp_postgres.py`, validation d’URL, application Alembic optionnelle, contrôle de la révision `20260823_0054`, des tables/triggers append-only et lancement des tests ciblés ; aucune URL/secret dans la sortie.

## Vérifications externes encore ouvertes

- [ ] Exécuter la recette avec PostgreSQL 16 réellement accessible, puis conserver le verdict, les hashes de migration et la preuve des triggers append-only. Le sandbox actuel répond `connection refused` sur `127.0.0.1:5432`.
- [ ] Définir avec le fournisseur réel le contrat de bus, l’URL HTTPS, le mode d’authentification, les garanties de livraison et la stratégie de replay ; injecter ensuite ces paramètres hors Git et exécuter une recette contrôlée. Aucun bus réel n’est configuré dans le dépôt.
- [ ] Rétablir des runners GitHub Actions exécutants avant de considérer une CI distante comme verte ou de fusionner la PR #49/main.

## Frontières explicitement non retenues par les audits

MinIO sans contrat de stockage établi, sharding/Redis/tracing distribué spéculatifs, DAST/Semgrep déjà couvert par Bandit/Trivy, et tests de charge nécessitant un environnement dédié ne sont pas des tâches ouvertes de cette remédiation.
