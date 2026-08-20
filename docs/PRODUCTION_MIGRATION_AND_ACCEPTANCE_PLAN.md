# Plan de migration et de recette — Prochain déploiement production SMART_AO V8

**Version :** 1.0  
**Référence logicielle :** `main` au commit `2df3d2c`  
**Précondition absolue :** staging Docker réel accepté selon le plan post-déploiement  
**Décision actuelle :** `NO-GO` tant que la recette staging réelle n’est pas exécutée et documentée

## 1. Objet et principe de gouvernance

Ce document transforme le rapport staging final en procédure de passage en production. Il ne constitue pas une autorisation de mise en production immédiate. Le code et la CI sont prêts, mais le rapport de staging indique que Docker, PostgreSQL connecté, HTTPS, ClamAV EICAR, workers, backup et restauration isolée n’ont pas encore été exécutés dans le sandbox.

> Aucune mise en production ne doit être déclenchée à partir de la seule simulation statique Compose. La décision de passage exige un staging réel accepté, un backup restaurable et une approbation explicite de l’opérateur responsable.

La procédure applique les invariants suivants : tenant résolu côté serveur, confidentialité financière absolue, append-only pour les registres immuables, révision optimiste, idempotence, absence de données financières dans les webhooks et absence de downgrade automatique.

## 2. Critères d’entrée obligatoires

| Critère | Preuve requise | État actuel |
|---|---|---|
| `main` identifié | Commit, tag de release et diff final | Disponible : `2df3d2c` |
| CI complète | Backend, frontend, image-security | Verte pour les PR du cycle |
| Couverture backend | Rapport CI archivé | 92,88 % |
| Staging réel | Rapport PASS signé avec logs | Non disponible |
| Backup staging restauré | Hash et rapport isolé | Non disponible |
| Secrets production | Gestionnaire de secrets, jamais Git | À préparer |
| Fenêtre de maintenance | Responsable et horaires UTC | À planifier |
| Procédure de rollback | App rollback et restauration DB revue | À approuver |

Le déploiement est automatiquement `NO-GO` si un critère critique est absent, si un secret apparaît dans un log, si l’image n’est pas digest-pinnée, ou si la recette staging est seulement statique.

## 3. Préparation de la release

Créer un tag immuable sur le commit exact qui sera déployé, par exemple `v8-production-YYYYMMDD`, après validation de la staging. Conserver la liste des images et leurs digests, le checksum du bundle frontend, le hash du Dockerfile et la version Alembic attendue. Le tag doit être associé à la fiche de changement et à la fenêtre de maintenance.

Vérifier que les variables production sont injectées par le gestionnaire de secrets et non par un fichier commité. Les valeurs obligatoires comprennent l’URL PostgreSQL, les paramètres JWT, le hostname public, les identifiants PostgreSQL, les paramètres de stockage, ClamAV et les endpoints de supervision. Les secrets doivent être distincts du staging et soumis à une rotation contrôlée.

Effectuer une revue à deux personnes du fichier Compose de production ou de sa variante approuvée. Confirmer les digests, les limites de ressources, les réseaux, les volumes persistants, les healthchecks, les ports exposés et les règles Caddy. PostgreSQL et ClamAV ne doivent jamais être publiés sur Internet.

## 4. Backup et point de restauration

Avant toute modification de production, geler les opérations d’écriture non essentielles et exécuter le backup PostgreSQL ainsi que la sauvegarde des volumes documentaires privés. Calculer un hash pour chaque artefact, stocker une copie hors hôte et vérifier qu’elle est lisible.

Le responsable doit connaître le point de restauration exact, l’heure UTC, le commit courant, la version de schéma et l’emplacement hors hôte. Une restauration de contrôle doit avoir été réussie en staging isolé ; une simple création de fichier `.sql.gz` n’est pas une preuve de restaurabilité.

Ne jamais utiliser `SMART_AO_ALLOW_EMPTY_BACKUP=1` en production. Une base non initialisée ou vide est un arrêt immédiat du déploiement.

## 5. Séquence de migration production

La séquence proposée est volontairement forward-only :

1. ouvrir la fenêtre de maintenance et annoncer le gel des opérations sensibles ;
2. vérifier le commit, les digests, les secrets et l’état de la supervision ;
3. exécuter le backup et archiver les hashes ;
4. démarrer ou vérifier PostgreSQL et ClamAV avec leurs healthchecks ;
5. vérifier l’état courant `alembic current` et la tête `alembic heads` ;
6. lancer `alembic upgrade head` avec `SMART_AO_DATABASE_URL` injectée par l’environnement de production ;
7. vérifier la transaction, la version de schéma et les tables attendues ;
8. démarrer le backend, les workers, le frontend et Caddy ;
9. attendre les healthchecks et exécuter les smoke tests ;
10. ouvrir progressivement le trafic selon la stratégie de canary approuvée ;
11. observer les erreurs, latences, outbox, workers et connexions DB pendant la fenêtre de surveillance ;
12. clôturer la fenêtre seulement après validation des critères de sortie.

Les migrations doivent être compatibles avec les données existantes et ne doivent pas supprimer ou renommer une structure utilisée sans stratégie expand/contract approuvée. Aucun downgrade automatique n’est autorisé.

