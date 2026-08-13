# SMART_AO V8 — SEC-01
## Contrat de sécurité : identité, tenant, autorisation et audit

**Version :** 1.0  
**Statut :** contrat normatif à valider **avant** toute implémentation de S02  
**Auteur :** Manus AI  
**Périmètre :** identité locale, entreprises (`tenant`), rôles, autorisation contextualisée, sessions, journalisation, secrets, opérations support et exigences de tests.  
**Hors périmètre :** SSO client, SCIM, API publique partenaire, chiffrement de données métier au repos, tarification, dépôt sur profil acheteur et mécanismes d’IA métier. Ces sujets devront prolonger SEC-01, sans le contredire.

---

## 1. Objet et décision de gel

SMART_AO traite les DCE, les pièces administratives, les données de sociétés BTP et, à terme, les prix, marges, devis et trésoreries. La sécurité ne peut donc pas être une simple couche ajoutée aux routes HTTP. Elle doit décider **qui est la personne**, **pour quelle entreprise elle agit**, **sur quelle affaire elle peut agir**, **quelles classes de données elle peut recevoir**, et **quel fait d’audit permet de l’expliquer**.

> **Décision SEC-01 :** toute autorisation est évaluée côté serveur selon le contexte complet `identité × membership tenant × rôle × affectation × ressource × classification × action × état de session`. L’absence d’une permission explicite, d’un lien métier actif ou d’une preuve d’authentification suffisante vaut refus.

Cette décision traduit les contrats V8 existants : une donnée est tenant-scoped, les corps JSON publics ne portent jamais le tenant, l’identité ou les permissions, et les routes ne manipulent pas directement les modèles ORM.[5] [6] Elle suit également les principes de moindre privilège, de refus par défaut et de vérification de l’accès à chaque requête recommandés pour les applications web.[4]

| Décision de sécurité | Statut après S01 | Exigence S02 |
|---|---|---|
| `tenant_id` sur les roots et références du premier slice | **Déjà implémenté** | Le rattacher à une identité et à un membership actif résolus côté serveur. |
| Command receipts, Domain Events et outbox corrélés | **Déjà implémentés** | Les compléter par un audit de sécurité indépendant et minimisé. |
| Cloisonnement patron / collaborateur des prix et marges | **Contrat métier figé** | Le rendre impossible par RBAC/ABAC, projections, exports et téléchargements. |
| Authentification locale, MFA, sessions, rôles | **Non implémenté** | Créer le modèle, les migrations, les dépendances HTTP et les tests S02. |
| Support technique ponctuel et traçable | **Non implémenté** | Interdire tout accès permanent et imposer une procédure « break-glass ». |

---

## 2. Objectifs de sécurité et non-objectifs

### 2.1 Objectifs obligatoires

| ID | Objectif | Garantie attendue |
|---|---|---|
| `SEC-OBJ-01` | **Confidentialité inter-entreprises** | Un utilisateur du tenant A ne peut ni lire, ni modifier, ni déduire l’existence d’une ressource du tenant B. |
| `SEC-OBJ-02` | **Confidentialité financière** | Un collaborateur, partenaire, worker ou appel IA ne reçoit jamais un prix, coût, marge, devis, trésorerie ou règle de chiffrage sans droit patron explicite. |
| `SEC-OBJ-03` | **Intégrité engageante** | Une décision, une autorisation de dépôt, un prix officiel ou un changement de rôle ne peuvent être acceptés que par une identité autorisée, avec contexte, auteur et date auditables. |
| `SEC-OBJ-04` | **Disponibilité raisonnable** | Les attaques de mot de passe, de reset, d’énumération ou d’upload sont limitées sans empêcher silencieusement la reprise d’activité de l’entreprise. |
| `SEC-OBJ-05` | **Traçabilité utile et proportionnée** | Les opérations sensibles sont attribuables et exploitables en cas d’incident, sans journaliser les mots de passe, tokens, documents complets ou montants. |
| `SEC-OBJ-06` | **Révocation immédiate** | La suspension d’un compte, d’un membership, d’une affectation ou d’une session prend effet sur la requête suivante. |
| `SEC-OBJ-07` | **Évolutivité contrôlée** | Les futurs modules, connecteurs, workers et IA réutilisent le même `ActorContext` et ne créent pas une seconde politique d’autorisation. |

### 2.2 Non-objectifs explicites de S02

S02 ne prétend pas fournir une certification, un SSO fédéré ou une gestion de terminaux. Il ne délègue pas les décisions patron à un moteur automatique et ne rend pas les données financièrement sensibles consultables par une simple distinction visuelle d’écran. L’absence de chiffrement applicatif de colonnes dans S02 ne réduit pas l’obligation de limiter les accès ; elle sera traitée avant l’activation de `pricing` et des données de trésorerie.

---

## 3. Classes de données et conséquences d’accès

