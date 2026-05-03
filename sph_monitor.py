import asyncio
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import sph_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHECK_INTERVAL = 15 * 60
WORK_START_HOUR = 6
WORK_END_HOUR = 15


def create_user_monitor(user_id: str, credentials: dict, callback=None) -> "SPHMonitor":
    state_file = f"sph_state_{user_id}.json"
    return SPHMonitor(state_file=state_file, callback=callback, credentials=credentials)


class SPHMonitor:
    def __init__(
        self,
        state_file: str = "sph_state.json",
        callback=None,
        credentials: dict | None = None,
    ):
        self.state_file = Path(state_file)
        self.callback = callback
        self.credentials = credentials
        self.api = sph_client.SchulportalHessenAPI()
        self.previous_state = self._load_state()
        self.running = False

    def _load_state(self) -> dict:
        if self.state_file.exists():
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_state(self, state: dict):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _hash_data(self, data) -> str:
        if isinstance(data, (dict, list)):
            data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(str(data).encode()).hexdigest()

    async def login(self):
        if self.credentials:
            result = self.api.login(
                self.credentials["school_id"],
                self.credentials["username"],
                self.credentials["password"],
            )
        else:
            result = self.api.login_using_env()
        logger.info(f"Login result: {result}")
        return result

    def _is_within_working_hours(self) -> bool:
        now = datetime.now()
        current_hour = now.hour
        return WORK_START_HOUR <= current_hour < WORK_END_HOUR

    async def check_changes(self) -> list[dict]:
        changes = []

        try:
            messages = self.api.nachrichten_get_headers()
            messages_hash = self._hash_data(messages)
            if "messages" not in self.previous_state:
                self.previous_state["messages"] = messages_hash
                changes.append(
                    {"type": "messages", "data": messages, "action": "initial"}
                )
            elif self.previous_state.get("messages") != messages_hash:
                changes.append(
                    {"type": "messages", "data": messages, "action": "changed"}
                )
                self.previous_state["messages"] = messages_hash

            substitution = self.api.dsb_get_substitution_plan(password="berlin", username="282822")
            substitution_hash = self._hash_data(substitution)
            if "substitution" not in self.previous_state:
                self.previous_state["substitution"] = substitution_hash
                changes.append(
                    {"type": "substitution", "data": substitution, "action": "initial"}
                )
            elif self.previous_state.get("substitution") != substitution_hash:
                changes.append(
                    {"type": "substitution", "data": substitution, "action": "changed"}
                )
                self.previous_state["substitution"] = substitution_hash

            homework = self.api.meinunterricht_get_submissions()
            homework_hash = self._hash_data(homework)
            if "homework" not in self.previous_state:
                self.previous_state["homework"] = homework_hash
                changes.append(
                    {"type": "homework", "data": homework, "action": "initial"}
                )
            elif self.previous_state.get("homework") != homework_hash:
                changes.append(
                    {"type": "homework", "data": homework, "action": "changed"}
                )
                self.previous_state["homework"] = homework_hash

            calendar = self.api.kalender_get_events()
            calendar_hash = self._hash_data(calendar)
            if "calendar" not in self.previous_state:
                self.previous_state["calendar"] = calendar_hash
                changes.append(
                    {"type": "calendar", "data": calendar, "action": "initial"}
                )
            elif self.previous_state.get("calendar") != calendar_hash:
                changes.append(
                    {"type": "calendar", "data": calendar, "action": "changed"}
                )
                self.previous_state["calendar"] = calendar_hash

            self._save_state(self.previous_state)

        except Exception as e:
            logger.error(f"Error checking changes: {e}")

        return changes

    async def start_monitoring(self, interval: int = CHECK_INTERVAL):
        self.running = True

        await self.login()

        while self.running:
            try:
                if not self.api.logged_in:
                    await self.login()

                if self._is_within_working_hours():
                    changes = await self.check_changes()

                    if changes and self.callback:
                        for change in changes:
                            await self.callback(change)
                else:
                    logger.info("Outside working hours (6am-3pm), skipping check")

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)

    def stop(self):
        self.running = False
