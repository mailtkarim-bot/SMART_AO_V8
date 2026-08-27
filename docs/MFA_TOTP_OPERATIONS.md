# MFA TOTP et actions sensibles

SMART AO expose une cérémonie TOTP sous `/api/v1/auth/mfa/totp`. L’utilisateur authentifié démarre un enrôlement, conserve les codes de récupération hors de l’application, puis confirme l’enrôlement avec le code fourni par son application. La désactivation impose également un code TOTP. Les opérations mutantes utilisent le double-submit CSRF et restent soumises au rate limiting backend.

Le cockpit frontend est disponible dans la section sécurité de session pour les sessions authentifiées. L’URI de provisioning et les codes de récupération ne sont affichés qu’après une demande d’enrôlement authentifiée ; les codes de récupération ne sont ni journalisés ni persistés en clair par le serveur.

La finalisation humaine GO/NO-GO d’une Decision exige désormais un **step-up MFA récent** au niveau de la policy d’autorisation. Cette garde s’applique avant le dispatch de la commande ; elle ne remplace ni la vérification du contexte Decision gelé, ni le contrôle de révision, ni la revue humaine. Les lectures et les actions qui ne sont pas explicitement marquées `mfa_required` ne sont pas modifiées par ce lot.

La configuration de production du service TOTP (`SMART_AO_TOTP_ENCRYPTION_KEY` et `SMART_AO_TOTP_ISSUER`) doit être fournie hors Git et validée sur l’environnement cible. Ce document ne prétend pas avoir opéré cette configuration sur un VPS ou un fournisseur réel.
