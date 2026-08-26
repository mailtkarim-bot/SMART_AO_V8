# Détection des contradictions inter-documents

## Périmètre

Le cockpit Decision expose un détecteur déterministe qui compare les fragments `CCTP` de la version DCE applicable aux lignes `DPGF` et `BPU` issues d’imports `COMMITTED`. Il ne remplace pas une lecture humaine et ne produit ni conformité, ni arbitrage financier, ni conclusion juridique.

Endpoint patronal :

```text
GET /api/v1/patron/cases/{case_id}/document-contradictions?limit=25
```

La lecture est tenant-scoped et case-scoped. Les résultats sont calculés à partir de données persistées et reçoivent toujours le statut `REVIEW_REQUIRED`.
La projection est en lecture seule : elle ne crée pas de mutation métier et ne confirme aucune contradiction sans validation patronale.

## Taxonomie fermée v1

| Code | Déclenchement déterministe | Preuve de comparaison |
|---|---|---|
| `PRICING_UNIT_MISMATCH` | Le fragment CCTP contient explicitement une unité normalisée différente de l’unité de la ligne candidate | `CCTP_EXPLICIT_UNIT_V1` |
| `VARIANT_PRICING_SCOPE_CONFLICT` | Le fragment CCTP interdit explicitement les variantes/options et la ligne candidate contient une variante ou une option | `CCTP_VARIANT_PROHIBITION_V1` |

Le candidat de ligne est d’abord obtenu par le matcher CCTP–DPGF/BPU existant. Une contradiction n’est produite que si un rapprochement déterministe existe ; un élément non rapproché n’est pas présenté à tort comme une contradiction.

## Projection publique

La projection fournit l’identifiant stable du constat, la version DCE, le fragment source et ses offsets UTF-8, une localisation bornée, la ligne DPGF/BPU concernée, la base de comparaison et le statut de revue. Elle ne fournit pas le texte source, la quantité, le prix unitaire ni le total.

Les identifiants stables sont dérivés du tenant, du case, de la version, du fragment, du batch, de la ligne et du type de contradiction. Une même observation rejouée produit donc le même identifiant de constat sans créer d’écriture mutable.

## Limites

Le moteur ne fait pas d’OCR, de recherche sémantique, de lemmatisation, de raisonnement juridique, d’inférence de quantité ou de comparaison financière. Les unités non reconnues sont laissées sans conclusion plutôt que forcées dans une catégorie. La précision et le rappel doivent encore être mesurés sur un corpus DCE autorisé ; aucune mesure réelle n’est déclarée dans ce lot.
