# Audit SEC-01 — DCE Requirements Confirmation

**Date :** 14 août 2026.  
**Périmètre :** `DCE-REQUIREMENTS-01` publié (`054054e`) et `DCE-REQUIREMENTS-CONFIRMATION-01` publié sur `main` (`88bf725`), avec correctifs CI (`8efb0ca`, `6bf989a`).  
**Méthode :** revue des contrats, du modèle de menace SEC-01, des modèles SQLAlchemy, des migrations Alembic, de la policy centrale, du transport HTTP, des tests PostgreSQL et des contrôles CI. Cet audit n’est ni une certification ni un test d’intrusion.

## Conclusion exécutive

Le slice de confirmation humaine est maintenant techniquement complet pour sa frontière déclarée. Il conserve l’exigence source inchangée, écrit un registre append-only, reconstruit une projection courante, applique l’idempotence du dispatcher et refuse les acteurs système. La route HTTP utilise le bearer réel et ne reçoit ni tenant, ni acteur, ni rôle, ni capability, ni `case_id` de confiance.

La portée de sécurité est volontairement **DCE-scopée avec résolution transitoire d’une Case active unique**. Le serveur recherche la Case depuis l’exigence et sa DCE avant d’évaluer la ReBAC. Une DCE associée à zéro ou plusieurs Cases actives est refusée avec `COMMAND_REJECTED`; aucune confirmation globale n’est écrite dans ce cas. Cette décision évite un contournement d’affectation, mais devra évoluer vers une exigence Case-scopée avant de permettre à une même DCE de servir plusieurs affaires dans un futur slice.

| Niveau | Constat | État au 14 août 2026 |
|---|---|---|
| Critique | Aucune confirmation humaine ne modifie l’exigence source, ne calcule un prix, ne produit un Go/No-Go ou ne dépose un dossier. | Conforme au périmètre livré. |
| Élevé | La route authentifiée résout le contexte serveur, appelle la façade SEC-01 et applique la policy auditée. | Fermé par code et cinq scénarios API PostgreSQL. |
| Élevé | Les succès de confirmation sont écrits par `SecurityAuditWriter` dans la transaction du handler, avec receipt, événement métier et outbox. | Fermé pour ce slice. Les succès génériques d’autres mutations restent hors de cette remédiation. |
| Élevé | Les refus de policy sont audités par `AuditedAuthorizationPolicy`; les refus manuels système, hors tenant et `NOT_APPLICABLE` collaborateur sont également écrits par la façade. | Fermé pour ce slice. |
| Moyen | Les données restent `INTERNAL_OPERATIONAL`; les DTO HTTP sont fermés et n’exposent ni document source ni donnée financière. | Conforme par modèle, contrat et tests de transport. |
| Moyen | Les outils `detect-secrets`, `pip-audit` et `bandit` sont intégrés à la CI. Le scan d’image est conditionné à l’existence d’un `Dockerfile`. | Fermé pour le dépôt actuel; aucun Dockerfile n’existe encore, donc aucun scan d’image ne peut honnêtement être présenté comme exécuté. |

## Contrôles vérifiés

| Exigence SEC-01 | Preuve observée | Verdict |
|---|---|---|
| Isolation tenant et FK composites | Les tables de confirmation portent `tenant_id`; les relations vers l’exigence et le tenant sont composites; la route résout l’exigence dans le tenant authentifié. | Conforme. |
| Portée Case sans confiance client | `DceRequirementConfirmationService` recherche la DCE de l’exigence puis au maximum deux Cases actives correspondantes. Il autorise uniquement le cardinal `1`; toute autre cardinalité est rejetée. | Conforme avec réserve d’évolution Case-scopée documentée. |
| Acteur humain obligatoire | Le service et le handler refusent `SYSTEM`; le refus est audité lorsque l’appel arrive par le périmètre de service. | Conforme. |
| Capability, classification et affectation | `AuditedAuthorizationPolicy` reçoit `dce.requirement.confirm`, `DCE_REQUIREMENT`, `INTERNAL_OPERATIONAL` et la `case_id` résolue. Un collaborateur sans affectation active est refusé. | Conforme. |
| Séparation patron/collaborateur | Un collaborateur affecté peut confirmer ou demander une revue; `NOT_APPLICABLE` est refusé et audité. Le patron peut produire `NOT_APPLICABLE` avec le motif fermé requis. | Conforme pour ce slice. |
| Historique non destructif | `dce_requirement_confirmations` est protégé par trigger PostgreSQL contre `UPDATE` et `DELETE`; la projection courante ne remplace jamais le registre historique. | Conforme. |
| Révision et idempotence | Le handler verrouille l’exigence et la projection; il refuse les révisions obsolètes. Le dispatcher protège `(tenant_id, actor_id, command_type, idempotency_key)` et rejoue le receipt. | Conforme par code existant et régression. |
| Minimisation event/outbox | L’événement métier transporte uniquement les identifiants, outcome, motif, révision et compteurs. Aucun extrait, texte source, document ou montant n’est sérialisé. | Conforme par contrat et modèle. |
| Audit minimisé | `SecurityAuditWriter` impose l’allow-list de métadonnées et valide action, motif, pseudonymes et types. Le succès porte `AUTHZ_SUCCEEDED`; les refus portent `AUTHZ_DENIED`. | Conforme. |
| Réponses HTTP neutres | Absence de bearer : `401`; ressource hors tenant : `404 NOT_FOUND_OR_FORBIDDEN`; conflit d’idempotence : `409`; rejet métier ou portée ambiguë : `422 COMMAND_REJECTED`; refus de policy : `403 FORBIDDEN`. | Conforme. |
| Confidentialité financière | Le contrat et les DTO de confirmation ne portent aucun prix, marge, devis, trésorerie, credential, token ou document complet. | Conforme pour ce slice. |

