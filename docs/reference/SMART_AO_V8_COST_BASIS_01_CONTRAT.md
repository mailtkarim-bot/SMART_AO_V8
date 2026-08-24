# COST-BASIS-01 — Contrat du coût de revient et du prix plancher

## Objet

Ce slice ajoute un calcul déterministe, patronal et financier privé au bounded context `pricing`. Il calcule le coût de revient complet d’un scénario, le seuil de rentabilité, le prix plancher selon une marge minimale et le prix cible selon la marge visée.

Le calcul est pur : il ne connaît ni FastAPI, ni SQLAlchemy, ni tenant runtime, ni fournisseur externe. La commande qui l’utilise reste autorisée uniquement à un acteur patronal et la lecture reste couverte par la classification `FINANCIAL_PRIVATE`.

## Unité et arithmétique

Tous les montants sont des entiers en unités mineures de devise, par exemple centimes d’euro. Les taux de marge sont des points de base : `1 000 bps = 10 %`. Aucun `float`, arrondi implicite ou conversion monétaire non déterministe n’est accepté.

Le coût total est :

```text
coût total = coûts directs
           + frais généraux
           + sous-traitance
           + contingence
           + réserve pénalités
           + réserve retenues
           + réserve garanties
```

La marge brute est `ventes - coût total`. Le prix minimal garantissant un taux de marge `r` est calculé par division entière avec plafond :

```text
prix minimal = ceil(coût total × 10 000 / (10 000 - r))
```

`r` est borné à `[0, 9 999]` bps. Le taux plancher ne peut pas dépasser le taux cible.

## Persistence et idempotence

Les sorties COST-BASIS sont persistées sur `pricing_scenarios` par la migration `20260824_0057`. Les nouvelles colonnes sont additives, non nulles et initialisées à zéro pour les scénarios historiques. Elles ne remplacent aucun scénario et ne modifient aucun historique de transition.

La création de scénario continue d’utiliser la transaction root existante du dispatcher, la clé d’idempotence et le contrôle du snapshot financier `PUBLISHED`. Le snapshot source est sélectionné avec le tenant et le `case_id`. Une autre tenant ou un snapshot non publié ne peut pas alimenter un scénario.

## Champs privés

Les réserves, coûts, marges, seuils et prix cibles sont exclusivement patronaux. Ils ne doivent apparaître dans un contrat collaborateur, une projection collaborateur, un événement collaborateur, un log applicatif ou une notification non autorisée.

## Hors périmètre

Ce slice ne prétend pas calculer automatiquement un prix de marché, un risque juridique CCAP, une trésorerie réelle, une marge fournisseur ou une décision GO/NO-GO. Il ne remplace pas la validation humaine. Les taux et réserves sont des entrées patronales qui doivent être justifiées dans le scénario et revues avant sélection ou dépôt.

## Validation

Les tests unitaires couvrent les réserves, la division avec plafond, les limites de taux et le refus des valeurs négatives/booléennes. La migration est rendue en SQL offline dans le sandbox. La persistence PostgreSQL online et le parcours Docker doivent être rejoués dans un environnement disposant de PostgreSQL/Docker ; ils ne sont pas prétendus validés localement sans cette preuve.
