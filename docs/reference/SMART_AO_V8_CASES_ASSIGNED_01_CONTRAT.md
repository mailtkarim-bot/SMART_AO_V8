# SMART_AO V8 — CASES-ASSIGNED-01

## Objet

Exposer une collection d’affaires strictement filtrée par le contexte authentifié serveur afin que l’espace collaborateur puisse choisir une Case sans connaître ni deviner un identifiant.

## Route

`GET /api/v1/cases/assigned`

La route exige un bearer JWT valide. Elle résout le tenant, le membership, le rôle, les capabilities et les scopes d’affectation côté serveur. Aucun `tenant_id`, rôle, membership, scope ou filtre d’autorisation fourni par le navigateur n’est accepté.

## Règle ReBAC

Pour un collaborateur, une Case est projetée uniquement si une affectation serveur active existe pour le membership courant, que sa fenêtre temporelle est valide, que son scope contient `case.dce.read` et que sa classification contient `INTERNAL_OPERATIONAL`. Une affectation sans capability, expirée, suspendue ou sans classification autorisée ne produit aucune ligne.

Le patron administrateur conserve sa visibilité tenant-scopée selon la policy SEC-01 déjà publiée. Les autres acteurs restent soumis au deny-by-default. Une Case d’un autre tenant est indiscernable d’une Case inexistante.

## Projection publique fermée

Chaque élément peut contenir uniquement : `case_id`, `work_label`, `case_lifecycle`, `commercial_stage` et `dce_availability`. La projection exclut `tenant_id`, `functional_identity_hash`, `scope_json`, `scope_fingerprint`, `object_description` détaillée, affectation, acteur, prix, marge, budget, décision, stockage, hash, URL, audit et contenu DCE.

La collection est triée de manière déterministe par `updated_at DESC`, puis `id ASC`. Une collection vide est une réponse `200 []`, jamais une erreur et jamais une indication sur l’existence de Cases hors périmètre.

## Contrat CSRF navigateur

Le cookie refresh reste `HttpOnly`, `Secure`, `SameSite=Lax`. Le cookie CSRF reste lisible par le navigateur, `Secure`, `SameSite=Strict`, mais son chemin devient `/` afin que le frontend servi sous `/` puisse lire sa valeur et la renvoyer dans `X-CSRF-Token` vers `/api/v1/auth/refresh` et `/api/v1/auth/logout`. Le serveur continue de comparer strictement cookie et en-tête ; élargir le chemin ne supprime pas le double-submit.

## Critères de fermeture

Le slice est fermé lorsque la route est branchée au même `AuthenticationContextResolver` et à la même `AuditedAuthorizationPolicy` que la lecture Case individuelle, que les tests patron/collaborateur/refus inter-tenant/non-fuite passent, et que les tests navigateur prouvent le refus CSRF puis le succès de refresh et logout avec le cookie de chemin `/`.
