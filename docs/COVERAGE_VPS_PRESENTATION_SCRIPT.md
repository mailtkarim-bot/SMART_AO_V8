# Script de présentation — Couverture et déploiement VPS

**Projet :** SMART_AO V8 — assistant de réponse aux appels d’offres BTP  
**Branche :** `ops/vps-deploy-health-digests-01`  
**Commit de référence :** [`8c07d76`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/8c07d76)  
**CI de référence :** [run 32248079724](https://github.com/mailtkarim-bot/SMART_AO_V8/actions/runs/32248079724)  
**Auteur :** Manus AI  

## Consigne générale de présentation

Cette présentation doit être délivrée comme un point technique de préparation, et non comme un procès-verbal de mise en production. La couverture est mesurée et la CI est verte, mais aucun VPS réel de préproduction n’a encore été provisionné ou vérifié. Il faut donc distinguer systématiquement les éléments **démontrés dans le dépôt et la CI** des contrôles qui nécessitent encore une infrastructure cible, des secrets opérationnels et des preuves produites à distance.

Le fil directeur est le suivant : les routes patronales constituaient un angle mort important ; elles ont été renforcées par des tests HTTP ciblés ; le script de déploiement démarre désormais explicitement le worker webhook ; puis le déploiement VPS devra être accepté uniquement après sept preuves indépendantes.

---

## Slide 1 — SMART_AO V8 — Couverture & Gate VPS

### Message à dire

« Cette présentation résume deux sujets qui doivent avancer ensemble : la remontée de la couverture sur les modules métier sensibles et la préparation du gate de déploiement VPS. Nous travaillons sur la branche `ops/vps-deploy-health-digests-01`, qui contient le socle de tests, les scripts opérateur et les contrôles CI nécessaires pour préparer la préproduction.

Le point important est la distinction entre préparation et validation. Le dépôt est prêt à être testé contre un VPS, mais aucun VPS réel n’est encore disponible dans notre environnement. Nous ne présenterons donc aucun résultat de charge, de TLS, de sauvegarde distante ou de restauration comme déjà acquis. Les résultats confirmés concernent la suite de tests, la couverture locale, les contrats opérateur et la CI GitHub.

L’objectif de la session est d’abord de sécuriser la marge de couverture, ensuite de fermer les écarts opérateur identifiés, et enfin de dérouler le gate VPS lorsque l’infrastructure sera réellement provisionnée. »

### Transition

« Commençons par la mesure de référence qui permet de piloter ce durcissement sans ambiguïté. »

---

## Slide 2 — Le jalon global est atteint, la marge doit être protégée

### Message à dire

« La campagne backend complète compte 558 tests réussis et produit une couverture globale avec branches de 86,72 %. Le seuil strict configuré dans le projet est de 85,50 %, ce qui laisse une marge de 1,22 point. Cette marge est suffisante pour passer la CI, mais elle ne doit pas être considérée comme une autorisation de relâcher les tests : les prochaines modifications métier peuvent rapidement consommer cet écart.

La couverture de 86,72 % est une mesure locale issue de la campagne complète. La CI du commit de référence est verte sur les jobs backend, frontend et sécurité image ; elle valide le seuil configuré et les contrôles de qualité du dépôt. En revanche, elle ne constitue pas une preuve de fonctionnement d’un VPS, d’un certificat TLS réel, d’une sauvegarde hors machine ou d’un worker exécuté en production.

La règle de pilotage retenue est donc de maintenir au moins 86 % tout en continuant à couvrir les branches qui portent des risques de sécurité, d’idempotence, de stockage et de transitions métier. »

### Chiffres à commenter

| Indicateur | Valeur | Interprétation |
|---|---:|---|
| Tests backend réussis | **558** | Campagne complète locale |
| Couverture globale avec branches | **86,72 %** | Marge au-dessus du gate |
| Seuil CI strict | **85,50 %** | Seuil bloquant configuré |
| Marge courante | **+1,22 point** | À protéger par les prochains lots |
| VPS réel vérifié | **Non** | Infrastructure cible indisponible |

### Transition

« La moyenne globale est satisfaisante, mais elle masque encore des zones faibles. Regardons où se trouve le risque résiduel. »

---

## Slide 3 — Les routes HTTP patronales sont le principal angle mort

### Message à dire

« La priorité de ce slice vient des façades HTTP patronales. Avant l’ajout des tests, `patron_submission` se situait à 29,31 % et `patron_actions` à 35,48 %. La transmission de préparation était également faible, à 37,50 %. Ces modules sont importants parce qu’ils exposent les opérations de dépôt, d’export, de file d’actions et de transitions d’état.

Le risque n’est pas uniquement celui d’un code non exécuté. Une branche HTTP non testée peut modifier un code de statut, exposer une information interdite, ignorer une clé d’idempotence ou accepter une transition incorrecte. Le plan de couverture traite donc séparément les contrats HTTP, les services techniques comme `document_storage`, l’observabilité et l’orchestrateur de préparation.

Les autres priorités sont ordonnées par combinaison de risque et de rendement : `logging` à 59,38 % pour la traçabilité, `document_storage` à 76,60 % pour les chemins et I/O, puis `preparation/service` à 79,86 % pour l’orchestration. Le but n’est pas de remplir artificiellement des lignes ; chaque test doit confirmer un invariant ou une décision observable. »

### Transition

« Cette logique conduit à organiser les travaux en lots, chacun associé à un invariant métier vérifiable. »

---

## Slide 4 — Chaque lot de tests protège un invariant métier

### Message à dire

« Le plan de remontée est organisé en six lots. Le lot A couvre les fondations techniques et l’observabilité. Le lot B traite les contrats HTTP du wizard et du cockpit patron. Le lot C se concentre sur le DCE, la quarantaine et le stockage. Le lot D couvre l’orchestrateur de préparation et la revue. Le lot E renforce le wizard collaborateur et les actions patronales. Enfin, le lot F traite pricing, preuves et rapports.

Ces lots sont encadrés par cinq invariants. Premièrement, le tenant est toujours résolu côté serveur et ne provient pas d’un identifiant de confiance fourni par le client. Deuxièmement, les données financières restent absentes des contrats collaborateur et des webhooks. Troisièmement, les registres immuables restent append-only. Quatrièmement, les commandes vérifient la révision optimiste. Cinquièmement, le rejeu idempotent ne doit pas produire de double effet.

Cette méthode permet de lier la couverture au comportement attendu. Un pourcentage sans ces assertions ne suffirait pas à qualifier le socle. »

### Transition

« Le slice livré applique cette méthode aux deux façades patronales les plus faibles. »

---

## Slide 5 — Les façades patronales sont maintenant testées par branches

### Message à dire

« Nous avons ajouté 35 tests de routes dans `backend/tests/api/test_patron_submission_actions_routes.py`. Ils utilisent un runtime FastAPI isolé et des services contrôlés afin de couvrir les décisions de route sans dépendre d’un système externe.

Pour `patron_submission`, les tests vérifient la préparation du dossier avec le parcours 201 puis 200 au rejeu, les refus d’authentification, les permissions, les clés d’idempotence réutilisées, les commandes déjà en cours, les conflits de révision, les dossiers introuvables et les préparations bloquées. L’export vérifie aussi le statut 200, le contenu binaire ZIP, `Content-Type: application/zip`, `Cache-Control: no-store` et le nom de fichier, puis couvre les refus, les manifests invalides et l’indisponibilité du stockage.

Pour `patron_actions`, les tests couvrent la lecture de la file et son `open_count`, la création idempotente, les permissions patron, les conflits de commande, les doublons métier, les cas invalides, puis les transitions avec rejeu, conflit de révision, action déjà fermée et transition invalide. Les erreurs sont contrôlées par leurs codes HTTP et leurs détails contractuels. »

### Résumé des branches couvertes

| Surface | Scénarios principaux |
|---|---|
| Préparation submission | 201 nominal, 200 replay, 401, 403, 404, 409, 422 |
| Export ZIP | Octets ZIP, en-têtes privés, 404, 403, 422, 503 |
| File d’actions | Projection, `open_count`, permissions, 403 |
| Création d’action | 201, 200 replay, 403, 409, 422 |
| Transition | 201, 200 replay, conflits, action fermée, transition invalide |
| Authentification | Bearer absent, Basic, Bearer vide, contexte invalide |

### Transition

« La couverture HTTP est renforcée. Il faut maintenant s’assurer que le chemin opérateur démarre réellement tous les composants attendus. »

---

## Slide 6 — Le déploiement préproduction démarre toute la chaîne

### Message à dire

« Le script `ops/deploy-preprod.sh` suit quatre familles d’opérations. Il valide d’abord la configuration et les digests d’images. Il attend ensuite PostgreSQL, effectue la sauvegarde prévue et applique les migrations Alembic jusqu’à la tête. Il démarre enfin les services applicatifs, puis exécute les smoke tests et healthchecks.

Le correctif de ce slice concerne le démarrage explicite du worker `submission-export-webhook-worker`. La commande de démarrage inclut désormais le backend, le worker de rétention DCE, le worker d’export webhook, le frontend et Caddy. Cette exigence est protégée par `backend/tests/ops/test_preprod_ops_contract.py`, qui vérifie que le nom du worker et sa présence dans la commande `compose up -d` ne peuvent pas disparaître silencieusement.

La CI vérifie la syntaxe et les contrats du dépôt, mais elle ne remplace pas l’exécution sur une machine cible. Sur le VPS, il faudra confirmer que le service est effectivement `running`, que son healthcheck est cohérent, que sa boucle de consommation traite l’outbox et qu’aucune donnée financière ne traverse le payload webhook. »

### Commande opérateur attendue sur le VPS

```bash
docker compose logs --since=15m submission-export-webhook-worker
```

« Cette commande est une procédure future de vérification ; elle n’a pas encore produit de logs, car aucun VPS de préproduction n’est provisionné. »

### Transition

« Le démarrage des services ne suffira pas à accepter la préproduction. Il faut obtenir sept preuves indépendantes. »

---

## Slide 7 — Le gate VPS exige sept preuves indépendantes

### Message à dire

« Le premier contrôle porte sur le réseau et TLS : le domaine doit répondre en HTTPS avec un certificat valide, tandis que PostgreSQL et ClamAV restent inaccessibles depuis Internet. Le deuxième contrôle est le test EICAR : le fichier de test doit être refusé par ClamAV et placé dans le chemin de quarantaine attendu, sans être matérialisé comme document propre.

Le troisième contrôle valide l’export ZIP et l’outbox webhook. L’archive doit être déterministe, le worker doit traiter l’événement, et le payload doit rester limité aux données autorisées. Le quatrième contrôle concerne la sauvegarde hors VPS, avec manifeste et hashes vérifiables. Le cinquième contrôle est la restauration isolée : il faut vérifier la présence des tables, l’échantillon documentaire, l’isolation tenant et l’état sémantique de l’outbox.

Les deux derniers contrôles portent sur les timers systemd de backup et de santé, puis sur une supervision externe capable de déclencher une alerte. Toute preuve manquante, tout secret exposé ou tout service interne publié doit produire un statut refusé, pas une validation partielle. »

### Preuves à conserver

| Contrôle | Preuve minimale |
|---|---|
| Réseau/TLS | URL HTTPS, certificat, ports exposés |
| EICAR | Réponse de rejet et entrée de quarantaine |
| Export/outbox | Hash ZIP, événement traité, payload sans finance |
| Backup externe | Manifeste, hash, destination hors VPS |
| Restauration | Logs, tables, échantillon, tenant, outbox |
| Timers | `systemctl status` et journaux d’exécution |
| Supervision | Capture ou événement d’alerte contrôlé |

### Transition

« La conclusion doit donc séparer clairement ce qui est déjà validé dans GitHub de ce qui dépend encore du provisionnement VPS. »

---

## Slide 8 — Prochaine séquence : CI verte, durcissement, puis VPS réel

### Message à dire

« Le commit `8c07d76` publie les 35 tests de routes patronales, le test de contrat opérateur et le démarrage explicite du worker webhook. La CI `32248079724` est verte sur le frontend, le backend et la sécurité image. La campagne locale complète atteint 86,72 % avec branches sur 558 tests.

La prochaine étape n’est pas de déclarer le VPS validé. Il faut d’abord disposer de l’hôte cible, des DNS, des secrets opérationnels, du stockage de backup hors VPS et du mécanisme de supervision. Une fois ces prérequis fournis, le déploiement doit être exécuté de façon contrôlée, puis le worker doit être vérifié par ses logs et par l’état de l’outbox. Les campagnes de charge et de restauration ne seront considérées comme réalisées qu’avec des artefacts conservés.

La décision finale est donc simple : le socle logiciel est publié et la CI est verte ; la préproduction VPS reste préparée mais non validée opérationnellement. Cette distinction protège la traçabilité et évite d’anticiper des résultats que l’infrastructure n’a pas encore produits. »

### Transition de clôture

« Nous pouvons maintenant passer au prochain lot de couverture ou, dès que le VPS sera disponible, au gate opérationnel avec conservation systématique des preuves. »

---

## Statut des logs du worker sur le VPS

Aucun log réel du worker `submission-export-webhook-worker` ne peut être affiché actuellement, car aucun VPS de préproduction n’est provisionné ou connecté à cette session. L’état disponible est donc **NON EXÉCUTÉ / NON OBSERVÉ**, et non « sain » ou « en erreur ».

Après déploiement, les commandes minimales seront :

```bash
docker compose ps submission-export-webhook-worker
docker compose logs --since=15m submission-export-webhook-worker
docker compose logs --since=15m submission-export-webhook-worker | grep -E "ERROR|WARNING|processed|retry|dead-letter"
```

La preuve attendue devra inclure l’horodatage, l’identifiant du conteneur, les événements consommés, le nombre de retries éventuels et l’absence de données financières dans les lignes de log ou le payload journalisé.

## Références

[1]: https://github.com/mailtkarim-bot/SMART_AO_V8/commit/8c07d76 "Commit 8c07d76 — tests patronaux et démarrage explicite du worker"

[2]: https://github.com/mailtkarim-bot/SMART_AO_V8/actions/runs/32248079724 "CI run 32248079724 — backend, frontend et sécurité image"

[3]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/ops/vps-deploy-health-digests-01/backend/tests/api/test_patron_submission_actions_routes.py "Tests HTTP patron_submission et patron_actions"

[4]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/ops/vps-deploy-health-digests-01/ops/deploy-preprod.sh "Script de déploiement préproduction"

[5]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/ops/vps-deploy-health-digests-01/docs/VPS_DEPLOYMENT_POST_DEPLOYMENT_PLAN.md "Plan de déploiement et de vérification post-déploiement VPS"

[6]: https://github.com/mailtkarim-bot/SMART_AO_V8/blob/ops/vps-deploy-health-digests-01/docs/COVERAGE_UNDER_85_ANALYSIS.md "Plan de remontée des modules sous 85 %"
