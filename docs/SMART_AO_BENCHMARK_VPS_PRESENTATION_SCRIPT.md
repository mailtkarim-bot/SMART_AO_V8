# Script détaillé — Benchmark ZIP et validation VPS

**Durée cible :** 12 à 15 minutes  
**Public :** responsable produit, équipe backend, opérateur infrastructure  
**Support :** présentation SMART_AO V8 — Benchmark ZIP et validation VPS

## Slide 1 — Cover

Bienvenue. Cette présentation fait le point sur trois sujets liés à la préparation de SMART_AO V8 : le benchmark de compression des dossiers de réponse, l’audit du worker webhook de notification outbox et la préparation de la validation opérationnelle sur un VPS réel.

L’objectif n’est pas de déclarer la production prête sur la seule base de tests locaux. Nous allons séparer clairement les résultats déjà mesurés, les garanties apportées par le code et les preuves qui restent à obtenir sur l’infrastructure cible. Le fil directeur est la maîtrise du compromis entre taille d’archive, coût de traitement, confidentialité et opérabilité.

**Transition vers la slide 2 :** Commençons par la décision principale issue du benchmark.

## Slide 2 — Décision en une phrase

La décision actuelle est de conserver `ZIP_DEFLATED` avec `compresslevel=6`. Sur le corpus mesuré, ce profil réduit la taille de l’archive de 3,70 % par rapport à la taille des fichiers entrants, alors que le niveau 9 ne fournit aucune réduction additionnelle observable.

Le corpus comprenait deux PDF publics BTP, représentant environ 5,81 Mo et 98 pages. La mesure est reproductible : les entrées sont ordonnées, les timestamps ZIP sont figés, les permissions sont déterministes et un SHA-256 est calculé sur l’archive finale. Cette conclusion reste toutefois une conclusion locale. Elle ne constitue ni un test de capacité VPS, ni une mesure de performance réseau ou de stockage distant.

**Transition vers la slide 3 :** Pour comprendre pourquoi le gain reste limité, regardons la composition du corpus.

## Slide 3 — Le corpus reflète des documents déjà compressés

Le premier document est un DCE plomberie de 75 pages et le second un CCTP de lot travaux de 23 pages. La taille totale avant archivage est de 5 807 069 octets.

Ce choix est intéressant parce qu’il ressemble à une partie réelle d’un dossier BTP, mais il impose aussi une limite importante : les PDF contiennent déjà souvent des structures compressées. DEFLATE ne peut donc pas récupérer autant d’espace que sur un fichier texte, un CSV, un DOCX ou un XLSX non compressé. Le résultat de 3,70 % doit être interprété comme une mesure du corpus présent, et non comme une promesse générale pour tous les dossiers.

Les documents publics ont été utilisés pour la mesure puis supprimés du workspace. Le dépôt conserve le script et les résultats, pas les fichiers sources.

**Transition vers la slide 4 :** Comparons maintenant les trois profils de compression et le temps qu’ils consomment.

## Slide 4 — Le niveau 6 domine le compromis taille / temps

`ZIP_STORED` produit une archive de 5 807 704 octets en environ 0,048 seconde : il est rapide, mais n’apporte aucun gain de compression. `ZIP_DEFLATED` niveau 6 descend à 5 592 481 octets en environ 0,220 seconde. Le niveau 9 produit exactement la même taille, mais en environ 0,248 seconde sur cette exécution.

Le niveau 9 coûte donc davantage sans bénéfice de taille sur ce corpus. La décision rationnelle est de garder le niveau 6 comme baseline. Cette baseline devra être enrichie par cinq répétitions à froid et à chaud, une médiane, un p95, une mesure RSS, le CPU, les I/O et un corpus multi-format avant toute décision de capacité.

**Transition vers la slide 5 :** La compression n’est qu’une partie du problème ; observons maintenant la gestion mémoire et le flux de données.

## Slide 5 — L’implémentation protège la mémoire, mais le flux source reste perfectible

L’implémentation utilise `SpooledTemporaryFile` avec un seuil de 8 MiB. Tant que l’archive reste sous ce seuil, le buffer peut rester en mémoire ; au-delà, il bascule vers un fichier temporaire. Cela réduit le risque de conserver une archive volumineuse entièrement en RAM.

Le déterminisme est également protégé par les timestamps fixés et les permissions privées. En revanche, le benchmark lit chaque fichier deux fois : une fois pour calculer son hash dans le manifest, puis une seconde fois pour l’écrire dans le ZIP. Le service applicatif matérialise aussi actuellement le document source en bytes avant l’assemblage.

La prochaine optimisation structurelle serait une interface de stockage lisible par flux ou une opération de hash-and-write par chunks. Elle devra conserver les mêmes hashes, l’ordre des entrées et les mêmes garanties de confidentialité.

**Transition vers la slide 6 :** Passons du ZIP au worker qui notifie l’export et examinons ce qui est déjà testé.

## Slide 6 — Le worker webhook couvre les décisions critiques

Le worker dispose de 14 tests unitaires dédiés. La couverture ciblée du module est de 80 % avec analyse des branches. Les tests couvrent notamment le claim avec lease, l’absence de message, le mauvais topic, le payload invalide, le retry sur réponse HTTP non 2xx, l’absence de configuration webhook et l’idempotence d’un message déjà publié.

La garantie de confidentialité repose sur une allowlist stricte. Le webhook reçoit uniquement l’identifiant du dossier, le hash de l’archive et le canal `DOWNLOAD`. Aucun montant, snapshot financier, storage key ou contenu documentaire ne doit franchir ce contrat.

