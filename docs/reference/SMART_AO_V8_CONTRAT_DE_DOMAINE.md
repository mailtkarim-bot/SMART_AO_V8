# SMART_AO V8 — Contrat de domaine

**Version :** 1.2 — clarification des concepts, ownership et agrégats à formaliser  
**Statut :** référence de conception à valider avant création du dépôt V8  
**Auteur :** Manus AI  
**Périmètre :** noyau métier patron et collaborateur : pilotage patron, accès délégué, préparation DCE, tâches, demandes, preuves, transmission et continuité vers le chiffrage. L’analyse DCE détaillée et l’exécution chantier seront prolongées sans modifier les règles fondatrices ci-dessous.

---

## 1. Objet du contrat

Ce contrat définit les réalités métier que SMART_AO doit conserver, les frontières responsables de leurs changements, leurs états possibles et les règles qui ne doivent jamais être violées. Il fait le lien entre la matrice V8.2 et le futur code. Il ne décrit pas les tables SQL finales ni les écrans ; il décrit **ce qui est vrai dans le métier**, indépendamment de la technologie.

> **Règle fondatrice :** une commande ne peut modifier qu’une frontière métier explicitement responsable du changement demandé. Toute conséquence durable doit être attribuable à un fait métier daté, à un auteur, à un contexte et à une entreprise.

SMART_AO représente une **Affaire** continue : elle peut commencer par une opportunité, se poursuivre par un DCE et une réponse, être déposée, devenir un marché gagné, puis vivre en exécution. Cette continuité visible ne signifie pas qu’un seul objet technique contient tout. Les mutations critiques sont réparties entre des frontières métier spécialisées afin d’éviter les incohérences de V7.1.

---

## 2. Les règles universelles V8

| Règle | Contrat impératif |
|---|---|
| **Isolement entreprise** | Toute donnée, commande, lecture, document, preuve, calcul ou événement porte l’identifiant de son entreprise. Une ressource d’une autre entreprise est inaccessible et ne doit pas être révélée par un message d’erreur. |
| **Identifiants stables** | Chaque réalité durable possède un identifiant immuable, non réutilisé et non déduit d’un nom affiché. |
| **Historique non destructif** | Une décision, un prix officiel, un document utilisé, un DCE ou un paquet de dépôt validé n’est jamais écrasé. Une nouvelle version le remplace pour l’avenir, tout en conservant le lien historique. |
| **Provenance obligatoire** | Une conclusion importante doit référencer ses sources, leurs versions, son auteur ou moteur de production et sa date de calcul. |
| **Argent déterministe** | Tous les montants, taux, index et calculs financiers utilisent des valeurs décimales exactes. Aucun modèle IA ne crée, modifie ou valide un montant. |
| **Décision humaine** | Une décision réservée au patron possède un choix explicite, un auteur habilité, une date, un contexte figé et, lorsqu’il y a risque, un motif. |
| **Information incertaine** | Une donnée importante est toujours qualifiée : `confirmée`, `à vérifier`, `manquante`, `contradictoire`, `expirée` ou `non applicable`. |
| **Prix privé** | Les coûts, marges, scénarios, devis, trésorerie et règles internes ne peuvent jamais être retournés dans une lecture, un export ou une notification non autorisés. |
| **Version et fraîcheur** | Une donnée dont la validité varie indique sa version, sa date de référence et, lorsque nécessaire, son état de fraîcheur. |
| **Commandes rejouables** | Toute commande critique comporte une clé d’idempotence. Une répétition identique retourne le même résultat ; une répétition avec contenu différent est refusée. |

---

## 3. Carte des frontières métier

Une **frontière métier** est l’unité responsable d’une mutation et de ses invariants. Le terme est volontairement utilisé à la place de « gros objet » : une Affaire reste visible comme un ensemble continu pour le patron, mais elle ne devient jamais un conteneur mutable où tous les modules écrivent librement.

| Code | Frontière métier | Responsabilité exclusive | Ne doit jamais faire |
|---|---|---|---|
| `ORG` | **Entreprise** | Identité, règles privées, capacités, qualifications, références, partenaires et préparation de l’entreprise. | Déposer une offre, décider une affaire ou modifier un prix officiel. |
| `AFF` | **Affaire** | Cycle de vie commercial, rattachement à une consultation/lot, responsables et continuité de l’affaire. | Contenir en direct les coûts détaillés, les documents binaires ou la décision complète. |
| `DCE` | **DCE et version de consultation** | Réception, intégrité, versions, rectificatifs, pièces et statut de lecture d’un DCE. | Modifier les documents originaux acheteur ou déclarer seule une obligation confirmée. |
| `ACT` | **Action patron** | File de décisions et arbitrages réservés au patron, causes, priorité, délégation et clôture. | Produire une décision métier sans passer par la frontière Décision. |
| `DEC` | **Décision** | Choix humain, contexte figé, conditions, révocation/supersession et conséquence autorisée. | Modifier rétroactivement son contexte ou se déclarer automatique. |
| `PRF` | **Preuve et document** | Original, version, métadonnées, confidentialité, autorisation d’usage, expiration et traçabilité. | Modifier un original, masquer une expiration ou donner un accès hors autorisation. |
| `PRX` | **Prix privé et version d’offre** | Scénarios, hypothèses, devis, calculs déterministes, version officielle et état de fiabilité. | Écraser une version validée ou exposer un prix privé à un collaborateur. |
| `DEP` | **Paquet et dépôt** | Contrôles, composition versionnée, autorisation patron, déclaration de dépôt et accusé de réception. | Déclarer un dépôt réussi sans accusé ou preuve explicite. |
| `ASN` | **Affectation et délégation** | Accès d’un collaborateur à une affaire, rôle, périmètre, durée et retrait. | Donner un accès global par défaut aux prix ou à toutes les affaires. |
| `OPP` | **Opportunité et profil de veille** | Profil de recherche, opportunité observée, qualification, écartement, transmission et création d’affaire. | Déduire qu’une affaire correspond sans exposer les critères correspondants et non correspondants. |

Les analyses DCE, exigences, risques, protections et calculs sont des réalités de domaine associées principalement à une affaire et une version de DCE. Ils possèdent leur propre identité et provenance. Leur cycle détaillé sera étendu dans le contrat du parcours collaborateur, mais les règles d’intégrité ci-dessous sont déjà applicables.

---

## 4. Réalités transverses du domaine

| Réalité | Définition | Propriétaire de vérité | Éléments minimaux immuables |
|---|---|---|---|
| **Consultation** | Référence acheteur à laquelle une ou plusieurs affaires peuvent être liées. | `DCE` | Acheteur, identifiant externe si connu, objet, lieu, source, date de création. |
| **Lot sélectionné** | Périmètre de réponse choisi par l’entreprise dans une consultation. | `AFF` | Numéro/libellé source, consultation, affaire associée. |
| **Exigence** | Obligation, critère, interdiction ou élément demandé par l’acheteur. | `DCE` + analyse vérifiée | Type, état, source DCE, version, extrait/localisation, affaire. |
| **Capacité** | Équipe, qualification, matériel, référence, partenaire ou règle interne mobilisable. | `ORG` | Nature, périmètre, source, période, état de vérification. |
| **Preuve** | Élément autorisé à démontrer une capacité ou couvrir une exigence. | `PRF` | Original/version, émetteur, dates, confidentialité, autorisation d’usage. |
| **Risque** | Situation pouvant affecter délai, marge, conformité, preuve, droit ou trésorerie. | `AFF` | Famille, impact, état, causes, sources, propriétaire de traitement. |
| **Protection** | Action ou mesure visant à réduire un risque. | `ACT` ou `AFF` | Risque relié, action attendue, responsable, date, résultat. |
| **Contexte de décision** | Instantané non modifiable des informations considérées par le patron. | `DEC` | Versions DCE, exigences, risques, capacités, preuves, prix, inconnus et horodatage. |
| **Événement de domaine** | Changement durable produit par une commande acceptée. Il ne doit pas être confondu avec un fait/constat métier. | Noyau transversal | Type, entreprise, auteur/origine, date, ressource, révision et charge utile métier. |

---

# Partie I — Contrats détaillés des frontières métier

## 5. `AFF` — Contrat de l’Affaire

### 5.1. Responsabilité

L’Affaire matérialise le travail commercial BTP choisi par l’entreprise. Elle porte son identité, son rattachement à une consultation et un lot, ses acteurs, son état de cycle de vie et les liens vers les autres frontières. Elle ne porte pas les détails de prix, les fichiers, les analyses ou les décisions ; elle les référence.

### 5.2. États de l’Affaire

