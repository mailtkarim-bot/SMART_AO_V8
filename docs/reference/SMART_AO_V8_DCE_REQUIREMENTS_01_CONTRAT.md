# SMART_AO V8 — DCE-REQUIREMENTS-01 : exigences atomiques dérivées du règlement de consultation

**Statut :** normatif.
**Périmètre :** matérialisation interne et reproductible des signaux RC persistés en exigences atomiques à confirmer par un humain.
**Dépendances :** SEC-01, DCE-ADMIT-01, DCE-DOCUMENT-EXTRACTION-01, DCE-ANALYSIS-01 et DCE-CLASSIFICATION-01.

## 1. But et frontière

DCE-REQUIREMENTS-01 transforme des **observations lexicales déjà sourcées** de DCE-ANALYSIS-01 en objets de travail atomiques. Une exigence permet de suivre une consigne relevée dans le règlement de consultation sans que le logiciel affirme sa portée juridique, sa complétude ou son applicabilité à l’entreprise.

> Une exigence atomique est une proposition de suivi issue d’un signal sourcé. Elle est `PENDING_HUMAN_CONFIRMATION` par défaut et ne devient jamais, dans ce slice, une obligation juridique, une tâche, une pièce manquante, un blocage ou une décision de réponse.

Le règlement de consultation peut notamment présenter les modalités de candidature, de remise de l’offre, de visite, de dépôt, de validité et les critères d’attribution. Ces thèmes sont les sources des exigences proposées ci-dessous ; leur présence dans un signal ne dispense pas d’une vérification humaine du DCE. [1] [2]

## 2. Préconditions non négociables

La matérialisation est une commande interne. Seul un `actor_kind = SYSTEM` peut l’émettre. Aucun endpoint HTTP, utilisateur, collaborateur, patron, navigateur, webhook ou document importé ne peut fabriquer des exigences durables.

| Fait relu côté serveur | Condition exigée | Refus ou résultat sûr sinon |
|---|---|---|
| DCE | même tenant, `ADMITTED` ou `SUPERSEDED`, intégrité `VERIFIED` | `DCE_VERSION_NOT_REQUIREMENTS_READY` |
| Analyse RC | même tenant et même DCE, statut `COMPLETED` | `DCE_RC_ANALYSIS_COMPLETED_REQUIRED` |
| Observation | reliée à cette analyse, règle/version et source cohérentes | `DCE_RC_OBSERVATION_REQUIRED` |
| Source | fragment du même tenant et de la même DCE, offsets vérifiables | `DCE_REQUIREMENT_SOURCE_REQUIRED` |
| Manifest | SHA-256 canonique des observations réellement converties | `DCE_REQUIREMENT_INPUT_MANIFEST_REQUIRED` |
| Commande | acteur `SYSTEM`, IDs uniques, statuts fermés et mapping fermé | `DCE_REQUIREMENT_SYSTEM_ACTOR_REQUIRED` |

Une analyse `NO_RC_MARKER`, `REJECTED_LIMIT` ou `FAILED_SAFE` ne crée aucune exigence. Une analyse `COMPLETED` sans observation produit un résultat terminal `NO_SIGNAL` qui n’affirme pas l’absence d’exigence dans le DCE.

## 3. Mapping fermé : signal RC → exigence atomique

L’algorithme ne relit pas les originaux, ne reparcourt pas les fragments de texte et ne réinterprète pas la clause. Il relit les observations immuables déjà vérifiées par DCE-ANALYSIS-01 et copie uniquement les références nécessaires à leur suivi.

