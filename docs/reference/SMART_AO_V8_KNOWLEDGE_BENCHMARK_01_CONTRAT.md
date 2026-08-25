# SMART_AO V8 — KNOWLEDGE-BENCHMARK-01

## 1. Objet

Ce contrat définit un manifeste opérateur pour mesurer un retrieval DCE contrôlé avant toute activation de production. Le manifeste ne contient pas le texte des fragments, les embeddings, les extraits, les montants ni les clés de stockage. Il transporte uniquement des identifiants, des hashes de requêtes, des classifications autorisées et des localisations structurées nécessaires à l’évaluation.

Le lot comprend :

- le value object pur `app.modules.knowledge.application.benchmark` ;
- la commande `scripts/validate_knowledge_benchmark.py` ;
- la validation de la conformité du corpus et le calcul de `recall_at_k`, du temps moyen et du p95 à partir d’un rapport de run externe ;
- des arrêts fermés lorsque le manifeste est incomplet, non anonymisé, non autorisé, non tenant-scoped ou contient des champs sensibles.

La commande ne lit aucun PDF et n’exécute pas BGE. Elle prépare et contrôle les preuves qui seront produites sur une machine disposant du corpus autorisé, de PostgreSQL et du cache local du modèle.

## 2. Manifeste attendu

Le document JSON racine doit contenir :

| Champ | Contraintes |
|---|---|
| `schema_version` | Entier `1`. |
| `corpus_id` | Identifiant minuscule borné, sans secret ni chemin local. |
| `model_id` | Identifiant exact du modèle évalué. |
| `anonymized` | Doit être `true`. |
| `authorized` | Doit être `true`. |
| `tenant_scoped` | Doit être `true`. |
| `cases` | Tableau non vide de Case/version DCE. |

Chaque Case contient `case_id`, `dce_version_id`, des fragments avec `source_fragment_id`, `classification` (`PUBLIC` ou `INTERNAL_OPERATIONAL`) et un `locator` structuré non vide, ainsi que des requêtes. Une requête contient `query_id`, `query_sha256` et au moins un `expected_fragment_id` appartenant à la même Case.

Le texte de requête n’est pas enregistré : `query_sha256` doit être un SHA-256 hexadécimal minuscule. Le helper `query_sha256()` ne sert qu’à produire ce hash dans un environnement contrôlé ; il ne doit pas être utilisé pour imprimer le texte.

## 3. Rapport de run

Le rapport facultatif transmis par `--results` est un tableau contenant uniquement :

```json
[
  {
    "query_id": "q-01",
    "retrieved_fragment_ids": ["<source-fragment-uuid>"],
    "elapsed_ms": 12.4
  }
]
```

Les résultats doivent référencer des `query_id` connus, sans doublon. Le scoring applique `top_k` avant de calculer le rappel par requête. La sortie ne contient que l’identifiant du corpus, le modèle, le nombre de requêtes évaluées, `recall_at_k`, `mean_elapsed_ms` et `p95_elapsed_ms`.

## 4. Commande opérateur

Validation du manifeste uniquement :

```bash
uv run python scripts/validate_knowledge_benchmark.py /path/to/manifest.json
```

Validation avec scoring d’un rapport déjà produit par le runner RAG :

```bash
uv run python scripts/validate_knowledge_benchmark.py \
  /path/to/manifest.json \
  --results /path/to/results.json \
  --top-k 5
```

Une sortie `manifest_valid` ne constitue pas une preuve de précision RAG. Une sortie `benchmark_valid` atteste uniquement que les identifiants et mesures fournis sont cohérents avec le manifeste ; elle ne certifie ni le corpus, ni la disponibilité BGE, ni la qualité métier.

## 5. Arrêt fermé et confidentialité

L’outil refuse tout champ nommé `text`, `excerpt`, `content`, `embedding`, `vector`, `amount`, `price`, `currency`, `financial` ou `storage_key`, y compris dans une structure imbriquée. Il refuse également les fragments `FINANCIAL_PRIVATE`, les fragments attendus d’une autre Case, les IDs dupliqués et les corpus non déclarés anonymisés, autorisés et tenant-scoped.

Le benchmark ne remplace pas la confirmation humaine. Aucun score ne doit être transformé automatiquement en exigence satisfaite, décision patronale, calcul pricing ou preuve de dépôt.

## 6. Preuves restant externes

La recette complète reste à exécuter sur un environnement autorisé :

1. corpus DCE anonymisé ou explicitement autorisé ;
2. cache local BGE vérifié avec `local_files_only` ;
3. indexation one-shot avec les flags RAG explicites ;
4. rapport de résultats généré sans contenu documentaire ;
5. mesures durée/CPU/mémoire/taille d’index ;
6. rejeu idempotent et contrôle tenant/Case/version ;
7. revue humaine comparant la baseline structurée et le retrieval.

Le sandbox ne fournit pas ces preuves et aucun résultat de benchmark réel n’est revendiqué par ce lot.
