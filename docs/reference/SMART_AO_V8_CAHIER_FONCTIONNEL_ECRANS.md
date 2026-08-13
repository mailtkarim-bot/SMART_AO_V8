# SMART_AO V8 — Cahier fonctionnel détaillé : écrans et parcours

**Version :** 0.1 — rédaction progressive avec le fondateur  
**Statut :** document de travail à valider section par section  
**Objet :** décrire exactement ce que voient et font le patron, les collaborateurs et les partenaires autorisés. Ce document ne contient ni code ni détail d’infrastructure interne ; il sert de pont entre la vision métier et la future conception technique.

---

## 1. Règle générale : SMART_AO est un guide de travail, pas un ERP à menus

SMART_AO ne doit jamais donner au client l’impression d’entrer dans un ERP classique chargé de menus, de boutons, de tableaux et de fonctions qu’il doit découvrir seul. Le logiciel doit au contraire guider l’utilisateur dans le travail réel de réponse aux appels d’offres : **une étape utile à la fois, une explication simple, une action principale et une reprise de travail évidente**.

> **Promesse d’expérience :** « Vous n’avez pas à chercher quoi faire. SMART_AO vous montre l’étape utile, ce qui manque, pourquoi cela compte et ce qui sera produit ensuite. »

Le patron garde une vision plus large de l’entreprise et des affaires. Le collaborateur, lui, travaille dans un parcours concentré sur l’affaire qui lui est attribuée. Aucun des deux ne doit se perdre dans un empilement de pages.

---

## 2. Comment le client reçoit et ouvre SMART_AO

Chaque entreprise cliente possède son propre environnement SMART_AO sur un VPS dédié. À la mise en service, elle reçoit une adresse web sécurisée propre à son entreprise, par exemple :

```text
https://dupont-batiment.smartaobtp.fr
```

L’utilisateur ouvre cette adresse dans son navigateur habituel. Il ne télécharge aucun logiciel, ne manipule aucun serveur et n’utilise aucun outil de développement. Cette simplicité fait partie de l’offre commerciale : le patron reçoit un lien, se connecte et travaille.

| Moment | Ce qui se passe | Ce que voit ou fait le client |
|---|---|---|
| Mise en service | L’instance dédiée de l’entreprise est activée et sécurisée. | Le patron reçoit un e-mail d’invitation. |
| Première ouverture | Le patron clique sur le lien reçu. | Il arrive sur la page d’activation de son compte. |
| Création du mot de passe | Il choisit son mot de passe personnel et confirme son identité. | Il devient le seul administrateur initial de son entreprise. |
| Première connexion | Il se connecte à l’adresse web de son entreprise. | Il entre dans SMART_AO, sans aucune installation locale. |
| Création des collaborateurs | Il invite ses salariés depuis son espace patron. | Chaque salarié reçoit son propre lien, identifiant et mot de passe. |
| Travail quotidien | Patron et collaborateurs retournent sur la même adresse web. | Chacun voit uniquement les affaires, données et actions autorisées. |

### 2.1. Écran A01 — Activation du compte patron

Cet écran est ouvert depuis le lien sécurisé envoyé au premier client. Il est volontairement très simple : il ne vend pas le produit, il permet au patron de prendre possession de son espace.

| Élément | Contenu attendu |
|---|---|
| Identité visuelle | Logo SMART_AO, nom de l’entreprise cliente et design sobre. |
| Message en haut de page | **« Bienvenue dans l’espace SMART_AO de [Entreprise]. Vous allez activer le compte qui vous permet de piloter vos appels d’offres en toute confidentialité. »** |
| Informations visibles | Nom de l’entreprise, e-mail invité et rappel que le compte est réservé au patron administrateur. |
| Actions demandées | Créer le mot de passe, confirmer le mot de passe, accepter les conditions d’utilisation et la politique de confidentialité. |
| Action principale | **« Activer mon espace sécurisé »**. |
| Aide contextuelle | Un lien discret : « Pourquoi dois-je créer un compte administrateur ? » avec une réponse simple sur la séparation patron/collaborateurs. |
| Résultat | Le compte patron est activé ; l’utilisateur est dirigé vers la première étape de prise en main. |

Si le lien a expiré, l’écran ne doit pas produire une erreur technique. Il affiche : **« Ce lien n’est plus actif. Demandez un nouveau lien d’activation à votre contact SMART_AO ou utilisez l’adresse de connexion de votre entreprise. »**

### 2.2. Écran A02 — Connexion quotidienne

La page de connexion est la page que le patron et les collaborateurs voient lorsqu’ils reviennent sur l’adresse de leur entreprise.

| Élément | Contenu attendu |
|---|---|
| Message principal | **« Connectez-vous à votre espace SMART_AO. Vous retrouverez exactement le travail à faire et l’avancement de vos dossiers. »** |
| Champs | Adresse e-mail et mot de passe. |
| Action principale | **« Se connecter »**. |
| Actions secondaires | « Mot de passe oublié » et « Vous avez reçu une invitation ? ». |
| Réassurance | Mention visible : « Espace privé de [Entreprise] — vos données ne sont pas partagées avec d’autres entreprises. » |
| Résultat | L’utilisateur entre dans son espace correspondant à son rôle. |

Un collaborateur ne doit jamais pouvoir sélectionner son rôle à la connexion. Son rôle est défini par l’invitation et les droits attribués par le patron. Ainsi, il ne peut pas se connecter accidentellement dans un espace financier ou administratif qui ne lui appartient pas.

---

## 3. Charte d’expérience guidée commune à tous les écrans

Cette charte s’applique à tout SMART_AO : onboarding, affaires, analyse DCE, bibliothèque, prix, documents, chiffrage, dépôt et suivi de marché.

