# NEXT BUSINESS LOT — SUBMISSION-SIGNATURE-HTTP-01

## 1. Décision de séquencement

Le lot suivant le parcours `PRICING-IMPORT-HTTP-PERSISTENCE-01` est `SUBMISSION-SIGNATURE-HTTP-01`. Il complète le bounded context `submission` en exposant par HTTP le service de signature électronique déjà présent dans l’application. Le lot ne simule pas un dépôt électronique, ne contacte aucun fournisseur externe et ne transforme jamais une signature en preuve de dépôt.

> **État d’implémentation — 23 août 2026 :** le backend des trois opérations HTTP est maintenant câblé sur la branche de travail : DTOs fermés, capabilities patronales dédiées, provider résolu au runtime, callback HMAC sur corps brut, delivery idempotente, reader tenant-scoped et montage conditionnel du routeur. Le frontend de suivi patronal et la recette avec un fournisseur réel restent séparés; l’absence de provider ou de secret laisse la surface désactivée et aucun dépôt externe n’est affirmé.

La dépendance fonctionnelle est le `SubmissionPackage` immutable déjà préparé et exportable. La dépendance technique est le service `SubmissionSignatureHandler`, la migration `20260818_0047_submission_signatures` et les commandes fermées `RequestSubmissionSignatureCommand` / `RecordSubmissionSignatureCommand` déjà codées. La sortie attendue est un parcours patronal HTTP testable, idempotent, tenant-scoped et limité à des faits de signature hashés.

> **Frontière absolue :** `SIGNED` signifie uniquement qu’un callback fournisseur hash-only a été enregistré pour un manifest de soumission précis. Il ne signifie ni dépôt externe réussi, ni accusé de réception, ni attribution.

## 2. Périmètre métier

| Inclus | Exclu explicitement |
|---|---|
| Demande patronale de signature d’un paquet immutable. | Intégration réelle à un fournisseur de signature. |
| Callback authentifié et vérifié par provider déclaré. | Réception d’un secret, d’un document signé ou d’une URL fournisseur. |
| Rejeu idempotent et conflit de commande. | Mutation du manifest ou du paquet de soumission. |
| Lecture minimale de l’état de signature. | Dépôt auprès d’une plateforme d’achat public. |
| Audit append-only et outbox sans contenu documentaire. | Passage automatique à `SUBMITTED` ou `PROVEN`. |

Les contrats HTTP ne doivent contenir ni tenant fourni par le client, ni rôle faisant autorité, ni prix, marge, coût, trésorerie, contenu documentaire, storage key, hash de manifest complet ou secret fournisseur. Les deux hashes déjà exigés par la commande callback restent des faits opaques : ils ne doivent pas être renvoyés dans une projection générale.

## 3. API cible

Les chemins proposés sont patronaux et doivent utiliser le runtime bearer existant, la résolution serveur du tenant et `AuditedAuthorizationPolicy`.

| Opération | Endpoint proposé | Résultat public |
|---|---|---|
| Demander une signature | `POST /api/v1/patron/submission-packages/{submission_package_id}/signatures` | Receipt `SUBMISSION_SIGNATURE_REQUESTED`, référence opaque et révision. |
| Enregistrer le callback | `POST /api/v1/patron/submission-signatures/{signature_id}/callback` | Receipt `SUBMISSION_SIGNATURE_RECORDED`, état public `SIGNED` ou `REJECTED` sans hashes. |
| Lire l’état | `GET /api/v1/patron/submission-signatures/{signature_id}` | Provider, état fermé, paquet référencé et révision ; aucune donnée cryptographique. |

La demande de signature doit résoudre côté serveur le paquet, sa version et la membership signataire. Le provider est une valeur fermée ou configurée côté serveur ; le client ne doit pas pouvoir enregistrer un provider arbitraire sans validation de configuration. Le callback doit exiger une preuve d’authenticité du canal choisi avant l’appel du handler applicatif ; si cette preuve n’est pas encore contractualisée, la route reste refusée plutôt que de prétendre qu’un callback est fiable.

## 4. Plan d’implémentation en sept étapes

### Étape 1 — Contrat et capability

Le contrat HTTP, les capabilities patronales `submission.signature.read` et `submission.signature.write`, la classification `SECURITY_RESTRICTED`, les statuts publics et les refus neutres sont implémentés. Aucun collaborateur, webhook généraliste ou contrat financier ne reçoit une donnée de signature.

