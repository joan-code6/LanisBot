import discord
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class Response:
    content: str
    embed: Optional[discord.Embed] = None
    ephemeral: bool = False


@dataclass
class PaginatedResponse:
    pages: List[Response]
    current_page: int = 0


def paginate_list(items: List[Any], items_per_page: int = 10) -> List[List[Any]]:
    pages = []
    for i in range(0, len(items), items_per_page):
        pages.append(items[i:i + items_per_page])
    return pages


class ResponseFormatter:
    HELP_TEXT = """
**Lanis Bot Commands**

So kannst du mit mir sprechen:

**Messages**
- "show my messages" or "show my nachrichten"
- "how many unread messages do i have?"

**Calendar**
- "show calendar" or "show my calendar for this week"
- "any events today?"

**Homework**
- "show homework" or "show my assignments"
- "what assignments do i have?"

**Substitution**
- "show substitution plan" or "vertretungsplan"
- "what's the substitution for today?"

**Timetable**
- "show timetable" or "stundenplan"

**Profile**
- "show my profile" or "my data"

**Login**
- `/login [school_id] [username] [password]`
- Beispiel: `/login 1234 john.doe mypassword`

**Logout**
- "logout" or "abmelden"

**Help**
- "help" or "hilfe"

Schreib mir einfach eine Nachricht und ich helfe dir!
""".strip()

    @staticmethod
    def format_error(error: str) -> Response:
        embed = discord.Embed(
            title="❌ Error",
            description=error,
            color=discord.Color.red(),
        )
        return Response(content="", embed=embed)

    @staticmethod
    def format_success(message: str, data: Any = None) -> Response:
        embed = discord.Embed(
            title="✅ Success",
            description=message,
            color=discord.Color.green(),
        )
        if data:
            embed.add_field(name="Details", value=str(data)[:1000], inline=False)
        return Response(content="", embed=embed)

    @staticmethod
    def format_login_prompt() -> Response:
        embed = discord.Embed(
            title="🔐 Login Required",
            description="Bitte logge dich ein, um auf dein Schulportal-Konto zuzugreifen.",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="So loggst du dich ein",
            value="Nutze: `/login [school_id] [username] [password]`\n\nBeispiel:\n`/login 1234 john.doe MyPassword123`",
            inline=False,
        )
        return Response(content="", embed=embed)

    @staticmethod
    def format_messages(messages: list) -> Response:
        if not messages:
            embed = discord.Embed(
                title="📬 Your Messages",
                description="No messages found.",
                color=discord.Color.blue(),
            )
            return Response(content="", embed=embed)

        embed = discord.Embed(
            title=f"📬 Your Messages ({len(messages)} recent)",
            color=discord.Color.blue(),
        )

        for i, msg in enumerate(messages[:10], 1):
            subject = msg.get("subject", "No subject")[:50]
            from_name = msg.get("from", "Unknown")
            date = msg.get("date", "Unknown")
            read_status = "✓" if msg.get("read") else "○"
            embed.add_field(
                name=f"{read_status} #{i}: {subject}",
                value=f"From: {from_name}\nDate: {date}",
                inline=False,
            )
        return Response(content="", embed=embed)

    @staticmethod
    def format_calendar(events: list) -> Response:
        if not events:
            embed = discord.Embed(
                title="📅 Your Calendar",
                description="No events found.",
                color=discord.Color.blue(),
            )
            return Response(content="", embed=embed)

        embed = discord.Embed(
            title=f"📅 Upcoming Events ({len(events)} this week)",
            color=discord.Color.blue(),
        )

        for event in events[:10]:
            title = event.get("title", "Untitled")[:50]
            start = event.get("start", "Unknown")
            embed.add_field(name=title, value=f"📅 {start}", inline=False)
        return Response(content="", embed=embed)

    @staticmethod
    def format_homework(homework: list) -> Response:
        if not homework:
            embed = discord.Embed(
                title="📚 Your Homework",
                description="No homework found.",
                color=discord.Color.blue(),
            )
            return Response(content="", embed=embed)

        embed = discord.Embed(
            title=f"📚 Homework ({len(homework)} items)",
            color=discord.Color.blue(),
        )

        for item in homework[:10]:
            title = item.get("title", "Untitled")[:50]
            course = item.get("course", "Unknown")
            due = item.get("due", "No due date")
            embed.add_field(name=title, value=f"Course: {course}\nDue: {due}", inline=False)
        return Response(content="", embed=embed)

    @staticmethod
    def format_substitution(data: Dict[str, Any]) -> Response:
        days = data.get("days", [])
        if not days:
            embed = discord.Embed(
                title="🚪 Substitution Plan",
                description="No substitution plan available.",
                color=discord.Color.blue(),
            )
            return Response(content="", embed=embed)

        embed = discord.Embed(
            title="🚪 Substitution Plan",
            color=discord.Color.blue(),
        )

        for day in days[:5]:
            date = day.get("date", "Unknown")
            entries = day.get("entries", [])
            entry_text = "\n".join([
                f"- {e.get('hour', '?')}: {e.get('substitution', 'N/A')}"
                for e in entries[:3]
            ]) or "No changes"
            embed.add_field(name=date, value=entry_text[:500], inline=False)
        return Response(content="", embed=embed)

    @staticmethod
    def format_timetable(data: Dict[str, Any]) -> Response:
        embed = discord.Embed(
            title="📅 Your Timetable",
            description="Use the web portal for full timetable view.",
            color=discord.Color.blue(),
        )
        if data:
            embed.add_field(name="Data", value=str(data)[:500], inline=False)
        return Response(content="", embed=embed)

    @staticmethod
    def format_profile(data: Dict[str, Any]) -> Response:
        embed = discord.Embed(
            title="👤 Your Profile",
            color=discord.Color.blue(),
        )
        for key, value in data.items():
            if key not in ["cookies", "session"]:
                embed.add_field(name=key.title(), value=str(value)[:500], inline=True)
        return Response(content="", embed=embed)

    @staticmethod
    def format_help() -> Response:
        embed = discord.Embed(
            title="❓ Help",
            description=ResponseFormatter.HELP_TEXT,
            color=discord.Color.blue(),
        )
        return Response(content="", embed=embed)

    @staticmethod
    def format_unknown() -> Response:
        embed = discord.Embed(
            title="❓ I don't understand",
            description="I couldn't understand your request. Try `help` for a list of commands.",
            color=discord.Color.orange(),
        )
        return Response(content="", embed=embed)


response_formatter = ResponseFormatter()