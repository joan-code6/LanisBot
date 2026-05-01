import json
import os
from datetime import datetime
from pathlib import Path


class Memory:
    def __init__(self, memory_file: str = "memory.json"):
        self.memory_file = Path(memory_file)
        self.memory = self._load()

    def _load(self) -> dict:
        if self.memory_file.exists():
            with open(self.memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return self._create_default()

    def _create_default(self) -> dict:
        return {
            "info": {},
            "reminders": [],
            "notes": [],
            "conversation": [],
            "last_updated": datetime.now().isoformat(),
        }

    def save(self):
        self.memory["last_updated"] = datetime.now().isoformat()
        if self.memory_file.parent:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

    def get(self) -> dict:
        return self.memory

    def update_info(self, key: str, value):
        self.memory["info"][key] = value
        self.save()

    def add_reminder(self, text: str, time: str = None):
        self.memory["reminders"].append(
            {"text": text, "time": time, "created": datetime.now().isoformat()}
        )
        self.save()

    def remove_reminder(self, index: int):
        if 0 <= index < len(self.memory["reminders"]):
            self.memory["reminders"].pop(index)
            self.save()

    def add_note(self, text: str):
        self.memory["notes"].append(
            {"text": text, "created": datetime.now().isoformat()}
        )
        self.save()

    def add_to_conversation(self, role: str, content: str):
        self.memory["conversation"].append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )
        self.save()

    def clear_conversation(self):
        self.memory["conversation"] = []
        self.save()

    def get_conversation_text(self) -> str:
        return "\n".join(
            [
                f"{msg['role']}: {msg['content']}"
                for msg in self.memory.get("conversation", [])
            ]
        )

    def edit_from_ai_response(self, edit_json: str) -> bool:
        try:
            edit_data = json.loads(edit_json)

            if edit_data.get("action") == "add_reminder":
                self.add_reminder(
                    edit_data["params"]["text"], edit_data["params"].get("time")
                )
                return True

            elif edit_data.get("action") == "remove_reminder":
                self.remove_reminder(edit_data["params"]["index"])
                return True

            elif edit_data.get("action") == "add_note":
                self.add_note(edit_data["params"]["text"])
                return True

            elif edit_data.get("action") == "update_info":
                self.update_info(
                    edit_data["params"]["key"], edit_data["params"]["value"]
                )
                return True

            elif edit_data.get("action") == "clear_conversation":
                self.clear_conversation()
                return True

            return False

        except (json.JSONDecodeError, KeyError):
            return False