| État | Signification métier | Transitions autorisées principales |
|---|---|---|
| `OPPORTUNITE_A_EXAMINER` | Signal reçu, pas encore choisi comme travail actif. | Qualifier, transmettre, écarter, créer l’affaire. |
| `ANALYSE_EN_COURS` | DCE ou informations en cours de réception/analyse. | Attendre décision, arrêter, demander complément. |
| `ATTENTE_DECISION` | Synthèse suffisamment préparée pour un arbitrage patron. | Go, Go sous conditions, No-Go. |
| `PREPARATION_OFFRE` | Pièces, mémoire, tâches, visites et réponses sont préparées. | Prête à chiffrer, suspendre, arrêter. |
| `PRETE_A_CHIFFRER` | Partie technique/administrative transmise au patron. | Chiffrage en cours, retour préparation, arrêter. |
| `CHIFFRAGE_EN_COURS` | Prix et scénarios privés en construction. | Prête contrôle final, retour préparation, arrêter. |
| `PRETE_CONTROLE_FINAL` | Prix officiel et pièces préparés ; contrôle de dépôt attendu. | Prête au dépôt, retour préparation/chiffrage. |
| `PRETE_AU_DEPOT` | Paquet contrôlé et autorisé ; action humaine de dépôt attendue. | Déposée, retour contrôle. |
| `DEPOSEE` | Dépôt déclaré ; accusé de réception attendu ou archivé. | Résultat connu, nouvelle version si rectificatif autorisé. |
| `RESULTAT_CONNU` | Attribuée, perdue, sans suite ou retirée. | Marché gagné/exécution, archiver. |
| `MARCHE_GAGNE` | Marché obtenu ; continuité vers l’exécution. | Exécution, clôture. |
| `EXECUTION` | Marché en réalisation ; périmètre futur détaillé. | Clôture, litige/réserve selon extension. |
| `ARRETEE` | L’entreprise a renoncé, avec motif conservé. | Réouvrir uniquement par nouvelle décision explicite. |
| `ARCHIVEE` | Affaire hors portefeuille actif, historique conservé. | Consulter, restaurer avec motif. |

### 5.3. Invariants

1. Une affaire appartient à une seule entreprise.
2. Une affaire possède un **périmètre explicite et non ambigu**. Ce périmètre peut couvrir un lot, un ensemble autorisé de lots, une tranche, une variante ou un périmètre personnalisé rattaché à la consultation. Il ne mélange jamais des éléments sans relation ni justification source.
3. Une affaire déposée, arrêtée, archivée ou passée au résultat ne peut pas être modifiée comme une affaire active sans transition autorisée.
4. Un rectificatif DCE ne change pas seul l’état de l’affaire ; il peut rendre ses décisions, son prix ou son paquet `à revoir`.
5. Le responsable courant, s’il existe, est une affectation active autorisée pour l’affaire.

### 5.4. Commandes et faits métier principaux

| Commande | Précondition métier | Fait métier principal |
|---|---|---|
| `CreateAffair` | Entreprise active ; consultation/lot ou objet manuel identifié. | `AffairCreated` |
| `AssignAffair` | Utilisateur collaborateur actif ; rôle limité et affaire non archivée. | `AffairAssigned` |
| `ReassignAffair` | Nouvelle affectation valide ; motif enregistré si retrait d’un responsable actif. | `AffairReassigned` |
| `MoveAffairToDecision` | Analyse minimale présente ; inconnus visibles. | `AffairReadyForDecision` |
| `MoveAffairToPricing` | Décision Go active ; préparation transmise. | `AffairReadyForPricing` |
| `StopAffair` | Patron habilité ; motif obligatoire. | `AffairStopped` |
| `ArchiveAffair` | Aucune action bloquante non arbitrée, ou justification explicite. | `AffairArchived` |

---

## 6. `DCE` — Contrat du DCE, de ses pièces et de ses versions

### 6.1. Responsabilité

Cette frontière protège l’intégrité des pièces acheteur. Un DCE est reçu, hashé, classé et versionné. Une nouvelle pièce ou un rectificatif ne remplace jamais silencieusement la pièce précédente.

### 6.2. États

| État | Sens |
|---|---|
| `RECU` | Fichier admis, original conservé et identifiant attribué. |
| `A_CLASSER` | Nature de pièce non confirmée. |
| `CLASSE` | Nature reconnue ou validée humainement. |
| `LISIBLE_PARTIELLEMENT` | Extraction incomplète ; aucune conclusion ne peut être affichée comme exhaustive. |
| `ANALYSE` | Extraction disponible pour contrôle et analyse. |
| `RECTIFICATIF` | Nouvelle version officiellement reçue et reliée au DCE précédent. |
| `INUTILISABLE` | Fichier endommagé, incomplet ou non exploitable ; la cause est conservée. |

### 6.3. Invariants

1. Un original acheteur est immuable ; toutes les extractions et annotations sont dérivées et versionnées.
2. Toute exigence, date, pénalité ou contrainte affichée référence une pièce et une version DCE.
3. Un rectificatif possède son propre original, date de réception et lien de supersession.
4. L’absence d’une pièce ne devient jamais une affirmation : elle produit l’état `manquant` ou `à vérifier`.

---

## 7. `ACT` — Contrat de l’Action patron

### 7.1. Responsabilité

L’Action patron représente un arbitrage, une validation ou une action qui ne peut pas être achevée par un collaborateur seul. Elle regroupe plusieurs causes possibles, sans produire elle-même la décision ou le prix.

### 7.2. États

| État | Transition autorisée |
|---|---|
| `A_TRAITER` | Prendre en compte, déléguer préparation, décider, abandonner. |
| `PRISE_EN_COMPTE` | Préparer, décider, demander information, abandonner. |
| `EN_ATTENTE_TIERS` | Relancer, recevoir information, reprendre, abandonner. |
| `EN_ATTENTE_INFORMATION` | Recevoir information, corriger, reprendre, abandonner. |
| `DECIDEE_SOUS_CONDITIONS` | Vérifier conditions, clôturer, révoquer/remplacer. |
| `TERMINEE` | Consultation seulement ; réouverture uniquement par nouvelle action. |
| `ABANDONNEE_AVEC_MOTIF` | Consultation seulement ; une nouvelle action peut être créée. |
| `REMPLACEE` | Consultation de l’action remplaçante uniquement. |

### 7.3. Invariants

1. Une action possède au moins une cause, une raison compréhensible, un propriétaire patron et un état.
2. Deux actions actives ne peuvent pas être créées pour la même cause, même affaire, même type d’arbitrage et même contexte courant.
3. Une action sous conditions référence les conditions, responsables et échéances ; une condition sans responsable est invalide.
4. Une action terminée, abandonnée ou remplacée demeure dans le Journal de vérité.

---

## 8. `DEC` — Contrat de la Décision humaine

### 8.1. Responsabilité

La Décision conserve un choix humain engageant : répondre, ne pas répondre, répondre sous conditions, valider un prix, accepter/refuser un partenaire, accepter un risque ou autoriser un dépôt. Elle est la seule frontière autorisée à figer le contexte de décision.

### 8.2. États

| État | Signification |
|---|---|
| `BROUILLON` | Préparation possible, aucune conséquence métier. |
| `EN_ATTENTE_PATRON` | Informations prêtes pour arbitrage. |
| `VALIDEE` | Choix final patron, contexte figé et conséquence autorisée. |
| `VALIDEE_SOUS_CONDITIONS` | Choix patron avec conditions traçables. |
| `REFUSEE` | Choix de ne pas poursuivre/autoriser, motif conservé. |
| `A_REVOIR` | Un changement significatif rend le contexte obsolète. |
| `SUPERSEDEE` | Une décision plus récente la remplace ; elle reste consultable. |

### 8.3. Invariants

1. Une décision finalisée appartient à un seul type d’arbitrage et une seule affaire ou ressource précisément identifiée.
2. Toute décision finalisée possède un `decision_context_id` immuable.
3. Une décision `VALIDEE` ou `VALIDEE_SOUS_CONDITIONS` ne peut pas changer de choix ; elle est supersédée par une nouvelle décision.
4. Toute condition possède un libellé, un responsable, une date ou un motif expliquant l’absence de date, et une conséquence de non-réalisation.
5. Une décision patron ne peut pas être produite par une analyse SMART_AO.

### 8.4. Contexte de décision

Le contexte figé contient, selon le type de décision, les références exactes aux versions DCE, exigences, inconnus, risques, capacités, preuves, prix, devis, hypothèses et avis consultés. Il porte une empreinte déterministe. Une évolution ultérieure ne réécrit jamais ce contexte ; elle peut seulement rendre la décision `A_REVOIR`.

---

## 9. `PRF` — Contrat de la Preuve, du document et de son autorisation d’usage

### 9.1. Responsabilité

Cette frontière gère l’original, les versions, les métadonnées, les dates, l’accès et le droit d’utiliser une pièce dans une affaire. Elle couvre notamment qualification, assurance, référence, attestation, modèle, document partenaire et pièce administrative.

### 9.2. États

| État | Sens |
|---|---|
| `DISPONIBLE` | Original et métadonnées minimum disponibles, sans garantie d’usage automatique. |
| `A_VERIFIER` | Utilisation ou périmètre à confirmer. |
| `CONFIRMEE_POUR_AFFAIRE` | Usage validé pour une affaire et un périmètre précis. |
| `EXPIREE` | Date connue dépassée ; ne peut pas être présentée comme valide. |
| `ARCHIVEE` | Non proposée aux nouvelles affaires, historique conservé. |
| `REMPLACEE` | Une version plus récente existe ; l’ancienne reste consultable. |

### 9.3. Invariants

1. L’original ne peut pas être modifié après admission.
2. Une version n’est jamais supprimée lorsqu’elle est liée à une décision, un prix, un paquet ou un dépôt.
3. Une preuve sans droit d’usage, sans périmètre connu ou expirée ne peut pas devenir `CONFIRMEE_POUR_AFFAIRE` sans validation humaine motivée.
4. Une autorisation d’usage est limitée par affaire, périmètre, durée et niveau de confidentialité.

---

## 10. `PRX` — Contrat du Prix privé et de la version d’offre

### 10.1. Responsabilité

Le Prix privé rassemble les données confidentielles permettant au patron de construire une offre : sources de prix, devis, hypothèses, scénarios, calculs, exposition aux risques et version officielle. Les calculs sont déterministes et reproductibles.

