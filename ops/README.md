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
| `docs/reference/SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md` | Cible d’architecture, sauvegarde, réseau et observabilité. |

## 3. Pré-requis VPS

Le VPS doit disposer de Docker Engine et du plugin Compose, d’un domaine DNS pointant vers l’adresse publique, d’un pare-feu n’autorisant que SSH administré, HTTP et HTTPS, d’un disque persistant chiffré ou protégé par la politique d’hébergement, et d’un espace séparé pour les sauvegardes hors VPS. Docker doit être configuré pour démarrer au boot et les journaux doivent avoir une rotation bornée.

Avant tout lancement, installer un dépôt de déploiement privé ou cloner le commit exact validé par CI. Ne jamais placer un vrai `.env.preprod`, une clé privée TLS ou un dump de production dans Git. Le fichier `ops/.env.preprod` doit avoir des permissions `0600` et être accessible uniquement à l’utilisateur de déploiement.

## 4. Préparation contrôlée

Depuis la racine du dépôt, sur le VPS :

```bash
cp ops/.env.preprod.example ops/.env.preprod
chmod 600 ops/.env.preprod
$EDITOR ops/.env.preprod

docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml config

docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml build --pull
```

La commande `config` doit être relue avant tout démarrage. Elle ne doit afficher aucun secret dans un terminal partagé, un ticket ou un log centralisé. Les images doivent être remplacées par des références de release ou des digests immuables avant un déploiement client ; les tags présents dans le template servent au premier essai de préproduction.

## 5. Démarrage et vérifications ClamAV

```bash
docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml up -d

docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml ps

curl --fail --silent --show-error \
  --resolve "${SMART_AO_PUBLIC_HOST}:443:127.0.0.1" \
  "https://${SMART_AO_PUBLIC_HOST}/healthz"
```

Le démarrage n’est considéré comme valide que lorsque PostgreSQL et ClamAV sont `healthy`, que le backend accepte une connexion TCP interne, que Caddy obtient un certificat valide et que le frontend répond via HTTPS. Le port `3310` de ClamAV ne doit jamais apparaître dans la liste des ports publiés. Le test antivirus réel doit utiliser un fichier EICAR de test dans la quarantaine de préproduction, puis vérifier le rejet, l’absence de publication et la traçabilité de l’état `REJECTED`; ce fichier ne doit jamais être utilisé dans un environnement client.

## 6. Migrations et rollback

Une release se déploie dans cet ordre : sauvegarde PostgreSQL vérifiée, validation de la version d’image, démarrage des dépendances, exécution de `alembic upgrade head` depuis le conteneur backend, vérification des healthchecks et test HTTP minimal. Les migrations destructives ou irréversibles sont interdites sans procédure de sauvegarde et de restauration testée.

```bash
docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml run --rm backend \
  alembic -c backend/alembic.ini upgrade head
```

Le rollback applicatif privilégie la remise en place de l’image précédente et l’arrêt des workers. Un downgrade Alembic n’est jamais exécuté automatiquement en production ; il doit être explicitement validé après examen de la migration et de la sauvegarde.

## 7. Sauvegarde et restauration à prouver

La préproduction doit disposer d’un job externe ou d’un service opérateur pour sauvegarder PostgreSQL quotidiennement et avant migration, les volumes documentaires selon la politique de rétention, la configuration versionnée et les volumes Caddy nécessaires aux certificats. Les sauvegardes doivent être chiffrées, transférées hors VPS et contrôlées par hash.

Avant toute ouverture client, restaurer une base et un échantillon de documents sur un environnement isolé, appliquer ou non les migrations selon la version sauvegardée, vérifier les droits tenant, vérifier les hashes des objets, contrôler les jobs d’outbox et produire un rapport de restauration. Une sauvegarde jamais restaurée n’est pas une preuve de continuité.

## 8. Points encore bloquants pour S12

Le template ne fournit pas encore le job de sauvegarde hors VPS, la supervision/alerte, la rotation des logs, le firewall automatisé, le health endpoint applicatif détaillé, la rotation de secrets, le pinning final par digest, ni l’exercice de restauration. Ces éléments doivent faire l’objet de tickets ops séparés avant un premier client.
