import asyncio
import logging
import re
import os

import discord
from discord import app_commands

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SPHDiscordBot(discord.Client):
    def __init__(self, agent, memory):
        intents = discord.Intents.default()
        intents.message_content = False

        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.agent = agent
        self.memory = memory
        self.guild_id = os.getenv("DISCORD_GUILD_ID")

    async def setup(self):
        await self.tree.sync()
        logger.info("Slash commands synced globally")

        if self.guild_id:
            guild = discord.Object(id=self.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Slash commands synced to guild")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user}")
        await self.setup()

async def on_message(self, message):
        if message.author.bot:
            return

        if message.guild is not None:
            return

        user_message = message.content.strip()
        if not user_message:
            return
        
        thinking_msg = await message.reply("🤔 thinking...")
        
        progress_text = []
        
        async def progress_callback(update: str):
            progress_text.append(update)
            combined = "🤔 **thinking...**\n\n" + "\n\n".join(progress_text)
            try:
                await thinking_msg.edit(content=combined[:2000])
            except Exception:
                pass
            
        response = await self.agent.handle_message(
            user_message, user_id=str(message.author.id),
            progress_callback=progress_callback
        )
        
        await thinking_msg.edit(content=response[:2000])

    async def start_bot(self, token: str):
        await self.start(token)


@app_commands.command(name="ask", description="Ask the SPH assistant a question")
@app_commands.describe(question="Your question about school")
@app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
async def ask_command(interaction: discord.Interaction, question: str):
    if interaction.guild is not None:
        await interaction.response.send_message("Please DM me instead.", ephemeral=True)
        return

    bot = interaction.client
    if not isinstance(bot, SPHDiscordBot):
        await interaction.response.send_message("Bot not ready.", ephemeral=True)
        return

    await interaction.response.defer()
    
    thinking_msg = await interaction.followup_send("🤔 thinking...", ephemeral=True)
    
    progress_text = []
    
    async def progress_callback(update: str):
        progress_text.append(update)
        combined = "🤔 **thinking...**\n\n" + "\n\n".join(progress_text)
        try:
            await thinking_msg.edit(content=combined[:2000])
        except Exception:
            pass
        
    response = await bot.agent.handle_message(
        question, user_id=str(interaction.user.id),
        progress_callback=progress_callback
    )
    await interaction.followup_send(response[:2000], ephemeral=True)


@app_commands.command(name="login", description="Set your SPH credentials")
@app_commands.describe(
    school_id="Your school ID",
    username="Your SPH username",
    password="Your SPH password",
)
@app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
async def login_command(
    interaction: discord.Interaction,
    school_id: str,
    username: str,
    password: str,
):
    if interaction.guild is not None:
        await interaction.response.send_message("Please DM me instead.", ephemeral=True)
        return

    bot = interaction.client
    if not isinstance(bot, SPHDiscordBot):
        await interaction.response.send_message("Bot not ready.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    response = await bot.agent.login_user(
        str(interaction.user.id), school_id, username, password
    )
    await interaction.followup.send(response, ephemeral=True)


@app_commands.command(name="new", description="Clear conversation history")
@app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
async def new_command(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message("Please DM me instead.", ephemeral=True)
        return

    bot = interaction.client
    if not isinstance(bot, SPHDiscordBot):
        await interaction.response.send_message("Bot not ready.", ephemeral=True)
        return

    bot.agent.clear_user_conversation(str(interaction.user.id))
    await interaction.response.send_message(
        "Conversation cleared. Starting fresh.", ephemeral=True
    )


@app_commands.command(name="logout", description="Remove your stored credentials")
@app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
async def logout_command(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message("Please DM me instead.", ephemeral=True)
        return

    bot = interaction.client
    if not isinstance(bot, SPHDiscordBot):
        await interaction.response.send_message("Bot not ready.", ephemeral=True)
        return

    response = bot.agent.logout_user(str(interaction.user.id))
    await interaction.response.send_message(response, ephemeral=True)


@app_commands.command(
    name="delete-all-my-data", description="Delete all stored data for you"
)
@app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
async def delete_all_my_data_command(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message("Please DM me instead.", ephemeral=True)
        return

    bot = interaction.client
    if not isinstance(bot, SPHDiscordBot):
        await interaction.response.send_message("Bot not ready.", ephemeral=True)
        return

    response = bot.agent.delete_all_user_data(str(interaction.user.id))
    await interaction.response.send_message(response, ephemeral=True)


def setup_tree(bot: SPHDiscordBot):
    bot.tree.add_command(ask_command)
    bot.tree.add_command(login_command)
    bot.tree.add_command(new_command)
    bot.tree.add_command(logout_command)
    bot.tree.add_command(delete_all_my_data_command)
