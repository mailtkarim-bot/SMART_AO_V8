# SMART_AO V8 — DCE-STAGING-01 : Contrat de staging sécurisé des pièces DCE

**Statut :** normatif.  
**Périmètre :** registre durable, tenant-scopé et contrôlé des objets documentaires avant leur admission dans une `DceVersion`.  
**Dépendances :** SEC-01, DCE-ADMIT-01 et DCE-ADMIT-HTTP-01.

## 1. Intention métier et frontière

Avant d’être intégrée à un DCE, une pièce reçue d’une plateforme acheteur, d’un email ou d’un import manuel doit être isolée, contrôlée puis identifiée de manière traçable. Le staging garantit que l’admission ne référence jamais une clé librement fournie par un navigateur ou une pièce non contrôlée.

> Un objet en staging n’est pas encore une pièce DCE. Il devient seulement **consommable** par une admission lorsque son contenu a été écrit en quarantaine, contrôlé par le scanner, identifié par son type réel et marqué `CLEAN` par un composant de confiance.

DCE-STAGING-01 livre le **plan de contrôle durable**, son intégration transactionnelle à l’admission et l’intention HTTP authentifiée de staging. L’entrée binaire HTTP, l’adaptateur MinIO/S3 effectif et le worker ClamAV sont explicitement différés dans DCE-UPLOAD-01 : aucune API publique ne peut déclarer elle-même qu’un contenu est propre.

## 2. Objet durable `DceStagedObject`

| Attribut | Règle |
|---|---|
| Identité | `storage_object_id` UUID généré par le serveur ; jamais choisi par le client. |
| Isolation | `tenant_id` obligatoire, FK vers le tenant et FK composite vers la `Consultation` propriétaire. Aucun objet ne traverse un tenant. |
| Rattachement | `consultation_id` obligatoire dès la demande de staging. L’objet ne peut être consommé que dans une `DceVersion` de cette même consultation. |
| Clé de stockage | `storage_key` privée, générée par l’adaptateur serveur sous un préfixe tenant-scopé. Elle n’est ni acceptée ni renvoyée par une route HTTP. |
| Métadonnées fiables | nom original, taille, SHA-256 et media type réel sont renseignés par le flux de confiance après écriture ; jamais réputés vrais sur seule déclaration navigateur. |
| Scan | état, moteur, version de signatures, date et résultat. Une erreur de scanner est bloquante. |
| Consommation | `consumed_by_dce_version_id` et `consumed_at` sont établis dans la même transaction que l’admission, puis ne peuvent plus être modifiés. |
| Rétention | expiration obligatoire. Un objet non consommé devient inutilisable à expiration ; le contenu physique doit être effacé par le futur worker, tout en conservant seulement les traces de sécurité minimales. |

## 3. Machine d’état

| État | Signification | Transitions autorisées | Peut être admis dans un DCE ? |
|---|---|---|---|
| `AWAITING_UPLOAD` | Intention de staging créée ; aucun contenu fiable n’est disponible. | `QUARANTINED`, `EXPIRED` | Non |
| `QUARANTINED` | Contenu écrit dans l’espace isolé ; scan ou contrôle technique en attente. | `CLEAN`, `REJECTED`, `EXPIRED` | Non |
| `CLEAN` | Type réel, taille, hash et scan antivirus ont été validés par un composant de confiance. | `CONSUMED`, `EXPIRED` | Oui, une seule fois |
| `REJECTED` | Fichier infecté, type interdit, taille incohérente, hash incohérent ou scan en erreur. | `EXPIRED` | Non |
| `CONSUMED` | Référence définitivement liée à une `DceVersion`. | Aucune | Non, déjà consommé |
| `EXPIRED` | Objet jamais admis hors délai de rétention. | Aucune | Non |

Les transitions non listées sont des refus. Une erreur ClamAV, une signature de scan indisponible ou un résultat inconnu produit `REJECTED` : le système est **fail-closed**.

## 4. Contrôles de contenu et de stockage

| Contrôle | Exigence normative |
|---|---|
| Chemin | Le backend dérive la clé à partir du tenant et de `storage_object_id`. Toute clé fournie par HTTP est rejetée ou ignorée ; elle ne devient jamais une vérité serveur. |
| Chiffrement et réseau | Stockage chiffré au repos selon l’environnement ; échanges serveur-stockage et serveur-scanner authentifiés et chiffrés. |
| Taille | Limite initiale de **2 000 000 000 octets** par objet, cohérente avec DCE-ADMIT-01. La limite est contrôlée pendant l’écriture, pas seulement après réception. |
| Hash | SHA-256 calculé sur les octets effectivement reçus, jamais accepté comme preuve depuis le navigateur. |
| Type | Le type MIME réel provient de l’inspection de signature (« magic bytes »). Le `Content-Type` et le suffixe sont seulement des indices enregistrables. |
| Formats | La allow-list de production est configurée côté serveur. Les archives, exécutables, macros actives et formats non prévus doivent être placés en quarantaine ou rejetés jusqu’à l’existence d’un parcours spécifique. |
| Antivirus | Le scanner fournit un verdict `CLEAN`, `INFECTED` ou `ERROR`, ainsi que moteur, signatures et horodatage. `INFECTED` et `ERROR` ne créent jamais un objet consommable. |
| Journalisation | Aucun octet, hash de document, clé de stockage, nom de fichier complet ni URI de backend n’est écrit dans le journal de sécurité. Les logs opérationnels sont minimisés et pseudonymisés. |

## 5. Autorisation

La création d’une intention de staging est autorisée sur la `Consultation` propriétaire par la capability `dce.prepare`, la policy tenant-scopée et l’audit append-only de SEC-01. Le `ActorContext` serveur seul crée la provenance acteur. La capacité `system.job.execute` est nécessaire au composant interne qui enregistre un verdict de scan ; aucune route web d’utilisateur ne porte cette capacité.

