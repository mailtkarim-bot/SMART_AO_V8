# Matrice de réconciliation de l’audit SMART_AO_V8

Ce document compare l’audit joint, réalisé sur une version antérieure du dépôt, à l’état courant de `ops/vps-deploy-health-digests-01`. Il évite de réimplémenter des corrections déjà publiées et fixe les lacunes encore à traiter.

| Constat de l’audit | État courant vérifié | Décision corrective |
|---|---|---|
| C1 — application production assemblée vide et clé JWT absente | **Corrigé** par `backend/app/bootstrap/production.py`, `app.bootstrap.production:app`, variables JWT obligatoires et refus des placeholders ; Compose démarre cette factory. | Ajouter des tests de garde si une régression apparaît, mais ne pas recréer l’assemblage. |
| C2 — absence de protection anti-brute-force sur login/refresh | **Ouvert** : aucune limitation par identité/IP n’est présente dans la frontière HTTP. | Implémenter un throttling déterministe, fail-closed, borné en mémoire par processus pour le préprod, avec abstraction remplaçable Redis/PostgreSQL et audit minimal des refus. |
| E1 — infrastructure de tests non hermétique | **Ouvert** : plusieurs tests utilisent encore `127.0.0.1:5432` et chaque module construit ses propres fixtures. | Centraliser la résolution `SMART_AO_TEST_DATABASE_URL`, supprimer les URLs codées en dur et ajouter une fixture commune sans masquer les tests PostgreSQL. |
| E2 — observabilité applicative quasi absente | **Partiellement corrigé** : healthchecks, logs Docker/Caddy et supervision opérateur existent, mais pas de logging JSON applicatif ni métriques de base. | Ajouter un module d’observabilité structuré, request-id, logs minimisés et endpoint métriques sans finance ni secrets. |
| M1 — Compose de production expose PostgreSQL | **Corrigé** dans `ops/docker-compose.preprod.yml` : seul Caddy publie 80/443, le réseau interne est privé. | Conserver un test de contrat Compose. |
| M2 — backend root, absence de healthcheck/image digest | **Partiellement corrigé** : digests et healthcheck Compose sont présents, mais l’image backend n’impose pas encore un utilisateur non-root. | Ajouter un utilisateur runtime non privilégié et vérifier les permissions de la quarantaine. |
| M3 — dépendances frontend `latest` et absence de CI frontend | **Partiellement corrigé** : le job frontend existe et le build strict passe, mais `package.json` contient encore `latest`. | Remplacer `latest` par les versions exactes déjà résolues dans `pnpm-lock.yaml` et conserver le build strict. |
| M4 — absence de seuil coverage bloquant | **Ouvert** : la CI exécute pytest mais aucun seuil de couverture n’est imposé. | Ajouter un seuil initial explicite et reproductible, sans diminuer la couverture effective par exclusion silencieuse. |
| M5 — CORS non cadré | **À cadrer** : le déploiement same-origin via Caddy n’exige pas CORS, mais le mode frontend/API séparés n’a pas de contrat. | Ajouter une configuration d’origines explicite ; aucune origine `*` en production et aucun CORS si la liste est vide. |
| Faible — rotation JWT absente | **Partiellement corrigé** : un utilitaire manuel de rotation existe, mais le codec reste mono-clé sans `kid`/chevauchement. | Documenter la fenêtre d’invalidation actuelle puis préparer le support multi-clés seulement si la politique de déploiement l’exige. |

## Ordre de traitement

Les corrections sont livrées par tranches : anti-brute-force et garde production, centralisation des tests, observabilité/runtime non-root, puis reproductibilité et raccordement frontend. Chaque tranche doit rester tenant-scoped, ne jamais exposer de donnée financière dans les contrats collaborateur, conserver l’idempotence et être validée localement puis par CI GitHub.