### 10.2. États de scénario et de version officielle

| Réalité | États |
|---|---|
| **Scénario** | `BROUILLON`, `A_COMPLETER`, `A_REVOIR`, `COMPARE`, `ARCHIVE`. |
| **Version officielle de prix** | `PREPAREE`, `A_REVOIR`, `VALIDEE_PATRON`, `REMPLACEE`, `UTILISEE_DEPOT`. |
| **Fiabilité chiffrage** | `COUVERT`, `PARTIEL`, `FRAGILE`, `NON_PRET` ; l’état est explicable par les postes, preuves et hypothèses. |

### 10.3. Invariants

1. Tout montant est stocké avec devise, précision décimale et règle de calcul applicable.
2. Un scénario ne modifie jamais une version officielle.
3. Une version officielle validée référence les pièces DCE, hypothèses, devis et calculs pris en compte.
4. Une nouvelle version DCE ou une modification de poste couvert rend la version officielle `A_REVOIR` sans la supprimer.
5. Une version `VALIDEE_PATRON` ne peut être utilisée pour le dépôt que si l’affaire est compatible avec cette version DCE et que les blocages affichés ont été traités ou explicitement acceptés.

---

## 11. `DEP` — Contrat du Paquet de dépôt et de la preuve de dépôt

### 11.1. Responsabilité

Cette frontière prépare et protège le paquet à déposer. Elle ne réalise pas l’action sur le profil acheteur à la place du patron et ne transforme jamais l’existence d’un ZIP en dépôt effectif.

### 11.2. États

| État | Signification |
|---|---|
| `EN_PREPARATION` | Contrôles et composition en cours. |
| `BLOQUE` | Une pièce, une version, une signature ou une règle nécessaire n’est pas satisfaite. |
| `PRET_CONTROLE` | Le paquet est assemblé, contrôlé et attend la revue patron. |
| `AUTORISE_DEPOT` | Patron ou délégataire habilité a autorisé la version précise. |
| `DEPOT_DECLARE` | L’utilisateur a déclaré avoir déposé ; accusé non encore archivé. |
| `ACCUSE_ARCHIVE` | Preuve de dépôt associée à la bonne version et à la bonne affaire. |
| `REMPLACE` | Une nouvelle version de paquet est nécessaire. |

### 11.3. Invariants

1. Un paquet référence une seule affaire, une seule version DCE applicable et une version précise de chaque fichier inclus.
2. Un paquet autorisé au dépôt ne peut pas être modifié ; toute modification crée une nouvelle version.
3. `DEPOT_DECLARE` n’est pas synonyme de dépôt prouvé.
4. `ACCUSE_ARCHIVE` nécessite la preuve, la plateforme, la date/heure déclarée ou extraite, et le lien à la version de paquet.

---

## 12. `ASN` — Contrat de l’Affectation et de la délégation

| Règle | Contrat |
|---|---|
| Portée | Une affectation concerne une personne, une affaire, un rôle et un périmètre d’actions. |
| Durée | Toute délégation ponctuelle possède début, fin ou règle d’expiration. |
| Données privées | Aucun rôle collaborateur ne porte un droit implicite au Prix privé, à la marge, à la trésorerie ou au portefeuille complet. |
| Retrait | Le retrait bloque l’accès futur, préserve les contributions et crée un fait métier. |
| Compte suspendu | Toutes les affectations restent historiques mais aucun accès actif n’est possible. |
| Contrôle | Une commande d’affectation vérifie l’état du compte et la compatibilité du rôle avant d’accorder l’accès. |

---

## 13. `OPP` — Contrat de l’Opportunité et du profil de veille

| État opportunité | Sens | Transition principale |
|---|---|---|
| `DETECTEE` | Signal reçu d’une source ou ajout manuel. | Examiner. |
| `A_EXAMINER` | Correspondance expliquée mais non qualifiée. | Transmettre, qualifier, écarter, mettre en veille. |
| `TRANSMISE` | Préanalyse confiée à un collaborateur. | Recevoir synthèse, créer affaire, écarter. |
| `EN_VEILLE` | À suivre sans travail actif immédiat. | Réexaminer, écarter, créer affaire. |
| `QUALIFIEE` | Informations suffisantes pour devenir une affaire. | Créer affaire. |
| `ECARTEE` | Patron renonce ; motif conservé. | Consulter seulement ou réouvrir avec motif. |
| `TRANSFORMEE_EN_AFFAIRE` | Lien immuable vers l’affaire créée. | Continuation dans `AFF`. |

Un profil de veille est versionné. Chaque opportunité garde le profil, la version de critères et la source qui ont conduit à sa proposition.

---

# Partie II — Relations, cohérence et événements

## 14. Cardinalités et politiques de suppression

| Relation | Cardinalité | Règle de conservation |
|---|---|---|
| Entreprise → Affaire | 1 → N | Une affaire n’est jamais déplacée entre entreprises. |
| Affaire → Version DCE | 1 → N | Plusieurs versions possibles ; une seule version courante applicable à la fois. |
| Affaire → Action patron | 1 → N | Une action peut être fermée/remplacée ; aucune suppression destructive. |
| Action patron → Causes | 1 → N | Une cause peut être rattachée à une action active selon la règle de déduplication. |
| Décision → Contexte figé | 1 → 1 | Contexte immuable, jamais mis à jour. |
| Affaire → Décisions | 1 → N | Historique complet ; une décision active par type/périmètre selon l’invariant de commande. |
| Preuve → Versions | 1 → N | Original et versions conservés selon rétention contractuelle. |
| Affaire → Versions de prix | 1 → N | Une seule version officielle active par DCE/lot/périmètre. |
| Paquet de dépôt → Fichiers | 1 → N | Chaque fichier est une version identifiée ; paquet non modifiable après autorisation. |
| Opportunité → Affaire | 0..1 → 1 | L’opportunité transformée conserve le lien vers l’affaire ; l’affaire conserve la source. |

La suppression physique n’est autorisée que dans le cadre d’une politique de rétention explicite, hors ressources utilisées pour une décision, un dépôt, un calcul validé ou une obligation légale/contractuelle. La règle par défaut est l’archivage fonctionnel.

---

## 15. Événements de domaine et Journal de vérité

### 15.1. Contrat d’un fait métier

Tout **événement de domaine** durable contient au minimum :

| Champ | Règle |
|---|---|
| `event_id` | Identifiant immuable. |
| `event_type` | Nom métier au passé, par exemple `PricingVersionApproved`. |
| `occurred_at` | Date/heure de l’acceptation métier. |
| `tenant_id` | Entreprise propriétaire. |
| `actor_type` / `actor_id` | Patron, collaborateur, partenaire, moteur déterministe ou système. |
| `aggregate_type` / `aggregate_id` | Frontière qui a accepté le changement. |
| `affair_id` | Présent lorsqu’un fait est rattaché à une affaire. |
| `causation_id` | Identifiant de la commande source. |
| `correlation_id` | Identifiant de l’opération ou parcours commun. |
| `payload_version` | Version du contrat d’événement. |
| `payload` | Données métier minimales nécessaires à la reconstruction ou projection. |

### 15.2. Règle Journal de vérité

Le Journal de vérité est une **situation préparée** à partir d’événements de domaine sélectionnés. Il ne devient jamais une seconde source de vérité. Il affiche seulement des phrases métier, sources, versions, auteurs et conséquences, jamais des logs techniques, mots de passe, clés ou détails d’infrastructure.

---

## 16. Concurrence, version et effets différés

| Sujet | Règle V8 |
|---|---|
| **Mutation locale** | Une commande cible une frontière avec une version attendue ou un contexte figé. Un conflit produit une réponse explicite, jamais une fusion silencieuse. |
| **Décision/paiement/dépôt** | La commande vérifie le contexte figé et les versions DCE/prix/paquet requises ; un changement significatif retourne `STALE_CONTEXT` ou `VERSION_CONFLICT`. |
| **Mises à jour de vues** | Le fait métier est durable avant l’actualisation de cockpit, listes et indicateurs. Une vue peut se rafraîchir après la commande mais affiche son état de fraîcheur. |
| **Rectificatif DCE** | Il crée une nouvelle version ; les objets dépendants sont marqués à revoir par un fait explicite, sans effacement. |
| **Échec technique** | Aucun résultat métier n’est confirmé tant que la transaction métier n’est pas validée. |
| **Échec métier** | La commande retourne une violation explicable des préconditions ou invariants, avec les éléments à corriger. |

---

## 17. Critères de recette du Contrat de domaine

Le domaine V8 sera considéré prêt à être codé lorsque les tests pourront démontrer les comportements suivants :

| Critère | Preuve attendue |
|---|---|
| Isolement | Une commande et une lecture inter-entreprises échouent sans exposer l’existence de la ressource. |
| Historique | Une nouvelle version de DCE, prix ou preuve ne modifie pas la décision et le dépôt historiques. |
| Prix privé | Aucun collaborateur ne reçoit un montant, coût, marge, devis ou fichier privé via aucune vue ou erreur. |
| Décision | Une décision finalisée conserve son contexte figé et exige un patron autorisé. |
| Dépôt | Aucun état « déposé avec preuve » n’existe sans accusé archivé. |
| Doublons | Une même commande idempotente ne crée ni seconde décision, ni seconde version, ni second événement. |
| Rectificatif | La version nouvelle marque les dépendances à revoir sans supprimer leur historique. |
| Explication | Toute exigence, risque, capacité, prix ou alerte à impact ouvre une provenance appropriée. |
| Concurrence | Une mutation concurrente incompatible produit un conflit explicite et n’altère pas le résultat déjà validé. |

