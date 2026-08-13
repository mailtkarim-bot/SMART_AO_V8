# SMART_AO V8 — Matrice Vue → Action → Préconditions → Transition métier → Résultat durable → Événement → Vue mise à jour

**Version :** 1.0  
**Statut :** à valider avant le Contrat de domaine V8  
**Périmètre :** actions du patron administrateur ; les actions collaborateur seront ajoutées dans une matrice séparée  
**Documents amont :** Cahier Espace Patron V8.2 ; Contrat Métier vers Interface V1.1.

---

## 1. Rôle de cette matrice

Le Cahier Espace Patron fixe ce que le patron doit voir et faire. Le Contrat Métier vers Interface définit les données, sources, états, droits, provenances et règles de fraîcheur nécessaires à chaque vue. Cette matrice va un cran plus loin : elle définit le changement métier produit lorsque le patron réalise une action.

> **Une action visible dans SMART_AO ne peut pas être un simple bouton.** Elle doit avoir des préconditions, changer une situation métier précise, produire un résultat durable, inscrire un fait dans le Journal de vérité et actualiser les vues concernées.

Cette matrice ne décrit pas encore des classes, des tables, des endpoints ou des technologies. Ses termes « transition » et « événement » désignent des changements et faits métier observables.

---

## 2. Format canonique d’une ligne de matrice

| Colonne | Sens contractuel |
|---|---|
| **ID** | Identifiant stable de la transition. |
| **Vue d’entrée** | Vue depuis laquelle le patron déclenche l’action. |
| **Action patron** | Libellé compréhensible par le patron. |
| **Préconditions** | Ce qui doit être vrai avant l’autorisation de l’action. |
| **Transition métier** | Changement de situation produit par l’action. |
| **Résultat durable** | Ce qui doit être conservé comme nouvel état, version, relation, décision ou autorisation. |
| **Événement métier** | Fait ajouté au Journal de vérité. |
| **Vues mises à jour** | Situations métier qui doivent être recalculées ou marquées à revoir. |
| **Refus / erreur** | Ce que SMART_AO explique si l’action ne peut pas avoir lieu. |

### 2.1. Notation des préconditions

| Notation | Signification |
|---|---|
| **A** | Autorisation : le patron ou une personne explicitement habilitée possède le droit nécessaire. |
| **C** | Cohérence : la situation affichée n’est ni obsolète, ni partielle lorsqu’une validation stricte est requise. |
| **S** | Sources : les sources, versions et dates de référence nécessaires sont visibles. |
| **V** | Validation : les validations humaines ou contrôles obligatoires sont présents. |
| **R** | Règle métier : condition propre à l’action, par exemple absence de blocage de dépôt. |

Une précondition non satisfaite n’est jamais cachée. SMART_AO indique laquelle manque, pourquoi elle compte, qui peut la traiter et l’action suivante possible.

---

## 3. Invariants applicables à toutes les transitions

| ID | Invariant |
|---|---|
| **I-01** | Une action sensible ne peut être déclenchée que par une personne autorisée. |
| **I-02** | Une décision patron conserve un contexte de décision figé : sources, versions, faits, inconnus, risques, prix et capacités considérés. |
| **I-03** | Une nouvelle décision ou version peut superséder une ancienne ; elle ne l’efface jamais. |
| **I-04** | Un scénario de prix ne modifie jamais silencieusement la version officielle. |
| **I-05** | Un paquet préparé, un dépôt déclaré et un accusé archivé sont trois états distincts. |
| **I-06** | Pour une même cause métier et un même objet, une seule Action patron active existe ; plusieurs causes peuvent être regroupées dans cette action. |
| **I-07** | Toute information à impact conserve sa nature : fait, calcul, déduction, recommandation ou décision humaine. |
| **I-08** | Une vue ne présente pas une situation partielle ou obsolète comme actuelle sans l’indiquer. |
| **I-09** | Les données privées patron ne sont jamais transmises à un collaborateur non habilité. |
| **I-10** | Le Journal de vérité contient des faits métier, jamais des opérations techniques internes. |

---

# Partie I — Affaires, actions et décisions

## 4. Création, attribution et continuité de l’affaire

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-001** | Accueil, Affaires, Opportunités | `Créer une affaire` | A : patron autorisé ; S : opportunité ou données minimales identifiées. | Une nouvelle affaire est créée, ou une opportunité devient une affaire suivie. | Identité d’affaire, origine, état initial, responsable patron et lien éventuel à l’opportunité. | `Affaire créée`. | Accueil, Portefeuille, Opportunités, Journal. | « Le lot ou l’objet de l’affaire doit être identifié pour éviter un doublon. » |
| **M-002** | Portefeuille, Vue de direction, Équipe | `Attribuer un collaborateur` | A : patron ; R : collaborateur actif ; affaire non archivée. | Une affectation de travail est créée pour l’affaire. | Rôle, périmètre, tâches initiales, date et patron attribuant. | `Collaborateur attribué à l’affaire`. | Affaire, Équipe, Accueil si une transmission est attendue. | « Ce compte est suspendu ou cette affaire est terminée. » |
| **M-003** | Affaires, Équipe | `Réattribuer l’affaire` | A : patron ; R : nouveau collaborateur actif ; motif de transfert saisi. | Le responsable opérationnel change sans perte de l’historique. | Nouvelle affectation, ancienne affectation terminée, motif et date. | `Responsable d’affaire modifié`. | Affaire, Équipe, Accueil, Journal. | « Un nouveau responsable doit être choisi avant le retrait de l’ancien. » |
| **M-004** | Affaires, Vue de direction | `Arrêter l’affaire` | A : patron ; R : motif obligatoire ; C : état actuel visible. | L’affaire cesse d’être active dans le portefeuille commercial. | État `arrêtée`, motif, date, décision patron ; données conservées. | `Affaire arrêtée`. | Accueil, Portefeuille, Opportunités, Journal. | « Une affaire déposée ou gagnée doit être clôturée par le chemin approprié, pas simplement arrêtée. » |
| **M-005** | Affaires | `Archiver l’affaire` | A : patron ; R : affaire terminée, perdue, abandonnée ou clôturée ; aucune action active non traitée. | L’affaire quitte les vues actives tout en restant consultable. | État d’archivage, date, motif et responsable. | `Affaire archivée`. | Portefeuille, Accueil, Journal. | « Des actions ou obligations restent actives ; traitez-les ou annulez-les avec motif. » |

## 5. Cycle de vie de l’Action patron

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-010** | Toute vue concernée | `Créer une Action patron` | R : une cause métier exige une décision/arbitrage patron ; I-06 vérifié. | Une action est créée ou une cause est ajoutée à une action existante. | Action, causes, niveau de traitement, propriétaire, approbateur, échéance et liens métier. | `Action patron créée` ou `Cause ajoutée à une action`. | Accueil, File d’actions, Affaire/ressource concernée, Journal. | « Une action active existe déjà pour cette cause ; la nouvelle cause a été regroupée. » |
| **M-011** | File d’Actions | `Prendre en compte` | A : patron ; action à l’état Nouvelle. | L’action passe de Nouvelle à Prise en compte. | Heure de prise en compte et patron concerné. | `Action patron prise en compte`. | Accueil, File d’actions, Journal. | « Cette action a déjà été prise en compte ou est clôturée. » |
| **M-012** | File d’Actions, Affaire | `Déléguer une préparation` | A : patron ; R : exécutant actif ; tâche précise, délai et approbateur connus. | L’action passe en préparation ou attente ; une tâche est confiée. | Propriétaire, exécutant, approbateur, tâche, délai et périmètre. | `Préparation déléguée`. | Accueil, Affaire, Équipe, File d’actions, Journal. | « La décision ne peut pas être déléguée à la place du patron ; seule sa préparation l’est. » |
| **M-013** | File d’Actions, Dossier de décision | `Mettre en attente d’information` | A : patron ou personne habilitée ; R : information/tiers attendu identifié. | L’action passe en attente d’information ou d’un tiers. | Attente, contact ou source attendue, date de relance et responsable. | `Action mise en attente`. | Accueil, Affaire, Équipe, Journal. | « Indiquez ce qui est attendu, de qui et avant quelle date. » |
| **M-014** | File d’Actions | `Résoudre l’action` | V : résultat ou décision vérifiable ; C : aucune cause active non traitée dans l’action. | L’action passe à Résolue. | Résultat, preuve ou décision de résolution, validateur et date. | `Action patron résolue`. | Accueil, File d’actions, Affaire, Journal. | « Une cause de l’action reste ouverte ; elle doit être traitée, écartée ou transférée. » |
| **M-015** | File d’Actions | `Clôturer l’action` | R : action Résolue ; résultat durable conservé. | L’action passe à Clôturée. | Date de clôture et résultat final. | `Action patron clôturée`. | Accueil, File d’actions, Journal. | « L’action doit d’abord être résolue. » |
| **M-016** | File d’Actions | `Annuler avec motif` | A : patron ; R : motif explicite ; action non remplacée. | L’action passe à Annulée avec motif. | Motif, date, patron et éventuelle conséquence sur l’affaire. | `Action patron annulée`. | Accueil, Affaire, Journal. | « Une action liée à un blocage DCE ne peut être annulée sans décision patron documentée. » |
| **M-017** | File d’Actions, Affaire | `Remplacer l’action` | R : une nouvelle cause, version ou situation rend l’action précédente inadaptée. | L’action active passe à Remplacée et une nouvelle action est créée. | Lien explicite ancienne action → nouvelle action. | `Action patron remplacée`. | Accueil, File d’actions, Affaire, Journal. | « La nouvelle action doit être créée avant de remplacer l’ancienne. » |

