# SMART_AO V8 — Cahier métier de l’espace collaborateur

**Version :** 1.0  
**Statut :** premier document de référence du noyau opérationnel SMART_AO, à valider avant les contrats d’interface et de domaine complémentaires  
**Auteur :** Manus AI  
**Périmètre :** travail des salariés affectés à une affaire, depuis la réception de l’affectation jusqu’à la transmission structurée au patron pour décision, chiffrage et dépôt.

---

## 1. Pourquoi l’espace collaborateur est le cœur de SMART_AO

Le patron décide, chiffre, arbitre et autorise. Le collaborateur prépare le terrain sur lequel le patron peut décider sans perdre de temps : il reçoit une affaire, organise les pièces, lit le DCE, vérifie ce qui est demandé, rassemble les preuves, identifie les inconnus, prépare les éléments techniques et administratifs, consulte les personnes autorisées puis transmet un dossier clair.

SMART_AO ne doit pas demander au collaborateur de naviguer dans un ERP, de mémoriser une méthode ou de reconstituer un dossier dans des e-mails et des dossiers Windows. Il doit lui présenter **la prochaine tâche utile**, le document concerné, la preuve attendue, la source, le délai et la personne à qui remonter un blocage.

> **Promesse de l’espace collaborateur :** « Je sais quelle affaire je dois traiter, où j’en suis, ce qu’il faut vérifier, ce qui manque, ce que je peux préparer et ce que je dois transmettre au patron. »

Les métiers BTP concernés par ce parcours combinent souvent, selon la taille de l’entreprise, l’analyse du DCE, la constitution administrative, l’étude technique, la préparation de l’offre, la consultation de partenaires et la transmission structurée à la direction. [1] [2] [3] [4]

---

## 2. Utilisateurs couverts et limite de rôle

SMART_AO ne suppose pas que toutes les PME BTP disposent des mêmes intitulés de poste. Une même personne peut être chargée d’affaires, métreur, assistant études, conducteur de travaux ou assistante administrative. L’espace collaborateur s’adapte à cette réalité en attribuant des **responsabilités de préparation**, pas des statuts hiérarchiques rigides.

| Profil opérationnel | Ce qu’il prépare dans SMART_AO | Ce qu’il ne décide pas seul |
|---|---|---|
| **Chargé d’affaires / responsable d’affaires** | Opportunité, compréhension DCE, organisation de la réponse, mémoire, coordination de l’équipe et relation avec les parties autorisées. | Go/No-Go final, prix, marge, acceptation d’un risque patron, autorisation de dépôt. |
| **Chargé d’études de prix / métreur** | Pièces techniques, quantités, couverture des prestations, besoins fournisseurs, hypothèses techniques et alertes de chiffrage. | Coût de revient final, prix de vente, marge, règle de prix ou version officielle. |
| **Conducteur de travaux / référent chantier** | Faisabilité, moyens, phasage, durée, contraintes terrain, visite, sécurité, méthodologie et risques d’exécution. | Engagement commercial, prix, marge et dépôt. |
| **Assistant administratif** | Pièces de candidature, formulaires, attestations, références, classement, complétude et préparation de paquet. | Validation de pièce sensible, signature, déclaration engageante ou dépôt. |
| **Collaborateur polyvalent de PME** | Ensemble des tâches attribuées ci-dessus, selon l’affaire et ses compétences. | Toujours les mêmes frontières patron : prix privé, marge, décision finale et dépôt. |

Le rôle n’est donc pas une étiquette décorative. Pour chaque affaire, SMART_AO associe la personne, son périmètre de travail, les tâches attendues, les documents autorisés et les personnes auxquelles elle peut demander une information.

---

## 3. Ce que le collaborateur voit — et ce qu’il ne voit jamais

Le collaborateur travaille dans un espace personnel. Il voit uniquement les affaires attribuées, les tâches ouvertes, les documents nécessaires à son périmètre et les messages qui le concernent.

| Visible au collaborateur affecté | Invisible par défaut |
|---|---|
| Affaires attribuées et leur lot/périmètre. | Affaires non attribuées. |
| DCE, plans et annexes autorisés pour l’affaire. | Bibliothèque complète de l’entreprise. |
| Exigences, critères, tâches, échéances, risques et inconnus liés à son travail. | Prix de vente, coûts internes, déboursés, marges, trésorerie et fichiers de prix. |
| Documents à préparer, pièces manquantes, modèles autorisés et preuves à joindre. | Devis fournisseurs confidentiels, règles de chiffrage et scénarios patron. |
| Questions du patron, demandes de complément et décisions qui ont un impact sur ses tâches. | Dossier de décision patron complet, sauf résumé explicitement partagé. |
| État de l’affaire : préparation, retour demandé, prête à transmettre, etc. | Décision Go/No-Go, acceptation de risque ou prix final, tant que le patron ne partage pas l’information utile. |
| Son propre historique de travail et les tâches attribuées. | Portefeuille global, stratégie commerciale et données d’autres collaborateurs. |

> **Règle :** une information financière ou stratégique ne doit pas être « cachée visuellement » dans l’interface collaborateur. Elle ne doit jamais être préparée ni envoyée au navigateur du collaborateur.

Le patron peut exceptionnellement déléguer une information ou une tâche sensible à une personne de confiance. Cette délégation est limitée à une affaire, une durée, un périmètre précis et un historique.

---

## 4. Principes de travail du collaborateur

| Principe | Règle métier |
|---|---|
| **Une affaire à la fois** | L’écran principal privilégie la tâche actuelle et l’affaire la plus urgente ; il ne présente pas un tableau ERP chargé. |
| **Une tâche compréhensible** | Toute tâche répond à : quoi faire, pourquoi, où regarder, quelle preuve produire, pour quand et à qui remettre. |
| **Sauvegarde permanente** | Toute saisie utile est sauvegardée en brouillon ; le collaborateur peut s’interrompre et reprendre exactement où il en était. |
| **Source avant conclusion** | Une obligation, date, pénalité, critère ou contradiction doit être relié à une pièce, une page ou un extrait DCE consultable. |
| **Le doute est une information** | Le collaborateur peut signaler `à vérifier`, `manquant`, `contradictoire` ou `non compris` ; il ne doit jamais être obligé de deviner. |
| **Pas de raccourci silencieux** | Une étape non terminée ne peut pas être présentée comme terminée. Une dérogation patron est explicitement visible avec son motif. |
| **Le patron décide** | Le collaborateur prépare, propose, alerte et transmet. Il ne valide pas le prix, la marge, le Go/No-Go ou le dépôt. |
| **Le travail est réutilisable** | Une réponse, une référence, une méthode ou une preuve préparée peut être proposée dans une autre affaire, mais elle n’est jamais réutilisée sans contrôle du nouveau DCE. |

---

## 5. Le parcours métier complet d’une affaire côté collaborateur

Le parcours est un **wizard métier** : les étapes sont visibles, l’étape active est claire, les tâches obligatoires ne sont jamais dissimulées. Une affaire peut revenir à une étape antérieure après un rectificatif, une demande patron ou une nouvelle information. Le passage vers l’étape suivante ne dépend pas d’un simple clic ; il dépend de conditions observables.