---

## 18. Décisions de gel avant implémentation

1. Les frontières `AFF`, `ACT`, `DEC`, `PRF`, `PRX`, `DEP`, `ASN`, `DCE`, `ORG` et `OPP` constituent le vocabulaire de domaine V8 initial.
2. Toute extension future — analyse collaborateur, exécution, facturation, veille avancée — devra rattacher chaque mutation à l’une de ces frontières ou justifier une nouvelle frontière.
3. Aucun écran ne modifie directement une donnée métier : il émet une commande normalisée vers la frontière propriétaire.
4. Toute décision, version officielle de prix et autorisation de dépôt est immuable après finalisation et remplaçable seulement par supersession/version nouvelle.
5. Le contrat d’implémentation des commandes est la référence suivante obligatoire avant toute API d’écriture.

---

# Partie III — Extension collaborateur du domaine V8

## 19. Principe d’intégration collaborateur

L’espace collaborateur ne crée pas un deuxième métier séparé du patron. Il prépare l’affaire à l’intérieur de frontières spécialisées, puis remet au patron un **instantané vérifiable**. Le patron conserve le Go/No-Go, le chiffrage, l’acceptation de risque, l’autorisation de dépôt et les données financières.

```text
Affectation autorisée
  ↓
Travail collaboratif : tâches, demandes, preuves, revues
  ↓
Paquet de préparation évalué
  ↓
Instantané immuable transmis
  ↓
Action et décision patron
  ↓
Chiffrage / contrôle final / dépôt
```

| Code | Frontière collaborateur | Responsabilité exclusive | Ne doit jamais faire |
|---|---|---|---|
| `ASN` | **Affectation et délégation** | Droit contextualisé d’un acteur sur une affaire et son périmètre. | Conférer un accès financier implicite ou modifier une tâche. |
| `TSK` | **Tâche de préparation** | Travail à réaliser, responsabilités, dépendances, blocages et résultat de fin. | Décider le prix, le Go/No-Go ou le dépôt. |
| `DMD` | **Demande et réponse** | Échange structuré d’une information, pièce, disponibilité ou clarification. | Faire d’une réponse reçue une preuve validée sans revue. |
| `REV` | **Revue** | Contrôle humain d’un résultat, document, réponse, capacité ou engagement candidat. | Modifier silencieusement l’objet revu. |
| `PRE` | **Paquet de préparation** | Contenu vivant de la préparation et évaluation de disponibilité pour transmission. | Se déclarer dépôt ou version officielle de prix. |
| `SNP` | **Instantané de préparation** | Photographie immuable de l’état précis remis au patron. | Être modifié après création ou devenir l’affaire vivante. |
| `TRN` | **Transmission patron** | Acheminement et cycle de réception/retour d’un instantané vers le patron. | Autoriser un prix ou constituer une décision patron. |
| `SHR` | **Partage externe** | Accès ponctuel et versionné d’un partenaire à des ressources autorisées. | Étendre automatiquement le partage à une nouvelle version. |
| `IMP` | **Évaluation d’impact DCE** | Résultat traçable du changement de version DCE sur les objets préparés. | Modifier les sources DCE ou effacer le travail antérieur. |

Les frontières existantes gardent leurs responsabilités : `DCE` possède les originaux, versions et exigences sourcées ; `PRF` possède les preuves et documents ; `AFF` possède la continuité de l’affaire ; `DEC`, `PRX` et `DEP` restent strictement patronaux.

---

## 20. `ASN` — Affectation et délégation étendue

### 20.1. Responsabilité

Une affectation est la seule base durable du travail collaborateur sur une affaire. Elle accorde un périmètre explicite : lots, ressources, actions, durée et éventuelle délégation. Elle est évaluée à chaque lecture sensible et à chaque commande ; l’affichage ancien d’un écran ne suffit jamais à autoriser une action.

### 20.2. États

| État | Sens | Transitions principales |
|---|---|---|
| `PROPOSEE` | Affectation préparée, non encore active. | Activer, annuler. |
| `ACTIVE` | Accès et actions de périmètre autorisés. | Restreindre, suspendre, expirer, retirer. |
| `SUSPENDUE` | Accès temporairement bloqué, historique conservé. | Réactiver, retirer. |
| `EXPIREE` | Date de fin atteinte. | Renouveler par nouvelle affectation ou retraiter. |
| `RETIREE` | Aucun accès futur ; contributions conservées. | Consultation historique seulement. |
| `REMPLACEE` | Nouvelle affectation liée à une réattribution. | Consultation de l’affectation remplaçante. |

### 20.3. Invariants

1. Une affectation appartient à une entreprise, une affaire, un acteur et une période définie.
2. Une affectation active définit explicitement son périmètre de ressources et d’actions ; l’absence de droit vaut refus.
3. Une affectation active ne peut jamais inclure par défaut `FinancialClass` ou `StrategicClass`.
4. Le retrait préserve les brouillons, résultats, tâches et faits historiques ; il interdit tout nouvel accès ou toute nouvelle commande.
5. Toute action sensible vérifie le contexte : **acteur × affectation active × portée × classe de ressource × verbe × contexte affaire**.
6. Une délégation à durée limitée expire automatiquement sans supprimer l’historique de la personne déléguée.

### 20.4. Faits métier

`AssignmentProposed`, `AssignmentActivated`, `AssignmentScopeChanged`, `AssignmentSuspended`, `AssignmentExpired`, `AssignmentRevoked`, `AssignmentReplaced`, `AssignmentAcknowledged`, `AssignmentClarificationRequested`.

---

## 21. `TSK` — Tâche de préparation

### 21.1. Responsabilité

La tâche est l’unité durable de travail préparatoire. Elle représente une action attendue pour une affaire : classifier une pièce, préparer une référence, organiser une visite, vérifier une exigence, relire un document, obtenir une réponse ou corriger un élément impacté. Le wizard est une projection de tâches et de conditions ; il ne possède pas le workflow.

### 21.2. États

| État | Sens |
|---|---|
| `A_FAIRE` | Créée et non commencée. |
| `EN_COURS` | Exécutant identifié et travail engagé. |
| `EN_ATTENTE` | Réponse, pièce, revue ou tiers attendu. |
| `BLOQUEE` | Dépendance forte ou cause bloquante non résolue. |
| `PRETE_A_RELIRE` | Résultat soumis à une revue. |
| `TERMINEE` | Résultat accepté au niveau attendu. |
| `REMPLACEE` | Une nouvelle tâche prend explicitement le relais. |
| `ABANDONNEE_AVEC_MOTIF` | Travail arrêté avec impact connu. |

### 21.3. Responsabilités humaines

| Rôle de tâche | Devoir |
|---|---|
| **Propriétaire** | Garantit l’existence et le traitement du travail. |
| **Exécutant** | Réalise la tâche et produit le résultat. |
| **Relecteur** | Vérifie le résultat lorsque la revue est requise. |
| **Approbateur** | Valide si une autorité supérieure est nécessaire. |

Une même personne peut cumuler des rôles seulement si la politique de l’entreprise et la criticité de la tâche l’autorisent. Une tâche critique peut exiger un relecteur distinct de l’exécutant.

### 21.4. Dépendances et blocages

| Type de dépendance | Politique |
|---|---|
| `FORTE` | Empêche la fin de la tâche dépendante. |
| `SOUPLE` | Permet la fin avec avertissement visible dans la préparation. |
| `INFORMATIONNELLE` | Informe sans bloquer ni dégrader automatiquement l’état. |

Un blocage possède obligatoirement : type, objet bloquant, source, motif, auteur, date, propriétaire de résolution et état de résolution. `BLOQUEE` seul n’est jamais une information suffisante.

### 21.5. Invariants

1. Une tâche est rattachée à une seule affaire et peut référencer une exigence, une preuve, un document, une demande ou un impact DCE.
2. Une tâche terminée possède un résultat de fin, une source/preuve ou une dérogation explicitement identifiée.
3. Une tâche à dépendance forte insatisfaite ne peut pas devenir `TERMINEE`.
4. Une tâche remplacée est non modifiable ; elle référence la tâche qui la remplace.
5. Une boucle de dépendances est interdite.
6. Deux tâches actives ne peuvent pas avoir la même finalité, affaire, objet source et responsabilité sans justification explicite de parallélisation.

### 21.6. Faits métier

`TaskCreated`, `TaskClaimed`, `TaskAssigneeChanged`, `TaskResultRecorded`, `TaskBlockerDeclared`, `TaskUnblocked`, `TaskDependencyAdded`, `TaskDependencyRemoved`, `TaskReviewRequested`, `TaskCompleted`, `TaskReplaced`, `TaskAbandoned`.

---

## 22. `DMD` — Demande, réponse et clarification

### 22.1. Responsabilité

Une demande structure ce qui est attendu d’un patron, collaborateur ou partenaire : pièce, information, disponibilité, relecture, clarification ou décision. Elle ne remplace ni la tâche, ni la revue, ni la décision. Elle peut être causée par une tâche et sa réponse peut alimenter une revue ou une preuve.

### 22.2. États

