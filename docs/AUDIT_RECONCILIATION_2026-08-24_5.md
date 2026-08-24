# Rapport de retour — audit n°5 SMART_AO V8

**Date de vérification :** 24 août 2026
**Branche examinée :** `docs/pricing-http-next-lot-28` à `cb46d6e` avant ce lot
**Source :** [`docs/operator-reports/RAPPORT_AUDIT_05_VERIFICATION.md`](operator-reports/RAPPORT_AUDIT_05_VERIFICATION.md)
**Méthode :** lecture complète du rapport, confrontation aux fichiers concernés, correction des findings avérés, validations locales disponibles et conservation séparée des preuves qui nécessitent un environnement Docker/PostgreSQL réel.

## 1. Verdict exécutif

Le cinquième audit est **pertinent**. Il a détecté un défaut critique que la validation statique précédente ne pouvait pas révéler : le service `migrate` du Compose de développement utilisait `/app/alembic.ini`, alors que l’image backend copie réellement le fichier vers `/app/backend/alembic.ini`. Il a également identifié quatre durcissements utiles et sûrs : protection anti-dérive de la tête Alembic, isolation d’une assertion event-bus, couverture plus complète de la garde 0056, et robustesse de la suite frontend sous charge CPU.

Ces points ont été corrigés sans modifier les invariants métier : isolation tenant côté serveur, append-only historique, idempotence, révision optimiste et confidentialité financière. Le rapport source a été archivé dans `docs/operator-reports/`.

| Finding | Qualification | Correction |
|---|---|---|
| N5-01 — chemin Alembic dev erroné | **Confirmé critique** | `/app/alembic.ini` remplacé par `/app/backend/alembic.ini`; contrat Compose ajouté. |
| N5-02 — tête Alembic hardcodée | **Confirmé** | Constante platform partagée + test comparant cette constante au graphe Alembic réel. Diagnostic DB/schema séparé. |
| N5-03 — test event-bus dépendant de l’ordre | **Confirmé** | Assertion `PUBLISHED` limitée au tenant seedé par le test. |
| N5-04 — garde 0056 sous-testée | **Confirmé** | Test des 18 colonnes historiques verrouillées et de `DELETE`; projection reste testée comme seule surface mutable. |
| N5-05 — extra calendar absent de la commande canonique | **Confirmé environnemental** | `make install`, `make test` et le runbook PostgreSQL incluent explicitement `--extra calendar`. |
| N5-06 — timeout frontend fragile sous charge | **Confirmé comme risque de test** | `testTimeout` et `hookTimeout` Vitest réglés à 15 secondes, sans changement de code de production. |
| Nouvelles remarques métier/infra | **Confirmées comme ouvertes** | Aucun contournement artificiel; elles restent dans la feuille de route. |

## 2. Corrections détaillées

### 2.1 Démarrage Compose de développement

Le finding N5-01 était exact. `ops/docker/backend.Dockerfile` définit `WORKDIR /app`, copie `backend` vers `/app/backend`, puis utilise le fichier Alembic situé dans ce répertoire. Le service `migrate` du Compose dev pointe maintenant vers `/app/backend/alembic.ini`. Le backend et le worker de rétention restent dépendants de `service_completed_successfully`, ce qui conserve la garantie qu’ils ne démarrent pas sur un schéma non migré.

Le chemin préproduction était déjà correct et n’a pas été modifié. La correction n’est pas présentée comme une preuve de démarrage réel : Docker n’est pas disponible dans le sandbox courant.

### 2.2 Anti-dérive de la tête Alembic et diagnostic readiness

Le finding N5-02 est confirmé. La valeur attendue est désormais centralisée dans `backend/app/platform/persistence/schema.py` sous `EXPECTED_ALEMBIC_HEAD`. Le contrôle `/healthz/ready` utilise cette constante. Le nouveau test d’architecture charge le graphe Alembic avec `ScriptDirectory` et exige que sa tête réelle corresponde à la constante. L’ajout d’une future migration sans mise à jour de ce contrat fera donc échouer le test au lieu de laisser une dérive silencieuse.

Le diagnostic a également été séparé : une connexion PostgreSQL fonctionnelle donne `database: ok`; l’absence ou le retard de `alembic_version` donne `schema: failed`. Cela distingue mieux la panne de base de données de la panne de migration. Le script `ops/healthcheck-preprod.sh` exige désormais aussi `schema: ok` dans la réponse readiness.

### 2.3 Isolation du test event-bus

Le finding N5-03 est confirmé. Le test de rejet externe comptait tous les messages `PUBLISHED` de la base, ce qui pouvait être influencé par un autre test exécuté avant lui. L’assertion est maintenant limitée au `tenant_id` créé par le test. La logique du worker et le contrat de publication après accusé fournisseur ne sont pas modifiés.