| Classe | Exemples | Lecture | Écriture / action | Envoi externe |
|---|---|---|---|---|
| `PUBLIC_TENDER` | Avis public, objet de marché, DCE public | Patron et collaborateur affecté | Selon module et affectation | Désactivé par défaut ; activable et minimisé par patron. |
| `INTERNAL_OPERATIONAL` | Tâches, analyses, demandes, avancement wizard | Patron ; collaborateur affecté au périmètre | Selon rôle, affectation et état de l’affaire | Interdit par défaut. |
| `PERSONAL_OR_ADMINISTRATIVE` | Kbis, RIB, attestations, CV, coordonnées | Patron ; collaborateur uniquement si pièce et tâche autorisées | Selon autorisation d’usage | Interdit par défaut. |
| `FINANCIAL_PRIVATE` | Coûts, marges, DPGF privée, devis, trésorerie | Patron uniquement ; délégation patron explicite future | Patron uniquement | **Interdit**. |
| `SECURITY_RESTRICTED` | Hash de mot de passe, secret MFA, session, recovery code, audit brut, quarantaine | Aucun utilisateur métier ; service spécialisé seulement | Service sécurité contrôlé | **Interdit**. |
| `SUPPORT_RESTRICTED` | Ticket, diagnostic minimisé, consentement break-glass | Support seulement pour le périmètre validé | Support selon procédure | Interdit sauf infrastructure autorisée. |

La classification est une propriété serveur de la ressource et de sa représentation exportée. Un bouton caché, une colonne masquée ou une convention frontend ne constitue jamais un contrôle d’accès. Les prix ne sont pas transmis au navigateur collaborateur, même sous forme masquée.[7]

---

## 4. Modèle de menace

### 4.1 Frontières de confiance

| Zone | Entités | Hypothèse de confiance | Contrôle obligatoire |
|---|---|---|---|
| Navigateur utilisateur | Patron, collaborateur, partenaire | **Non fiable** : JSON, IDs, rôle, tenant et en-têtes peuvent être falsifiés. | Session validée, anti-CSRF, validation Pydantic fermée, contexte serveur. |
| Caddy / TLS | Reverse proxy public | De confiance sous configuration versionnée. | HTTPS, HSTS, en-têtes de sécurité, limitation initiale ; API et DB non publiées. |
| API V8 | Routes, dépendances, handlers | De confiance partielle : toute route peut devenir un point de contournement. | Authentification puis autorisation centralisées, aucun ORM en route. |
| PostgreSQL | État canonique, idempotence, audit | De confiance mais non exposé publiquement. | Réseau privé, rôles DB séparés, migrations contrôlées, sauvegardes chiffrées. |
| MinIO / objet | Originaux, exports, dérivés | De confiance mais contenant des fichiers non fiables. | Bucket privé, métadonnées tenant, contrôle à chaque téléchargement, lien court, antivirus. |
| Worker / outbox | Parsing, génération, notifications | De confiance uniquement avec `ActorContext=SYSTEM` borné. | Aucun privilège patron implicite ; commandes internes corrélées et idempotentes. |
| Service externe | IA, OCR, SMTP, backup, n8n | **Non fiable par défaut** pour les données métier. | Politique explicite, minimisation, secret dédié, audit, possibilité de désactivation. |
| Support technique | Opérateur SMART_AO | Non autorisé par défaut aux données client. | Break-glass, consentement, périmètre/durée, audit renforcé. |

Le déploiement cible ne publie sur Internet que Caddy ; l’API, PostgreSQL, MinIO, worker et ClamAV restent sur le réseau interne.[7]

### 4.2 Scénarios de menace prioritaires

