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
    assert auth == {"type": "api_key", "secret_env": "MARKETS_API_KEY", "key_param": "api_key"}
    assert "secret_value" not in output.read_text(encoding="utf-8")


def test_sensitive_query_values_are_redacted():
    url = append_api_key("https://example.test/mcp?mode=tools", "private-key")

    assert "private-key" not in redact_url(url)
    assert redact_url(url) == "https://example.test/mcp?mode=tools&api_key=REDACTED"


def test_secret_resolution_reads_only_the_named_environment_variable(monkeypatch):
    monkeypatch.setenv("MARKETS_API_KEY", "private-key")

    assert resolve_secret("MARKETS_API_KEY") == "private-key"
    assert resolve_secret(None) is None


def test_append_api_key_uses_custom_param_name():
    url = append_api_key("https://mcp.tavily.com/mcp/", "tavily-key", param_name="tavilyApiKey")
    assert "tavilyApiKey=tavily-key" in url


def test_append_api_key_defaults_to_api_key_param():
    url = append_api_key("https://example.test/mcp", "my-key")
    assert "api_key=my-key" in url


def test_resolve_secret_falls_back_to_secret_store(monkeypatch, tmp_path):
    from axiolex.mcp import secret_store as ss_mod

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", "a" * 64)
    store = ss_mod.SecretStore(file_path=str(tmp_path / "secrets.enc"))
    store.set_secret("tavily", "stored-key")
    monkeypatch.setattr(ss_mod, "get_secret_store", lambda: store)

    assert resolve_secret("TAVILY_API_KEY", provider_id="tavily") == "stored-key"


def test_resolve_secret_env_takes_precedence_over_store(monkeypatch, tmp_path):
    from axiolex.mcp import secret_store as ss_mod

    monkeypatch.setenv("TAVILY_API_KEY", "env-key")
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", "b" * 64)
    store = ss_mod.SecretStore(file_path=str(tmp_path / "secrets.enc"))
    store.set_secret("tavily", "stored-key")
    monkeypatch.setattr(ss_mod, "get_secret_store", lambda: store)

    assert resolve_secret("TAVILY_API_KEY", provider_id="tavily") == "env-key"


def test_resolve_secret_returns_none_when_neither_source_has_value(monkeypatch, tmp_path):
    from axiolex.mcp import secret_store as ss_mod

    monkeypatch.delenv("MISSING_KEY", raising=False)
    monkeypatch.setattr(ss_mod, "get_secret_store", lambda: ss_mod.SecretStore(file_path=str(tmp_path / "nonexistent.enc")))

    assert resolve_secret("MISSING_KEY", provider_id="no-provider") is None
