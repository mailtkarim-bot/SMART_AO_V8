# SMART_AO V8 — État final des remédiations

**Date :** 26 août 2026  
**Référentiel de preuve :** `main` à `6c2c5bb`

## Objet

Ce document clôture la tranche de remédiation exécutable dans le dépôt et le sandbox courant. Il distingue les corrections effectivement codées et fusionnées, les validations locales obtenues, les validations CI exécutées sur un runner GitHub attribué et les recettes qui nécessitent encore un environnement, des secrets, un corpus autorisé ou une décision métier externe.

> Une recette non exécutable dans l’environnement courant n’est pas marquée comme validée. Les scripts et harnesses publiés constituent une préparation opérable, pas une preuve d’exécution.

## Lots clôturés dans cette tranche

| Lot | Correction | Preuve de code | Preuve de validation | État |
|---|---|---|---|---|
| DCE context identifiers | Normalisation explicite des identifiants UUID du `CommandContext` dans le handler DCE, typing de la projection et rattachement sûr des evidences à la classification courante. Une evidence sans classification est refusée explicitement. | PR #74, HEAD main `f7e4617` | Run CI `32910860728` : backend, frontend, image-security et Trivy réussis ; backend `11m19s`. Validations locales : Ruff, mypy ciblé et 17 tests non-DB réussis. | Fusionné |
| Membership patron assignment typing | Normalisation de `membership_id`, fingerprints acceptant des séquences covariantes et mapping explicite des trois modèles ORM d’interaction. | PR #75, HEAD main `6c2c5bb` | Run CI `32912209432` : backend, frontend, image-security et Trivy réussis ; backend `24m40s`. Validations locales : 36 tests ciblés non-DB réussis. | Fusionné |
| Dette mypy globale | Suppression des cinq dernières erreurs du module membership après la correction DCE. | `uv run mypy backend/app` | `Success: no issues found in 354 source files`, exécuté sur la branche correspondant au commit fusionné puis vérifié sur `main`. | Clôturé localement |

Les checks CI des PR #74 et #75 ont été vérifiés avant fusion avec `0 failing`, `0 pending` et **4 successful**. Les avertissements de dépréciation Node.js 20 et CodeQL v3 n’ont pas entraîné d’échec ; ils restent des sujets de maintenance de workflow distincts.

## État de `main`

Le dépôt local est propre et synchronisé avec `origin/main` :

```text
6c2c5bb (HEAD -> main, origin/main, origin/HEAD) fix: type patron assignment handlers (#75)
f7e4617 fix: normalize DCE handler context ids (#74)
```

Le contrôle global suivant est vert :

```text
uv run mypy backend/app
Success: no issues found in 354 source files
```

Aucune modification n’a été committée directement sur `main`. Les deux lots ont suivi le cycle branche dédiée, validations locales, commit, push, PR, CI complète verte, squash merge et synchronisation de `main`.

## Validations préparées mais non déclarées exécutées

Les éléments suivants restent ouverts et doivent être exécutés avec leurs preuves propres avant une qualification préproduction ou production :

| Frontière | Ce qui est codé ou outillé | Ce qui manque encore comme preuve externe |
|---|---|---|
| Docker, VPS, Caddy et HTTPS public | Compose, Dockerfiles digest-pinnés, checklist et scripts de preflight publiés. | Exécution sur un hôte Docker/VPS réel, health/readiness, certificats, HTTPS public, logs persistants et supervision réseau. |
| ClamAV réel et EICAR | Import fail-closed, intégration clamd et harness de recette publiés. | Test EICAR contre un daemon ClamAV réellement déployé, avec conservation du verdict et de la signature. |
| PostgreSQL online | Tests DB, migrations, contraintes, triggers et recettes sont présents ; les workflows CI ont exécuté leurs tests backend. | Une recette opérée et archivée sur la base cible de préproduction reste nécessaire pour les paramètres, sauvegardes, restauration, concurrence et supervision de cette cible. |
| Backup/restauration | Scripts et procédure de sauvegarde/restauration isolée publiés. | Exécution opérée hors hôte avec hashes, échantillon documentaire, contrôle tenant, état outbox et preuve de rotation. |
| Fournisseurs et secrets | Adaptateurs et contrats locaux fail-closed pour S3, SMTP, signature, bus, OCR et BOAMP. | Comptes, URL, secrets injectés hors Git, garanties de livraison et recettes contrôlées auprès des fournisseurs réels. |
| Corpus DCE/BGE/OCR/RAG | Manifeste Golden contrôlé, validateur et workers préparés. | Corpus DCE anonymisé et autorisé, cache/modèle BGE, mesures de rappel/précision et validation de l’usage des données. |
| Performance/N+1 | Readers bornés et tests de comportement publiés. | Profilage sous PostgreSQL de préproduction et optimisation guidée par mesures, non par hypothèse. |
| Validation juridique et métier | DTOs, événements et garde-fous techniques limitent les surfaces sensibles ; les enveloppes DC1/DC2/DC4 sont non contractuelles. | Validation formelle des textes, droits `PATRON_DELEGATE`, usages opérationnels, conservation et conformité par les responsables compétents. |

Ces points ne sont **pas** comptés comme exécutés par la présente tranche. Les scripts tels que `ops/preflight-checklist.sh`, les recettes PostgreSQL et les runbooks associés doivent être lancés dans les environnements correspondants, puis leurs sorties conservées comme artefacts de recette.

## Conclusion de la tranche codable

La dette de typage mypy globale identifiée après le lot DCE est résolue : **354 fichiers de l’application backend sont vérifiés sans erreur**. Les régressions découvertes par la CI ont été corrigées avant fusion, notamment l’invariant de clé étrangère entre evidence et classification DCE. La suite de remédiation techniquement codable dans le dépôt est donc clôturée pour cette tranche ; les frontières listées ci-dessus demeurent volontairement ouvertes jusqu’à obtention de preuves externes ou de décisions métier autorisées.
