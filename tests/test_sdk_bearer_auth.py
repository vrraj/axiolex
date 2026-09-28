from unittest.mock import MagicMock, patch

from axiolex.sdk import Axiolex


def test_sdk_uses_explicit_bearer_token_without_changing_constructor_compatibility():
    with patch("axiolex.sdk.httpx.Client") as client_class:
        Axiolex("http://example.test", bearer_token="secret").client
    assert client_class.call_args.kwargs["headers"] == {"Authorization": "Bearer secret"}


def test_sdk_reads_bearer_token_from_environment(monkeypatch):
    monkeypatch.setenv("AXIOLEX_BEARER_TOKEN", "environment-secret")
    with patch("axiolex.sdk.httpx.Client") as client_class:
        Axiolex().client
    assert client_class.call_args.kwargs["headers"] == {"Authorization": "Bearer environment-secret"}


def test_sdk_keeps_legacy_constructor_behavior_without_a_token(monkeypatch):
    monkeypatch.delenv("AXIOLEX_BEARER_TOKEN", raising=False)
    with patch("axiolex.sdk.httpx.Client") as client_class:
        Axiolex().client
    assert client_class.call_args.kwargs["headers"] == {}
