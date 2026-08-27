# ARCH-001 — Façade Collaborator Info Blockers

Ce lot sépare la façade applicative du workflow Membership « demandes d’information et bloqueurs » de ses accès SQLAlchemy de lecture et d’audit.

## Frontière livrée

La façade `CollaboratorInfoBlockerService` dépend désormais de `CollaboratorInfoBlockerReader`, un port applicatif qui expose uniquement les opérations nécessaires à l’autorisation et à la lecture : résolution de tâche depuis une demande, résolution de l’affectation active, lecture projetée du workflow et enregistrement d’un refus d’autorisation.

`SqlAlchemyCollaboratorInfoBlockerReader`, situé sous `membership/infrastructure/`, implémente ce port. Il conserve les filtres tenant-scoped et projette les enregistrements ORM vers des dataclasses applicatives immuables. L’audit de refus est également maintenu dans cet adaptateur.

La composition root construit l’adaptateur et l’injecte dans la façade. Les handlers mutationnels restent inchangés dans leur responsabilité transactionnelle : verrous, contrôles de révision, mutations append-only, événements et outbox restent exécutés par le dispatcher SQLAlchemy.

## Invariants vérifiés

- Un collaborateur actif et son affectation active doivent être résolus dans le tenant courant.
- L’autorisation utilise le `case_id` de l’affectation résolue, sans faire confiance à une valeur fournie par le client.
- Les commandes de réponse peuvent résoudre leur tâche par `request_id` ; les commandes de tâche utilisent leur `task_id`.
- Les refus sont délégués au reader, qui porte l’écriture d’audit.
- La lecture HTTP continue de recevoir les mêmes attributs métier via les projections applicatives.
- Un test pur de frontière couvre l’exécution et la lecture avec un faux reader, sans session factory ni PostgreSQL.

## Limite métrique ARCH-001

Le handler transactionnel demeure sous `membership/application/` parce qu’il porte volontairement les transactions, verrous et mutations ORM. Ce lot améliore la frontière de la façade et déplace les lectures/audits dans l’infrastructure, mais ne prétend donc pas réduire mécaniquement le compteur de fichiers `application/` important directement l’ORM.

Les tests d’intégration DB existants restent la preuve attendue pour les invariants transactionnels. PostgreSQL n’étant pas disponible dans l’environnement local de ce lot, aucune exécution DB locale n’est revendiquée ; la validation complète DB/migrations/coverage relève de la CI GitHub.
