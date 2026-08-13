# SMART_AO V8 — Contrat Métier vers Interface : Espace collaborateur

**Version :** 1.0  
**Statut :** référence de conception à valider avant la matrice de transitions collaborateur  
**Périmètre :** interface de travail des collaborateurs affectés à une affaire ; préparation DCE, analyse, preuves, documents, mémoire technique, demandes et transmission au patron.  
**Hors périmètre :** décision Go/No-Go, prix, marge, trésorerie, validation finale de risque et dépôt.

---

## 1. Objet du contrat

Ce contrat traduit le cahier métier collaborateur en exigences vérifiables d’interface. Il fixe, pour chaque vue, la question métier à laquelle SMART_AO répond, les données visibles, leur origine, les états, les actions autorisées, les contrôles, les erreurs et la provenance.

Il ne définit pas encore les tables, les APIs ou le code. Il empêche cependant toute interface qui laisserait le collaborateur travailler sur une affaire non attribuée, confondrait une suggestion avec une preuve, ou transmettrait au patron un dossier dont le contenu n’est pas clairement figé.

> **Question centrale de l’espace collaborateur :** « Quel travail préparatoire dois-je accomplir maintenant, avec quelles sources, pour remettre au patron une affaire honnête, exploitable et traçable ? »

---

## 2. Règles contractuelles communes

### 2.1. Contrat de toute vue collaborateur

Chaque vue collaborateur doit pouvoir répondre aux questions suivantes.

| Élément contractuel | Exigence |
|---|---|
| **Question métier** | Une seule question principale, affichée ou immédiatement compréhensible. |
| **Affaire et affectation** | La vue indique toujours l’affaire, le lot/périmètre et l’affectation qui autorise la consultation. |
| **Données visibles** | Les données appartiennent au périmètre de l’affectation active ; aucune donnée prix/marge/trésorerie ne doit être chargée. |
| **Provenance** | Toute donnée issue du DCE, d’un document, d’un partenaire ou d’un collaborateur indique sa source ou son auteur. |
| **Fraîcheur** | Toute donnée sensible au temps affiche sa date/version : DCE, pièce, échéance, disponibilité, attestation, réponse partenaire. |
| **État** | La vue distingue `à jour`, `partielle`, `à vérifier`, `obsolète`, `en attente`, `bloquée` et `indisponible`. |
| **Action principale** | Une seule action de progression est mise en avant. Les autres actions sont secondaires et expliquées. |
| **Sauvegarde** | Brouillon et dernière sauvegarde sont visibles lorsqu’il y a saisie. |
| **Erreur** | L’erreur explique ce qui manque, pourquoi cela compte et comment la résoudre. |
| **Historique** | Le collaborateur peut voir les faits liés à son périmètre, sans accéder au journal patron confidentiel. |

### 2.2. Natures d’information visibles

Une même interface ne doit jamais confondre une donnée source, une interprétation ou une décision.

| Nature | Présentation attendue | Exemple |
|---|---|---|
| **Fait sourcé** | Source DCE, pièce entreprise, réponse partenaire ou constat nommé. | « Visite obligatoire » — RC p. 8. |
| **Calcul** | Valeur calculée avec entrées affichables. | Date interne calculée à partir de la date de dépôt. |
| **Constat / analyse** | Observation SMART_AO ou collaborateur, à vérifier si nécessaire. | « Deux pièces semblent contradictoires ». |
| **Suggestion** | Proposition non engageante, avec cause. | « Demander une clarification à l’acheteur ». |
| **Tâche / demande** | Travail ou information attendue, responsable et échéance. | « Obtenir attestation à jour ». |
| **Décision patron** | Résumé éventuellement partagé par le patron. | « Retour demandé : compléter les références ». |

### 2.3. États communs

| État d’information | Sens | Effet par défaut |
|---|---|---|
| **Confirmée** | Source ou revue suffisante. | Peut soutenir une preuve ou la préparation. |
| **À vérifier** | Incertitude, ambiguïté ou relecture nécessaire. | Crée/recommande une tâche ou une revue. |
| **Manquante** | Pièce, donnée ou preuve absente. | Reste explicite ; jamais remplie par défaut. |
| **Contradictoire** | Deux sources incompatibles. | Exige comparaison ou question. |
| **Expirée** | Document/capacité hors validité. | Ne peut pas être présenté comme preuve actuelle. |
| **Non applicable** | Non concernée avec motif et source. | Sort de la checklist sans disparaître. |

Les alertes sont distinctes : `urgent`, `bloquant`, `à risque`, `à surveiller`. Un fait peut être confirmé et urgent ; un document manquant peut ne pas bloquer le travail.

---

## 3. Vue C-01 — Mon travail aujourd’hui

