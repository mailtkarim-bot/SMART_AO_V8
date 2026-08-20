# Spécification de validation opérationnelle VPS

## Objectif

Cette procédure définit le **gate de validation préproduction** à exécuter dès qu’un VPS réel sera disponible. Elle ne remplace pas les tests CI : elle vérifie le comportement intégré des images, du réseau privé, de PostgreSQL, de ClamAV, de Caddy, des sauvegardes, de la restauration et des workers.

La validation doit être exécutée par un opérateur disposant d’un accès SSH au VPS, d’un nom DNS contrôlé pour la préproduction et d’un stockage hors VPS pour les sauvegardes. Aucune étape ne doit être déclarée réussie sur la seule base d’un fichier de configuration ou d’un `docker compose config` local.

## Préconditions et preuves d’entrée

| Domaine | Précondition | Preuve à conserver |
|---|---|---|
| VPS | Ubuntu compatible, disque et mémoire suffisants, horloge synchronisée | `uname -a`, `df -h`, `free -h`, `timedatectl` |
| Accès | Compte opérateur non root avec `sudo`, clé SSH et pare-feu configuré | commande SSH, règles firewall exportées |
| DNS/TLS | `SMART_AO_PUBLIC_HOST` résout vers le VPS | résolution DNS avant déploiement |
| Secrets | `.env.preprod` complété hors Git, permissions `0600`, aucun placeholder | hash du fichier sans révéler son contenu |
| Images | images applicatives construites depuis le commit validé et dépendances épinglées par digest | commit, sortie Compose et digests |
| Sauvegarde | destination hors VPS chiffrée et accessible | test d’écriture et hash du manifeste |
| Charge | scénario et seuils approuvés avant exécution | fichier de paramètres de test |

Les secrets, mots de passe, tokens JWT, URL privées et données financières ne doivent jamais apparaître dans les logs, les rapports ou les commandes copiées dans le ticket opérateur.

## Séquence d’exécution

### 1. Préparation contrôlée

L’opérateur clone exactement le commit validé, copie `ops/.env.preprod.example` vers `ops/.env.preprod`, complète les variables hors Git et applique `chmod 600`. Il exécute ensuite `ops/deploy-preprod.sh config`. Cette étape doit refuser les placeholders, les images runtime non digest-pinnées, une configuration Caddy invalide et une publication inattendue de ports internes.

Preuves minimales : hash du commit, hash du fichier Compose rendu sans secrets, liste des services, liste des ports publiés et code de retour de `config`.

### 2. Déploiement et migrations

L’opérateur exécute `ops/deploy-preprod.sh deploy`. Le script doit prendre son verrou exclusif, démarrer PostgreSQL et ClamAV, attendre leurs healthchecks, réaliser la sauvegarde préalable si la base n’est pas vide, exécuter `alembic upgrade head`, démarrer le backend, le frontend, Caddy, le worker DCE et le worker `submission-export-webhook`.

L’exécution est arrêtée si la sauvegarde préalable échoue, si une migration échoue, si un conteneur redémarre en boucle ou si un service expose un port interne. Aucun downgrade automatique n’est autorisé.

### 3. Santé réseau et TLS

Exécuter `ops/deploy-preprod.sh healthcheck` puis vérifier manuellement :

```bash
curl --fail --silent --show-error "https://${SMART_AO_PUBLIC_HOST}/healthz/live"
curl --fail --silent --show-error "https://${SMART_AO_PUBLIC_HOST}/healthz/ready"
docker compose -f ops/docker-compose.preprod.yml ps
ss -lntup
```

Les critères sont les suivants : le certificat correspond au nom DNS, `/healthz/live` répond, `/healthz/ready` confirme PostgreSQL et ClamAV, le frontend répond via HTTPS, PostgreSQL et ClamAV ne sont pas publiés sur l’interface externe, et Caddy présente les en-têtes de sécurité attendus.

### 4. Test ClamAV réel avec EICAR

Créer le fichier EICAR uniquement dans la quarantaine de préproduction, le soumettre au chemin d’upload prévu, puis vérifier que ClamAV le rejette, que l’objet n’est pas matérialisé comme document CLEAN, que l’état final est `REJECTED`, et que le journal applicatif conserve le code de rejet sans révéler le contenu.

