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
- [ ] **SUBMISSION-SIGNATURE-HTTP-01** — exposer le service de signature électronique déjà présent par des routes patronales authentifiées, avec callback hash-only vérifié, projection minimale, audit, idempotence et séparation stricte d’avec la preuve de dépôt. Le cadrage est dans [`docs/NEXT_BUSINESS_LOT_SUBMISSION_SIGNATURE_HTTP_01.md`](docs/NEXT_BUSINESS_LOT_SUBMISSION_SIGNATURE_HTTP_01.md) ; ne commencer le code qu’après validation réelle de la PR #49.
- [ ] **Gate VPS réel**, lorsque l’utilisateur disposera d’un VPS : builder les images digest-pinnées, lancer PostgreSQL/ClamAV/Caddy, exécuter le test EICAR, vérifier HTTPS et `/healthz/ready`, installer les timers systemd, tester la sauvegarde hors VPS, la restauration isolée et la supervision externe.
- [ ] **Raccordement frontend à l’API publiée**, uniquement après réception et vérification d’une URL HTTPS backend réelle ; ne pas fixer `VITE_API_BASE_URL` avant cette preuve.
- [ ] **Rapport opérateur de restauration**, à produire pendant le gate VPS réel avec hashes, échantillon documentaire, contrôle tenant, état outbox, logs, backup hors hôte et preuve de rotation des secrets.

## Frontières explicitement non retenues par les audits

MinIO sans contrat de stockage établi, sharding/Redis/tracing distribué spéculatifs, DAST/Semgrep déjà couvert par Bandit/Trivy, et tests de charge nécessitant un environnement dédié ne sont pas des tâches ouvertes de cette remédiation.
