# ARCH-001 — Façade de gestion patronale des affectations

Ce lot sépare la façade patronale de gestion des affectations Case de ses handlers transactionnels SQLAlchemy, sans modifier les six commandes métier existantes.

## Frontière livrée

`PatronAssignmentManagementService` orchestre désormais l’exigence d’un acteur patron, le membership, la résolution tenant-scoped de la Case ou de l’affectation, l’autorisation ReBAC et la construction du `CommandContext`. Les refus précoces sont délégués à `AssignmentManagementReader.record_denial`; la façade ne crée plus de session SQLAlchemy ni de writer d’audit.

`PatronAssignmentManagementHandler`, déplacé dans `patron_assignment_handler.py`, conserve les mutations atomiques `CreateCaseAssignment`, `AmendCaseAssignmentScope`, `SuspendCaseAssignment`, `ReactivateCaseAssignment`, `EndCaseAssignment` et `ValidateAssignmentInteraction`. Il conserve les verrous de lignes, contrôles de lifecycle et de fenêtre, révisions optimistes, unicité des affectations ouvertes, écritures d’historique, validations append-only, événements et outbox.

Le handler et sa factory sont réexportés par le module façade afin de préserver le bootstrap, le dispatcher et les imports de tests existants.

## Invariants conservés

- Les résolutions patronales sont bornées par `tenant_id` et l’identifiant Case ou affectation demandé.
- Le `case_id` utilisé par l’autorisation et le dispatcher provient de la projection serveur résolue.
- Une Case absente, inactive ou archivée reste refusée selon la commande concernée.
- Une affectation hors état ou hors fenêtre reste refusée par le handler sous verrou.
- Les révisions attendues et les transitions d’état restent contrôlées dans la transaction.
- Les permissions d’action et de classification restent portées dans le scope d’affectation.
- Les demandes de validation d’interaction restent liées à une source existante et non déjà validée.

Deux tests purs de frontière couvrent la résolution de Case par le reader, le `case_id` propagé au dispatcher et l’audit délégué d’un refus non patronal. Les tests DB, migrations, concurrence et couverture complète sont validés par la CI GitHub ; ils ne sont pas revendiqués localement sans PostgreSQL.
