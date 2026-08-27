# ARCH-001 — Façade Pricing Scenario Transition

## Objet

Ce micro-lot poursuit l’inversion progressive des dépendances de `pricing/application`. La façade `PricingScenarioTransitionService` autorise les commandes de transition et délègue au dispatcher ; elle ne lit ni n’écrit directement la base de données.

L’argument `session_factory` a été retiré de son constructeur, car il n’était pas utilisé par la façade. La composition root reste le seul endroit qui assemble l’adaptateur SQLAlchemy `SqlAlchemyPricingScenarioReader` et le dispatcher. Le handler `TransitionPricingScenarioHandler` conserve volontairement SQLAlchemy et les modèles persistants pour les verrous, la lecture de la dernière transition append-only, le contrôle de version, la sélection unique et l’écriture des événements.

## Invariants préservés

| Invariant | Preuve attendue |
|---|---|
| Seul un `PATRON_ADMIN` disposant d’un membership peut demander une transition | Contrôle de la façade et test pur de rejet |
| L’autorisation est évaluée avant dispatch | Test de frontière et policy existante |
| La transition est exécutée dans le dispatcher transactionnel | Suite Pricing Transition DB en CI |
| La version attendue et la sélection unique restent contrôlées par le handler | Tests d’intégration existants conservés |
| Aucun accès SQLAlchemy n’est nécessaire pour construire la façade | `test_pricing_transition_facade.py` |

## Fichiers modifiés

`transition_service.py` ne stocke plus de fabrique de session. `bootstrap/application.py` ne transmet plus cette dépendance. La fixture d’intégration est alignée sur le nouveau contrat. Le test de frontière utilise un reader, un dispatcher et une policy minimaux, sans PostgreSQL.

## Limites

Le compteur ARCH-001 reste à **35 fichiers** selon la métrique d’import reproductible. Ce lot réduit une injection inutile dans une façade mais ne sépare pas physiquement le handler ORM du même module ; il ne faut donc pas annoncer une baisse de ce compteur. Les tests DB et la couverture PostgreSQL complète doivent être confirmés par la CI, car PostgreSQL et Docker ne sont pas disponibles dans le sandbox local.

## Validation locale

Le sous-ensemble nouveau et Pricing Transition a passé 2 tests non-DB. La suite backend hors DB a passé **1 113 tests**, avec 477 tests DB désélectionnés. Le frontend a passé le typecheck, le lint, **119 tests Vitest** et le build.