```text
Affectation reçue
   ↓
1. Prendre connaissance de l’affaire
   ↓
2. Réceptionner et organiser le DCE
   ↓
3. Lire, confirmer et signaler les exigences
   ↓
4. Vérifier terrain, capacités et partenaires
   ↓
5. Préparer les pièces administratives et techniques
   ↓
6. Préparer le mémoire, les méthodes et les éléments de réponse
   ↓
7. Contrôler la complétude et transmettre au patron
   ↓
Retour patron / rectificatif / complément éventuel
```

| Étape | Question métier du collaborateur | Résultat durable attendu | Passage possible si… |
|---:|---|---|---|
| 0 | « Cette affaire est-elle bien la mienne et que me demande-t-on ? » | Affectation lue, périmètre compris ou question ouverte. | L’affaire et le rôle sont reconnus. |
| 1 | « Quels documents ai-je reçus et qu’est-ce qui manque ? » | Inventaire DCE, classement initial, fichiers illisibles/manquants signalés. | Les pièces disponibles sont admises et les absences déclarées. |
| 2 | « Qu’exige réellement l’acheteur ? » | Exigences, critères, dates, visites, pièces, lots, contradictions et inconnus sourcés. | Chaque pièce prioritaire a été lue ou déclarée à vérifier. |
| 3 | « Notre entreprise peut-elle préparer techniquement ce qui est demandé ? » | Capacités/preuves proposées, visite préparée, besoins partenaires et risques terrain. | Les besoins non couverts ont un responsable ou une alerte patron. |
| 4 | « Quelles pièces administratives et techniques dois-je compléter ? » | Checklist de réponse, brouillons, documents joints, manques et demandes de pièces. | Les éléments sous responsabilité collaborateur sont préparés ou explicitement bloqués. |
| 5 | « Comment démontrer une réponse spécifique et réalisable ? » | Mémoire technique structuré, méthodes, moyens, planning, références, variantes et engagements traçables. | Les critères du RC sont couverts ou signalés comme non couverts. |
| 6 | « Puis-je transmettre au patron un dossier honnête et exploitable ? » | Synthèse de transmission, points ouverts, risques, décisions attendues et paquet préparé. | Contrôle de complétude réalisé, aucune information critique cachée. |

Le collaborateur peut revenir aux étapes précédentes quand une information nouvelle le justifie. SMART_AO demande alors le motif : `rectificatif DCE`, `retour patron`, `document reçu`, `erreur corrigée`, `information partenaire`, `visite`, `autre`. La correction est historisée, sans effacer l’ancien état.

---

## 6. Écran d’accueil collaborateur — « Mon travail aujourd’hui »

L’utilisateur ne commence jamais par une page vide ou une liste de menus. Il arrive sur une page qui répond à trois questions : **quelle affaire est prioritaire, quelle tâche dois-je faire maintenant et qu’est-ce qui bloque mon travail ?**

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ SMART_AO | Mes affaires                                  🔔 3 | Salma ▾ │
├──────────────────────────────────────────────────────────────────────────┤
│ Bonjour Salma. Vous avez 2 tâches prioritaires aujourd’hui.              │
│                                                                            │
│ À FAIRE MAINTENANT                                                        │
│ Centre médical Filieris — Lot 01                                          │
│ Vérifier les pièces demandées par le RC · échéance interne : aujourd’hui  │
│ [Ouvrir la tâche]  [Voir l’affaire]                                       │
├──────────────────────────────────────────────────────────────────────────┤
│ MES AFFAIRES ACTIVES                 │ EN ATTENTE DE MOI                  │
│ • Centre médical — analyse DCE        │ • 1 document demandé au patron    │
│ • École Victor Hugo — mémoire         │ • 2 réponses partenaires attendues│
│ • Résidence Les Tilleuls — visite     │ • 1 retour patron à traiter        │
│ [Voir toutes mes affaires]            │ [Voir mes attentes]                │
├──────────────────────────────────────────────────────────────────────────┤
│ MES TÂCHES                            │ ACTIVITÉ RÉCENTE                   │
│ Aujourd’hui 2 · Cette semaine 6       │ Rectificatif reçu · 09:12           │
│ Bloquantes 1 · À vérifier 3           │ Tâche attribuée · hier              │
│ [Ouvrir mes tâches]                   │ [Voir l’historique]                │
└──────────────────────────────────────────────────────────────────────────┘
```

| Zone | Informations affichées | Actions permises |
|---|---|---|
| **À faire maintenant** | Une tâche prioritaire, affaire, raison, échéance interne et état. | Ouvrir la tâche, voir l’affaire, signaler un blocage. |
| **Mes affaires actives** | Affaires attribuées, étape réelle, prochaine tâche, date limite et état de transmission. | Ouvrir une affaire, filtrer, demander une réattribution. |
| **En attente de moi** | Réponse patron, pièce, partenaire ou correction requise. | Ouvrir la demande, répondre, signaler une relance. |
| **Mes tâches** | Comptage transparent par date et état ; pas de score de productivité caché. | Ouvrir la liste ou filtrer. |
| **Activité récente** | Faits liés aux seules affaires accessibles. | Ouvrir l’élément associé. |

Le collaborateur ne voit pas le Cockpit Patron. Son espace est une **file de travail personnelle**, pas une version dégradée du tableau de bord direction.

---

## 7. La liste « Mes affaires »

La liste ne doit contenir que les affaires auxquelles le collaborateur est actuellement ou historiquement affecté selon ses droits. Chaque ligne est un point d’entrée vers une affaire et non un espace de décision financière.

| Colonne | Contenu | Règle |
|---|---|---|
| Affaire | Objet court, acheteur, lot/périmètre. | Toujours reconnaissable sans ouvrir la fiche. |
| Mon rôle | Chargé d’analyse, études, administratif, visite, mémoire, contrôle documentaire ou autre rôle attribué. | Peut être multiple mais explicite. |
| Étape actuelle | Libellé métier : `Organisation DCE`, `Analyse`, `Pièces`, `Mémoire`, `À transmettre`, etc. | Jamais un pourcentage décoratif seul. |
| Ma prochaine tâche | Une phrase et un bouton vers la tâche. | Toujours calculée à partir des tâches actives. |
| Échéance | Date limite acheteur si confirmée ; sinon date interne avec libellé. | Source et état disponibles. |
| Blocage | Pièce manquante, réponse attendue, contradiction, retour patron ou aucun. | Visible sans masquer le travail accompli. |
| Transmission | Non prête, en préparation, transmise, retour demandé, acceptée pour chiffrage. | Ne révèle pas la décision de prix. |

Filtres disponibles : `toutes`, `à faire aujourd’hui`, `bloquées`, `à transmettre`, `en attente du patron`, `en attente d’un tiers`, `dépôt proche`, `archivées`. Le collaborateur ne peut pas élargir un filtre aux affaires non attribuées.

---

## 8. La fiche collaborateur d’une affaire

L’affaire ouverte affiche un parcours court, pas une collection d’onglets concurrents. Le bandeau montre toujours l’affaire, le lot, la date limite, l’état d’information et la prochaine étape.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ ← Mes affaires                                                            │
│ Centre médical Filieris — Lot 01 Gros œuvre                               │
│ Date limite : 18/09/2026 12:00 · État : Analyse en cours                  │
│ Mon rôle : Analyse DCE et préparation technique                           │
├──────────────────────────────────────────────────────────────────────────┤
│ [1 Documents] — [2 Exigences] — [3 Terrain & capacités] — [4 Pièces]     │
│ [5 Réponse technique] — [6 Contrôle] — [7 Transmission]                  │
├──────────────────────────────────────────────────────────────────────────┤
│ Étape 2 : Exigences et critères                                           │
│ 14 éléments confirmés · 3 à vérifier · 1 contradiction · 2 pièces manquantes│
│                                                                            │
│ Tâche actuelle : Vérifier les modalités de visite                         │
│ Source : RC · p. 8 · « La visite est obligatoire… »                       │
│ [Confirmer] [Signaler une question] [Demander une pièce] [Voir la page]   │
└──────────────────────────────────────────────────────────────────────────┘
```

