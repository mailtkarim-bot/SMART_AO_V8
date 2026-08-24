# RAPPORT D'AUDIT N°5 — VÉRIFICATION DU LOT « FOURTH AUDIT REMEDIATIONS »

**Date** : 24 août 2026 · **Branche** : `docs/pricing-http-next-lot-28` @ `cb46d6e`
**Méthode** : lecture de la réconciliation des devs (`rapports/Réconciliation du quatrième audit…`) → review ligne à ligne du diff `4114438..cb46d6e` → **exécution intégrale des preuves que leur sandbox ne pouvait pas produire** : suite complète × PostgreSQL réel (1 343 tests), couverture avec DB active, suite frontend ×2, validation colonne par colonne de la migration critique.

---

## 1. EXECUTIVE SUMMARY

### Note globale révisée : **62 / 100** (+4) — « La régression est réparée et prouvée ; le lot qui devait rendre le stack démarrable casse le démarrage dev »

| Axe | n°4 | n°5 | Évolution |
|---|---|---|---|
| 🔐 Sécurité | 89 | **90** | Supply chain CVE enfin cohérente (pip-audit = Trivy = image réelle). |
| 🏗️ Ingénierie backend | 71 | **76** | Migration 0056 irréprochable, régression corrigée et prouvée sur DB réelle. Restent : couplage inter-modules, garde sous-testée. |
| ⚙️ Opérations | 55 | **63** | Service `migrate` + readiness schéma + restart policies. Mais **le compose dev est cassé par un mauvais chemin** et la CI reste sans runner. |
| 🖥️ Frontend | 58 | **60** | ErrorBoundary remount correct ; 98/98 confirmés (1 timeout sous charge CPU, vert en isolation). |
| 💼 Valeur métier BTP | 26 | **26** | Aucun slice métier — assumé et correctement priorisé comme prochain lot par les devs. |

### Résultats d'exécution (la valeur centrale de cet audit)

| Preuve exécutée ici | Résultat | Verdict sur les revendications devs |
|---|---|---|
| Suite complète backend × PostgreSQL réel | **1 342 / 1 343 passed (99,9 %)** en 14 min | ✅ Confirmé et au-delà de leurs affirmations (eux : non exécutable) |
| Régression patron_action (audit n°4) | Les 2 tests transitions **passent** avec la migration 0056 | ✅ **Régression corrigée, prouvée en base réelle** |
| Couverture avec DB active | **90,99 %** > seuil 85,50 % (`handlers.py` : 97,23 %) | ✅ Gate largement tenu ; la mesure hors-DB est officiellement obsolète |
| Bugs de tests DB de l'audit n°4 (seeds flush, JSON path, regex) | boamp ×2, qualification, capacity, watch_profile : **tous verts** | ✅ Causes racines correctement traitées |
| Suite frontend | **98/98** (échec isolé = timeout 16 s sous charge CPU du run parallèle ; 5/5 en 4,4 s seul) | ✅ Confirmé, avec réserve de robustesse |
| Migration 0056 vs modèle ORM | 18 colonnes verrouillées + 3 mutables = 21 : **aucune colonne oubliée**, DELETE interdit, downgrade fidèle | ✅ Irréprochable |

### Le nouveau défaut critique découvert

🔴 **`docker-compose.yml:26` — le service `migrate` pointe vers `/app/alembic.ini` alors que l'image place le fichier à `/app/backend/alembic.ini`** (`backend.Dockerfile:3,20` : WORKDIR `/app`, `COPY backend ./backend`). Conséquence mécanique : le conteneur migrate crashera à chaque `docker compose up` local → le backend et le worker, gated sur `service_completed_successfully`, **ne démarreront jamais en dev**. Ironie exacte du mode de défaillance fustigé à l'audit n°4 : un correctif validé statiquement (les tests de contrat ne vérifient la chaîne que pour la preprod) et jamais exécuté. La preprod est correcte (`ops/docker-compose.preprod.yml:57-72` + bon chemin dans `deploy-preprod.sh:104`).

---

## 2. VERDICT PAR CORRECTIF REVENDIQUÉ

