import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet


class CredentialsStore:
    def __init__(self, file_path: str = "credentials.json"):
        self.file_path = Path(file_path)
        self.master_key = os.getenv("CREDENTIALS_MASTER_KEY")
        if not self.master_key:
            raise ValueError("CREDENTIALS_MASTER_KEY not set")
        self.fernet = Fernet(self._normalize_key(self.master_key))
        self.data = self._load()

    def _normalize_key(self, key: str) -> bytes:
        key_bytes = key.encode("utf-8")
        if len(key_bytes) == 44 and key_bytes.endswith(b"="):
            return key_bytes
        return base64.urlsafe_b64encode(key_bytes.ljust(32, b"0")[:32])

    def _load(self) -> dict:
        if self.file_path.exists():
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def set_user_creds(
        self, user_id: str, school_id: str, username: str, password: str
    ):
        payload = json.dumps(
            {
                "school_id": school_id,
                "username": username,
                "password": password,
            }
        )
        token = self.fernet.encrypt(payload.encode("utf-8")).decode("utf-8")
        self.data[user_id] = token
        self._save()

    def get_user_creds(self, user_id: str) -> dict | None:
        token = self.data.get(user_id)
        if not token:
            return None
        try:
            payload = self.fernet.decrypt(token.encode("utf-8")).decode("utf-8")
            return json.loads(payload)
        except Exception:
            return None

    def remove_user_creds(self, user_id: str):
        if user_id in self.data:
            del self.data[user_id]
            self._save()

    def has_user(self, user_id: str) -> bool:
        return user_id in self.data
