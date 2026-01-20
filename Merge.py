# ONE TIME USE SCRIPT TO MERGE STUDENT INFO FROM LEGACY CSV INTO CURRENT CSV
import csv
import os
from decimal import Decimal, InvalidOperation

CSV_FILE = "students.csv"
LEGACY_CSV = "Student Info - Sheet1.csv"


def parse_discord_id(raw):
    value = (raw or "").strip()
    if not value:
        return ""
    try:
        if "e" in value.lower() or "." in value:
            return str(int(Decimal(value)))
        return str(int(value))
    except (InvalidOperation, ValueError):
        return value


def legacy_used_discord(raw):
    txt = (raw or "").strip().lower()
    if txt in {"true", "yes", "1"}:
        return "Yes"
    if txt in {"false", "no", "0"}:
        return "No"
    return ""


def load_legacy_student_info():
    if not os.path.exists(LEGACY_CSV):
        return {}
    legacy = {}
    with open(LEGACY_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            discord_id = parse_discord_id(row.get("Discord ID", ""))
            if not discord_id:
                continue
            entry = {
                "username": (row.get("Discord Name") or "").strip(),
                "server_id": parse_discord_id(row.get("Server ID", "")),
                "full_name": (row.get("Full name") or "").strip(),
                "state": (row.get("State") or "").strip(),
                "school": (row.get("School") or "").strip(),
                "gender": (row.get("Gender") or "").strip(),
                "used_discord": legacy_used_discord(row.get("Used Discord")),
                "form": (row.get("Form ") or row.get("Form") or "").strip(),
                "timestamp": (row.get("Time completed Survey") or "").strip(),
                "invite_code": (row.get("Join Method") or "").strip(),
            }
            legacy.setdefault(discord_id, []).append(entry)
    return legacy


def load_students():
    if not os.path.exists(CSV_FILE):
        return [], []
    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return rows, reader.fieldnames or []


def write_students(rows, fieldnames):
    if not fieldnames:
        return
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def apply_entry(row, entry, fieldnames):
    changed = False

    def set_if_missing(field, value):
        nonlocal changed
        if field in fieldnames and value and not row.get(field):
            row[field] = value
            changed = True

    if entry["server_id"] and not row.get("Server ID"):
        row["Server ID"] = entry["server_id"]
        changed = True
    if entry["username"] and row.get("Username") != entry["username"]:
        row["Username"] = entry["username"]
        changed = True

    set_if_missing("Full Name", entry["full_name"])
    set_if_missing("State", entry["state"])
    set_if_missing("School", entry["school"])
    set_if_missing("Gender", entry["gender"])
    set_if_missing("Used Discord", entry["used_discord"])
    set_if_missing("Form", entry["form"])
    set_if_missing("Timestamp", entry["timestamp"])
    set_if_missing("Invite Code", entry["invite_code"])

    if (
        "Join Method" in fieldnames
        and entry["invite_code"]
        and (not row.get("Join Method") or row["Join Method"] == "Existing")
    ):
        row["Join Method"] = entry["invite_code"]
        changed = True

    return changed


def build_row(discord_id, entry, fieldnames):
    row = {field: "" for field in fieldnames}
    row["Discord ID"] = discord_id
    row["Username"] = entry["username"]
    row["Server ID"] = entry["server_id"]
    row["Join Method"] = entry["invite_code"] or "Existing"
    row["Full Name"] = entry["full_name"]
    row["State"] = entry["state"]
    row["School"] = entry["school"]
    row["Gender"] = entry["gender"]
    row["Used Discord"] = entry["used_discord"]
    row["Form"] = entry["form"]
    row["Timestamp"] = entry["timestamp"]
    if "Invite Code" in fieldnames:
        row["Invite Code"] = entry["invite_code"]
    return row


def merge_student_info_from_legacy():
    legacy = load_legacy_student_info()
    if not legacy:
        return
    rows, fieldnames = load_students()
    if not fieldnames:
        return

    id_index = {row.get("Discord ID", ""): row for row in rows if row.get("Discord ID")}
    username_index = {}
    for row in rows:
        uname = (row.get("Username") or "").strip().lower()
        if uname:
            username_index.setdefault(uname, []).append(row)

    changed = False

    for discord_id, entries in legacy.items():
        if not entries:
            continue
        preferred_entry = entries[0]
        target_row = id_index.get(discord_id)
        if target_row:
            preferred_entry = next(
                (e for e in entries if e["server_id"] and e["server_id"] == target_row.get("Server ID")),
                preferred_entry,
            )
        else:
            uname = (preferred_entry["username"] or "").lower()
            candidates = username_index.get(uname, [])
            if candidates:
                target_row = candidates[0]
                preferred_entry = next(
                    (e for e in entries if e["server_id"] and e["server_id"] == target_row.get("Server ID")),
                    preferred_entry,
                )
        if target_row:
            if discord_id and not target_row.get("Discord ID"):
                target_row["Discord ID"] = discord_id
                id_index[discord_id] = target_row
                changed = True
            if apply_entry(target_row, preferred_entry, fieldnames):
                changed = True
            continue

        new_row = build_row(discord_id or "", preferred_entry, fieldnames)
        rows.append(new_row)
        if new_row.get("Discord ID"):
            id_index[new_row["Discord ID"]] = new_row
        uname = (preferred_entry["username"] or "").strip().lower()
        if uname:
            username_index.setdefault(uname, []).append(new_row)
        changed = True

    if changed:
        write_students(rows, fieldnames)


merge_student_info_from_legacy()
