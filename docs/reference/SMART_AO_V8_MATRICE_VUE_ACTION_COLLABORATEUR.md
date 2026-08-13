# SMART_AO V8 — Matrice Vue → Action : Espace collaborateur

**Version :** 1.0  
**Statut :** référence de transitions collaborateur à valider avant l’extension du Contrat de domaine et les commandes normalisées correspondantes.  
**Périmètre :** affectation, tâches, demandes, exigences, preuves, documents, réponse technique, préparation, transmission, retours patron et rectificatifs.

---

## 1. Objet de la matrice

Cette matrice traduit les boutons et actions de l’espace collaborateur en transitions métier non ambiguës. Elle complète le Contrat Métier vers Interface — Collaborateur.

Chaque ligne répond à sept questions :

1. **Dans quelle vue** le collaborateur agit-il ?
2. **Quelle intention** exprime-t-il ?
3. **Quelles conditions** doivent être satisfaites avant l’action ?
4. **Quelle frontière métier** garantit la transition ?
5. **Quel résultat durable** est enregistré ?
6. **Quel fait métier** est tracé ?
7. **Quelles vues** deviennent à actualiser ?

> **Règle :** un bouton ne modifie jamais directement un écran. Il exprime une intention qui doit être autorisée, vérifiée, enregistrée et projetée dans les vues concernées.

---

## 2. Convention de lecture

| Colonne | Signification |
|---|---|
| **Vue** | Écran ou zone de départ de l’action. |
| **Action / intention** | Ce que l’utilisateur demande au système. |
| **Préconditions** | Ce qui doit être vrai avant toute mutation. |
| **Frontière métier** | Réalité qui possède la mutation et garantit les invariants. |
| **Transition et résultat durable** | Changement conservé et reconstructible. |
| **Fait métier** | Événement durable à tracer ; il n’est pas une simple notification technique. |
| **Vues à actualiser** | Situations préparées à recalculer ; elles peuvent être rafraîchies après la transaction mais doivent afficher leur fraîcheur. |
| **Refus explicite** | Motif lisible si l’action est bloquée. |

Les événements utilisent un vocabulaire métier français. Le futur code pourra leur associer des noms normalisés, sans faire dériver le sens fonctionnel.

---

## 3. Invariants communs collaborateur

| ID | Invariant |
|---|---|
| `COL-INV-01` | Toute lecture ou action collaborateur exige une affectation active et un périmètre autorisant la ressource et l’action demandées. |
| `COL-INV-02` | Une donnée exclue du périmètre — notamment prix privé, marge, trésorerie et devis confidentiel — n’est jamais incluse dans une réponse destinée au collaborateur. |
| `COL-INV-03` | Une tâche ne peut être terminée que si ses dépendances critiques sont satisfaites ou si une dérogation patron est explicitement enregistrée. |
| `COL-INV-04` | Une exigence issue du DCE ne peut être confirmée sans source/version ; une contradiction doit référencer au moins deux sources. |
| `COL-INV-05` | Une demande, une tâche, une revue, un message et une décision sont des objets distincts et ne se substituent jamais silencieusement. |
| `COL-INV-06` | Une transmission au patron contient un instantané figé ; elle ne désigne jamais l’état mutable de l’affaire au moment où le patron la consulte. |
| `COL-INV-07` | Un rectificatif DCE ne supprime aucun travail historique ; il crée des impacts et rend des éléments à revoir ou obsolètes. |
| `COL-INV-08` | Un collaborateur ne peut ni valider un prix, ni accepter un risque patron, ni autoriser un dépôt, ni décider seul le Go/No-Go. |
| `COL-INV-09` | Un partage externe porte sur des versions explicitement autorisées, expire à une date définie et ne s’élargit jamais automatiquement. |
| `COL-INV-10` | Toute action critique est idempotente : la répétition de la même intention n’engendre pas un second travail, une seconde transmission ou une seconde demande. |

---

## 4. Affectations et démarrage du travail

| ID | Vue | Action / intention | Préconditions | Frontière métier | Transition et résultat durable | Fait métier | Vues à actualiser | Refus explicite |
|---|---|---|---|---|---|---|---|---|
| `COL-01` | Mes affaires / notification | **Prendre connaissance de mon affectation** | Affectation active ; collaborateur destinataire. | Affectation | L’affectation est reconnue par la personne, avec date de lecture. | `Affectation reconnue` | Mon travail aujourd’hui, Mes affaires, activité patron limitée. | « Cette affectation n’est plus active. » |
| `COL-02` | Mes affaires | **Demander clarification du périmètre** | Affectation active ; question décrite. | Demande | Demande au patron créée, liée à l’affectation et au périmètre ambigu. | `Clarification d’affectation demandée` | En attente de moi, file d’Actions patron, historique. | « Décrivez ce qui manque dans votre périmètre. » |
| `COL-03` | Mes affaires / tâche | **Signaler indisponibilité** | Affectation active ; raison et période renseignées. | Affectation + Demande | Indisponibilité enregistrée ; patron averti si une échéance est concernée. | `Indisponibilité collaborateur signalée` | Mes affaires, tâches concernées, Action patron éventuelle. | « Indiquez la période ou la contrainte qui empêche le travail. » |
| `COL-04` | Accueil | **Ouvrir une affaire attribuée** | Affectation active × périmètre de lecture autorisé. | Affectation | Aucune mutation durable requise ; accès contrôlé. | Aucun fait métier obligatoire. | Aucun ; vue C-03 affichée. | « Vous n’avez plus accès à cette affaire. » |

