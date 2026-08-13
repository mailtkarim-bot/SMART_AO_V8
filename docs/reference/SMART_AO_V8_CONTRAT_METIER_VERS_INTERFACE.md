# SMART_AO V8 — Contrat Métier vers Interface

**Version :** 1.0  
**Statut :** document de référence à valider avant le contrat de domaine et tout code de l’espace patron  
**Périmètre :** patron administrateur uniquement ; le contrat collaborateur sera écrit séparément après validation  
**Documents amont :** Vision fonctionnelle SMART_AO V8, Cahier de l’espace patron V8.2, Référence d’architecture et d’infrastructure V8.

---

## 1. Objet du contrat

Ce document est le pont entre le métier BTP et les futurs écrans de SMART_AO. Il ne décrit ni tables de base de données, ni classes, ni API, ni technologies. Il décrit ce que l’interface doit permettre au patron de comprendre, de vérifier, de décider et de protéger.

Chaque vue doit répondre à une **question métier unique**. Pour éviter les écrans décoratifs, elle doit aussi préciser :

| Élément contractuel | Ce que cela signifie |
|---|---|
| **Question métier** | La question que le patron doit pouvoir résoudre grâce à cette vue. |
| **Utilisateur autorisé** | Qui peut ouvrir la vue et qui ne peut pas y accéder. |
| **Situation d’arrivée** | À quel moment le patron ouvre cette vue. |
| **Données nécessaires** | Les informations que la vue doit recevoir pour être utile. |
| **Source de vérité** | L’origine de chaque information : DCE, pièce d’entreprise, déclaration humaine, décision ou calcul validé. |
| **États affichés** | Les états métier possibles, jamais des états techniques. |
| **Actions autorisées** | Ce que le patron peut demander, décider ou valider. |
| **Conditions de passage** | Ce qui bloque ou autorise une décision, une transmission ou un dépôt. |
| **Erreurs et limites** | Ce que SMART_AO doit dire clairement lorsqu’une information manque, se contredit ou n’est pas applicable. |
| **Provenance** | Ce que le patron peut ouvrir pour comprendre pourquoi une information est affichée. |
| **Résultat durable** | Ce qui doit être conservé après l’action : décision, version, tâche, preuve, historique ou nouvelle situation. |

> **Règle fondatrice :** une interface SMART_AO ne peut jamais afficher une conclusion importante sans pouvoir montrer d’où elle vient, ce qui manque et ce que le patron peut faire ensuite.

---

## 2. Le vocabulaire contractuel commun

Le vocabulaire suivant doit être identique dans toutes les vues patron. Une même réalité métier ne doit jamais changer de nom d’un écran à l’autre.

| Terme | Définition métier |
|---|---|
| **Affaire** | Conteneur continu d’un travail commercial BTP, depuis l’opportunité jusqu’à la clôture du marché. |
| **Opportunité** | Signal ou avis à qualifier avant de décider de créer une affaire active. |
| **DCE** | Ensemble de pièces reçues pour une consultation ; plusieurs versions ou rectificatifs peuvent exister. |
| **Exigence** | Ce que l’acheteur demande, interdit, impose, note ou conditionne. |
| **Capacité** | Ce que l’entreprise affirme pouvoir mobiliser pour une affaire précise : équipe, qualification, matériel, partenaire, organisation ou trésorerie. |
| **Preuve** | Élément qui permet de démontrer une capacité ou de répondre à une exigence : document, référence, attestation, photo autorisée, certificat ou validation humaine. |
| **Inconnu** | Élément qui ne peut pas encore être utilisé comme certain. |
| **Risque** | Élément pouvant affecter le prix, le délai, la conformité, une preuve ou les droits de l’entreprise. |
| **Protection** | Mesure ou élément à sécuriser pour réduire un risque. |
| **Action patron** | Décision ou arbitrage qui ne peut être réalisé que par le patron administrateur. |
| **Dossier de décision** | Ensemble figé des faits, inconnus, risques, sources, conditions et options permettant au patron de décider. |
| **Version** | État identifié d’un document, d’un DCE, d’un prix ou d’un dossier de dépôt ; une version validée n’écrase jamais la précédente. |
| **Journal de vérité** | Chronologie métier des sources, actions, décisions, validations et dépôts ayant compté pour une affaire. |

---

## 3. États transverses

### 3.1. État d’une information

Toute donnée importante est présentée avec l’un des états suivants. L’interface affiche toujours l’état, la raison et l’action possible.

| État | Sens | Exemple d’affichage | Action possible |
|---|---|---|---|
| **Confirmé** | La donnée est appuyée par une source ou validation adaptée à son périmètre. | « Qualification confirmée jusqu’au 31/12/2026 ». | Ouvrir la source. |
| **À vérifier** | La donnée existe mais son usage pour l’affaire ou son périmètre doit être confirmé. | « Référence comparable à vérifier pour ce lot ». | Demander validation. |
| **Manquant** | La pièce ou l’information requise n’a pas été trouvée ou reçue. | « Attestation de visite manquante ». | Demander la pièce ou marquer non applicable avec motif. |
| **Contradictoire** | Deux sources ne donnent pas la même information. | « Quantité différente entre plan et DPGF ». | Ouvrir les sources et préparer une question. |
| **Expiré** | La date connue ne permet plus de présenter la pièce comme valable. | « Assurance expirée le 30/06/2026 ». | Remplacer le document. |
| **Non applicable** | L’élément ne concerne pas l’affaire ; le motif est conservé. | « DC4 non applicable : aucun sous-traitant déclaré ». | Voir le motif. |

### 3.2. État d’une action patron

| État | Sens |
|---|---|
| **À traiter** | Le patron doit prendre connaissance et agir. |
| **En attente d’un tiers** | Une tâche est confiée à un collaborateur, partenaire ou organisme ; le patron reste responsable du suivi. |
| **En attente d’information** | Une réponse acheteur, une pièce, un devis ou une confirmation est attendue. |
| **Décidée sous conditions** | Le patron a autorisé la suite sous réserve d’actions nommées et datées. |
| **Terminée** | L’action a produit un résultat vérifiable. |
| **Abandonnée avec motif** | Le patron a choisi de ne pas poursuivre ; le motif est conservé. |

### 3.3. Niveau de traitement

| Niveau | Règle d’affichage |
|---|---|
| **URGENT** | Échéance proche exigeant une action immédiate. |
| **BLOQUANT** | L’affaire ne peut pas franchir l’étape suivante sans traitement. |
| **À RISQUE** | Impact potentiellement important sur marge, délai, conformité, preuve ou droit. |
| **À SURVEILLER** | Élément non urgent à suivre avant qu’il ne devienne critique. |
| **INFORMATION** | Fait utile qui n’exige aucune action immédiate. |

Le niveau de traitement ne remplace jamais l’état de l’information. Par exemple, une qualification **expirée** peut être **bloquante** pour une affaire, tandis qu’un document **à vérifier** peut être seulement **à surveiller**.

---

## 4. Sources de vérité et provenance

Toutes les vues doivent identifier la nature de leurs données. L’interface peut réunir plusieurs sources dans une même synthèse, mais ne doit jamais les mélanger sans les étiqueter.

| Code de source | Nature | Exemples |
|---|---|---|
| **DCE** | Pièce reçue de l’acheteur. | RC, CCAP, CCTP, DPGF, BPU, plan, annexe, rectificatif. |
| **ENTREPRISE** | Donnée ou preuve appartenant au client. | Qualification, assurance, référence, équipe, matériel, fichier de prix. |
| **PARTENAIRE** | Donnée transmise par un fournisseur, cotraitant, sous-traitant ou tiers. | Devis, attestation, disponibilité, fiche technique. |
| **HUMAIN** | Déclaration, validation ou décision explicite d’une personne. | Décision Go/No-Go, visite confirmée, capacité d’équipe validée. |
| **CALCUL** | Résultat déterministe fondé sur des données validées. | Total DPGF, date limite, pénalité calculée, scénario de trésorerie. |
| **SMART_AO** | Analyse, rapprochement ou recommandation produite par le logiciel. | Contradiction détectée, question proposée, recommandation de protection. |