| Correctif revendiqué (réconciliation n°4) | Verdict | Preuve d'exécution |
|---|---|---|
| Migration 0056 garde colonne-scopée (option B de l'audit n°4) | ✅ **CONFORME — complète** | Review exhaustive : toutes les colonnes historiques verrouillées via `IS DISTINCT FROM` (tolère les no-op), seuls `state`/`aggregate_revision`/`updated_at` mutables, DELETE refusé, downgrade restaurateur fidèle à 0038, chaîne linéaire depuis 0055. Testée en base réelle : transitions OK, altération de `title` rejetée. |
| Readiness = connexion + tête Alembic + ClamAV | ⚠️ CONFORME, fragile | `application.py:654-659` échoue proprement (table absente → 503). MAIS tête **hardcodée** `"20260824_0056"` (`:640`) sans test anti-dérive : la prochaine migration rendra tous environnements `not_ready` si le bump est oublié. Défaut mineur : `database` et `schema` dans le même try → diagnostic ambigu si table absente. |
| Compose : service migrate + depends_on completed | ❌ PREPROD OK / **DEV CASSÉ** | Voir constat critique ci-dessus. Worker dev : `restart: unless-stopped` ajouté ✅. Nit : `PGPASSWORD:?required` exigé et jamais consommé dans le migrate preprod (`:65`) — barrière superflue au `docker compose up`. |
| Seeds/assertions DB corrigés | ✅ **CONFORME** | Flush tenant (`test_boamp_observation_persistence.py:62`, `test_opportunity_event_bus_persistence.py:34`), chemin JSON `payload_json["data"]["profile_id"]` aligné sur l'enveloppe du dispatcher, regex `reused with a different request` — tous verts en base réelle. |
| Extras/supply chain (object-storage ARG, `uv export --all-extras`, build CI 6 extras) | ✅ **CONFORME** | pip-audit, Trivy et image installée couvrent désormais exactement les mêmes 6 extras. Cohérence structurelle réelle — reste non prouvée en run (CI sans runner, documenté honnêtement). |
| `compose.local-dev.yml` loopback | ✅ CONFORME | `127.0.0.1:5433` asserté par contrat et présent. |
| Port storage consommateurs migrés | ✅ CONFORME | Zéro import résiduel application→`preparation.infrastructure.document_storage`. |
| ErrorBoundary remount | ✅ CONFORME (réserve test) | `<Fragment key={resetKey}>` = remount React correct. Le test existant ne prouve pas le remount (enfant déterministe → boucle fallback ; aucun compteur de montages). |

### Nouveaux constats de ce lot

| ID | Gravité | Constat | Localisation |
|---|---|---|---|
| N5-01 | 🔴 | Migrate dev : chemin alembic.ini erroné → stack dev inbootable | `docker-compose.yml:26` |
| N5-02 | 🟠 | Tête Alembic hardcodée dans readiness sans garde anti-dérive ni recoupement test | `bootstrap/application.py:640` |
| N5-03 | 🟠 | Test event_bus retry **dépendant de l'ordre** : aucun fixture truncate dans le module ; le 1er test publie un message, le 2e exige `count(PUBLISHED)==0` global → rouge en suite, vert isolé | `tests/process/test_opportunity_event_bus_persistence.py:125-129` |
| N5-04 | 🟡 | Garde 0056 sous-testée : ni DELETE ni les 17 autres colonnes verrouillées ne sont exercés | `tests/application/test_patron_action_transitions.py:112-123` |
| N5-05 | 🟡 | Échecs ICS ×2 sans l'extra calendar dans le venv local (passe avec `--extra calendar`) : environnement, pas code — mais la commande de validation canonique du projet devrait l'inclure | `ics_calendar.py:62-64` |
| N5-06 | 🟡 | Frontend : timeout vitest serré — échec sous charge CPU parallèle, vert sinon | `App.test.tsx` (16,7 s vs 4,4 s isolé) |

---

## 3. CE QUI RESTE OUVERT (assumé par les devs, confirmé par audit)

Aucune régression de périmètre : les devs listent correctement ce qu'ils n'ont pas fait.

1. **Valeur métier BTP (26/100, inchangée)** — CCAP clause par clause, pénalités/retenues/cautionnement, coût de revient + prix plancher, CCTP↔DPGF↔CCAP, DC1/DC2/DC4, groupement/sous-traitance, OCR actif, mémoire technique assisté, boucle décisionnelle GO/NO-GO fermée. C'est le prochain lot annoncé — le bon ordre.
2. Outbox : contrat `cockpit_projection` + rétention toujours non définis (accumulation continue).
3. MFA/TOTP : cérémonie absente.
4. Import pricing XLSX : toujours sans ClamAV/libmagic.
5. N+1 : non mesurés (correctement refusés « à l'aveugle »).
6. Frontend produit : pas de routeur/deep-links, UUIDs manuels, montants centimes, bus message last-wins, timer proactif absent.
7. CI GitHub : runners toujours morts (run `32680863228` : `steps: []`) — **tous les gates restent théoriques côté distant**, y compris les nouveaux scans supply chain pourtant maintenant bien conçus.
8. Couplage inter-modules : 35 imports croisés dont ~18 `application→infrastructure` (le port storage a supprimé les pires).

---

## 4. PLAN D'ACTION — LOT SUIVANT

### Lot A — Débloquer l'exécution (< 1 jour)
1. Corriger `docker-compose.yml:26` : `/app/alembic.ini` → `/app/backend/alembic.ini` ; étendre le test de contrat à la chaîne dev (pas seulement preprod). Critère : `docker compose up` local amène backend healthy avec base migrée.
2. Ajouter le fixture truncate autouse au module event_bus (ou scopé l'assertion au tenant seedé) — dernier rouge de la suite.
3. Anti-dérive readiness : dériver la tête attendue d'un constant partagé importé par le test de contrat (le test échoue si migration ajoutée sans bump).
4. Inclure `--extra calendar` dans la commande de validation documentée (ou installer l'extra dans l'environnement de dev par défaut).

### Lot B — Verrouiller la preuve (semaine 1)
5. **Script `scripts/prove_online.sh`** (demande répétée de l'audit n°4, toujours absent) : postgres local → pytest full → coverage → verdict horodaté. Cette session prouve encore une fois sa nécessité : 3 bugs de boot/isolation ont été trouvés uniquement parce qu'un humain a exécuté.
6. Runners GitHub Actions vivants — condition sine qua non de toute fusion vers main.
7. Renforcer la garde 0056 par tests (DELETE + échantillon de colonnes verrouillées).

### Lot C — Livrer la valeur métier (semaines 2-8, la vraie priorité produit)
8. CCAP-RISK-01 → COST-BASIS-01 → DOC-GEN-01 (DC1/DC2/DC4) → boucle GO/NO-GO → croisement CCTP-DPGF-CCAP → OCR opt-in. Détail inchangé depuis l'audit n°3 (§7 de `RAPPORT_AUDIT_04_VERIFICATION.md`).

---

## 5. CONCLUSION

Le lot est **de bonne foi et de bonne facture** : la régression critique signalée à l'audit n°4 est réparée avec exactement l'option recommandée, la migration est exemplaire (rien d'oublié, downgrade fidèle), et 8 bugs de preuves ont été correctement traités. Exécuté ici contre PostgreSQL réel : **99,9 % de réussite et 90,99 % de couverture**.

Mais la récurrence est désormais statistiquement établie : **trois lots consécutifs ont livré un défaut qui aurait été attrapé par la simple exécution de ce qui était déjà écrit** (couverture gate, tests DB, démarrage compose). Tant que `prove_online.sh` n'existe pas et que les runners restent morts, chaque nouveau lot produira la même classe de défaut — y compris celui-ci, qui casse le démarrage dev dans le lot précisément intitulé « rendre le stack démarrable ».

**Verdict opérationnel : NO-GO production maintenu.** Le projet est techniquement plus proche du GO que jamais ; la distance restante n'est plus du code, c'est de la discipline de preuve — puis le moteur métier BTP, toujours vide.
