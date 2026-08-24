"""One-shot DCE RC analysis job using persisted completed fragments."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap.application import AppRuntime
from app.modules.dce.application.analysis import DceRcAnalysisService


async def run_once(
    *,
    session_factory: sessionmaker[Session],
    runtime: AppRuntime,
    tenant_id: UUID,
    dce_version_id: UUID,
    now: datetime | None = None,
) -> dict[str, object]:
    """Analyze one DCE and return only a safe command receipt projection."""
    service = DceRcAnalysisService(
        session_factory=session_factory,
        dispatcher=runtime.dispatcher,
    )
    result = service.analyze(
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
        now=now,
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
        receipt = asyncio.run(
            run_once(
                session_factory=session_factory,
                runtime=runtime,
                tenant_id=args.tenant_id,
                dce_version_id=args.dce_version_id,
            )
        )
        print(
            json.dumps(
                {
                    **receipt,
                    "tenant_id": str(args.tenant_id),
                    "dce_version_id": str(args.dce_version_id),
                },
                sort_keys=True,
            )
        )
    finally:
        engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--dce-version-id", type=UUID, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main()


__all__ = ["run_once"]
