# SMART_AO V8

SMART_AO V8 est un SaaS web dédié aux entreprises françaises du BTP pour qualifier les appels d'offres, analyser les DCE, préparer les réponses et sécuriser les décisions patronales.

> Le premier slice implémente le noyau durable : **Case**, **Consultation/DceVersion** et **Decision**. Il ne contient ni chiffrage, ni dépôt, ni IA métier, ni espace collaborateur complet tant que les invariants du socle ne sont pas prouvés.

## Principes non négociables

- Le patron décide, chiffre, valide et dépose ; le collaborateur prépare et transmet.
- Les prix, marges, devis et données de trésorerie ne traversent jamais les contrats collaborateur.
- Une transaction modifie un aggregate métier propriétaire ; les effets inter-modules passent par événements, outbox et commandes idempotentes.
- Les versions DCE, contextes de décision et résultats validés sont non destructifs.
- Le domaine reste pur : FastAPI, SQLAlchemy, MinIO, workers et LLM restent hors de `domain/`.

## Démarrage local prévu

```bash
cp .env.example .env
make up
make test
```

Le premier commit pose l'ossature, la documentation de référence, le health check et les tests de fumée. Les migrations DATA-01 seront écrites avec les modèles SQLAlchemy, dans le prochain incrément de code, afin d'éviter des migrations factices.

## Documentation

- [Carte documentaire](docs/reference/SMART_AO_V8_DOCUMENTATION_MAP.md)
- [État de projet](docs/PROJECT_STATE.md)
- [Contrat d'arborescence](docs/reference/SMART_AO_V8_ARC_01_CONTRAT_ARBORESCENCE_MODULES.md)
- [Contrat de domaine](docs/reference/SMART_AO_V8_DOMAIN_01_AGGREGATE_OWNERSHIP_MATRIX.md)
- [Premier slice : états et invariants](docs/reference/SMART_AO_V8_DOMAIN_03_STATE_MACHINES_INVARIANTS_FIRST_SLICE.md)

## Structure

- `backend/app/modules/` : modules métier isolés.
- `backend/app/platform/` : mécanismes transversaux sans métier BTP.
- `backend/app/interfaces/` : interfaces HTTP minces.
- `backend/tests/` : tests de domaine, intégration, architecture, concurrence, sécurité et processus.
- `web/` : frontend React/Vite, organisé par fonctionnalités métier.
- `docs/` : contrats actifs et point de reprise inter-session.
