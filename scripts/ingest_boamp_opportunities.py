#!/usr/bin/env python3
"""Run a bounded, read-only BOAMP opportunity ingestion.

The script emits a staging report only. It never persists an opportunity, creates a
Case, assigns a score, or sends DCE content to an external service.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.modules.market_watch.infrastructure.boamp import (  # noqa: E402
    BOAMP_RECORDS_URL,
    BoampReadOnlySearch,
    BoampRegistryUnavailable,
)
from app.modules.opportunity.application.boamp_ingestion import (  # noqa: E402
    BoampOpportunityIngestionService,
    OpportunityIngestionLimitError,
)
from app.modules.opportunity.domain.watch_profile import WatchProfileCriteria  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest a bounded public BOAMP search into a JSON staging report."
    )
    parser.add_argument(
        "--keyword",
        action="append",
        required=True,
        help="Allowlisted watch-profile keyword; repeat for additional keywords.",
    )
    parser.add_argument(
        "--included-department",
        action="append",
        default=[],
        help="Optional French department code to include; repeatable.",
    )
    parser.add_argument(
        "--excluded-department",
        action="append",
        default=[],
        help="Optional French department code to exclude; repeatable.",
    )
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--max-pages-per-keyword", type=int, default=5)
    parser.add_argument("--max-results", type=int, default=200)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--base-url", default=BOAMP_RECORDS_URL)
    parser.add_argument(
        "--now",
        help="UTC ISO-8601 instant for reproducible expiry filtering; defaults to current UTC.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the JSON report to this path instead of stdout.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        now = _parse_now(args.now)
        criteria = WatchProfileCriteria(
            keywords=tuple(args.keyword),
            included_departments=tuple(args.included_department),
            excluded_departments=tuple(args.excluded_department),
        )
        search = BoampReadOnlySearch(
            base_url=args.base_url,
            timeout_seconds=args.timeout_seconds,
        )
        report = BoampOpportunityIngestionService(
            search_port=search,
            page_size=args.page_size,
            max_pages_per_keyword=args.max_pages_per_keyword,
            max_results=args.max_results,
        ).ingest(criteria=criteria, now=now)
    except (BoampRegistryUnavailable, OpportunityIngestionLimitError, ValueError) as error:
        print(f"BOAMP ingestion refused: {error}", file=sys.stderr)
        return 2
    payload = {
        "schema": "SMART_AO_OPPORTUNITY_INGESTION_REPORT_V1",
        "source": "BOAMP",
        "generated_at": now.isoformat(),
        "searched_keywords": list(report.searched_keywords),
        "pages_read": report.pages_read,
        "truncated": report.truncated,
        "candidates": [
            {**candidate.snapshot(), "fingerprint_sha256": candidate.fingerprint()}
            for candidate in report.candidates
        ],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(serialized)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    return 0


def _parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--now must include a timezone")
    return parsed.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
