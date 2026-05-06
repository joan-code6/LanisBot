import os
import json
import io
import sys
import logging
import asyncio
import hashlib
import aiohttp
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sph_client import SchulportalHessenAPI

load_dotenv()

from credential_store import credential_store

logger = logging.getLogger("LanisBot.AIAgent")

HAI_API_KEY = os.getenv("HAI_API_KEY", "")

API_DOCS_PATH = Path("API.md")
SPH_DOCS = ""
if API_DOCS_PATH.exists():
    SPH_DOCS = API_DOCS_PATH.read_text(encoding="utf-8")

TOOL_DESCRIPTIONS = [
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Execute Python code with the 'api' object (SchulportalHessenAPI). Use this to call SPH API methods.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Python code to execute using 'api' object"}},
                "required": ["code"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_data",
            "description": "Get cached user profile data (name, email, etc.) from earlier login",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_modules",
            "description": "Get cached available modules/apps from LANIS",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a final message to the Discord user",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        }
    },
]

SYSTEM_PROMPT = """Du bist ein hilfreicher Assistent für Schüler, die ihr Schulportal (SPH oder LANIS) abfragen kann.

Ein 'api' Objekt (SchulportalHessenAPI) ist für dich eingeloggt, wenn du eingeloggt bist.

Sieh dir diese vollständige API-Dokumentation an:
""" + SPH_DOCS + """

## WICHTIG - Agent Loop
1. Verstehe die Nutzerfrage
2. Falls du Daten brauchst, führe Code aus mit execute_code
3. Wiederhole Schritt 2 bis du alle Daten hast
4. Sende das Ergebnis mit send_message an den Nutzer

Sei präzise und antworte auf Deutsch."""


