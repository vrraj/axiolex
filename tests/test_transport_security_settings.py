"""Startup validation for inbound transport and authentication settings."""

import base64

import pytest

from axiolex import cli
from axiolex.core.config import (
    Config,
    ServerConfig,
    load_config,
    uvicorn_tls_kwargs,
    validate_server_security,
)
from axiolex.mcp import server as mcp_server


def _token() -> str:
    return base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")


def test_default_startup_configuration_is_loopback_http_without_auth(monkeypatch):
    for key in (
        "AXIOLEX_HOST",
        "AXIOLEX_PORT",
        "AXIOLEX_PROTOCOL",
        "AXIOLEX_AUTH_MODE",
        "AXIOLEX_API_BEARER_TOKEN",
        "AXIOLEX_EXTERNAL_AUTH_GATEWAY",
        "BM25S_HOST",
        "BM25S_PORT",
    ):
        monkeypatch.delenv(key, raising=False)

    server = load_config().server

    assert (server.host, server.port, server.protocol, server.auth_mode) == (
        "127.0.0.1",
        9700,
        "http",
        "off",
    )


@pytest.mark.parametrize(
    "server, message",
    [
        (ServerConfig(protocol="ftp"), "AXIOLEX_PROTOCOL"),
        (ServerConfig(port=0), "AXIOLEX_PORT"),
        (ServerConfig(host="0.0.0.0", auth_mode="off"), "loopback"),
        (ServerConfig(auth_mode="static"), "AXIOLEX_API_BEARER_TOKEN"),
        (ServerConfig(auth_mode="external"), "AXIOLEX_EXTERNAL_AUTH_GATEWAY"),
        (ServerConfig(protocol="https"), "AXIOLEX_SSL_CERTFILE"),
        (
            ServerConfig(
                protocol="https",
                ssl_certfile="/definitely/missing/cert.pem",
                ssl_keyfile="/definitely/missing/key.pem",
            ),
            "could not load",
        ),
    ],
)
def test_invalid_inbound_startup_configuration_fails_closed(server, message):
    with pytest.raises(ValueError, match=message):
        validate_server_security(server)


def test_static_and_external_modes_accept_their_required_configuration():
    static = ServerConfig(host="0.0.0.0", auth_mode="static", api_bearer_token=_token())
    external = ServerConfig(
        host="0.0.0.0",
        auth_mode="external",
        external_auth_gateway="internal-api-gateway",
    )

    validate_server_security(static)
    validate_server_security(external)


def test_tls_kwargs_are_only_present_for_https():
    assert uvicorn_tls_kwargs(ServerConfig()) == {}
    assert uvicorn_tls_kwargs(
        ServerConfig(
            protocol="https",
            ssl_certfile="/certs/localhost.pem",
            ssl_keyfile="/certs/localhost-key.pem",
        )
    ) == {
        "ssl_certfile": "/certs/localhost.pem",
        "ssl_keyfile": "/certs/localhost-key.pem",
    }


def test_cli_passes_validated_tls_kwargs_to_uvicorn(monkeypatch):
    calls = []
    config = Config()
    config.server.protocol = "https"
    monkeypatch.setattr(cli, "load_config", lambda _: config)
    monkeypatch.setattr(cli, "validate_server_security", lambda _: None)
    monkeypatch.setattr(
        cli,
        "uvicorn_tls_kwargs",
        lambda _: {"ssl_certfile": "cert.pem", "ssl_keyfile": "key.pem"},
    )
    monkeypatch.setattr(cli.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr("sys.argv", ["axiolex-server"])

    cli.main()

    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 9700,
            "reload": False,
            "log_level": "info",
            "ssl_certfile": "cert.pem",
            "ssl_keyfile": "key.pem",
        }
    ]


@pytest.mark.parametrize("transport", ["streamable-http", "sse"])
def test_standalone_mcp_http_launches_through_validated_uvicorn(monkeypatch, transport):
    calls = []

    class FakeServer:
        def streamable_http_app(self):
            return object()

        def sse_app(self):
            return object()

    config = Config()
    config.server.protocol = "https"
    monkeypatch.setattr(mcp_server, "load_config", lambda: config)
    monkeypatch.setattr(mcp_server, "validate_server_security", lambda _: None)
    monkeypatch.setattr(
        mcp_server,
        "uvicorn_tls_kwargs",
        lambda _: {"ssl_certfile": "cert.pem", "ssl_keyfile": "key.pem"},
    )
    monkeypatch.setattr(mcp_server, "create_mcp_server", lambda **_: FakeServer())
    monkeypatch.setattr(
        mcp_server.uvicorn,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["axiolex-mcp-server", "--transport", transport],
    )

    mcp_server.main()

    assert calls[0][1] == {
        "host": "127.0.0.1",
        "port": 9701,
        "ssl_certfile": "cert.pem",
        "ssl_keyfile": "key.pem",
    }
