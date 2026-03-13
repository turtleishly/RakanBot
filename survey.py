"""
Survey Cog — handles the student demographic survey flow.

Registers:
  - on_member_join   → auto-start survey for new members
  - !studentInfo     → manually trigger survey
    - !scan            → backfill missing student rows for the current server
"""

import asyncio
import discord
from discord.ext import commands

from config import (
        DISABLE_SUPABASE,
    ENGLISH_SERVER_ID,
    MESSAGES,
    STATE_SCHOOLS,
)
from database import (
    ensure_student_row,
    format_member_roles,
    format_timestamp,
        get_student_ids_for_server,
        insert_student_membership_rows,
    save_survey_answer,
)

# Invite cache shared across the cog
invite_cache: dict[int, list] = {}


# ── Question helpers ──────────────────────────────────────────────────

async def ask_question(bot, member, guild_id, question_text, options, timeout=60 * 15):
    """Send a reaction-based multiple-choice question via DM."""
    msgs = MESSAGES[guild_id]
    option_text = "\n".join(f"{emoji} {text}" for emoji, text in options)
    msg = await member.send(f"{question_text}\n\n{option_text}")

    for emoji, _ in options:
        try:
            await msg.add_reaction(emoji)
            await asyncio.sleep(0.35)
        except discord.Forbidden:
            print(msgs["forbidden2"])

    lookup = dict(options)

    def check(reaction, user):
        return (
            user == member
            and reaction.message.id == msg.id
            and str(reaction.emoji) in lookup
        )

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=timeout, check=check)
        return lookup[str(reaction.emoji)]
    except asyncio.TimeoutError:
        await member.send(msgs["timeout1"])
        return None


async def ask_text_response(bot, member, guild_id, prompt, max_length=64, timeout=60 * 15):
    """Send a free-text question via DM and wait for a reply."""
    msgs = MESSAGES[guild_id]
    await member.send(msgs["name"].format(prompt=prompt, max_length=max_length))

    def check(message):
        return message.author == member and isinstance(message.channel, discord.DMChannel)

    while True:
        try:
            msg = await bot.wait_for("message", timeout=timeout, check=check)
            if len(msg.content) <= max_length:
                return msg.content
            await member.send(msgs["maxlength"].format(max_length=max_length))
        except asyncio.TimeoutError:
            await member.send(msgs["timeout2"])
            return None


# ── Full survey flow ──────────────────────────────────────────────────

async def run_survey(bot, member, guild_id):
    """Walk a member through the full demographic survey via DM."""
    try:
        msgs = MESSAGES[guild_id]
        state_schools = STATE_SCHOOLS[guild_id]
        is_en = guild_id == ENGLISH_SERVER_ID

        # 1. State
        states = list(state_schools.keys())
        state_emojis = [chr(0x1F1E6 + i) for i in range(len(states))]
        state_options = list(zip(state_emojis, states))
        selected_state = await ask_question(bot, member, guild_id, msgs["intro"], state_options)
        if not selected_state:
            return

        # 2. School
        schools = state_schools[selected_state]
        school_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        school_options = list(zip(school_emojis[: len(schools)], schools))
        selected_school = await ask_question(
            bot, member, guild_id, msgs["choose_school"].format(state=selected_state), school_options
        )
        if not selected_school:
            return

        # 3. Gender
        gender_options = [
            ("1️⃣", "Male" if is_en else "Laki-laki"),
            ("2️⃣", "Female" if is_en else "Perempuan"),
        ]
        selected_gender = await ask_question(bot, member, guild_id, msgs["choose_gender"], gender_options)
        if not selected_gender:
            return

        # 4. Full name
        student_name = await ask_text_response(bot, member, guild_id, msgs["full_name"])
        if not student_name:
            return

        # 5. Used Discord before?
        yes_no = [
            ("👍", "Yes" if is_en else "Ya"),
            ("👎", "No" if is_en else "Tidak"),
        ]
        used_discord_resp = await ask_question(bot, member, guild_id, msgs["discord_used"], yes_no)
        if not used_discord_resp:
            return
        used_discord = used_discord_resp in ("Yes", "Ya")

        # 6. Form / grade
        form_options = [
            ("1️⃣", "Form 1" if is_en else "13 tahun"),
            ("2️⃣", "Form 2" if is_en else "14 tahun"),
            ("3️⃣", "Form 3" if is_en else "15 tahun"),
            ("4️⃣", "Form 4" if is_en else "16 tahun"),
            ("5️⃣", "Form 5" if is_en else "17 tahun"),
            ("6️⃣", "Form 6" if is_en else "18 tahun"),
            ("❓", "Other" if is_en else "Lainnya"),
        ]
        selected_form = await ask_question(bot, member, guild_id, msgs["form"], form_options)
        if selected_form in ("Other", "Lainnya"):
            selected_form = await ask_text_response(bot, member, guild_id, msgs["form_other"])
        if not selected_form:
            return

        # Resolve invite code (best-effort)
        used_invite_code = None
        if hasattr(member, "guild") and member.guild is not None:
            invites_before = invite_cache.get(member.guild.id, [])
            invites_after = await member.guild.invites()
            for after in invites_after:
                before = next((i for i in invites_before if i.code == after.code), None)
                if before and before.uses < after.uses:
                    used_invite_code = after.code
                    break
            invite_cache[member.guild.id] = invites_after

        # Persist
        ensure_student_row(
            member.id,
            member.name,
            guild_id,
            roles=format_member_roles(member),
            invite_code=used_invite_code,
            join_timestamp=member.joined_at,
        )
        save_survey_answer(
            member.id,
            member.name,
            guild_id,
            student_name,
            selected_state,
            selected_school,
            selected_gender,
            used_discord,
            selected_form,
            invite_code=used_invite_code,
        )
        await member.send(msgs["thanks"])

    except discord.Forbidden:
        print(msgs["forbidden1"].format(member_name=member.name))


