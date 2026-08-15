# SMART_AO V8 — Rapport global d’avancement

**Date de mise à jour :** 15 août 2026  
**Référence de code publiée :** `e480987` sur `main`  
**Fonctionnalité métier la plus récente :** publication patron d’un rapport financier `DRAFT → PUBLISHED`  
**Preuve technique la plus récente :** CI GitHub `31892907918` verte ; 308 tests backend locaux verts.

## 1. La vision simple du produit

SMART_AO V8 est en construction comme un **assistant de réponse aux appels d’offres BTP**, et non comme un ERP généraliste. Son travail futur est de guider une entreprise depuis un DCE reçu jusqu’à un dossier de réponse contrôlé : lecture du règlement de consultation, préparation collaborative, contrôle patron, chiffrage confidentiel puis production des pièces à remettre.

La règle fondamentale est déjà inscrite dans l’architecture : le collaborateur prépare et remonte des informations opérationnelles ; le patron conserve la décision, le chiffrage, la marge, la trésorerie et le dépôt. Les données financières ne doivent jamais apparaître dans l’espace collaborateur.

> À ce stade, SMART_AO V8 est un **socle backend sécurisé et testé**, avec un premier wizard collaborateur. Ce n’est pas encore un logiciel commercialisable pour gérer un appel d’offres de bout en bout.

## 2. Où nous en sommes réellement

| Domaine | État | Ce qui existe réellement | Ce qui ne doit pas encore être vendu comme disponible |
|---|---|---|---|
| Noyau métier | **Solide** | Affaire (`Case`), consultation, version DCE, décision, révision, événements, idempotence, historique. | Parcours complet utilisateur final. |
| Sécurité entreprise | **Solide** | Tenant par entreprise, comptes patron/collaborateur, sessions, refresh, MFA, RBAC/ABAC/ReBAC, audit append-only. | Provisionnement automatisé client/VPS prêt à l’emploi. |
| Admission DCE | **Avancé** | Staging privé, upload binaire, limites, SHA-256, signature MIME, ClamAV, rétention, registre durable. | Exploitation Docker réelle sur VPS et corpus de DCE BTP de validation terrain. |
| Lecture et analyse DCE | **Avancé mais déterministe** | Extraction PDF/DOCX/XLSX/TXT, classification, signaux du RC, exigences atomiques, confirmation humaine, lecture Case-scopée. | OCR robuste de plans, analyse IA complète, garantie de conformité ou calcul automatique de délais. |
| Travail collaborateur | **Partiel mais sécurisé** | Affectation, accusé de réception, clarification, indisponibilité, historique fermé et wizard de lecture DCE. | Pilotage complet des tâches, pièces produites, relances, assemblage final de réponse. |
| Cockpit patron | **Partiel** | Lecture des affectations, journaux et interactions ; fondation de lecture financière ; publication explicite d’un snapshot financier. | Interface patron complète, décisions Go/No-Go ergonomiques, chiffrage et préparation de dépôt. |
| Finance | **Fondation seulement** | Snapshots, lignes en unités mineures, lecture patron d’un snapshot publié, publication `DRAFT → PUBLISHED` immutable. | Saisie/création de brouillon, import de prix Excel, calcul de DPGF/BPU, marge, trésorerie opérationnelle. |
| Documents de réponse | **Non démarré** | Aucun générateur métier final n’est revendiqué. | Mémoire technique, DC1/DC2/DUME, DPGF/BPU, ZIP de remise, signature ou dépôt. |
| Recherche d’affaires | **Non démarré** | Aucune collecte de plateformes d’appels d’offres. | Veille automatique, qualification géographique, alertes ou prospection. |
| Frontend et déploiement | **Partiel** | React/Tailwind : connexion, sélection des affaires affectées, wizard collaborateur ; contrat d’API configurable. | Raccordement HTTPS réel, cockpit patron, déploiement VPS client, supervision, sauvegardes, exploitation. |

## 3. Les fondations déjà terminées

Le travail réalisé n’est pas seulement de la maquette. Les éléments suivants sont codés, testés et intégrés à la CI :

