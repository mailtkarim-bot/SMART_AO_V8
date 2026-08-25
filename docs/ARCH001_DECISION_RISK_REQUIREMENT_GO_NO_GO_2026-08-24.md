# SMART_AO V8 — Tranche Decision : risques, exigences confirmées et GO/NO-GO contrôlé

**Date : 24 août 2026**
**Branche : `docs/pricing-http-next-lot-28`**
**Auteur : Manus AI**

## 1. Objet et périmètre

Cette tranche choisit explicitement le bounded context **Decision** pour poursuivre la réduction progressive de la dette ARCH-001. Elle ajoute le premier croisement structuré entre un risque CCAP/CCTP et une exigence DCE, puis ouvre une action patronale de traitement et une finalisation humaine GO/NO-GO contrôlée.

Le périmètre ne prétend pas analyser automatiquement un DCE. Une extraction terminée n’est pas une qualification humaine. Une exigence non confirmée, ambiguë ou appartenant à une autre version DCE ne peut pas être utilisée comme fondement d’un lien ou d’une finalisation.

## 2. Garde de frontière ARCH-001

`PatronDecisionDossierService` ne reçoit plus de session SQLAlchemy. Il dépend du port applicatif `DecisionDossierReader`, tandis que `SqlAlchemyDecisionDossierReader` reste dans `decision/infrastructure/`. La composition root est le seul endroit qui assemble l’adaptateur concret. Le test `test_decision_application_dossier_uses_reader_boundary` vérifie l’absence d’import SQLAlchemy et d’import infrastructure dans le service applicatif.

| Élément | Décision d’architecture | Preuve locale |
|---|---|---|
| Bounded context | `decision` | Arborescence et modules `domain`, `application`, `public`, `infrastructure` |
| Service contrôlé | `PatronDecisionDossierService` | Port `DecisionDossierReader` injecté |
| Adaptateur SQL | `SqlAlchemyDecisionDossierReader` | Module infrastructure dédié |
| Garde | AST sans SQLAlchemy/infrastructure dans le service | Test architecture ciblé passé |
| Composition | Injection depuis `bootstrap/application.py` | Câblage runtime statique et Ruff passé |

Les handlers historiques d’écriture Decision et certains autres bounded contexts conservent encore des imports ORM dans leurs modules d’application. L’extraction est donc réelle mais partielle ; aucune fermeture globale d’ARCH-001 n’est revendiquée.

## 3. Croisement risque–exigence

La commande fermée `LinkRiskToRequirementCommand` relie un risque déjà enregistré à une exigence DCE via une relation limitée à `IMPACTS`, `MITIGATES` ou `CONSTRAINS`. Le serveur contrôle l’affaire, la version DCE applicable, l’appartenance du risque à cette affaire/version et l’existence d’une confirmation courante `CONFIRMED` pour l’exigence.

La persistence `decision_risk_requirement_links` est tenant-scoped et append-only. Elle contient une clé fonctionnelle et les identifiants d’idempotence, de commande, d’acteur et de membership. La migration `20260824_0059` ajoute les FKs composites vers la Case, le risque, l’exigence, la version DCE et le tenant, ainsi que les contraintes de vocabulaire et le trigger PostgreSQL contre `UPDATE` et `DELETE`.

La provenance exposée par ce lien est minimale : références `decision-risk:<id>` et `dce-requirement:<id>`. Aucun extrait documentaire, texte source ou montant financier n’est copié dans l’événement. La liaison est réservée à la capability `decision.risk.link.write`, accordée au patron administrateur et absente du collaborateur.

## 4. Génération de l’action patronale

Après validation du lien, le handler peut appeler `DecisionPatronActionWriter` dans la même transaction. L’implémentation `PatronActionWriter.create_from_risk_requirement_link` crée une action `DECIDE_GO_NO_GO` à l’état `OPEN`, de sévérité `BLOCKING`, avec une clé fonctionnelle idempotente dérivée du lien.

Cette action demande au patron de revoir le risque et l’exigence avant la décision finale. Elle ne constitue pas une qualification automatique et ne divulgue pas le contenu de la pièce DCE. Le receipt contient les références d’agrégats, et l’événement `PatronActionCreated` reste sparse.

## 5. Finalisation GO/NO-GO

La route patronale ajoutée est :

```text
POST /api/v1/patron/cases/{case_id}/decisions/{decision_id}/go-no-go
```

Le corps HTTP fermé porte uniquement la commande, la clé d’idempotence, la révision attendue, le fingerprint affiché, l’issue `GO` ou `NO_GO` et une justification patronale. Le handler refuse une Decision absente, hors affaire, non `GO_NO_GO`, non `PENDING_PATRON`, non `CURRENT`, non `FROZEN`, sans contexte gelé ou sans référence.

Le reader `SqlAlchemyDecisionVerifiedContextReader` vérifie les références de type `DCE_REQUIREMENT`. Il résout la version DCE applicable de la Case et ne valide le contexte que si toutes les exigences référencées sont dans cette version et possèdent une confirmation humaine courante `CONFIRMED`. L’absence de Case, l’absence de version ou une exigence non confirmée entraînent un refus fail-closed.

La mise à jour utilise `expected_revision` avec le helper de révision optimiste. Le receipt retourne la nouvelle version. L’événement `DecisionFinalized` transporte l’identifiant de Decision, l’affaire, l’issue et la révision ; il ne transporte pas la justification, le contenu documentaire ou une donnée financière.

Cette surface est une **finalisation humaine contrôlée**, pas un moteur de décision automatique. Le système ne déduit ni `GO` ni `NO_GO` à partir d’un document non vérifié et ne remplace pas l’arbitrage du patron.

## 6. Validation exécutée

| Contrôle | Résultat |
|---|---:|
| Ruff sur backend et scripts | Passé |
| Tests ciblés Decision/routes/actions | **41 passed, 2 deselected** |
| Suite backend hors `db` | **954 passed, 458 deselected** |
| mypy Decision, PatronAction et bootstrap | **33 source files, no issues** |
| SQL Alembic offline | Généré jusqu’à `20260824_0059` |
| Vérification du trigger append-only | Contrat statique + présence dans SQL offline |
| PostgreSQL online | Non exécuté dans le sandbox |
| Docker, ClamAV, VPS, HTTPS, fournisseur externe | Non exécutés et non revendiqués |
| CI GitHub avec runner réel | Bloquée avant étapes, non preuve de tests |

Les tests ont produit seulement un avertissement de dépréciation Starlette/httpx déjà présent dans l’environnement ; il ne constitue pas un échec fonctionnel.

## 7. Risques et travaux restants

La validation PostgreSQL online doit encore confirmer les FKs composites, le trigger, les collisions concurrentes et la transaction persistence + événement + outbox. Une lecture patronale paginée des liens reste à ajouter. Les références de contexte `DCE_REQUIREMENT` devront également être produites de manière explicite par le flux de préparation Decision avant toute utilisation réelle.

Le prochain travail métier utile est le rapprochement contrôlé des risques avec DPGF/BPU et les traitements patronaux détaillés, sans exposer la tarification au collaborateur. Restent également le corpus Golden, l’OCR/RAG qualifiant sous confirmation humaine, DC1/DC2/DC4, le dépôt et la recette opérationnelle. Le verdict produit reste **NO-GO opérationnel** tant que les validations externes et la CI réellement exécutée ne sont pas disponibles.