| ID | Menace | Exemple BTP | Impact | Contrôles SEC-01 | Preuve de test |
|---|---|---|---|---|---|
| `THR-01` | IDOR / fuite inter-tenant | Un patron A remplace un UUID de Consultation par celui de B. | Critique | Filtre tenant obligatoire, policy objet, 404 neutre, audit refus. | `S02-SEC-01..03` |
| `THR-02` | Escalade verticale | Collaborateur appelle directement l’approbation Go ou le futur endpoint prix. | Critique | Capability patron, MFA récente pour action engageante, policy centrale. | `S02-SEC-10..12` |
| `THR-03` | Escalade horizontale | Collaborateur affecté à l’affaire X consulte l’affaire Y du même tenant. | Élevé | Affectation active, scope lot/tranche, refus par défaut. | `S02-SEC-13..15` |
| `THR-04` | Vol de session | Cookie volé, refresh token rejoué ou compte laissé ouvert. | Élevé | Cookie sécurisé, rotation, détection de réemploi, révocation serveur, expiration courte. | `S02-SEC-20..24` |
| `THR-05` | Credential stuffing / énumération | Essais de mots de passe ou reset pour découvrir des comptes. | Élevé | Argon2id, messages neutres, rate limit par IP et identifiant, temporisation, audit. | `S02-SEC-25..29` |
| `THR-06` | Fuite financière par projection ou export | Endpoint collaborateur renvoie une marge cachée dans JSON. | Critique | Classification serveur, DTO dédiés, tests récursifs d’absence, export contrôlé. | `S02-SEC-30..33` |
| `THR-07` | Fichier ou URL non autorisé | Lien MinIO public/devinable vers un DCE ou une assurance. | Élevé | Bucket privé, autorisation objet avant URL signée, TTL court, audit téléchargement. | `S02-SEC-34..36` |
| `THR-08` | Injection / fichier malveillant | PDF, archive ou tableur transmis au parser. | Élevé | Limite/quota, type réel, hash, ClamAV, quarantaine, parsing isolé. | `S02-SEC-37..39` |
| `THR-09` | Fuite via logs, outbox ou IA | Token, mot de passe, DPGF privée ou RIB exporté dans un log. | Critique | Schéma audit minimisé, redaction, allow-list des événements externes, scans CI. | `S02-SEC-40..43` |
| `THR-10` | Abus support / administrateur VPS | Diagnostic permanent sur des dossiers clients. | Élevé | Break-glass expirant, consentement, double trace, accès de service minimal. | `S02-SEC-44..46` |
| `THR-11` | Altération ou effacement d’audit | Compte compromis efface des traces de téléchargement. | Élevé | Append-only applicatif, privilèges DB séparés, export scellé, supervision. | `S02-SEC-47..49` |
| `THR-12` | Secret de déploiement exposé | JWT key ou mot de passe DB dans Git, image ou logs. | Critique | Secrets hors Git, permissions, rotation, scan CI, séparation par VPS. | `S02-SEC-50..52` |

---

## 5. Architecture d’autorisation

### 5.1 Résolution obligatoire du contexte serveur

Le client ne fournit jamais `tenant_id`, `actor_id`, `role`, permission, classification effective, `caused_by_event_id` ou identité de support. Toute route suit la séquence suivante :

```text
HTTPS request
  → corrélation technique
  → validation session / révocation / MFA
  → identité authentifiée
  → membership actif dans le tenant demandé ou sélectionné
  → résolution ActorContext côté serveur
  → autorisation ressource + action + contexte
  → construction de commande sans attribut de confiance client
  → handler propriétaire et transaction
  → audit de sécurité / réponse publique minimisée
```

`ActorContext` est le seul objet de confiance transmis à l’application. Il enrichit le `ServerResolvedContext` d’APP-01 par les attributs nécessaires à la policy ; il est interne, immuable durant la requête et jamais sérialisé dans une réponse.

| Champ `ActorContext` | Origine serveur | Usage |
|---|---|---|
| `actor_id`, `identity_id` | Session validée | Attribution, audit, contrôle de suspension. |
| `tenant_id`, `membership_id` | Membership actif sélectionné et vérifié | Filtre de chaque repository, objet, job et stockage. |
| `actor_kind` | Rôle/membership | Distinction patron, délégataire, collaborateur, système, support. |
| `capabilities` | Policy recalculée | Décision d’autorisation ; jamais acceptée depuis JWT brut. |
| `case_assignment` / scope | Assignment active, si ressource affaire | Contrôle collaborateur par affaire, lots, tranches, durée. |
| `session_id`, `auth_strength` | Session et MFA | Révocation et step-up pour opérations sensibles. |
| `correlation_id`, `request_id` | Middleware | Chaînage de commande, événement, audit et logs. |

### 5.2 Modèle RBAC + ABAC + relation métier

SMART_AO adopte un modèle hybride. Le rôle fournit une capacité large ; les attributs de la ressource et la relation d’affectation décident l’accès réel. Ce choix évite d’accorder à un collaborateur l’ensemble du portefeuille parce qu’il possède un rôle global. Il applique les recommandations de contrôle d’accès par moindre privilège, refus par défaut et vérification objet par objet.[4]

```text
allow(actor, action, resource, context) =
    active_identity
    AND active_membership(tenant)
    AND session_is_valid
    AND role_grants_candidate_capability
    AND resource.tenant_id == context.tenant_id
    AND resource.classification is permitted
    AND relationship_scope_is_sufficient
    AND business_state_allows_action
    AND step_up_if_required
```

Aucune règle ne peut « compenser » l’absence de `tenant_id` ou de membership. Toute policy retourne une décision explicite `ALLOW`, `DENY_NOT_FOUND_OR_FORBIDDEN`, `DENY_AUTHENTICATION_REQUIRED`, `DENY_STEP_UP_REQUIRED` ou `DENY_POLICY` ; seule la couche HTTP transforme cette décision en réponse publique minimisée.

---

## 6. Identité, membership et bootstrap du premier patron

### 6.1 Entités S02 à créer

