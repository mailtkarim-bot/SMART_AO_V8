# Déploiement manuel de la préproduction SMART_AO V8

## Objet et périmètre

Ce document décrit un déploiement manuel sur un VPS dédié à la **préproduction**, sans donnée client et sans secret de production. Il s’appuie sur `ops/deploy-preprod.sh`, `ops/healthcheck-preprod.sh`, le Compose préproduction et les scripts de backup/restore déjà versionnés dans le dépôt.

Cette procédure ne déploie rien depuis la CI et ne fournit aucune preuve qu’un VPS réel est actuellement disponible. L’opérateur doit disposer d’un accès SSH au VPS, d’une fenêtre de maintenance approuvée et d’un second contrôle humain avant de considérer la recette comme PASS.

> Ne jamais exécuter cette procédure contre une base, un stockage, un DNS ou des secrets de production. Ne jamais copier `ops/.env.preprod` dans Git, dans un ticket ou dans un artefact CI.

## Préconditions VPS

Le VPS doit être dédié au staging, disposer de Docker Engine avec Compose v2, de `git`, `curl`, `openssl`, `jq`, `sha256sum`, `gzip` et de suffisamment d’espace disque pour les images, les backups et les volumes privés. PostgreSQL et ClamAV doivent rester accessibles uniquement sur le réseau Compose interne ; seul Caddy publie les ports HTTP/HTTPS.

Le dépôt doit être installé dans un chemin stable, par exemple `/opt/smart-ao-v8`, avec un utilisateur opérateur autorisé à exécuter Docker. Le répertoire des preuves doit être privé et non servi par Caddy :

```bash
sudo install -d -o "$USER" -g "$USER" -m 700 /opt/smart-ao-v8/artifacts
cd /opt/smart-ao-v8
```

## 1. Sélectionner le commit à déployer

Déployer uniquement un commit déjà fusionné dans `main` et dont la CI complète est verte. Pour la version actuelle, l’opérateur doit remplacer la valeur ci-dessous par le SHA validé dans le dossier de changement :

```bash
git fetch --prune origin
git switch main
git pull --ff-only origin main
git rev-parse HEAD
git status --short --branch
```

L’arbre doit être propre. Conserver le SHA, l’horodatage UTC, la version Docker Compose et les digests d’images dans le dossier de preuves. Le déploiement d’une branche de travail ou d’un arbre local modifié est interdit.

## 2. Préparer les secrets et la configuration locale

Créer le fichier à partir du modèle sans afficher son contenu dans le terminal. Il doit être spécifique au staging et avoir le mode `0600` :

```bash
cd /opt/smart-ao-v8
umask 077
cp -n ops/.env.preprod.example ops/.env.preprod
chmod 600 ops/.env.preprod
${EDITOR:-vi} ops/.env.preprod
stat -c '%a %n' ops/.env.preprod
```

Renseigner au minimum un hostname staging résolu vers le VPS, `SMART_AO_DATABASE_URL`, les paramètres PostgreSQL, une clé JWT de staging, son issuer et son audience, ainsi que les paramètres Caddy requis par le Compose. Les valeurs `REPLACE_WITH_*`, les clés de production et les URLs de production sont interdites.

Pour le lot OCR, laisser par défaut `SMART_AO_INSTALL_DOCUMENT_OCR=0` et `SMART_AO_OCR_ENABLED=0` tant que les modèles locaux et le dictionnaire n’ont pas été fournis, vérifiés par hash et approuvés pour le staging. Si l’OCR est explicitement validé, activer les deux flags et fournir des chemins lisibles vers les trois modèles ONNX et `ppocr_keys.txt`. Le pipeline ne télécharge aucun modèle ni dictionnaire.

## 3. Valider sans exposer les secrets

Exécuter les contrôles syntaxiques et la validation contrôlée du dépôt :

```bash
cd /opt/smart-ao-v8
bash -n ops/deploy-preprod.sh ops/healthcheck-preprod.sh \
  ops/backup-preprod.sh ops/restore-preprod.sh
ops/deploy-preprod.sh config \
  2>&1 | tee "artifacts/config-$(date -u +%Y%m%dT%H%M%SZ).log"
```

Pour constituer une preuve non secrète de la topologie, archiver séparément les services et les images résolues, sans archiver la sortie complète de `docker compose config` qui pourrait contenir des variables sensibles :

```bash
set -a
source ops/.env.preprod
set +a
docker compose --env-file ops/.env.preprod -f ops/docker-compose.preprod.yml \
  config --services | tee "artifacts/services-$(date -u +%Y%m%dT%H%M%SZ).txt"
docker compose --env-file ops/.env.preprod -f ops/docker-compose.preprod.yml \
  config --images | tee "artifacts/images-$(date -u +%Y%m%dT%H%M%SZ).txt"
```

Le contrôle est bloquant si une image n’est pas digest-pinnée, si Caddy est invalide, si un placeholder subsiste, si le fichier de configuration n’est pas en `0600` ou si PostgreSQL/ClamAV disposent d’un port publié. Le script vérifie également la cohérence des flags OCR ; lorsque l’OCR est activé, l’installation de l’extra OCR doit l’être aussi et les chemins de modèles/dictionnaire seront revalidés dans le conteneur après construction.

## 4. Déployer avec backup préalable et migration

Après validation, exécuter le script versionné. Il utilise un verrou, vérifie la configuration, sauvegarde la base existante, applique `alembic upgrade head`, démarre les services et exécute un smoke test :

```bash
mkdir -p artifacts
ops/deploy-preprod.sh deploy \
  2>&1 | tee "artifacts/deploy-$(date -u +%Y%m%dT%H%M%SZ).log"
```

