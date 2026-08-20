# 1 - Conclusion

En conclusion, notre socle applicatif est prêt pour la phase de validation en préproduction, mais gardons en tête que la preuve définitive sur le VPS reste une étape à part entière. Tous les livrables techniques sont d'ores et déjà disponibles pour l'équipe. Vous disposez du rapport complet de benchmark, de l'audit du code webhook, du plan de charge détaillé ainsi que de la spécification opérationnelle du VPS. Ces documents constituent la base de notre travail pour les prochaines heures.

# 2 - Le worker webhook couvre les décisions critiques

Passons maintenant à la sécurité des notifications. Le worker webhook couvre les décisions critiques avec quatorze tests unitaires dédiés et une couverture de code de quatre-vingts pour cent incluant les branches. Nous validons ici les leases, les messages absents, les topics incorrects, les retries HTTP et l'idempotence. Côté données, la charge utile respecte une allowlist stricte comprenant le dossier, le hash de l'archive et le canal de téléchargement. Aucun montant, aucun snapshot financier, aucune clé de stockage ni aucun contenu documentaire ne transitent par ce canal, ce qui garantit l'absence totale de fuite financière. Et pour sécuriser ce dispositif en conditions réelles, quatre points précis restent à traiter.

# 3 - Quatre risques restent à fermer avant production

Ces quatre risques doivent impérativement être fermés avant la mise en production. D'abord, nous devons valider la concurrence PostgreSQL réelle entre plusieurs workers utilisant SKIP LOCKED. Ensuite, il s'agit de tester le comportement face au réseau réel avec les timeouts, les erreurs HTTP, les URLs invalides et les codes de limitation de débit. Troisième point, nous gérons les redirections tout en renforçant la validation des hashes SHA-256 au format hexadécimal. Enfin, nous mettons en place la politique d'échec définitif combinée aux alertes et au mécanisme de dead letter. Une fois ces garanties logicielles posées, l'infrastructure cible fera l'objet d'une qualification rigoureuse.

# 4 - Le VPS sera validé par un gate en sept contrôles

Cette qualification s'appuie sur un processus de validation strict. Le VPS sera validé par un gate en sept contrôles successifs. Nous commençons par l'accès SSH, le DNS, les permissions des secrets, le pare-feu et le stockage de sauvegarde. Viennent ensuite le fichier Compose à digests épinglés, le déploiement des services, la vérification des sondes de santé TLS et les tests antivirus avec le fichier EICAR. Les contrôles six et sept couvrent l'export, l'outbox, le webhook, ainsi que les sauvegardes hors site et la restauration isolée. Cette séquence méthodique garantit un déploiement propre avant de lancer les tests de charge progressifs.

# 5 - La charge sera progressive et arrêtée par des garde-fous

La mise en charge se fera par paliers stricts pour tester la robustesse du système avant la mise en production. Nous commençons par dix, puis cinquante, puis cent exports séquentiels, avant de pousser à dix requêtes concurrentes. Pendant ces tests, nous surveillons de près la latence, le ratio de compression, les métriques p50 et p95, ainsi que la consommation CPU, mémoire RSS et les entrées sorties disque. Nous avons défini des critères d'arrêt immédiat très clairs. Si nous détectons la moindre perte de message dans l'outbox, une fuite financière, des erreurs serveur persistantes ou une saturation anormale, nous coupons tout. La validation finale exige zéro perte, des mécanismes de reprise bornés et une restauration isolée parfaitement maîtrisée.

# 6 - Prochaines étapes ordonnées

Pour consolider ce travail, nous devons suivre une feuille de route rigoureuse et ordonnée. Nous allons d'abord implémenter les tests PostgreSQL pour valider la concurrence avec l'utilisation de skip locked, tout en créant un endpoint HTTP local pour nos tests. Ensuite, nous répéterons le benchmark cinq fois pour chaque profil afin de publier des médianes et des percentiles p95 indiscutables, et nous élargirons notre corpus avec des fichiers bureautiques non sensibles. Dès que nous aurons l'accès au VPS, au DNS et au stockage distant, nous pourrons exécuter notre grille de contrôle et automatiser l'injection de charge depuis un runner totalement séparé.

# 7 - Cover

Bienvenue à tous. Nous faisons le point aujourd'hui sur la version huit de Smart AO, en nous concentrant sur le benchmark de compression zip, l'audit du worker webhook et notre feuille de route pour le déploiement sur VPS. Ce travail pose les bases techniques indispensables avant de basculer en préproduction. Voyons ensemble les premiers enseignements chiffrés.

# 8 - Décision en une phrase

Notre décision principale tient en une phrase. Le niveau de compression deflate six est retenu. Il réduit la taille de notre archive BTP de trois virgule soixante-dix pour cent sur le corpus mesuré, sans aucun gain supplémentaire au niveau neuf. Ces chiffres proviennent d'une mesure locale reproductible, avec des hashes et des timestamps figés. Gardez bien en tête que cette validation est strictement locale pour l'instant et que le test grandeur nature sur le VPS reste à venir.

# 9 - Le corpus reflète des documents déjà compressés

Pour comprendre ce résultat, regardons de plus près notre corpus de test. Il se compose de deux documents PDF publics du secteur BTP, totalisant quatre-vingt-dix-huit pages pour environ cinq virgule huit mégaoctets. Le premier document compte soixante-quinze pages de cahier des charges de plomberie, et le second vingt-trois pages de CCTP. Ces fichiers sont par nature déjà compressés, ce qui limite mécaniquement le gain additionnel qu'un algorithme de type Deflate peut espérer obtenir. La structure interne des PDF explique pourquoi pousser la compression plus loin ne sert à rien.

# 10 - Le niveau 6 domine le compromis taille / temps

Le tableau comparatif confirme sans appel ce compromis entre taille et temps d'exécution. Le profil Stored est très rapide mais ne compresse rien. Le profil Deflate six atteint une taille de cinq millions cinq cent quatre-vingt-douze mille octets pour deux cent vingt millisecondes. Passer au niveau neuf donne exactement le même résultat en taille, mais alourdit le temps de traitement à deux cent quarante-huit millisecondes. Le choix du niveau six s'impose donc naturellement. Nous devrons toutefois compléter ces mesures locales par l'analyse des percentiles p50 et p95, de la consommation mémoire RSS, du processeur, des entrées-sorties, et étendre le test à d'autres formats comme le docx, le xlsx, le csv ou le texte brut.

# 11 - L’implémentation protège la mémoire, mais le flux source reste perfectible

Du côté de l'implémentation, notre code protège efficacement la mémoire grâce à l'utilisation d'un spool temporary file qui bascule sur disque au-delà de huit mégaoctets. De plus, les timestamps et les permissions sont figés pour garantir un hachage stable et une stricte confidentialité. Mais le flux source reste perfectible. Actuellement, notre processus lit chaque fichier PDF deux fois, d'abord pour calculer son empreinte, puis pour l'écrire dans l'archive. La prochaine étape d'optimisation consistera à lire les données par blocs pour alléger la pression sur le système. Transition vers le sujet suivant.