---

## 5. DCE, documents et versions

| ID | Vue | Action / intention | Préconditions | Frontière métier | Transition et résultat durable | Fait métier | Vues à actualiser | Refus explicite |
|---|---|---|---|---|---|---|---|---|
| `COL-10` | Documents DCE | **Confirmer le classement d’une pièce** | Affectation + accès document ; type de pièce sélectionné. | Document / Classification | Classification humaine ajoutée ou corrigée ; original inchangé. | `Classement de pièce confirmé` | Inventaire DCE, progression Documents, journal affaire. | « Cette pièce n’est plus accessible dans votre périmètre. » |
| `COL-11` | Documents DCE | **Signaler une pièce manquante** | Famille ou pièce attendue identifiée ; motif renseigné. | DCE / Constat | Constat de manque créé avec source de l’attente et état `manquante`. | `Pièce DCE manquante signalée` | Documents, Exigences, tâches, préparation. | « Indiquez quelle pièce est attendue et sur quelle source repose cette attente. » |
| `COL-12` | Documents DCE | **Déclarer un fichier illisible** | Document existant ; description du problème. | Document / Constat | Incident de lecture enregistré ; document marqué à revoir. | `Lecture de document à revoir signalée` | Documents, tâches, contrat de préparation. | « Précisez la page ou la partie illisible. » |
| `COL-13` | Documents DCE | **Comparer deux versions DCE** | Deux versions autorisées ; version source et cible disponibles. | Version DCE / Impact | Comparaison demandée ou consultée ; aucune décision automatique. | `Comparaison de versions consultée` | Documents, Impact DCE. | « Les deux versions nécessaires ne sont pas disponibles. » |
| `COL-14` | Documents DCE | **Déclarer un document non applicable** | Justification, source ou règle entreprise ; aucun conflit actif. | Document préparé | Statut `non applicable`, motif, auteur et date conservés. | `Document déclaré non applicable` | Documents, contrôle de préparation. | « Un document critique ne peut pas être déclaré non applicable sans motif sourcé. » |
| `COL-15` | Documents préparés | **Soumettre un document à revue** | Brouillon existant ; relecteur autorisé ; version identifiée. | Revue | Revue ouverte sur une version précise ; document `à relire`. | `Revue documentaire demandée` | Documents, tâches, demandes reçues du relecteur. | « Sélectionnez un relecteur et une version de document. » |
| `COL-16` | Documents préparés | **Proposer un document pour le paquet** | Document dans un état compatible ; version et source identifiées. | Paquet de préparation | Document ajouté comme candidat au paquet vivant ; pas encore figé. | `Document proposé au paquet` | Documents, contrôle de préparation, aperçu du paquet. | « Ce document est obsolète, expiré ou n’a pas été revu. » |

---

## 6. Exigences, constats et dépendances

| ID | Vue | Action / intention | Préconditions | Frontière métier | Transition et résultat durable | Fait métier | Vues à actualiser | Refus explicite |
|---|---|---|---|---|---|---|---|---|
| `COL-20` | Exigences | **Confirmer une exigence** | Source DCE, version, page/extrait, libellé et nature renseignés. | Exigence | Exigence passe à `confirmée`, avec provenance intégrale. | `Exigence confirmée` | Exigences, tâches, contrôle de préparation, vue patron affaire. | « Une exigence ne peut pas être confirmée sans source DCE précise. » |
| `COL-21` | Exigences | **Marquer une exigence à vérifier** | Motif et élément ambigu renseignés. | Exigence | État `à vérifier` + tâche/revue proposée ou créée. | `Exigence à vérifier signalée` | Exigences, tâches, préparation. | « Indiquez ce qui rend cette exigence incertaine. » |
| `COL-22` | Exigences | **Signaler une contradiction** | Deux sources/version/extraits référencés. | Exigence + Constat | Constat contradictoire durable, relié aux deux sources et à une question/tâche. | `Contradiction DCE signalée` | Exigences, tâches, demandes, vue patron si criticité importante. | « Une contradiction doit référencer deux sources incompatibles. » |
| `COL-23` | Exigences | **Associer une tâche à une exigence** | Exigence visible ; action attendue, responsable et échéance définis. | Tâche | Tâche créée, liée à l’exigence et à la preuve attendue. | `Tâche créée depuis exigence` | Tâches, étape wizard, contrôle de préparation. | « Affectez un responsable ou signalez que le responsable est à décider. » |
| `COL-24` | Tâches | **Ajouter une dépendance** | Deux tâches distinctes, justification fournie ; aucune boucle de dépendance. | Tâche / Dépendance | Relation de dépendance durable créée. | `Dépendance de tâche ajoutée` | Tâches, recommandation prochaine tâche, état d’étape. | « Cette dépendance créerait une boucle ou est déjà satisfaite. » |
| `COL-25` | Tâches | **Supprimer une dépendance** | Auteur autorisé ; justification ; tâche non terminée de manière irréversible. | Tâche / Dépendance | Dépendance retirée avec historique. | `Dépendance de tâche retirée` | Tâches, préparation. | « Cette dépendance est requise par une règle de préparation ou une action patron. » |

