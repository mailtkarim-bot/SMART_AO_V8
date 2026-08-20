from __future__ import annotations

import hashlib
import json
import tempfile
import time
import zipfile
from pathlib import Path

CORPUS_ROOT = Path(__file__).parents[1] / "artifacts" / "btp-corpus"


def assemble(
    files: list[Path], compression: int, compresslevel: int | None
) -> tuple[int, str, float]:
    started = time.perf_counter()
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as archive:
        options = {"compression": compression}
        if compresslevel is not None:
            options["compresslevel"] = compresslevel
        with zipfile.ZipFile(archive, "w", **options) as bundle:
            manifest = {
                "schema_version": 2,
                "entries": [
                    {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                    for path in files
                ],
            }
            info = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = compression
            info.external_attr = 0o600 << 16
            bundle.writestr(info, json.dumps(manifest, sort_keys=True).encode())
            for path in files:
                info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = compression
                info.external_attr = 0o600 << 16
                bundle.writestr(info, path.read_bytes())
        archive.seek(0)
        result = archive.read()
    return len(result), hashlib.sha256(result).hexdigest(), time.perf_counter() - started


def main() -> None:
    files = sorted(CORPUS_ROOT.glob("*.pdf"))
    if not files:
        raise SystemExit(f"no PDF corpus found under {CORPUS_ROOT}")
    input_bytes = sum(path.stat().st_size for path in files)
    print(f"corpus_files={len(files)} corpus_input_bytes={input_bytes}")
    for label, compression, level in (
        ("stored", zipfile.ZIP_STORED, None),
        ("deflated-6", zipfile.ZIP_DEFLATED, 6),
        ("deflated-9", zipfile.ZIP_DEFLATED, 9),
    ):
        archive_bytes, digest, elapsed = assemble(files, compression, level)
        ratio = archive_bytes / input_bytes
        print(
            f"profile={label} archive_bytes={archive_bytes} ratio={ratio:.6f} "
            f"reduction_percent={(1 - ratio) * 100:.2f} elapsed_seconds={elapsed:.6f} "
            f"archive_sha256={digest}"
        )


if __name__ == "__main__":
    main()
