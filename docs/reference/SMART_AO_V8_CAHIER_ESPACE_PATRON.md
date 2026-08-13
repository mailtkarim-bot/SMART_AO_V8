# SMART_AO V8 — Cahier fonctionnel de l’espace patron

**Version :** 1.0 — proposition à valider avant de concevoir le parcours d’analyse DCE  
**Statut :** spécification fonctionnelle détaillée — aucun code d’interface n’est écrit à ce stade  
**Utilisateur principal :** patron / dirigeant / administrateur de l’entreprise BTP  
**Périmètre :** espace privé du patron, installation de l’entreprise, cockpit, équipe, bibliothèque, opportunités, affaires, chiffrage privé, marchés gagnés, sécurité et réglages.

---

## 1. Mission de l’espace patron

L’espace patron est le lieu où le dirigeant pilote son entreprise dans SMART_AO. Il ne doit pas ressembler à un ERP lourd ou à un tableau de bord rempli de chiffres incompréhensibles. Son rôle est de permettre au patron de répondre chaque jour, en quelques minutes, à six questions concrètes :

1. **Quelles affaires exigent ma décision aujourd’hui ?**
2. **Quels dossiers sont prêts à être chiffrés ou déposés ?**
3. **Quels risques, délais, documents ou engagements peuvent me coûter de l’argent ?**
4. **Mon entreprise est-elle prête à répondre : documents, équipes, qualifications, partenaires et prix ?**
5. **Quelles opportunités correspondent réellement à ma stratégie ?**
6. **Quels marchés gagnés exigent une action pour protéger ma marge, ma trésorerie ou mes droits ?**

> **Promesse de l’espace patron :** « Vous gardez la maîtrise de vos affaires, de vos prix, de vos documents et de vos décisions. SMART_AO vous montre ce qui mérite votre attention avant qu’un oubli ne devienne un coût. »

Le patron ne travaille pas dans le même espace que ses collaborateurs. Il conserve la vision complète et les données confidentielles ; les collaborateurs préparent les affaires qui leur sont attribuées, sans accéder aux prix, aux marges, aux trésoreries ni aux décisions privées.

---

## 2. Séparation patron, collaborateurs et partenaires

SMART_AO est installé une seule fois pour l’entreprise, sur son VPS dédié. Il ne crée pas un serveur par salarié. L’étanchéité est obtenue par un espace applicatif propre à chaque utilisateur : les données visibles, les actions autorisées et les exports possibles dépendent de son rôle et de l’affaire concernée.

| Profil | Ce qu’il voit | Ce qu’il fait | Ce qu’il ne voit jamais par défaut |
|---|---|---|---|
| **Patron administrateur** | Toutes les affaires, opportunités, documents, alertes, marchés gagnés et cockpit de décision. | Crée les comptes, configure l’entreprise, attribue les affaires, valide, chiffre, décide et autorise le dépôt. | Les données d’autres entreprises clientes. |
| **Collaborateur** | Ses affaires attribuées, les tâches, les documents autorisés, les messages et la progression de son wizard. | Analyse, classe, complète, prépare, demande une pièce et transmet au patron. | Prix, devis fournisseurs, marges, trésorerie, fichiers Excel confidentiels, stratégie globale et affaires non attribuées. |
| **Partenaire externe** | Une demande limitée à une affaire et à un périmètre précis. | Fournit un prix, une disponibilité, une attestation ou un document. | Bibliothèque entière, autres affaires, autres partenaires, prix internes et informations du patron. |
| **Support SMART_AO** | Santé technique selon autorisation contractuelle. | Maintient l’instance, analyse un incident et applique une mise à jour. | DCE, prix, documents et données métier sans demande justifiée, accord et traçabilité. |

### 2.1. Règle de confidentialité absolue

Les éléments suivants sont **réservés au patron** : fichiers de prix, déboursés, devis fournisseurs, prix de vente, coefficients, marges, seuils d’alerte financière, trésorerie, capacités financières, règles de chiffrage, décisions Go/No-Go et paramètres de traitement externe des DCE.

Un collaborateur ne reçoit pas une version masquée de ces données : elles ne doivent pas lui être envoyées du tout. Le patron peut donner une autorisation ponctuelle à une personne de confiance, mais cette autorisation est explicite, limitée à une affaire et journalisée.

---

## 3. Règles d’ergonomie patron

Le patron a besoin d’une vision globale, mais pas d’un labyrinthe. Chaque écran patron respecte les règles suivantes.

| Règle | Conséquence concrète |
|---|---|
| Une page a une intention | Le cockpit sert à décider ; la bibliothèque sert à organiser les preuves ; le chiffrage sert à fixer le prix. |
| Une action principale | Le bouton visuellement dominant correspond à la prochaine action importante. |
| Des détails à la demande | Le résumé est visible en premier ; les tableaux complets et sources s’ouvrent seulement si le patron le demande. |
| Pas de jargon informatique | Les libellés sont : « Ajouter un document », « Vérifier le dossier », « Demander un prix », pas « Importer une ressource ». |
| Une situation expliquée | Tout risque indique le document source, son impact, le responsable et l’action possible. |
| Une progression réelle | SMART_AO affiche les étapes terminées et les blocages ; il n’affiche pas de pourcentage décoratif. |
| Aucune perte de travail | Chaque modification est enregistrée ou clairement signalée comme non enregistrée. |
| Retour contrôlé | Le patron peut revenir en arrière ; une modification importante peut demander une nouvelle validation. |

---

## 4. Plan de navigation patron