---

## 7. Exécution des tâches et revues

| ID | Vue | Action / intention | Préconditions | Frontière métier | Transition et résultat durable | Fait métier | Vues à actualiser | Refus explicite |
|---|---|---|---|---|---|---|---|---|
| `COL-30` | Accueil / Tâches | **Prendre en charge une tâche** | Affectation active ; tâche disponible ou assignée au collaborateur. | Tâche | État `en cours`, acteur et horodatage enregistrés. | `Tâche prise en charge` | Mon travail aujourd’hui, Mes tâches, affaire. | « Cette tâche est affectée à une autre personne ou votre périmètre ne l’autorise pas. » |
| `COL-31` | Tâche | **Enregistrer un résultat de travail** | Tâche active ; contenu, source ou brouillon fourni. | Tâche | Résultat versionné ajouté à la tâche ; sauvegarde de brouillon. | `Résultat de tâche enregistré` | Tâche, affaire, documents/réponse concernés. | « Le résultat doit indiquer ce qui a été vérifié, préparé ou constaté. » |
| `COL-32` | Tâche | **Signaler un blocage** | Cause ou dépendance renseignée. | Tâche + Demande éventuelle | État `bloquée` ou `en attente`; demande/tâche de déblocage créée si nécessaire. | `Tâche bloquée signalée` | Accueil, tâches, contrôle de préparation, Action patron si requis. | « Indiquez ce qui bloque et l’information ou la personne attendue. » |
| `COL-33` | Tâche | **Demander une revue** | Élément précis, version et relecteur autorisé. | Revue | Revue créée ; tâche `prête à relire`. | `Revue de travail demandée` | Tâches, demandes/revues, activité. | « Un brouillon ou une preuve précise doit être soumis à revue. » |
| `COL-34` | Revue | **Accepter une revue** | Relecteur autorisé ; version inchangée depuis l’ouverture ou version explicitement revue. | Revue | Revue acceptée ; objet validé pour le niveau de revue concerné. | `Revue acceptée` | Documents, tâche, contrôle de préparation. | « Une version plus récente existe ; revoyez la version actuelle. » |
| `COL-35` | Revue | **Retourner avec correction** | Relecteur autorisé ; motif et corrections demandées renseignés. | Revue + Tâche | Revue retournée ; tâche créée/réouverte avec corrections ciblées. | `Revue retournée avec corrections` | Tâches, affaire, accueil collaborateur concerné. | « Indiquez les corrections à réaliser et leur lien avec l’objet revu. » |
| `COL-36` | Tâche | **Terminer une tâche** | Preuve de fin présente ; dépendances bloquantes satisfaites ou dérogation explicite. | Tâche | État `terminée`, résultat et preuve de fin figés. | `Tâche terminée` | Tâches, progression étape, contrôle de préparation. | « Cette tâche dépend encore d’un élément bloquant non résolu. » |
| `COL-37` | Tâche | **Remplacer une tâche** | Motif, nouvelle tâche et lien de remplacement fournis. | Tâche | Ancienne tâche `remplacée`, nouvelle tâche créée/associée. | `Tâche remplacée` | Tâches, historique, prochaine recommandation. | « La tâche doit être remplacée par un travail identifiable, pas seulement masquée. » |
| `COL-38` | Tâche | **Abandonner avec motif** | Autorisation suffisante ; motif et impact renseignés. | Tâche | État `abandonnée avec motif`; contrôle de préparation recalculé. | `Tâche abandonnée` | Tâches, préparation, Action patron si criticité importante. | « Une tâche bloquante exige une décision ou dérogation patron. » |

---

## 8. Demandes, réponses et partage externe

