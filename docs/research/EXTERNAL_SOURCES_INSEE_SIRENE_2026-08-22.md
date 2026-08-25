# Sources externes — connecteur INSEE Sirene

## Décision

Le premier connecteur externe ajouté après le stockage objet est un adaptateur **read-only** vers l’API officielle INSEE Sirene. Il est exposé derrière `CompanyRegistryPort` dans le bounded context `enterprise` et n’est pas appelé automatiquement par une route HTTP ni par une transition métier. L’activation est explicite via `SMART_AO_INSEE_ENABLED=1`, avec un token injecté à l’exécution seulement.

Le connecteur valide un SIREN de neuf chiffres, applique un timeout borné, refuse les redirections, normalise uniquement les faits non financiers nécessaires à une vérification d’entreprise et échoue fermé sur les réponses d’authentification, de quota, serveur ou de schéma inattendu. Il ne persiste pas et ne modifie pas la bibliothèque entreprise. Les tests utilisent un client simulé ; aucune requête réelle ni secret n’a été exécuté dans le sandbox.

## Sources officielles

1. [API Sirene — portail API INSEE](https://portail-api.insee.fr/catalog/api/2ba0e549-5587-3ef1-9082-99cd865de66f) — URL officielle `https://api.insee.fr/api-sirene/3.11`, version de référence annoncée par le portail et description de l’accès aux unités légales et établissements.
2. [Documentation API Sirene — portail API INSEE](https://portail-api.insee.fr/catalog/api/2ba0e549-5587-3ef1-9082-99cd865de66f/doc) — point d’entrée documentaire officiel, à consulter avant toute recette réelle ou évolution de contrat.
3. [API Sirene open data — data.gouv.fr](https://www.data.gouv.fr/dataservices/api-sirene-open-data) — référencement public du service et de ses données ouvertes.

## Limites et suite

Le portail INSEE signale l’évolution de la nomenclature NAF vers NAF 2025 à compter de 2027 ; le code d’activité ne doit donc pas être traité comme une valeur intemporelle. Une prochaine évolution devra versionner la provenance et la date d’observation si l’enrichissement devient persistant. Les statuts de diffusion partielle doivent également être respectés : l’application ne doit pas rediffuser de données personnelles ni utiliser ces informations à des fins de prospection.

La recette restante doit être réalisée sur une machine opérateur avec un token de test, un SIREN non sensible et des assertions de non-persistance/non-fuite des secrets. Cette intégration est **codée et testée avec faux client**, mais elle n’est pas une preuve de disponibilité de l’API INSEE ni une certification de production.
