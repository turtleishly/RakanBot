"""
Data Collection Cog — collects messages & reactions from server channels into the Supabase `activity` table.

Features:
  - !collect_general   → collect new messages from the current channel
  - !collect_all       → iterate all readable channels & threads in that server
  - !collect_now       → alias: collect all channels immediately (for manual runs)
  - !list_channels     → list all channels in the server
  - !get_message       → fetch a specific message (debug)
  - Weekly auto-collection via discord.ext.tasks (every Monday 00:00 MYT)
"""

import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping

import discord
from discord.ext import commands, tasks

from config import (
    EXCLUDED_CHANNEL_IDS,
    EXCLUDED_CHANNEL_NAMES,
    COLLECTION_CHANNEL_LIMIT,
    OWNER_IDS,
    ENGLISH_SERVER_ID,
    INDONESIAN_SERVER_ID,
)

ALLOWED_SERVER_IDS: set[int] = {ENGLISH_SERVER_ID, INDONESIAN_SERVER_ID}

# ── Supabase table name ───────────────────────────────────────────────
# DDL (run once in Supabase SQL editor):
#
#   CREATE TABLE activity (
#       id              BIGSERIAL PRIMARY KEY,
#       message_sent_at TEXT,
#       message_id      BIGINT,
#       channel_id      BIGINT,
#       channel_name    TEXT,
#       member_id       TEXT,
#       username        TEXT,
#       member_roles    TEXT,
#       row_created_at  TEXT,
#       message_type    TEXT,
#       content         TEXT,
#       server_id       BIGINT
#   );
#   CREATE INDEX ON activity (server_id, channel_id, message_id DESC);

STANDARD_COLUMNS = [
    "Message Sent At",
    "Message ID",
    "Channel ID",
    "Channel name",
    "Member ID",
    "Username",
    "Member Roles",
    "Row Created At",
    "Message type",
    "Content",
    "Server ID",
]

MALAYSIA_TZ = timezone(timedelta(hours=8))

# Max messages to fetch per channel (oldest → newest within the limit)
MESSAGES_PER_CHANNEL = 3000


# ── Helpers ───────────────────────────────────────────────────────────

