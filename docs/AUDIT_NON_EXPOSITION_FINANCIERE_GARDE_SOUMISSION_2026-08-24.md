# Audit ciblé — non-exposition financière et garde de soumission

**Projet :** SMART_AO V8  
**Branche auditée :** `docs/pricing-http-next-lot-28`  
**HEAD de départ :** `08a750c`  
**Date :** 24 août 2026  
**Auteur :** Manus AI

## 1. Conclusion exécutive

La revue confirme que le rapprochement DPGF/BPU ajouté au bounded context **Decision** ne sélectionne ni ne sérialise les montants `quantity_decimal`, `unit_price_minor` et `total_minor`. Les contrats HTTP publics sont fermés par `extra="forbid"`, la façade applicative impose une lecture réservée au patron administrateur et la matrice de capabilities ne donne pas `DECISION_RISK_READ` au collaborateur. Les filtres du reader SQL imposent le tenant, la Case, les documents `DPGF`/`BPU` et l’état `COMMITTED`.

La revue ne permet toutefois pas de conclure que le dépôt est déjà bloqué par le garde Decision : **`evaluate_submission_gate` reste un domaine pur non consommé par le workflow Submission**. Les routes patronales appellent directement `SubmissionPackageService.prepare` et `SubmissionPackageService.export`; aucun reader de snapshot Decision ni appel au garde n’est actuellement branché avant préparation, export ou transmission. Le dépôt effectif n’est donc pas encore protégé par ce garde.

Un défaut réel de robustesse a été corrigé dans le garde : des compteurs négatifs ou des valeurs mal typées pouvaient auparavant être considérés comme absents, et un statut de condition contradictoire pouvait passer pour un GO ordinaire. Le garde bloque désormais ces snapshots avec `INVALID_DECISION_SNAPSHOT` et refuse, pour les outcomes non conditionnels, tout statut différent de `NOT_APPLICABLE` ou tout compteur de conditions non nul.

## 2. Périmètre et méthode

L’audit a porté sur les contrats publics, routes FastAPI, façade applicative, reader SQLAlchemy, actions patronales, événements/outbox de Decision et Submission, matrice d’autorisation, garde de soumission et tests associés. Les recherches ont ciblé notamment `quantity_decimal`, `unit_price_minor`, `total_minor`, les agrégats financiers, `FINANCIAL_PRIVATE`, les payloads d’événements, `model_dump`, `asdict`, les rôles collaborateur et délégué.

Les validations réalisées sont locales et hors base PostgreSQL. Aucun test d’intégration PostgreSQL en ligne, aucun démarrage Docker et aucune exécution réelle CI n’ont été revendiqués.

## 3. Résultats sur la non-exposition financière

### 3.1 Stockage financier et frontière Decision

Les trois champs financiers privés appartiennent aux modèles de persistence pricing. Le reader Decision ne les sélectionne pas : sa requête projette uniquement l’identifiant du batch, le type documentaire, l’état, le numéro de ligne, le code, la désignation et l’unité. La construction de `DecisionPricingReconciliationProjection` reprend exclusivement ces colonnes et ajoute les marqueurs non financiers `CODE_OR_DESIGNATION` et `COMMITTED_NORMALIZED_IMPORT` [1].

Les contrats publics `DecisionPricingReconciliationItem` et `DecisionPricingReconciliationResponse` ne déclarent aucun montant, quantité financière, marge ou coût. Ils utilisent `ConfigDict(extra="forbid")`; une clé `total_minor` ou `unit_price_minor` ajoutée à un payload est donc rejetée par validation Pydantic [2]. Le contrat des liens risque–exigence est également fermé et ne transporte que les identifiants, la relation, la rationale, les références sources et l’état de l’action [2].

| Surface | Données exposées | Contrôle constaté | Verdict |
|---|---|---|---|
| `PricingImportRowRecord` | Quantité, prix unitaire, total | Modèle privé de persistence pricing | Correct, hors surface Decision |
| Reader `reconcile()` | Batch, document, état, ligne, code, désignation, unité | Projection SQL explicite sans colonnes financières | Correct |
| DTO rapprochement Decision | Candidats non financiers uniquement | `extra="forbid"` | Correct |
| Route `/patron/.../pricing-reconciliation` | DTO public de rapprochement | Façade patronale + policy | Correct dans son périmètre |
| Actions `DECIDE_GO_NO_GO` issues d’un lien | Identifiants et textes métier fixes | Source refs identifiants uniquement | Correct pour ce générateur |
| Événements Decision/PatronAction | Identifiants, relation, état, sévérité | Payloads sparse | Correct dans le périmètre audité |
| Manifeste/outbox Submission | `snapshot_id`, révision, hashes et état | Aucun champ monétaire | Correct sur la non-exposition |

