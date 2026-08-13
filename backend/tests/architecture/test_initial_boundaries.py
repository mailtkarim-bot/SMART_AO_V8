from pathlib import Path

MODULES = ("case", "dce", "decision")
LAYERS = ("domain", "application", "infrastructure", "public")


def test_first_slice_modules_expose_all_required_layers() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "modules"
    for module_name in MODULES:
        for layer_name in LAYERS:
            assert (root / module_name / layer_name).is_dir()
