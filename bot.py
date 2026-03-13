"""
Entry point for the Rakan Survey Bot.

Creates the bot, loads cogs, and connects to Discord.
"""

import asyncio
import os
import traceback

import discord
from discord.ext import commands

from config import DISABLE_SUPABASE, DISCORD_TOKEN, OWNER_IDS

# ── Bot setup ─────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

DEBUG_EVENTS = os.getenv("BOT_DEBUG_EVENTS", "1").strip().lower() in {"1", "true", "yes", "on"}
DEBUG_COMMANDS = os.getenv("BOT_DEBUG_COMMANDS", "1").strip().lower() in {"1", "true", "yes", "on"}
DEBUG_MESSAGES = os.getenv("BOT_DEBUG_MESSAGES", "0").strip().lower() in {"1", "true", "yes", "on"}


def _debug(msg: str) -> None:
    if DEBUG_EVENTS:
        print(f"[debug] {msg}")

# ── Cog loading ───────────────────────────────────────────────────────

EXTENSIONS = [
    "survey",
    "moderation", #Add in 'data_collection' HERE if you want to collect activity
    "data_collection",
]


async def load_extensions():
    for ext in EXTENSIONS:
        await bot.load_extension(ext)
        print(f"  Loaded cog: {ext}")


# ── Error handling ────────────────────────────────────────────────────

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Unknown command. Try `!studentInfo`.")
        return

    error_message = f"Error in command '{ctx.command}': {error}"
    for owner_id in OWNER_IDS:
        try:
            owner = await bot.fetch_user(owner_id)
            await owner.send(error_message)
        except Exception as e:
            print(f"Failed to DM owner {owner_id}: {e}")
    await ctx.send("An error occurred. The bot owner has been notified.")


@bot.event
async def on_error(event_method, *args, **kwargs):
    error_details = traceback.format_exc()
    message = f"Global error in event '{event_method}':\n{error_details}"
    for owner_id in OWNER_IDS:
        try:
            owner = await bot.fetch_user(owner_id)
            await owner.send(message)
        except Exception as e:
            print(f"Failed to DM owner {owner_id}: {e}")
    print(message)


@bot.event
async def on_connect():
    _debug("Gateway connected")


@bot.event
async def on_disconnect():
    _debug("Gateway disconnected")


@bot.event
async def on_resumed():
    _debug("Gateway session resumed")


@bot.event
async def on_ready():
    _debug(f"READY user={bot.user} latency_ms={bot.latency * 1000:.1f}")


@bot.listen("on_message")
async def _trace_on_message(message: discord.Message):
    if not DEBUG_MESSAGES or message.author.bot:
        return
    guild_id = message.guild.id if message.guild else "DM"
    print(
        f"[message] guild={guild_id} channel={message.channel.id} "
        f"author={message.author.id} content={message.content!r}"
    )


@bot.before_invoke
async def _trace_before_invoke(ctx: commands.Context):
    if DEBUG_COMMANDS:
        print(
            f"[command] invoke name={ctx.command} "
            f"guild={getattr(ctx.guild, 'id', 'DM')} user={ctx.author.id}"
        )


@bot.after_invoke
async def _trace_after_invoke(ctx: commands.Context):
    if DEBUG_COMMANDS:
        print(f"[command] done name={ctx.command}")


# ── Main ──────────────────────────────────────────────────────────────

async def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is empty. Set it in your .env file before starting the bot.")
    if DISABLE_SUPABASE:
        _debug("Supabase disabled for debugging. Data collection and survey persistence are paused.")

    async with bot:
        await load_extensions()
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
