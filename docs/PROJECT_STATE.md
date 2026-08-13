# PROJECT_STATE

## Slice courant
`S01-E` — persistance tenant-scoped de `Consultation` et `DceVersion`, deuxième migration DATA-01, avant les repositories Case et Decision.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | S01-D socle de durabilité : tenant, receipts d’idempotence, Domain Events, outbox, Process Inbox et migration Alembic 0001 ; consulter `git log -1` pour le commit courant. |
| Migration Alembic | `20260813_0001` validée : upgrade, downgrade et `alembic check` sur PostgreSQL local sont verts. La base locale est volontairement revenue à `base`. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : 45 tests verts, dont 6 scénarios PostgreSQL du socle durable. |
| CI | Workflow backend configuré et publié ; son exécution GitHub doit être surveillée à chaque push. |

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

## Prochaine action unique

Commencer `S01-E` : écrire les tests rouges PostgreSQL de `Consultation` et `DceVersion`, puis implémenter la migration `20260813_0002_consultation_dce` et leurs modèles SQLAlchemy sans relation mutable vers Case ou Decision.

## Décisions ouvertes

| Sujet | État | Moment de décision |
|---|---|---|
| Persistance Consultation/DceVersion DATA-01 | À implémenter | S01-E : migration `20260813_0002` après validation S01-D. |
| Persistance Case et Decision DATA-01 | Différée | Après S01-E, par migrations séparées `0003` puis `0004`. |
| Authentification réelle et bootstrap du premier patron | Différé | Avant le premier endpoint protégé. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
