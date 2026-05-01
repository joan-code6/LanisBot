import os
import json
import httpx


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_reminder",
            "description": "Add a reminder for the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Reminder text"},
                    "time": {
                        "type": "string",
                        "description": "Optional time for the reminder",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_reminder",
            "description": "Remove a reminder by index",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "Index of the reminder to remove",
                    },
                },
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "Add a note",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Note text"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_info",
            "description": "Update student info in memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Info key"},
                    "value": {"type": "string", "description": "Info value"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_conversation",
            "description": "Clear conversation history",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_get_messages",
            "description": "Fetch message headers from the school portal",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_get_substitution_plan",
            "description": "Fetch substitution plan (Vertretungsplan)",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_get_homework",
            "description": "Fetch homework assignments from all courses (what teachers assigned, with done status)",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_get_submissions",
            "description": "Fetch homework submissions (what the student has already turned in or marked as done)",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_get_calendar",
            "description": "Fetch calendar events",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_get_courses",
            "description": "Fetch course overview",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_get_course",
            "description": "Fetch details for a specific course",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_id": {"type": "string", "description": "Course ID"},
                },
                "required": ["course_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_get_entry_details",
            "description": "Fetch entry details for a course entry",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Entry URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_set_homework_done",
            "description": "Mark homework as done or undone",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_id": {"type": "string", "description": "Course ID"},
                    "entry_id": {"type": "string", "description": "Entry ID"},
                    "done": {
                        "type": "boolean",
                        "description": "Whether homework is done (default true)",
                    },
                },
                "required": ["course_id", "entry_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sph_send_message",
            "description": "Send a message through the school portal",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_data": {
                        "type": "object",
                        "description": "Message data object with recipients, subject, body",
                    },
                },
                "required": ["message_data"],
            },
        },
    },
]


class HAIClient:
    def __init__(self, api_key: str = None, model: str = "qwen/qwen3-32b"):
        self.api_key = api_key or os.getenv("HAI_API_KEY")
        if not self.api_key:
            raise ValueError("HAI_API_KEY not set")

        self.model = model
        self.base_url = "https://ai.hackclub.com/proxy/v1"

    async def chat(
        self, messages: list, system_prompt: str = None, tools: bool = True
    ) -> dict:
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        if tools:
            payload["tools"] = TOOLS
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]

    async def chat_with_tool_loop(
        self, memory: dict, user_message: str, execute_tool, user_data: str = None
    ) -> str:
        system_prompt = self._build_system_prompt(memory, user_data)
        messages = [{"role": "user", "content": user_message}]

        max_tool_rounds = 5
        for _ in range(max_tool_rounds):
            msg = await self.chat(messages, system_prompt, tools=True)

            messages.append(msg)

            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    name = fn["name"]
                    args = json.loads(fn["arguments"])
                    result = await execute_tool(name, args)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
            else:
                content = msg.get("content", "")
                memory["conversation"] = memory.get("conversation", [])
                memory["conversation"].append({"role": "user", "content": user_message})
                if content:
                    memory["conversation"].append(
                        {"role": "assistant", "content": content}
                    )
                return content

        final_msg = await self.chat(messages, system_prompt, tools=False)
        content = final_msg.get("content", "")
        memory["conversation"] = memory.get("conversation", [])
        memory["conversation"].append({"role": "user", "content": user_message})
        if content:
            memory["conversation"].append({"role": "assistant", "content": content})
        return content

    def _build_system_prompt(self, memory: dict, user_data: str = None) -> str:
        prompt = """You are a helpful AI assistant for a student. You have access to the student's school portal (SchulportalHessen/SPH) and can help with school-related tasks.

Use the provided tools to fetch data or perform actions. Only call tools when the user actually needs data or an action. Do not call tools for general conversation.

You have access to the student's profile data from the portal. Use it to personalize your responses."""

        if user_data:
            prompt += f"\n\nStudent Profile Data:\n{user_data}"

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
