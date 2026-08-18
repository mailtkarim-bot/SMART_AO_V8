import ast
from pathlib import Path

FORBIDDEN_PREFIXES = (
    "app.modules.dce.infrastructure",
    "app.modules.membership.application",
)


def test_preparation_application_does_not_import_foreign_internals() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "modules" / "preparation" / "application"
    violations: list[str] = []
    for source_path in sorted(root.glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported = node.module if isinstance(node, ast.ImportFrom) else None
            if imported is None:
                continue
            if imported.startswith(FORBIDDEN_PREFIXES):
                violations.append(f"{source_path.name}: {imported}")
    assert violations == []