La navigation principale reste courte. Elle est affichée sur le côté gauche sur ordinateur et devient un menu compact sur tablette. La partie centrale de l’écran est réservée à l’action du jour.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ SMART_AO  | DUPONT BÂTIMENT                               🔔 3  [Noor ▾]    │
├───────────────┬─────────────────────────────────────────────────────────────┤
│ ▣ Cockpit     │                                                             │
│ ▤ Affaires    │                 CONTENU DE LA PAGE                          │
│ ◉ Opportunités│                                                             │
│ ▦ Entreprise  │                                                             │
│ ▤ Bibliothèque│                                                             │
│ € Chiffrage   │                                                             │
│ ♟ Équipe      │                                                             │
│ ⚙ Réglages    │                                                             │
└───────────────┴─────────────────────────────────────────────────────────────┘
```

| Entrée | Rôle | Bouton principal quand la page est ouverte |
|---|---|---|
| **Cockpit** | Priorités et décisions du jour. | `Traiter mes priorités`. |
| **Affaires** | Toutes les consultations, offres, dépôts et marchés gagnés. | `Créer ou importer une affaire`. |
| **Opportunités** | Veille d’avis, affaires reçues et préqualification. | `Créer un profil de recherche`. |
| **Entreprise** | Identité, capacités, zones, contacts, signataires et règles internes. | `Compléter mon entreprise`. |
| **Bibliothèque** | Documents, références, modèles, partenaires et pièces expirantes. | `Ajouter des documents`. |
| **Chiffrage privé** | Prix, devis, coûts, marges, scénarios et trésorerie. | `Ouvrir une affaire à chiffrer`. |
| **Équipe** | Comptes, attributions, invitations et disponibilité des collaborateurs. | `Inviter un collaborateur`. |
| **Réglages** | Notifications, sécurité, traitement de données, support et historique. | `Vérifier mes réglages`. |

Les marchés gagnés apparaissent dans **Affaires** comme un état particulier, afin que le patron garde un seul portefeuille. Ils disposent ensuite d’un cockpit d’exécution spécifique.

---

## 5. Écran P00 — Cockpit patron

### 5.1. Objet de l’écran

Le cockpit est la première page après connexion. Il ne cherche pas à montrer toute l’entreprise ; il montre ce qui demande une décision ou une action du patron aujourd’hui.

> **Message-guide :** « Bonjour [Prénom]. Voici les affaires et les éléments qui exigent votre attention. Vous pouvez traiter les priorités maintenant ou ouvrir une vue complète de votre portefeuille. »

### 5.2. Maquette fonctionnelle

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Bonjour Noor.  3 décisions attendent votre validation.                       │
│ [Traiter mes priorités]                                    [Créer une affaire]│
├─────────────────────────────────────────────────────────────────────────────┤
│ À DÉCIDER          À CHIFFRER          À DÉPOSER         À PROTÉGER         │
│     3                   2                  1                  4             │
│ Go/No-Go            dossiers prêts      échéance < 48 h   pièces / risques   │
│ [Voir]               [Voir]              [Voir]             [Voir]           │
├─────────────────────────────────────────────────────────────────────────────┤
│ AFFAIRES PRIORITAIRES                                                        │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Centre médical Guesnain — Lot 01                    Dépôt 18/09 12:00   │ │
│ │ Étape 7/11 · Préparation terminée · Blocage : DPGF à chiffrer           │ │
│ │ Préparé par Karim                                      [Ouvrir]         │ │
│ ├─────────────────────────────────────────────────────────────────────────┤ │
│ │ Réhabilitation école — Lot peinture                  Visite demain 9:00 │ │
│ │ Étape 4/11 · Attestation de visite attendue                           │ │
│ │ Préparé par Salma                                      [Ouvrir]         │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│ OPPORTUNITÉS À EXAMINER                         SANTÉ DE L’ENTREPRISE        │
│ • 4 opportunités correspondent à vos profils     • 1 assurance expire / 45 j│
│ [Examiner les opportunités]                      [Voir la bibliothèque]     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3. Éléments de l’écran et boutons

| Zone | Information affichée | Bouton | Effet du bouton |
|---|---|---|---|
| Bandeau d’accueil | Prénom, nombre de décisions et résumé de la priorité. | `Traiter mes priorités` | Ouvre la liste des actions patron triée par échéance et impact. |
| Action rapide | Création/import d’une consultation reçue hors veille. | `Créer une affaire` | Ouvre le formulaire minimal de création d’affaire ou l’import de DCE. |
| Carte « À décider » | Affaires nécessitant Go/No-Go, décision de variante, validation de partenaire ou acceptation d’un risque. | `Voir` | Ouvre une liste filtrée des décisions avec sources et options. |
| Carte « À chiffrer » | Affaires transmises par les collaborateurs, prêtes pour le patron. | `Voir` | Ouvre la file de chiffrage privé. |
| Carte « À déposer » | Dossiers dont l’échéance approche et dont le dépôt demande contrôle ou validation. | `Voir` | Ouvre le coffre de dépôt des affaires concernées. |
| Carte « À protéger » | Pièces expirantes, risques élevés, rectificatifs, alertes de trésorerie et documents tiers attendus. | `Voir` | Ouvre le registre d’alertes, classé par gravité. |
| Affaire prioritaire | Nom, acheteur, lot, échéance, étape réelle, responsable et blocage. | `Ouvrir` | Ouvre le résumé patron de cette affaire. |
| Opportunités | Nombre et raison de correspondance. | `Examiner les opportunités` | Ouvre la veille avec les profils appliqués. |
| Santé entreprise | Documents, qualifications, prix ou profils à mettre à jour. | `Voir la bibliothèque` | Ouvre la vue de préparation de l’entreprise. |

### 5.4. Règles d’affichage des priorités

| Priorité | Quand elle apparaît | Couleur et texte |
|---|---|---|
| **Bloquante** | Dépôt imminent, document éliminatoire absent, pièce expirée, risque non validé ou action patron indispensable. | Rouge + texte explicite. |
| **Importante** | Échéance proche, dossier prêt à chiffrer, rectificatif à revoir ou prix fournisseur attendu. | Orange + action recommandée. |
| **À préparer** | Action utile mais non urgente : mise à jour d’une référence, profil de veille, document bientôt expirant. | Bleu/gris + date cible. |
| **Information** | Travail terminé, opportunité détectée, document ajouté ou action collaborateur reçue. | Neutre ; aucune alerte intrusive. |

Le cockpit ne montre pas les montants de marge ou de trésorerie dans les cartes globales. Ces informations sont visibles seulement après ouverture de l’affaire ou de la page chiffrage privée.

---

## 6. Écran P01 — Entreprise : la fiche officielle et opérationnelle

Cette page est le profil de l’entreprise qui répond aux consultations. Elle est organisée par cartes courtes, non par un formulaire interminable. Le patron peut compléter une carte, l’enregistrer et revenir plus tard.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ ENTREPRISE — Dupont Bâtiment                         [Enregistrer]          │
│ Votre profil alimente vos candidatures et vous aide à qualifier les affaires.│
├─────────────────────────────────────────────────────────────────────────────┤
│ [Identité juridique ✓] [Contacts ✓] [Métiers] [Capacités] [Signataires]      │
│ [Implantations] [Règles internes]                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ IDENTITÉ JURIDIQUE                                                           │
│ Raison sociale *          [ Dupont Bâtiment                         ]        │
│ Nom commercial            [ Dupont Construction                    ]        │
│ Forme juridique *         [ SAS ▾ ]                                         │
│ SIREN *                   [ 123 456 789                           ]         │
│ SIRET répondant *         [ 123 456 789 00012                     ]         │
│ TVA intracommunautaire    [ FR...                                  ]         │
│ [Enregistrer cette rubrique et continuer]                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.1. Carte P01-A — Identité juridique

| Champ | Obligatoire | Aide | Validation attendue |
|---|---:|---|---|
| Raison sociale | Oui | Nom légal figurant sur les documents officiels. | Non vide ; réutilisé dans les formulaires. |
| Nom commercial | Non | Nom connu des clients si différent du nom légal. | Texte libre. |
| Forme juridique | Oui | SARL, SAS, SA, EI, EURL, etc. | Choix dans une liste complétable. |
| SIREN | Oui | Numéro de l’entreprise. | Format contrôlé ; patron confirme la donnée. |
| SIRET répondant | Oui | Établissement qui répond aux marchés. | Format contrôlé. |
| Numéro TVA intracommunautaire | Non | À renseigner si pertinent pour l’entreprise. | Format contrôlé si renseigné. |
| RCS / registre compétent | Non | Information d’immatriculation disponible sur les documents de l’entreprise. | Texte libre contrôlé. |
| Code APE/NAF | Non | Activité déclarée ; ne remplace pas les métiers réellement maîtrisés. | Format contrôlé si renseigné. |
| Date de création | Non | Utile si une consultation demande l’ancienneté. | Date. |

**Boutons :** `Enregistrer cette rubrique`, `Retour au cockpit`, `Continuer vers les contacts`.

### 6.2. Carte P01-B — Adresses et implantations

| Champ | Usage futur |
|---|---|
| Adresse du siège social | Candidatures, courriers et identité de l’entreprise. |
| Adresse de facturation, si différente | Suivi après attribution et documents administratifs. |
| Dépôt, atelier ou agence | Calcul de distance, organisation logistique et profil de veille. |
| Adresse de correspondance | Courriers ou interlocuteurs si distincts. |
| Zone de service principale | Première base du profil de recherche. |

Le patron peut ajouter plusieurs implantations. Chaque implantation reçoit un nom simple : « Siège Lille », « Dépôt Arras », « Agence Paris ».

**Boutons :** `Ajouter une implantation`, `Modifier`, `Retirer`, `Enregistrer et continuer`.

### 6.3. Carte P01-C — Contacts et personnes habilitées

| Champ | Public par défaut | Utilisation |
|---|---|---|
| Représentant légal | Patron uniquement | Contrôle de l’entité habilitée à engager l’entreprise. |
| Signataire autorisé | Patron uniquement | Documents lorsque le DCE exige ou prévoit une signature. |
| Contact appels d’offres | Patron et collaborateurs concernés | Questions à l’acheteur, suivi de réponse et invitations. |
| Contact administratif | Patron selon choix | Pièces administratives et candidatures. |
| Contact travaux | Selon affaires attribuées | Planning, moyens, visite, méthodes et exécution. |
| Contact facturation | Patron uniquement par défaut | Situations, factures et trésorerie après attribution. |
| Contact urgence | Patron uniquement | Alertes critiques d’accès ou de dépôt. |

Une personne peut occuper plusieurs fonctions. SMART_AO doit éviter de demander la même information plusieurs fois.

**Boutons :** `Ajouter une personne`, `Définir comme signataire`, `Modifier`, `Désactiver`, `Enregistrer et continuer`.

### 6.4. Carte P01-D — Métiers et savoir-faire

| Rubrique | Informations à renseigner |
|---|---|
| Corps d’état et lots | Gros œuvre, démolition, peinture, CVC, électricité, menuiserie, VRD, etc. |
| Prestations précises | Techniques, travaux spécifiques, interventions exclues et spécialités. |
| Types de chantier | Neuf, réhabilitation, site occupé, logement, santé, industriel, patrimoine, etc. |
| Méthodes particulières | Travaux de nuit, phasage, milieu occupé, désamiantage sous compétence déclarée, travaux à haute contrainte, etc. |
| Références de capacité | Nombre de chantiers, équipe ou matériel nécessaire, sans créer de promesse automatique. |

**Boutons :** `Ajouter un métier`, `Ajouter une spécialité`, `Déclarer une exclusion`, `Enregistrer mes capacités`.

### 6.5. Carte P01-E — Qualifications, assurances et habilitations

| Champ | Exemple | Ce que SMART_AO fait |
|---|---|---|
| Type de qualification | Qualibat, RGE, habilitation, certification métier. | Classe la pièce et la relie aux activités. |
| Numéro / référence | Numéro figurant sur le document. | Mémorise le numéro sans l’inventer. |
| Périmètre | Activités couvertes, niveaux, catégories ou zones. | Alerte si le lot dépasse le périmètre connu. |
| Date d’émission / expiration | Dates figurant sur la pièce. | Crée une alerte avant échéance. |
| Document original | Certificat, attestation ou habilitation. | Conserve le fichier source. |

**Boutons :** `Ajouter une qualification`, `Téléverser le justificatif`, `Créer un rappel de renouvellement`, `Enregistrer`.

### 6.6. Carte P01-F — Règles internes du patron

Ces données ne sont jamais présentées comme des règles universelles. Elles traduisent la manière dont l’entreprise souhaite décider.

| Réglage privé | Exemple | Usage |
|---|---|---|
| Marge cible | Valeur ou fourchette définie par le patron. | Alerte dans le chiffrage privé. |
| Seuil d’alerte de marge | Niveau sous lequel l’affaire doit être justifiée. | Carte « À protéger » et décision Go/No-Go. |
| Provision aléas habituelle | Valeur définie par métier ou affaire. | Scénarios de chiffrage, jamais appliquée automatiquement sans contrôle. |
| Capacité d’affaires simultanées | Nombre ou volume acceptable selon l’entreprise. | Signal de surcharge dans les opportunités et décisions. |
| Délais minimums de réponse | Temps minimal souhaité avant dépôt. | Classement des opportunités et mode urgence. |
| Règles de validation | Qui peut préparer, relire et transmettre. | Parcours collaborateurs et coffre de dépôt. |

**Boutons :** `Ajouter une règle`, `Modifier`, `Désactiver une règle`, `Voir l’historique`, `Enregistrer mes règles`.

---

## 7. Écran P02 — Équipe, comptes et délégations

### 7.1. Vue équipe

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ ÉQUIPE                                               [Inviter un collaborateur]│
│ Vous contrôlez qui peut travailler sur quelles affaires.                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ Nom             Fonction          Accès actif   Affaires       Action         │
│ Karim A.        Chargé d’affaires Oui           3              [Gérer]        │
│ Salma B.        Conductrice       Oui           2              [Gérer]        │
│ Youssef C.      Métreur           Invitation    0              [Renvoyer]     │
├─────────────────────────────────────────────────────────────────────────────┤
│ [Voir les accès retirés]             [Consulter l’historique des actions]     │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Information dans la liste | Sens métier |
|---|---|
| Nom et fonction | Identifier la personne responsable. |
| Statut d’accès | Invitation envoyée, actif, suspendu ou désactivé. |
| Affaires attribuées | Mesurer la charge et savoir qui travaille sur quoi. |
| Dernière activité | Vérifier qu’une affaire n’est pas sans suivi. |
| Alerte éventuelle | Dossier en retard, action demandée au patron ou invitation non finalisée. |

### 7.2. Fenêtre « Inviter un collaborateur »

| Champ ou action | Règle fonctionnelle |
|---|---|
| Prénom et nom | Obligatoires. |
| E-mail professionnel | Obligatoire et utilisé pour l’invitation sécurisée. |
| Fonction | Chargé d’affaires, métreur, conducteur de travaux, assistante, responsable administratif ou texte libre. |
| Message d’invitation | Facultatif ; ajouté au message d’activation. |
| Affaires initiales | Facultatives. Le patron peut attribuer plus tard. |
| Résumé des droits | Visible avant envoi : « Accès aux affaires attribuées ; aucun accès aux prix, marges ou trésorerie. » |
| Bouton principal | `Envoyer l’invitation`. |
| Boutons secondaires | `Annuler`, `Enregistrer sans envoyer`. |

### 7.3. Fenêtre « Gérer les accès de [Nom] »

| Action | Effet |
|---|---|
| `Attribuer une affaire` | Ajoute une affaire, avec rôle et tâches attribués. |
| `Retirer une affaire` | Bloque l’accès futur ; les contributions restent dans l’historique. |
| `Voir ses travaux` | Ouvre une liste d’étapes, documents et transmissions réalisés. |
| `Suspendre le compte` | Bloque la connexion immédiatement, sans supprimer les traces. |
| `Réactiver le compte` | Réouvre uniquement les accès encore autorisés. |
| `Renvoyer une invitation` | Génère un nouveau lien d’activation si nécessaire. |
| `Supprimer définitivement` | Non disponible tant que des contributions existent ; proposer d’abord la désactivation. |

---

## 8. Écran P03 — Bibliothèque et Passeport Entreprise

La bibliothèque est le capital de l’entreprise. Elle doit permettre au patron de savoir, avant de répondre à une affaire, si les preuves, documents, capacités et partenaires nécessaires sont prêts.

### 8.1. Maquette fonctionnelle

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ BIBLIOTHÈQUE DE L’ENTREPRISE                       [Ajouter des documents]   │
│ 18 pièces prêtes · 2 à renouveler · 1 à vérifier · 5 documents patron privé │
├─────────────────────────────────────────────────────────────────────────────┤
│ [Toutes] [Administratif] [Qualifications] [Références] [Équipe] [Partenaires]│
│ [Modèles] [Prix privés]                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ Document             Statut            Validité        Utilisé dans          │
│ Décennale 2026       À renouveler      30/11/2026      2 affaires             │
│ Qualibat 2111        Prêt              31/12/2026      4 affaires             │
│ Prix Gros œuvre V8   Patron privé      01/09/2026      1 chiffrage            │
│ [Ouvrir] [Remplacer] [Utilisations] [Créer une tâche]                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2. Filtres disponibles

| Filtre | Valeurs |
|---|---|
| Famille | Administratif, assurance, qualification, référence, équipe, matériel, partenaire, modèle, prix, financier privé. |
| Statut | Prêt, à vérifier, bientôt à renouveler, expiré, absent, réservé patron. |
| Activité / lot | Métiers et lots renseignés dans l’entreprise. |
| Date | Émis, expire avant, expiré depuis, sans date connue. |
| Utilisation | Non utilisé, utilisé dans une affaire, demandé par une affaire, archivé. |
| Confidentialité | Partageable selon attribution, patron uniquement, partage ponctuel. |

### 8.3. Bouton principal « Ajouter des documents »

Le bouton ouvre un parcours en trois fenêtres, pas une zone de dépôt aveugle.

| Fenêtre | Question posée | Actions |
|---|---|---|
| **1. Choisir la famille** | « Quel type de document ajoutez-vous ? » | Sélection d’une famille ; aide expliquant les exemples. |
| **2. Déposer les fichiers** | « Ajoutez le document original de votre entreprise ou partenaire. » | Glisser-déposer, sélection de fichiers, suppression avant import. |
| **3. Décrire et protéger** | « Pour quand et pour quel usage ce document est-il valable ? » | Dates, périmètre, source, confidentialité, commentaire et responsable. |

Le patron peut ajouter plusieurs fichiers à la fois, mais chaque fichier doit recevoir une classification avant d’être proposé dans une affaire.

### 8.4. Fiche d’un document

| Champ affiché | Explication |
|---|---|
| Nom et fichier original | Nom proposé par le patron ; original accessible selon droit. |
| Famille / sous-type | Permet de savoir ce que le document peut prouver. |
| Émetteur / source | Assureur, entreprise, URSSAF, client, fournisseur, partenaire, etc. |
| Date d’émission et expiration | Déclenche les alertes, sans inventer une validité. |
| Périmètre | Activité, lot, personne, matériel, partenaire ou zone concernée. |
| Niveau de confidentialité | Patron, partage par affaire ou partage ponctuel. |
| Utilisations | Affaires dans lesquelles le document a été proposé, joint ou validé. |
| Historique | Création, remplacement, validation, consultation et retrait. |

**Boutons de la fiche :** `Ouvrir le document`, `Télécharger si autorisé`, `Remplacer par une nouvelle version`, `Modifier les informations`, `Créer une tâche de renouvellement`, `Voir les affaires concernées`, `Archiver`.

---

## 9. Écran P04 — Partenaires, fournisseurs et sous-traitants

Cette page complète la bibliothèque. Elle donne au patron une vision de son réseau, de ses documents et de sa capacité à répondre avec d’autres entreprises sans chercher dans des e-mails dispersés.

| Donnée de partenaire | Champ à renseigner |
|---|---|
| Identité | Raison sociale, forme juridique, SIREN/SIRET si connu, adresse, site. |
| Contact | Nom, e-mail, téléphone, fonction et contact urgence. |
| Rôle habituel | Fournisseur, sous-traitant, cotraitant, bureau d’études, diagnostiqueur, loueur, transporteur, etc. |
| Métiers et spécialités | Activités qu’il couvre réellement. |
| Zone et disponibilité déclarée | Zone habituelle, périodes connues, capacité à confirmer par affaire. |
| Documents | Assurances, qualifications, attestations, références, RIB si nécessaire et autorisé. |
| Conditions connues | Délais, minimum de commande, exclusions, mode de consultation ; sans en déduire un prix garanti. |
| Évaluation interne privée | Fiabilité, qualité, délais, retours d’expérience, réservés au patron. |

### 9.1. Fenêtre « Demander une pièce ou un prix »

| Élément | Contenu |
|---|---|
| Affaire concernée | Nom de l’affaire, lot et échéance. |
| Périmètre partagé | Documents et pages que le patron autorise à partager. |
| Demande | Prix, disponibilité, assurance, qualification, fiche technique, attestation ou confirmation de capacité. |
| Date souhaitée | Date de retour attendue, distincte de la date de dépôt final. |
| Message proposé | Brouillon clair que le patron peut modifier et valider. |
| Bouton principal | `Envoyer la demande`. |
| Résultat | Demande datée, statut envoyé/reçu/en retard et documents retournés associés à l’affaire. |

Le partenaire ne reçoit jamais la bibliothèque entière ni le chiffrage du patron. Il ne voit que ce qui est nécessaire à sa demande.

---

## 10. Écran P05 — Opportunités et profils de veille

### 10.1. Objet de l’écran

L’écran Opportunités aide le patron à trouver puis qualifier les affaires qui correspondent à son entreprise. Il ne se contente pas d’afficher des avis : chaque opportunité doit expliquer pourquoi elle correspond, quels critères ne correspondent pas encore et quelle action permet d’aller plus loin.

Les sources publiques telles que le BOAMP peuvent alimenter la veille selon les connecteurs autorisés. Le BOAMP propose une recherche d’avis par critères ; SMART_AO transforme ces critères en profils métier de l’entreprise et conserve l’explication de chaque correspondance. [1]

### 10.2. Maquette fonctionnelle

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ OPPORTUNITÉS                                           [Créer un profil]     │
│ Profil actif : « Gros œuvre — Hauts-de-France » · 14 résultats cette semaine │
├─────────────────────────────────────────────────────────────────────────────┤
│ [À examiner 6] [À transmettre 2] [Écartées 18] [Profils 3]                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Lycée de Douai — Réhabilitation — Lot Gros œuvre                             │
│ Dépôt : 04/10 · 38 km · Montant estimé : 250–400 k€                           │
│ Correspond : gros œuvre, réhabilitation, rayon 120 km                         │
│ Attention : visite obligatoire · qualification à vérifier                     │
│ [Examiner] [Transmettre à un collaborateur] [Écarter]                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.3. Profil de veille : champs à renseigner

| Groupe de champs | Champs précis |
|---|---|
| Identification du profil | Nom du profil, actif/en pause, commentaire stratégique du patron. |
| Activités recherchées | Métiers, lots, mots-clés souhaités, mots-clés exclus, techniques maîtrisées. |
| Types de travaux | Neuf, réhabilitation, site occupé, entretien, logement, santé, industrie, patrimoine, public, privé. |
| Localisation | Siège, dépôt ou agence de départ ; rayon en kilomètres ; régions, départements, communes prioritaires ou exclues. |
| Taille d’affaire | Montant minimum, maximum, taille de lot préférée, durée acceptable, début souhaité. |
| Type d’acheteur | Public, privé, bailleur, collectivité, établissement de santé, industriel, donneur d’ordre suivi ou à éviter. |
| Capacité | Équipe disponible, matériel, périodes saturées, délai minimum avant dépôt, limite d’affaires simultanées. |
| Partenariats | Réponse seule, groupement possible, sous-traitance possible, compétences à rechercher. |
| Exclusions | Risques, zones, délais, types de travaux ou conditions que le patron refuse. |
| Alertes | Fréquence, e-mail ou cockpit, nombre maximal de résultats, seuil de correspondance. |

### 10.4. Boutons de l’opportunité

| Bouton | Effet |
|---|---|
| `Examiner` | Ouvre la fiche d’opportunité avec critères, sources, date, pièces et première qualification. |
| `Transmettre à un collaborateur` | Crée une tâche de préanalyse, sans créer encore une offre ni donner accès aux prix. |
| `Créer une affaire` | Transforme l’opportunité en affaire SMART_AO, avec sources et profil à l’origine. |
| `Écarter` | Demande un motif : zone, montant, charge, risque, hors métier, délai, acheteur, autre. |
| `Mettre en veille` | Conserve l’opportunité à suivre sans l’attribuer immédiatement. |
| `Créer un profil` | Ouvre le formulaire complet ci-dessus. |
| `Modifier le profil` | Met à jour les critères avec historique : qui, quoi, quand, pourquoi. |

---

## 11. Écran P06 — Portefeuille des affaires

L’écran Affaires rassemble toutes les consultations de l’entreprise, de la première opportunité au marché gagné, perdu ou archivé. Il ne mélange pas les lots : un lot sélectionné devient une affaire distincte, reliée à la consultation mère lorsqu’il y en a plusieurs.

### 11.1. États visibles d’une affaire

| État | Signification | Action patron la plus probable |
|---|---|---|
| Opportunité à examiner | Avis ou dossier non encore pris en charge. | Qualifier, transmettre ou écarter. |
| Analyse en cours | Collaborateur travaille sur le DCE. | Suivre les blocages ou ajouter un responsable. |
| Attente de décision | Une synthèse technique est disponible. | Répondre, répondre sous conditions ou arrêter. |
| Préparation de l’offre | Pièces, mémoire, questions et tâches sont en cours. | Lever les blocages, fournir documents ou partenaires. |
| Prête à chiffrer | Collaborateur a transmis le dossier. | Ouvrir le chiffrage privé. |
| Chiffrage en cours | Le patron construit et contrôle son offre financière. | Compléter, comparer, simuler et valider. |
| Prête au contrôle final | Prix et pièces sont préparés, dépôt à vérifier. | Ouvrir le coffre de dépôt. |
| Déposée | Accusé de réception importé et version archivée. | Suivre l’attribution et les demandes ultérieures. |
| Gagnée / perdue / arrêtée | Issue connue ou décision de ne pas poursuivre. | Capitaliser les leçons et archiver. |

### 11.2. Maquette fonctionnelle

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ AFFAIRES                                      [Créer une affaire] [Filtres]  │
│ [Toutes] [À décider] [À chiffrer] [À déposer] [Déposées] [Marchés gagnés]   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Affaire                 État              Échéance        Responsable Action│
│ Guesnain Lot 01         Prête à chiffrer  18/09 12:00     Karim       [Ouvrir]│
│ École Douai Lot 07      Analyse en cours  Visite demain   Salma       [Suivre]│
│ Mairie Lens Lot 03      Déposée           Attente réponse Noor        [Voir]  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.3. Boutons de la liste des affaires

| Bouton | Effet |
|---|---|
| `Créer une affaire` | Crée une affaire manuelle ou ouvre l’import d’un DCE reçu. |
| `Filtres` | Ouvre les filtres : état, échéance, responsable, lot, métier, acheteur, risque et période. |
| `Ouvrir` | Ouvre le résumé patron de l’affaire. |
| `Suivre` | Ouvre les tâches, documents et progression du collaborateur. |
| `Réattribuer` | Change le responsable ou ajoute un relecteur. |
| `Arrêter l’affaire` | Demande une décision patron et un motif conservé dans la mémoire commerciale. |
| `Archiver` | Cache l’affaire des vues actives sans supprimer documents, décisions ni preuves. |

---

## 12. Écran P07 — Résumé patron d’une affaire

Le résumé patron est la page qui permet de reprendre un DCE préparé par un collaborateur sans relire tous les fichiers. Il présente l’information par décision, jamais par moteur technique.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ CENTRE MÉDICAL GUESNAIN — LOT 01                              [Retour]      │
│ Dépôt 18/09/2026 12:00 · Responsable : Karim · Étape : prête à chiffrer      │
├─────────────────────────────────────────────────────────────────────────────┤
│ [Résumé] [Obligations] [Documents] [Risques] [Questions] [Prix privé]        │
├─────────────────────────────────────────────────────────────────────────────┤
│ CE QUE VOUS DEVEZ DÉCIDER                                                    │
│ • Visite obligatoire : attestation reçue ✓                                    │
│ • Diagnostic amiante complémentaire absent : risque à accepter / questionner  │
│ • Pénalité : 200 €/jour, plafond 20 % HT                                      │
│ [Décider de répondre]  [Demander une correction]  [Ouvrir le chiffrage]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Onglet | Contenu | Bouton principal |
|---|---|---|
| **Résumé** | Date, lot, responsable, étape, décisions attendues et blocages. | `Décider de répondre` ou `Ouvrir le chiffrage`. |
| **Obligations** | Carte RC/CCAP/CCTP : pièces, délais, critères, visite, formats, signatures et actions. | `Voir la source`. |
| **Documents** | Documents reçus, manquants, brouillons, modèles acheteur, pièces tiers et statut. | `Traiter les documents manquants`. |
| **Risques** | Pénalités, contraintes, contradictions, incertitudes, conditions de site et risques contractuels. | `Décider du traitement`. |
| **Questions** | Questions à l’acheteur, sources, impact et statut envoyé/répondu. | `Valider une question`. |
| **Prix privé** | DPGF/BPU/DQE, devis, coûts, scénarios et marge. | `Ouvrir le chiffrage privé`. |

### 12.1. Boutons de décision du patron

| Bouton | Condition d’apparition | Effet |
|---|---|---|
| `Décider de répondre` | Première analyse suffisamment complète. | Ouvre la décision Go/No-Go avec risques, capacités et conditions. |
| `Répondre sous conditions` | Un élément critique reste à sécuriser. | Enregistre les conditions, responsables, dates et empêche la fausse clôture. |
| `Arrêter l’affaire` | Patron choisit de ne plus investir de temps. | Demande un motif et archive sans supprimer l’historique. |
| `Demander une correction` | Le patron veut renvoyer une tâche au collaborateur. | Crée une demande précise, avec message et échéance. |
| `Demander un prix / document` | Partenaire ou tiers doit intervenir. | Ouvre la demande limitée au périmètre autorisé. |
| `Ouvrir le chiffrage privé` | Le dossier technique est suffisamment préparé. | Ouvre l’écran P08. |
| `Ouvrir le coffre de dépôt` | Toutes les validations requises sont réalisées. | Ouvre le contrôle final et l’assemblage. |

---

## 13. Écran P08 — Chiffrage privé, prix et décision de marge

Cet écran est exclusivement patron. Il ne peut pas être ouvert, recherché, exporté ou aperçu par un collaborateur sans autorisation exceptionnelle explicite.

### 13.1. Objet de l’écran

Le chiffrage privé ne remplace pas le savoir-faire du patron. Il l’aide à retrouver ses prix, contrôler la couverture du DCE, comparer les devis, comprendre les risques et décider d’un prix final en connaissance de cause.

> **Message-guide :** « Vous êtes dans votre espace de chiffrage privé. Les prix internes, devis, marges et scénarios de cette affaire ne sont visibles que par vous. »

### 13.2. Onglets de chiffrage

| Onglet | Ce que le patron voit et renseigne |
|---|---|
| **Pièces de prix acheteur** | DPGF, BPU, DQE, acte d’engagement, onglets Excel, postes, unités, cellules à compléter et contrôles de cohérence. |
| **Prix de l’entreprise** | Fichiers Excel source, versions de prix, postes rapprochés, éléments non reconnus et choix du patron. |
| **Fournisseurs et sous-traitants** | Devis reçus, validité, périmètre, exclusions, délais, statut de réponse et écarts avec les postes du DCE. |
| **Coût de revient** | Main-d’œuvre, matériel, matériaux, sous-traitance, frais de chantier et hypothèses validées. |
| **Scénarios** | Prix prudent, prix cible, prix compétitif, aléas et conditions ; toujours avec hypothèses visibles. |
| **Marge et trésorerie** | Marge selon scénario, avances, retenues, rythme de dépenses/encaissements et alertes de tension. |
| **Contrôles** | Postes sans prix, incohérences, montant AE/DPGF/BPU, options/PSE, révision, pénalités et risques à accepter. |
| **Décision finale** | Montant retenu, version à reporter, marge acceptée, réserves, signataire et validation patron. |

### 13.3. Champs principaux du chiffrage

| Zone | Champs et informations |
|---|---|
| Prix de base | Montant HT, TVA selon cadre, montant TTC de lecture, forme de prix, date de validité et source. |
| Déboursés | Main-d’œuvre, matériaux, matériel, sous-traitance, transport, installation et frais spécifiques, selon modèle de l’entreprise. |
| Hypothèses | Rendements, quantités à confirmer, accès, horaires, évacuations, matériaux, délais, prix fournisseurs et risques identifiés. |
| Frais | Frais de chantier, frais généraux, provisions, assurances ou coûts spécifiques définis par le patron. |
| Marge | Objectif, minimum d’alerte, marge calculée par scénario et commentaire de décision. |
| Trésorerie | Avance, retenue, cautions, échéancier, dépenses attendues, encaissements attendus et besoin de financement estimé. |
| Clauses | Pénalités, révision/actualisation, durée, dates de base, garanties, conditions de paiement, clauses à vérifier. |

### 13.4. Boutons du chiffrage

| Bouton | Effet |
|---|---|
| `Importer mes prix` | Ouvre la sélection d’un fichier privé existant ou d’une nouvelle version Excel. |
| `Rapprocher les postes` | Propose une correspondance entre postes DPGF/BPU et références internes, à confirmer par le patron. |
| `Ajouter un devis fournisseur` | Joint un devis, son périmètre, sa date, ses exclusions et le partenaire concerné. |
| `Créer un scénario` | Duplique les hypothèses dans un scénario nommé, sans écraser la version précédente. |
| `Comparer les scénarios` | Compare prix, coût, marge, trésorerie, risques et hypothèses. |
| `Voir les incohérences` | Liste les postes non couverts, totaux incohérents, options mélangées ou données à vérifier. |
| `Préparer la version de prix` | Remplit une copie de travail du modèle acheteur selon la décision patron. |
| `Valider mon prix` | Enregistre la décision patron, les hypothèses, le scénario retenu et la personne validatrice. |
| `Transmettre au contrôle final` | Rend disponible le dossier au coffre de dépôt, sans déposer automatiquement. |

Aucun bouton `Valider mon prix` ne doit fonctionner si le patron n’a pas vu les risques bloquants, les hypothèses non confirmées et la cohérence des pièces de prix. Il peut néanmoins décider d’accepter un risque, à condition que cette décision soit enregistrée avec son motif.

---

## 14. Écran P09 — Coffre de dépôt et validation finale

Le coffre de dépôt répond à une seule question : **« Puis-je déposer cette offre sans oublier une pièce, sans envoyer la mauvaise version et sans signer un engagement non validé ? »**

| Zone du coffre | Information affichée |
|---|---|
| Candidature | DUME/DC, attestations, assurances, qualifications, RIB et groupement selon le RC. |
| Offre technique | Mémoire, planning, moyens, références, environnement, variantes et annexes. |
| Offre financière | DPGF/BPU/DQE/AE, options, PSE et versions validées par le patron. |
| Pièces de tiers | Attestation de visite, devis, documents partenaires, garanties ou documents à obtenir. |
| Formats et structure | Fichiers, formats, taille, nom, arborescence ou enveloppes demandées par l’acheteur. |
| Signatures et validations | Éléments à signer, personne habilitée, action humaine attendue et statut. |
| Historique | Version de chaque fichier, patron qui a validé, date et modifications depuis la dernière validation. |

### 14.1. Boutons du coffre

| Bouton | Effet |
|---|---|
| `Vérifier le dossier` | Exécute les contrôles de complétude et de cohérence selon le RC. |
| `Voir les éléments bloquants` | Affiche uniquement les points empêchant une validation. |
| `Créer le dossier de dépôt` | Assemble les fichiers validés dans la structure demandée, sans modifier les originaux. |
| `Télécharger le ZIP de dépôt` | Permet au patron ou à la personne habilitée de télécharger le dossier. |
| `Marquer comme déposé` | Demande l’accusé de réception, la date/heure et la plateforme utilisée. |
| `Importer l’accusé de réception` | Archive la preuve de dépôt et associe les fichiers déposés. |
| `Créer une nouvelle version` | Réouvre le dossier après une modification ; la version précédente reste archivée. |

SMART_AO ne promet jamais le dépôt automatique universel. Le patron ou la personne habilitée effectue le dépôt sur la plateforme demandée par l’acheteur ; SMART_AO contrôle, prépare et archive la preuve.

---

## 15. Écran P10 — Marchés gagnés : protéger la marge après attribution

Lorsqu’une offre est gagnée, l’affaire bascule dans l’état **Marché gagné**. Le patron ne doit pas perdre les informations collectées pendant la réponse : obligations, pièces, risques, hypothèses, engagements du mémoire et décisions de prix deviennent la base de suivi du marché.

| Carte du marché gagné | Ce que le patron voit | Action principale |
|---|---|---|
| **Démarrage** | Ordre de service, documents à remettre, sous-traitance, assurances, plans, contacts et actions initiales. | `Préparer le démarrage`. |
| **Obligations et délais** | Jalons, réunions, visas, livrables, contrôles, échéances et pénalités potentielles. | `Traiter les obligations proches`. |
| **Trésorerie** | Avance, situations, retenues, paiements attendus, dépenses et alertes. | `Mettre à jour la situation`. |
| **Variations et preuves** | Ordres, changements, photos, impacts prix/délai, demandes de prix nouveau, avenants et réserves. | `Créer une fiche de variation`. |
| **Réception et garanties** | Réserves, DOE, PV, levées, garanties et interventions après réception. | `Préparer la réception`. |

Les fonctions de suivi d’exécution seront définies dans leur propre cahier lorsque l’espace patron pré-attribution sera validé. Elles sont néanmoins présentes ici pour que le patron voie que SMART_AO garde la continuité entre l’offre et le chantier.

---

## 16. Écran P11 — Réglages, sécurité et confiance

Le patron contrôle les paramètres sensibles de son instance. Cette page doit rester claire et ne jamais devenir un panneau technique incompréhensible.

| Rubrique | Informations et actions |
|---|---|
| **Mon compte** | Nom, e-mail, mot de passe, deuxième facteur, sessions actives et déconnexion des appareils. |
| **Notifications** | Échéances, alertes de pièces, transmissions collaborateurs, opportunités, dépôts et fréquence des e-mails. |
| **Confidentialité des DCE** | Traitement local/dédié uniquement, traitement externe autorisé ou interdit, historique des choix par affaire. |
| **Intelligence assistée** | Provider autorisé, types de documents autorisés, budget, journal des utilisations et désactivation. |
| **Accès et audit** | Invitations, comptes suspendus, export des actions sensibles et historique des validations. |
| **Support** | État de l’instance, demande de support, autorisation temporaire d’intervention et historique. |
| **Abonnement** | Informations d’offre affichées de manière commerciale, sans exposer la facturation technique au collaborateur. |

### 16.1. Boutons de sécurité

| Bouton | Effet |
|---|---|
| `Activer la double authentification` | Lance la configuration du deuxième facteur patron. |
| `Voir mes sessions actives` | Liste les appareils et permet de déconnecter une session inconnue. |
| `Créer une règle de notification` | Ouvre un formulaire de destinataire, type d’alerte, fréquence et seuil. |
| `Modifier la politique de traitement` | Demande une confirmation claire avant d’autoriser des sorties externes de données. |
| `Exporter le journal d’audit` | Produit un export de consultations, validations, téléchargements et décisions selon les droits patron. |
| `Contacter le support` | Ouvre une demande sans exposer automatiquement les documents du client. |

---

## 17. Messages de guidage obligatoires dans l’espace patron

| Situation | Message SMART_AO attendu |
|---|---|
| Premier accès | « Préparons votre entreprise. Vous pourrez compléter les éléments non urgents plus tard. » |
| Compte collaborateur créé | « L’invitation est envoyée. Cette personne ne verra que les affaires que vous lui attribuerez. » |
| Prix importé | « Ce fichier est enregistré comme référence privée. Il ne sera jamais visible par vos collaborateurs sans votre autorisation. » |
| Pièce expirante | « Ce document approche de sa date de renouvellement. Il peut bloquer une prochaine réponse s’il n’est pas mis à jour. » |
| Opportunité reçue | « Cette affaire correspond à votre profil pour les raisons suivantes : [métier, zone, taille]. » |
| DCE transmis par collaborateur | « La préparation technique est terminée. Vous devez maintenant vérifier les risques et décider du chiffrage. » |
| Risque non résolu | « Ce point reste non confirmé. Vous pouvez demander une précision, traiter le risque ou accepter son impact avant de poursuivre. » |
| Dossier de dépôt prêt | « Le dossier est complet selon les contrôles disponibles. Vérifiez une dernière fois vos engagements avant de déposer sur la plateforme de l’acheteur. » |

---

## 18. Critères de validation de l’espace patron

L’espace patron sera fonctionnellement validé lorsque les scénarios suivants pourront être rejoués sans ambiguïté :

| Scénario | Résultat attendu |
|---|---|
| Nouveau patron | Active son compte, renseigne son entreprise, crée un collaborateur et ajoute un premier document. |
| Confidentialité | Le collaborateur reçoit une affaire mais ne peut ni voir ni deviner les prix, marges, devis ou règles privées. |
| Bibliothèque | Le patron ajoute une assurance, une qualification et un fichier de prix ; SMART_AO distingue les dates, usages et droits. |
| Veille | Le patron crée deux profils de recherche et comprend pourquoi une opportunité est proposée ou écartée. |
| Affaire préparée | Le collaborateur transmet une affaire ; le patron voit les obligations, risques, documents et demandes avant de chiffrer. |
| Chiffrage | Le patron importe ses prix, compare des scénarios, valide un montant et transmet la version de prix au coffre de dépôt. |
| Dépôt | Le patron contrôle le dossier, télécharge le ZIP, importe l’accusé de réception et conserve la version déposée. |
| Marché gagné | Le patron retrouve les obligations, les étapes de démarrage, les éléments de trésorerie et les variations à suivre. |
| Sécurité | Le patron suspend un compte, consulte les actions sensibles et modifie la politique de traitement d’un DCE. |

---

## 19. Décisions à valider par le fondateur avant le cahier collaborateur

1. Les huit entrées de navigation patron sont-elles les bonnes, ou faut-il en retirer ou renommer une ?
2. Le patron doit-il pouvoir créer un second administrateur de confiance, ou rester le seul administrateur dans la première version ?
3. La page **Chiffrage privé** doit-elle apparaître directement dans le menu ou seulement lorsqu’une affaire est prête à chiffrer ?
4. Les données financières doivent-elles pouvoir être partagées à un profil « responsable administratif/financier » distinct, ou rester intégralement réservées au patron au départ ?
5. La veille doit-elle commencer uniquement par BOAMP et l’import manuel, ou faut-il prévoir dès le premier produit une seconde source définie ?
6. Le suivi complet des marchés gagnés fait-il partie du premier produit vendu, ou doit-il être affiché comme un module activé après le noyau appels d’offres ?
7. Le patron doit-il autoriser chaque envoi partenaire un par un, ou pouvoir donner des règles de partage pré-approuvées par type de demande ?

Aucune page du parcours collaborateur ne sera finalisée avant la validation de ces décisions et de l’espace patron.

---

## Références d’inspiration métier

[1] [BOAMP — Recherche d’avis](https://www.boamp.fr/pages/recherche/)  
[2] [BTPSuivi — Pilotage de rentabilité, documents et conformité BTP](https://www.btpsuivi.fr/)  
[3] [Orisha Construction — Détection, chiffrage et réponse aux appels d’offres](https://www.orisha.com/fr/construction/besoin/entreprise-btp-etude-prix-chiffrages-gestion-appel-offre)  
[4] [ConstructConnect — Bid Management](https://www.constructconnect.com/fr/products/bid-management)


---

# V8.1 — Architecture fonctionnelle transversale de l’espace patron

Cette section complète et, lorsqu’elle le précise, **remplace** certaines représentations précédentes du cahier. Elle ne change pas les écrans métier déjà décrits ; elle les organise autour d’un même fonctionnement. L’objectif est que le patron ne navigue pas entre des modules pour chercher l’information : SMART_AO lui présente d’abord ce qui exige sa décision, ce qui met une affaire en danger et ce qu’il peut déléguer ou contrôler.

> **Principe directeur V8.1 :** le patron ne pense pas en modules. Il pense : « Que dois-je décider ? Qu’est-ce qui peut me coûter ? Qu’est-ce qui bloque ? Qu’est-ce qui est prêt ? Qui attend mon retour ? »

## 20. L’Accueil devient le Patron Command Center

La page `Cockpit` est renommée **Accueil** dans la navigation. Son sous-titre fonctionnel est **Command Center**. Il ne s’agit pas d’un dashboard statistique ; c’est le briefing quotidien du patron.

L’Accueil répond toujours à quatre questions :

1. **Que se passe-t-il ?**
2. **Pourquoi est-ce important maintenant ?**
3. **Quel est l’impact possible sur une affaire, une marge, une preuve ou un droit ?**
4. **Quelle action dois-je prendre ou attribuer ?**

### 20.1. Nouvelle structure de navigation patron

La section 4 est remplacée par la structure suivante. Les entrées principales correspondent aux grands objets du métier. Le chiffrage, le dépôt et les marchés gagnés sont des espaces d’une affaire ; les réglages restent dans le menu personnel du patron.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ SMART_AO | DUPONT BÂTIMENT                                  🔔 3  [Noor ▾] │
├──────────────┬──────────────────────────────────────────────────────────────┤
│ ● Accueil    │                                                              │
│ ▤ Affaires   │                    CONTENU DE LA PAGE                         │
│ ◉ Opportunités                                                             │
│ ▦ Entreprise │                                                              │
│ ▤ Bibliothèque                                                             │
│ ♟ Équipe     │                                                              │
│              │                                                              │
│              │                                                              │
│              │                                                              │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

| Entrée principale | Question métier à laquelle elle répond | Espaces inclus |
|---|---|---|
| **Accueil** | « Que dois-je traiter aujourd’hui ? » | Actions patron, protection, échéances, santé entreprise, portefeuille prioritaire et activité récente. |
| **Affaires** | « Où en est chacune de mes affaires et qu’est-ce qui bloque ? » | Opportunité transformée en affaire, DCE, décision, réponse, chiffrage privé, dépôt, résultat, marché gagné et exécution. |
| **Opportunités** | « Quelles affaires méritent que nous investissions du temps ? » | Profils de veille, correspondances, explications, inconnus et qualification initiale. |
| **Entreprise** | « Que pouvons-nous réellement démontrer et mobiliser ? » | Identité, capacités, qualifications, implantations, règles internes et préparation progressive. |
| **Bibliothèque** | « Avons-nous les preuves et documents nécessaires ? » | Preuves, références, qualifications, assurances, modèles, partenaires et prix privés. |
| **Équipe** | « Qui travaille sur quoi et qui attend mon retour ? » | Comptes, attributions, disponibilités, travaux transmis et délégations. |
| **Menu personnel** | « Comment sécuriser et régler mon espace ? » | Mon compte, sécurité, notifications, politique de traitement DCE, audit, support et réglages. |

**Chiffrage privé** n’est plus une entrée principale autonome. Il est ouvert depuis une affaire prête à chiffrer ou depuis une action patron. Il reste toujours privé au patron.

**Réglages** ne fait plus partie des grands objets métier. Il est accessible depuis le menu `[Noor ▾]`, avec les entrées `Mon compte`, `Sécurité`, `Notifications`, `Confidentialité`, `Journal d’audit`, `Support`.

---

## 21. La file d’actions patron : une seule porte d’entrée pour les décisions et arbitrages

Le manque principal du premier cahier était l’absence d’une file commune pour les actions que seul le patron peut traiter. Cette file devient l’élément central de l’Accueil et le lien entre les affaires, les documents, les risques, les partenaires, les marchés gagnés et l’équipe.

Une **Action patron** est une demande qui ne peut pas rester sans décision. Elle possède toujours une raison, une affaire ou un élément concerné, une échéance si elle existe, un impact, des sources et une action recommandée.

### 21.1. Types d’actions patron

| Type d’action | Exemple | Décision ou action proposée |
|---|---|---|
| **Décider de répondre** | Une analyse DCE est terminée. | Répondre, répondre sous conditions, ne pas répondre. |
| **Valider un prix** | Le collaborateur a transmis le dossier et le chiffrage est prêt. | Ouvrir le chiffrage, valider, retourner une correction ou arrêter. |
| **Valider une variante ou PSE** | Une variante est autorisée ou une PSE doit être chiffrée. | Retenir, écarter ou demander une analyse complémentaire. |
| **Valider un partenaire** | Un sous-traitant ou cotraitant est proposé. | Accepter sous réserve, demander une pièce ou refuser. |
| **Arbitrer un risque** | Document manquant, clause pénale, plan contradictoire ou information inconnue. | Réduire, accepter, demander une précision, transférer ou arrêter. |
| **Valider un engagement** | Une promesse du mémoire engage une équipe, une méthode, un délai, un coût ou une preuve future. | Valider, corriger ou retirer l’engagement. |
| **Contrôler le dépôt** | L’offre est prête au contrôle final. | Ouvrir le coffre, traiter les blocages et préparer le dépôt. |
| **Renouveler une preuve** | Assurance, qualification ou attestation arrive à échéance. | Créer la tâche, remplacer le document ou marquer non applicable. |
| **Répondre à une question ou à un rectificatif** | L’acheteur modifie le DCE ou répond à une question. | Ouvrir les impacts, réattribuer une revue et valider les changements. |
| **Valider une situation de trésorerie** | Une avance, retenue, paiement ou tension concerne une affaire. | Ouvrir les données privées et décider de l’action à mener. |
| **Protéger les droits du marché gagné** | Ordre verbal, variation, réserve ou facture non réglée. | Créer une fiche factuelle, préparer un courrier ou consulter un conseil. |

### 21.2. Structure commune d’une action patron

| Élément visible | Exemple |
|---|---|
| Intitulé clair | « Valider le Go / No-Go — Centre médical Guesnain, Lot 01 ». |
| Niveau de traitement | Urgent, bloquant, à risque ou à surveiller. |
| Pourquoi maintenant | « Date limite de dépôt dans 36 heures ». |
| Affaire / élément concerné | Lien vers l’affaire, le document, le partenaire ou le marché gagné. |
| Impact possible | « Offre impossible à déposer », « prix non couvert », « qualification à confirmer ». |
| Éléments connus | Ce qui est confirmé et sourcé. |
| Inconnus et points à vérifier | Ce qui ne doit pas être traité comme une certitude. |
| Recommandation | Action proposée par SMART_AO, jamais décision imposée. |
| Responsable actuel | Patron, collaborateur, partenaire ou tiers chargé de la prochaine étape. |
| Échéance | Date de dépôt, visite, retour fournisseur, expiration ou date définie par le patron. |
| Sources | RC, CCAP, CCTP, DPGF, document d’entreprise, devis ou constat terrain. |

### 21.3. Actions versus notifications

Une **notification** informe. Elle peut être lue, effacée ou regroupée. Une **Action patron** ne disparaît pas parce qu’une notification a été lue.

| Élément | Rôle | Exemple |
|---|---|---|
| Notification | Information ponctuelle. | « Karim a ajouté un nouveau document. » |
| Action patron | Travail ou décision encore à traiter. | « Valider si ce document permet de répondre au RC. » |
| Tâche collaborateur | Travail confié à une personne. | « Vérifier la date de l’assurance. » |
| Alerte | Signal de risque ou d’échéance. | « Attestation expire dans 30 jours. » |

Une action patron n’est clôturée que par une décision, une réalisation vérifiable, une délégation enregistrée ou un abandon motivé. L’Accueil doit empêcher les doublons : deux alertes provenant de la même cause doivent nourrir une même action plutôt que créer deux décisions concurrentes.

---

## 22. Urgence, gravité et protection : ne pas mélanger les dangers

Une assurance qui expire dans quarante-cinq jours et un dépôt dans douze heures ne demandent pas le même traitement. De même, une clause pouvant détruire une marge doit rester visible même si son échéance est éloignée.

SMART_AO classe les éléments à protéger avec quatre états lisibles ; il ne montre jamais une formule de score opaque.

| État affiché | Signification | Exemple |
|---|---|---|
| **URGENT** | Action à prendre immédiatement à cause d’une échéance proche. | Dépôt demain à 12 h, visite dans 24 h, question à envoyer avant ce soir. |
| **BLOQUANT** | L’affaire ne peut pas passer au stade suivant sans traitement. | Attestation obligatoire absente, DPGF non remplie, validation patron manquante. |
| **À RISQUE** | Impact potentiellement important sur marge, délai, conformité ou droit. | Pénalité élevée, devis fournisseur en attente, variation non documentée. |
| **À SURVEILLER** | Élément non urgent mais à suivre avant qu’il ne devienne critique. | Qualification à renouveler dans deux mois, capacité équipe tendue en septembre. |

La zone **Protéger** de l’Accueil regroupe les éléments selon quatre familles, toujours visibles dans le même ordre :

| Famille de protection | Ce qui y apparaît |
|---|---|
| **Délais** | Visites, questions, dépôts, jalons, réponses attendues, renouvellements et échéances de marché. |
| **Preuves** | Documents manquants, expirés, à vérifier, références non validées et qualifications inadaptées. |
| **Marge** | Prestations non couvertes, devis en attente, pénalités, hypothèses fragiles, hausse de coût et scénarios de trésorerie. |
| **Droits** | Variations, ordres, réserves, avenants, factures contestées, preuves de dépôt et chronologies à conserver. |

---

## 23. Nouvelle maquette de l’Accueil / Command Center

La section 5 est enrichie par la présentation suivante. Les chiffres affichés sont des comptes d’actions ou d’éléments explicables, jamais un score de rentabilité ou de fiabilité présenté comme une vérité.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Bonjour Noor                                                                 │
│ 7 actions ou décisions nécessitent votre attention.                          │
│ [Traiter mes actions]                                      [Créer une affaire]│
├─────────────────────────────────────────────────────────────────────────────┤
│ URGENT                                                                      │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Centre médical Guesnain — dépôt demain 12:00                            │ │
│ │ 2 éléments bloquants · 1 décision patron · Karim prépare le dossier     │ │
│ │ [Ouvrir le contrôle final]                                               │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ À DÉCIDER                         À SURVEILLER                              │
│ • Go/No-Go — École Douai          • Assurance expire dans 31 jours          │
│ • Variante — Mairie Lens          • 2 pièces partenaires attendues          │
│ • Prix fournisseur — Guesnain     [Voir les éléments à surveiller]          │
│ [Voir toutes mes décisions]                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ PROTÉGER : [Délais 2] [Preuves 3] [Marge 2] [Droits 0]                       │
│ [Ouvrir la protection]                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ PORTEFEUILLE PRIORITAIRE                 SANTÉ DE L’ENTREPRISE               │
│ 4 affaires avancent normalement           Documents : 2 à renouveler         │
│ 2 affaires attendent votre décision       Équipe : surcharge septembre        │
│ [Ouvrir mes affaires]                     [Voir ce qu’il faut préparer]     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 23.1. Le bouton `Traiter mes actions`

Ce bouton ouvre une liste de travail patron unique. Chaque ligne montre l’essentiel ; le patron ouvre une ligne seulement lorsqu’il souhaite prendre la décision.

| Colonne | Contenu |
|---|---|
| État | Urgent, bloquant, à risque ou à surveiller. |
| Action | Libellé métier, par exemple « Valider le prix ». |
| Affaire | Nom, lot et acheteur lorsqu’ils sont concernés. |
| Pourquoi | Motif court et explicable. |
| Échéance | Date et heure si elles existent. |
| Impact | Dépôt, marge, preuve, droit, capacité ou trésorerie. |
| Action suivante | Ouvrir la décision, réattribuer, demander une pièce ou reporter avec motif. |

Le patron peut filtrer la file par affaire, type d’action, responsable, échéance et famille de protection. Il ne peut pas masquer définitivement une action sans décision ou justification.

---

## 24. Le Dossier de décision : un format unique pour tous les choix patron

Chaque décision importante doit s’ouvrir dans une même fenêtre fonctionnelle. Ainsi, le patron n’a pas à réapprendre un écran pour répondre à une affaire, accepter une variante, valider un prix ou arbitrer un risque.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ DÉCISION — RÉPONDRE OU NE PAS RÉPONDRE                                      │
│ Centre médical Guesnain — Lot 01 · Décision attendue avant 15/09             │
├─────────────────────────────────────────────────────────────────────────────┤
│ CE QUE NOUS SAVONS                   CE QUI EST ENCORE INCONNU               │
│ ✓ Qualification disponible           ? Complément diagnostic amiante         │
│ ✓ Référence comparable               ? Prix final fournisseur                 │
│ ✓ Équipe à confirmer                 ? Planning de coactivité                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ RISQUES                              CONDITIONS À SÉCURISER                  │
│ 🔴 Pénalité 200 €/jour               • Obtenir le prix fournisseur            │
│ 🟠 Délai global 11 mois              • Confirmer le traitement amiante         │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCES : RC p. 8 · CCAP art. 8 · CCTP Lot 01 p. 44                          │
│ [Répondre] [Répondre sous conditions] [Ne pas répondre]                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 24.1. Blocs obligatoires du Dossier de décision

| Bloc | Contenu | Règle |
|---|---|---|
| Ce que nous savons | Informations confirmées avec source. | Aucun élément déduit sans mention ne doit y entrer. |
| Ce qui est inconnu | Informations absentes, contradictoires ou à confirmer. | Un inconnu n’est jamais masqué par un score. |
| Risques | Délais, marge, pénalités, capacités, preuves, droits ou trésorerie. | Chaque risque indique son impact et son état. |
| Conditions à sécuriser | Actions nécessaires avant de poursuivre sous conditions. | Chaque condition possède un responsable et une date cible. |
| Sources | Documents et passages d’origine. | L’utilisateur peut ouvrir la source depuis la décision. |
| Choix patron | Options de décision adaptées au contexte. | Toute décision est datée, attribuée et réversible seulement avec traçabilité. |

### 24.2. Choix proposés selon le type de décision

| Décision | Choix standards |
|---|---|
| Go / No-Go | `Répondre`, `Répondre sous conditions`, `Ne pas répondre`. |
| Prix | `Valider le prix`, `Revenir au chiffrage`, `Demander une correction`, `Arrêter`. |
| Variante | `Retenir`, `Écarter`, `Étudier davantage`. |
| Partenaire | `Accepter`, `Accepter sous réserve`, `Demander une pièce`, `Refuser`. |
| Risque | `Réduire`, `Demander une précision`, `Accepter avec motif`, `Transférer`, `Arrêter`. |
| Dépôt | `Valider le dossier`, `Retourner au dossier`, `Créer une nouvelle version`. |

---

## 25. La Vue de direction de l’affaire : comprendre une affaire en dix secondes

La page « Résumé patron d’une affaire » devient la **Vue de direction de l’affaire**. Elle doit montrer une situation avant de donner accès aux détails techniques.

### 25.1. En-tête de la vue

```text
CENTRE MÉDICAL GUESNAIN — LOT 01
État : PRÊTE À CHIFFRER       Dépôt : 18/09/2026 à 12:00       Responsable : Karim

