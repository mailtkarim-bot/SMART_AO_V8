# Observation API BOAMP — 22 août 2026

La page officielle du jeu de données BOAMP indique que les enregistrements sont consultables et téléchargeables via une API. La console expose le point de terminaison des enregistrements de l’Explore API 2.1 et les paramètres `dataset`, `select`, `where`, `group_by`, `order_by`, `limit`, `offset`, `refine`, `exclude`, `lang` et `timezone`. La recherche texte n’est pas appliquée depuis la console API.

Source visitée : https://www.boamp.fr/explore/dataset/boamp/api/

Avant d’implémenter un adaptateur, il faudra confirmer dans la documentation de l’API les noms de champs autorisés, le plafond de `limit`, les codes d’erreur et les éventuelles limites d’usage. Aucun appel applicatif réel n’a été effectué dans le cadre de cette observation.

La réponse affichée par la page officielle expose notamment `idweb`, `id`, `objet`, `famille`, `dateparution`, `datefindiffusion`, `datelimitereponse`, `nomacheteur`, `etat`, `descripteur_code`, `descripteur_libelle`, `type_marche`, `nature` et `nature_categorise`. Elle contient également des champs plus riches tels que `donnees` et `gestion` pouvant inclure des informations détaillées et parfois financières ; un adaptateur initial devra donc appliquer un `select` allowlisté et exclure ces champs riches. La page affichait 1 699 619 enregistrements au moment de la consultation, chiffre contextuel non utilisé comme donnée métier.

La documentation et la page visitée confirment une API de recherche/téléchargement en lecture. Le futur slice doit rester tenant-scoped au niveau de la mise en cache ou de l’alerte interne, limiter `limit`/`offset`, normaliser les erreurs et ne jamais copier la totalité des données BOAMP dans une réponse HTTP collaborateur ou dans un contrat financier.
