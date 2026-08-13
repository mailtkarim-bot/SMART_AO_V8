# SMART_AO V8 — DCE-UPLOAD-01 : réception binaire sécurisée en quarantaine

**Statut :** normatif.  
**Périmètre :** réception d’un flux binaire dans l’objet déjà préparé par DCE-STAGING-01, écriture privée, calcul réel d’intégrité, identification par signature, scan ClamAV et transition durable vers un objet admissible ou rejeté.  
**Dépendances :** SEC-01, DCE-STAGING-01, DCE-ADMIT-01 et DCE-ADMIT-HTTP-01.

## 1. Intention et limite de responsabilité

DCE-UPLOAD-01 transforme une intention `AWAITING_UPLOAD` en objet documentaire réellement contrôlé. Un navigateur ne peut ni choisir une clé de stockage, ni déclarer un hash, ni imposer un type MIME, ni déclarer qu’un document est sain. Ces faits sont calculés exclusivement après écriture dans une zone privée de quarantaine.

> Un octet reçu n’est jamais un document DCE admissible. Il demeure en quarantaine et l’objet reste indisponible tant que le flux, le type réel, la taille, le hash et le verdict ClamAV ne sont pas tous validés.

Ce slice implémente un adaptateur local de quarantaine pour le VPS et un client `clamd` interne. Il ne publie ni bucket, ni URL présignée, ni chemin de système de fichiers. Une évolution vers MinIO/S3 devra implémenter les mêmes ports et invariants, sans changer les routes ou les handlers métier.

## 2. Machine d’état étendue

| État | Signification | Transitions autorisées | Accès utilisateur |
|---|---|---|---|
| `AWAITING_UPLOAD` | Intention persistée ; aucune écriture binaire n’a commencé. | `UPLOADING`, `EXPIRED`, `REJECTED` | Seul état accepté par l’endpoint d’upload. |
| `UPLOADING` | Le serveur a réclamé l’objet de manière atomique pour un unique flux. | `QUARANTINED`, `REJECTED`, `EXPIRED` | Ni réutilisable ni admissible. |
| `QUARANTINED` | Fichier écrit dans l’espace privé, taille/hash/type réel persistés ; verdict antivirus attendu. | `CLEAN`, `REJECTED`, `EXPIRED` | Ni téléchargeable ni admissible. |
| `CLEAN` | Scan ClamAV concluant et contrôles techniques satisfaits. | `CONSUMED`, `EXPIRED` | Seul état admissible par `RegisterDceVersionCommand`. |
| `REJECTED` | Flux incomplet, taille/type interdit, malware, scanner indisponible ou erreur technique. | `EXPIRED` | Jamais admissible. |
| `CONSUMED` | Objet immuablement rattaché à une `DceVersion`. | Aucune | Géré uniquement par DCE-ADMIT-01. |
| `EXPIRED` | Objet non consommé sorti de la période de rétention. | Aucune | Jamais admissible. |

La réclamation `AWAITING_UPLOAD → UPLOADING` est une commande idempotente et verrouillée en base. Un second flux concurrent, un replay tardif ou une reprise après crash ne peut pas écraser l’objet ; il reçoit un refus neutre. Une interruption de flux ou une indisponibilité de scanner se termine par `REJECTED` : la conception est **fail-closed**.

## 3. Frontière HTTP

| Élément | Règle normative |
|---|---|
| Méthode et URL | `PUT /api/v1/dce-staged-objects/{storage_object_id}/content` |
| Authentification | Bearer résolu côté serveur ; tenant, rôle, capability et identité ne viennent jamais du body. |
| Autorisation | `dce.prepare` et policy auditée sur la `Consultation` propriétaire de l’objet staged. Un tenant tiers reçoit `404 NOT_FOUND_OR_FORBIDDEN` audité ; un collaborateur sans scope reçoit `403` audité. |
| Corps | Flux brut (`application/octet-stream` possible mais non autoritatif). Le endpoint refuse `multipart/form-data`, JSON et base64. |
| Idempotence | En-tête `Idempotency-Key` UUID obligatoire. Il sert seulement à réclamer le flux ; les octets ne sont jamais rejoués depuis un receipt. |
| Taille | `Content-Length` est une optimisation de refus précoce seulement. La limite effective de **2 000 000 000 octets** est appliquée à chaque chunk lu. |
| Réponse | Ne contient que `storage_object_id`, état final et receipt métier minimal. Aucun chemin, URL, hash, type réel, signature ClamAV, nom de bucket ou diagnostic interne n’est retourné. |

Le navigateur ne communique ni `storage_key`, ni hash, ni MIME, ni taille déclarée de confiance. Le nom initial et la taille attendue sont ceux de l’intention DCE-STAGING-01 ; l’upload recalcule la taille réelle.

## 4. Parcours fiable du flux

