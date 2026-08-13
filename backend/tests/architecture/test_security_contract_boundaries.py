from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
SECURITY_DIR = PROJECT_ROOT / "app" / "platform" / "security"
SECURITY_CONTRACT_FILES = (
    SECURITY_DIR / "context.py",
    SECURITY_DIR / "authorization.py",
)
ERROR_MAPPING = PROJECT_ROOT / "app" / "interfaces" / "http" / "error_mapping.py"


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_security_contracts__when_inspected__then_have_no_framework_orm_or_business_imports(
) -> None:
    imports = set().union(*(_imports_from(path) for path in SECURITY_CONTRACT_FILES))

    assert not any(name.startswith("fastapi") for name in imports)
    assert not any(name.startswith("sqlalchemy") for name in imports)
    assert not any(name.startswith("app.modules") for name in imports)


def test_http_authorization_mapping__when_inspected__then_never_serializes_internal_reason(
) -> None:
    source = ERROR_MAPPING.read_text(encoding="utf-8")

    assert "decision.reason" not in source
    assert "decision.code" in source
