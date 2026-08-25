# Rapport de retour développeur — Audit légendaire SMART_AO V8

**Date :** 24 août 2026
**Branche :** `docs/pricing-http-next-lot-28`
**Commit audité initialement :** `33986fb58e382a36b623055b7a0a3033f5c51ac3`
**Rapport auditeur archivé :** `docs/operator-reports/AUDIT_LEGENDAIRE_SMART_AO_V8_2026-08-24.md`
**Auteur :** Manus AI

## 1. Objet et règle de preuve

Le rapport légendaire a été lu intégralement et confronté au dépôt, aux tests et aux invariants du projet. Il est globalement pertinent, particulièrement sur la détection d’une régression du test de contrat Compose et sur le démarrage à froid du stack de développement. Ces deux points n’étaient pas visibles dans la validation précédente et doivent être corrigés.

Les résultats Docker/PostgreSQL/ClamAV live et la couverture avec base PostgreSQL rapportés par l’auditeur sont conservés comme **preuves externes de son environnement**. Ils ne sont pas présentés comme des exécutions locales du sandbox. La seule nouvelle correction exécutée localement ici est la correction du contrat Compose et du fallback JWT de développement ; aucune preuve VPS, fournisseur externe, EICAR, HTTPS public, backup/restore ou CI avec runner n’est fabriquée.

## 2. Résumé de décision

| Point | Décision développeur |
|---|---|
| **OPS-L-001 — test Compose obsolète** | **Confirmé et corrigé.** Le test attendait encore le mapping littéral `127.0.0.1:5432:5432`, alors que le Compose est désormais paramétrable. |
| **OPS-L-002 — cold-start dev cassé** | **Confirmé par le rapport et corrigé dans le code/configuration.** Le fallback `dev-only-*` était refusé par le runtime production ; il est remplacé par une clé explicitement locale, documentée dans `.env.example`, sans modifier la garde production. |
| **SEC-001 — PAT dans le clone d’audit** | **Avéré pour le clone observé par l’auditeur ; non présent dans le clone développeur.** La révocation de l’ancien PAT reste une action du propriétaire GitHub et n’est pas prouvée ici. |
| **CI** | **Toujours bloquée.** Le run post-push `32728988801` a échoué avec `runnerName: null` et `steps: []` sur les trois jobs. |
| **CreateCase** | **Confirmé comme livré côté backend.** La recette PostgreSQL et l’écran frontend restent ouverts. |
| **Dead-letter** | **Partiellement corrigée.** Les retries sont bornés et `FAILED` existe pour les workers ciblés ; `cockpit_projection`, l’alerte et la rétention restent à décider. |
| **Architecture** | **Nouveau slice conforme ; dette historique ARCH-001 inchangée.** Aucun import application→infrastructure supplémentaire n’a été introduit par CreateCase. |
| **Verdict opérationnel** | **NO-GO maintenu.** Le produit n’est pas encore une plateforme AO complète et la chaîne de preuve CI/production reste incomplète. |

## 3. Corrections appliquées

### 3.1 Test de contrat Compose — OPS-L-001

Le test `backend/tests/ops/test_preprod_ops_contract.py::test_dev_compose_is_loopback_bound_and_not_repurposable_as_preprod` attendait le texte fixe `"127.0.0.1:5432:5432"`. Cette assertion était devenue fausse après l’amélioration sûre du Compose :

```yaml
- "127.0.0.1:${SMART_AO_POSTGRES_HOST_PORT:-5432}:5432"
```

Le test vérifie maintenant le mapping paramétrable, le binding loopback, l’environnement `development`, l’absence de l’ancien préfixe `dev-only-signing-key`, et la présence de la clé de développement explicitement documentée dans `.env.example`. La garantie testée est donc plus forte : le port reste local, mais les conflits peuvent être résolus par variable sans réintroduire une exposition réseau.

### 3.2 Démarrage à froid — OPS-L-002

Le rapport a correctement identifié une incohérence entre le fallback du Compose de développement et la garde du runtime `app.bootstrap.production`. Le runtime refuse toute valeur commençant par `dev-only-`, tandis que le Compose injectait précisément `dev-only-signing-key-change-me-0123456789`.

La correction retenue est limitée au contexte local :

```yaml
SMART_AO_ENV: development
SMART_AO_JWT_SIGNING_KEY: ${SMART_AO_JWT_SIGNING_KEY:-local-development-signing-key-change-me-0123456789}
```

La même valeur est ajoutée à `.env.example`, avec l’avertissement qu’elle ne doit jamais être réutilisée en préproduction ou production. La garde de production reste inchangée : `SMART_AO_JWT_SIGNING_KEY` est toujours obligatoire, les placeholders sont refusés et les clés préfixées `dev-only-` sont interdites. `ops/.env.preprod.example` conserve une valeur `REPLACE_WITH_...` et la Compose préproduction exige toujours une injection explicite.

