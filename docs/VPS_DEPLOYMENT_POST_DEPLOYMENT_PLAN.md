# Plan de déploiement et de vérification post-déploiement VPS

**Projet :** SMART_AO V8  
**Branche :** `ops/vps-deploy-health-digests-01`  
**Nature :** préproduction contrôlée, sans données client  
**Statut actuel :** prêt à exécuter dès qu’un VPS réel, un DNS de préproduction et un stockage hors VPS sont disponibles ; aucune validation VPS réelle n’est déclarée à ce stade.

## 1. Objectif et décision de sortie

Ce document transforme les scripts et la spécification opérationnelle du dépôt en une séquence exécutable. Il vérifie la chaîne Docker Compose, PostgreSQL, ClamAV, backend, frontend, Caddy, workers, migrations, sauvegardes, restauration isolée, TLS, observabilité et charge contrôlée. Il complète les tests CI ; il ne les remplace pas. [1] [2]

La décision finale est `ACCEPTÉ`, `CONDITIONNEL` ou `REFUSÉ`. Elle est `REFUSÉE` si un secret apparaît dans un artefact, si PostgreSQL ou ClamAV est publié, si l’EICAR n’est pas rejeté, si une sauvegarde n’est pas restaurée isolément, si une fuite financière atteint un contrat collaborateur ou un webhook, si l’outbox perd ou double un effet, ou si une preuve obligatoire manque.

> **Limite actuelle :** le dépôt contient un template et des scripts opérateur, mais aucun VPS réel n’a exécuté le stack. Une configuration locale, un `docker compose config` ou une CI verte ne constituent pas une preuve de déploiement réel. [1] [3]

## 2. Préconditions d’entrée

| Domaine | Condition | Preuve attendue | Bloquant si absent |
|---|---|---|---|
| Hôte | VPS Ubuntu compatible, Docker Engine et Compose, disque et mémoire mesurés | `uname -a`, `df -h`, `free -h`, `timedatectl`, versions Docker | Oui |
| Accès | Compte non root avec `sudo`, clé SSH, politique de pare-feu | commande SSH et export des règles | Oui |
| DNS/TLS | Nom DNS de préproduction résolu vers le VPS, ports 80/443 accessibles | résolution avant déploiement et certificat final | Oui |
| Code | Commit exact `ops/vps-deploy-health-digests-01`, arbre propre, CI verte | SHA GitHub, URL run CI, `git status` | Oui |
| Secrets | `.env.preprod` hors Git, mode `0600`, aucune valeur `REPLACE_WITH_*` | hash du fichier sans contenu | Oui |
| Sauvegarde | Répertoire local protégé et destination chiffrée hors VPS | test d’écriture, manifeste SHA-256, transfert | Oui |
| Corpus | Documents BTP autorisés, non sensibles et hashés | manifeste de corpus sans fichiers attachés | Oui pour charge |
| Supervision | Accès aux journaux Docker/Caddy/systemd et canal d’alerte externe | test d’alerte documenté | Oui avant ouverture client |

Le fichier `.env.preprod` ne doit jamais être commité, copié dans un ticket ou inclus dans un rapport. Les commandes qui contiennent des URLs privées, mots de passe, tokens ou clés sont exclues des preuves textuelles.

## 3. Préparation du VPS

L’opérateur crée un compte de déploiement non root, installe Docker depuis une source approuvée, active le service Docker au démarrage, limite le pare-feu à SSH administré, HTTP et HTTPS, et configure une rotation bornée des logs. PostgreSQL, ClamAV, le backend, le frontend interne et le réseau Docker `internal` restent privés. [3]

Le dépôt est placé au chemin `/opt/smart-ao` afin de correspondre aux unités systemd fournies. L’opérateur clone le commit exact validé, contrôle `git rev-parse HEAD`, puis crée l’environnement hors Git :

```bash
cd /opt
sudo git clone https://github.com/mailtkarim-bot/SMART_AO_V8.git smart-ao
sudo chown -R deploy:deploy /opt/smart-ao
cd /opt/smart-ao
sudo -u deploy git checkout ops/vps-deploy-health-digests-01
cp ops/.env.preprod.example ops/.env.preprod
chmod 600 ops/.env.preprod
$EDITOR ops/.env.preprod
```

