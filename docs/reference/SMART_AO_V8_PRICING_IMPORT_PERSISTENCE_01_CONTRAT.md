# PRICING-IMPORT-PERSISTENCE-01 — Contrat de persistance contrôlée

## 1. Objet et frontière

Ce slice transforme une prévisualisation patronale DPGF/BPU/Excel en un lot financier serveur réutilisable, puis permet son application atomique dans un brouillon financier patronal. Il ne dépose aucun fichier sur un portail externe et ne modifie jamais un snapshot financier publié.

La prévisualisation ne conserve **aucun binaire brut**. Elle conserve uniquement les lignes normalisées nécessaires à une décision patronale ultérieure : type de document, empreinte SHA-256 calculée côté serveur, numéro de ligne, code, désignation, unité, quantité, prix unitaire en centimes et total en centimes. Les lignes invalides ne sont pas applicables.

## 2. Modèle de cycle de vie

| Objet | États | Règle |
|---|---|---|
| Lot d’import | `PREVIEWED`, `COMMITTED` | Append-only. La transition vers `COMMITTED` est unique et atomique avec l’ajout des lignes financières. |
| Ligne normalisée | Valide ou erreur | Append-only. Une ligne contenant une erreur ne peut jamais alimenter le brouillon financier. |
| Brouillon financier | `DRAFT` uniquement pour application | Le snapshot est verrouillé avec `FOR UPDATE` et sa révision doit correspondre à la commande. |

Un même lot ne peut être committé qu’une seule fois. Le rejeu de la même commande retourne le receipt idempotent ; une nouvelle commande visant un lot déjà committé est refusée par `IMPORT_ALREADY_COMMITTED`.

## 3. Autorisation et confidentialité

La préparation et l’application d’un lot sont exclusivement patronales et exigent la capability `financial.report.line.write` avec la classification `FINANCIAL_PRIVATE`. Le `tenant_id`, l’acteur, la membership, la Case et le brouillon sont résolus côté serveur. Aucun contrat collaborateur ne reçoit le lot, ses montants, ses lignes ou son empreinte.

Les réponses publiques de commit sont limitées au receipt, à l’identifiant du brouillon, à la nouvelle révision et au nombre de lignes appliquées. Elles n’exposent ni désignation, ni montant, ni prix unitaire, ni nom de fichier, ni hash source.

## 4. Atomicité et invariants PostgreSQL

Le commit doit verrouiller dans une transaction unique le lot d’import puis le snapshot financier. Il vérifie le tenant, la Case, l’état `PREVIEWED`, la révision optimiste et l’absence de publication. Il insère les lignes financières avec `category = SALES`, met à jour les totaux du snapshot, incrémente `aggregate_revision`, passe le lot à `COMMITTED`, puis écrit événement, outbox et receipt dans la transaction du dispatcher.

Les registres de lot et de lignes normalisées sont append-only par trigger PostgreSQL. Les clés étrangères composites empêchent tout rattachement inter-tenant. L’unicité est imposée par `(tenant_id, batch_id, row_number)` pour les lignes et par `(tenant_id, command_id)` pour le lot.

## 5. Rejets obligatoires

Le serveur refuse un lot absent, étranger, déjà committé, contenant une ligne invalide, visant un snapshot publié ou présentant une révision obsolète. Le serveur refuse également toute tentative de modifier ou supprimer un lot ou une ligne normalisée.

Les valeurs monétaires sont entières en centimes. Les quantités restent des décimaux canoniques sous forme textuelle. Aucun flottant n’est persistant dans le registre financier.

## 6. Scénarios de test requis

Les tests PostgreSQL doivent couvrir la création d’un lot normalisé, le commit de deux lignes vers un brouillon `DRAFT`, la mise à jour des totaux et de la révision, le rejeu idempotent, le conflit de révision, l’absence de ligne valide, le lot déjà committé, le snapshot publié, l’isolation tenant, le refus collaborateur et les triggers append-only.
