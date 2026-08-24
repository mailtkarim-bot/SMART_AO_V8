from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "verify_object_storage.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("verify_object_storage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_script_refuses_write_without_explicit_flag(monkeypatch) -> None:
    module = _load_script()
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    with pytest.raises(SystemExit, match="--confirm-write"):
        module.main()


class FakeStorage:
    instances: list[FakeStorage] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.operations: list[tuple[str, str]] = []
        self.__class__.instances.append(self)

    def write(self, *, storage_key: str, content: bytes) -> str:
        self.operations.append(("write", storage_key))
        return hashlib.sha256(content).hexdigest()

    def head(self, *, storage_key: str) -> dict[str, object]:
        self.operations.append(("head", storage_key))
        return {
            "content_length": len(b"SMART_AO_OBJECT_STORAGE_VERIFY_V1\n"),
            "sha256": hashlib.sha256(b"SMART_AO_OBJECT_STORAGE_VERIFY_V1\n").hexdigest(),
        }

    def read(self, *, storage_key: str) -> bytes:
        self.operations.append(("read", storage_key))
        return b"SMART_AO_OBJECT_STORAGE_VERIFY_V1\n"

    async def delete(self, *, storage_key: str) -> None:
        self.operations.append(("delete", storage_key))


def test_verify_script_runs_head_write_read_delete_without_logging_bucket(
    monkeypatch, capsys
) -> None:
    module = _load_script()
    FakeStorage.instances.clear()
    monkeypatch.setattr(module, "S3PrivateObjectStorage", FakeStorage)
    monkeypatch.setenv("SMART_AO_OBJECT_STORAGE_BUCKET", "private-bucket")
    monkeypatch.setenv("SMART_AO_OBJECT_STORAGE_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--confirm-write"])

    module.main()

    output = capsys.readouterr().out
    assert '"status": "ok"' in output
    assert "private-bucket" not in output
    assert "minio:9000" not in output
    assert len(FakeStorage.instances) == 1
    assert [operation for operation, _ in FakeStorage.instances[0].operations] == [
        "write",
        "head",
        "read",
        "delete",
    ]
