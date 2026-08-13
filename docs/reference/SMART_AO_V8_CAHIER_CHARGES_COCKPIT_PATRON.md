# SMART_AO V8 — Cahier des charges de l’interface Cockpit Patron

**Version :** 1.0  
**Statut :** référence fonctionnelle détaillée avant conception graphique et développement  
**Auteur :** Manus AI  
**Utilisateur principal :** patron administrateur d’une entreprise BTP  
**Périmètre :** écran d’accueil patron, file d’actions et panneaux décisionnels directement accessibles depuis le Cockpit.

---

## 1. Mission du Cockpit

Le Cockpit Patron est l’écran d’accueil de SMART_AO. Il ne cherche pas à représenter toute l’entreprise, à remplacer une comptabilité ni à afficher une accumulation de graphiques. Son unique objectif est de permettre au patron de répondre rapidement à la question suivante :

> **« Qu’est-ce qui exige ma décision ou mon contrôle maintenant, pourquoi et quelle action dois-je entreprendre ? »**

Le Cockpit est une **vue préparée de décision**. Il ne possède pas sa propre vérité métier. Il rassemble des situations déjà établies par les frontières Affaire, Action patron, Décision, DCE, Preuve, Prix, Dépôt, Affectation et Opportunité. Toute donnée affichée doit être explicable, dater son information quand elle est sensible et ouvrir la ressource source.

Le Cockpit ne peut afficher ni un score global opaque, ni une marge détaillée exposée dans les cartes globales, ni une action présentée comme urgente sans expliquer sa cause.

---

## 2. Utilisateurs, droits et limites

| Profil | Accès au Cockpit | Actions possibles | Limites impératives |
|---|---|---|---|
| **Patron administrateur** | Accès complet à son Cockpit d’entreprise. | Traiter une action, ouvrir une affaire, décider, déléguer une préparation, créer une affaire, filtrer et ouvrir les sources autorisées. | Aucune donnée d’une autre entreprise. |
| **Délégataire patron habilité** | Accès limité aux cartes et affaires définies dans la délégation. | Seulement les commandes expressément autorisées et limitées dans le temps. | Pas de prix privé ou de décision réservée sans délégation explicite. |
| **Collaborateur** | Aucun accès au Cockpit Patron. | Aucun. | Il dispose de son propre espace de travail, non d’une version masquée du Cockpit. |
| **Partenaire externe** | Aucun accès. | Aucun. | Il ne reçoit que les demandes ponctuelles qui lui sont adressées. |

La confidentialité financière est appliquée **avant** la préparation de la vue. Une carte globale ne reçoit jamais les coûts, marges, déboursés, devis fournisseurs, trésoreries détaillées ou fichiers de prix, même masqués.

---

## 3. Principes de conception non négociables

| Principe | Exigence d’interface |
|---|---|
| **Une visite, une priorité** | Le patron doit voir l’action suivante la plus importante sans faire défiler ou filtrer. |
| **Pas de fausse précision** | Aucun pourcentage d’avancement décoratif, aucun score global de confiance, aucune date inventée. |
| **Risque séparé de l’urgence** | Une carte doit distinguer le niveau `URGENT`, `BLOQUANT`, `À RISQUE`, `À SURVEILLER` et l’état de l’information. |
| **Explication immédiate** | Toute ligne à impact comporte `Pourquoi ?`, une source, l’affaire concernée et une prochaine action. |
| **Lecture d’abord, détail sur demande** | La page donne une synthèse en quelques secondes ; les sources, hypothèses et tables détaillées ne s’ouvrent qu’au besoin. |
| **Action humaine explicite** | Le Cockpit ne valide pas automatiquement une décision, un prix ou un dépôt. Il ouvre le bon Dossier de décision ou la bonne vue de travail. |
| **Aucune perte de contexte** | Toute navigation vers une affaire conserve le retour au Cockpit avec les filtres actifs. |
| **État visible** | La page indique lorsqu’elle est partielle, obsolète ou en cours d’actualisation. |
| **Accessible sans survol** | Les explications indispensables sont visibles ou accessibles par clic/clavier ; le survol est un confort, jamais la seule source d’information. |

---