## 6. Dossier de décision et choix du patron

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-020** | Affaire, Action patron | `Ouvrir un Dossier de décision` | A : patron ; S : situation métier disponible ; C : fraîcheur indiquée. | Un contexte de décision est préparé pour consultation ; aucune décision n’est prise. | Contexte présenté avec sources, versions, inconnus, risques et options. | Aucun événement décisionnel ; ouverture éventuellement enregistrée dans l’audit. | Dossier de décision uniquement. | « La situation est partielle ou obsolète ; certains éléments doivent être revus avant décision. » |
| **M-021** | Dossier de décision | `Répondre à l’affaire` | A : patron ; S : faits/inconnus/risques visibles ; V : contexte de décision complet ; R : décision Go autorisée. | Décision active devient `GO`. | Décision GO, contexte figé, date, patron, motif. | `GO validé`. | Accueil, Affaire, Portefeuille, Journal, Action patron. | « Les éléments nécessaires à la décision ne sont pas disponibles ou la situation a changé. » |
| **M-022** | Dossier de décision | `Répondre sous conditions` | A : patron ; V : conditions définies ; R : chaque condition possède propriétaire, exécutant, approbateur et date. | Décision active devient `GO sous conditions`; actions/conditions sont actives. | Décision, contexte figé, liste des conditions et actions associées. | `GO sous conditions validé`. | Accueil, Affaire, File d’actions, Équipe, Journal. | « Une condition sans responsable ou sans échéance ne permet pas de poursuivre sous conditions. » |
| **M-023** | Dossier de décision | `Ne pas répondre` | A : patron ; R : motif saisi. | Décision active devient `NO-GO`; préparation est arrêtée. | Décision, contexte, motif et éventuelles leçons pour la veille. | `NO-GO validé`. | Accueil, Affaire, Portefeuille, Opportunités, Journal. | « Le motif est requis pour alimenter l’historique commercial. » |
| **M-024** | Dossier de décision | `Accepter un risque avec motif` | A : patron ; S : risque, impact, sources et protections visibles ; R : motif/limite d’acceptation. | Le risque reste ouvert mais possède une décision humaine d’acceptation. | Décision de risque, contexte, limites, date et patron. | `Risque accepté avec motif`. | Affaire, Accueil, Protection, Journal. | « Un risque sans impact ou source connue ne peut pas être accepté comme s’il était documenté. » |
| **M-025** | Dossier de décision | `Demander une précision` | R : question, destinataire, source et échéance identifiés. | Une demande de clarification est créée ; l’action passe en attente. | Question, lien aux sources, destinataire, date et responsable. | `Clarification demandée`. | Affaire, File d’actions, Journal. | « La source ou l’objet de la question doit être indiqué. » |
| **M-026** | Dossier de décision | `Superséder une décision` | A : patron ; R : nouvelle décision et nouveau contexte ; C : changement ou motif explicite. | Une nouvelle décision devient active ; l’ancienne est conservée comme supersédée. | Lien ancienne décision → nouvelle décision, motifs et contextes distincts. | `Décision supersédée`. | Accueil, Affaire, Portefeuille, Journal. | « La décision actuelle ne peut pas être écrasée sans une nouvelle décision documentée. » |

# Partie II — Entreprise, preuves, capacités et équipe

## 7. Capacités, qualifications, références et partenaires

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-030** | Entreprise & capacités | `Ajouter une capacité` | A : patron ; R : type de capacité, périmètre et source/déclaration renseignés. | Une capacité entreprise est créée à l’état à vérifier ou confirmé selon preuve. | Capacité, périmètre, période, propriétaire de vérité et statut. | `Capacité entreprise ajoutée`. | Entreprise, Santé entreprise, Affaires concernées, Journal. | « Le métier ou le périmètre de la capacité est nécessaire. » |
| **M-031** | Entreprise & capacités | `Confirmer une capacité pour une affaire` | A : patron/habilité ; S : capacité, période, charge et preuve visibles ; C : pas d’obsolescence critique. | La capacité est marquée confirmée pour cette affaire précise. | Lien exigence → capacité → preuve → affaire ; validateur et date. | `Capacité confirmée pour l’affaire`. | Affaire, Carte de décision, Santé entreprise, Journal. | « La capacité générale existe, mais sa disponibilité ou son périmètre n’est pas confirmé pour cette affaire. » |
| **M-032** | Entreprise & capacités | `Ajouter une qualification` | A : patron ; S : original ou source de qualification ; dates/périmètre connus ou indiqués inconnus. | Une qualification est ajoutée avec dimensions d’existence, validité, applicabilité et vérification. | Qualification versionnée, dates, périmètre, propriétaire de vérité et état. | `Qualification ajoutée`. | Entreprise, Bibliothèque, Santé, Affaires concernées, Journal. | « Une qualification sans source ne peut pas être affichée comme confirmée. » |
| **M-033** | Entreprise, Bibliothèque | `Ajouter une référence` | A : patron ; R : chantier, rôle, date/période et droit d’usage renseignés. | Une référence réutilisable est créée. | Fiche référence, preuves, comparabilité potentielle et droit d’usage. | `Référence entreprise ajoutée`. | Entreprise, Bibliothèque, Affaires concernées, Journal. | « Une référence sans droit d’usage reste interne et ne peut pas être proposée à l’acheteur. » |
| **M-034** | Entreprise, Bibliothèque | `Ajouter un partenaire` | A : patron ; R : identité, rôle potentiel, contact et périmètre renseignés. | Un partenaire est créé sans être automatiquement conforme ou disponible. | Profil partenaire, documents, état de vérification, périmètre et autorisations. | `Partenaire ajouté`. | Entreprise, Bibliothèque, Affaires, Journal. | « Un partenaire ajouté n’est pas encore confirmé pour une affaire. » |
| **M-035** | Affaire, Partenaires | `Accepter un partenaire pour une affaire` | A : patron ; S : périmètre, documents et disponibilité visibles ; V : réserves/conditions définies si nécessaire. | Le partenaire est retenu ou retenu sous réserve pour l’affaire. | Lien partenaire-affaire, rôle, conditions, validations et éléments partagés. | `Partenaire retenu pour l’affaire`. | Affaire, Dossier de décision, Protection, Journal. | « Les documents ou la disponibilité du partenaire doivent être confirmés ou posés en conditions. » |

