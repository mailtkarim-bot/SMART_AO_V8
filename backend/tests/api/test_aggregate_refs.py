import pytest
from app.interfaces.http.aggregate_refs import require_aggregate_revision


@pytest.mark.api
def test_require_aggregate_revision_accepts_non_negative_integer() -> None:
    assert require_aggregate_revision(0) == 0
    assert require_aggregate_revision(3) == 3


@pytest.mark.api
@pytest.mark.parametrize("value", [-1, True, False, "3", 3.0, None])
def test_require_aggregate_revision_rejects_malformed_values(value: object) -> None:
    with pytest.raises(ValueError, match="INVALID_AGGREGATE_REVISION"):
        require_aggregate_revision(value)
