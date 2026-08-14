# SMART_AO V8 — CASE-DCE-READ-01 : lecture DCE opérationnelle par affaire

**Statut :** proposition normative soumise à validation métier avant tout code.  
**Périmètre :** première lecture exploitable d’un DCE depuis une `Case` affectée, destinée au wizard collaborateur.  
**Dépendances :** SEC-01, Case, Consultation/DceVersion, DCE-DOCUMENT-EXTRACTION-01, DCE-ANALYSIS-01, DCE-CLASSIFICATION-01, DCE-REQUIREMENTS-01 et DCE-REQUIREMENTS-CONFIRMATION-01.

## 1. Décision de frontière

Une exigence demeure un **fait source rattaché à une version DCE**. Elle ne sera pas déplacée vers une `Case`, et elle ne sera pas dupliquée lorsque plusieurs affaires utilisent le même DCE. Cette règle préserve l’historique de l’analyse et empêche qu’un collaborateur transforme accidentellement une lecture de document en propriété métier arbitraire.

La `Case` est le contexte de travail et de sécurité. Elle détermine l’affaire ouverte par le collaborateur, la DCE applicable, l’affectation ReBAC et le périmètre de la lecture. Toute route collaborateur de ce slice commence donc par une `case_id`, jamais par une `dce_version_id` libre fourni par le navigateur.

> Une lecture Case-scopée signifie : « cet utilisateur affecté consulte les faits DCE applicables à cette affaire ». Elle ne signifie ni que le DCE n’est utilisé par aucune autre affaire, ni que les exigences sont définitivement propres à cette affaire, ni que le dossier est conforme ou prêt à déposer.

## 2. Objectif métier du premier incrément visible

Le premier écran doit permettre à un collaborateur affecté de répondre sans naviguer dans un ERP à quatre questions : quelle affaire je traite, quel DCE est applicable, quels signaux exigent une revue humaine, et quelle source justifie chaque signal.

Le résultat attendu est une **liste de travail sourcée**, non un rapport juridique. Le collaborateur peut confirmer qu’un signal est retenu pour la préparation ou demander une revue. Il ne peut ni calculer un délai, ni conclure à une conformité, ni choisir un prix, ni voir une marge, ni déposer une offre.

| Élément métier affiché | Source durable | Limite d’interprétation |
|---|---|---|
| Affaire, lot et statut de travail | `Case` autorisée | Aucun portefeuille global ni donnée stratégique. |
| Version DCE applicable et état technique | `Case.applicable_dce_version_id` puis `DceVersion` | Aucune DCE libre hors affaire. |
| Famille de pièce et disponibilité d’analyse | Classification/extraction existantes | Aucun original, stockage, hash ou URL. |
| Exigence atomique | `dce_requirements` | Toujours un signal sourcé, jamais une conformité. |
| État de confirmation | Projection append-only de confirmation | Qualification humaine de préparation uniquement. |
| Provenance consultable | Famille de pièce et locator technique borné | Aucun extrait complet, contenu original ou pièce financière. |

## 3. Portée Case et résolution exclusivement serveur

La route proposée est :

```text
GET /api/v1/cases/{case_id}/dce-reading
```

Le serveur applique l’ordre suivant, sans faire confiance au corps de requête ni à un identifiant DCE transmis par le client :

1. Résoudre le bearer JWT, la session, l’identité, la membership et l’`ActorContext` réels.
2. Relire la `Case` avec filtre `tenant_id` ; si elle est absente ou hors tenant, retourner `404 NOT_FOUND_OR_FORBIDDEN`.
3. Vérifier que la Case est active et qu’elle possède une `applicable_dce_version_id` non retirée. Sinon retourner `422 COMMAND_REJECTED` avec un corps public minimisé.
4. Relire la DCE applicable par FK composite tenant-scopée.
5. Construire une `AuthorizationResource` dont `case_id` est la Case résolue et dont la classification est `INTERNAL_OPERATIONAL`.
6. Évaluer la capability dédiée `case.dce.read` et la policy SEC-01 auditée avant toute sérialisation.
7. Construire la vue à partir des registres DCE existants, filtrés par tenant et par DCE applicable.

Le collaborateur ne reçoit aucun accès par une route globale du type `/dce-versions/{id}`. La route globale DCE-READ-01 demeure volontairement plus restrictive pour les collaborateurs.

## 4. Acteurs et matrice de policy

| Acteur | Capability requise | Préconditions serveur | Autorisations dans ce slice | Interdits absolus |
|---|---|---|---|---|
| `COLLABORATEUR` affecté | `case.dce.read` | Membership active, affectation active à la Case, action et classification présentes dans le scope ReBAC. | Lire la vue de son affaire ; consulter les exigences ; confirmer ou demander une revue selon DCE-REQUIREMENTS-CONFIRMATION-01. | Voir une autre affaire, tout prix/marge/trésorerie, marque `NOT_APPLICABLE`, Go/No-Go, dépôt, modification de la source. |
| `PATRON_ADMIN` | `case.dce.read` | Membership active ; policy `ALLOW`. | Lire toute Case de son tenant et les mêmes sources de travail. | Altérer les registres source par cette route. |
| `PATRON_DELEGATE` | Grant explicite futur | Capability calculée côté serveur ; policy `ALLOW`. | Même vue seulement dans son périmètre délégué. | Droit déduit du rôle seul. |
| `SYSTEM` | Aucune route HTTP humaine | N/A | Aucun accès via ce transport. | Utiliser une session humaine ou confirmer une exigence. |

Les refus de policy sont enregistrés par `AuditedAuthorizationPolicy`. Une Case hors tenant ou inconnue produit une réponse neutre et un audit minimisé de refus de portée. Aucun détail d’affectation, de scope, de DCE concurrente ou de règle interne n’est envoyé au navigateur.