PROCHAINE ACTION PATRON : Finaliser le chiffrage privé
[Ouvrir le chiffrage] [Voir la décision] [Voir les risques]
```

### 25.2. Carte de confiance décisionnelle

Cette carte remplace l’indicateur linéaire `Étape 7/11`. Une affaire réelle est conditionnelle : une seule pièce éliminatoire peut bloquer le dépôt, tandis que certaines étapes ne sont pas applicables. SMART_AO doit donc afficher les éléments qui permettent de décider, sans fabriquer un score global opaque.

| Axe de décision | Forme d’affichage | Exemple |
|---|---|---|
| **Exigences** | Couvertes / à traiter / inconnues. | « 34 exigences couvertes · 2 à traiter ». |
| **Capacités** | Confirmées / à confirmer / non couvertes. | « Équipe : 1 capacité à confirmer ». |
| **Preuves** | Prêtes / à vérifier / manquantes. | « 12 preuves prêtes · 1 document manquant ». |
| **Risques** | Ouverts par gravité et famille. | « 3 risques ouverts, dont 1 sur la marge ». |
| **Inconnus** | Nombre et importance des données non confirmées. | « 2 inconnus : diagnostic et coactivité ». |
| **Décision actuelle** | Non décidée / Go / Go sous conditions / No-Go / Prix validé / Prête à déposer. | « Go sous conditions ». |

### 25.3. Zones visibles avant les détails

| Zone | Question à laquelle elle répond |
|---|---|
| Décision actuelle | « Quelle est la position du patron ? » |
| Prochaine action | « Que dois-je faire maintenant ? » |
| Risques prioritaires | « Qu’est-ce qui peut coûter, bloquer ou engager l’entreprise ? » |
| Preuves et inconnus | « Que pouvons-nous démontrer et qu’est-ce qui manque ? » |
| Équipe | « Qui travaille, qui attend un retour, qui doit intervenir ? » |
| Échéances | « Qu’est-ce qui arrive dans les prochaines heures ou prochains jours ? » |
| Derniers changements | « Qu’est-ce qui a changé depuis ma dernière consultation ? » |

Les détails restent accessibles sous les onglets `Analyse DCE`, `Obligations`, `Documents`, `Risques`, `Questions`, `Chiffrage privé`, `Dépôt`, `Journal de vérité`.

---

## 26. Santé de l’entreprise : une préparation expliquée, jamais un score magique

La santé de l’entreprise n’est pas une note globale. Elle permet au patron de voir ce qui est prêt, ce qui est fragile et ce qui limitera sa capacité à répondre.

| Domaine | Affichage recommandé | Exemple d’action |
|---|---|---|
| Documents administratifs | Prêt / pièces à renouveler / pièces inconnues. | `Mettre à jour une pièce`. |
| Qualifications et assurances | Couverture connue par activité ; alertes d’expiration. | `Vérifier le périmètre`. |
| Références et preuves | Métiers suffisamment documentés ou pauvres en preuves. | `Ajouter une référence`. |
| Partenaires | Pièces et capacités confirmées ou à demander. | `Demander une attestation`. |
| Équipe et capacité | Charge prévue, périodes tendues et compétences manquantes. | `Revoir la disponibilité`. |
| Prix privés | Fichiers récents, métiers couverts et éléments à mettre à jour. | `Ajouter une nouvelle version`. |
| Veille | Profils actifs, zones et critères suffisants. | `Créer ou corriger un profil`. |

La page peut afficher un état qualitatif par domaine : **Prêt**, **À vérifier**, **À renforcer** ou **Non renseigné**. Elle ne doit pas produire un « 92/100 » sans expliquer les causes.

---

## 27. Timeline entreprise et Journal de vérité

### 27.1. Timeline de pilotage

Le patron doit pouvoir voir ce qui arrive dans le temps sans entrer dans chaque affaire. Une vue `Aujourd’hui / 7 jours / 30 jours / 90 jours` présente exclusivement les événements utiles : dépôt, visite, décision, retour partenaire, renouvellement, paiement, jalon d’exécution et engagement critique.

| Horizon | Exemple de contenu |
|---|---|
| **Aujourd’hui** | Décision Go/No-Go, réponse à question, prix fournisseur attendu, action de dépôt. |
| **7 jours** | Visites, dépôts, rectificatifs, expéditions de documents, validations de partenaire. |
| **30 jours** | Renouvellements, démarrage de marché, avance, situation, échéance de garantie ou capacité saturée. |
| **90 jours** | Charge prévisionnelle, échéances d’assurance, marchés à démarrer, périodes de trésorerie tendue. |

### 27.2. Journal de vérité d’une affaire

Chaque affaire possède une chronologie commune. Elle ne remplace pas les documents ; elle permet de comprendre ce qui est arrivé, dans quel ordre et avec quelle conséquence.

```text
12 septembre — DCE version 1 reçu
13 septembre — Visite obligatoire détectée depuis le RC
14 septembre — Visite confirmée par Salma
15 septembre — Go sous conditions validé par Noor
16 septembre — Rectificatif reçu ; 2 exigences à revoir
17 septembre — Prix révisé et validé
18 septembre 11:42 — Dépôt confirmé ; accusé de réception archivé
```

| Élément journalisé | Exemples |
|---|---|
| Documents et versions | DCE reçu, rectificatif, nouveau modèle DPGF, attestation remplacée. |
| Décisions | Go/No-Go, prix, variante, partenaire, risque accepté ou refusé. |
| Validations | Patron, collaborateur, responsable technique ou tiers. |
| Actions | Tâche attribuée, question préparée, demande fournisseur envoyée, document ajouté. |
| Événements de dépôt | Dossier final créé, accusé de réception ajouté, nouvelle version ouverte. |
| Événements de marché gagné | Ordre de service, variation, réserve, situation et paiement. |

Le Journal de vérité conserve la source, l’auteur, le moment et la version. Il n’interprète pas seul un droit juridique ; il garde les faits utiles pour la décision du patron ou d’un conseil.

---

## 28. Une affaire garde la même identité du premier signal à la fin du marché

La section 11 est complétée par une règle de continuité : une affaire ne change jamais d’identité parce qu’elle passe d’une opportunité à un DCE, puis à une offre déposée, puis à un marché gagné. Le patron retrouve toujours son historique au même endroit.

```text
OPPORTUNITÉ → QUALIFICATION → ANALYSE DCE → DÉCISION → PRÉPARATION
      → CHIFFRAGE → CONTRÔLE FINAL → DÉPÔT → RÉSULTAT → MARCHÉ GAGNÉ
      → EXÉCUTION → TERMINÉE
