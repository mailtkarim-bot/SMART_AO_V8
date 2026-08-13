# PROJECT_STATE

## Slice courant
`S02` — identité, tenant et premier patron ; `SEC-01` et `S02-A` sont livrés. La prochaine action imposée est `S02-B` : persistance Identity, PasswordCredential, TenantMembership et bootstrap patron, avant toute session ou route authentifiée.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | SEC-01 : [`fdf6cc1`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/fdf6cc1), contrat normatif identité, tenant, RBAC/ABAC, sessions et audit. |
| Migration Alembic | `20260813_0004` reste validée : upgrade depuis `base`, downgrade vers `base` et `alembic check` sur PostgreSQL local sont verts. La base locale est volontairement revenue à `base`. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : **90 tests verts**, dont le scénario M1 PostgreSQL complet. SEC-01 est documentaire et n’ajoute pas encore de migration ni de test Python. |
| CI | PostgreSQL 16 est exécuté dans CI depuis [`e61cdb7`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/e61cdb7) ; le workflow GitHub du 13 août 2026 est vert pour SEC-01 (lint et smoke tests). |

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
- SEC-01 livré : contrat normatif de sécurité préalable à S02, avec modèle de menace, séparation tenant, identité, sessions, MFA, RBAC/ABAC contextuel, audit append-only, secrets et tests de sécurité.
- S02-A livré : `ActorContext` immuable, classification de données, port de policy, policy baseline par défaut refusante, exigence MFA récente, mapping HTTP neutre et tests de frontière sans ORM/framework.

## Prochaine action unique

Démarrer `S02-B` : écrire les tests PostgreSQL rouges pour `Identity`, `PasswordCredential`, `TenantMembership` et le bootstrap patron à usage unique ; créer ensuite la migration et les modèles sans session navigateur ni route authentifiée.

## Décisions ouvertes

| Sujet | État | Moment de décision |
|---|---|---|
| Persistance Case DATA-01 | Livrée | S01-F : migration `20260813_0003`, validée et publiée. |
| Persistance Decision DATA-01 | Livrée | S01-G : migration `20260813_0004`, validée localement et par CI GitHub. |
| Repositories applicatifs du premier slice | Livrés | S01-H : un adapter par root, filtrage tenant, snapshots neutres, révision optimiste et CI GitHub verte. |
| Handlers, dispatcher et outbox transactionnelle | Livrés pour le premier chemin | S01-I : `CreateConsultation` démontre la chaîne complète, validée localement et par CI GitHub ; les commandes suivantes se branchent sur le même dispatcher. |
| Endpoints APP-01 et projections RYOW minimales | Livrés pour Consultation | S01-J : premier chemin HTTP testé et validé par CI GitHub ; l’authentification réelle est encore différée. |
| Démonstration métier M1 de bout en bout | Livrée | S01-K : scénario PostgreSQL vérifié, historique DCE/Case/Decision conservé après rectificatif et CI GitHub verte. |
| SEC-01 : sécurité, identité, tenant, RBAC et audit | Livré | Contrat normatif validé dans `docs/reference/SMART_AO_V8_SEC_01_CONTRAT_SECURITE_IDENTITE_TENANT_AUDIT.md`. |
| Contrats de contexte et policy S02-A | Livrés | `ActorContext`, `AuthorizationPolicyPort`, policy baseline et erreurs HTTP neutres validés par 10 nouveaux tests. |
| Identité, tenant, RBAC et bootstrap patron | À implémenter | `S02-B` : modèles/migration `Identity`, `PasswordCredential`, `TenantMembership` et bootstrap patron avant les sessions. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
