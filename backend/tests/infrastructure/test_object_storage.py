from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from app.platform.storage.object_storage import S3PrivateObjectStorage


class FakeClient:
    def __init__(self, content: bytes = b"stored") -> None:
        self.content = content
        self.put_requests: list[dict[str, object]] = []
        self.deleted: list[dict[str, str]] = []

    def put_object(self, **request):
        self.put_requests.append(request)
        return {"ETag": '"etag"'}

    def get_object(self, **request):
        return {
            "ContentLength": len(self.content),
            "Body": BytesIO(self.content),
        }

    def delete_object(self, **request):
        self.deleted.append(request)


def test_s3_write_is_private_conditional_and_hashes_content() -> None:
    client = FakeClient()
    storage = S3PrivateObjectStorage(bucket="private", client=client)

    digest = storage.write(storage_key="tenant/object.bin", content=b"stored")

    assert digest == "87b04e58961f9a99d853d4046a0b5b793e7c3e4bbd21f5aca8fb17c20cdb1d8b"
    assert client.put_requests[0]["Bucket"] == "private"
    assert client.put_requests[0]["Key"] == "tenant/object.bin"
    assert client.put_requests[0]["IfNoneMatch"] == "*"
    assert client.put_requests[0]["ServerSideEncryption"] == "AES256"
    assert client.put_requests[0]["Metadata"] == {
        "sha256": digest,
    }


def test_s3_read_and_bounded_async_read() -> None:
    client = FakeClient(content=b"stored")
    storage = S3PrivateObjectStorage(bucket="private", client=client)

    assert storage.read(storage_key="tenant/object.bin") == b"stored"
    assert asyncio.run(
        storage.read_bytes(storage_key="tenant/object.bin", max_bytes=6)
    ) == b"stored"

    with pytest.raises(ValueError, match="read limit"):
        asyncio.run(storage.read_bytes(storage_key="tenant/object.bin", max_bytes=5))


def test_s3_rejects_path_traversal_and_bucket_with_path() -> None:
    client = FakeClient()
    with pytest.raises(ValueError):
        S3PrivateObjectStorage(bucket="private/unsafe", client=client)
    storage = S3PrivateObjectStorage(bucket="private", client=client)
    with pytest.raises(ValueError):
        storage.write(storage_key="../escape", content=b"x")


def test_s3_translates_conditional_conflict_to_file_exists() -> None:
    class ConflictClient(FakeClient):
        def put_object(self, **request):
            raise RuntimeError(
                "conflict",
                {
                    "Error": {"Code": "PreconditionFailed"},
                },
            )

    class BotoStyleError(Exception):
        response = {"Error": {"Code": "PreconditionFailed"}}

    class BotoStyleConflictClient(FakeClient):
        def put_object(self, **request):
            raise BotoStyleError("conflict")

    storage = S3PrivateObjectStorage(bucket="private", client=BotoStyleConflictClient())
    with pytest.raises(FileExistsError):
        storage.write(storage_key="tenant/object.bin", content=b"x")

    # A non-Boto exception is deliberately propagated rather than guessed.
    storage = S3PrivateObjectStorage(bucket="private", client=ConflictClient())
    with pytest.raises(RuntimeError):
        storage.write(storage_key="tenant/object.bin", content=b"x")