```

| État de l’affaire | Vue patron attendue |
|---|---|
| Opportunité | Correspondance, pourquoi, inconnus, première action. |
| Qualification | Compatibilité métier, zone, capacité, visite et éléments à obtenir. |
| Analyse DCE | Obligations, critères, risques, documents, questions et responsable. |
| Décision | Dossier de décision et conditions à sécuriser. |
| Préparation | Avancement réel des pièces, preuves, mémoire, partenaires et tâches. |
| Chiffrage | Espace privé : prix, coûts, scénarios, marge, trésorerie et contrôles. |
| Dépôt | Coffre, version, validations, ZIP et accusé de réception. |
| Résultat | Gagnée, perdue, sans suite ou à analyser. |
| Marché gagné | Protection : obligations, marge, trésorerie, variations, preuves et réserves. |
| Terminée | Réception, garanties, leçons, références et archivage. |

---

## 29. Onboarding patron progressif : préparer juste ce qui sert maintenant

Les sections P01 à P06 ne doivent pas être imposées comme un long tunnel initial. Le patron peut commencer à travailler après un minimum utile ; SMART_AO demande le reste au moment où l’information devient nécessaire.

| Moment | Informations demandées | Pourquoi maintenant |
|---|---|---|
| **Jour 0** | Identité minimale, premier métier, première implantation ou zone. | Permettre de créer l’entreprise et de qualifier une première affaire. |
| **Première opportunité** | Critères de veille, zone, taille d’affaire et exclusions. | Éviter de proposer des avis inutiles. |
| **Première analyse DCE** | Qualifications, équipe, capacités ou documents seulement lorsqu’ils sont demandés. | Ne pas remplir une bibliothèque abstraite. |
| **Première réponse technique** | Références, méthodes, matériels et preuves comparables. | Alimente un mémoire réellement spécifique. |
| **Premier chiffrage** | Fichiers de prix, fournisseurs, règles et hypothèses privées. | Évite d’imposer des données financières avant leur besoin réel. |
| **Premier partenaire** | Profil, documents et règles de partage. | Prépare une demande limitée et sécurisée. |
| **Premier marché gagné** | Contacts opérationnels, obligations, trésorerie et suivi d’exécution. | Protège le démarrage sans surcharger la phase appel d’offres. |

Une page `Préparer mon entreprise` reste disponible à tout moment, avec les éléments `Prêt`, `À compléter plus tard`, `À vérifier` et `Non applicable`. Elle remplace toute obligation d’achever un long wizard avant de travailler.

---

## 30. Chiffrage privé : résultat, explication, détail et scénarios

La section 13 est enrichie par trois niveaux de lecture, afin que le patron ne soit pas confronté à un tableur complexe dès l’ouverture.

| Niveau | Ce que le patron voit | Exemple |
|---|---|---|
| **1. Résultat** | Prix actuel, marge estimée, état de confiance et problèmes majeurs. | « Prix actuel : 428 500 € · 2 obligations non couvertes ». |
| **2. Explication** | Sources de coût, risques, devis, hypothèses et impacts sur prix/marge. | « Le devis fournisseur X expire demain ; le poste Y est non couvert ». |
| **3. Détail** | DPGF/BPU/DQE, postes, unités, formules, fournisseurs, coûts, trésorerie et versions. | Tableaux de calcul, fichiers Excel et rapprochements validés. |

Les scénarios sont natifs. Un scénario est une copie de travail privée qui ne modifie jamais l’offre officielle tant que le patron ne choisit pas de retenir sa version.

| Scénario exemple | Hypothèse modifiée | Résultat comparé |
|---|---|---|
| Base | Hypothèses actuelles. | Prix, coût, marge, trésorerie et risques. |
| Prudent | Provision ou coût fournisseur plus élevé. | Impact sur marge et besoin de trésorerie. |
| Délai +15 jours | Risque de délai ou de coactivité. | Impact de coût, pénalité potentielle et marge. |
| Fournisseur +8 % | Augmentation du devis d’un fournisseur. | Postes affectés, nouveau prix ou marge. |
| Pénalité | Hypothèse de retard ou d’exposition contractuelle. | Impact maximal et décision de protection. |

---

## 31. Les sept écrans patron fondamentaux

Le cahier conserve les écrans détaillés existants, mais la construction doit commencer par les sept vues qui portent le plus de valeur métier. Les autres vues se grefferont dessus sans changer la logique.

| Priorité | Écran | Question patron principale |
|---:|---|---|
| 1 | **Accueil / Command Center** | « Qu’est-ce qui demande mon attention maintenant ? » |
| 2 | **Vue de direction de l’affaire** | « Où en est cette affaire, qu’est-ce qui bloque et quelle est ma prochaine action ? » |
| 3 | **Dossier de décision** | « Que savons-nous, que manque-t-il, quels risques est-ce que j’accepte ? » |
| 4 | **Entreprise** | « Que pouvons-nous réellement démontrer et mobiliser ? » |
| 5 | **Bibliothèque / Passeport entreprise** | « Avons-nous les preuves, documents et autorisations nécessaires ? » |
| 6 | **Opportunités** | « Pourquoi cette affaire nous est proposée et vaut-elle notre temps ? » |
| 7 | **Chiffrage privé** | « Est-ce que mon prix couvre réellement ce que je promets ? » |

Le **Cockpit de protection du marché gagné** est un espace d’affaire activé au moment de l’attribution. Il sera détaillé après le cahier du parcours DCE ; son rôle est déjà fixé dans les sections 15 et 28.

---

## 32. Règles de conception à transmettre plus tard à la documentation technique

Les règles suivantes sont inscrites ici parce qu’elles protègent l’expérience métier. Leur traduction technique détaillée appartient au futur contrat de domaine et au cahier d’architecture, pas à ce document d’écrans.

1. L’Accueil reçoit une vue patron déjà cohérente ; l’interface ne doit pas reconstruire la logique métier à partir de multiples listes hétérogènes.
2. Chaque vue agrégée correspond à une question métier : Accueil, Vue de direction de l’affaire, Santé entreprise, Opportunités ou Protection du marché gagné.
3. Les données patron et collaborateur sont construites pour des droits différents dès leur production côté serveur ; les données privées ne sont pas envoyées puis cachées dans l’interface.
4. Toute action patron est créée, mise à jour et clôturée selon une même règle ; elle apparaît de la même manière dans l’Accueil, une affaire, la bibliothèque ou le marché gagné.
5. Toute décision importante garde son contexte, ses sources, sa personne validatrice, sa date et la version des éléments considérés.
6. Les vues de l’interface ne doivent jamais dépendre directement de la forme des tables ou fichiers internes. Elles présentent une situation métier stable, même si l’organisation technique évolue.

---

## 33. Nouvelles conditions de validation du cahier patron V8.1

Avant de passer au cahier collaborateur, le fondateur doit confirmer que les règles suivantes représentent bien le logiciel qu’il veut vendre :

1. **L’Accueil commence par les actions du patron, non par des statistiques.**
2. **Une Action patron unique rassemble toutes les décisions et arbitrages qui lui sont réservés.**
3. **Urgence, blocage, risque et surveillance sont distingués.**
4. **Toutes les décisions importantes suivent un Dossier de décision standard.**
5. **Une affaire conserve son identité de l’opportunité à la clôture du marché.**
6. **La Vue de direction de l’affaire remplace la progression linéaire en étapes.**
7. **La santé entreprise explique chaque fragilité sans score global opaque.**
8. **La bibliothèque est une bibliothèque de preuves et de capacités, avec les usages et autorisations associés.**
9. **L’onboarding est progressif : l’information est demandée au moment où elle devient utile.**
10. **Le chiffrage est un espace privé intégré à une affaire, avec scénarios séparés de l’offre officielle.**
11. **Le Journal de vérité assure la chronologie des sources, versions, décisions, validations et dépôts.**

Ces règles prennent le dessus sur les formulations antérieures lorsqu’elles diffèrent.


---

# V8.2 — Durcissement final du cahier patron

Cette passe finale ne crée pas de nouveaux modules. Elle élimine les derniers doublons et verrouille les règles qui permettront à SMART_AO de rester cohérent lorsque les écrans, les analyses DCE, le chiffrage et les marchés gagnés seront développés.

## 34. Arbitrages définitifs de navigation et de concepts

| Sujet | Règle V8.2 | Conséquence visible pour le patron |
|---|---|---|
| Accueil | L’Accueil / Command Center est le point de départ. | Le patron commence toujours par ses actions, protections et échéances. |
| Quatre cartes initiales | `À décider`, `À chiffrer`, `À déposer`, `À protéger` ne sont plus quatre systèmes séparés. | Elles deviennent des filtres de la même file d’Actions patron. |
| Chiffrage privé | C’est un espace d’une affaire. | Le patron ouvre `Affaire X → Prix`, jamais un chiffrage déconnecté de son DCE. |
| Marché gagné | C’est un état puis une vue de l’affaire. | Toute l’histoire de l’offre reste à portée de main après attribution. |
| Entreprise | L’entrée est renommée **Entreprise & capacités**. | Le patron voit d’abord ce que l’entreprise peut mobiliser et prouver ; l’identité juridique est une sous-partie. |
| Réglages | Restent dans le menu personnel. | La navigation métier n’est pas polluée par des paramètres techniques. |
| Sept écrans fondamentaux | Les six surfaces fondamentales sont : Accueil, Affaire, Entreprise & capacités, Bibliothèque, Opportunités, Chiffrage privé. | L’Équipe est une vue de l’entreprise ; le Marché gagné est une vue de l’affaire. |

## 35. Action patron, risque et protection : trois choses distinctes

Ces notions sont liées mais ne doivent pas être confondues.

```text
Constat ou risque détecté
        ↓
