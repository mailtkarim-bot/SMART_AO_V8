from unittest.mock import MagicMock

import app.platform.security.public_http as public_http
import pytest


@pytest.mark.security
def test_public_https_rejects_credentials_and_fragments() -> None:
    with pytest.raises(ValueError, match="without credentials"):
        public_http.validate_public_https_destination(
            "https://user" + ":" + "pass@example.test/hook"
        )
    with pytest.raises(ValueError, match="without credentials"):
        public_http.validate_public_https_destination("https://example.test/hook#fragment")


@pytest.mark.security
def test_public_https_rejects_private_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        public_http.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 443))],
    )

    with pytest.raises(ValueError, match="not public"):
        public_http.validate_public_https_destination("https://example.test/hook")


@pytest.mark.security
def test_public_https_opener_does_not_follow_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock(status=204)
    context = MagicMock()
    context.__enter__.return_value = response
    opener = MagicMock()
    opener.open.return_value = context
    monkeypatch.setattr(public_http, "_NO_REDIRECT_OPENER", opener)
    monkeypatch.setattr(
        public_http.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    request = public_http.Request("https://example.test/hook", method="POST")
    result = public_http.open_public_https(request, timeout=2.0)

    assert result is context
    opener.open.assert_called_once_with(request, timeout=2.0)