class AIAgent:
    def __init__(self):
        self.sessions: Dict[str, SchulportalHessenAPI] = {}
        self.session_timestamps: Dict[str, datetime] = {}
        self.user_data: Dict[str, Dict[str, Any]] = {}
        self.available_modules: Dict[str, Dict[str, Any]] = {}
        self.result_cache: Dict[str, tuple] = {}
        self.conversation_history: Dict[str, list] = {}
        self.max_iterations = 10
        self.session_timeout_minutes = 30
        self.cache_ttl_seconds = 60

    def _get_cache_key(self, user_id: str, message: str) -> str:
        return f"{user_id}:{hashlib.md5(message.encode()).hexdigest()}"

    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        if cache_key in self.result_cache:
            result, timestamp = self.result_cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl_seconds:
                return result
            else:
                del self.result_cache[cache_key]
        return None

    def _set_cached_result(self, cache_key: str, result: Dict[str, Any]):
        self.result_cache[cache_key] = (result, datetime.now())

    def _load_user_data(self, api: SchulportalHessenAPI, user_id: str):
        try:
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')
            try:
                user_data = api.benutzer_get_data()
                if user_data.get("success"):
                    self.user_data[user_id] = user_data.get("data", {})
                
                modules = api.get_apps()
                if modules.get("success"):
                    self.available_modules[user_id] = modules.get("data", {})
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr
        except Exception as e:
            logger.error(f"Failed to load user data for {user_id}: {e}")

    def get_or_create_session(self, user_id: str) -> SchulportalHessenAPI:
        now = datetime.now()
        
        if user_id in self.sessions:
            last_active = self.session_timestamps.get(user_id)
            if last_active:
                timeout = timedelta(minutes=self.session_timeout_minutes)
                if now - last_active < timeout:
                    self.session_timestamps[user_id] = now
                    return self.sessions[user_id]
            
            del self.sessions[user_id]
            if user_id in self.session_timestamps:
                del self.session_timestamps[user_id]
            if user_id in self.user_data:
                del self.user_data[user_id]
            if user_id in self.available_modules:
                del self.available_modules[user_id]
        
        creds = credential_store.get_credentials(user_id)
        if not creds:
            api = SchulportalHessenAPI()
            api.logged_in = False
            self.sessions[user_id] = api
            return api
        
        api = SchulportalHessenAPI()
        self.sessions[user_id] = api
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')
        try:
            result = api.login(creds["school_id"], creds["username"], creds["password"])
            api.logged_in = result.get("success", False)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        return self.sessions[user_id]

    def login_user(self, user_id: str, school_id: str, username: str, password: str) -> Dict[str, Any]:
        credential_store.store_credentials(user_id, school_id, username, password)
        
        api = SchulportalHessenAPI()
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')
        try:
            result = api.login(school_id, username, password)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        
        if result.get("success"):
            self.sessions[user_id] = api
            api.logged_in = True
            self.session_timestamps[user_id] = datetime.now()
            self._load_user_data(api, user_id)
        else:
            credential_store.delete_credentials(user_id)
        
        return result

    def logout_user(self, user_id: str):
        if user_id in self.sessions:
            del self.sessions[user_id]
        if user_id in self.session_timestamps:
            del self.session_timestamps[user_id]
        if user_id in self.user_data:
            del self.user_data[user_id]
        if user_id in self.available_modules:
            del self.available_modules[user_id]
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
        credential_store.delete_credentials(user_id)

    def clear_history(self, user_id: str):
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]

    def execute_code(self, user_id: str, code: str) -> str:
        api = self.get_or_create_session(user_id)
        if not api.logged_in:
            return json.dumps({"success": False, "error": "Nicht eingeloggt. Bitte nutze /login [school_id] [username] [password]"})
        
        code = code.strip()
        if not code:
            return json.dumps({"success": False, "error": "Kein Code zum Ausführen angegeben"})
        
        if "password" in code.lower() or "passwort" in code.lower():
            return json.dumps({"success": False, "error": "Aus Sicherheitsgründen werden Passwörter nicht angezeigt oder verarbeitet"})
        
        try:
            result = eval(code, {"__builtins__": {}}, {"api": api})
            if hasattr(result, "get"):
                if not result.get("success"):
                    error_msg = result.get("message") or result.get("error") or "Unbekannter Fehler"
                    result["error"] = error_msg
                    result["user_message"] = self._get_user_friendly_error(error_msg)
                return json.dumps(result, ensure_ascii=False, indent=2)
            return str(result)
        except Exception as e:
            error_str = str(e)
            return json.dumps({"success": False, "error": error_str, "user_message": self._get_user_friendly_error(error_str)})

    def _get_user_friendly_error(self, error: str) -> str:
        error_lower = error.lower()
        
        if "login" in error_lower or "auth" in error_lower or "401" in error_lower:
            return "Login fehlgeschlagen. Bitte überprüfe deine Anmeldedaten."
        elif "timeout" in error_lower or "connection" in error_lower or "network" in error_lower:
            return "Verbindungsproblem. Bitte versuche es später noch einmal."
        elif "permission" in error_lower or "forbidden" in error_lower or "403" in error_lower:
            return "Kein Zugriff auf diese Daten. Du hast keine Berechtigung."
        elif "not found" in error_lower or "404" in error_lower:
            return "Keine Daten gefunden."
        else:
            return "Ein Fehler ist aufgetreten. Bitte versuche es erneut."

    async def chat(self, user_id: str, message: str) -> Dict[str, Any]:
        if not HAI_API_KEY:
            return {"success": False, "error": "No AI API key configured", "user_message": "Bot ist nicht richtig konfiguriert. Bitte kontaktiere den Administrator."}

        history = self.conversation_history.get(user_id, [])
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": message}]
        
        last_error = None
        for iteration in range(self.max_iterations):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://ai.hackclub.com/proxy/v1/chat/completions",
                        headers={"Authorization": "Bearer " + HAI_API_KEY, "Content-Type": "application/json"},
                        json={"model": "openai/gpt-5.4-mini", "messages": messages, "tools": TOOL_DESCRIPTIONS},
                    ) as resp:
                        if resp.status != 200:
                            text = await resp.text()
                            error_msg = f"API error {resp.status}: {text[:200]}"
                            logger.error(error_msg)
                            return {"success": False, "error": error_msg, "user_message": "Der KI-Dienst antwortet nicht. Bitte versuche es später erneut."}
                        
                        result = await resp.json()
                        choice = result.get("choices", [{}])[0]
                        msg = choice.get("message", {})

                        content = msg.get("content") or ""
                        tool_calls = msg.get("tool_calls", [])
                        
                        if tool_calls:
                            for tc in tool_calls:
                                func = tc.get("function", {})
                                name = func.get("name")
                                args = json.loads(func.get("arguments", "{}"))
                                call_id = tc.get("id", "call_" + str(iteration))
                                
                                if name == "execute_code":
                                    code = args.get("code", "")
                                    code_result = self.execute_code(user_id, code)
                                    messages.append({"role": "assistant", "tool_calls": [tc]})
                                    messages.append({"role": "tool", "tool_call_id": call_id, "content": code_result})
                                elif name == "get_user_data":
                                    user_data = self.user_data.get(user_id, {})
                                    data_result = json.dumps(user_data, ensure_ascii=False, indent=2)
                                    messages.append({"role": "assistant", "tool_calls": [tc]})
                                    messages.append({"role": "tool", "tool_call_id": call_id, "content": data_result})
                                elif name == "get_available_modules":
                                    modules = self.available_modules.get(user_id, {})
                                    modules_result = json.dumps(modules, ensure_ascii=False, indent=2)
                                    messages.append({"role": "assistant", "tool_calls": [tc]})
                                    messages.append({"role": "tool", "tool_call_id": call_id, "content": modules_result})
                                elif name == "send_message":
                                    final = args.get("message", "")
                                    self._save_to_history(user_id, message, final, tool_calls)
                                    return {"success": True, "final_message": final}

                        elif content and content.strip():
                            return {"success": True, "final_message": content}

                        continue
            except asyncio.TimeoutError:
                last_error = "Zeitüberschreitung bei der Anfrage"
                logger.error(f"Timeout for user {user_id}")
            except aiohttp.ClientError as e:
                last_error = f"Verbindungsfehler: {str(e)}"
                logger.error(f"Client error for user {user_id}: {e}")
            except json.JSONDecodeError as e:
                last_error = f"Fehler beim Verarbeiten der Antwort: {str(e)}"
                logger.error(f"JSON decode error for user {user_id}: {e}")
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error for user {user_id}: {e}")
        
        user_message = self._get_user_friendly_error(last_error) if last_error else "Die Anfrage hat zu lange gedauert. Bitte versuche es erneut."
        return {"success": False, "error": last_error or "Max iterations reached", "user_message": user_message}

    def _save_to_history(self, user_id: str, user_msg: str, assistant_msg: str, tool_calls: list = None):
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        self.conversation_history[user_id].append({"role": "user", "content": user_msg})
        
        if tool_calls:
            self.conversation_history[user_id].append({"role": "assistant", "content": assistant_msg, "tool_calls": tool_calls})
        elif assistant_msg:
            self.conversation_history[user_id].append({"role": "assistant", "content": assistant_msg})


ai_agent = AIAgent()