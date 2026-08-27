# ARCH-001 — Port de contexte des capabilities Enterprise

## Objet

Ce sous-lot inverse la dépendance d’un service applicatif Enterprise vers l’infrastructure. Avant l’ajout d’une version immuable d’une capability, `EnterpriseCapabilityService` doit résoudre le `company_id` de la capability dans le tenant de l’acteur afin d’effectuer l’autorisation patronale. Cette résolution passe désormais par le port applicatif `EnterpriseCapabilityContextReader`.

La modification est structurelle : elle ne change ni le contrat HTTP, ni les commandes métier, ni les transitions de domaine. Elle retire au chemin applicatif mutationnel la connaissance du modèle SQLAlchemy utilisé pour la résolution de contexte.

## Contrat applicatif

Le port est défini dans `backend/app/modules/enterprise/application/ports.py` :

```python
class EnterpriseCapabilityContextReader(Protocol):
    def company_id_for_capability(
        self, *, tenant_id: UUID, capability_id: UUID
    ) -> UUID | None: ...
```

Le retour `None` est volontairement ambigu du point de vue HTTP : il permet au service de conserver le comportement `NOT_FOUND_OR_FORBIDDEN` et de ne pas révéler si une capability existe dans un autre tenant.

## Adaptateur d’infrastructure

`SqlAlchemyEnterpriseCapabilityContextReader`, situé dans `backend/app/modules/enterprise/infrastructure/capability_context_reader.py`, implémente le port avec une requête SQLAlchemy minimale qui ne projette que `company_id` et applique simultanément les deux prédicats suivants :

| Invariant | Condition appliquée |
|---|---|
| Isolation tenant | `EnterpriseCapabilityRecord.tenant_id == tenant_id` |
| Identité de la ressource | `EnterpriseCapabilityRecord.id == capability_id` |
| Projection minimale | Sélection de `EnterpriseCapabilityRecord.company_id` uniquement |
| Absence de fuite | `None` est renvoyé si aucun enregistrement ne correspond |

L’adaptateur ouvre et ferme sa session de lecture localement. Il ne réalise aucune mutation et ne contient aucune règle d’autorisation.

## Composition root

Dans `backend/app/bootstrap/application.py`, la composition root construit l’adaptateur SQLAlchemy et l’injecte dans `EnterpriseCapabilityService`. Le service applicatif reçoit donc une abstraction testable, tandis que le choix de SQLAlchemy reste confiné au câblage d’exécution.

Le test DB existant de fondation Enterprise utilise le même adaptateur concret que la production. Un test pur supplémentaire, `backend/tests/architecture/test_enterprise_capability_ports.py`, injecte un fake/mock du port et vérifie que `add_version` :

1. appelle le port avec le `tenant_id` de l’acteur et le `capability_id` de la commande ;
2. autorise la ressource résolue via le `company_id` retourné ;
3. ne dépend pas d’une session ou d’un modèle ORM pour cette résolution ;
4. transmet ensuite la commande au dispatcher.

## Invariants métier préservés

Le service continue de refuser la mutation lorsque la capability n’est pas résolue dans le tenant courant. L’autorisation est toujours évaluée sur le `company_id` propriétaire, et le dispatch de la commande reste le mécanisme qui exécute les validations métier, l’idempotence et la persistance déjà en place.

Le port ne contourne pas les contrôles existants : il ne décide ni de l’état de la capability, ni de la révision attendue, ni de la validité des preuves, ni des droits du rôle. Il ne fait que fournir le contexte propriétaire nécessaire à l’autorisation préalable.

## Validation effectuée

| Contrôle | Résultat |
|---|---|
| Ruff ciblé sur les fichiers Enterprise, bootstrap et tests | Réussi |
| Mypy ciblé sur les quatre fichiers de production | Réussi |
| Test unitaire pur du port | Réussi |
| Test de fondation Enterprise sans marqueur DB | Aucun test exécuté : les six tests de ce fichier sont marqués `db` |
| PostgreSQL local / tests DB | Non revendiqué dans le sandbox courant ; la preuve DB doit venir de la CI configurée |
| VPS, staging, production, fournisseurs externes et secrets | Non concernés et non revendiqués par ce lot |

## Limites et suite

Ce lot ne prétend pas terminer ARCH-001. Les autres imports applicatifs d’infrastructure doivent être mesurés séparément et traités par petits lots, sans élargir cette PR à des changements de contrat. Les validations PostgreSQL, migrations, image de sécurité et intégrations externes restent dépendantes des environnements correspondants et seront rapportées uniquement sur preuve.