| Bloc | Résultat durable |
|---|---|
| Domaine et traçabilité | Les objets centraux conservent leurs versions, décisions et événements. Les commandes sont idempotentes : un rejeu ne crée pas deux opérations. |
| Isolation des entreprises | Toute ressource est recherchée dans son tenant ; une ressource d’une autre entreprise est neutre côté HTTP. |
| Séparation patron/collaborateur | Les droits viennent des faits serveur et non du navigateur. Le collaborateur ne reçoit que les affaires et actions explicitement affectées. |
| DCE | Le flux protège l’admission de documents et matérialise des résultats sourcés. Une exigence détectée est un signal à confirmer par un humain, jamais une conformité automatique. |
| Affectations | Le patron crée, modifie, suspend, réactive et termine les affectations ; le collaborateur peut signaler l’avancement et ses blocages. Tous ces actes possèdent un historique. |
| Finance confidentielle | Les montants sont manipulés en unités mineures et réservés au patron. La publication est atomique, révisionnée et irréversible dans le périmètre actuel. |

## 4. Le point exact atteint dans le parcours d’une affaire

Le parcours cible est : **DCE reçu → DCE sécurisé → lecture/confirmation → préparation collaborateur → contrôle patron → chiffrage → dossier de réponse → dépôt**.

Aujourd’hui, le logiciel couvre réellement les quatre premières briques de données et de sécurité : réception sécurisée, traitement documentaire déterministe, lecture guidée par affaire, et collaboration encadrée. Il commence aussi le contrôle patron et la confidentialité financière. Il ne couvre pas encore la fabrication effective des pièces de réponse, le chiffrage utilisable au quotidien, ni le dépôt.

| Étape du parcours BTP | Statut actuel | Décision humaine conservée |
|---|---|---|
| Recevoir et sécuriser le DCE | Construite côté backend. | Le patron reste responsable du choix d’ouvrir et de traiter l’affaire. |
| Lire le RC et extraire des exigences | Construite sous forme de signaux sourcés et confirmables. | Un humain confirme ce qui est réellement demandé. |
| Répartir le travail | Construite pour les affectations et interactions structurées. | Le patron décide qui intervient et sur quel périmètre. |
| Préparer l’offre technique | Non terminée. | Le collaborateur devra compléter et transmettre, sans décision autonome du logiciel. |
| Chiffrer et arbitrer | Fondation seulement. | Prix, marge, Go/No-Go restent exclusivement patron. |
| Générer et rassembler les pièces | Non démarré. | Le patron valide chaque document final. |
| Déposer l’offre | Non démarré. | Le dépôt est une action humaine explicite. |

## 5. Ce que nous venons exactement de finir

La dernière frontière, `FINANCIAL-REPORT-PUBLICATION-01`, ne crée pas encore un chiffrage. Elle sécurise le moment où un chiffrage déjà présent sous forme de brouillon devient publiable pour le patron.

1. Le seul acteur admis est un `PATRON_ADMIN` disposant de `financial.report.publish`.
2. Le système verrouille le snapshot, vérifie qu’il est encore `DRAFT` et que sa révision est celle attendue.
3. Il crée un acte durable de publication, passe le snapshot à `PUBLISHED`, date l’acte côté serveur et augmente la révision.
4. Il écrit l’événement, l’outbox et le receipt dans la même transaction.
5. La réponse HTTP ne contient aucun montant, marge, ligne, libellé, source ni formule.

Le test de sécurité prouve qu’un collaborateur reçoit `403 FORBIDDEN` **avant toute lecture du snapshot**. La CI du commit fonctionnel `13bc1b2` est verte ; la branche `main` a ensuite été vérifiée verte par la CI `31892907918`.

## 6. La prochaine étape recommandée

La prochaine priorité n’est **pas** le frontend patron tout de suite. Le backend vient d’apprendre à publier un brouillon financier, mais il ne sait pas encore créer ce brouillon de manière contrôlée. Sans cette étape, le bouton « publier » serait techniquement correct mais inutilisable dans le travail quotidien d’un entrepreneur.

La recommandation est donc d’ouvrir le slice suivant : **FINANCIAL-REPORT-DRAFT-CREATION-01**.