## 8. Bibliothèque et preuves

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-040** | Bibliothèque, Entreprise, Affaire | `Ajouter une preuve` | A : patron/habilité ; R : original, famille, source, confidentialité et périmètre renseignés. | Une preuve est admise dans la bibliothèque avec ses dimensions d’état. | Original, métadonnées, version, source, propriétaire de vérité et droits d’usage. | `Preuve ajoutée`. | Bibliothèque, Entreprise, Santé, Affaires concernées, Journal. | « Le fichier ou sa source doit être conservé ; une simple description ne suffit pas comme preuve. » |
| **M-041** | Bibliothèque | `Remplacer une version` | A : patron/habilité ; S : preuve existante et nouvelle source disponibles. | Une nouvelle version devient candidate à l’usage ; l’ancienne reste archivée. | Chaîne de versions, motif de remplacement, dates et état de validation. | `Version de preuve ajoutée`. | Bibliothèque, Santé, Affaires concernées, Journal. | « Une preuve active ne peut pas être écrasée ; ajoutez une nouvelle version. » |
| **M-042** | Bibliothèque, Affaire | `Autoriser une preuve pour une affaire` | A : patron ; S : preuve existante ; R : affaire, périmètre et droit d’usage compatibles. | La preuve est associée à l’affaire comme utilisable/proposée/à confirmer. | Autorisation d’usage, périmètre, date et patron ayant autorisé. | `Preuve autorisée pour l’affaire`. | Affaire, Bibliothèque, Carte de décision, Journal. | « Cette preuve est expirée, hors périmètre ou sans droit d’usage confirmé. » |
| **M-043** | Bibliothèque, Accueil | `Créer une action de renouvellement` | A : patron/habilité ; S : date d’expiration ou échéance connue. | Une Action patron ou tâche de préparation est créée. | Action liée à la preuve, échéance, propriétaire/exécutant/approbateur. | `Renouvellement demandé`. | Accueil, File d’actions, Bibliothèque, Santé, Journal. | « La date de renouvellement doit être connue ou une vérification doit être créée. » |
| **M-044** | Bibliothèque | `Archiver une preuve` | A : patron ; R : motif ; C : usages actifs examinés. | La preuve n’est plus proposée par défaut ; usages historiques restent visibles. | État archivé, motif, date et affaires impactées. | `Preuve archivée`. | Bibliothèque, Affaires concernées, Santé, Journal. | « Cette preuve est encore utilisée dans une affaire active ; choisissez un remplacement ou acceptez l’impact. » |

## 9. Équipe, comptes et délégations

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-050** | Équipe | `Inviter un collaborateur` | A : patron ; R : identité, e-mail, fonction et périmètre initial renseignés. | Une invitation sans accès global est créée. | Invitation, rôle, date d’expiration et affaires initiales éventuelles. | `Invitation collaborateur créée`. | Équipe, Journal. | « Un compte actif utilise déjà cette adresse. » |
| **M-051** | Équipe | `Suspendre un compte` | A : patron ; R : motif ; C : affaires et tâches affectées examinées. | Le compte perd ses accès futurs sans perte d’historique. | Suspension, motif, date et plan de réattribution. | `Compte collaborateur suspendu`. | Équipe, Affaires concernées, Accueil, Journal. | « Des tâches actives doivent être réattribuées ou maintenues sous suivi patron. » |
| **M-052** | Équipe, Affaire | `Créer une délégation ponctuelle` | A : patron ; R : ressource, permissions, durée, motif et bénéficiaire définis. | Une autorisation limitée est accordée. | Délégation datée, périmètre, permissions, motif et donneur. | `Délégation ponctuelle accordée`. | Équipe, Affaire/ressource, Journal. | « Une délégation permanente ou sans périmètre est interdite. » |
| **M-053** | Équipe | `Retirer une délégation` | A : patron ; S : délégation active identifiée. | La délégation est clôturée avant ou à son échéance. | Date, motif et patron. | `Délégation retirée`. | Équipe, Affaire/ressource, Journal. | « Cette délégation est déjà expirée ou retirée. » |

# Partie III — Opportunités, prix, dépôt et journal

## 10. Opportunités et qualification initiale

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-060** | Opportunités | `Créer un profil de veille` | A : patron ; R : métiers, zone ou critère initial renseigné. | Un profil de veille est actif ou brouillon. | Critères, exclusions, fréquence, auteur et état du profil. | `Profil de veille créé`. | Opportunités, Santé entreprise, Journal. | « Au moins un métier, une zone ou un critère de recherche est nécessaire. » |
| **M-061** | Opportunités | `Examiner une opportunité` | A : patron/habilité ; S : opportunité et source connues. | L’opportunité passe d’inédite à examinée. | Date, utilisateur et notes éventuelles. | `Opportunité examinée`. | Opportunités, Journal. | « La source de l’opportunité n’est pas disponible. » |
| **M-062** | Opportunités | `Transmettre pour qualification` | A : patron ; R : collaborateur actif et périmètre défini. | Une tâche de qualification est créée sans décision de répondre. | Affectation, données partagées et échéance. | `Qualification d’opportunité attribuée`. | Opportunités, Équipe, Accueil, Journal. | « Une opportunité sans source ou objet identifié ne peut pas être qualifiée utilement. » |
| **M-063** | Opportunités | `Créer l’affaire depuis l’opportunité` | A : patron ; S : opportunité examinée ; R : objet/lot choisi. | Voir M-001 ; l’opportunité est liée à l’affaire créée. | Affaire, origine et lien durable. | `Opportunité transformée en affaire`. | Opportunités, Affaires, Accueil, Journal. | « Précisez le lot ou le périmètre à traiter. » |
| **M-064** | Opportunités | `Écarter avec motif` | A : patron/habilité ; R : motif. | L’opportunité est écartée de la veille active. | Motif, date et utilisateur. | `Opportunité écartée`. | Opportunités, mémoire commerciale, Journal. | « Le motif est requis pour améliorer les sélections futures. » |

## 11. Prix privé et version officielle

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-070** | Prix privé | `Créer un scénario` | A : patron ; S : affaire et DCE applicable connus ; R : nom et version de base identifiés. | Un scénario privé dérivé est créé ; le prix officiel reste inchangé. | Scénario, auteur, date, base, hypothèses et état privé. | `Scénario de prix créé`. | Prix privé, Affaire, Journal. | « Une version de base ou un DCE applicable doit être identifié. » |
| **M-071** | Prix privé | `Modifier une hypothèse de scénario` | A : patron ; R : hypothèse, valeur, motif et unité définis. | Le scénario est recalculé ou marqué à recalculer ; aucune version officielle ne change. | Nouvelle hypothèse, ancien/neuf valeur, motif et résultats associés. | `Hypothèse de scénario modifiée`. | Prix privé, Fiabilité du chiffrage, Affaire, Journal. | « Cette modification concerne le prix officiel ; créez ou modifiez un scénario privé. » |
| **M-072** | Prix privé | `Demander un devis fournisseur` | A : patron ou délégation ; R : fournisseur, périmètre et délai définis. | Une demande partenaire est créée ; poste/prix devient en attente si nécessaire. | Demande, périmètre, destinataire, échéance et état. | `Devis fournisseur demandé`. | Prix privé, Actions, Affaire, Journal. | « Le périmètre de la demande doit être défini avant partage. » |
| **M-073** | Prix privé | `Préparer une version officielle de prix` | A : patron ; S : scénario choisi et DCE applicable connus ; R : aucune modification non expliquée. | Une version officielle candidate est créée à partir du scénario retenu. | Version candidate, scénario d’origine, DCE/pièces applicables, auteur et date. | `Version de prix préparée`. | Prix privé, Affaire, Coffre de dépôt, Journal. | « Le scénario ou le DCE de référence est absent ou obsolète. » |
| **M-074** | Prix privé, Dossier de décision | `Valider le prix officiel` | A : patron ; C : situation non obsolète ; S : DCE applicable, hypothèses, devis, fiabilité visibles ; R : blocages empêchant validation traités ou acceptés avec motif. | La version officielle candidate devient active ; l’ancienne est supersédée si elle existe. | Version active, décision, contexte figé, DCE de référence et patron validateur. | `Prix officiel validé`. | Prix privé, Affaire, Dossier de décision, Coffre de dépôt, Journal. | « Le prix ne peut pas être validé tant que les éléments bloquants ou le DCE applicable ne sont pas établis. » |
| **M-075** | Affaire, Prix privé | `Marquer le prix à revoir` | R : nouveau DCE, nouveau devis, contradiction ou changement de capacité impactant le prix. | La version officielle active devient à revoir ; une action patron existe ou est enrichie. | Motif d’obsolescence, sources et lien à l’action de revue. | `Prix marqué à revoir`. | Accueil, Affaire, Prix privé, Coffre de dépôt, Journal. | Aucun : cette transition est possible dès qu’un impact est identifié. |

