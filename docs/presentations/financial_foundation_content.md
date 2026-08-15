# SMART_AO V8 — Fondation financière patron

## Cover

**SMART_AO V8 — Fondation financière patron**

Architecture confidentielle, snapshots immuables et 14 opérations OpenAPI.

## Slide 1

**Une frontière financière sans compromis de confidentialité**

- Seul le patron actif peut consulter un snapshot financier publié.
- Les collaborateurs ne voient ni existence, ni montant, ni marge, ni trésorerie.
- La lecture ne calcule rien et ne déclenche aucune décision automatique.

## Slide 2

**Le snapshot isole le calcul de sa consultation**

- `financial_report_snapshots` porte les totaux, devise, règles et état de publication.
- `financial_report_lines` porte les lignes monétaires autorisées.
- Les deux registres sont append-only ; aucune correction en place.

## Slide 3

**Sept rubriques financières, un format monétaire unique**

- Chiffre d’affaires, coûts directs, frais généraux et sous-traitance.
- Aléas, marge brute et trésorerie prévisionnelle.
- Tous les montants sont des entiers en unités mineures, jamais des flottants.

## Slide 4

**Une route de lecture strictement patronale**

- `GET /api/v1/patron/cases/{case_id}/financial-reports/{report_id}`.
- Capability dédiée : `financial.report.read`.
- Snapshot `PUBLISHED` seulement ; tenant étranger masqué par `404` neutre.

## Slide 5

**La réponse financière ne laisse aucune trace exploitable**

- DTO fermés : ni tenant, ni auteur, ni source, ni formule, ni audit.
- `Cache-Control: no-store` sur toute réponse `200`.
- Les refus sont audités sans montant ni libellé de ligne.

## Slide 6

**Les 14 opérations OpenAPI forment une chaîne contrôlée**

- 3 interactions collaborateur et leur historique fermé.
- 5 commandes patron d’affectation, 3 lectures de cockpit et 1 validation d’interaction.
- La 14e opération ajoute la lecture financière patron sans élargir les accès collaborateur.

## Slide 7

**Validation locale : migrations, accès et montants testés**

- Migration `20260815_0025` vérifiée par Alembic.
- Test patron : unités mineures, ligne financière, `no-store` et redaction.
- Test collaborateur : refus `403`; suite backend à 306 tests verts.

## Slide 8

**La prochaine décision : publier un snapshot, jamais le recalculer**

- Future commande patron de publication avec verrouillage et idempotence.
- Passage `DRAFT → PUBLISHED` par acte append-only séparé.
- Aucune dépublication ni modification du snapshot déjà publié.

## Slide 9

**Le cockpit devient un outil de contrôle, pas un ERP opaque**

Une lecture financière précise, traçable et exclusivement patronale — prête à être enrichie par la publication explicite des snapshots.