### 4.1. Règle de provenance dans l’interface

Pour toute information à impact, le patron doit pouvoir ouvrir `Pourquoi ?` et consulter au minimum :

| Information à expliquer | Informations de provenance requises |
|---|---|
| Exigence | Pièce DCE, page ou emplacement, extrait et version. |
| Risque | Données et documents à l’origine, impact estimé, limites et responsable. |
| Capacité | Donnée entreprise/partenaire, période, périmètre et personne validatrice. |
| Prix ou scénario | Version de prix, hypothèses, devis, calculs et patron validateur. |
| Décision | Dossier de décision, choix, date, conditions et sources considérées. |
| Alerte | Règle ayant produit l’alerte, échéance, source et action attendue. |

---

## 5. Règles d’accès applicables à toutes les vues

| Règle | Contrat fonctionnel |
|---|---|
| **Patron administrateur** | Peut consulter toutes les vues patron de son entreprise, créer des actions et prendre les décisions réservées. |
| **Collaborateur** | Ne reçoit jamais les vues patron, le prix privé, les marges, les scénarios, les règles internes ou la totalité du portefeuille. |
| **Partenaire** | Ne reçoit qu’une demande limitée à une affaire et au périmètre explicitement partagé. |
| **Données privées** | Ne doivent pas être envoyées à un utilisateur non autorisé, même sous forme masquée ou grisée. |
| **Délégation ponctuelle** | Le patron peut la donner pour une affaire, une ressource, une permission et une durée précises ; le motif est enregistré. |
| **Journal d’accès** | Les consultations, validations, exports et partages sensibles sont traçables pour le patron. |

---

# Partie I — Contrats des vues patron

## 6. V-01 — Accueil / Command Center

| Élément | Contrat |
|---|---|
| **Question métier** | « Qu’est-ce qui demande mon attention aujourd’hui, pourquoi et que dois-je faire ? » |
| **Utilisateur autorisé** | Patron administrateur uniquement. |
| **Situation d’arrivée** | Première connexion, retour après une action, clic sur `Accueil`. |
| **Résultat attendu** | Le patron peut choisir la prochaine action utile sans chercher dans les modules. |
| **Action principale** | `Traiter mes actions`. |

### 6.1. Données nécessaires

| Bloc affiché | Données exigées | Sources possibles |
|---|---|---|
| Actions patron | Intitulé, niveau de traitement, état, affaire, raison, échéance, impact, prochaine action. | Action, risque, exigence, document, décision, affaire. |
| Urgences | Actions dont l’échéance ou le blocage exige une réaction immédiate. | DCE, calendrier, décision, document. |
| Protection | Éléments classés par délais, preuves, marge et droits. | Risques, documents, prix, marché gagné. |
| Portefeuille prioritaire | Affaire, état métier, prochaine action, responsable, échéance et blocage. | Affaires, tâches, décisions, calendrier. |
| Santé entreprise | État explicable des documents, qualifications, références, partenaires, équipe, prix et veille. | Entreprise & capacités, bibliothèque, équipe. |
| Activité récente | Faits métier récents, non techniques. | Journal de vérité. |

### 6.2. États et comportement

| État de vue | Affichage requis | Action autorisée |
|---|---|---|
| Actions urgentes | Zone en tête de page avec raisons et échéances. | Ouvrir la décision ou l’action. |
| Aucune action | Message calme : « Aucune action patron urgente aujourd’hui. » | Ouvrir portefeuille ou opportunités. |
| Donnée insuffisante | Expliquer que l’entreprise ou l’affaire n’est pas encore suffisamment renseignée. | `Préparer mon entreprise` ou `Créer une affaire`. |
| Chargement incomplet | Ne pas afficher un cockpit partiel comme complet. | Montrer clairement les blocs non disponibles et une action de réessai. |

### 6.3. Erreurs métier à afficher

| Situation | Message utilisateur | Suite possible |
|---|---|---|
| Une action n’a plus de ressource accessible | « Cette action concerne un élément qui a été archivé ou remplacé. » | Ouvrir l’historique ou attribuer une revue. |
| Échéance inconnue | « L’échéance n’a pas encore été confirmée dans les documents reçus. » | Ouvrir les sources ou demander une vérification. |
| Doublon d’action | Ne pas afficher deux lignes identiques. | Regrouper les causes dans une même action. |

### 6.4. Provenance obligatoire

Chaque action ouvre une fiche affichant `Pourquoi ?`, `Source`, `Impact`, `Responsable`, `Échéance`, `Action requise` et, le cas échéant, `Action recommandée`.

---

## 7. V-02 — File d’Actions patron

| Élément | Contrat |
|---|---|
| **Question métier** | « Quelles décisions, validations et arbitrages ne peuvent être traités que par moi ? » |
| **Utilisateur autorisé** | Patron administrateur uniquement. |
| **Arrivée** | Bouton `Traiter mes actions`, badge d’action, lien depuis une affaire ou une alerte. |
| **Résultat attendu** | Le patron traite, délègue, conditionne ou clôture une action avec une trace complète. |

### 7.1. Colonnes et filtres

| Information visible | Règle |
|---|---|
| Niveau | Urgent, bloquant, à risque, à surveiller. |
| Type d’action | Go/No-Go, prix, dépôt, partenaire, risque, document, trésorerie, droit. |
| Affaire ou ressource | Lien vers l’affaire, le document, le partenaire ou le marché. |
| Pourquoi | Phrase courte et explicable. |
| Échéance | Date/heure ou « pas d’échéance connue ». |
| Impact | Délais, preuves, marge, droits, capacité ou trésorerie. |
| État | À traiter, attente tiers, attente information, décidée sous conditions, terminée, abandonnée. |
| Action suivante | Ouvrir, déléguer, demander une pièce, décider ou consulter la source. |

| Filtre | Valeurs |
|---|---|
| Période | Aujourd’hui, 7 jours, 30 jours, date libre. |
| Niveau | Urgent, bloquant, à risque, à surveiller. |
| Affaire | Une affaire ou toutes. |
| Impact | Délais, preuves, marge, droits. |
| État | À traiter, attente, sous conditions, terminée. |
| Responsable | Patron, collaborateur, partenaire ou tiers. |

### 7.2. Actions autorisées

| Bouton | Précondition | Résultat durable |
|---|---|---|
| `Ouvrir la décision` | L’action appelle une décision patron. | Ouvre le Dossier de décision associé. |
| `Déléguer une préparation` | Une tâche peut être confiée sans transférer la décision. | Tâche datée, responsable, lien et trace. |
| `Demander une pièce` | Un tiers ou collaborateur est identifié. | Demande limitée et état `En attente d’un tiers`. |
| `Reporter sous conditions` | Le patron définit les conditions, responsables et dates. | Action `Décidée sous conditions`. |
| `Terminer` | Preuve ou décision enregistrée. | Action clôturée avec résultat. |
| `Abandonner avec motif` | Le patron choisit de ne pas poursuivre. | Action close mais historique conservé. |

---

## 8. V-03 — Dossier de décision

| Élément | Contrat |
|---|---|
| **Question métier** | « Avec les informations disponibles maintenant, quel choix puis-je prendre et sous quelles conditions ? » |
| **Utilisateur autorisé** | Patron administrateur ; un collaborateur peut préparer un brouillon mais ne peut pas finaliser la décision. |
| **Arrivée** | Action patron, bouton d’une affaire, alerte de risque ou transition d’état. |
| **Résultat attendu** | Une décision explicite, justifiée, datée et reconstructible. |

### 8.1. Données obligatoires du contexte de décision