| Étape | Responsable | Preuve durable ou effet |
|---|---|---|
| 1. Réclamation | Handler transactionnel | Verrouille l’objet `AWAITING_UPLOAD` et passe à `UPLOADING`; event, outbox et receipt atomiques. |
| 2. Écriture | Port `DceQuarantineStoragePort` | Lit les chunks un à un, compte les octets, calcule SHA-256 et écrit sous une clé privée dérivée par le serveur. Aucun chemin client n’est interprété. |
| 3. Contrôle de type | Port `DceContentInspectionPort` | Détermine le MIME par signature (« magic bytes »), puis le compare à l’allow-list serveur. `Content-Type` et extension ne sont pas des preuves. |
| 4. Quarantaine durable | Commande système | Passe `UPLOADING → QUARANTINED` et persiste taille, SHA-256 minuscule et type réel. Toute incohérence de taille ou de type passe directement à `REJECTED`. |
| 5. Antivirus | Port `DceMalwareScanPort` | Soumet le contenu privé à `clamd` via le protocole interne `INSTREAM`; conserve le verdict, l’identifiant moteur/signatures et l’horodatage. |
| 6. Verdict | Commande système | Passe `QUARANTINED → CLEAN` seulement pour un verdict `CLEAN`; `INFECTED`, `ERROR` ou timeout passent à `REJECTED`. |
| 7. Compensation | Service d’upload | Après rejet ou erreur, tente l’effacement idempotent du binaire. Une erreur d’effacement est journalisée pour la rétention, sans réautoriser l’objet. |

La persistance relationnelle et le système de fichiers ne partagent pas une transaction ACID. La cohérence est donc obtenue par une réclamation durable avant écriture, une clé non réutilisable, une compensation d’effacement et un état terminal fail-closed. Une panne entre écriture et verdict laisse au plus un fichier privé orphelin associé à `UPLOADING`; la rétention le fait expirer et l’efface, sans jamais le rendre admissible.

## 5. Ports et adaptateurs

| Port | Contrat minimal |
|---|---|
| `DceQuarantineStoragePort` | Écrit un `AsyncIterable[bytes]` sous une clé déjà dérivée côté serveur ; renvoie seulement taille réelle et SHA-256 ; supprime un objet de façon idempotente. |
| `DceContentInspectionPort` | Inspecte les octets privés ou le fichier privé et retourne le MIME détecté. |
| `DceMalwareScanPort` | Retourne `CLEAN`, `INFECTED` ou `ERROR`, avec moteur, signatures/version et date. Toute exception de transport devient `ERROR`. |
| `DceUploadService` | Orchestration sans accès HTTP : réclamation, écriture, inspection, mise en quarantaine, scan, verdict et compensation. |

L’adaptateur de production initial est `LocalQuarantineStorageAdapter`, sous un répertoire non servi par Nginx/Uvicorn et de permissions restrictives. `ClamdTcpMalwareScanAdapter` se connecte à `clamav:3310` uniquement sur le réseau Docker interne. Le port `3310` ne doit jamais être publié sur l’hôte. Les images ClamAV officielles écoutent `clamd` sur ce port mais Docker ne l’expose pas sans publication explicite. [1]

## 6. Contrôles de sécurité

| Risque | Mesure obligatoire |
|---|---|
| Écrasement ou course | Commande de réclamation, verrou `SELECT … FOR UPDATE`, état `UPLOADING`, écriture atomique sans overwrite. |
| Dépassement mémoire/disque | Lecture par chunks, limite incrémentale, aucun chargement complet en mémoire, `Content-Length` seulement anticipatif. |
| Traversée de chemin | Clé et chemin dérivés de `tenant_id` et `storage_object_id` validés serveur ; aucun segment de chemin client. |
| MIME trompeur | Détection par signature ; allow-list configurée côté serveur ; extension et en-tête ignorés comme preuve. |
| Malware ou scanner indisponible | Scan `clamd` après quarantaine ; `INFECTED`, erreur, timeout et réponse inattendue valent rejet terminal. |
| Fuite de contenu | Pas de download, URL, hash, type réel, signature, chemin ou extrait dans les réponses, audit ou logs de sécurité. |
| Reprise ambiguë | Échec de flux terminal ; créer une nouvelle intention de staging est requis. Aucun objet déjà réclamé n’est réutilisé. |

## 7. Allow-list initiale

L’allow-list est une configuration serveur fermée. Sa valeur initiale est réduite aux formats documentaires attendus dans les DCE : PDF, DOC/DOCX, XLS/XLSX, ODT/ODS, images PNG/JPEG/TIFF et ZIP. Les archives restent en quarantaine et ne sont jamais extraites dans ce slice ; l’inspection récursive, les protections anti-bombes et le dépaquetage contrôlé relèvent du futur DCE-DOCUMENT-PARSE-01.

Un type détecté hors allow-list est terminalement rejeté même si le nom du fichier porte une extension acceptable. Tout ajout de format nécessite une décision de sécurité, une valeur de configuration et des tests de signature.

## 8. Critères de sortie

DCE-UPLOAD-01 doit prouver par tests : refus sans bearer, refus collaborateur et isolation tenant auditée, rejet d’un état non `AWAITING_UPLOAD`, prévention de deux réclamations, contrôle incrémental de taille malgré un `Content-Length` absent ou faux, hash de contenu réellement calculé, MIME déterminé par signature, verdict ClamAV `CLEAN` vers `CLEAN`, `INFECTED`/erreur/timeout vers `REJECTED`, suppression compensatoire, absence de clé ou chemin dans les réponses, et impossibilité d’admettre un objet échoué.

## 9. Non-objectifs

Ce slice ne produit pas d’URL présignée, ne met pas de bucket ou ClamAV sur le réseau public, ne rend pas de document téléchargeable, ne réalise pas d’OCR ni d’extraction, ne décompresse pas les archives, ne permet pas de reprendre un flux interrompu et ne supprime pas encore les fichiers par worker planifié. L’expiration/effacement automatisé et l’analyse documentaire viendront dans des slices distincts.

## Références

[1]: https://docs.clamav.net/manual/Installing/Docker.html "ClamAV — Docker : images officielles, port clamd TCP 3310 et réseau interne"
