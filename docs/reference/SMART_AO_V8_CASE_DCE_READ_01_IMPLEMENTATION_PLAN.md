# SMART_AO V8 — Plan d’implémentation CASE-DCE-READ-01

**Statut :** proposition d’exécution après validation des contrats.  
**Objectif :** livrer la première lecture DCE d’une affaire affectée, avec une API Case-scopée sécurisée, puis seulement la première interface collaborateur.

## 1. Règle de séquençage

La lecture d’affaire doit exister et être prouvée au backend avant de créer l’écran React. L’interface ne doit jamais reconstruire une autorisation, assembler des données DCE depuis plusieurs endpoints globaux ou cacher financièrement une information qu’elle a déjà reçue.

> Ordre obligatoire : **contrat figé → policy et query serveur → route HTTP et tests → projection UI → test de parcours réel**.

## 2. Incréments proposés

| ID | Incrément | Livrable durable | Critère de sortie |
|---|---|---|---|
| `CASE-DCE-READ-01-A` | Capability et matrice de policy | Capability fermée `case.dce.read`; mapping patron/collaborateur/délégation ; contrat de resource Case-scopée. | Tests unitaires de policy : patron autorisé, collaborateur affecté autorisé, absence d’affectation refusée, Case manquante refusée. |
| `CASE-DCE-READ-01-B` | Query applicative Case-scopée | `GetCaseDceReadingHandler` ou service de lecture sans FastAPI ; projection typée et fermée. | Tenant, Case active, DCE applicable et readiness relus serveur ; aucune colonne interdite dans le modèle de sortie. |
| `CASE-DCE-READ-01-C` | Provenance bornée et cohérence de lecture | Adaptateur SQLAlchemy qui joint uniquement DCE, classifications, exigences, confirmations courantes et locator autorisé. | Tests PostgreSQL : ordre stable, tenant isolation, DCE étrangère inaccessible, absence de source sans fuite. |
| `CASE-DCE-READ-01-D` | Transport HTTP authentifié | `GET /api/v1/cases/{case_id}/dce-reading`; DTO Pydantic fermés ; réponses neutres. | Bearer réel, policy auditée, 401/403/404/422 documentés, DTO sans données financières, original, hash ni stockage. |
| `CASE-DCE-READ-01-E` | Tests de sécurité et régression | Suite API et DB dédiée. | Patron, collaborateur affecté, collaborateur hors Case, autre tenant, Case sans DCE, DCE supersédée, sortie sans fuite et absence de mutation. |
| `WIZARD-COLLAB-01-A` | Socle Web React | Shell d’authentification, route `Mes affaires`, client HTTP typé, gestion stricte de 401/403/404/422. | Aucun mock financier ; affichage des erreurs neutres et de l’état de chargement. |
| `WIZARD-COLLAB-01-B` | Liste des affaires affectées | Première vue personnelle `Mes affaires`, alimentée par un endpoint futur distinct de liste Case. | Une affaire non affectée n’est jamais dans le DOM ou la réponse réseau. |
| `WIZARD-COLLAB-01-C` | Vue de lecture d’affaire | Bandeau, barre wizard V0, compteurs, liste des exigences, panneau de détail et actions confirmation/revue. | Seule l’étape Lecture DCE est active ; les étapes futures sont visuelles et explicitement non disponibles. |
| `WIZARD-COLLAB-01-D` | Parcours de preuve sur DCE de référence | Scénario navigateur DCE réel autorisé. | Le collaborateur ouvre une affaire, retrouve une source, confirme/demande une revue, recharge et retrouve l’état sans fuite financière. |

## 3. Design des éléments backend

### 3.1 Capability à ajouter

`case.dce.read` est distinct de `dce.prepare`. La première exprime le droit de consulter une **vue d’affaire** ; la seconde reste associée aux opérations de préparation/ingestion DCE déjà existantes. Aucun rôle ne doit obtenir la nouvelle capability implicitement par la présence d’un JWT.

