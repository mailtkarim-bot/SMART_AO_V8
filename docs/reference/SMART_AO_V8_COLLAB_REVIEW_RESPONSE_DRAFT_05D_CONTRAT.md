# SMART_AO V8 — COLLAB-REVIEW-01 / RESPONSE-DRAFT-01

## 1. Objet et frontière

Ce slice ajoute une revue humaine versionnée d’un document technique généré et un brouillon de réponse technique non financier. Il ne valide ni conformité DCE, ni engagement commercial, ni prix, ni marge, ni trésorerie, ni décision Go/No-Go, ni dépôt.

> Une correction ne modifie jamais la cible relue. Elle crée un enregistrement append-only rattaché à la révision précise de la revue ; un nouveau document ou un nouveau brouillon constitue une nouvelle version.

## 2. Commandes fermées

| Commande | Autorité | Effet |
|---|---|---|
| `RequestPreparationReview` | Collaborateur affecté avec `preparation.review.request` | Crée la révision `REQUESTED` d’une revue sur une version immuable de document technique. |
| `DecidePreparationReview` | `PATRON_ADMIN` avec `preparation.review.decide` | Ajoute `ACCEPTED`, `RETURNED_WITH_CORRECTIONS` ou `REJECTED`, sans mutation de la cible. |
| `AddPreparationCorrection` | `PATRON_ADMIN` avec `preparation.review.decide` | Ajoute une correction ciblée à une révision retournée. |
| `CreateTechnicalResponseDraft` | Collaborateur affecté avec `preparation.document.write` | Crée une version `DRAFT` à partir d’un document technique et de références internes bornées. |

Le serveur résout tenant, acteur, membership, Case, affectation, package, document et version. Le client ne peut pas fournir de tenant, rôle, capability ou propriétaire de confiance. Les routes sont `POST /api/v1/preparation/{package_id}/reviews`, `POST /api/v1/preparation/{package_id}/reviews/{review_id}/decision`, `POST /api/v1/preparation/{package_id}/reviews/{review_id}/corrections` et `POST /api/v1/preparation/{package_id}/response-drafts`. Elles retournent seulement un receipt fermé `201` ou `200` en rejeu.

## 3. Transitions et versionnement

Une revue commence par `REQUESTED`. Une décision patronale crée une nouvelle révision : `ACCEPTED`, `RETURNED_WITH_CORRECTIONS` ou `REJECTED`. Une correction n’est admise que sur une revue `RETURNED_WITH_CORRECTIONS` et est numérotée indépendamment. Une revue terminée ne peut pas être écrasée ; une nouvelle demande crée un nouveau `review_id`.

Un brouillon possède un `draft_id` stable et une version monotone. Il porte seulement des codes de sections fermés (`COVER`, `UNDERSTANDING`, `METHOD`, `RESOURCES`, `SCHEDULE`, `RISKS`, `SOURCES`), des UUID de sources internes, un rôle responsable collaborateur et un contenu stocké dans le storage privé. Le locator et le hash ne sont jamais renvoyés par un contrat collaborateur.

## 4. Sécurité et non-fuite

Toute écriture porte `command_id`, `idempotency_key`, `correlation_id` et une révision attendue lorsque la racine mutable est concernée. Le dispatcher fournit le rejeu idempotent et l’outbox transactionnelle. Une révision obsolète produit `VERSION_CONFLICT`.

L’accès collaborateur exige une affectation active et une classification `INTERNAL_OPERATIONAL`. La décision et la correction exigent le rôle patron `PATRON_ADMIN`. Les contrats Pydantic sont `extra=forbid` et refusent les termes financiers dans les notes et instructions. Les événements et receipts ne transportent ni texte de correction, ni contenu documentaire, ni storage key, ni hash, ni données financières.

Les tables `preparation_reviews`, `preparation_review_corrections` et `technical_response_drafts` sont append-only par trigger PostgreSQL. Les corrections référencent la paire tenant/review/révision exacte ; aucune modification ou suppression physique n’est autorisée.

## 5. Critères de fermeture

Les tests PostgreSQL couvrent demande, rejeu, refus d’autorité, décision, conflit de révision, retour avec correction, acceptation, append-only, outbox/événements, création de brouillon versionné et payload financier interdit. Le cycle Alembic `upgrade head/check/downgrade base`, Ruff, detect-secrets, suite backend complète et CI doivent être verts avant publication.
