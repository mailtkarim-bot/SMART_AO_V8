# SMART AO V8 — OPPORTUNITY-QUALIFICATION-01

## Objet

Ce lot fournit une lecture patronale des observations BOAMP persistées et une qualification humaine explicite. Il ne crée pas automatiquement de `Case`, ne modifie pas le score historique et ne transforme pas une observation publique en preuve de candidature.

## Lecture patronale

La lecture exige un acteur `PATRON_ADMIN` actif dans le tenant demandé. Le repository filtre chaque requête par `tenant_id`, borne `limit` à 200 résultats et accepte un seuil `min_score` entre 0 et 100. Les résultats sont triés par score décroissant, échéance croissante puis identifiant.

La projection expose uniquement l’identifiant d’observation, l’identifiant public BOAMP, le titre public borné, les dates, départements, types de marché, statut source, score, version d’explication, explication et fingerprint. Elle n’expose ni tenant, acteur, credentials, texte DCE, document, prix, montant ou marge.

## Qualification

Les décisions fermées sont `QUALIFIED`, `REJECTED` et `SNOOZED`. Les motifs compatibles sont contrôlés par le domaine :

| Décision | Motifs autorisés |
|---|---|
| `QUALIFIED` | `RELEVANT_PUBLIC_SIGNAL` |
| `REJECTED` | `NOT_RELEVANT`, `EXPIRED` |
| `SNOOZED` | `INSUFFICIENT_PUBLIC_DATA` |

Chaque qualification conserve l’observation, l’acteur patronal, la décision, le motif, le score au moment de la décision et la version du score. La table est append-only. Un nouveau choix humain crée une nouvelle qualification historique ; il ne réécrit pas la décision précédente.

## Idempotence et audit

La migration `20260823_0054` impose les FK tenant/acteur/observation, les catalogues fermés, les contraintes de score et les unicités de `command_id` et `idempotency_key`. Le repository dérive un identifiant de qualification stable à partir du tenant et de la clé d’idempotence. Un rejeu identique restitue l’événement existant sans créer de doublon. Une collision incompatible est rejetée.

La qualification crée l’événement `BoampOpportunityQualified` et le message outbox `opportunity.boamp.qualification.recorded` dans la même transaction. Le payload d’audit ne contient pas le titre ni les détails de l’observation.

## Script opérateur

Le script [`scripts/read_qualify_boamp_opportunities.py`](../../scripts/read_qualify_boamp_opportunities.py) fonctionne en deux modes : lecture patronale quand `--decision` est absent, qualification quand `--decision` est fourni. Les deux modes exigent `--tenant-id`, `--actor-id` et une URL PostgreSQL runtime. La qualification exige en plus `--observation-id`, `--reason-code`, `--command-id` et `--idempotency-key`.

```bash
uv run python scripts/read_qualify_boamp_opportunities.py \
  --database-url "$SMART_AO_DATABASE_URL" \
  --tenant-id <tenant-uuid> \
  --actor-id <patron-uuid> \
  --min-score 60 \
  --limit 50
```

```bash
uv run python scripts/read_qualify_boamp_opportunities.py \
  --database-url "$SMART_AO_DATABASE_URL" \
  --tenant-id <tenant-uuid> \
  --actor-id <patron-uuid> \
  --observation-id <observation-uuid> \
  --decision QUALIFIED \
  --reason-code RELEVANT_PUBLIC_SIGNAL \
  --command-id <command-uuid> \
  --idempotency-key <idempotency-uuid> \
  --now 2026-08-23T12:00:00Z
```

Le script n’est pas une route publique et ne doit pas recevoir d’identité depuis un payload BOAMP. Les identités sont fournies par l’opérateur autorisé, puis vérifiées côté DB et service.

## Validation et limites

Les tests applicatifs et de projection sont déterministes et n’appellent aucun réseau. La migration est validable offline jusqu’à `0054`. Les tests PostgreSQL online et le parcours réel de qualification restent à exécuter sur une base PostgreSQL disponible. `QUALIFIED` signifie uniquement « retenue par le patron selon ce motif » ; il ne vaut ni décision d’offre, ni dépôt, ni signature, ni preuve juridique.
