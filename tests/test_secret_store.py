import os

import pytest

from axiolex.mcp.secret_store import SecretStore, SecretStoreError


_TEST_KEY = "a" * 64  # 32 bytes hex


def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", _TEST_KEY)
    store = SecretStore(file_path=str(tmp_path / "secrets.enc"))

    store.set_secret("tavily", "tvly-abc123")
    assert store.has_secret("tavily")
    assert store.get_secret("tavily") == "tvly-abc123"


def test_get_secret_returns_none_for_missing_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", _TEST_KEY)
    store = SecretStore(file_path=str(tmp_path / "secrets.enc"))

    assert store.get_secret("nonexistent") is None
    assert store.has_secret("nonexistent") is False


def test_delete_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", _TEST_KEY)
    store = SecretStore(file_path=str(tmp_path / "secrets.enc"))

    store.set_secret("tavily", "tvly-abc123")
    assert store.delete_secret("tavily") is True
    assert store.has_secret("tavily") is False
    assert store.delete_secret("tavily") is False  # already gone


def test_overwrite_existing_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", _TEST_KEY)
    store = SecretStore(file_path=str(tmp_path / "secrets.enc"))

    store.set_secret("tavily", "old-key")
    store.set_secret("tavily", "new-key")
    assert store.get_secret("tavily") == "new-key"


def test_missing_master_key_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("AXIOLEX_SECRET_MASTER_KEY", raising=False)
    store = SecretStore(file_path=str(tmp_path / "secrets.enc"))

    with pytest.raises(SecretStoreError, match="AXIOLEX_SECRET_MASTER_KEY"):
        store.set_secret("tavily", "key")


def test_wrong_master_key_raises_on_decrypt(tmp_path, monkeypatch):
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", _TEST_KEY)
    store = SecretStore(file_path=str(tmp_path / "secrets.enc"))
    store.set_secret("tavily", "tvly-abc123")

    # Now swap to a different key
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", "b" * 64)
    with pytest.raises(SecretStoreError, match="decrypt"):
        store.get_secret("tavily")


def test_tampered_ciphertext_raises(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", _TEST_KEY)
    path = tmp_path / "secrets.enc"
    store = SecretStore(file_path=str(path))
    store.set_secret("tavily", "tvly-abc123")

    # Corrupt the ciphertext by flipping characters in the base64 blob.
    data = json.loads(path.read_text())
    original = data["tavily"]["ciphertext"]
    data["tavily"]["ciphertext"] = original[:-4] + "AAAA"
    path.write_text(json.dumps(data))

    with pytest.raises(SecretStoreError):
        store.get_secret("tavily")


def test_empty_secret_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", _TEST_KEY)
    store = SecretStore(file_path=str(tmp_path / "secrets.enc"))

    with pytest.raises(ValueError):
        store.set_secret("tavily", "")


def test_file_permissions_restricted(tmp_path, monkeypatch):
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", _TEST_KEY)
    path = tmp_path / "secrets.enc"
    store = SecretStore(file_path=str(path))
    store.set_secret("tavily", "tvly-abc123")

    mode = os.stat(path).st_mode & 0o777
    assert mode == 0o600


def test_multiple_providers_independent(tmp_path, monkeypatch):
    monkeypatch.setenv("AXIOLEX_SECRET_MASTER_KEY", _TEST_KEY)
    store = SecretStore(file_path=str(tmp_path / "secrets.enc"))

    store.set_secret("tavily", "tvly-key")
    store.set_secret("alphavantage", "av-key")

    assert store.get_secret("tavily") == "tvly-key"
    assert store.get_secret("alphavantage") == "av-key"
    assert store.has_secret("tavily")
    assert store.has_secret("alphavantage")