Il n’est pas affirmé que le démarrage Docker a été rejoué dans le sandbox courant : Docker n’y est pas disponible. Le rapport auditeur fournit une preuve externe de l’échec et de son mécanisme ; la correction a été validée par tests statiques et unitaires, mais le `make up` à froid doit être rejoué sur une machine Docker.

## 4. Qualification des autres findings

| ID | Qualification | Action |
|---|---|---|
| **SEC-001** | Pertinent et critique dans le clone audité. Le remote du clone développeur utilisé pour la correction est `https://github.com/mailtkarim-bot/SMART_AO_V8.git`, sans credential. Cela ne prouve pas la révocation d’un PAT historique. | Le propriétaire doit révoquer/régénérer le PAT depuis GitHub et vérifier son journal de sécurité. Aucun secret n’est recopié dans ce rapport. |
| **OPS-001** | Confirmé. Le run post-push de `33986fb` a des jobs sans runner ni steps. | Ne pas fusionner PR #49 ni `main`. Résoudre l’attribution des runners puis exécuter un run complet. |
| **ARCH-001** | Confirmé par inspection, sans aggravation par CreateCase. Le handler utilise les ports applicatifs ; les 64 arêtes historiques restent une dette. | Refactor par bounded context, avec tests de concurrence et de migrations à chaque tranche. |
| **BTP-L-001** | Positif et pertinent. CreateCase existe au backend avec capability patronale, idempotence, validation Case/Consultation et persistence par ports. | Ajouter ultérieurement écran frontend, E2E navigateur et validation PostgreSQL online. |
| **SEC-006-L** | Corrigé. Les headers backend sont montés et couverts par test ; le rapport auditeur les a observés live dans son environnement. | Conserver une recette edge séparée pour HSTS, CSP, Caddy et HTTPS. |
| **SEC-004-L** | Partiellement corrigé. Les redirections sont refusées et les destinations privées filtrées pour webhook et bus. La fenêtre théorique DNS TOCTOU reste explicitement reconnue. | Envisager l’épinglage IP/TLS uniquement avec une conception compatible avec certificats, CDN et multi-A/CNAME. |
| **DB-003-L** | Partiellement corrigé. La policy `retry_policy.py` borne les tentatives à 10 par défaut, plafonne à 100, applique un backoff maximum et écrit `FAILED` sans prochaine tentative. | Ajouter simulation d’intégration poison→FAILED, métrique/alerte et politique de rétention ; définir `cockpit_projection` avant consommation ou purge. |
| **SEC-002** | Confirmé ouvert. Les tables et la décision step-up ne constituent pas une cérémonie MFA/TOTP. | Implémenter enrollment, confirmation, recovery, step-up et tests avant toute promesse MFA. |
| **SEC-003** | Confirmé ouvert. Le rate limiter reste process-local et ne couvre pas toutes les routes coûteuses. | Décider un store partagé ou une admission edge avant multi-réplique. |
| **OPS-005** | Non reproduit par la nouvelle exécution locale : 23 fichiers et 98 tests frontend passent en 6,89 s. Cela ne constitue pas dix répétitions sans erreur. | Surveiller et reproduire sous contrainte CPU avant de modifier la concurrence Vitest. |
| **INT-*** | Qualification pertinente. Les adaptateurs et antennes optionnels ne valent pas des fournisseurs réels. | Recettes distinctes BGE/RAG, Docling/OCR, S3, BOAMP, INSEE, SMTP/ICS, bus et signature, avec secrets hors Git. |
| **BTP-2…15** | Gaps toujours réels : coût de revient/prix plancher, risques CCAP et croisement documentaire, OCR, DC1/DC2/DC4, décision finalisable, fournisseur de signature et dépôt externe. | Les traiter par slices métier indépendants, avec tests et preuves sur corpus anonymisé. |
| **DOC-L-001** | Confirmé puis corrigé. La mention de `906` tests verts était prématurée au commit audité, car un test de contrat échouait. | La nouvelle mesure locale est **906 passés, 458 désélectionnés**, après correction ; la documentation doit utiliser cette mesure et conserver la distinction avec les 1 363 tests DB+non-DB de l’auditeur. |

## 5. Validation locale après correction

Les contrôles suivants ont été exécutés dans le sandbox courant après la correction :

