# Golden Corpus DCE

Ce dossier contient le contrat de manifeste et un exemple volontairement vide. Le dépôt ne contient aucun document d’appel d’offres réel, anonymisé ou synthétique présenté comme vérité métier. Le manifeste sert à déclarer les pièces autorisées pour une campagne de mesure, puis à relier chaque fichier à son hash SHA-256 et à ses attentes d’extraction vérifiables.

## Contrat

Chaque entrée doit contenir un identifiant stable, un nom de fichier sans chemin, un hash SHA-256 en minuscules, un type MIME autorisé, des fragments textuels attendus et des libellés attendus. Les attentes doivent rester dépourvues de secrets, de montants confidentiels et de données personnelles non anonymisées. Le validateur refuse les champs supplémentaires, les chemins absolus ou traversants, les hashes invalides, les doublons et les types non supportés.

## Validation

Depuis la racine du dépôt, exécuter :

```bash
cd backend
uv run python -m app.platform.quality.golden_corpus ../ops/golden-corpus/manifest.example.json
```

Une sortie `documents=0` prouve uniquement que le manifeste est syntaxiquement et structurellement valide. Elle ne constitue pas une mesure OCR, un taux de rappel ou une validation de compréhension documentaire.

Pour une campagne réelle, déposer le manifeste et les fichiers dans un espace hors Git, vérifier les hashes indépendamment, puis exécuter le harness d’extraction sur l’environnement qui possède les documents et les modèles autorisés. Publier ensuite uniquement des métriques agrégées et des identifiants anonymisés. La recette avec corpus DCE réel, scans dégradés, tableaux, annexes et attentes validées par un opérateur reste une validation d’environnement et requiert l’accord de confidentialité approprié.