### 3.1. Une page = une intention de travail

Chaque page doit répondre à une seule question : **qu’est-ce que l’utilisateur doit comprendre ou faire maintenant ?** Une page ne rassemble jamais par défaut l’ensemble des données d’une affaire. Elle contient le minimum nécessaire pour accomplir l’étape courante correctement.

| Règle | Application dans l’interface |
|---|---|
| Une intention | La page porte un titre d’action clair : « Vérifier les pièces reçues », pas « Documents ». |
| Une priorité | Une seule action principale visuellement mise en avant : « Continuer vers l’analyse », « Envoyer au patron », « Valider le chiffrage ». |
| Peu d’actions secondaires | Elles sont présentes seulement si utiles : enregistrer, revenir, demander une pièce, voir le document source. |
| Peu d’informations à la fois | Les détails sont placés dans une section « Voir le détail » sans cacher l’information critique. |
| Aucune impasse | L’utilisateur sait toujours comment revenir, enregistrer, demander de l’aide ou reprendre plus tard. |

Tous les boutons ne doivent pas forcément ouvrir une nouvelle page. Un bouton d’action locale peut enregistrer une information, ajouter une pièce ou ouvrir une source. En revanche, il ne doit exister qu’une **action principale de progression** qui mène à l’étape suivante lorsque les conditions sont réunies.

### 3.2. Structure obligatoire de chaque écran de travail

| Zone | Rôle | Exemple d’affichage |
|---|---|---|
| **1. Bandeau de situation** | Situe l’utilisateur dans l’affaire et le parcours. | « Centre médical de Guesnain — Lot 01 — Étape 3 sur 11 ». |
| **2. Message-guide** | Explique simplement ce qui est attendu et pourquoi. | « Vérifiez que toutes les pièces du DCE sont présentes. Les documents manquants peuvent modifier votre prix ou votre délai. » |
| **3. Travail à faire maintenant** | Présente les champs, documents ou décisions de l’étape. | Liste de pièces, tableau de contrôles ou formulaire court. |
| **4. Conséquence / résultat** | Indique ce qui sera produit après validation. | « Après cette étape, SMART_AO préparera la liste des obligations et des risques. » |
| **5. Actions de page** | Retour, sauvegarde, aide, action principale. | « Enregistrer et quitter », « Retour », « Continuer vers l’analyse ». |
| **6. État de sauvegarde** | Rassure l’utilisateur que son travail est conservé. | « Enregistré il y a 12 secondes » ou « Modification non enregistrée ». |

Le message-guide est toujours visible en haut de l’espace de travail. Il ne doit pas prendre la forme d’un faux chatbot ou prétendre qu’une intelligence artificielle parle à l’utilisateur. Il s’agit de la voix claire et professionnelle de SMART_AO : une aide écrite, contextuelle et utile.

### 3.3. Aide sur les boutons et les termes

Chaque bouton, icône, sigle BTP ou expression inhabituelle doit être compréhensible sans formation longue.

| Élément | Règle d’aide |
|---|---|
| Bouton principal | Son libellé décrit le résultat : « Transmettre au patron pour validation », jamais seulement « Valider ». |
| Icône seule | Interdite lorsqu’elle déclenche une action importante. Elle doit être accompagnée d’un libellé. |
| Survol de souris | Une infobulle claire explique l’action, sans être la seule source d’information. |
| Mobile ou tactile | La même explication doit être accessible par appui ou visible dans le libellé, car il n’existe pas de survol. |
| Terme métier | Une aide courte apparaît à côté du terme : par exemple « DPGF : détail des prix demandé par l’acheteur ». |
| Erreur ou blocage | Le message indique ce qui manque, pourquoi c’est nécessaire et l’action possible pour le résoudre. |

Exemple de formulation attendue :

> **« Il manque le diagnostic amiante annoncé dans le dossier. Vous pouvez continuer l’analyse, mais SMART_AO signalera ce point au patron car il peut modifier le prix et les conditions d’intervention. »**

### 3.4. Progression contrôlée, retour et reprise

Le parcours SMART_AO est guidé sans être prisonnier. L’utilisateur avance étape par étape pour éviter les oublis, mais il conserve la possibilité de s’arrêter, revenir et compléter une donnée plus tard lorsque cela est autorisé.

| Situation | Comportement attendu |
|---|---|
| L’utilisateur quitte une affaire en cours | Son avancement est sauvegardé automatiquement et il retrouve la même étape à son retour. |
| Une information non critique manque | Il peut continuer si le patron l’autorise ; le statut devient clairement « À compléter ». |
| Une information bloquante manque | L’étape suivante reste inaccessible et le logiciel explique précisément la raison. |
| L’utilisateur veut corriger une étape précédente | Il peut revenir en arrière ; les conséquences sur les étapes suivantes sont signalées. |
| Le patron a validé un verrou important | La modification reste possible selon ses droits, mais une nouvelle validation peut être demandée. |
| Le dossier est prêt au dépôt | Une version finale est verrouillée ; toute modification crée une nouvelle version, jamais un écrasement silencieux. |

### 3.5. Messages systématiques de SMART_AO

SMART_AO accompagne l’utilisateur par des messages courts, sobres et contextuels. Ils doivent renforcer la confiance sans infantiliser l’entrepreneur.

| Moment | Style de message attendu |
|---|---|
| Début d’étape | « Voici ce que vous allez vérifier maintenant. » |
| Donnée manquante | « Cette information manque encore. Voici pourquoi elle peut être importante. » |
| Contradiction | « Deux documents ne donnent pas la même information. Vérifiez ce point avant de vous engager. » |
| Travail enregistré | « Votre travail est enregistré. Vous pourrez reprendre cette étape plus tard. » |
| Transmission au patron | « La préparation est terminée. Le patron va maintenant vérifier les éléments réservés et prendre sa décision. » |
| Action réussie | « Cette étape est terminée. SMART_AO a préparé la suite du dossier. » |
| Risque élevé | « Attention : ce point peut modifier votre prix, votre délai ou votre responsabilité. » |

