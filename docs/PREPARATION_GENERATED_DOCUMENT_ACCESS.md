# Accès contrôlé aux documents générés de préparation

## Objet

Le wizard collaborateur permet désormais de relire et de télécharger les documents générés par le serveur. Le lot couvre les documents `TECHNICAL_RESPONSE`, `DC1`, `DC2` et `DC4` déjà projetés dans le package de préparation.

La projection de package continue de retourner uniquement les métadonnées allowlistées : identifiant, version, type, état et révision de readiness. La clé de stockage privée et le hash interne ne sont pas exposés.

## Contrat HTTP

Le contenu est servi par `GET /api/v1/collaborator/preparation/{package_id}/documents/{document_id}/content`. Sans paramètre supplémentaire, la réponse est inline et de type `text/markdown`. Avec `?download=true`, la même ressource est servie avec une disposition `attachment`.

Les deux variantes imposent `Cache-Control: no-store` et `X-Content-Type-Options: nosniff`. Le nom de fichier est dérivé uniquement du type documentaire borné par la contrainte métier et de sa version.

## Autorisation et anti-contournement

Le serveur exige un acteur `COLLABORATEUR` avec membership actif. Il résout le package dans le tenant courant, vérifie que l’assignment actif appartient au membership et autorise la ressource avec la policy de préparation. Le document doit appartenir au package demandé et être dans l’état `GENERATED`.

Un document d’un autre package, d’un autre tenant, absent ou dans un état non généré est présenté comme introuvable. Une métadonnée existante dont le contenu privé est indisponible produit une erreur de service, sans divulguer la clé interne.

L’aperçu frontend lit un Blob depuis cette route et affiche le texte dans une zone `pre` bornée en hauteur. Le téléchargement crée un lien temporaire en mémoire puis libère l’URL objet. Aucun lien public, dépôt externe ou envoi automatique n’est créé.

## Validation

Le test d’intégration backend couvre la projection sans métadonnées privées, l’aperçu inline, le téléchargement attachment, les en-têtes anti-cache et anti-sniffing, l’égalité du contenu et le cas document absent. Les tests frontend couvrent le transport Blob, le rendu des boutons, la soumission des identifiants et l’affichage de l’aperçu sans métadonnées de stockage.

Les tests nécessitant PostgreSQL restent exécutés par la CI GitHub. Le sandbox local ne fournit pas de serveur PostgreSQL sur `127.0.0.1:5432`.

## Limites

Ce lot ne transforme pas le Markdown en PDF ou en DOCX, ne valide pas juridiquement le contenu DC1/DC2/DC4 et ne publie aucun document sur un portail de dépôt. Il rend seulement accessible, à l’acteur collaborateur autorisé, le contenu déjà produit et contrôlé par le backend.
