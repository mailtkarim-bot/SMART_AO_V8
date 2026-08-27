# ARCH-001 — Lecteur de projection Enterprise Library

## Objet

Ce micro-lot extrait la lecture de la bibliothèque privée Enterprise du service applicatif vers un port de lecture injecté. `EnterpriseLibraryService.read_company` conserve l’autorisation patronale puis délègue la construction de `EnterpriseCompanyProjection` à `EnterpriseLibraryReader`.

Le service de lecture ne construit plus de requête SQLAlchemy pour cette projection. L’adaptateur `SqlAlchemyEnterpriseLibraryReader`, placé dans `enterprise.infrastructure.library_reader`, porte la connaissance des modèles SQLAlchemy et du détail de la projection.

## Contrat applicatif

Le port est défini dans `backend/app/modules/enterprise/application/ports.py` :

```python
class EnterpriseLibraryReader(Protocol):
    def read_company(self, *, tenant_id: UUID) -> EnterpriseCompanyProjection | None: ...
```

La projection applicative existante reste inchangée. Elle contient les données légales de la société et une collection de `EnterpriseDocumentProjection`, comprenant notamment la dernière vérification connue et sa révision.

Le retour `None` est traduit par le service en `NOT_FOUND_OR_FORBIDDEN`, après l’autorisation. Cette neutralité conserve l’absence de divulgation d’une société appartenant à un autre tenant ou d’une bibliothèque inexistante.

## Responsabilités de l’adaptateur

`SqlAlchemyEnterpriseLibraryReader` applique les invariants de lecture suivants :

| Invariant | Mise en œuvre |
|---|---|
| Isolation tenant | La société et les documents sont filtrés par `tenant_id` |
| Projection privée cohérente | Les documents sont limités à la société résolue du tenant |
| Vérification la plus récente | Sous-requête ordonnée par `revision DESC`, limitée à une ligne |
| Révision de vérification | Maximum des révisions, avec valeur `0` par défaut |
| Ordre déterministe | Documents triés par date de création puis identifiant |
| Aucune mutation | L’adaptateur ne fait que lire et retourne une projection immuable |

Le code de persistance reste également dans les handlers de commandes `create_company` et `register_document`; ce lot ne modifie pas leur comportement mutationnel ni leurs validations de concurrence.

## Composition root et tests

La composition root construit `SqlAlchemyEnterpriseLibraryReader(runtime.session_factory)` et l’injecte dans `EnterpriseLibraryService`. Les fixtures DB du service Library et du private upload utilisent le même adaptateur concret afin de tester le chemin réel de projection.

Les usages internes de `EnterpriseLibraryService` qui ne font qu’appeler `_authorize` peuvent omettre le lecteur, car ils ne lisent pas la projection. En revanche, `read_company` refuse explicitement une configuration sans lecteur avec `ENTERPRISE_LIBRARY_READER_NOT_CONFIGURED`, ce qui évite une lecture silencieusement non câblée.

## Validation effectuée

| Contrôle | Résultat |
|---|---|
| Ruff ciblé | Réussi après réordonnancement automatique des imports |
| Mypy ciblé sur ports, service, adaptateur et bootstrap | Réussi, aucun problème sur 4 fichiers |
| Tests DB Library et private upload en sandbox | Désélectionnés avec `-m not db` : 14 tests DB ; PostgreSQL local absent |
| Suite backend hors DB | À rejouer avant publication de la PR |
| CI GitHub avec PostgreSQL, couverture, Trivy et image-security | À utiliser comme validation complète après push |
| VPS, staging, production, fournisseurs et secrets | Non concernés et non revendiqués |

## Limites

Ce lot n’ajoute ni cache, ni pagination, ni synchronisation de documents, ni validation d’un stockage externe. Il ne revendique pas une recette PostgreSQL locale, une exécution Docker, une disponibilité de fournisseur ou un déploiement. Les éventuels gains de performance et l’absence de N+1 devront être confirmés par profilage dédié.
