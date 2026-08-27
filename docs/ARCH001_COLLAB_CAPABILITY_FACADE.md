# ARCH-001 — Façade des capacités collaborateur

Ce lot sépare l’orchestration applicative du service `CollaboratorCapabilityAssessmentService` de ses lectures SQLAlchemy, sans modifier le workflow métier de proposition de capacité ou de signalement d’un gap.

## Frontière livrée

La façade dépend désormais du Protocol `CollaboratorCapabilityReader`. Elle conserve l’autorisation de cas, prépare le contexte acteur et délègue les commandes au dispatcher transactionnel. Elle demande au reader la validation de l’affectation active avant chaque écriture et avant la lecture des évaluations.

`SqlAlchemyCollaboratorCapabilityReader`, situé sous `membership/infrastructure/`, implémente le port. Il applique les filtres `tenant_id`, membre, affaire, affectation, état actif et fenêtre temporelle ; il vérifie également l’action autorisée dans le périmètre de l’affectation. Les propositions et gaps sont retournés sous forme de projections applicatives immuables.

Les handlers transactionnels restent séparés sous `membership/application/`, car ils doivent continuer à exécuter dans la session du dispatcher les validations de sources, verrous et écritures ORM, l’idempotence fonctionnelle, les révisions, les événements et l’outbox.

## Invariants conservés

- Une proposition ou un gap reste borné au tenant, à l’affaire et à l’affectation active du collaborateur.
- L’action requise est contrôlée par l’affectation : proposition pour `propose_capability`, gap pour `report_gap`.
- Les sources DCE/tâche et les capacités restent validées dans le handler transactionnel, dans la même transaction que l’écriture.
- La lecture des évaluations ne peut pas contourner le contrôle d’affectation.
- Le catalogue Enterprise n’est pas muté par la façade collaborateur.
- Le routeur HTTP conserve le contrat de projection existant.

Un test pur de frontière vérifie l’injection sans `session_factory`, le préflight d’affectation, les actions déléguées et le refus d’un acteur non collaborateur. Les tests DB existants restent nécessaires pour la preuve transactionnelle complète.

## Limites de validation locale

PostgreSQL n’est pas disponible dans l’environnement local de ce lot ; les tests marqués `db`, les migrations et la couverture complète sont donc laissés à la CI GitHub. Aucun corpus DCE, fournisseur externe ou comportement de production n’est déduit de ce refactoring.
