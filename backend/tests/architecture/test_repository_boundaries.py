from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.architecture
@pytest.mark.parametrize(
    "relative_path",
    [
        "backend/app/modules/case/application/ports.py",
        "backend/app/modules/dce/application/ports.py",
        "backend/app/modules/decision/application/ports.py",
    ],
)
def test_application_repository_ports_have_no_sqlalchemy_dependency(relative_path: str) -> None:
    source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    assert "sqlalchemy" not in imported_modules


@pytest.mark.architecture
@pytest.mark.parametrize(
    ("relative_path", "owner_module"),
    [
        ("backend/app/modules/case/infrastructure/repositories.py", "case"),
        ("backend/app/modules/dce/infrastructure/repositories.py", "dce"),
        ("backend/app/modules/decision/infrastructure/repositories.py", "decision"),
    ],
)
def test_repository_does_not_import_another_module_internal(
    relative_path: str,
    owner_module: str,
) -> None:
    source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    internal_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("app.modules.")
        and not node.module.startswith(f"app.modules.{owner_module}.")
    }

    assert not internal_imports
