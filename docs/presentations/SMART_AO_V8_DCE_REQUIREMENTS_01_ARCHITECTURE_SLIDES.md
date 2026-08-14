# SMART_AO V8 — DCE-REQUIREMENTS-01

## Cover
DCE-REQUIREMENTS-01

Exigences atomiques sourcées du règlement de consultation

Architecture actuelle, garanties et limites de livraison

## Slide 1
### Le problème métier est borné avant d’être automatisé

- Un signal RC n’est pas encore une obligation juridique.
- Une exigence est une proposition de suivi interne, à confirmer par un humain.
- Le système ne calcule ni délai, ni conformité, ni prix, ni Go/No-Go.

## Slide 2
### La chaîne DCE sépare extraction, analyse et décision

- `DCE-DOCUMENT-EXTRACTION-01` produit des fragments techniques sourcés.
- `DCE-ANALYSIS-01` transforme les fragments en signaux RC déterministes.
- `DCE-REQUIREMENTS-01` matérialise les signaux en exigences atomiques.
- La décision reste dans un futur périmètre patron, jamais dans cette chaîne.

## Slide 3
### Le matérialiseur ne relit jamais les originaux

- Entrée unique : observations `COMPLETED` de l’analyse RC.
- Mapping fermé : candidature, offre, dépôt, format, visite, critère, négociation, validité.
- Manifest SHA-256 canonique et relecture serveur avant écriture.
- Extrait, texte original, nom de fichier et montant absents des messages durables.

## Slide 4
### Trois registres garantissent la traçabilité

- `dce_requirement_materialization_runs` : run, version, statut et manifest.
- `dce_requirements` : une exigence par observation, toujours en attente humaine.
- `dce_requirement_sources` : fragment et offsets de la preuve technique.
- FK composites tenant-scoped, idempotence et triggers append-only.

## Slide 5
### La transaction protège le replay et l’intégrité

- Le service `SYSTEM` prépare une commande fermée.
- Le dispatcher vérifie receipt et idempotence avant le handler.
- Le handler relit tenant, DCE, analyse, observations et sources.
- La transaction écrit run, exigences, preuves, événement et outbox ensemble.

## Slide 6
### La confirmation humaine est la prochaine frontière contrôlée

- `DCE-REQUIREMENTS-CONFIRMATION-01` ajoute une succession historisée.
- Patron et collaborateur affecté ne disposent pas des mêmes outcomes.
- La policy SEC-01 doit vérifier tenant, membership, capability et Case.
- La confirmation ne devient ni conformité, ni prix, ni autorisation de dépôt.

## Slide 7
### État réel de livraison

- `DCE-REQUIREMENTS-01` : publié sur `main`, migration `0016`, 213 tests verts, CI verte.
- Confirmation humaine : contrat, migration `0017`, socle et test local présents, non publiés.
- Audit SEC-01 : écarts restants sur audit succès, route authentifiée et preuve de portée Case.
- Décision : ne pas vendre la confirmation humaine avant fermeture de ces écarts.
