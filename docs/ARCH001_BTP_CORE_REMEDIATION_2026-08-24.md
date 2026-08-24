# Remédiation ARCH-001 et cœur métier BTP — état du 24 août 2026

## Objet

Ce document décrit le lot de codage engagé après la demande de traiter en priorité la dette d’architecture **ARCH-001** et le cœur métier BTP. Le lot reste volontairement incrémental : il ne prétend pas transformer en une seule livraison un produit AO complet, et il ne présente pas comme validées les recettes qui nécessitent PostgreSQL online, Docker, un fournisseur réel ou un environnement externe.

## ARCH-001 — tranche livrée

La première tranche cible les lectures membership qui avaient un contrat applicatif déjà disponible mais construisaient directement leur adaptateur SQLAlchemy dans la couche application.

`PatronAssignmentCockpitService` et `AssignmentHistoryService` ne connaissent désormais plus leurs classes `SqlAlchemy...Reader`. Ils consomment respectivement `PatronAssignmentCockpitReader` et `AssignmentHistoryReader`, via une factory de session/reader injectée. La composition root est l’unique endroit qui assemble ces ports avec les adaptateurs SQLAlchemy. Les projections restent des dataclasses fermées et ne contiennent aucune donnée financière.

Un test d’architecture vérifie que ces deux services n’importent ni SQLAlchemy ni un module `.infrastructure`. Cette règle est une protection contre la réintroduction de la dette ; elle ne prétend pas encore avoir supprimé toutes les arêtes historiques de ARCH-001.

Le narrowing de `assignment_id` dans le service collaborateur a également été corrigé pour rétablir le gate mypy sans modifier les contrôles tenant/membership.

## Cœur métier BTP — COST-BASIS-01 livré

Le bounded context `pricing` possède désormais un value object pur `CostBasisInput`/`CostBasisResult` et la fonction `calculate_cost_basis`. Le calcul couvre les coûts directs, frais généraux, sous-traitance, contingence, réserves de pénalités, retenues et garanties, ainsi que la marge brute, le seuil de rentabilité, le prix plancher et le prix cible.

Les montants restent des entiers en unités mineures de devise et les taux sont en points de base. Le prix minimal est calculé avec une division entière plafonnée. Les entrées négatives, booléennes, taux hors bornes et taux plancher supérieurs au taux cible sont refusés.

Le calcul est raccordé au handler de création des scénarios pricing. Les réserves et seuils sont persistés dans `pricing_scenarios` par la migration additive `20260824_0057`. Des contraintes PostgreSQL garantissent la positivité des réserves et seuils ainsi que la cohérence des taux. La route HTTP pricing propage ces champs dans un DTO fermé patronal. Une erreur de validation COST-BASIS devient `INVALID_COST_BASIS` plutôt qu’une erreur serveur générique.

Ce slice ne calcule pas automatiquement un prix de marché, ne diagnostique pas un risque juridique CCAP et ne prend pas une décision GO/NO-GO. Il fournit une base déterministe et révisable au parcours patronal ; les hypothèses doivent rester justifiées et validées par le patron.

## Validation locale

| Contrôle | Résultat |
|---|---:|
| Suite backend hors `db` | **915 passed, 458 deselected** |
| Tests architecture + pricing + cockpit | **31 passed** dans la dernière cible dédiée |
| Ruff backend/scripts | Passé |
| Mypy membership/pricing/public | Passé sur 32 fichiers |
| Scripts shell | Passé avec `bash -n` |
| Migration Alembic | SQL offline rendu jusqu’au head `20260824_0057` |
| PostgreSQL online | Non disponible dans le sandbox ; non revendiqué |
| Docker/VPS/fournisseurs externes | Non revendiqués |

Les warnings restants sont des warnings tiers FastAPI/Starlette dans la suite backend. Aucune donnée financière n’a été ajoutée aux contrats collaborateur.

## Prochaines tranches nécessaires

ARCH-001 doit continuer bounded context par bounded context. Les prochaines cibles à traiter sont les services membership mutationnels, puis les services pricing/decision qui accèdent encore directement aux modèles ORM. Chaque extraction doit introduire un snapshot ou un port explicite, conserver le root transactionnel du dispatcher et être couverte par un test de frontière et un test de concurrence adapté.

Le cœur métier BTP reste à compléter avec le croisement structuré CCAP–CCTP–DPGF–BPU, l’analyse des risques et exigences, l’OCR/corpus Golden, la bibliothèque de qualifications et références, la génération DC1/DC2/DC4, la décision GO/NO-GO complète et le parcours de dépôt. Ces capacités ne seront déclarées finalisées qu’avec leurs contrats, persistence, contrôles tenant, revue humaine et tests correspondants.

La preuve PostgreSQL online est obligatoire pour la migration `0057`, les contraintes, l’idempotence et les scénarios concurrentiels. Le sandbox courant ne permet pas de la fabriquer.
