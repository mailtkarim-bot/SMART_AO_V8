# SMART_AO V8 — SUBMISSION-SIGNATURE-HTTP-01

## Objet et frontière

Ce contrat expose au patron un suivi de signature électronique associé à un `SubmissionPackage` immuable. Il enregistre une intention de demande et, lorsqu’un canal authentifié fournit un callback, un fait hashé de résultat. `SIGNED` ne signifie ni dépôt sur une plateforme d’achat public, ni accusé de réception, ni attribution.

Le provider et le secret HMAC sont des paramètres runtime. Tant que les deux ne sont pas configurés, le routeur n’est pas monté par le bootstrap. Aucun secret, certificat ou jeton de fournisseur n’est stocké dans le dépôt.

## Surface HTTP

| Méthode | Endpoint | Autorité | Sortie |
|---|---|---|---|
| `POST` | `/api/v1/patron/submission-packages/{submission_package_id}/signatures` | Bearer patron administrateur actif, `submission.signature.write` | Receipt `SUBMISSION_SIGNATURE_REQUESTED`, idempotent. |
| `POST` | `/api/v1/patron/submission-signatures/{signature_id}/callback` | Bearer patron administrateur actif et `X-Signature-Callback: sha256=<hex>` | Receipt `SUBMISSION_SIGNATURE_RECORDED`, idempotent par `delivery_id`. |
| `GET` | `/api/v1/patron/submission-signatures/{signature_id}` | Bearer patron administrateur actif, `submission.signature.read` | Projection minimale de l’état, sans hashes cryptographiques. |

Les corps JSON sont `extra=forbid`. La demande ne permet pas au client de choisir le provider ni la membership signataire : le provider vient de la configuration serveur et la membership est celle de l’acteur authentifié. Le callback utilise `delivery_id` comme `command_id`, `idempotency_key` et `correlation_id` pour qu’un rejeu de livraison ne produise pas une seconde transition.

## Authentification du callback

La signature HMAC-SHA-256 est calculée sur les octets exacts du corps HTTP, avant dispatch applicatif, avec le secret runtime normalisé. Le format accepté est `sha256=` suivi de 64 caractères hexadécimaux minuscules. Un secret de moins de 32 caractères désactive la surface avec `503 SIGNATURE_CALLBACK_UNAVAILABLE`; une signature absente, malformée ou incorrecte produit `401 CALLBACK_UNAUTHENTICATED`.

Cette vérification est un canal générique de test et d’intégration. Elle ne prétend pas fournir une signature électronique qualifiée, une identité juridique du signataire ou une preuve de remise. Ces propriétés nécessitent un adaptateur fournisseur, une validation de certificats et une recette contractuelle séparés.

## Invariants de données

La demande vérifie `tenant_id + submission_package_id`, la version optimiste attendue et le statut du paquet avant de créer une intention append-only. Le callback vérifie `tenant_id + signature_id`, le provider et le `submission_package_id` reçu avant de finaliser une signature `REQUESTED` en `SIGNED` ou `REJECTED`. Une signature finalisée ne peut pas être modifiée par un second callback.

Le reader applique le même tenant et ne retourne que `signature_id`, `submission_package_id`, `case_id`, provider, statut fermé, version attendue, révision et `external_submission: NOT_PERFORMED`. Les champs `provider_reference_hash` et `signature_sha256` restent dans la persistence et ne franchissent jamais la projection HTTP ou frontend.

## Frontière frontend

Le client React peut demander une signature et lire son état. Il ne fabrique pas de callback, ne calcule pas de HMAC, ne contacte pas un provider et n’affiche aucun hash. Le panneau distingue `REQUESTED`, `SIGNED`, `REJECTED`, `NON_DEMANDÉE` et conserve séparément l’état de dépôt externe, toujours `NOT_PERFORMED` dans ce lot.

## Preuves requises

Les tests unitaires/API couvrent les DTOs fermés, l’absence de bearer, l’acteur patron actif, la policy dédiée, le provider serveur, les signatures HMAC valides/invalides, le rejeu par delivery ID, la projection minimale et les erreurs neutres. Les tests PostgreSQL doivent compléter la preuve de transition append-only, de révision optimiste et d’isolation inter-tenant. La recette réelle devra utiliser un provider de test, des secrets hors Git, une vérification TLS/certificats et une preuve de délivrabilité séparée; elle n’est pas réalisée dans le sandbox.
