# Rakan Survey Bot

Standalone Discord bot that:
1. Collects student demographic data via an interactive DM survey
2. Logs student activity (messages & reactions) across server channels
3. Enforces basic word-level moderation
4. Can backfill missing student rows with a manual server scan

## Project structure

```
Refactored_bot/
├── bot.py              # Entry point — creates the bot, loads cogs, runs
├── config.py           # All constants: server IDs, translations, school maps, exclusions
├── database.py         # Student data — Supabase `students` table
├── data_collection.py  # Data Collection Cog — Supabase `activity` table
├── survey.py           # Survey Cog — DM survey flow + on_member_join
├── moderation.py       # Moderation Cog — bad-word filter
├── migrate_csv_to_supabase.py  # One-time backfill from CSV files to Supabase
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## Quick start (local)

```bash
# 1. Create & activate a venv
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell

# 2. Install dependencies
pip install uv #For faster downloads
uv pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and fill in:
#   DISCORD_TOKEN  — your bot token
#   SUPABASE_URL   — from Supabase project settings → API
#   SUPABASE_KEY   — service_role key (keeps writes server-side only)

# 4. Run
python bot.py
```

## Deploy (Docker / Railway / Fly.io)

```bash
docker build -t rakan-survey-bot .
docker run --env-file .env rakan-survey-bot
```

On Railway (paid), Fly.io(paid) or Koyeb(free?), push the repo and set `DISCORD_TOKEN`, `SUPABASE_URL`, and `SUPABASE_KEY` as environment variables. The `Dockerfile` is auto-detected.

---

## Supabase setup

Create a free project at [supabase.com](https://supabase.com), then run the following SQL in the **SQL Editor**:

```sql
-- Student survey data
CREATE TABLE students (
    id           BIGSERIAL PRIMARY KEY,
    discord_id   TEXT NOT NULL,
    username     TEXT,
    server_id    TEXT,
    join_method  TEXT,
    roles        TEXT,
    full_name    TEXT,
    state        TEXT,
    school       TEXT,
    gender       TEXT,
    used_discord TEXT,
    form         TEXT,
    timestamp    TEXT,
    invite_code  TEXT,
    UNIQUE (discord_id, server_id)
);

-- Message + reaction activity log
CREATE TABLE activity (
    id              BIGSERIAL PRIMARY KEY,
    message_sent_at TEXT,
    message_id      BIGINT,
    channel_id      BIGINT,
    channel_name    TEXT,
    member_id       TEXT,
    username        TEXT,
    member_roles    TEXT,
    row_created_at  TEXT,
    message_type    TEXT,
    content         TEXT,
    server_id       BIGINT
);
CREATE INDEX ON activity (server_id, channel_id, message_id DESC);
```

Then copy your **Project URL** and **`service_role` key** from _Project Settings → API_ into `.env`:

```
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<service_role key>
```

### Import existing CSV history

If Supabase CSV import says headers are incompatible, that's expected: your old files use human-readable headers (e.g. `Message Sent At`) while the table uses snake_case (e.g. `message_sent_at`).

Notes:
- `students` import uses upsert on `(discord_id, server_id)` so reruns are safe.
- `activity` import inserts rows as-is, so rerunning it will duplicate historical rows.

---

## Data collection
To enable collection for the `activity` table, you need to add in 'data_collection' in the `EXTENSIONS` list in bot.py

I have disabled it by default.

### Automatic (weekly)

Once the bot is running, a background task automatically collects new messages from **all** eligible channels every **7 days** (starting from first boot). When the collection completes the bot DMs the first reachable owner in `OWNER_IDS`.

No action needed — just keep the bot running.

### Manual / immediate collection

From any text channel the bot can read, run one of:

| Command | What it does |
|---|---|
| `!collect_now` | Collect new messages from **all** channels + threads in the server |
| `!collect_all` | Same as above (accepts `include_threads` flag) |
| `!collect_general` | Collect new messages from **the current channel only** |

The collected data is saved to the Supabase **`activity`** table in real time.  
Only **new** messages since the last collection are fetched — safe to re-run as often as you like.

### Excluding channels

Edit `EXCLUDED_CHANNEL_IDS` or `EXCLUDED_CHANNEL_NAMES` in `config.py` to skip channels you don't want collected (e.g. admin-only, bot-testing).

### Debug helpers

| Command | What it does |
|---|---|
| `!list_channels` | Show all channels visible to the bot |
| `!get_message <channel_id> <message_id>` | Fetch & display a specific message |

---

## Student survey and backfill

The normal path is still automatic onboarding: when a new member joins an allowed server, the bot creates their membership row and DMs them the survey.

If the bot was offline during joins, use the scan command as a failsafe:

| Command | What it does |
|---|---|
| `!studentInfo` | Manually trigger the demographic survey for yourself |
| `!scan` | Scan the current allowed server and add only missing rows to the `students` table |

Notes:
- `!scan` only works in servers where the survey is enabled.
- `!scan` does not overwrite existing student rows or survey answers.
- `!scan` skips bots and records missing members with `join_method = Existing`.

## Data storage

All data is persisted in Supabase (PostgreSQL):
- `database.py` — writes survey answers to the **`students`** table  
- `data_collection.py` — appends messages & reactions to the **`activity`** table  

Data survives container restarts and redeployments automatically.