| ID | Vue | Action / intention | Préconditions | Frontière métier | Transition et résultat durable | Fait métier | Vues à actualiser | Refus explicite |
|---|---|---|---|---|---|---|---|---|
| `COL-40` | Demandes | **Créer une demande interne** | Destinataire, affaire, objet demandé, raison et délai/priorité renseignés. | Demande | Demande ouverte, liée à l’affaire et à l’objet concerné. | `Demande interne créée` | Mes attentes, destinataire, tâche source, activité. | « Précisez ce qui est demandé et pourquoi. » |
| `COL-41` | Demandes | **Créer une demande partenaire** | Besoin partenaire autorisé ; périmètre, ressources et durée validés. | Demande + Partage externe | Demande et partage versionné créés, limités à l’objet autorisé. | `Demande partenaire créée` + `Partage externe accordé` | Demandes, partenaires, contrôle de préparation, journal affaire. | « Ce document ou ce périmètre n’est pas autorisé au partage externe. » |
| `COL-42` | Demandes reçues | **Répondre à une demande** | Demande active ; réponse ou ressource autorisée fournie. | Demande / Réponse | Réponse enregistrée et reliée à la demande. | `Réponse à demande reçue` | Demandes, tâche/revue liée, activité. | « Cette demande est expirée, annulée ou hors de votre périmètre. » |
| `COL-43` | Réponse reçue | **Créer une revue depuis une réponse** | Réponse disponible ; élément à contrôler et relecteur renseignés. | Revue | Revue créée ; la réponse n’est pas encore une preuve validée. | `Réponse soumise à revue` | Revues, tâche liée, documents/capacités. | « Sélectionnez l’élément précis que cette réponse permet de vérifier. » |
| `COL-44` | Partage externe | **Révoquer un partage** | Autorisation de révocation ; partage actif. | Partage externe | Partage révoqué avec date/motif ; accès partenaire retiré. | `Partage externe révoqué` | Partenaires, demandes, activité. | « Ce partage n’est plus actif. » |
| `COL-45` | Demandes | **Relancer une demande** | Demande active, non close ; délai de relance respecté. | Demande | Relance ajoutée sans recréer la demande initiale. | `Demande relancée` | Demandes, activité, tâche en attente. | « Cette demande est déjà clôturée ou une relance a été envoyée trop récemment. » |

---

## 9. Capacités, preuves et réponse technique

| ID | Vue | Action / intention | Préconditions | Frontière métier | Transition et résultat durable | Fait métier | Vues à actualiser | Refus explicite |
|---|---|---|---|---|---|---|---|---|
| `COL-50` | Terrain & capacités | **Proposer une capacité pour l’affaire** | Capacité visible dans le périmètre ; version/preuve connue. | Affaire / Capacité proposée | Proposition liée à l’affaire avec état de validité. | `Capacité proposée pour affaire` | Capacités, réponse technique, préparation patron. | « Cette capacité est expirée, non autorisée ou hors de votre périmètre. » |
| `COL-51` | Terrain & capacités | **Signaler une capacité manquante ou expirée** | Besoin lié à une exigence ou tâche. | Constat + Tâche/Demande | Manque signalé ; action de renouvellement ou décision créée. | `Capacité insuffisante signalée` | Capacités, tâches, risques, Action patron si critique. | « Reliez ce manque à une exigence, une tâche ou un besoin précis. » |
| `COL-52` | Réponse technique | **Enregistrer un brouillon de réponse** | Affectation et responsabilité de rédaction autorisées. | Brouillon de réponse | Nouvelle version brouillon enregistrée ; jamais un engagement automatique. | `Brouillon de réponse enregistré` | Réponse technique, tâches, contrôle de préparation. | « Votre périmètre n’autorise pas la modification de cette section. » |
| `COL-53` | Réponse technique | **Déclarer un engagement candidat** | Phrase/section précise, type d’engagement et source renseignés. | Engagement candidat | Engagement candidat lié au brouillon, capacité/moyen/responsable ou hypothèse. | `Engagement candidat identifié` | Réponse technique, revues, préparation. | « Un engagement candidat doit pointer vers une phrase et une source de capacité ou hypothèse. » |
| `COL-54` | Réponse technique | **Demander validation d’un engagement** | Engagement candidat complet ; relecteur autorisé. | Revue d’engagement | Revue créée ; l’engagement reste candidat. | `Validation d’engagement demandée` | Revues, réponse, transmission. | « Cet engagement ne possède pas encore de capacité, responsable ou hypothèse associée. » |
| `COL-55` | Réponse technique | **Proposer un élément réutilisable** | Élément versionné, origine connue, compatibilité à contrôler. | Compatibilité d’élément réutilisable | Proposition de réemploi créée pour l’affaire, sans copie automatique. | `Élément réutilisable proposé` | Réponse, revues, préparation. | « L’origine ou la version de cet élément n’est pas connue. » |
| `COL-56` | Réponse technique | **Accepter la compatibilité d’un élément réutilisable** | Relecteur autorisé ; contrôle nouveau DCE réalisé. | Compatibilité d’élément réutilisable | Élément accepté/rejeté/à revoir pour l’affaire actuelle. | `Compatibilité de réemploi décidée` | Réponse technique, préparation, historique. | « La compatibilité doit être vérifiée pour l’affaire actuelle. » |