Un collaborateur n’est admis que si ses facts serveur confirment simultanément la capability, une affectation `Case` valable, l’action et la classification autorisées. Sans scope de `Case`, le refus est `403` audité. Un tenant tiers reçoit `404 NOT_FOUND_OR_FORBIDDEN` audité.

## 6. Frontière HTTP de préparation

| Élément | Règle |
|---|---|
| Méthode et URL | `POST /api/v1/dce-staged-objects` |
| Authentification | Bearer résolu côté serveur ; tenant, acteur, rôle et capability sont absents du body. |
| Autorisation | `dce.prepare` et policy auditée sur la `Consultation` propriétaire. Un tenant tiers reçoit `404 NOT_FOUND_OR_FORBIDDEN` audité ; un collaborateur sans scope reçoit `403` audité. |
| Requête | `command_id`, `idempotency_key`, `consultation_id`, révision attendue, nom déclaré, taille attendue, canal et expiration. `storage_object_id`, `storage_key`, hash et type MIME sont interdits dans le payload. |
| Allocation | Le serveur dérive un `storage_object_id` opaque et stable pour un même tenant, acteur et idempotency key. Il dérive aussi la clé privée ; cette clé reste interne. |
| Succès | `201` à la première préparation, `200` au replay strict. La réponse expose uniquement l’identifiant d’objet, `AWAITING_UPLOAD` et l’expiration ; jamais la clé ou une URL de backend. |

## 7. Contrats de commandes

| Commande | Appelant | Préconditions | Effet durable |
|---|---|---|---|
| `PrepareDceStagingCommand` | Utilisateur autorisé | Consultation existante, révision attendue, nom déclaré et taille attendue dans les limites. | Crée un objet `AWAITING_UPLOAD`, une clé privée serveur et une expiration. La réponse ne contient pas la clé. |
| `RecordDceStagedObjectScanCommand` | Système de confiance | Objet dans `QUARANTINED`, résultat de scan complet, hash/taille/type réel. | Fige le verdict : `CLEAN` ou `REJECTED`. Aucun fait de scan ne vient du navigateur. |
| `ExpireDceStagedObjectCommand` | Système de rétention | Objet non consommé et date d’expiration atteinte. | Marque `EXPIRED`; l’effacement physique est un effet de bord outbox idempotent. |
| `RegisterDceVersionCommand` étendue | Utilisateur autorisé | Tous les `storage_object_id` sont `CLEAN`, non expirés, non consommés et liés à la consultation du même tenant. | Crée la version DCE et ses documents ; consomme chaque objet dans la même transaction. |

## 8. Adaptateurs techniques requis

Le domaine ne dépend ni de MinIO, ni de S3, ni de ClamAV. Les ports suivants sont nécessaires :

| Port | Responsabilité |
|---|---|
| `DceQuarantineStoragePort` | Allouer la clé privée, recevoir un flux sous limite, calculer le hash, déplacer ou supprimer un objet. |
| `DceContentInspectionPort` | Produire le type réel et les informations de sûreté de format à partir des octets. |
| `DceMalwareScanPort` | Scanner le contenu et fournir un verdict vérifiable, moteur, signatures et date. |
| `DceStagingRetentionPort` | Réaliser l’effacement physique demandé par l’outbox, de manière idempotente. |

La V8 de production visée est un monolithe modulaire avec PostgreSQL, object storage privé et scanner local sur le VPS dédié. Les ports permettent des doublures déterministes de test et empêchent les SDK de stockage d’entrer dans les routes, commandes ou aggregates métier.

## 9. Intégration obligatoire à DCE-ADMIT

À partir de DCE-STAGING-01, le payload HTTP d’admission ne doit plus contenir `storage_key`, taille, hash ou media type comme faits d’autorité. Il référence des `storage_object_id` propres ; le handler lit les métadonnées contrôlées du registre tenant-scopé, crée les `DceDocument` immuables et marque les objets `CONSUMED` dans la transaction du dispatcher.

Tout objet absent, hors tenant, rattaché à une autre consultation, non `CLEAN`, expiré ou déjà consommé entraîne un rejet complet sans `DceVersion`, document, événement, outbox ni receipt durable.

## 10. Réponse et confidentialité

Les réponses utilisateur autorisées exposent uniquement les identifiants d’objets, leur état, la date d’expiration et éventuellement des codes de refus neutres. Elles excluent systématiquement `storage_key`, URI de backend, secret présigné, hash, signatures antivirus, contenu, extraits et diagnostics internes. La lecture DCE-READ-01 reste inchangée et n’expose jamais les documents ni leur stockage.

## 11. Critères de sortie

La livraison DCE-STAGING-01 doit démontrer par tests PostgreSQL et sécurité : création tenant-scopée d’une intention, absence de clé de stockage dans les réponses, transitions d’état valides uniquement, fail-closed du scan, impossibilité de consommer un objet absent/hors tenant/non propre/expiré/déjà consommé, atomicité `DceVersion + DceDocument + consommation`, audit du refus collaborateur et neutralité inter-tenant. Les tests doivent prouver que le rollback de l’admission conserve l’objet à l’état `CLEAN` non consommé.

## 12. Non-objectifs de ce slice

DCE-STAGING-01 ne téléverse encore aucun octet HTTP, ne distribue aucune URL présignée, ne configure pas MinIO/S3, ne déploie pas ClamAV et ne parse pas les fichiers. Ces effets de bord appartiennent au prochain slice DCE-UPLOAD-01, fondé sur les ports et invariants définis ici.
