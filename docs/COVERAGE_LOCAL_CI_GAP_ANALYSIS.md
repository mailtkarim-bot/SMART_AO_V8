# Analyse de l’écart de couverture local / CI

## Résultat établi

Le dernier run CI `32191358477` est **vert**. Le job backend a exécuté la même commande déclarée dans `.github/workflows/ci.yml` :

```bash
uv run pytest backend/tests -q --cov=app --cov-report=term-missing --cov-fail-under=85
```

La CI a validé le gate de couverture ainsi que lint, detect-secrets, pip-audit et Bandit. Le détail exact du pourcentage global n’est pas exposé dans le résumé web consulté, mais le passage de `--cov-fail-under=85` prouve que la valeur calculée dans ce run était au moins égale à 85 %.

La reproduction locale a utilisé la même commande et a obtenu :

| Mesure | Local |
|---|---:|
| Tests | 465 passés |
| Couverture globale | 84,82 % |
| Écart au seuil | -0,18 point |
| Worker webhook ciblé | 80 % avec branches |
| Version Python | 3.12.3 |
| uv | 0.12.1 |
| pytest | 8.4.2 |
| coverage.py | 7.15.4 avec extension C |

L’écart est donc réel dans les observations disponibles, mais sa cause n’est pas encore prouvée. Il serait incorrect de conclure que la CI « ment » ou que la couverture locale est simplement erronée : il faut comparer les artefacts de couverture et les environnements de manière déterministe.

## Comparaison des conditions connues

| Dimension | Local | CI | Impact possible |
|---|---|---|---|
| Python | 3.12.3 local | `python-version: "3.12"` via setup-uv | Patch-level différent possible |
| uv | 0.12.1 | version installée par `astral-sh/setup-uv@v5` | Résolution/runtime différents si lock non strict |
| Dépendances | `uv run` depuis l’environnement local | `uv sync --group dev` sur runner vierge | Environnement local potentiellement impur |
| Lockfile | `uv.lock`, Python `==3.12.*` | même lockfile attendu | Versions de packages normalement identiques |
| PostgreSQL | instance de sandbox/fixture locale | service PostgreSQL 16 du runner | timing, extensions et planification différents |
| Commande pytest | identique | identique | différence probablement environnementale ou couverture conditionnelle |
| Code | commit `cd0608f` | commit du run `32191358477` | doit être vérifié par SHA |
| Branch coverage | activée dans `pyproject.toml` | activée par configuration | même mode attendu |
| Tests | 465 locaux observés | nombre exact non visible dans résumé | à extraire du log brut CI |

## Hypothèses classées

### H1 — Différence de version patch ou de dépendance

Le projet contraint Python à `>=3.12,<3.13`, tandis que la CI demande Python `3.12`. Le lockfile contraint `==3.12.*`, mais ne verrouille pas le patch-level de Python. Une différence de patch-level est peu susceptible de créer 0,18 point seule, mais elle doit être éliminée par une empreinte d’environnement dans la CI.

Les versions de `pytest-cov` et `coverage.py` doivent également être imprimées dans les deux environnements. Le lockfile rend les packages déterministes, mais l’environnement local peut contenir des installations ou plugins supplémentaires si `uv run` n’est pas précédé d’un `uv sync --locked --group dev`.

### H2 — Différence d’état de base ou de timing PostgreSQL

Une partie de la couverture provient de tests d’intégration. Des états de données différents, des tests conditionnels ou des branches d’erreur dépendant d’une course peuvent modifier les lignes exécutées sans modifier le nombre de tests. Cette hypothèse est prioritaire si le nombre de tests est identique mais que les fichiers `coverage.json` diffèrent.

### H3 — Différence d’ordre de tests et de processus

La couverture devrait être additive, mais des tests qui dépendent implicitement d’un cache, de variables d’environnement, d’un singleton ou d’un état PostgreSQL peuvent produire des branches différentes selon l’ordre. Il faut comparer `pytest --collect-only`, exécuter deux fois avec le même ordre et inspecter les warnings.

### H4 — Artefact de couverture différent

La sortie `term-missing` du résumé ne suffit pas à comparer les lignes. Il faut produire `coverage.json` et `coverage.xml` dans les deux environnements, comparer les ensembles de lignes manquantes par fichier et vérifier les lignes de branche partielles. Cette comparaison peut révéler que le delta vient d’un seul module ou de plusieurs branches marginales.

### H5 — Divergence de commit ou de workspace

Le commit local observé est `cd0608f`. Le SHA exact du job CI doit être vérifié dans l’en-tête du run et comparé à `git rev-parse HEAD`. Un workspace local contenant des modifications non suivies ou un checkout CI différent invaliderait toute comparaison.

