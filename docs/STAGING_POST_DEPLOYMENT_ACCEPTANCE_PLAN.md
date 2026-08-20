# Plan de recette post-déploiement — Staging Docker SMART_AO V8

**Version :** 1.0  
**Périmètre :** `main` après fusion des PR #12, #17, #18, #19 et #20  
**Objectif :** fournir une preuve opératoire reproductible du staging final sans exposer de secret ni exécuter de downgrade automatique.

## 1. Préconditions et responsabilités

La recette doit être exécutée sur une machine Docker dédiée au staging, ou sur le VPS de préproduction, avec Docker Compose v2, `curl`, `openssl`, `jq`, `sha256sum`, `systemd` si les timers sont inclus, et un accès réseau contrôlé. Elle ne doit utiliser aucune base de production ni aucun secret de production.

L’opérateur prépare un fichier `ops/.env.preprod` local, de mode `0600`, à partir de `.env.preprod.example`. Les valeurs doivent être non placeholders et spécifiques au staging : hôte public de recette, `SMART_AO_DATABASE_URL`, clés JWT, issuer/audience, identifiants PostgreSQL et paramètres Caddy. Le fichier ne doit jamais être commité ni copié dans les artefacts CI.

Avant exécution, l’opérateur capture le commit déployé, le digest de chaque image, la version Docker Compose, la version Alembic attendue et l’horodatage UTC. Un second opérateur valide le périmètre et le caractère non productif de l’environnement.

## 2. Validation de configuration avant démarrage

Exécuter :

```bash
chmod 600 ops/.env.preprod
bash -n ops/deploy-preprod.sh ops/healthcheck-preprod.sh ops/backup-preprod.sh ops/restore-preprod.sh
ops/deploy-preprod.sh config
```

Le résultat attendu est une configuration Compose résolue sans erreur, avec toutes les images référencées par digest SHA-256. Le contrôle doit confirmer que les services `postgres`, `clamav`, `backend`, `frontend`, `caddy`, `dce-retention-worker` et `submission-export-webhook-worker` sont présents. Les ports publics doivent être limités à Caddy ; PostgreSQL et ClamAV doivent rester sur le réseau interne.

Archiver la sortie de `docker compose config`, la liste des images et le résultat de `caddy validate`. Toute image sans digest, tout placeholder, tout secret imprimé dans un log ou tout port interne publié constitue un échec bloquant.

## 3. Déploiement contrôlé

Exécuter uniquement après validation de la configuration :

```bash
ops/deploy-preprod.sh deploy 2>&1 | tee "artifacts/deploy-$(date -u +%Y%m%dT%H%M%SZ).log"
```

Le script doit tirer les images externes digest-pinnées, construire les images applicatives, démarrer PostgreSQL et ClamAV, attendre leurs healthchecks, créer ou vérifier le backup préalable, appliquer `alembic upgrade head`, puis démarrer backend, workers, frontend et Caddy.

L’opérateur ne doit pas définir `SMART_AO_ALLOW_EMPTY_BACKUP=1` sauf pour une première base explicitement approuvée et documentée. En cas d’échec, aucune commande `alembic downgrade` ne doit être lancée automatiquement. Conserver les logs, le backup et l’état des conteneurs avant toute décision de reprise.

## 4. Vérification des conteneurs et de la migration ORM

Exécuter :

```bash
docker compose --env-file ops/.env.preprod -f ops/docker-compose.preprod.yml ps
docker compose --env-file ops/.env.preprod -f ops/docker-compose.preprod.yml exec -T backend alembic current
docker compose --env-file ops/.env.preprod -f ops/docker-compose.preprod.yml exec -T backend alembic heads
docker compose --env-file ops/.env.preprod -f ops/docker-compose.preprod.yml exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\dt'
```

Le résultat attendu est une seule révision courante égale à `20260818_0047`, correspondant à la tête Alembic publiée. La migration doit atteindre PostgreSQL via `SMART_AO_DATABASE_URL`, et non via `127.0.0.1` du conteneur backend.

Vérifier la présence des tables Enterprise (`enterprise_companies`, `enterprise_documents`, `enterprise_document_uploads`, `enterprise_document_verifications`), des tables pricing (`pricing_scenarios`, `pricing_import_batches`, `pricing_import_rows`, `pricing_import_transitions`) et des registres transverses (`command_receipts`, `outbox_messages`). Vérifier les triggers append-only et les contraintes tenant-scopées des tables immuables.

## 5. Readiness et sécurité réseau

Exécuter :

```bash
ops/deploy-preprod.sh smoke
ops/deploy-preprod.sh healthcheck
curl --fail --silent --show-error "https://${SMART_AO_PUBLIC_HOST}/healthz/live"
curl --fail --silent --show-error "https://${SMART_AO_PUBLIC_HOST}/healthz/ready"
```

Le certificat HTTPS doit correspondre au hostname staging, être valide et ne pas utiliser un certificat de développement exposé par erreur. `/healthz/live` doit confirmer que le processus répond ; `/healthz/ready` doit confirmer la disponibilité des dépendances nécessaires.

Compléter avec une inspection des ports exposés :