Les variables obligatoires sont `SMART_AO_PUBLIC_HOST`, `SMART_AO_DATABASE_URL`, `SMART_AO_JWT_SIGNING_KEY`, `SMART_AO_JWT_ISSUER`, `SMART_AO_JWT_AUDIENCE`, `POSTGRES_DB`, `POSTGRES_USER` et `POSTGRES_PASSWORD`. Le premier déploiement d’une base réellement vide doit être explicitement autorisé par `SMART_AO_ALLOW_EMPTY_BACKUP=1`; cette exception ne doit jamais être utilisée pour masquer une perte de données.

## 4. Contrôle de configuration avant démarrage

L’opérateur conserve dans un répertoire privé de preuves le commit, la date UTC, le hash du rendu Compose sans secrets, les services, les ports et le code retour de validation. Le contrôle initial est :

```bash
cd /opt/smart-ao
ops/deploy-preprod.sh config

docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml config --services

docker compose --env-file ops/.env.preprod \
  -f ops/docker-compose.preprod.yml config --services \
  | sort
```

Le contrôle doit confirmer que les seules publications sont `80/tcp`, `443/tcp` et `443/udp` sur Caddy, que `3310` n’est pas publié, et que les images explicites PostgreSQL, ClamAV et Caddy comportent un digest. Les images backend et frontend sont construites localement à partir de Dockerfiles dont les images de base sont digest-pinnées ; l’ID et le digest de chaque image finale doivent cependant être relevés après build dans le rapport de release. [3]

### Écart identifié avant le premier gate réel

Le fichier `ops/deploy-preprod.sh` démarre actuellement `backend`, `dce-retention-worker`, `frontend` et `caddy`, mais pas explicitement `submission-export-webhook-worker`, alors que la documentation et le Compose le déclarent requis. Avant le déploiement réel, il faut soit corriger le script pour démarrer ce worker, soit consigner une commande opérateur équivalente et ajouter un test de contrat. Le gate ne doit pas être déclaré vert tant que ce point n’est pas résolu.

De même, `smoke` vérifie que les services sont `running`, tandis que `healthcheck` vérifie seulement PostgreSQL, ClamAV, backend et Caddy. La santé et le redémarrage des deux workers doivent être contrôlés séparément par `docker compose ps`, `docker inspect` et les logs filtrés. [3]

## 5. Déploiement contrôlé

La release est exécutée dans une fenêtre de maintenance avec un verrou exclusif. La séquence attend PostgreSQL et ClamAV, sauvegarde la base si elle n’est pas vide, applique les migrations et démarre le stack :

```bash
cd /opt/smart-ao
ops/deploy-preprod.sh deploy
ops/deploy-preprod.sh status
ops/deploy-preprod.sh healthcheck
```

L’opérateur conserve le résultat de `alembic current`, `alembic heads`, les digests ou IDs des images, le statut de chaque conteneur, les compteurs de redémarrage et les timestamps UTC. La tête attendue au moment de cette branche est `20260818_0047`, à confirmer dans le dépôt et dans la base avant de l’inscrire comme preuve.

Une migration échouée, un conteneur en boucle de redémarrage, un backup préalable échoué ou un healthcheck en erreur arrête la release. Aucun downgrade Alembic automatique n’est autorisé. Le rollback applicatif est une remise en place explicitement revue de l’image précédente, jamais une improvisation destructive sur la base.

## 6. Vérification réseau, TLS et santé

Les contrôles automatiques du script vérifient les endpoints live/ready via le nom DNS résolu vers l’hôte local, les services principaux, la publication de `3310` et la fraîcheur d’un backup SQL. Ils doivent être complétés depuis un runner externe afin de prouver le chemin réseau réel :

```bash
curl --fail --silent --show-error \
  "https://${SMART_AO_PUBLIC_HOST}/healthz/live"
curl --fail --silent --show-error \
  "https://${SMART_AO_PUBLIC_HOST}/healthz/ready"
curl --fail --silent --show-error -I \
  "https://${SMART_AO_PUBLIC_HOST}/"
```

L’opérateur vérifie aussi que le certificat correspond au DNS, que les redirections et en-têtes de sécurité sont présents, que le frontend est servi via Caddy, et que `ss -lntup` ne montre pas de port PostgreSQL ou ClamAV exposé. Les logs Caddy et backend sont inspectés sur une fenêtre UTC bornée, puis filtrés avant conservation.

| Contrôle | Acceptation |
|---|---|
| `/healthz/live` | Réponse HTTP correcte et stable |
| `/healthz/ready` | PostgreSQL et ClamAV confirmés disponibles |
| Caddy | Certificat correspondant au DNS et proxy fonctionnel |
| Frontend | Page servie par HTTPS, sans dépendance vers une URL backend non validée |
| Ports | Aucun port PostgreSQL, ClamAV ou API interne publié |
| Workers | DCE retention et export webhook actifs, sans redémarrage inattendu |
| Logs | Aucun secret, token, contenu financier ou contenu documentaire |

