import os
import sys
import logging
import json
import asyncio
import signal
from functools import wraps
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timedelta

load_dotenv()

import discord
from discord import app_commands

from command_parser import command_parser, CommandType
from credential_store import credential_store
from response_formatter import response_formatter
from ai_agent import ai_agent


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("LanisBot")


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.requests[user_id] = [ts for ts in self.requests[user_id] if ts > cutoff]
        
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        self.requests[user_id].append(now)
        return True

    def get_remaining(self, user_id: str) -> int:
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.requests[user_id] = [ts for ts in self.requests[user_id] if ts > cutoff]
        return max(0, self.max_requests - len(self.requests[user_id]))


class LanisBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.dm_messages = True
        intents.dm_reactions = True
        intents.message_content = True
        intents.guild_messages = True
        super().__init__(intents=intents)
        
        self.rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
        self._shutdown_event = asyncio.Event()
        self._start_time = datetime.now()

    async def setup_hook(self):
        self.tree = app_commands.CommandTree(self)
        
        @self.tree.command(name="login", description="Log in to your Schulportal account")
        async def login_command(interaction: discord.Interaction, school_id: str, username: str, password: str):
            user_id = str(interaction.user.id)
            await interaction.response.send_message("🔐 Versuche dich einzuloggen...", ephemeral=True)
            result = ai_agent.login_user(user_id, school_id, username, password)
            if result.get("success"):
                await interaction.followup.send("✅ Erfolgreich eingeloggt!", ephemeral=True)
            else:
                error = result.get("error", "Unbekannter Fehler")
                await interaction.followup.send(f"❌ Login fehlgeschlagen: {error}", ephemeral=True)

        @self.tree.command(name="logout", description="Log out from your Schulportal account")
        async def logout_command(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            ai_agent.logout_user(user_id)
            await interaction.response.send_message("✅ Erfolgreich abgemeldet!", ephemeral=True)
        
        @self.tree.command(name="new", description="Start a new conversation (clears history)")
        async def new_command(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            ai_agent.clear_history(user_id)
            await interaction.response.send_message("✅ Neue Konversation gestartet! Alles vorherige wurde vergessen.", ephemeral=True)
        
        @self.tree.command(name="status", description="Check your login status")
        async def status_command(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            has_creds = credential_store.has_credentials(user_id)
            if has_creds:
                creds = credential_store.get_credentials(user_id)
                uptime = datetime.now() - self._start_time
                hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime_str = f"{hours}h {minutes}m"
                
                if creds:
                    await interaction.response.send_message(
                        f"✅ Du bist eingeloggt!\n\n👤 Benutzer: `{creds.get('username', 'N/A')}`\n🏫 Schule: `{creds.get('school_id', 'N/A')}`\n⏱️ Bot-Uptime: {uptime_str}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"✅ Du bist eingeloggt!\n\n⏱️ Bot-Uptime: {uptime_str}",
                        ephemeral=True
                    )
            else:
                uptime = datetime.now() - self._start_time
                hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime_str = f"{hours}h {minutes}m"
                await interaction.response.send_message(
                    f"❌ Du bist nicht eingeloggt.\n\nNutze `/login [school_id] [username] [password]` um dich anzumelden.\n\n⏱️ Bot-Uptime: {uptime_str}",
                    ephemeral=True
                )
        
        @self.tree.command(name="help", description="Show help information")
        async def help_command(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            resp = response_formatter.format_help()
            if resp.embed:
                await interaction.response.send_message(embed=resp.embed, ephemeral=True)
            else:
                await interaction.response.send_message(resp.content, ephemeral=True)
        
        @self.tree.command(name="about", description="Show bot info")
        async def about_command(interaction: discord.Interaction):
            uptime = datetime.now() - self._start_time
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"
            
            embed = discord.Embed(
                title="LanisBot Info",
                description="Discord bot für Schulportal Hessen (LANIS)",
                color=discord.Color.blue()
            )
            embed.add_field(name="Version", value="1.1.0", inline=True)
            embed.add_field(name="Uptime", value=uptime_str, inline=True)
            embed.add_field(name="Server", value=f"{len(self.guilds)}", inline=True)
            embed.add_field(name="Made with", value="discord.py + AI", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await self.tree.sync()
        logger.info("Slash commands synced!")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("Bot is ready to receive DMs!")

    async def on_message(self, message: discord.Message):
        if message.author.id == self.user.id:
            return

        if isinstance(message.channel, discord.DMChannel):
            await self.handle_dm(message)
        elif isinstance(message.channel, discord.TextChannel):
            await self.handle_guild_message(message)

    async def handle_guild_message(self, message: discord.Message):
        content = message.content.strip()
        
        if not content:
            return
        
        if content.lower().startswith("!lanis"):
            user_id = str(message.author.id)
            actual_content = content[6:].strip()
            
            if not actual_content:
                await message.reply("Nutze `!lanis help` für Hilfe")
                return
            
            logger.info(f"Received guild command from {user_id}: {actual_content}")
            
            if not self.rate_limiter.is_allowed(user_id):
                remaining = self.rate_limiter.get_remaining(user_id)
                await message.reply(f"Zu viele Anfragen! Bitte warte kurz. (Verbleibend: {remaining})")
                return
            
            if actual_content.lower() in ["help", "hilfe"]:
                resp = response_formatter.format_help()
                if resp.embed:
                    await message.reply(embed=resp.embed)
                else:
                    await message.reply(resp.content)
                return
            
            if actual_content.lower().startswith("login"):
                await message.reply("Bitte nutze DMs für Login: `/login [school_id] [username] [password]`")
                return
            
            if not credential_store.has_credentials(user_id):
                await message.reply("Du bist nicht eingeloggt! Bitte logge dich per DM ein: `/login [school_id] [username] [password]`")
                return

            await message.channel.typing()
            
            ai_result = await ai_agent.chat(user_id, actual_content)
            
            if not ai_result.get("success"):
                user_message = ai_result.get("user_message")
                if user_message:
                    await message.reply(f"Fehler: {user_message}")
                else:
                    await message.reply("Fehler: " + str(ai_result.get("error", "Ein Fehler ist aufgetreten")))
                return
            
            final_msg = ai_result.get("final_message")
            if final_msg:
                if len(final_msg) > 2000:
                    for i in range(0, len(final_msg), 2000):
                        await message.reply(final_msg[i:i + 2000])
                else:
                    await message.reply(final_msg)

    async def handle_dm(self, message: discord.Message):
        user_id = str(message.author.id)
        content = message.content.strip()

        logger.info(f"Received DM from {user_id}: {content}")

        if not content:
            return

        if not self.rate_limiter.is_allowed(user_id):
            remaining = self.rate_limiter.get_remaining(user_id)
            await message.channel.send(f"⚠️ Zu viele Anfragen! Bitte warte kurz. (Verbleibend: {remaining})")
            logger.warning(f"Rate limited user {user_id}")
            return

        parsed = command_parser.parse(content)

        if parsed.command == CommandType.LOGIN:
            creds = parsed.args.get("credentials")
            if creds:
                await message.channel.send("🔐 Versuche dich einzuloggen...")
                result = ai_agent.login_user(
                    user_id,
                    creds["school_id"],
                    creds["username"],
                    creds["password"],
                )
                if result.get("success"):
                    await message.channel.send("✅ Erfolgreich eingeloggt!")
                else:
                    error = result.get("error", "Unbekannter Fehler")
                    await message.channel.send(f"❌ Login fehlgeschlagen: {error}")
            else:
                await message.channel.send("Bitte nutze: `/login [school_id] [username] [password]`")
            return

        if parsed.command == CommandType.LOGOUT:
            ai_agent.logout_user(user_id)
            await message.channel.send("✅ Erfolgreich abgemeldet!")
            return

        if parsed.command == CommandType.UNKNOWN and content.strip().lower() == "/new":
            ai_agent.clear_history(user_id)
            await message.channel.send("✅ Neue Konversation gestartet! Alles vorherige wurde vergessen.")
            return

        if parsed.command == CommandType.HELP:
            resp = response_formatter.format_help()
            if resp.embed:
                await message.channel.send(embed=resp.embed)
            else:
                await message.channel.send(resp.content)
            return

        if not credential_store.has_credentials(user_id):
            resp = response_formatter.format_login_prompt()
            if resp.embed:
                await message.channel.send(embed=resp.embed)
            else:
                await message.channel.send(resp.content)
            return

        await message.channel.typing()
        

        ai_result = await ai_agent.chat(user_id, content)

        if not ai_result.get("success"):
            user_message = ai_result.get("user_message")
            if user_message:
                await message.channel.send(f"❌ {user_message}")
            else:
                await message.channel.send("❌ " + str(ai_result.get("error", "Ein Fehler ist aufgetreten")))
            return

        final_msg = ai_result.get("final_message")
        if final_msg:
            await message.channel.send(final_msg)

        logger.info(f"Responded to {user_id}")


async def run_bot():
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

    if not token:
        logger.error("No bot token! Set DISCORD_BOT_TOKEN in .env")
        sys.exit(1)

    client = LanisBot()
    
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig):
        logger.info(f"Received signal {sig}, shutting down gracefully...")
        asyncio.ensure_future(client.close())
        shutdown_event.set()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        except NotImplementedError:
            pass
    
    try:
        await client.start(token)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        await client.close()
    except Exception as e:
        logger.error(f"Bot error: {e}")
        await client.close()


if __name__ == "__main__":
    asyncio.run(run_bot())