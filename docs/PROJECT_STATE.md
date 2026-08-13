# PROJECT_STATE

## Slice courant
`S02` — identité, tenant, sessions, MFA, bootstrap patron, policy contextualisée, audit append-only et premières routes métier authentifiées ; les fondations SEC-01, les lectures Consultation/DCE, l’admission atomique, le staging, l’upload et la rétention physique DCE sont livrés. La prochaine action est DCE-DOCUMENT-EXTRACTION-01 : registre et extraction déterministe des contenus après admission, sans exposer les originaux.

## Dernier état vert

| Élément | État |
|---|---|
| Commit | DCE-RETENTION-01 publié sur `main` : [`576abcb`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/576abcb), contrat, migration `0012`, worker d’outbox, balayage d’orphelins, retry durable et tests. |
| Migration Alembic | `20260813_0012` validée : upgrade depuis `base`, `alembic check` sans écart puis downgrade vers `base` sur PostgreSQL local. La base locale est volontairement revenue à `base`. |
| Tests | `ruff check` vert ; `pytest backend/tests -q` : **197 tests verts**, dont effacement idempotent, absence de fichier, retry/backoff, protection CLEAN et récupération d’orphelin `UPLOADING`. |
| CI | PostgreSQL 16 est exécuté dans CI depuis [`e61cdb7`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/e61cdb7) ; le [workflow DCE-RETENTION-01](https://github.com/mailtkarim-bot/SMART_AO_V8/actions/runs/31729224213) est vert (lint et smoke tests). Docker n’est pas disponible dans le sandbox : le démarrage réel du worker, la syntaxe Compose et l’exécution contre ClamAV restent à vérifier sur le VPS/Docker cible. |

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
- Bootstrap patron livré : provisionnement local de tenant `ACTIVE` et secret d’amorçage aléatoire uniquement hashé avec expiration d’une heure ; complétion créant dans une transaction unique l’identité patron, son credential Argon2id, sa membership `PATRON_ADMIN ACTIVE` et la consommation définitive du secret. Réemploi, expiration, cross-tenant, slug dupliqué et échec de hash n’exposent aucune création partielle.
- RBAC/ABAC/ReBAC livré : catalogue fermé de capabilities calculées seulement depuis les faits serveur ; policy tenant/classification/MFA/affectation renforcée ; migration `20260813_0008` créant les affectations collaborateur `Case` avec FKs composites tenant-scoped, scope JSONB actions/classifications, dates et unicité de l’affectation active. Le résolveur de contexte authentifié ne lit aucun rôle dans le JWT et injecte seulement les capabilities de la membership et les scopes actifs, filtrés et valides de la base.
- Audit de sécurité append-only livré : migration `20260813_0009`, vocabulaire d’événements fermé, métadonnées applicatives allow-listées et pseudonymisées, trigger PostgreSQL interdisant `UPDATE` et `DELETE`, writer transactionnel et décorateurs pour login/refresh/logout ainsi que refus de policy. Les tokens, mots de passe, hash Argon2id, cookies, contenu DCE et montants sont refusés par conception du port d’audit.
- Routes Consultation authentifiées livrées : `POST` et `GET` n’existent dans l’application composée qu’avec un runtime d’authentification réel. Elles résolvent le bearer en `ActorContext`, adaptent ce contexte serveur en `CommandContext` seulement après capability/policy, conservent l’idempotence et retournent `404 NOT_FOUND_OR_FORBIDDEN` pour une Consultation hors tenant. Le refus est journalisé par la policy auditée.
- DCE-READ-01 livré : contrat normatif dans `docs/reference/SMART_AO_V8_DCE_READ_01_CONTRAT.md` et route `GET /api/v1/dce-versions/{id}`. La réponse expose seulement les métadonnées de version autorisées (cycle de vie, intégrité, readiness, dates et références), jamais les documents, stockage, hashes, provenance ni extraits. `dce.prepare`, tenant, policy et audit sont contrôlés côté serveur ; un collaborateur sans `Case` affectée est refusé.
- DCE-ADMIT-01 livré : contrat normatif dans `docs/reference/SMART_AO_V8_DCE_ADMIT_01_CONTRAT.md`, commande `RegisterDceVersionCommand` et handler transactionnel. L’admission valide la Consultation et sa révision, l’unicité des IDs et hashes documentaires, ainsi que le `corpus_hash` SHA-256 du manifeste trié, séparé par un caractère LF réel et non par les deux caractères littéraux `\\` et `n`. La transaction écrit dans l’ordre la racine `DceVersion`, les documents, l’événement, l’outbox et le receipt idempotent ; le replay par le même tenant/acteur/commande ne crée aucun doublon.
- DCE-ADMIT-HTTP-01 livré : contrat normatif dans `docs/reference/SMART_AO_V8_DCE_ADMIT_HTTP_01_CONTRAT.md` et route `POST /api/v1/dce-versions`. Le bearer est résolu uniquement côté serveur, puis `dce.prepare` et la policy auditée sont appliqués à la Consultation propriétaire avant le dispatcher. Un patron admis reçoit seulement le receipt autorisé ; le replay renvoie `200` sans doublon, un collaborateur sans scope reçoit `403` audité et un autre tenant reçoit `404 NOT_FOUND_OR_FORBIDDEN` audité. Aucun hash, document, provenance, `storage_object_id` ou `storage_key` n’est retourné.
- DCE-STAGING-01 livré : contrat normatif dans `docs/reference/SMART_AO_V8_DCE_STAGING_01_CONTRAT.md`, modèle `DceStagedObject`, migration `20260813_0010`, transitions PostgreSQL et registre tenant-scopé de quarantaine. `POST /api/v1/dce-staged-objects` prépare une intention autorisée par bearer, `dce.prepare` et policy auditée, avec identifiant opaque alloué par le serveur ; aucune clé, URL, hash ou métadonnée de scanner n’est renvoyée. Les commandes système de scan et de rétention sont fail-closed ; l’admission lit seulement les objets `CLEAN`, les verrouille puis les marque `CONSUMED` avec la `DceVersion` dans la transaction atomique. La FK composite interdit tout document DCE sans objet staged du même tenant.
- DCE-UPLOAD-01 livré : contrat normatif dans `docs/reference/SMART_AO_V8_DCE_UPLOAD_01_CONTRAT.md`, migration `20260813_0011` ajoutant l’état `UPLOADING` et les transitions PostgreSQL `AWAITING_UPLOAD → UPLOADING → QUARANTINED → CLEAN|REJECTED`. `PUT /api/v1/dce-staged-objects/{id}/content` exige un bearer, `dce.prepare`, une policy auditée et une clé d’idempotence ; il accepte uniquement un flux brut, sans JSON/multipart. Le service écrit par chunks dans une quarantaine privée, calcule SHA-256 et taille réels, détecte le MIME par signature libmagic, soumet le contenu à ClamAV `INSTREAM` interne puis enregistre `CLEAN` ou `REJECTED` fail-closed. Les réponses n’exposent aucune clé, URL, hash, MIME ou signature scanner. Docker Compose prévoit `clamav/clamav:1.4_base` sans publication du port `3310`; son exécution réelle reste à vérifier sur un hôte Docker car le sandbox n’a pas Docker.
- DCE-RETENTION-01 livré : contrat normatif dans `docs/reference/SMART_AO_V8_DCE_RETENTION_01_CONTRAT.md`, migration `20260813_0012` et worker Docker sans port public. Le worker balaie les objets non consommés arrivés à expiration, les fait passer de façon transactionnelle à `EXPIRED`, puis consomme `dce_staging_retention` avec `FOR UPDATE SKIP LOCKED`. Il efface seulement les binaires des objets relus `REJECTED` ou `EXPIRED`; `CLEAN` et `CONSUMED` sont bloqués par conception. `FileNotFound` est un succès idempotent, une erreur passe l’outbox en `RETRY` avec backoff borné et `last_error_code` fermé. Le worker partage uniquement PostgreSQL et le volume privé de quarantaine.

## Prochaine action unique

Démarrer DCE-DOCUMENT-EXTRACTION-01 : figer le registre immuable d’extractions documentaires après admission, les adaptateurs déterministes PDF/DOCX/XLSX/images, la provenance page/fragment et les limites anti-bombes. Les originaux restent privés ; seules des projections minimisées et sourcées pourront alimenter l’analyse DCE future.

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
| Bootstrap applicatif tenant + patron | Livré | Service local atomique : tenant + identité + credential Argon2id + membership patron + token consommé, sans secret persistant. |
| Policy RBAC/ABAC/ReBAC et première affectation | Livré | Catalogue de capabilities calculé côté serveur, policy classification/scope et table `case_assignments` tenant-scoped injectée dans le contexte authentifié. |
| Audit de sécurité append-only | Livré | Migration `20260813_0009`, vocabulaire fermé, métadonnées minimisées, trigger append-only et instrumentation auth/policy. |
| Routes Consultation authentifiées | Livrées | Bearer résolu côté serveur, capability `consultation.create/read`, policy auditée, isolation tenant et réemploi idempotent préservés. |
| Lecture DCE sécurisée | Livrée | DCE-READ-01 : route tenant-scoped, `dce.prepare`, réponse de métadonnées minimale et refus audités. |
| Admission durable DceVersion | Livrée | DCE-ADMIT-01 : contrat, commande, handler transactionnel, manifeste SHA-256 canonique avec séparateur LF réel, persistence racine/documents/événement/outbox/receipt et replay idempotent démontrés par 4 tests DB. |
| Admission DCE par HTTP sécurisée | Livrée | DCE-ADMIT-HTTP-01 : `POST /api/v1/dce-versions`, bearer réel, `dce.prepare`, policy auditée sur Consultation, isolation tenant, receipt minimal et replay HTTP contrôlé. |
| Registre de staging sécurisé DCE | Livré | DCE-STAGING-01 : migration `0010`, objets tenant-scopés, clé privée générée serveur, états/quarantaine/scan/rétention, transitions PostgreSQL, préparation HTTP auditée et consommation atomique par admission. |
| Upload binaire sécurisé DCE | Livré localement | DCE-UPLOAD-01 : migration `0011`, flux privé chunké, limite effective, hash réel, libmagic, client ClamAV `INSTREAM`, contrôles fail-closed, endpoint bearer/policy/audit et Compose ClamAV non exposé. Le test Docker réel reste requis sur VPS, car le sandbox ne possède pas Docker. |
| Rétention physique DCE | Livrée localement | DCE-RETENTION-01 : migration `0012`, worker d’outbox idempotent sans port, `SKIP LOCKED`, expiration d’orphelins, suppression seulement `REJECTED`/`EXPIRED`, retry/backoff et code d’erreur durable. Le test Docker réel reste requis sur VPS. |
| Installation React/Vite complète | Différée | Après les premiers endpoints/read models du slice. |
| API Manus, retrieval et agents | Différés | Slice analyse DCE/cognitive. |

## Risques bloquants

Aucun risque métier bloquant identifié. Les risques techniques sont traités par petits incréments, tests et CI.
