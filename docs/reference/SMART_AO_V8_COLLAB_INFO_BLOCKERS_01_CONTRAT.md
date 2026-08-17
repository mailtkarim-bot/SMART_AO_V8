# SMART_AO V8 — COLLAB-INFO-BLOCKERS-01

## 1. Objet

`COLLAB-INFO-BLOCKERS-01` étend le wizard collaborateur avec des demandes d’information bornées par une affectation active, des réponses versionnées et des blocages opérationnels de tâche. Le slice ne transporte aucune donnée financière, stratégique ou décisionnelle.

Le root `InformationRequest` porte la demande durable. Les réponses sont append-only et chaque réponse référence la révision de la demande observée. Le root `Task` porte l’état opérationnel `BLOCKED`; un blocker identifié est historisé et sa résolution est contrôlée par révision optimiste.

## 2. Commandes fermées

| Commande | Root propriétaire | Résultat |
|---|---|---|
| `CreateInformationRequest` | `InformationRequest` | Crée une demande `OPEN` liée à une tâche et à une affectation active. |
| `RecordInformationRequestResponse` | `InformationRequest` | Ajoute une réponse versionnée et passe la demande à `ANSWERED`. |
| `DeclareTaskBlocker` | `Task` | Ajoute un blocker `OPEN`, passe la tâche à `BLOCKED` et émet `TaskBlockerDeclared`. |
| `ResolveTaskBlocker` | `Task` | Résout un blocker après contrôle de la révision et remet la tâche à `IN_PROGRESS` ou `READY`. |

Les requêtes de lecture restent limitées à l’affaire et à l’affectation active du collaborateur. Une demande d’information ne vaut ni décision patronale, ni validation de preuve, ni transmission externe.

## 3. Champs autorisés

`CreateInformationRequest` accepte uniquement `task_id`, `expected_task_revision`, `request_kind`, `subject`, `question`, `requested_object`, `reason`, `priority`, `due_at` et les identifiants de commande. `RecordInformationRequestResponse` accepte `request_id`, `expected_revision`, `response_text`, `source_locator` et un outcome fermé. `DeclareTaskBlocker` accepte `task_id`, `expected_revision`, `blocker_kind`, `description`, `source_locator` et `resolution_owner`. `ResolveTaskBlocker` accepte `task_id`, `blocker_id`, `expected_revision` et `resolution_note`.

Les champs supplémentaires sont rejetés. Les textes et locators sont filtrés contre les termes de prix, coût, marge, trésorerie, décision, dépôt, soumission et chiffrage.

## 4. Invariants

Le serveur résout `tenant_id`, `actor_id`, `membership_id`, l’affaire et l’affectation. L’affectation doit être active, appartenir au collaborateur et inclure `work.task.read` ou `work.task.write` selon le verbe. Les requests et blockers étrangers au tenant sont retournés avec une réponse neutre.

Une clé d’idempotence rejouée avec le même contenu retourne le receipt mémorisé sans seconde mutation ni second événement. Une clé réutilisée avec un payload différent est rejetée. Une révision obsolète retourne `VERSION_CONFLICT`. Une tâche bloquée ne peut pas être clôturée; une demande répondue ne crée pas de seconde réponse implicite.

Les réponses contiennent le texte opérationnel et une localisation de source facultative, mais jamais de montant, de prix, de marge, de trésorerie, de décision ou d’autorisation de dépôt. Les événements et outbox reprennent uniquement les identifiants opaques et les états.

## 5. Événements

Les événements minimaux sont `InformationRequestCreated`, `RequestResponseReceived`, `TaskBlockerDeclared` et `TaskBlockerResolved`. Ils sont persistés par le dispatcher commun avec receipts et outbox dans la même transaction.

## 6. Lecture « Mon travail »

La lecture des tâches projette `BLOCKED` comme état durable. Les demandes d’information rattachées à une tâche peuvent être listées sans exposer d’autres affaires, demandes d’un autre tenant, finance ou données de stockage privé.