### Étape 2 — Adaptateur HTTP et bootstrap

Le routeur patronal est créé sans ORM direct, les handlers existants sont injectés via le bootstrap et le dispatcher transactionnel est réutilisé. Le tenant, l’acteur, la membership appelante, la capability, le provider et le secret de callback sont résolus côté serveur/runtime. Le routeur n’est monté que lorsque provider et secret sont configurés.

### Étape 3 — Projection de lecture

Le reader tenant-scoped expose seulement l’état `REQUESTED|SIGNED|REJECTED`, les identifiants de signature/paquet/Case, le provider fermé, la version attendue, la révision et `external_submission: NOT_PERFORMED`. Il n’expose jamais `provider_reference_hash`, `signature_sha256`, storage locator, contenu ou secrets.

### Étape 4 — Authentification du callback

La frontière HMAC est implémentée : secret runtime hors base métier, signature `sha256=` vérifiée sur le corps HTTP brut avant dispatch, longueur minimale du secret et identifiant de livraison réutilisé comme clé d’idempotence. Cette preuve est générique et ne constitue pas l’intégration d’un fournisseur réel; un adaptateur fournisseur et sa recette dédiée restent requis.

### Étape 5 — Tests unitaires, PostgreSQL et API

Les tests unitaires/API couvrent la policy, le tenant résolu serveur, le paquet absent, la version obsolète, le provider incohérent, la double finalisation, le rejeu par delivery ID, le callback mal authentifié, la projection minimale et la non-fuite des hashes. Les tests PostgreSQL append-only et inter-tenant du handler existant restent la preuve d’intégration à compléter dans le passage de validation complète.

### Étape 6 — Contrats OpenAPI et frontend patron

Le backend publie les contrats OpenAPI via les DTOs Pydantic; le panneau TypeScript de suivi patronal reste le prochain incrément frontend. Il ne devra jamais fabriquer la preuve cryptographique ni appeler directement un fournisseur et devra distinguer `REQUESTED`, `SIGNED` et `REJECTED` de l’état de dépôt, qui reste `NOT_PERFORMED` tant qu’un accusé externe vérifiable n’est pas archivé.

### Étape 7 — Validation et publication

Exécuter la suite backend PostgreSQL complète, les tests ciblés, Alembic `upgrade head/check`, Ruff, detect-secrets, tests frontend, build strict, tests d’architecture, export OpenAPI et `git diff --check`. Commiter chaque sous-comportement cohérent, pousser une PR dédiée et ne considérer le lot terminé qu’après une CI réellement exécutée et verte.

## 5. Invariants de sortie

| Invariant | Preuve attendue |
|---|---|
| Tenant résolu serveur | Tests de lecture/écriture inter-tenant et route sans `tenant_id` client. |
| Autorité patronale | Collaborateur refusé par policy auditée avant toute lecture du paquet. |
| Append-only | Update/delete SQL refusés sur l’intention et les preuves ; une seconde finalisation est rejetée. |
| Idempotence | Même commande/callback rejoué sans nouvelle preuve ni nouvel effet métier. |
| Confidentialité | Recherche automatisée d’interdits dans DTOs, receipts, événements, outbox, logs et frontend. |
| Dépôt non simulé | `SIGNED` ne modifie jamais `external_submission: NOT_PERFORMED`. |
| Révision optimiste | Demande liée à la version courante du paquet ; version obsolète refusée. |

## 6. Dépendances et ordre immédiat

Le lot ne doit commencer qu’après résolution de la situation CI de la PR #49 ou, à défaut, après conservation explicite du blocage infrastructurel dans `PROJECT_STATE.md`. La première action de codage sera d’écrire les tests de contrat et d’API pour les trois routes, puis de vérifier si la vérification cryptographique de callback peut être contractualisée sans inventer de fournisseur.

Le gate VPS demeure séparé. Il sera nécessaire pour tester ClamAV réel, HTTPS, rotation des secrets, sauvegarde/restauration et supervision ; il ne doit pas être remplacé par un faux callback local présenté comme une preuve de production.

## 7. Definition of Done

Le lot sera terminé lorsque les trois opérations HTTP sont tenant-scoped, authentifiées, auditées et documentées ; lorsque les callbacks invalides et rejoués sont traités sans double effet ; lorsque les projections et receipts sont minimaux ; lorsque `external_submission` reste `NOT_PERFORMED` ; et lorsque backend, frontend, migrations, linting, secrets, architecture, OpenAPI et CI sont verts.
