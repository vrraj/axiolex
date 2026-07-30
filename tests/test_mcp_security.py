import yaml
import pytest

from axiolex.mcp.discovery import MCPDiscovery, MCPProviderAuth, MCPProviderConfig
from axiolex.mcp.security import append_api_key, redact_url, resolve_secret


def test_provider_auth_rejects_inline_secret_values():
    with pytest.raises(ValueError, match="secret_env"):
        MCPProviderAuth(type="api_key", secret_value="not-for-config")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"endpoint": "https://example.test/mcp?apikey=not-for-config"},
        {"headers": {"Authorization": "Bearer not-for-config"}},
    ],
)
def test_provider_config_rejects_inline_credentials(kwargs):
    with pytest.raises(ValueError, match="secret_env"):
        MCPProviderConfig(id="markets", name="Markets", **kwargs)


def test_provider_yaml_never_persists_secret_values(tmp_path):
    discovery = MCPDiscovery(
        providers=[
            MCPProviderConfig(
                id="markets",
                name="Markets",
                endpoint="https://example.test/mcp",
                auth=MCPProviderAuth(type="api_key", secret_env="MARKETS_API_KEY"),
            )
        ],
        config_file=None,
    )
    output = tmp_path / "providers.yaml"

    discovery.save_to_yaml(str(output))

    saved = yaml.safe_load(output.read_text(encoding="utf-8"))
    auth = saved["providers"][0]["auth"]
    assert auth == {"type": "api_key", "secret_env": "MARKETS_API_KEY"}
    assert "secret_value" not in output.read_text(encoding="utf-8")


def test_sensitive_query_values_are_redacted():
    url = append_api_key("https://example.test/mcp?mode=tools", "private-key")

    assert "private-key" not in redact_url(url)
    assert redact_url(url) == "https://example.test/mcp?mode=tools&apikey=REDACTED"


def test_secret_resolution_reads_only_the_named_environment_variable(monkeypatch):
    monkeypatch.setenv("MARKETS_API_KEY", "private-key")

    assert resolve_secret("MARKETS_API_KEY") == "private-key"
    assert resolve_secret(None) is None
