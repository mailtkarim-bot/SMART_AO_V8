import ast
from pathlib import Path

import pytest

BANNED_IMPORT_PREFIXES = (
    "fastapi",
    "sqlalchemy",
    "pydantic",
    "celery",
    "httpx",
    "requests",
    "app.modules.dce",
    "app.modules.decision",
)


@pytest.mark.architecture
def test_case_domain_has_no_framework_or_foreign_module_import() -> None:
    domain_path = (
        Path(__file__).resolve().parents[2] / "app" / "modules" / "case" / "domain" / "case.py"
    )
    tree = ast.parse(domain_path.read_text(encoding="utf-8"), filename=str(domain_path))

    imported_modules = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    imported_modules.extend(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0
    )

    assert all(
        not imported.startswith(prefix)
        for imported in imported_modules
        for prefix in BANNED_IMPORT_PREFIXES
    )
