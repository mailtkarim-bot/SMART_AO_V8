# Sources externes — export calendrier ICS

## Décision

Le slice calendrier ajoute un port applicatif pur `SubmissionDeadlineCalendarPort` et un adaptateur `IcsSubmissionDeadlineCalendar`. Il produit un fichier ICS local conforme à RFC 5545 pour une échéance de dossier, avec dates timezone-aware converties en UTC, identifiant d’événement déterministe dérivé d’un hash et description sans document, extrait, montant ou donnée financière.

L’extra `calendar` installe `icalendar` uniquement lorsqu’il est demandé au build. AppRuntime reste désactivé par défaut et ne construit le renderer qu’avec `SMART_AO_CALENDAR_ENABLED=1`. Aucun agenda distant, CalDAV, OAuth, synchronisation ou envoi e-mail n’est introduit. Le port est prêt à être raccordé ultérieurement à une action patronale ou à une projection de préparation, mais ce slice ne modifie aucune transition métier et n’expose pas encore de nouvelle route HTTP.

Les tests valident la déterminisme, la structure `VCALENDAR/VEVENT`, les timestamps UTC et le rejet des dates naïves ou inversées. La génération a été testée localement avec la dépendance optionnelle installée ; aucune synchronisation vers un service réel n’a été effectuée.

## Sources officielles

1. [icalendar — documentation officielle](https://icalendar.readthedocs.io/) — bibliothèque Python de génération/parser compatible RFC 5545.
2. [icalendar 7.3.0 — PyPI](https://pypi.org/project/icalendar/) — version consultée et plage de compatibilité Python ; le projet verrouille une plage `<8.0` dans l’extra optionnel.
3. [RFC 5545 — Internet Calendaring and Scheduling Core Object Specification](https://datatracker.ietf.org/doc/html/rfc5545) — format d’échange iCalendar indépendant d’un service de calendrier, règles de composants et de lignes CRLF.

## Limites de recette

La recette réelle devra ouvrir le fichier dans plusieurs clients calendaires, vérifier l’affichage du fuseau et contrôler qu’aucune donnée financière ou documentaire ne traverse l’export. Le produit ne doit pas considérer la création du fichier comme une invitation acceptée ou comme une synchronisation réussie. Une éventuelle synchronisation CalDAV/Google/Microsoft devra faire l’objet d’un connecteur séparé, avec identité, secrets, consentement et politique de révocation explicitement définis.
