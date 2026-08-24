# Recette CI et PostgreSQL Docker — 24 août 2026

## Résultat

La vérification n’a pas confirmé le démarrage d’un runner GitHub Actions et la simulation PostgreSQL Docker n’a pas pu être lancée dans le sandbox. Ces deux limites sont techniques et observées directement ; aucune exécution inexistante n’est présentée comme une preuve.

## GitHub Actions

Le dernier run de la branche `docs/pricing-http-next-lot-28` est le run [`32761180934`](https://github.com/mailtkarim-bot/SMART_AO_V8/actions/runs/32761180934), associé au commit `8798f36`. Son état final est `failure`. Les trois jobs `backend`, `frontend` et `image-security` sont terminés avec `runnerName: null` et zéro étape exécutée. La récupération des journaux échoue également avec `log not found`, ce qui est cohérent avec l’absence de runner et de steps, et non avec un échec de test identifiable.

| Job | État | Runner | Étapes | Conclusion exploitable |
|---|---|---|---:|---|
| backend | completed | `null` | 0 | Aucun test CI exécuté |
| frontend | completed | `null` | 0 | Aucun build CI exécuté |
| image-security | completed | `null` | 0 | Aucun scan CI exécuté |

La CI ne peut donc pas être qualifiée de verte. Aucun rerun n’est présenté comme utile tant qu’un runner exécutable n’est pas effectivement attribué.

## Docker et PostgreSQL

Dans le sandbox, `docker` est absent du `PATH`, et il n’existe donc aucune possibilité de créer un conteneur PostgreSQL éphémère depuis cet environnement. Cette constatation confirme que le Docker installé sur l’ordinateur de l’utilisateur n’est pas accessible depuis le sandbox.

La migration peut être contrôlée hors ligne, mais ce contrôle ne crée aucune table réelle et n’exécute aucun seed. Le script de recette à exécuter sur une machine équipée devra fournir une URL PostgreSQL jetable, démarrer un conteneur PostgreSQL, attendre son healthcheck, appliquer `alembic upgrade head`, puis lancer le seed et les assertions d’intégrité.

## Seed contrôlé attendu

Le seed de recette doit créer un tenant patronal, une Case, une version DCE applicable, une exigence confirmée par un humain, un risque sourcé, une liaison risque–exigence, une Decision au contexte `FROZEN`, puis une finalisation `CONDITIONAL_GO` avec conditions explicites. Les assertions doivent vérifier la persistence des conditions à l’état `OPEN`, l’événement et l’outbox dans la même transaction, l’idempotence, les FKs composites, l’append-only et le refus des ressources d’un autre tenant.

Le seed ne doit jamais utiliser une qualification issue d’un fragment non vérifié. Il ne doit pas publier `quantity_decimal`, `unit_price_minor` ou `total_minor` dans les projections de rapprochement ou les événements de cette surface.

## Validation locale disponible

Le dernier gate hors DB reste **971 tests passés et 458 désélectionnés**. Les contrôles Ruff, mypy ciblé et detect-secrets ont passé. La migration Alembic a déjà été générée en SQL offline jusqu’à `20260824_0059`. Ces résultats sont des preuves locales de code et de génération SQL, pas une preuve de persistence PostgreSQL.

## Conclusion opérationnelle

Le statut reste **non validé pour PostgreSQL réel et non validé pour CI**. L’action requise est de rendre accessible une machine possédant Docker et PostgreSQL, ou de fournir un runner GitHub réellement exécutable, puis de rejouer la recette décrite ci-dessus avec conservation des journaux, du hash de migration et des résultats d’assertions.
