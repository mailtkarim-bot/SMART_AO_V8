"""Explicit operator smoke test for a private S3-compatible bucket."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from uuid import uuid4

from app.platform.storage.object_storage import S3PrivateObjectStorage


VERIFY_CONTENT = b"SMART_AO_OBJECT_STORAGE_VERIFY_V1\n"


def main() -> None:
    args = _parse_args()
    if not args.confirm_write:
        raise SystemExit("refusing object-storage write without --confirm-write")
    bucket = os.getenv("SMART_AO_OBJECT_STORAGE_BUCKET", "").strip()
    if not bucket:
        raise SystemExit("SMART_AO_OBJECT_STORAGE_BUCKET is required")
    storage = S3PrivateObjectStorage(
        bucket=bucket,
        endpoint_url=os.getenv("SMART_AO_OBJECT_STORAGE_ENDPOINT_URL") or None,
        region_name=os.getenv("SMART_AO_OBJECT_STORAGE_REGION") or None,
        server_side_encryption=os.getenv("SMART_AO_OBJECT_STORAGE_SSE", "AES256") or None,
    )
    key = f"operator-verification/{uuid4().hex}.bin"
    expected_sha256 = hashlib.sha256(VERIFY_CONTENT).hexdigest()
    try:
        digest = storage.write(storage_key=key, content=VERIFY_CONTENT)
        head = storage.head(storage_key=key)
        content = storage.read(storage_key=key)
        if digest != expected_sha256 or content != VERIFY_CONTENT:
            raise RuntimeError("object-storage verification failed integrity checks")
        if head.get("content_length") != len(VERIFY_CONTENT) or head.get("sha256") != digest:
            raise RuntimeError("object-storage verification failed metadata checks")
    finally:
        asyncio.run(storage.delete(storage_key=key))
    print(
        json.dumps(
            {
                "status": "ok",
                "content_length": len(VERIFY_CONTENT),
                "sha256": expected_sha256,
                "deleted": True,
            },
            sort_keys=True,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-write",
        action="store_true",
        help="explicitly authorize writing and deleting a temporary verification object",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