Le fichier EICAR ne doit jamais être utilisé dans un environnement client. Après le test, supprimer les artefacts de test et conserver uniquement les logs, statuts et hashes autorisés.

### 5. Export, outbox et worker webhook

Préparer un dossier de soumission de test avec des pièces non sensibles, exécuter un export patronal et vérifier :

1. l’archive est déterministe et son hash est conservé dans la réponse opérateur ;
2. l’action crée l’audit `SUBMISSION_PACKAGE_EXPORTED` et une notification outbox ;
3. le worker consomme `submission.package.exported` une seule fois malgré plusieurs cycles ;
4. sans `SMART_AO_EXPORT_WEBHOOK_URL`, le message est traité comme skip contrôlé ;
5. avec un endpoint de test, seuls l’événement, l’identifiant du dossier, le hash de l’archive et le canal `DOWNLOAD` sont transmis ;
6. aucun montant, snapshot financier, ligne de prix, fichier ou storage key ne traverse le webhook ;
7. un code HTTP non 2xx ou une indisponibilité provoque un retry borné et ne perd pas le message.

La preuve attendue contient le topic, les compteurs du worker, le statut final outbox, le nombre d’essais et le code d’erreur éventuel, sans le contenu du payload financier.

### 6. Sauvegarde hors VPS et restauration isolée

Exécuter le backup avant migration et après validation, transférer les artefacts vers le stockage hors VPS, vérifier le manifeste SHA-256 et conserver le résultat. Exécuter ensuite `ops/deploy-preprod.sh restore <backup.sql.gz>` dans une base temporaire isolée.

La restauration est valide seulement si la vérification des tables de contrôle, l’échantillon documentaire, les hashes, la séparation tenant et l’état outbox réussissent. La base active ne doit pas être modifiée par cette opération. Détruire la base temporaire après le contrôle et conserver les logs de création/destruction.

### 7. Timers et supervision

Installer et activer les unités systemd de backup et de healthcheck. Vérifier `systemctl is-enabled`, `systemctl is-active`, `systemctl list-timers`, les journaux du dernier lancement et la réception d’une alerte simulée. Une supervision externe doit détecter au minimum l’échec du healthcheck, l’absence de timer, l’âge excessif du dernier backup et le redémarrage répété d’un conteneur.

## Test de charge contrôlé

Le test doit commencer par une charge basse et être exécuté hors fenêtre de migration. Il doit utiliser des dossiers de test non sensibles et mesurer séparément : latence `/healthz/ready`, temps d’assemblage ZIP, taille d’archive, CPU, mémoire, I/O disque, profondeur outbox, taux de retry et redémarrages de conteneurs.

Le scénario minimal comprend 10, 50 et 100 exports séquentiels, puis 10 exports concurrents. Chaque palier dure au maximum cinq minutes avec une montée progressive. Le test s’arrête immédiatement en cas d’erreur 5xx persistante, de saturation mémoire, de perte d’outbox, de fuite de données dans un log ou de dégradation du healthcheck.

Les seuils initiaux proposés sont des **budgets de validation**, pas des SLO de production : zéro perte ou duplication observable de notification, zéro fuite de données financières, zéro redémarrage inattendu, 100 % de réponses HTTP correctes sur le scénario nominal, et absence de croissance non bornée de `PENDING`/`RETRY`. Les valeurs de latence et de débit doivent être calibrées sur la taille réelle des documents avant d’être contractualisées.

## Rapport obligatoire

Le rapport final doit contenir le commit déployé, les digests d’images, les versions de migration, les timestamps UTC, les sorties healthcheck, les statuts Compose, les logs worker filtrés des secrets, les résultats ClamAV/EICAR, le manifeste de sauvegarde et ses hashes, la preuve de restauration isolée, l’échantillon documentaire, la vérification tenant, les compteurs outbox et les résultats de charge.

La validation est **REFUSED** si une preuve est manquante, si le VPS réel n’a pas été utilisé, si une sauvegarde n’a jamais été restaurée, si un secret apparaît dans les logs, si le port ClamAV ou PostgreSQL est publié, ou si les critères de non-fuite financière ne sont pas démontrés.