### 3.1. Question métier

> « Quelle affaire et quelle tâche dois-je traiter en priorité, et qu’est-ce qui attend mon intervention ? »

### 3.2. Données visibles

| Zone | Données | Source de vérité |
|---|---|---|
| **À faire maintenant** | Recommandation de prochaine tâche, affaire, lot, motif de priorité, échéance, dépendances bloquantes. | Tâches actives, dépendances, état d’affaire et affectation. |
| **Mes affaires actives** | Affaires affectées, rôle/responsabilités, étape visible, prochaine tâche, date limite et transmission. | Affectations actives + situation préparée collaborateur. |
| **En attente de moi** | Retours patron, demandes, revues, réponses partenaires ou rectificatifs à traiter. | Demandes, revues, transmissions, versions DCE. |
| **Mes tâches** | Compteurs par état : aujourd’hui, semaine, bloquantes, en attente. | Tâches dont le collaborateur est responsable. |
| **Activité récente** | Faits autorisés sur les affaires affectées. | Historique filtré par affectation. |

### 3.3. Boutons et actions

| Bouton | Précondition | Résultat attendu | Erreur explicite possible |
|---|---|---|---|
| `Ouvrir la tâche` | Affectation active et tâche visible. | Ouvre C-05 avec contexte. | « Cette affectation a été retirée ou expirée. » |
| `Voir l’affaire` | Affectation active. | Ouvre C-03. | « Vous n’avez plus accès à cette affaire. » |
| `Voir mes attentes` | Au moins une attente visible. | Filtre C-06 sur demandes/retours. | Aucun. |
| `Signaler un blocage` | Tâche ouverte. | Ouvre le formulaire de blocage lié à la tâche. | « Décrivez l’information ou la dépendance manquante. » |
| `Voir toutes mes affaires` | Aucun. | Ouvre C-02. | Aucun. |

La recommandation « À faire maintenant » est une lecture calculée ; elle ne crée jamais une tâche et ne modifie pas l’ordre réel des tâches.

---

## 4. Vue C-02 — Mes affaires

### 4.1. Question métier

> « Sur quelles affaires suis-je affecté, quel est mon périmètre et laquelle nécessite mon travail ? »

### 4.2. Liste et filtres

| Colonne | Valeur | Règle de présentation |
|---|---|---|
| Affaire | Objet, acheteur, lot/périmètre. | Aucun prix, aucune marge. |
| Mes responsabilités | Analyse, visite, pièces, mémoire, contrôle documentaire, etc. | Issues de l’affectation. |
| État de préparation | Préparation, à revoir, prête à transmettre, transmise, retour demandé. | État de travail, pas un verdict financier. |
| Prochaine tâche | Tâche ou recommandation calculée. | Toujours distinguée de la tâche elle-même. |
| Échéance | Date acheteur confirmée ou date interne libellée. | Source/version accessible. |
| Blocage | Résumé de la cause, sans détails confidentiels. | Affiche seulement les blocages de périmètre. |
| Transmission | En préparation, transmise, reçue, retournée, acceptée pour phase suivante. | N’ouvre pas le prix privé. |

Filtres obligatoires : `actives`, `à faire aujourd’hui`, `bloquées`, `à revoir`, `en attente de moi`, `en attente du patron`, `à transmettre`, `archivées`.

### 4.3. Actions

| Bouton | Effet |
|---|---|
| `Ouvrir` | Ouvre C-03 si l’affectation est active. |
| `Demander clarification du périmètre` | Crée une demande au patron sans élargir les droits. |
| `Signaler indisponibilité` | Alerte le patron sur une échéance ou une réattribution nécessaire. |
| `Voir mes tâches` | Ouvre C-05 filtré sur l’affaire. |

---

## 5. Vue C-03 — Espace de préparation d’une affaire

### 5.1. Question métier

> « Où en est mon travail sur cette affaire, qu’est-ce qui reste à faire et quelle étape mérite mon attention ? »

Cette vue est le point d’entrée de l’affaire. Les sept étapes visibles sont une **projection du travail** ; elles n’imposent pas une séquence rigide au domaine.

```text
[Documents] — [Exigences] — [Terrain & capacités] — [Pièces]
[Réponse technique] — [Contrôle] — [Transmission]
```

### 5.2. Bandeau d’affaire

| Information | Source | Action disponible |
|---|---|---|
| Objet, acheteur, lot, rôle collaborateur. | Affaire + affectation. | Voir le périmètre. |
| Date limite et état de confirmation. | Exigence DCE sourcée. | Voir source. |
| Version DCE analysée. | Version DCE active. | Comparer les versions. |
| Étape affichée. | État agrégé des tâches/conditions. | Ouvrir l’étape. |
| Blocages et éléments à revoir. | Tâches, impact assessment, demandes. | Voir les causes. |
| Dernière sauvegarde. | Brouillon utilisateur. | Aucun. |