## 12. Coffre de dépôt et preuve de dépôt

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-080** | Coffre de dépôt | `Contrôler le dossier de dépôt` | A : patron/habilité ; S : pièces, versions et RC disponibles. | Les contrôles sont calculés ; blocages et actions sont créés ou regroupés. | Rapport de contrôle daté, causes, états et sources. | `Contrôle de dépôt exécuté`. | Coffre, Affaire, Accueil, Actions, Journal. | « Le DCE ou les pièces de dépôt ne sont pas suffisamment disponibles pour contrôler le dossier. » |
| **M-081** | Coffre de dépôt | `Créer un paquet préparé` | A : patron/habilité ; V : contrôles requis non bloquants ; R : version de prix officielle active lorsque nécessaire. | Un paquet de dépôt immuable est préparé. | Liste de fichiers, versions, structure, date, créateur et état `Paquet préparé`. | `Paquet de dépôt préparé`. | Coffre, Affaire, Journal. | « Les pièces bloquantes ou la version de prix empêchent la préparation du paquet. » |
| **M-082** | Coffre de dépôt | `Autoriser le dépôt` | A : patron ou délégation explicite ; C : paquet à jour ; V : blocages traités ; R : conditions de signature et format affichées. | Le paquet passe à `Prêt pour dépôt`. | Autorisation, patron, date, paquet et conditions de dépôt. | `Dépôt autorisé`. | Coffre, Affaire, Accueil, Journal. | « Le paquet a été modifié, est obsolète ou contient un blocage. » |
| **M-083** | Coffre de dépôt | `Enregistrer le dépôt déclaré` | A : patron/habilité ; R : plateforme, date/heure, paquet et personne déposante renseignés. | Le paquet passe à `Déposé`, en attente de preuve. | Déclaration de dépôt, déposant, plateforme et horodatage. | `Dépôt déclaré`. | Coffre, Affaire, Accueil, Journal. | « Le paquet effectivement déposé doit être identifié. » |
| **M-084** | Coffre de dépôt | `Archiver l’accusé de réception` | A : patron/habilité ; S : original de preuve ou donnée de confirmation disponible ; R : dépôt déclaré lié. | Le dépôt passe à `Accusé archivé`. | Preuve originale, référence plateforme, paquet lié et horodatage. | `Accusé de réception archivé`. | Coffre, Affaire, Journal. | « Un accusé doit être relié à un dépôt déclaré et à un paquet identifié. » |
| **M-085** | Coffre de dépôt, Affaire | `Créer une nouvelle version après dépôt` | A : patron ; R : motif ; S : dépôt précédent conservé. | Une nouvelle préparation est ouverte ; le dépôt précédent reste historique. | Nouvelle branche/version de préparation, lien au dépôt antérieur et motif. | `Nouvelle version de réponse ouverte`. | Affaire, Coffre, Prix si impact, Journal. | « Le dépôt précédent ne peut pas être modifié ou supprimé. » |

## 13. DCE, rectificatifs et Journal de vérité

| ID | Vue d’entrée | Action patron | Préconditions | Transition métier | Résultat durable | Événement métier | Vues mises à jour | Refus / erreur |
|---|---|---|---|---|---|---|---|---|
| **M-090** | Affaire, Bibliothèque | `Ajouter une nouvelle version DCE` | A : patron/habilité ; S : nouvelle pièce reçue et affaire identifiée. | Une version DCE/rectificatif est enregistrée ; l’ancienne reste historique. | Version, réception, source et lien à la version remplacée. | `DCE rectificatif reçu`. | Affaire, Analyse, Prix, Coffre, Accueil, Journal. | « La nouvelle pièce doit être reliée à une affaire ou une consultation identifiable. » |
| **M-091** | Affaire, Action patron | `Évaluer l’impact d’un rectificatif` | S : ancienne et nouvelle versions accessibles ; R : analyse des éléments impactés disponible ou à lancer. | Les éléments touchés sont marqués à revoir ; décisions/prix/paquet peuvent devenir obsolètes. | Liste d’impacts, statut, responsables et actions créées/regroupées. | `Impact de rectificatif évalué`. | Affaire, Actions, Prix, Coffre, Accueil, Journal. | « L’impact ne peut pas être déclaré nul sans comparaison ou validation humaine documentée. » |
| **M-092** | Journal de vérité | `Ouvrir une provenance` | S : fait historique et source accessible ou état d’indisponibilité connu. | Aucune transition : consultation uniquement. | Aucune modification métier. | Aucun événement métier ; audit de consultation sensible éventuel. | Journal, vue d’origine. | « La source n’est plus accessible ; l’événement historique reste visible avec son état. » |
| **M-093** | Journal de vérité | `Exporter un journal métier` | A : patron/habilité ; R : périmètre et format définis. | Aucune transition métier d’affaire ; un export traçable est produit. | Export, périmètre, date, auteur et motif si requis. | `Journal métier exporté`. | Journal, audit, éventuellement Affaire. | « Les données privées ou partagées doivent respecter les droits de l’exportateur. » |

# Partie IV — Matrice de propagation des vues

## 14. Vues à actualiser par type de fait métier

| Fait métier | Accueil | File actions | Affaire | Entreprise | Bibliothèque | Opportunités | Équipe | Prix | Coffre | Journal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Action créée/modifiée/clôturée | Oui | Oui | Si liée | Non | Si liée | Si liée | Si déléguée | Si liée | Si liée | Oui |
| Décision prise/supersédée | Oui | Oui | Oui | Si capacité impactée | Si preuve impactée | Si opportunité liée | Si tâche impactée | Si prix lié | Si dépôt lié | Oui |
| Preuve ajoutée/versionnée/expirée | Oui si action | Oui si action | Si utilisée | Oui | Oui | Non | Non | Si prix/proof liée | Si dépôt impacté | Oui |
| Capacité/qualification confirmée | Oui si action | Oui si action | Oui | Oui | Si preuve liée | Qualification possible | Non | Possible | Possible | Oui |
| DCE rectificatif | Oui | Oui | Oui | Non | DCE lié | Non | Si réattribution | Oui si impact | Oui si impact | Oui |
| Scénario/prix modifié | Oui si action | Oui si action | Oui | Non | Devis lié | Non | Non | Oui | Oui si prix officiel | Oui |
| Paquet/dépôt/accusé | Oui | Oui si blocage | Oui | Non | Pièces liées | Non | Non | Prix validé visible | Oui | Oui |
| Compte/affectation/délégation | Oui si transmission | Oui si action | Oui si affaire | Non | Non | Non | Oui | Non | Non | Oui |

---

## 15. Critères de recette de la matrice

| ID | Scénario de recette | Résultat attendu |
|---|---|---|
| **R-01** | Une attestation expire alors qu’elle est utilisée dans deux affaires actives. | Une cause est ajoutée à une Action patron ou des actions distinctes selon les affaires ; les deux affaires, la bibliothèque et la santé entreprise sont mises à jour. |
| **R-02** | Le patron valide un Go sur DCE V2 puis reçoit DCE V3. | Le Go V2 reste historique ; l’affaire actuelle signale DCE V3 ; une revue est créée si l’impact est possible. |
| **R-03** | Le patron modifie un scénario fournisseur +8 %. | Seul le scénario change ; la version officielle n’est pas modifiée ; la fiabilité du chiffrage est recalculée. |
| **R-04** | Le patron valide une version officielle de prix. | Le DCE applicable et le scénario retenu sont figés avec la décision ; l’ancienne version reste consultable. |
| **R-05** | Le coffre assemble un ZIP sans preuve de dépôt. | L’état est `Paquet préparé` ou `Prêt pour dépôt`, jamais `Déposé` ou `Dépôt réussi`. |
| **R-06** | Un collaborateur est suspendu alors qu’il a une tâche active. | Son accès est bloqué ; le patron voit la tâche à réattribuer ; l’historique est conservé. |
| **R-07** | Une même pièce manquante provoque plusieurs alertes. | Une seule Action patron active regroupe les causes pour le même objet et la même affaire. |
| **R-08** | Une vue est partielle à cause d’une analyse en cours. | Elle indique clairement `Mise à jour en cours` ou `Partielle` et ne déclare pas « aucun risque ». |
| **R-09** | Une décision sous conditions est prise. | Toutes les conditions ont propriétaire, exécutant, approbateur et date ; l’affaire n’est pas annoncée comme prête à déposer tant qu’elles ne sont pas traitées. |
| **R-10** | Une recommandation SMART_AO est affichée. | Elle est identifiée comme recommandation, distincte d’une exigence acheteur ou d’une décision patron. |

