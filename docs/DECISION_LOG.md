# Decision Log

| Date | Décision | Motif | Référence |
|---|---|---|---|
| 2026-08-13 | Démarrer V8 par `Case`, `DceVersion` et `Decision`. | C'est le socle de continuité, source et arbitrage humain avant analyse, prix et dépôt. | DOMAIN-01, DOMAIN-03 |
| 2026-08-13 | Adopter un monolithe modulaire PostgreSQL. | Fiabilité, simplicité opérationnelle et déploiement VPS par client ; aucune microarchitecture prématurée. | DOMAIN-01, ARC-01 |
| 2026-08-13 | Créer uniquement les modules du premier slice. | Éviter l'architecture vide et garder chaque dossier relié à un test et un besoin réel. | ARC-01 |
| 2026-08-13 | Utiliser `docs/PROJECT_STATE.md` comme point de reprise. | Garantir la continuité inter-session et l'arrivée d'un autre développeur. | ARC-01 |