Les messages n’utilisent jamais de formulation vague comme « Analyse terminée » si le résultat contient des incertitudes. Ils indiquent ce qui est confirmé, ce qui reste à vérifier et qui doit agir.

### 3.6. Règles visuelles et ergonomiques

| Sujet | Décision fonctionnelle |
|---|---|
| Menus | Pas de menu chargé pour le collaborateur. Une navigation réduite à l’affaire, au parcours, aux tâches et à l’aide. |
| Patron | Un cockpit global existe, mais chaque action importante l’amène ensuite dans un parcours clair, pas dans une accumulation de tableaux. |
| Couleurs | Couleurs réservées aux statuts : terminé, à faire, attention, bloquant, validé patron. Elles ne sont jamais la seule information affichée. |
| Texte | Français clair, titres d’action, phrases courtes et vocabulaire BTP expliqué lorsque nécessaire. |
| Formulaires | Champs regroupés par décision métier, jamais par structure technique de base de données. |
| Tableaux | Utilisés uniquement pour comparer, contrôler ou décider ; pas comme écran principal par défaut. |
| Responsive | L’interface fonctionne d’abord sur ordinateur ; elle reste lisible sur tablette. Les actions critiques de chiffrage et dépôt sont optimisées pour écran de bureau. |
| Accessibilité | Contraste suffisant, navigation clavier, libellés explicites et messages non dépendants du survol ou de la couleur. |

---

## 4. Première séquence à définir ensuite

La présente version fixe l’arrivée dans SMART_AO et la manière dont tout le logiciel doit guider son utilisateur. La prochaine discussion avec le fondateur définira la première étape vécue par le patron après sa connexion : **son premier écran d’accueil et son installation initiale d’entreprise**.

Les sections suivantes seront ajoutées une par une, après validation :

1. accueil du patron et état de préparation de l’entreprise ;
2. création des comptes collaborateurs ;
3. bibliothèque administrative, technique et financière ;
4. profil de recherche d’affaires ;
5. accueil collaborateur ;
6. création et analyse d’une affaire DCE ;
7. passage au patron, chiffrage, contrôle et dépôt ;
8. suivi du marché gagné.

Aucune section ultérieure ne sera considérée comme définitive tant qu’elle n’aura pas été relue et validée par le fondateur.

---

## 5. L’espace patron : le centre privé de décision de l’entreprise

Le premier utilisateur de SMART_AO est le **patron administrateur**. Son espace doit lui donner la maîtrise de son entreprise sans l’enfermer dans un ERP. Il voit les affaires, les alertes, la préparation des dossiers, la bibliothèque de l’entreprise, les opportunités et les données financières qui lui sont réservées.

Le collaborateur ne reçoit pas une copie réduite du cockpit patron. Il reçoit un **espace de travail personnel**, limité aux affaires et tâches qui lui sont attribuées. Le patron reste le seul à créer, modifier, suspendre ou supprimer les comptes collaborateurs.

### 5.1. Règle d’étanchéité : un espace personnel par utilisateur, pas un serveur par salarié

L’idée d’un environnement étanche pour chaque collaborateur est juste. Toutefois, SMART_AO ne doit pas créer un VPS ou un logiciel séparé pour chaque salarié. L’entreprise possède une seule instance SMART_AO privée ; à l’intérieur, chaque utilisateur possède un espace personnel et protégé.

| Utilisateur | Ce qu’il peut voir | Ce qu’il ne doit jamais voir par défaut |
|---|---|---|
| **Patron administrateur** | Toutes les affaires, bibliothèque complète, opportunités, documents, contrôles, prix, devis, marges, trésorerie, comptes collaborateurs et décisions. | Les données d’une autre entreprise cliente. |
| **Collaborateur** | Les affaires, pièces, tâches, messages et dossiers qui lui sont explicitement attribués. | Prix internes, devis fournisseurs, marges, trésorerie, règles de chiffrage, paramètres globaux et affaires non attribuées. |
| **Partenaire externe** | Une demande limitée : par exemple fournir un prix, un certificat ou une pièce pour une affaire précise. | Toute autre affaire, bibliothèque de l’entreprise, prix internes, marge et données collaborateurs. |

> **Promesse à écrire dans le produit :** « Votre entreprise possède son espace SMART_AO privé. Le patron décide ce que chaque personne peut consulter, préparer ou valider. Les prix, marges et données sensibles restent sous son contrôle. »

Le patron peut créer autant de comptes collaborateurs que nécessaire. SMART_AO ne pose pas de limite fonctionnelle artificielle. Si une très grande entreprise atteint les capacités prévues par son abonnement ou son VPS, l’évolution de ressources est discutée avec elle ; ce n’est jamais un blocage caché dans l’interface.

---

## 6. La navigation patron : courte, visible et orientée action

Le patron doit pouvoir revenir à tout moment à une vue globale. Il a donc une navigation plus large que le collaborateur, mais elle reste limitée à sept entrées maximum. Les alertes et demandes de décision sont visibles sans ouvrir plusieurs sous-menus.

