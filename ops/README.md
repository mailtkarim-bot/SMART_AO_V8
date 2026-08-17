# Opérations SMART_AO V8

## 1. Positionnement

Le fichier `docker-compose.yml` reste destiné au développement local. La préproduction VPS utilise `ops/docker-compose.preprod.yml`, qui expose uniquement Caddy sur les ports 80 et 443. PostgreSQL, l’API, le worker, le frontend interne et ClamAV communiquent sur des réseaux Docker privés ; aucun port PostgreSQL, API ou ClamAV n’est publié directement.

Cette configuration est un **template de préproduction**. Elle ne contient aucun secret réel et n’a pas été déployée sur un VPS dans cette étape.

## 2. Fichiers de la configuration

| Fichier | Rôle |
|---|---|
| `ops/docker-compose.preprod.yml` | Services VPS, volumes, réseaux privés, healthchecks et restart policy. |
| `ops/docker/backend.Dockerfile` | Image Python backend/worker actuelle. |
| `ops/docker/frontend.Dockerfile` | Build frontend React/Vite multi-stage servi par Nginx interne. |
| `ops/nginx/frontend.conf` | Fallback SPA et endpoint interne `/healthz`. |
| `ops/Caddyfile` | TLS automatique, en-têtes de sécurité, reverse proxy same-origin. |
| `ops/.env.preprod.example` | Variables documentées ; à copier puis compléter hors Git. |
| `ops/deploy-preprod.sh` | Déploiement verrouillé : validation, backup, pull/build pinné, migration, démarrage, smoke et opérations 7b. |
| `ops/backup-preprod.sh` | Backup PostgreSQL, quarantaine privée et volumes Caddy avec manifest SHA-256 et rétention. |
| `ops/restore-preprod.sh` | Restauration vérifiée dans une base PostgreSQL isolée temporaire ; aucune écriture de la base active. |
| `ops/healthcheck-preprod.sh` | Supervision HTTPS, live/ready, dépendances healthy, port ClamAV et fraîcheur backup. |
| `ops/rotate-jwt-key-preprod.sh` | Rotation JWT manuelle, confirmée et atomique pendant une fenêtre de maintenance. |
| `ops/systemd/` | Service/timer de backup quotidien et healthcheck périodique avec alerte journalisée. |
| `docs/reference/SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md` | Cible d’architecture, sauvegarde, réseau et observabilité. |

## 3. Pré-requis VPS

Le VPS doit disposer de Docker Engine et du plugin Compose, d’un domaine DNS pointant vers l’adresse publique, d’un pare-feu n’autorisant que SSH administré, HTTP et HTTPS, d’un disque persistant chiffré ou protégé par la politique d’hébergement, et d’un espace séparé pour les sauvegardes hors VPS. Docker doit être configuré pour démarrer au boot et les journaux doivent avoir une rotation bornée.

Avant tout lancement, installer un dépôt de déploiement privé ou cloner le commit exact validé par CI. Ne jamais placer un vrai `.env.preprod`, une clé privée TLS ou un dump de production dans Git. Le fichier `ops/.env.preprod` doit avoir des permissions `0600` et être accessible uniquement à l’utilisateur de déploiement. La factory Uvicorn `app.bootstrap.production:app` exige `SMART_AO_DATABASE_URL`, `SMART_AO_JWT_SIGNING_KEY`, `SMART_AO_JWT_ISSUER` et `SMART_AO_JWT_AUDIENCE`; aucune clé de test n’est acceptée.

## 4. Préparation contrôlée

Depuis la racine du dépôt, sur le VPS :

Le chemin opérateur recommandé est le script verrouillé :

```bash
cp ops/.env.preprod.example ops/.env.preprod
chmod 600 ops/.env.preprod
$EDITOR ops/.env.preprod
ops/deploy-preprod.sh config
```

`config` refuse les placeholders, vérifie Compose, valide Caddy et refuse toute image runtime qui ne contient pas `@sha256:`. Le script `deploy` prend un verrou exclusif, démarre les dépendances, attend PostgreSQL, sauvegarde la base existante, applique `alembic upgrade head`, démarre le stack et exécute le smoke test. Sur une base vide uniquement, `SMART_AO_ALLOW_EMPTY_BACKUP=1` doit être défini explicitement pour le premier déploiement. Aucun downgrade n’est automatique.

```bash
cp ops/.env.preprod.example ops/.env.preprod
chmod 600 ops/.env.preprod
$EDITOR ops/.env.preprod

docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml config

docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml build --pull
```

Les images Compose et les images `FROM` des Dockerfiles sont désormais référencées par digest. Le digest doit être renouvelé volontairement, revu, testé et publié avec une nouvelle CI ; un simple changement de tag n’est pas accepté.