def _now_myt() -> str:
    return datetime.now(MALAYSIA_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _seconds_until_next_monday_midnight_myt() -> float:
    """Return seconds until the next Monday 00:00 in MYT."""
    now = datetime.now(MALAYSIA_TZ)
    next_monday = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_ahead = (7 - now.weekday()) % 7
    if days_ahead == 0 and now >= next_monday:
        days_ahead = 7
    next_monday = next_monday + timedelta(days=days_ahead)
    return max((next_monday - now).total_seconds(), 0.0)


def _is_excluded(ch) -> bool:
    try:
        if getattr(ch, "id", None) in EXCLUDED_CHANNEL_IDS:
            return True
        if getattr(ch, "name", None) in EXCLUDED_CHANNEL_NAMES:
            return True
    except Exception:
        return False
    return False


def _get_latest_saved_message_id(channel_id: int) -> int | None:
    """Return the largest message_id already stored for *channel_id* in the `activity` table."""
    from config import get_supabase
    try:
        result = (
            get_supabase()
            .table("activity")
            .select("message_id")
            .eq("channel_id", channel_id)
            .order("message_id", desc=True)
            .limit(1)
            .execute()
        )
        if result.data and isinstance(result.data[0], dict):
            message_id = result.data[0].get("message_id")
            if isinstance(message_id, int) and not isinstance(message_id, bool):
                return message_id
            if isinstance(message_id, str) and message_id.isdigit():
                return int(message_id)
    except Exception:
        pass
    return None


def _activity_signature(record: Mapping[str, Any]) -> tuple[int, int, str, str, str]:
    return (
        int(record.get("channel_id", 0)),
        int(record.get("message_id", 0)),
        str(record.get("member_id", "")),
        str(record.get("message_type", "")),
        str(record.get("content", "")),
    )


def _iter_chunks(values: list[int], chunk_size: int):
    for i in range(0, len(values), chunk_size):
        yield values[i : i + chunk_size]


def _get_existing_activity_signatures(channel_id: int, message_ids: list[int]) -> set[tuple[int, int, str, str, str]]:
    """Fetch existing activity signatures for the given channel/message IDs."""
    from config import get_supabase

    if not message_ids:
        return set()

    signatures: set[tuple[int, int, str, str, str]] = set()
    sb = get_supabase()

    for batch in _iter_chunks(sorted(set(message_ids)), 200):
        try:
            result = (
                sb.table("activity")
                .select("channel_id,message_id,member_id,message_type,content")
                .eq("channel_id", channel_id)
                .in_("message_id", batch)
                .execute()
            )
        except Exception:
            continue

        for row in result.data or []:
            if isinstance(row, dict):
                signatures.add(_activity_signature(row))

    return signatures


def _insert_activity_records(records: list[dict]) -> None:
    from config import get_supabase

    get_supabase().table("activity").insert(records).execute()


def _member_roles_list(member) -> list[str]:
    if member is None:
        return ["Unknown"]
    return [r.name for r in member.roles if r.name != "@everyone"] or ["None"]


async def _resolve_member(guild: discord.Guild, user_id: int):
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            member = None
    return member


# ── Core collection routine ───────────────────────────────────────────

async def _collect_channel(channel, guild: discord.Guild, skip_message_id: int | None = None) -> int:
    """
    Fetch new messages (since last saved) from *channel*, insert rows into the Supabase `activity` table.
    Returns number of new messages collected.
    """
    latest_saved = await asyncio.to_thread(_get_latest_saved_message_id, channel.id)
    now_str = _now_myt()

    messages: list[discord.Message] = []
    try:
        async for msg in channel.history(limit=MESSAGES_PER_CHANNEL):
            if skip_message_id and msg.id == skip_message_id:
                continue
            if latest_saved and msg.id <= latest_saved:
                break
            messages.append(msg)
    except discord.Forbidden:
        return 0

    if not messages:
        return 0

    rows: list[list] = []
    for msg in messages:
        # Handle AI Image Generator bot attribution
        if msg.author.name == "AI Image Generator":
            match = re.search(r"<@(\d+)>", msg.content)
            member_id = match.group(1) if match else None
            member = await _resolve_member(guild, int(member_id)) if member_id else None
            rows.append([
                msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                msg.id,
                channel.id,
                getattr(channel, "name", None),
                member_id or "Unknown",
                member.name if member else "Unknown",
                _member_roles_list(member),
                now_str,
                "Bot prompt",
                "AI Generated Image prompted by this user",
            ])
        elif msg.content:
            member = await _resolve_member(guild, msg.author.id)
            rows.append([
                msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                msg.id,
                channel.id,
                getattr(channel, "name", None),
                msg.author.id,
                member.name if member else str(msg.author),
                _member_roles_list(member),
                now_str,
                "Message",
                msg.content,
            ])

        # Reactions on this message
        for reaction in msg.reactions:
            async for user in reaction.users():
                member = await _resolve_member(guild, user.id)
                rows.append([
                    "N/A",
                    msg.id,
                    channel.id,
                    getattr(channel, "name", None),
                    user.id,
                    member.name if member else user.name,
                    _member_roles_list(member),
                    now_str,
                    "Reaction",
                    f"Reaction by user: {reaction.emoji}",
                ])

    # Batch-insert into Supabase `activity` table
    records = [
        {
            "message_sent_at": row[0],
            "message_id": row[1],           # int (BIGINT)
            "channel_id": row[2],           # int (BIGINT)
            "channel_name": row[3],
            "member_id": str(row[4]),
            "username": row[5],
            "member_roles": ", ".join(row[6]) if isinstance(row[6], list) else str(row[6]),
            "row_created_at": row[7],
            "message_type": row[8],
            "content": row[9],
            "server_id": guild.id,          # int (BIGINT)
        }
        for row in rows
    ]

    existing_signatures = await asyncio.to_thread(
        _get_existing_activity_signatures,
        channel.id,
        [msg.id for msg in messages],
    )
    deduped_records: list[dict] = []
    seen_signatures: set[tuple[int, int, str, str, str]] = set()

    for record in records:
        signature = _activity_signature(record)
        if signature in seen_signatures or signature in existing_signatures:
            continue
        seen_signatures.add(signature)
        deduped_records.append(record)

    if deduped_records:
        await asyncio.to_thread(_insert_activity_records, deduped_records)

    return len(messages)


async def _channel_has_messages(ch) -> bool:
    if getattr(ch, "last_message_id", None):
        return True
    try:
        async for _ in ch.history(limit=1):
            return True
    except (discord.Forbidden, Exception):
        pass
    return False


async def _collect_all_channels(guild: discord.Guild, include_threads: bool = True) -> list[tuple[str, int, int]]:
    """Collect from every eligible channel + threads. Returns [(name, id, count), ...]."""
    results: list[tuple[str, int, int]] = []
    seen_threads: set[int] = set()
    limit = COLLECTION_CHANNEL_LIMIT if COLLECTION_CHANNEL_LIMIT > 0 else None
    processed = 0

    for ch in guild.channels:
        if _is_excluded(ch):
            continue
        if limit is not None and processed >= limit:
            break

        try:
            count = await _collect_channel(ch, guild)
        except Exception as exc:
            print(f"[collect] Channel failed: {getattr(ch, 'name', ch)} ({getattr(ch, 'id', 'n/a')}) -> {exc}")
            count = 0
        results.append((ch.name, ch.id, count))
        processed += 1

        if include_threads:
            # Active threads
            for t in getattr(ch, "threads", []) or []:
                if _is_excluded(t) or t.id in seen_threads:
                    continue
                if await _channel_has_messages(t):
                    seen_threads.add(t.id)
                    try:
                        ct = await _collect_channel(t, guild)
                    except Exception as exc:
                        print(f"[collect] Thread failed: {t.name} ({t.id}) -> {exc}")
                        ct = 0
                    results.append((f"{ch.name} -> {t.name}", t.id, ct))

            # Archived threads
            try:
                async for at in ch.archived_threads(limit=None):
                    if _is_excluded(at) or at.id in seen_threads:
                        continue
                    seen_threads.add(at.id)
                    try:
                        ct = await _collect_channel(at, guild)
                    except Exception as exc:
                        print(f"[collect] Archived thread failed: {at.name} ({at.id}) -> {exc}")
                        ct = 0
                    results.append((f"{ch.name} -> {at.name} (archived)", at.id, ct))
            except (AttributeError, discord.Forbidden, Exception):
                pass

    # Guild-level threads not caught above
    if include_threads:
        for t in getattr(guild, "threads", []) or []:
            if _is_excluded(t) or t.id in seen_threads:
                continue
            parent = getattr(t, "parent", None)
            if _is_excluded(parent):
                continue
            if parent:
                perms = parent.permissions_for(guild.me)
                if not perms.read_messages:
                    continue
            if await _channel_has_messages(t):
                seen_threads.add(t.id)
                try:
                    ct = await _collect_channel(t, guild)
                except Exception as exc:
                    print(f"[collect] Guild thread failed: {t.name} ({t.id}) -> {exc}")
                    ct = 0
                name = f"{parent.name} -> {t.name}" if parent else f"THREAD: {t.name}"
                results.append((name, t.id, ct))

    return results


# ── Cog ───────────────────────────────────────────────────────────────

class DataCollectionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.weekly_collect.is_running():
            self.weekly_collect.start()
            print("  Data collection: weekly auto-collect scheduled")

    def cog_unload(self):
        self.weekly_collect.cancel()

    # ── Scheduled task: every Monday at 00:00 MYT (16:00 UTC Sunday) ──

    @tasks.loop(hours=168)  # 7 days
    async def weekly_collect(self):
        print(f"[Auto-collect] Starting weekly collection at {_now_myt()}")
        for guild in self.bot.guilds:
            if guild.id not in ALLOWED_SERVER_IDS:
                continue
            results = await _collect_all_channels(guild, include_threads=True)
            total = sum(r[2] for r in results)
            print(f"[Auto-collect] {guild.name}: {total} new messages across {len(results)} channels")

            # Notify first available owner
            for owner_id in OWNER_IDS:
                try:
                    owner = await self.bot.fetch_user(owner_id)
                    await owner.send(
                        f"**Weekly data collection complete** for **{guild.name}**\n"
                        f"Collected **{total}** new messages across **{len(results)}** channels."
                    )
                    break
                except Exception:
                    continue

    @weekly_collect.before_loop
    async def _before_weekly(self):
        await self.bot.wait_until_ready()
        sleep_seconds = 7 * 24 * 3600  # wait a full 7 days from startup
        print("[Auto-collect] First scheduled run in 168.00 hours (7 days from startup)")
        await asyncio.sleep(sleep_seconds)

    # ── Manual commands ───────────────────────────────────────────────

    @commands.command(name="collect_general")
    async def collect_general(self, ctx: commands.Context):
        """Collect new messages from the current channel into Supabase (`activity` table)."""
        if ctx.guild is None:
            await ctx.send("This command must be used in a server.")
            return

        count = await _collect_channel(ctx.channel, ctx.guild, skip_message_id=ctx.message.id)
        if count == 0:
            latest = await asyncio.to_thread(_get_latest_saved_message_id, ctx.channel.id)
            if latest:
                await ctx.send(f"No new messages since message ID {latest}.")
            else:
                await ctx.send("No messages found to save.")
        else:
            await ctx.send(f"Saved **{count}** new messages (+ reactions) to Supabase (`activity`).")

    @commands.command(name="collect_all")
    async def collect_all(self, ctx: commands.Context, include_threads: bool = True):
        """Collect new messages from ALL eligible channels in this server."""
        if ctx.guild is None:
            await ctx.send("This command must be used in a server.")
            return
        if ctx.guild.id not in ALLOWED_SERVER_IDS:
            await ctx.send("❌ Data collection is not enabled for this server.")
            return
        await ctx.send("Starting full collection... this may take a while.")
        results = await _collect_all_channels(ctx.guild, include_threads=include_threads)
        total = sum(r[2] for r in results)
        if not results:
            await ctx.send("No readable channels found.")
            return
        lines = [f"{name} ({cid}): {cnt}" for name, cid, cnt in results]
        out = "Collected per channel:\n" + "\n".join(lines) + f"\n\nTotal: {total}"
        if len(out) > 1900:
            out = out[:1900] + "\n(truncated)"
        await ctx.send(f"```{out}```")

    @commands.command(name="collect_now")
    async def collect_now(self, ctx: commands.Context):
        """Alias for !collect_all — immediately collect everything."""
        await self.collect_all(ctx)

    @commands.command(name="list_channels")
    async def list_channels(self, ctx: commands.Context, include_threads: bool = True):
        """List all channels (and threads) visible to the bot."""
        guild = ctx.guild
        if guild is None:
            await ctx.send("This command must be used in a server.")
            return

        lines: list[str] = []
        seen_threads: set[int] = set()

        for ch in guild.channels:
            if _is_excluded(ch):
                continue
            lines.append(f"{ch.name} [{ch.type}]: {ch.id}")

            if include_threads:
                for t in getattr(ch, "threads", []) or []:
                    if _is_excluded(t) or t.id in seen_threads:
                        continue
                    if await _channel_has_messages(t):
                        seen_threads.add(t.id)
                        lines.append(f"  └ {t.name}: {t.id}")
                try:
                    async for at in ch.archived_threads(limit=None):
                        if _is_excluded(at) or at.id in seen_threads:
                            continue
                        seen_threads.add(at.id)
                        lines.append(f"  └ {at.name} (archived): {at.id}")
                except (AttributeError, discord.Forbidden, Exception):
                    pass

        if not lines:
            await ctx.send("No channels found.")
            return

        # Chunk output to stay under 2000 chars
        chunks: list[str] = []
        current = "Channels (name: id):\n"
        for line in lines:
            if len(current) + len(line) + 7 > 1994:
                chunks.append(current)
                current = ""
            current += line + "\n"
        if current:
            chunks.append(current)
        for part in chunks:
            await ctx.send(f"```{part}```")

    @commands.command(name="get_message")
    async def get_message(self, ctx: commands.Context, channel_id: int, message_id: int):
        """Fetch and display a specific message (debug helper)."""
        if ctx.guild is None:
            await ctx.send("This command must be used in a server.")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await ctx.send("Channel not found.")
            return
        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, AttributeError):
            await ctx.send("Message not found.")
            return
        member = await _resolve_member(ctx.guild, message.author.id)
        await ctx.send(
            f"**Message** `{message_id}`:\n"
            f"Sent: {message.created_at:%Y-%m-%d %H:%M:%S}\n"
            f"Channel: {message.channel.id}\n"
            f"Author: {member.name if member else message.author} ({message.author.id})\n"
            f"Roles: {_member_roles_list(member)}\n"
            f"Content: {message.content}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(DataCollectionCog(bot))
