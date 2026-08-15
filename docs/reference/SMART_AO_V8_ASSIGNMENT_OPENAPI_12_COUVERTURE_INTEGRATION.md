# SMART_AO V8 — Couverture d’intégration des 12 opérations Assignment/OpenAPI

**Périmètre de référence :** snapshot OpenAPI à douze opérations, publié par `PATRON-ASSIGNMENT-INTERACTIONS-READ-01`, avant l’ajout de `POST /interaction-validations`.

## Synthèse d’exécution

Le harnais `backend/tests/api/test_assignment_interactions_api.py` couvre les douze opérations par un runtime FastAPI réel, un bearer JWT résolu côté serveur, PostgreSQL et les policies SEC-01. La vérification ciblée précédente du harnais a produit **30 tests verts**. Cette couverture est fonctionnelle et de sécurité ; elle n’est pas une métrique de lignes de code.

| Groupe | Opérations | Couverture d’intégration |
|---|---:|---|
| Commandes collaborateur | 3 | Exécution, rejeu, refus de scope, idempotence et tenant neutre. |
| Lecture collaborateur | 1 | Liste vide, fusion des trois sources, borne, refus et non-fuite. |
| Commandes patron | 5 | Création, amendement, suspension, réactivation, fin, motifs fermés et receipts. |
| Lectures cockpit patron | 3 | Liste, journal d’autorité, interactions, filtres, bornes, rôles et neutralité. |
| **Total** | **12** | **12/12 opérations disposant d’au moins un scénario d’intégration direct.** |

## Matrice route par route

| # | Opération OpenAPI | Scénarios d’intégration principaux | Codes validés | Confidentialité et ReBAC |
|---:|---|---|---|---|
| 1 | `POST /api/v1/assignments/{assignment_id}/acknowledgement` | `test_assignment_acknowledgement_returns_closed_receipt_and_replays` | `201`, `200` | Receipt fermé, affectation résolue côté serveur. |
| 2 | `POST /api/v1/assignments/{assignment_id}/clarification-requests` | `test_other_assignment_routes_dispatch_their_closed_command` (paramétré) | `201` | Scope collaborateur requis ; texte libre absent des lectures. |
| 3 | `POST /api/v1/assignments/{assignment_id}/unavailability-reports` | `test_other_assignment_routes_dispatch_their_closed_command` (paramétré) | `201` | Motif fermé ; détails libres exclus des projections. |
| 4 | `GET /api/v1/assignments/{assignment_id}/history` | `test_assignment_history_returns_closed_empty_then_bounded_history` | `200` | Fusion bornée, projection fermée des trois sources. |
| 5 | `POST /api/v1/patron/cases/{case_id}/assignments` | `test_patron_assignment_creation_and_scope_amendment_return_closed_receipts` | `201`, `200` | `PATRON_ADMIN`, `assignment.manage`, receipt sans scope sensible. |
| 6 | `POST /api/v1/patron/assignments/{assignment_id}/scope-amendments` | `test_patron_assignment_creation_and_scope_amendment_return_closed_receipts` | `201` | Scope fermé et exclusion des actions financières. |
| 7 | `POST /api/v1/patron/assignments/{assignment_id}/suspensions` | `test_patron_assignment_suspension_returns_closed_receipt_and_replays` | `201`, `200`, `422` | Motif fermé, journal append-only et receipt sans motif. |
| 8 | `POST /api/v1/patron/assignments/{assignment_id}/reactivations` | `test_patron_assignment_reactivation_returns_closed_receipt_and_replays` | `201`, `200`, `422` | Fenêtre, Case et cible revalidées côté serveur. |
| 9 | `POST /api/v1/patron/assignments/{assignment_id}/end` | `test_patron_assignment_end_returns_closed_receipt_and_replays` | `201`, `200`, `409`, `422` | Fin irréversible, motif conservé hors receipt. |
| 10 | `GET /api/v1/patron/assignments` | `test_patron_assignment_cockpit_lists_filtered_assignments_and_closed_journal` | `200`, `401`, `403`, `422` | Liste tenant-scopée, filtre fermé, aucune identité cible ni finance. |
| 11 | `GET /api/v1/patron/assignments/{assignment_id}/journal` | `test_patron_assignment_cockpit_lists_filtered_assignments_and_closed_journal` | `200`, `403`, `404`, `422` | Journal d’autorité fermé, ordre déterministe et neutralité inter-tenant. |
| 12 | `GET /api/v1/patron/assignments/{assignment_id}/interactions` | `test_patron_reads_closed_collaborator_interactions_with_kind_filter` | `200`, `401`, `403`, `404`, `422` | Signaux structurés uniquement ; note, question, raison, auteur et finance exclus. |

## Garanties transverses attestées

Les tests `test_assignment_scope_denial_is_403_and_audited`, `test_assignment_foreign_or_missing_is_neutral_404_and_audited`, `test_assignment_idempotency_key_reuse_with_different_payload_is_409` et leurs homologues patron prouvent les comportements transverses : bearer absent `401`, refus de capability/scope `403` audité, tenant étranger masqué par `404 NOT_FOUND_OR_FORBIDDEN`, et idempotence divergente `409`.

Le rapport ne prétend pas couvrir l’intégralité des futures frontières financières, de réponse patron à une clarification ou de notification. Ces comportements restent hors des douze opérations référencées et devront recevoir un contrat, une route, des tests propres et un ajout explicite à l’OpenAPI.

## Reproduction

```bash
cd /home/ubuntu/smart_ao_v8
uv run pytest backend/tests/api/test_assignment_interactions_api.py -q
uv run python scripts/export_assignment_openapi.py
```

La prochaine opération `POST /api/v1/patron/assignments/{assignment_id}/interaction-validations` est volontairement exclue de ce rapport de base 12 ; elle fera l’objet d’un rapport mis à jour à treize opérations après publication.