| Entrée de navigation | Ce que le patron y trouve | Action principale proposée |
|---|---|---|
| **Cockpit** | Vue de l’entreprise aujourd’hui : affaires, blocages, échéances et décisions attendues. | « Voir ce qui exige votre décision ». |
| **Affaires** | Tous les DCE, lots et réponses en cours ou archivés. | « Ouvrir une affaire » ou « Créer une affaire ». |
| **Opportunités** | Avis d’appels d’offres issus de la veille, import manuel ou sources activées. | « Examiner une opportunité ». |
| **Entreprise** | Identité, activité, équipes, capacités, informations de réponse et paramètres de l’entreprise. | « Compléter la fiche entreprise ». |
| **Bibliothèque** | Documents administratifs, techniques, références, partenaires, modèles et fichiers de prix. | « Ajouter un document d’entreprise ». |
| **Équipe** | Comptes collaborateurs, rôles, invitations, accès et affaires attribuées. | « Inviter un collaborateur ». |
| **Aide et réglages** | Notifications, accès IA autorisés, sécurité, langue, support et historique des actions sensibles. | « Vérifier les réglages de mon espace ». |

Cette navigation est affichée de façon discrète. Elle peut être une barre latérale courte sur ordinateur, réduite sur tablette. Elle ne doit pas occuper la page principale ni concurrencer l’action du moment.

---

## 7. Première arrivée du patron : installer l’entreprise avant de traiter une affaire

Après l’activation de son compte, le patron ne doit pas tomber sur un cockpit vide. SMART_AO ouvre un **parcours d’installation de l’entreprise**. Le message-guide explique que cette préparation permettra ensuite de remplir plus vite les dossiers, réutiliser les bonnes pièces et protéger les informations confidentielles.

> **Message d’accueil proposé :** « Bienvenue [Prénom]. Avant de traiter vos premiers appels d’offres, préparons les informations et documents que SMART_AO réutilisera pour votre entreprise. Vous pourrez compléter ce profil plus tard ; nous vous indiquerons toujours ce qui manque. »

L’installation de l’entreprise n’est pas une seule page interminable. Elle est découpée en étapes courtes ; le patron peut s’arrêter et reprendre son travail.

| Étape d’installation | Question simple posée au patron | Résultat visible |
|---:|---|---|
| **P01. Identifier mon entreprise** | « Qui répond aux marchés ? » | Fiche juridique et coordonnées de l’entreprise. |
| **P02. Décrire mes métiers et capacités** | « Quels travaux réalisez-vous réellement ? » | Métiers, lots, zones, qualifications, équipes et matériel déclarés. |
| **P03. Ajouter mon équipe** | « Qui travaille avec vous dans SMART_AO ? » | Comptes collaborateurs et responsabilités. |
| **P04. Déposer mes documents d’entreprise** | « Quelles pièces SMART_AO doit-il pouvoir retrouver ? » | Bibliothèque classée, datée et contrôlée. |
| **P05. Ajouter mes prix et historiques privés** | « Quels fichiers doivent vous aider à chiffrer ? » | Base de prix interne versionnée, réservée au patron. |
| **P06. Définir ma veille d’opportunités** | « Quelles affaires souhaitez-vous voir remonter ? » | Un ou plusieurs profils de recherche actifs. |
| **P07. Vérifier que mon entreprise est prête** | « Puis-je commencer à travailler sur un DCE ? » | Tableau de préparation avec éléments prêts, à compléter ou sensibles. |

Le patron peut passer temporairement une étape non bloquante. SMART_AO affiche alors clairement ce qui ne pourra pas être préparé automatiquement dans les prochains dossiers. Par exemple : « Vous pourrez analyser un DCE, mais SMART_AO ne pourra pas encore préremplir vos références car aucune référence n’a été ajoutée. »

---

## 8. Écran P01 — Identité et informations de l’entreprise

Cet écran transforme les informations d’une entreprise en données réutilisables pour les formulaires, documents, réponses, invitations et courriers. Il est organisé en sous-parties visibles une par une ; il ne demande jamais au patron de remplir tous les champs d’un coup.

### 8.1. Sous-étape P01-A — Identité juridique

| Information demandée | Aide affichée | Usage futur dans SMART_AO |
|---|---|---|
| Raison sociale | « Nom légal qui apparaît sur vos documents officiels. » | DC1/DC2, courriers, acte d’engagement et documents administratifs. |
| Nom commercial | « Nom sous lequel vos clients vous connaissent, si différent. » | Interface, mémoire et communication commerciale. |
| Forme juridique | « Par exemple : SARL, SAS, SA, EI. » | Formulaires et fiches entreprise. |
| SIREN / SIRET | « Indiquez le numéro de l’établissement qui répondra aux marchés. » | Préremplissage et vérifications administratives. |
| RCS ou registre compétent | « Informations figurant sur votre immatriculation. » | Documents administratifs lorsqu’ils sont demandés. |
| Numéro de TVA intracommunautaire | « Facultatif si vous ne l’utilisez pas dans vos réponses actuelles. » | Formulaires et échanges selon besoin. |
| Adresse du siège et adresse opérationnelle | « Dites-nous où l’entreprise est juridiquement et opérationnellement implantée. » | Courriers, recherche géographique et calculs de distance. |
| Coordonnées générales | Téléphone, e-mail générique, site web si disponible. | Communications et documents générés. |

### 8.2. Sous-étape P01-B — Personnes habilitées et contacts utiles

| Information demandée | Pourquoi SMART_AO la demande | Confidentialité |
|---|---|---|
| Représentant légal | Identifier la personne habilitée à engager l’entreprise. | Patron uniquement par défaut. |
| Signataire(s) autorisé(s) | Préparer les documents et contrôles de signature quand le DCE l’exige. | Patron uniquement. |
| Contact administratif | Recevoir les demandes de pièces ou relances administratives. | Patron décide du partage. |
| Contact appels d’offres | Personne qui suit les consultations et les demandes de précision. | Visible selon attribution. |
| Contact travaux / exploitation | Personne à mobiliser pour moyens, planning, méthodes et visite. | Visible selon attribution. |
| Contact facturation | Préparer le suivi après attribution. | Patron uniquement par défaut. |

