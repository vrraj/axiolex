"""Encrypted at-rest secret store for MCP provider credentials.

Secrets are encrypted with AES-256-GCM using a master key read from the
``AXIOLEX_SECRET_MASTER_KEY`` environment variable (a 32-byte hex string,
generatable via ``openssl rand -hex 32``).  The encrypted file lives at
``source_files/mcp_secrets.enc`` by default and contains a JSON mapping of
provider IDs to ``{nonce, ciphertext}`` pairs.

This store is an *opt-in* alternative to putting each provider key in ``.env``.
``resolve_secret`` always checks the OS environment first, then falls back to
this store, so both paths coexist without migration.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Dict, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_MASTER_KEY_ENV = "AXIOLEX_SECRET_MASTER_KEY"
_DEFAULT_STORE_PATH = "source_files/mcp_secrets.enc"


class SecretStoreError(Exception):
    """Raised when the secret store cannot be used safely."""


def _master_key() -> bytes:
    """Return the 32-byte master key from the environment."""
    hex_key = os.getenv(_MASTER_KEY_ENV)
    if not hex_key:
        raise SecretStoreError(
            f"{_MASTER_KEY_ENV} is not set. Generate one with "
            f"'openssl rand -hex 32' and add it to your .env file."
        )
    try:
        return bytes.fromhex(hex_key)
    except ValueError as exc:
        raise SecretStoreError(
            f"{_MASTER_KEY_ENV} must be a hex string (64 hex chars)."
        ) from exc


class SecretStore:
    """Encrypt, persist, and retrieve per-provider secrets at rest."""

    def __init__(self, file_path: str = _DEFAULT_STORE_PATH):
        self.file_path = file_path

    # -- internal helpers -------------------------------------------------

    def _load_raw(self) -> Dict[str, Dict[str, str]]:
        """Load and parse the encrypted store file."""
        if not os.path.exists(self.file_path):
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise SecretStoreError(
                f"Could not read secret store at {self.file_path}: {exc}"
            ) from exc

    def _save_raw(self, data: Dict[str, Dict[str, str]]) -> None:
        """Write the encrypted store file."""
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # Restrict permissions to owner only.
        os.chmod(self.file_path, 0o600)

    # -- public API -------------------------------------------------------

    def get_secret(self, provider_id: str) -> Optional[str]:
        """Decrypt and return the secret for ``provider_id``, or ``None``."""
        data = self._load_raw()
        entry = data.get(provider_id)
        if not entry:
            return None
        try:
            key = _master_key()
            nonce = base64.b64decode(entry["nonce"])
            ciphertext = base64.b64decode(entry["ciphertext"])
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
            return plaintext.decode("utf-8")
        except SecretStoreError:
            raise
        except Exception as exc:
            raise SecretStoreError(
                f"Failed to decrypt secret for provider '{provider_id}'. "
                f"The master key may be wrong or the store may be corrupted."
            ) from exc

    def set_secret(self, provider_id: str, value: str) -> None:
        """Encrypt and store ``value`` for ``provider_id``."""
        if not value:
            raise ValueError("Secret value must not be empty.")
        key = _master_key()
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, value.encode("utf-8"), None)
        data = self._load_raw()
        data[provider_id] = {
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        self._save_raw(data)

    def delete_secret(self, provider_id: str) -> bool:
        """Remove the secret for ``provider_id``. Return ``True`` if it existed."""
        data = self._load_raw()
        if provider_id not in data:
            return False
        del data[provider_id]
        self._save_raw(data)
        return True

    def has_secret(self, provider_id: str) -> bool:
        """Return ``True`` if a secret exists for ``provider_id``."""
        return provider_id in self._load_raw()


# Module-level singleton for convenience.
_store: Optional[SecretStore] = None


def get_secret_store() -> SecretStore:
    """Return a process-wide :class:`SecretStore` singleton."""
    global _store
    if _store is None:
        _store = SecretStore()
    return _store
