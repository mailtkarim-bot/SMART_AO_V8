# SMART_AO V8 — Script de présentation DCE-REQUIREMENTS-01

**Objet :** accompagner la présentation de l’architecture du slice `DCE-REQUIREMENTS-01`.  
**Audience :** propriétaire produit, architecte logiciel, auditeur sécurité et équipe de développement.  
**Durée indicative :** 10 à 15 minutes.  
**Version du script :** 14 août 2026.

## Intention générale

Cette présentation ne prétend pas montrer un moteur qui « comprend » juridiquement un règlement de consultation. Elle montre une chaîne prudente qui transforme des éléments textuels sourcés en propositions atomiques de préparation, puis s’arrête avant toute décision humaine ou financière. Le fil conducteur est la séparation des responsabilités : **extraire n’est pas analyser, analyser n’est pas décider, et confirmer n’est pas déclarer conforme**.

---

## Cover — DCE-REQUIREMENTS-01

### Message à dire

« Cette présentation porte sur le slice DCE-REQUIREMENTS-01 de SMART_AO V8. Son rôle est de transformer des signaux déterministes issus du règlement de consultation en exigences atomiques sourcées, toujours soumises à une confirmation humaine. Nous allons voir ce que le système produit, ce qu’il conserve comme preuve, comment la transaction protège l’intégrité, et surtout ce qu’il refuse volontairement de faire. »

### Point de cadrage

« Le système ne fournit pas ici un avis juridique, ne calcule pas de délai, ne détermine pas la conformité, ne choisit pas un prix et ne décide pas de répondre ou de déposer. Cette limite n’est pas une faiblesse de conception : elle protège l’entrepreneur contre une automatisation qui présenterait une hypothèse comme une certitude. »

### Transition

« Commençons par le problème métier exact : un signal repéré dans un RC ne constitue pas encore une obligation exploitable. »

---

## Slide 1 — Le problème métier est borné avant d’être automatisé

### Message à dire

« Dans un DCE, une phrase peut sembler imposer une pièce, un format ou une modalité de dépôt. Pourtant, la phrase peut être conditionnelle, ambiguë, attachée à un lot, corrigée par une annexe ou contredite par une version rectificative. SMART_AO ne transforme donc pas directement un texte en vérité juridique. Il conserve d’abord un signal sourcé, puis le matérialise sous la forme d’une exigence atomique à examiner. »

« Une exigence de ce slice signifie : “voici un élément du RC qui mérite une confirmation humaine pour la préparation du dossier”. Elle ne signifie pas : “l’entreprise est conforme”, “la pièce manque” ou “le dossier est prêt”. Cette distinction doit rester visible dans le produit, dans les API et dans les messages durables. »

### Point de vigilance

« Il faut résister à la tentation commerciale de présenter cette sortie comme une conformité automatique. La valeur vendue est la réduction du temps de lecture et la traçabilité de la préparation, pas une délégation de responsabilité juridique au logiciel. »

### Transition

« Cette prudence devient possible parce que la chaîne technique est découpée en frontières qui ne se mélangent pas. »

---

## Slide 2 — La chaîne DCE sépare extraction, analyse et décision

### Message à dire

« La première frontière, DCE-DOCUMENT-EXTRACTION-01, produit des fragments techniques : page PDF, paragraphe DOCX, cellule XLSX ou ligne de texte, avec un locator précis. Elle ne décide rien. La deuxième frontière, DCE-ANALYSIS-01, relit uniquement ces fragments et reconnaît des signaux RC selon des règles déterministes versionnées. Elle peut repérer un signal de candidature, de dépôt, de délai, de format ou de visite, mais elle ne déduit pas l’absence d’une pièce. »

« La troisième frontière, DCE-REQUIREMENTS-01, transforme chaque observation reconnue en exigence atomique. Elle conserve le type, la directive et la source. La décision patron, le prix, le Go/No-Go et l’autorisation de dépôt appartiennent à des périmètres ultérieurs, avec une séparation financière stricte. »

### Point de vigilance

« L’IA ou une future couche d’assistance peut aider à préparer une lecture, mais elle ne doit pas contourner ces registres ni injecter une décision dans une extraction technique. »

### Transition

« Regardons maintenant la règle la plus importante du matérialiseur : il ne relit pas les originaux. »

---

## Slide 3 — Le matérialiseur ne relit jamais les originaux

### Message à dire

« Le matérialiseur reçoit une entrée fermée : une analyse RC terminée, son manifest d’entrée et les observations persistées. Il ne va pas rouvrir le PDF, le DOCX ou le fichier Excel. Cette règle rend l’opération reproductible et vérifiable. Pour une même analyse, un même manifeste et une même version du matérialiseur, le résultat attendu est le même. »

« Le mapping est fermé. Il couvre les familles prévues : document de candidature, document d’offre, délai de remise, canal de réponse, contrainte de fichier, visite, critère d’attribution, négociation et validité de l’offre. Un signal qui n’entre pas dans le catalogue n’est pas transformé silencieusement en exigence. »

« Le manifest SHA-256 et la relecture serveur empêchent également qu’un appel fabriqué par un client modifie la source de vérité. Les messages durables ne contiennent ni nom de fichier original, ni texte complet, ni montant. »

### Transition

« Ces décisions ne restent pas seulement dans le code : elles sont représentées par trois registres complémentaires. »