## 6. Plan de recette production

### 6.1 Infrastructure et sécurité

Vérifier les conteneurs, les digests, les limites de ressources, les réseaux et les ports. Contrôler le certificat TLS, le hostname, HSTS selon la politique approuvée, les endpoints `/healthz/live` et `/healthz/ready`, ainsi que les logs Caddy. Vérifier qu’aucun secret, token, clé ou contenu documentaire n’apparaît dans les logs.

### 6.2 Base et migration ORM

Vérifier que `alembic current` atteint la tête attendue `20260818_0047` et qu’il n’existe pas plusieurs heads. Contrôler les tables Enterprise, pricing, submission, `command_receipts` et `outbox_messages`. Vérifier les contraintes tenant-scopées, les index, les triggers append-only et la cohérence des clés étrangères.

### 6.3 Authentification, tenant et confidentialité

Avec un compte de recette autorisé, vérifier login, renouvellement de session, refus d’un rôle insuffisant, isolation entre deux tenants et absence d’accès à une ressource d’un autre tenant. Utiliser uniquement des données de recette et ne jamais introduire de RIB, montant réel ou document commercial réel.

### 6.4 Pricing

Vérifier la consultation des scénarios privés, le commit d’un batch `PREVIEWED` vers un brouillon `DRAFT`, la révision optimiste, le rejeu idempotent et le refus d’une seconde écriture incohérente. Vérifier que le receipt et les messages webhook ne contiennent aucun montant financier.

Côté interface, vérifier que le bouton se bloque pendant le commit, que l’état `FAILED` du reload reste distinct du commit confirmé, et que le changement d’affaire ou de batch remet l’état visuel à `IDLE`.

### 6.5 Enterprise, stockage et ClamAV

Tester l’upload d’un document non sensible de recette, le passage en quarantaine, le hash, le verdict `CLEAN`, la création de l’état `PENDING` et la décision humaine séparée. Injecter le fichier EICAR uniquement dans une zone temporaire isolée ; le résultat attendu est un rejet ClamAV sans projection dans la bibliothèque validée.

### 6.6 Préparation, submission et outbox

Générer un paquet de réponse à partir de pièces de recette validées, vérifier le manifest, l’export ZIP, l’audit et la preuve de dépôt. Vérifier les workers de rétention et de webhook, l’idempotence de consommation, l’absence de doublons et l’absence de données financières dans les messages externes.

### 6.7 Résilience

Contrôler la reprise après redémarrage d’un worker, la reconnexion PostgreSQL, la non-perte d’un événement outbox et la lisibilité des logs structurés. Vérifier qu’un backup peut être restauré dans un environnement isolé sans mélanger les tenants ni exposer les documents privés.

## 7. Stratégie de canary et observation

Si l’infrastructure le permet, commencer par un trafic canary limité à des comptes internes de recette. Maintenir une période d’observation couvrant au minimum une lecture, un commit pricing, un upload, un export et un événement outbox. Comparer les erreurs, latences, saturation DB, consommation mémoire et files workers avec les seuils définis par l’exploitation.

Tout dépassement de seuil, erreur d’isolation tenant, fuite financière, duplication de transition, échec ClamAV, erreur de migration ou dégradation HTTPS déclenche un `NO-GO` et l’arrêt de l’élargissement du trafic.

## 8. Rollback contrôlé

Le rollback applicatif consiste d’abord à redéployer l’image précédente si le schéma reste compatible. Pour une migration incompatible, restaurer la base depuis le backup vérifié dans une fenêtre contrôlée, après arrêt des writers et validation de l’impact. Ne jamais lancer un downgrade automatique pour corriger une panne de production.

Après rollback, vérifier la version Alembic, les tables, les receipts, l’outbox, les workers, l’authentification et l’isolation tenant. Conserver tous les logs et hashes, ouvrir un incident, puis préparer une nouvelle release corrigée.

## 9. Critères de décision

| Décision | Conditions |
|---|---|
| `GO` | Staging réel PASS, backup restauré, migration validée, smoke tests verts, canary stable et approbation explicite |
| `HOLD` | Donnée ou preuve manquante, métrique ambiguë, dépendance opérationnelle non confirmée |
| `NO-GO` | Fuite de secret/donnée financière, échec migration, problème tenant, backup non restaurable, image non pinnée ou healthcheck critique rouge |

## 10. Dossier de conformité à conserver

Le dossier doit contenir la fiche de changement, le tag et commit déployés, les digests, la configuration Compose résolue sans secrets, les logs de migration, `alembic current/heads`, les résultats de healthchecks, les tests HTTPS et ClamAV, les résultats métier, les métriques de surveillance, les backups et hashes, le rapport de restauration, la décision GO/HOLD/NO-GO et les approbations.

## Références

[1]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/main/ops/deploy-preprod.sh "Script de déploiement préproduction"
[2]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/main/ops/docker-compose.preprod.yml "Compose préproduction digest-pinné"
[3]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/main/docs/STAGING_POST_DEPLOYMENT_ACCEPTANCE_PLAN.md "Plan de recette staging post-déploiement"
[4]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/main/backend/alembic/env.py "Configuration Alembic runtime"
