# SMART_AO V8 — CASE-DCE-READ-01 : premier wizard collaborateur

**Statut :** proposition métier et interface à valider avant conception React et API.  
**Périmètre :** le premier écran réellement utilisable par un collaborateur affecté à une affaire.  
**Contrat de sécurité associé :** `SMART_AO_V8_CASE_DCE_READ_01_CONTRAT.md`.

## 1. Promesse de l’écran

Le collaborateur n’ouvre pas une bibliothèque documentaire, une table de base de données ou un cockpit patron. Il ouvre **son affaire**, voit l’étape à traiter et peut examiner les signaux du DCE qui nécessitent une action humaine.

> « Je sais quelle affaire je traite, ce qui a été repéré dans le DCE, où le vérifier et si je dois le retenir ou demander une revue. »

Cette première version s’arrête volontairement avant la préparation des pièces, le mémoire, le chiffrage et le dépôt. Elle installe cependant la structure du wizard qui accueillera ces étapes ultérieures.

## 2. Parcours visible V0

```text
Mes affaires
    ↓
Ouvrir une affaire affectée
    ↓
1. Lire le dossier et ses signaux
    ↓
Confirmer pour préparation  OU  Demander une revue
    ↓
Retour à la liste des éléments restants
```

La barre de progression affiche les étapes métier futures, mais seule l’étape `1. Lecture DCE` est active dans ce slice. Les étapes suivantes sont visibles comme **à venir**, sans bouton actif : `Terrain & capacités`, `Pièces`, `Réponse technique`, `Contrôle`, `Transmission`.

Cette décision évite deux erreurs : simuler des fonctionnalités inexistantes et faire croire que le collaborateur a validé une affaire complète alors qu’il a seulement revu des signaux sourcés.

## 3. Vue A — « Mes affaires »

### But

Offrir un point d’entrée personnel et filtré. Le collaborateur ne voit ni le portefeuille du patron, ni les autres affaires du tenant, ni des montants.

| Zone | Informations autorisées | Action | Interdit |
|---|---|---|---|
| À traiter maintenant | Affaire, lot/périmètre, état `Lecture DCE`, prochain élément à revoir, échéance seulement si elle est déjà sourcée. | `Ouvrir l’affaire`. | Montant, marge, score commercial, Go/No-Go. |
| Mes affaires affectées | Libellé, acheteur si non sensible, lot, statut de lecture, compteurs de signaux et de revues. | Filtrer puis ouvrir une affaire affectée. | Toute affaire sans affectation active. |
| En attente de revue | Nombre d’éléments marqués `REVIEW_REQUIRED`. | Filtrer les éléments concernés. | Nom, décision ou commentaire privé du patron. |
| Aide | Rappel : source avant conclusion. | Ouvrir la règle d’usage. | Conseils juridiques ou financiers. |

### États d’une affaire dans ce premier wizard

| État visible | Définition honnête | Ce qu’il ne faut pas en déduire |
|---|---|---|
| `À ouvrir` | Une Case affectée possède une DCE applicable disponible à la lecture. | Le DCE est complet ou l’affaire est recevable. |
| `Lecture en cours` | Au moins une exigence est encore sans confirmation humaine. | Le collaborateur est en retard ou le dossier est incomplet. |
| `À revoir` | Une ou plusieurs exigences ont `REVIEW_REQUIRED`. | Une contradiction est résolue ou une décision patron existe. |
| `Lecture préparée` | Toutes les exigences rendues par la vue ont reçu une qualification humaine autorisée. | Le dossier est conforme, complet, chiffré ou prêt à transmettre. |
| `Information indisponible` | La Case n’a pas de DCE applicable exploitable, ou l’analyse n’est pas prête. | Il n’existe aucun DCE ou aucune obligation. |

## 4. Vue B — « Lecture DCE de l’affaire »

### Bandeau stable

Le bandeau est présent sur toutes les vues du wizard afin que le collaborateur ne perde jamais son contexte.

```text
← Mes affaires
Réhabilitation école Victor-Hugo — Lot Gros œuvre
Étape 1 sur 7 : Lecture DCE
DCE : analyse disponible · 9 éléments à examiner · 2 à revoir
[Pourquoi cette étape ?] [Signaler un blocage]
```

Le libellé d’affaire est un libellé de travail non financier. Le bandeau ne contient ni budget, ni estimation, ni prix fournisseur, ni marge, ni décision de répondre.

### Barre wizard

```text
[1 Lecture DCE] — [2 Terrain & capacités] — [3 Pièces] — [4 Réponse technique]
[5 Contrôle] — [6 Transmission]
```

| Élément | Règle de comportement |
|---|---|
| `1 Lecture DCE` | Actif ; seul onglet cliquable du premier incrément. |
| Étapes 2 à 6 | Affichées avec le label `À venir`. Elles ne sont ni cliquables, ni évaluées, ni utilisées dans un calcul d’avancement. |
| Compteur | Affiche seulement les éléments rendus par l’API : `à confirmer`, `à revoir`, `confirmés`. |
| Freshness | Si la DCE est supersédée, affiche `Rectificatif / version à revoir` et bloque toute illusion de travail achevé. |