### 5.3. Passage d’étape

| Action | Condition | Effet |
|---|---|---|
| `Ouvrir une étape` | Affectation et portée autorisées. | Ouvre la vue spécialisée. |
| `Voir ce qui manque` | Aucun. | Ouvre la liste des conditions non satisfaites. |
| `Signaler un doute` | Commentaire minimum + objet concerné. | Crée constat à vérifier et, si besoin, tâche/revue. |
| `Demander une aide` | Destinataire et objet précisés. | Crée une demande C-06. |
| `Transmettre au patron` | Contrat de préparation favorable ou dérogation patron. | Ouvre C-11 ; ne transmet pas sans contrôle. |

---

## 6. Vue C-04 — Documents et versions DCE

### 6.1. Question métier

> « Quels documents fondent mon travail, sont-ils lisibles, correctement classés et encore à jour ? »

| Élément visible | Données nécessaires | Actions collaborateur |
|---|---|---|
| Inventaire DCE | Nom original, type, version, format, source, lisibilité, hash, date réception. | Confirmer le type, déclarer une absence, signaler un fichier illisible. |
| Aperçu source | Pages, texte extrait, zones de table et repère de source. | Voir la page, commenter, créer une exigence ou tâche. |
| Familles de pièces | RC, CCAP, AE, CCTP, DPGF/BPU, plans, annexes, rectificatifs. | Corriger la classification proposée. |
| Comparaison versions | Versions, différences, impact connu/inconnu. | Ouvrir les impacts et demander revue. |
| Documents préparés | Version, auteur, statut, source, validateur, date de validation. | Ouvrir, préparer, demander revue, marquer non applicable avec motif. |

### 6.2. États documentaires

`non commencé`, `brouillon`, `en attente d’information`, `à relire`, `prêt à transmettre`, `retourné avec correction`, `validé pour paquet`, `non applicable`, `obsolète`, `à revoir`.

`Validé pour paquet` signifie uniquement qu’un document est candidat au paquet de réponse ; il ne signifie jamais que le dépôt est autorisé.

### 6.3. Erreurs et protections

| Situation | Message obligatoire |
|---|---|
| Fichier illisible | « Ce fichier ne peut pas encore fonder une exigence. Signalez une lecture à revoir ou demandez une nouvelle copie. » |
| Pièce attendue absente | « Cette pièce est absente du corpus reçu. Elle n’est pas présumée inexistante chez l’acheteur. » |
| Version plus récente | « Une nouvelle version concerne cet élément ; le travail préparé doit être revu avant transmission. » |
| Document expiré | « Cette pièce est connue mais expirée. Elle ne peut pas être proposée comme preuve actuelle. » |

---

## 7. Vue C-05 — Exigences, constats et tâches

### 7.1. Question métier

> « Que demande exactement le DCE, quel travail en découle et quelle preuve permettra de montrer que cette demande est traitée ? »

| Zone | Données visibles | Actions |
|---|---|---|
| Exigences | Intitulé, nature, action attendue, source, échéance, état, criticité, responsable, preuve attendue. | Confirmer, marquer à vérifier, signaler contradiction, associer tâche/preuve, demander décision. |
| Constats | Observation, auteur, date, source, état, objet lié. | Créer revue, convertir en tâche/demande si justifié. |
| Tâches | Action attendue, état, dépendances, responsable, échéance, preuve de fin. | Prendre en charge, bloquer, demander une information, soumettre à revue, terminer. |
| Dépendances | Tâches ou informations nécessaires avant un résultat. | Voir la cause et ouvrir l’élément dépendant. |
| Recommandation | Prochaine tâche proposée, raison, urgence/dépendance. | Ouvrir la tâche ; ne modifie pas le graphe. |

### 7.2. Boutons de tâche

| Bouton | Préconditions | Résultat durable |
|---|---|---|
| `Prendre en charge` | Tâche assignée ou prenable selon périmètre. | État `en cours`, acteur et horodatage. |
| `Ajouter un résultat` | Tâche ouverte + contenu/preuve. | Brouillon ou résultat associé à la tâche. |
| `Signaler un blocage` | Cause, dépendance ou besoin renseigné. | État `bloquée` ou `en attente`, demande/tâche créée si nécessaire. |
| `Demander une revue` | Élément précis et relecteur autorisé. | Revue ouverte, tâche `prête à relire`. |
| `Terminer` | Preuve de fin et dépendances critiques satisfaites. | Tâche terminée ou réponse expliquant le refus. |
| `Remplacer` | Motif et nouvelle tâche associée. | Ancienne tâche remplacée, historique conservé. |

