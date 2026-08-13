# SMART_AO V8 — DCE-DOCUMENT-EXTRACTION-01 : registre d’extractions immuables et sourcées

**Statut :** normatif.
**Périmètre :** lecture interne de documents DCE déjà admis, extraction déterministe et persistance immuable de projections minimisées avec provenance.
**Dépendances :** SEC-01, DCE-ADMIT-01, DCE-STAGING-01, DCE-UPLOAD-01 et DCE-RETENTION-01.

## 1. But et frontière

DCE-DOCUMENT-EXTRACTION-01 transforme un original DCE déjà admis en un ensemble borné de fragments textuels sourcés. Il prépare l’analyse métier future — règlement de consultation, pièces administratives, cahier des clauses, BPU, DPGF et plans — sans confondre extraction technique, interprétation métier et décision humaine.

> Une extraction n’est pas une analyse, une classification, une exigence, un prix, une réponse à l’acheteur ou une décision Go/No-Go. C’est une projection technique reproductible, rattachée à un document immuable et à un emplacement vérifiable.

Le slice ne fournit aucun téléchargement HTTP d’original, de fragment intégral ni d’archive. Seuls les travailleurs système peuvent lire la quarantaine privée associée à un `DceDocument` admis.

## 2. Préconditions non négociables

Le service d’extraction doit relire côté serveur le document et son objet staged liés par FK composite. Il ne travaille que si les faits suivants sont simultanément vrais :

| Fait relu | Condition | Refus sinon |
|---|---|---|
| Document | appartient au tenant et à une `DceVersion` `ADMITTED` ou `SUPERSEDED` | Aucun fichier ni registre créé. |
| Objet staged | est le même tenant, est `CONSUMED` par cette version et possède hash/taille/MIME contrôlés | `DOCUMENT_STORAGE_NOT_CONSUMED`. |
| Intégrité | `DceVersion.integrity = VERIFIED` | `DCE_VERSION_NOT_VERIFIED`. |
| Original | est accessible uniquement sous sa clé privée contrôlée | `PRIVATE_DOCUMENT_UNAVAILABLE`. |
| Média | appartient à la allow-list du slice | `MEDIA_TYPE_UNSUPPORTED`. |

Le document original, son `storage_key`, le hash, les erreurs de bibliothèque et les détails antivirus ne font jamais partie d’une réponse HTTP, d’un événement cockpit, d’un audit SEC-01 ou d’un message de log applicatif.

## 3. Formats initialement supportés

| MIME contrôlé | Extracteur déterministe | Provenance minimale |
|---|---|---|
| `application/pdf` | pypdf ; texte par page | `{"kind":"pdf_page","page":n}` |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx ; paragraphes non vides | `{"kind":"docx_paragraph","paragraph":n}` |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | openpyxl en lecture seule ; cellules textuelles non vides | `{"kind":"xlsx_cell","sheet":"…","cell":"A1"}` |
| `text/plain` | UTF-8 strict, sans détection automatique d’encodage | `{"kind":"text_line","line":n}` |

Les formats image, ODT, XLS historique, DWG, ZIP, courrier électronique et OCR sont explicitement hors périmètre de ce slice. Ils produiront une extraction `UNSUPPORTED`, jamais un faux texte ni une erreur opaque qui ferait croire au produit qu’un contenu a été lu.

## 4. Limites anti-bombes et minimisation

L’extraction applique des limites avant de persister une projection. Les plafonds sont des constantes système, non modifiables par une requête navigateur.

| Contrôle | Limite DCE-EXTRACT-01 | Comportement au dépassement |
|---|---:|---|
| Taille de l’original à lire | 128 Mio | `REJECTED_LIMIT` ; aucun fragment. |
| Pages PDF | 2 000 | `REJECTED_LIMIT` ; aucun fragment. |
| Paragraphes DOCX | 100 000 | `REJECTED_LIMIT` ; aucun fragment. |
| Feuilles XLSX | 200 | `REJECTED_LIMIT` ; aucun fragment. |
| Cellules textuelles XLSX | 500 000 | `REJECTED_LIMIT` ; aucun fragment. |
| Lignes texte | 500 000 | `REJECTED_LIMIT` ; aucun fragment. |
| Caractères d’un fragment | 8 000 | Fragment découpé de façon déterministe, avec position ordinale continue. |
| Caractères totaux par extraction | 10 000 000 | `REJECTED_LIMIT` ; transaction annulée, aucun fragment. |

