# LanisBot

AI agent for SchulportalHessen (SPH) with Discord integration and persistent memory.

## What it does
- Answers questions about school data via Discord DMs
- Stores reminders/notes and full chat history per user
- Per-user SPH credentials stored encrypted on disk

## Setup
1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy env template and fill it:

```bash
copy .env.example .env
```

Required values:
- `HAI_API_KEY` (Hack Club AI key)
- `DISCORD_BOT_TOKEN` (optional, to enable Discord bot)
- `DISCORD_GUILD_ID` (optional, for slash command sync)
- `DISCORD_CHANNEL_ID` (optional, to post notifications to one channel)
- `CREDENTIALS_MASTER_KEY` (secret used to encrypt per-user credentials)
Optional values (only if you still use env-based login):
- `LANIS_API_USERNAME`, `LANIS_API_PASSWORD`, `LANIS_API_SCHOOL_ID`

## Run

```bash
python agent.py
```

## Memory
The file `memory.json` is created automatically and is always included in the AI context. You can edit it manually.

## Credentials
On first DM, the bot will ask for SPH credentials. Use:

```
login <school_id> <username> <password>
```

Credentials are encrypted and stored in `credentials.json`.

## Commands
- `/login` to set SPH credentials
- `/new` to clear conversation history
- `/logout` to remove stored credentials
- `/delete-all-my-data` to delete credentials and memory

## Notes
- The agent uses the Hack Club AI OpenAI-compatible endpoint: `https://ai.hackclub.com/proxy/v1/chat/completions`
- To disable Discord, just leave `DISCORD_BOT_TOKEN` unset.
