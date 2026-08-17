# SMART_AO V8 — ENTERPRISE-LIBRARY-HTTP-01

## Surface patronale

Cette frontière expose la première bibliothèque entreprise par HTTP, derrière la résolution Bearer et la policy `enterprise.library.read/write`.

| Méthode | Route | Usage |
|---|---|---|
| `POST` | `/api/v1/patron/enterprise/company` | Créer la fiche société unique du tenant. L’identifiant est généré côté serveur de façon déterministe à partir du `command_id`. |
| `POST` | `/api/v1/patron/enterprise/companies/{company_id}/documents` | Enregistrer une pièce `INSURANCE`, `KBIS` ou `RIB` avec `expected_revision`. L’identifiant documentaire est généré côté serveur. |
| `GET` | `/api/v1/patron/enterprise/company` | Lire la projection patronale de la société et des documents enregistrés. |

## Sécurité et réponses

Toutes les routes exigent un Bearer actif. Les routes sont réservées au `PATRON_ADMIN`; un collaborateur reçoit `403 FORBIDDEN` sans résolution de la bibliothèque. Une société absente ou hors tenant est rendue indistinguable par `404 NOT_FOUND_OR_FORBIDDEN`.

Les écritures renvoient un receipt fermé avec `command_id`, `idempotency_key`, `result_code`, références d’agrégat, identifiants d’événements et indicateur de rejeu. Une première écriture renvoie `201`; un rejeu idempotent renvoie `200`; une révision obsolète renvoie `409 VERSION_CONFLICT`; un payload avec champ serveur interdit ou une valeur invalide renvoie `422`.

La réponse de lecture contient l’identité légale, l’adresse, la révision, le type et le statut de vérification des documents. Elle n’expose jamais `storage_object_id`, `original_filename`, `sha256`, `command_id`, `idempotency_key`, le contenu du document, l’IBAN ou une donnée bancaire.

## Tests

Le harnais PostgreSQL `backend/tests/api/test_enterprise_library_api.py` couvre le parcours patron création → trois documents → lecture, le rejeu idempotent, le rejet de champ `tenant_id`, le conflit de révision et le refus collaborateur.