| Bloc | Données visibles |
|---|---|
| Situation | Affaire, lot, état, échéance, responsable, décision attendue. |
| Ce que nous savons | Faits confirmés avec sources. |
| Ce qui reste inconnu | Données manquantes, contradictoires ou à vérifier. |
| Risques | Impact, gravité, famille de protection et statut. |
| Capacités et preuves | Équipe, qualification, référence, matériel, partenaire et niveau de couverture. |
| Prix et trésorerie | Données privées uniquement lorsqu’elles sont utiles à cette décision. |
| Conditions à sécuriser | Tâches, responsables, dates et conséquences si elles échouent. |
| Choix possibles | Options adaptées à la décision. |
| Provenance | Sources, versions et validations consultées. |

### 8.2. Décisions et règles de validation

| Type | Choix patron | Condition de validation |
|---|---|---|
| Répondre à une affaire | Répondre / sous conditions / ne pas répondre. | Le patron voit les inconnus et risques ouverts. |
| Valider un prix | Valider / corriger / demander revue / arrêter. | La fiabilité du chiffrage et les éléments non couverts sont affichés. |
| Accepter un partenaire | Accepter / sous réserve / demander pièce / refuser. | Périmètre de prestation et documents du partenaire visibles. |
| Arbitrer un risque | Réduire / demander précision / accepter avec motif / transférer / arrêter. | Impact, sources et stratégie de protection visibles. |
| Valider le dépôt | Valider / retourner au dossier / créer nouvelle version. | Tous les blocages de dépôt sont affichés. |

### 8.3. Erreurs métier

| Situation | Comportement requis |
|---|---|
| Source non accessible | La décision indique que la source est indisponible ; elle ne la considère pas confirmée. |
| Décision déjà prise sur une version ancienne | Signaler le changement et demander au patron de confirmer ou revoir sa décision. |
| Condition sans responsable | Empêcher une décision « sous conditions » non attribuée. |
| Choix incompatible | Expliquer clairement la contradiction, par exemple valider un dépôt avec une pièce éliminatoire manquante. |

---

## 9. V-04 — Portefeuille des affaires

| Élément | Contrat |
|---|---|
| **Question métier** | « Où en est chacune de mes affaires et laquelle mérite que j’intervienne ? » |
| **Utilisateur autorisé** | Patron administrateur. |
| **Arrivée** | Navigation `Affaires`, lien depuis l’Accueil, une opportunité ou une notification. |
| **Résultat attendu** | Le patron ouvre l’affaire utile, attribue, filtre ou décide sans perdre la continuité de l’historique. |

### 9.1. Informations par ligne

| Donnée | Source | Règle d’affichage |
|---|---|---|
| Identité affaire | Création ou opportunité. | Nom, acheteur, lot, lieu. |
| État métier | Situation de l’affaire. | Opportunité, analyse, décision, préparation, chiffrage, dépôt, résultat, exécution, terminée. |
| Prochaine action | Action patron ou tâche la plus importante. | Phrase utile, pas un simple pourcentage. |
| Échéance | DCE, calendrier ou marché gagné. | Date/heure et niveau de proximité. |
| Responsable | Affectation humaine. | Patron, collaborateur ou responsable courant. |
| Blocage | Risque ou condition active. | Visible seulement s’il existe. |
| Décision actuelle | Dossier de décision. | Go, Go sous conditions, No-Go, non décidée, prix validé, etc. |

### 9.2. Actions autorisées

| Bouton | Résultat |
|---|---|
| `Créer une affaire` | Crée une affaire manuelle ou démarre l’import d’un DCE. |
| `Ouvrir` | Ouvre la Vue de direction de l’affaire. |
| `Attribuer` | Ouvre l’affectation d’un collaborateur ou relecteur. |
| `Réattribuer` | Change le responsable en conservant l’historique. |
| `Arrêter l’affaire` | Demande un motif et clôt la situation commerciale sans supprimer les traces. |
| `Archiver` | Retire la vue active tout en conservant le Journal de vérité. |
| `Voir les marchés gagnés` | Filtre les affaires dans l’état Marché gagné/exécution. |

---

## 10. V-05 — Vue de direction de l’affaire

| Élément | Contrat |
|---|---|
| **Question métier** | « Quelle est la situation de cette affaire, qu’est-ce qui est prêt, qu’est-ce qui bloque et que dois-je faire maintenant ? » |
| **Utilisateur autorisé** | Patron administrateur. |
| **Arrivée** | Bouton `Ouvrir` depuis les Affaires, l’Accueil, une action ou une opportunité transformée en affaire. |
| **Résultat attendu** | Comprendre l’affaire en dix secondes et ouvrir le bon espace de travail détaillé. |

### 10.1. Données de synthèse obligatoires

| Zone | Données nécessaires |
|---|---|
| Identité | Nom, acheteur, lot, lieu, responsable, date limite et état métier. |
| Décision actuelle | Non décidée, Go, Go sous conditions, No-Go, prix validé, prête au contrôle, déposée, gagnée, perdue. |
| Prochaine action patron | Action requise ou recommandée, raison, impact, échéance et bouton. |
| Carte de décision | Exigences, capacités, preuves, risques, inconnus et décision actuelle. |
| Risques prioritaires | Risques ouverts par famille délais/preuves/marge/droits. |
| Équipe | Responsables, tâches actives et transmissions. |
| Changements récents | Événements métier depuis la dernière consultation patron. |

### 10.2. Carte de décision sans score opaque

| Axe | Affichage requis |
|---|---|
| Exigences | Nombre couvertes / à traiter / inconnues, avec lien vers le détail. |
| Capacités | Confirmées / à confirmer / non couvertes. |
| Preuves | Prêtes / à vérifier / manquantes / expirées. |
| Risques | Nombre ouvert, niveau et impact. |
| Inconnus | Nombre, nature et responsable de vérification. |
| Décision | État explicite et conditions éventuelles. |

### 10.3. Actions autorisées

| Bouton | Destination ou résultat |
|---|---|
| `Ouvrir le Dossier de décision` | Ouvre la décision active. |
| `Ouvrir l’analyse DCE` | Ouvre la vue détaillée de l’analyse, sans afficher les prix privés. |
| `Traiter les preuves` | Ouvre documents et éléments manquants liés à l’affaire. |
| `Voir les risques` | Ouvre les risques et protections de cette affaire. |
| `Ouvrir le prix privé` | Ouvre le workspace de chiffrage patron. |
| `Préparer le dépôt` | Ouvre le coffre de dépôt lorsque les conditions sont remplies. |
| `Consulter le journal` | Ouvre le Journal de vérité filtré sur cette affaire. |

---

## 11. V-06 — Entreprise & capacités

| Élément | Contrat |
|---|---|
| **Question métier** | « Qu’est-ce que mon entreprise peut réellement mobiliser et prouver pour ses affaires ? » |
| **Utilisateur autorisé** | Patron administrateur. |
| **Arrivée** | Navigation `Entreprise`, demandes de préparation, action sur une capacité ou un document manquant. |
| **Résultat attendu** | Le patron peut enrichir son passeport opérationnel progressivement et comprendre ses fragilités. |

### 11.1. Données nécessaires

| Bloc | Données |
|---|---|
| Identité | Raison sociale, SIREN/SIRET, forme juridique, adresses, coordonnées. |
| Signataires | Représentant légal, signataires autorisés, délégations et contacts. |
| Capacités | Métiers, spécialités, types de chantiers, zones, matériels, équipes, charge et périodes disponibles. |
| Qualifications | Certificats, périmètres, dates, preuves et statuts. |
| Références | Chantiers, comparabilité, preuves, photos autorisées et droit d’usage. |
| Partenaires | Compétences, périmètres, documents, zone, état et disponibilité à confirmer. |
| Règles patron | Seuils internes, capacité, validation, marge et stratégie de réponse. |
| Préparation | États qualitatifs par domaine et actions proposées. |

