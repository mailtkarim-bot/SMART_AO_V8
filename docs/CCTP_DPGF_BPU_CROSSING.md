# Croisement automatique CCTP–DPGF–BPU

## Périmètre

Le croisement est une **projection patronale en lecture seule**. Il rapproche les fragments textuels classifiés `CCTP` de la version DCE applicable au dossier avec les lignes normalisées des imports `DPGF` et `BPU` à l’état `COMMITTED`.

Le résultat est une liste de candidats explicables. Il ne constitue ni une conformité contractuelle, ni une estimation, ni une recommandation financière, ni une décision d’attribution. Chaque candidat est explicitement marqué `REVIEW_REQUIRED`.

## Endpoint

```text
GET /api/v1/patron/cases/{case_id}/cctp-pricing-crossing?limit=25
```

L’accès est réservé au `PATRON_ADMIN` disposant de la capacité Decision appropriée. La requête résout `cases.applicable_dce_version_id`, filtre le tenant sur chaque jointure et ignore les dossiers sans version DCE applicable.

La projection retourne uniquement les éléments suivants :

| Élément | Rôle |
|---|---|
| `dce_version_id` | Version DCE source applicable |
| `source_fragment_id` | Fragment CCTP d’origine |
| `source_locator_label` | Localisation humaine bornée, par exemple page ou paragraphe |
| `source_start_byte_offset`, `source_end_byte_offset` | Intervalle UTF-8 du fragment source |
| `batch_id`, `document_kind`, `row_number` | Référence de la ligne DPGF/BPU normalisée |
| `code`, `designation`, `unit` | Métadonnées descriptives de la ligne |
| `match_score_bps` | Score lexical borné sur 10 000 |
| `match_basis` | Justification déterministe du rapprochement |
| `verification_status` | Toujours `REVIEW_REQUIRED` dans ce lot |

Les colonnes `quantity_decimal`, `unit_price_minor` et `total_minor` ne font pas partie du contrat public.

## Algorithme déterministe

Le matcher de domaine applique une normalisation stable : casse minuscule, suppression des accents, séparation des caractères non alphanumériques et retrait d’un vocabulaire fermé de mots-outils français.

Un code de ligne est prioritaire lorsqu’ensemble de ses tokens normalisés apparaît dans le fragment CCTP. Cette correspondance reçoit le basis `CODE_EXACT` et le score `10 000`.

À défaut, le matcher calcule l’intersection entre les tokens de la désignation et ceux du fragment. Un candidat est conservé lorsque deux tokens de désignation au moins sont partagés, ou lorsqu’une désignation mono-token suffisamment spécifique est partagée. Le score correspond à la proportion de tokens partagés, bornée à `10 000`. La présence de l’unité dans le fragment ajoute un bonus borné de 500 points et utilise le basis `NORMALIZED_TOKEN_OVERLAP_AND_UNIT`.

Les résultats sont triés de manière stable par score décroissant, famille documentaire, identifiant de batch, numéro de ligne puis fragment source. La limite publique est bornée entre 1 et 100.

## Limites assumées

Le lot ne fait pas d’OCR, de recherche sémantique, de lemmatisation, de calcul de quantité ou de prix, de décision automatique, ni de validation juridique. Les documents DCE doivent déjà être extraits et classifiés ; les imports DPGF/BPU doivent être normalisés et `COMMITTED`. La mesure de précision/rappel nécessite encore un corpus DCE autorisé et une validation métier externe.