### 7.3. Interdits

Le collaborateur ne peut pas effacer une exigence, rendre une exigence satisfaite sans preuve, modifier une source DCE ou transformer une suggestion en décision patron.

---

## 8. Vue C-06 — Demandes, réponses et retours

### 8.1. Question métier

> « De qui ai-je besoin, quelle réponse est attendue et que dois-je faire après son retour ? »

| Liste | Contenu | Actions |
|---|---|---|
| **Demandes émises** | Destinataire, objet, raison, élément demandé, échéance, état, source. | Relancer, annuler selon droit, consulter réponse. |
| **Demandes reçues** | Demande patron/collègue, périmètre, réponse attendue, date. | Répondre, joindre une pièce autorisée, signaler indisponibilité. |
| **Retours patron** | Correction demandée, étape touchée, cause, délai. | Ouvrir la tâche créée, demander précision. |
| **Réponses partenaires** | Partenaire, demande source, ressources reçues, date, statut de revue. | Créer tâche de revue, proposer la preuve. |

### 8.2. Créer une demande

| Champ | Règle |
|---|---|
| Destinataire | Patron, collègue ou partenaire autorisé. |
| Objet demandé | Pièce, information, disponibilité, revue, décision ou clarification. |
| Lien affaire | Obligatoire. |
| Source / raison | Obligatoire si la demande découle du DCE ou d’une tâche. |
| Échéance | Date si connue ; sinon priorité et raison. |
| Ressources partagées | Liste explicite, versionnée et autorisée. |
| Message | Question courte et actionnable, sans donner accès au prix privé. |

Une réponse partenaire ou patron ne clôture pas automatiquement la tâche liée ; elle rend seulement la tâche ou la revue possible.

---

## 9. Vue C-07 — Terrain, capacités, partenaires et réponse technique

### 9.1. Question métier

> « Quelles méthodes, moyens, références, capacités et partenaires permettent de répondre réellement à cette affaire ? »

| Sous-vue | Données | Actions autorisées |
|---|---|---|
| **Visite et terrain** | Accès, contraintes, diagnostics, site occupé, coactivité, photos/notes autorisées, attestation. | Consigner constat, proposer une tâche, demander une décision. |
| **Capacités** | Références, qualifications, équipes, matériels, état de validité, preuves. | Proposer, marquer à vérifier, signaler manque/expiration. |
| **Partenaires** | Besoin, disponibilité déclarée, documents, demande liée, retour. | Créer demande autorisée, proposer une réponse à revue. |
| **Mémoire technique** | Critères RC, sections, brouillons, engagements candidats, sources et trous de couverture. | Préparer, réutiliser avec contrôle, demander revue. |
| **Variantes / options** | Périmètre distinct, exigences, réponse technique candidate. | Préparer seulement si attribué ; demander décision patron. |

### 9.2. Engagements candidats

Une phrase de mémoire peut être signalée comme engagement candidat lorsque son contenu promet un moyen, un délai, une méthode, une équipe ou un résultat. L’interface affiche : la phrase, la source, le responsable proposé, la capacité/preuve associée et son statut de revue.

| Action | Résultat |
|---|---|
| `Associer une capacité` | L’engagement candidat est relié à un élément vérifiable. |
| `Marquer comme hypothèse` | Le contenu ne peut pas être présenté comme engagement validé. |
| `Demander validation` | Crée une revue patron/référent compétent. |
| `Retirer du brouillon` | Conserve une trace éditoriale sans produire un engagement. |

---

## 10. Vue C-08 — Contrôle de préparation

### 10.1. Question métier

> « Puis-je déclarer ma préparation prête à être transmise, et si non, qu’est-ce qui bloque exactement ? »

Cette vue applique le **Contrat de préparation**. Elle ne simule pas une validation patron et ne donne aucun indicateur de prix.

| Dimension | État affiché | Détail visible |
|---|---|---|
| Inventaire DCE | Conforme / à compléter / à revoir. | Pièces classées, absences et versions. |
| Exigences | Conforme / bloquante / à vérifier. | Exigences non classées, contradictoires ou sans responsable. |
| Documents | Prêts / brouillons / manquants / non applicables. | Pièces critiques et statut. |
| Réponse technique | Couverte / partielle / à revoir. | Critères non couverts, engagements candidats. |
| Preuves | Actuelles / expirées / manquantes / à confirmer. | Références et qualifications concernées. |
| Demandes | Résolues / ouvertes / bloquantes. | Destinataires et échéances. |
| Risques | Déclarés / à transmettre / non analysés. | Risques par type, sans prix/marge. |
| Données privées | Conformes. | Vérifie que le paquet collaborateur ne contient aucune donnée patron interdite. |