async def get_scan_members(guild: discord.Guild) -> list[discord.Member]:
    """Return a best-effort full member list for scan operations."""
    members: dict[int, discord.Member] = {
        member.id: member for member in guild.members if not member.bot
    }

    try:
        async for member in guild.fetch_members(limit=None):
            if member.bot:
                continue
            members[member.id] = member
    except discord.HTTPException as exc:
        print(f"[survey] Member scan fallback for guild {guild.id}: {exc}")

    return list(members.values())


# ── Cog definition ────────────────────────────────────────────────────

class SurveyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -- Events --

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = member.guild.id

        # Track invite
        used_invite_code = None
        invites_before = invite_cache.get(guild_id, [])
        try:
            invites_after = await member.guild.invites()
        except discord.Forbidden:
            invites_after = invites_before
        else:
            for after in invites_after:
                before = next((i for i in invites_before if i.code == after.code), None)
                if before and before.uses < after.uses:
                    used_invite_code = after.code
                    break
            invite_cache[guild_id] = invites_after

        ensure_student_row(
            member.id,
            member.name,
            guild_id,
            join_method=used_invite_code or "Invite",
            roles=format_member_roles(member),
            invite_code=used_invite_code,
            join_timestamp=member.joined_at,
        )

        if guild_id not in MESSAGES:
            return
        try:
            await member.send(MESSAGES[guild_id]["welcome"])
            await run_survey(self.bot, member, guild_id)
        except discord.Forbidden:
            print(MESSAGES[guild_id]["forbidden1"].format(member_name=member.name))

    # -- Commands --

    @commands.command(name="studentInfo", aliases=["student_info"])
    async def student_info_command(self, ctx: commands.Context):
        """Manually trigger the demographic survey."""
        if ctx.guild is None:
            await ctx.send("This command must be used in a server channel.")
            return

        if ctx.guild.id not in MESSAGES:
            await ctx.send("❌ Survey is not enabled for this server.")
            return

        await run_survey(self.bot, ctx.author, ctx.guild.id)

    @commands.command(name="scan")
    async def scan_command(self, ctx: commands.Context):
        """Backfill missing student membership rows for the current server only."""
        if ctx.guild is None:
            await ctx.send("This command must be used in a server channel.")
            return

        if ctx.guild.id not in MESSAGES:
            await ctx.send("❌ Student scan is not enabled for this server.")
            return

        if DISABLE_SUPABASE:
            await ctx.send("❌ Supabase writes are disabled, so scan cannot save any students right now.")
            return

        async with ctx.typing():
            members = await get_scan_members(ctx.guild)
            existing_student_ids = get_student_ids_for_server(ctx.guild.id)

            rows_to_insert = []
            skipped_existing = 0
            for member in members:
                member_id = str(member.id)
                if member_id in existing_student_ids:
                    skipped_existing += 1
                    continue

                timestamp = format_timestamp(member.joined_at)
                row = {
                    "discord_id": member_id,
                    "username": member.name,
                    "server_id": str(ctx.guild.id),
                    "join_method": "Existing",
                    "roles": format_member_roles(member),
                }
                if timestamp:
                    row["timestamp"] = timestamp
                rows_to_insert.append(row)

            inserted = insert_student_membership_rows(rows_to_insert)

        await ctx.send(
            f"Scan complete for **{ctx.guild.name}**. Checked {len(members)} members, "
            f"added {inserted} missing students, skipped {skipped_existing} existing records."
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(SurveyCog(bot))
