# Audit du benchmark ZIP et des tests du worker webhook

## 1. Audit du script de benchmark

Le script `scripts/benchmark_submission_zip_corpus.py` est **reproductible dans son périmètre** : il trie les PDF par nom, fixe les dates ZIP au 1er janvier 1980, fixe les permissions à `0600`, calcule le SHA-256 de chaque entrée et de l’archive finale, mesure avec `perf_counter()` et compare trois profils de compression.

La comparaison est méthodologiquement utile, mais le script n’est pas une reproduction exacte de `SubmissionPackageService.export`. Il fabrique un manifest simplifié à partir des noms et hashes des PDF, alors que le service assemble un manifest métier déjà matérialisé et un seul `technical-response.md`. Il mesure donc correctement le coût ZIP et l’effet du type de compression, mais pas le coût complet de lecture PostgreSQL, d’autorisation, d’audit, d’outbox ou de stockage privé.

| Point examiné | Constat | Conséquence |
|---|---|---|
| Ordre des entrées | Stable grâce à `sorted()` | Comparaison reproductible |
| Timestamps | Fixés | Hash d’archive stable |
| Permissions | `0600` sur les entrées | Cohérent avec un dossier privé |
| Compression | `STORED`, niveau 6, niveau 9 | Comparaison pertinente |
| Buffer | `SpooledTemporaryFile`, seuil 8 MiB | Réduction du risque de saturation RAM |
| Lecture source | `read_bytes()` appelé deux fois par fichier | Mesure et mémoire plus coûteuses que nécessaire |
| Corpus | Deux PDF publics uniquement | Bon smoke benchmark, faible représentativité statistique |
| Mesure | Un seul run par profil | Pas d’intervalle, variance non mesurée |
| Observabilité | Temps total uniquement | CPU, RSS, I/O et page faults absents |

Le principal écart technique est la double lecture de chaque PDF : une première lecture pour le hash du manifest, puis une seconde pour écrire l’entrée ZIP. Le service de production lit aussi actuellement le document généré en bytes avant l’assemblage. Une évolution utile serait une fonction de hash-and-write par chunks, ou une interface de stockage exposant un flux binaire, afin de limiter les copies mémoire. Cette évolution doit préserver le hash du document et le déterminisme de l’archive.

Le benchmark devrait être renforcé par au moins cinq répétitions par profil, une médiane et un p95, un corpus mixte PDF/DOCX/XLSX/CSV/TXT, des fichiers déjà compressés et non compressés, ainsi qu’une mesure RSS maximale. Les données BTP réelles doivent rester hors Git ou être déposées avec une autorisation explicite ; le dépôt ne doit conserver que les scripts, métadonnées et résultats non sensibles.

## 2. Audit des tests webhook

Les tests ajoutés sont majoritairement unitaires et utilisent des `MagicMock` pour simuler les context managers SQLAlchemy. Ils valident les décisions principales sans dépendre d’un endpoint réseau ni d’une base PostgreSQL. Cette approche est rapide et adaptée aux branches de validation, mais elle ne prouve pas le comportement transactionnel concurrent.

| Zone du worker | État | Commentaire |
|---|---|---|
| Allowlist sans finance | Couvert | `manifest_sha256` et identifiant de snapshot exclus |
| Payload incomplet ou mauvais canal | Couvert | Rejet puis retry |
| Backoff borné | Couvert | Paramétrage jusqu’à 20 essais |
| Worker sans URL | Couvert | Skip contrôlé et publication idempotente |
| Claim et lease | Couvert unitairement | La requête SQL réelle reste à tester |
| Message absent / topic incorrect | Couvert | Skip sans effet métier |
| HTTP non 2xx | Couvert par monkeypatch | Pas d’appel réseau réel |
| URL non HTTP(S) | Couvert | Refus du schéma `file:` |
| Déjà publié | Couvert | `_publish` et `_retry` ne modifient pas le message |
| Réponse 2xx réelle | Non couvert | Ajouter un serveur HTTP local contrôlé |
| Exceptions réseau | Non couvert | Tester `HTTPError`, `URLError`, timeout et `OSError` |
| Concurrence PostgreSQL | Non couvert | Deux sessions et `SKIP LOCKED` requis |
| Build runtime | Non couvert | Variables absentes, URL vide, timeout invalide |
| Boucle `main` | Non couvert | Faible priorité ; tester surtout l’injection du poller |
| Échec définitif / dead-letter | Non implémenté | Décision opératoire à contractualiser |

Les cas limites les plus importants sont les suivants. Premièrement, une livraison peut réussir côté endpoint puis le worker peut tomber avant de marquer l’outbox `PUBLISHED`; une répétition est donc normale et le consommateur externe doit dédupliquer par identifiant d’événement ou de dossier. Deuxièmement, les redirections HTTP ne sont pas contractualisées : elles peuvent conduire le payload vers un hôte inattendu. Troisièmement, un endpoint peut répondre `429`, rester lent ou maintenir durablement les messages en retry. Quatrièmement, un hash de 64 caractères mais non hexadécimal est actuellement accepté. Cinquièmement, aucun seuil d’échec définitif ni dead-letter n’est implémenté.

## 3. Priorités recommandées

La priorité P0 est le test d’intégration PostgreSQL de concurrence, avec deux workers et assertion qu’un seul claim est obtenu. La priorité P1 est l’ajout d’un endpoint HTTP local de test pour vérifier le body, les headers, le code 2xx, les erreurs réseau et l’absence de données financières. La priorité P1 complémentaire est la validation stricte d’un hash SHA-256 hexadécimal et la définition des redirections. La priorité P2 est la politique de dead-letter, les métriques de backlog et l’automatisation des répétitions du benchmark.
