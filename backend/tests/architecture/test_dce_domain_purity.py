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
    "app.modules.case",
    "app.modules.decision",
)


@pytest.mark.architecture
@pytest.mark.parametrize("filename", ("consultation.py", "dce_version.py"))
def test_dce_domain_has_no_framework_or_foreign_module_import(filename: str) -> None:
    domain_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "modules"
        / "dce"
        / "domain"
        / filename
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
