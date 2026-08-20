# Plan d’exécution VPS — benchmark ZIP et tests de charge

## 1. Objectif et périmètre

Cette procédure qualifie le comportement de SMART_AO V8 sur un VPS réel sans utiliser de données client. Elle mesure séparément l’assemblage ZIP, le parcours d’export, la notification outbox et la consommation webhook. Elle ne constitue pas un test de capacité de production tant que la taille des documents, le matériel VPS et les objectifs de débit n’ont pas été validés.

Le benchmark de compression utilise un corpus BTP autorisé et non sensible, conservé hors Git. Le test de charge est lancé depuis un runner distinct du VPS afin de mesurer l’expérience réseau sans confondre la charge cliente et la charge serveur.

## 2. Préconditions d’entrée

| Élément | Contrôle requis |
|---|---|
| VPS | Accès SSH non root avec sudo, horloge synchronisée, espace disque mesuré |
| Réseau | DNS de préproduction résolu, 80/443 accessibles, PostgreSQL/ClamAV non exposés |
| Code | Commit et digests approuvés, branche propre, migrations connues |
| Secrets | `.env.preprod` hors Git, permissions 0600, webhook de test uniquement |
| Corpus | Autorisation d’usage, hash des fichiers, absence de données client |
| Backup | Destination chiffrée hors VPS, test de transfert et manifeste SHA-256 |
| Observabilité | Accès aux logs Docker/Caddy/systemd et aux métriques système |

Avant de commencer, exécuter `ops/deploy-preprod.sh config`, vérifier le rendu Compose sans secrets, confirmer les ports publiés et conserver le commit déployé.

## 3. Déploiement et smoke test

1. Exécuter `ops/deploy-preprod.sh deploy` avec la fenêtre de maintenance approuvée.
2. Vérifier les états `healthy` de PostgreSQL et ClamAV.
3. Vérifier les services backend, frontend, Caddy, DCE retention et submission export webhook.
4. Exécuter `ops/healthcheck-preprod.sh` ou `ops/deploy-preprod.sh healthcheck`.
5. Vérifier `https://<host>/healthz/live` et `https://<host>/healthz/ready`.
6. Confirmer le certificat TLS, les en-têtes de sécurité et l’absence de publication des ports internes.
7. Exécuter le test EICAR uniquement en préproduction et vérifier le rejet `REJECTED`.

Le test est bloqué si une migration, un healthcheck, le certificat, la quarantaine ou la séparation réseau échoue.

## 4. Préparer le corpus de compression

Le corpus doit comporter au minimum :

| Classe | Exemples attendus |
|---|---|
| PDF déjà compressé | CCTP, CCAP, règlement de consultation |
| Document bureautique | DOCX technique autorisé |
| Tableur | XLSX BPU/DPGF anonymisé et autorisé |
| Texte/tabulaire | CSV ou TXT de spécifications |
| Mélange | Dossier complet multi-format non sensible |

Pour chaque fichier, calculer un SHA-256 avant transfert, conserver uniquement les métadonnées dans le manifeste de campagne et supprimer les fichiers du VPS après la campagne. Ne jamais utiliser un DPGF ou BPU client réel sans autorisation explicite.

## 5. Mesure du benchmark ZIP

Le script doit être exécuté dans le conteneur ou dans l’environnement exactement utilisé par le service. Pour chaque profil (`ZIP_STORED`, `ZIP_DEFLATED` niveau 6, `ZIP_DEFLATED` niveau 9), exécuter au moins cinq répétitions à froid puis cinq répétitions à chaud. La première exécution est conservée séparément car elle peut inclure le coût de cache disque et d’initialisation.

Mesures obligatoires :

- taille totale des fichiers d’entrée et taille ZIP finale ;
- ratio `archive_bytes / input_bytes` et réduction en pourcentage ;
- durée d’assemblage avec `perf_counter()` ;
- médiane, p95 et maximum sur les répétitions ;
- SHA-256 de l’archive et égalité des hashes sur deux assemblages identiques ;
- RSS maximale, CPU utilisateur/système, I/O disque et espace libre ;
- taille et nombre de fichiers par corpus.

La décision actuelle `DEFLATED` niveau 6 doit être conservée comme baseline. Le niveau 9 ne doit être retenu que s’il apporte une réduction mesurable justifiant son coût CPU.

## 6. Scénario d’export et outbox

Créer des dossiers de soumission de test dans un tenant dédié. Pour chaque export :

1. déclencher l’export patronal ;
2. vérifier la présence de l’audit `SUBMISSION_PACKAGE_EXPORTED` ;
3. vérifier la création du message `submission.package.exported` ;
4. contrôler le hash et la déterminisme de l’archive ;
5. attendre la consommation par le worker ;
6. vérifier le statut `PUBLISHED`, le nombre de tentatives et l’absence de doublon ;
7. inspecter le récepteur webhook de test pour confirmer l’allowlist et l’absence de finance.

