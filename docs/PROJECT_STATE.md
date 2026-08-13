# PROJECT_STATE

## Slice courant
`S02` — identité, tenant et premier patron ; la prochaine action imposée est la rédaction de `SEC-01` avant toute route authentifiée.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | S01-K démonstration M1 : [`a95a9e6`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/a95a9e6), avec runner intégré Consultation → DCE v1 → Case → Decision Go → rectificatif. |
| Migration Alembic | `20260813_0004` reste validée : upgrade depuis `base`, downgrade vers `base` et `alembic check` sur PostgreSQL local sont verts. La base locale est volontairement revenue à `base`. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : **90 tests verts**, dont le scénario M1 PostgreSQL complet. |
| CI | PostgreSQL 16 est exécuté dans CI depuis [`e61cdb7`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/e61cdb7) ; le workflow GitHub du 13 août 2026 est vert pour S01-K (lint et 90 tests). |

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
- S01-H livré : ports applicatifs sans dépendance ORM, snapshots de persistance neutres, repositories SQLAlchemy tenant-scoped par root, chargement exclusif des entités internes et update atomique protégé par `aggregate_revision`.
- S01-I livré : dispatcher technique générique, empreinte canonique, replay idempotent, mismatch de clé, rollback avant commit et transaction atomique `root + Domain Event + outbox + receipt` démontrés par `CreateConsultation`.
- S01-J livré : route FastAPI `POST/GET /api/v1/consultations`, contrat public Pydantic, replay HTTP 200, lecture RYOW tenant-scoped et interface HTTP sans ORM ni import d’infrastructure métier.
- S01-K livré : runner de démonstration M1 contre PostgreSQL, prouvant Consultation, DCE v1, Case, Decision Go finalisée, DCE rectificatif v2, DCE historique conservé et marquage Case/Decision à revoir sans suppression.

## Prochaine action unique

Rédiger `SEC-01` : threat model, identité, tenant, RBAC patron/collaborateur, contexte serveur et règles d’audit, avant d’implémenter S02 et toute route authentifiée.

## Décisions ouvertes

| Sujet | État | Moment de décision |
|---|---|---|
| Persistance Case DATA-01 | Livrée | S01-F : migration `20260813_0003`, validée et publiée. |
| Persistance Decision DATA-01 | Livrée | S01-G : migration `20260813_0004`, validée localement et par CI GitHub. |
| Repositories applicatifs du premier slice | Livrés | S01-H : un adapter par root, filtrage tenant, snapshots neutres, révision optimiste et CI GitHub verte. |
| Handlers, dispatcher et outbox transactionnelle | Livrés pour le premier chemin | S01-I : `CreateConsultation` démontre la chaîne complète, validée localement et par CI GitHub ; les commandes suivantes se branchent sur le même dispatcher. |
| Endpoints APP-01 et projections RYOW minimales | Livrés pour Consultation | S01-J : premier chemin HTTP testé et validé par CI GitHub ; l’authentification réelle est encore différée. |
| Démonstration métier M1 de bout en bout | Livrée | S01-K : scénario PostgreSQL vérifié, historique DCE/Case/Decision conservé après rectificatif et CI GitHub verte. |
| Identité, tenant, RBAC et bootstrap patron | À concevoir | `SEC-01` obligatoire avant l’implémentation S02 et toute route authentifiée. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
