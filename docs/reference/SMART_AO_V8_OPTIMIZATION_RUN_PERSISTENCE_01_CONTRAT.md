# SMART_AO V8 — OPTIMIZATION-RUN-PERSISTENCE-01

## Objet

Ce lot persiste les exécutions du planificateur OR-Tools de capacité dans un bounded context dédié. Il ne transforme pas le solveur en moteur de prix, ne prend pas de montant financier et ne produit pas de décision patronale automatique.

Le service applicatif charge l’input par un port `CaseCapacityInputPort`, vérifie la paire `tenant_id + case_id` et compare `source_revision` à `expected_source_revision`. Un écart rejette l’écriture avant persistence.

## Données autorisées

Le snapshot d’entrée contient seulement les identifiants opaques des demandes et ressources ainsi que les unités entières `required_units` et `capacity_units`. Le snapshot de résultat contient les couples demande/ressource affectés et les demandes non affectées. Les clés de montant, prix, marge, coût, texte DCE et embedding sont hors contrat.

Le hash `input_sha256` est calculé sur un JSON canonique trié, UTF-8, sans espace superflu. Il permet de prouver la version d’entrée auditée sans stocker un contenu documentaire ou financier.

## Persistence et audit

La table `optimization_runs` est tenant-scoped et possède une FK composite `(tenant_id, case_id)` vers `cases`. Les clés `(tenant_id, command_id)`, `(tenant_id, idempotency_key)` et `(tenant_id, id)` sont uniques. Les colonnes `source_revision`, `status`, `input_sha256`, snapshots, acteur et corrélation sont obligatoires.

L’écriture du run et de l’événement `OPTIMIZATION_RUN_RECORDED` est transactionnelle. Le payload d’audit contient l’identifiant du run, la Case, la révision source, le solveur, le statut et le hash d’entrée, mais pas les snapshots détaillés. Un rejeu strict retourne le même run et le même événement. La réutilisation d’une clé avec un contenu différent lève une collision d’idempotence. Si plusieurs contraintes uniques entrent simultanément en collision avec des lignes distinctes, le repository rejette également la commande plutôt que de choisir arbitrairement une ligne.

Un trigger PostgreSQL refuse toute mise à jour ou suppression de `optimization_runs`. L’audit est donc append-only; une correction future devra produire un nouveau run relié par une nouvelle commande, jamais muter l’ancien.

## État et limites

Les statuts OR-Tools sont fermés à `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN` et `MODEL_INVALID`. Une résolution infaisable est persistée comme fait technique; elle n’est pas convertie en succès ou en recommandation métier.

Le service de ce lot n’est pas encore exposé par une route HTTP et ne lance pas automatiquement le solveur après une admission DCE ou un changement pricing. Une exposition future devra ajouter une capability patronale, une policy, une projection allowlistée et un contrôle de revision côté serveur.

Les tests unitaires et les contrôles statiques sont exécutables dans le sandbox. Le repository utilise `ON CONFLICT DO NOTHING` avec `RETURNING`, puis relit toutes les lignes candidates correspondant à `run_id`, `command_id` ou `idempotency_key`; une cardinalité différente de un est un conflit fermé. La migration PostgreSQL et les six scénarios d’intégration transactionnelle exigent un serveur PostgreSQL; aucun serveur n’est disponible dans le sandbox courant, donc aucune réussite PostgreSQL réelle ne doit être déclarée avant la recette sur Docker ou machine cible.