Le récepteur doit enregistrer uniquement un compteur, les headers non secrets, la taille du body, les clés reçues et un hash du body. Il ne doit pas persister le body complet.

## 7. Paliers de charge

Les paliers sont exécutés dans l’ordre, avec retour au niveau nominal entre deux paliers :

| Palier | Charge | Durée maximale | Passage |
|---|---:|---:|---|
| Smoke | 1 export | 2 min | zéro erreur et audit présent |
| P1 | 10 exports séquentiels | 5 min | backlog résorbé |
| P2 | 50 exports séquentiels | 10 min | aucun retry permanent |
| P3 | 100 exports séquentiels | 15 min | ressources stables |
| P4 | 10 exports concurrents | 10 min | un seul effet par événement |
| Rejeu | mêmes événements rejoués | 5 min | idempotence confirmée |

Le harnais arrête la campagne si le healthcheck devient instable, si un message est perdu, si un body contient une clé interdite, si le backlog augmente sans résorption, si la mémoire ou le disque sature, ou si un conteneur redémarre de manière inattendue.

## 8. Collecte et format des résultats

Chaque campagne produit un manifeste JSON comprenant `campaign_id`, commit, timestamp UTC, profil, corpus hashes, paramètres de charge, tailles, durées, p50/p95, CPU/RSS/I/O, compteurs outbox et codes HTTP. Les logs Docker et Caddy sont exportés sur une fenêtre temporelle précise, filtrés des secrets et joints sous forme de résumé.

Les artefacts sont stockés hors du dépôt dans un emplacement privé : rapport Markdown, JSON brut, manifeste SHA-256, résumé des logs, preuve healthcheck, preuve EICAR, état outbox et preuve de backup/restauration. Les documents BTP ne sont pas joints au rapport.

## 9. Critères d’acceptation

La campagne est acceptée uniquement si :

- les hashes sont identiques lors des assemblages déterministes ;
- aucun export nominal ne produit de 5xx ou de perte outbox ;
- un rejeu ne crée pas de double livraison ;
- les retries sont bornés et résorbés ;
- aucun champ financier, storage key ou contenu n’atteint le webhook ;
- les services restent healthy et les ressources reviennent au niveau nominal ;
- le backup est vérifié et la restauration isolée réussit ;
- le rapport contient toutes les preuves exigées.

Une seule violation de confidentialité ou de conservation outbox entraîne un statut **REFUSÉ**, indépendamment des performances.

## 10. Scripts d’automatisation livrés

Le dépôt fournit maintenant trois outils opérateur et un comparateur de couverture :

| Script | Usage |
|---|---|
| `scripts/run_vps_compression_campaign.py` | Répète les profils ZIP à froid et à chaud, calcule médiane/p95, hashes et CPU process |
| `scripts/run_vps_load_campaign.py` | Envoie une charge GET bornée vers des chemins de test, avec concurrence contrôlée et rapport JSON sans body |
| `scripts/collect_coverage_diagnostics.py` | Capture l’empreinte runtime et produit les rapports de couverture local/CI |
| `scripts/compare_coverage_reports.py` | Compare les totaux, fichiers, lignes manquantes et branches entre deux rapports JSON |

Exemple de benchmark sur le VPS, après transfert d’un corpus autorisé :

```bash
uv run python scripts/run_vps_compression_campaign.py \
  --corpus-dir /srv/smart-ao/corpus-btp-approved \
  --output /srv/smart-ao/reports/compression-$(date -u +%Y%m%dT%H%M%SZ).json \
  --repetitions 5
```

Exemple de charge santé depuis le runner séparé :

```bash
uv run python scripts/run_vps_load_campaign.py \
  --base-url https://preprod.example.invalid \
  --paths-file ./ops/load/health-paths.json \
  --output ./reports/load-health-p1.json \
  --requests 10 --concurrency 1 --timeout-seconds 10
```

Pour les chemins d’export authentifiés, le token est fourni uniquement par la variable d’environnement `SMART_AO_LOAD_BEARER_TOKEN`. Le script ne l’écrit jamais dans le rapport et ne conserve qu’un compteur, les codes HTTP, les chemins de test et les latences. Le fichier de chemins doit contenir uniquement des chemins relatifs préparés à l’avance ; il ne doit pas contenir de données financières ni d’URL arbitraires.

Le mode `--dry-run` est obligatoire pour valider les paramètres et les paliers avant tout appel distant. Aucun de ces scripts ne crée de dossier, ne modifie la base, ne déclenche d’export non autorisé ou ne pousse de document dans le webhook par lui-même.