### 3.2 Autorisation et isolation

La façade de lecture Decision refuse tout acteur qui n’est pas `PATRON_ADMIN` avec une membership active et autorise ensuite `DECISION_RISK_READ` sur une ressource tenant-scoped [3]. La matrice de capabilities accorde cette capability au patron administrateur, mais pas au collaborateur ni au délégué [4]. La policy ABAC vérifie le `tenant_id`, la membership active, la capability, puis refuse toute classification `FINANCIAL_PRIVATE` à un acteur autre que `PATRON_ADMIN` [5].

Le reader applique correctement les filtres `tenant_id` et `case_id` à l’existence du lien et aux lignes pricing. Il restreint les batches à `document_kind IN ('DPGF', 'BPU')` et `state = 'COMMITTED'`; la jointure de lignes impose également l’égalité de tenant et de batch [1]. La pagination des liens joint l’action patronale sur une clé fonctionnelle dérivée de l’identifiant du lien et conserve le filtre tenant sur le lien et l’action [1].

La jointure `sa.func.concat('decision-risk-requirement:', <UUID>)` est compatible avec le comportement PostgreSQL attendu de `concat`, qui convertit ses arguments en texte. Elle n’a cependant pas été exécutée contre PostgreSQL dans cet environnement; une recette online reste nécessaire avant de considérer cette preuve comme définitive.

### 3.3 Événements, logs et sérialisation

Dans le périmètre Decision/PatronAction/Submission inspecté, les événements transportent des identifiants, versions, états, relation, hashes et marqueurs de livraison. Le manifeste Submission référence uniquement l’identifiant et la révision du snapshot publié; les notifications outbox ne transportent pas de prix, de `financial_snapshot_id` ou de contenu d’archive sensible [6]. Les réponses HTTP de la route Decision sont reconstruites champ par champ à partir de projections non financières, sans `asdict` d’un modèle financier [7].

Cette conclusion est une preuve de revue ciblée, pas une preuve d’absence mathématique dans chaque module historique du dépôt. Les surfaces financières dédiées — pricing, financial report et routes patronales pricing — restent légitimement accessibles au périmètre patronal et doivent conserver leur classification `FINANCIAL_PRIVATE`.

## 4. Résultats sur le garde de soumission

Le garde actuel vérifie les règles suivantes :

1. la Decision doit être `FINALIZED`;
2. l’outcome doit être `GO` ou `CONDITIONAL_GO`, jamais `NO_GO` ni une valeur inconnue;
3. le contexte doit être `FROZEN`;
4. toutes les exigences DCE doivent être confirmées humainement;
5. un `CONDITIONAL_GO` doit avoir le statut `SATISFIED` et zéro condition ouverte;
6. un outcome non conditionnel ne doit avoir aucune condition ouverte;
7. aucune action de risque ne doit rester non résolue [8].

La première version vérifiait les compteurs par truthiness. Ainsi, un compteur négatif pouvait contourner la règle, et une valeur non booléenne truthy pouvait être acceptée pour `all_dce_requirements_confirmed`. Le code a été renforcé pour bloquer tout compteur négatif, booléen ou valeur non entière, ainsi que toute valeur qui n’est pas exactement `True` pour la confirmation DCE. Une valeur contradictoire `condition_status="OPEN"` avec `outcome="GO"` et zéro condition est maintenant bloquée par `UNEXPECTED_OPEN_CONDITIONS` [8].

Le snapshot demeure un objet de transfert interne et non un modèle Pydantic HTTP. Le contrôle fail-closed protège donc contre les erreurs de composition et les valeurs incohérentes, mais il ne remplace pas un reader applicatif tenant-scoped qui reconstruira ces valeurs depuis les agrégats persistés.

## 5. Écart bloquant restant : absence d’intégration runtime

`rg` ne trouve actuellement aucun consommateur applicatif de `evaluate_submission_gate` ou de `DecisionSubmissionGateSnapshot` en dehors du module domaine et de ses tests. La route patronale de préparation appelle `service.prepare(...)`, et la route d’export appelle `service.export(...)` [9]. Le service Submission contrôle déjà le rôle patronal, la capability `SUBMISSION_AUTHORIZE`, le tenant du package, la readiness, le document technique, le snapshot financier publié et l’intégrité du manifeste; mais il ne lit pas encore l’état Decision ni le résultat du garde [10].

Il faut donc distinguer les deux affirmations suivantes :