| Entité | Responsabilité | Champs minimaux | Invariants |
|---|---|---|---|
| `Identity` | Personne authentifiable, indépendante du tenant. | UUID, email normalisé, état, vérification email, dates. | Email unique normalisé ; aucun tenant implicite ; jamais supprimée physiquement si audit lié. |
| `PasswordCredential` | Empreinte Argon2id et métadonnées de changement. | identity, hash, paramètres/version, changed_at, must_change. | Aucun mot de passe clair, réversible ou exportable. |
| `TenantMembership` | Relation identité ↔ entreprise et rôle principal. | tenant, identity, role, state, activated/revoked dates. | Une membership suspendue/révoquée interdit toute session dans le tenant. |
| `Assignment` | Portée collaborateur sur une affaire. | membership, case, actions, lots/tranches, dates, state. | Aucun droit financier implicite ; expiration vérifiée sur chaque action. |
| `Session` | Session serveur révoquable et rotation. | session id, identity, tenant context, refresh hash, expiry, revoked_at, auth strength. | Refresh token à usage unique ; réemploi = révocation de famille. |
| `MfaCredential` | Secret TOTP chiffré ou méthode de possession future. | identity, encrypted secret, verified_at, last_used_at, state. | Secret jamais envoyé au client après enrollment ; activation prouvée. |
| `RecoveryCode` | Continuité MFA contrôlée. | hash, usage unique, generated_at, consumed_at. | Codes affichés une seule fois, stockés hachés. |
| `SecurityAuditEvent` | Trace de sécurité indépendante du métier. | §10.2. | Append-only, payload minimisé, accès restreint. |

### 6.2 États d’identité et de membership

| Objet | États | Effet d’accès |
|---|---|---|
| `Identity` | `PENDING_VERIFICATION`, `ACTIVE`, `SUSPENDED`, `LOCKED`, `ARCHIVED` | Seule `ACTIVE` peut ouvrir une session ; `LOCKED` est temporaire après défense anti-abus. |
| `TenantMembership` | `INVITED`, `ACTIVE`, `SUSPENDED`, `REVOKED`, `EXPIRED` | Seule `ACTIVE` peut former un `ActorContext` du tenant. |
| `Session` | `ACTIVE`, `ROTATED`, `REVOKED`, `EXPIRED`, `COMPROMISED` | Seule `ACTIVE` permet un refresh ; un réemploi la rend `COMPROMISED`. |
| `MfaCredential` | `PENDING`, `ACTIVE`, `DISABLED`, `REPLACED` | Une méthode `ACTIVE` est requise pour les patrons après période d’enrôlement. |

### 6.3 Bootstrap sûr

Le VPS d’un client ne propose **aucune inscription publique**. Le premier patron est créé par une commande d’installation unique, exécutée localement dans le contexte administrateur du déploiement. Elle crée le tenant, l’identité et une membership `PATRON_ADMIN` dans une seule transaction.

| Étape | Règle |
|---|---|
| Initialisation | Le bootstrap génère un secret d’invitation à usage unique, conservé seulement sous forme de hash avec expiration courte. |
| Première connexion | Le patron définit son mot de passe, vérifie son email si SMTP activé et reçoit l’obligation d’enrôler MFA avant la fin de la période de grâce. |
| Terminaison | Le token bootstrap est consommé puis rendu définitivement inutilisable ; aucun second patron ne peut être créé par ce chemin. |
| Invitations suivantes | Seul un patron actif, MFA satisfaite, peut inviter ou suspendre un collaborateur ; l’invitation est liée à un tenant et à une durée. |
| Erreur | Une invitation inexistante, expirée, déjà consommée ou associée à un autre tenant répond de manière neutre. |

---

## 7. Rôles et matrice d’autorisation

### 7.1 Rôles stables S02

| Rôle | Objet | Capacités autorisées | Interdits non négociables |
|---|---|---|---|
| `PATRON_ADMIN` | Membership tenant | Entreprise, comptes, invitations, politique IA, toutes les lectures métier autorisées, décisions, prix, exports et dépôt selon module. | Autre tenant ; effacement d’audit ; contournement de l’immuabilité métier. |
| `PATRON_DELEGATE` | Membership + délégation explicite | Sous-ensemble nommé par patron : décision non financière, revue, export ou dépôt futur selon grant. | Prix/marge/décision/dépôt sans capability explicite et MFA requise. |
| `COLLABORATEUR` | Membership + Assignment | Préparation DCE sur affaires affectées, tâches, demandes, pièces explicitement autorisées, transmission au patron. | Prix, marge, trésorerie, décisions, dépôt, portefeuille non affecté, politique IA globale. |
| `PARTENAIRE_EXTERNAL` | Grant limité dans le temps | Répondre à une demande ou déposer un fichier dans un espace limité. | Authentification interne, bibliothèque, autres affaires, exports, prix et DCE complet. |
| `SUPPORT_BREAK_GLASS` | Grant support temporaire | Diagnostic strictement convenu, sans lecture de contenu par défaut. | Accès persistant, consultation libre des DCE, documents, prix ou données personnelles. |
| `SYSTEM` | Identité technique non interactive | Consommer outbox, exécuter jobs et commandes internes déclarées. | Session navigateur, finalisation patron, extension de ses droits par payload. |

### 7.2 Capacités fonctionnelles initiales

