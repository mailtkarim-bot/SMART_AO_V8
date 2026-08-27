# ARCH-001 — Contrat applicatif du registre Enterprise

## Objet

Ce micro-lot poursuit l’inversion des dépendances du module Enterprise pour la recherche read-only de société par SIREN. Le service applicatif `EnterpriseRegistryLookupService` ne dépend plus de `app.modules.enterprise.infrastructure.insee_registry` pour ses types. Le contrat `CompanyRegistryPort` et la projection `RegisteredCompany` résident désormais dans `backend/app/modules/enterprise/application/ports.py`.

L’adaptateur `InseeSireneRegistry` reste dans l’infrastructure et implémente ce contrat. La composition root importe le port depuis l’application et l’implémentation depuis l’infrastructure, ce qui maintient le câblage hors des services applicatifs.

## Contrat et projection

`CompanyRegistryPort` expose une seule opération :

```python
find_by_siren(*, siren: str) -> RegisteredCompany | None
```

`RegisteredCompany` est une projection bornée et non sensible :

| Champ | Type | Rôle |
|---|---|---|
| `siren` | `str` | SIREN normalisé à neuf chiffres |
| `legal_name` | `str | None` | Dénomination légale retournée par la source |
| `active` | `bool | None` | État administratif traduit en valeur bornée |
| `activity_code` | `str | None` | Code d’activité projeté |
| `source` | `str` | Source explicitement allowlistée, par défaut `INSEE_SIRENE` |

Le service applicatif ne connaît ni HTTPX, ni l’URL SIRENE, ni les codes de statut externes, ni les détails du payload INSEE.

## Compatibilité et câblage

L’adaptateur importe maintenant le contrat depuis la couche application. Les symboles sont toujours importés dans le module d’infrastructure afin de ne pas casser les consommateurs de test existants qui les importent depuis `insee_registry`; cette compatibilité ne réintroduit pas de dépendance infrastructure dans le service applicatif.

Dans `backend/app/bootstrap/application.py`, `CompanyRegistryPort` est importé depuis `enterprise.application.ports` et `InseeSireneRegistry` depuis `enterprise.infrastructure.insee_registry`. La construction de `EnterpriseRegistryLookupService` reste réalisée dans la composition root.

## Invariants préservés

La validation du SIREN, la projection allowlistée, le traitement des réponses `404`, les erreurs externes bornées et la politique d’autorisation patronale restent inchangés. Le lot ne persiste aucune donnée et ne transforme pas une recherche externe en décision métier.

L’intégration INSEE réelle, la présence d’un token, les limites de fournisseur et la disponibilité réseau ne sont pas revendiquées par les tests locaux. Les tests utilisent un client HTTP contrôlé et des doubles de registre ; aucune recette fournisseur réelle n’est déduite de ce lot.

## Validation effectuée

| Contrôle | Résultat |
|---|---|
| Ruff ciblé sur ports, service, adaptateur, bootstrap et tests | Réussi |
| Mypy ciblé sur les quatre fichiers de production | Réussi |
| Tests API du registre patronal et tests de l’adaptateur INSEE | `16 passed` |
| PostgreSQL, Docker, VPS, staging et production | Non concernés et non revendiqués |
| Fournisseur INSEE réel, secrets et quotas | Non validés dans cet environnement |

## Limites

Ce changement ne constitue pas une validation juridique, commerciale ou fournisseur de la donnée SIRENE. Il ne met pas en place de cache distribué, de résilience réseau supplémentaire ou de synchronisation de sociétés. Ces sujets restent séparés de l’inversion de dépendances.
