# SMART_AO V8 — DCE-READ-01 : Contrat de lecture sécurisée de DceVersion

**Statut :** normatif pour le premier endpoint DCE HTTP.  
**Périmètre :** lecture des métadonnées de version DCE ; aucune admission, aucun upload, aucun téléchargement et aucun contenu documentaire.

## 1. Objectif

L’endpoint `GET /api/v1/dce-versions/{dce_version_id}` permet à un utilisateur autorisé de vérifier l’état durable d’une version de DCE rattachée à une consultation. Il fournit les informations nécessaires au pilotage du dossier — intégrité, cycle de vie et disponibilité d’analyse — sans exposer les documents originaux, leurs extraits, leur emplacement de stockage ou les pièces administratives éventuelles.

> Cette route ne constitue ni un navigateur de documents, ni une API d’ingestion, ni une API d’analyse. Les commandes d’admission, retrait, supersession et la restitution documentaire exigent des contrats et handlers distincts.

## 2. Préconditions de sécurité

| Contrôle | Règle obligatoire |
|---|---|
| Authentification | Bearer JWT vérifié, puis session, identité et membership relues côté serveur. |
| Capability | `dce.prepare` est requise. |
| Tenant | Le tenant propriétaire de la version est résolu côté serveur avant la policy. Une version absente ou hors tenant retourne uniquement `404 NOT_FOUND_OR_FORBIDDEN`. |
| Classification | La représentation est classée `PUBLIC_TENDER`. Aucun contenu de document n’est inclus. |
| Collaborateur | La route n’est pas liée à une `Case` ; un collaborateur ne reçoit donc pas cet accès global à une version DCE dans ce premier sous-slice. L’accès DCE collaborateur sera ouvert uniquement via une future route rattachée à une affaire et à son `case_assignment`. |
| Audit | Tout refus de policy est écrit par le décorateur d’audit append-only, avec références pseudonymes seulement. |

## 3. Réponse autorisée

La réponse HTTP ne peut exposer que les champs suivants.

| Champ | Signification | Justification |
|---|---|---|
| `id` | Identifiant de la version DCE | Référence stable de navigation. |
| `consultation_id` | Consultation parente | Permet le rattachement au dossier d’appel d’offres. |
| `predecessor_dce_version_id` | Version immédiatement antérieure | Rend visible la chaîne de rectificatifs sans effacer l’historique. |
| `source_received_at` | Date de réception de la source | Indicateur de fraîcheur métier. |
| `lifecycle` | `ADMITTED`, `SUPERSEDED` ou `WITHDRAWN` | État durable de la version. |
| `integrity` | `VERIFIED`, `PARTIAL` ou `UNUSABLE` | Qualité d’admission du corpus. |
| `classification_readiness` | État de classification | Pilotage de préparation. |
| `analysis_readiness` | État de disponibilité d’analyse | Pilotage de l’étape suivante. |
| `aggregate_revision` | Révision optimiste | Référence de cohérence pour les futures commandes. |

## 4. Données explicitement interdites

La route ne sérialise jamais `storage_key`, `storage_object_id`, `original_filename`, `media_type`, `sha256`, `corpus_hash`, `provenance_url`, `provenance_reference`, extrait, localisation source, classification documentaire, anomalie documentaire, déclaration de document manquant, motif de retrait ou contenu de pièce DCE.

## 5. Réponses

| Situation | HTTP | Corps public |
|---|---:|---|
| Lecture autorisée | `200` | Métadonnées strictement listées à la section 3. |
| Bearer absent ou invalide | `401` | `UNAUTHENTICATED`. |
| Capability ou policy refusée | `403` ou `404` | Code public de la policy ; aucune règle interne n’est révélée. |
| Version absente ou hors tenant | `404` | `NOT_FOUND_OR_FORBIDDEN`. |

## 6. Critères de sortie

Les tests doivent prouver le bearer obligatoire, la lecture patron autorisée, l’absence de champ documentaire interdit, le refus collaborateur sans scope Case, le refus inter-tenant neutre et l’événement d’audit correspondant.
