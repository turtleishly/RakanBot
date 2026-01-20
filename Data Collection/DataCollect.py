import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import re
import datetime
import pytz
import csv

malaysia_time = datetime.datetime.now(pytz.timezone("Asia/Kuala_Lumpur"))

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Enable members intent

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


# ensure CSVs are created inside this module's directory
DATA_DIR = os.path.dirname(__file__)
os.makedirs(DATA_DIR, exist_ok=True)
def data_path(name):
    return os.path.join(DATA_DIR, name)

STANDARD_COLUMNS = ['Message Sent At', 'Message ID', 'Channel ID','Channel name', 'Member ID', 'Username', 'Member Roles', 'Row Created At','Message type', 'Content']

# Exclusion lists: add channel IDs or channel names to exclude from collection/listing.
# Example: EXCLUDED_CHANNEL_IDS = {123456789012345678, 987654321098765432}
# Example: EXCLUDED_CHANNEL_NAMES = {"announcements", "bot-testing"}
EXCLUDED_CHANNEL_IDS = {1351929278672932935,1346622879814385818,1394922620423770292,1349396038917689415,1389347115469242532}
EXCLUDED_CHANNEL_NAMES = set()

def _is_excluded_channel(ch):
	"""Return True if channel `ch` should be skipped according to exclusion lists."""
	try:
		if getattr(ch, "id", None) in EXCLUDED_CHANNEL_IDS:
			return True
		if getattr(ch, "name", None) in EXCLUDED_CHANNEL_NAMES:
			return True
	except Exception:
		# conservative: don't exclude on unexpected errors
		return False
	return False

#--------------------------------------Collect General--------------------------------------------

x=3000 #Limit per channel of how many messages to get

# new helper: find the maximum Message ID recorded for a given channel in General.csv
def _get_latest_saved_message_id(csv_path, channel_id):
	"""
	Return the largest Message ID stored for channel_id in csv_path, or None if not found.
	"""
	if not os.path.isfile(csv_path):
		return None
	try:
		with open(csv_path, 'r', encoding='utf-8') as f:
			reader = csv.reader(f)
			# skip header if present
			headers = next(reader, None)
			max_id = None
			for row in reader:
				# row format: [Message Sent At, Message ID, Channel ID, ...]
				if len(row) < 3:
					continue
				try:
					row_channel = row[2]
					if row_channel == '':
						continue
					if int(row_channel) != channel_id:
						continue
					mid = int(row[1])
				except Exception:
					continue
				if max_id is None or mid > max_id:
					max_id = mid
			return max_id
	except Exception:
		# if reading fails, conservatively return None (so we won't skip fetching)
		return None

