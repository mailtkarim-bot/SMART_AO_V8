"""One-shot DCE extraction job using the configured optional parser."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap.application import AppRuntime
from app.modules.dce.infrastructure.extraction_factory import (
    build_dce_document_extraction_service,
)
from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter


async def run_once(
    *,
    session_factory: sessionmaker[Session],
    runtime: AppRuntime,
    storage: LocalQuarantineStorageAdapter,
    tenant_id: UUID,
    dce_document_id: UUID,
) -> dict[str, object]:
    """Extract one document and return only a safe command receipt projection."""
    service = build_dce_document_extraction_service(
        session_factory=session_factory,
        dispatcher=runtime.dispatcher,
        storage=storage,
    )
    result = await service.extract(
        tenant_id=tenant_id,
        dce_document_id=dce_document_id,
    )
    return {
        "status": result.status,
        "result_code": result.result_code,
        "command_id": result.command_id,
        "idempotency_key": result.idempotency_key,
        "event_count": len(result.event_ids),
    }


def main() -> None:
    args = _parse_args()
    database_url = os.environ["SMART_AO_DATABASE_URL"]
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    session_factory: sessionmaker[Session] = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    try:
        runtime = AppRuntime.create(session_factory=session_factory)
        storage = LocalQuarantineStorageAdapter(
            root=Path(
                os.getenv(
                    "SMART_AO_DCE_QUARANTINE_ROOT",
                    "/var/lib/smart_ao/dce-quarantine",
                )
            )
        )
        receipt = asyncio.run(
            run_once(
                session_factory=session_factory,
                runtime=runtime,
                storage=storage,
                tenant_id=args.tenant_id,
                dce_document_id=args.dce_document_id,
            )
        )
        print(
            json.dumps(
                {
                    **receipt,
                    "tenant_id": str(args.tenant_id),
                    "dce_document_id": str(args.dce_document_id),
                },
                sort_keys=True,
            )
        )
    finally:
        engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--dce-document-id", type=UUID, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()