```bash
docker compose --env-file ops/.env.preprod -f ops/docker-compose.preprod.yml port postgres 5432
docker compose --env-file ops/.env.preprod -f ops/docker-compose.preprod.yml port clamav 3310
```

Les commandes de publication PostgreSQL et ClamAV ne doivent retourner aucun endpoint public. Un résultat vide ou une erreur indiquant qu’aucun port n’est publié est attendu.

## 6. Test ClamAV EICAR et stockage privé

Créer le fichier EICAR uniquement dans le répertoire temporaire du staging, jamais dans un volume de production :

```bash
printf '%s' 'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*' > /tmp/eicar.com
```

Le test attendu est le rejet par ClamAV et le maintien du fichier en quarantaine ou sa suppression selon la politique configurée. Aucun document infecté ne doit atteindre une projection publique ni une table `enterprise_documents` validée. Archiver le verdict, le code de rejet, le timestamp et le hash du fichier de test, puis supprimer le fichier temporaire.

Créer ensuite un petit document non sensible de test. Vérifier le parcours upload privé, le calcul du hash, le verdict `CLEAN`, le statut `PENDING` et la séparation entre upload technique et décision humaine. Ne jamais utiliser un vrai Kbis, RIB ou certificat d’assurance dans cette recette.

## 7. Smoke métier pricing et submission

Avec un compte patron de staging et une affaire de test, vérifier que les scénarios pricing restent privés, que le tenant est résolu côté serveur et que le receipt de commit ne contient aucun montant. Rejouer la même commande avec la même clé d’idempotence et confirmer l’absence de duplication.

Vérifier les trois comportements frontend intégrés : le second clic est bloqué pendant le commit, un commit confirmé suivi d’un échec de reload affiche un avertissement distinct, et le changement de contexte remet l’état visuel à `IDLE`.

Préparer un paquet de soumission non sensible, effectuer un export contrôlé et vérifier l’audit d’export, l’outbox et le worker `submission-export-webhook-worker`. Les webhooks de recette ne doivent contenir ni prix, ni marge, ni montant financier.

## 8. Outbox, workers et observabilité

Vérifier que les deux workers sont `running` et `healthy`, que les événements attendus sont consommés sans duplication et que les erreurs sont corrélées par `command_id`, `idempotency_key` et `correlation_id`. Les logs doivent exclure les tokens, mots de passe, clés JWT, documents binaires et données financières interdites.

Contrôler les compteurs de l’outbox avant et après un événement contrôlé. Un rejeu doit être idempotent et ne doit pas créer une seconde transition append-only. Archiver les logs structurés, le statut des workers et l’échantillon de messages anonymisés.

## 9. Backup, restauration et preuve de reprise

Avant tout test destructif contrôlé, exécuter :

```bash
ops/deploy-preprod.sh backup
```

Conserver le backup PostgreSQL, les archives de volumes privés et les fichiers de hash. Exécuter ensuite la restauration dans une instance PostgreSQL isolée :

```bash
ops/deploy-preprod.sh restore /path/to/backup.sql.gz
```

La restauration doit vérifier le checksum, la cohérence du schéma, l’isolation du tenant de test, la présence des registres outbox et la lisibilité d’un échantillon documentaire non sensible. L’environnement isolé doit être supprimé après collecte des preuves.

## 10. Critères de sortie

La recette est **PASS** seulement si toutes les lignes suivantes sont démontrées :

| Domaine | Critère de sortie |
|---|---|
| Images | Tous les services déployés avec les digests attendus |
| Migration | `alembic current` atteint l’unique head `20260818_0047` |
| PostgreSQL | Healthcheck vert, tables et contraintes attendues présentes |
| ClamAV | EICAR rejeté, document sain accepté en quarantaine puis `CLEAN` |
| HTTPS | Certificat valide, live et ready accessibles |
| Réseau | PostgreSQL et ClamAV non publiés |
| Pricing | Idempotence, révision optimiste et confidentialité financière vérifiées |
| Submission | Export, audit et worker webhook vérifiés sans donnée financière webhook |
| Backup | Backup horodaté, hashé et restauration isolée réussie |
| Observabilité | Logs sans secret, corrélations et erreurs exploitables |

Un seul échec bloquant laisse le staging en état **REJECTED**. L’opérateur conserve les logs et le backup, n’effectue pas de downgrade automatique, ouvre un ticket correctif et planifie une nouvelle fenêtre de recette.

## 11. Dossier de preuves à conserver

Le dossier final doit contenir le commit et les digests déployés, la sortie Compose résolue, les logs de déploiement, `alembic current` et `heads`, l’état des conteneurs, les résultats live/ready, le verdict EICAR, les checksums de backup, le rapport de restauration isolée, les états outbox/workers, les logs filtrés et la validation de rotation des secrets. Aucune valeur secrète en clair ne doit figurer dans ce dossier.

## Références

[1]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/main/ops/README.md "Documentation opérateur SMART_AO V8"
[2]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/main/ops/deploy-preprod.sh "Script de déploiement préproduction"
[3]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/main/ops/docker-compose.preprod.yml "Compose préproduction digest-pinné"
[4]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/main/backend/alembic/env.py "Configuration Alembic runtime"