### 11.2. Actions autorisées

| Bouton | Résultat |
|---|---|
| `Ajouter une capacité` | Ajoute un métier, spécialité, équipe, matériel ou zone avec statut à confirmer si nécessaire. |
| `Ajouter une qualification` | Ouvre l’ajout de preuve et de périmètre. |
| `Ajouter une référence` | Crée une fiche de référence réutilisable avec droit d’usage. |
| `Ajouter un partenaire` | Crée une fiche partenaire, jamais une conformité automatique. |
| `Définir une règle patron` | Ajoute une règle privée versionnée. |
| `Préparer mon entreprise` | Affiche les éléments prêts, à compléter, à vérifier et non applicables. |
| `Voir les affaires concernées` | Montre les affaires où une capacité ou preuve est utilisée, requise ou insuffisante. |

### 11.3. Erreurs métier

| Situation | Comportement requis |
|---|---|
| Qualification sans preuve | Capacité reste « à vérifier » ; ne peut pas être présentée comme confirmée. |
| Référence sans droit d’usage | Elle ne peut pas être proposée au mémoire sans validation patron. |
| Capacité déclarée hors période | L’affaire affiche une capacité « à confirmer », pas une disponibilité garantie. |
| Information minimale absente | SMART_AO explique le bénéfice de la compléter, sans empêcher toute utilisation de l’application. |

---

## 12. V-07 — Bibliothèque / Passeport des preuves

| Élément | Contrat |
|---|---|
| **Question métier** | « Quelles preuves et pièces mon entreprise possède-t-elle, sont-elles utilisables et dans quelles affaires ? » |
| **Utilisateur autorisé** | Patron administrateur ; partage limité selon autorisation. |
| **Arrivée** | Navigation `Bibliothèque`, action de renouvellement, besoin d’une affaire, ajout de document. |
| **Résultat attendu** | Le patron ajoute, retrouve, protège, renouvelle et relie chaque preuve à ses usages. |

### 12.1. Données nécessaires par élément

| Information | Règle |
|---|---|
| Nom et original | Le fichier original est conservé ; une synthèse ne le remplace pas. |
| Famille | Identité, qualification, assurance, référence, équipe, matériel, partenaire, modèle ou prix privé. |
| Sous-type | Ex. décennale, Qualibat, fiche chantier, devis fournisseur, modèle mémoire. |
| Émetteur / source | Entreprise, assureur, organisme, client, partenaire, fournisseur. |
| Périmètre | Activité, lot, personne, matériel, partenaire, zone ou affaire. |
| Dates | Émission, expiration, date de dernière vérification lorsque connues. |
| État | Confirmé, à vérifier, manquant, contradictoire, expiré, non applicable. |
| Confidentialité | Patron, partage par affaire ou partage ponctuel. |
| Utilisations | Affaires où l’élément est utilisé, demandé, proposé ou à confirmer. |
| Historique | Ajout, remplacement, validation, partage, retrait, archivage. |

### 12.2. Actions autorisées

| Bouton | Résultat |
|---|---|
| `Ajouter des documents` | Parcours classer → déposer → décrire/protéger. |
| `Ouvrir l’original` | Ouvre le fichier si le patron dispose du droit. |
| `Remplacer par une version` | Ajoute une nouvelle version, sans détruire l’ancienne. |
| `Créer un rappel` | Crée une action ou tâche de renouvellement. |
| `Voir les utilisations` | Affiche les affaires et l’état de l’usage. |
| `Autoriser pour une affaire` | Crée une autorisation ponctuelle, datée et limitée. |
| `Archiver` | Retire l’élément des propositions, conserve l’historique. |

---

## 13. V-08 — Opportunités / Radar

| Élément | Contrat |
|---|---|
| **Question métier** | « Quelles opportunités correspondent à ma stratégie, pourquoi et que faut-il vérifier avant d’y investir du temps ? » |
| **Utilisateur autorisé** | Patron administrateur ; transmission possible à un collaborateur sans accès aux prix. |
| **Arrivée** | Navigation `Opportunités`, alerte de veille, création de profil, import manuel. |
| **Résultat attendu** | Le patron qualifie, écarte, met en veille ou transforme une opportunité en affaire. |

### 13.1. Données par opportunité

| Bloc | Données |
|---|---|
| Identité | Objet, acheteur, lot, lieu, source, date de publication et date limite. |
| Correspondance | Métiers, zone, montant, type de travaux, acheteur, capacité, exclusions et raison de correspondance. |
| Inconnus | Éléments non disponibles avant téléchargement DCE ou analyse. |
| Alertes | Visite, délai court, qualification visible, charge, critères ou risque apparent. |
| Action | Examiner, transmettre, créer une affaire, écarter ou mettre en veille. |
| Décision passée | Motif d’écartement ou transmission, afin d’améliorer la mémoire commerciale. |

### 13.2. Erreurs et limites

| Situation | Message attendu |
|---|---|
| Aucune source active | « Aucun profil ou aucune source ne permet de proposer des opportunités pour le moment. » |
| Score de correspondance | Le système ne doit pas afficher un score inexpliqué ; il liste les critères correspondants et non correspondants. |
| Donnée publique incomplète | « Certaines informations seront confirmées après réception du DCE. » |
| Opportunité doublonnée | Regrouper les sources et éviter la création de deux affaires pour le même lot. |

---

## 14. V-09 — Équipe et affectations

| Élément | Contrat |
|---|---|
| **Question métier** | « Qui peut travailler sur mes affaires, qui travaille actuellement et qui attend mon retour ? » |
| **Utilisateur autorisé** | Patron administrateur. |
| **Arrivée** | Navigation `Équipe`, action de délégation, besoin d’affectation ou gestion d’accès. |
| **Résultat attendu** | Le patron contrôle les comptes, les accès, les charges et les transmissions sans exposer les données privées. |

### 14.1. Données nécessaires

| Information | Règle |
|---|---|
| Identité et fonction | Nom, e-mail professionnel, fonction déclarée. |
| Statut de compte | Invitation, actif, suspendu ou désactivé. |
| Affaires attribuées | Liste, rôle, échéances et charge visible. |
| Travaux transmis | Dossiers en attente patron ou tâches terminées. |
| Délégations | Ressource, permission, durée, motif et patron ayant accordé l’accès. |
| Historique | Affectation, retrait, suspension, contribution et transmission. |

### 14.2. Actions autorisées

| Bouton | Résultat |
|---|---|
| `Inviter un collaborateur` | Crée une invitation et aucun accès par défaut hors affaires sélectionnées. |
| `Attribuer une affaire` | Accorde l’accès à l’affaire définie avec rôle/tâches. |
| `Retirer une affaire` | Supprime l’accès futur sans détruire les contributions. |
| `Voir les travaux transmis` | Ouvre les dossiers et tâches en attente patron. |
| `Suspendre le compte` | Bloque l’accès ; aucune donnée n’est supprimée. |
| `Créer une délégation ponctuelle` | Accorde une permission limitée, datée et motivée. |

---

## 15. V-10 — Prix privé d’une affaire

| Élément | Contrat |
|---|---|
| **Question métier** | « Est-ce que mon prix couvre réellement ce que je promets et quels risques accepte mon entreprise ? » |
| **Utilisateur autorisé** | Patron administrateur ; aucune visibilité collaborateur par défaut. |
| **Arrivée** | Vue de direction, Action patron `Valider un prix`, Dossier de décision ou affaire prête à chiffrer. |
| **Résultat attendu** | Le patron compare des scénarios, explique son prix, valide une version officielle et prépare le contrôle final. |

### 15.1. Lecture en trois niveaux