### 10.2. Boutons

| Bouton | Conditions | Effet |
|---|---|---|
| `Corriger les éléments bloquants` | Au moins un blocage. | Ouvre une liste filtrée de tâches/exigences. |
| `Déclarer prêt pour revue` | Aucun blocage ou dérogation patron existante. | Crée un contrôle de préparation et rend possible C-09. |
| `Demander une dérogation` | Blocage identifié + motif. | Crée demande patron ; ne contourne pas le blocage. |
| `Voir le détail` | Aucun. | Ouvre les sources, tâches et responsables. |

---

## 11. Vue C-09 — Préparation figée et transmission patron

### 11.1. Question métier

> « Quel état précis vais-je transmettre au patron, et quelles décisions attend-il de moi ? »

Cette vue crée une frontière nette entre l’affaire vivante et la photographie remise au patron.

| Zone | Contenu figé | Règle |
|---|---|---|
| Synthèse de l’affaire | Lot, objet, version DCE, date limite, collaborateur, périmètre. | Toute version est nommée. |
| Éléments préparés | Documents, exigences, preuves, réponses techniques, tâches terminées. | Références à des versions précises. |
| Éléments non résolus | Inconnus, contradictions, manques, demandes en attente. | Jamais masqués. |
| Risques | Type, criticité, source, propriétaire et action proposée. | Pas d’acceptation de risque collaborateur. |
| Décisions demandées | Go/No-Go, partenaire, engagement, dérogation, chiffrage, dépôt, etc. | Formulées comme demandes patron. |
| Questions acheteur | Brouillons, sources, échéance, statut. | Aucun envoi sans autorisation. |
| Contrôle de préparation | Résultat, blocages, dérogations éventuelles. | Partie du snapshot. |

### 11.2. Boutons

| Bouton | Précondition | Transition visible |
|---|---|---|
| `Prévisualiser l’instantané` | Contrôle de préparation exécuté. | Aucun changement ; vue de prévisualisation. |
| `Déclarer prête pour transmission` | Conditions du contrat de préparation satisfaites. | Préparation `prête pour revue`. |
| `Transmettre au patron` | Affectation active, permission de transmission, préparation prête. | Instantané créé ; transmission `transmise au patron`. |
| `Annuler la prévisualisation` | Aucun. | Retour au travail vivant. |
| `Reprendre la préparation` | Transmission non reçue ou retour patron. | Le travail vivant reste modifiable ; ancien snapshot conservé. |

Après transmission, le collaborateur voit le statut `transmise`, puis `reçue`, `retournée avec corrections`, `acceptée pour phase suivante` ou `invalidée`. L’acceptation pour chiffrage n’accorde jamais de droit sur l’espace prix.

---

## 12. Vue C-10 — Rectificatifs et impacts

### 12.1. Question métier

> « Qu’est-ce qui a changé dans le DCE, et quel travail préparé n’est plus fiable ? »

| Élément | Contenu affiché | Action |
|---|---|---|
| Nouvelle version | Date, origine, documents modifiés. | Voir comparaison. |
| Exigences touchées | Créées, modifiées, supprimées, à confirmer. | Ouvrir, reclasser, associer tâche. |
| Tâches touchées | À revoir, obsolètes, remplacées ou nouvelles. | Ouvrir le travail concerné. |
| Documents touchés | À revoir ou toujours valides. | Ouvrir la version et demande de revue. |
| Mémoire touché | Sections candidates à revoir. | Ouvrir la section et sa source. |
| Instantané/transmission | Toujours actuel ou invalidé. | Informer le patron si une transmission est concernée. |

L’interface ne montre jamais « recommencer l’analyse ». Elle montre : **« Voici exactement les éléments devenus à revoir, avec la source et le changement détecté. »**

---

## 13. Droits et contrôles communs

| Action | Conditions d’autorisation minimales |
|---|---|
| Lire une affaire | Affectation active × périmètre de ressources autorisé. |
| Créer/modifier une tâche | Affectation active × responsabilité/action autorisée × affaire non archivées. |
| Voir une preuve | Affectation × classe de données × droit de document. |
| Partager à un partenaire | Autorisation explicite + partage externe actif + ressource versionnée. |
| Transmettre au patron | Affectation + permission de transmission + contrat de préparation satisfaisant. |
| Voir un retour patron | Affectation active et affaire concernée. |
| Voir le prix/chiffrage | Interdit, sauf délégation patron hors périmètre standard et explicitement documentée. |

Aucun filtre graphique ne peut remplacer ces contrôles. Les données exclues de l’affectation ne doivent pas être livrées au navigateur collaborateur.

---

## 14. Critères de recette interface collaborateur

