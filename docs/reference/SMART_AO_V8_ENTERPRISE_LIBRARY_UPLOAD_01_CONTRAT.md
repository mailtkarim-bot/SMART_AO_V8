# SMART_AO V8 — ENTERPRISE-LIBRARY-UPLOAD-01

## Objet

Cet incrément sécurise la réception privée des documents de la bibliothèque entreprise et ajoute la vérification humaine patronale. Il réutilise le pipeline de quarantaine DCE, mais conserve un registre tenant-scoped propre à la société afin qu’un upload puisse précéder l’admission append-only du document.

## États et transitions

| Objet | États | Transitions autorisées |
|---|---|---|
| Intention d’upload | `AWAITING_UPLOAD`, `UPLOADING`, `QUARANTINED`, `CLEAN`, `REJECTED`, `EXPIRED` | `AWAITING_UPLOAD → UPLOADING → QUARANTINED → CLEAN` ou `REJECTED`; les erreurs sont fail-closed |
| Document entreprise | `PENDING`, `VALIDATED`, `EXPIRED`, `REJECTED` | Le document est append-only; le statut courant est projeté depuis l’historique de vérification |
| Vérification humaine | historique append-only | Chaque décision porte une révision; une révision obsolète est refusée par `VERSION_CONFLICT` |

Le stockage privé est écrit dans un fichier temporaire, sous une clé générée par le serveur, puis inspecté par signature MIME et scanné. Un échec d’écriture, d’inspection ou de scan supprime le contenu de quarantaine lorsque possible et laisse l’intention non admissible.

## Routes publiques

| Méthode | Route | Réponse publique |
|---|---|---|
| `POST` | `/api/v1/patron/enterprise/companies/{company_id}/documents/upload` | Receipt minimal contenant l’ID opaque de l’intention dans `aggregate_refs` |
| `PUT` | `/api/v1/patron/enterprise/companies/{company_id}/documents/uploads/{upload_id}/content` | `upload_id` et `state=CLEAN` uniquement |
| `POST` | `/api/v1/patron/enterprise/companies/{company_id}/documents` | Admission append-only après upload CLEAN |
| `POST` | `/api/v1/patron/enterprise/companies/{company_id}/documents/{document_id}/verification` | Receipt minimal de vérification |
| `GET` | `/api/v1/patron/enterprise/company` | Projection métier fermée, dernier outcome humain seulement |

Le flux binaire exige `Idempotency-Key`, n’accepte ni JSON ni multipart comme contenu attendu et ne renvoie ni chemin, URL, bucket, hash, MIME, signature scanner, contenu, IBAN ou nom de fichier.

## Autorisation et tenant

Les trois opérations d’écriture sont réservées au `PATRON_ADMIN` actif avec membership résolue côté serveur. Le collaborateur est refusé avant la lecture du stockage privé. Toute résolution de société, intention ou document est filtrée par `tenant_id`; une ressource étrangère reçoit une réponse neutre.

## Admission et vérification

Un document ne peut être admis qu’avec une intention appartenant à la même société, au même tenant et à l’état `CLEAN`. Le hash, la taille, le MIME et le verdict scanner sont alors récupérés depuis la persistance serveur. Le payload client ne peut pas fournir ou remplacer ces faits.

La vérification humaine écrit un historique append-only, avec outcome fermé `VALIDATED|REJECTED`, motif fermé et révision attendue. Aucun acteur `SYSTEM` ou collaborateur ne peut produire cette décision. La projection de lecture prend la décision de plus haute révision sans mettre à jour le document immutable.

## Tests attendus

Les tests couvrent le succès CLEAN, le hash calculé, le rejet MIME/scan, le nettoyage de quarantaine, le rejeu d’un flux déjà réclamé, le refus collaborateur, l’isolation inter-tenant, le conflit de révision, les payloads fermés et l’absence de fuite des métadonnées privées.
