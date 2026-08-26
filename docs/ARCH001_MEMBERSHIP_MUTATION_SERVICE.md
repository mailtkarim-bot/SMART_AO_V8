# ARCH-001 — Façade mutationnelle membership unique

## Objectif

Le lot ARCH-001 réduit la dépendance des adaptateurs HTTP à plusieurs implémentations mutationnelles membership. Les routes d’affectation patron et collaborateur reçoivent désormais une même façade applicative `MembershipMutationService`.

Cette façade est une **composition explicite**, pas une nouvelle autorité métier. Les services existants `PatronAssignmentManagementService` et `AssignmentInteractionService` restent responsables de leurs contrôles propres : rôle de l’acteur, membership actif, tenant, relation d’affectation, capacité, état métier, révision optimiste, idempotence et dispatch transactionnel.

## Contrat exposé

| Famille | Méthodes | Composant conservant les règles |
|---|---|---|
| Patron | `create`, `amend_scope`, `suspend`, `reactivate`, `end`, `validate_interaction` | `PatronAssignmentManagementService` |
| Collaborateur | `acknowledge`, `clarify`, `report_unavailability` | `AssignmentInteractionService` |

Chaque méthode conserve les paramètres `actor`, `command` et `now`, et retourne le même `DispatchResult`. Les DTO HTTP, les chemins, les réponses, les codes d’erreur, les événements et les tables ne changent pas.

## Câblage

Le bootstrap construit une fois les deux composants role-specific puis les compose dans `MembershipMutationService`. Les deux routeurs assignment reçoivent ensuite la façade. Aucun routeur ne construit ou ne connaît directement l’implémentation de la mutation qui lui est déléguée.

> La façade ne contourne aucune policy et ne prend aucune décision d’autorisation. Elle ne fait que rendre le point d’entrée mutationnel membership unique et testable.

## Sécurité et limites

Le lot ne modifie pas le périmètre d’autorisation. Une requête patron continue d’être contrôlée par la policy patron et le handler patron ; une requête collaborateur continue d’être contrôlée par la policy collaborateur et le handler collaborateur. Les contrôles tenant et membership restent exécutés côté serveur, avant le dispatch.

Le lot ne constitue pas une migration de données et ne requiert pas de migration Alembic. Il ne prétend pas éliminer toute dépendance infrastructurelle des applications membership : il traite uniquement le point d’entrée assignment retenu comme premier incrément ARCH-001, sans changement de contrat métier.

## Validation

La suite unitaire vérifie la délégation des neuf mutations et la conservation exacte des résultats et arguments. Les suites HTTP existantes continuent d’exercer les contrats de routes. Les validations PostgreSQL et la CI complète restent obligatoires avant fusion.
