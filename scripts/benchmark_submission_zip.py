from __future__ import annotations

import hashlib
import json
import tempfile
import time
import zipfile


def assemble(size_bytes: int) -> tuple[int, str, float]:
    manifest = json.dumps(
        {"schema_version": 2, "entries": [{"kind": "TECHNICAL", "sha256": "a" * 64}]},
        separators=(",", ":"),
    ).encode()
    technical = b"A" * size_bytes
    started = time.perf_counter()
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as archive:
        with zipfile.ZipFile(
            archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as bundle:
            for name, content in (
                ("manifest.json", manifest),
                ("technical-response.md", technical),
            ):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                bundle.writestr(info, content)
        archive.seek(0)
        result = archive.read()
    return len(result), hashlib.sha256(result).hexdigest(), time.perf_counter() - started


def main() -> None:
    for size in (1 * 1024 * 1024, 10 * 1024 * 1024):
        archive_size, digest, elapsed = assemble(size)
        print(
            f"input_bytes={size} archive_bytes={archive_size} elapsed_seconds={elapsed:.6f} "
            f"archive_sha256={digest}"
        )


if __name__ == "__main__":
    main()
