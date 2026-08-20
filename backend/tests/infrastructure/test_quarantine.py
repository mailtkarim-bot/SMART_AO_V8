import asyncio
from collections.abc import AsyncIterable
from pathlib import Path

import pytest
from app.modules.dce.application.upload import DceUploadRejectedError
from app.modules.dce.infrastructure import quarantine
from app.modules.dce.infrastructure.quarantine import (
    ClamdTcpMalwareScanAdapter,
    LocalQuarantineStorageAdapter,
    PythonMagicContentInspectionAdapter,
)


async def _stream(*chunks: bytes) -> AsyncIterable[bytes]:
    for chunk in chunks:
        yield chunk


def _write(storage: LocalQuarantineStorageAdapter, key: str, *chunks: bytes, max_bytes=100):
    return asyncio.run(storage.write(storage_key=key, stream=_stream(*chunks), max_bytes=max_bytes))


def test_local_quarantine_round_trip_delete_and_path(tmp_path: Path):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)

    result = _write(storage, "tenant/object.bin", b"a", b"", b"bc")
    path = asyncio.run(storage.local_path(storage_key="tenant/object.bin"))

    assert result.byte_size == 3
    assert len(result.sha256) == 64
    assert path.read_bytes() == b"abc"
    assert oct(path.parent.stat().st_mode & 0o777) == "0o700"
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert asyncio.run(storage.read_bytes(storage_key="tenant/object.bin", max_bytes=3)) == b"abc"
    asyncio.run(storage.delete(storage_key="tenant/object.bin"))
    asyncio.run(storage.delete(storage_key="tenant/object.bin"))
    assert not path.exists()


@pytest.mark.parametrize(
    "key", ["/absolute", "../escape", "tenant/../escape"]
)
def test_local_quarantine_rejects_path_traversal_and_empty_segments(tmp_path: Path, key: str):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)

    with pytest.raises(ValueError, match="invalid private storage key"):
        asyncio.run(storage.local_path(storage_key=key))


def test_local_quarantine_rejects_non_bytes_and_removes_partial_file(tmp_path: Path):
    async def invalid_stream():
        yield b"valid"
        yield "invalid"  # type: ignore[misc]

    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    with pytest.raises(TypeError, match="must yield bytes"):
        asyncio.run(
            storage.write(storage_key="tenant/object", stream=invalid_stream(), max_bytes=100)
        )
    assert not list(tmp_path.rglob("*.part"))
    assert not (tmp_path / "tenant/object").exists()


def test_local_quarantine_enforces_limit_and_cleans_partial_file(tmp_path: Path):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)

    with pytest.raises(DceUploadRejectedError) as error:
        _write(storage, "tenant/object", b"123", b"456", max_bytes=5)

    assert error.value.status_code == 413
    assert not list(tmp_path.rglob("*.part"))
    assert not (tmp_path / "tenant/object").exists()


def test_local_quarantine_refuses_collision_without_overwrite(tmp_path: Path):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    _write(storage, "tenant/object", b"first")

    with pytest.raises(FileExistsError, match="already exists"):
        _write(storage, "tenant/object", b"second")
    assert (tmp_path / "tenant/object").read_bytes() == b"first"


def test_local_quarantine_read_enforces_extraction_limit(tmp_path: Path):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    _write(storage, "tenant/object", b"12345")

    with pytest.raises(ValueError, match="extraction limit"):
        asyncio.run(storage.read_bytes(storage_key="tenant/object", max_bytes=4))


def test_python_magic_adapter_delegates_to_libmagic(tmp_path: Path, monkeypatch):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    _write(storage, "tenant/object", b"content")
    observed = {}

    def fake_from_file(path: str, *, mime: bool):
        observed["path"] = path
        observed["mime"] = mime
        return "Application/PDF"

    monkeypatch.setattr(quarantine.magic, "from_file", fake_from_file)
    detected = asyncio.run(
        PythonMagicContentInspectionAdapter(storage=storage).detect_media_type(
            storage_key="tenant/object"
        )
    )

    assert detected == "application/pdf"
    assert observed["path"].endswith("tenant/object")
    assert observed["mime"] is True


class _Reader:
    def __init__(self, response: bytes):
        self.response = response

    async def readuntil(self, separator: bytes) -> bytes:
        return self.response


class _Writer:
    def __init__(self):
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


def test_clamd_scan_streams_file_and_returns_clean(tmp_path: Path, monkeypatch):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    _write(storage, "tenant/object", b"abc")
    version_writer = _Writer()
    scan_writer = _Writer()
    connections = iter([(_Reader(b"ClamAV 1.2\x00"), version_writer),
                        (_Reader(b"stream: OK\x00"), scan_writer)])

    async def fake_open_connection(host, port):
        assert (host, port) == ("clamd", 3310)
        return next(connections)

    monkeypatch.setattr(quarantine.asyncio, "open_connection", fake_open_connection)
    adapter = ClamdTcpMalwareScanAdapter(
        storage=storage, host="clamd", port=3310, timeout_seconds=1, chunk_size=2
    )

    result = asyncio.run(adapter.scan(storage_key="tenant/object"))

    assert result.verdict == "CLEAN"
    assert result.scanner_signature_version == "ClamAV 1.2"
    assert scan_writer.writes[0] == b"zINSTREAM\x00"
    assert scan_writer.writes[-1] == b"\x00\x00\x00\x00"
    assert scan_writer.closed is True


@pytest.mark.parametrize(
    ("response", "verdict"),
    [(b"stream: Eicar-Test-Signature FOUND\x00", "INFECTED"),
     (b"unexpected response\x00", "ERROR")],
)
def test_clamd_scan_maps_infected_and_unknown_verdicts(
    tmp_path: Path, monkeypatch, response, verdict
):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    _write(storage, "tenant/object", b"abc")
    connections = iter([(_Reader(b"version\x00"), _Writer()), (_Reader(response), _Writer())])

    async def fake_open_connection(host, port):
        return next(connections)

    monkeypatch.setattr(quarantine.asyncio, "open_connection", fake_open_connection)
    adapter = ClamdTcpMalwareScanAdapter(
        storage=storage, host="clamd", port=3310, timeout_seconds=1
    )

    result = asyncio.run(adapter.scan(storage_key="tenant/object"))

    assert result.verdict == verdict


def test_clamd_scan_fails_closed_on_connection_error(tmp_path: Path, monkeypatch):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)

    async def failing_open_connection(host, port):
        raise OSError("clamd unavailable")

    monkeypatch.setattr(quarantine.asyncio, "open_connection", failing_open_connection)
    adapter = ClamdTcpMalwareScanAdapter(
        storage=storage, host="clamd", port=3310, timeout_seconds=1
    )

    result = asyncio.run(adapter.scan(storage_key="tenant/object"))

    assert result.verdict == "ERROR"
    assert result.scanner_name == "clamd"
    assert result.scanner_signature_version == "unavailable"


def test_clamd_version_decodes_and_truncates_response(tmp_path: Path, monkeypatch):
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    writer = _Writer()
    long_version = b"v" * 300 + b"\x00"

    async def fake_open_connection(host, port):
        return _Reader(long_version), writer

    monkeypatch.setattr(quarantine.asyncio, "open_connection", fake_open_connection)
    adapter = ClamdTcpMalwareScanAdapter(
        storage=storage, host="clamd", port=3310, timeout_seconds=1
    )

    version = asyncio.run(adapter._version())

    assert len(version) == 240
    assert writer.writes == [b"zVERSION\x00"]
    assert writer.closed is True
