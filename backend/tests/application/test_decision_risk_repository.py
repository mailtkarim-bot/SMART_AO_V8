from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.infrastructure.risk_repository import SqlAlchemyDecisionRiskRepository


def test_source_supports_requires_exact_utf8_excerpt_at_offsets() -> None:
    text = "Préambule — le titulaire respecte le délai contractuel."
    excerpt = "le titulaire respecte le délai"
    start = text.encode("utf-8").index(excerpt.encode("utf-8"))
    end = start + len(excerpt.encode("utf-8"))
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(text=text)

    assert SqlAlchemyDecisionRiskRepository().source_supports(
        session=session,
        tenant_id=uuid4(),
        dce_version_id=uuid4(),
        source_fragment_id=uuid4(),
        source_excerpt=excerpt,
        start_byte_offset=start,
        end_byte_offset=end,
    ) is True


@pytest.mark.parametrize(
    ("source_excerpt", "start_delta", "end_delta"),
    [
        ("délai contractuel", 0, 0),
        ("le titulaire respecte le délai", 1, 0),
        ("le titulaire respecte le délai", 0, -1),
    ],
)
def test_source_supports_rejects_non_matching_excerpt_or_offsets(
    source_excerpt: str, start_delta: int, end_delta: int
) -> None:
    text = "Préambule — le titulaire respecte le délai contractuel."
    expected = "le titulaire respecte le délai"
    start = text.encode("utf-8").index(expected.encode("utf-8")) + start_delta
    end = start + len(expected.encode("utf-8")) + end_delta
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(text=text)

    assert SqlAlchemyDecisionRiskRepository().source_supports(
        session=session,
        tenant_id=uuid4(),
        dce_version_id=uuid4(),
        source_fragment_id=uuid4(),
        source_excerpt=source_excerpt,
        start_byte_offset=start,
        end_byte_offset=end,
    ) is False


def test_source_supports_rejects_offsets_inside_utf8_character() -> None:
    text = "Risque élevé"
    text_bytes = text.encode("utf-8")
    start = text_bytes.index("é".encode()) + 1
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(text=text)

    assert SqlAlchemyDecisionRiskRepository().source_supports(
        session=session,
        tenant_id=uuid4(),
        dce_version_id=uuid4(),
        source_fragment_id=uuid4(),
        source_excerpt="é",
        start_byte_offset=start,
        end_byte_offset=start + 1,
    ) is False
