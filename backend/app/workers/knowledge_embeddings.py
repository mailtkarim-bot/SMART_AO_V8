"""One-shot local BGE indexing job for a case DCE version."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.knowledge.infrastructure.factory import build_local_knowledge_service


def main() -> None:
    args = _parse_args()
    database_url = os.environ["SMART_AO_DATABASE_URL"]
    model_id = os.getenv("SMART_AO_BGE_MODEL_ID", "BAAI/bge-m3")
    cache_dir = Path(os.getenv("SMART_AO_BGE_CACHE_DIR", "/var/lib/smart_ao/models"))
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    session_factory: sessionmaker[Session] = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    service = build_local_knowledge_service(
        session_factory=session_factory,
        model_id=model_id,
        cache_dir=cache_dir,
        local_files_only=os.getenv("SMART_AO_BGE_LOCAL_FILES_ONLY", "1") == "1",
    )
    indexed_count = service.index_case_dce(
        tenant_id=args.tenant_id,
        case_id=args.case_id,
        dce_version_id=args.dce_version_id,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "indexed_count": indexed_count,
                "tenant_id": str(args.tenant_id),
                "case_id": str(args.case_id),
                "dce_version_id": str(args.dce_version_id),
                "model_id": model_id,
            },
            sort_keys=True,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--case-id", type=UUID, required=True)
    parser.add_argument("--dce-version-id", type=UUID, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