---

## 16. Passage au document suivant

Une fois cette matrice validée, le Contrat de domaine V8 devra répondre à une question différente : **quelles réalités métier doivent exister, quelles règles garantissent leurs transitions et quels événements permettent d’actualiser les situations métier ?**

La matrice donne déjà les entrées nécessaires :

```text
Vue → Action patron → Préconditions → Transition métier
     → Résultat durable → Événement métier → Vues actualisées
```

> **Règle de passage :** le Contrat de domaine ne doit pas inventer une action, une transition ou une vue qui n’existe pas dans cette matrice sans décision explicite du fondateur.


---

# V8.2 — Passe Commande → Frontière métier → Invariants → Transition → Événement → Situations préparées

Cette passe ne crée **aucune nouvelle fonctionnalité**. Elle durcit la matrice précédente afin qu’un futur Contrat de domaine puisse être écrit sans ambiguïté. Elle sépare ce qui, jusque-là, était regroupé sous le mot général « transition ».

> **Règle de lecture :** une action utilisateur exprime une intention ; une commande la normalise ; une frontière métier vérifie les règles ; le résultat produit un ou plusieurs faits métier ; ces faits alimentent ensuite les situations préparées pour les écrans et, lorsque nécessaire, le Journal de vérité.

```text
Vue → intention utilisateur → commande → frontière métier
    → création / relation / transition / version
    → postconditions → fait métier → situations préparées → interface
```

Le **Journal de vérité n’est pas le fait métier lui-même**. Il est une chronologie métier préparée à partir de certains faits, avec une phrase compréhensible, une provenance et une conséquence.

## 17. Les cinq types de changement métier

| Type de changement | Définition | Exemples SMART_AO |
|---|---|---|
| **Création** | Une nouvelle réalité métier apparaît. | Créer une affaire, une action patron, une preuve, une version de prix ou un paquet de dépôt. |
| **Transition d’état** | Une réalité existante change d’état. | Prix candidat → prix officiel ; action en attente → résolue ; paquet préparé → prêt pour dépôt. |
| **Changement de relation** | Un lien métier est créé, modifié ou terminé. | Affecter un collaborateur, autoriser une preuve dans une affaire, retenir un partenaire. |
| **Création ou supersession de version** | Une nouvelle version immuable devient disponible ou applicable. | DCE V3 reçu, preuve V2 ajoutée, prix officiel V4 actif. |
| **Effet de situation préparée** | Une situation présentée au patron doit être reconstruite, invalidée, enrichie ou rafraîchie. | Accueil à rafraîchir après décision, Journal enrichi après dépôt. |

La matrice V8.1 garde le terme « transition métier » pour la lecture fonctionnelle. Cette passe V8.2 associe désormais chaque ligne à son type exact de changement.

## 18. Contrat commun d’une commande métier

| Élément | Règle V8.2 |
|---|---|
| **Intention utilisateur** | Formulation visible, par exemple « Valider le prix officiel ». |
| **Commande normalisée** | Intention stable utilisée dans les documents suivants, par exemple `ApprovePricingVersion`. |
| **Frontière métier propriétaire** | Réalité qui porte la règle et protège la cohérence de la mutation : Prix, Décision, Affaire, Action patron, Preuve, Capacité, Dépôt ou Affectation. |
| **Acteur** | Personne qui formule la commande. |
| **Propriétaire** | Réalité métier qui possède le changement. |
| **Exécutant** | Personne qui a réalisé une préparation éventuelle. |
| **Approbateur** | Personne qui valide le résultat lorsqu’une approbation est exigée. |
| **Préconditions** | Autorisation, cohérence, sources, validation et règles métier nécessaires avant traitement. |
| **Invariants** | Règles qui ne peuvent pas être violées, même par une interface ou un appel répété. |
| **Type de changement** | Création, transition, relation, version ou combinaison. |
| **Postconditions** | Éléments qui doivent être vrais après un succès. |
| **Résultat durable** | Nouvel état, relation, version, décision, autorisation ou preuve conservée. |
| **Fait métier** | Changement métier publié par la frontière propriétaire. |
| **Situation préparée impactée** | Situation patron qui doit être enrichie, reconstruite, invalidée ou rafraîchie. |
| **Idempotence** | Règle de répétition : une même commande critique, identifiée, ne crée pas deux résultats différents. |
| **Cohérence** | Garantie attendue : immédiate à validation ou actualisation différée explicitement visible. |
| **Échec / conflit** | Cas métier de refus, conflit de version, contexte obsolète, répétition ou panne sans changement métier. |

## 19. Politique transversale de version V8

| Règle | Application |
|---|---|
| **Immuable** | Une version validée ou reçue n’est jamais modifiée sur place. |
| **Nouvelle version** | Toute correction crée une nouvelle version avec une date, un auteur/origine et une référence à la version précédente lorsque nécessaire. |
| **Applicable à partir de** | Une version indique à partir de quel moment ou quelle décision elle devient applicable. |
| **Supersession** | Utilisée pour les versions et décisions : la nouvelle devient applicable, l’ancienne reste historique. |
| **Remplacement** | Utilisé pour une action ou une tâche : une nouvelle action remplace l’ancienne, sans signifier que l’ancienne était une version. |
| **Annulation** | Utilisée lorsqu’un élément ne doit plus être exécuté et n’est pas remplacé. |
| **Clôture** | Utilisée lorsqu’une action a atteint son résultat prévu. |
| **Expiration** | Utilisée lorsqu’une donnée ou preuve perd sa validité au regard d’une date. |
| **Obsolescence** | Utilisée lorsqu’un contexte, une décision, un prix ou un paquet peut ne plus être applicable après un changement matériel. |

La règle « supersédé » ne doit donc pas devenir un mécanisme universel.

## 20. Politique de propagation de l’obsolescence

Un changement matériel ne rend pas automatiquement toute l’affaire invalide. Il rend explicites les éléments qui doivent être revus.

```text
Nouveau fait ou nouvelle version
      ↓
Éléments directement concernés
      ↓
Éléments dépendants potentiellement obsolètes
      ↓
Actions de revue requises
      ↓
Situations patron marquées « à revoir » ou « mise à jour en cours »
```

| Changement matériel | Éléments qui peuvent devenir obsolètes | Effet requis |
|---|---|---|
| Rectificatif DCE | Exigences, constats, risques, questions, prix, décision Go, paquet de dépôt. | Évaluer l’impact ; créer/regrouper une action de revue ; marquer uniquement les éléments concernés. |
| Nouvelle preuve/qualification | Décisions, capacités ou propositions qui s’appuyaient sur l’ancienne preuve. | Réévaluer les usages liés ; ne pas effacer l’historique. |
| Nouveau devis fournisseur | Scénarios, prix candidat/officiel et décision financière. | Marquer le prix à revoir si le périmètre ou montant est impacté. |
| Capacité équipe modifiée | Décision de répondre, planning, mémoire, protection de délai. | Marquer la capacité ou décision à revoir selon la période et l’affaire. |
| Modification du paquet après autorisation | Autorisation de dépôt et préparation. | L’autorisation devient non applicable ; nouvelle revue obligatoire. |

## 21. Règles de succès, conflit, reprise et idempotence

| Situation | Règle contractuelle |
|---|---|
| **Succès** | La mutation est validée, le résultat durable est conservé, le fait métier est produit et les situations préparées sont marquées pour mise à jour. |
| **Échec de validation** | Aucune mutation métier ; SMART_AO explique les préconditions ou invariants non satisfaits. |
| **Conflit** | Aucune mutation silencieuse ; SMART_AO indique l’élément concurrent, par exemple une nouvelle version déjà active. |
| **Contexte obsolète** | Aucune décision stricte n’est validée ; le patron doit ouvrir la situation actuelle et choisir de revoir ou superséder. |
| **Échec d’infrastructure** | Aucun changement métier n’est considéré comme acquis ; l’utilisateur reçoit un état de reprise, jamais un faux succès. |
| **Répétition identifiée** | Une commande critique portant le même identifiant retourne le même résultat durable ; aucun doublon de décision, dépôt, autorisation ou événement n’est créé. |
| **Répétition non identifiée** | Les invariants métier et les contraintes d’unicité empêchent autant que possible les doublons ; une revue est créée en cas de doute. |

