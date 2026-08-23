"""Private S3-compatible object storage adapter.

The adapter is compatible with Amazon S3 and MinIO endpoints, but never
returns a bucket, URL, presigned URL or storage key through an HTTP contract.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import PurePosixPath
from typing import Any

from app.platform.storage.ports import GeneratedDocumentStorage


class S3PrivateObjectStorage(GeneratedDocumentStorage):
    """Private object storage for generated documents and DCE reads."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        client: Any | None = None,
        server_side_encryption: str | None = "AES256",
    ) -> None:
        self._bucket = _validate_bucket(bucket)
        self._server_side_encryption = server_side_encryption
        self._client = client or _build_client(
            endpoint_url=endpoint_url,
            region_name=region_name,
        )

    def write(self, *, storage_key: str, content: bytes) -> str:
        key = _validate_key(storage_key)
        digest = hashlib.sha256(content).hexdigest()
        request: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": content,
            "ContentLength": len(content),
            "ContentType": "application/octet-stream",
            "IfNoneMatch": "*",
            "Metadata": {"sha256": digest},
        }
        if self._server_side_encryption:
            request["ServerSideEncryption"] = self._server_side_encryption
        try:
            self._client.put_object(**request)
        except Exception as exc:
            if _error_code(exc) in {"PreconditionFailed", "ConditionalRequestConflict"}:
                raise FileExistsError("private object already exists") from exc
            raise
        return digest

    def head(self, *, storage_key: str) -> dict[str, object]:
        response = self._client.head_object(
            Bucket=self._bucket,
            Key=_validate_key(storage_key),
        )
        metadata = response.get("Metadata", {})
        return {
            "content_length": response.get("ContentLength"),
            "content_type": response.get("ContentType"),
            "sha256": metadata.get("sha256") if isinstance(metadata, dict) else None,
        }

    def read(self, *, storage_key: str) -> bytes:
        response = self._client.get_object(
            Bucket=self._bucket,
            Key=_validate_key(storage_key),
        )
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()

    async def read_bytes(self, *, storage_key: str, max_bytes: int) -> bytes:
        if max_bytes < 0:
            raise ValueError("max_bytes must be non-negative")
        return await asyncio.to_thread(
            self._read_bounded,
            storage_key=storage_key,
            max_bytes=max_bytes,
        )

    async def delete(self, *, storage_key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=_validate_key(storage_key),
        )

    def _read_bounded(self, *, storage_key: str, max_bytes: int) -> bytes:
        response = self._client.get_object(
            Bucket=self._bucket,
            Key=_validate_key(storage_key),
        )
        body = response["Body"]
        try:
            content_length = response.get("ContentLength")
            if isinstance(content_length, int) and content_length > max_bytes:
                raise ValueError("private object exceeds configured read limit")
            content = body.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError("private object exceeds configured read limit")
            return content
        finally:
            body.close()


def _build_client(*, endpoint_url: str | None, region_name: str | None) -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("object-storage extra is not installed") from exc
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region_name,
    )


def _validate_bucket(bucket: str) -> str:
    if not bucket or bucket.strip() != bucket or "/" in bucket:
        raise ValueError("invalid private object bucket")
    return bucket


def _validate_key(storage_key: str) -> str:
    relative = PurePosixPath(storage_key)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("invalid private object key")
    return storage_key


def _error_code(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error")
        if isinstance(error, dict):
            code = error.get("Code")
            if isinstance(code, str):
                return code
    return None