| Niveau | Données affichées | Action possible |
|---|---|---|
| **Résultat** | Prix actuel, marge estimée, fiabilité du chiffrage, problèmes majeurs et prochaine action. | `Voir les impacts`, `Comparer les scénarios`. |
| **Explication** | Postes non couverts, devis manquants, hypothèses, risques, clauses et impacts. | `Ouvrir les sources`, `Demander un devis`, `Modifier une hypothèse`. |
| **Détail** | DPGF/BPU/DQE, postes, unités, fichiers, calculs, coûts, fournisseurs, trésorerie et versions. | `Préparer une version de prix`, `Créer un scénario`. |

### 15.2. Données nécessaires

| Bloc | Données |
|---|---|
| Pièces acheteur | DPGF, BPU, DQE, acte d’engagement, version et champs à compléter. |
| Prix entreprise | Fichiers privés, dates, familles, correspondances de postes et données validées. |
| Fournisseurs/partenaires | Devis, périmètre, dates, exclusions, délais et état de réponse. |
| Coûts et hypothèses | Main-d’œuvre, matériel, matériaux, sous-traitance, frais, aléas et conditions. |
| Scénarios | Nom, auteur, hypothèses modifiées, effets et statut. |
| Fiabilité | Postes contrôlés, non couverts, devis absents, hypothèses à confirmer et contradictions. |
| Trésorerie | Avance, retenue, rythmes de dépenses/encaissements et alertes. |
| Version officielle | Version de prix retenue et patron validateur. |

### 15.3. Invariants fonctionnels

1. Un scénario privé ne modifie jamais le prix officiel sans choix explicite du patron.
2. Le prix officiel ne peut être présenté comme prêt au dépôt sans version patron validée.
3. Un élément non couvert ou une hypothèse non validée doit rester visible dans la fiabilité du chiffrage.
4. Les pièces acheteur originales ne sont jamais écrasées ; seules des copies de travail ou versions préparées sont modifiées.
5. Aucun collaborateur ne reçoit les données de coût, marge, prix ou trésorerie.

---

## 16. V-11 — Coffre de dépôt

| Élément | Contrat |
|---|---|
| **Question métier** | « Puis-je déposer cette offre sans oublier de pièce, sans envoyer une mauvaise version et sans prendre un engagement non validé ? » |
| **Utilisateur autorisé** | Patron administrateur ou personne expressément habilitée au dépôt. |
| **Arrivée** | Action `Contrôler le dépôt`, Vue de direction ou prix officiel validé. |
| **Résultat attendu** | Dossier contrôlé, version de dépôt créée, ZIP/structure disponible et preuve de dépôt archivée après l’action humaine. |

### 16.1. Données et contrôles nécessaires

| Bloc | Vérifications attendues |
|---|---|
| Candidature | Pièces exigées, états, dates, formulaires et signatures si demandées. |
| Offre technique | Mémoire, cadre acheteur, planning, moyens, références, variantes et annexes. |
| Offre financière | DPGF/BPU/DQE/AE, cohérence des versions et validation patron. |
| Pièces tiers | Visite, assurance, partenaire, banque ou autre élément requis. |
| Format | Arborescence, formats, noms, enveloppes, taille connue et contraintes du RC. |
| Versions | Document source, brouillon, version patron validée, version de dépôt. |
| Accusé de réception | Plateforme, date/heure, fichier ou preuve déposée après action humaine. |

### 16.2. Erreurs bloquantes

| Situation | Effet |
|---|---|
| Pièce obligatoire manquante | Empêche la validation finale ; crée une action ou tâche explicite. |
| Document expiré | Empêche son utilisation comme preuve sans remplacement ou décision motivée. |
| Prix non validé | Empêche la création de la version financière finale. |
| Version modifiée après validation | Demande une nouvelle revue patron. |
| Signature requise mais non confirmée | Signale l’action humaine et ne prétend pas qu’elle a été faite. |
| Format incertain | Affiche « à vérifier selon le RC » avec la source de la règle. |

---

## 17. V-12 — Journal de vérité

| Élément | Contrat |
|---|---|
| **Question métier** | « Que s’est-il réellement passé dans cette affaire, avec quelles sources, décisions et versions ? » |
| **Utilisateur autorisé** | Patron administrateur ; vue réduite possible pour le collaborateur dans son périmètre, définie dans son futur contrat. |
| **Arrivée** | Onglet d’affaire, lien depuis décision, document, dépôt ou marché gagné. |
| **Résultat attendu** | Chronologie métier compréhensible, exportable selon droits, sans journal technique inutile. |

### 17.1. Événements métier affichables

| Famille | Exemples |
|---|---|
| Réception | DCE reçu, annexe ajoutée, rectificatif, réponse acheteur. |
| Analyse | Exigence détectée, contradiction identifiée, question préparée. |
| Préparation | Document ajouté, preuve validée, partenaire sollicité, visite confirmée. |
| Décision | Go/No-Go, risque accepté, partenaire validé, prix retenu. |
| Dépôt | Dossier assemblé, validation, dépôt marqué, accusé ajouté. |
| Résultat/exécution | Marché gagné/perdu, ordre de service, variation, réserve, situation, paiement. |

### 17.2. Données minimales par ligne

Date/heure, type de fait, phrase métier, auteur ou origine, affaire, ressource liée, version si pertinente, lien vers source et conséquence ou action suivante.

---

# Partie II — Contrats transverses

## 18. C-01 — Contrat de l’Action patron

| Élément | Règle |
|---|---|
| Création | Une action apparaît lorsqu’un fait exige une décision ou un arbitrage patron. |
| Unicité | Une même cause métier ne crée pas plusieurs actions concurrentes. |
| Propriétaire | Le patron reste décisionnaire même si une tâche préparatoire est déléguée. |
| Explication | Raison, impact, source, état et prochaine action sont obligatoires. |
| Échéance | Obligatoire lorsqu’elle est connue ; inconnue sinon, sans invention. |
| Clôture | Décision, preuve, abandon motivé ou résultat vérifiable requis. |
| Historique | Toute modification de priorité, responsable, condition ou décision est journalisée. |

## 19. C-02 — Contrat de la Décision humaine

| Élément | Règle |
|---|---|
| Autorité | Seul le patron ou une personne explicitement habilitée peut finaliser une décision réservée. |
| Contexte | La décision conserve les sources, faits, inconnus, risques et versions considérées. |
| Conditions | Toute décision sous conditions définit des actions, responsables et dates. |
| Réversibilité | Une nouvelle décision peut remplacer l’ancienne, mais elle ne l’efface jamais. |
| Explication | La décision ne peut pas être « automatique » : un choix patron et un motif sont visibles. |

## 20. C-03 — Contrat de la provenance

| Règle | Conséquence interface |
|---|---|
| Source obligatoire pour les faits importants | Bouton `Pourquoi ?` et lien source disponibles. |
| Distinction fait/recommandation | Une déduction SMART_AO est étiquetée ; elle n’est pas affichée comme clause DCE. |
| Version obligatoire | Une information DCE ou de prix indique la version source quand elle est sensible. |
| Source inaccessible | L’information passe à `À vérifier` ou `Manquant` selon la situation. |
| Citations internes | Les extraits DCE restent associés à la pièce et à la page ou zone connue. |

## 21. C-04 — Contrat d’erreur et de limite

| Situation | Formulation SMART_AO obligatoire |
|---|---|
| Information absente | « Nous ne trouvons pas cette information dans les documents reçus. » |
| Contradiction | « Ces deux documents donnent des informations différentes. Une vérification est nécessaire. » |
| Donnée non applicable | « Cet élément n’est pas applicable à cette affaire pour le motif enregistré. » |
| Calcul incomplet | « Le calcul utilise les hypothèses suivantes ; les éléments non confirmés restent visibles. » |
| Recommandation non contraignante | « SMART_AO recommande cette action ; le choix reste au patron. » |
| Limite de compétence | « SMART_AO organise les faits et prépare une base de travail ; une validation métier, juridique, bancaire ou technique peut rester nécessaire. » |
| Accès refusé | « Cette information est réservée au patron ou à une personne explicitement autorisée. » |