| Rôle ou contexte | `case.dce.read` |
|---|---|
| `PATRON_ADMIN` actif | Oui. |
| `COLLABORATEUR` actif | Oui, seulement avec affectation Case et scopes ReBAC compatibles. |
| `PATRON_DELEGATE` | Seulement via grant serveur explicite futur. |
| `SYSTEM` | Non, dans le transport HTTP humain. |

### 3.2 Projection de lecture proposée

```text
CaseDceReadingView
├── case_id
├── work_label
├── reading_status
├── dce: CaseDceReadingDceView
│   ├── dce_version_id
│   ├── lifecycle
│   ├── integrity
│   ├── extraction_readiness
│   ├── classification_readiness
│   ├── analysis_readiness
│   └── supersession_visible
├── counters: CaseDceReadingCounters
└── requirements: list[CaseDceReadingRequirementView]
    ├── requirement_id
    ├── requirement_type
    ├── directive_signal
    ├── confirmation_state
    ├── uncertainty_state
    ├── document_family
    ├── source_locator_label
    └── allowed_actions
```

La projection n’inclut pas de texte de fragment, de document original, de pièce stockée, de metadata de scan, de nom de fichier, de hash, de prix, de marge, de budget ou d’audit brut.

### 3.3 Décision de persistance

`CASE-DCE-READ-01-A` à `E` ne requièrent pas encore de migration de modèle de travail Case-scopé. Il s’agit d’une **projection de lecture** sur les registres existants, sécurisée par la Case du chemin HTTP.

En revanche, la création ultérieure de notes, tâches, questions, confirmations propres à une affaire ou impact de rectificatif nécessitera un nouveau root explicite. Il est interdit de réutiliser la confirmation DCE globale comme substitut implicite d’un état propre à la Case si la même DCE peut être partagée.

## 4. Plan de tests minimum

| Couche | Cas obligatoires |
|---|---|
| Policy pure | Tenant différent, membership inactive, capability absente, `case_id` absente, affectation expirée, action absente du scope, classification refusée, patron autorisé. |
| PostgreSQL | FK tenant-scopées, Case vers DCE, DCE étrangère, DCE sans exigences, ordre déterministe, confirmation courante correctement projetée, absence de mutation. |
| HTTP | 401 sans bearer, 403 collaborateur sans affectation, 404 Case hors tenant, 422 Case sans DCE applicable, 200 patron, 200 collaborateur affecté, corps sans clés interdites. |
| Sécurité de données | Recherche automatisée des clés `price`, `margin`, `budget`, `storage`, `sha`, `filename`, `excerpt`, `content`, `audit` dans le JSON publié. |
| Interface | Aucun rendu d’une affaire non affectée ; états vides honnêtes ; aucune étape future clickable ; action confirmation reflète le receipt serveur. |

## 5. Critères avant ouverture du Web

Le développement du Web ne commence que lorsque `CASE-DCE-READ-01-A` à `E` ont été validés par tests et publication GitHub. Cette séquence est volontaire : une interface très belle mais qui reçoit une DCE globale ou un prix par erreur serait un recul de sécurité.

## 6. Estimation de charge relative

| Bloc | Poids relatif | Risque principal |
|---|---:|---|
| A — Capability/policy | Faible | Ouvrir trop largement le scope collaborateur. |
| B/C — Query et provenance | Moyen | Faire fuiter des métadonnées de document ou mal relier les sources. |
| D/E — HTTP et tests | Moyen | Réponses non neutres, corps trop riche, régression policy. |
| Wizard A/B | Moyen | Créer une fondation web trop large ou une liste non filtrée. |
| Wizard C/D | Élevé | Simuler une progression métier sans persistance/proof réelle. |

## 7. Point de décision avant code

Le fondateur doit d’abord valider que le premier écran collaborateur est bien limité à la **lecture et qualification humaine des exigences sourcées d’une affaire**, et non à l’ensemble des sept étapes du parcours collaborateur. Une fois cette validation donnée, nous implémentons `CASE-DCE-READ-01-A` dans le dépôt, sans créer encore de frontend.
