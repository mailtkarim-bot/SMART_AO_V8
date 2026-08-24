# SMART_AO V8 — Lecture Decision, rapprochement DPGF/BPU et GO conditionnel

**Date : 24 août 2026**
**Branche : `docs/pricing-http-next-lot-28`**
**Auteur : Manus AI**

## Objet

Cette tranche complète le bounded context `Decision` déjà choisi pour la réduction progressive d’ARCH-001. Elle apporte une lecture patronale paginée des liens risque–exigence et de leurs actions, prépare un rapprochement contrôlé avec les lots DPGF/BPU normalisés, et consolide la finalisation `CONDITIONAL_GO` sans transformer un document non vérifié en qualification.

## Lecture patronale paginée

Le nouveau port `DecisionRiskRequirementReader` expose une page tenant-scoped ordonnée de manière déterministe par `(created_at, link_id)`. Le curseur encode ces deux éléments et les pages sont plafonnées à 100 liens. La projection contient les identifiants du lien, de la Case, du risque, de l’exigence et de la version DCE, ainsi que la relation, la justification patronale, les références sources et l’action `DECIDE_GO_NO_GO` associée.

La route patronale est :

```text
GET /api/v1/patron/cases/{case_id}/risk-requirement-links?limit=25&cursor=...
```

Le serveur résout l’acteur et le tenant, puis impose la capability `decision.risk.read`. Le collaborateur n’a aucun accès à cette projection. Le reader ne renvoie pas le contenu intégral des fragments documentaires et ne lit aucun champ financier.

## Rapprochement DPGF/BPU

La route patronale de préparation du rapprochement est :

```text
GET /api/v1/patron/cases/{case_id}/risk-requirement-links/{link_id}/pricing-reconciliation?search=...&limit=25
```

Le service vérifie le patron, la Case, le lien et le tenant. L’adaptateur ne consulte que les lots pricing `COMMITTED` de la Case dont le type est `DPGF` ou `BPU`. La recherche bornée porte sur le code ou la désignation de la ligne. Les résultats sont décrits comme des candidats, avec `match_basis=CODE_OR_DESIGNATION` et `verification_status=COMMITTED_NORMALIZED_IMPORT`.

La projection exclut volontairement `quantity_decimal`, `unit_price_minor` et `total_minor`. Elle ne calcule ni marge, ni prix, ni conformité. La sélection d’un candidat et son interprétation restent une étape patronale ultérieure. Les données financières demeurent dans le périmètre `FINANCIAL_PRIVATE` existant et ne sont pas exposées par cette API.

| Donnée | Exposée dans cette projection ? | Motif |
|---|---:|---|
| Code de ligne | Oui | Permettre l’identification du candidat |
| Désignation | Oui | Permettre la revue patronale |
| Unité | Oui | Contexte minimal de la ligne |
| Numéro de ligne | Oui | Traçabilité de la source normalisée |
| État du lot | Oui | Refuser les lots non commités |
| Quantité | Non | Réduire la fuite de données financières |
| Prix unitaire | Non | Confidentialité financière |
| Total | Non | Confidentialité financière |

## Conditions de GO conditionnel

Le contrat de finalisation accepte maintenant `GO`, `CONDITIONAL_GO` et `NO_GO`. Une issue `CONDITIONAL_GO` exige entre une et 32 conditions. Chaque condition possède un identifiant unique, un libellé non vide, un responsable patronal, une échéance ou une justification d’absence d’échéance, et une conséquence d’échec non vide.

Les invariants existants de `DecisionCondition` sont réutilisés avant persistence. Les conditions sont créées dans `decision_conditions` avec l’état `OPEN`, dans la même transaction que la finalisation de la Decision. `GO` et `NO_GO` refusent toute condition fournie. Le receipt indique seulement le nombre de conditions ; l’événement sparse contient l’issue, la révision et ce nombre, sans justification ni contenu documentaire.

Le système ne déduit pas l’issue. La finalisation reste une décision humaine contre un contexte `FROZEN`, un fingerprint affiché et une révision optimiste. Le garde `DecisionVerifiedContextReader` exige que toute référence de type `DCE_REQUIREMENT` soit confirmée humainement et appartienne à la version DCE applicable de la Case.

## Validation locale

| Contrôle | Résultat |
|---|---:|
| Tests ciblés pagination/rapprochement/routes/GO conditionnel | **32 passed, 1 warning** |
| Gate backend hors `db` après cette extension | **964 passed, 458 deselected** |
| Ruff ciblé | Passé |
| mypy ciblé Decision/PatronAction/bootstrap | Passé sur 38 fichiers |
| PostgreSQL online | Non exécuté |
| Docker/VPS/ClamAV/HTTPS/fournisseur externe | Non exécutés |
| CI GitHub Actions | Échec avant étapes, runners non alloués |

La validation hors PostgreSQL ne constitue pas une preuve d’application des migrations ni de fonctionnement des triggers en base réelle. La CI GitHub `32748619776` a terminé avec les trois jobs en échec, `runnerName: null` et zéro étape ; aucun test distant n’a donc été exécuté.

## Travaux restants

La prochaine validation doit appliquer `20260824_0059` sur PostgreSQL réel et vérifier les FKs, le trigger append-only, l’isolation tenant, les collisions concurrentes, la transaction lien/action/outbox et la finalisation d’un contexte réellement préparé. Il faudra ensuite persister un rapprochement patronal explicite si le produit doit conserver la décision de correspondance, sans réintroduire de montants dans une surface collaborateur.

Le moteur de rapprochement sémantique CCAP/CCTP–DPGF/BPU, l’OCR/RAG qualifiant, le corpus Golden, DC1/DC2/DC4, le dépôt et le gate opérationnel restent hors de cette tranche. Le statut de production demeure **NO-GO** tant que les preuves externes et la CI réellement exécutée ne sont pas disponibles.