La commande `config` doit être relue avant tout démarrage. Elle ne doit afficher aucun secret dans un terminal partagé, un ticket ou un log centralisé. Les références du template sont déjà pinnées par digest ; leur renouvellement est une opération de release volontaire, revue et testée.

## 5. Démarrage et vérifications ClamAV

```bash
docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml up -d

docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml ps

curl --fail --silent --show-error \
  --resolve "${SMART_AO_PUBLIC_HOST}:443:127.0.0.1" \
  "https://${SMART_AO_PUBLIC_HOST}/healthz/live"
curl --fail --silent --show-error \
  --resolve "${SMART_AO_PUBLIC_HOST}:443:127.0.0.1" \
  "https://${SMART_AO_PUBLIC_HOST}/healthz/ready"
```

Le démarrage n’est considéré comme valide que lorsque PostgreSQL et ClamAV sont `healthy`, que `/healthz/live` répond, que `/healthz/ready` confirme PostgreSQL et ClamAV, que Caddy obtient un certificat valide et que le frontend répond via HTTPS. Le contrôle automatisé est `ops/deploy-preprod.sh healthcheck`; il vérifie aussi la fraîcheur d’un backup SQL et l’absence de publication du port ClamAV. Le port `3310` de ClamAV ne doit jamais apparaître dans la liste des ports publiés. Le test antivirus réel doit utiliser un fichier EICAR de test dans la quarantaine de préproduction, puis vérifier le rejet, l’absence de publication et la traçabilité de l’état `REJECTED`; ce fichier ne doit jamais être utilisé dans un environnement client.

## 6. Migrations et rollback

Une release se déploie dans cet ordre : validation de la version d’image, démarrage des dépendances, attente de PostgreSQL, sauvegarde PostgreSQL vérifiée si la base contient déjà des tables, exécution de `alembic upgrade head` depuis le conteneur backend, vérification des healthchecks et test HTTP minimal. Une base vide n’est admise qu’au premier déploiement avec `SMART_AO_ALLOW_EMPTY_BACKUP=1` explicitement défini. Les migrations destructives ou irréversibles sont interdites sans procédure de sauvegarde et de restauration testée.

```bash
docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml run --rm backend \
  alembic -c backend/alembic.ini upgrade head
```

Le rollback applicatif privilégie la remise en place de l’image précédente et l’arrêt des workers. Un downgrade Alembic n’est jamais exécuté automatiquement en production ; il doit être explicitement validé après examen de la migration et de la sauvegarde.

## 7. Sauvegarde et restauration à prouver

La préproduction doit disposer d’un job externe ou d’un service opérateur pour sauvegarder PostgreSQL quotidiennement et avant migration, les volumes documentaires selon la politique de rétention, la configuration versionnée et les volumes Caddy nécessaires aux certificats. Les sauvegardes doivent être chiffrées, transférées hors VPS et contrôlées par hash.

Avant toute ouverture client, exécuter `ops/deploy-preprod.sh restore /var/backups/smart-ao/smart_ao_<timestamp>.sql.gz`. Le script vérifie le manifest SHA-256, restaure dans une base isolée temporaire, vérifie les tables `tenants`, `command_receipts` et `outbox_messages`, puis détruit la base temporaire. L’opérateur doit compléter ce contrôle par un échantillon de documents, les droits tenant, les hashes des objets et un rapport de restauration. Une sauvegarde jamais restaurée n’est pas une preuve de continuité.

Installer les unités `ops/systemd/smart-ao-backup.{service,timer}`, `smart-ao-healthcheck.{service,timer}` et `smart-ao-health-alert.service` sous `/etc/systemd/system/`, puis activer les timers. Les journaux Docker utilisent une rotation `json-file` bornée ; Caddy écrit aussi un access log JSON avec rétention bornée. Un agent externe doit agréger les alertes du journal système et surveiller l’absence de timer, l’échec du healthcheck et l’âge du dernier backup.

La rotation JWT n’est pas automatique : après sauvegarde de l’environnement, saisir une nouvelle clé hors historique, lancer `SMART_AO_CONFIRM_ROTATE=YES ops/rotate-jwt-key-preprod.sh` pendant une fenêtre de maintenance, redémarrer le stack et vérifier l’authentification. Cette version n’implémente pas de chevauchement multi-clés `kid`; la rotation invalide donc les sessions émises avec l’ancienne clé et doit être planifiée.

## 8. Points encore bloquants pour S12

Le template fournit désormais le script de déploiement, les scripts backup/restore/healthcheck/rotation, les timers systemd, la rotation des logs, les healthchecks live/ready détaillés et le pinning par digest. Restent requis avant un premier client : exécution sur un VPS réel, transfert des backups hors VPS, supervision externe, firewall administré, test EICAR ClamAV, rotation de secrets avec fenêtre validée et rapport de restauration. Le sandbox ne possède pas Docker et aucun VPS réel n’a encore exécuté le stack.