| État | Sens |
|---|---|
| `PREPAREE` | Brouillon non envoyé. |
| `ENVOYEE` | Demande remise au destinataire. |
| `REPONSE_RECUE` | Réponse enregistrée, non encore acceptée comme utile/preuve. |
| `EN_REVUE` | Réponse évaluée par une personne autorisée. |
| `ACCEPTEE` | Réponse utilisable pour l’objet visé. |
| `REJETEE` | Réponse insuffisante ou non conforme, motif conservé. |
| `A_CLARIFIER` | Réponse partielle ou ambiguë. |
| `ANNULEE` | Demande annulée avec motif. |
| `EXPIREE` | Délai dépassé sans réponse finale. |

### 22.3. Invariants

1. Une demande possède un demandeur, un destinataire, une affaire, un objet demandé, une raison et un état.
2. Une réponse est versionnée, horodatée et ne clôt jamais automatiquement une tâche critique.
3. Une réponse partenaire devient une preuve potentielle uniquement après revue et autorisation d’usage.
4. Une relance est liée à la demande d’origine et ne crée pas une nouvelle demande métier.
5. Une demande expirée reste consultable ; elle peut être relancée ou remplacée selon permission.

### 22.4. Faits métier

`RequestCreated`, `RequestSent`, `RequestReminderSent`, `RequestResponseReceived`, `RequestResponseAccepted`, `RequestResponseRejected`, `RequestClarificationRequested`, `RequestCancelled`, `RequestExpired`.

---

## 23. `REV` — Revue de travail

### 23.1. Responsabilité

La revue vérifie un objet identifié : résultat de tâche, document, réponse, capacité, preuve, compatibilité de réemploi ou engagement candidat. Elle ne modifie jamais l’original silencieusement ; elle accepte, retourne ou rejette une version précise.

### 23.2. États et invariants

| État | Règle |
|---|---|
| `OUVERTE` | Objet, version et relecteur sont obligatoires. |
| `EN_COURS` | Relecteur actif. |
| `ACCEPTEE` | La version revue est explicitement acceptée pour le niveau de revue défini. |
| `RETOURNEE` | Corrections ciblées, sans écraser le résultat initial. |
| `REJETEE` | Objet impropre avec motif. |
| `ANNULEE` | Objet remplacé, permission retirée ou demande annulée. |

1. Une revue concerne une version précise ; une nouvelle version nécessite une nouvelle revue ou une reprise explicite.
2. Le relecteur doit disposer de l’accès à l’objet et de l’action `VALIDATE` sur la classe de ressource.
3. Une revue acceptée ne transforme pas seule un engagement candidat en décision patron ; elle atteste uniquement le niveau de contrôle défini.
4. Le retour crée ou réactive les tâches de correction concernées.

### 23.3. Faits métier

`ReviewOpened`, `ReviewStarted`, `ReviewAccepted`, `ReviewReturnedWithCorrections`, `ReviewRejected`, `ReviewCancelled`.

---

## 24. `PRE` — Paquet de préparation et disponibilité

### 24.1. Responsabilité

Le paquet de préparation représente le contenu **vivant** que le collaborateur prépare avant transmission : exigences, tâches, documents, preuves, brouillons techniques, demandes, risques visibles et décisions attendues. Il ne constitue ni une offre déposée, ni une version de prix, ni une décision patron.

### 24.2. États

| État | Sens |
|---|---|
| `EN_PREPARATION` | Travail vivant en cours. |
| `A_REVOIR` | Rectificatif, retour ou changement significatif affecte le contenu. |
| `PRET_POUR_REVUE` | Contrôle de préparation favorable ; transmission potentielle. |
| `TRANSMIS` | Un instantané a été soumis au patron ; le paquet vivant peut continuer à évoluer séparément. |
| `RETOURNE_AVEC_CORRECTIONS` | Patron ou relecteur demande un nouveau cycle ciblé. |
| `ACCEPTE_POUR_PHASE_SUIVANTE` | Préparation reçue pour chiffrage/contrôle ultérieur ; aucun accès financier accordé. |
| `ARCHIVE` | Cycle terminé, références conservées. |

### 24.3. Politique de disponibilité

La disponibilité est une évaluation du domaine, jamais un booléen saisi par le collaborateur.

| Résultat | Signification |
|---|---|
| `READY` | Aucun blocage ; transmission possible. |
| `READY_WITH_WARNINGS` | Pas de blocage, avertissements visibles dans l’instantané. |
| `BLOCKED` | Un ou plusieurs bloqueurs non résolus/non dérogés empêchent la transmission. |

La décision renvoie séparément `blockers`, `warnings` et `informational`. Les règles de préparation sont versionnées par type d’affaire/lot si nécessaire.

### 24.4. Invariants

1. Un paquet de préparation appartient à une affaire et une version DCE applicable.
2. Le paquet ne contient jamais de prix, marge, devis privé ou décision stratégique patron.
3. Un paquet `PRET_POUR_REVUE` référence la dernière évaluation de disponibilité encore valide.
4. Une modification d’exigence, de document, de tâche, de preuve ou de DCE concernée rend l’évaluation à revoir selon les règles d’impact.
5. La transmission ne fige jamais le paquet vivant ; elle crée un `SNP` distinct.

### 24.5. Faits métier

`PreparationReadinessEvaluated`, `PreparationDeclaredReady`, `PreparationMarkedForRework`, `ReadinessWaiverRequested`, `ReadinessWaiverGranted`, `ReadinessWaiverRefused`, `PreparationAcceptedForNextPhase`.

---

## 25. `SNP` — Instantané de préparation

### 25.1. Responsabilité

L’instantané est la photographie **immuable** remise au patron. Il permet de savoir exactement ce qui a été transmis, même si l’affaire, le DCE, les tâches ou les documents évoluent ensuite.

### 25.2. Contenu minimal

| Élément figé | Exigence |
|---|---|
| Affaire et affectation | Identifiants, rôle, périmètre, auteur de transmission. |
| Version DCE | Version applicable, référence de consultation et lot. |
| Exigences | Identifiants, états, sources et éléments non résolus. |
| Preuves | Références de versions, état d’usage, dates. |
| Documents préparés | Versions précises et statut de revue. |
| Tâches | État, résultat, blocages, dépendances critiques. |
| Demandes | Demandes ouvertes et réponses en attente/revue. |
| Risques visibles | Type, source, criticité, traitement préparatoire. |
| Décisions demandées | Questions explicites remises au patron. |
| Disponibilité | Résultat `READY`, `READY_WITH_WARNINGS` ou `BLOCKED`, détails. |
| Intégrité | `snapshot_id`, `snapshot_version`, `content_hash`, auteur, date. |

### 25.3. Invariants

1. Un instantané est append-only et ne peut jamais être modifié après création.
2. Son empreinte est calculée à partir de son contenu canonique et de références de versions stables.
3. Un instantané ne peut être créé que depuis un paquet de préparation et une évaluation de disponibilité valides.
4. Une version DCE ou une ressource ultérieure ne réécrit jamais un instantané ; elle peut le rendre historiquement non actuel via `IMP`.
5. L’existence d’un instantané ne signifie pas que le patron l’a reçu, approuvé ou utilisé pour le prix.

### 25.4. Faits métier

`PreparationSnapshotCreated`, `PreparationSnapshotIntegrityVerified`, `PreparationSnapshotMarkedStale`, `PreparationSnapshotSuperseded`.

---

## 26. `TRN` — Transmission au patron

### 26.1. Responsabilité

La transmission relie un instantané à un destinataire patron et gère son cycle de réception, retour et prise en compte. Elle ne devient pas une décision patron ; elle déclenche au plus une Action patron de revue.

### 26.2. États

| État | Sens |
|---|---|
| `PRETE_A_SOUMETTRE` | Préparation/instantané disponibles ; commande non encore acceptée. |
| `TRANSMISE` | Instantané envoyé à la file patron. |
| `RECUE` | Patron ou délégataire a accusé la réception métier. |
| `RETOURNEE` | Corrections ciblées demandées. |
| `ACCEPTEE_POUR_PHASE_SUIVANTE` | Préparation utilisée comme base pour chiffrage ou contrôle ultérieur. |
| `RETIREE_AVANT_RECEPTION` | Transmission retirée avant lecture/réception patron. |
| `INVALIDEe_PAR_IMPACT` | Snapshot ou contenu rendu non actuel par impact significatif. |
| `SUPERSEDEE` | Une transmission plus récente remplace la transmission courante. |

### 26.3. Invariants

1. Une transmission référence un seul instantané immuable et un destinataire patron/délégataire.
2. Une transmission reçue ne peut pas être retirée ; un nouveau cycle de préparation est requis.
3. Une transmission retournée doit contenir au moins une correction/action ciblée.
4. Une acceptation pour phase suivante ne crée pas un droit collaborateur sur `PRX`.
5. Deux transmissions actives identiques du même instantané vers le même destinataire sont interdites.

### 26.4. Faits métier

`PreparationSubmittedToPatron`, `PreparationReceivedByPatron`, `PreparationReturnedByPatron`, `PreparationAcceptedForPricing`, `PreparationWithdrawnBeforeReceipt`, `PreparationTransmissionInvalidated`, `PreparationTransmissionSuperseded`.

---

## 27. `SHR` — Partage externe

### 27.1. Responsabilité

Le partage externe permet à un partenaire de consulter ou remettre des ressources précises sans recevoir l’accès global à l’affaire. Chaque partage est limité par destinataire, ressources versionnées, verbes d’accès, périmètre et date d’expiration.

### 27.2. États

| État | Sens |
|---|---|
| `PREPARE` | Partage configuré, pas encore actif. |
| `ACTIF` | Ressources et permissions autorisées disponibles au partenaire. |
| `EXPIRE` | Date atteinte ; accès supprimé. |
| `REVOQUE` | Retrait explicite par acteur autorisé. |
| `REMPLACE` | Nouveau partage distinct pour ressources ou versions différentes. |

