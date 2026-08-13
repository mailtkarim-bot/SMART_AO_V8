# PROJECT_STATE

## Slice courant
`S01-G` — persistance tenant-scoped et historique non destructif de `Decision`, quatrième migration DATA-01, avant les repositories applicatifs.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | S01-F persistance Case : [`edab4a2`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/edab4a2), avec migration `20260813_0003`, Case tenant-scoped et historiques Consultation/DCE. |
| Migration Alembic | `20260813_0003` validée : upgrade depuis `base`, downgrade vers `base` et `alembic check` sur PostgreSQL local sont verts. La base locale est volontairement revenue à `base`. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : **59 tests verts**, dont 7 scénarios PostgreSQL Case. |
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

## Prochaine action unique

Commencer `S01-G` : écrire les tests rouges PostgreSQL de `Decision`, puis implémenter la migration `20260813_0004_decision` et ses contextes fingerprintés, conditions et supersessions, sans FK mutable vers Case, Pricing ou Submission.

## Décisions ouvertes

| Sujet | État | Moment de décision |
|---|---|---|
| Persistance Case DATA-01 | Livrée | S01-F : migration `20260813_0003`, validée et publiée. |
| Persistance Decision DATA-01 | À implémenter | S01-G : migration séparée `20260813_0004` après validation de S01-F. |
| Authentification réelle et bootstrap du premier patron | Différé | Avant le premier endpoint protégé. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