Élément à protéger
        ↓
Action ou décision réservée au patron
```

| Notion | Définition métier | Exemple |
|---|---|---|
| **Risque** | Ce qui peut affecter le prix, le délai, la conformité, la preuve ou les droits de l’entreprise. | Pénalité de 200 € par jour ou plan contradictoire. |
| **Élément à protéger** | Ce que l’entreprise doit sécuriser pour réduire le risque. | Confirmer le délai, poser une question, renforcer une preuve ou couvrir une prestation. |
| **Action patron** | L’arbitrage ou la validation que le patron doit faire après avoir reçu les faits et options. | Accepter l’exposition, répondre sous conditions ou arrêter l’affaire. |

Un risque ne devient pas automatiquement une action patron. S’il peut être traité par un collaborateur ou un partenaire, SMART_AO crée d’abord une tâche ou une demande. Le patron ne reçoit une action que lorsqu’une décision, un arbitrage, un engagement ou une validation lui revient.

## 36. Le Dossier de décision est un contexte de décision figé

Le terme visible pour le patron reste **Dossier de décision**, car il est simple et métier. Il possède cependant une propriété non négociable : lorsqu’une décision est prise, SMART_AO conserve le contexte qui a permis de la prendre.

| Élément conservé avec une décision | Exemples |
|---|---|
| État de l’affaire | Lot, date, phase de l’affaire et personnes impliquées. |
| Informations confirmées | Exigences, capacités, preuves et données ayant été contrôlées. |
| Inconnus et contradictions | Pièce absente, réponse attendue, conflit entre documents, hypothèse non vérifiée. |
| Risques et protections | Exposition, impact, conditions demandées et mesures retenues. |
| Prix ou scénario considéré | Version de prix et hypothèses privées utilisées lorsque la décision porte sur le chiffrage. |
| Sources | Documents, pages, pièces d’entreprise, devis ou constats associés. |
| Décision humaine | Choix, validateur, date, motif et éventuelles conditions. |

Le patron doit pouvoir revenir des mois plus tard et comprendre : **« Avec les informations disponibles ce jour-là, pourquoi ai-je pris cette décision ? »**

## 37. États transverses de toute information importante

Le mot « inconnu » est insuffisant. Toute information importante — document, qualification, capacité, prix, donnée DCE, référence, partenaire ou exigence — utilise un état explicable.

| État affiché | Signification |
|---|---|
| **Confirmé** | Une source ou une validation humaine permet de l’utiliser avec le périmètre connu. |
| **À vérifier** | L’information existe, mais son usage pour l’affaire ou son périmètre doit être confirmé. |
| **Manquant** | L’information ou la pièce demandée n’a pas été trouvée ou fournie. |
| **Contradictoire** | Deux sources ou déclarations se contredisent. |
| **Expiré** | La date connue ne permet plus de le présenter comme valable. |
| **Non applicable** | L’élément ne concerne pas cette affaire ; le motif doit être enregistré lorsque l’exclusion est importante. |

L’état est toujours accompagné d’une raison et, lorsque possible, d’une action : ouvrir la source, demander une pièce, confirmer le périmètre, résoudre la contradiction, remplacer ou justifier la non-applicabilité.

## 38. Distinction entre action requise et action recommandée

SMART_AO doit aider sans transformer toutes ses suggestions en obligations.

| Type | Sens | Exemple |
|---|---|---|
| **Action requise** | Élément exigé par le DCE, une décision du patron ou un blocage de sécurité. | « Obtenir l’attestation de visite exigée avant dépôt. » |
| **Action recommandée** | Suggestion de SMART_AO basée sur un risque, une pratique ou une opportunité d’amélioration. | « Appeler le fournisseur avant 16 h pour réduire le risque prix. » |
| **Information** | Élément utile qui ne demande pas de travail immédiat. | « Karim a ajouté une référence comparable. » |

Cette distinction doit être visible par une étiquette textuelle. Une recommandation ne peut jamais bloquer seule une affaire ; une action requise peut bloquer un passage si son absence rend le dossier non conforme ou la décision non validée.

## 39. Vue de direction : synthèse d’abord, travail détaillé ensuite

La Vue de direction de l’affaire est une synthèse. Elle ne doit jamais devenir un deuxième écran d’analyse DCE ni un tableau de travail concurrent.

```text
AFFAIRE
├── Vue de direction : situation, décision, risques, preuves, équipe, prochaine action
├── Analyse DCE : pièces, obligations, critères, constats et sources
├── Préparation : tâches, documents, mémoire, partenaires et questions
├── Prix privé : chiffrage, scénarios, marge, trésorerie et contrôles
├── Dépôt : contrôle final, version et accusé de réception
├── Exécution : activée uniquement après marché gagné
└── Journal de vérité : chronologie métier commune
```

La Vue de direction ne donne donc pas accès directement à tous les champs. Elle indique la bonne porte d’entrée : `Ouvrir l’analyse`, `Traiter les preuves`, `Ouvrir le prix privé`, `Voir les risques`, `Préparer le dépôt` ou `Consulter le journal`.

## 40. Entreprise & capacités : le passeport opérationnel

L’entrée **Entreprise** est renommée **Entreprise & capacités**. L’identité juridique reste nécessaire, mais l’écran doit surtout répondre à la question : **« Qu’est-ce que mon entreprise peut réellement mobiliser et prouver pour une affaire ? »**

| Sous-partie | Rôle métier |
|---|---|
| Identité et signataires | Identifier l’entreprise qui répond et les personnes habilitées. |
| Implantations et zones | Comprendre d’où l’entreprise peut intervenir et calculer une faisabilité logistique. |
| Capacités | Métiers, équipes, matériels, charge et disponibilités. |
| Qualifications et assurances | Vérifier ce que l’entreprise peut légalement ou contractuellement prouver. |
| Références et savoir-faire | Sélectionner des travaux réellement comparables et réutilisables. |
| Partenaires | Vérifier les compétences complémentaires et les documents attendus. |
| Règles patron | Définir les limites internes de capacité, de décision et de chiffrage. |
| Préparation entreprise | Faire apparaître les éléments prêts, à vérifier, à renforcer ou non applicables. |

### 40.1. Relation exigence → capacité → preuve

La bibliothèque ne doit pas être un coffre-fort de fichiers. Pour chaque exigence importante d’une affaire, SMART_AO doit permettre au patron de voir si l’entreprise a une capacité et une preuve correspondantes.

| Exigence du DCE | Capacité de l’entreprise | Preuve disponible | État possible |
|---|---|---|---|
| Cinq chantiers comparables | Trois références directement comparables ; deux partielles. | Fiches de référence, attestations, photos autorisées. | Capacité partielle à arbitrer. |
| Qualification spécifique | Qualification détenue dans le passeport entreprise. | Certificat, date et périmètre. | Confirmé, à vérifier ou expiré. |
| Équipe dédiée | Chef de chantier et équipe déclarés disponibles. | CV, organigramme, planning interne ou confirmation. | À confirmer pour cette période. |
| Matériel imposé | Matériel détenu, louable ou couvert par partenaire. | Inventaire, devis de location ou confirmation fournisseur. | Confirmé ou manquant. |

La capacité n’est pas une affirmation générale. Elle est toujours examinée **pour l’affaire concernée**, avec sa période, son lot, son site et ses contraintes.

## 41. Fiabilité du chiffrage : une lecture factuelle, pas un score de confiance

La section 30 est complétée par la règle suivante : le chiffrage n’affiche jamais un vague « état de confiance » ou un pourcentage de probabilité. Il affiche une **fiabilité du chiffrage** fondée sur des éléments vérifiables.

| Élément affiché | Exemple |
|---|---|
| Postes contrôlés | « 94 % des postes ont une source de prix ou un coût validé. » |
| Postes non couverts | « 2 prestations du DCE ne sont pas encore reliées au prix. » |
| Devis en attente | « 2 devis fournisseurs n’ont pas été reçus. » |
| Hypothèses à confirmer | « Rendement de démolition à confirmer après visite. » |
| Contradictions | « Quantité DPGF et plan à rapprocher. » |
| Prix officiel | « Aucun prix officiel n’est modifié tant que le patron ne valide pas une version. » |

La fiabilité est donc l’explication de ce qui est solide et de ce qui reste fragile. Elle ne prétend jamais prédire que le montant choisi garantira une marge ou une rentabilité.

## 42. Journal de vérité : uniquement des faits métier

Le Journal de vérité est le socle historique de l’affaire, mais il ne doit pas devenir un journal de diagnostic informatique.

| À afficher | À ne pas afficher au patron |
|---|---|
| DCE reçu, rectificatif, pièce remplacée, décision prise, prix validé, partenaire confirmé, dépôt effectué, paiement reçu. | Requêtes techniques, cache, tentatives internes, redémarrage de service, journal de traitement ou erreurs de worker. |
| Auteur, source, version, moment et conséquence métier. | Détails d’infrastructure sans intérêt pour une décision BTP. |

Les événements techniques nécessaires au support sont conservés dans les outils d’exploitation, séparés de l’expérience utilisateur.

## 43. Garantie d’intégrité des scénarios de prix

Cette règle devient un invariant du produit :

> **Un scénario privé ne modifie jamais silencieusement le prix officiel d’une offre.**

Chaque scénario affiche un nom, sa date, son auteur, les hypothèses modifiées et ses effets sur coût, marge, trésorerie, risques et prix. Pour qu’un scénario devienne la version officielle proposée dans le DPGF/BPU/AE, le patron doit choisir explicitement `Retenir ce scénario pour préparer la version de prix` puis valider la version obtenue dans le coffre de dépôt.

## 44. Règle finale de frontière métier / technique

Le cahier patron décrit exclusivement le comportement observable : informations visibles, actions possibles, décisions, validations, états, sources et erreurs compréhensibles par le patron.

Il ne doit jamais contenir de noms de classes, tables, files d’attente, adresses techniques, commandes, points d’API ou choix de bibliothèques. La future documentation de domaine traduira séparément les concepts métier suivants : Action patron, Dossier de décision, Affaire, preuve, capacité, risque, protection, version et journal de vérité.

## 45. Cahier patron V8.2 — conditions de gel

L’espace patron est prêt à être considéré comme fonctionnellement figé lorsque le fondateur valide les règles suivantes :

1. L’Accueil est un Command Center orienté vers les actions, protections et échéances.
2. Les anciennes quatre cartes sont uniquement des filtres de la file d’Actions patron.
3. Risque, protection et action patron sont trois concepts distincts et reliés.
4. Le Dossier de décision conserve le contexte réel dans lequel le patron décide.
5. Toute information importante utilise un état explicite : confirmé, à vérifier, manquant, contradictoire, expiré ou non applicable.
6. Les actions requises, les actions recommandées et les informations sont distinguées.
7. L’Affaire conserve son identité de l’opportunité à la clôture ; la Vue de direction reste une synthèse, les autres vues réalisent le travail détaillé.
8. Entreprise & capacités devient le passeport opérationnel de l’entreprise, relié aux exigences et preuves de chaque affaire.
9. Le chiffrage est privé, lié à une affaire, présenté par résultat/explication/détail et protégé par des scénarios non destructifs.
10. Le Journal de vérité ne contient que des faits métier utiles à la compréhension de l’affaire.
11. Les règles de ce cahier seront traduites dans un futur contrat `Métier → Interface`, puis dans un contrat de domaine et d’architecture, sans mélanger les niveaux.

Ces règles V8.2 remplacent toute formulation antérieure contraire dans le cahier patron.
