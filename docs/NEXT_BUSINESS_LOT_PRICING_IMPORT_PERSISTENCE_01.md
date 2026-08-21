# Prochain lot métier — PRICING-IMPORT-PERSISTENCE-01

## 1. Point de départ vérifié

La branche `main` est au commit [`491a705`](https://github.com/mailtkarim-bot/SMART_AO_V8/commit/491a705), fusion de la sonde frontend de readiness backend. Le frontend dispose désormais d’un client API typé pour `/healthz/ready`, d’un hook d’état et d’un affichage des dépendances `database` et `clamav`. La prévisualisation patronale DPGF/BPU/Excel existe déjà, mais elle ne persiste pas encore un lot réutilisable ni son application atomique dans un brouillon financier.

Le contrat normatif de référence est [`SMART_AO_V8_PRICING_IMPORT_PERSISTENCE_01_CONTRAT.md`](reference/SMART_AO_V8_PRICING_IMPORT_PERSISTENCE_01_CONTRAT.md). Il constitue la frontière métier à respecter ; ce plan n’ajoute aucune règle financière implicite.

## 2. Objectif du slice

Transformer une prévisualisation `.xlsx` validée en un lot d’import serveur `PREVIEWED`, conserver uniquement les lignes normalisées nécessaires à une décision patronale, puis permettre au patron de committer une seule fois les lignes valides dans un brouillon `DRAFT`.

Le commit du lot doit être atomique avec l’ajout des lignes financières, la mise à jour des totaux et de la révision du brouillon, la transition `PREVIEWED → COMMITTED`, l’événement, l’outbox et le receipt idempotent. Aucun fichier binaire brut ne doit être conservé par ce slice.

## 3. Découpage de mise en œuvre

| Étape | Travail | Résultat attendu |
|---:|---|---|
| 1 | Tests de contrat et de persistance | Fixtures PostgreSQL et scénarios nominaux/erreur écrits avant le code métier. |
| 2 | Modèle et migration | Roots tenant-scoped du lot et des lignes normalisées, états fermés, unicités, FKs composites et triggers append-only. |
| 3 | Commande et service de création | Transformation contrôlée de la prévisualisation en lot `PREVIEWED`, sans binaire brut et avec empreinte SHA-256 serveur. |
| 4 | Commande et service de commit | Verrouillage du lot puis du brouillon, contrôle de révision/publication, insertion des lignes `SALES`, totaux et transition atomiques. |
| 5 | Routes patronales | DTO fermés, capability `financial.report.line.write`, classification `FINANCIAL_PRIVATE`, tenant/acteur/Case/brouillon résolus côté serveur. |
| 6 | Projection frontend | Affichage du lot, des erreurs et de l’état de commit sans exposer de données financières au wizard ou aux webhooks. |
| 7 | Réconciliation et CI | Ruff, detect-secrets, Alembic upgrade/check/downgrade, tests PostgreSQL, couverture et build/Vitest frontend. |

## 4. Scénarios de test obligatoires

Les tests PostgreSQL devront couvrir la création d’un lot normalisé, le commit de deux lignes vers un brouillon `DRAFT`, les totaux et la nouvelle révision, le rejeu idempotent, le conflit de révision, l’absence de ligne valide, le lot déjà committé, le snapshot publié, l’isolation tenant, le refus collaborateur et les triggers append-only.

Les tests HTTP devront vérifier les receipts minimaux, les statuts publics `201/200/403/404/409/422`, l’absence de montant/libellé/prix unitaire/nom de fichier/hash dans les réponses de commit, ainsi que l’absence de données financières dans les contrats collaborateur et les événements/outbox.

## 5. Invariants non négociables

> Le `tenant_id`, l’acteur, la membership, la Case et le brouillon sont toujours résolus côté serveur.

> Aucun snapshot `PUBLISHED` ne peut être modifié. Le commit vise uniquement un brouillon `DRAFT` verrouillé avec une révision optimiste vérifiée.

> Les lots et lignes normalisées sont append-only. Une ligne invalide ne peut jamais alimenter le brouillon financier.

> Les montants sont des entiers en centimes et les quantités sont des décimaux canoniques sous forme textuelle. Aucun flottant ne doit être persistant.

> Le dépôt externe reste hors périmètre et `external_submission` ne doit jamais être transformé en preuve de dépôt par ce slice.

## 6. Ordre d’exécution recommandé

Commencer par les tests unitaires du contrat de normalisation et les tests PostgreSQL du cycle `PREVIEWED → COMMITTED`. Ajouter ensuite la migration et les ports applicatifs, puis implémenter le service transactionnel avant d’ouvrir les routes HTTP. Le frontend ne sera raccordé qu’après validation des projections fermées et de la non-fuite financière.

Le gate VPS reste indépendant et devra être exécuté sur un hôte Docker réel lorsqu’un VPS sera disponible ; il ne doit pas servir de prétexte pour contourner les validations métier de ce slice.
