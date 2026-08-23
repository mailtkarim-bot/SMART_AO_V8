# Recette PostgreSQL locale SMART_AO V8

Le script `scripts/start_local_postgres.sh` démarre ou réutilise un conteneur PostgreSQL 16 local dédié aux tests de persistence. Il utilise par défaut la même image `postgres:16-alpine` digest-pinnée que le Compose de développement, un volume Docker nommé `smart-ao-v8-postgres-data` et le port hôte `5433`. Le port `5433` évite le conflit connu avec l’ancienne base V7 éventuellement exposée sur `5432`.

Le script ne supprime jamais de conteneur ni de volume. Il vérifie les paramètres, crée le volume si nécessaire, démarre le conteneur, attend son healthcheck et n’affiche jamais le mot de passe. Les identifiants par défaut sont réservés au développement local ; pour une machine partagée, ils doivent être remplacés par des variables d’environnement non versionnées.

## Démarrage

Depuis la racine du dépôt :

```bash
scripts/start_local_postgres.sh
```

Le script est idempotent pour son nom de conteneur et son volume. Pour consulter l’état sans afficher de credentials :

```bash
docker ps --filter name=smart-ao-v8-postgres
docker inspect --format '{{.State.Health.Status}}' smart-ao-v8-postgres
```

Pour arrêter le conteneur sans supprimer les données :

```bash
docker stop smart-ao-v8-postgres
```

## Exécution des tests PostgreSQL

Avec les valeurs locales par défaut :

```bash
SMART_AO_TEST_DATABASE_URL='postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5433/smart_ao' \
  uv run pytest -m db
```

Avec un mot de passe personnalisé, la valeur doit rester dans l’environnement du shell ou dans un fichier local ignoré par Git :

```bash
export SMART_AO_TEST_DB_PASSWORD='valeur-locale-non-versionnee'
scripts/start_local_postgres.sh
export SMART_AO_TEST_DATABASE_URL="postgresql+psycopg://smart_ao:${SMART_AO_TEST_DB_PASSWORD}@127.0.0.1:5433/smart_ao"
uv run pytest -m db
```

La recette spécifique BOAMP peut ensuite être exécutée avec une URL fournie hors dépôt :

```bash
SMART_AO_DATABASE_URL="$SMART_AO_TEST_DATABASE_URL" \
  uv run python scripts/recipe_boamp_postgres.py --apply
```

## Variables contrôlées

| Variable | Valeur par défaut | Usage |
|---|---|---|
| `SMART_AO_POSTGRES_CONTAINER` | `smart-ao-v8-postgres` | Nom du conteneur local. |
| `SMART_AO_POSTGRES_VOLUME` | `smart-ao-v8-postgres-data` | Volume persistant isolé. |
| `SMART_AO_POSTGRES_IMAGE` | Image PostgreSQL 16 digest-pinnée | Override explicite pour un environnement contrôlé. |
| `SMART_AO_TEST_DB_NAME` | `smart_ao` | Base créée par l’image officielle. |
| `SMART_AO_TEST_DB_USER` | `smart_ao` | Utilisateur de test. |
| `SMART_AO_TEST_DB_PASSWORD` | `smart_ao` | Mot de passe local ; jamais affiché par le script. |
| `SMART_AO_TEST_DB_PORT` | `5433` | Port exposé sur la machine hôte. |
| `SMART_AO_POSTGRES_WAIT_SECONDS` | `90` | Délai maximal d’attente du healthcheck. |

Le script ne lance pas Alembic et ne modifie pas les données métier. Après son démarrage, les tests ou la recette choisie par l’opérateur restent responsables de l’application des migrations et du nettoyage logique des schémas.

## Limites de preuve

Le script et ses tests CLI sont validés statiquement et avec un faux binaire Docker. Le sandbox de développement ne dispose pas d’un daemon Docker accessible ; aucun conteneur réel n’a donc été créé dans cette session. Une réussite de la recette PostgreSQL ne pourra être déclarée qu’après exécution sur une machine disposant réellement de Docker et PostgreSQL 16.