## 22. C-05 — Contrat de version

| Ressource | Règle |
|---|---|
| DCE | Chaque pièce reçue et rectificatif est conservé comme version distincte. |
| Document entreprise | L’original et les remplacements sont conservés ; l’ancienne version n’est pas détruite. |
| Mémoire | Brouillon, version revue, version validée et version de dépôt restent distingués. |
| Prix | Scénarios privés et version officielle sont séparés. |
| Dépôt | Les fichiers déposés, la date, la plateforme et l’accusé de réception sont associés à une version de dépôt. |
| Décision | Une nouvelle décision remplace l’état actif mais pas l’historique. |

## 23. C-06 — Critères de recette fonctionnelle

Le contrat est considéré respecté lorsque chaque vue peut être testée avec un scénario réel et qu’elle produit le bon comportement observable.

| Test | Résultat attendu |
|---|---|
| Action patron créée par une pièce manquante | Elle apparaît dans l’Accueil, la file d’actions et l’affaire sans doublon. |
| Action délégable | Le collaborateur reçoit une tâche ; le patron garde la décision et voit l’attente. |
| Document expiré | Il ne peut pas être présenté comme prêt ; les affaires concernées sont visibles. |
| Décision sous conditions | Les conditions ont un responsable, une date et restent visibles jusqu’à traitement. |
| Rectificatif DCE | L’affaire montre ce qui est impacté, l’ancienne version reste disponible et une revue est demandée. |
| Scénario de prix | Il modifie uniquement son scénario, jamais la version officielle sans validation patron. |
| Collaborateur connecté | Il ne reçoit pas de données patron, même sous forme masquée. |
| Dépôt | Le coffre bloque les pièces obligatoires manquantes et archive la preuve quand le patron l’importe. |
| Journal de vérité | Il montre les faits métier, pas les opérations internes de l’application. |

---

## 24. Suite documentaire obligatoire

Après validation de ce Contrat Métier vers Interface, l’ordre de travail est le suivant :

1. **Contrat de domaine V8** : traduire les réalités métier stabilisées en responsabilités, états, règles et transitions ;
2. **Contrat d’accès et de confidentialité** : détailler les vues patron, collaborateur et partenaire sans fuite de données ;
3. **Contrat documentaire DCE** : préciser comment chaque pièce devient source, exigence, preuve, question, risque et action ;
4. **Cahier collaborateur** : écrire les écrans du wizard d’analyse DCE à partir des mêmes contrats transverses ;
5. **Plan de tests Golden DCE** : valider le produit sur le DCE réel avant toute promesse commerciale.

> **Règle de passage :** aucun code d’écran patron ne doit être considéré comme final avant la validation de ce contrat et du Contrat de domaine V8 qui en découlera.

---

## 25. Décision demandée au fondateur

Le fondateur doit confirmer que ce document définit bien la manière dont les écrans patron seront construits : chaque vue répond à une question métier, reçoit des données avec provenance, affiche les états réels, limite les actions selon les droits, exige les validations humaines nécessaires et conserve les décisions dans le Journal de vérité.


---

# V1.1 — Durcissement du Contrat Métier vers Interface

Cette extension complète le contrat sans changer le parcours fonctionnel validé. Elle précise comment SMART_AO doit représenter le temps, les versions, la fraîcheur, les causes, les décisions et les mises à jour de vues. Son objectif est d’empêcher qu’une interface affiche une information vraie mais ancienne, une recommandation comme un fait, ou une décision actuelle comme si elle avait toujours été prise dans le contexte le plus récent.

## 26. Contrat de fraîcheur des informations

Toute information susceptible d’évoluer doit pouvoir afficher sa **date de référence** lorsque cette fraîcheur peut modifier la décision du patron.

| Élément | Exemple de date de référence | Affichage attendu |
|---|---|---|
| Qualification | Date de dernière vérification et date d’expiration. | « Vérifiée le 04/08/2026 · valable jusqu’au 31/12/2026 ». |
| Disponibilité équipe | Dernière confirmation humaine. | « Dernière confirmation : 11/08 à 16:42 ». |
| Devis fournisseur | Date du devis, validité et dernière relance. | « Devis du 02/08 · valable jusqu’au 16/08 ». |
| DCE | Date de réception de la version applicable. | « DCE version 3 reçu le 12/08 à 09:18 ». |
| Prix | Date de calcul et version DCE considérée. | « Calculé le 14/08 sur DCE version 3 ». |
| Vue patron | Heure de la dernière situation métier connue. | « Situation mise à jour à 14:35 ». |

### 26.1. États de fraîcheur d’une vue

| État | Sens métier | Comportement requis |
|---|---|---|
| **À jour** | La vue reflète les derniers faits disponibles pour son périmètre. | La situation peut être présentée comme actuelle. |
| **Mise à jour en cours** | Un nouveau fait existe et son impact est en cours de traitement. | Afficher ce statut et ne pas masquer le nouveau fait. |
| **Partielle** | Une partie de la vue est connue ; une autre reste indisponible ou non analysée. | Identifier le bloc incomplet et proposer une action. |
| **Indisponible** | SMART_AO ne peut pas produire la vue demandée. | Ne jamais présenter l’absence comme « aucun élément ». |
| **Vide** | L’analyse est disponible mais aucun élément n’existe dans cette catégorie. | Afficher une phrase positive et précise, par exemple « Aucun risque ouvert détecté à ce stade ». |
| **Obsolète** | La vue ou une décision repose sur un contexte dépassé par un fait plus récent. | Afficher le changement et demander une revue si l’impact est possible. |

`Vide` n’est jamais synonyme d’`Indisponible`. Par exemple, « aucun risque détecté » n’est possible que si la revue des risques est disponible et à jour.

## 27. Contrat de cohérence de chaque vue

Les vues n’exigent pas toutes le même niveau de synchronisation. Le niveau requis doit être défini fonctionnellement, sans exposer la plomberie technique au patron.

| Niveau de cohérence | Signification | Vues concernées |
|---|---|---|
| **Immédiate à la validation** | Une action ne peut être confirmée qu’avec les informations applicables au moment de la décision. | Dossier de décision, validation de prix, coffre de dépôt, partage sensible. |
| **Situation cohérente** | La vue doit présenter un ensemble de données cohérent ; elle peut afficher une date de mise à jour. | Accueil, Vue de direction de l’affaire, Santé entreprise, Action patron. |
| **Différée acceptable** | Un léger délai de mise à jour est acceptable s’il est affiché et n’autorise aucune conclusion engageante. | Bibliothèque, Radar opportunités, activité récente, statistiques. |

Une vue de dépôt ou une décision patron ne peut pas être validée sur une situation `Obsolète`, `Partielle` ou `Indisponible` lorsqu’un élément manquant concerne directement la décision.

## 28. Nature d’une information : fait, calcul, déduction, recommandation ou décision

La source seule ne suffit pas. Toute information affichée dans une vue importante doit indiquer sa **nature**, afin de ne jamais présenter une conclusion SMART_AO comme une clause provenant du DCE.

| Nature | Définition | Exemple | Présentation interface |
|---|---|---|---|
| **Fait** | Information explicitement présente dans une source ou validée par une personne. | « Pénalité : 200 € par jour » dans le CCAP. | Source et extrait visibles. |
| **Calcul** | Résultat déterministe obtenu à partir de données et règles connues. | « Exposition maximale estimée : 37 000 € ». | Formule, données et hypothèses ouvrables. |
| **Déduction** | Interprétation ou rapprochement établi à partir de faits. | « Les pièces semblent contradictoires sur ce poste ». | Étiquetée « analyse SMART_AO » avec sources. |
| **Recommandation** | Action proposée par SMART_AO ou une règle interne. | « Demander une clarification avant décision ». | Étiquetée « recommandée » ; jamais bloquante seule. |
| **Décision humaine** | Choix explicite réalisé par une personne autorisée. | « Répondre sous conditions ». | Patron, date, contexte, motif et conditions visibles. |