Cette couverture unitaire est utile, mais elle ne remplace pas un test PostgreSQL réel. Les mocks ne prouvent pas que deux workers concurrents se comportent correctement avec `FOR UPDATE SKIP LOCKED`.

**Transition vers la slide 7 :** Voici les quatre familles de risques qui doivent être fermées avant de considérer le worker prêt pour la production.

## Slide 7 — Quatre risques restent à fermer avant production

Le premier risque est la concurrence réelle : deux sessions doivent tenter de récupérer le même message et nous devons démontrer qu’une seule livraison est effectuée.

Le deuxième concerne le réseau : succès 2xx réel, timeouts, erreurs de connexion, 429 et réponses 5xx doivent être testés avec un serveur contrôlé. Le troisième concerne les redirections et la validation des hashes. Un hash de 64 caractères n’est pas nécessairement un SHA-256 hexadécimal valide, et une redirection incontrôlée peut déplacer un payload vers un hôte imprévu.

Le quatrième est la politique d’échec définitif. Un message qui reste indéfiniment en retry doit déclencher une alerte et, selon la décision d’architecture, passer en `FAILED` ou dans une dead-letter queue.

**Transition vers la slide 8 :** Une fois ces risques logiciels traités, nous pouvons qualifier l’infrastructure VPS selon un gate explicite.

## Slide 8 — Le VPS sera validé par un gate en sept contrôles

Le premier contrôle porte sur les accès, le DNS, les permissions des secrets, le pare-feu et le stockage de sauvegarde. Le deuxième vérifie le Compose digest-pinné et l’absence de ports PostgreSQL ou ClamAV publiés.

Le troisième couvre le démarrage des migrations, de PostgreSQL, ClamAV, du backend, du frontend et de Caddy. Le quatrième vérifie TLS, les certificats et les endpoints live et ready. Le cinquième est le test EICAR, limité à la préproduction, avec un rejet `REJECTED` traçable.

Les deux derniers contrôles portent sur l’export, l’audit, l’outbox et le webhook, puis sur la sauvegarde hors VPS, la restauration isolée, les timers systemd et la supervision externe. Tant que le VPS réel n’est pas disponible, ces contrôles restent spécifiés mais non exécutés.

**Transition vers la slide 9 :** Après le smoke test et les contrôles de sécurité, la charge doit augmenter progressivement avec des garde-fous.

## Slide 9 — La charge sera progressive et arrêtée par des garde-fous

La campagne commencera par un export unique, puis passera à 10 exports séquentiels, 50, 100 et enfin 10 exports concurrents. Entre les paliers, le système doit revenir à un niveau nominal et le backlog outbox doit être observé.

Nous mesurerons la latence des healthchecks, le ratio ZIP, la durée d’assemblage, les p50 et p95, le CPU, la RSS, les I/O disque, le backlog, les retries et les redémarrages. Le test s’arrête immédiatement en cas de perte de message, de fuite de données financières, d’erreurs 5xx persistantes, de saturation mémoire ou de publication d’un port interne.

L’acceptation n’est pas seulement une question de débit. Elle exige zéro perte, zéro fuite, des retries bornés et résorbés, ainsi qu’une restauration isolée réussie.

**Transition vers la slide 10 :** Avant d’exécuter ce protocole, nous devons fermer les écarts de reproductibilité et compléter les tests prioritaires.

## Slide 10 — Prochaines étapes ordonnées

La première étape est de diagnostiquer l’écart de couverture local/CI. La CI a validé le seuil de 85 %, alors que la reproduction locale avec 465 tests a obtenu 84,82 %. Nous devons comparer les versions Python, uv, pytest-cov et coverage, le SHA du commit, la collecte des tests, les warnings, les états PostgreSQL et les rapports JSON/XML de couverture.

Ensuite, nous ajouterons le test PostgreSQL concurrent, un endpoint HTTP local contrôlé, les scénarios timeout/429/redirection, la validation stricte des hashes et une politique `FAILED` ou dead-letter. Le benchmark sera répété cinq fois par profil avec médiane et p95, puis élargi à des formats bureautiques autorisés.

Enfin, avec un VPS, un DNS et un stockage hors site, nous exécuterons le gate opérationnel et automatiserons la charge depuis un runner séparé.

**Transition vers la slide 11 :** Terminons par la décision de maturité actuelle et la distinction entre préparation et preuve opérationnelle.

## Slide 11 — Conclusion

Le choix technique actuel est clair : `ZIP_DEFLATED` niveau 6 est la baseline de compression la plus équilibrée sur le corpus BTP mesuré. Le worker webhook possède ses garanties unitaires essentielles et protège le contrat contre la fuite financière, mais il doit encore être validé avec PostgreSQL réel, un transport HTTP contrôlé et une politique d’échec définitif.

Le socle applicatif est prêt pour une validation préproduction, mais la preuve VPS n’est pas encore acquise. Les artefacts disponibles sont le rapport benchmark, l’audit de code webhook, l’analyse de l’écart de couverture, le plan d’exécution VPS, la spécification opérationnelle et ce script de présentation.

La prochaine décision de gouvernance est donc de fournir la cible VPS et ses accès contrôlés, puis d’exécuter la procédure sans déclarer la production validée avant d’avoir obtenu toutes les preuves.

**Transition de clôture :** Ouvrir les questions sur l’accès VPS, le corpus autorisé et les seuils de charge à contractualiser.
