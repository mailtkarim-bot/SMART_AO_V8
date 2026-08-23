# SMART AO V8 — OPPORTUNITY-WATCH-PROFILE-01

## Positionnement

Après les lots pricing, signature et optimisation, le prochain lot métier prévu par `ROADMAP-01` est S10, la veille et la qualification des opportunités. Ce premier incrément ne contacte pas encore BOAMP et ne crée pas encore de `Case`. Il établit le profil patronal versionné qui explique ce qu’une entreprise recherche.

Le profil est une préférence de veille, pas une preuve DCE, pas une décision commerciale et pas une autorisation de dépôt. Les montants de marché, prix, marges, coûts et données financières sont volontairement hors de ce premier contrat ; ils devront faire l’objet d’un périmètre patronal privé distinct.

## Règles domaine

| Élément | Règle |
|---|---|
| Propriétaire | Un profil appartient à un seul `tenant_id` et ne peut jamais être déplacé. |
| Nom | Texte patronal borné, non vide après normalisation, maximum 120 caractères. |
| État | `ACTIVE` ou `PAUSED`; seul le patron pourra piloter l’état dans un futur adaptateur persistant. |
| Mots-clés | Jusqu’à 32 valeurs, normalisées en minuscules, chacune bornée à 80 caractères. |
| Types de projet | Catalogue fermé : `NEW_BUILD`, `REFURBISHMENT`, `OCCUPIED_SITE`, `TERTIARY`, `HEALTHCARE`, `HOUSING`, `INDUSTRY`, `PUBLIC`, `PRIVATE`, `HERITAGE`. |
| Types d’acheteur | Catalogue fermé : `PUBLIC_BUYER`, `PRIVATE_BUYER`, `SOCIAL_LANDLORD`, `LOCAL_AUTHORITY`, `HEALTHCARE_BUYER`, `INDUSTRIAL_BUYER`, `KNOWN_CLIENT`. |
| Zones | Codes de département bornés, inclusions et exclusions séparées ; une zone exclue ne doit pas être déduite d’une absence d’inclusion. |
| Rayon | Optionnel, entier compris entre 1 et 1 000 kilomètres. |
| Mode de réponse | Catalogue fermé : `SOLO`, `CONSORTIUM`, `SUBCONTRACTING`. |
| Version | Chaque modification produit une nouvelle version et un hash canonique ; aucune version historique n’est écrasée. |

## Frontières

Le profil ne contient ni texte de DCE, ni extrait, ni embedding, ni document, ni secret, ni credential fournisseur. Le profil ne confère aucune capability de lecture BOAMP à un collaborateur et ne détermine pas seul qu’une opportunité est pertinente. Un futur service de scoring devra produire une explication structurée, conserver sa source et rester soumis à une revue patronale.

Le lot suivant pourra persister le profil et exposer une lecture patronale tenant-scoped avec `command_id`, `idempotency_key`, révision optimiste, outbox et audit minimisé. L’ingestion d’avis externes, la déduplication, le scoring et la conversion contrôlée en Case resteront des lots séparés.

## Critères de sortie de ce sous-lot

Le noyau domaine doit être pur, sans FastAPI ni SQLAlchemy. Les tests doivent démontrer la normalisation déterministe, les catalogues fermés, les bornes, l’exclusion des doublons et la stabilité du snapshot canonique. Aucune recette BOAMP réelle n’est requise ni effectuée par ce sous-lot.