| Signal `requirement_kind` | `requirement_type` atomique | Question de suivi pour l’humain | Exclusion explicite |
|---|---|---|---|
| `RC_DOCUMENT_CANDIDATURE` | `CANDIDATURE_DOCUMENT` | « Une pièce ou modalité de candidature est-elle à prévoir ? » | Aucune vérification de disponibilité, validité ou conformité. |
| `RC_CONTENT_OFFER` | `OFFER_DOCUMENT` | « Une pièce de l’offre est-elle à préparer ou joindre ? » | Aucune génération, signature ou validation de document. |
| `RC_SUBMISSION_DEADLINE` | `SUBMISSION_DEADLINE_SIGNAL` | « Une date ou heure de remise mérite-t-elle une vérification humaine ? » | Aucun parsing de date, fuseau, calendrier ou rappel automatique. |
| `RC_RESPONSE_CHANNEL` | `SUBMISSION_CHANNEL` | « Un canal de dépôt doit-il être vérifié ? » | Aucune connexion à une plateforme ni dépôt. |
| `RC_FILE_CONSTRAINT` | `FILE_CONSTRAINT` | « Une contrainte de format, taille ou signature doit-elle être contrôlée ? » | Aucune validation de fichier ou signature. |
| `RC_SITE_VISIT` | `SITE_VISIT` | « Une visite est-elle à confirmer ou à organiser ? » | Aucun rendez-vous ni création de tâche. |
| `RC_AWARD_CRITERION` | `AWARD_CRITERION_SIGNAL` | « Un critère d’attribution doit-il être examiné par le patron ? » | Aucun score, pondération fiable, stratégie de prix ou calcul. |
| `RC_NEGOTIATION` | `NEGOTIATION_SIGNAL` | « La clause de négociation doit-elle être relue ? » | Aucune décision sur une négociation future. |
| `RC_OFFER_VALIDITY` | `OFFER_VALIDITY_SIGNAL` | « La validité de l’offre doit-elle être vérifiée ? » | Aucun calcul d’expiration ou avis juridique. |

Le `directive` lexical de l’observation (`REQUIRED_SIGNAL`, `OPTIONAL_SIGNAL`, `UNSPECIFIED`) est conservé sous le nom `directive_signal`. Il n’est ni transformé en obligation, ni utilisé pour bloquer le wizard.

## 4. Identité, atomicité et absence de fusion silencieuse

Une exigence est le reflet d’une observation sourcée; elle ne fusionne pas plusieurs phrases, documents ou signaux. Son identité fonctionnelle est `(tenant_id, requirements_run_id, source_observation_id)`. Ainsi, deux observations distinctes de même type deviennent deux exigences distinctes, à confirmer ou rapprocher ultérieurement par un humain.

| Champ durable | Sens | Valeurs / règles |
|---|---|---|
| `requirement_type` | Famille atomique de suivi | Catalogue du §3. |
| `directive_signal` | Posture lexicale héritée | `REQUIRED_SIGNAL`, `OPTIONAL_SIGNAL`, `UNSPECIFIED`. |
| `confirmation_status` | État humain attendu | Initialement et exclusivement `PENDING_HUMAN_CONFIRMATION` dans ce slice. |
| `uncertainty_status` | Degré de prudence | Initialement et exclusivement `SOURCE_SIGNAL_ONLY`. |
| `source_observation_id` | Preuve d’origine | Observation immuable de l’analyse choisie. |
| `source_fragment_id`, offsets | Traçabilité de lecture | Copie contrôlée de la source de l’observation, jamais saisie par l’appelant. |

Une future confirmation humaine doit créer une succession historique explicite ; elle ne peut ni modifier, ni supprimer l’exigence générée. Ce futur mécanisme n’est pas livré ici.

## 5. Manifest, versions et idempotence

Une exécution est ciblée par une `dce_rc_analysis_id` `COMPLETED`. Son manifest est le SHA-256 UTF-8 de lignes ordonnées par UUID d’observation normalisé, séparées par un LF réel :

```text
<observation_id>|<requirement_kind>|<directive>|<rule_id>|<rule_version>|<fragment_id>|<start_byte_offset>|<end_byte_offset>
```

Le manifest ne contient ni extrait, ni texte, ni nom de fichier, ni hash d’original, ni clé privée, ni prix. L’unicité fonctionnelle d’une exécution est `(tenant_id, dce_version_id, dce_rc_analysis_id, input_manifest_sha256, materializer_id, materializer_version)`.

La commande `RecordDceRequirementMaterializationRun` reçoit un identifiant et une clé d’idempotence déterministes depuis cette identité. Un même replay retourne le receipt existant sans réécrire aucun objet. Une nouvelle analyse ou une nouvelle version du matérialiseur produit une nouvelle exécution et conserve l’historique antérieur.

## 6. Registre append-only et transaction