| Élément | Règle |
|---|---|
| **Chemin en sept étapes** | Chaque étape montre un état : non commencée, en cours, à vérifier, bloquée, prête à transmettre ou terminée. |
| **Données financières** | Aucune donnée de prix, marge, devis ou trésorerie dans le bandeau, les étapes ou les messages collaborateur. |
| **Retour patron** | Une demande patron apparaît comme une tâche clairement identifiée, avec délai et conséquence attendue. |
| **Rectificatif** | Le bandeau affiche immédiatement qu’une nouvelle version DCE concerne l’affaire et les étapes à revoir. |
| **Sauvegarde** | Le dernier enregistrement et le statut brouillon sont visibles. |
| **Aide** | Chaque action importante possède `Pourquoi ?`, `Voir la source`, `Exemple attendu` et `Signaler un doute`. |

---

## 9. Étape 1 — Réceptionner et organiser le DCE

### 9.1. But métier

Le collaborateur doit savoir ce qui a été reçu, ce qui est lisible, ce qui manque et ce qui peut être analysé. Il ne doit pas classer manuellement des dizaines de fichiers sans aide.

| Ce que SMART_AO présente | Ce que le collaborateur fait | Résultat durable |
|---|---|---|
| Inventaire des fichiers, nom original, format, taille, date de réception, statut antivirus et intégrité. | Confirme ou corrige le type de pièce proposé. | Pièce classée avec trace de la correction humaine. |
| Familles attendues selon le DCE : RC, AE, CCAP, CCTP, DPGF/BPU/DQE, plans, annexes, réponses. | Signale une absence, un doublon, un fichier illisible ou une pièce à demander. | Manque/incident documenté, tâche ou demande créée. |
| Aperçu et texte extrait avec page source. | Vérifie que la pièce est exploitable, demande OCR/revue si nécessaire. | État de lisibilité et confiance documentés. |
| Historique des versions. | Identifie un rectificatif ou une pièce remplacée. | Version DCE enregistrée, impacts à revoir préparés. |

### 9.2. Boutons autorisés

| Bouton | Action métier | Limite |
|---|---|---|
| `Confirmer le classement` | Confirme le type d’une pièce. | Ne modifie pas l’original. |
| `Signaler une pièce manquante` | Crée un signal manquant et, selon choix, une demande au patron. | Ne conclut pas que la pièce n’existe pas chez l’acheteur. |
| `Déclarer un fichier illisible` | Enregistre un problème de lecture, la page concernée et un commentaire. | Ne supprime pas le fichier. |
| `Comparer les versions` | Ouvre une comparaison source à source. | Ne décide pas seule de l’impact contractuel. |
| `Demander une revue` | Transmet au patron ou au référent une question ciblée. | Le collaborateur doit décrire ce qu’il ne comprend pas. |

---

## 10. Étape 2 — Comprendre les exigences du DCE

### 10.1. But métier

Le collaborateur transforme un dossier diffus en une liste contrôlable de ce que l’acheteur exige : dates, visites, pièces, critères, formats, contraintes techniques, variantes, options, pénalités, exigences environnementales, références et conditions de dépôt.

Le logiciel peut proposer des éléments après lecture des documents, mais le collaborateur les **confirme, corrige, classe ou marque comme incertains**. Une proposition automatique n’est jamais une exigence confirmée sans source.

### 10.2. Fiche d’exigence

| Champ | Description | Obligatoire quand… |
|---|---|---|
| Intitulé | Formulation courte : « Visite obligatoire ». | Toujours. |
| Nature | Administrative, technique, financière à transmettre au patron, planning, environnement, sécurité, dépôt, variante, partenaire, autre. | Toujours. |
| Action attendue | Fournir, faire, démontrer, respecter, demander une précision ou décider. | Toujours. |
| Source | Pièce, version, page, extrait ou zone de tableau/plan. | Toujours pour un élément issu du DCE. |
| Échéance | Date/heure, période ou « non confirmée ». | Dès qu’elle est identifiable. |
| Responsable proposé | Collaborateur, patron, partenaire, tiers ou non attribué. | Toujours ; `non attribué` devient une alerte. |
| État | Confirmée, à vérifier, manquante, contradictoire, expirée, non applicable. | Toujours. |
| Preuve attendue | Document, attestation, réponse, photo, visite, planning, référence, calcul ou autre. | Dès que l’exigence demande une démonstration. |
| Critère associé | Critère de notation ou exigence de recevabilité, s’il est connu. | Quand le RC le permet. |
| Commentaire collaborateur | Ce qui doit être compris ou signalé au patron. | Optionnel mais tracé. |

### 10.3. Actions disponibles

| Action | Effet | Ne fait pas |
|---|---|---|
| `Confirmer` | L’exigence devient confirmée avec source conservée. | Ne valide pas l’offre ou le prix. |
| `Marquer à vérifier` | Demande une relecture ou une confirmation. | Ne fait pas disparaître l’exigence. |
| `Signaler une contradiction` | Relie au moins deux sources incompatibles et crée une question. | Ne décide pas quelle pièce prévaut sans règle explicite. |
| `Associer une tâche` | Crée une tâche avec responsable et échéance. | Ne modifie pas l’exigence source. |
| `Associer une preuve` | Propose un document/capacité autorisé. | Ne confirme pas seul le droit d’usage si sensible. |
| `Demander une décision` | Crée une transmission vers patron lorsque nécessaire. | Ne transforme pas une proposition en décision. |

---

## 11. Étape 3 — Terrain, capacités et partenaires

Le collaborateur ne décide pas que l’entreprise est capable de répondre. Il rassemble les éléments permettant au patron de le vérifier : contraintes terrain, visite, méthodes possibles, moyens nécessaires, références disponibles, disponibilités équipe, besoins sous-traitants, questions fournisseur et risques techniques.

### 11.1. Fiche de visite et de terrain

| Rubrique | Informations à saisir ou vérifier |
|---|---|
| Organisation de visite | Obligatoire ou recommandée, date, lieu, contact, inscription, attestation attendue, accompagnant. |
| Accès et logistique | Accès chantier, stationnement, livraisons, horaires, coactivité, voisinage, zones sensibles. |
| Existant et diagnostics | Bâtiment occupé, amiante, plomb, réseaux, désordres, accès technique, pièces absentes. |
| Méthodes et séquences | Installation, phasage, protections, nuisances, travaux en site occupé, interfaces lots. |
| Moyens | Personnel, matériel, engins, levage, échafaudage, stockage, sous-traitance potentielle. |
| Risques | Sécurité, délai, technique, environnement, disponibilité, réception des fournitures. |
| Preuves | Photos autorisées, attestation, notes, croquis, document source. |
| Décisions à demander | Ce qui dépasse le rôle collaborateur : acceptation de risque, partenaire, option ou engagement. |

