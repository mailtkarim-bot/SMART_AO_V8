# Plan infrastructure VPS et automatisation des tests de charge

## Objectif

Mettre en place une préproduction VPS reproductible, observable et réversible, puis automatiser les tests de santé, d’export ZIP et de consommation outbox sans exposer de données financières. Le plan démarre uniquement lorsqu’un VPS, un DNS de préproduction et un stockage de sauvegarde hors VPS sont disponibles.

## Phase 0 — Préparer les accès et le budget de risque

L’opérateur fournit un VPS dédié à la préproduction, une adresse IP, un nom DNS, un compte SSH non root avec `sudo`, une politique de pare-feu et une destination de sauvegarde hors VPS. Les secrets restent dans `.env.preprod` sur la machine cible avec `0600`; ils ne sont jamais ajoutés au dépôt, au benchmark ou aux rapports.

Les critères d’entrée sont un accès SSH fonctionnel, une résolution DNS correcte, une horloge synchronisée et une capacité disque suffisante pour PostgreSQL, ClamAV, la quarantaine, les archives et les sauvegardes temporaires. Avant le premier déploiement, l’opérateur valide également une fenêtre de maintenance et un plan de destruction de la préproduction.

## Phase 1 — Installer et durcir le VPS

Installer Docker Engine et le plugin Compose depuis une source approuvée, configurer le démarrage automatique, le pare-feu et la rotation des journaux. Seuls 80/443 doivent être accessibles depuis Internet; SSH doit être limité aux adresses opérateur autorisées. PostgreSQL, ClamAV et le réseau interne Compose ne doivent pas publier de port externe.

Installer les unités systemd du projet pour le backup et le healthcheck, activer les timers et vérifier leur première exécution. La configuration doit être exportée avant déploiement, sans secrets, afin de conserver la preuve de l’état initial.

## Phase 2 — Déployer et vérifier la chaîne applicative

Exécuter `ops/deploy-preprod.sh config`, puis `ops/deploy-preprod.sh deploy`. La séquence attend PostgreSQL et ClamAV, réalise le backup préalable si nécessaire, applique `alembic upgrade head`, lance les services, puis exécute les contrôles de santé.

L’automatisation doit collecter les sorties suivantes : commit déployé, digests d’images, versions Alembic, statut de chaque service, ports publiés, réponses live/ready, statut TLS et âge du dernier backup. Une release est refusée si un digest manque, si une migration échoue ou si un port interne est exposé.

## Phase 3 — Installer un harnais de charge contrôlé

Le harnais doit fonctionner depuis une machine distincte du VPS afin de mesurer le service via HTTPS et de ne pas confondre la charge client avec la charge serveur. Il doit disposer d’un mode dry-run, d’un identifiant de campagne, d’un jeu de dossiers non sensibles et d’un export JSON des métriques.

Le scénario comprend quatre familles de mesures :

| Famille | Mesures |
|---|---|
| Santé | latence et taux de succès de `/healthz/live` et `/healthz/ready` |
| ZIP | taille d’entrée, taille ZIP, ratio, temps, p50/p95, hash déterministe |
| Outbox | messages PENDING/RETRY/PUBLISHED, tentatives, âge du plus ancien message |
| Ressources | CPU, RSS, I/O, redémarrages, espace disque, logs d’erreur |

Les paliers sont 10 exports séquentiels, 50 exports séquentiels, 100 exports séquentiels et 10 exports concurrents. Chaque palier est séparé par une période d’observation et ne doit pas utiliser de documents clients. Le harnais conserve uniquement les identifiants de campagne, tailles, timings, codes HTTP, hashes et compteurs.

## Phase 4 — Automatiser l’exécution

Ajouter un workflow manuel GitHub Actions ou une commande opérateur déclenchée depuis un runner autorisé. Le workflow doit demander explicitement l’URL de préproduction, l’identifiant de campagne et le niveau de charge; il ne doit jamais prendre les secrets depuis les logs. Les secrets de webhook et d’authentification sont injectés par le gestionnaire de secrets du runner.

Le workflow exécute d’abord un smoke test, puis le palier 10, et ne poursuit vers 50 ou 100 que si le smoke test et le palier précédent sont verts. Les artefacts publiés sont un rapport Markdown/JSON, un résumé des logs filtré et les hashes des archives. Les fichiers documentaires eux-mêmes ne sont pas publiés.

Une tâche planifiée côté VPS peut surveiller le backlog et la santé, mais le test de charge ne doit pas être lancé automatiquement en production sans fenêtre approuvée. La fréquence, le budget CPU et le volume maximal doivent être des paramètres versionnés et revus avant activation.

## Phase 5 — Contrôler les invariants métier et sécurité

Chaque campagne doit prouver qu’aucune donnée financière ne traverse le webhook. Le récepteur de test doit refuser ou signaler les clés inattendues, notamment les montants, lignes de prix, snapshots financiers, storage keys et contenus documentaires. Le test doit également démontrer qu’un rejeu du même événement ne crée pas de double effet côté récepteur.

La campagne doit vérifier l’isolation tenant avec des dossiers de test distincts, l’absence de publication des fichiers privés, le maintien des permissions `0600`, la conservation de l’audit d’export et l’absence de secrets dans les journaux.

## Phase 6 — Critères d’arrêt et décision

Arrêter immédiatement la campagne en cas de perte d’outbox, réponse 5xx persistante, fuite de payload, redémarrage répété, saturation mémoire, dépassement de l’espace disque, échec TLS, exposition d’un port interne ou divergence de hash pour un même dossier.

La validation est ACCEPTÉE seulement si toutes les campagnes prévues terminent sans perte ni fuite, si les retries restent bornés, si le backlog revient à zéro ou à son niveau de référence, si les backups sont vérifiés et si la restauration isolée a réussi. Sinon, le résultat est CONDITIONNEL ou REFUSÉ et doit inclure une action corrective avec responsable et échéance.

## Artefacts attendus

La campagne produit :

1. un manifeste de campagne avec commit, URL cible non secrète, timestamps UTC et paramètres;
2. un rapport Markdown avec p50/p95, ratios ZIP, taux d’erreur et compteurs outbox;
3. un JSON brut des mesures;
4. un résumé des logs Docker/Caddy/worker filtré des secrets;
5. les hashes des archives et du backup;
6. la preuve du healthcheck, du test ClamAV, de la restauration isolée et de la vérification tenant.

Les artefacts sont conservés dans un emplacement privé avec une durée de rétention définie. Aucun document BTP, token, mot de passe ou contenu financier ne doit être attaché au workflow GitHub ou au ticket public.