| ID | Situation | Résultat testable |
|---|---|---|
| `CUI-01` | Un collaborateur ouvre son accueil. | Il voit uniquement ses tâches, affaires et événements autorisés. |
| `CUI-02` | Une affaire comporte cinq tâches actives. | La prochaine tâche est recommandée avec son motif sans créer une sixième tâche. |
| `CUI-03` | Une tâche dépend d’une visite obligatoire non confirmée. | La tâche dépendante est bloquée avec la cause et le lien vers la visite. |
| `CUI-04` | Une pièce DCE est absente. | L’utilisateur peut la déclarer manquante et poursuivre les éléments non bloqués. |
| `CUI-05` | Un rectificatif modifie le RC. | L’écran Impact montre seulement les exigences, tâches, documents et sections touchés. |
| `CUI-06` | Le collaborateur reçoit une réponse partenaire. | La réponse est liée à la demande, puis proposée à revue ; elle ne clôture rien automatiquement. |
| `CUI-07` | La préparation contient une exigence bloquante non classée. | La transmission patron est refusée avec une explication actionnable. |
| `CUI-08` | La préparation est transmise. | Un instantané versionné est créé et le patron reçoit une action de revue. |
| `CUI-09` | Le patron accepte la préparation pour chiffrage. | Le collaborateur voit l’état mais ne voit aucun prix, marge ou fichier de chiffrage. |
| `CUI-10` | Un partenaire externe a un partage expiré. | Il ne peut plus ouvrir les ressources et aucune nouvelle version n’est automatiquement partagée. |

---

## 15. Frontière avec les documents suivants

Ce contrat prépare la Matrice Vue → Action collaborateur. La matrice définira, pour chaque bouton ci-dessus : l’intention normalisée, l’autorisation, les préconditions, la frontière métier, les invariants, le résultat durable, le fait métier, l’instantané éventuel et les vues à actualiser.

## 16. Révision V8.1 — Séparation interface, commandes et domaine

Cette révision n’ajoute aucun écran ni aucune fonction métier au parcours collaborateur. Elle durcit le contrat afin que l’interface reste une interface : elle affiche des situations préparées et émet des intentions ; elle ne possède pas les transitions métier, les règles d’autorisation ou l’évaluation des impacts.

```text
Interface collaborateur
  ↓ exprime une intention
Commande normalisée
  ↓ est autorisée et contrôlée
Transition métier
  ↓ produit un résultat durable et un fait métier
Situations préparées
  ↓ sont affichées dans les vues collaborateur et patron
```

| Niveau | Ce que le présent contrat définit | Ce qu’il ne définit pas |
|---|---|---|
| **Interface** | Ce qui est affiché, à qui, dans quel état, les boutons disponibles et le résultat observable. | Tables, API, calcul métier, mutation directe des états. |
| **Application** | La commande déclenchée, son contexte d’accès et la réponse attendue. | Propriétaire du domaine et invariants détaillés. |
| **Domaine** | À définir dans le contrat de domaine : propriétaire, invariants, événements, concurrence et politiques. | Disposition graphique ou composants UI. |

### 16.1. Toute action d’interface déclenche une commande

Une action visible possède désormais une intention normalisée. Le bouton n’effectue jamais lui-même une transition métier.

| Action visible | Commande déclenchée | Résultat observable par le collaborateur |
|---|---|---|
| Confirmer le classement d’une pièce | `ConfirmDocumentClassification` | Classification confirmée ou refus expliquée. |
| Signaler une pièce manquante | `DeclareMissingDocument` | Manque tracé et tâche/demande éventuelle. |
| Confirmer une exigence | `ConfirmRequirement` | Exigence confirmée avec source. |
| Créer une tâche | `CreateTask` | Tâche visible dans l’affaire et l’accueil du responsable. |
| Prendre en charge | `ClaimTask` | Tâche en cours au nom de l’utilisateur. |
| Ajouter un résultat | `RecordTaskResult` | Brouillon/résultat versionné. |
| Signaler un blocage | `DeclareTaskBlocker` | Cause durable et action de déblocage visible. |
| Demander une revue | `RequestReview` | Revue ouverte sur une version précise. |
| Créer une demande | `CreateRequest` | Demande avec destinataire, échéance et objet. |
| Répondre à une demande | `RecordRequestResponse` | Réponse reçue, éventuellement à revoir. |
| Proposer une capacité | `ProposeCapabilityForCase` | Capacité candidate avec état de validité. |
| Enregistrer le mémoire | `SaveResponseDraft` | Nouvelle version brouillon. |
| Déclarer un engagement candidat | `DeclareCandidateCommitment` | Engagement candidat à contrôler. |
| Exécuter le contrôle de préparation | `EvaluatePreparationReadiness` | État `READY`, `READY_WITH_WARNINGS` ou `BLOCKED`. |
| Transmettre au patron | `SubmitPreparationForPatronReview` | Instantané immuable + transmission patron. |
| Traiter un rectificatif | `EvaluateDceChangeImpact` | Liste ciblée d’éléments à revoir. |