### 11.2. Capacités et preuves

L’écran propose les capacités de l’entreprise autorisées pour l’affaire : qualifications, références, équipes, matériels, modèles et partenaires. Le collaborateur peut les proposer, demander une confirmation ou signaler une absence. Il ne peut ni inventer une référence ni affirmer une qualification expirée comme valide.

| Situation | Action collaborateur | Résultat transmis |
|---|---|---|
| Capacité disponible et preuve actuelle | Proposer pour l’affaire. | Proposition sourcée au patron ou au relecteur. |
| Capacité disponible mais preuve expirée | Signaler l’expiration. | Tâche de renouvellement ou alerte patron. |
| Capacité supposée mais non prouvée | Marquer à vérifier. | Aucun engagement automatique. |
| Partenaire nécessaire | Créer une demande de consultation limitée. | Besoin, périmètre et date de retour. |
| Capacité absente | Déclarer le manque. | Risque ou décision patron à prendre. |

---

## 12. Étape 4 — Préparer les pièces administratives et techniques

Cette étape ne consiste pas à « générer tout sans contrôle ». SMART_AO présente la liste spécifique des pièces demandées par le RC, les annexes et les règles du DCE. Le collaborateur complète les éléments autorisés, prépare les brouillons, rattache les originaux et transmet les éléments nécessitant le patron ou un tiers.

| Famille | Travail collaborateur | Frontière patron ou tiers |
|---|---|---|
| **Candidature** | Vérifier la liste, sélectionner les pièces autorisées, compléter les champs non sensibles, signaler expiration/manque. | Signature, déclaration engageante, attestation officielle, validation finale. |
| **DUME / DC1 / DC2 / DC4** | Préparer les rubriques à partir de données autorisées, identifier sous-traitance/groupement, signaler champs inconnus. | Signature, affirmations légales, choix final de montage. |
| **Références / qualifications** | Choisir et proposer les preuves adaptées au lot et au critère. | Autorisation de partage si nécessaire ; validation d’usage sensible. |
| **Mémoire / méthodologie** | Préparer le contenu répondant aux critères, moyens, planning et engagements. | Validation des engagements, prix, promesses stratégiques. |
| **Plans / planning / PIC** | Rassembler, annoter, proposer ou demander les éléments nécessaires. | Validation technique par personne habilitée lorsque requise. |
| **Annexes spécifiques** | Traiter chaque annexe comme une tâche séparée, même si elle n’est pas dans une liste standard. | Validation ou production par le professionnel compétent. |

Chaque document possède un état : `non commencé`, `brouillon`, `en attente d’information`, `à relire`, `prêt à transmettre`, `retourné avec correction`, `validé pour paquet`, `non applicable`. La mention `validé pour paquet` ne signifie jamais « dépôt autorisé ».

---

## 13. Étape 5 — Préparer une réponse technique spécifique

La réponse technique est le travail où SMART_AO doit réellement aider le collaborateur à gagner du temps sans produire un texte générique. Le mémoire est organisé par les critères du RC et les réalités du chantier, pas par un modèle unique identique pour tous les marchés.

### 13.1. Structure du mémoire guidé

| Bloc | Questions guidées au collaborateur | Preuves ou sorties attendues |
|---|---|---|
| Compréhension du projet | Quel est l’objet, le contexte, les contraintes, les interfaces et les enjeux ? | Synthèse sourcée, éléments à confirmer. |
| Méthodologie | Comment les travaux seront-ils préparés, réalisés, contrôlés et réceptionnés ? | Méthodes réalistes, étapes, responsables. |
| Moyens humains | Quels profils sont mobilisés et pour quelles responsabilités ? | Organigramme, CV/références autorisés, rôles. |
| Moyens matériels | Quels matériels, protections, engins et installations sont nécessaires ? | Liste, disponibilité à vérifier, limites. |
| Planning et phasage | Comment respecter les délais, préparer, coordonner les interfaces et gérer les jalons ? | Planning proposé, hypothèses, risques délai. |
| Qualité, sécurité et environnement | Comment répondre aux exigences QHSE, déchets, nuisances, site occupé, insertion ou environnement ? | Mesures concrètes, preuves disponibles, actions nécessaires. |
| Références | Quelles réalisations comparables démontrent l’expérience demandée ? | Références autorisées, critères de similitude, pièces de preuve. |
| Variantes / PSE | Quelle solution alternative est demandée ou proposée, et quel est son impact technique ? | Distinction nette offre de base / variante / option. |

### 13.2. Règles d’authenticité

1. Le collaborateur ne peut pas considérer un texte comme final sans vérifier sa cohérence avec le DCE et les capacités de l’entreprise.
2. Toute promesse opérationnelle doit être liée à un responsable, un moyen, une preuve ou marquée comme hypothèse à arbitrer.
3. Une réponse réutilisée depuis une affaire ancienne affiche son origine, sa date et les éléments qui doivent être adaptés.
4. SMART_AO peut signaler une phrase trop générique, une promesse non prouvée ou un critère non couvert ; il ne prétend pas certifier qu’un mémoire fera gagner le marché.

---

## 14. Étape 6 — Contrôler et transmettre au patron

La transmission n’est pas un simple bouton « Terminé ». C’est un dossier structuré qui permet au patron de comprendre rapidement : ce qui est prêt, ce qui manque, ce qui nécessite une décision, ce qui est risqué et ce que le collaborateur propose.

### 14.1. Tableau de transmission

| Rubrique | Contenu obligatoire avant transmission |
|---|---|
| Situation de l’affaire | Lot, date limite, étape atteinte, responsable, dernière version DCE analysée. |
| DCE et pièces | Pièces reçues, pièces manquantes, rectificatifs, fichiers à vérifier. |
| Exigences | Confirmées, à vérifier, contradictoires, non applicables et non couvertes. |
| Documents de réponse | Prêts, brouillons, en attente, non applicables et responsables. |
| Technique | Mémoire, moyens, méthodes, planning, références, variantes et points ouverts. |
| Capacités / partenaires | Éléments proposés, disponibles, expirés, manquants ou à valider. |
| Risques | Délais, preuves, technique, sécurité, environnement, interfaces, partenaires. |
| Décisions attendues | Go/No-Go, partenaire, dérogation, engagement, chiffrage, dépôt ou autre. |
| Questions à l’acheteur | Questions rédigées, sources, importance et échéance proposée. |
| Limites de la préparation | Ce que le collaborateur n’a pas pu confirmer, avec raisons et demande suivante. |

### 14.2. Bouton `Transmettre au patron`

| Élément | Règle |
|---|---|
| Préconditions | Les étapes obligatoires sont terminées, bloquées avec motif ou déclarées non applicables ; la synthèse ne contient pas de champ critique vide sans statut. |
| Résultat | L’affaire passe à `ATTENTE_DECISION` ou `PRETE_A_CHIFFRER` selon le travail attendu ; une Action patron et un Dossier de décision préparé sont créés ou actualisés. |
| Visible au collaborateur | « Transmis le [date] à [patron]. En attente de retour. » |
| Visible au patron | Résumé, points ouverts, risques, preuves, exigences et décisions demandées ; aucune conclusion collaborateur n’est affichée comme décision patron. |
| Retour possible | Le patron peut demander une correction ciblée ; SMART_AO crée alors une tâche et replace l’affaire à l’étape concernée. |