## 7. Test ClamAV réel en préproduction

Le test EICAR est exécuté uniquement sur la préproduction, dans un tenant et un dossier de test dédiés. Le fichier est soumis par le chemin d’upload prévu, puis l’opérateur vérifie que ClamAV le rejette, que le document n’est jamais matérialisé en état `CLEAN`, que l’état final est `REJECTED`, que le code de rejet est auditable et qu’aucun contenu du fichier ne figure dans les logs.

Après le test, les artefacts EICAR et les documents de test sont supprimés. Le rapport ne conserve que le statut, les timestamps, les compteurs et les hashes autorisés. Une preuve EICAR manquante entraîne un statut `REFUSÉ`, même si les healthchecks sont verts. [1]

## 8. Export, audit, outbox et webhook

Un dossier de soumission non sensible est préparé dans un tenant de préproduction. L’opérateur déclenche un export, vérifie le hash déterministe de l’archive, l’audit `SUBMISSION_PACKAGE_EXPORTED`, le message outbox `submission.package.exported` et la consommation par le worker.

La campagne doit être exécutée en deux modes. Sans `SMART_AO_EXPORT_WEBHOOK_URL`, le skip contrôlé est attendu. Avec un endpoint de test dédié, le récepteur ne conserve pas le body complet ; il conserve uniquement un compteur, des headers non secrets, la taille, les clés reçues et un hash du body. Le récepteur doit confirmer que seuls l’événement, l’identifiant du dossier, le hash de l’archive et le canal `DOWNLOAD` traversent le webhook.

Les assertions bloquantes sont l’absence de montant, snapshot financier, ligne de prix, storage key, chemin privé ou contenu documentaire ; l’absence de double livraison lors d’un rejeu ; un retry borné en cas de réponse non 2xx ; et la résorption du backlog `PENDING`/`RETRY`. Les logs du worker sont filtrés avant conservation. [1] [2]

## 9. Sauvegarde hors VPS et restauration isolée

Le script de backup produit un dump PostgreSQL compressé, des archives optionnelles de quarantaine et des volumes Caddy, puis un manifeste SHA-256 dans le répertoire local de backup. Il ne constitue pas à lui seul une sauvegarde hors VPS. L’opérateur transfère les artefacts vers une destination chiffrée externe, vérifie le hash après transfert et conserve l’identifiant de la copie hors VPS. [3]

La restauration est exécutée avec :

```bash
ops/deploy-preprod.sh restore /var/backups/smart-ao/smart_ao_<timestamp>.sql.gz
```

Le script vérifie le manifeste voisin lorsqu’il existe, restaure dans une base temporaire, vérifie la présence de tables publiques et de `tenants`, `command_receipts`, `outbox_messages`, puis détruit la base temporaire. Ces contrôles sont nécessaires mais insuffisants pour la preuve métier complète. [3]

L’opérateur doit compléter la restauration par une vérification isolée de :

| Vérification métier | Preuve attendue |
|---|---|
| Échantillon documentaire | Hash avant/après, type d’objet et état sans joindre le document au rapport |
| Isolation tenant | Un tenant A ne lit aucune ligne ni objet du tenant B |
| Outbox | États `PENDING`, `RETRY`, `PUBLISHED`, tentatives et idempotence conservés |
| Audit | Événements d’export et de téléchargement présents et append-only |
| Confidentialité | Aucun montant ou contenu financier inattendu dans les tables collaboratives/webhook |
| Base active | Aucun changement causé par la restauration temporaire |
| Nettoyage | Nom de base temporaire, création et destruction consignés |

## 10. Timers, logs et supervision externe

