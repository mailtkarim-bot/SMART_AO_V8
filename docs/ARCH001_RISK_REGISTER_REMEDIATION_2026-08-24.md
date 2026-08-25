# ARCH-001 et registre des risques CCAP/CCTP — rapport de tranche

## Résumé

Cette tranche poursuit la réduction de la dette ARCH-001 sans déplacement massif des handlers transactionnels. Elle extrait les lectures préparatoires des services mutationnels membership et pricing derrière des ports applicatifs, puis livre un premier registre structuré des risques issus d’un DCE versionné.

Le résultat est une base métier utilisable par le patron pour qualifier un risque CCAP ou CCTP avec une provenance contrôlée. Il ne constitue pas encore la totalité du moteur d’analyse AO : le croisement DPGF/BPU, l’OCR/corpus Golden, les risques automatiques issus d’un fournisseur, la génération DC1/DC2/DC4 et la décision GO/NO-GO complète restent des tranches distinctes.

## Réduction ARCH-001

`PatronAssignmentManagementService` ne résout plus directement les modèles ORM pour ses contrôles de case et d’affectation. Il reçoit un `AssignmentManagementReader` applicatif, tandis que `SqlAlchemyAssignmentManagementReader` est câblé dans la composition root. Le même principe est appliqué à `PricingScenarioService` et `PricingScenarioTransitionService` avec `PricingScenarioReader` et `SqlAlchemyPricingScenarioReader`.

Les handlers restent raccordés au dispatcher transactionnel existant. Cette décision est intentionnelle : elle évite de déplacer en dehors du root transactionnel les écritures, les événements et les receipts qui portent l’idempotence et la révision. La tranche ne prétend donc pas avoir supprimé toutes les arêtes historiques application→infrastructure ; elle établit un pattern contrôlé pour les prochaines extractions.

## Registre structuré CCAP/CCTP

Le domaine pur `decision.domain.risk` définit les catégories `CCAP` et `CCTP`, les niveaux de sévérité et de vraisemblance, le traitement initial `OPEN`, les limites de texte et l’ordre des offsets. La commande fermée `RegisterStructuredRiskCommand` ne reçoit ni tenant ni acteur ; ces éléments sont résolus dans le contexte serveur.

La route patronale `POST /api/v1/patron/cases/{case_id}/risks` utilise une capability dédiée `decision.risk.write`. Le handler vérifie l’existence de l’affaire dans le tenant, la correspondance entre la version DCE et la version applicable à l’affaire, l’existence d’un fragment extrait par une analyse DCE `COMPLETED`, puis la concordance de l’extrait et des offsets avec le texte du fragment.

La persistence `decision_risks` est append-only dans cette tranche. Elle porte la provenance, la clé fonctionnelle, l’acteur patronal, la membership, la commande et la clé d’idempotence. Les contraintes PostgreSQL interdisent les catégories, états, offsets et textes invalides. L’événement `DecisionRiskRegistered` est sparse : il contient l’identifiant, l’affaire, la catégorie et la sévérité, mais jamais l’énoncé ou l’extrait source.

## Validation

| Contrôle | Résultat |
|---|---:|
| Suite backend hors marqueur `db` | **929 passed, 458 deselected** |
| Tests risques domaine/application/API | Passés |
| Tests frontières architecture | Passés |
| Ruff backend/scripts ciblés | Passé |
| Mypy Decision, membership application et pricing | Passé sur 57 fichiers |
| Scripts shell | Passés avec `bash -n` |
| Alembic offline | Migration 0058 rendue jusqu’au head attendu |
| PostgreSQL online | Non disponible dans le sandbox ; non revendiqué |
| Docker, CI runner, VPS et fournisseurs | Non revendiqués |

## Limites et suite

La migration `20260824_0058_create_decision_risks.py` doit être exécutée sur PostgreSQL réel avec une base jetable. Il faudra vérifier les FKs composites, les contraintes, l’isolation tenant, la concurrence sur `functional_key`, le rejeu d’idempotence et la transaction event/outbox/receipt. Ces éléments sont couverts par le contrat applicatif et le SQL offline, mais pas par une recette PostgreSQL online dans le sandbox courant.

La prochaine extraction ARCH-001 doit cibler un bounded context explicitement choisi et ajouter un garde de frontière correspondant. La prochaine valeur métier est le croisement structuré des risques avec les exigences DCE, puis la génération contrôlée des actions patronales et de la décision GO/NO-GO. Aucune de ces étapes ne doit exposer des montants financiers au collaborateur ni fabriquer une qualification à partir d’un document non vérifié.