---

## 15. La tâche : unité de travail du collaborateur

Une tâche est l’unité de travail réelle, pas une notification vague. Elle peut être créée par le parcours, une exigence, une demande patron, un rectificatif, une pièce manquante ou une réponse partenaire.

| Champ de tâche | Signification |
|---|---|
| Intitulé | Formulation claire : « Vérifier la visite obligatoire » ou « Préparer les références similaires ». |
| Affaire / étape | Ressource et étape du wizard concernées. |
| Pourquoi | Origine : exigence DCE, retour patron, rectificatif, document manquant ou règle entreprise. |
| Source | Pièce/page/extrait ou demande patron ; peut être vide seulement pour une tâche interne explicitement identifiée. |
| Action attendue | Vérifier, fournir, lire, préparer, demander, comparer, visiter, rédiger ou transmettre. |
| Responsable | Collaborateur assigné ; un responsable vide est une anomalie. |
| Échéance | Échéance acheteur, échéance interne ou état « à préciser ». |
| Importance | Urgent, bloquant, à risque, à surveiller. |
| Preuve de fin | Document, commentaire sourcé, confirmation, réponse partenaire, photo, attestation ou validation. |
| État | À faire, en cours, en attente patron, en attente tiers, à relire, terminée, abandonnée avec motif, remplacée. |

| Action collaborateur | Effet métier | Limite |
|---|---|---|
| `Prendre en charge` | La tâche passe en cours avec horodatage. | Ne retire pas les autres responsabilités patron. |
| `Signaler un blocage` | État, raison, pièce et besoin sont enregistrés ; une demande peut être créée. | Ne clôture pas la tâche. |
| `Demander une information` | Demande ciblée à un patron, collègue ou partenaire autorisé. | Partage limité au périmètre nécessaire. |
| `Proposer une preuve` | Rattache une preuve candidate à la tâche. | Ne valide pas l’usage si patron requis. |
| `Terminer` | Déclare le résultat et la preuve de fin. | Une tâche critique peut exiger revue avant statut terminé final. |
| `Demander une revue` | Transmet la tâche à un relecteur/patron. | N’est pas une décision finale. |

---

## 16. Communications et demandes sans chaos d’e-mails

Le collaborateur doit pouvoir demander une réponse sans disperser les informations dans sa messagerie personnelle. Les demandes restent rattachées à l’affaire, à l’exigence ou à la tâche concernée.

| Destinataire | Ce que le collaborateur peut demander | Informations partagées | Résultat attendu |
|---|---|---|---|
| Patron | Décision, pièce sensible, validation, information entreprise, arbitrage de risque. | Résumé, sources, question et délai ; jamais un accès à prix non nécessaire. | Réponse, tâche, décision ou retour correction. |
| Collègue affecté | Lecture, information technique, document autorisé, visite ou aide. | Seulement l’affaire/périmètre attribué. | Commentaire, pièce ou tâche partagée. |
| Partenaire externe | Disponibilité, document, qualification, méthode ou demande de prix limitée. | Périmètre explicitement autorisé par le patron. | Réponse partenaire, document ou indisponibilité. |
| Acheteur | Question formalisée à soumettre selon le RC. | Brouillon et sources ; envoi soumis à autorisation interne. | Question prête à envoyer ou réponse acheteur enregistrée. |

Toute demande porte une date, un auteur, un destinataire, une affaire, une raison et un état. Une réponse reçue est reliée à la demande initiale ; elle peut créer une tâche de revue ou une mise à jour d’exigence.

---

## 17. États d’information et alertes honnêtes

Le collaborateur ne doit pas avoir à contourner l’incertitude pour faire avancer son dossier. SMART_AO utilise les mêmes états dans toute l’affaire.

| État | Quand l’utiliser | Effet sur le parcours |
|---|---|---|
| **Confirmée** | Une information est sourcée et relue ou validée selon la règle. | Peut servir de base à une preuve ou tâche terminée. |
| **À vérifier** | Source ambiguë, lecture incomplète ou besoin de relecture humaine. | Crée une tâche ou empêche une transmission « prête » selon criticité. |
| **Manquante** | Pièce, information ou preuve attendue non disponible. | Crée demande/alerte ; ne se transforme pas en valeur par défaut. |
| **Contradictoire** | Deux sources ou versions donnent des réponses incompatibles. | Exige une comparaison et, si nécessaire, une question/décision. |
| **Expirée** | Document ou capacité connu mais date dépassée. | Ne peut pas être proposé comme preuve valide sans décision. |
| **Non applicable** | L’exigence ne concerne pas l’affaire, avec motif et source. | Sort de la checklist obligatoire mais reste justifiée. |

Les alertes sont séparées de ces états : `URGENT`, `BLOQUANT`, `À RISQUE`, `À SURVEILLER`. Une information peut être confirmée et urgente, ou manquante mais non bloquante.

---

## 18. Rectificatifs, retours patron et reprise du travail

### 18.1. Rectificatif DCE

Lorsqu’un rectificatif est ajouté, le collaborateur voit une bannière sur l’affaire :

> **« Une nouvelle version du DCE a été reçue le [date]. 4 éléments de votre préparation sont à revoir. »**

| Élément impacté | Comportement |
|---|---|
| Date, visite, dépôt ou format | Tâche urgente créée si changement confirmé. |
| Exigence modifiée | Ancienne exigence conservée, nouvelle version à relire. |
| Document préparé | Marqué `à revoir`, jamais supprimé. |
| Mémoire ou planning | Sections concernées identifiées lorsque la source est connue ; sinon état à vérifier. |
| Transmission patron | Patron averti si une décision, un prix ou un paquet pouvait être concerné. |

### 18.2. Retour patron

Un retour patron doit être spécifique : « Compléter les références similaires », « Revoir la visite », « Le DCE a changé », « Préparer les éléments pour chiffrage ». Le collaborateur reçoit une tâche, la source du retour et l’étape à reprendre. Il ne reçoit jamais un message vague « à refaire » sans motif.

---

## 19. Ce que le collaborateur remet réellement au patron

Le produit du travail collaborateur n’est pas un dossier opaque ou un ensemble de PDF. C’est un **dossier préparé de décision et de réponse**.

| Livrable | Finalité patron |
|---|---|
| Inventaire DCE et versions | Savoir quelles pièces fondent l’analyse et ce qui manque. |
| Fiche d’exigences sourcées | Voir obligations, critères, dates, pièces, visites, contradictions et responsables. |
| Registre des inconnus | Décider sans faux sentiment de certitude. |
| Registre des risques | Voir ce qui peut affecter délais, preuves, technique, environnement, partenaires ou marge. |
| Préparation administrative | Distinguer prêt, brouillon, manquant, expiré, à signer et non applicable. |
| Préparation technique | Mémoire structuré, méthodes, moyens, planning, références, variantes et engagements. |
| Demandes partenaires | Disponibilités, documents, informations et retours attendus. |
| Questions acheteur | Questions préparées avec source, urgence et raison. |
| Synthèse de transmission | Ce qui est prêt, ce qui est bloqué, ce qui est proposé, ce qui attend une décision patron. |
| Paquet préparé | Fichiers candidats, versions et contrôles réalisés ; jamais une déclaration de dépôt. |

---

## 20. Ce que SMART_AO ne doit pas faire dans l’espace collaborateur

