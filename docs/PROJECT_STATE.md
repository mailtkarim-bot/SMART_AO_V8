# PROJECT_STATE

## Slice courant
`S01-C` — domaine pur de `Decision` dans le slice `Case + Consultation/DceVersion + Decision`.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | S01-B domaine pur de Consultation/DceVersion : identité, lots/tranches, corpus immuable, retrait et supersession ; consulter `git log -1` pour le commit courant. |
| Migration Alembic | Aucune migration appliquée. DATA-01 définit les quatre premières migrations à écrire avec les modèles SQLAlchemy, après les roots de domaine purs. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : 26 tests verts. Domain Case, Consultation/DceVersion et frontières d’architecture couverts. |
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

## Prochaine action unique

Commencer `S01-C` : écrire les tests rouges purs de `Decision` (brouillon, contexte figé, Go/Go conditionnel/No-Go, conditions, contexte obsolète et supersession), conformément à DOMAIN-03 et TEST-01.

## Décisions ouvertes

| Sujet | État | Moment de décision |
|---|---|---|
| Mise en œuvre précise SQLAlchemy/Alembic DATA-01 | Prête à coder | Après les domaines purs Case, Consultation/DceVersion et Decision. |
| Authentification réelle et bootstrap du premier patron | Différé | Avant le premier endpoint protégé. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
