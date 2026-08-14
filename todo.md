# CASE-WEB-02 — Raccordement backend

- [x] Auditer le modèle d’affectation Case et les champs réellement projetables.
- [x] Définir le DTO fermé de `GET /api/v1/cases/assigned`.
- [x] Ajouter la query tenant-scopée et la policy ReBAC `case.dce.read`.
- [x] Exposer la route authentifiée avec réponses neutres et audit des refus.
- [x] Vérifier le chemin et la visibilité navigateur du cookie CSRF.
- [x] Tester login, refresh, logout, CSRF invalide et cookie HttpOnly.
- [x] Rejouer Ruff, pytest, Alembic et les contrôles SEC-01 avant publication.
- [ ] Raccorder le frontend à l’endpoint publié et mettre à jour la mémoire durable.
