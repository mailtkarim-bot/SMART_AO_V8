# PROJECT_STATE

## Slice courant
`S01-A` — domaine pur de `Case` dans le slice `Case + Consultation/DceVersion + Decision`.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | `ce76712` — socle V8, contrats de référence et nettoyage des artefacts Python publiés sur `main`. |
| Migration Alembic | Aucune migration appliquée. DATA-01 définit les quatre premières migrations à écrire avec les modèles SQLAlchemy. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : 2 tests verts. La suite métier est à écrire selon TEST-01. |
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

## Prochaine action unique

Écrire les premiers tests rouges de domaine de `Case` (`CASE-INV-01` à `CASE-INV-04`) avant toute persistance, conformément à DOMAIN-03 et TEST-01.

## Décisions ouvertes

| Sujet | État | Moment de décision |
|---|---|---|
| Mise en œuvre précise SQLAlchemy/Alembic DATA-01 | Prête à coder | Après les tests domaine Case verts. |
| Authentification réelle et bootstrap du premier patron | Différé | Avant le premier endpoint protégé. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
