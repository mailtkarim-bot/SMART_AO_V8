# SMART_AO V8 — DCE-RETENTION-01 : effacement physique sûr et idempotent

**Statut :** normatif.  
**Périmètre :** balayage des objets DCE expirés ou bloqués, consommation du topic d’outbox de rétention, suppression physique privée, reprises et traces durables.  
**Dépendances :** SEC-01, DCE-STAGING-01 et DCE-UPLOAD-01.

## 1. But

DCE-RETENTION-01 retire les fichiers privés qui ne doivent plus être conservés sans jamais rendre un document à nouveau disponible ni supprimer une pièce qui peut encore être admise ou constitue une preuve d’un DCE admis. Le worker est déterministe, sans IA, sans HTTP public et sans accès au bucket depuis le navigateur.

> La base de données reste l’autorité métier. Le stockage privé ne reçoit qu’un ordre d’effacement après relecture transactionnelle de l’état durable de l’objet DCE.

## 2. Objets effaçables et interdits

| État durable relu par le worker | Action | Justification |
|---|---|---|
| `REJECTED` | Suppression physique idempotente autorisée. | Le flux est échoué, infecté, de type interdit ou techniquement invalide ; il ne peut jamais être admis. |
| `EXPIRED` | Suppression physique idempotente autorisée. | L’objet non consommé a dépassé sa durée de rétention et a déjà été rendu terminal par une commande système. |
| `UPLOADING` dont `expires_at <= maintenant` | Le balayage lance d’abord `ExpireDceStagedObjectCommand`, puis traite l’outbox d’expiration. | Une panne pendant le flux peut laisser un fichier orphelin ; il reste non admissible et doit être rendu terminal avant effacement. |
| `AWAITING_UPLOAD`, `QUARANTINED`, `CLEAN` non expiré | Aucune suppression. | L’objet demeure en cours de traitement ou potentiellement admissible. |
| `CLEAN` expiré | Le balayage le fait expirer, puis l’effacement est autorisé. | L’objet n’a pas été consommé pendant la fenêtre contractuelle. |
| `CONSUMED` | Interdiction absolue. | Il est référencé par une `DceVersion` immuable et fait partie de l’historique du marché. |

Le worker ne supprime jamais la ligne `dce_staged_objects`, le document DCE, l’événement, l’outbox ou le receipt. Il efface uniquement le binaire privé référencé par une clé déjà connue du serveur.

## 3. Déclencheurs et sujets d’outbox

| Origine | Événement | Topic | Traitement |
|---|---|---|---|
| Expiration système | `DCE_STAGING_EXPIRED` | `dce_staging_retention` | Suppression du binaire si l’objet relu est réellement `EXPIRED`. |
| Rejet de flux | `DCE_STAGING_UPLOAD_REJECTED` | `dce_staging_retention` | Suppression du binaire partiellement écrit, si présent. |
| Verdict scan ou quarantaine rejeté | `DCE_STAGING_QUARANTINE_RECORDED` / `DCE_STAGING_SCAN_RECORDED` avec état `REJECTED` | `dce_staging_retention` | Suppression du binaire privé si l’état relu est `REJECTED`. |
| Balayage périodique | Objet non consommé dont `expires_at <= maintenant` | commande système puis même topic | Rend un objet en attente, en cours d’upload, en quarantaine ou propre terminal avant suppression. |

Les handlers d’upload doivent publier un message `dce_staging_retention` pour chaque transition vers `REJECTED`. L’événement est écrit dans la même transaction que l’état terminal et le receipt de commande.

## 4. Consommation idempotente de l’outbox

Le worker acquiert un lot de messages `PENDING` ou `RETRY` dont `next_attempt_at` est absent ou arrivé à échéance, en utilisant un verrou PostgreSQL `FOR UPDATE SKIP LOCKED`. Ainsi, plusieurs processus peuvent être démarrés sans traiter le même message simultanément.

Pour chaque message de topic `dce_staging_retention`, le worker relit l’objet staged par la paire tenant/ID provenant du payload d’outbox. Il agit alors ainsi :