---

## 10. Préparation, instantané et transmission patron

| ID | Vue | Action / intention | Préconditions | Frontière métier | Transition et résultat durable | Fait métier | Vues à actualiser | Refus explicite |
|---|---|---|---|---|---|---|---|---|
| `COL-60` | Contrôle de préparation | **Exécuter le contrôle de préparation** | Affectation active ; affaire et règles disponibles. | Paquet de préparation / Readiness | Évaluation de préparation calculée avec critères, blocages, dérogations et date de référence. | `Contrôle de préparation exécuté` | Contrôle, affaire, transmission. | « Le contrôle ne peut pas être exécuté car la version DCE active est indisponible. » |
| `COL-61` | Contrôle de préparation | **Demander une dérogation patron** | Élément bloquant identifié ; motif et impact transmis. | Demande + Action patron | Demande de dérogation créée ; blocage reste visible. | `Dérogation de préparation demandée` | Contrôle, file patron, tâches. | « Une dérogation doit viser un blocage précis. » |
| `COL-62` | Contrôle de préparation | **Déclarer la préparation prête pour revue** | Contrôle favorable ou dérogations explicites ; collaborateur responsable. | Paquet de préparation | Paquet passe à `prêt pour revue`; liste de contenu vivante conservée. | `Préparation déclarée prête pour revue` | Transmission, affaire, Action patron potentielle. | « Les éléments bloquants listés doivent être résolus ou dérogés. » |
| `COL-63` | Transmission | **Prévisualiser l’instantané** | Paquet prêt pour revue ; contrôle récent. | Paquet de préparation | Aucune mutation ; contenu qui serait figé présenté. | Aucun fait métier obligatoire. | Aucun. | « Le contrôle de préparation doit être relancé car des éléments ont changé. » |
| `COL-64` | Transmission | **Transmettre au patron** | Affectation + permission de transmettre ; paquet prêt ; contrôle valide ; aucun prix privé inclus. | Transmission + Instantané de préparation | Instantané versionné créé, transmission `transmise au patron`, action patron de revue créée. | `Instantané de préparation créé` + `Préparation transmise au patron` | Affaire collaborateur, Command Center patron, Actions patron, Journal de vérité. | « La préparation ne peut pas être transmise : [liste des blocages précis]. » |
| `COL-65` | Transmission | **Retirer une transmission non reçue** | Transmission non reçue par patron ; auteur ou autorisation suffisante. | Transmission | Transmission retirée ; snapshot reste archivé mais non actif. | `Transmission retirée avant réception` | Affaire, Actions patron, journal. | « Le patron a déjà reçu cette transmission ; demandez plutôt un retour ou créez une nouvelle préparation. » |
| `COL-66` | Retour patron | **Prendre en compte un retour patron** | Retour ciblé, affectation active. | Tâche + Transmission | Tâches de correction créées/réouvertes ; transmission passée à `retournée`. | `Retour patron pris en compte` | Accueil, tâches, affaire, transmission. | « Ce retour concerne une affectation qui n’est plus active. » |
| `COL-67` | Affaire / Transmission | **Reprendre après acceptation patron** | Patron a accepté pour phase suivante ; nouvelle demande de préparation ou rectificatif existe. | Paquet + Transmission | Nouveau cycle de préparation ouvert, ancien snapshot conservé. | `Nouveau cycle de préparation ouvert` | Affaire, tâches, transmission. | « Aucun retour, rectificatif ou nouveau périmètre ne justifie un nouveau cycle. » |

---

## 11. Rectificatifs et évaluation d’impact

| ID | Vue | Action / intention | Préconditions | Frontière métier | Transition et résultat durable | Fait métier | Vues à actualiser | Refus explicite |
|---|---|---|---|---|---|---|---|---|
| `COL-70` | Impact DCE | **Lancer l’évaluation d’impact** | Nouvelle version DCE active ; ancienne version connue ou changement déclaré. | Évaluation d’impact | Impacts calculés/enregistrés sur exigences, tâches, documents, réponse et transmissions. | `Impact de version DCE évalué` | Impact DCE, tâches, étapes, contrôle, Action patron. | « La comparaison nécessite une version source et une version cible. » |
| `COL-71` | Impact DCE | **Marquer un élément à revoir** | Élément impacté identifié ; motif/source du changement. | Tâche / Document / Brouillon | État `à revoir` avec lien vers l’impact. | `Élément marqué à revoir` | Tâches, documents, réponse, préparation. | « L’impact ou la source du changement est requis. » |
| `COL-72` | Impact DCE | **Confirmer qu’un élément reste valide** | Revue réalisée sur la version active. | Revue | L’élément est déclaré compatible avec la nouvelle version, avec auteur/date. | `Compatibilité après rectificatif confirmée` | Impact DCE, tâche/document concerné, préparation. | « Une revue de la version active est nécessaire avant confirmation. » |
| `COL-73` | Impact DCE | **Invalider un instantané transmis** | Impact bloquant sur contenu snapshot ; version DCE postérieure. | Transmission + Instantané | Snapshot marqué non actuel ; patron averti ; nouvelle préparation requise si nécessaire. | `Instantané de préparation invalidé` | Transmission, Actions patron, affaire, journal. | « Cet instantané ne dépend pas de l’élément impacté. » |

