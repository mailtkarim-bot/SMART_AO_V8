from __future__ import annotations

import ast

import pytest
from app.modules.enterprise.infrastructure.models.enterprise import (
    EnterpriseCompanyRecord,
    EnterpriseDocumentRecord,
    EnterpriseDocumentUploadRecord,
    EnterpriseDocumentVerificationRecord,
)
from app.platform.security.models import (
    EnterpriseCompanyRecord as LegacyEnterpriseCompanyRecord,
)
from app.platform.security.models import (
    EnterpriseDocumentRecord as LegacyEnterpriseDocumentRecord,
)
from app.platform.security.models import (
    EnterpriseDocumentUploadRecord as LegacyEnterpriseDocumentUploadRecord,
)
from app.platform.security.models import (
    EnterpriseDocumentVerificationRecord as LegacyEnterpriseDocumentVerificationRecord,
)

from tests.support.database import REPOSITORY_ROOT

POST_SLICE_MODULES = (
    "enterprise",
    "decision",
    "membership",
    "patron_action",
    "preparation",
    "pricing",
    "submission",
)


@pytest.mark.architecture
def test_enterprise_records_are_module_owned_with_legacy_reexports() -> None:
    records = (
        EnterpriseCompanyRecord,
        EnterpriseDocumentRecord,
        EnterpriseDocumentUploadRecord,
        EnterpriseDocumentVerificationRecord,
    )
    legacy_records = (
        LegacyEnterpriseCompanyRecord,
        LegacyEnterpriseDocumentRecord,
        LegacyEnterpriseDocumentUploadRecord,
        LegacyEnterpriseDocumentVerificationRecord,
    )

    assert all(
        record.__module__ == "app.modules.enterprise.infrastructure.models.enterprise"
        for record in records
    )
    assert records == legacy_records


@pytest.mark.architecture
def test_post_slice_modules_expose_application_and_public_boundaries() -> None:
    modules_root = REPOSITORY_ROOT / "backend/app/modules"
    for module_name in POST_SLICE_MODULES:
        module_root = modules_root / module_name
        assert (module_root / "application").is_dir(), module_name
        assert (module_root / "public").is_dir(), module_name


@pytest.mark.architecture
def test_membership_read_services_use_only_application_ports() -> None:
    source_paths = (
        REPOSITORY_ROOT
        / "backend/app/modules/membership/application/patron_assignment_cockpit.py",
        REPOSITORY_ROOT / "backend/app/modules/membership/application/assignment_history.py",
    )
    for source_path in source_paths:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert "sqlalchemy" not in imported_names, source_path
        assert "sqlalchemy" not in imported_modules, source_path
        assert not any(".infrastructure" in module for module in imported_modules), source_path


@pytest.mark.architecture
def test_decision_application_dossier_uses_reader_boundary() -> None:
    source_path = REPOSITORY_ROOT / "backend/app/modules/decision/application/patron_dossier.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "sqlalchemy" not in imported_names
    assert "sqlalchemy" not in imported_modules
    assert not any(".infrastructure" in module for module in imported_modules)
    assert "app.modules.decision.application.queries" in imported_modules


@pytest.mark.architecture
def test_post_slice_application_does_not_import_http_routes() -> None:
    modules_root = REPOSITORY_ROOT / "backend/app/modules"
    for module_name in POST_SLICE_MODULES:
        for source_path in (modules_root / module_name / "application").glob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            imported_modules = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }
            assert not any(
                module.startswith("app.interfaces.http") for module in imported_modules
            ), source_path


@pytest.mark.architecture
def test_post_slice_public_does_not_import_orm_or_infrastructure() -> None:
    modules_root = REPOSITORY_ROOT / "backend/app/modules"
    for module_name in POST_SLICE_MODULES:
        for source_path in (modules_root / module_name / "public").glob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            imported_modules = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }
            assert "sqlalchemy" not in imported_modules, source_path
            assert not any(".infrastructure" in module for module in imported_modules), source_path


@pytest.mark.architecture
def test_frontend_exposes_feature_boundaries_for_post_slice_workspaces() -> None:
    features_root = REPOSITORY_ROOT / "web/src/features"
    for feature_name in ("case", "dce", "decision"):
        assert (features_root / feature_name).is_dir(), feature_name
    assert (REPOSITORY_ROOT / "web/src/infrastructure").is_dir()
    assert (REPOSITORY_ROOT / "web/src/shared").is_dir()

