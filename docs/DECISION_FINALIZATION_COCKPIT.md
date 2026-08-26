# Cockpit Decision — finalisation GO/NO-GO

## Objet

Le cockpit patron expose désormais l’action de finalisation d’une Decision `GO_NO_GO` lorsque le contexte courant est `FROZEN`, que la Decision est `PENDING_PATRON`, que son outcome est `UNDECIDED` et qu’un fingerprint serveur est disponible.

Cette surface ne déduit aucun outcome. Le patron choisit explicitement `GO`, `CONDITIONAL_GO` ou `NO_GO` et fournit une justification. Pour `CONDITIONAL_GO`, les conditions restent saisies selon le DTO backend fermé et sont validées par le serveur.

## Protection contre un contexte obsolète

Le read model `GET /api/v1/patron/cases/{case_id}/decision-dossier` fournit `context_fingerprint`, qui est un hash technique du contexte sélectionné. Le frontend le retransmet dans `displayed_fingerprint` à `POST /api/v1/patron/cases/{case_id}/decisions/{decision_id}/go-no-go` avec la révision agrégat affichée.

Le serveur compare le fingerprint et la révision avant toute mutation. Une page ancienne ou un contexte modifié ne peut donc pas finaliser silencieusement une Decision sur des faits différents de ceux affichés.

## Données exposées

Le dossier continue à exclure les montants, marges, prix, contenus documentaires bruts, secrets et données d’infrastructure. Le fingerprint est une preuve technique opaque ; il ne remplace ni la lecture humaine des sources, ni une validation juridique, ni une preuve de conformité.

## Parcours opérateur

Le patron crée ou charge le dossier, gèle le contexte vérifié, relit les inconnus, risques et sources, puis choisit une issue et saisit une justification. Le bouton de finalisation n’apparaît qu’après gel du contexte. Après succès, le dossier est rechargé depuis le serveur afin d’afficher l’état final et la révision courante.

Les erreurs de concurrence, de fingerprint périmé, d’exigence DCE non confirmée ou de décision non prête restent des refus serveur ; le frontend ne les transforme pas en succès local.

## Validation

Le client API est couvert par un test de chemin encodé et de payload comprenant le fingerprint. Le composant est couvert par des tests de visibilité conditionnelle et de soumission. Le backend conserve les tests de route, de projection et de finalisation PostgreSQL. Aucun test ne constitue une validation juridique ou une recette de production.
