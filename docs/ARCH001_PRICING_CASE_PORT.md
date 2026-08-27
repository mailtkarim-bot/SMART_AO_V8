# ARCH-001 — port de résolution Case du pricing

Le service applicatif `PricingImportCreationService` ne construit plus de requête SQLAlchemy pour vérifier l’existence du dossier métier. Il dépend désormais du port `CaseExistenceReader`, défini dans `pricing/application/ports.py`.

La composition root injecte l’adaptateur `SqlAlchemyCaseExistenceReader`, situé dans `pricing/infrastructure/case_reader.py`. L’adaptateur impose le couple `(tenant_id, case_id)` et retourne uniquement un booléen. Il n’expose aucun modèle ORM au service applicatif et ne renvoie aucune donnée de dossier.

La persistance transactionnelle du batch d’import et de ses lignes reste dans le handler de commande existant ; ce sous-lot ne change ni le contrat HTTP, ni les calculs financiers, ni les contrôles de classification `FINANCIAL_PRIVATE`. Les tests DB de création continuent de vérifier la résolution tenant-scoped et la persistance dans la transaction de commande.
