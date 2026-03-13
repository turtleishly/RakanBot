"""
Supabase-backed student database.

Handles reading and writing to the `students` table in Supabase.
Table DDL — run once in the Supabase SQL editor:

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
"""

from datetime import datetime, timezone, timedelta
from typing import Any

from config import DISABLE_SUPABASE, get_supabase

# ── Helpers ───────────────────────────────────────────────────────────

MALAYSIA_TZ = timezone(timedelta(hours=8))
_SUPABASE_DISABLED_NOTICE_PRINTED = False


def _log_supabase_disabled_once() -> None:
    global _SUPABASE_DISABLED_NOTICE_PRINTED
    if not _SUPABASE_DISABLED_NOTICE_PRINTED:
        print("[database] Supabase disabled: skipping database writes.")
        _SUPABASE_DISABLED_NOTICE_PRINTED = True


def format_member_roles(member) -> str:
    """Return a comma-separated string of a member's roles (excluding @everyone)."""
    roles = [role.name for role in getattr(member, "roles", []) if role.name != "@everyone"]
    return ", ".join(roles) if roles else "None"


def format_timestamp(value) -> str:
    """Normalise various timestamp representations to a consistent string."""
    if not value:
        return ""
    if isinstance(value, str):
        return value.split(".")[0][:19]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(MALAYSIA_TZ)
        return value.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


# ── High-level operations ─────────────────────────────────────────────

def ensure_student_row(
    user_id,
    username,
    server_id,
    join_method=None,
    roles="",
    invite_code=None,
    join_timestamp=None,
) -> None:
    """Insert or update a student's membership row in the `students` table."""
    if DISABLE_SUPABASE:
        _log_supabase_disabled_once()
        return

    uid = str(user_id)
    sid = str(server_id)
    try:
        sb = get_supabase()
    except Exception as exc:
        print(f"[database] ensure_student_row skipped: {exc}")
        return

    try:
        existing = sb.table("students").select("*").eq("discord_id", uid).eq("server_id", sid).execute().data
    except Exception as exc:
        print(f"[database] ensure_student_row query failed: {exc}")
        return

    data: dict = {"discord_id": uid, "server_id": sid, "username": username, "roles": roles}
    if invite_code:
        data["invite_code"] = invite_code
    if join_timestamp:
        ts = format_timestamp(join_timestamp)
        if ts:
            data["timestamp"] = ts

    if existing:
        row: dict[str, Any] = existing[0] if isinstance(existing[0], dict) else {}
        if join_method and (
            not row.get("join_method")
            or row["join_method"] == "Existing"
            or join_method != "Existing"
        ):
            data["join_method"] = join_method
        try:
            sb.table("students").update(data).eq("discord_id", uid).eq("server_id", sid).execute()
        except Exception as exc:
            print(f"[database] ensure_student_row update failed: {exc}")
    else:
        if join_method:
            data["join_method"] = join_method
        try:
            sb.table("students").insert(data).execute()
        except Exception as exc:
            print(f"[database] ensure_student_row insert failed: {exc}")


def get_student_ids_for_server(server_id) -> set[str]:
    """Return all known Discord user IDs for a server from the `students` table."""
    if DISABLE_SUPABASE:
        _log_supabase_disabled_once()
        return set()

    sid = str(server_id)
    try:
        sb = get_supabase()
    except Exception as exc:
        print(f"[database] get_student_ids_for_server skipped: {exc}")
        return set()

    try:
        rows = sb.table("students").select("discord_id").eq("server_id", sid).execute().data or []
    except Exception as exc:
        print(f"[database] get_student_ids_for_server query failed: {exc}")
        return set()

    student_ids: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            discord_id = row.get("discord_id")
            if discord_id:
                student_ids.add(str(discord_id))
    return student_ids


def insert_student_membership_rows(rows: list[dict[str, Any]], batch_size: int = 200) -> int:
    """Insert prebuilt membership rows without updating any existing student record."""
    if DISABLE_SUPABASE:
        _log_supabase_disabled_once()
        return 0
    if not rows:
        return 0

    try:
        sb = get_supabase()
    except Exception as exc:
        print(f"[database] insert_student_membership_rows skipped: {exc}")
        return 0

    inserted = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        try:
            sb.table("students").insert(batch).execute()
            inserted += len(batch)
        except Exception as exc:
            print(f"[database] insert_student_membership_rows insert failed: {exc}")
            break
    return inserted


def save_survey_answer(
    user_id,
    username,
    server_id,
    student_name,
    state,
    school,
    gender,
    used_discord,
    selected_form,
    invite_code=None,
) -> None:
    """Save full survey answers for a student in the `students` table."""
    if DISABLE_SUPABASE:
        _log_supabase_disabled_once()
        return

    uid = str(user_id)
    sid = str(server_id)
    try:
        sb = get_supabase()
    except Exception as exc:
        print(f"[database] save_survey_answer skipped: {exc}")
        return

    data = {
        "discord_id": uid,
        "username": username,
        "server_id": sid,
        "full_name": student_name,
        "state": state,
        "school": school,
        "gender": gender,
        "used_discord": str(bool(used_discord)),
        "form": selected_form,
    }
    if invite_code:
        data["invite_code"] = invite_code

    try:
        existing = (
            sb.table("students")
            .select("*")
            .eq("discord_id", uid)
            .eq("server_id", sid)
            .limit(1)
            .execute()
            .data
        )
    except Exception as exc:
        print(f"[database] save_survey_answer query failed: {exc}")
        return
    if existing:
        row: dict[str, Any] = existing[0] if isinstance(existing[0], dict) else {}
        update_data = {"username": username}

        one_time_fields = ["full_name", "state", "school", "gender", "used_discord", "form"]
        for field in one_time_fields:
            if _is_blank(row.get(field)) and not _is_blank(data.get(field)):
                update_data[field] = data[field]

        if invite_code and _is_blank(row.get("invite_code")):
            update_data["invite_code"] = invite_code

        if len(update_data) > 1:
            try:
                sb.table("students").update(update_data).eq("discord_id", uid).eq("server_id", sid).execute()
            except Exception as exc:
                print(f"[database] save_survey_answer update failed: {exc}")
    else:
        try:
            sb.table("students").insert(data).execute()
        except Exception as exc:
            print(f"[database] save_survey_answer insert failed: {exc}")
