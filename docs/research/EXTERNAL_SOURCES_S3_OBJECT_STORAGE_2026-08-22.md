# Sources vérifiées — S3/MinIO privé — 22 août 2026

## Écriture conditionnelle

Source officielle : [Boto3 `put_object`](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html)

La documentation officielle décrit `IfNoneMatch="*"` pour n’écrire l’objet que si la clé n’existe pas déjà. Elle indique qu’un conflit concurrent peut produire `409 ConditionalRequestConflict` et qu’un objet existant produit `412 PreconditionFailed`.

Source officielle : [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)

S3 documente que `If-None-Match` empêche l’écrasement d’une donnée existante sous la même clé et nécessite une autorisation `s3:PutObject`. Cette propriété est utilisée par l’adaptateur pour préserver l’append-only logique des documents générés.

## Lecture et métadonnées

Sources officielles : [Boto3 `get_object`](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_object.html) et [Boto3 `head_object`](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/head_object.html)

`GetObject` lit une clé complète et renvoie un corps de réponse ; `HeadObject` ne renvoie que les métadonnées. L’adaptateur actuel utilise `GetObject` côté serveur, impose une limite de taille avant lecture complète lorsque la longueur est fournie, ferme le corps, et ne renvoie aucune URL, bucket ou clé dans un contrat HTTP.

## Décision d’intégration

Le client `boto3` est une dépendance optionnelle `object-storage`, compatible avec un endpoint S3 ou MinIO. Le stockage local reste la valeur par défaut. L’activation S3/MinIO exige explicitement `SMART_AO_OBJECT_STORAGE_ENABLED=1`, un bucket et une configuration d’exécution hors dépôt ; la recette réelle MinIO, les permissions, le chiffrement, la sauvegarde et la restauration restent à exercer sur Docker réel.
