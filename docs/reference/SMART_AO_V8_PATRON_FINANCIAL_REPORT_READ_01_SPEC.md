# SMART_AO V8 — PATRON-FINANCIAL-REPORT-READ-01 — Spécification technique préparatoire

**Statut : PRÉPARATOIRE — aucune route financière n’est exposée ni implémentée.**

## 1. Objet et décision de séquencement

Le prochain cockpit financier doit permettre au patron de consulter un **rapport financier figé**, rattaché à une affaire, et non un tableur brut, une formule mutable ou le fichier de prix importé d’un collaborateur. À ce stade du dépôt V8, aucun agrégat de prix, de chiffrage, de marge, de DPGF, de BPU, de DQE, de devis ou de trésorerie n’existe dans le backend. Il serait donc techniquement faux et métierement dangereux d’exposer une route financière dès maintenant.

La route décrite ci-dessous est une cible contractuelle. Son implémentation est bloquée jusqu’à la création préalable de `FINANCIAL-REPORT-FOUNDATION-01`, qui devra matérialiser des snapshots patron immuables et leurs sources de calcul vérifiables.

> Aucun collaborateur ne doit pouvoir inférer un prix, une marge, un total, un coefficient, une hypothèse de chiffrage ou l’existence d’un rapport financier à partir d’une réponse, d’un code d’erreur, d’un journal ou d’un cache.

## 2. Route cible réservée

```text
GET /api/v1/patron/cases/{case_id}/financial-reports/{report_id}
```

| Élément | Règle prévue |
|---|---|
| Acteur | `PATRON_ADMIN` uniquement, membership active. Aucun collaborateur, délégué, partenaire, support ou système. |
| Capability future | `financial.report.read`, catalogue fermé distinct de `assignment.manage`. |
| Ressource policy | `CASE_FINANCIAL_REPORT`, tenant-scopée, `case_id` résolu depuis le rapport. |
| Méthode | Lecture seule ; pas de calcul, mutation, outbox, receipt ou rafraîchissement à la demande. |
| Paramètres | UUID `case_id` et UUID `report_id` de chemin. Aucun filtre de montant, date, client, fournisseur ou version n’est accepté avant une liste distincte. |
| Codes publics | `200`, `401`, `403`, `404 NOT_FOUND_OR_FORBIDDEN`, `422`. Aucune réponse partielle. |

La vérification s’effectue dans cet ordre : bearer, rôle/capability, rapport tenant-scopé, concordance `report.case_id == case_id`, policy. Une affaire ou un rapport d’un autre tenant reste indiscernable d’une absence par `404 NOT_FOUND_OR_FORBIDDEN`.

## 3. Agrégats et persistance préalables obligatoires

`FINANCIAL-REPORT-FOUNDATION-01` devra produire un agrégat patron `FinancialReportSnapshot`, append-only, avant toute lecture HTTP. Un rapport ne pourra être exposé que s’il est complet, calculé selon un profil de règles versionné et validé par un acte patron explicite ultérieur.

| Table/registre futur | Responsabilité minimale | Invariant non négociable |
|---|---|---|
| `financial_report_snapshots` | En-tête immuable : tenant, affaire, `report_id`, statut, devise, horodatage, version des règles et empreinte de calcul. | Un snapshot publié n’est jamais modifié ni supprimé. |
| `financial_report_lines` | Lignes financières atomiques appartenant à un seul snapshot : famille, libellé normalisé, quantité, unité, montant monétaire minoré. | Aucune ligne n’existe hors snapshot ; les montants sont stockés en unité mineure entière, jamais en flottant. |
| `financial_report_source_refs` | Références vers les données de prix, bordereaux ou hypothèses versionnées utilisées pour le calcul. | La route de lecture n’expose ni chemin de stockage, ni hash complet, ni fichier source. |
| `financial_report_publications` | Acte patron séparé qui rend un snapshot consultable dans le cockpit. | Le calcul et la publication restent deux faits distincts. |

Les montants doivent être représentés par une paire `amount_minor: int` et `currency_code: CHAR(3)`, avec devise explicite, règles d’arrondi versionnées et interdiction de `float`. Les sources Excel, documents DCE et devis ne deviennent jamais accessibles par transit via cette route.

