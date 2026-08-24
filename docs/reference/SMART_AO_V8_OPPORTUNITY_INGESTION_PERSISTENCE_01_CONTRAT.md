# SMART_AO V8 — OPPORTUNITY-INGESTION-PERSISTENCE-01

## Objet

Ce lot persiste les observations publiques BOAMP après validation d’un rapport staging. Chaque écriture est rattachée à un tenant, un profil de veille, une version de profil et une identité d’acteur fournie par l’opérateur autorisé. La persistence produit un run immuable, des observations fingerprintées, des liens de provenance, un score explicable et un événement d’audit transactionnel.

## Modèle de données

La migration `20260823_0053` crée `boamp_ingestion_runs`, `boamp_opportunity_observations` et `boamp_ingestion_observation_links`. Le run possède des FK composites vers le tenant, l’acteur membre du tenant, le profil et la version exacte du profil. Les observations sont identifiées par `source`, `source_notice_id` et `fingerprint_sha256`. Les liens indiquent quelles observations ont été vues par chaque run.

Les runs, observations et liens sont append-only via des triggers PostgreSQL. Les contraintes refusent les fingerprints et hashes qui ne correspondent pas à 64 caractères hexadécimaux, les scores hors de `[0, 100]`, les statuts inconnus et les structures d’explication qui ne sont pas des objets JSON.

## Score explicable

`BoampOpportunityScoringService` est versionné `BOAMP_PUBLIC_V1`. Il utilise uniquement des signaux publics : mots-clés trouvés dans le titre, département inclus, statut source actif et échéance publique future. Chaque facteur conserve un code, un booléen de correspondance, un nombre de points et une explication. Le score ne déduit aucun prix, montant, marge, capacité financière ou probabilité de gain.

Le score est un signal de tri technique. Il ne qualifie pas automatiquement l’opportunité et ne crée pas de dossier de réponse. La revue patronale, la qualification et la conversion en `Case` restent des étapes distinctes.

## Idempotence et audit

Le repository dérive un `run_id` déterministe à partir du tenant et de l’`idempotency_key`, puis vérifie simultanément les collisions de run, commande et clé d’idempotence. Un hash de requête différent est rejeté. Un rejeu restitue le run et ses liens existants sans créer un second événement ni un second message outbox.

Le run, les observations nouvelles, les liens, l’événement `BoampIngestionRecorded` et le message `opportunity.boamp.ingestion.recorded` sont écrits dans la transaction fournie par l’appelant. Le payload d’audit ne contient que les identifiants, la version, les nombres et le hash de requête ; les détails d’avis restent dans la projection tenant-scoped.

## Script opérateur

Le script [`scripts/persist_boamp_opportunities.py`](../../scripts/persist_boamp_opportunities.py) reçoit un rapport `SMART_AO_OPPORTUNITY_INGESTION_REPORT_V1`, vérifie strictement son schéma et les fingerprints, recalcule le score puis écrit avec les identifiants `tenant`, `profile`, `actor`, `command` et `idempotency` fournis hors du rapport.

```bash
uv run python scripts/persist_boamp_opportunities.py \
  --input /tmp/boamp-opportunities.json \
  --database-url "$SMART_AO_DATABASE_URL" \
  --tenant-id <tenant-uuid> \
  --profile-id <profile-uuid> \
  --profile-version 1 \
  --actor-id <actor-uuid> \
  --command-id <command-uuid> \
  --idempotency-key <idempotency-uuid> \
  --keyword réhabilitation \
  --included-department 59 \
  --now 2026-08-23T12:00:00Z
```

Le script n’accepte aucun tenant ou acteur depuis le JSON, ne crée pas d’authentification et ne doit pas être exposé comme endpoint public. Il ne contient pas de secret et ne simule pas une requête BOAMP.

## Validation

Les tests unitaires de scoring et de validation du rapport sont exécutables sans infrastructure externe. Les tests DB couvrent persistence/rejeu et conflit de hash, mais exigent PostgreSQL. La chaîne Alembic est validée offline jusqu’à `0053`, y compris les FK composites et les triggers. La migration online et une persistence BOAMP réelle restent à exécuter sur une base PostgreSQL autorisée.
