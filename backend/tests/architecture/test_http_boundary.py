from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.architecture
def test_consultation_route_has_no_orm_or_module_infrastructure_import() -> None:
    source = (
        REPOSITORY_ROOT / "backend/app/interfaces/http/routes/consultations.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert "sqlalchemy" not in imports
    assert not any(".infrastructure" in module for module in imports)
    assert not any(".domain" in module for module in imports)
