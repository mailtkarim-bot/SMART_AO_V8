# Tickets de refactoring — `usePricingImport`

## Contexte commun

Le hook `web/src/features/pricing/usePricingImport.ts` encapsule désormais les états et l’action de commit d’un batch DPGF/BPU/Excel dans un brouillon financier patronal. Le serveur conserve l’autorité sur le tenant, l’autorisation financière, l’état du batch, la révision optimiste, l’idempotence et la matérialisation des lignes.

Les trois tickets ci-dessous traitent des points d’attention UX et de robustesse identifiés lors de la revue post-merge de la PR #12. Ils ne doivent pas déplacer de règle métier financière vers le frontend.

## PRICING-HOOK-ROBUSTNESS-01 — Empêcher les doubles soumissions concurrentes

**Priorité :** haute. **Type :** refactoring frontend avec tests. **Dépendance :** aucune.

### Problème

Le bouton de commit reste activable pendant l’appel réseau. Un double-clic crée deux requêtes avec deux clés d’idempotence différentes. Le serveur protège correctement les données et rejette la seconde requête selon l’état du batch, mais l’utilisateur peut voir une erreur alors que le premier commit a réussi.

### Solution attendue

Ajouter un état local `pricingImportSubmitting` dans `usePricingImport`, l’exposer au composant `PricingPanel`, désactiver le bouton pendant la requête et garantir sa remise à `false` dans un bloc `finally`. Le serveur reste la seule source de vérité ; le verrou frontend ne remplace ni l’idempotence ni les verrous SQL.

### Critères d’acceptation

1. Une seule invocation réseau est possible tant que le commit courant est en cours.
2. Le bouton indique un état de traitement et est désactivé pendant la requête.
3. L’état revient à `false` après succès, erreur HTTP, conflit de révision ou erreur inattendue.
4. Un rejeu explicite avec la même commande continue d’afficher `REPLAYED` sans créer de ligne supplémentaire.
5. Aucun montant financier ni secret n’est ajouté au frontend.

### Tests requis

Tester le rendu désactivé pendant une promesse non résolue, la libération du verrou après succès et après rejet, ainsi que l’absence de seconde invocation concurrente. Conserver les tests backend d’idempotence et de conflit comme garde serveur.

## PRICING-HOOK-ROBUSTNESS-02 — Distinguer commit confirmé et échec de rechargement

**Priorité :** haute. **Type :** refactoring frontend avec gestion d’erreurs. **Dépendance :** PRICING-HOOK-ROBUSTNESS-01 recommandée mais non obligatoire.

### Problème

Le commit et `onDraftReload()` sont actuellement dans le même bloc `try`. Si le commit serveur réussit puis que la lecture du brouillon échoue, le message affiché indique que le commit a échoué, alors que l’écriture est confirmée.

### Solution attendue

Séparer la phase de commit de la phase de resynchronisation. Après un receipt de commit valide, conserver l’état `COMMITTED` ou `REPLAYED` et afficher un message confirmant l’écriture. Si le rechargement échoue, afficher un avertissement distinct indiquant que le commit est confirmé mais que la lecture doit être relancée. Le contrat de `setMessage` peut être étendu avec un ton `warning` si nécessaire, sans divulguer de données financières.

### Critères d’acceptation

1. Une réponse serveur réussie ne peut jamais être reformulée en « commit échoué » uniquement parce que le rechargement a échoué.
2. Une erreur de commit conserve le message d’erreur métier ou HTTP et ne déclenche pas de faux état de succès.
3. Le receipt `replayed: true` reste présenté comme un rejeu idempotent confirmé.
4. L’utilisateur sait s’il doit relancer la lecture du brouillon.
5. Les erreurs `VERSION_CONFLICT`, `IMPORT_ALREADY_COMMITTED` et `IMPORT_HAS_ERRORS` restent compréhensibles côté interface sans exposer le contenu financier.

### Tests requis

Couvrir séparément : commit refusé, commit accepté puis reload refusé, commit accepté et reload réussi, rejeu accepté puis reload refusé. Vérifier l’état final et le texte du message dans chaque scénario.

## PRICING-HOOK-ROBUSTNESS-03 — Réinitialiser l’état d’affichage lors d’un changement de contexte

**Priorité :** moyenne. **Type :** refactoring d’état frontend avec tests. **Dépendance :** aucune.

### Problème

`pricingImportState` reste à `COMMITTED` ou `REPLAYED` après changement d’affaire, de brouillon ou de batch. L’indication visuelle peut donc décrire l’ancien contexte et induire le patron en erreur, même si aucune donnée serveur n’est corrompue.

### Solution attendue

Réinitialiser l’état d’affichage à `IDLE` lorsqu’un identifiant de dossier, de brouillon ou de batch change. Évaluer explicitement si les révisions saisies doivent aussi être réinitialisées, sans écraser une saisie utilisateur de manière surprenante. La réinitialisation doit être purement UX et ne doit envoyer aucune commande au serveur.

### Critères d’acceptation

1. Changer d’affaire ou de brouillon ne laisse pas l’état `COMMITTED`/`REPLAYED` attaché au nouveau contexte.
2. Changer uniquement un batch remet l’état à `IDLE` sans appeler l’API.
3. Les révisions restent cohérentes avec les valeurs saisies ou sont réinitialisées selon une règle documentée.
4. Aucun effet secondaire réseau n’est déclenché par la réinitialisation.
5. Le composant reste compatible avec le contrat de props existant ou documente tout changement nécessaire.

### Tests requis

Tester chaque changement de contexte séparément, vérifier l’absence d’appel API, et contrôler que l’état initial d’un nouveau contexte est `IDLE`. Ajouter un test de non-régression du commit après réinitialisation.

## Ordre recommandé

Implémenter d’abord `ROBUSTNESS-01`, puis `ROBUSTNESS-02`, et enfin `ROBUSTNESS-03`. Chaque ticket doit être livré par une modification isolée, avec build frontend strict et tests ciblés avant intégration.
