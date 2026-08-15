# SMART_AO V8 — FINANCIAL-REPORT-FOUNDATION-01 — Contrat normatif

**Statut : FIGÉ avant code.**

## Frontière

Cette frontière crée un snapshot financier patron immuable et sa lecture fermée. Elle ne calcule pas un prix automatiquement, ne prend aucune décision Go/No-Go et ne rend jamais les données financières accessibles à un collaborateur.

## Persistance minimale

| Registre | Champs essentiels | Invariant |
|---|---|---|
| `financial_report_snapshots` | tenant, affaire, rapport, statut `PUBLISHED`, devise, règles, date de calcul, totaux mineurs | Snapshot immuable, un rapport publié seulement. |
| `financial_report_lines` | rapport, ligne, catégorie fermée, libellé, quantité décimale, unité, montant mineur | Une ligne appartient à un snapshot ; aucun flottant. |

Les catégories fermées initiales sont `SALES`, `DIRECT_COST`, `OVERHEAD`, `SUBCONTRACTING`, `CONTINGENCY`, `GROSS_MARGIN` et `FORECAST_CASHFLOW`. Elles couvrent le chiffre d’affaires, les coûts directs, frais généraux, sous-traitance, provision d’aléas, marge brute et trésorerie prévisionnelle. Tous les montants sont des entiers signés en unités mineures ; aucune colonne monétaire n’accepte un flottant.

La fondation ne crée ni import Excel, ni source fournisseur, ni publication automatisée. Les données de test sont insérées uniquement par le harnais PostgreSQL, jamais par une route métier.

## Route cible

```text
GET /api/v1/patron/cases/{case_id}/financial-reports/{report_id}
```

Le bearer réel doit correspondre à une membership `PATRON_ADMIN` active avec la capability fermée `financial.report.read`. Un collaborateur ou un délégué reçoit `403`; une affaire ou un rapport absent/hors tenant reçoit `404 NOT_FOUND_OR_FORBIDDEN`. La réponse porte `Cache-Control: no-store`.

## Projection fermée

La réponse expose exclusivement `report_id`, `case_id`, `status`, `currency_code`, `calculated_at`, `ruleset_version`, les totaux mineurs et les lignes autorisées. Elle exclut tenant, auteur, membership, commande, audit, stockage, hash, fichier source, formules, références fournisseur, notes et données bancaires.

## Validation

Le slice exige une migration additive, triggers anti-`UPDATE`/`DELETE`, lecture tenant-scopée, audit sans montant, tests `200/401/403/404/422`, cache interdit, redaction et OpenAPI actualisée. Toute évolution de prix ou tout calcul devient une frontière séparée.
