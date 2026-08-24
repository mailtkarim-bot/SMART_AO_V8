# SMART_AO V8 — OPTIMIZATION-CAPACITY-01

## 1. Objet

Ce contrat raccorde l’adaptateur OR-Tools CP-SAT à un service applicatif case-scoped de planification de capacités. Il ne crée pas de prix, de marge, de coût, de trésorerie, de décision patronale ni de preuve de dépôt. Le solveur reçoit uniquement des unités entières de demande et de capacité par l’intermédiaire d’un port tenant-scoped.

Le service est volontairement sans persistence dans ce premier slice. Une persistance ultérieure devra définir une version de calcul immuable, les inputs exacts, l’audit, la révision optimiste et les règles de rejeu dans un lot séparé.

## 2. Entrées autorisées

Le port `CaseCapacityInputPort` charge une structure `CaseCapacityPlanInput` pour un `tenant_id` et une `case_id` résolus par le serveur. Elle contient :

| Champ | Règle |
|---|---|
| `tenant_id` | Doit être identique au tenant demandé par le service. |
| `case_id` | Doit être identique à la Case demandée. |
| `demands` | Tuple de `ResourceDemand` à `required_units` entier strictement positif et identifiant unique. |
| `supplies` | Tuple de `ResourceSupply` à `capacity_units` entier strictement positif et identifiant unique. |

Aucun champ monétaire ou texte DCE n’est accepté par ce contrat. Le service rejette les données dont le tenant ou la Case retournés par l’adaptateur ne correspondent pas à la requête.

## 3. Résolution déterministe

`ResourceAssignmentOptimizer` reste l’unique adaptateur OR-Tools. Il utilise CP-SAT, des capacités entières, un timeout borné et un seul worker de recherche. L’ordre fourni des capacités constitue le tie-break stable lorsque plusieurs affectations sont possibles.

La sortie `CaseCapacityPlan` expose uniquement le tenant, la Case, l’identifiant du solveur, le statut fermé `OPTIMAL|FEASIBLE|INFEASIBLE|UNKNOWN|MODEL_INVALID`, les paires demande-capacité et les identifiants non affectés. Une sortie `INFEASIBLE` est conservée comme résultat du calcul et ne déclenche aucun fallback silencieux.

## 4. Frontières d’autorité

Le service ne résout pas d’identité et n’autorise pas un tenant fourni dans un payload HTTP. Un futur adaptateur de données devra obtenir la Case, les qualifications ou les ressources à partir de repositories tenant-scoped et devra appliquer les politiques d’admission métier avant de construire `CaseCapacityPlanInput`.

Le résultat n’autorise pas automatiquement un collaborateur, ne sélectionne pas un scénario pricing et ne publie aucun montant. Tout affichage patronal ou toute persistence nécessite une projection et une capability dédiées, qui ne font pas partie de ce slice.

## 5. Preuves du slice

Les tests couvrent l’appel tenant/Case-scoped au port, le rejet d’une réponse d’adaptateur hors périmètre, la conservation d’un résultat infaisable, le déterminisme et les validations des unités positives et des identifiants uniques. La suite ne prétend pas prouver un gain métier sur un corpus réel : aucune donnée d’entreprise réelle ni capacité issue d’un dossier client n’a été utilisée.

Le raccordement est donc **implémenté et testé comme contrat applicatif**, mais il reste **non persisté et non exposé par HTTP** jusqu’à la définition d’un input métier validé, d’une policy et d’une revue de valeur.
