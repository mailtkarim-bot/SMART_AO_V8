# SMART_AO V8 — Recette PostgreSQL du GO conditionnel et garde de soumission

**Date : 24 août 2026**
**Branche : `docs/pricing-http-next-lot-28`**
**Auteur : Manus AI**

## Conclusion exécutive

La recette PostgreSQL réelle n’a pas pu être exécutée dans l’environnement disponible. Le sandbox ne possède ni exécutable PostgreSQL détectable, ni listener TCP sur le port 5432, ni variable `SMART_AO_DATABASE_URL`, ni socket Docker. Cette absence est enregistrée comme une limite d’environnement et non comme une réussite de recette.

En revanche, la tranche applicative est préparée pour cette recette. Le GO conditionnel persiste des conditions `OPEN` dans `decision_conditions` dans la même transaction que la finalisation de la Decision. Les contrôles locaux hors DB sont passés et un garde domaine de soumission a été ajouté afin de ne rendre un futur dépôt admissible que pour une Decision finalisée `GO` ou `CONDITIONAL_GO` dont le contexte est gelé, les exigences DCE confirmées, les conditions satisfaites et les actions de risques résolues.

## Vérification de l’environnement

| Vérification | Observation | Interprétation |
|---|---|---|
| Exécutable `pg_isready` | Absent | Aucun client de sonde PostgreSQL local |
| Listener `:5432` | Aucun | Aucun serveur PostgreSQL local détecté |
| `SMART_AO_DATABASE_URL` | Non définie | Aucune cible de base fournie au sandbox |
| Socket `/var/run/docker.sock` | Absent | Docker de l’ordinateur utilisateur inaccessible depuis ce sandbox |

Aucune migration online, insertion de données, vérification de trigger, test inter-tenant ou validation outbox ne peut donc être honnêtement déclaré ici.

## Recette à exécuter dans un environnement équipé

Une recette réelle devra être lancée avec une URL PostgreSQL dédiée et jetable, après confirmation que la cible est autorisée :

```bash
export SMART_AO_DATABASE_URL='postgresql+psycopg://<user>:<password>@<host>:<port>/<database>'
cd backend
uv run alembic upgrade head
uv run pytest -q -m db backend/tests/application/test_decision_finalization.py
```

La recette devra compléter ces tests ciblés avec un seed contrôlé : tenant A, patron A, Case A, version DCE applicable, contexte Decision gelé, exigences confirmées, risque lié, puis finalisation `CONDITIONAL_GO`. Les assertions minimales sont l’existence des lignes `decisions` et `decision_conditions`, l’état `OPEN`, la révision attendue, les événements/outbox dans la même unité transactionnelle et l’absence de données financières dans le receipt et l’événement.

Un second passage devra tenter l’écriture avec un tenant B, une exigence non confirmée, une ancienne version DCE et une Case étrangère. Chaque cas doit être refusé sans révéler l’existence de la ressource étrangère. Enfin, UPDATE et DELETE sur une condition ou une liaison append-only doivent être refusés par la base, et un replay avec la même clé idempotente doit retourner le receipt canonique.

## Rapprochement DPGF/BPU contrôlé

La préparation livrée expose exclusivement au patron des candidats provenant de lots `COMMITTED` DPGF/BPU de la même Case. La recherche est bornée par code ou désignation et ordonnée de manière déterministe. La projection contient le numéro de ligne, le code, la désignation, l’unité, le type et l’état du lot ainsi que la base de correspondance.

Les colonnes `quantity_decimal`, `unit_price_minor` et `total_minor` ne sont pas sélectionnées par le reader et n’existent pas dans les DTOs publics de cette surface. Le résultat est un candidat de revue, jamais une qualification automatique, une conformité, une marge ou un prix calculé. Les lots non `COMMITTED`, les autres tenants et les autres Cases sont exclus côté adaptateur.

## Garde de soumission préparé

Le domaine `submission_gate.py` centralise les préconditions non financières suivantes :

| Précondition | Effet si absente |
|---|---|
| Decision `FINALIZED` | Blocage `DECISION_NOT_FINALIZED` |
| Issue `GO` ou `CONDITIONAL_GO` | Blocage de `NO_GO` ou d’une issue inconnue |
| Contexte `FROZEN` | Blocage `DECISION_CONTEXT_NOT_FROZEN` |
| Exigences DCE confirmées | Blocage `DCE_REQUIREMENTS_NOT_CONFIRMED` |
| Conditions d’un `CONDITIONAL_GO` satisfaites | Blocage `CONDITIONAL_GO_OPEN_CONDITIONS` |
| Actions de risques résolues | Blocage `UNRESOLVED_RISK_ACTIONS` |

Ce garde est une préparation pour un futur contrôle de soumission. Il ne publie pas de dossier, ne modifie pas le Case et ne décide pas à la place du patron. La décision reste humaine et le garde ne consomme aucun montant financier.

## Validation locale réellement exécutée

| Contrôle | Résultat |
|---|---:|
| Tests backend hors `db` | **971 passed, 458 deselected** |
| Tests ciblés lecture/rapprochement/GO conditionnel/garde | **39 passed, 1 warning** |
| Ruff | Passé |
| mypy Decision/PatronAction/bootstrap | Passé sur 39 fichiers |
| detect-secrets | Passé |
| PostgreSQL online | Non exécuté : service indisponible |
| Docker/VPS/ClamAV/HTTPS | Non exécutés |

Le run GitHub Actions reste séparé de la validation locale : le dernier run connu `32756930349` était queued sans runner et sans étape. Cela ne constitue pas une preuve de CI verte.

## Statut de production

Le statut demeure **NO-GO** pour une mise en production ou un dépôt réel. Le code dispose d’un chemin de recette et de garde-fous supplémentaires, mais la persistence PostgreSQL réelle, l’outbox exécutée, les tests de concurrence, le contrôle opérationnel du dépôt et la validation dans Docker/VPS restent à exécuter sur des environnements effectivement disponibles.
