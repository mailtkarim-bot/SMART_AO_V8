# Plan technique — couverture PostgreSQL et cas limites webhook

## État observé

Le dernier run CI `32189035352` est terminé avec succès. Les trois jobs sont verts : backend en 5 min 13 s, frontend en 17 s et image-security en 5 s. Le job backend a exécuté le lint, le scan de secrets, l’audit de dépendances, Bandit et la suite de tests avec couverture.

La reproduction locale exacte de la commande CI a exécuté **465 tests**, mais a obtenu **84,82 %** et a échoué de 0,18 point au seuil local de 85 %. Cette divergence doit être traitée comme une anomalie de reproductibilité à investiguer, même si le run CI est vert. Le module `submission_export_webhook.py` atteint localement 80 % avec branches sur sa suite ciblée de 14 tests.

## 1. Fixture PostgreSQL dédiée

Créer une fixture dans `backend/tests/application/test_submission_export_webhook_integration.py` en réutilisant la fixture `database_engine`/`session_factory` du dépôt. Chaque test doit tronquer les tables tenant-scoped dans une transaction contrôlée, créer un tenant et un `DomainEventRecord`, puis créer un `OutboxMessageRecord` sur le topic `submission.package.exported`.

Le payload de fixture doit contenir uniquement : `submission_package_id`, `archive_sha256` en hexadécimal de 64 caractères et `delivery=DOWNLOAD`. Ajouter volontairement des clés financières dans un test négatif pour vérifier qu’elles ne sont jamais transmises au récepteur.

Le worker doit être construit avec une `sessionmaker` réelle et un endpoint HTTP local contrôlé. Le récepteur de test doit enregistrer le nombre d’appels, le body et les headers, sans écrire le contenu documentaire sur disque.

## 2. Test de concurrence `SKIP LOCKED`

Le scénario crée un seul message PENDING puis lance deux workers avec deux sessions SQLAlchemy indépendantes. Une barrière de synchronisation doit faire démarrer les deux claims au même moment. Chaque worker exécute `run_once(now=NOW)`.

Assertions obligatoires :

| Assertion | Résultat attendu |
|---|---|
| Nombre de claims effectifs | 1 |
| Nombre de livraisons HTTP | 1 |
| Statut final outbox | `PUBLISHED` |
| Compteur `attempt_count` | 0 sur le chemin nominal |
| Second worker | `skipped=1` ou aucun message claimé |
| Données transmises | allowlist uniquement |

Le test doit être répété plusieurs fois pour réduire le risque de faux positif lié à l’ordonnancement. Il ne doit pas utiliser un mock de session pour valider `FOR UPDATE SKIP LOCKED`.

## 3. Test de lease et récupération

Créer un message dont `next_attempt_at` est dans le futur : aucun worker ne doit le traiter. Créer ensuite un message dont le lease a expiré : un worker doit pouvoir le reprendre. Vérifier qu’un message temporairement claimé n’est pas repris par un second worker avant l’expiration du lease.

Tester également un lease court et une livraison plus lente que le timeout. Le résultat attendu est un retry sans double mutation de l’outbox.

## 4. Endpoint HTTP contrôlé

Utiliser un serveur HTTP local contrôlé dans le test, ou un adapter de transport injectable, avec les réponses suivantes :

| Réponse | Attendu |
|---|---|
| 200 / 204 | `PUBLISHED`, `delivered=1` |
| 3xx | comportement explicitement refusé ou policy documentée; par défaut retry |
| 429 | retry borné, conservation du message et code dédié |
| 500 / 503 | retry borné avec code HTTP |
| timeout | retry `EXPORT_WEBHOOK_DELIVERY_FAILED` |
| fermeture socket | retry sans exception non maîtrisée |
| réponse lente sous timeout | publication normale |

Le test doit vérifier `Content-Type`, `User-Agent`, méthode POST et absence des champs `manifest_sha256`, `financial_snapshot_id`, montants, lignes de prix, storage keys et contenu.

## 5. Validation stricte du payload

Durcir `_safe_payload` pour accepter uniquement :

```text
submission_package_id : UUID canonique
archive_sha256        : [0-9a-f]{64}
delivery              : DOWNLOAD
```

Décider explicitement si les UUID non canoniques sont normalisés ou refusés. Refuser les hash majuscules si le contrat reste strictement lowercase, ou normaliser avant hash si cette compatibilité est nécessaire. Ajouter des tests pour les chaînes de 64 caractères non hexadécimales, les valeurs nulles, les types non chaînes, les champs supplémentaires sensibles et les valeurs Unicode.

## 6. Redirections et sécurité réseau

Configurer le transport pour ne pas suivre automatiquement les redirections, ou vérifier que toute redirection reste sur l’hôte et le schéma autorisés. Refuser les URLs avec userinfo, fragment ou hôte absent. En production, préférer HTTPS et une allowlist d’hôtes si un contrat d’intégration est disponible.

Ajouter un test qui simule une redirection vers un autre hôte et vérifie qu’aucune donnée n’est envoyée à la destination finale.

## 7. Échec définitif et observabilité

Définir un maximum d’essais ou une durée maximale de retry. Au dépassement, passer le message en `FAILED`, renseigner un code d’erreur borné et émettre une alerte opérateur sans payload sensible. La décision doit préciser si une table dead-letter est nécessaire ou si `outbox_messages.status=FAILED` suffit.

Ajouter des compteurs non sensibles : messages claimés, livrés, ignorés, retry, failed, âge du plus ancien retry et durée de livraison p50/p95. Ne jamais journaliser le body complet, un hash financier ou un storage key.

## 8. Reproductibilité de la couverture

Comparer les versions Python, uv, dépendances, variables d’environnement, ordre de test et présence éventuelle de tests sélectionnés entre CI et local. Exécuter deux fois la commande CI complète avec un fichier de couverture séparé. Conserver les sorties `TOTAL`, nombre de tests, warnings et versions.

L’objectif immédiat est de dépasser 85 % avec une marge d’au moins 0,5 point, puis de conserver un seuil bloquant. L’écart local de 84,82 % doit être résolu avant d’interpréter la couverture comme stable.

## Ordre de réalisation

1. Ajouter le test PostgreSQL de claim concurrent et le test HTTP 2xx réel.
2. Ajouter leases expirés, non échus, timeout et 429.
3. Durcir hash/UUID/URL et ajouter les tests de redirection.
4. Décider et implémenter `FAILED`/dead-letter et les métriques bornées.
5. Rejouer deux fois la couverture complète localement et dans CI.
6. Publier le slice uniquement lorsque les deux environnements passent avec une marge supérieure à 0,5 point.
