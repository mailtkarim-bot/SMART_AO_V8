# ARCH-001 — Façade Collaborator Work Task

Ce lot sépare l’orchestration applicative du service `CollaboratorWorkTaskService` de ses lectures SQLAlchemy et de son écriture d’audit, sans modifier les transitions métier des tâches collaborateur.

## Frontière livrée

La façade dépend désormais du Protocol `CollaboratorWorkTaskReader`. Elle conserve les contrôles d’acteur, prépare le contexte de commande, vérifie l’autorisation et délègue les écritures au dispatcher transactionnel. La liste de tâches est obtenue via le reader après résolution d’une affectation active pour l’affaire.

`SqlAlchemyCollaboratorWorkTaskReader`, situé sous `membership/infrastructure/`, implémente la résolution de l’affectation d’une tâche, la résolution de l’affectation active par affaire, la lecture tenant-scoped des tâches et l’enregistrement des refus d’autorisation. Les enregistrements ORM sont projetés vers `CollaboratorTaskProjection` et `AssignmentProjection`.

Les handlers transactionnels restent sous `membership/application/`, car ils doivent continuer à exécuter dans la session du dispatcher les verrous, contrôles de révision, validations de tâche et de source DCE, transitions d’état, résultats append-only, événements et outbox.

## Invariants conservés

- Un collaborateur et son membership sont requis pour toute commande ou lecture.
- La tâche et l’affectation sont toujours résolues dans le tenant courant.
- L’autorisation utilise l’identifiant et le `case_id` de l’affectation résolue, et non une valeur reconstruite par la façade.
- La liste de tâches est filtrée par tenant, affaire et affectation.
- Les handlers revalident dans la transaction l’état actif, la fenêtre de validité, le périmètre d’action et la classification.
- Les transitions `READY`, `IN_PROGRESS` et `COMPLETED`, les contrôles de révision et la preuve de complétion restent inchangés.
- Les refus d’accès sont délégués à l’adaptateur d’audit.

Un test pur de frontière vérifie l’injection sans `session_factory`, le préflight d’affectation, le `case_id` propagé dans le contexte, la lecture projetée et le refus d’un acteur non collaborateur.

## Limites de validation locale

PostgreSQL n’est pas disponible dans l’environnement local de ce lot. Les tests marqués `db`, les migrations et la couverture complète sont donc validés par la CI GitHub, sans extrapolation vers un environnement de production ou de staging.
