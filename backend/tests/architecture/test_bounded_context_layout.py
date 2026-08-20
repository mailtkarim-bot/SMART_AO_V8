from pathlib import Path


def test_enterprise_bounded_context_has_its_own_layers() -> None:
    modules_root = Path(__file__).resolve().parents[2] / "app" / "modules"
    enterprise_root = modules_root / "enterprise"
    membership_root = modules_root / "membership"

    assert (enterprise_root / "application").is_dir()
    assert (enterprise_root / "public").is_dir()
    assert not list(membership_root.glob("**/enterprise*.py"))