---

## 12. Effets sur les vues patron

L’espace collaborateur ne décide pas ; il alimente les vues patron par des faits préparatoires précis.

| Fait collaborateur | Effet patron autorisé |
|---|---|
| Pièce manquante ou contradiction critique | Action patron si décision ou demande acheteur nécessaire. |
| Capacité insuffisante | Risque ou décision patron selon criticité. |
| Préparation transmise | Nouvelle Action patron « Revoir la préparation ». |
| Transmission reçue | Dossier de décision mis à jour avec instantané exact. |
| Retour patron | Tâches de correction visibles au collaborateur. |
| Rectificatif impactant | Action patron si un prix, une décision ou un paquet de dépôt pourrait être devenu obsolète. |
| Partage externe créé/révoqué | Journal de vérité et suivi partenaire. |

Aucun fait collaborateur ne valide seul le prix, le Go/No-Go, une dérogation de risque ou le dépôt.

---

## 13. Critères de recette de la matrice

| ID | Vérification |
|---|---|
| `CMAT-01` | Chaque action critique est reliée à une affectation et à un périmètre, pas seulement à un rôle utilisateur. |
| `CMAT-02` | Toute tâche terminée possède un résultat, une preuve de fin ou une dérogation tracée. |
| `CMAT-03` | Une réponse à une demande ne clôture jamais silencieusement une tâche critique. |
| `CMAT-04` | Un rectificatif rend à revoir uniquement les éléments affectés et conserve les versions antérieures. |
| `CMAT-05` | Une transmission patron crée un instantané figé et non une référence à l’état mutable de l’affaire. |
| `CMAT-06` | Une transmission avec un blocage non dérogé est refusée avec la liste exacte des éléments bloquants. |
| `CMAT-07` | Un collaborateur ne reçoit aucune donnée financière via les vues, les actions, les erreurs ou les projections. |
| `CMAT-08` | Une action répétée avec la même intention ne crée pas de doublon de tâche, demande, partage ou transmission. |
| `CMAT-09` | Une nouvelle version DCE ne s’ajoute jamais automatiquement à un partage partenaire actif. |
| `CMAT-10` | Toute vue affiche si sa situation est à jour, partielle, à vérifier, obsolète ou indisponible. |

---

## 14. Suite documentaire

Cette matrice prépare l’extension collaborateur du Contrat de domaine V8. Les frontières à définir sont : **Affectation**, **Tâche**, **Demande**, **Revue**, **Paquet de préparation**, **Instantané de préparation**, **Transmission**, **Partage externe** et **Évaluation d’impact**.

## 15. Révision V8.1 — Matrice Vue → Intention → Commande → Transition

La matrice précédente reste la référence des transitions visibles. Cette révision ajoute les colonnes structurelles nécessaires pour que l’interface n’absorbe pas le métier et que chaque commande soit sécurisée contre les droits insuffisants, la concurrence et les répétitions réseau.

```text
Vue
  ↓
Intention utilisateur
  ↓
Commande normalisée
  ↓
Autorisation contextualisée
  ↓
Préconditions et invariants
  ↓
Frontière métier propriétaire
  ↓
Transition et postconditions
  ↓
Fait métier
  ↓
Instantané éventuel et situations préparées
```

### 15.1. Colonnes normatives supplémentaires

| Colonne V8.1 | Règle |
|---|---|
| **Commande** | Intention stable émise par l’interface ; elle n’est jamais remplacée par une mutation UI directe. |
| **Classe de ressource** | Document, preuve, opérationnel, partenaire, financier ou stratégique ; détermine le périmètre de sécurité. |
| **Contexte d’accès** | Acteur × affectation active × périmètre × classe de ressource × action × état de l’affaire. |
| **Version attendue** | Version de l’objet sensible connue de l’interface au moment de la commande. |
| **Idempotence** | Clé obligatoire pour les créations, transmissions, demandes, partages, rattachements et remplacements critiques. |
| **Concurrence** | Les conflits de version sont explicitement refusés ; aucune écriture silencieuse de type « dernier écrit gagne ». |
| **Cohérence** | `stricte` avant résultat critique ; `différée` seulement pour l’actualisation d’une vue, avec fraîcheur visible. |
| **Instantané** | Référence à l’instantané immuable créé ou invalidé, lorsque l’action touche une transmission. |

### 15.2. Commandes et contexte de ressources

