# État du gate staging SMART_AO V8

**Date de collecte :** 2026-08-20 UTC  
**Commit main contrôlé :** `8e62c5d`  
**Environnement de collecte :** sandbox Linux Manus, sans Docker installé  
**Décision :** **NO-GO staging réel / production**

## Synthèse opératoire

Le contrôle statique du template staging est **PASS**. Les services attendus, le réseau privé, les healthchecks, les ports edge et les digests d’images ont été vérifiés par `scripts/simulate_staging_deploy.sh --static-only`.

Le gate Docker réel n’est pas exécutable dans cet environnement : la commande `docker` est absente. En conséquence, aucun build, pull, démarrage Compose, PostgreSQL, ClamAV, Caddy, migration Alembic, test EICAR, vérification HTTPS, backup ou restauration n’est déclaré comme réalisé. Cette limitation maintient la décision **NO-GO** conformément au plan de recette.

## Preuves collectées

| Contrôle | Résultat | Preuve ou limite |
|---|---|---|
| Présence du main contrôlé | PASS | `8e62c5d` |
| Structure Compose staging | PASS | `scripts/simulate_staging_deploy.sh --static-only` |
| Réseau interne et ports edge | PASS statique | Vérification textuelle du Compose ; pas de socket Docker disponible |
| Workers attendus | PASS statique | `dce-retention-worker` et `submission-export-webhook-worker` détectés |
| Healthchecks | PASS statique | Présence vérifiée dans le Compose |
| Digests Docker | PASS statique | Dockerfiles et Compose vérifiés par le simulateur |
| Résolution `docker compose config` | NON EXÉCUTÉE | Docker absent : `docker is required for --compose-config` |
| Build et lancement des images | NON EXÉCUTÉS | Docker absent |
| PostgreSQL et tête Alembic | NON EXÉCUTÉS | Aucun conteneur staging disponible |
| ClamAV et EICAR | NON EXÉCUTÉS | Aucun conteneur staging disponible |
| HTTPS Caddy et `/healthz/ready` | NON EXÉCUTÉS | Aucun hostname staging réel fourni |
| Backup/restauration isolée | NON EXÉCUTÉS | Aucun environnement staging réel disponible |

## Commandes de reprise sur une machine Docker

À exécuter depuis une copie propre de `main`, avec un fichier `ops/.env.preprod` staging en mode `0600` et des valeurs non placeholders :

```bash
cd SMART_AO_V8
chmod 600 ops/.env.preprod
bash -n ops/deploy-preprod.sh ops/healthcheck-preprod.sh ops/backup-preprod.sh ops/restore-preprod.sh
bash scripts/simulate_staging_deploy.sh --static-only
bash scripts/simulate_staging_deploy.sh --compose-config
ops/deploy-preprod.sh config
ops/deploy-preprod.sh deploy 2>&1 | tee "artifacts/deploy-$(date -u +%Y%m%dT%H%M%SZ).log"
ops/deploy-preprod.sh smoke
ops/deploy-preprod.sh healthcheck
```

Après le démarrage, l’opérateur doit exécuter l’intégralité de `docs/STAGING_POST_DEPLOYMENT_ACCEPTANCE_PLAN.md`, notamment la vérification de la tête Alembic `20260818_0047`, le test EICAR, l’upload sain en quarantaine, le smoke pricing/submission, l’état des workers, le backup horodaté et la restauration isolée. Le rapport final doit contenir les hashes, l’échantillon documentaire non sensible, le contrôle tenant, l’état outbox, les logs filtrés et la preuve de rotation des secrets.

## Règle de décision

Le statut ne pourra devenir **PASS** qu’après démonstration de tous les critères de sortie du plan staging. Un résultat statique ne remplace pas la preuve d’exécution Docker réelle. Tant que Docker, un environnement non productif et un hostname HTTPS staging ne sont pas disponibles, aucune migration de production ni configuration `VITE_API_BASE_URL` backend ne doit être activée.