| Ordre | Prochaine frontière | But métier | Pourquoi maintenant |
|---:|---|---|---|
| 1 | Création contrôlée de snapshot financier `DRAFT` | Permettre au patron d’ouvrir un brouillon de chiffrage pour une affaire, sans exposer de données au collaborateur. | C’est le maillon manquant directement avant la publication déjà codée. |
| 2 | Écriture contrôlée des lignes financières du brouillon | Ajouter/modifier les lignes de chiffrage avec révision, unités mineures et historisation. | Un brouillon vide ne produit aucune valeur opérationnelle. |
| 3 | Cockpit patron web de lecture/édition | Donner au patron un environnement simple pour visualiser ses affaires, chiffrages et validations. | L’API doit exister avant l’écran afin de ne pas fabriquer une interface fictive. |
| 4 | Bibliothèque entreprise patron | Administrer société, assurances, Kbis, RIB, qualifications, documents expirables et références. | Ces données alimenteront ensuite les pièces administratives et techniques. |
| 5 | Wizard collaborateur de préparation de réponse | Associer exigences, preuves, tâches et pièces techniques à l’affaire. | C’est le cœur opérationnel avant assemblage des livrables. |
| 6 | Génération documentaire et contrôle de complétude | Produire les documents demandés par le RC, sans affirmer une conformité automatique. | C’est le résultat visible et vendable à l’entrepreneur. |
| 7 | Préproduction VPS et DCE réels | Tester flux complet, Docker, ClamAV, sauvegardes, HTTPS et DCE représentatifs. | Aucun client ne doit arriver avant cette preuve de terrain. |

## 7. Ce qui dépend du VPS et ce qui n’en dépend pas

Nous pouvons continuer sans VPS sur les contrats, le backend, les migrations PostgreSQL, les tests d’intégration, la CI GitHub et les écrans React locaux.

Le VPS devient nécessaire pour la vraie préproduction : URL HTTPS, cookies sécurisés dans un navigateur réel, Docker/ClamAV, stockage privé, reverse proxy, sauvegardes, logs, supervision et tests avec des DCE réels. L’absence actuelle de VPS ne bloque donc pas le prochain slice de création de brouillons financiers.

## 8. Décision simple à prendre maintenant

La décision recommandée est : **continuer immédiatement avec la création patron de brouillon financier**, puis ses lignes de chiffrage. Cela donnera une chaîne cohérente : le patron crée un brouillon, le chiffre, puis le publie dans son périmètre confidentiel.

Après cette chaîne financière minimale, nous construirons le cockpit patron web correspondant. Le frontend collaborateur reste en attente d’une URL HTTPS réelle pour son branchement complet, mais cette dépendance ne doit pas arrêter le backend métier.

## 9. Mesure d’avancement honnête

Il serait trompeur d’annoncer un pourcentage unique du logiciel : le socle de sécurité et de traçabilité est très avancé, mais les fonctions qui font gagner du temps au patron sur la production d’une réponse ne sont pas encore réalisées. La bonne lecture est donc la suivante :

| Axe | Niveau actuel | Lecture honnête |
|---|---|---|
| Fiabilité de la base technique | Élevé | Les frontières déjà ouvertes ont des contrats, migrations, tests, audits et CI. |
| Cœur DCE documentaire | Intermédiaire à avancé | Les données sont admises, lues et structurées ; les résultats métier finaux restent à construire. |
| Collaboration opérationnelle | Intermédiaire | Les droits et interactions existent ; le travail de production d’offre est à développer. |
| Chiffrage patron | Initial | La confidentialité et la publication sont prêtes ; la saisie et le calcul ne le sont pas. |
| Produit visible client | Initial à intermédiaire | Un premier wizard collaborateur existe ; le cockpit patron et l’expérience complète manquent. |
| Prêt à vendre | Non | Il manque encore les pièces de réponse, les validations de terrain et la préproduction VPS. |

## 10. Références internes

| Document | Rôle |
|---|---|
| `docs/PROJECT_STATE.md` | Point de reprise technique et état des slices publiés. |
| `todo.md` | Checklist durable des travaux restants. |
| `docs/reference/SMART_AO_V8_PATRON_FINANCIAL_REPORT_PUBLICATION_01_SPEC.md` | Contrat de la dernière frontière financière. |
| `docs/reference/SMART_AO_V8_ASSIGNMENT_OPENAPI.md` | Registre des quinze opérations HTTP documentées. |
| `docs/presentations/financial_foundation_slides/slide_notes.md` | Script de présentation de la fondation financière. |