### 27.3. Invariants

1. Toute ressource partagée est une version précise, une classe autorisée et un périmètre explicite.
2. Une nouvelle version d’une ressource n’est jamais ajoutée à un partage existant sans nouvelle commande explicite.
3. Aucun partage collaborateur ne peut inclure une ressource financière ou stratégique non explicitement déléguée par le patron.
4. Expiration ou révocation coupe l’accès futur sans effacer les réponses et faits historiques du partenaire.
5. Toute lecture partenaire réévalue le partage actif, le destinataire, la version et le verbe autorisé.

### 27.4. Faits métier

`ExternalSharePrepared`, `ExternalShareGranted`, `ExternalShareExpired`, `ExternalShareRevoked`, `ExternalShareReplaced`, `PartnerResourceAccessed` lorsque la politique d’audit métier le requiert.

---

## 28. `IMP` — Évaluation d’impact DCE

### 28.1. Responsabilité

L’évaluation d’impact répond à la question : **« qu’est-ce qui devient à revoir après une nouvelle version du DCE ? »** Elle ne modifie ni l’original acheteur, ni le travail historique ; elle relie une version source et une version cible à des objets affectés et justifie chaque impact.

### 28.2. États

| État | Sens |
|---|---|
| `A_EVALUER` | Nouvelle version DCE reçue, analyse d’impact non finalisée. |
| `EN_EVALUATION` | Comparaison et rapprochement en cours. |
| `EVALUATION_TERMINEE` | Impacts identifiés et classés. |
| `A_CONFIRMATION_HUMAINE` | Un impact reste incertain ou contradictoire. |
| `APPLIQUEE` | Les objets concernés sont marqués à revoir, confirmés ou inchangés selon la politique. |
| `SANS_IMPACT_METIER` | Comparaison faite, aucun objet métier affecté. |

### 28.3. Invariants

1. Une évaluation associe obligatoirement une version DCE précédente et une version DCE nouvelle, ou un motif explicite d’absence de version antérieure.
2. Chaque impact identifie l’objet concerné, le type de changement, les sources avant/après, le niveau de certitude et la conséquence proposée.
3. L’interface affiche l’impact ; elle ne le calcule pas ni ne modifie elle-même les états métiers.
4. Un objet affecté devient `à revoir` ou `obsolète` selon la politique ; l’objet historique et l’ancien instantané restent conservés.
5. Un impact sur une transmission active peut créer une Action patron et rendre la transmission non actuelle, sans supprimer la décision historique.

### 28.4. Faits métier

`DceImpactAssessmentStarted`, `DceImpactIdentified`, `DceImpactConfirmed`, `DceImpactApplied`, `DceImpactRequiresHumanReview`, `DceImpactCompletedWithoutBusinessEffect`.

---

## 29. Relations collaborateur et règles de conservation

| Relation | Cardinalité | Contrat de conservation |
|---|---|---|
| Affaire → Affectations | 1 → N | Toutes les affectations historiques restent consultables selon droits. |
| Affaire → Tâches | 1 → N | Tâches terminées/remplacées/abandonnées conservées. |
| Tâche → Dépendances | N ↔ N orientée | Aucune boucle ; type de dépendance conservé. |
| Tâche → Résultats | 1 → N | Résultats versionnés ; aucun écrasement silencieux. |
| Demande → Réponses | 1 → N | Réponses conservées, une réponse peut être revue plusieurs fois. |
| Revue → Objet versionné | N → 1 | La revue pointe une version précise et ne la modifie pas. |
| Paquet de préparation → Instantanés | 1 → N | Chaque transmission crée un snapshot distinct ; paquet vivant séparé. |
| Instantané → Transmission | 1 → N contrôlée | Une seule transmission active identique par destinataire. |
| Partage externe → Ressources | 1 → N | Chaque ressource est versionnée ; nouvelle version = nouveau partage. |
| Évaluation d’impact → Objets affectés | 1 → N | L’impact relie, ne supprime pas ; chaque conséquence est traçable. |

---

## 30. Concurrence, idempotence et projections collaborateur

### 30.1. Concurrence

Les frontières `TSK`, `DMD`, `REV`, `PRE`, `TRN`, `SHR` et `IMP` portent une version de concurrence. Une commande sensible indique la version attendue de la frontière. En cas de divergence, le domaine refuse la mutation et retourne un conflit métier compréhensible : objet modifié, auteur/date connue lorsque autorisé, et nécessité de recharger ou de revoir.

Les politiques suivantes sont impératives :

| Situation | Politique |
|---|---|
| Deux personnes terminent une tâche | Première transition acceptée ; seconde réponse idempotente si même commande, sinon conflit. |
| Résultat de tâche concurrent | Nouvelle version ou conflit explicite ; jamais écrasement silencieux. |
| Transmission répétée | Même clé d’idempotence = même transmission ; autre contenu = nouvelle évaluation/snapshot requis. |
| Affectation retirée en cours d’action | Commande refusée au contrôle serveur ; brouillon historique conservé. |
| Partage externe concurrent | Un partage n’est actif qu’après contrôle du destinataire, périmètre et version. |

### 30.2. Idempotence

Chaque commande critique porte : entreprise, acteur, type de commande, clé d’idempotence, empreinte de requête, date de réception et résultat terminal. Une clé réutilisée avec une empreinte différente est refusée ; une même empreinte retourne le résultat initial sans recréer de fait métier.

### 30.3. Situations préparées

| Situation préparée | Alimentation principale | Consistance attendue |
|---|---|---|
| **Mon travail aujourd’hui** | Affectations actives, tâches, demandes, retours et échéances. | Peut être différée ; fraîcheur visible. |
| **Mes affaires** | Affaires affectées, état de préparation et blocages de périmètre. | Peut être différée ; contrôle d’accès strict à la lecture. |
| **Espace de préparation** | DCE courant, tâches, exigences, documents, demandes, paquet. | À jour lors d’une commande critique. |
| **Contrôle de préparation** | Paquet, tâches, règles de disponibilité, impacts et dérogations. | Stricte avant transmission. |
| **Impact DCE** | Version DCE source/cible, objets affectés et revue humaine. | Stricte avant marquage des objets. |
| **Command Center patron** | Transmissions, risques, actions patron et impacts significatifs. | Peut être différée ; état de fraîcheur affiché. |

---

## 31. Faits métier collaborateur dans le Journal de vérité

Les faits collaborateur importants enrichissent le Journal de vérité sans exposer les données privées du patron. Le journal sélectionne les faits utiles à l’affaire : transmission, rectificatif, tâche critique terminée/bloquée, demande partenaire importante, revue acceptée/rejetée, retrait d’affectation, snapshot créé ou impact DCE appliqué.

La Timeline collaborateur reste une projection de travail de périmètre limité. L’Audit de sécurité conserve les détails de connexion, autorisation et commandes, mais n’est pas un outil de suivi métier.

---

## 32. Critères de recette de l’extension collaborateur

| ID | Scénario | Preuve attendue |
|---|---|---|
| `DOM-COL-01` | Affectation retirée pendant une saisie. | Brouillon et faits conservés ; toute commande ultérieure refusée par `ASN`. |
| `DOM-COL-02` | Deux collaborateurs terminent la même tâche. | Une seule fin de tâche durable ; conflit ou résultat idempotent clair. |
| `DOM-COL-03` | Réponse partenaire reçue. | Demande à `REPONSE_RECUE` ; aucune preuve/tâche critique automatiquement clôturée. |
| `DOM-COL-04` | Résultat soumis à revue puis corrigé. | Revue référence la version exacte ; retour crée/réactive les tâches ciblées. |
| `DOM-COL-05` | Préparation avec avertissement non bloquant. | `READY_WITH_WARNINGS`, snapshot complet et transmission autorisée. |
| `DOM-COL-06` | Préparation avec exigence bloquante manquante. | `BLOCKED`, aucun snapshot de transmission et liste de bloqueurs explicite. |
| `DOM-COL-07` | Transmission patron répétée après retry réseau. | Un seul snapshot/transmission et même résultat terminal. |
| `DOM-COL-08` | Nouvelle version DCE touche une exigence déjà transmise. | Impact durable, ancien snapshot conservé, travail courant à revoir et action patron créée si nécessaire. |
| `DOM-COL-09` | Nouvelle version d’un document partagé existe. | Nouveau partage requis ; partenaire ne reçoit pas la version nouvelle. |
| `DOM-COL-10` | Collaborateur tente un accès financier par navigation ou commande. | Refus sans révéler prix, marge, devis ni existence d’une ressource sensible. |

## 33. Décisions de gel V8.1

1. `ASN`, `TSK`, `DMD`, `REV`, `PRE`, `SNP`, `TRN`, `SHR` et `IMP` sont désormais des frontières formelles du domaine V8.
2. Les exigences restent liées au `DCE` et aux analyses vérifiées ; les preuves/documents restent sous `PRF`; les collaborateurs ne dupliquent pas ces propriétaires.
3. Le paquet vivant (`PRE`) et l’instantané immuable (`SNP`) sont deux réalités distinctes et non interchangeables.
4. Une transmission patron (`TRN`) ne produit jamais une décision, un prix ou un droit financier.
5. Les impacts DCE (`IMP`) ciblent le travail à revoir sans effacer les versions, snapshots ou décisions historiques.
6. Toute commande collaborateur devra dériver de ces frontières, exiger une affectation contextualisée et suivre la politique commune d’idempotence et de concurrence.