# new reusable helper: collect messages from any channel (used by collect_general and collect_all)
async def _collect_general_for_channel(channel, guild, stop_at_message_id=None):
	"""
	Collect up to `x` messages from `channel`, stopping if we encounter a previously-saved message ID
	(or if we see stop_at_message_id which is typically the command message to skip).
	Returns number of messages fetched (not counting skipped/old messages).
	"""
	csv_path = data_path('General.csv')
	latest_saved_id = _get_latest_saved_message_id(csv_path, channel.id)

	# Fetch up to x newest messages but stop once we reach previously-saved messages
	messages = []
	async for msg in channel.history(limit=x):
		# optionally skip a specific message (e.g. the command message in the current channel)
		if stop_at_message_id and msg.id == stop_at_message_id:
			continue
		# stop when we reach previously-saved messages for this channel
		if latest_saved_id and msg.id <= latest_saved_id:
			break
		messages.append(msg)

	if not messages:
		return 0

	rows = []
	for msg in messages:
		# map member lookups to the provided guild
		if msg.author.name == "AI Image Generator":
			match = re.search(r"<@(\d+)>", msg.content)
			member_id = match.group(1) if match else None
			member = None
			username = "Unknown"
			member_roles = ["Unknown"]
			if member_id:
				member = guild.get_member(int(member_id))
				if not member:
					try:
						member = await guild.fetch_member(int(member_id))
					except discord.NotFound:
						member = None
				username = member.name if member else "Unknown"
				member_roles = [role.name for role in member.roles if role.name != "@everyone"] if member else ["Unknown"]
			row = [
				msg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
				msg.id,
				msg.channel.id if msg.channel else None,
				msg.channel.name if msg.channel else None,
				member_id if member_id else "Unknown",
				username,
				member_roles,
				malaysia_time.strftime('%Y-%m-%d %H:%M:%S'),
				"Bot prompt",
				"AI Generated Image prompted by this user"
			]
			rows.append(row)
		elif (msg.content == ""):
			pass
		else:
			member = guild.get_member(msg.author.id)
			if not member:
				try:
					member = await guild.fetch_member(msg.author.id)
				except discord.NotFound:
					member = None
			username = member.name if member else str(msg.author)
			member_roles = [role.name for role in member.roles if role.name != "@everyone"] if member else ["Unknown"]
			row = [
				msg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
				msg.id,
				msg.channel.id if msg.channel else None,
				msg.channel.name if msg.channel else None,
				msg.author.id,
				username,
				member_roles,
				malaysia_time.strftime('%Y-%m-%d %H:%M:%S'),
				"Message",
				msg.content
			]
			rows.append(row)

		# capture reactions for THIS message
		for reaction in msg.reactions:
			async for user in reaction.users():
				member = guild.get_member(user.id)
				if not member:
					try:
						member = await guild.fetch_member(user.id)
					except discord.NotFound:
						member = None
				username_r = member.name if member else user.name
				user_roles = [role.name for role in member.roles if role.name != "@everyone"] if member else ["Unknown"]
				channel_name = msg.channel.name if msg.channel else None
				reaction_row = [
					"N/A",
					msg.id,
					msg.channel.id if msg.channel else None,
					channel_name,
					user.id,
					username_r,
					user_roles,
					malaysia_time.strftime('%Y-%m-%d %H:%M:%S'),
					"Reaction",
					f"Reaction by user: {str(reaction.emoji)}"
				]
				rows.append(reaction_row)
		# --- end reactions capture ---

	# Write to CSV (append mode)
	file_exists = os.path.isfile(csv_path)
	with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
		writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
		if not file_exists or os.path.getsize(csv_path) == 0:
			writer.writerow(STANDARD_COLUMNS)
		writer.writerows(rows)

	return len(messages)

@bot.command()
async def collect_general(ctx):
	# call the reusable helper for the current channel (skip the command message)
	count = await _collect_general_for_channel(ctx.channel, ctx.guild, stop_at_message_id=ctx.message.id)
	if count == 0:
		# check if there was previously a saved id for the channel to craft a helpful message
		csv_path = data_path('General.csv')
		latest_saved_id = _get_latest_saved_message_id(csv_path, ctx.channel.id)
		if latest_saved_id:
			await ctx.send(f"No new messages to save since message ID {latest_saved_id}.")
		else:
			await ctx.send("No messages found to save.")
	else:
		await ctx.send(f"Fetched and saved {count} new messages (plus reactions) to General.csv.")