| Cas relu | Effet sur le fichier | Effet sur le message |
|---|---|---|
| Objet absent | Aucun ; l’état est déjà cohérent. | `PUBLISHED` : succès idempotent. |
| `REJECTED` ou `EXPIRED` | Appel `delete(storage_key)` idempotent. `FileNotFound` est un succès. | `PUBLISHED`, `published_at` renseigné. |
| `CLEAN`, `CONSUMED` ou état non terminal | Aucun. | `PUBLISHED` avec code interne `RETENTION_SKIPPED_NOT_DELETABLE` ; un message historique ne permet jamais une suppression indue. |
| Erreur du stockage privé | Aucun changement métier. | `RETRY`, compteur incrémenté, `next_attempt_at` calculé par backoff borné. |

La suppression d’un fichier et le marquage SQL du message ne forment pas une transaction ACID commune. L’ordre obligatoire est : **suppression idempotente d’abord, puis `PUBLISHED`**. En cas de crash entre les deux, le nouvel essai appelle de nouveau `delete`, qui est sans danger si le fichier est absent.

## 5. Backoff, erreurs et observabilité

Les erreurs de stockage ne sont jamais ignorées. Le message passe à `RETRY` avec un délai exponentiel borné : 30 secondes, 60 secondes, 120 secondes, puis au plus 1 heure. Le compteur est conservé dans `outbox_messages.attempt_count`.

Le worker ne logge ni contenu DCE, ni hash, ni chemin absolu, ni clé de stockage. Ses journaux techniques ne contiennent au plus que l’ID pseudonymisé du message, l’ID opaque de l’objet et un code d’erreur fermé. Le worker n’écrit pas d’audit SEC-01 : il agit en processus système sur un événement déjà durable ; il n’évalue aucune action utilisateur.

## 6. Balayage des orphelins

À chaque boucle, avant ou après la consommation d’outbox, le worker sélectionne un lot borné d’objets non consommés avec `expires_at <= maintenant`, verrouille chaque objet et appelle `ExpireDceStagedObjectCommand` avec l’acteur système. Cette commande crée l’événement et l’outbox de rétention dans une même transaction.

Un `UPLOADING` expiré est donc traité exactement comme une intention abandonnée : le fichier éventuellement présent est supprimé uniquement après sa transition durable vers `EXPIRED`. Un objet `CONSUMED` est exclu dès la requête SQL et revalidé par le handler métier.

## 7. Exécution sur le VPS

Le worker est un service Docker séparé du backend HTTP. Il partage uniquement le volume privé de quarantaine et la connexion PostgreSQL ; il n’expose aucun port, ne dépend pas de ClamAV et n’est pas exécutable dans le navigateur. Il reçoit les mêmes variables de connexion et de racine privée que le backend.

Pour les tests, le worker expose une méthode `run_once()` déterministe. En production, son point d’entrée boucle avec un délai configurable entre les passages. L’arrêt du conteneur doit être propre : aucun message en cours n’est marqué `PUBLISHED` avant un effacement réussi.

## 8. Critères de sortie

DCE-RETENTION-01 doit prouver :

1. l’expiration d’un objet `UPLOADING` déclenche une outbox puis son effacement ;
2. un objet `REJECTED` est effacé et le message devient `PUBLISHED` ;
3. un second passage est sans effet destructif supplémentaire ;
4. un fichier déjà absent est un succès idempotent ;
5. une erreur de stockage produit `RETRY`, un compteur et un backoff ;
6. `CLEAN` et `CONSUMED` ne sont jamais supprimés, même devant un message de rétention falsifié ou historique ;
7. plusieurs workers ne prennent pas simultanément le même message ;
8. le worker ne retourne, ne journalise ni ne publie de clé, chemin, contenu, hash ou diagnostic antivirus.

## 9. Non-objectifs

Ce slice ne supprime pas l’historique métier, ne purge pas les audit logs, ne télécharge aucun document, ne réalise pas de nouvelle analyse antivirus et ne met pas en place une politique d’archivage légal longue durée. Il ne remplace pas non plus la sauvegarde chiffrée du VPS, qui relève de l’exploitation.