| Interdit | Raison |
|---|---|
| Afficher un coût, une marge, un déboursé, un devis fournisseur ou une trésorerie privée. | Confidentialité patron et prévention des fuites. |
| Autoriser le dépôt, valider un prix ou prendre une décision Go/No-Go. | Ces actes appartiennent au patron ou à une délégation explicitement encadrée. |
| Marquer une exigence comme satisfaite sans preuve ou justificatif. | Risque de faux dossier complet. |
| Générer une réponse générique présentée comme adaptée au DCE. | Le mémoire doit rester spécifique, vérifiable et réalisable. |
| Effacer un document, une version, une exigence ou une tâche utilisée dans l’historique. | Traçabilité, rectificatifs et reconstruction des décisions. |
| Masquer une incertitude pour permettre le passage d’étape. | L’honnêteté opérationnelle prime sur une progression artificielle. |
| Envoyer un document à un partenaire sans périmètre autorisé. | Confidentialité entreprise, DCE et fournisseurs. |
| Déclarer un dépôt réalisé à partir d’un ZIP créé. | Le dépôt requiert une action externe et une preuve archivée. |

---

## 21. Critères de réussite de l’espace collaborateur

| ID | Scénario | Résultat attendu |
|---|---|---|
| `COL-R01` | Un collaborateur se connecte. | Il ne voit que ses affaires attribuées et ses tâches ; aucune donnée financière n’est présente dans les réponses. |
| `COL-R02` | Une tâche indique une visite obligatoire. | La source RC, l’échéance, l’attestation attendue et la prochaine action sont visibles. |
| `COL-R03` | Une annexe DCE est absente. | Le collaborateur peut la déclarer manquante, demander une pièce et poursuivre les éléments non bloqués. |
| `COL-R04` | Deux documents DCE donnent une règle incompatible. | Il peut signaler une contradiction avec les deux sources, sans devoir choisir seul. |
| `COL-R05` | Un collaborateur interrompt son travail. | À la reprise, il retrouve l’affaire, l’étape, la tâche et les brouillons exacts. |
| `COL-R06` | Un rectificatif est reçu après préparation du mémoire. | Les sections concernées sont `à revoir`, l’historique reste consultable et le patron est averti si nécessaire. |
| `COL-R07` | Une preuve entreprise est expirée. | Elle ne peut pas être proposée comme valide ; le collaborateur crée une alerte ou demande un renouvellement. |
| `COL-R08` | Le collaborateur termine son analyse. | Il transmet une synthèse structurée au patron ; aucune décision ni prix n’est automatiquement finalisé. |
| `COL-R09` | Le patron renvoie une demande de correction. | Une tâche ciblée apparaît avec son motif et l’étape concernée. |
| `COL-R10` | Un partenaire répond à une demande limitée. | La réponse est rattachée à l’affaire et à la demande ; le partenaire ne voit pas les autres affaires. |

---

## 22. Suite documentaire prévue pour le cœur collaborateur

Ce cahier métier est le premier document de la série collaborateur. Une fois validé, nous reproduirons exactement la discipline déjà appliquée au patron :

| Ordre | Prochain document | Objet |
|---:|---|---|
| 2 | **Contrat Métier vers Interface — Collaborateur** | Question de chaque vue, données, sources, états, actions, erreurs, droits et provenance. |
| 3 | **Matrice de transitions — Collaborateur** | Tâche, exigence, preuve, demande, rectificatif, transmission et retour patron : préconditions, transitions, résultats et faits métier. |
| 4 | **Extension du Contrat de domaine V8** | Frontières complémentaires Analyse, Exigence, Tâche, Demande et Transmission. |
| 5 | **Spécification de commandes collaborateur** | Commandes normalisées, autorisations, idempotence et projections propres au parcours de préparation. |
| 6 | **Cahier des charges du Wizard DCE** | Écran par écran, champs, boutons, messages et critères de recette. |

Le patron et le collaborateur se rejoignent à une seule frontière saine : **la transmission structurée de l’affaire préparée**. Le patron ne récupère pas un dossier brouillon ; il reçoit un état explicite, des preuves, des inconnus, des risques et les décisions qu’il doit prendre.

---

## 23. Révision V1.1 — Les objets qui rendent le travail collaborateur fiable

La première version du cahier décrit correctement le travail réel du collaborateur. Cette révision ne change pas le parcours visible ; elle formalise les réalités qui empêchent ce parcours de devenir rigide, imprécis ou dangereux dès que plusieurs personnes, un rectificatif ou des documents sensibles interviennent.

> **Le collaborateur n’est pas un patron limité. Il produit un travail préparatoire vérifiable. Le patron reçoit ce travail, en apprécie les limites et prend une décision engageante.**

### 23.1. Rôle dans l’entreprise et responsabilité dans une affaire

Le poste d’une personne et son travail dans une affaire sont deux choses différentes. Une personne peut être métreur dans l’entreprise, référent technique sur le lot 01 d’une affaire, puis seulement assistant administratif sur une autre. Les droits ne peuvent donc pas reposer sur un unique champ « rôle collaborateur ».

| Concept | Question à laquelle il répond | Exemples |
|---|---|---|
| **Rôle organisationnel** | « Quelle est la fonction habituelle de cette personne dans l’entreprise ? » | Chargé d’affaires, métreur, conducteur de travaux, assistante administrative. |
| **Affectation d’affaire** (`Assignment`) | « Sur quelle affaire, quel lot et quel périmètre cette personne travaille-t-elle actuellement ? » | Lot 01, analyse technique, contrôle documentaire, visite, mémoire technique. |
| **Périmètre d’affectation** (`Assignment Scope`) | « Quelles ressources et quelles actions cette personne peut-elle voir ou réaliser dans cette affaire ? » | CCTP + références autorisées + tâches techniques ; exclusion explicite des prix privés. |

Une affectation comporte au minimum : l’affaire, la personne, les responsabilités attribuées, les lots/périmètres concernés, les catégories de données accessibles, les actions autorisées, la date de début, la date de fin éventuelle, le patron qui a accordé l’affectation et son état.

| État d’affectation | Signification | Effet |
|---|---|---|
| **Active** | La personne peut travailler dans le périmètre accordé. | Accès et tâches autorisés. |
| **Suspendue** | Le travail est temporairement arrêté sans effacer l’historique. | Aucune nouvelle lecture ou action. |
| **Terminée** | La mission est achevée ou retirée. | Historique consultable selon politique, aucune nouvelle action. |
| **Expirée** | La date de fin est dépassée. | Accès retiré jusqu’à renouvellement explicite. |

> **Règle de sécurité :** la lecture d’une ressource collaborateur exige toujours deux conditions : une affectation active à l’affaire **et** un périmètre autorisant cette ressource. Être salarié de l’entreprise ne suffit jamais.

### 23.2. Le wizard est la vue du travail ; les tâches sont le travail réel

Les sept étapes visibles — affaire, DCE, exigences, terrain, pièces, réponse, transmission — restent indispensables pour rassurer l’utilisateur. Elles ne doivent toutefois jamais devenir un moteur séquentiel qui bloquerait le travail réel.

Le moteur métier repose sur des **tâches**, leurs dépendances et des conditions de préparation. Le wizard est une projection simple de cet ensemble.

```text
Étapes visibles dans l’interface
        ↓
Tâches actives par affaire
        ↓
Dépendances, sources, blocages et conditions de préparation
        ↓
État réel de chaque étape affichée au collaborateur
```

