# Taxonomie des clauses de risque CCAP/CCTP

## Périmètre

L’analyseur RC détecte désormais sept familles de signaux contractuels sur les fragments extraits dont la classification courante est `CCAP` ou `CCTP`. Les observations restent des **signaux de source** : elles ne constituent pas une qualification juridique, une décision de conformité ou une décision d’attribution.

Chaque observation conserve le mécanisme existant de preuve : `fragment_id`, extrait borné, offsets UTF-8 exacts, `rule_id` versionné et directive `REQUIRED_SIGNAL`, `OPTIONAL_SIGNAL` ou `UNSPECIFIED` déduite du voisinage textuel. L’analyse système est idempotente ; la version de l’analyseur passe à `2` pour empêcher la réutilisation silencieuse des résultats produits par la version précédente.

## Taxonomie fermée

| Code | Domaine | Règle |
|---|---|---|
| `CCAP_PENALTIES` | Pénalités | `CCAP_DELAY_PENALTIES_V1` |
| `CCAP_RETENTION_GUARANTEE` | Retenue de garantie | `CCAP_RETENUE_GARANTIE_V1` |
| `CCAP_GUARANTEE` | Cautionnement et garantie financière | `CCAP_CAUTIONNEMENT_V1` |
| `CCAP_INSURANCE` | Assurances responsabilité, décennale ou dommages | `CCAP_ASSURANCE_V1` |
| `CCTP_VARIANTS` | Variantes, options et prestations supplémentaires | `CCTP_VARIANTES_OPTIONS_V1` |
| `CCAP_SUBCONTRACTING` | Sous-traitance, acte spécial et DC4 | `CCAP_SOUS_TRAITANCE_V1` |
| `CCAP_QUALIFICATIONS` | Qualifications, certifications, habilitations et agréments | `CCAP_QUALIFICATIONS_V1` |

Les catégories sont portées par la contrainte SQL fermée de `dce_rc_requirement_observations`. Lorsqu’elles sont matérialisées dans `dce_requirements`, elles utilisent le type fermé `CONTRACT_RISK_SIGNAL` et restent en `PENDING_HUMAN_CONFIRMATION` / `SOURCE_SIGNAL_ONLY`.

## Sécurité et limites

La détection est limitée au tenant et à la version DCE analysée. Les règles contractuelles ne s’exécutent pas sur des documents non classifiés ou classifiés `RC`. Les résultats sont append-only via les tables existantes d’analyse et de sources.

Le moteur est lexical et déterministe. Il ne réalise ni OCR, ni recherche sémantique, ni résolution de synonymes, ni interprétation de seuils, ni calcul de retenue ou de pénalité. La présence d’un signal exige une revue humaine. La précision et le rappel devront être mesurés ultérieurement sur un corpus DCE autorisé ; aucune mesure de corpus réel n’est déclarée ici.
