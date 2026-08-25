# Contrat du worker de bus d’événements externe

## Périmètre

Le worker `app.workers.opportunity_event_bus` publie uniquement les notifications BOAMP déjà écrites dans l’outbox transactionnelle. Il ne fait pas de polling Manus, ne transforme pas une observation en `Case` et ne transporte pas de titre, de document, de contenu DCE, de champ financier ou de credential métier.

Le worker est **désactivé par défaut**. Il ne peut être activé que par `SMART_AO_EXTERNAL_EVENT_BUS_ENABLED=1`, avec une URL HTTPS et un token injectés hors Git. Le service Compose préproduction est placé derrière le profil `external-bus`; il n’est donc pas démarré par la stack ordinaire.

## Topics autorisés

| Topic | Payload exact |
|---|---|
| `opportunity.boamp.ingestion.recorded` | `ingestion_run_id`, `observation_count`, `request_hash` |
| `opportunity.boamp.qualification.recorded` | `qualification_id`, `observation_id`, `decision`, `reason_code` |

Tout autre topic, toute clé supplémentaire, toute clé manquante ou toute décision inconnue est rejeté et enregistré en retry. Les valeurs d’identifiants et de hash sont transmises sous forme de chaînes ; le hash d’ingestion doit contenir 64 caractères hexadécimaux dans le payload produit par le repository.

## Enveloppe externe

L’adaptateur générique `HttpExternalEventBus` envoie une requête `POST` JSON canonique :

```json
{
  "event_id": "<UUID>",
  "payload": {},
  "tenant_id": "<UUID>",
  "topic": "<topic-allowlisté>"
}
```

Le corps est sérialisé avec des clés triées et des séparateurs compacts. L’adaptateur ajoute `Content-Type: application/json`, un identifiant d’agent, `Authorization: Bearer <token>` et `X-SMART-AO-Signature: sha256=<HMAC-SHA256>`. Le HMAC porte sur les octets bruts du corps et utilise le token runtime comme secret partagé.

Le fournisseur doit reconnaître `event_id` comme clé de déduplication. Le modèle de livraison est **at-least-once** : une panne après réception fournisseur mais avant confirmation locale peut provoquer un rejeu. Le fournisseur doit donc rendre le traitement idempotent par `event_id` et conserver le topic/payload reçus pour son audit propre.

## Accusé et transitions

Seul un statut HTTP `2xx` est considéré comme un accusé de livraison. Après cet accusé, le worker passe le message à `PUBLISHED`, renseigne `published_at` et efface la prochaine échéance. Une erreur réseau, un timeout, une réponse non-`2xx`, une configuration absente ou un payload invalide conserve le message en `RETRY` avec compteur, échéance de backoff et code d’erreur. Un message ne doit jamais passer à `PUBLISHED` en mode désactivé ou dry-run.

La claim PostgreSQL utilise `FOR UPDATE SKIP LOCKED`, une lease et un batch borné. Les tentatives sont espacées par un backoff exponentiel plafonné à une heure. Le worker ne supprime pas les notifications et ne contourne pas l’append-only des événements métier.

## Activation contrôlée

Exemple de variables hors dépôt :

```bash
export SMART_AO_EXTERNAL_EVENT_BUS_ENABLED=1
export SMART_AO_EXTERNAL_EVENT_BUS_URL='https://bus.example.invalid/v1/events'
export SMART_AO_EXTERNAL_EVENT_BUS_TOKEN='secret-injecte-par-le-secret-manager'
```

La recette réelle est bloquée tant que le fournisseur n’a pas communiqué son endpoint, son schéma d’authentification, sa politique de déduplication, ses codes de réponse, ses limites de débit, son délai de conservation et son mécanisme de replay. Aucun SDK Kafka/RabbitMQ ni nom de fournisseur n’est inventé dans le dépôt.

## Critères de recette fournisseur

Avant activation en préproduction, l’opérateur doit vérifier, avec des événements synthétiques non sensibles et un tenant de test :

1. validation de la signature HMAC et du rejet d’une signature altérée ;
2. acceptation des deux topics et rejet de tout topic hors allowlist ;
3. déduplication d’un même `event_id` envoyé deux fois ;
4. réponse `2xx` suivie d’une seule transition locale à `PUBLISHED` ;
5. panne/timeout suivi de `RETRY`, puis reprise après backoff ;
6. absence de secret, titre, document ou donnée financière dans la trace et le payload ;
7. vérification des métriques, logs structurés et de la capacité de replay opérateur.

Ces critères sont une antenne de raccordement. Ils ne constituent pas une preuve d’exécution tant qu’un fournisseur réel et un environnement contrôlé ne sont pas disponibles.
