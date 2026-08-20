from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
from uuid import uuid4


class GeneratedDocumentStorage:
    """Port for private generated-document bytes."""

    def write(self, *, storage_key: str, content: bytes) -> str:
        raise NotImplementedError

    def read(self, *, storage_key: str) -> bytes:
        raise NotImplementedError


class LocalGeneratedDocumentStorage(GeneratedDocumentStorage):
    """Atomic private storage under the already protected DCE root."""

    def __init__(self, *, root: Path) -> None:
        self._root = root.resolve()

    def write(self, *, storage_key: str, content: bytes) -> str:
        target = self._path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(target.parent, 0o700)
        if target.exists():
            raise FileExistsError("private generated document already exists")
        temporary = target.parent / f".{target.name}.{uuid4().hex}.part"
        try:
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            os.chmod(target, 0o600)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return hashlib.sha256(content).hexdigest()

    def read(self, *, storage_key: str) -> bytes:
        return self._path(storage_key).read_bytes()

    def _path(self, storage_key: str) -> Path:
        relative = PurePosixPath(storage_key)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("invalid private generated document key")
        candidate = (self._root / Path(*relative.parts)).resolve()
        if self._root not in candidate.parents:
            raise ValueError("generated document key escapes private root")
        return candidate