Les commandes critiques qui exigent une idempotence explicite sont : décision patron, validation de prix, autorisation de dépôt, enregistrement de dépôt, archivage d’accusé, attribution/délégation et création de paquet préparé.

## 22. Matrice de cardinalités V8

| Relation | Cardinalité métier |
|---|---|
| Entreprise → Affaires | Une entreprise possède plusieurs affaires ; une affaire appartient à une seule entreprise. |
| Affaire → DCE | Une affaire peut référencer plusieurs versions de DCE ; une version DCE peut concerner une ou plusieurs affaires seulement si elle a été reçue pour cette consultation. |
| Affaire → Décisions | Une affaire possède plusieurs décisions historiques ; une décision active peut être en vigueur par type de décision. |
| Décision → Contexte figé | Une décision possède exactement un contexte figé. |
| Contexte figé → Sources | Un contexte référence une ou plusieurs sources et versions. |
| Affaire → Prix | Une affaire possède plusieurs scénarios et versions de prix ; une seule version officielle active existe par périmètre de prix applicable. |
| Affaire → Paquets de dépôt | Une affaire peut avoir plusieurs paquets ; un paquet correspond à une version de préparation précise. |
| Dépôt déclaré → Paquet | Un dépôt déclaré référence exactement un paquet préparé/prêt à déposer. |
| Paquet → Fichiers | Un paquet contient un ou plusieurs fichiers versionnés. |
| Preuve → Affaires | Une preuve peut être utilisée ou proposée dans plusieurs affaires. |
| Action patron → Causes | Une action active peut regrouper plusieurs causes. |
| Cause + Affaire → Action active | Une même cause métier ne possède qu’une Action patron active par affaire. |
| Affectation → Affaire / Collaborateur | Une affectation relie une affaire et un collaborateur avec un rôle et une période. |
| Journal de vérité → Faits métier | Un fait métier peut produire zéro ou plusieurs entrées journalisées selon son importance ; une entrée journalisée référence un fait ou une décision métier identifiable. |

# Partie V — Matrice Commande → Frontière métier → Invariants → Événement

## 23. Commandes d’affaire, d’affectation et d’action patron

| ID V8.1 | Commande normalisée | Frontière métier propriétaire | Type de changement | Préconditions/invariants principaux | Postconditions | Fait métier produit | Situations préparées impactées | Cohérence |
|---|---|---|---|---|---|---|---|---|
| M-001 | `CreateCase` | Affaire | Création | Patron autorisé ; objet/lot identifiable ; pas de doublon fonctionnel. | Affaire créée avec identité continue, origine et état initial. | `CaseCreated` | Portefeuille affaires : REBUILD ; Radar : INVALIDATE ; Journal : APPEND. | Immédiate pour l’affaire ; différée acceptable pour le Radar. |
| M-002 | `AssignCaseResponsibility` | Affectation d’affaire | Relation | Patron autorisé ; collaborateur actif ; affaire active. | Affectation active avec rôle et périmètre ; ancienne relation préservée si historique. | `CaseResponsibilityAssigned` | Affaire : REBUILD ; Équipe : REBUILD ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-003 | `ReassignCaseResponsibility` | Affectation d’affaire | Relation | Nouveau responsable actif ; motif ; transfert valide. | Nouvelle affectation active ; ancienne terminée avec motif. | `CaseResponsibilityReassigned` | Affaire : REBUILD ; Équipe : REBUILD ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-004 | `StopCase` | Affaire | Transition d’état | Patron autorisé ; motif ; affaire non déposée/gagnée par un état incompatible. | Affaire arrêtée, actions futures annulées ou revues selon politique. | `CaseStopped` | Portefeuille : REBUILD ; Accueil : ASYNC_REFRESH ; Actions : INVALIDATE ; Journal : APPEND. | Immédiate. |
| M-005 | `ArchiveCase` | Affaire | Transition d’état | État terminal ; aucune obligation/action active. | Affaire archivée mais historique conservé. | `CaseArchived` | Portefeuille : REBUILD ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-010 | `OpenPatronAction` | Action patron | Création ou regroupement | Cause/objet définis ; unicité cause+affaire. | Une action active ou une cause ajoutée à l’action active existante. | `PatronActionOpened` ou `PatronActionCauseAdded` | Action Center : REBUILD ; Affaire : ASYNC_REFRESH ; Accueil : ASYNC_REFRESH ; Journal : APPEND selon importance. | Immédiate pour unicité ; différée pour Accueil. |
| M-011 | `AcknowledgePatronAction` | Action patron | Transition d’état | Action Nouvelle ; patron autorisé. | État Prise en compte, acteur et horaire conservés. | `PatronActionAcknowledged` | Action Center : REBUILD ; Accueil : ASYNC_REFRESH ; Journal : APPEND si utile. | Immédiate. |
| M-012 | `DelegateActionPreparation` | Action patron + Tâche | Relation et création | Patron autorisé ; exécutant actif ; tâche/date/périmètre définis. | Action en préparation/attente ; tâche séparée créée ; décision reste patron. | `ActionPreparationDelegated` | Action Center : REBUILD ; Équipe : REBUILD ; Affaire : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-013 | `AwaitActionInformation` | Action patron | Transition d’état | Objet/tiers/délai attendu définis. | Action En attente avec attente documentée. | `ActionAwaitingInformation` | Action Center : REBUILD ; Affaire : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-014 | `ResolvePatronAction` | Action patron | Transition d’état | Toutes les causes traitées/écartées ; résultat ou décision présent. | Action Résolue avec preuve de résolution. | `PatronActionResolved` | Action Center : REBUILD ; Affaire : REBUILD si impact ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-015 | `ClosePatronAction` | Action patron | Transition d’état | Action Résolue. | Action Clôturée, non active. | `PatronActionClosed` | Action Center : REBUILD ; Accueil : ASYNC_REFRESH ; Journal : APPEND si pertinent. | Immédiate. |
| M-016 | `CancelPatronAction` | Action patron | Transition d’état | Motif ; pas de remplacement. | Action Annulée avec motif. | `PatronActionCancelled` | Action Center : REBUILD ; Affaire : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-017 | `ReplacePatronAction` | Action patron | Relation + transition | Nouvelle action valide créée avant remplacement. | Ancienne action Remplacée, lien vers nouvelle action. | `PatronActionReplaced` | Action Center : REBUILD ; Affaire : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |

## 24. Commandes de décision et de risque

| ID V8.1 | Commande normalisée | Frontière métier propriétaire | Type de changement | Préconditions/invariants principaux | Postconditions | Fait métier produit | Situations préparées impactées | Cohérence |
|---|---|---|---|---|---|---|---|---|
| M-021 | `ApproveGoDecision` | Décision | Création + transition | Patron autorisé ; contexte de décision à jour ; sources et risques visibles ; décision Go admissible. | Décision GO active ; contexte figé ; décision antérieure du même type supersédée si nécessaire. | `GoDecisionApproved` | Vue direction affaire : REBUILD ; Action Center : REBUILD ; Portefeuille : ASYNC_REFRESH ; Journal : APPEND. | Immédiate à validation. |
| M-022 | `ApproveConditionalGoDecision` | Décision | Création + relation | Conditions possèdent propriétaire, exécutant, approbateur, date ; contexte à jour. | GO sous conditions actif ; actions/tâches de condition créées ou liées. | `ConditionalGoDecisionApproved` | Affaire : REBUILD ; Action Center : REBUILD ; Équipe : REBUILD ; Journal : APPEND. | Immédiate à validation. |
| M-023 | `ApproveNoGoDecision` | Décision | Création + transition | Patron autorisé ; motif ; contexte visible. | NO-GO actif ; préparation non poursuivie ; leçons enregistrées. | `NoGoDecisionApproved` | Portefeuille : REBUILD ; Radar : ASYNC_REFRESH ; Actions : INVALIDATE ; Journal : APPEND. | Immédiate. |
| M-024 | `AcceptRiskWithRationale` | Décision de risque | Création + relation | Risque, sources, impact et protections visibles ; motif/limite d’acceptation. | Décision d’acceptation liée au risque ; risque reste visible. | `RiskAcceptedWithRationale` | Protection : REBUILD ; Action Center : REBUILD ; Affaire : REBUILD ; Journal : APPEND. | Immédiate. |
| M-025 | `RequestClarification` | Affaire / Question de clarification | Création + relation | Source, question, destinataire, date et affaire définis. | Demande créée ; action en attente liée. | `ClarificationRequested` | Affaire : REBUILD ; Action Center : REBUILD ; Journal : APPEND. | Immédiate. |
| M-026 | `SupersedeDecision` | Décision | Supersession de version | Nouvelle décision et nouveau contexte à jour ; motif de révision. | Nouvelle décision active ; précédente conservée comme supersédée. | `DecisionSuperseded` | Affaire : REBUILD ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate à validation. |