# Partie IV — Passe de clarification V1.2

## 34. Objet de la passe V1.2

Cette passe ne change pas les parcours patron ou collaborateur validés. Elle empêche seulement de transformer les mots du métier en un modèle technique ambigu. Les termes **frontière métier**, **bounded context**, **aggregate**, **entité**, **objet-valeur**, **politique**, **processus** et **projection** ne sont pas interchangeables.

> **Règle V8.2 :** une frontière métier décrit une responsabilité. Elle ne devient pas automatiquement un aggregate, une table, un repository ou un service. La matrice `DOMAIN-01 — Aggregate / Ownership / Consistency` devra prendre cette décision explicitement pour chaque réalité.

| Niveau | Rôle dans V8 | Exemple |
|---|---|---|
| **Bounded Context** | Vocabulaire et règles qui doivent rester cohérents ensemble. | Collaboration, Prix, Dépôt, Preuves. |
| **Aggregate** | Consistance atomique d’une mutation ; une transaction ne possède qu’un aggregate racine. | Décision, Tâche, Affectation, Snapshot. |
| **Entité** | Identité durable interne à un aggregate ou un contexte. | Dépendance de tâche, cause d’action, condition de décision. |
| **Objet-valeur** | Valeur sans identité propre, remplacée comme un tout. | Argent, plage de dates, portée, provenance, empreinte. |
| **Politique** | Règle de calcul, de contrôle ou de classement sans propriété durable autonome. | Calcul de disponibilité, règle d’impact DCE, priorité de tâche. |
| **Processus / orchestrateur** | Réagit à un événement et demande une conséquence dans une autre frontière. | Après impact DCE, créer une action patron ou demander une revue. |
| **Projection** | Vue reconstruisible pour l’interface ; jamais propriétaire de vérité. | Cockpit, Mon travail aujourd’hui, Journal de vérité. |

## 35. Terminologie non ambiguë : source, fait, interprétation et événement

SMART_AO ne doit jamais confondre ce qui est écrit dans un DCE, ce que le système interprète et ce qui a changé dans le logiciel.

| Terme V8 | Définition | Exemple |
|---|---|---|
| **Énoncé source** | Extrait localisé d’un document/version DCE ou d’une autre pièce originale. | « La visite est obligatoire ». |
| **Fait métier** | Assertion structurée sur une situation métier, sourcée et qualifiée. | « Visite obligatoire pour le lot 03 ». |
| **Exigence interprétée** | Obligation, critère, interdiction ou attente structurée à partir d’un ou plusieurs énoncés sources. | Type `VISITE`, portée lot 03, date connue ou `à vérifier`. |
| **Preuve** | Document, version ou élément autorisé à démontrer une capacité ou couvrir une exigence. | Attestation de visite, Qualibat, référence chantier. |
| **Couverture de preuve** | Relation explicite entre une exigence et une ou plusieurs preuves. | `COMPLETE`, `PARTIELLE`, `INAPPLICABLE`, `CONTRADICTOIRE`, `A_VERIFIER`. |
| **Évaluation** | Appréciation structurée Requirement × Capacité × Preuve. | `COUVERT`, `PARTIEL`, `MANQUANT`, `INCONNU`, `CONTRADICTOIRE`. |
| **Constat (Finding)** | Résultat d’analyse interprétable, avec provenance, certitude, objets concernés et conséquences possibles. | « L’attestation disponible ne couvre pas le périmètre demandé ». |
| **Risque** | Conséquence défavorable potentielle d’un constat, d’une exigence ou d’un écart. | Risque d’irrecevabilité ou de retard. |
| **Événement de domaine** | Changement durable provoqué par une commande acceptée. | `QualificationMarkedExpired`, `TaskCompleted`. |

La chaîne métier de référence devient donc :

```text
Document/version source
  → énoncé source
  → fait / exigence interprétée
  → preuve + couverture
  → évaluation
  → constat
  → risque
  → protection / tâche / action patron
  → décision
```

`Analysis` n’est jamais un aggregate fourre-tout. C’est un processus ou un ensemble de résultats qui produit des exigences, évaluations, constats et impacts, chacun avec une identité, une provenance et un cycle propre.

## 36. Consultation, DCE, lot et périmètre d’affaire

Les relations suivantes sont désormais normatives :

```text
Consultation
  ├── Lots
  └── Versions DCE

Affaire
  ├── référence une Consultation
  └── référence un Périmètre d’affaire explicite
        ├── lot unique
        ├── ensemble de lots autorisé
        ├── tranche
        ├── variante / prestation supplémentaire
        └── périmètre personnalisé justifié
```

Une version DCE reste l’original acheteur et ses pièces. Elle est la source des énoncés, non le propriétaire direct de l’interprétation ou de la décision. L’Affaire est un aggregate minimal candidat : identité, rattachement consultation/périmètre, état de cycle de vie, responsabilité courante et références croisées. Elle **référence** les analyses, décisions, prix, dépôts, tâches et preuves ; elle ne les possède pas tous comme enfants mutables.

## 37. Organisation et capacités : décomposition obligatoire sans multiplication prématurée des contexts

`ORG` reste un bounded context unique au lancement, mais ne doit jamais devenir un objet fourre-tout. Sa décomposition conceptuelle est obligatoire :

| Sous-ensemble `ORG` | Réalité possédée | Exemples |
|---|---|---|
| **Profil entreprise** | Identité et coordonnées de l’entreprise. | SIREN, signataires, adresses. |
| **Capacités** | Ce que l’entreprise peut mobiliser. | Équipe, matériel, savoir-faire. |
| **Qualifications** | Titres, certifications et périodes de validité. | Qualibat, assurance. |
| **Références** | Réalisations et preuves réutilisables sous conditions. | Chantier similaire, attestation. |
| **Partenaires** | Parties externes mobilisables et leurs pièces. | Fournisseur, sous-traitant, cotraitant. |
| **Politiques internes** | Règles privées et gouvernance. | Règles de réemploi, confidentialité. |

La matrice `DOMAIN-01` déterminera lesquels deviennent des aggregates distincts. Aucune commande ne peut modifier simultanément plusieurs sous-ensembles dans une seule transaction atomique sans justification explicite.

## 38. Axes d’état normalisés

Un seul champ `status` ne doit jamais mélanger résultat, cycle, validité et fraîcheur. Les axes sont séparés partout où ils ont un sens :

| Axe | Question répondue | Exemples |
|---|---|---|
| **Lifecycle** | Où en est l’objet dans son cycle ? | `ACTIVE`, `COMPLETED`, `SUPERSEDED`, `ARCHIVED`. |
| **Disposition / Outcome** | Quel choix ou résultat a été produit ? | `GO`, `GO_WITH_CONDITIONS`, `NO_GO`; `ACCEPTED`, `REFUSED`. |
| **Validity** | Le contenu reste-t-il applicable au contexte ? | `CURRENT`, `STALE`, `EXPIRED`, `NOT_APPLICABLE`. |
| **Readiness** | Peut-il passer à l’étape suivante ? | `READY`, `READY_WITH_WARNINGS`, `BLOCKED`. |
| **Freshness** | L’information affichée reflète-t-elle l’état récent attendu ? | `FRESH`, `STALE`, `PARTIAL`, `UNKNOWN`. |
| **Work state** | Quel est l’avancement d’un travail ? | `TODO`, `IN_PROGRESS`, `WAITING`, `BLOCKED`, `DONE`. |
| **Alert severity** | Quelle attention mérite-t-elle ? | `URGENT`, `BLOCKING`, `AT_RISK`, `WATCH`. |

Pour une décision, la normalisation est impérative : `decision_type`, `outcome/disposition`, `lifecycle` et `validity` sont distincts. Une décision peut être `GO_WITH_CONDITIONS`, `SUPERSEDED` et historiquement valide au moment où elle a été prise.

## 39. Politique globale de version et de temps

Toute réalité versionnée utilise une sémantique commune, sans imposer que chaque aggregate ait la même structure physique.

| Attribut | Contrat |
|---|---|
| `business_version_id` | Identifie une version métier immuable, par exemple DCE V3 ou document V2. |
| `predecessor_version_id` | Référence la version métier remplacée, si elle existe. |
| `superseded_by_version_id` | Référence la version qui prend effet pour l’avenir. |
| `content_hash` | Empreinte du contenu canonique lorsqu’il est applicable. |
| `effective_at` | Moment à partir duquel le contenu doit être considéré applicable. |
| `created_at` | Moment de création dans SMART_AO. |
| `author/origin` | Auteur humain, système ou fournisseur source. |
| `observed_at` | Moment où SMART_AO ou un acteur a constaté l’information. |
| `occurred_at` | Moment du changement métier. |
| `recorded_at` | Moment où le changement a été enregistré durablement. |

`business_version_id` ne doit jamais être confondu avec `aggregate_revision`. La première est un fait métier ; la seconde est la révision de concurrence attendue pour éviter un écrasement concurrent.

## 40. Transactions atomiques, événements et projections

> **Règle d’atomicité V8 :** une transaction métier atomique modifie un seul aggregate propriétaire. Les conséquences dans une autre frontière sont déclenchées par des événements et doivent être idempotentes.

Cette règle interdit les transactions géantes de type « affectation + tâches + action patron + journal » dans une même mutation multi-frontières. Une commande peut valider et modifier son aggregate, produire son événement interne et inscrire celui-ci dans une outbox transactionnelle. Les processus aval créent ensuite leurs propres commandes idempotentes.

