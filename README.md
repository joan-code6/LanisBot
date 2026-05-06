# LanisBot

A Discord bot that lets users access their Schulportal Hessen (LANIS) account via direct messages. The bot uses an AI agent to handle all user requests naturally - users just chat with the bot in plain language.

## Design Philosophy

This bot is different from traditional command-based bots. Instead of parsing user commands and mapping them to specific functions, **every message is sent to an AI**, which then:

1. **Understands the user's intent** from natural language
2. **Decides what API calls to make** via the `execute_code()` tool
3. **Sends the result back** to the user via `send_message()`

### Why No Command Parsing?

The AI already handles everything. If a user says:
- "show my messages" → AI calls `api.nachrichten_get_headers()`
- "what homework do I have?" → AI calls `api.meinunterricht_get_overview()`
- "show my timetable" → AI calls `api.stundenplan_get_plan()`
- "read message 5" → AI calls `api.nachrichten_get_conversation()`

There is **no need** for manual command parsing. The AI understands context, extracts parameters naturally, and makes the appropriate API calls.

## Architecture

```
User DM --> Bot --> AI Agent --> SPH API --> Schulportal Hessen
              |
              +-> execute_code() - calls sph_client API methods
              +-> send_message()  - returns results to user
```

- **bot.py**: Discord bot handling DMs and slash commands
- **ai_agent.py**: AI agent that processes messages and executes API calls
- **command_parser.py**: Only handles `/login`, `/logout`, and `/help` (things that must work without AI)
- **credential_store.py**: Encrypted storage for user credentials
- **response_formatter.py**: Formats Discord embeds

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure `.env`:
   ```
   DISCORD_BOT_TOKEN=your_token
   CREDENTIALS_MASTER_KEY=random_string
   HAI_API_KEY=your_hackclub_api_key
   ```

3. Run:
   ```bash
   python bot.py
   ```

## Usage

### DM Commands

```
/login [school_id] [username] [password]
/logout
/help
/status
/about
```

### Natural Language (via DM)

Just chat with the bot naturally:
- "show my messages"
- "what homework do I have?"
- "show my calendar for this week"
- "what's my timetable?"
- "show my profile"

### Server Commands

In servers, use `!lanis` prefix:
```
!lanis show my messages
!lanis what homework do I have
```

## Security

- Credentials are encrypted with Fernet (symmetric encryption)
- Each user has their own encrypted session
- Sessions expire after 24 hours
- Passwords are never logged or exposed

## Requirements

- Python 3.9+
- discord.py 2.0+
- python-dotenv
- cryptography
- aiohttp
- sph_client (custom package)