# ARCH-001 — Découplage de la façade Pricing Scenario

## Objet

Ce micro-lot retire l’argument `session_factory` inutilisé de `PricingScenarioService`. La façade applicative consommait déjà `PricingScenarioReader` pour ses lectures, `CommandDispatcher` pour ses écritures et `AuthorizationPolicyPort` pour l’autorisation. Conserver un session factory dans cette façade entretenait une dépendance infrastructurelle sans usage.

Le handler `PricingScenarioHandler` reste séparé dans le même module fonctionnel et conserve l’accès ORM transactionnel nécessaire à la création d’un scénario. Ce lot ne modifie pas le handler, le calcul de coût de revient, les versions, les réserves, la persistance ou les contrats HTTP.

## Modification

Le constructeur est désormais :

```python
PricingScenarioService(
    reader=pricing_reader,
    dispatcher=dispatcher,
    policy=policy,
)
```

La composition root et les fixtures de tests ont été mises à jour. La méthode `list_for_case` continue d’appeler `PricingScenarioReader.list_for_case` avec le tenant et le dossier. La méthode `execute` conserve la garde patronale, l’autorisation `PRICING_WRITE` et le contexte de dispatch.

## Invariants

| Invariant | Preuve |
|---|---|
| Patron requis | Garde `ActorKind.PATRON_ADMIN` et membership actif conservée |
| Autorisation | `Capability.PRICING_WRITE` évaluée avant dispatch |
| Isolation | Le tenant vient du contexte acteur et la lecture passe par le reader |
| Écriture | Le dispatcher reste responsable de la commande |
| Lecture | `PricingScenarioReader` reste l’unique dépendance de lecture de la façade |
| Transaction métier | Le handler garde les requêtes ORM et le calcul déterministe |

## Couverture et qualité

Le test pur `backend/tests/architecture/test_pricing_scenario_facade.py` vérifie le chemin d’écriture, le chemin de lecture, l’appel au reader, l’autorisation et l’absence de besoin d’un `session_factory`.

| Contrôle | Résultat |
|---|---|
| Test pur de façade | `1 passed` |
| Ruff ciblé | Réussi |
| Mypy ciblé | Réussi |
| Suite backend hors DB | À confirmer dans la validation avant PR |
| Frontend typecheck/lint/Vitest/build | À confirmer dans la validation avant PR |
| CI PostgreSQL, couverture globale, Trivy, image-security | À confirmer après push |

La couverture globale locale doit être lue avec prudence : l’exécution hors DB ne couvre pas tous les handlers transactionnels PostgreSQL. Le gate CI de couverture configuré à 85,50 % reste la référence pour le parcours complet.

## Limites

Ce micro-lot est un découplage de construction et ne constitue ni une nouvelle fonctionnalité pricing, ni une validation de calcul économique, ni une décision commerciale automatique. Aucun environnement VPS, staging ou production, fournisseur externe, corpus DCE, OCR/RAG, eIDAS ou validation juridique n’est revendiqué.
