from tests.support.database import REPOSITORY_ROOT

DOCKERFILE = REPOSITORY_ROOT / "ops" / "docker" / "backend.Dockerfile"


def test_backend_image_is_digest_pinned_and_runs_non_root() -> None:
    content = DOCKERFILE.read_text(encoding="utf-8")

    assert content.startswith("FROM python:3.12-slim@sha256:")
    assert "USER smartao" in content
    assert "groupadd --system --gid 10001 smartao" in content
    assert "useradd --system --uid 10001 --gid 10001" in content
    assert (
        "install --directory --owner=smartao --group=smartao --mode=0700 "
        "/var/lib/smart_ao/dce-quarantine"
    ) in content
    assert "SMART_AO_DCE_QUARANTINE_ROOT=" in content
    assert "/var/lib/smart_ao/dce-quarantine" in content