> **Invariant V8 :** une recommandation de prochaine tâche n’émet jamais de commande de création de tâche. Une recommandation est une lecture calculée : action candidate + raison + sources + priorité.

### 16.2. États orthogonaux : ne jamais créer un enum fourre-tout

Le contrat ne doit pas mélanger l’état d’une donnée, l’état du travail, sa fraîcheur et la disponibilité d’une vue.

| Axe | Valeurs de référence | Exemple |
|---|---|---|
| **État de donnée** | Confirmée, à vérifier, manquante, contradictoire, expirée, non applicable. | L’attestation est expirée. |
| **État de travail** | Non commencée, en cours, en attente, bloquée, prête à relire, terminée, remplacée, abandonnée. | La tâche de visite est bloquée. |
| **Fraîcheur** | Actuelle, à revoir, obsolète, remplacée. | La section mémoire est à revoir après DCE v3. |
| **Disponibilité de vue** | Disponible, partielle, indisponible. | La comparaison DCE est partielle car un plan est illisible. |
| **Alerte** | Gravité, urgence et blocage sont trois axes indépendants. | Urgent + confirmé + non bloquant. |

Une vue peut donc présenter « document confirmé, tâche en attente, preuve obsolète, vue partielle » sans fabriquer un faux état unique incompréhensible.

### 16.3. Nature, provenance et fraîcheur

Toute donnée présentée possède une nature et, lorsque pertinent, une date d’observation, d’effet ou de vérification.

| Nature | Signification |
|---|---|
| `SOURCE_FACT` | Fait extrait d’un DCE, d’un document entreprise ou d’une réponse partenaire. |
| `HUMAN_OBSERVATION` | Constat attribué à une personne : visite, lecture, commentaire, photo. |
| `CALCULATION` | Valeur issue d’un calcul traçable et de ses entrées. |
| `SYSTEM_ASSESSMENT` | Évaluation SMART_AO : impact, couverture, cohérence ou préparation. |
| `RECOMMENDATION` | Suggestion non engageante, avec raison et preuve. |
| `HUMAN_DECISION` | Décision prise par un patron ou une personne explicitement autorisée. |

| Horodatage | Usage |
|---|---|
| `observed_at` | Moment où une disponibilité, un constat ou une réponse a été observé. |
| `effective_at` | Moment auquel une qualification, une version ou une information prend effet. |
| `verified_at` | Moment où une source a été vérifiée par une personne ou un processus reconnu. |

### 16.4. Contexte d’accès et classes de ressources

L’autorisation est évaluée sur le contexte complet, jamais sur un rôle général ou un bouton visible.

```text
Acteur × Affectation active × Périmètre × Classe de ressource × Action × Contexte de l’affaire
```

| Classe de ressource | Exemples |
|---|---|
| `DocumentClass` | RC, CCTP, plan, annexe, document préparé. |
| `EvidenceClass` | Référence, qualification, attestation, constat de visite. |
| `OperationalClass` | Tâche, exigence, demande, planning, méthodologie. |
| `PartnerClass` | Demande partenaire, réponse, partage externe. |
| `FinancialClass` | Coût, marge, prix de vente, devis privé, trésorerie. |
| `StrategicClass` | Décision patron, stratégie commerciale, arbitrage confidentiel. |

Les verbes d’accès sont également distincts : `DISCOVER`, `READ_METADATA`, `READ_CONTENT`, `DOWNLOAD`, `COMMENT`, `EDIT_DRAFT`, `SUBMIT`, `SHARE`, `VALIDATE`. Savoir qu’un document existe ne donne pas automatiquement le droit de le lire, le télécharger ou le partager.

Toute navigation et toute commande réévaluent ce contexte côté serveur. Une affectation retirée entre l’ouverture d’une tâche et le clic « Terminer » entraîne un refus, même si l’ancien écran est encore affiché.

### 16.5. Responsabilités de tâche, dépendances et blocages

Une tâche peut associer plusieurs rôles humains sans brouiller l’autorité.

| Rôle de tâche | Responsabilité |
|---|---|
| **Propriétaire** | Porte la responsabilité globale que la tâche existe et soit traitée. |
| **Exécutant** | Réalise le travail. |
| **Relecteur** | Vérifie la qualité du résultat. |
| **Approbateur** | Valide lorsque la tâche exige une autorité supérieure. |

