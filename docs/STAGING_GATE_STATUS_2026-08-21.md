# État du gate staging SMART_AO V8 — 2026-08-21

**Commit main contrôlé :** `a72b6bf` — fusion de la PR #36 EnterpriseLibraryPanel.  
**Environnement de collecte :** sandbox Linux Manus.  
**Décision :** **NO-GO staging réel / production**.

## Synthèse opératoire

Le contrôle statique du template staging est **PASS**. `scripts/simulate_staging_deploy.sh` confirme la structure Compose, le réseau privé, les workers attendus, les healthchecks, les ports edge et la présence des digests Docker. La simulation a été exécutée sans secrets, sans build, sans pull et sans démarrage de service.

Le gate Docker réel reste **non exécutable** dans cet environnement : la commande `docker` est absente (`bash: docker: command not found`). Aucun build d’image, `docker compose config`, lancement PostgreSQL/ClamAV/Caddy, migration Alembic, test EICAR, vérification HTTPS, backup ou restauration n’est déclaré réalisé. Le résultat statique ne remplace pas la preuve d’exécution demandée par le plan de recette.

## État logiciel contrôlé

| Élément | Résultat | Preuve |
|---|---|---|
| Main contrôlé | PASS | `a72b6bf` |
| Tests frontend locaux | PASS | 53 tests dans 13 fichiers |
| Build frontend strict | PASS | TypeScript strict + Vite |
| CI de la PR #36 | PASS | Run `32474338731` : backend, frontend, image-security |
| Simulation staging | PASS statique | `scripts/simulate_staging_deploy.sh` |
| Docker Engine | BLOQUANT | commande `docker` absente |
| `docker compose config` | NON EXÉCUTÉ | aucun moteur Docker |
| PostgreSQL et Alembic | NON EXÉCUTÉS | aucun conteneur réel |
| ClamAV et EICAR | NON EXÉCUTÉS | aucun conteneur réel |
| HTTPS Caddy et `/healthz/ready` | NON EXÉCUTÉS | aucun hostname staging réel |
| Backup/restauration isolée | NON EXÉCUTÉS | aucun environnement staging réel |

## Reprise sur l’ordinateur Docker de l’utilisateur

Depuis une copie propre de `main`, avec un fichier `ops/.env.preprod` staging en mode `0600`, des digests inchangés et des valeurs non placeholders :

```bash
cd SMART_AO_V8
git fetch origin main
git switch --detach origin/main
chmod 600 ops/.env.preprod
bash -n ops/deploy-preprod.sh ops/healthcheck-preprod.sh ops/backup-preprod.sh ops/restore-preprod.sh
bash scripts/simulate_staging_deploy.sh --static-only
bash scripts/simulate_staging_deploy.sh --compose-config
ops/deploy-preprod.sh config
ops/deploy-preprod.sh deploy 2>&1 | tee "artifacts/deploy-$(date -u +%Y%m%dT%H%M%SZ).log"
ops/deploy-preprod.sh smoke
ops/deploy-preprod.sh healthcheck
```

Après le démarrage, l’opérateur doit exécuter intégralement `docs/STAGING_POST_DEPLOYMENT_ACCEPTANCE_PLAN.md`. Les preuves attendues sont les hashes d’images et de manifests, la tête Alembic, le test EICAR, un upload sain en quarantaine, les smoke tests pricing/submission, l’état des workers, le backup horodaté, la restauration isolée, le contrôle tenant, l’état outbox, les logs filtrés et la rotation des secrets.

## Règle de décision

Le statut ne pourra devenir **PASS** qu’après démonstration de tous les critères de sortie du plan staging sur un hôte Docker réel et avec une URL HTTPS backend réelle. Tant que ces éléments ne sont pas fournis, aucune configuration `VITE_API_BASE_URL` backend ni migration de production ne doit être activée.