#------------------------------------------automatic iteration over all channels----------------------------------------------
# new command: iterate over guild channels (and threads) and call the helper for each eligible one
@bot.command(name="collect_all")
async def collect_all(ctx, include_threads: bool = True, max_channels: int = 0):
    """
    Iterate up to `max_channels` readable text channels (and threads if include_threads) in the guild and run collection for each.
    Usage: !collect_all [include_threads=True] [max_channels=5]
    Provide max_channels <= 0 to disable the limit.
    """
    guild = ctx.guild
    if guild is None:
        await ctx.send("This command must be used in a server (guild).")
        return

    async def channel_has_messages(ch):
        # fast check
        if getattr(ch, "last_message_id", None):
            return True
        # fallback: try to fetch one message
        try:
            async for _ in ch.history(limit=1):
                return True
        except discord.Forbidden:
            return False
        except Exception:
            return False
        return False

    results = []
    seen_thread_ids = set()

    # interpret limit: None means no limit
    limit = max_channels if (isinstance(max_channels, int) and max_channels > 0) else None
    processed_count = 0

    # iterate every channel in the guild (no filters)
    for ch in guild.channels:
        # skip excluded channels entirely (do not count them toward processed_count)
        if _is_excluded_channel(ch):
            continue
        # respect the channel limit (count channels processed regardless of type)
        if limit is not None and processed_count >= limit:
            break

        # Attempt collection for every channel; don't abort on permission errors
        try:
            count = await _collect_general_for_channel(ch, guild)
        except discord.Forbidden:
            # can't read this channel, treat as zero collected but continue
            count = 0
        except Exception:
            # any other error: skip but continue
            count = 0

        results.append((ch.name, ch.id, count))
        processed_count += 1

        if include_threads:
            # active/cached threads
            threads = getattr(ch, "threads", []) or []
            for t in threads:
                # skip if thread excluded
                if _is_excluded_channel(t):
                    continue
                if getattr(t, "id", None) and t.id not in seen_thread_ids:
                    if await channel_has_messages(t):
                        seen_thread_ids.add(t.id)
                        count_t = await _collect_general_for_channel(t, guild)
                        results.append((f"{ch.name} -> {t.name}", t.id, count_t))

            # archived threads (attempt; may not exist on all discord.py versions or may require permissions)
            try:
                # ch.archived_threads(...) is an async iterable on versions that expose it
                async for at in ch.archived_threads(limit=None):
                    # skip archived thread if excluded
                    if _is_excluded_channel(at):
                        continue
                    if getattr(at, "id", None) and at.id not in seen_thread_ids:
                        seen_thread_ids.add(at.id)
                        try:
                            count_at = await _collect_general_for_channel(at, guild)
                        # archived threads may be unreadable; don't fail the whole run
                        except discord.Forbidden:
                            count_at = 0
                        except Exception:
                            count_at = 0
                        results.append((f"{ch.name} -> {at.name} (archived)", at.id, count_at))
            except AttributeError:
                # method doesn't exist on this discord.py version; ignore
                pass
            except discord.Forbidden:
                # can't access archived threads in this channel
                pass
            except Exception:
                # other failures accessing archived threads; continue
                pass

    # guild-level threads not caught above
    if include_threads:
        guild_threads = getattr(guild, "threads", []) or []
        for t in guild_threads:
            # guild-level threads are not counted against the channel limit
            # skip if thread or its parent is excluded
            if _is_excluded_channel(t) or _is_excluded_channel(getattr(t, "parent", None)):
                continue
            if getattr(t, "id", None) and t.id not in seen_thread_ids:
                parent = getattr(t, "parent", None)
                parent_ok = True
                if parent:
                    perms = parent.permissions_for(guild.me or ctx.guild.me)
                    if not perms.read_messages:
                        parent_ok = False
                if not parent_ok:
                    continue
                if await channel_has_messages(t):
                    seen_thread_ids.add(t.id)
                    name = f"{parent.name} -> {t.name}" if parent else f"THREAD: {t.name}"
                    count_t = await _collect_general_for_channel(t, guild)
                    results.append((name, t.id, count_t))

    total_saved = sum(r[2] for r in results)
    if not results:
        await ctx.send("No readable channels with messages found to collect.")
        return

    # report first N lines then totals (keep message short)
    report_lines = []
    for name, cid, cnt in results:
        report_lines.append(f"{name} ({cid}): {cnt}")
    out = "Collected messages per channel (new messages saved):\n" + "\n".join(report_lines)
    out += f"\n\nTotal new messages saved across channels: {total_saved}"
    if limit is not None:
        out += f"\n(Processed up to {limit} channels — processed {processed_count})"
    if len(out) > 1900:
        out = out[:1900] + "\n\n(Truncated)"
    await ctx.send(f"```{out}```")
    print("done!")

