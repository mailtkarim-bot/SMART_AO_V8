# Stabilisation CI — 2026-08-21

## Résultat

Le run main `32480225089` a détecté une régression réelle dans `test_patron_assignment_reactivation_returns_closed_receipt_and_replays` : la fixture utilisait une affectation terminant le **21 août 2026 à 12:00 UTC**, tandis que le job CI a exécuté le scénario après cette échéance. Le service a correctement refusé la réactivation par `422`; c’est la fixture qui dépendait de l’horloge réelle.

La PR #40 corrige cette dépendance en utilisant une fenêtre fixe et déterministe du `1er janvier 2020` au `31 décembre 2099`. Le comportement métier n’est pas assoupli : la route continue de contrôler côté serveur l’état `SUSPENDED`, la révision optimiste, l’état de la Case, la cible collaborateur et la fenêtre d’accès.

## Correction de migration

Le test ciblé a également révélé qu’un downgrade de `20260814_0023` tentait de réintroduire une contrainte ne contenant pas les motifs de réactivation déjà écrits dans le journal append-only. La migration conserve désormais le catalogue étendu pendant le downgrade. Ce choix est non destructif : les lignes immuables ne sont ni supprimées ni réécrites pour satisfaire artificiellement une ancienne contrainte.

## Preuves

| Contrôle | Résultat |
|---|---|
| Test API ciblé de réactivation | PASS — 1 scénario |
| Suite API affectations/interactions locale | PASS — 37 scénarios |
| `alembic upgrade head` | PASS — tête `20260818_0047` |
| `alembic check` | PASS |
| Ruff et diff | PASS |
| CI PR #40 `32481205940` | PASS — backend, frontend, image-security |
| CI main après fusion `32481773297` | PASS — backend, frontend, image-security |

Le main contrôlé après fusion est `52b906d`.