---

## Slide 4 — Trois registres garantissent la traçabilité

### Message à dire

« Le premier registre, `dce_requirement_materialization_runs`, décrit l’exécution : la DCE, le statut, le manifest, la version du matérialiseur et les compteurs. Il permet de répondre à la question : quelle projection a été produite, à partir de quelle entrée ? »

« Le deuxième, `dce_requirements`, porte une exigence par observation. L’exigence reste toujours `PENDING_HUMAN_CONFIRMATION` et `SOURCE_SIGNAL_ONLY`. Le troisième, `dce_requirement_sources`, conserve la preuve technique : fragment source et offsets. On peut donc remonter de l’exigence vers l’observation, puis vers l’extraction, sans réinterpréter le document. »

« Les FKs composites imposent le tenant sur chaque relation. Les registres historiques sont protégés contre la modification et la suppression. Une projection courante future ne devra jamais effacer l’historique. »

### Transition

« La traçabilité ne suffit pas si deux appels concurrents peuvent produire des états incohérents. C’est le rôle de la transaction et de l’idempotence. »

---

## Slide 5 — La transaction protège le replay et l’intégrité

### Message à dire

« Le service système prépare une commande fermée. Le dispatcher calcule l’empreinte de la commande et examine le receipt idempotent avant d’appeler le handler. Une même clé réutilisée avec le même payload rejoue le résultat durable; la même clé avec un payload différent est un conflit. »

« Le handler verrouille les enregistrements nécessaires, relit le tenant, la DCE, l’analyse, les observations et les sources, puis écrit dans une seule transaction. Le résultat inclut le run, les exigences, leurs preuves, l’événement métier, l’outbox et le receipt. Si une étape échoue, la transaction est annulée : il ne doit pas rester une exigence sans preuve, ni une preuve sans run. »

« Cette mécanique est essentielle pour un logiciel de marchés : un traitement relancé après une interruption ne doit ni dupliquer les exigences ni écraser une version précédemment produite. »

### Transition

« Une exigence doit ensuite être relue par un humain. C’est une nouvelle frontière, avec une policy différente et des droits différents. »

---

## Slide 6 — La confirmation humaine est la prochaine frontière contrôlée

### Message à dire

« DCE-REQUIREMENTS-CONFIRMATION-01 ajoute une succession append-only séparée de l’exigence source. Un patron peut confirmer, demander une revue ou déclarer un signal non applicable avec le motif fermé prévu. Un collaborateur affecté peut confirmer ou demander une revue, mais ne peut pas déclarer le signal non applicable. Un acteur système ne peut jamais produire une confirmation humaine. »

« Dans la version durcie, la route HTTP ne reçoit pas de `tenant_id`, de rôle, de capability, de classification ni de `case_id` de confiance. Le serveur résout l’exigence dans son tenant, retrouve sa DCE puis recherche une Case active unique. Cette Case est utilisée pour la policy ReBAC et l’affectation du collaborateur. S’il n’y a aucune Case, ou s’il y en a plusieurs, le système refuse plutôt que de choisir arbitrairement. »

« Le succès d’autorisation et les refus pertinents sont audités avec des métadonnées minimisées. La confirmation reste une qualification de préparation interne : elle ne signifie ni conformité, ni prix, ni Go/No-Go, ni autorisation de dépôt. »

### Transition

« Terminons par l’état réel de livraison, en séparant ce qui est publié de ce qui est encore soumis au contrôle final de CI. »

---

## Slide 7 — État réel de livraison

### Message à dire

« Cette diapositive est un instantané de l’état au moment où la présentation a été générée. Elle indiquait DCE-REQUIREMENTS-01 publié, la confirmation humaine encore bloquée par l’audit de sécurité, la route HTTP et la preuve de portée Case. Depuis cet instantané, ces écarts ont été fermés localement. »

« L’état actuel est le suivant : DCE-REQUIREMENTS-01 reste publié sur `main`; la confirmation humaine possède sa route authentifiée, ses DTO fermés, sa résolution de Case unique, son audit de succès et de refus, ses migrations `0017` et `0018`, et cinq tests API sur le contexte d’authentification réel. La régression complète compte 219 tests verts; Ruff, Alembic, detect-secrets, pip-audit et Bandit sont verts localement. »

« La réserve à dire clairement est l’image de déploiement : le dépôt ne contient pas encore de Dockerfile pour cette frontière, donc le scan Trivy est préparé conditionnellement mais n’est pas présenté comme exécuté. La publication finale dépend encore du diff final, du push et de la réussite de la CI GitHub. »

### Message de clôture

« Le produit ne gagne pas sa fiabilité en prétendant tout décider. Il la gagne en montrant précisément ce qu’il sait, ce qu’il conserve comme preuve et ce qu’il laisse volontairement à l’entrepreneur. »

---

## Conclusion générale pour le présentateur

« DCE-REQUIREMENTS-01 constitue une brique de préparation fiable : une observation RC sourcée devient une exigence atomique, historisée et confirmable, sans être transformée en jugement juridique ou commercial. Cette frontière prépare la suite du produit, mais elle ne la préempte pas. La prochaine étape métier sera de rendre les exigences correctement Case-scopées lorsque plusieurs affaires partagent une même DCE, puis de construire les écrans wizard qui permettront au collaborateur de progresser sans exposer les données financières du patron. »
