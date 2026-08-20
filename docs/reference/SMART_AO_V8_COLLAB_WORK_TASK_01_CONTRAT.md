# SMART_AO V8 — COLLAB-WORK-TASK-01

## Objet

Cet incrément ouvre le premier noyau durable du wizard collaborateur : une tâche de préparation liée à une exigence DCE visible dans une affaire et à une affectation active. Le collaborateur peut créer la tâche depuis son périmètre, la prendre, enregistrer un résultat sourcé puis la terminer. La tâche ne permet ni de voir ni de modifier un prix, une marge, un coût, une trésorerie, une décision patronale ou une autorisation de dépôt.

## Périmètre fonctionnel

| Commande | Règle |
|---|---|
| `CreateTaskFromRequirement` | L’exigence et l’affaire doivent appartenir au tenant et être couvertes par l’affectation active. La clé fonctionnelle empêche un doublon actif de même finalité. |
| `ClaimTask` | Seul le collaborateur affecté ou un acteur explicitement délégué peut faire passer `READY` à `IN_PROGRESS`. |
| `RecordTaskResult` | Le résultat est versionné et doit contenir un texte borné, une référence de source/preuve ou une raison explicite d’impossibilité. Il ne devient pas automatiquement une Evidence confirmée. |
| `CompleteTask` | La tâche ne peut être terminée qu’après un résultat admissible. La révision attendue est obligatoire. |

Les états sont `READY`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED` et `ABANDONED`. La première version implémente `READY → IN_PROGRESS → COMPLETED`; les blocages et abandons restent des extensions dédiées qui ne doivent pas être simulées par une clôture silencieuse.

## Autorisation

Le serveur résout `tenant_id`, `actor_id`, membership, `case_id`, `assignment_id` et le scope ReBAC. Le payload ne contient aucune valeur d’autorité. Une affectation suspendue, terminée, expirée ou hors périmètre reçoit `ASSIGNMENT_INACTIVE` ou `SCOPE_DENIED` sans révéler une ressource étrangère.

## Confidentialité

Le contrat public n’accepte pas les champs `price`, `cost`, `margin`, `treasury`, `financial`, `decision`, `go_no_go`, `deposit` ou `submission_authorization`. Les événements, receipts, read models et erreurs ne transportent aucune donnée financière. Un résultat collaborateur est une préparation ou une alerte, jamais une décision.

## Idempotence et concurrence

Chaque écriture durable porte `command_id`, `idempotency_key`, `correlation_id` éventuel et `expected_revision` lorsqu’un root existant est modifié. Le rejeu exact retourne le receipt mémorisé sans second événement. Une même clé pour un payload différent produit `IDEMPOTENCY_KEY_REUSED`. Une révision obsolète produit `VERSION_CONFLICT` sans mutation partielle.

## Tests de sortie

Les tests doivent prouver la création sourcée, le rejeu idempotent, le refus collaborateur non affecté, l’isolation inter-tenant, le conflit de révision, la clôture sans résultat, les champs payload interdits, l’absence de données financières dans les événements/receipts et le maintien de l’historique des résultats.
