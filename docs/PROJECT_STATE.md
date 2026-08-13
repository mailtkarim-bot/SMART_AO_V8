# PROJECT_STATE

## Slice courant
`S02` — identité, tenant, sessions et MFA ; `SEC-01`, `S02-A`, `S02-B`, `S02-C` et `S02-D` sont livrés. La prochaine action imposée est le bootstrap atomique de l’entreprise et du premier patron, avant l’onboarding d’un premier client ou toute exposition d’action métier sensible.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | S02-D HTTP : [`7cf3056`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/7cf3056), cookies sécurisés, routes auth et contexte serveur. |
| Migration Alembic | `20260813_0007` est validée : upgrade depuis `base`, downgrade vers `base` et `alembic check` sur PostgreSQL local sont verts. La base locale est volontairement revenue à `base`. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : **134 tests verts**, dont 5 scénarios API S02-D couvrant cookies, CSRF, JWT, refresh et logout. |
| CI | PostgreSQL 16 est exécuté dans CI depuis [`e61cdb7`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/e61cdb7) ; le [workflow GitHub S02-D HTTP](https://github.com/mailtkarim-bot/SMART_AO_V8/actions/runs/31707943005) est vert (lint et 134 tests). |

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
- S02-B livré : migration `20260813_0005`, tables `Identity`, `PasswordCredential`, `TenantMembership` et tokens bootstrap hashés/expirables, avec contraintes de rôles, états, unicités, Argon2id et patron actif unique.
- S02-C livré : migration `20260813_0006`, sessions tenant-scoped révocables, familles refresh rotatives, hashes opaques sans token en clair, consommation conditionnelle anti-réemploi, facteurs TOTP chiffrés et recovery codes hashés consommables une seule fois. Les clés composites empêchent les références inter-tenant et les index partiels imposent un seul patron actif, un seul refresh actif par famille et un seul TOTP actif par identité.
- S02-D transactionnel livré : service sans dépendance HTTP pour login, logout et rotation de refresh ; vérification Argon2id, token opaque généré puis hashé SHA-256, session/famille/premier refresh créés dans une même transaction, réemploi compromettant la famille et révoquant la session, logout idempotent et invalidation après suspension de membership. La migration `20260813_0007` introduit l’expiration absolue des sessions : 8 heures d’inactivité, 24 heures standard et 12 heures pour patron/délégataire.
- S02-D HTTP livré : access token JWT HS256 de 15 minutes sans rôle, tenant ni permission faisant autorité ; refresh token uniquement en cookie `HttpOnly`/`Secure`/`SameSite=Lax`, CSRF double-submit distinct `Secure`/`SameSite=Strict`, routes login/refresh/logout à refus neutre et résolveur de contexte serveur contrôlant JWT, version de session, identité, membership et expiration avant toute action authentifiée.

## Prochaine action unique

Démarrer le bootstrap applicatif atomique : créer tenant + identité patron + credential Argon2id + membership `PATRON_ADMIN` + token bootstrap hashé, puis consommer ce token dans une transaction unique. La réponse ne devra jamais exposer le secret durablement ; les routes d’onboarding seront conçues seulement après cette transaction prouvée par tests.

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
| Persistance identité et membership S02-B | Livrée | Migration `20260813_0005`, contraintes PostgreSQL Identity/Credential/Membership/Bootstrap et 10 tests DB dédiés. |
| Sessions, refresh tokens et MFA | Livrés | `S02-C` : migration `20260813_0006`, contraintes PostgreSQL de session, rotation/réemploi refresh et facteurs TOTP/recovery. |
| Services transactionnels login/logout/refresh | Livrés | `S02-D` : Argon2id, session/famille/refresh atomiques, rotation, détection du réemploi, logout et invalidation après suspension. |
| Expiration absolue de session | Livrée | Migration `20260813_0007` : borne absolue distincte de l’inactivité, non extensible pendant refresh. |
| Interfaces HTTP et contexte authentifié | Livrés | `S02-D` : JWT court sans claims d’autorisation, cookies sécurisés, CSRF, routes login/refresh/logout et contrôle serveur de session/membership/identité. |
| Bootstrap applicatif tenant + patron | À implémenter | Transaction tenant + patron + credential + token bootstrap consommé avant onboarding client. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
