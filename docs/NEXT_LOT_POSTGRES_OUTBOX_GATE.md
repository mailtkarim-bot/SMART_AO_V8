# Prochain lot — Gate PostgreSQL 0051–0054 et worker outbox

## Objectif

Obtenir une preuve d’exécution réelle de la chaîne PostgreSQL `0051` à `0054`, de la persistence BOAMP et du worker outbox BOAMP, sans modifier les invariants ni introduire de fournisseur externe fictif.

## Préconditions

L’opérateur doit disposer de Docker et lancer PostgreSQL 16 via `scripts/start_local_postgres.sh`. Le service doit être accessible sur `127.0.0.1:5433` avec une URL fournie hors dépôt dans `SMART_AO_DATABASE_URL` et `SMART_AO_TEST_DATABASE_URL`. Aucun mot de passe ne doit être écrit dans Git, les logs persistés ou les rapports.

## Séquence d’exécution

```bash
scripts/start_local_postgres.sh

export SMART_AO_TEST_DATABASE_URL='postgresql+psycopg://<user>:<password>@127.0.0.1:5433/<database>'
export SMART_AO_DATABASE_URL="$SMART_AO_TEST_DATABASE_URL"

uv run alembic -c backend/alembic.ini upgrade 20260823_0054
uv run pytest -q backend/tests/infrastructure/test_boamp_observation_persistence.py \
  backend/tests/infrastructure/test_boamp_qualification_persistence.py \
  backend/tests/process/test_opportunity_event_bus_persistence.py
uv run python scripts/recipe_boamp_postgres.py --apply
```

La migration doit produire `alembic_version=20260823_0054`. La recette doit vérifier les quatre tables BOAMP et leurs triggers append-only, puis exécuter les trois suites de tests.

## Critères de succès

| Contrôle | Preuve attendue |
|---|---|
| Migration | Révision PostgreSQL `20260823_0054` et absence d’erreur Alembic. |
| Persistence observation | Création, rejeu idempotent, conflit de hash et outbox unique. |
| Qualification | Création, rejeu, event/outbox unique et mutation refusée par trigger. |
| Worker après ack | Message `PENDING` publié vers l’adaptateur de test, puis `PUBLISHED`. |
| Worker en panne | Message conservé en `RETRY`, compteur et échéance de backoff renseignés. |
| Isolation | Les requêtes et seeds restent tenant-scoped ; aucun payload riche ou financier. |
| Recipe | Verdict JSON sans DSN, password, token, titre ou contenu sensible. |

## Étape bus fournisseur séparée

Après la réussite PostgreSQL, le fournisseur bus doit encore fournir son endpoint HTTPS, son mécanisme d’authentification, ses codes `2xx`/erreurs, sa déduplication par `event_id`, sa conservation et sa stratégie de replay. La recette fournisseur est ensuite exécutée sur deux événements synthétiques non sensibles. Elle ne doit pas être confondue avec la validation locale de `InMemoryExternalEventBus`.

## État actuel

Dans le sandbox du 23 août 2026, la validation Alembic offline jusqu’à `0054` réussit et le nouveau test worker est collectable, mais la migration online et les trois tests PostgreSQL sont bloqués par `connection refused` sur `127.0.0.1:5433`; Docker n’est pas installé. Le lot est donc **codé et prêt à exécution**, mais non validé online.
