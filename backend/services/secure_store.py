from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet


class SecureStore:
    def __init__(self, key_path: Path | None = None) -> None:
        self.key_path = key_path or Path("backend/.secrets/nexa-credentials.key")
        self._fernet = Fernet(self._load_key())

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")

    def _load_key(self) -> bytes:
        env_key = os.getenv("NEXA_CREDENTIAL_ENCRYPTION_KEY")
        if env_key:
            return env_key.encode("utf-8")
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.exists():
            return self.key_path.read_bytes()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        return key