## 4. Schéma Pydantic cible fermé

Les noms suivants décrivent la future réponse, non un modèle déjà exposé. Tout champ absent de cette table est interdit par `extra="forbid"`.

| DTO cible | Champs autorisés | Exclusions |
|---|---|---|
| `PatronFinancialReportResponse` | `report_id`, `case_id`, `status`, `currency_code`, `calculated_at`, `ruleset_version`, `summary`, `lines`. | Tenant, auteur, membership, commande, corrélation, audit, chemin source, hash, fichier, marge cible secrète ou métadonnée de stockage. |
| `FinancialReportSummaryResponse` | Totaux strictement issus du snapshot : `sales_total_minor`, `direct_cost_total_minor`, `overhead_total_minor`, `subcontracting_total_minor`, `contingency_total_minor`, `gross_margin_minor`, `gross_margin_rate_bps`, `forecast_cashflow_minor`. | Formules brutes, coefficients internes non validés, détail RH, trésorerie bancaire, prix d’achat fournisseur non autorisé. |
| `FinancialReportLineResponse` | `line_id`, `category`, `label`, `quantity_decimal`, `unit`, `amount_minor`, `currency_code`, `source_status`. | Chemin du fichier Excel, cellules, formules, identifiant fournisseur, note libre ou référence de stockage. |

La visibilité de chaque catégorie de ligne fera partie du snapshot et non d’une logique d’interface. Une version future pourra créer des niveaux d’exposition patron séparés, mais ils ne doivent pas être inférés à partir du rôle collaborateur.

## 5. Menaces, audit et observabilité

La lecture financière est une ressource `CONFIDENTIAL_FINANCIAL`, jamais `INTERNAL_OPERATIONAL`. Toute autorisation ou tout refus doit être journalisé par SEC-01 sans montants, titres de lignes, IDs de source, hash ou contenu financier dans les métadonnées d’audit. Les logs applicatifs, traces, métriques, erreurs de sérialisation et cache partagé doivent redacter les réponses financières.

| Menace | Contrôle prévu |
|---|---|
| Collaborateur qui appelle directement l’URL patron | `403` auditée ; aucune présence de rapport révélée. |
| UUID d’un autre tenant | `404 NOT_FOUND_OR_FORBIDDEN`, lookup tenant-scopé. |
| Snapshot incomplet ou non publié | `404 NOT_FOUND_OR_FORBIDDEN`, pas de réponse partielle. |
| Arrondi ou recalcul divergent | Snapshot immuable, montants mineurs, `ruleset_version` et empreinte calculée. |
| Fuite dans logs/cache | Réponses `Cache-Control: no-store`, redaction de logs, aucun objet source dans le DTO. |
| Détournement vers une décision automatique | La route est en lecture seule ; aucune recommandation Go/No-Go, prix cible ou dépôt. |

## 6. Plan de réalisation avant exposition HTTP

| Étape | Livrable requis | Critère de sortie |
|---:|---|---|
| 1 | Contrat `FINANCIAL-REPORT-FOUNDATION-01` et matrice de classification des champs. | Le patron valide exactement les données exposables et exclues. |
| 2 | Modèles SQLAlchemy, migration additive, triggers append-only et index tenant/Case/snapshot. | Upgrade/check/downgrade verts ; aucun montant flottant. |
| 3 | Handler de matérialisation contrôlé, règles versionnées et preuves de source. | Calcul reproductible sans route publique. |
| 4 | Acte patron de publication du snapshot. | Un snapshot incomplet ou non publié est illisible. |
| 5 | Reader tenant-scopé et projection Pydantic fermée. | Aucun champ interdit dans le JSON ou l’OpenAPI. |
| 6 | Route cible, tests d’intégration, audit SEC-01, export OpenAPI. | `200/401/403/404/422`, tenant, redaction et non-cache validés. |

Cette spécification ne crée aucune dette d’exposition : tant que les étapes 1 à 4 ne sont pas figées et testées, le cockpit patron continuera de ne présenter aucun rapport financier réel ou simulé.