### 2.4 Garde append-only 0056

Le finding N5-04 est confirmé. La migration 0056 verrouille 18 colonnes historiques et laisse seulement `state`, `aggregate_revision` et `updated_at` mutables. Le test PostgreSQL couvre maintenant chaque colonne verrouillée individuellement — identifiant, tenant, dates, affaire, clé fonctionnelle, type, sévérité, textes, échéance, références, acteurs, commande, idempotence et corrélation — ainsi que `DELETE`. Les tentatives exigent l’erreur `append-only`.

La projection autorisée est toujours testée séparément avec la mise à jour de `state` et `aggregate_revision`. Le test élargi est marqué implicitement DB par sa fixture `session_factory`; il nécessite donc PostgreSQL réel et n’est pas compté dans la suite non-DB.

### 2.5 Extra calendar et validation frontend

Le finding N5-05 ne révèle pas une dépendance absente du projet : `icalendar` est bien déclaré et verrouillé dans l’extra `calendar`. Le défaut portait sur la procédure d’installation/validation qui pouvait créer un environnement sans cet extra. `Makefile` utilise maintenant `uv sync --group dev --extra calendar` pour l’installation et `uv run --extra calendar pytest` pour les commandes de test. Le runbook `docs/LOCAL_POSTGRES_TESTING.md` reprend la même exigence.

Pour N5-06, la configuration Vitest définit `testTimeout` et `hookTimeout` à 15 secondes afin de rendre les tests composants fiables sur des runners partagés ou fortement chargés. Il s’agit d’un plafond de test explicite, pas d’un masquage d’un délai réseau applicatif : les timeouts du transport frontend restent inchangés et bornés séparément.

## 3. Validation exécutée

| Contrôle | Résultat |
|---|---|
| Suite backend non-DB | **888 passed, 458 deselected, 4 warnings** en 12,15 s |
| Tests ciblés architecture/ops/readiness | **31 passed, 1 warning** |
| Suite frontend | **23 fichiers, 98 tests passés** |
| Typecheck frontend | Passé |
| Build Vite | Passé |
| ESLint | 0 erreur, 2 avertissements `react-hooks/exhaustive-deps` connus dans `App.tsx` |
| Ruff backend/scripts | Passé |
| mypy noyau sécurité | Passé sur les quatre fichiers de sécurité configurés |
| `uv lock --check` | Passé |
| `pnpm install --frozen-lockfile --ignore-scripts` | Passé |
| Syntaxe shell | `bash -n` passé pour les scripts opérateur concernés |
| `git diff --check` | Passé avant commit |
| Docker réel | Non disponible dans le sandbox |
| PostgreSQL online | Non disponible dans le sandbox |
| CI GitHub | Toujours non probante; le dernier run connu avait des jobs sans étapes |

La migration 0056 et la nouvelle constante ont également été contrôlées statiquement par le test du graphe Alembic. La validation réelle du trigger colonne-scopée, des tests event-bus et du démarrage Compose doit rester exécutée sur la machine disposant de PostgreSQL et Docker. Aucune couverture DB ni réussite Docker n’est revendiquée par ce retour.

## 4. Éléments non corrigés volontairement

Les écarts suivants du rapport sont pertinents mais dépassent une correction sûre de plomberie : définition et rétention du topic `cockpit_projection`, cérémonie TOTP/MFA, ClamAV/libmagic de l’import pricing, mesure des N+1, routeur/deep-links/pagination frontend, renouvellement proactif JWT, réduction structurée des couplages inter-modules, et lots métier CCAP-RISK, COST-BASIS, prix plancher, DC1/DC2/DC4, OCR et RAG/BGE sur corpus réel.

La couverture de 90,99 % et la réussite PostgreSQL de 1 342/1 343 annoncées par le rapport source sont des preuves fournies par l’auditeur. Elles n’ont pas été reproduites dans le sandbox courant et ne sont donc pas transformées en revendication locale. Le projet demeure **NO-GO production** tant que la recette online, Docker/ClamAV/HTTPS, la sauvegarde-restauration, les runners GitHub et la validation métier ne sont pas exécutés sur leurs environnements cibles.

## 5. Commits attendus

Les corrections seront publiées dans un commit de code dédié et la présente réconciliation, avec le rapport source archivé, dans un commit documentaire séparé. La branche `docs/pricing-http-next-lot-28` ne doit pas être fusionnée vers `main` sur la base d’un run CI qui échoue avant ses étapes.

> **Conclusion :** l’audit n°5 a trouvé un défaut réel de démarrage dev et plusieurs faiblesses de preuve. Ils sont maintenant traités. Le résultat améliore la démarrabilité, la détectabilité des dérives et la stabilité des tests, mais ne constitue ni une recette Docker/PostgreSQL online ni l’achèvement du produit métier BTP.
