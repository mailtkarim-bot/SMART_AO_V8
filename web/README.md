# Cockpit patron SMART_AO V8

Le frontend fournit le premier incrément du **cockpit patron** : lecture des affaires assignées, chargement d’un snapshot financier `DRAFT`, affichage de la synthèse et des lignes, puis ajout contrôlé d’une ligne avec la révision courante.

Le cockpit ne contient aucune logique d’autorisation métier. Il transmet le Bearer token à l’API FastAPI, qui reste seule responsable de l’identité, du tenant, de la capability et de la policy financière.

## Démarrage local

Depuis ce répertoire :

```bash
pnpm install --frozen-lockfile
pnpm dev
```

L’interface est disponible sur `http://localhost:5173`. Le proxy Vite redirige `/api` vers `http://localhost:8000` en développement. Une URL API différente peut être renseignée depuis **Connexion API**.

Le Bearer token est conservé uniquement dans le stockage local du navigateur pour permettre la démonstration locale. Il n’est envoyé qu’à l’URL API configurée et ne doit pas être utilisé comme mécanisme de stockage de session définitif en production.

## Contrat consommé

| Opération | Route | Usage dans le cockpit |
|---|---|---|
| Liste | `GET /api/v1/cases/assigned` | Cartes des affaires visibles par le patron. |
| Lecture | `GET /api/v1/patron/cases/{case_id}/financial-reports/{report_id}/draft` | Snapshot DRAFT, révision, totaux et lignes. |
| Écriture | `POST /api/v1/patron/cases/{case_id}/financial-reports/{report_id}/lines` | Ajout d’une ligne avec `expected_revision`. |

Les receipts de commande ne sont pas utilisés pour afficher des montants : ils restent fermés et minimaux, conformément au contrat backend.

## Validation

```bash
pnpm build
```

Le build TypeScript strict est également exécuté par le workflow CI à chaque Pull Request.
