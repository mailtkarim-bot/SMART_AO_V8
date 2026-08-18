# Rapport benchmark ZIP et audit worker webhook

## Périmètre

Le benchmark a été exécuté sur deux documents publics de consultation BTP au format PDF, téléchargés uniquement pour la mesure locale : un DCE plomberie de 75 pages et un CCTP de lot travaux de 23 pages. Les fichiers bruts restent des artefacts locaux et ne sont pas ajoutés au dépôt applicatif.

Sources du corpus : [DCE plomberie de Pernes-les-Fontaines](https://www.perneslesfontaines.fr/uploads/co_document/dce-complet-relance-lot-n-5-plomberie.pdf) et [CCTP lot 4 Grand Fitzjames](https://www.arraa.org/sites/default/files/media/documents/cahier_des_charges/cctp_lot4_grandfitzjames_smbvbreche.pdf). La taille totale mesurée avant archivage est de **5 807 069 octets**.

Le script reproductible est `scripts/benchmark_submission_zip_corpus.py`. Il fixe les timestamps ZIP, conserve les permissions privées, calcule le SHA-256 de l’archive et compare `ZIP_STORED`, `ZIP_DEFLATED` niveau 6 et `ZIP_DEFLATED` niveau 9.

## Résultats

| Profil | Taille archive | Ratio archive / entrée | Réduction | Temps |
|---|---:|---:|---:|---:|
| `ZIP_STORED` | 5 807 704 octets | 1,000109 | -0,01 % | 0,047991 s |
| `ZIP_DEFLATED` niveau 6 | 5 592 481 octets | 0,963047 | 3,70 % | 0,220432 s |
| `ZIP_DEFLATED` niveau 9 | 5 592 481 octets | 0,963047 | 3,70 % | 0,248503 s |

Le niveau 6 réduit la taille de l’archive de **215 223 octets** par rapport à `ZIP_STORED`, soit environ 3,70 %, avec un temps de compression inférieur au niveau 9 sur cette exécution. Le niveau 9 n’apporte aucune réduction supplémentaire et coûte environ 12,7 % de temps supplémentaire par rapport au niveau 6. Le choix de `ZIP_DEFLATED` niveau 6 est donc confirmé pour ce corpus.

Les PDF sont déjà partiellement compressés, ce qui explique le gain modéré. Ce résultat ne doit pas être extrapolé à des fichiers DOCX, XLSX, CSV ou TXT non compressés, qui peuvent présenter des gains supérieurs. Il ne mesure pas non plus la consommation CPU et mémoire d’un conteneur VPS ; ces métriques restent à collecter sur l’environnement cible.

## Déterminisme

Le benchmark produit un hash d’archive distinct pour chaque profil et conserve des dates ZIP fixes. La validation applicative existante vérifie déjà l’export déterministe du dossier. Une prochaine campagne devra exécuter deux fois le même corpus et confirmer l’égalité exacte des hashes, puis varier l’ordre d’arrivée des documents pour confirmer que l’ordre manifesté par le service reste stable.

## Couverture du worker

La mesure ciblée avec couverture de branches a été exécutée sur 14 tests : **80 % de couverture ligne** du module `submission_export_webhook.py`, avec 22 lignes et 7 embranchements partiels encore non couverts. La CI complète reste le référentiel du seuil global du projet ; la couverture ciblée est volontairement analysée séparément pour éviter de masquer les zones à risque derrière la couverture des autres modules.

Les chemins désormais couverts sont l’allowlist de payload, l’exclusion des informations financières, le backoff borné, l’absence de configuration webhook, la publication, le claim avec lease, le message absent, le mauvais topic, le payload invalide, le retry sur HTTP non 2xx, l’URL non HTTP(S) et l’idempotence d’un message déjà publié.

Les chemins restant à renforcer sont : le succès réel de `_post_json` avec vérification de la requête émise, les exceptions réseau `HTTPError`, `URLError`, timeout et `OSError`, la lecture de la configuration par `build_default_worker`, la boucle `main`, le traitement multi-message de `run_once`, et un test PostgreSQL concurrent démontrant que deux workers ne livrent pas le même message.

## Cas limites à traiter avant production

| Cas limite | Risque | Test recommandé |
|---|---|---|
| Deux workers claiment simultanément | Double livraison ou lease incohérent | Test PostgreSQL avec deux sessions et `SKIP LOCKED` |
| Le webhook répond 2xx puis le worker tombe avant `PUBLISHED` | Livraison répétée | Endpoint idempotent côté consommateur et test de rejeu |
| Le webhook répond 3xx | Acceptation involontaire d’une redirection | Décider explicitement : traiter comme échec ou interdire les redirections |
| Réponse 429 avec `Retry-After` | Backoff trop agressif | Parser une politique de retry ou conserver le backoff borné documenté |
| Payload avec hash de mauvaise alphabet | Hash de longueur correcte mais invalide | Valider `[0-9a-f]{64}` et ajouter un test |
| URL webhook avec identifiants, fragment ou redirection externe | Fuite de secret ou sortie de périmètre | Interdire userinfo/fragment et contrôler les redirections |
| Endpoint très lent | Accumulation de leases et retries | Timeout, métriques de durée et test d’expiration de lease |
| Message `FAILED` ou retry épuisé | Perte silencieuse | Politique explicite de dead-letter/alerte opérateur |
| Payload JSON non dictionnaire | Exception ou retry incorrect | Déjà rejeté, conserver le test de non-régression |
| Tenant inexistant ou événement supprimé | Notification orpheline | Test d’intégrité référentielle et traitement idempotent |
| Hash d’archive non canonique en majuscules | Contrat de hash ambigu | Normaliser ou refuser explicitement |

La priorité immédiate est le test PostgreSQL de concurrence et la définition d’une politique d’échec définitif. Le worker actuel ne doit pas être présenté comme une file durable complète tant qu’aucun mécanisme d’alerte ou de dead-letter n’est contractualisé pour les messages qui restent en retry.

## Conclusion

Sur le corpus public disponible, `ZIP_DEFLATED` niveau 6 est le meilleur compromis observé. L’optimisation `SpooledTemporaryFile` reste pertinente pour limiter la RAM lorsque l’archive dépasse 8 MiB, mais la lecture du document source demeure actuellement matérialisée en mémoire par l’interface de stockage ; une optimisation ultérieure pourrait introduire un flux de lecture par chunks.

La validation VPS est spécifiée dans `docs/VPS_OPERATIONAL_VALIDATION_SPEC.md`. Elle reste non exécutée tant qu’aucun VPS, DNS, accès SSH et stockage de sauvegarde hors VPS ne sont disponibles.
