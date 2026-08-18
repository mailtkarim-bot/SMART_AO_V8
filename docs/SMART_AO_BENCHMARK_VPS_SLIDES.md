# SMART_AO V8 — Benchmark ZIP et validation VPS

## Cover
Benchmark de compression, audit du worker webhook et feuille de route opérationnelle VPS

Août 2026 · Branche `ops/vps-deploy-health-digests-01`

## Slide 1
### Décision en une phrase
Le niveau `ZIP_DEFLATED` 6 est retenu : il réduit l’archive BTP de 3,70 % sur le corpus mesuré sans gain supplémentaire au niveau 9.

- Corpus : 2 PDF publics BTP, 5,81 Mo, 98 pages cumulées
- Mesure locale reproductible avec hashes et timestamps ZIP figés
- Validation VPS encore distincte et non exécutée

## Slide 2
### Le corpus reflète des documents déjà compressés
- DCE plomberie : 75 pages
- CCTP lot travaux : 23 pages
- Taille totale avant archivage : 5 807 069 octets
- Les PDF limitent mécaniquement le gain attendu de DEFLATE

## Slide 3
### Le niveau 6 domine le compromis taille / temps
| Profil | Taille ZIP | Réduction | Temps |
|---|---:|---:|---:|
| STORED | 5 807 704 o | -0,01 % | 0,048 s |
| DEFLATED 6 | 5 592 481 o | 3,70 % | 0,220 s |
| DEFLATED 9 | 5 592 481 o | 3,70 % | 0,248 s |

- Niveau 9 : aucune réduction additionnelle
- Décision : conserver `compresslevel=6`
- À compléter : p50/p95, RSS, CPU, I/O et corpus DOCX/XLSX/CSV/TXT

## Slide 4
### L’implémentation protège la mémoire, mais le flux source reste perfectible
- `SpooledTemporaryFile` bascule sur disque au-delà de 8 MiB
- Timestamps et permissions figés pour le déterminisme et la confidentialité
- Le benchmark lit chaque PDF deux fois : hash puis écriture ZIP
- Prochaine optimisation : lecture par chunks ou interface de stockage en flux

## Slide 5
### Le worker webhook couvre les décisions critiques
- 14 tests unitaires dédiés, couverture ciblée : 80 % avec branches
- Allowlist : dossier, hash archive, canal `DOWNLOAD`
- Aucun montant, snapshot financier, storage key ou contenu documentaire
- Couverture ajoutée : lease, message absent, topic incorrect, retry HTTP, idempotence

## Slide 6
### Quatre risques restent à fermer avant production
- Concurrence PostgreSQL réelle entre deux workers avec `SKIP LOCKED`
- Succès réseau réel, timeouts, `HTTPError`, `URLError` et `429`
- Redirections et validation stricte des hashes SHA-256 hexadécimaux
- Politique d’échec définitif, alerte et dead-letter

## Slide 7
### Le VPS sera validé par un gate en sept contrôles
1. Accès SSH, DNS, secrets `0600`, firewall et stockage backup
2. Compose digest-pinné et ports internes non publiés
3. Migrations, PostgreSQL, ClamAV, backend, frontend et Caddy
4. TLS, `/healthz/live`, `/healthz/ready` et certificats
5. EICAR préproduction et traçabilité `REJECTED`
6. Export, audit, outbox, worker webhook et non-fuite financière
7. Backup hors VPS, restauration isolée, timers et supervision

## Slide 8
### La charge sera progressive et arrêtée par des garde-fous
- Paliers : 10, 50, 100 exports séquentiels puis 10 concurrents
- Mesures : latence, ratio ZIP, p50/p95, CPU, RSS, I/O, backlog, retries
- Arrêt immédiat : perte outbox, fuite, 5xx persistants, saturation ou port exposé
- Acceptance : zéro perte, zéro fuite, retries bornés, restauration réussie

## Slide 9
### Prochaines étapes ordonnées
- Ajouter les tests PostgreSQL de concurrence et un endpoint HTTP local de test
- Répéter le benchmark cinq fois par profil et publier médiane/p95
- Ajouter un corpus autorisé DOCX/XLSX/CSV/TXT sans données sensibles
- Obtenir VPS, DNS et stockage hors site
- Exécuter le gate opérationnel puis automatiser la charge depuis un runner séparé

## Slide 10
### Conclusion
Le socle applicatif est prêt pour la validation préproduction, mais la preuve VPS reste une étape distincte.

Les artefacts de référence sont : le rapport benchmark, l’audit code webhook, le plan de charge et la spécification opérationnelle VPS.