| Lignes de la matrice | Commande normalisée | Classe principale | Cohérence | Idempotence |
|---|---|---|---|---|
| `COL-01` à `COL-04` | `AcknowledgeAssignment`, `RequestAssignmentClarification`, `ReportAssignmentUnavailability` | OperationalClass | Stricte pour tout changement d’affectation ; différée pour l’accueil. | Requise pour demande et signalement. |
| `COL-10` à `COL-16` | `ConfirmDocumentClassification`, `DeclareMissingDocument`, `ReportUnreadableDocument`, `RequestDocumentReview`, `ProposeDocumentForPreparation` | DocumentClass | Stricte sur la classification et la version ; différée pour les listes. | Requise pour incidents, revues et propositions. |
| `COL-20` à `COL-25` | `ConfirmRequirement`, `MarkRequirementUnverified`, `DeclareRequirementConflict`, `CreateTaskFromRequirement`, `AddTaskDependency`, `RemoveTaskDependency` | OperationalClass | Stricte : les exigences et dépendances fondent la préparation. | Requise pour création de tâche et liens de dépendance. |
| `COL-30` à `COL-38` | `ClaimTask`, `RecordTaskResult`, `DeclareTaskBlocker`, `RequestReview`, `AcceptReview`, `ReturnReviewWithCorrections`, `CompleteTask`, `ReplaceTask`, `AbandonTaskWithReason` | OperationalClass | Stricte : état de tâche, responsabilités et preuve de fin. | Requise pour résultat, blocage, revue et fin de tâche. |
| `COL-40` à `COL-45` | `CreateRequest`, `CreatePartnerRequest`, `RecordRequestResponse`, `CreateReviewFromResponse`, `RevokeExternalShare`, `SendRequestReminder` | PartnerClass / OperationalClass | Stricte sur partage, révocation et réponse ; différée pour les compteurs. | Requise pour demande, partage, réponse et relance. |
| `COL-50` à `COL-56` | `ProposeCapabilityForCase`, `ReportCapabilityGap`, `SaveResponseDraft`, `DeclareCandidateCommitment`, `RequestCommitmentReview`, `ProposeReusableItem`, `DecideReusableItemCompatibility` | EvidenceClass / OperationalClass | Stricte sur une décision de compatibilité ; brouillon versionné. | Requise pour proposition, brouillon et demande de revue. |
| `COL-60` à `COL-67` | `EvaluatePreparationReadiness`, `RequestReadinessWaiver`, `DeclarePreparationReady`, `PreviewPreparationSnapshot`, `SubmitPreparationForPatronReview`, `WithdrawUnreceivedTransmission`, `AcknowledgePatronReturn`, `OpenNewPreparationCycle` | OperationalClass / StrategicClass filtrée | Stricte pour préparation, snapshot et transmission. | Obligatoire pour toute transmission/retour critique. |
| `COL-70` à `COL-73` | `EvaluateDceChangeImpact`, `MarkAffectedItemNeedsReview`, `ConfirmPostAmendmentCompatibility`, `InvalidatePreparationSnapshot` | DocumentClass / OperationalClass | Stricte pour l’impact et l’invalidation ; différée pour les listes. | Requise pour évaluation et invalidation. |

### 15.3. Autorisation contextualisée et non-escalation

Une permission d’interface ne garantit jamais une commande. Le serveur réévalue le contexte complet pour toute commande sensible :

```text
Autorisé ?
= acteur authentifié
  × affectation active
  × périmètre de l’affectation
  × classe de la ressource
  × verbe demandé
  × contexte de l’affaire
  × préconditions de la commande
```

| Verbe | Portée |
|---|---|
| `DISCOVER` | Savoir qu’une ressource existe. |
| `READ_METADATA` | Voir nom, statut, date, type et source courte. |
| `READ_CONTENT` | Lire le contenu ou l’extrait autorisé. |
| `DOWNLOAD` | Télécharger la version explicitement autorisée. |
| `COMMENT` | Ajouter un commentaire ou constat. |
| `EDIT_DRAFT` | Modifier un brouillon attribué. |
| `SUBMIT` | Soumettre un travail, une revue ou une transmission. |
| `SHARE` | Accorder un partage externe limité. |
| `VALIDATE` | Valider si l’affectation et la délégation le permettent. |

> **Non-escalation :** une navigation depuis un résumé vers un détail, un téléchargement ou un partage réévalue toujours l’autorisation. Aucun bouton ne peut élargir indirectement le périmètre collaborateur.

### 15.4. Tâches, blocages et demandes : précisions de transition

| Objet | Règle V8.1 |
|---|---|
| **Tâche** | Porte un propriétaire, un exécutant, un relecteur éventuel et un approbateur éventuel. |
| **Dépendance forte** | Empêche la fin de la tâche dépendante. |
| **Dépendance souple** | Produit un avertissement ; la tâche peut être terminée. |
| **Dépendance informationnelle** | Informe sans bloquer ni avertir par défaut. |
| **Blocage** | Objet explicable : type, objet bloquant, source, raison, propriétaire, date et résolution. |
| **Demande** | Cycle `préparée → envoyée → réponse reçue → en revue → acceptée / rejetée / à clarifier`. |
| **Réponse** | Ne clôt aucune tâche et ne devient pas preuve acceptée sans revue appropriée. |