### 8.3. Sous-étape P01-C — Identité visuelle et modèles

Le patron peut téléverser le logo de l’entreprise, choisir le nom affiché dans SMART_AO et ajouter, s’il le souhaite, la signature visuelle de ses documents. Cette étape est facultative : un dossier de réponse doit rester correct même sans charte graphique.

| Action | Résultat |
|---|---|
| **Ajouter le logo** | Logo affiché dans l’espace de l’entreprise et utilisable dans les documents internes ou modèles autorisés. |
| **Ajouter les coordonnées de pied de page** | Données réutilisées dans les courriers ou rapports de l’entreprise. |
| **Ajouter un modèle existant** | Modèle Word/PDF/Excel stocké dans la bibliothèque pour réutilisation future. |
| **Continuer sans personnalisation** | SMART_AO utilise une présentation neutre jusqu’à ce que le patron complète cette partie. |

**Action principale de P01 :** `Enregistrer mon entreprise et continuer`.

---

## 9. Écran P02 — Métiers, capacités et périmètre réel de l’entreprise

SMART_AO doit connaître ce que l’entreprise sait réellement faire. Cet écran ne sert pas à produire un catalogue commercial décoratif ; il permet de filtrer les opportunités, de vérifier la capacité à répondre et de réutiliser des preuves pertinentes dans les mémoires techniques.

| Rubrique | Informations que le patron peut renseigner | Utilisation par SMART_AO |
|---|---|---|
| **Métiers et spécialités** | Corps d’état, lots, travaux principaux, techniques maîtrisées, interventions associées. | Filtrage d’opportunités, lecture des lots, choix de références et mémoire. |
| **Types de chantier** | Neuf, réhabilitation, site occupé, tertiaire, industriel, logement, santé, public, patrimoine, etc. | Qualification des risques et sélection de références. |
| **Qualifications et certifications** | Qualibat, RGE, habilitations, certifications amiante, autres titres pertinents. | Vérification de capacité et alerte de péremption. |
| **Zone d’intervention habituelle** | Départements, régions, villes, code postal de base et rayon de déplacement. | Veille d’affaires et analyse de faisabilité. |
| **Effectif et encadrement** | Taille globale, responsables travaux, chefs de chantier, équipes disponibles. | Capacité, moyens humains et préparation du mémoire. |
| **Matériel et moyens** | Matériels détenus, louables, sous-traitables ou indisponibles. | Mémoire, coûts, logistique et contrôle de faisabilité. |
| **Capacité maximale choisie par le patron** | Nombre ou volume d’affaires simultanées acceptable, périodes déjà chargées, seuils internes. | Alerte de surcharge et décision Go/No-Go. |
| **Partenaires habituels** | Fournisseurs, sous-traitants, cotraitants et compétences complémentaires. | Recherche de partenaire, demande de pièce et réponse en groupement. |

SMART_AO ne déduit pas qu’une entreprise est capable de réaliser un lot parce qu’elle a coché un mot-clé. Les informations renseignées servent de point de départ ; le patron valide toujours la capacité réelle pour une affaire précise.

**Action principale de P02 :** `Enregistrer mes capacités et continuer`.

---

## 10. Écran P03 — Équipe et comptes collaborateurs

Le patron crée les comptes collaborateurs depuis une page simple. L’objectif n’est pas de gérer des ressources humaines complexes : il s’agit d’autoriser les bonnes personnes à travailler sur les bonnes affaires, sans leur donner accès aux informations réservées.

### 10.1. Vue d’ensemble de l’équipe

| Zone | Contenu |
|---|---|
| Message-guide | **« Invitez les personnes qui prépareront vos dossiers. Elles ne verront que les affaires que vous leur attribuerez et n’auront pas accès à vos prix ni à vos marges. »** |
| Liste des personnes | Nom, fonction, statut d’invitation, nombre d’affaires attribuées, dernière connexion et compte actif/suspendu. |
| Action principale | `Inviter un collaborateur`. |
| Action secondaire | Modifier une fonction, suspendre un accès, renvoyer une invitation ou consulter les affaires attribuées. |
| Réassurance | « Vous gardez à tout moment le contrôle des comptes et des accès de votre entreprise. » |

### 10.2. Formulaire d’invitation d’un collaborateur

| Information | Règle |
|---|---|
| Prénom et nom | Obligatoires. |
| Adresse e-mail professionnelle | Obligatoire ; elle reçoit le lien d’activation sécurisé. |
| Fonction dans l’entreprise | Exemples proposés : chargé d’affaires, métreur, conducteur de travaux, assistante, responsable administratif. |
| Type de compte | `Collaborateur`. Le patron est le seul type de compte administrateur au départ. |
| Affaires attribuées | Aucune à l’invitation ou une sélection initiale si les affaires existent déjà. |
| Autorisations exceptionnelles | Le patron peut autoriser l’édition d’un document précis ou l’accès à une tâche, jamais aux prix globaux par défaut. |
| Message personnel | Facultatif, ajouté à l’e-mail d’invitation. |

Après envoi, SMART_AO affiche : **« Invitation envoyée à [Nom]. Cette personne n’aura accès à aucune affaire tant que vous ne lui en attribuez pas une. »**

### 10.3. Ce que le patron peut faire à tout moment

| Action patron | Résultat |
|---|---|
| Attribuer une affaire à un collaborateur | Le collaborateur voit l’affaire et le wizard correspondant. |
| Retirer une affaire | L’accès disparaît immédiatement ; les travaux déjà enregistrés restent dans l’historique de l’affaire. |
| Suspendre un compte | La connexion est bloquée sans supprimer l’historique ni les documents réalisés. |
| Réactiver un compte | La personne retrouve uniquement les droits encore attribués. |
| Modifier la fonction | L’étiquette de fonction change ; les droits réels restent définis par les règles d’accès et les affaires attribuées. |
| Consulter l’historique | Le patron voit les actions importantes : documents ajoutés, étapes terminées, retours demandés et transmissions. |

