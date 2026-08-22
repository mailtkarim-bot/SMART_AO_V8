from __future__ import annotations

import ast
from pathlib import Path

import pytest


@pytest.mark.architecture
def test_knowledge_domain_has_no_framework_or_infrastructure_imports() -> None:
    domain_path = Path(__file__).resolve().parents[2] / "app" / "modules" / "knowledge" / "domain"
    imported_modules: list[str] = []
    for path in domain_path.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        imported_modules.extend(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0
        )

    banned_prefixes = (
        "fastapi",
        "sqlalchemy",
        "pydantic",
        "sentence_transformers",
        "ortools",
        "app.modules",
    )
    assert all(
        not imported.startswith(prefix)
        for imported in imported_modules
        for prefix in banned_prefixes
    )
