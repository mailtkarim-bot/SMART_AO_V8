# SMART_AO V8 — CASE-DCE-READ-01-B : contrat de query applicative fermée

**Statut :** normatif.  
**Dépendances :** CASE-DCE-READ-01, SEC-01, Case, DCE-REQUIREMENTS-01 et DCE-REQUIREMENTS-CONFIRMATION-01.  
**Périmètre :** projection de lecture applicative tenant-scopée ; aucune route HTTP, aucune sérialisation Pydantic publique et aucune interface React.

## 1. But

Cette query construit la vue de lecture DCE d’une **Case unique**. Elle relit l’affaire et sa DCE applicable depuis PostgreSQL avec le `tenant_id` de confiance. Elle ne charge jamais une DCE choisie par un identifiant provenant du navigateur.

Elle permet au futur transport HTTP de distinguer trois situations sans inventer de données : affaire introuvable dans le tenant, affaire connue sans DCE applicable, affaire connue avec une projection DCE disponible.

> Cette query ne prend aucune décision d’autorisation. Le transport résout d’abord l’`ActorContext`, puis applique `case.dce.read` et la policy SEC-01 sur la Case résolue avant toute sérialisation. La query garantit le périmètre tenant et la fermeture du modèle ; elle ne remplace jamais la policy ReBAC.

## 2. Entrée et résultat fermés

```text
GetCaseDceReading(tenant_id, case_id) -> CaseDceReadingLookup | None
```

| Résultat | Signification | Consommateur HTTP futur |
|---|---|---|
| `None` | La Case est absente ou hors tenant. | `404 NOT_FOUND_OR_FORBIDDEN`. |
| `NO_APPLICABLE_DCE` | La Case est trouvée mais ne désigne aucune DCE applicable. | `422 COMMAND_REJECTED`. |
| `AVAILABLE` | La Case et la DCE applicable sont tenant-cohérentes ; une projection fermée est disponible. | Évaluer la policy puis retourner `200` si autorisée. |
| `DCE_REFERENCE_BROKEN` | État défensif : FK/consistance inattendue, sans projetable DCE. | `422 COMMAND_REJECTED`, audit application futur. |

La query ne fait aucune écriture, ne produit ni receipt ni événement, ne prend aucun verrou et ne modifie pas les confirmations, analyses, classifications ou sources.

## 3. Modèle de projection

```text
CaseDceReadingLookup
├── case_id
├── work_label
├── case_lifecycle
├── commercial_stage
├── dce_freshness
├── availability
└── reading: CaseDceReadingProjection | None
    ├── dce_version_id
    ├── lifecycle
    ├── integrity
    ├── classification_readiness
    ├── analysis_readiness
    ├── source_received_at
    ├── requirements: tuple[CaseDceReadingRequirement]
    │   ├── requirement_id
    │   ├── requirement_type
    │   ├── directive_signal
    │   ├── confirmation_outcome | PENDING_HUMAN_CONFIRMATION
    │   ├── uncertainty_status
    │   ├── document_family | SOURCE_UNCLASSIFIED
    │   └── source_locator_label
    └── counters
        ├── total
        ├── pending_human_confirmation
        ├── confirmed
        ├── review_required
        └── not_applicable
```

`work_label` provient du titre de Case et doit être traité comme un libellé opérationnel, jamais comme une donnée financière. Les données de consultation détaillées, les données de décision et le contenu de `scope_json` sont exclus.

## 4. Détermination des exigences et de leur état

La query sélectionne uniquement les exigences dont `dce_version_id` est la DCE applicable de la Case, avec le même `tenant_id` sur chaque jointure.

