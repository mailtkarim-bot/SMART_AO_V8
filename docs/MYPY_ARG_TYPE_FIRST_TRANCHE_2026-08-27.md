# Première tranche mypy `arg-type` — 2026-08-27

## Périmètre

Cette tranche cible les deux fichiers de test les plus chargés parmi les priorités identifiées : `backend/tests/application/test_submission_package.py` et `backend/tests/application/test_enterprise_upload_handlers.py`.

La correction remplace les `SimpleNamespace` passés à des handlers et services typés par les commandes Pydantic du domaine lorsque cela est possible. Pour les doubles de lecture qui modélisent des enregistrements persistants, le franchissement vers une méthode privée du handler est documenté par un `cast` local. Cette approche évite les exclusions mypy et ne modifie aucun contrat de production.

## Mesure avant / après

| Mesure mypy globale | Avant la tranche | Après la tranche |
|---|---:|---:|
| Sources analysées | 680 | 680 |
| Erreurs totales | 230 | **220** |
| Erreurs `arg-type` | 171 | **141** |
| Fichiers contenant des erreurs | 78 | mesure globale à reclasser |
| `arg-type` dans `test_submission_package.py` | 17 | **0** |
| `arg-type` dans `test_enterprise_upload_handlers.py` | 15 | **0** |

La baisse globale de 30 erreurs `arg-type` correspond aux 32 erreurs des deux fichiers avant correction, moins les deux erreurs introduites temporairement par le nouveau test de frontière puis résolues dans le même lot. La baisse de dix erreurs totales doit être suivie avec la même commande lors de chaque micro-lot.

## Erreurs restantes

Après cette tranche, les catégories globales restantes sont : `arg-type` 141, `attr-defined` 19, `index` 13, `misc` 7, `var-annotated` 5, `unused-ignore` 4, `assignment` 3, `operator` 2 et `return-value` 1. Le mypy ciblé sur les deux fichiers prioritaires et le test de frontière est vert.

## Prochaines tranches

La prochaine tranche `arg-type` doit traiter un groupe homogène de factories de tests API, en commençant par les doubles `AuthenticationContextResolver` et `ConsultationSecurityRuntime`. Les erreurs de Protocol doivent être corrigées avec des interfaces minimales réellement compatibles. Les `SimpleNamespace` réservés aux objets persistants doivent ensuite être remplacés progressivement par des Protocols de projection ou des factories typées.

Le formatage Ruff reste séparé du refactoring métier. Le lint global est vert, tandis que la dette historique `ruff format --check .` demeure suivie indépendamment par bounded context, sans reformatter massivement des fichiers non liés.