Les extracteurs ouvrent les archives OOXML avec les bibliothèques en lecture seule et ne résolvent aucune ressource externe, macro, lien, formule ni contenu embarqué. Les cellules XLSX sont projetées en valeurs textuelles contrôlées, jamais en formule calculée ni en lien externe.

## 5. Registre immuable

Le registre comprend deux tables tenant-scopées :

| Table | Rôle | Éléments clés |
|---|---|---|
| `dce_document_extractions` | Une tentative déterministe terminée pour un document/hash/extracteur/version. | Statut, version de l’extracteur, hash du document d’entrée, compteurs, code fermé et horodatage. |
| `dce_document_extraction_fragments` | Fragments minimisés, ordonnés et sourcés d’une extraction `COMPLETED`. | Position ordinale, locator JSONB validé, texte et hash SHA-256 du fragment. |

Une extraction est unique par `(tenant_id, dce_document_id, input_sha256, extractor_id, extractor_version)`. Elle est append-only : `INSERT` seulement, aucun `UPDATE` ni `DELETE`. Les fragments ne peuvent être créés que pour une extraction `COMPLETED` du même tenant et sont eux aussi append-only.

Les statuts fermés sont : `COMPLETED`, `UNSUPPORTED`, `REJECTED_LIMIT` et `FAILED_SAFE`. Une erreur de lecture, un PDF chiffré, une archive corrompue ou une incohérence de métadonnées devient `FAILED_SAFE` sans trace technique brute.

## 6. Transaction et idempotence

L’entrée d’extraction est une commande système idempotente. Les octets restent hors dispatcher ; le service lit le document privé, produit une projection bornée en mémoire et délègue au handler uniquement les faits minimisés à enregistrer.

Dans une transaction PostgreSQL unique, le handler verrouille le document et l’objet staged, vérifie les préconditions, insère la ligne d’extraction, insère ses fragments, crée l’événement `DCE_DOCUMENT_EXTRACTION_RECORDED`, l’outbox `cockpit_projection` et le receipt. Si une limite ou un échec sûr est rencontré, une extraction terminale sans fragment, événement et receipt est persistée de manière identique.

Le même tenant, l’acteur système, type de commande et idempotency key renvoie le receipt sans créer un doublon. Une collision de l’unicité fonctionnelle est lue comme un résultat terminal existant, jamais réécrite.

## 7. Provenance et confidentialité

Chaque fragment porte un locator JSONB fermé selon son format et une position ordinale. Le texte extrait est conservé uniquement parce qu’il est requis pour l’analyse DCE future, mais il ne peut être retourné par les endpoints de lecture existants. Toute future API de consultation de fragments devra avoir son propre contrat SEC-01, une policy de classification et une pagination stricte.

L’événement et l’outbox ne contiennent que : ID extraction, ID document, statut, nombre de fragments et compteurs ; jamais le texte, locator détaillé, hash, nom de fichier ni clé de stockage.

## 8. Critères de sortie

DCE-DOCUMENT-EXTRACTION-01 doit démontrer :

1. une extraction PDF, DOCX, XLSX et texte par adaptateur déterministe ;
2. provenance page, paragraphe, cellule ou ligne pour chaque fragment ;
3. immuabilité PostgreSQL des registres et FKs composites tenant-scopées ;
4. refus sûr d’un média non supporté, d’un original absent et d’une limite dépassée sans fragment ;
5. absence de doublon au replay et à une collision d’extracteur ;
6. exclusion de tout original, clé privée, hash et texte des events/outbox/réponses publiques ;
7. absence d’accès HTTP au fichier ou aux fragments ;
8. compatibilité avec l’admission, le staging, l’upload et la rétention déjà validés.

## 9. Non-objectifs

Ce slice ne fait ni OCR, ni reconnaissance de plan, ni classification réglementaire, ni extraction de prix, ni LLM, ni recherche documentaire, ni génération de mémoire technique. Il ne répare pas non plus un PDF corrompu ou une archive OOXML hostile ; ces cas sont explicitement enregistrés comme échecs sûrs.
