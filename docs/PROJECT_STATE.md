# PROJECT_STATE

## Slice courant
`S01-H` — repositories applicatifs tenant-scoped de Case, Consultation, DceVersion et Decision, avant les handlers de commandes et l’outbox transactionnelle.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | S01-G persistance Decision : migration `20260813_0004`, contextes fingerprintés immuables, conditions et supersession tenant-scoped ; consulter `git log -1` pour le commit courant. |
| Migration Alembic | `20260813_0004` validée : upgrade depuis `base`, downgrade vers `base` et `alembic check` sur PostgreSQL local sont verts. La base locale est volontairement revenue à `base`. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : **67 tests verts**, dont 8 scénarios PostgreSQL Decision. |
| CI | PostgreSQL 16 ajouté au workflow par [`e61cdb7`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/e61cdb7) ; le workflow GitHub du 13 août 2026 est vert (lint et 59 tests). |

## Ce qui est terminé

- Vision métier, interfaces patron/collaborateur et règles de confidentialité documentées.
- DOMAIN-01 : ownership, transactions, événements, outbox et cohérence.
- DOMAIN-03 : machines d'état et invariants du premier slice.
- APP-01 : contrats Pydantic des commandes, réponses et erreurs.
- TEST-01 : plan pytest de domaine, DB, sécurité, architecture et concurrence.
- DATA-01 : mapping SQLAlchemy/Alembic attendu.
- ARC-01 : arborescence modulaire et règles d'import.
- Dépôt GitHub privé créé et premier commit publié sur `main`; contrats importés dans `docs/reference/`.
- ROADMAP-01 ajoutée : ordre global des slices jusqu’à la préproduction VPS.
- Documentation consolidée : PDF classés dans `docs/pdf/`, sources Markdown V8 importées dans `docs/reference/` et navigation centralisée dans `DOCUMENTATION_CATALOG.md`.
- S01-A livré : aggregate `Case` pur, `CaseScope`, origine manuelle justifiée, références tenant-scoped, événements minimaux et tests `CASE-01` à `CASE-04`/ownership.
- S01-B livré : aggregates purs `Consultation` et `DceVersion`, identité acheteur, lots/tranches source, corpus et documents immuables, manques sourcés, retrait, supersession et tests de frontière.
- S01-C livré : aggregate pur `Decision`, contextes fingerprintés, finalisation patron, Go/Go conditionnel/No-Go, conditions, stale context, revue requise, supersession et tests de frontière.
- S01-D livré : base SQLAlchemy, tenant minimal, receipts idempotents, Domain Events, outbox, Process Inbox, migration `20260813_0001`, contraintes PostgreSQL et rollback transactionnel prouvés.
- S01-E livré : modèles et migration `20260813_0002` Consultation/DceVersion, lots/tranches/documents/ancres source, FKs composites tenant-scoped, unicités de corpus et triggers d’immutabilité PostgreSQL.
- S01-F livré : modèles et migration `20260813_0003` Case, références tenant-scoped Consultation/DCE, unicité de l’identité fonctionnelle active, historiques internes et absence d’ownership mutable vers Decision, Pricing, Task ou Submission.
- S01-G livré : modèles et migration `20260813_0004` Decision, FKs composites tenant-scoped vers Case et contextes internes, finalisation contrôlée, cycle de supersession, conditions et trigger d’immutabilité des contextes figés.

## Prochaine action unique

Commencer `S01-H` : définir les ports applicatifs et implémenter les repositories SQLAlchemy tenant-scoped de Case, Consultation, DceVersion et Decision, avec chargement exclusif de leurs entités internes et garde de révision optimiste.

## Décisions ouvertes

| Sujet | État | Moment de décision |
|---|---|---|
| Persistance Case DATA-01 | Livrée | S01-F : migration `20260813_0003`, validée et publiée. |
| Persistance Decision DATA-01 | Livrée | S01-G : migration `20260813_0004`, validée localement avant publication. |
| Repositories applicatifs du premier slice | À implémenter | S01-H : un repository par root, filtrage tenant et révision optimiste. |
| Authentification réelle et bootstrap du premier patron | Différé | Avant le premier endpoint protégé. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
