"""Verify that a local BGE model cache is usable without downloading anything."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.modules.knowledge.infrastructure.bge_embeddings import BgeEmbeddingProvider


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="BAAI/bge-m3")
    parser.add_argument("--cache-dir", type=Path, default=Path("/var/lib/smart_ao/models"))
    args = parser.parse_args()
    provider = BgeEmbeddingProvider(
        model_id=args.model_id,
        cache_dir=args.cache_dir,
        local_files_only=True,
    )
    try:
        [vector] = provider.embed(["test de cache local"])
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "model_cache_not_ready",
                    "model_id": args.model_id,
                    "cache_dir": str(args.cache_dir),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": "ok",
                "model_id": args.model_id,
                "cache_dir": str(args.cache_dir),
                "dimension": len(vector),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