| Type de dépendance | Effet |
|---|---|
| **Forte** | Empêche la fin de la tâche dépendante. |
| **Souple** | N’empêche pas de terminer, mais crée un avertissement de préparation. |
| **Informationnelle** | Informe sans contraindre la transition. |

Un blocage est un objet explicable : type, objet bloquant, source, raison, date, propriétaire et résolution. Le système ne doit jamais se contenter d’un statut `BLOCKED` sans cause.

### 16.6. Demande, réponse et revue

Une demande suit un cycle distinct de la tâche.

```text
Préparée → Envoyée → Réponse reçue → En revue → Acceptée / Rejetée / À clarifier
```

Une réponse reçue n’est jamais une preuve acceptée. Elle devient une entrée de revue, qui peut ensuite alimenter une tâche, une capacité, un document ou un constat.

### 16.7. Instantané de préparation, préparation et transmission

L’instantané de préparation est immuable et représente exactement l’état remis au patron. Il contient au minimum : affaire, affectation, version DCE, exigences, références de preuves, versions de documents préparés, états de tâches, blocages ouverts, demandes ouvertes, risques visibles au collaborateur, décisions demandées, auteur et date.

Chaque instantané porte un identifiant, une version et une empreinte de contenu. Cette empreinte permet d’affirmer : **« le patron a reçu exactement cet état de préparation »**.

La préparation ne se réduit plus à un booléen. La politique de préparation fournit :

| État | Signification |
|---|---|
| `READY` | Aucun blocage ; transmission possible. |
| `READY_WITH_WARNINGS` | Pas de blocage, mais avertissements visibles au patron. |
| `BLOCKED` | Au moins un élément bloquant non résolu ou non dérogé. |

Une réponse de refus de transmission retourne toujours trois listes distinctes : `blockers`, `warnings`, `informational`. Elle ne transforme jamais tous les éléments en erreurs.

### 16.8. Concurrence, idempotence et séparation des historiques

Pour les ressources métier sensibles, SMART_AO applique une concurrence optimiste : une commande indique la version attendue de l’objet modifié. Si une autre personne a déjà modifié l’objet, le système refuse l’écrasement silencieux et propose une comparaison ou une reprise.

Les commandes `CreateTask`, `CreateRequest`, `AttachEvidence`, `ReplaceDocument`, `ShareExternal` et `SubmitPreparationForPatronReview` exigent une clé d’idempotence. Un double clic ou une répétition réseau retourne le résultat de la première réussite ; il ne crée pas de doublon.

| Historique | Finalité | Visible à |
|---|---|---|
| **Timeline collaborateur** | Travail observable : tâches, demandes, retours, rectificatifs. | Collaborateur selon affectation. |
| **Journal métier** | Faits importants de l’affaire, décisions, transmissions et versions. | Selon politique patron/collaborateur. |
| **Audit de sécurité** | Connexions, droits, tentatives, commandes et accès techniques. | Patron/support autorisé ; jamais comme interface de travail. |

### 16.9. Critères de recette supplémentaires V8.1

| ID | Scénario | Résultat attendu |
|---|---|---|
| `CUI-11` | Une affectation est retirée pendant qu’un collaborateur travaille. | Son brouillon et l’historique restent conservés ; toute nouvelle lecture ou commande est refusée côté serveur. |
| `CUI-12` | Deux collaborateurs terminent la même tâche. | Une réussite est conservée ; le second reçoit un résultat idempotent ou un conflit explicite, jamais un écrasement. |
| `CUI-13` | Un rectificatif ne touche aucun élément métier. | Aucune tâche ni transmission n’est invalidée. |
| `CUI-14` | Un rectificatif touche uniquement un document préparé. | Seul ce document est à revoir ; la préparation globale reste utilisable si aucune règle bloquante n’est touchée. |
| `CUI-15` | Un rectificatif modifie la date limite. | La nouvelle date est sourcée ; priorités et échéances internes sont recalculées. |
| `CUI-16` | Un rectificatif touche une exigence d’un snapshot déjà transmis. | Snapshot historique conservé ; nouveau travail à revoir ; patron averti. |
| `CUI-17` | Une nouvelle version d’un document partagé existe. | Elle n’est pas envoyée automatiquement au partenaire. |
| `CUI-18` | Une vue a besoin d’une donnée privée pour un calcul interne. | La donnée peut être utilisée par le système autorisé mais n’est jamais incluse dans les données affichées au collaborateur. |

## Références internes

- `SMART_AO_V8_CAHIER_ESPACE_COLLABORATEUR.md`
- `SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE.md`
- `SMART_AO_V8_MATRICE_TRANSITIONS_METIER.md`
- `SMART_AO_V8_CONTRAT_DE_DOMAINE.md`

---

**Fin du Contrat Métier vers Interface — Collaborateur — version 1.0**