| Élément | Définition | Exemple |
|---|---|---|
| **Tâche** | Travail durable confié à une personne, avec résultat et preuve de fin. | Vérifier la visite obligatoire. |
| **Dépendance de tâche** | Travail qui doit être disponible ou résolu avant qu’une autre tâche puisse être réellement terminée. | Préparer le planning dépend des délais confirmés et du phasage. |
| **Recommandation de prochaine tâche** | Suggestion calculée à partir des tâches actives, urgences et dépendances. | « Commencer par la visite obligatoire ». |
| **Étape du wizard** | Regroupement visuel de tâches. | « Terrain et capacités ». |
| **Condition de préparation** | Fait vérifiable exigé pour qualifier une étape ou une transmission. | Les exigences bloquantes doivent être classées. |

Une recommandation de prochaine tâche ne crée jamais une nouvelle tâche et ne modifie jamais la vérité métier. Elle aide seulement le collaborateur à choisir où commencer.

### 23.3. Graphe de travail et états de validité

Une affaire peut exiger de travailler en parallèle sur les exigences, la visite, les fournisseurs, les références et le mémoire. Un rectificatif ne doit pas renvoyer le collaborateur au début du parcours ; il doit rendre précisément les éléments touchés « à revoir ».

| État de travail | Signification | Ce que voit le collaborateur |
|---|---|---|
| **À faire** | La tâche existe mais n’a pas commencé. | Action disponible. |
| **En cours** | Une personne travaille dessus. | Brouillon et dernière sauvegarde. |
| **En attente** | Une réponse patron, partenaire, acheteur ou pièce est attendue. | Qui est attendu, depuis quand et pour quoi. |
| **Bloquée** | Une dépendance critique empêche la progression. | Cause précise et action de déblocage. |
| **À revoir** (`Needs Review`) | Une information nouvelle peut avoir invalidé le travail fait. | Origine du changement et éléments affectés. |
| **Obsolète** (`Stale`) | Une version ou une preuve ancienne ne peut plus être considérée actuelle. | Nouvelle source à comparer ou confirmer. |
| **Prête à relire** | Le collaborateur a produit le résultat attendu. | Relecteur ou patron à solliciter. |
| **Terminée** | Le résultat et la preuve de fin sont enregistrés. | Historique et source conservés. |
| **Remplacée** | Une tâche plus récente prend le relais. | Lien vers la tâche remplaçante. |
| **Abandonnée avec motif** | La tâche ne sera pas poursuivie. | Motif, autorité et trace. |

> **Règle :** `à revoir` et `obsolète` ne sont pas des synonymes de « non terminé ». Ils indiquent que du travail réellement accompli doit être contrôlé à la lumière d’une information nouvelle.

### 23.4. Une demande, un message, une tâche, une revue et une décision sont différents

SMART_AO ne doit jamais créer un objet vague de type « message collaboratif » qui mélange toutes les interactions.

| Objet | Finalité | Exemple | Peut modifier le métier ? |
|---|---|---|---|
| **Message** | Informer sans attendre d’exécution. | « Le rectificatif a été reçu. » | Non. |
| **Demande** (`Request`) | Obtenir un élément ou une réponse identifiée. | « Merci de fournir l’attestation URSSAF à jour. » | Crée une attente, pas une décision. |
| **Tâche** (`Task`) | Faire un travail attribué et prouvable. | « Vérifier la visite obligatoire ». | Oui, lorsque la tâche produit un résultat validé. |
| **Revue** (`Review`) | Vérifier ou corriger un travail déjà préparé. | « Relire les références proposées ». | Oui, par acceptation ou retour ciblé. |
| **Décision** (`Decision`) | Trancher une option engageante. | Go sous conditions, prix validé, dépôt autorisé. | Oui, exclusivement dans la frontière de décision autorisée. |

Une demande suit le cycle suivant : **demande → réponse → tâche/revue éventuelle**. Une réponse ne clôture jamais automatiquement une tâche critique sans contrôle du résultat reçu.

### 23.5. Partage externe sous contrôle

Un partenaire ne reçoit jamais « le dossier ». Il reçoit une sélection de ressources explicites, limitée à l’objectif de la demande et à une durée déterminée.

| Élément du partage externe | Règle métier |
|---|---|
| Partenaire | Fournisseur, sous-traitant, cotraitant ou bureau d’études identifié. |
| Affaire / lot | Périmètre explicite et non implicite. |
| Ressources partagées | Liste de documents, extraits ou plans précis, avec version figée. |
| Permissions | Lire, télécharger, répondre ou déposer une pièce ; aucune permission globale. |
| Durée | Date d’expiration et révocation possible à tout moment. |
| Autorité | Patron ou délégation patron explicitement accordée. |
| Trace | Qui a partagé, quoi, quand, pourquoi et à qui. |

Une nouvelle version DCE n’est jamais automatiquement ajoutée à un partage externe existant. Le patron ou la personne autorisée doit approuver le nouveau périmètre.

### 23.6. Préparation figée et transmission au patron

La transmission au patron est une véritable transition de responsabilité. Elle ne correspond ni à une tâche terminée ni à une simple notification.

Le collaborateur prépare un **Paquet de préparation** (`Preparation Package`) : exigences, preuves, documents, inconnus, risques, demandes ouvertes, questions, éléments techniques, propositions et décisions attendues. Lorsque le système contrôle ce paquet, il produit un **Instantané de préparation** (`Preparation Snapshot`) figé.

```text
Affaire vivante
  ├── DCE et versions
  ├── exigences
  ├── tâches et preuves
  ├── documents préparés
  ├── risques et inconnus
  └── réponse technique
            ↓
  Instantané de préparation #n
            ↓
  Transmission au patron
```

| État de transmission | Signification | Autorité de transition |
|---|---|---|
| **En préparation** | Le collaborateur prépare les éléments. | Collaborateur affecté. |
| **Prête pour revue** | Les contrôles de préparation sont calculés et le collaborateur peut déclarer sa préparation prête. | Système + collaborateur. |
| **Transmise au patron** | L’instantané est envoyé dans la file d’actions patron. | Collaborateur autorisé, après contrôles. |
| **Reçue par le patron** | Le patron a ouvert/accusé la réception du paquet. | Patron. |
| **Retournée avec corrections** | Le patron demande des compléments ciblés. | Patron. |
| **Acceptée pour phase suivante** | Le patron accepte la préparation comme base de décision ou de chiffrage. | Patron. |
| **Invalidée** | Un rectificatif ou une information critique rend l’instantané non fiable. | Système ou patron selon origine. |

L’état `acceptée pour chiffrage` signifie uniquement : **la préparation est une base de travail pour le patron**. Il ne donne aucun accès au chiffrage, aux prix, aux marges ou à la décision finale au collaborateur.

### 23.7. Contrat de préparation — objectiver « prêt à transmettre »

SMART_AO ne laisse pas un collaborateur déclarer seul qu’un dossier est terminé. Il calcule un état de préparation à partir de critères explicites.