### Liste de travail

Une ligne correspond à une exigence atomique source DCE. La liste est filtrable, mais un filtre ne change jamais le statut durable.

| Colonne | Valeur présentée | Règle métier |
|---|---|---|
| À examiner | Intitulé construit à partir du type fermé : par exemple `Visite de site`, `Pièce de candidature`, `Contrainte de fichier`. | Pas de titre LLM ou de texte juridique inventé. |
| Catégorie | Type d’exigence fermé. | Aucun libellé financier détaillé au collaborateur. |
| Signal | `Required`, `Optional` ou `Unspecified`, présenté comme **signal source**. | Ne devient jamais « obligatoire juridiquement » par l’UI. |
| État de travail | `À confirmer`, `Confirmée`, `À revoir`, `Non applicable` si produit par le patron. | Ne signifie jamais conformité. |
| Source | Famille de pièce et locator borné, par exemple `RC · page 8`. | Aucun extrait complet, fichier original ou clé privée. |
| Action | `Confirmer`, `Demander une revue`, `Voir la source`. | Le collaborateur ne voit pas `Non applicable`. |

### Panneau détail d’exigence

Le clic sur une ligne ouvre un panneau latéral ou une vue dédiée, jamais une fenêtre flottante opaque.

```text
VISITE DE SITE
Signal DCE : requis selon la source
Source : RC · page 8
État : à confirmer

Que faites-vous ?
[Confirmer pour préparation]  [Demander une revue]

Aide : cette action ne valide ni une conformité, ni un prix, ni un dépôt.
```

Le panneau ne contient pas encore de texte libre. Le motif fermé de l’action est proposé par la vue : `Source revue` pour la confirmation, `Source ambiguë` ou `Clarification nécessaire` pour une demande de revue. Un futur slice de question acheteur ajoutera une rédaction guidée et persistée séparément.

## 5. Règles d’interaction et erreurs honnêtes

| Situation | Message utilisateur | Conséquence technique |
|---|---|---|
| Pas d’affectation active | `Cette affaire n’est plus accessible dans votre espace.` | Réponse neutre ; aucun détail de policy. |
| DCE non exploitable | `La lecture n’est pas encore disponible pour cette affaire.` | Aucun faux état vide ; bouton de relance absent pour le collaborateur. |
| DCE rectifiée/supersédée | `Une version plus récente doit être revue avant de poursuivre.` | État visible ; actions de confirmation bloquées si contrat backend le prévoit. |
| Conflit de révision | `Cet élément a été mis à jour. La liste a été actualisée.` | Recharger la vue ; ne pas rejouer silencieusement l’action. |
| Refus de policy | `Action non autorisée.` | Message minimal et audit côté serveur. |
| Réseau indisponible | `L’action n’a pas été enregistrée. Vérifiez la connexion avant de réessayer.` | Aucun succès affiché avant receipt serveur. |

## 6. Séparation patron/collaborateur à l’écran

| Élément | Collaborateur | Patron |
|---|---|---|
| Lecture d’une affaire | Seulement Case affectée et scope autorisé. | Toute Case de son tenant, selon policy. |
| `Confirmer pour préparation` | Oui, si affecté. | Oui. |
| `Demander une revue` | Oui, si affecté. | Oui. |
| `Non applicable` | Jamais présenté. | Action séparée, justifiée et auditée. |
| Prix, marge, budget, devis | Jamais chargé dans le navigateur. | Hors du présent wizard ; futur cockpit dédié. |
| Go/No-Go et dépôt | Jamais présenté comme action. | Hors du présent wizard ; futur périmètre patron. |

## 7. Mesures de réussite du premier wizard

Le premier wizard est considéré utile seulement si un collaborateur affecté peut ouvrir une affaire, comprendre pourquoi chaque signal est affiché, retrouver une source bornée, confirmer ou demander une revue, interrompre puis reprendre sans perte, et transmettre aucun prix ni élément confidentiel au navigateur.

Il n’est pas considéré terminé parce qu’il affiche une barre de progression, des compteurs colorés ou une liste vide. Les preuves de sortie sont les tests de policy, les tests HTTP, les tests de non-fuite de DTO, les tests de révision/idempotence et une revue métier sur un DCE de référence autorisé.

## 8. Éléments explicitement différés

Les étapes `Terrain & capacités`, `Pièces`, `Réponse technique`, `Contrôle` et `Transmission` sont visibles comme trajectoire produit mais ne doivent recevoir ni modèle durable, ni bouton actif, ni faux compteur dans ce slice. Elles seront ouvertes uniquement après le retour d’expérience du premier écran de lecture DCE opérationnelle.
