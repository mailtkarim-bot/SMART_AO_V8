# ARCH-001 — Façade des interactions d’affectation

Ce lot découple la façade `AssignmentInteractionService` de SQLAlchemy et de l’écriture directe de l’audit, sans modifier les trois mutations collaborateur existantes : accusé de réception, demande de clarification et déclaration d’indisponibilité.

## Frontière livrée

La façade dépend du port partagé `AssignmentManagementReader` pour résoudre une affectation dans le tenant courant et pour déléguer l’audit des refus. Elle conserve la vérification du type d’acteur, du membership, de l’appartenance de l’affectation au membership, l’autorisation ReBAC et la construction du `CommandContext` envoyé au dispatcher.

`SqlAlchemyAssignmentManagementReader`, situé dans `membership/infrastructure/`, implémente les lectures tenant-scoped et l’écriture d’audit. Le reader accepte un `SecurityAuditWriter` injectable ; la façade n’instancie donc plus de session SQLAlchemy ni de writer d’audit.

Les handlers ont été déplacés dans `membership/application/assignment_handler.py`. Ils restent transactionnels et conservent les verrous `FOR UPDATE`, les contrôles d’état et de fenêtre de validité, la révision attendue, la classification, les écritures append-only, l’idempotence fonctionnelle, les événements et l’outbox.

## Invariants conservés

- Toute interaction exige un acteur `COLLABORATEUR` et un membership présent.
- La résolution de l’affectation est bornée par `tenant_id` et vérifie le `membership_id` côté façade puis dans la transaction.
- Le `case_id` utilisé pour l’autorisation et le contexte provient de l’affectation résolue côté serveur.
- Une affectation inactive, hors fenêtre ou dépourvue de l’action requise reste refusée par le handler transactionnel.
- Une affaire archivée, une révision obsolète ou un contexte incohérent restent refusés.
- Les refus précoces sont délégués au reader pour être audités dans une transaction séparée.

Deux tests purs de frontière vérifient l’injection sans `session_factory`, la résolution tenant-scoped, le `case_id` propagé au dispatcher et la délégation d’un refus à l’audit.

## Limites de validation locale

PostgreSQL n’est pas disponible dans l’environnement local. Les tests marqués `db`, les migrations et la couverture complète sont donc validés par la CI GitHub ; aucune preuve de staging ou de production n’est déduite de ce lot.