## 29. Provenance chaînée et propriétaire de vérité

Une information complexe possède souvent plusieurs causes. La provenance doit donc être **chaînable** : le patron peut remonter de la décision au fait initial et descendre du fait vers ses conséquences.

```text
Décision patron
   ↓
Recommandation ou choix
   ↓
Risque ou protection
   ↓
Calcul ou déduction
   ↓
Faits confirmés
   ↓
Preuves et versions de documents
```

### 29.1. Trois responsabilités à distinguer

| Élément | Question à laquelle il répond | Exemple |
|---|---|---|
| **Source** | « Dans quel document, donnée ou déclaration cette information apparaît-elle ? » | Certificat Qualibat, devis fournisseur, RC. |
| **Propriétaire de vérité** | « Qui est responsable de la réalité métier de cette information ? » | Entreprise pour sa qualification, fournisseur pour son devis, acheteur pour le DCE, patron pour sa décision. |
| **Validateur** | « Qui a confirmé que l’information pouvait être utilisée pour cette affaire ? » | Patron, collaborateur habilité, partenaire ou tiers désigné. |

Une qualification, par exemple, peut avoir comme source un certificat, comme propriétaire de vérité l’entreprise concernée et comme validateur le patron qui confirme son emploi dans une affaire donnée.

### 29.2. Matrice canonique des sources

| Nature principale | Autorité métier | Versionnable | Modifiable par | Doit être citée lorsqu’elle a un impact |
|---|---|---:|---|---:|
| DCE / pièce acheteur | Acheteur | Oui | Réception d’une nouvelle version uniquement | Oui |
| Preuve entreprise | Entreprise | Oui | Patron ou personne habilitée | Oui |
| Donnée partenaire | Partenaire ou tiers | Oui | Tiers, puis patron pour l’usage | Oui |
| Calcul | SMART_AO avec règles déterministes | Oui | Recalcul à partir de nouvelles données | Oui |
| Déduction | SMART_AO | Oui | Nouvelle analyse ou correction humaine | Oui |
| Recommandation | SMART_AO ou règle patron | Oui | Règle modifiée ou contexte modifié | Oui |
| Décision | Patron ou personne explicitement habilitée | Oui | Nouvelle décision seulement | Oui |

## 30. Contexte de décision figé et distinction entre présent et historique

Toute décision patron doit référencer l’état de vérité utilisé au moment où elle est prise. Ce contexte est figé, même si l’affaire continue ensuite d’évoluer.

| Élément du contexte de décision | Exemple |
|---|---|
| Moment de décision | 12/08/2026 à 17:31. |
| DCE applicable | DCE version 3. |
| Preuves considérées | Qualification version 2, référence version 5. |
| Capacités considérées | Équipe confirmée le 11/08 à 16:42. |
| Prix considéré | Scénario privé S4, calculé le 12/08. |
| Risques et protections | R1 pénalité, R2 délai, condition d’obtention devis. |
| Décideur | Patron administrateur. |
| Choix et motif | Go sous conditions, avec raisons et conditions. |

### 30.1. Règle de non-confusion

| Notion | Sens |
|---|---|
| **Situation actuelle** | Ce que SMART_AO sait aujourd’hui de l’affaire. |
| **Contexte de décision** | Ce qui était connu et présenté au patron au moment précis de sa décision. |
| **Décision active** | La dernière décision non supersédée qui guide l’affaire. |
| **Décision historique** | Toute décision conservée pour expliquer l’évolution de l’affaire. |

Si un DCE version 3 arrive après un Go pris sur DCE version 2, SMART_AO ne réécrit pas l’ancienne décision. Il affiche : « Go du 12/08 pris sur DCE version 2 ; DCE version 3 reçu le 16/08 ; revue nécessaire. »

## 31. Cycle de vie normatif d’une Action patron

| État | Sens | Transitions autorisées |
|---|---|---|
| **Nouvelle** | L’action vient d’être créée par une cause métier. | Prise en compte, délégation, annulation motivée. |
| **Prise en compte** | Le patron a ouvert et reconnu l’action. | En préparation, en attente, résolue, annulée. |
| **En préparation** | Le patron ou un tiers prépare les éléments nécessaires. | En attente, résolue, annulée. |
| **En attente** | Une information, une pièce, un devis ou une tâche tiers est attendue. | En préparation, résolue, annulée, remplacée. |
| **Résolue** | Le résultat ou la décision attendue existe. | Clôturée ou remplacée par une nouvelle action. |
| **Clôturée** | L’action ne requiert plus de suivi actif. | Aucune, sauf création d’une nouvelle action liée. |
| **Annulée avec motif** | Elle n’a plus lieu d’être sans qu’une autre action la remplace. | Aucune. |
| **Remplacée** | Une nouvelle action, version ou situation a remplacé celle-ci. | Lien obligatoire vers l’action qui la remplace. |

### 31.1. Unicité et regroupement des causes

> **Invariant : pour une même cause métier et un même objet concerné, SMART_AO ne crée qu’une seule Action patron active.**

Une Action patron peut regrouper plusieurs causes. Exemple : l’action `Contrôler le dépôt` peut réunir une attestation expirée, une DPGF incohérente et une signature à confirmer. La résolution ne peut être complète que lorsque les causes concernées ont été traitées, écartées avec motif ou remplacées par une décision patron.

## 32. Axes distincts de priorité

Le système ne doit pas utiliser un seul statut géant pour exprimer urgence, gravité et blocage. Chaque élément possède trois axes ; l’interface compose ensuite une lecture compréhensible.

| Axe | Valeurs | Question métier |
|---|---|---|
| **Gravité** | Information, attention, risque, critique. | « Si cet élément se réalise ou reste non traité, quel impact peut-il avoir ? » |
| **Urgence** | Normale, prochaine, immédiate. | « Quand faut-il s’en occuper ? » |
| **Impact sur le passage** | Non bloquant, bloquant. | « L’affaire peut-elle avancer sans cet élément ? » |

Exemples d’affichage : `URGENT · BLOQUANT`, `RISQUE · NON BLOQUANT`, `À SURVEILLER`. Les couleurs ne remplacent jamais le libellé écrit.

## 33. Dimensions d’état d’une preuve ou capacité

Pour éviter les statuts impossibles comme « expiré mais à vérifier », une preuve ou capacité combine des dimensions distinctes.

| Dimension | Question | Valeurs typiques |
|---|---|---|
| Existence | « L’élément existe-t-il ? » | Présent, manquant. |
| Validité | « Est-il valable à la date utile ? » | Valide, expiré, date inconnue. |
| Applicabilité | « Concerne-t-il cette affaire ? » | Applicable, non applicable, à déterminer. |
| Vérification | « Son usage a-t-il été confirmé ? » | Confirmé, à vérifier, contradictoire. |
| Utilisation | « Dans quelles affaires est-il employé ? » | Liste des usages, proposition, utilisation non confirmée. |

L’interface peut présenter une synthèse lisible, mais le détail doit rester ouvrable pour éviter toute ambiguïté.

## 34. Responsabilités d’action : propriétaire, exécutant, approbateur

Le simple mot « responsable » est insuffisant dans une entreprise BTP. Toute action ou condition importante distingue les rôles suivants.

| Rôle | Question | Exemple |
|---|---|---|
| **Propriétaire** | Qui est responsable de ce que l’action arrive à son terme ? | Karim est propriétaire de l’obtention de l’attestation. |
| **Exécutant** | Qui réalise concrètement la tâche ? | Karim demande l’attestation à l’organisme. |
| **Approbateur** | Qui doit accepter le résultat avant passage ? | Noor confirme que l’attestation est utilisable. |

Une même personne peut tenir les trois rôles. Une action patron conserve toujours le patron comme approbateur lorsque sa validation est requise.