| Commande ou contrôle | Résultat |
|---|---|
| Test Compose ciblé | **2 tests passés**, incluant le contrat Compose et le refus de clé JWT de développement en production. |
| `uv lock --check` | Passé. |
| `uv run ruff check backend scripts` | Passé. |
| `uv run pytest -q -m 'not db' backend/tests` | **906 passed, 458 deselected**, quatre warnings tiers de dépréciation. |
| `bash -n ops/*.sh scripts/*.sh` | Passé. |
| `pnpm install --frozen-lockfile --ignore-scripts` | Passé. |
| `pnpm test --run` | **23 fichiers, 98 tests passés**. |
| `pnpm typecheck` | Passé. |
| `pnpm lint` | 0 erreur, deux warnings `react-hooks/exhaustive-deps` connus dans `App.tsx`. |
| `pnpm build` | Passé ; bundle JS 294,03 kB, 82,95 kB gzip. |
| Docker/PostgreSQL online dans le sandbox | **Non exécutés : Docker indisponible.** |
| CI GitHub post-push | Échec avant steps : `runnerName: null`, `steps: []`. |

La mesure de couverture locale complète n’a pas été recalculée dans cette séquence ; le résultat externe de 90,95 % avec PostgreSQL et le résultat historique de 67,45 % hors DB ne doivent pas être mélangés. Le taux ne sera mis à jour qu’avec une commande de couverture clairement identifiée et réellement exécutée.

## 6. Plan de remède restant

| Priorité | Action de sortie | Condition de validation |
|---|---|---|
| **P0** | Révoquer le PAT historique du clone audité. | Journal de sécurité GitHub et ancien token refusé ; action du propriétaire. |
| **P0** | Rétablir les runners et exécuter la CI complète. | Jobs backend/frontend/image-security avec runner, steps, conclusions et artifacts réels. |
| **P0** | Rejouer le quickstart Docker à froid. | `cp .env.example .env && make up` healthy sur hôte Docker isolé, puis logs/health conservés. |
| **P1** | Recetter PostgreSQL `0056` et CreateCase. | Migrations online, isolation tenant, FKs, append-only, idempotence et révision prouvées. |
| **P1** | Finaliser outbox. | Test poison→FAILED, métrique/alerte, rétention explicite et décision `cockpit_projection`. |
| **P1** | Coder MFA/TOTP avant toute promesse commerciale. | Enrollment, vérification, recovery, step-up récent et tests complets. |
| **P2** | Ajouter écran CreateCase et E2E navigateur. | Login réel, cookies/CSRF, création, rejeu, lecture et contrôle d’accès via HTTPS. |
| **P2** | Coder COST-BASIS, CCAP-RISK, croisement, OCR et génération DC. | Démo sur DCE anonymisé, preuves sourcées, revue humaine et absence de fuite financière. |
| **P2** | Recetter les intégrations externes une par une. | Rapport horodaté par brique, credentials hors Git, timeout, replay et désactivation vérifiés. |
| **P3** | Réduire ARCH-001 et automatiser la parité enums/checks. | Tests d’architecture et migrations verts après chaque bounded context. |

## 7. Verdict final adressé à l’auditeur

Le nouvel audit est **validé dans son diagnostic principal**. Il a détecté une régression réelle que la validation précédente avait manquée : le test de contrat Compose n’avait pas été aligné après le paramétrage du port PostgreSQL. Il a également détecté une incohérence réelle de démarrage à froid : le fallback JWT local était refusé par le runtime de production. Ces deux points sont corrigés dans le code/configuration et couverts par tests.

Le rapport est également correct de maintenir le verdict **NO-GO**. La CI n’exécute toujours pas de steps, la preuve Docker/PostgreSQL fournie est celle de l’environnement auditeur et non une preuve du sandbox, le PAT du clone d’audit doit être révoqué par le propriétaire, et les fonctionnalités BTP centrales ne sont pas encore complètes.

La correction ne prétend pas que SMART_AO V8 est désormais prod ready. Elle établit un état plus exact : **socle technique renforcé, quickstart local corrigé conceptuellement, suite non-DB verte après mise à jour du contrat, mais recette Docker réelle à rejouer, CI à rétablir et produit métier encore incomplet**.

> Au commit de correction suivant `33986fb`, le produit reste **NO-GO opérationnel**. Les corrections immédiates portent sur OPS-L-001 et OPS-L-002. Les preuves PostgreSQL/Docker/VPS/ClamAV/HTTPS/backup-restore/fournisseur externe/CI exécutée ne sont pas fabriquées. Les invariants tenant, append-only, idempotence, révision optimiste, DTO fermés et confidentialité financière restent non négociables.

## Références

[1]: AUDIT_LEGENDAIRE_SMART_AO_V8_2026-08-24.md "Rapport d’audit légendaire archivé"
[2]: AUDIT_RECONCILIATION_2026-08-24_6.md "Réconciliation précédente de l’audit exhaustif"
[3]: PROJECT_STATE.md "État canonique du projet"
[4]: ../todo.md "Checklist durable"
