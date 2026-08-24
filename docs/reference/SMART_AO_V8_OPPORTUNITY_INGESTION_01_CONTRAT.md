# SMART_AO V8 — OPPORTUNITY-INGESTION-01

## Objet

Ce lot prépare l’ingestion contrôlée d’avis publics BOAMP à partir d’un profil de veille patronal. Il ne transforme pas encore un avis en `Case`, ne calcule pas de score de pertinence et ne persiste pas de décision métier. Le premier incrément fournit un service applicatif et un script opérateur produisant un rapport JSON de staging borné.

## Architecture

Le service `BoampOpportunityIngestionService` dépend uniquement du port `PublicNoticeSearchPort`. L’adaptateur `BoampReadOnlySearch` conserve l’appel Explore API 2.1 derrière ce port. Aucun module domaine ne dépend de FastAPI, SQLAlchemy, `httpx` ou du fournisseur BOAMP.

Le script [`scripts/ingest_boamp_opportunities.py`](../../scripts/ingest_boamp_opportunities.py) est un outil one-shot. Il compose un `WatchProfileCriteria`, appelle le port BOAMP en lecture seule et écrit un rapport technique sur stdout ou dans le chemin `--output` demandé.

## Budget et garde-fous

Les mots-clés proviennent du profil et sont normalisés par le domaine. Le service refuse un profil sans mot-clé et borne le nombre de mots-clés, la taille d’une page, le nombre de pages par mot-clé et le nombre total de résultats. Le script ne lance aucune boucle infinie, ne suit pas de redirection implicite de l’adaptateur et ne déclenche pas de tâche de fond.

Les départements inclus et exclus sont appliqués localement après la lecture. Un avis expiré est écarté lorsque sa date limite est antérieure à l’instant UTC de référence. Les identifiants `idweb` sont dédupliqués de façon déterministe et les candidats sont triés par identifiant public.

## Projection allowlistée

Chaque candidat contient exclusivement `source`, `source_notice_id`, `title` borné, dates de publication et de réponse, codes département, types de marché, statut source et `fingerprint_sha256`. Le script ne transporte pas les objets BOAMP riches `donnees` ou `gestion`, le texte DCE, les pièces jointes, les montants, les prix, les marges, des embeddings, des credentials ou des tokens.

Le fingerprint est un hash de la projection normalisée. Il ne remplace pas la clé source `source_notice_id` et ne constitue ni une preuve d’intégrité juridique, ni une preuve de dépôt, ni une signature.

## Exemple d’exécution contrôlée

```bash
uv run python scripts/ingest_boamp_opportunities.py \
  --keyword réhabilitation \
  --keyword école \
  --included-department 59 \
  --excluded-department 62 \
  --page-size 20 \
  --max-pages-per-keyword 5 \
  --max-results 200 \
  --now 2026-08-23T12:00:00Z \
  --output /tmp/boamp-opportunities.json
```

Une exécution réseau réelle n’est pas effectuée dans le sandbox. Elle devra être réalisée sur un environnement autorisé, avec connectivité HTTPS, journaux sans token, contrôle du budget de requêtes, gestion du rate limit et validation d’une réponse BOAMP stable.

## Prochains incréments

La persistence des `OpportunityCandidate`, la provenance d’une observation et le rejeu idempotent formeront un sous-lot séparé. La déduplication métier multi-source, le scoring explicable, la revue patronale, le rattachement à une opportunité et la conversion en `Case` ne doivent pas être déduits automatiquement par ce script.
