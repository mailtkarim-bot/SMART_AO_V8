# PROJECT_STATE

## Slice courant
`S01-D` — fondation de persistance du premier slice : socle tenant, revisions, événements et outbox avant les repositories Case/DCE/Decision.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | S01-C domaine pur de Decision : contexte figé, Go/Go conditionnel/No-Go, conditions, stale context et supersession ; consulter `git log -1` pour le commit courant. |
| Migration Alembic | Aucune migration appliquée. DATA-01 peut désormais être implémenté : le socle tenant/revisions/events/outbox précède les repositories. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : 39 tests verts. Les trois roots du premier slice et leurs frontières d’architecture sont couverts. |
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

## Prochaine action unique

Commencer `S01-D` : écrire les tests rouges de persistance du socle tenant/revision/domain events/outbox, puis implémenter la première migration Alembic DATA-01 sans repository cross-root.

## Décisions ouvertes

| Sujet | État | Moment de décision |
|---|---|---|
| Mise en œuvre précise SQLAlchemy/Alembic DATA-01 | À implémenter | S01-D, maintenant que les trois domaines purs sont verts. |
| Authentification réelle et bootstrap du premier patron | Différé | Avant le premier endpoint protégé. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