| Table | Grain | Contenu autorisé |
|---|---|---|
| `dce_requirement_materialization_runs` | Une conversion déterministe d’une analyse RC. | Manifest, version, statut, compteurs et code terminal fermé. |
| `dce_requirements` | Une exigence atomique par observation source. | Type, directive, prudence, statut de confirmation et IDs de preuve. |
| `dce_requirement_sources` | Une preuve technique par exigence. | Observation, fragment et offsets recopiés et contrôlés. |

Les trois tables sont tenant-scopées et append-only par triggers PostgreSQL. Une exigence ne peut être insérée que pour un run `COMPLETED`, une analyse `COMPLETED`, une observation du même tenant et de la même DCE, avec le même fragment et les mêmes offsets que la source persistée de cette observation.

Dans une transaction unique, le handler verrouille la DCE, l’analyse, les observations et leurs sources; il revalide le manifest et le mapping fermé; il écrit l’exécution, les exigences et preuves; puis le dispatcher écrit le receipt, l’événement et l’outbox. Il ne modifie ni le corpus DCE, ni les extractions, ni les observations RC, ni les classifications, ni les readinessees de DCE.

## 7. Statuts, limites, événements et confidentialité

| Contrôle | Limite / règle | Résultat sûr |
|---|---:|---|
| Observations par run | 20 000 | `REJECTED_LIMIT`, zéro exigence. |
| Exigences par run | 20 000 | `REJECTED_LIMIT`, zéro exigence. |
| Sources par exigence | 1 | Toute agrégation future exige un contrat. |
| `COMPLETED` | Une exigence pour chaque observation source | Toutes restent `PENDING_HUMAN_CONFIRMATION`. |
| `NO_SIGNAL` | Analyse terminée sans observation | Zéro exigence, sans affirmation d’absence métier. |
| `REJECTED_LIMIT` / `FAILED_SAFE` | Code fermé obligatoire | Zéro exigence. |

L’événement `DCE_REQUIREMENTS_MATERIALIZED` porte uniquement l’ID de run, l’ID de DCE, l’ID d’analyse, le statut et les compteurs. L’outbox `cockpit_projection` ne contient ni extrait, ni texte, ni offsets, ni hash de document, ni nom de fichier, ni information financière.

Aucune route HTTP n’est ajoutée. Les futures lectures cockpit et collaborateur devront appliquer SEC-01, une policy, la minimisation des extraits et l’interdiction de rendre l’état `PENDING_HUMAN_CONFIRMATION` comme une conclusion métier.

## 8. Critères de sortie

Le slice doit démontrer :

1. le mapping reproductible d’une observation RC vers une exigence atomique unique;
2. le maintien du type, de la directive, du statut de prudence et de la source;
3. un résultat `NO_SIGNAL` sans exigence pour une analyse `COMPLETED` vide;
4. l’absence de matérialisation pour une analyse non `COMPLETED`;
5. l’acteur `SYSTEM`, l’isolation tenant, le manifest et le replay idempotent;
6. l’immutabilité PostgreSQL des runs, exigences et preuves;
7. l’absence de texte ou de données sensibles dans événement/outbox;
8. l’absence de calcul juridique, financier ou de décision métier automatisée.

## 9. Non-objectifs

DCE-REQUIREMENTS-01 ne confirme, n’infirme, ne calcule, ne planifie, ne notifie, ne relance et ne dépose rien. Il ne calcule aucune échéance, ne crée aucune tâche, ne déclare aucune pièce manquante, ne contrôle aucune signature ou conformité, ne calcule aucune note/prix/marge, ne génère aucun document et ne prend aucune décision Go/No-Go. Il ne lit pas les binaires ni les originaux, ne fait ni OCR ni LLM, et n’expose aucun endpoint HTTP.

## Références

[1]: https://entreprendre.service-public.gouv.fr/vosdroits/F32130 "Service Public Entreprendre — Examiner les documents de la consultation d’un marché public, vérifié le 1er avril 2026"
[2]: https://entreprendre.service-public.gouv.fr/vosdroits/F32106 "Service Public Entreprendre — Remettre la réponse à un marché public et échanger avec l’acheteur public, vérifié le 1er avril 2026"