#-------------------------------------debuggin use only: get specific message------------------------------------------------------

@bot.command()
async def get_message(ctx, channel_id: int, message_id: int):
    channel = bot.get_channel(channel_id)
    if not channel:
        await ctx.send("Channel not found.")
        return

    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        await ctx.send("Message not found.")
        return

    member = ctx.guild.get_member(message.author.id)
    if not member:
        try:
            member = await ctx.guild.fetch_member(message.author.id)
        except discord.NotFound:
            member = None
    username = member.name if member else str(message.author)
    member_roles = [role.name for role in member.roles if role.name != "@everyone"] if member else ["Unknown"]

    await ctx.send(
        f"Content of message `{message_id}`:\n"
        f"Sent At: {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Channel ID: {message.channel.id if message.channel else None}\n"
        f"Member ID: {message.author.id}\n"
        f"Username: {username}\n"
        f"Member Roles: {member_roles}\n"
        f"Content: {message.content}"
    )

#-------------------------------------debuggin use only: list of all channels in server------------------------------------------------------
@bot.command(name="list_channels")
async def list_channels(ctx, include_threads: bool = True):
    """
    Print channel names + IDs in the current guild.
    Usage: !list_channels
    """
    guild = ctx.guild
    if guild is None:
        await ctx.send("This command must be used in a server (guild).")
        return

    async def channel_has_messages(ch):
        # fast check
        if getattr(ch, "last_message_id", None):
            return True
        # fallback: try to fetch one message
        try:
            async for _ in ch.history(limit=1):
                return True
        except discord.Forbidden:
            # bot can't read this channel
            return False
        except Exception:
            return False
        return False

    lines = []
    seen_thread_ids = set()

    # iterate every channel in the guild (no filters)
    for ch in guild.channels:
        # skip excluded parent channels entirely
        if _is_excluded_channel(ch):
            continue
        # include channel name + id (attempt to show type for clarity)
        try:
            lines.append(f"{ch.name} [{ch.type}]: {ch.id}")
        except Exception:
            lines.append(f"{getattr(ch, 'name', 'Unknown')}: {getattr(ch, 'id', 'Unknown')}")

        if include_threads:
            # include active threads under this channel
            threads = getattr(ch, "threads", []) or []
            for t in threads:
                # skip excluded threads
                if _is_excluded_channel(t):
                    continue
                if getattr(t, "id", None) and t.id not in seen_thread_ids:
                    # thread may have no messages, check quickly
                    if await channel_has_messages(t):
                        seen_thread_ids.add(t.id)
                        lines.append(f"  └ {t.name}: {t.id}")

            # also attempt to list archived threads (marked)
            try:
                async for at in ch.archived_threads(limit=None):
                    # skip archived thread if excluded
                    if _is_excluded_channel(at):
                        continue
                    if getattr(at, "id", None) and at.id not in seen_thread_ids:
                        # don't attempt to check messages for every archived thread (may be many); show presence
                        seen_thread_ids.add(at.id)
                        lines.append(f"  └ {at.name} (archived): {at.id}")
            except AttributeError:
                # no archived_threads API on this version
                pass
            except Exception:
                # ignore failures listing archived threads
                pass

    if not lines:
        await ctx.send("No channels found.")
        return

    # Send output in 2000-char chunks inside code blocks for readability
    msg_limit = 2000 - 6  # account for code block markers
    current = "Included channels (name: id):\n"
    out_chunks = []
    for line in lines:
        if len(current) + len(line) + 1 > msg_limit:
            out_chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        out_chunks.append(current)

    for part in out_chunks:
        await ctx.send(f"```{part}```")


bot.run(token)