| Capacité | Patron admin | Délégataire | Collaborateur affecté | Partenaire | System |
|---|---:|---:|---:|---:|---:|
| Lire Consultation / DCE public autorisé | Oui | Selon grant | Oui, périmètre affecté | Non | Si job déclaré |
| Écrire préparation DCE | Oui | Selon grant | Oui, périmètre affecté | Réponse limitée | Si job déclaré |
| Lire document administratif autorisé | Oui | Selon grant | Seulement pièce/tâche autorisée | Non | Si job déclaré |
| Lire ou modifier `FINANCIAL_PRIVATE` | Oui | Future délégation explicite seulement | **Non** | **Non** | **Non** |
| Créer/activer/suspendre utilisateur | Oui | Non | Non | Non | Non |
| Finaliser Go/No-Go | Oui + MFA | Grant explicite + MFA | **Non** | **Non** | **Non** |
| Autoriser dépôt / prix | Oui + MFA | Grant explicite + MFA, futur slice | **Non** | **Non** | **Non** |
| Télécharger/exporter sensible | Oui, audit | Grant explicite, audit | Seulement artefact autorisé | Seulement objet partagé | Non |
| Lire audit de son tenant | Synthèse limitée | Non par défaut | Non | Non | Écriture seulement |

La policy ne déduit jamais un droit financier d’une affectation d’affaire. Une affectation active autorise seulement les actions et classes explicitement déclarées dans son scope, conformément au contrat `ASN`.[5]

---

## 8. Authentification, MFA et sessions

### 8.1 Mots de passe et défense anti-abus

Les mots de passe locaux sont stockés exclusivement sous **Argon2id** via `argon2-cffi`, avec sel généré par la bibliothèque et paramètres versionnés. Le profil initial cible au minimum 64 MiB de mémoire, trois itérations et un parallélisme mesuré sur le VPS client ; les paramètres doivent être calibrés avant mise en production, puis augmentés lors d’un changement de mot de passe si nécessaire. Aucun hash générique SHA-256, MD5 ou SHA-1 ne peut être utilisé comme credential.

| Règle | Exigence |
|---|---|
| Identifiant | Email normalisé et unique, ou identifiant entreprise documenté ultérieurement ; jamais compte partagé. |
| Mot de passe | Au moins 14 caractères ; collage et gestionnaires de mots de passe autorisés ; vérification contre une liste de mots de passe compromis lorsque le mécanisme est disponible sans fuite du mot de passe. |
| Tentatives | Rate limit cumulant IP, identifiant normalisé et session ; délai progressif ; verrouillage temporaire après seuil ; message identique quel que soit l’état du compte. |
| Renouvellement | Pas de renouvellement périodique imposé pour les utilisateurs ordinaires ; changement forcé après bootstrap/reset ; changement immédiat en cas de soupçon de compromission. |
| Reset | Token à usage unique, hashé, expirant, réponse de demande neutre ; toutes les sessions actives sont révoquées après succès. |

Ces règles retiennent l’identifiant individuel, le stockage par empreinte, la MFA et la limitation de tentatives recommandés par la CNIL et l’ANSSI.[1] [3]

### 8.2 MFA et step-up

| Situation | Niveau requis |
|---|---|
| Consultation et préparation collaborative courante | Session authentifiée valide. |
| Patron admin après période d’enrôlement | MFA active obligatoire. |
| Création/suspension de compte, modification de MFA, exports sensibles, activation d’un service externe | MFA récente, inférieure ou égale à 15 minutes. |
| Finalisation Go/No-Go, prix officiel, autorisation de dépôt, break-glass | MFA récente et justification métier lorsque requise par le module. |
| Recovery code | Réauthentification par mot de passe puis consommation unique ; audit critique. |

La première méthode S02 est TOTP avec secret chiffré applicativement et recovery codes. WebAuthn est une évolution préférée mais n’est pas simulée dans S02. Le produit n’utilise pas de biométrie propre.

### 8.3 Sessions de navigateur

| Élément | Décision SEC-01 |
|---|---|
| Access token | JWT signé, durée maximale 15 minutes, `iss`, `aud`, `sub`, `sid`, `jti`, `iat`, `exp`, version de session ; aucun rôle ou permission faisant autorité. |
| Refresh token | Valeur opaque aléatoire, cookie `HttpOnly`, `Secure`, `SameSite=Lax`, hashée en base ; rotation à chaque usage. |
| Expiration | Inactivité maximale 8 heures ; durée absolue 24 heures ; 12 heures pour patron/délégataire ; plus courte possible par politique tenant. |
| Révocation | Vérification serveur de `Session.state`, de la membership et de l’identité sur chaque requête authentifiée ; déconnexion, reset, suspension et réemploi de refresh révoquent. |
| CSRF | Token anti-CSRF distinct obligatoire sur toute méthode unsafe utilisant les cookies. |
| Stockage navigateur | Aucun token d’authentification dans `localStorage`, URL, logs frontend ou payload métier. |
| Sélection tenant | Choix d’un tenant parmi memberships actives ; changement de tenant crée/actualise le contexte mais n’accorde jamais une membership. |

