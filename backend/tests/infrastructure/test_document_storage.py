from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from app.modules.preparation.infrastructure import document_storage
from app.modules.preparation.infrastructure.document_storage import LocalGeneratedDocumentStorage


def test_write_is_atomic_private_and_returns_content_hash(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    storage = LocalGeneratedDocumentStorage(root=root)
    content = b"document bytes"

    digest = storage.write(storage_key="case-1/answer.pdf", content=content)
    target = root / "case-1" / "answer.pdf"

    assert digest == hashlib.sha256(content).hexdigest()
    assert target.read_bytes() == content
    assert target.stat().st_mode & 0o777 == 0o600
    assert (root / "case-1").stat().st_mode & 0o777 == 0o700
    assert list(target.parent.glob("*.part")) == []


def test_write_rejects_existing_target_without_overwriting(tmp_path: Path) -> None:
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "generated")
    storage.write(storage_key="answer.pdf", content=b"first")

    with pytest.raises(FileExistsError, match="already exists"):
        storage.write(storage_key="answer.pdf", content=b"second")

    assert (tmp_path / "generated" / "answer.pdf").read_bytes() == b"first"


def test_write_removes_temporary_file_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "generated")

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("filesystem unavailable")

    monkeypatch.setattr(document_storage.os, "replace", fail_replace)

    with pytest.raises(OSError, match="filesystem unavailable"):
        storage.write(storage_key="answer.pdf", content=b"content")

    assert list((tmp_path / "generated").glob("*.part")) == []
    assert not (tmp_path / "generated" / "answer.pdf").exists()


@pytest.mark.parametrize(
    "storage_key", ["/absolute.pdf", "../escape.pdf", "case/../escape.pdf", "."]
)
def test_path_rejects_absolute_dot_and_parent_segments(
    tmp_path: Path, storage_key: str
) -> None:
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "generated")

    with pytest.raises(ValueError, match="invalid private generated document key|escapes"):
        storage.write(storage_key=storage_key, content=b"content")


@pytest.mark.parametrize("storage_key", ["", "./"])
def test_path_rejects_empty_or_normalized_segments(tmp_path: Path, storage_key: str) -> None:
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "generated")

    with pytest.raises(ValueError, match="invalid private generated document key|escapes"):
        storage.read(storage_key=storage_key)


def test_path_rejects_symlink_that_escapes_private_root(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    outside = tmp_path / "outside"
    outside.mkdir()
    root.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    storage = LocalGeneratedDocumentStorage(root=root)

    with pytest.raises(ValueError, match="escapes private root"):
        storage.write(storage_key="linked/answer.pdf", content=b"content")

    assert not (outside / "answer.pdf").exists()


def test_read_returns_written_bytes_and_missing_key_is_explicit(tmp_path: Path) -> None:
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "generated")
    storage.write(storage_key="answer.pdf", content=b"content")

    assert storage.read(storage_key="answer.pdf") == b"content"
    with pytest.raises(FileNotFoundError):
        storage.read(storage_key="missing.pdf")


def test_root_is_resolved_before_path_validation(tmp_path: Path) -> None:
    root = tmp_path / "generated" / ".." / "generated"
    storage = LocalGeneratedDocumentStorage(root=root)

    storage.write(storage_key="answer.pdf", content=b"content")

    assert (tmp_path / "generated" / "answer.pdf").exists()
    assert os.path.realpath(root) == str(tmp_path / "generated")
