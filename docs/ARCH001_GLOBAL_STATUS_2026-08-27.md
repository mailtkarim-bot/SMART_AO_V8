# ARCH-001 — État global du refactoring au 27 août 2026

## Périmètre et méthode

Ce rapport décrit l’état observé dans le dépôt `SMART_AO_V8` après le dernier merge sur `main`. Le compteur ARCH-001 est calculé par recherche reproductible des fichiers Python situés sous `backend/app/modules/*/application` et `backend/app/bootstrap` qui importent encore directement un module `infrastructure`.

La couverture locale indiquée ici correspond à une exécution de la suite backend hors marqueur `db`. Elle est donc informative et ne remplace pas la couverture CI complète avec PostgreSQL, migrations et tests d’intégration.

## État Git et refactorings récemment livrés

La branche locale est `main`, synchronisée avec `origin/main`, sans modification de travail. Le dernier commit est `7d5db4b`, issu de la PR #106.

Les micro-lots récemment fusionnés sont :

| Lot | PR | Résultat architectural |
|---|---:|---|
| Enterprise Capability | #100 | Résolution du propriétaire via `EnterpriseCapabilityContextReader` |
| Enterprise Registry | #101 | Contrat registre INSEE déplacé dans l’application |
| Enterprise Library | #102 | Projection de bibliothèque déléguée à un lecteur injecté |
| Financial Report Reader | #103 | Projection de rapport financier sortie du service Membership |
| Pricing Import Reader | #104 | Preview et état dérivé des transitions lus via un port |
| Financial Line Context Reader | #105 | Existence du snapshot vérifiée via un port avant mutation |
| Financial Draft Case Reader | #106 | Existence du dossier vérifiée via un port avant création du brouillon |

Les handlers transactionnels restent responsables des verrous, transitions, révisions, écritures et événements. Les extractions de lecteurs n’ont pas transformé les actions patronales en décisions automatiques et ne constituent pas une validation juridique.

## Métriques globales observées

| Indicateur | Valeur | Qualification |
|---|---:|---|
| Fichiers de tests backend | 221 | Comptage des `test_*.py` hors cache |
| Fichiers de tests frontend | 27 | Comptage des fichiers `*.test.*` sous `web/src` |
| Tests backend hors DB | **1108 passed**, 477 deselected | Exécution locale réussie |
| Couverture backend locale hors DB, branches incluses | **69,27 %** | Rapport partiel, gate global non concluant |
| Gate CI de couverture | 85,50 % | Gate complet exécuté en CI avec PostgreSQL |
| Ruff global | Réussi | Aucun problème de lint détecté |
| Mypy global `backend` | **228 erreurs dans 76 fichiers** | Principalement des incompatibilités de types dans des tests/fixtures ; le contrôle CI actuellement configuré est plus ciblé |
| Format Ruff global | **210 fichiers à reformater**, 665 déjà formatés | Dette de formatage préexistante hors périmètre de ce micro-lot |
| Format Ruff des fichiers du dernier lot | Réussi | Fichiers touchés par #106 correctement formatés |
| Frontend | Typecheck, lint, 119 tests, build réussis | Validation locale et CI récentes vertes |

La couverture locale de 69,27 % ne doit pas être comparée directement au résultat CI complet : les tests DB désélectionnés représentent une partie importante du parcours transactionnel. De même, le résultat mypy global inclut 678 sources, dont des fixtures et tests qui ne sont pas tous soumis au même périmètre dans le workflow CI.

## Compteur ARCH-001

La métrique actuelle donne **35 fichiers** contenant encore un import direct d’infrastructure dans le périmètre application/bootstrap. Les candidats pricing et membership restants comprennent notamment :

- `membership/application/assignment.py` ;
- `membership/application/collab_capability.py` ;
- `membership/application/collab_info_blockers.py` ;
- `membership/application/collab_work_task.py` ;
- `membership/application/financial_report_draft.py` ;
- `membership/application/financial_report_lines.py` ;
- `membership/application/financial_report_publication.py` ;
- `membership/application/patron_assignment.py` ;
- `pricing/application/import_creation.py` ;
- `pricing/application/import_service.py` ;
- `pricing/application/service.py` ;
- `pricing/application/transition_service.py`.

Certains fichiers apparaissent encore dans ce compteur parce qu’ils contiennent un handler transactionnel qui importe légitimement des modèles persistants, même si la façade de service a déjà été partiellement découplée. Le compteur mesure donc une dette d’arêtes d’import, et non un nombre exact de services entièrement non refactorés.

## Feuille de route globale

### Tranches techniquement codables en cours

La priorité immédiate reste l’inversion progressive des dépendances dans les bounded contexts pricing et membership. Le prochain micro-lot doit rester limité à un service ou à un lecteur cohérent, avec port explicite, adaptateur dans la composition root, test pur de frontière et tests DB conservés pour la transaction. Les candidats prioritaires sont `financial_report_publication.py`, `import_creation.py` et les façades pricing/scénarios qui conservent encore des dépendances historiques.

Le second axe technique est l’augmentation de la couverture et la réduction des erreurs mypy dans les tests et fixtures, sans masquer les erreurs par des exclusions artificielles. La dette de formatage globale doit être traitée séparément, par lots dédiés, car elle touche 210 fichiers et ne doit pas être mélangée à un refactoring métier.

### Fonctionnalités métier restant à construire

Le cœur BTP différenciant reste à compléter avec la détection structurée des clauses CCAP/CCTP, le croisement CCTP–DPGF–BPU, la détection de contradictions interdocuments, les transitions de traitement des risques, l’OCR des DCE scannés, la qualité d’un corpus Golden OCR/RAG, ainsi que la bibliothèque de qualifications et références.

Le parcours commercial reste également à compléter avec les intégrations fournisseurs réelles, la signature eIDAS réelle, les contrôles E2E navigateur authentifiés, le routeur frontend, le rate limiting distribué et le profilage N+1. Les brouillons DC1/DC2/DC4 restent des propositions serveur bornées, non des documents juridiquement validés.

### Validation et exploitation externes

Les recettes VPS, staging et production, Docker local, ClamAV/EICAR, HTTPS réel, sauvegarde/restauration opérée, secrets, SMTP/S3/bus, fournisseurs de signature, corpus autorisé et validation juridique restent explicitement hors revendication tant que les accès, données, prestataires et responsables de validation ne sont pas fournis.

## Conclusion opérationnelle

Le dépôt possède désormais une série de petits ports et adaptateurs pour plusieurs parcours Enterprise, pricing et membership, avec une CI GitHub post-merge verte jusqu’à la PR #106. Le projet n’est pas déclaré entièrement vendable sur cette seule base : la dette d’architecture diminue, mais la couverture locale partielle, les erreurs mypy globales de tests, le formatage historique et plusieurs capacités métier/externe restent à traiter séparément.
