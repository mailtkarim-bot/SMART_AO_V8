# SMART_AO V8 — DCE-ADMIT-01 : Contrat d’admission atomique d’un corpus DCE

**Statut :** normatif pour la première commande durable `RegisterDceVersion`.  
**Périmètre :** admission de métadonnées et références de documents déjà pré-stagés ; aucun octet, multipart, upload HTTP, antivirus ou object storage n’est exposé dans ce sous-slice.

## 1. Intention métier

L’admission transforme un corpus DCE déjà disponible dans un stockage interne contrôlé en une `DceVersion` durable, immuable et rattachée à une `Consultation` du même tenant. Une nouvelle version n’écrase jamais un corpus admis. Les rectificatifs relèvent d’une commande distincte de supersession.

> Cette commande ne déclare pas qu’un fichier existe réellement dans un object storage. Elle enregistre des références pré-stagées dont la vérification technique de présence, antivirus et droits de téléchargement appartiendra au futur flux d’upload sécurisé.

## 2. Commande `RegisterDceVersion`

| Élément | Règle |
|---|---|
| Métadonnées durables | `command_id`, `idempotency_key`, `correlation_id` optionnel, `dce_version_id`. |
| Consultation | `consultation_id` et `consultation_revision` obligatoire. La consultation doit exister dans le tenant et porter exactement cette révision. Elle n’est jamais modifiée par la commande. |
| Documents | Au moins un document ; chaque document porte un identifiant, `storage_object_id`, `storage_key`, nom original, media type, taille positive, hash SHA-256 et origine de réception. Les identifiants et hashes sont uniques à l’intérieur du corpus. |
| Corpus hash | SHA-256 hexadécimal minuscule, égal au hash du manifeste canonique des hashes documentaires triés lexicographiquement et séparés par `\n`. Cette règle garantit un corpus déterministe indépendamment de l’ordre du payload. |
| Provenance | Canal, référence optionnelle, URL optionnelle et date de réception obligatoire. Le canal est fermé à `BUYER_PLATFORM`, `EMAIL`, `MANUAL_UPLOAD`, `RECTIFICATION`. |
| États initiaux | `ADMITTED`, `VERIFIED`, `UNCLASSIFIED`, `NOT_READY`, révision `0`. |
| Acteur | Les colonnes créateur/mise à jour proviennent exclusivement du `CommandContext` serveur. |

## 3. Invariants et refus

| Invariant | Effet public / durable |
|---|---|
| Consultation absente, autre tenant ou révision différente | Rejet avant insertion DCE. |
| Corpus hash invalide ou différent du manifeste canonique | Rejet avant insertion. |
| Document absent, identifiant/hash dupliqué, taille non positive ou metadata invalide | Rejet avant insertion. |
| Même `(tenant, consultation, corpus_hash)` | La contrainte PostgreSQL rejette le doublon. Un même idempotency key et même intention rejoue le succès déjà sauvegardé ; une intention différente est refusée. |
| Échec après ajout root/document mais avant commit | Aucun root, document, event, outbox ou receipt ne survit. |

## 4. Atomicité

La transaction du dispatcher contient exactement la `DceVersion`, ses `DceDocument` enfants, le `DomainEvent` `DCE_VERSION_REGISTERED`, l’`OutboxMessage` dérivé et le `CommandReceipt`. Le payload événementiel/outbox ne contient pas de document, `storage_key`, hash ou provenance ; il se limite aux identifiants de tenant, consultation et version.

## 5. Sécurité

La future route HTTP devra exiger bearer, capability `dce.prepare`, policy tenant-scoped et audit des refus avant de déléguer au dispatcher. DCE-ADMIT-01 livre d’abord le noyau transactionnel ; il n’expose aucun endpoint ni upload réel.

## 6. Critères de sortie

Les tests prouvent l’admission réussie, la stabilité du hash malgré l’ordre des documents, le root/documents/event/outbox/receipt dans une transaction unique, le replay idempotent, le refus de révision Consultation périmée, le rejet du corpus incohérent, le doublon fonctionnel et le rollback après erreur contrôlée.