| Dimension de préparation | Condition minimale | Niveau de blocage par défaut |
|---|---|---|
| Inventaire DCE | Les pièces reçues sont classées ; les absences/illisibilités sont déclarées. | Important. |
| Exigences | Les exigences bloquantes sont identifiées, sourcées et classées. | Bloquant. |
| Inconnus critiques | Les inconnus sont visibles, attribués ou transmis. | Bloquant si non attribués. |
| Documents | Chaque pièce exigée est préparée, déclarée manquante, non applicable ou attribuée. | Variable selon exigence. |
| Réponse technique | Les critères concernés sont couverts ou explicitement non couverts. | Important / bloquant selon RC. |
| Preuves | Les preuves critiques sont présentes, expirées, manquantes ou à confirmer avec un état honnête. | Bloquant si exigence de recevabilité. |
| Demandes ouvertes | Les demandes bloquantes sont résolues ou visibles au patron. | Bloquant seulement si la réponse est indispensable. |
| Risques | Les risques majeurs sont signalés et non cachés. | Important ; transmission possible si le patron doit arbitrer. |
| Données financières | Aucune donnée financière privée n’est incluse dans le paquet collaborateur. | Bloquant. |

Les niveaux de criticité sont fixés comme suit :

| Criticité | Effet sur la transmission |
|---|---|
| **Bloquante** | Empêche la création d’un instantané prêt pour revue tant qu’elle n’est pas résolue, dérogée par le patron ou explicitement transmise comme décision urgente patron. |
| **Importante** | N’empêche pas nécessairement la transmission, mais apparaît en tête du dossier patron. |
| **Informationnelle** | Reste visible dans l’historique et la synthèse sans bloquer le flux. |

### 23.8. Réponse technique, engagements et réutilisation

Un brouillon de mémoire n’est pas un engagement. Une phrase telle que « nous mettrons en œuvre… » devient un **engagement candidat**, puis seulement un engagement validé après revue par la personne compétente et, lorsque nécessaire, par le patron.

| Objet | Statut | Conséquence |
|---|---|---|
| **Brouillon de réponse** | Texte de travail. | Peut évoluer librement avec historique. |
| **Engagement candidat** | Promesse détectée ou explicitement déclarée, à vérifier. | Doit être reliée à une capacité, un moyen, un responsable ou une hypothèse. |
| **Engagement validé** | Promesse autorisée dans la réponse retenue. | Devient traçable pour l’exécution si marché gagné. |
| **Élément réutilisable** | Référence, méthode, preuve ou bloc de contenu provenant d’une autre affaire. | Doit passer un contrôle de compatibilité avec le nouveau DCE. |

Une référence ou méthode n’est donc jamais « copiée dans une affaire ». Elle est proposée, contrôlée pour le nouveau contexte, acceptée, rejetée ou marquée à revoir.

### 23.9. Impact ciblé d’un rectificatif

Après réception d’une nouvelle version DCE, SMART_AO réalise une **évaluation d’impact**. Il ne demande jamais de refaire tout le travail sans raison.

| Objet évalué | Résultat possible |
|---|---|
| Exigences | Créée, modifiée, supprimée, à confirmer ou inchangée. |
| Tâches | Maintenue, à revoir, obsolète, remplacée ou nouvelle. |
| Documents préparés | Valides, à revoir ou non concernés. |
| Sections de mémoire | Valides, à revoir ou non concernées. |
| Capacité/preuve | Toujours compatible, à vérifier ou insuffisante. |
| Paquet de préparation | Toujours utilisable ou invalidé. |
| Transmission patron | Toujours actuelle ou retour nécessaire au collaborateur. |

Le collaborateur voit une phrase simple : **« Voici exactement ce qui est devenu à revoir et pourquoi. »** L’analyse détaillée reste accessible par source et par version.

### 23.10. Le domaine humain collaborateur

Le noyau collaborateur de SMART_AO s’appelle fonctionnellement **Préparation du travail et collaboration**. Il ne possède pas l’Affaire, le DCE, la base de capacités ou les prix ; il y fait référence pour organiser le travail humain de préparation.

```text
Affectation
   ↓
Tâches et demandes
   ↓
Travail, preuves, constats et brouillons
   ↓
Revues et contrôle de préparation
   ↓
Instantané de préparation
   ↓
Transmission au patron
```

| Objet collaborateur central | Ce qu’il possède | Ce qu’il référence |
|---|---|---|
| Affectation | Personne, responsabilités, périmètre, dates et état. | Affaire, lots, catégories de ressources. |
| Tâche | Travail, dépendances, état, preuve de fin et responsable. | Affaire, exigence, document, demande ou transmission. |
| Demande | Auteur, destinataire, objet demandé, réponse et état. | Affaire, tâche, exigence, partenaire. |
| Revue | Élément à contrôler, relecteur, résultat et retour. | Brouillon, preuve, document, tâche ou engagement candidat. |
| Paquet de préparation | Contenu préparé et contrôles de complétude. | Affaire et ressources référencées. |
| Instantané de préparation | Versions figées réellement transmises au patron. | Paquet et ressources versionnées. |
| Partage externe | Ressources autorisées, partenaire, durée et permissions. | Affaire, versions documentaires et demande. |

### 23.11. Conditions de gel de la partie collaborateur

Le cahier collaborateur peut être considéré comme stabilisé lorsque les décisions suivantes sont validées :

1. Les droits dépendent d’une **affectation d’affaire et de son périmètre**, pas seulement d’un rôle utilisateur.
2. Les sept étapes restent une expérience utilisateur, tandis que le travail réel repose sur des tâches et leurs dépendances.
3. `Tâche`, `demande`, `message`, `revue` et `décision` sont des réalités distinctes.
4. Le système distingue clairement le travail actuel, obsolète, à revoir, bloqué et prêt.
5. Un rectificatif produit une évaluation d’impact ciblée, jamais une réinitialisation aveugle.
6. Une transmission patron est construite à partir d’un **instantané de préparation** figé.
7. L’état « prêt à transmettre » est calculé par un contrat de préparation et une criticité explicite.
8. Aucune transmission ne donne au collaborateur accès au chiffrage ou aux prix privés.
9. Les engagements de réponse sont identifiés puis validés, jamais créés automatiquement par un brouillon ou une IA.
10. Le futur contrat d’interface collaborateur doit respecter l’enchaînement : **Affectation → Tâches/Demandes → Travail/Preuves → Revue → Instantané → Transmission patron**.

## Références

[1] [Apec — Chargé d’affaires dans le BTP](https://www.apec.fr/tous-nos-metiers/commercial-marketing/charge-daffaires-dans-le-btp.html)  
[2] [France compétences — RNCP38141 Chargé d’affaires BTP](https://www.francecompetences.fr/recherche/rncp/38141/)  
[3] [Onisep — Chargé / Chargée d’études de prix](https://www.onisep.fr/ressources/univers-metier/metiers/charge-chargee-d-etudes-de-prix)  
[4] [Constructys — Chargé(e) d’affaires bâtiment](https://espace-competences.constructys.fr/metiers-du-batiment/encadrement-de-chantier/fiche-chargee-daffaires-batiment/)

## Références internes

- `SMART_AO_VISION_METIER_PARCOURS_UTILISATEUR.md`
- `SMART_AO_V8_CAHIER_ESPACE_PATRON.md`
- `SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE.md`
- `SMART_AO_V8_MATRICE_TRANSITIONS_METIER.md`
- `SMART_AO_V8_CONTRAT_DE_DOMAINE.md`
- `recherche_espace_collaborateur_btp_2026.md`

---

**Fin du Cahier métier de l’espace collaborateur — version 1.0**
