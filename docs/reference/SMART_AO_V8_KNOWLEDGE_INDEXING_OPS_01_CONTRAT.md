# SMART_AO V8 — KNOWLEDGE-INDEXING-OPS-01

## 1. Objet

Ce contrat définit l’antenne opérateur one-shot pour indexer les fragments d’une version DCE admise dans le registre local de retrieval BGE. Il ne crée pas de nouvelle route HTTP utilisateur, ne déclenche pas automatiquement l’indexation après admission et ne transforme pas un score de retrieval en preuve métier.

Le slice est conçu pour être exécuté plus tard sur une machine disposant de PostgreSQL, de l’image backend et d’un cache local BGE préchargé. Le sandbox peut valider les contrats et les tests, mais ne constitue pas une preuve de disponibilité du modèle, de Docker ou d’un corpus DCE réel.

## 2. Frontière de sécurité

L’indexation est autorisée uniquement lorsque les deux flags runtime suivants valent explicitement `1` ou une valeur booléenne reconnue :

```text
SMART_AO_RAG_ENABLED=1
SMART_AO_RAG_INDEXING_ENABLED=1
```

Le premier flag autorise la capacité RAG de lecture. Le second constitue un opt-in séparé pour l’écriture d’embeddings. En leur absence, ou si leur valeur est ambiguë, le worker s’arrête avant toute connexion à la base.

Le modèle est chargé avec `SMART_AO_BGE_LOCAL_FILES_ONLY=1` par défaut. La recette cible doit donc précharger le modèle dans le volume de cache et exécuter `scripts/verify_bge_model_cache.py` avant l’indexation. Aucun téléchargement implicite ne doit être utilisé pour une donnée DCE.

Le worker reçoit un tenant, une Case et une version DCE par arguments UUID. La source SQLAlchemy existante limite la lecture aux fragments `COMPLETED` de la version applicable à la Case et du tenant indiqué. Les embeddings restent append-only et idempotents par fragment, modèle et hash du texte ; un contenu différent pour une identité existante provoque un échec, jamais un écrasement.

## 3. Commande opérateur

Le wrapper vérifie le nombre et le format des UUID, exige un fichier `ops/.env.preprod` de mode `0600`, puis lance le backend en mode one-shot :

```bash
ops/run-knowledge-embeddings-preprod.sh \
  TENANT_ID CASE_ID DCE_VERSION_ID
```

Le wrapper utilise `docker compose run --rm --no-deps backend`. Il n’ouvre aucun port, ne démarre aucun service permanent et n’ajoute aucune adresse de destinataire ou credential externe. Le volume BGE est monté en lecture seule par le service backend préproduction.

## 4. Sortie autorisée

La sortie JSON technique peut contenir uniquement :

```json
{
  "status": "ok",
  "indexed_count": 0,
  "tenant_id": "uuid",
  "case_id": "uuid",
  "dce_version_id": "uuid",
  "model_id": "BAAI/bge-m3"
}
```

Elle ne doit contenir ni texte de fragment, ni extrait, ni locator détaillé, ni embedding, ni montant, ni contenu financier. Le nombre zéro est valide lorsque la version ne possède encore aucun fragment `COMPLETED`.

## 5. Erreurs et arrêt fermé

Le worker doit s’arrêter avec une erreur explicite et sans indexation lorsque :

| Condition | Comportement |
|---|---|
| `SMART_AO_RAG_ENABLED` désactivé ou ambigu | Arrêt avant connexion à la base. |
| `SMART_AO_RAG_INDEXING_ENABLED` désactivé ou ambigu | Arrêt avant connexion à la base. |
| Cache BGE absent ou extra non installé | Échec sans fallback distant implicite. |
| UUID invalide dans le wrapper | Refus opérateur avec code d’usage. |
| Fichier env absent ou non protégé | Refus opérateur avec code de configuration. |
| Version DCE étrangère, non applicable ou non extractée | Aucun fragment lu; aucune écriture hors du tenant. |
| Embedding déjà existant avec un hash ou vecteur différent | Échec d’identité; aucune mutation de la ligne existante. |

Une erreur d’indexation ne doit pas être présentée comme une preuve de disponibilité du RAG. La décision de relancer, de changer de modèle ou d’activer un déclenchement automatique appartient à une revue séparée.

## 6. Preuves requises hors sandbox

Avant activation sur une machine réelle, l’opérateur doit conserver :

1. le hash de l’image backend et l’identifiant exact du modèle ;
2. la sortie de vérification du cache BGE sans téléchargement ;
3. un corpus DCE anonymisé, non financier ou explicitement autorisé ;
4. le nombre de fragments lus et indexés, sans conserver de texte dans les logs ;
5. une mesure de durée, CPU, mémoire et taille de l’index ;
6. un contrôle tenant/Case/version et un test de rejeu idempotent ;
7. un benchmark de précision et de latence comparant la baseline structurée ;
8. une revue humaine avant toute utilisation d’un résultat dans une décision ou un calcul.

Ces preuves ne sont pas exécutées par ce slice dans le sandbox. Le déclenchement automatique après admission reste interdit tant qu’elles ne sont pas réunies et qu’un contrat d’orchestration dédié n’a pas été approuvé.

## 7. Statut

Le code, le wrapper, les flags et les tests de contrat sont implémentés localement. Le modèle BGE réel, Docker, le corpus réel, la mesure de performance et la recette de production restent à exécuter sur l’environnement cible.