**Action principale de P03 :** `Continuer vers les documents de mon entreprise`.

---

## 11. Écran P04 — Bibliothèque de l’entreprise

La bibliothèque n’est pas un disque dur désordonné. C’est la mémoire documentée de l’entreprise : les pièces à joindre, les preuves à réutiliser, les documents à surveiller et les données privées nécessaires au patron.

L’écran d’entrée affiche un grand bouton : **`Ajouter des documents d’entreprise`**. Ce bouton ouvre un parcours de classement guidé, et non une zone de téléversement confuse.

### 11.1. Écran P04-A — Choisir ce que l’on ajoute

| Zone proposée | Exemples de documents | Visibilité par défaut |
|---|---|---|
| **Administratif et juridique** | Kbis, RIB, délégation, assurances, attestations URSSAF/fiscales, qualifications. | Patron ; partage uniquement lorsqu’une affaire l’exige. |
| **Références et savoir-faire** | Fiches chantier, photos autorisées, attestations de bonne exécution, méthodes validées. | Patron et collaborateurs autorisés selon l’affaire. |
| **Équipe et moyens** | CV, habilitations, organigrammes, listes de matériel, certificats. | Selon attribution et nécessité de l’affaire. |
| **Technique et qualité** | Fiches produits, FDES, procédures, modèles de plan qualité, SOGED, contrôle. | Selon attribution. |
| **Partenaires** | Fournisseurs, sous-traitants, cotraitants, documents et périmètres d’intervention. | Patron par défaut. |
| **Modèles de réponse** | Modèles Word, Excel, courriers, trames internes, anciens mémoires validés. | Patron ; publication sélective dans une affaire. |
| **Prix et données confidentielles** | Fichiers Excel internes, historiques de prix, devis, déboursés, règles de marge et trésorerie. | **Patron uniquement.** |

Le patron peut glisser-déposer plusieurs documents. Avant l’import, SMART_AO lui demande toujours de choisir la zone de la bibliothèque ; le logiciel peut proposer une classification, mais le patron ou la personne autorisée confirme lorsqu’elle affecte la confidentialité.

### 11.2. Écran P04-B — Décrire un document ajouté

| Information | Pourquoi elle est demandée |
|---|---|
| Nom du document | Retrouver rapidement la bonne pièce. |
| Type de document | Savoir s’il s’agit d’une assurance, d’une référence, d’un prix, d’une qualification, etc. |
| Périmètre concerné | Activité, lot, personne, partenaire, site ou zone de validité. |
| Date d’émission et date d’expiration connue | Déclencher les alertes de renouvellement. |
| Source | Entreprise, assureur, URSSAF, fournisseur, partenaire, client antérieur, etc. |
| Niveau de confidentialité | Patron seulement, partageable sur affaires attribuées ou partage explicite ponctuel. |
| Commentaire facultatif | Expliquer la limite, une réserve ou la prochaine action. |

SMART_AO conserve toujours le fichier original. Lorsqu’il extrait une information ou génère une fiche de synthèse, cette fiche ne remplace jamais le document source.

### 11.3. Écran P04-C — État de la bibliothèque

Le patron peut consulter une vue simple : pièces prêtes, pièces bientôt expirées, pièces absentes par rapport à ses activités déclarées et pièces à vérifier.

| Statut | Exemple de message |
|---|---|
| Prêt | « Assurance décennale ajoutée — expiration connue le 30/11/2026. » |
| À renouveler | « Qualification à renouveler dans 60 jours. Préparez une nouvelle version avant une prochaine réponse. » |
| À vérifier | « Ce certificat ne précise pas encore le périmètre de qualification. » |
| Absent | « Aucun modèle de référence n’a été ajouté pour le lot Gros œuvre. » |
| Privé patron | « Ce fichier de prix n’est visible que dans votre espace chiffrage. » |

---

## 12. Écran P05 — Prix, historiques et règles privées du patron

Les fichiers Excel de l’entreprise sont une partie essentielle de la personnalisation SMART_AO. Le logiciel doit s’adapter aux prix et à la méthode de chiffrage du patron ; il ne doit pas imposer une base nationale standard ni écraser les fichiers existants.

Cette page est exclusivement patron. Un collaborateur ne voit ni son entrée de navigation ni ses données.

| Zone | Ce que le patron peut faire | Protection attendue |
|---|---|---|
| **Fichiers de prix** | Ajouter un Excel existant, lui donner un nom, une date d’effet, un métier, une zone ou une famille de postes. | Original immuable ; toute nouvelle importation crée une version. |
| **Historique de chantier** | Ajouter un ancien DPGF, BPU, retour de coût, devis ou aléa, si le patron souhaite s’en servir comme repère. | Visible uniquement au patron, sauf extraction expurgée autorisée. |
| **Devis partenaires** | Classer des devis par fournisseur, date, périmètre, validité et exclusions. | Non visible par défaut au collaborateur. |
| **Hypothèses de chiffrage** | Définir ses propres règles : frais de chantier, frais généraux, marge cible, seuil d’alerte, provisions, conditions de paiement. | Toute règle est versionnée, datée et modifiable affaire par affaire par le patron. |
| **Contrôle des importations** | Vérifier les onglets, colonnes reconnues, lignes non comprises et cellules sensibles. | SMART_AO ne modifie jamais le fichier original sans créer une copie de travail. |