## 25. Commandes de preuves, capacités, partenaires et équipe

| ID V8.1 | Commande normalisée | Frontière métier propriétaire | Type de changement | Préconditions/invariants principaux | Postconditions | Fait métier produit | Situations préparées impactées | Cohérence |
|---|---|---|---|---|---|---|---|---|
| M-030 | `CreateCompanyCapability` | Capacité entreprise | Création | Type, périmètre, propriétaire de vérité, source/déclaration. | Capacité créée avec état de vérification. | `CompanyCapabilityCreated` | Entreprise & capacités : REBUILD ; Santé : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-031 | `ConfirmCaseCapability` | Capacité pour affaire | Relation + validation | Capacité, période, charge, preuve et affaire compatibles. | Relation exigence-capacité-preuve confirmée pour l’affaire. | `CaseCapabilityConfirmed` | Vue direction affaire : REBUILD ; Entreprise : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-032 | `AddQualificationVersion` | Preuve / Qualification | Création de version | Source originale, périmètre et dates connus ou explicitement inconnus. | Nouvelle qualification versionnée ; ancienne conservée. | `QualificationVersionAdded` | Bibliothèque : REBUILD ; Entreprise : REBUILD ; Santé : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-033 | `CreateCompanyReference` | Référence entreprise | Création | Chantier, rôle, période, droit d’usage. | Référence créée, avec preuve et droit d’usage. | `CompanyReferenceCreated` | Entreprise : REBUILD ; Bibliothèque : REBUILD ; Journal : APPEND. | Immédiate. |
| M-034 | `CreatePartnerProfile` | Partenaire | Création | Identité, contact, rôle potentiel, périmètre. | Partenaire créé à vérifier, jamais automatiquement conforme. | `PartnerProfileCreated` | Entreprise : REBUILD ; Bibliothèque : REBUILD ; Journal : APPEND. | Immédiate. |
| M-035 | `ApproveCasePartner` | Relation partenaire-affaire | Relation + décision | Périmètre, documents, disponibilité et réserves visibles. | Partenaire retenu ou retenu sous réserve pour l’affaire. | `CasePartnerApproved` | Affaire : REBUILD ; Dossier décision : REBUILD ; Protection : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-040 | `AddEvidenceVersion` | Preuve | Création de version | Original, famille, source, confidentialité, périmètre. | Preuve admise/versionnée avec droits d’usage. | `EvidenceVersionAdded` | Bibliothèque : REBUILD ; Santé : ASYNC_REFRESH ; Affaires liées : INVALIDATE ; Journal : APPEND. | Immédiate. |
| M-041 | `ReplaceEvidenceVersion` | Preuve | Création de version | Preuve existante et nouvelle source valide. | Nouvelle version candidate ; ancienne archivale mais consultable. | `EvidenceVersionReplaced` | Bibliothèque : REBUILD ; Affaires liées : INVALIDATE ; Journal : APPEND. | Immédiate. |
| M-042 | `AuthorizeEvidenceForCase` | Autorisation d’usage de preuve | Relation | Preuve, affaire, droit d’usage et périmètre compatibles. | Autorisation d’usage datée et limitée. | `EvidenceAuthorizedForCase` | Affaire : REBUILD ; Bibliothèque : REBUILD ; Journal : APPEND. | Immédiate. |
| M-043 | `RequestEvidenceRenewal` | Action patron / Preuve | Création + relation | Échéance connue ou vérification demandée. | Action/tâche de renouvellement liée à la preuve. | `EvidenceRenewalRequested` | Accueil : ASYNC_REFRESH ; Actions : REBUILD ; Bibliothèque : REBUILD ; Journal : APPEND. | Immédiate. |
| M-044 | `ArchiveEvidence` | Preuve | Transition d’état | Motif ; usages actifs examinés. | Preuve archivée ; usages actifs marqués à revoir si nécessaire. | `EvidenceArchived` | Bibliothèque : REBUILD ; Affaires concernées : INVALIDATE ; Santé : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-050 | `InviteCollaborator` | Compte / Invitation | Création | Identité, e-mail, fonction, périmètre initial. | Invitation créée sans accès global. | `CollaboratorInvited` | Équipe : REBUILD ; Journal : APPEND. | Immédiate. |
| M-051 | `SuspendCollaborator` | Compte / Affectation | Transition + invalidation relations | Motif ; tâches et affaires actives examinées. | Compte suspendu ; accès retirés ; réattributions à traiter. | `CollaboratorSuspended` | Équipe : REBUILD ; Affaires : INVALIDATE ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-052 | `GrantTemporaryDelegation` | Délégation d’accès | Création | Ressource, permissions, durée, motif, bénéficiaire. | Délégation limitée active. | `TemporaryDelegationGranted` | Équipe : REBUILD ; Ressource concernée : REBUILD ; Journal : APPEND. | Immédiate. |
| M-053 | `RevokeTemporaryDelegation` | Délégation d’accès | Transition d’état | Délégation active identifiée. | Délégation terminée ; accès retiré. | `TemporaryDelegationRevoked` | Équipe : REBUILD ; Ressource concernée : REBUILD ; Journal : APPEND. | Immédiate. |

## 26. Commandes d’opportunité, prix et dépôt