| Champ projeté | Construction autorisée |
|---|---|
| `requirement_type` | Valeur fermée de `dce_requirements.requirement_type`. |
| `directive_signal` | Valeur fermée de `dce_requirements.directive_signal`. |
| `uncertainty_status` | Valeur fermée de `dce_requirements.uncertainty_status`. |
| `confirmation_outcome` | `dce_requirement_confirmation_current.outcome`, ou `PENDING_HUMAN_CONFIRMATION` si aucune projection courante n’existe. |
| `document_family` | Classification courante de la pièce source si disponible ; sinon `SOURCE_UNCLASSIFIED`. |
| `source_locator_label` | Étiquette dérivée uniquement d’un locator de fragment connu : `page N`, `paragraphe N`, `cellule FEUILLE!A1` ou `ligne N`, précédée de la famille de pièce. |

Les exigences sont ordonnées de manière déterministe par type, puis par label de locator, puis par UUID. Les compteurs sont dérivés de la collection finale, jamais d’une requête de comptage différente.

## 5. Provenance strictement bornée

Le lien technique autorisé est :

```text
dce_requirement
  → dce_requirement_source
  → dce_document_extraction_fragment
  → dce_document_extraction
  → dce_document
  → dce_document_classification (courante seulement)
```

Le formatter de locator accepte exclusivement les clés attendues des formats déjà extraits : `pdf_page/page`, `docx_paragraph/paragraph`, `xlsx_cell/sheet/cell` et `text_line/line`. Toute forme inconnue, valeur non positive ou chaîne trop longue produit le libellé neutre `Source localisée` ; elle n’est jamais retournée brute.

## 6. Données interdites par construction

La projection, ses dataclasses, son port et son adapter ne doivent contenir aucun des champs suivants :

| Catégorie | Champs et contenus interdits |
|---|---|
| Stockage et intégrité technique | `storage_key`, `storage_object_id`, `original_filename`, `media_type`, `byte_size`, `sha256`, `corpus_hash`, `input_sha256`, `text_sha256`. |
| Provenance privée | URL, channel, référence de provenance, source de retrait, motif de retrait, raison d’incident. |
| Contenu documentaire | texte de fragment, extrait d’analyse, extrait de statement, locator JSON brut, texte OCR, commentaire libre. |
| Données sensibles | prix, budget, coût, marge, devis, trésorerie, identité d’auteur, identifiant de session, audit brut, token, credential. |
| Décision métier hors périmètre | score de conformité, Go/No-Go, prix final, statut de dépôt, décision patron. |

## 7. Cas de bord obligatoires

| Cas | Résultat attendu |
|---|---|
| Case inexistante dans le tenant | `None`, sans requête de DCE secondaire. |
| Case d’un autre tenant | `None`, même résultat que l’absence. |
| Case sans DCE applicable | Lookup `NO_APPLICABLE_DCE`, lecture `None`. |
| FK DCE incohérente ou DCE non retrouvée | Lookup `DCE_REFERENCE_BROKEN`, lecture `None`. |
| DCE supersédée ou retirée | Projection disponible avec `lifecycle` réel ; aucun faux état `CURRENT`. |
| DCE sans exigences | Projection disponible, collection vide et compteurs à zéro. |
| Exigence sans confirmation | `PENDING_HUMAN_CONFIRMATION`. |
| Exigence avec confirmation courante | Dernier `outcome` projeté seulement, sans auteur ni historique. |
| Source ou classification absente | `SOURCE_UNCLASSIFIED` et label neutre ; aucun champ interne brut. |

## 8. Preuves de sortie

Le sous-slice B est terminé seulement si une suite PostgreSQL prouve : isolation tenant ; Case sans DCE ; DCE applicable correcte ; DCE d’un autre tenant impossible ; projection de confirmations courantes ; compteurs cohérents ; ordre déterministe ; DCE supersédée visible ; source non classifiée traitée sans fuite ; et absence de toute clé interdite dans la représentation Python convertie en données primitives.

## 9. Non-objectifs

Ce sous-slice ne fait ni authorisation HTTP, ni audit de policy, ni endpoint, ni téléchargement, ni rendu PDF, ni recherche plein texte, ni question acheteur, ni tâche, ni annotation, ni génération de document, ni mutation de confirmation. Ces responsabilités restent dans les incréments C et suivants.
