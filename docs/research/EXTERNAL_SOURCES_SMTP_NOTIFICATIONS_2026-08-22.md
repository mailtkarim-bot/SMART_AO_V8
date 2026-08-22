# Sources externes — notifications SMTP

## Décision

Le slice SMTP ajoute un port applicatif minimal `SubmissionExportNotificationPort` et un adaptateur `AioSmtpSubmissionExportNotifier`. Le message est construit côté serveur et ne transporte qu’un identifiant technique de paquet, un état de disponibilité et un lien implicite vers l’interface SMART AO. Aucun document, extrait DCE, montant ou donnée financière n’est attaché ou sérialisé.

L’adaptateur est optionnel : l’extra `notifications` installe `aiosmtplib` uniquement lorsque l’image est construite avec `SMART_AO_INSTALL_NOTIFICATIONS=1`. AppRuntime reste silencieux par défaut et ne crée le notifier qu’avec `SMART_AO_SMTP_ENABLED=1`, un hôte et une adresse d’expédition explicitement configurés. Les identifiants SMTP sont injectés seulement à l’exécution et ne sont jamais journalisés. Les adresses sont contrôlées contre les retours à la ligne afin d’éviter l’injection d’en-têtes. Le timeout est borné et les erreurs externes sont normalisées sans recopier le message de l’exception fournisseur.

Le port est préparé pour être consommé par un futur process manager/outbox dédié ; ce commit ne déclenche pas d’envoi automatique depuis une route HTTP et ne simule pas d’accusé de remise. Les tests utilisent un faux client asynchrone. Aucun serveur SMTP réel ni compte de messagerie n’a été utilisé dans le sandbox.

## Sources officielles

1. [aiosmtplib — The send Coroutine](https://aiosmtplib.readthedocs.io/en/latest/usage.html) — recommande `EmailMessage` et la coroutine `send()`, documente les paramètres d’hôte/port et les modes TLS/STARTTLS.
2. [aiosmtplib — The SMTP Client Class](https://aiosmtplib.readthedocs.io/en/latest/client.html) — décrit les connexions, TLS, STARTTLS, l’authentification et le caractère séquentiel du protocole SMTP.
3. [aiosmtplib 5.1.2 — PyPI](https://pypi.org/project/aiosmtplib/) — version publiée consultée et compatibilité Python 3.10+ ; le projet verrouille une plage `<6.0` dans l’extra optionnel.

## Limites de recette

La recette réelle doit utiliser un serveur de test ou un compte dédié, avec TLS adapté au fournisseur, une adresse de destination non sensible et une vérification que les journaux ne contiennent ni mot de passe ni contenu de message. Il faut également ajouter un process manager idempotent consommant une outbox dédiée si la notification doit être déclenchée après une transition métier. La présence du port et de l’adaptateur ne constitue pas une preuve de délivrabilité, de réputation de domaine, de configuration SPF/DKIM/DMARC ou de production readiness.