> **Vrai aujourd’hui :** le garde domaine sait calculer un résultat non financier et fail-closed à partir d’un snapshot fourni.

> **Faux aujourd’hui :** le dépôt, l’export ou la préparation sont déjà bloqués automatiquement par ce garde.

La tranche sûre suivante est de créer un port applicatif `SubmissionDecisionGateReader`, implémenté par un adapter infrastructure tenant-scoped, puis d’appeler le garde immédiatement avant la préparation autorisée et à nouveau avant l’export si l’état peut avoir changé. Le reader devra fournir uniquement les champs du snapshot, jamais les montants. Cette intégration devra couvrir les cas de tenant étranger, Decision absente, Decision obsolète, contexte non gelé, exigence non confirmée, action ouverte, condition ouverte et révision concurrente. Elle devra aussi définir explicitement le traitement de `PATRON_DELEGATE`, qui peut posséder `SUBMISSION_AUTHORIZE` mais ne possède pas aujourd’hui `DECISION_RISK_READ`.

Cette intégration n’a pas été codée dans le présent audit : elle modifierait le workflow métier Submission et nécessite un contrat de persistence et des tests transactionnels dédiés, idéalement avec PostgreSQL disponible.

## 6. Corrections et tests ajoutés

Les modifications locales non encore committées sont :

| Fichier | Modification |
|---|---|
| `backend/app/modules/decision/domain/submission_gate.py` | Blocage des snapshots invalides et des statuts de conditions contradictoires |
| `backend/tests/domain/test_decision_submission_gate.py` | Cas adversariaux : compteurs négatifs, valeurs mal typées, booléen non strict, contradiction GO/conditions |
| `backend/tests/architecture/test_decision_financial_boundary.py` | Garde textuel sur les surfaces auditées, capability collaborateur absente et rejet Pydantic des clés financières |
| `backend/app/modules/decision/application/ports.py` | Protocole structurel de référence PatronAction pour rétablir la vérification mypy de la composition |

La correction du protocole ne modifie pas le runtime; elle rend explicite la frontière port/adaptateur et supprime l’erreur mypy révélée par la campagne finale.

## 7. Preuves de validation

| Contrôle | Résultat |
|---|---|
| `uv lock --check` | Réussi |
| Ruff `backend scripts` | Réussi |
| Tests ciblés après correction | 45 réussis, 1 warning de dépréciation préexistant |
| Suite `pytest -m 'not db' backend/tests` | **981 réussis**, 458 désélectionnés, 4 warnings de dépréciation préexistants |
| Mypy Decision/Submission/PatronAction/bootstrap | Réussi, 72 fichiers contrôlés |
| Syntaxe shell `ops`/`scripts` | Réussie |
| Alembic offline | Réussi jusqu’à `20260824_0059` |
| `detect-secrets-hook` | Réussi |
| PostgreSQL online | Non exécuté : aucun PostgreSQL/Docker/socket/listener disponible |
| GitHub Actions | Non utilisé comme preuve : l’infrastructure runner reste bloquée selon l’état hérité |

## 8. Décision d’audit

La **non-exposition explicite** des montants dans le rapprochement Decision est correctement protégée dans le périmètre audité, avec des tests supplémentaires. La **confidentialité globale** dépend encore du maintien des contrôles patronaux sur les modules financiers historiques; aucune ouverture collaborateur n’a été identifiée dans les surfaces Decision auditées.

Le garde de soumission est maintenant plus robuste en domaine, mais le produit n’est pas encore pleinement conforme à la règle métier tant que ce garde n’est pas alimenté depuis la persistence et appelé dans le workflow Submission. Il ne faut donc pas présenter le dépôt comme effectivement bloqué au stade du dépôt final.

### Références

[1]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/app/modules/decision/infrastructure/risk_requirement_reader.py "Reader SQLAlchemy Decision"
[2]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/app/modules/decision/public/risk_requirement_read_contracts.py "Contrats publics Decision"
[3]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/app/modules/decision/application/risk_requirement_read.py "Façade applicative de lecture Decision"
[4]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/app/platform/security/capabilities.py "Matrice de capabilities"
[5]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/app/platform/security/authorization.py "Policy ABAC"
[6]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/app/modules/submission/application/service.py "Service Submission et événements"
[7]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/app/interfaces/http/routes/patron_decisions.py "Routes HTTP patronales Decision"
[8]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/app/modules/decision/domain/submission_gate.py "Garde domaine de soumission"
[9]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/app/interfaces/http/routes/patron_submission.py "Routes HTTP Submission"
[10]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/docs/pricing-http-next-lot-28/backend/tests/application/test_submission_package.py "Tests du package de soumission"
