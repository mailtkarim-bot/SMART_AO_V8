# SMART_AO V8 — ENTERPRISE-LIBRARY-01

## Objet

Cette frontière ouvre la première bibliothèque entreprise patronale. Elle conserve, dans le tenant de l’entreprise, une fiche légale unique et des preuves documentaires immuables pour les assurances, l’extrait Kbis et le RIB.

Le premier incrément est **applicatif et transactionnel**. Il ne fournit pas encore de route HTTP, d’upload binaire, de vérification automatique, de qualifications ou de références chantier. Les objets `storage_object_id` sont des références opaques vers le registre de stockage privé ; aucun contenu, hash, IBAN ou secret bancaire ne traverse les événements ou les receipts.

## Autorité et confidentialité

Seul `PATRON_ADMIN` reçoit `enterprise.library.read` et `enterprise.library.write`. Un collaborateur, un partenaire externe ou un délégataire ne reçoit aucune de ces capabilities dans ce slice. La policy est évaluée avant la résolution d’une société ou d’un document.

La société est rattachée au tenant authentifié. Un tenant ne peut posséder qu’une seule fiche société. Les documents sont rattachés par FK composite `(tenant_id, company_id)` et au membership patron qui les a enregistrés.

## Contrat de données initial

| Élément | Valeurs ou invariant |
|---|---|
| Société | `legal_name`, `trade_name`, SIREN à 9 chiffres, SIRET à 14 chiffres, TVA, adresse et pays ISO-3166 alpha-2. |
| Document | `INSURANCE`, `KBIS` ou `RIB`, libellé, référence opaque de stockage, nom de fichier, date d’émission, expiration optionnelle, SHA-256 lowercase et statut `PENDING`. |
| RIB | L’expiration est interdite dans ce premier contrat ; l’IBAN et les coordonnées bancaires ne sont jamais stockés dans cet incrément. |
| Assurance/Kbis | L’expiration doit être postérieure à l’émission lorsqu’elle est renseignée. |
| Historique | Les documents sont append-only ; aucune mise à jour ou suppression n’est autorisée en base. |
| Révision | La société commence à `0` et progresse à chaque document enregistré. L’écriture exige `expected_revision`. |
| Durabilité | Société/document, événement, outbox et receipt sont écrits dans la même transaction idempotente. |

## Hors périmètre

La lecture HTTP, l’upload et le scan ClamAV, la validation humaine, le remplacement par succession documentaire, les qualifications, les références, les contacts, les pièces expirables génériques et le cockpit UI feront l’objet d’incréments ultérieurs. Aucun document n’est déclaré valide par la seule présence du registre `PENDING`.