| ID V8.1 | Commande normalisée | Frontière métier propriétaire | Type de changement | Préconditions/invariants principaux | Postconditions | Fait métier produit | Situations préparées impactées | Cohérence |
|---|---|---|---|---|---|---|---|---|
| M-060 | `CreateOpportunityProfile` | Profil de veille | Création | Métier, zone ou critère initial. | Profil brouillon/actif créé. | `OpportunityProfileCreated` | Radar : REBUILD ; Santé : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-061 | `AcknowledgeOpportunity` | Opportunité | Transition d’état | Source/opportunité disponible. | Opportunité marquée examinée. | `OpportunityAcknowledged` | Radar : REBUILD ; Journal : APPEND. | Immédiate. |
| M-062 | `DelegateOpportunityQualification` | Qualification opportunité + Tâche | Création + relation | Collaborateur actif ; périmètre de qualification. | Tâche de qualification créée ; aucune décision de répondre. | `OpportunityQualificationDelegated` | Radar : REBUILD ; Équipe : REBUILD ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-063 | `ConvertOpportunityToCase` | Affaire | Création | Opportunité examinée ; lot/objet choisi. | Affaire créée, liée à l’opportunité. | `OpportunityConvertedToCase` | Radar : INVALIDATE ; Portefeuille : REBUILD ; Journal : APPEND. | Immédiate. |
| M-064 | `RejectOpportunity` | Opportunité | Transition d’état | Motif. | Opportunité écartée ; motif utilisable pour la mémoire commerciale. | `OpportunityRejected` | Radar : REBUILD ; Journal : APPEND. | Immédiate. |
| M-070 | `CreatePricingScenario` | Prix / Scénario | Création | Affaire, DCE applicable, nom/version de base. | Scénario privé créé ; version officielle inchangée. | `PricingScenarioCreated` | Prix privé : REBUILD ; Affaire : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-071 | `ChangePricingScenarioAssumption` | Prix / Scénario | Transition + recalcul | Hypothèse, valeur, unité et motif. | Hypothèse versionnée ; résultat recalculé ou marqué en cours. | `PricingScenarioAssumptionChanged` | Prix privé : REBUILD/ASYNC_REFRESH ; Affaire : ASYNC_REFRESH ; Journal : APPEND. | Immédiate sur l’hypothèse ; différée acceptable pour calcul lourd signalé. |
| M-072 | `RequestSupplierQuote` | Demande partenaire / Prix | Création | Fournisseur, périmètre, délai. | Demande envoyée/préparée ; attente liée au prix. | `SupplierQuoteRequested` | Prix : REBUILD ; Actions : REBUILD ; Affaire : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-073 | `PrepareOfficialPricingVersion` | Prix | Création de version | Scénario retenu ; DCE applicable ; sources non obsolètes. | Version candidate créée avec lien scénario/DCE/pièces. | `OfficialPricingVersionPrepared` | Prix : REBUILD ; Affaire : ASYNC_REFRESH ; Coffre : INVALIDATE ; Journal : APPEND. | Immédiate. |
| M-074 | `ApprovePricingVersion` | Prix | Transition d’état + supersession | Patron ; DCE applicable à jour ; fiabilité visible ; blocages traités/acceptés ; aucune version concurrente devenue active. | Candidate → officielle active ; précédente supersédée ; contexte figé. | `PricingVersionApproved` | Prix : REBUILD ; Vue direction affaire : REBUILD ; Action Center : REBUILD ; Coffre : INVALIDATE ; Journal : APPEND. | Immédiate à validation ; idempotence obligatoire. |
| M-075 | `MarkPricingForReview` | Prix | Transition d’état / obsolescence | Changement matériel identifié. | Prix actif marqué à revoir ; action de revue créée/regroupée. | `PricingMarkedForReview` | Prix : REBUILD ; Affaire : REBUILD ; Coffre : INVALIDATE ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate. |
| M-080 | `RunSubmissionControl` | Dépôt | Évaluation / création d’actions | DCE, pièces et versions disponibles. | Rapport de contrôle daté ; actions/causes créées ou enrichies. | `SubmissionControlCompleted` | Coffre : REBUILD ; Actions : REBUILD ; Affaire : ASYNC_REFRESH ; Journal : APPEND. | Différée acceptable si affichée « contrôle en cours » ; résultat cohérent obligatoire. |
| M-081 | `PrepareSubmissionPackage` | Paquet de dépôt | Création de version | Contrôles non bloquants ; prix officiel actif si requis ; DCE applicable connu. | Paquet immuable créé avec snapshot DCE/prix/documents/décision. | `SubmissionPackagePrepared` | Coffre : REBUILD ; Affaire : ASYNC_REFRESH ; Journal : APPEND. | Immédiate à constitution ; idempotence obligatoire. |
| M-082 | `AuthorizeSubmission` | Dépôt / Autorisation | Transition d’état | Patron/habilité ; paquet à jour ; blocages traités ; conditions de signature visibles. | Paquet → Prêt pour dépôt ; autorisation, empreinte, acteur et date enregistrés. | `SubmissionAuthorized` | Coffre : REBUILD ; Affaire : REBUILD ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate ; idempotence obligatoire. |
| M-083 | `RecordSubmission` | Dépôt | Transition d’état | Déposant/habilité ; paquet et plateforme identifiés ; date/heure déclarées. | Dépôt déclaré, en attente d’accusé. | `SubmissionRecorded` | Coffre : REBUILD ; Affaire : REBUILD ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Immédiate ; idempotence obligatoire. |
| M-084 | `ArchiveSubmissionAcknowledgement` | Dépôt / Preuve | Création + transition | Dépôt déclaré ; preuve originale/confirmation disponible. | Accusé archivé et relié au paquet/dépôt. | `SubmissionAcknowledgementArchived` | Coffre : REBUILD ; Affaire : REBUILD ; Journal : APPEND. | Immédiate ; idempotence obligatoire. |
| M-085 | `OpenNewResponseVersion` | Réponse / Paquet | Création de version | Motif ; dépôt précédent conservé. | Nouvelle préparation liée à version/dépôt antérieur. | `ResponseVersionOpened` | Affaire : REBUILD ; Coffre : REBUILD ; Prix : INVALIDATE si impact ; Journal : APPEND. | Immédiate. |

## 27. Commandes de version DCE, impact et journal

| ID V8.1 | Commande normalisée | Frontière métier propriétaire | Type de changement | Préconditions/invariants principaux | Postconditions | Fait métier produit | Situations préparées impactées | Cohérence |
|---|---|---|---|---|---|---|---|---|
| M-090 | `RegisterDceVersion` | DCE de l’affaire | Création de version | Pièce reçue, affaire/consultation identifiable, origine connue. | Nouvelle version DCE immuable, liée à précédente si applicable. | `DceVersionRegistered` | Affaire : INVALIDATE ; Analyse : ASYNC_REFRESH ; Prix : INVALIDATE ; Coffre : INVALIDATE ; Journal : APPEND. | Immédiate pour version ; différée visible pour analyse. |
| M-091 | `AssessDceChangeImpact` | Impact de changement d’affaire | Création + relations | Ancienne/nouvelle version accessibles ; analyse/validation de l’impact. | Éléments impactés, obsolescences, actions de revue et motifs conservés. | `DceChangeImpactAssessed` | Affaire : REBUILD ; Actions : REBUILD ; Prix : REBUILD/INVALIDATE ; Coffre : INVALIDATE ; Accueil : ASYNC_REFRESH ; Journal : APPEND. | Résultat cohérent obligatoire ; traitement peut être affiché en cours. |
| M-092 | `InspectBusinessProvenance` | Aucune mutation | Consultation | Source/fait accessible ou indisponibilité connue. | Aucun changement d’état métier. | Aucun fait métier obligatoire ; audit sensible optionnel. | Aucune situation métier modifiée. | Lecture cohérente. |
| M-093 | `ExportBusinessTimeline` | Export / Journal | Création d’artefact | Patron/habilité ; périmètre/droits respectés. | Export identifié, auteur, date, périmètre et motif éventuel. | `BusinessTimelineExported` | Journal/audit : APPEND ; aucune situation métier d’affaire. | Immédiate. |

## 28. Frontières métier provisoires à confirmer dans le Contrat de domaine

La continuité métier de l’Affaire reste complète dans l’interface. Elle ne doit toutefois pas produire une frontière transactionnelle géante. Le Contrat de domaine devra confirmer les frontières suivantes sans modifier le parcours utilisateur :

| Frontière métier provisoire | Responsabilité principale | Ne doit pas absorber |
|---|---|---|
| **Affaire** | Identité continue, état global, liens aux consultations et contexte commercial. | Tous les détails de prix, dépôt, preuves, tâches et décisions. |
| **Action patron** | Cycle de vie d’une action, causes, responsable, attente, résolution et remplacement. | Le contenu complet de la décision ou toutes les tâches d’exécution. |
| **Décision** | Contexte figé, choix, conditions, approbation, supersession. | Le calcul de prix ou l’analyse détaillée DCE. |
| **Preuve / Capacité** | Version, validité, droit d’usage, périmètre et autorisation. | Toute l’affaire où la preuve est utilisée. |
| **Prix** | Scénarios, hypothèses, versions candidates/officielles, fiabilité et obsolescence. | Le dépôt final ou l’ensemble des documents de réponse. |
| **Paquet et dépôt** | Snapshot de préparation, autorisation, dépôt déclaré et accusé. | Les règles de calcul ou les décisions antérieures. |
| **Affectation / délégation** | Relations de travail et d’accès limitées. | Les informations financières ou la décision patron elle-même. |

---

## 29. Passage au Contrat de domaine V8

Cette passe V8.2 fournit désormais la chaîne nécessaire :

```text
Vue → Intention → Commande normalisée → Frontière métier propriétaire
    → Préconditions + invariants → Création / relation / transition / version
    → Postconditions → Fait métier → Situations préparées impactées → Interface
```

Le Contrat de domaine V8 devra reprendre chaque commande de cette matrice et définir, pour chaque frontière métier : ses responsabilités, ses états autorisés, ses invariants, ses événements, ses relations et ses règles de concurrence.

> **Règle de passage :** le Contrat de domaine ne doit pas créer un « agrégat Affaire » géant. La continuité de l’Affaire appartient à l’expérience utilisateur ; les frontières transactionnelles doivent rester proportionnées aux mutations définies dans cette passe V8.2.