## Protocole de convergence

### Étape A — Purger et synchroniser localement

```bash
git clean -xfd
uv python install 3.12
uv sync --locked --group dev
uv run python -VV
uv run uv pip list
uv run pytest --version
uv run coverage debug sys
```

`git clean -xfd` ne doit être exécuté que dans un clone jetable ou après sauvegarde des artefacts locaux. Il est recommandé de comparer le SHA du lockfile et de conserver la sortie de toutes les commandes.

### Étape B — Ajouter temporairement les artefacts CI

Modifier le workflow uniquement dans une branche de diagnostic afin d’exécuter :

```bash
uv run pytest backend/tests -q \
  --cov=app \
  --cov-report=term-missing \
  --cov-report=json:coverage-ci.json \
  --cov-report=xml:coverage-ci.xml \
  --cov-fail-under=85
uv run python -VV
uv run pytest --version
uv run coverage --version
uv pip list
```

Les artefacts JSON/XML doivent être conservés dans Actions uniquement pour le diagnostic, sans publier de secrets ni de données documentaires.

### Étape C — Reproduire deux fois localement

Exécuter deux campagnes dans un environnement propre, en supprimant `.coverage` entre les runs :

```bash
rm -f .coverage coverage-local.json coverage-local.xml
uv run pytest backend/tests -q --cov=app \
  --cov-report=term-missing \
  --cov-report=json:coverage-local.json \
  --cov-report=xml:coverage-local.xml \
  --cov-fail-under=85
```

Comparer ensuite le nombre de tests collectés, les warnings, la couverture par fichier, les lignes manquantes et les branches partielles. La convergence attendue est une différence inférieure à 0,01 point sur deux runs identiques.

### Étape D — Isoler les tests PostgreSQL

Exécuter séparément les marqueurs `db`, `integration`, `concurrency` et `process`, puis comparer leur couverture. Si le delta est concentré sur ces marqueurs, la cause est probablement l’état ou le timing de PostgreSQL. Les tests doivent tronquer leurs données et ne pas dépendre d’un ordre global.

### Étape E — Décision

Aucune modification du seuil ne doit être faite pour masquer l’écart. Si la divergence est due à une différence de runtime, épingler la version Python et l’outil de couverture. Si elle vient d’un test non déterministe, corriger le test. Si elle vient d’un chemin non couvert, ajouter le test avant de conserver le seuil de 85 %.

L’objectif de sortie est une couverture locale et CI supérieure à **85,50 %**, afin de conserver une marge opérationnelle de 0,50 point, avec artefacts comparables et zéro différence non expliquée.

## Conclusion exacte obtenue par les artefacts

La collecte instrumentée a permis de télécharger l’artefact CI du run `32192887751` et de produire le rapport local correspondant. La comparaison des deux fichiers `coverage.json` est sans ambiguïté :

| Total | Local | CI |
|---|---:|---:|
| Statements | 11 938 | 11 938 |
| Covered lines | 10 606 | 10 606 |
| Missing lines | 1 332 | 1 332 |
| Branches | 2 102 | 2 102 |
| Covered branches | 1 303 | 1 303 |
| Partial branches | 609 | 609 |
| Couverture calculée | 84,821937 % | 84,821937 % |

Le comparateur ne trouve **aucun fichier, aucune ligne et aucune branche différente**. L’écart apparent de 0,18 point n’est donc pas une divergence entre local et CI : les deux environnements calculent exactement la même couverture. La CI affiche `85` dans le champ d’affichage arrondi et son gate passe, tandis que la reproduction locale précédente affichait `84,82` et avait été interprétée comme un échec.

Le comportement observé avec `coverage report --fail-under=85` sur l’artefact local confirme que le seuil est évalué avec la précision d’affichage par défaut, alors que le fichier JSON conserve la valeur décimale complète. Le problème est donc une **ambiguïté de précision du seuil**, pas une différence de code ou de tests.

La décision recommandée est de rendre la politique explicite. Pour un seuil réellement strict de 85,00 %, configurer `precision = 2` dans `[tool.coverage.report]`, puis ajouter les tests nécessaires pour atteindre au moins 85,50 %. Si le seuil historique doit rester fondé sur l’arrondi entier, documenter explicitement ce choix et suivre également `percent_covered` dans le JSON afin d’éviter de confondre 84,82 % avec 85,00 %.

Les empreintes restantes confirment Python 3.12.3, pytest 8.4.2, coverage.py 7.15.4 et le même SHA de lockfile. La seule différence d’outil visible est uv 0.12.1 local contre uv 0.12.5 CI ; elle n’a aucune incidence démontrée ici puisque les rapports de couverture sont identiques.