---

## 9. Isolation tenant, objets et recherches

### 9.1 Règles systématiques

1. **Toute table métier, table de sécurité tenant-scoped, événement, receipt, outbox, job, index vectoriel, objet MinIO et export porte `tenant_id`.**
2. **Tout accès par ID filtre d’abord `tenant_id`, puis l’ID et la policy objet.** Un UUID difficile à deviner n’est pas une autorisation.
3. **Toute relation inter-table reste tenant-scoped par FK composite** lorsque la relation est durable. Le tenant d’une référence est vérifié avant la création de commande.
4. **Toute recherche**, exacte ou sémantique, applique le filtre tenant dans la requête primaire, pas après agrégation de résultats.
5. **Toute URL de téléchargement** est créée après policy objet, expire rapidement et ne porte pas de secret métier ni de tenant dans un chemin public.
6. **Toute erreur cross-tenant** retourne `NOT_FOUND_OR_FORBIDDEN` sans nom, titre, hash, révision, type ou détail de la ressource ciblée.
7. **Le tenant ne provient jamais d’un header ou corps client libre.** Il provient de la session et de la membership validées ; un futur sous-domaine ne pourra être utilisé qu’après vérification avec cette membership.

### 9.2 Repositories, événements et jobs

| Zone | Règle tenant |
|---|---|
| Repository lecture | Signature explicite `tenant_id + aggregate_id`; retour `None` si hors tenant. |
| Repository écriture | `tenant_id` uniquement depuis `ActorContext`; update optimiste sur tenant + ID + révision. |
| Command receipt | Unicité `tenant + actor + command type + idempotency key`; réponse replayée revalidée contre session/membership actuelle. |
| Domain Event / outbox | `tenant_id`, acteur et corrélation obligatoires ; payload minimal sans secrets. |
| Worker | `SYSTEM` ne peut traiter qu’un message tenant-scoped ; aucune lecture transversale non filtrée. |
| Objet MinIO | Métadonnées tenant/affaire/version/classification ; vérification serveur avant URL ou stream. |
| Sauvegarde | Chaque snapshot est chiffré et l’accès restauration est limité au service de backup ou à une procédure patron/support autorisée. |

---

## 10. Audit, journalisation et rétention

### 10.1 Principes

L’audit métier existant (`DomainEventRecord`, `CommandReceiptRecord`) est utile mais insuffisant pour la sécurité : un refus d’authentification, une lecture sensible, un téléchargement ou un changement MFA peut ne produire aucun événement de domaine. S02 crée donc `SecurityAuditEvent` comme journal spécialisé append-only.

La CNIL recommande de tracer les activités métier, interventions techniques, anomalies et événements de sécurité en conservant l’auteur, la date, la nature et la référence de la donnée, tout en évitant les données personnelles excessives et toute conservation illimitée.[2]

### 10.2 Schéma minimal d’un événement d’audit

| Champ | Règle |
|---|---|
| `id`, `occurred_at`, `schema_version` | UUID et date UTC immuables ; version de contrat obligatoire. |
| `tenant_id` | Nullable seulement pour authentification pré-tenant, obligatoire dès qu’un tenant est connu. |
| `actor_id`, `identity_id`, `session_id` | Références pseudonymes ; null uniquement pour tentative anonyme. |
| `actor_kind` et `auth_strength` | Identifient la nature de l’acteur et le niveau MFA, sans inclure credential. |
| `event_type`, `outcome`, `severity` | Vocabulaire allow-listé ; `SUCCEEDED`, `DENIED`, `FAILED`, `SUSPICIOUS`. |
| `action`, `resource_type`, `resource_id` | Référence de ressource, jamais duplication de document/price payload. |
| `case_id` | Présent si l’événement concerne une affaire. |
| `correlation_id`, `command_id`, `request_id` | Permettent de relier commande, trace, événement métier et incident. |
| `source_ip_hash`, `user_agent_family` | Informations réduites ; IP brute réservée au journal technique à durée plus courte. |
| `reason_code`, `metadata_json` | Codes et métadonnées allow-listées ; aucun mot de passe, token, cookie, hash de password, RIB, DCE complet ou montant. |

### 10.3 Événements obligatoires

| Famille | Événements à tracer |
|---|---|
| Authentification | Login succès/échec, lock/unlock, logout, reset demandé/consommé, changement password, MFA enrollment/verification/disable, recovery code utilisé, session révoquée, refresh token réemployé. |
| Autorisation | Refus patron requis, refus tenant, refus affectation, refus classification financière, step-up requis. |
| Identité | Bootstrap patron, invitation créée/expirée/acceptée, membership activée/suspendue/révoquée, délégation modifiée. |
| Données sensibles | Lecture/download/export d’un objet `PERSONAL_OR_ADMINISTRATIVE` ou `FINANCIAL_PRIVATE`, génération de lien, partage externe, consultation de journal. |
| Actions engageantes | Décision finalisée, prix officiel validé, autorisation/déclaration de dépôt, modification politique IA. |
| Externe et support | Appel IA/OCR externe, envoi SMTP, activation/fin break-glass, changement de secret, restauration backup. |
| Sécurité plateforme | Antivirus refusé, type fichier incohérent, rate-limit, erreur de signature, anomalie de session, échec de publication critique. |