| Type d’événement | Contrat |
|---|---|
| **Événement interne** | Produit à l’intérieur d’un bounded context ; son payload peut évoluer avec le contexte. |
| **Événement publié / intégration** | Contrat stable, versionné et minimal, destiné à d’autres contexts, projections ou intégrations. |
| **Projection** | Consomme des événements, est reconstruisible et ne devient jamais propriétaire de l’état métier. |
| **Journal de vérité** | Projection métier lisible ; ni event store universel ni source transactionnelle. |

V8 ne prescrit **pas** un Event Sourcing complet. Le système peut utiliser une persistance classique avec historique versionné, événements de domaine, outbox et projections. L’exigence est la reconstructibilité des changements critiques, non le replay obligatoire de toute vérité depuis un flux d’événements.

Chaque enveloppe d’événement de domaine contient au minimum : `event_id`, `event_type`, `event_contract_version`, `tenant_id`, `aggregate_type`, `aggregate_id`, `aggregate_revision`, `occurred_at`, `recorded_at`, `actor`, `correlation_id`, `causation_id` et `payload` métier minimal.

## 41. Identités, tenant context et invariants transverses

| Identité / contexte | Règle |
|---|---|
| **Aggregate identity** | Identifie une réalité propriétaire de mutation. |
| **Tenant identity** | Identifie l’entreprise propriétaire. |
| **Correlation identity** | Lie les changements d’un même parcours ou traitement. |
| **Causation identity** | Lie un événement à la commande ou l’événement qui l’a causé. |
| **Business version** | Identifie une version métier immuable. |
| **Aggregate revision** | Révision de concurrence, utilisée avec `expected_revision`. |

> **Invariant de sécurité P0 :** le tenant context est dérivé de l’identité authentifiée et de l’hôte/instance autorisé. L’appelant ne choisit jamais arbitrairement l’entreprise cible. Toute valeur de tenant présente dans une commande est validée contre ce contexte résolu côté serveur.

Les invariants sont classés en quatre familles :

| Famille | Questions couvertes |
|---|---|
| **Identité** | Tenant, propriétaire, périmètre, identifiant stable, relation autorisée. |
| **État** | Transition permise, révision attendue, disponibilité et cycle légal. |
| **Provenance** | Source, version, auteur, horloges métier, justification. |
| **Sécurité** | Autorisation, confidentialité, délégation, partage et retrait d’accès. |

## 42. Couverture, évaluation, constat, risque et protection

La relation entre exigence et preuve devient explicite afin d’éviter toute logique dispersée de type « chercher un document qui ressemble ».

```text
Exigence interprétée
  ← Coverage → Preuve(s)
  + Capacité(s)
  → Évaluation
  → Constat
  → Risque
  → Plan de protection
  → Tâches ou Action patron
```

| Réalité | Responsabilité minimale |
|---|---|
| **Coverage** | Lie une exigence à des preuves/version(s) avec portée et état `COMPLETE`, `PARTIAL`, `INAPPLICABLE`, `CONFLICTING` ou `A_VERIFIER`. |
| **Assessment** | Évalue l’adéquation Exigence × Capacité × Coverage ; résultat `MATCH`, `PARTIAL`, `MISSING`, `UNKNOWN` ou `CONFLICTING`. |
| **Finding** | Constat avec provenance, niveau de confiance, objets affectés, état et conséquences possibles. |
| **Risk** | Risque décrit par impact, probabilité/criticité si connue, sources et propriétaire de traitement. |
| **ProtectionPlan** | Plan de réduction d’un risque ; il référence les tâches ou actions concrètes mais n’est pas leur synonyme. |

La matrice `DOMAIN-01` décidera si `Coverage`, `Assessment`, `Finding`, `Risk` et `ProtectionPlan` sont aggregates autonomes, entités ou politiques. Leur responsabilité métier et leurs relations sont toutefois figées dès maintenant.

## 43. Ownership, relations et dépendances autorisées

Les relations doivent préciser leur sens. Une référence ne donne jamais un droit de mutation ou de suppression au référent.

| Verbe relationnel | Sens contractuel |
|---|---|
| `OWNS` | Même aggregate : conservation et cycle de vie atomiques. |
| `REFERENCES` | Lien par identité vers une autre frontière ; aucune possession. |
| `DEPENDS_ON` | La validité/readiness dépend d’un autre objet sans le posséder. |
| `DERIVED_FROM` | Résultat calculé/interprété à partir d’une source/version. |
| `COVERS` | Preuve reliée à une exigence avec état de couverture. |
| `AFFECTS` | Changement/impact qui impose une relecture ou une action sur un objet. |

| Réalité | `OWNS` minimal | `REFERENCES` / autres relations |
|---|---|---|
| **Affaire** | Son identité, cycle, périmètre et responsabilité courante. | `REFERENCES` Consultation, Scope, DCE courant, Assignments, Decisions, Pricing, Submission, Preparation. |
| **DCE** | Originaux et versions DCE. | `DERIVED_FROM` énoncés sources ; `AFFECTS` ImpactAssessments. |
| **Exigence** | Interprétation, portée, statut et provenance. | `DERIVED_FROM` énoncés sources ; `COVERS` preuves ; `REFERENCES` Affaire/Scope. |
| **Preuve** | Original, versions, métadonnées et autorisations d’usage. | `COVERS` exigences ; `REFERENCES` capacités/partenaires. |
| **Prix officiel** | Version de prix, contexte, hypothèses et résultat déterministe. | `REFERENCES` snapshot DCE/exigences, devis, scénario, décision. |
| **Dépôt** | Paquet, versions incluses, fingerprint et accusé. | `REFERENCES` prix officiel, DCE, décision, contexte de dépôt. |
| **Tâche** | Travail, résultat, blocages et dépendances. | `REFERENCES` exigence, demande, revue, impact, affectation. |

## 44. Prix et dépôt reconstructibles

Une version officielle de prix est valide seulement si elle référence son contexte documentaire et de calcul : version DCE, instantané d’exigences, sources de coûts, devis fournisseurs, scénario, version de calcul déterministe, hypothèses et acteur de validation.

Un paquet de dépôt possède un `submission_fingerprint` comprenant au minimum : identifiant/ version du paquet, `content_hash`, version DCE, version officielle de prix applicable et contexte de décision/autorisation. Cette empreinte ne remplace pas l’accusé ; elle identifie exactement ce qui a été autorisé et déclaré.

## 45. Cohérence de lecture et sémantique de retry

| Niveau | Contrat |
|---|---|
| **Strong consistency** | Obligatoire à la mutation de l’aggregate propriétaire, aux décisions, au prix, au snapshot, à la transmission et au dépôt. |
| **Read-your-own-write** | Après une commande acceptée, l’acteur voit immédiatement son propre résultat ou un état de traitement explicite. |
| **Eventual consistency** | Autorisée pour cockpit, listes, notifications, indicateurs et journal, avec fraîcheur affichée. |
| **Retryable** | Échec technique ou timeout sans résultat confirmé ; même clé d’idempotence requise. |
| **Non-retryable** | Autorisation refusée, validation métier invalide ou commande incompatible avec l’état. |
| **Conflict** | `expected_revision` divergent ; l’utilisateur doit recharger/réconcilier. |
| **Stale context** | Référence DCE, snapshot, autorisation ou autre contexte plus applicable ; nouveau cycle requis. |

Une commande est une intention immuable. Elle comporte l’intention métier, le contexte authentifié résolu, ses préconditions d’autorisation, ses préconditions métier, `expected_revision`, clé d’idempotence et empreinte de requête. Son traitement et son résultat sont historisés séparément.

## 46. Décisions de gel V1.2 et prochaine passe obligatoire

1. Le Contrat de domaine V8 v1.2 distingue formellement énoncé source, fait métier, exigence interprétée, preuve, couverture, évaluation, constat, risque, plan de protection et événement de domaine.
2. `Événement de domaine` remplace partout le terme ambigu `Fait métier` lorsqu’il s’agit d’un changement produit par une commande.
3. Les frontières métier actuelles restent des responsabilités de domaine ; elles ne sont pas automatiquement des aggregates.
4. `ORG` est décomposé conceptuellement ; `AFF` est un aggregate minimal candidat qui référence davantage qu’il ne possède.
5. Les axes lifecycle, outcome, validity, readiness, freshness, work state et alert severity sont séparés.
6. Toute nouvelle version utilise la politique globale de version ; toute concurrence utilise `expected_revision`, distinct de la version métier.
7. Une transaction atomique ne modifie qu’un aggregate propriétaire ; les conséquences inter-frontières passent par événements, outbox et commandes idempotentes.
8. Le tenant context est résolu côté serveur à partir de l’identité authentifiée ; il n’est jamais choisi librement par le client.
9. Les projections, y compris le Journal de vérité, sont reconstruisibles et ne possèdent jamais l’état métier.
10. Avant tout modèle Pydantic, SQLAlchemy, repository ou API d’écriture, la passe suivante obligatoire est : **`DOMAIN-01 — Aggregate / Ownership / Consistency Matrix`**.

## Références internes

- `SMART_AO_VISION_METIER_PARCOURS_UTILISATEUR.md`
- `SMART_AO_V8_CAHIER_ESPACE_PATRON.md`
- `SMART_AO_V8_CONTRAT_METIER_VERS_INTERFACE.md`
- `SMART_AO_V8_MATRICE_TRANSITIONS_METIER.md`
- `SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md`

---

**Fin du Contrat de domaine V8 — version 1.0**
