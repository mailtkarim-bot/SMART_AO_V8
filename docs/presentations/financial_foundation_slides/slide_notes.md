# 1 - Sept rubriques, un format monétaire

La structure financière s'appuie sur sept rubriques normalisées, allant du chiffre d'affaires à la trésorerie prévisionnelle. Pour éliminer les erreurs d'arrondi, nous bannissons les nombres flottants au profit d'entiers stockés en unités mineures. 

Cette exactitude numérique alimente directement notre API de lecture.

# 2 - Un cockpit de contrôle patron

Nous livrons ici un véritable outil de pilotage pour le chef d'entreprise, pas un progiciel opaque. Smart-AO V8 transforme les montants sensibles en faits durables et lisibles uniquement par le patron. La précision repose sur des unités mineures et des snapshots reproductibles. La confidentialité s'appuie sur une projection fermée et non rémanente. La traçabilité garantit des registres append-only prêts pour la publication. Quatorze opérations OpenAPI, une seule frontière financière et une étanchéité totale pour le collaborateur offrent le contrôle attendu.

# 3 - Une confidentialité sans compromis

La confidentialité n'est pas négociable dans nos métiers. Le collaborateur n'a accès à rien, absolument rien, qui permette d'inférer la marge ou la trésorerie. Seul le profil PATRON_ADMIN actif peut consulter les rapports publiés, tandis que les refus d'accès restent totalement neutres pour éviter toute fuite.

Et cette étanchéité repose sur une séparation claire entre calcul et consultation.

# 4 - Fondation financière patron

Nous posons ici la base financière de SMART AO V8. Tout repose sur des snapshots immuables et des contrôles d'accès stricts pour le cockpit patronal. Et nous allons voir comment cette rigueur protège chaque donnée sensible.

# 5 - Une route strictement patronale

L'accès passe par une route unique et strictement verrouillée par la capability financial report read. Le système filtre tout, rendant invisible tout rapport non publié pour garantir une réponse fermée, en lecture seule et sans cache. 

Aucun brouillon ne fuite hors du registre.

# 6 - Prochaine frontière : publier le snapshot

Nous préparons maintenant notre prochaine grande étape métier. Il s'agit de publier le snapshot par un acte patron explicite et immuable. Aujourd'hui le calcul reste à l'état de brouillon hors du cockpit financier. Demain, la commande de publication verrouillera les données avec idempotence. Le registre actera l'horodatage sans stocker les montants sources. Rappelons notre règle absolue. Publier ne recalcule rien et ne dépublie jamais. Toute correction future exigera un nouveau snapshot distinct. Cette discipline conduit naturellement à notre vision d'ensemble.

# 7 - 14 opérations OpenAPI contrôlées

Toute notre architecture repose sur un contrat OpenAPI rigoureusement cloisonné. Nous pilotons exactement quatorze opérations contrôlées de bout en bout. Trois interactions pour le collaborateur, un historique fermé, cinq commandes d'affectation pour le patron et une validation en registre append-only. Sans oublier les quatre lectures du cockpit dont la finance. Cette quatorzième opération apporte la vue financière sans jamais élargir les droits du collaborateur. Chaque frontière est explicitement autorisée pour sécuriser l'ensemble.

# 8 - Aucune trace exploitable

La lecture financière fonctionne comme une projection fermée, non rémanente et rigoureusement rédigée. Nous garantissons ici zéro trace exploitable en dehors des faits stricts nécessaires au patron. Les totaux et lignes circulent en unités mineures avec leur devise et horodatage, mais aucune source ni preuve indirecte ne fuite. Pas de tenant, pas d'auteur, pas de hash. Le cache est interdit avec no-store et les audits SEC-01 restent expurgés. Et pour renforcer cette sécurité, toute tentative hors tenant renvoie un code neutre. C'est la suite logique de notre route strictement patronale, ouvrant la voie à l'organisation de nos interfaces.

# 9 - Le snapshot sépare calcul et consultation

Pour garantir une traçabilité sans faille, nous séparons strictement le calcul de la consultation. Le snapshot fige les totaux, les devises et les règles à un instant précis, interdisant toute correction par écrasement de l'historique. 

Le patron ne consulte ainsi que des données certifiées et figées, structurées selon un format monétaire rigoureux.

# 10 - Validation technique locale

Avant toute publication, la fondation financière subit une batterie de vérifications locales intransigeantes. Trois cent huit tests backend passent au vert sans aucune régression sur nos frontières de sécurité. Les migrations Alembic valident les snapshots et les triggers. L'accès financier exige le rôle dédié tandis que le collaborateur reçoit un refus net. Les montants restent en unités mineures et l'OpenAPI reflète la composition réelle de FastAPI. Quatre avertissements tiers subsistent, mais n'affectent aucun test. Cette validation locale pose la base indispensable pour la suite.