### 10.4 Intégrité, accès et conservation

| Sujet | Exigence |
|---|---|
| Écriture | L’application n’expose ni `UPDATE` ni `DELETE` sur `security_audit_events`; rôle DB applicatif séparé du rôle maintenance. |
| Protection | Les utilisateurs métier ne lisent pas les événements bruts ; le patron reçoit une vue synthétique de son tenant sans données techniques sensibles. |
| Scellement | Export quotidien signé ou chaîné (`previous_digest`, `event_digest`) vers stockage backup privé ; toute rupture est une alerte. |
| Rétention | 12 mois glissants par défaut pour le journal de sécurité ; ajustement documenté en cas de contentieux, obligation légale ou incident. Les logs techniques IP bruts ont une durée plus courte définie par l’exploitation. |
| Supervision | Une tâche vérifie la continuité d’écriture, le retard de scellement et les événements critiques non analysés. |
| Transparence | La politique de confidentialité et l’écran de connexion informent de la journalisation de sécurité et de sa finalité. |

---

## 11. Secrets, fichiers, intégrations et exploitation

### 11.1 Secrets et configuration

| Règle | Exigence |
|---|---|
| Hors Git | Aucun secret dans le dépôt, image, fixture, documentation, log ou capture. |
| Par environnement | Clés JWT, chiffrement MFA, accès S3, DB, SMTP et provider externe distincts par VPS/environnement. |
| Permissions | Fichier de secrets lisible uniquement par le compte de service ; aucune variable `.env` copiée dans une image de production. |
| Rotation | Clés signantes avec `kid` et période de chevauchement ; secrets externes rotatifs ; incident de fuite = révocation et audit. |
| CI | `detect-secrets`, `pip-audit`, `bandit` et scan image sont ajoutés avant préproduction, conformément à la référence infrastructure.[7] |

### 11.2 Admission et téléchargement de fichier

Tout upload passe par quota, contrôle de type réel, hash SHA-256, antivirus, déduplication, stockage privé, version immuable puis job planifié. Un fichier suspect est uniquement disponible en quarantaine technique.[7] Un téléchargement est une action auditable, conditionnée par le tenant, la classification, l’affaire, la version et le rôle au moment exact de l’émission du lien.

### 11.3 IA, OCR, e-mail, n8n et backup

Aucun connecteur ne contourne le `ActorContext`. Les prix, marges, déboursés, trésoreries et documents sensibles ne sont jamais envoyés à un provider IA externe ; les DCE publics restent désactivés par défaut et requièrent une politique patron explicite, une minimisation des pages et une trace.[7] Les webhooks et automatisations n8n futurs utilisent un secret dédié, une allow-list d’événements, un schéma signé ou vérifié, une idempotence et un kill switch patron.

---

## 12. Règles HTTP et réponses publiques

