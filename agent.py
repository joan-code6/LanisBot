import asyncio
import json
import logging
import os
import re

import sph_client
from dotenv import load_dotenv

from credentials_store import CredentialsStore
from hai_client import HAIClient
from memory import Memory
from sph_monitor import SPHMonitor

try:
    import discord
    from discord_bot import SPHDiscordBot, setup_tree

    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SPHAgent:
    def __init__(self, memory_file: str = "memory.json"):
        self.hai = HAIClient()
        self.memory = Memory(memory_file)
        self.api = sph_client.SchulportalHessenAPI()
        self.credentials = CredentialsStore()
        self.discord_bot = None
        self.sph_monitor = None
        self.user_memories: dict[str, Memory] = {}

    async def initialize(self):
        await self.hai.chat(
            [{"role": "user", "content": "ping"}], system_prompt="You are a test"
        )
        logger.info("HAI client initialized")

    async def handle_message(
        self, user_message: str, user_id: str | None = None
    ) -> str:
        if user_id:
            ready = await self._ensure_credentials(user_id)
            if not ready:
                return "Please send your SPH credentials in this format: `login <school_id> <username> <password>`"

        memory = self._get_user_memory(user_id)

        user_data = ""
        if user_id:
            user_data = self.get_user_data(user_id)

        async def execute_tool(name: str, args: dict):
            if name in self._memory_actions():
                return await self._execute_memory_tool(name, args, user_id)
            if name in self._sph_actions():
                return await self._execute_sph_tool(name, args, user_id)
            return {"error": "Unknown tool"}

        response = await self.hai.chat_with_tool_loop(
            memory, user_message, execute_tool, user_data
        )

        if user_id:
            self._save_user_memory(user_id)
        else:
            self.memory.save()

        return response

    async def handle_sp_change(self, change: dict):
        change_type = change.get("type")
        change_data = change.get("data")

        prompt = f"""A change was detected in the SchulportalHessen:
        
Type: {change_type}
Data: {json.dumps(change_data, ensure_ascii=False)}

Analyze this change and decide if any action is needed. If the user should be notified, draft a notification message. Also if any action should be taken (like adding to-do, reminders, etc.), respond with the action JSON.

Respond in this format:
Notification: [Your message to the user] (or "none" if no notification needed)
{{"action": "action_name", "params": {{...}}}} (or nothing if no action needed)"""

        memory = self.memory.get()
        memory["conversation"] = memory.get("conversation", [])
        memory["conversation"].append(
            {"role": "system", "content": f"SPH Change: {change_type}"}
        )

        response = await self.hai.chat(
            [{"role": "user", "content": prompt}],
            system_prompt=self._build_system_prompt(memory),
            tools=False,
        )
        final_response = response.get("content", "")
        notification = self._extract_notification(final_response)

        self.memory.save()

        if self.discord_bot:
            await self._notify_discord(notification)

        return final_response

    async def _execute_memory_tool(
        self, name: str, args: dict, user_id: str | None
    ) -> dict:
        if name == "add_reminder":
            if user_id:
                self.user_memories[user_id].add_reminder(args["text"], args.get("time"))
            else:
                self.memory.add_reminder(args["text"], args.get("time"))
            return {"status": "ok", "message": "Reminder added"}

        if name == "remove_reminder":
            if user_id:
                self.user_memories[user_id].remove_reminder(args["index"])
            else:
                self.memory.remove_reminder(args["index"])
            return {"status": "ok", "message": "Reminder removed"}

        if name == "add_note":
            if user_id:
                self.user_memories[user_id].add_note(args["text"])
            else:
                self.memory.add_note(args["text"])
            return {"status": "ok", "message": "Note added"}

        if name == "update_info":
            if user_id:
                self.user_memories[user_id].update_info(args["key"], args["value"])
            else:
                self.memory.update_info(args["key"], args["value"])
            return {"status": "ok", "message": "Info updated"}

        if name == "clear_conversation":
            if user_id:
                self.user_memories[user_id].clear_conversation()
            else:
                self.memory.clear_conversation()
            return {"status": "ok", "message": "Conversation cleared"}

        return {"error": "Unknown memory tool"}

    HARDCODED_SCHOOL_CREDENTIALS = {
        "5201": {"username": "282822", "password": "berlin"}
    }

    async def _execute_sph_tool(
        self, name: str, args: dict, user_id: str | None
    ) -> dict:
        if not user_id:
            return {"error": "Missing user id"}

        dsb_tools = {"sph_get_substitution_plan"}
        is_dsb = name in dsb_tools
        
        stored_creds = self.credentials.get_user_creds(user_id)
        creds = None
        
        if is_dsb:
            if "5201" in self.HARDCODED_SCHOOL_CREDENTIALS:
                creds = {
                    "school_id": "5201",
                    "username": self.HARDCODED_SCHOOL_CREDENTIALS["5201"]["username"],
                    "password": self.HARDCODED_SCHOOL_CREDENTIALS["5201"]["password"]
                }
            else:
                return {"error": "DSB (Vertretungsplan) not available for any school"}
        else:
            if not stored_creds:
                return {"error": "No SPH credentials set - please login with `login <school_id> <username> <password>`"}
            creds = stored_creds

        if not self.api.logged_in:
            try:
                result = self.api.login(
                    creds["school_id"], creds["username"], creds["password"]
                )
                if not result.get("success"):
                    return {
                        "error": f"Login failed: {result.get('message', 'unknown')}"
                    }
            except Exception as e:
                return {"error": f"Login error: {e}"}

        try:
            if name == "sph_get_messages":
                return self.api.nachrichten_get_headers()
            if name == "sph_get_substitution_plan":
                return self.api.dsb_get_substitution_plan()
            if name == "sph_get_homework":
                overview = self.api.meinunterricht_get_overview()
                if overview.get("success"):
                    homework = []
                    for entry in overview.get("entries", []):
                        if entry.get("homework"):
                            homework.append(
                                {
                                    "subject": entry.get("name", ""),
                                    "date": entry.get("datum", ""),
                                    "homework": entry.get("homework", ""),
                                    "done": entry.get("homework_done", False),
                                }
                            )
                    return {"success": True, "homework": homework}
                return {"success": False, "error": overview.get("error")}
            if name == "sph_get_submissions":
                return self.api.meinunterricht_get_submissions()
            if name == "sph_get_calendar":
                return self.api.kalender_get_events()
            if name == "sph_get_courses":
                return self.api.meinunterricht_get_overview()
            if name == "sph_get_course":
                return self.api.meinunterricht_get_course(args.get("course_id"))
            if name == "sph_get_entry_details":
                return self.api.meinunterricht_get_entry_details(args.get("url"))
            if name == "sph_set_homework_done":
                return self.api.meinunterricht_set_homework_done(
                    args.get("course_id"), args.get("entry_id"), args.get("done", True)
                )
            if name == "sph_send_message":
                return self.api.nachrichten_send_message(args.get("message_data", {}))
        except Exception as e:
            return {"error": str(e)}

        return {"error": "Unknown SPH tool"}

    def _memory_actions(self) -> set:
        return {
            "add_reminder",
            "remove_reminder",
            "add_note",
            "update_info",
            "clear_conversation",
        }

    def _sph_actions(self) -> set:
        return {
            "sph_get_messages",
            "sph_get_substitution_plan",
            "sph_get_homework",
            "sph_get_submissions",
            "sph_get_calendar",
            "sph_get_courses",
            "sph_get_course",
            "sph_get_entry_details",
            "sph_set_homework_done",
            "sph_send_message",
        }

    def _extract_notification(self, response: str) -> str:
        match = re.search(r"Notification:\s*(.*)", response, re.IGNORECASE | re.DOTALL)
        if not match:
            return response.strip()
        notification = match.group(1).strip()
        if notification.lower() == "none":
            return ""
        return notification

    async def _notify_discord(self, message: str):
        if not self.discord_bot or not message or message == "none":
            return

        if not DISCORD_AVAILABLE:
            return

        channel_id = os.getenv("DISCORD_CHANNEL_ID")
        if channel_id:
            try:
                channel = self.discord_bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(message)
                return
            except Exception:
                return

        for channel in self.discord_bot.get_all_channels():
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(message)
                    return
                except Exception:
                    pass

    def _build_system_prompt(self, memory: dict) -> str:
        prompt = """You are a helpful AI assistant for a student. You have access to the student's school portal (SchulportalHessen/SPH) and can help with school-related tasks.

Available actions:
- add_reminder: Add a reminder (params: text, time)
- remove_reminder: Remove a reminder by index (params: index)
- add_note: Add a note (params: text)
- update_info: Update student info (params: key, value)
- clear_conversation: Clear conversation history
- sph_get_messages: Fetch message headers
- sph_get_substitution_plan: Fetch substitution plan
- sph_get_homework: Fetch homework submissions
- sph_get_calendar: Fetch calendar events
- sph_get_courses: Fetch course overview
- sph_get_course: Fetch course details (params: course_id)
- sph_get_entry_details: Fetch entry details (params: url)
- sph_set_homework_done: Mark homework done (params: course_id, entry_id, done)
- sph_send_message: Send a portal message (params: message_data)

If you need to take an action, respond with a JSON object in your response. Put it at the end of the message. Format:
{"action": "action_name", "params": {"param1": "value1"}}

If this is a notification message, always start with: Notification: <message>.

Otherwise respond normally to the user.

You have memory that contains:
- Student info
- Reminders
- Notes
- Recent conversation"""

        if memory.get("info"):
            prompt += (
                f"\n\nStudent Info:\n{json.dumps(memory['info'], ensure_ascii=False)}"
            )

        if memory.get("reminders"):
            prompt += (
                f"\n\nReminders:\n{json.dumps(memory['reminders'], ensure_ascii=False)}"
            )

        if memory.get("notes"):
            prompt += f"\n\nNotes:\n{json.dumps(memory['notes'], ensure_ascii=False)}"

        return prompt

    async def run(self):
        await self.initialize()

        self.sph_monitor = None

        discord_token = os.getenv("DISCORD_BOT_TOKEN")
        if discord_token and DISCORD_AVAILABLE:
            self.discord_bot = SPHDiscordBot(self, self.memory)
            setup_tree(self.discord_bot)
            await self.discord_bot.start_bot(discord_token)
        else:
            logger.warning(
                "DISCORD_BOT_TOKEN not set or discord.py not installed, Discord bot not started"
            )
            return

    async def _handle_login_command(self, user_message: str, user_id: str) -> str:
        parts = user_message.strip().split()
        if len(parts) < 4:
            return "Invalid format. Use: `login <school_id> <username> <password>`"

        _, school_id, username, password = (
            parts[0],
            parts[1],
            parts[2],
            " ".join(parts[3:]),
        )
        try:
            result = self.api.login(school_id, username, password)
            if not result.get("success"):
                return f"Login failed: {result.get('message', 'unknown error')}"
        except Exception as e:
            return f"Login failed: {e}"

        self.credentials.set_user_creds(user_id, school_id, username, password)
        return "Login successful. You can now ask questions."

    async def _ensure_credentials(self, user_id: str) -> bool:
        if self.credentials.has_user(user_id):
            return True
        if "5201" in self.HARDCODED_SCHOOL_CREDENTIALS:
            return True
        return False

    async def login_user(
        self, user_id: str, school_id: str, username: str, password: str
    ) -> str:
        try:
            result = self.api.login(school_id, username, password)
            if not result.get("success"):
                return f"Login failed: {result.get('message', 'unknown error')}"
        except Exception as e:
            return f"Login failed: {e}"

        self.credentials.set_user_creds(user_id, school_id, username, password)
        return "Login successful. You can now ask questions."

    def logout_user(self, user_id: str) -> str:
        self.credentials.remove_user_creds(user_id)
        return "Logged out. Credentials removed."

    def delete_all_user_data(self, user_id: str) -> str:
        self.credentials.remove_user_creds(user_id)
        if user_id in self.user_memories:
            del self.user_memories[user_id]

        user_memory_file = os.path.join("memories", f"{user_id}.json")
        if os.path.exists(user_memory_file):
            try:
                os.remove(user_memory_file)
            except Exception:
                pass

        return "All your data has been deleted."

    def _get_user_memory(self, user_id: str | None) -> dict:
        if not user_id:
            return self.memory.get()

        if user_id not in self.user_memories:
            user_memory_file = os.path.join("memories", f"{user_id}.json")
            self.user_memories[user_id] = Memory(user_memory_file)

        return self.user_memories[user_id].get()

    def _save_user_memory(self, user_id: str):
        if user_id in self.user_memories:
            self.user_memories[user_id].save()

    def clear_user_conversation(self, user_id: str):
        if user_id not in self.user_memories:
            user_memory_file = os.path.join("memories", f"{user_id}.json")
            self.user_memories[user_id] = Memory(user_memory_file)
        self.user_memories[user_id].clear_conversation()

    def get_user_data(self, user_id: str) -> str:
        creds = self.credentials.get_user_creds(user_id)
        if not creds:
            return ""

        if not self.api.logged_in:
            try:
                self.api.login(creds["school_id"], creds["username"], creds["password"])
            except Exception:
                return ""

        try:
            data = self.api.benutzer_get_data()
            return json.dumps(data, ensure_ascii=False)
        except Exception:
            return ""


async def main():
    load_dotenv()
    agent = SPHAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
