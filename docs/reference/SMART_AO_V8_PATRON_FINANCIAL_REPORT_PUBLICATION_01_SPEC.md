# SMART_AO V8 — PATRON-FINANCIAL-REPORT-PUBLICATION-01 — Spécification technique

**Statut : PRÉPARATOIRE — aucune route d’écriture financière n’est encore exposée.**

## Finalité

Cette frontière sépare strictement le calcul d’un rapport de son acte de publication. Le patron peut rendre lisible un snapshot `DRAFT` déjà calculé et immuable ; il ne peut ni modifier les montants, ni recalculer, ni ajouter une ligne, ni prendre automatiquement une décision Go/No-Go ou de prix.

## Commande et route cibles

```text
POST /api/v1/patron/cases/{case_id}/financial-reports/{report_id}/publications
```

| Champ de commande | Règle |
|---|---|
| `command_id` | UUID idempotent, unique dans le tenant. |
| `idempotency_key` | UUID ; rejeu strict retourne le receipt antérieur. |
| `correlation_id` | UUID optionnel, jamais rendu dans le receipt. |
| `expected_revision` | Révision du snapshot à contrôler avant verrouillage. |

La commande `PublishFinancialReportCommand` verrouille le snapshot `FOR UPDATE`, exige `state=DRAFT`, vérifie l’affaire tenant-scopée et l’égalité de révision, puis crée un acte `financial_report_publications` append-only. Le snapshot devient `PUBLISHED`, reçoit `published_at` côté serveur et sa révision augmente de un. Aucun montant ne transite dans la commande, l’événement, le receipt ou l’audit.

## Sécurité et confidentialité

| Sujet | Règle |
|---|---|
| Acteur | `PATRON_ADMIN` actif seulement ; acteur système interdit. |
| Capability | `financial.report.publish`, catalogue fermé, distinct de `financial.report.read`. |
| Ressource | `CASE_FINANCIAL_REPORT`, classification `FINANCIAL_PRIVATE`, tenant-scopée. |
| Échecs | `401`, `403`, `404 NOT_FOUND_OR_FORBIDDEN`, `409 VERSION_CONFLICT`, `422 COMMAND_REJECTED`. |
| Audit | Autorisation/refus SEC-01 sans montant, libellé, source, hash ou règle de calcul. |
| Receipt | `FINANCIAL_REPORT_PUBLISHED`, références agrégat et événements seulement. |

## Migration attendue

La migration suivante devra ajouter la révision au snapshot si absente, créer `financial_report_publications` avec clés étrangères tenant/snapshot/patron, unicité tenant/snapshot et trigger anti-`UPDATE`/`DELETE`. La publication est définitive dans ce slice : il n’existe ni dépublication ni correction en place. Une correction ultérieure crée un nouveau snapshot et une frontière dédiée.

## Tests requis

Les tests PostgreSQL/API devront couvrir : publication réussie, rejeu `200`, double publication `422`, révision obsolète `409`, patron autorisé, collaborateur `403`, tenant étranger `404`, audit de refus, journal immuable et non-fuite de montants dans le receipt ou les logs HTTP.