## 5. Contrat de sortie HTTP fermé

La vue doit être une réponse Pydantic fermée. Elle ne reçoit ni ne retourne une information financière, une information de stockage ou un contenu documentaire brut.

| Groupe | Champs autorisés | Champs interdits |
|---|---|---|
| En-tête affaire | `case_id`, libellé de travail non financier, état du workflow de lecture, `dce_version_id`, fraîcheur DCE. | Objet complet si classifié, origine privée, décision patron, prix, marge, budget, charge interne. |
| État DCE | lifecycle, integrity, readiness extraction/classification/analyse, présence de rectificatif. | hash, clés storage, URL, taille, MIME, nom original, provenance privée. |
| Ligne d’exigence | `requirement_id`, type fermé, directive signal, état de confirmation, état d’incertitude, famille de pièce, locator source borné, indicateur d’action humaine possible. | Extrait, texte original, commentaire libre historique, auteur, audit brut, donnée financière. |
| Compteurs | total, à confirmer, à revoir, confirmées. | Score de conformité, pourcentage de complétude commerciale, score de chance de gain. |

Le locator présenté au collaborateur doit être contrôlé par le serveur : par exemple `RC · page 8` ou `ANNEXE · tableau 3`. Il ne doit jamais contenir le contenu d’un fragment, l’URL d’un objet ou un chemin de fichier.

## 6. Actions autorisées depuis le premier wizard

| Action visible | Transport | Précondition | Effet durable | Ce qu’elle ne signifie pas |
|---|---|---|---|---|
| `Voir la source` | Lecture Case-scopée future de locator/document rendu | Case autorisée et ressource classifiée | Aucun effet d’écriture. | Le document est complet, lu juridiquement ou validé. |
| `Confirmer pour préparation` | Route de confirmation existante, appelée avec requirement résolu dans la Case ouverte | Collaborateur affecté ou patron ; outcome autorisé. | Confirmation append-only. | Pièce produite, conformité, prix validé ou dépôt possible. |
| `Demander une revue` | Route de confirmation existante avec `REVIEW_REQUIRED` | Même preconditions. | Confirmation append-only. | Décision patron ou question acheteur envoyée. |
| `Filtrer les éléments à revoir` | Lecture locale de la vue fermée | Case autorisée. | Aucun effet durable. | État métier modifié. |

`NOT_APPLICABLE` ne sera pas présenté dans le premier wizard collaborateur. Il reste une action patron séparée, justifiée et auditée.

## 7. Consistance et rectificatifs

La vue est construite pour **une DCE applicable de la Case**, pas pour « la dernière DCE du tenant ». Si la Case pointe vers une DCE supersédée, elle affiche explicitement son état et bloque les actions qui exigent une DCE active selon la règle métier définie par le futur slice de rectificatif.

Dans ce premier incrément, un rectificatif ne recalcule pas silencieusement les confirmations. Il rend la lecture manifestement à revoir. Le prochain slice devra persister une analyse d’impact Case-scopée, plutôt que de deviner quels éléments restent valables.

## 8. Évolution de modèle explicitement différée

Ce slice ne modifie pas `dce_requirements` pour y ajouter `case_id`. La future persistance Case-scopée sera un registre distinct, par exemple `case_dce_requirement_reviews` ou `case_dce_reading_items`, avec : `tenant_id`, `case_id`, `dce_version_id`, `requirement_id`, état de travail, auteur, révision et preuves. Son contrat devra préciser si une revue est une projection de la confirmation DCE globale ou une nouvelle décision d’affaire.

Cette séparation est obligatoire avant d’autoriser une même DCE à alimenter plusieurs Cases actives avec des décisions de travail divergentes.

## 9. Réponses publiques

| Situation | HTTP | Corps public |
|---|---:|---|
| Lecture autorisée | `200` | Vue fermée décrite au §5. |
| Bearer absent, invalide ou session révoquée | `401` | `UNAUTHENTICATED`. |
| Case absente ou hors tenant | `404` | `NOT_FOUND_OR_FORBIDDEN`. |
| Capability, affectation ou classification refusée | `403` | `FORBIDDEN`. |
| Case inactive, sans DCE applicable ou DCE incompatible | `422` | `COMMAND_REJECTED`. |

## 10. Critères de sortie du slice backend

Le slice ne pourra être déclaré terminé que si les tests prouvent : bearer réel obligatoire ; patron autorisé ; collaborateur affecté autorisé uniquement pour sa Case ; collaborateur sans affectation refusé et audité ; inter-tenant neutre ; absence de champs financiers/documentaires interdits ; DCE rendue exclusivement via la Case ; source locator borné ; exigence et confirmation cohérentes ; rectificatif visible ; et absence de mutation de toute source lors d’une lecture.

## 11. Non-objectifs explicites

CASE-DCE-READ-01 ne fournit pas encore un lecteur PDF complet, OCR, plans, téléchargement d’originaux, annotation libre, question acheteur, tâche, calendrier, calcul de délai, registre de risque, génération de mémoire, chiffrage, DPGF/BPU, pièce administrative, ZIP de dépôt, Go/No-Go, signature, dépôt ou suivi de chantier. Ces fonctions seront ouvertes par contrats distincts après validation du premier wizard.

## 12. Décision demandée au fondateur

Valider les trois principes suivants avant codage :

1. La première interface collaborateur lit une **affaire** et non une DCE globale.
2. Les exigences restent DCE-sourcées ; la vue Case-scopée n’en déduit pas une conformité et n’ajoute pas de `case_id` à la source actuelle.
3. Le premier wizard s’arrête après la revue des exigences sourcées ; les tâches, questions, preuves d’entreprise et pièces de réponse restent les slices suivants.