> **Message-guide proposé :** « Ajoutez les fichiers qui reflètent votre manière réelle de chiffrer. SMART_AO les utilisera comme références privées : il ne remplace pas vos prix, il vous aide à les retrouver, les comparer et les appliquer avec contrôle. »

---

## 13. Écran P06 — Profil de recherche d’appels d’offres

La veille ne doit pas se limiter à afficher tous les avis disponibles. Le patron doit dire au logiciel ce qu’est une bonne affaire pour son entreprise. SMART_AO peut alors présenter les opportunités les plus pertinentes et expliquer pourquoi elles ont été retenues.

Un patron peut créer plusieurs profils de veille. Par exemple : **« Gros œuvre — Hauts-de-France »**, **« Réhabilitation de santé — rayon 150 km »** ou **« Petits marchés de proximité »**.

> **Important :** BOAMP est une source essentielle pour les avis publics, mais elle ne couvre pas à elle seule tous les appels d’offres privés. SMART_AO doit donc accepter aussi les opportunités importées manuellement, reçues par invitation ou issues de sources futures autorisées.

### 13.1. Sous-étape P06-A — Ce que l’entreprise recherche

| Famille de critères | Informations à renseigner |
|---|---|
| **Nom du profil** | Nom choisi par le patron, état actif ou en pause. |
| **Métiers et lots** | Corps d’état, travaux, mots-clés, familles de lots et spécialités à rechercher. |
| **Types de projet** | Neuf, réhabilitation, site occupé, tertiaire, santé, logement, industrie, public, privé, patrimoine, etc. |
| **Acheteurs recherchés** | Public, privé, bailleur, collectivité, établissement de santé, industriel, donneur d’ordre connu, etc. |
| **Montant ou taille de marché** | Minimum, maximum, ordre de grandeur préféré, taille de lot recherchée. |
| **Date et durée** | Période de début souhaitée, durée maximale acceptable, périodes indisponibles ou déjà saturées. |
| **Forme de réponse** | Entreprise seule, groupement accepté, sous-traitance possible, variantes acceptées selon stratégie. |

### 13.2. Sous-étape P06-B — Où l’entreprise souhaite travailler

| Information | Exemple d’usage |
|---|---|
| Adresse ou code postal de référence | Point de départ de l’entreprise ou d’une agence. |
| Rayon kilométrique | « Chercher dans un rayon de 120 km ». |
| Départements, régions ou villes prioritaires | Affiner les opportunités présentées. |
| Zones exclues | Éviter les zones trop éloignées, difficiles ou non rentables pour l’entreprise. |
| Contraintes logistiques | Besoin d’accès autoroutier, interdit de centre-ville, absence de base locale, etc. |

SMART_AO affiche la distance estimée et explique le critère ayant conduit à retenir ou écarter l’opportunité. La distance ne décide pas seule : le patron peut toujours examiner une affaire hors zone.

### 13.3. Sous-étape P06-C — Ce que le patron accepte ou refuse

| Critère | Choix proposés au patron |
|---|---|
| Qualifications nécessaires | Exiger une qualification détenue, accepter une qualification partenaire ou afficher avec alerte. |
| Visite obligatoire | Afficher, filtrer ou rendre prioritaire selon la disponibilité de l’entreprise. |
| Critères environnementaux / insertion | Afficher les marchés concernés, signaler les engagements à prévoir et les partenaires nécessaires. |
| Marchés multi-lots | Afficher les lots correspondant aux métiers, avec alerte si les lots sont inséparables. |
| Conditions de paiement et garanties | Signaler les conditions sensibles lorsqu’elles sont déjà visibles dans l’avis ou le dossier. |
| Exclusions stratégiques | Montant insuffisant, délai trop court, zone, type de chantier, client, risque technique ou capacité saturée. |

### 13.4. Sous-étape P06-D — Fréquence et présentation de la veille

| Réglage | Choix possibles |
|---|---|
| Rythme de recherche | Quotidien, jours ouvrés, hebdomadaire ou consultation manuelle. |
| Mode de notification | Cockpit uniquement, e-mail récapitulatif, alerte immédiate pour opportunité prioritaire. |
| Nombre d’opportunités affichées | Liste complète, meilleures correspondances ou seulement les opportunités dépassant un seuil choisi par le patron. |
| Explication du score | Toujours visible : métier, distance, montant, type de projet, capacité et exclusions appliquées. |

**Action principale de P06 :** `Activer mon profil de veille`.

---

## 14. Écran P07 — Cockpit du patron

Le cockpit n’est pas un tableau rempli de chiffres. Il répond à une question : **« Où dois-je intervenir aujourd’hui pour protéger une affaire, une marge, une échéance ou une décision ? »**

Le patron peut ouvrir tout le détail, mais l’écran d’accueil lui montre seulement les priorités du jour.

### 14.1. Bandeau d’accueil

> **« Bonjour [Prénom]. Voici les affaires qui exigent votre attention aujourd’hui. »**

Le bandeau peut contenir une courte phrase utile, jamais un message décoratif. Exemple : **« Deux dossiers attendent votre validation ; une attestation expire dans 14 jours. »**

### 14.2. Les cinq cartes de décision

| Carte | Ce qu’elle montre | Action principale |
|---|---|---|
| **À décider** | Affaires en attente d’un Go/No-Go, d’une réponse à condition ou d’une validation patron. | `Voir les décisions à prendre`. |
| **À chiffrer** | Affaires dont la préparation administrative et technique est terminée et qui attendent le patron. | `Ouvrir le chiffrage privé`. |
| **À déposer** | Dossiers contrôlés, date limite proche, dernière validation ou action de dépôt attendue. | `Vérifier le dossier final`. |
| **À protéger** | Pièces expirantes, risques élevés, retards, rectificatifs, documents manquants ou alertes de trésorerie. | `Traiter les alertes`. |
| **Opportunités à examiner** | Avis détectés qui correspondent au profil de veille et nécessitent une première décision. | `Examiner les opportunités`. |

