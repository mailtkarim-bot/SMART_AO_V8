# SMART_AO V8 — CASE-DCE-READ-01-C : contrat HTTP de lecture DCE par affaire

**Statut :** normatif.  
**Dépendances :** CASE-DCE-READ-01-A, CASE-DCE-READ-01-B, SEC-01.  
**Périmètre :** transport HTTP de la projection fermée ; aucune nouvelle persistance, aucun téléchargement ni interface React.

## 1. Endpoint

```http
GET /api/v1/cases/{case_id}/dce-reading
Authorization: Bearer <access-token>
```

Le chemin porte une `Case`, jamais une DCE libre. Le corps est absent. Le serveur résout l’identité, la session, la membership, la Case propriétaire, le tenant et la DCE applicable ; aucun de ces faits ne provient d’un query parameter, d’un header de confiance ou du navigateur.

## 2. Ordre obligatoire des contrôles

1. Vérifier le bearer et reconstruire l’`ActorContext` réel ; tout échec retourne `401 UNAUTHENTICATED`.
2. Relire le tenant propriétaire de la Case par son identifiant seulement. Si la Case est inconnue, retourner `404 NOT_FOUND_OR_FORBIDDEN`.
3. Construire une ressource `CASE_DCE_READING` avec `case_id`, tenant propriétaire et classification `INTERNAL_OPERATIONAL`.
4. Évaluer `case.dce.read` via `AuditedAuthorizationPolicy` avant de demander la projection fermée. Un refus est audité par SEC-01.
5. Appeler exclusivement `CaseDceReadingReader.get(tenant_id=context.tenant_id, case_id=case_id)`.
6. Si la query ne retrouve plus la Case, retourner `404 NOT_FOUND_OR_FORBIDDEN` ; si elle ne possède pas de DCE applicable ou si la référence est incohérente, retourner `422 COMMAND_REJECTED`.
7. Sérialiser seulement le DTO fermé de la projection `AVAILABLE`.

Cette séquence interdit à un collaborateur de choisir une DCE d’un autre dossier, empêche le chargement de données DCE avant l’autorisation et conserve un refus tenant neutre.

## 3. Matrice de policy

| Acteur | Conditions | Résultat |
|---|---|---|
| `PATRON_ADMIN` actif | Capability `case.dce.read`; Case du même tenant. | `200` avec DTO fermé. |
| `COLLABORATEUR` actif et affecté | Capability ; Case dans son scope actif ; action `case.dce.read` et classification `INTERNAL_OPERATIONAL` dans l’affectation. | `200` avec le même DTO fermé. |
| Collaborateur sans affectation ou scope incomplet | Policy SEC-01 refusante auditée. | `403 FORBIDDEN`. |
| Ressource d’un autre tenant | Policy tenant auditée. | `404 NOT_FOUND_OR_FORBIDDEN`. |
| Case inconnue | Aucun propriétaire fiable à auditer. | `404 NOT_FOUND_OR_FORBIDDEN`. |
| `SYSTEM`, support, partenaire | Aucun transport humain autorisé. | Refus selon policy. |

## 4. Réponse `200` fermée

```json
{
  "case_id": "UUID",
  "work_label": "Réhabilitation école — Gros œuvre",
  "case_lifecycle": "ACTIVE",
  "commercial_stage": "ANALYSIS",
  "dce_freshness": "CURRENT",
  "availability": "AVAILABLE",
  "dce": {
    "dce_version_id": "UUID",
    "lifecycle": "ADMITTED",
    "integrity": "VERIFIED",
    "classification_readiness": "CLASSIFIED",
    "analysis_readiness": "READY_FOR_ANALYSIS",
    "source_received_at": "2026-08-14T12:00:00Z"
  },
  "counters": {
    "total": 3,
    "pending_human_confirmation": 2,
    "confirmed": 1,
    "review_required": 0,
    "not_applicable": 0
  },
  "requirements": [
    {
      "requirement_id": "UUID",
      "requirement_type": "CANDIDATURE_DOCUMENT",
      "directive_signal": "REQUIRED_SIGNAL",
      "confirmation_outcome": "PENDING_HUMAN_CONFIRMATION",
      "uncertainty_status": "SOURCE_SIGNAL_ONLY",
      "document_family": "RC",
      "source_locator_label": "RC · page 8"
    }
  ]
}
```

Les modèles Pydantic utilisent `extra="forbid"`. Les champs de documents, stockage, hash, contenu, provenance privée, audit, auteur, prix, marge, budget, devis, trésorerie, score, Go/No-Go, dépôt et décision patron n’existent dans aucun DTO de cette route.

## 5. Réponses publiques

| Situation | HTTP | Corps public |
|---|---:|---|
| Projection disponible et policy autorisée | `200` | DTO fermé §4. |
| Bearer absent, invalide ou session révoquée | `401` | `UNAUTHENTICATED`. |
| Capability, affectation, action ou classification refusée | `403` | `FORBIDDEN`. |
| Case inconnue, hors tenant ou disparue après policy | `404` | `NOT_FOUND_OR_FORBIDDEN`. |
| Case sans DCE applicable ou référence DCE incohérente | `422` | `COMMAND_REJECTED`. |

Aucun détail interne de rôle, scope, affectation, tenant, DCE concurrente ou état de persistance n’est retourné dans les erreurs.

## 6. Critères de sortie

Les tests API doivent prouver : bearer obligatoire ; patron autorisé ; collaborateur avec affectation et scope `case.dce.read` autorisé ; collaborateur sans affectation refusé et audité ; scope sans action refusé ; autre tenant masqué par `404` et audité ; Case sans DCE à `422` ; réponse `200` sans clés interdites ni contenu source ; et route non enregistrée lorsqu’aucun runtime d’authentification réel n’est composé.

## 7. Non-objectifs

Le slice C ne télécharge pas de document, ne rend pas de PDF, ne modifie pas de confirmation, ne crée pas de tâche, ne calcule pas de délai, n’ouvre pas le wizard React, ne détermine pas la conformité, le prix, le Go/No-Go ou le dépôt.
