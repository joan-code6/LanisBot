import os
import json
import base64
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

load_dotenv()


class CredentialStore:
    def __init__(self):
        encryption_key = os.getenv("CREDENTIALS_MASTER_KEY", "")
        if not encryption_key:
            raise ValueError("CREDENTIALS_MASTER_KEY not set in .env")
        
        self.encryption_key = self._derive_key(encryption_key)
        self.fernet = Fernet(self.encryption_key)
        
        self.session_timeout_hours = int(os.getenv("SESSION_TIMEOUT_HOURS", "24"))
        
        self.credentials_file = Path("data/credentials.enc")
        self.sessions_file = Path("data/sessions.json")
        self._ensure_files()

    def _derive_key(self, key: str) -> bytes:
        salt = b"lanis_bot_salt_v1"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key_bytes = hashlib.sha256(key.encode()).digest()
        return base64.urlsafe_b64encode(kdf.derive(key_bytes))

    def _ensure_files(self):
        self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.credentials_file.exists():
            self.credentials_file.write_bytes(self.fernet.encrypt(b"{}"))
        if not self.sessions_file.exists():
            self.sessions_file.write_text("{}")

    def _read_credentials(self) -> Dict[str, Any]:
        try:
            data = self.credentials_file.read_bytes()
            decrypted = self.fernet.decrypt(data)
            return json.loads(decrypted)
        except Exception:
            return {}

    def _write_credentials(self, data: Dict[str, Any]):
        encrypted = self.fernet.encrypt(json.dumps(data).encode())
        self.credentials_file.write_bytes(encrypted)

    def _read_sessions(self) -> Dict[str, Any]:
        return json.loads(self.sessions_file.read_text())

    def _write_sessions(self, data: Dict[str, Any]):
        self.sessions_file.write_text(json.dumps(data, indent=2))

    def store_credentials(
        self, user_id: str, school_id: str, username: str, password: str
    ):
        creds: Dict[str, Any] = self._read_credentials()
        creds[user_id] = {
            "school_id": school_id,
            "username": username,
            "password": password,
            "created_at": datetime.now().isoformat(),
        }
        self._write_credentials(creds)

    def get_credentials(self, user_id: str) -> Optional[Dict[str, Any]]:
        creds = self._read_credentials()
        return creds.get(user_id)

    def delete_credentials(self, user_id: str):
        creds = self._read_credentials()
        if user_id in creds:
            del creds[user_id]
            self._write_credentials(creds)

    def has_credentials(self, user_id: str) -> bool:
        return user_id in self._read_credentials()

    def store_session(self, user_id: str, session_data: Dict[str, Any]):
        sessions = self._read_sessions()
        sessions[user_id] = {
            **session_data,
            "created_at": datetime.now().isoformat(),
        }
        self._write_sessions(sessions)

    def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        sessions = self._read_sessions()
        session = sessions.get(user_id)
        if session:
            created = datetime.fromisoformat(session["created_at"])
            timeout = timedelta(hours=self.session_timeout_hours)
            if datetime.now() - created < timeout:
                return session
            else:
                del sessions[user_id]
                self._write_sessions(sessions)
        return None

    def clear_session(self, user_id: str):
        sessions = self._read_sessions()
        if user_id in sessions:
            del sessions[user_id]
            self._write_sessions(sessions)


credential_store = CredentialStore()