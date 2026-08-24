# Prochain lot métier — PRICING-IMPORT-HTTP-PERSISTENCE-01

## 1. Point de départ vérifié

La branche `main` est au commit `970c9ff`, fusion de la validation renforcée des lignes normalisées dans la PR #48. Le service interne `PricingImportCreationService` sait déjà persister un lot `PREVIEWED` et ses lignes normalisées, avec receipt idempotent, événement et outbox. Le contrat de commande est fermé, sans binaire brut, et les quantités doivent être des décimaux canoniques textuels.

La route HTTP de preview XLSX existe encore principalement comme une projection calculée en mémoire. Elle doit être raccordée au service de création afin qu’une preview validée devienne réellement un lot serveur réutilisable par la route de commit. La route de commit existe déjà et attend `batch_id`, mais le parcours HTTP ne doit pas dépendre d’une insertion manuelle en base.

La validation locale actuelle est de 1 024 tests backend verts et 61 tests frontend verts. La CI de la PR #48 est verte ; le workflow push de `main` `32514213612` a échoué avant démarrage des runners GitHub-hosted, sans étape de code exécutée. Ce défaut d’infrastructure ne constitue pas une preuve de régression fonctionnelle.

## 2. Objectif du slice

Transformer le parcours patronal de preview DPGF/BPU/Excel en un parcours HTTP persistant : le serveur reçoit le fichier, le valide et le normalise, calcule son SHA-256, crée le lot `PREVIEWED` sans conserver le binaire, puis retourne une projection bornée permettant au patron de relire le lot et de le committer vers un brouillon `DRAFT`.

Le slice ne réalise aucun dépôt externe, ne modifie aucun snapshot `PUBLISHED`, ne transmet aucune donnée financière à un collaborateur et ne transforme jamais `external_submission` en preuve de dépôt.

## 3. Découpage d’implémentation

| Étape | Travail | Résultat attendu |
|---:|---|---|
| 1 | Contrat HTTP fermé | DTO de création, projection de lot, lignes d’erreur et receipt ; aucun champ arbitraire, binaire ou clé de stockage publique. |
| 2 | Raccordement preview → création | Après validation XLSX, calcul SHA-256 côté serveur et dispatch de `CreatePricingImportPreviewCommand`; aucun fichier brut en base ou outbox. |
| 3 | Idempotence HTTP | Rejeu de la même commande renvoie le receipt durable ; même clé avec un contenu différent renvoie `409`. |
| 4 | Lecture patronale du lot | `GET` tenant-scoped du lot et de ses lignes normalisées, avec Case résolue côté serveur et bornes de pagination si nécessaire. |
| 5 | Commit HTTP complet | Le `batch_id` issu de la création est accepté par le commit ; réponses minimales `201/200/403/404/409/422`, sans montant, désignation, prix, nom de fichier ou hash dans le receipt de commit. |
| 6 | Capability et audit | Utiliser `financial.report.line.write` pour le parcours persistant, classification `FINANCIAL_PRIVATE`, policy auditée et refus neutres. |
| 7 | Frontière frontend | Raccorder le hook pricing au lot persistant seulement après stabilisation des DTO HTTP ; aucune donnée financière dans wizard collaborateur, contrats collaborateur ou webhooks. |

## 4. Scénarios de test obligatoires

Les tests API PostgreSQL doivent couvrir la création patronale d’un lot avec deux lignes, la conservation des erreurs de lignes, le rejeu idempotent, le conflit de clé, le refus collaborateur, la Case étrangère, le type de document invalide, le classeur invalide, l’absence de lot, la lecture inter-tenant et le commit vers un brouillon `DRAFT`.

Les tests doivent aussi vérifier que le binaire brut n’est jamais présent dans `pricing_import_batches`, `pricing_import_rows`, les événements, l’outbox ou le receipt. Le receipt de commit doit rester limité aux références d’agrégats, à la nouvelle révision et au nombre de lignes appliquées. Les lignes invalides ne doivent jamais être insérées dans `financial_report_lines`.

## 5. Invariants non négociables

> Le `tenant_id`, l’acteur, la membership, la Case, le lot et le brouillon sont résolus côté serveur.

> Le binaire XLSX est lu uniquement pendant la validation ; seul le SHA-256 serveur et les lignes normalisées sont conservés.

> Le lot et ses lignes restent append-only. Le commit est unique, atomique et protégé par révision optimiste.

> Un snapshot `PUBLISHED` ne peut jamais être modifié. Le commit vise uniquement un `DRAFT` verrouillé avec `FOR UPDATE`.

> Les montants sont des entiers en centimes ; les quantités sont des décimaux canoniques textuels ; aucun flottant ne doit être persistant.

> Aucun contrat collaborateur, webhook ou projection non patronale ne reçoit montant, ligne, prix, désignation ou empreinte source.

## 6. Critères de sortie

Le lot sera considéré comme terminé lorsque les routes patronales de création, lecture et commit seront branchées au bootstrap réel, que les tests API PostgreSQL et la régression backend seront verts, que `alembic check`, Ruff, detect-secrets, Bandit, build frontend et Vitest seront verts, et qu’une CI GitHub complète aura validé la branche et `main` avec des runners effectivement démarrés.

Le gate VPS reste indépendant et ne doit pas retarder la validation de ce parcours métier local et CI.