## Écarts SEC-REQC et décisions de fermeture

| ID | Écart initial | Remédiation livrée | Preuve | Verdict |
|---|---|---|---|---|
| `SEC-REQC-01` | Capability et route authentifiée manquantes; tests patron/collaborateur absents. | Capability `dce.requirement.confirm`, route `POST /api/v1/dce-requirements/{requirement_id}/confirmations`, contexte bearer réel et scénarios patron, collaborateur sans affectation, collaborateur `NOT_APPLICABLE`. | `backend/app/interfaces/http/routes/dce_requirement_confirmations.py`; `backend/tests/api/test_dce_requirement_confirmation_api.py`. | **Fermé.** |
| `SEC-REQC-02` | Audit transactionnel du succès et des refus manuels absent. | `SecurityAuditWriter` est appelé dans la transaction du handler pour le succès; la façade écrit les refus système, hors tenant et `NOT_APPLICABLE` collaborateur. | `handlers.py`, `requirement_confirmation.py`; audit API PostgreSQL. | **Fermé pour le slice.** |
| `SEC-REQC-03` | La Case n’était pas contrôlée côté serveur. | Résolution tenant-scopée de l’exigence vers sa DCE puis vers une Case active unique; cardinalité ambiguë refusée; la Case n’est jamais acceptée du corps HTTP ni persistée dans la confirmation. | Contrat normatif mis à jour; tests inter-tenant et multi-Case. | **Fermé pour la frontière actuelle.** |
| `SEC-REQC-04` | Les autorisations réussies n’étaient pas enregistrées. | Ajout de `AUTHZ_SUCCEEDED` au vocabulaire et au modèle; audit succès transactionnel de la mutation de confirmation. Migration additive `0018`. | `audit.py`, `models.py`, `20260814_0018_security_audit_authorization_success.py`; test de succès audité. | **Fermé pour ce slice.** |
| `SEC-REQC-05` | Migration `0017` non publiée et non intégrée à la validation finale. | Migration `0017` conservée pour le registre; migration `0018` ajoutée pour le vocabulaire d’audit. Cycle `upgrade head`, `alembic check`, `downgrade base` exécuté avec succès, puis publication sur `main`. | Migrations `0017` et `0018`; workflow GitHub vert #31794051057. | **Fermé et publié.** |
| `SEC-REQC-06` | Contrôles secrets, dépendances, SAST et image absents de la CI. | CI ajoutée pour `detect-secrets-hook`, export uv + `pip-audit --strict`, `bandit -ll` et job Trivy conditionnel lorsqu’un Dockerfile existe. | [Workflow GitHub vert #31794051057](https://github.com/mailtkarim-bot/SMART_AO_V8/actions/runs/31794051057). | **Fermé pour l’état actuel; scan image non exécuté faute de Dockerfile.** |

## Validation exécutée

| Contrôle | Résultat |
|---|---|
| `uv run ruff check .` | Vert. |
| `uv run pytest backend/tests -q` | **219 tests verts**; trois avertissements de dépendance ou de constante HTTP dépréciée, sans échec. |
| `uv run alembic upgrade head` | Vert jusqu’à `20260814_0018`. |
| `uv run alembic check` | `No new upgrade operations detected.` |
| `uv run alembic downgrade base` | Vert. |
| `detect-secrets-hook --baseline .secrets.baseline` sur les fichiers Git | Vert. |
| Export uv de production puis `pip-audit --strict` | Aucune vulnérabilité connue détectée. |
| `bandit -q -r backend/app -ll` | Vert. |
| Scan d’image | Non exécuté : aucun `Dockerfile` dans le dépôt; le job CI conditionnel est prêt pour le futur artefact. |

## Décision de sécurité

> **Décision : `DCE-REQUIREMENTS-CONFIRMATION-01` est publié sur `main` et sa CI GitHub est verte. Le slice peut servir de base au prochain incrément, sous réserve de conserver sa limite de portée Case documentée.**

Cette autorisation ne constitue ni une certification de sécurité, ni une garantie d’absence de vulnérabilité, ni une validation juridique des réponses à un appel d’offres. Elle confirme uniquement que la frontière livrée respecte les invariants SEC-01 documentés et qu’elle est testée dans l’environnement PostgreSQL local décrit par le dépôt.

Le prochain risque métier important est la modélisation d’une exigence réellement Case-scopée pour les DCE partagées par plusieurs affaires. Ce risque est volontairement bloqué dans le slice courant au lieu d’être masqué par une sélection arbitraire.