### 15.5. Politique de préparation et instantané immuable

`EvaluatePreparationReadiness` ne renvoie pas un booléen. Il retourne une décision lisible :

| Résultat | Conditions | Effet sur la commande de transmission |
|---|---|---|
| `READY` | Aucun blocage ; critères satisfaits. | Transmission autorisée. |
| `READY_WITH_WARNINGS` | Pas de blocage ; avertissements importants/informationnels visibles. | Transmission autorisée avec avertissements dans le snapshot. |
| `BLOCKED` | Au moins un blocage non résolu ou non dérogé. | Transmission refusée avec trois listes : `blockers`, `warnings`, `informational`. |

`SubmitPreparationForPatronReview` suit obligatoirement cette séquence :

```text
Valider la préparation
  ↓
Créer PreparationSnapshot immuable
  ↓
Calculer snapshot_id + snapshot_version + content_hash
  ↓
Créer la transmission vers le patron
  ↓
Créer ou actualiser l’Action patron de revue
```

Un instantané contient les références aux versions exactes DCE, exigences, preuves, documents, états de tâches, demandes ouvertes, risques visibles, décisions demandées, affectation, auteur et date. L’empreinte de contenu permet de vérifier que le patron a reçu un état précis, sans réinterpréter l’affaire vivante ultérieurement.

### 15.6. Rectificatifs : impact produit par le domaine, affiché par l’interface

L’interface ne calcule jamais qu’une exigence, une tâche, un document ou un instantané est impacté. Elle affiche le résultat d’une évaluation métier.

```text
Nouvelle version DCE
  ↓
Commande EvaluateDceChangeImpact
  ↓
ImpactAssessment durable
  ↓
Exigences / tâches / documents / preuves / réponse / snapshot affectés
  ↓
Travail ciblé à revoir dans les vues collaborateur et alerte patron si nécessaire
```

| Scénario de rectificatif | Résultat attendu |
|---|---|
| Aucun impact métier | Aucun élément invalidé ; comparaison conservée. |
| Document seul affecté | Seul le document devient `à revoir` ; la préparation n’est pas globalement invalidée sans autre effet. |
| Délai de dépôt modifié | Date sourcée mise à jour ; priorités et échéances internes recalculées. |
| Exigence déjà transmise affectée | Snapshot historique conservé ; travail courant obsolète/à revoir ; patron averti. |

### 15.7. Concurrence et répétition

Les objets sensibles utilisent une concurrence optimiste : chaque commande porte une version attendue. Si la version réelle a changé, le système renvoie un conflit lisible, avec le fait connu et la ressource à recharger ; il ne remplace jamais silencieusement un brouillon, une tâche, une revue ou un document.

Les commandes critiques sont idempotentes. La même clé d’idempotence pour le même acteur, la même commande et le même périmètre retourne le premier résultat terminal ; elle ne crée pas un deuxième partage, une deuxième demande, une deuxième tâche ou une deuxième transmission.

| Cas | Résultat V8.1 |
|---|---|
| Double clic sur « Transmettre au patron » | Un seul snapshot et une seule transmission ; même résultat retourné. |
| Deux collaborateurs terminent une tâche | Première commande acceptée ; seconde commande idempotente si même intention, sinon conflit explicite. |
| Affectation retirée pendant une saisie | Brouillon conservé ; commande suivante refusée après contrôle serveur. |
| Deux personnes modifient un document sensible | Conflit de version ; comparaison/reprise requise. |

### 15.8. Historiques et données de vue

| Concept | Rôle |
|---|---|
| **Timeline collaborateur** | Travail directement observable dans les affaires accessibles. |
| **Journal métier** | Faits importants d’affaire : transmission, changement DCE, décision, version, partage. |
| **Audit de sécurité** | Tentatives d’accès, commandes, droits et événements techniques ; jamais une vue de travail. |
| **Entrées de vue** | Données autorisées nécessaires pour préparer une situation affichée. |
| **Données affichées** | Sous-ensemble strictement autorisé envoyé au navigateur. |

Une donnée peut servir à un calcul autorisé côté système sans être transmise à la vue collaborateur.

## Références internes

- `SMART_AO_V8_CAHIER_ESPACE_COLLABORATEUR.md`
- `SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE_COLLABORATEUR.md`
- `SMART_AO_V8_MATRICE_TRANSITIONS_METIER.md`
- `SMART_AO_V8_CONTRAT_DE_DOMAINE.md`

---

**Fin de la Matrice Vue → Action — Collaborateur — version 1.0**