Chaque carte affiche un nombre, un niveau de priorité et la prochaine action possible. Elle n’affiche pas par défaut des chiffres de marge ou de trésorerie sur la page générale, même si le patron peut les consulter ensuite dans l’affaire concernée.

### 14.3. Liste des affaires en cours

Sous les cartes, le patron voit une liste courte des affaires prioritaires, avec possibilité d’ouvrir la liste complète.

| Information visible par affaire | Exemple |
|---|---|
| Nom de l’affaire et acheteur | « Centre médical Filieris — Guesnain ». |
| Lot | « Lot 01 — Gros œuvre étendu ». |
| Date limite ou prochain jalon | « Dépôt : 18/09 à 12h00 ». |
| Responsable collaborateur | « Préparé par : [Nom] ». |
| Avancement clair | « Étape 7 sur 11 — préparation technique terminée ». |
| État global | En préparation, attente patron, à chiffrer, à déposer, déposé, arrêté. |
| Blocage principal | « Visite obligatoire non attestée », « DPGF en attente », « Rectificatif à revoir ». |
| Action suivante | « Ouvrir et décider », « Chiffrer », « Relancer », « Vérifier le dépôt ». |

Un pourcentage d’avancement ne doit être affiché que s’il repose sur des étapes réellement terminées. Le texte **« Étape 7 sur 11 »** et le blocage principal sont plus utiles qu’un « 87 % » décoratif.

### 14.4. État de préparation de l’entreprise

Le cockpit rappelle également, de façon secondaire, si l’entreprise est prête à répondre : documents expirants, références insuffisantes dans un métier, profil de veille incomplet, fichier de prix à actualiser ou partenaires sans pièces valides.

| Signal | Exemple d’action proposée |
|---|---|
| Attestation ou qualification expire bientôt | `Mettre à jour ma bibliothèque`. |
| Aucun fichier de prix récent pour un métier | `Ajouter une nouvelle version de prix`. |
| Aucun profil de veille actif | `Créer un profil de recherche`. |
| Collaborateur sans affaire attribuée | `Attribuer une affaire ou vérifier l’équipe`. |

---

## 15. Écran P08 — Liste complète des affaires et passage au chiffrage patron

Le menu **Affaires** ouvre une vue plus détaillée que le cockpit. Le patron retrouve l’historique complet : opportunités écartées, DCE importés, dossiers en préparation, affaires à chiffrer, offres déposées, marchés gagnés, perdus ou abandonnés.

| Filtre | Utilité |
|---|---|
| État de l’affaire | Retrouver les affaires à décider, à préparer, à chiffrer, à déposer ou archivées. |
| Collaborateur | Voir la charge et l’avancement de chaque personne. |
| Échéance | Donner la priorité aux dépôts, visites ou questions proches. |
| Métier / lot / zone | Retrouver les affaires comparables ou filtrer une activité. |
| Niveau de risque | Isoler les dossiers avec blocage ou alerte majeure. |
| Acheteur / client | Suivre l’historique d’un donneur d’ordre. |

### 15.1. Le transfert collaborateur → patron

Le collaborateur ne décide jamais seul qu’un dossier est financièrement terminé. Lorsqu’il a achevé les étapes qui lui sont confiées, il utilise le bouton :

> **`Transmettre au patron pour chiffrage et décision`**

SMART_AO effectue alors un premier contrôle : quelles pièces sont prêtes, lesquelles manquent, quelles exigences ont été relevées, quelles questions restent sans réponse et quelles actions de tiers sont attendues.

| Le patron reçoit | Ce que cela signifie |
|---|---|
| **Résumé préparatoire** | Le collaborateur a terminé son périmètre ; ce n’est pas encore une offre prête à déposer. |
| **Documents et exigences** | Pièces classées, obligations, critères, risques, visite, questions et mémoire technique en brouillon. |
| **Blocages visibles** | Ce qui empêche le chiffrage ou le dépôt : pièce absente, réponse fournisseur, diagnostic, document expiré, décision de variante, etc. |
| **Espace prix privé** | DPGF/BPU/DQE, devis, historiques, marges, scénarios, aléas, trésorerie et contrôles, visibles uniquement au patron. |
| **Décisions patron** | Revenir au collaborateur avec une demande, demander un prix ou une pièce, chiffrer, autoriser la finalisation ou arrêter l’affaire. |

Le patron peut reprendre une affaire avant la fin du travail collaborateur s’il le souhaite. Le transfert est donc un repère clair dans le parcours, pas une barrière artificielle.

---

## 16. Ce qui doit être validé avant de définir le premier écran collaborateur

Les sections 5 à 15 constituent la première proposition complète de l’espace patron. Avant de décrire l’accueil du collaborateur et son parcours DCE, le fondateur doit confirmer les choix suivants :

1. le collaborateur reçoit un **espace de travail personnel et étanche**, mais non un serveur séparé ;
2. l’installation patron suit les sept étapes P01 à P07 ;
3. la navigation patron comporte les sept entrées définies ;
4. la bibliothèque sépare strictement les prix privés du reste des documents ;
5. le profil de veille peut être multiple et ne dépend pas uniquement de BOAMP ;
6. le cockpit patron est centré sur les décisions, chiffrages, dépôts, alertes et opportunités ;
7. le passage collaborateur → patron s’effectue par une transmission explicite vers le chiffrage privé.

La prochaine section à rédiger sera l’**accueil collaborateur**, puis le premier écran où il reçoit ou crée une affaire à analyser.