## 4. Maquette fonctionnelle — écran ordinateur

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ SMART_AO | DUPONT BÂTIMENT                                🔔 4 | Noor ▾                │
├───────────────┬────────────────────────────────────────────────────────────────────────┤
│ ▣ Cockpit     │ Bonjour Noor. 3 actions demandent votre décision.                       │
│ ▤ Affaires    │ [Traiter mes actions]                         [Créer une affaire]        │
│ ◉ Opportunités├────────────────────────────────────────────────────────────────────────┤
│ ▦ Entreprise  │ PRIORITÉ DU JOUR                                                       │
│ ▤ Bibliothèque│ Réhabilitation Centre médical — Lot Gros œuvre                           │
│ € Chiffrage   │ Dépôt le 18/09 à 12:00 · DPGF à valider · 1 inconnue bloquante           │
│ ♟ Équipe      │ [Ouvrir le dossier de décision] [Pourquoi ?]                            │
│ ⚙ Réglages    ├────────────────────────────────────────────────────────────────────────┤
│               │ À TRAITER PAR MOI                                                       │
│               │ [Urgent 1] [Bloquant 2] [À risque 4] [À surveiller 6] [Toutes 13]        │
│               │ ┌────────────────────────────────────────────────────────────────────┐ │
│               │ │ URGENT · Dépôt · Centre médical — Lot 01 · dans 26 h                │ │
│               │ │ Prix officiel à autoriser · source : version DCE 03                  │ │
│               │ │ [Traiter] [Pourquoi ?]                                               │ │
│               │ ├────────────────────────────────────────────────────────────────────┤ │
│               │ │ BLOQUANT · Document · École Victor Hugo · attestation de visite    │ │
│               │ │ Pièce non reçue · responsable préparation : Salma                    │ │
│               │ │ [Ouvrir] [Demander une pièce]                                       │ │
│               │ └────────────────────────────────────────────────────────────────────┘ │
│               ├────────────────────────────────────────────────────────────────────────┤
│               │ AFFAIRES À SUIVRE              | PROTÉGER L’ENTREPRISE                 │
│               │ • 4 prêtes à chiffrer           | • 1 assurance expire dans 45 jours  │
│               │ • 2 en attente de décision      | • 2 rectificatifs à revoir          │
│               │ [Voir les affaires]             | [Voir les protections]              │
│               ├────────────────────────────────────────────────────────────────────────┤
│               │ OPPORTUNITÉS                      | ACTIVITÉ RÉCENTE                    │
│               │ • 5 à examiner                    | • Prix validé — 09:42               │
│               │ • 2 transmises                    | • Rectificatif reçu — 08:17         │
│               │ [Examiner]                        | [Ouvrir le journal]                 │
└───────────────┴────────────────────────────────────────────────────────────────────────┘
```

La barre latérale est persistante sur écran large. Sur tablette et mobile, elle devient un bouton `Menu` ; l’ordre des blocs reste le même et la priorité du jour reste placée avant tout autre contenu.

---

## 5. Découpage des zones du Cockpit

| Code | Zone | Question à laquelle elle répond | Priorité visuelle |
|---|---|---|---|
| `CP-01` | Bandeau d’arrivée | « Où suis-je et quelle est ma prochaine action ? » | Toujours en haut. |
| `CP-02` | Priorité du jour | « Quelle action unique ne dois-je pas repousser ? » | Visible sans défilement. |
| `CP-03` | File d’Actions patron | « Quelles décisions ou validations ne peuvent être traitées que par moi ? » | Zone centrale principale. |
| `CP-04` | Affaires à suivre | « Quelles affaires nécessitent un regard patron ? » | Bloc secondaire gauche. |
| `CP-05` | Protéger l’entreprise | « Qu’est-ce qui menace délais, preuves, marge ou droits ? » | Bloc secondaire droit. |
| `CP-06` | Opportunités | « Quelles opportunités méritent un investissement de temps ? » | Tertiaire, jamais avant une urgence. |
| `CP-07` | Activité récente | « Qu’est-ce qui a changé depuis ma dernière consultation ? » | Tertiaire, lecture courte. |
| `CP-08` | État de la vue | « Les informations sont-elles complètes et actuelles ? » | Discret mais toujours accessible. |

---

## 6. CP-01 — Bandeau d’arrivée et actions rapides

### 6.1. Informations affichées

| Élément | Règle | Source préparée |
|---|---|---|
| Salutation | Prénom du patron ou nom d’entreprise si le prénom est absent. | Compte patron. |
| Résumé d’action | Nombre d’actions `A_TRAITER` ou `PRISE_EN_COMPTE` relevant du patron. | Situation `patron_action_queue`. |
| État de fraîcheur | `À jour`, `Actualisation en cours`, `Partielle` ou `À vérifier`. | Métadonnées de projection. |
| Notification | Badge comptant seulement les notifications non lues et pertinentes. | Situation `notification_inbox`. |

### 6.2. Boutons

| Bouton | Commande ou navigation | Comportement | Cas de refus |
|---|---|---|---|
| `Traiter mes actions` | Navigation vers la File d’Actions avec filtre actif. | Ouvre tous les éléments actifs, triés par niveau, échéance puis impact. | Si la projection est indisponible : message et réessai, sans redirection vide. |
| `Créer une affaire` | Ouvre le parcours minimal de création d’affaire. | Aucune affaire n’est créée avant confirmation du formulaire. | Si entreprise inactive ou droits absents : expliquer le blocage. |
| `Voir les notifications` | Ouvre la boîte de notification. | Marquer comme lue exige une action distincte. | Ne pas masquer une action métier parce qu’une notification est lue. |

---

## 7. CP-02 — Priorité du jour

### 7.1. Règle de sélection

La priorité du jour est une **seule action** issue de la file d’Actions patron. Elle n’est pas un calcul opaque. L’ordre de sélection est le suivant :

1. action `URGENT` et `BLOQUANT` ;
2. action `URGENT` ;
3. action `BLOQUANT` dont l’échéance est la plus proche ;
4. action `À RISQUE` avec impact majeur et échéance connue ;
5. aucune priorité, si aucune action ne remplit ces critères.

En cas d’égalité, le Cockpit privilégie l’échéance la plus proche, puis l’affaire qui approche du dépôt, puis l’ancienneté de l’action. Ces règles sont affichables dans `Pourquoi cette priorité ?`.

### 7.2. Contenu obligatoire

| Champ | Règle d’affichage |
|---|---|
| Niveau de traitement | Texte et icône : `URGENT`, `BLOQUANT`, `À RISQUE` ou `À SURVEILLER`. |
| Type | Prix, dépôt, document, décision, partenaire, risque, capacité, droit ou trésorerie. |
| Affaire/ressource | Lien vers l’affaire ou la ressource concernée. |
| Phrase de cause | Une phrase simple : « DPGF à valider avant le dépôt » ; jamais un code interne. |
| Échéance | Date/heure avec fuseau applicable, ou « échéance non confirmée ». |
| Impact | Délais, preuves, marge, droits, capacité ou trésorerie. |
| État d’information | Confirmé, à vérifier, manquant, contradictoire, expiré ou non applicable. |
| Dernière mise à jour | Horodatage et origine du dernier fait influençant l’action. |

### 7.3. Boutons

| Bouton | Règle |
|---|---|
| `Traiter` | Ouvre la vue adéquate : Dossier de décision, Prix privé, Coffre de dépôt, preuve ou action détaillée. |
| `Pourquoi ?` | Ouvre un panneau latéral avec causes, sources, versions, conséquences et action attendue. |
| `Ouvrir l’affaire` | Ouvre la Vue de direction, sans perdre le retour au Cockpit. |
| `Déléguer une préparation` | Disponible seulement si la nature de l’action le permet ; ne délègue jamais la décision patron elle-même. |

---

## 8. CP-03 — File d’Actions patron

### 8.1. Finalité

Cette zone est le cœur du Cockpit. Elle présente les actions qui exigent une décision, validation ou arbitrage du patron. Les cartes historiques « À décider », « À chiffrer », « À déposer » et « À protéger » sont des **filtres** d’une même file ; elles ne constituent pas quatre systèmes séparés.

### 8.2. Filtres persistants

| Filtre | Valeurs | Effet |
|---|---|---|
| Niveau | Urgent, bloquant, à risque, à surveiller, tous. | Filtre sur le niveau de traitement, pas sur l’état de l’information. |
| Domaine | Décision, prix, dépôt, document, partenaire, risque, capacité, droit, trésorerie. | Regroupe par type d’arbitrage. |
| Affaire | Toutes ou une affaire précise. | Ne masque pas les actions entreprise hors affaire. |
| État | À traiter, prise en compte, attente tiers, attente information, sous conditions. | Les actions closes sont exclues par défaut. |
| Période | Aujourd’hui, 7 jours, 30 jours, période libre. | Porte sur échéance si elle est connue. |
| Impact | Délais, preuves, marge, droits, capacité, trésorerie. | Permet une revue ciblée. |

Un filtre appliqué est visible, supprimable individuellement et conservé au retour depuis une affaire. Une action filtrée ne doit jamais disparaître parce qu’elle est devenue plus urgente : le système signale un changement de résultat.

### 8.3. Ligne d’action

| Colonne | Contenu requis |
|---|---|
| Niveau | Niveau et indicateur de blocage. |
| Action | Nom humain : « Valider le prix officiel ». |
| Affaire | Nom, lot et lien lorsque l’action concerne une affaire. |
| Pourquoi | Cause résumée et nombre de causes regroupées. |
| Échéance | Date/heure ou statut inconnu. |
| Impact | Famille(s) d’impact. |
| État | État de cycle de l’action. |
| Responsable préparation | Personne ou tiers attendu, s’il existe. |
| Action suivante | Bouton unique prioritaire. |

### 8.4. Actions disponibles depuis une ligne

| Action d’interface | Commande métier sous-jacente | Préconditions visibles |
|---|---|---|
| `Ouvrir` | Aucune mutation ; navigation. | Ressource toujours accessible au patron. |
| `Prendre en compte` | `AcknowledgePatronAction`. | Action active, patron autorisé. |
| `Déléguer une préparation` | `DelegateActionPreparation`. | Nature délégable, collaborateur actif, échéance/date de retour définie. |
| `Demander une pièce` | `RequestEvidence`. | Destinataire et périmètre de partage définis. |
| `Décider` | Navigation vers `DEC`. | Dossier de décision préparé ou ouverture avec état partiel explicite. |
| `Reporter sous conditions` | `SetActionConditions`. | Conditions, responsables et dates/motifs complets. |
| `Clôturer` | `CompletePatronAction`. | Résultat vérifiable ou motif d’abandon. |

---

## 9. CP-04 — Affaires à suivre

Le bloc n’affiche pas tout le portefeuille. Il montre au maximum cinq affaires nécessitant un regard patron, avec un lien explicite vers la vue complète des affaires.

| Champ | Règle |
|---|---|
| Nom / acheteur / lot | Identité courte sans troncature ambiguë ; le détail reste accessible. |
| État de l’affaire | États du Contrat de domaine `AFF`, traduits en libellé métier. |
| Prochaine action patron | Une seule phrase, issue de l’Action patron prioritaire. |
| Échéance | Date/heure et niveau de proximité, ou « non confirmée ». |
| Responsable | Patron ou collaborateur actif assigné. |
| Blocage | Visible seulement s’il existe ; jamais sous forme de pourcentage. |
| Décision active | Go, Go sous conditions, No-Go, à décider, prix validé, dépôt autorisé, etc. |

| Bouton | Comportement |
|---|---|
| `Ouvrir` | Ouvre la Vue de direction de l’affaire. |
| `Voir les affaires` | Ouvre le portefeuille en conservant le filtre « exige attention patron ». |
| `Traiter` | Ouvre directement l’action active prioritaire de l’affaire. |

---

## 10. CP-05 — Protéger l’entreprise

Ce bloc organise les éléments risquant de faire perdre du temps, de l’argent ou des droits. Il ne fusionne pas les risques avec les actions : une même action peut traiter plusieurs risques et un risque peut ne demander aucune décision patron immédiate.

### 10.1. Les quatre familles

| Famille | Exemples | Indicateur affiché |
|---|---|---|
| **Délais** | Date limite, visite, réponse acheteur, échéance fournisseur, démarrage marché. | Nombre d’éléments urgents/bloquants. |
| **Preuves** | Attestation, assurance, qualification, référence, pièce de visite. | Éléments expirés/manquants/à vérifier. |
| **Marge** | Poste non couvert, devis absent, clause risquée, hypothèse fragile. | Éléments à examiner, sans montant détaillé global. |
| **Droits** | Pénalité, retenue, dérogation, réserve, variation, accusé de dépôt. | Risques ouverts et actions attendues. |

### 10.2. Règles d’affichage

Chaque élément indique sa famille, sa source, son affaire si applicable, son état, son impact, l’action ou protection associée et sa dernière mise à jour. Le clic ouvre le registre filtré, jamais une fenêtre qui prétend donner un avis juridique définitif.

---

## 11. CP-06 — Opportunités à examiner

Le Cockpit affiche uniquement les opportunités `A_EXAMINER` ou `TRANSMISES` qui correspondent aux profils actifs et qui possèdent une date limite connue ou une raison stratégique explicable.

| Champ | Règle |
|---|---|
| Objet / acheteur / lot / lieu | Informations issues de la source publique ou de la saisie patron. |
| Correspondance | Liste des critères correspondants et non correspondants, jamais un score seul. |
| Alertes | Visite, délai, qualification apparente, charge, zone ou donnée incomplète. |
| Fraîcheur | Date/heure de la dernière observation de la source. |
| Prochaine action | Examiner, créer une affaire, transmettre ou écarter. |

La création d’une affaire est toujours une commande explicite ; une opportunité ne devient jamais une affaire par simple affichage dans le Cockpit.

---

## 12. CP-07 — Activité récente et Journal de vérité

Le bloc affiche les douze derniers faits métier utiles à la direction : DCE reçu, rectificatif, preuve ajoutée, action créée, prix validé, décision prise, paquet autorisé, accusé archivé, opportunité transmise ou affaire arrêtée.

| Élément | Règle |
|---|---|
| Date/heure | Affichage localisé avec fuseau de l’entreprise. |
| Phrase métier | Compréhensible sans jargon technique. |
| Auteur/origine | Patron, collaborateur, partenaire, système d’analyse ou calcul déterministe. |
| Affaire/ressource | Lien autorisé vers la ressource. |
| Conséquence | « Action créée », « À revoir », « Prix remplacé », etc. |
| Bouton | `Ouvrir dans le journal`. |

Aucun journal technique, erreur brute, identifiant de base de données ou secret ne peut apparaître dans cette zone.

---

## 13. CP-08 — États de la vue et gestion des cas limites

| État | Comportement requis |
|---|---|
| `À jour` | Horodatage de dernière actualisation disponible sur demande. |
| `Actualisation en cours` | Conserver la dernière vue valide ; afficher une information discrète et un rafraîchissement à la fin. |
| `Partielle` | Identifier les blocs indisponibles et expliquer que la page ne constitue pas une vision exhaustive. |
| `Obsolète` | Avertir que des événements plus récents existent ou qu’une source doit être relue ; proposer l’actualisation. |
| `Vide` | Message métier adapté : « Aucune action patron active » ou « Aucune affaire à suivre ». |
| `Erreur de chargement` | Ne pas afficher un zéro ; afficher l’indisponibilité et `Réessayer`. |
| `Droits insuffisants` | Réponse neutre : accès non autorisé, sans révéler la présence d’un prix ou d’une autre ressource privée. |

---

## 14. Responsive, accessibilité et performance perçue

| Sujet | Exigence |
|---|---|
| **Ordinateur** | Navigation latérale, priorité du jour et actions sans défilement vertical initial sur résolution standard. |
| **Tablette** | Navigation compacte, mêmes commandes, listes transformées en cartes lisibles. |
| **Mobile** | Priorité du jour puis file d’actions ; aucune information critique uniquement au survol. Les tableaux deviennent des cartes avec libellés. |
| **Clavier** | Ordre de tabulation visible ; `Entrée` active le bouton principal ; focus non masqué. |
| **Contraste** | La couleur ne suffit jamais à transmettre urgence, blocage ou état d’information. |
| **Chargement** | Squelettes identifiant chaque bloc plutôt qu’une page blanche ; aucun chiffre fictif pendant le chargement. |
| **Rafraîchissement** | Le patron peut rafraîchir explicitement ; la page signale les changements reçus depuis sa dernière consultation. |

---

## 15. Projection de lecture requise : `CockpitPatron`

Le Cockpit lit une projection préparée et non les objets de domaine directement. Cette projection fournit uniquement des données autorisées au patron et porte un état de fraîcheur.

| Bloc de projection | Contenu minimal | Origines de domaine |
|---|---|---|
| `priority_action` | Action, raisons, échéance, impact, affaire, état information, liens de provenance. | `ACT`, `AFF`, `DEC`, `DCE`, `PRX`, `DEP`. |
| `action_queue` | Actions actives filtrables, causes regroupées, responsable, état et action suivante. | `ACT`, `ASN`, `AFF`. |
| `affairs_requiring_attention` | Identité, état, action prioritaire, échéance, blocage, responsable, décision active. | `AFF`, `ACT`, `DEC`, `DCE`. |
| `protection_summary` | Délais, preuves, marge, droits ; éléments ouverts et liens. | `AFF`, `PRF`, `PRX`, `DEP`, risques. |
| `opportunities_to_review` | Opportunité, profil, correspondances, alertes et fraîcheur. | `OPP`. |
| `company_readiness` | Documents, qualifications, capacités, partenaires et état de préparation. | `ORG`, `PRF`. |
| `recent_activity` | Faits métier sélectionnés et lisibles. | Faits métier transverses. |
| `view_status` | Version/horodatage, état, blocs indisponibles, changement détecté. | Infrastructure de projection, sans exposition technique. |

---

## 16. Critères de recette du Cockpit Patron

| ID | Scénario de recette | Résultat attendu |
|---|---|---|
| `CP-R01` | Le patron se connecte avec une action dépôt urgente et bloquante. | Cette action est la Priorité du jour, avec source, échéance et bouton `Traiter`. |
| `CP-R02` | Deux causes distinctes créent le même arbitrage de prix. | Une seule action affichée, contenant les deux causes. |
| `CP-R03` | Le collaborateur tente l’URL Cockpit. | Accès refusé sans contenu patron ni indication de prix. |
| `CP-R04` | Un rectificatif DCE est reçu après validation de prix. | Le Cockpit affiche une action `À revoir`, sans effacer la décision historique. |
| `CP-R05` | Aucune action patron active n’existe. | Message calme et liens vers portefeuille/opportunités ; aucune alerte factice. |
| `CP-R06` | Une projection est partielle. | Les blocs concernés indiquent `Partielle` ; aucun compteur à zéro trompeur. |
| `CP-R07` | Une assurance expire. | Elle apparaît dans Protéger l’entreprise avec date, source, usage et action de renouvellement. |
| `CP-R08` | Une opportunité ne correspond que partiellement au profil. | Critères correspondants et non correspondants sont affichés ; aucun score opaque seul. |
| `CP-R09` | Le patron ouvre `Pourquoi ?` sur une action. | Il voit causes, versions, sources, responsable, impact et action attendue. |
| `CP-R10` | Une commande de validation est exécutée puis la page se rafraîchit. | L’action évolue selon le fait métier, sans doublon ni disparition incohérente. |

---

## 17. Hors périmètre explicite

Le Cockpit ne remplace ni le chiffrage détaillé, ni l’analyse DCE, ni le coffre de dépôt, ni la comptabilité, ni un conseil juridique. Il redirige vers la vue appropriée avec un contexte conservé. Il ne peut pas prendre une décision, envoyer un dépôt, accepter une marge ou qualifier un document à la place du patron.

---

## 18. Conditions de gel

Le développement du Cockpit Patron peut commencer lorsque les conditions suivantes sont confirmées :

1. Le Contrat de domaine V8 est validé.
2. La projection `CockpitPatron` respecte les droits patron et ne contient aucune donnée financière globale inutile.
3. Chaque bouton du Cockpit est relié à une commande normalisée ou à une navigation sans effet de bord.
4. Les états `à jour`, `partielle`, `obsolète` et `erreur` sont conçus avant le style graphique.
5. Les dix critères de recette ci-dessus sont convertis en tests d’acceptation avant la première version utilisable.

---

## Références internes

- `SMART_AO_V8_CAHIER_ESPACE_PATRON.md`
- `SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE.md`
- `SMART_AO_V8_MATRICE_TRANSITIONS_METIER.md`
- `SMART_AO_V8_CONTRAT_DE_DOMAINE.md`

---

**Fin du Cahier des charges Cockpit Patron — version 1.0**