| Surface | Règle SEC-01 |
|---|---|
| Endpoints anonymes | Uniquement healthcheck sans détail sensible, login, refresh, reset et acceptation d’invitation ; même réponses neutres contre l’énumération. |
| Endpoints authentifiés | Dépendance unique de contexte serveur ; vérification session, membership et policy avant handler. |
| Headers | `Cache-Control: no-store` sur auth et réponses privées ; CSP, HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy` restrictive et protection clickjacking via Caddy. |
| CORS | Origines exactes du tenant/VPS ; jamais `*` avec cookies ; méthodes et headers minimaux. |
| Erreurs | `404 NOT_FOUND_OR_FORBIDDEN` pour ressource absente ou inaccessible ; pas de trace interne, nom de tenant, règle exacte ou ressource externe dans la réponse. |
| Pagination / recherche | Limites bornées, filter tenant obligatoire, tri allow-listé, aucune recherche globale implicite. |
| Exports | Création asynchrone, autorisation réévaluée au téléchargement, expiration et audit. |

---

## 13. Plan d’implémentation S02

| Sous-slice | Contenu | Sortie vérifiable |
|---|---|---|
| `S02-A` | Contrats SEC-01 dans le code : types `ActorContext`, policy interface, erreurs neutres, dépendances de route. | Tests schema/architecture prouvant qu’aucun contexte de confiance ne vient du JSON. |
| `S02-B` | Migration identité, membership, bootstrap patron, Argon2id, invitation et reset. | PostgreSQL contraint les états, unicités et révocations ; tests tenant A/B. |
| `S02-C` | Sessions rotatives, MFA TOTP/recovery, rate limiting et step-up. | Rejeu refresh détecté, suspension invalide session, patron sans MFA bloqué sur action sensible. |
| `S02-D` | Policies RBAC/ABAC/ReBAC et première affectation collaborateur. | Collaborateur limité à l’affaire/scope assigné ; aucune donnée financière sérialisée. |
| `S02-E` | Audit sécurité append-only, scellement et vue patron minimisée. | Événements sensibles auditables, impossibles à modifier par l’application, sans secret ni contenu excessif. |

Aucun endpoint métier actuel ne doit être déclaré « protégé » tant que `S02-A` à `S02-C` ne sont pas validés. Pendant ce stade de développement, les `CommandContext` injectés par tests restent un mécanisme de test, pas une authentification de production.

---

## 14. Plan de tests de sécurité S02

| ID | Scénario | Résultat attendu |
|---|---|---|
| `S02-SEC-01` | Patron A lit/écrit une ressource B via UUID modifié. | `404 NOT_FOUND_OR_FORBIDDEN`; aucune fuite, aucune trace métier B. |
| `S02-SEC-02` | Client envoie `tenant_id`, `actor_id`, rôle ou capability dans JSON. | `422`; le contexte résolu serveur est inchangé. |
| `S02-SEC-03` | JWT A contient un tenant B ou session de membership révoquée. | Session/tenant refusé avant repository. |
| `S02-SEC-10` | Collaborateur tente décision Go, prix, export financier ou dépôt. | `403`; mutation absente ; audit `AUTHORIZATION_DENIED`. |
| `S02-SEC-11` | Délégataire sans grant explicite tente une finalisation. | `403`; capability patron non inférée du rôle. |
| `S02-SEC-13` | Collaborateur du tenant A vise une Case A non affectée. | `404` ou `403` neutre selon route ; aucun DTO retourné. |
| `S02-SEC-20` | Logout, reset ou suspension avec refresh actif. | Refresh suivant rejeté ; session révoquée auditée. |
| `S02-SEC-21` | Réemploi d’un refresh token déjà tourné. | Famille de sessions compromise et révoquée ; alerte/audit critique. |
| `S02-SEC-22` | Patron tente action engageante avec MFA ancienne ou absente. | `403 STEP_UP_REQUIRED`; aucune commande métier. |
| `S02-SEC-25` | Rafale login/reset sur identifiant connu ou inconnu. | Même réponse publique, temporisation/rate limit, audit sans énumération. |
| `S02-SEC-30` | Sérialisation récursive collaborateur, receipt, event et erreur. | Aucun champ financier, secret, token, password hash ou document binaire. |
| `S02-SEC-34` | URL objet générée pour ressource hors tenant ou grant expiré. | URL absente ; audit refus ; objet non lisible. |
| `S02-SEC-40` | Login, reset, décision, téléchargement et appel externe. | `SecurityAuditEvent` complet/minimisé, corrélé, sans secret. |
| `S02-SEC-47` | Application tente update/delete d’un audit event. | Refus DB/policy ; scellement détecte toute altération. |
| `S02-SEC-50` | Secret dans source, log ou fixture. | CI échoue avant publication. |

---

## 15. Critères de sortie SEC-01 et S02

SEC-01 est accepté lorsque toutes les décisions de gel précédentes sont validées par le propriétaire du produit. S02 ne peut être présenté comme utilisable par un client que si les migrations, les contrôles HTTP, les policies et les tests `S02-SEC-*` pertinents sont verts, que le bootstrap patron ne laisse aucun token initial réutilisable et que les journaux de sécurité sont effectivement vérifiés sur un VPS de préproduction.

> **Règle finale :** aucune efficacité d’interface, automatisation, IA, tâche de fond ou nécessité de support ne justifie de contourner l’autorisation contextualisée, l’isolation tenant, la confidentialité financière ou l’historique audit.

---

## Références

[1] [CNIL — Sécurité : Authentifier les utilisateurs](https://www.cnil.fr/fr/securite-authentifier-les-utilisateurs), 14 mars 2024.  
[2] [CNIL — Sécurité : Tracer les opérations](https://www.cnil.fr/fr/securite-tracer-les-operations), 14 mars 2024.  
[3] [ANSSI — Recommandations relatives à l’authentification multifacteur et aux mots de passe](https://messervices.cyber.gouv.fr/guides/recommandations-relatives-lauthentification-multifacteur-et-aux-mots-de-passe), 8 octobre 2021.  
[4] [OWASP — Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).  
[5] [SMART_AO V8 — Contrat de domaine](SMART_AO_V8_CONTRAT_DE_DOMAINE.md).  
[6] [SMART_AO V8 — APP-01](SMART_AO_V8_APP_01_CONTRATS_PYDANTIC_PREMIER_SLICE.md).  
[7] [SMART_AO V8 — Architecture infrastructure de référence](SMART_AO_V8_ARCHITECTURE_INFRASTRUCTURE_REFERENCE.md).

---

**Fin de SEC-01 — Contrat de sécurité : identité, tenant, autorisation et audit — version 1.0**