Ne définir `SMART_AO_ALLOW_EMPTY_BACKUP=1` que lors d’une première base staging explicitement approuvée et documentée. En cas d’échec, conserver le log, le backup et l’état des conteneurs. Le script ne lance aucun `alembic downgrade` automatique. Si `SMART_AO_OCR_ENABLED=1`, le déploiement s’arrête avant le démarrage applicatif si l’un des trois modèles ONNX ou le dictionnaire local est absent ou illisible dans le volume monté.

## 5. Vérifier conteneurs, migration et réseau

Charger les variables uniquement dans le shell opérateur et ne pas les imprimer :

```bash
set -a
source ops/.env.preprod
set +a
COMPOSE=(docker compose --env-file ops/.env.preprod -f ops/docker-compose.preprod.yml)
"${COMPOSE[@]}" ps
"${COMPOSE[@]}" exec -T backend alembic current
"${COMPOSE[@]}" exec -T backend alembic heads
"${COMPOSE[@]}" port postgres 5432
"${COMPOSE[@]}" port clamav 3310
```

`alembic current` doit atteindre l’unique head attendue par `backend/app/platform/persistence/schema.py`, actuellement `20260826_0067` pour le code OCR fusionné. Les commandes de port PostgreSQL et ClamAV doivent ne retourner aucun endpoint public. Toute divergence de head, tout conteneur non sain ou tout port interne publié laisse la recette en état REJECTED.

## 6. Live, readiness et contrôles de sécurité

Exécuter les deux niveaux de vérification :

```bash
ops/deploy-preprod.sh smoke \
  2>&1 | tee "artifacts/smoke-$(date -u +%Y%m%dT%H%M%SZ).log"
ops/deploy-preprod.sh healthcheck \
  2>&1 | tee "artifacts/healthcheck-$(date -u +%Y%m%dT%H%M%SZ).log"
```

Le healthcheck doit démontrer un certificat correspondant au hostname staging, `/healthz/live` avec le processus sain, `/healthz/ready` avec la base, le schéma et ClamAV disponibles, des services `postgres`, `clamav`, `backend` et `caddy` sains, l’absence de ports internes publiés et un backup PostgreSQL récent.

La recette ClamAV EICAR, si elle est autorisée, doit être exécutée uniquement dans le répertoire temporaire du staging, jamais dans un volume de production :

```bash
printf '%s' 'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*' \
  > /tmp/eicar.com
sha256sum /tmp/eicar.com
# Exécuter ensuite le parcours upload/quarantaine prévu par la recette staging.
rm -f /tmp/eicar.com
```

Le verdict attendu est le rejet ou la quarantaine selon la politique configurée. Un document sain de test doit être non sensible et généré pour la recette ; aucun Kbis, RIB ou certificat réel ne doit être utilisé.

## 7. Backup et restauration isolée

Avant tout test destructif ou changement de configuration sensible :

```bash
ops/deploy-preprod.sh backup \
  2>&1 | tee "artifacts/backup-$(date -u +%Y%m%dT%H%M%SZ).log"
```

Vérifier ensuite un backup dans une base PostgreSQL temporaire isolée. Le script ne remplace pas la base principale :

```bash
ops/deploy-preprod.sh restore /var/backups/smart-ao/smart_ao_<timestamp>.sql.gz \
  2>&1 | tee "artifacts/restore-$(date -u +%Y%m%dT%H%M%SZ).log"
```

La restauration est PASS seulement si le checksum, les tables durables, la tête Alembic et les triggers append-only sont vérifiés, puis si la base temporaire est supprimée. Un échec impose de conserver les preuves et d’ouvrir une action corrective ; aucun downgrade automatique ne doit être tenté.

## 8. Dossier de preuves et décision de sortie

Le dossier de preuve doit contenir le SHA déployé, les versions/outils, les services et images résolus sans secret, les logs `config`, `deploy`, `smoke`, `healthcheck`, `backup` et `restore`, `alembic current/heads`, l’état des conteneurs, les résultats live/ready, les ports internes non publiés, le verdict EICAR si réalisé et les checksums des backups.

| Domaine | PASS attendu |
|---|---|
| Code | Commit fusionné dans `main`, arbre VPS propre, CI correspondante verte |
| Images | Services applicatifs construits ou tirés avec les digests attendus |
| Migration | Unique head Alembic atteinte, actuellement `20260826_0067` |
| Réseau | Seul Caddy expose les ports publics ; PostgreSQL et ClamAV restent internes |
| Santé | Live, readiness, conteneurs, PostgreSQL, ClamAV et Caddy sains |
| Sécurité | Fichier env en `0600`, aucun secret dans les preuves, EICAR rejeté si la recette est autorisée |
| Reprise | Backup horodaté et restauration isolée vérifiée |
| OCR | Opt-in uniquement ; modèles et dictionnaire locaux validés ; aucune métrique de précision revendiquée |

Un seul critère bloquant en échec laisse le staging en état **REJECTED**. L’opérateur conserve les preuves, n’effectue pas de downgrade improvisé et obtient une nouvelle décision de changement avant toute reprise.

## Références du dépôt

[1]: ../ops/deploy-preprod.sh "Orchestrateur de déploiement préproduction"
[2]: ../ops/healthcheck-preprod.sh "Healthcheck préproduction"
[3]: ../ops/docker-compose.preprod.yml "Compose préproduction digest-pinné"
[4]: ./STAGING_POST_DEPLOYMENT_ACCEPTANCE_PLAN.md "Plan d’acceptation staging"
[5]: ./CONTROLLED_DCE_OCR.md "Contrat OCR DCE contrôlé"
