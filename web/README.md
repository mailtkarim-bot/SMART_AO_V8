# Cockpit patron SMART_AO V8

Le frontend fournit le premier incrément du **cockpit patron** : lecture des affaires assignées, chargement d’un snapshot financier `DRAFT`, affichage de la synthèse et des lignes, puis ajout contrôlé d’une ligne avec la révision courante.

Le cockpit ne contient aucune logique d’autorisation métier. Il transmet le Bearer token à l’API FastAPI, qui reste seule responsable de l’identité, du tenant, de la capability et de la policy financière.

## Démarrage local

Depuis ce répertoire :

```bash
pnpm install --frozen-lockfile
pnpm dev
```

L’interface est disponible sur `http://localhost:5173`. L’URL API est configurée explicitement depuis **Connexion API** et, par défaut, vaut `http://localhost:8000` en développement. En production, une page HTTPS ne peut utiliser qu’une API HTTPS.

Le Bearer token est conservé uniquement en mémoire JavaScript. Le renouvellement utilise le cookie HttpOnly de session et le jeton CSRF associé ; aucun token d’accès n’est écrit dans `localStorage` ou `sessionStorage`.

## Contrat consommé

| Opération | Route | Usage dans le cockpit |
|---|---|---|
| Liste | `GET /api/v1/cases/assigned` | Cartes des affaires visibles par le patron. |
| Lecture | `GET /api/v1/patron/cases/{case_id}/financial-reports/{report_id}/draft` | Snapshot DRAFT, révision, totaux et lignes. |
| Écriture | `POST /api/v1/patron/cases/{case_id}/financial-reports/{report_id}/lines` | Ajout d’une ligne avec `expected_revision`. |

Les receipts de commande ne sont pas utilisés pour afficher des montants : ils restent fermés et minimaux, conformément au contrat backend.

## Validation

```bash
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

Les contrôles TypeScript strict, ESLint, tests Vitest et build sont également exécutés par le workflow CI à chaque Pull Request.
