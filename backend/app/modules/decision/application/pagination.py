from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID


def decode_cursor(value: str) -> tuple[datetime, UUID]:
    try:
        padded = value + "=" * (-len(value) % 4)
        created_at, link_id = base64.urlsafe_b64decode(padded).decode("utf-8").split("|", 1)
        return datetime.fromisoformat(created_at), UUID(link_id)
    except (ValueError, TypeError, UnicodeError) as error:
        raise ValueError("invalid decision risk link cursor") from error
