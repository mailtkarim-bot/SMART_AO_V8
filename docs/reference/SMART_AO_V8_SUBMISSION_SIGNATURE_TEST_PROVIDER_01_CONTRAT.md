# SMART_AO V8 — SUBMISSION-SIGNATURE-TEST-PROVIDER-01

## Objet

Ce contrat définit un **adaptateur de test local et déterministe** pour le callback HTTP du slice `SUBMISSION-SIGNATURE-HTTP-01`. Il permet aux tests d’intégration de produire un corps JSON fermé et son enveloppe HMAC sans contacter un fournisseur externe, sans envoyer de document et sans fournir une preuve de signature réelle.

L’adaptateur est `SignatureProviderTestAdapter`, situé dans `backend/app/modules/submission/infrastructure/fake_signature_provider.py`. Il ne doit pas être sélectionné par le runtime de production et ne remplace aucun fournisseur de signature électronique qualifié.

## Contrat produit

Pour un `delivery_id`, une `signature_id` et un `submission_package_id`, l’adaptateur produit :

| Élément | Contrat |
|---|---|
| Provider | Identifiant fermé `TEST_PROVIDER` |
| Corps | DTO `RecordSubmissionSignatureCallbackRequest` sérialisé en JSON ; champs strictement limités à `delivery_id`, `submission_package_id`, `provider`, `provider_reference_hash`, `signature_sha256` et `outcome` |
| Outcome | `SIGNED` ou `REJECTED`, validé par le DTO public |
| Hash de référence | SHA-256 déterministe d’un identifiant de test, jamais d’un document réel |
| Hash de signature | SHA-256 déterministe d’un identifiant de test et du résultat, jamais une signature cryptographique qualifiée |
| Authentification callback | `sha256=<HMAC-SHA256(secret, corps brut)>` |
| Secret | Fourni explicitement au constructeur, au moins 32 caractères ; aucun secret n’est écrit dans le dépôt ou les logs |
| Transport | Aucun transport ; l’adaptateur retourne des bytes et un header à remettre à un client de test ou à `TestClient` |
| Idempotence | Le même jeu d’identifiants produit exactement le même corps et le même HMAC ; le `delivery_id` reste la clé d’idempotence du callback HTTP |

Le HMAC est calculé sur les **bytes bruts** retournés, avant tout parsing ou reformatage JSON. Toute modification du corps après calcul doit être rejetée par la vérification du routeur.

## Frontières de sécurité

L’adaptateur ne lit aucun fichier, n’accepte aucune clé de stockage, ne reçoit aucun texte DCE, montant, donnée bancaire, certificat ou credential fournisseur. Il ne simule pas le dépôt dans un portail, ne modifie pas `external_submission`, ne crée pas de certificat et ne transforme pas un statut de test en preuve juridique.

Le callback conserve le contrat patronal existant : le routeur vérifie d’abord le HMAC du corps brut, puis résout l’acteur patron côté serveur. La persistance et l’outbox restent celles du handler de signature ; un rejeu du même `delivery_id` doit être traité par l’idempotence commune et un mismatch doit retourner `409`.

## Preuves locales

Les tests `backend/tests/infrastructure/test_fake_signature_provider.py` démontrent la fermeture du payload, la déterminisme, la longueur minimale du secret, la compatibilité avec `_verify_callback_signature` et le rejet d’un corps brut altéré. Ils ne constituent pas une recette réseau, une validation de certificat, une preuve de remise ou une qualification réglementaire.

## Activation et exploitation

Aucune variable d’environnement nouvelle n’est introduite. Le provider de test n’est pas branché dans le bootstrap de production et aucun appel sortant n’est ajouté. Une recette future peut l’utiliser seulement dans un environnement de test isolé avec un secret éphémère fourni hors Git ; elle doit vérifier le replay, le tenant, les logs minimisés et la conservation de `external_submission: NOT_PERFORMED`.

## Critère de sortie

Le slice est accepté lorsque les tests ciblés, Ruff, la détection de secrets et les tests HTTP signature existants passent, sans réseau réel. La validation d’un fournisseur externe réel reste un lot séparé, dépendant d’un contrat fournisseur signé, de credentials hors dépôt, d’une URL HTTPS et d’une preuve d’accusé réellement reçue.