Les unités `smart-ao-backup.service`, `smart-ao-backup.timer`, `smart-ao-healthcheck.service`, `smart-ao-healthcheck.timer` et `smart-ao-health-alert.service` sont installées sous `/etc/systemd/system/`, puis activées :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now smart-ao-backup.timer
sudo systemctl enable --now smart-ao-healthcheck.timer
systemctl is-enabled smart-ao-backup.timer smart-ao-healthcheck.timer
systemctl is-active smart-ao-backup.timer smart-ao-healthcheck.timer
systemctl list-timers --all | grep smart-ao
```

L’opérateur provoque ou attend une exécution contrôlée, vérifie le journal du dernier lancement et simule une alerte non destructive. Une supervision externe doit détecter l’échec de `/healthz/ready`, l’absence d’exécution d’un timer, l’âge excessif du dernier backup, un conteneur redémarré en boucle et une saturation disque. Aucun simple journal local ne constitue une supervision externe.

## 11. Charge contrôlée et benchmark ZIP

La charge est lancée depuis une machine distincte du VPS. Le mode `--dry-run` est d’abord exécuté. Les documents sont non sensibles, hashés et conservés hors Git. Le benchmark ZIP utilise au moins cinq répétitions froides et cinq chaudes par profil `STORED`, `DEFLATED` niveau 6 et `DEFLATED` niveau 9. La baseline reste `DEFLATED` niveau 6 tant qu’un gain de taille ne justifie pas le coût CPU du niveau 9. [2]

Les paliers de santé et d’export sont progressifs : smoke d’un export, 10 exports séquentiels, 50, 100, puis 10 concurrents et rejeu des mêmes événements. Chaque palier s’arrête si le healthcheck devient instable, si une notification est perdue ou dupliquée, si un champ interdit apparaît, si le backlog ne se résorbe pas, si la mémoire ou le disque sature, ou si un conteneur redémarre.

Le harnais de charge actuellement livré mesure principalement des endpoints GET et produit des rapports sans body. Il ne doit pas être présenté comme une automatisation complète de 100 exports métier tant qu’un scénario d’export authentifié et non sensible n’a pas été préparé. Les exports métier et le contrôle outbox restent une séquence opérateur ou un futur harnais dédié. [2]

## 12. Registre de preuves et décision finale

Le rapport opérateur est stocké hors Git dans un emplacement privé. Il contient uniquement les métadonnées nécessaires :

1. commit, branche, timestamps UTC et identifiant de campagne ;
2. version Docker/Compose, services, digests ou IDs d’images et migrations ;
3. sorties live/ready, TLS, ports, statuts Compose et compteurs de redémarrage ;
4. résultat EICAR, audit d’export, état outbox, retries et preuve d’allowlist webhook ;
5. manifeste corpus et archives avec hashes, sans fichiers documentaires ;
6. backup hors VPS, restauration isolée et contrôles tenant/document/outbox ;
7. état des timers, dernier backup, alerte simulée et supervision externe ;
8. résultats benchmark/charge, p50/p95, ratio ZIP, CPU/RSS/I/O et erreurs ;
9. résumé de logs filtré des secrets et décision finale avec actions correctives.

| Décision | Conditions |
|---|---|
| `ACCEPTÉ` | Tous les contrôles bloquants réussis et toutes les preuves présentes. |
| `CONDITIONNEL` | Aucun incident de sécurité ou de perte de données, mais une preuve non critique ou un contrôle de performance manque avec responsable et échéance. |
| `REFUSÉ` | Fuite, port interne exposé, EICAR accepté, backup non restauré, outbox perdue/doublée, migration non maîtrisée, secret dans les logs ou preuve critique absente. |

## 13. Séquence immédiate avant disponibilité du VPS

Avant le gate réel, les actions de dépôt à prévoir sont : corriger le démarrage explicite de `submission-export-webhook-worker`, ajouter la vérification de santé des deux workers, et étendre la restauration aux contrôles document, tenant et outbox ou documenter un script opérateur séparé. Ces changements doivent être livrés en slices testés, commités, poussés et validés par la CI avant toute exécution distante.

Tant qu’aucun VPS réel n’est disponible, la branche reste dans l’état **préparée mais non validée opérationnellement**. Le prochain jalon de couverture peut avancer indépendamment, mais aucun DNS, URL HTTPS backend ou résultat de charge ne doit être inventé ou fixé dans le frontend avant la preuve d’une URL réelle.

## Références

[1]: VPS_OPERATIONAL_VALIDATION_SPEC.md "Spécification de validation opérationnelle VPS"
[2]: VPS_COMPRESSION_LOAD_EXECUTION_PLAN.md "Plan benchmark ZIP et charge"
[3]: ../ops/README.md "Guide opérateur et limites du template préproduction"
[4]: ../ops/deploy-preprod.sh "Script de déploiement verrouillé"
[5]: ../ops/docker-compose.preprod.yml "Composition Docker préproduction"
[6]: ../ops/backup-preprod.sh "Script de sauvegarde"
[7]: ../ops/restore-preprod.sh "Restauration PostgreSQL isolée"
[8]: ../ops/healthcheck-preprod.sh "Healthcheck HTTPS et dépendances"
[9]: VPS_LOAD_AUTOMATION_PLAN.md "Plan d’automatisation des campagnes VPS"