## 35. Contrat renforcé du prix et du dépôt

### 35.1. Lien obligatoire entre prix officiel et DCE

Toute version de prix officielle doit référencer le DCE et les pièces de prix considérés comme applicables lors de sa validation. Une vue ne peut pas laisser croire qu’un prix calculé sur DCE version 2 couvre automatiquement un DCE version 4.

| Situation | Comportement requis |
|---|---|
| Nouveau rectificatif sans impact | Indiquer la nouvelle version et le motif de non-impact validé. |
| Nouveau rectificatif avec impact possible | Marquer le prix officiel et la décision associée comme `à revoir`. |
| Prix validé sur la version applicable | Afficher DCE/DPGF/BPU de référence et date de validation. |
| Prix basé sur hypothèses | Conserver les hypothèses et les présenter dans la fiabilité du chiffrage. |

### 35.2. Paquet préparé, dépôt et preuve

Un ZIP ou une arborescence créée par SMART_AO n’est pas un dépôt. Le contrat distingue les états suivants.

| État | Sens |
|---|---|
| **Paquet préparé** | Les fichiers sont assemblés pour contrôle, mais aucune autorisation de dépôt n’est donnée. |
| **Prêt pour dépôt** | Les contrôles requis sont terminés et le patron autorise le dépôt humain. |
| **Déposé** | Une personne a réalisé l’action sur la plateforme acheteur et l’a déclarée à SMART_AO. |
| **Accusé archivé** | La preuve de dépôt ou l’accusé de réception est ajouté et relié au paquet déposé. |

SMART_AO ne doit jamais afficher « dépôt réussi » avant l’ajout ou la confirmation de la preuve correspondante.

## 36. Contrat renforcé des opportunités

La correspondance avec un profil de veille et la qualification d’une opportunité sont deux étapes distinctes.

| Étape | Question | Exemple |
|---|---|---|
| **Correspondance** | « Cette opportunité ressemble-t-elle à la stratégie de l’entreprise ? » | Gros œuvre, 80 km, montant compatible. |
| **Qualification** | « L’entreprise peut-elle probablement répondre à cette affaire ? » | Qualification à vérifier, visite obligatoire, capacité équipe inconnue. |
| **Décision de créer l’affaire** | « Investissons-nous du temps dans l’analyse DCE ? » | Créer une affaire, transmettre, écarter ou mettre en veille. |

Une bonne correspondance ne doit jamais être affichée comme une capacité confirmée à répondre.

## 37. Matrice normative Vue → Actions autorisées

| Vue | Actions principales autorisées |
|---|---|
| Accueil / Command Center | Ouvrir une action, filtrer les priorités, créer une affaire, ouvrir le portefeuille. |
| File d’Actions patron | Prendre en compte, déléguer, demander une pièce, décider, clôturer, annuler avec motif. |
| Dossier de décision | Répondre, répondre sous conditions, refuser, accepter un risque, valider un prix, retourner une correction, autoriser une étape. |
| Portefeuille affaires | Créer, ouvrir, attribuer, réattribuer, arrêter, archiver, filtrer. |
| Vue de direction affaire | Ouvrir analyse, preuves, risques, prix privé, dépôt, journal ou décision. |
| Entreprise & capacités | Ajouter/modifier une capacité, qualification, référence, partenaire, règle interne ou préparation. |
| Bibliothèque | Ajouter une preuve, remplacer une version, autoriser un usage, demander un renouvellement, archiver. |
| Opportunités | Examiner, transmettre, créer une affaire, mettre en veille, écarter avec motif. |
| Équipe | Inviter, attribuer, retirer, suspendre, déléguer ponctuellement. |
| Prix privé | Créer un scénario, modifier une hypothèse, demander un devis, préparer une version, valider une version officielle. |
| Coffre de dépôt | Contrôler, créer un paquet préparé, autoriser le dépôt, enregistrer le dépôt, archiver l’accusé. |
| Journal de vérité | Filtrer, ouvrir une source, exporter selon droits ; aucune modification directe d’un fait historique. |

## 38. Matrice normative Vue → Situation métier préparée

Cette matrice n’impose aucun nom de classe ou de technologie. Elle définit simplement la **situation métier cohérente** que chaque vue doit recevoir.

| Vue | Situation métier préparée attendue |
|---|---|
| Accueil / Command Center | Actions patron, protection, échéances, portefeuille prioritaire, santé entreprise et activité récente. |
| File d’Actions patron | Actions actives, causes, propriétaires, exécutants, approbateurs, échéances et liens métier. |
| Dossier de décision | Contexte de décision, faits, inconnus, risques, capacités, preuves, prix si autorisé, conditions, choix et sources. |
| Portefeuille affaires | Résumés d’affaires, états, prochaines actions, responsables, blocages, décisions et échéances. |
| Vue de direction affaire | Synthèse de l’affaire, carte de décision, risques, preuves, équipe, échéances et changements récents. |
| Entreprise & capacités | Passeport opérationnel, préparation, capacités, qualifications, références, partenaires, charge et règles patron. |
| Bibliothèque | Preuves, versions, validités, états, usages, autorisations, renouvellements et historique. |
| Opportunités | Profils, correspondances expliquées, qualifications à effectuer, inconnus et actions disponibles. |
| Équipe | Comptes, accès, affectations, charge, travaux transmis et délégations. |
| Prix privé | Pièces de prix applicables, coûts, devis, scénarios, fiabilité, trésorerie, version officielle et liens DCE. |
| Coffre de dépôt | Paquet préparé, contrôles, versions, autorisations, dépôt déclaré et accusé archivé. |
| Journal de vérité | Chronologie métier, acteurs, sources, versions, décisions et conséquences. |

## 39. Préconditions et postconditions : règle obligatoire de toute action

Chaque action future devra être définie selon la séquence suivante :

```text
Action demandée
      ↓
Préconditions visibles et vérifiées
      ↓
Action autorisée ou refusée avec motif
      ↓
Résultat durable
      ↓
Postconditions visibles
      ↓
Journal de vérité et situations métier mises à jour
```

| Exemple : `Valider un prix` | Contrat |
|---|---|
| Préconditions | Patron autorisé ; version financière complète ; DCE applicable connu ; hypothèses visibles ; aucun blocage non traité empêchant la validation. |
| Action | Le patron valide une version de prix précise. |
| Résultat durable | La version officielle devient active ; l’ancienne reste accessible ; la décision et son contexte sont conservés. |
| Postconditions | La Vue de direction affiche le prix validé, le Coffre peut préparer le contrôle final et le Journal enregistre la validation. |
| Cas de refus | SMART_AO explique les éléments empêchant la validation et propose les actions à traiter. |

## 40. Conditions de gel V1.1

Le Contrat Métier vers Interface peut être considéré comme prêt pour la matrice `Vue → Action → Transition → Résultat` et le Contrat de domaine lorsque les règles suivantes sont validées :

1. Toute donnée variable possède, lorsque nécessaire, une fraîcheur et une date de référence visibles.
2. Toute vue déclare le niveau de cohérence qu’elle exige.
3. Toute information est distinguée comme fait, calcul, déduction, recommandation ou décision humaine.
4. Toute décision patron est rattachée à un contexte de décision figé et reconstruisible.
5. La situation actuelle n’écrase jamais le contexte historique d’une décision.
6. Toute Action patron possède préconditions, postconditions, cycle de vie, causes regroupées et résultat durable.
7. Gravité, urgence et blocage sont trois axes distincts.
8. Source, propriétaire de vérité, validateur, propriétaire, exécutant et approbateur ne sont jamais confondus.
9. Une version officielle de prix est liée au DCE applicable ; un scénario ne modifie jamais silencieusement cette version.
10. Un paquet préparé, un dépôt déclaré et un accusé archivé sont des états distincts.
11. Les matrices Vue → Actions autorisées et Vue → Situation métier préparée servent de référence pour le document suivant.
