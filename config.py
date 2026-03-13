"""
Shared constants: server IDs, school mappings, translations, bad-word lists.
All config lives here so every other module imports from one place.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Discord credentials ──────────────────────────────────────────────
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")

# ── Supabase ──────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
DISABLE_SUPABASE: bool = os.getenv("DISABLE_SUPABASE", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def get_supabase():
    """Return a Supabase client (lazy import so the package is optional at startup)."""
    if DISABLE_SUPABASE:
        raise RuntimeError("Supabase is disabled (DISABLE_SUPABASE=1).")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_KEY is missing.")
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Server IDs ────────────────────────────────────────────────────────
ENGLISH_SERVER_ID = 1345397894030557234
INDONESIAN_SERVER_ID = 1405443776083918900

# ── Owner IDs (notified on errors) ───────────────────────────────────
OWNER_IDS = [484723983900737538, 1346839447995420749]

# ── Data collection settings ──────────────────────────────────────────
# Channel IDs / names to skip when running !collect_all or auto-collection.
EXCLUDED_CHANNEL_IDS: set[int] = {
    1351929278672932935,
    1346622879814385818,
    1394922620423770292,
    1349396038917689415,
    1389347115469242532,
}
EXCLUDED_CHANNEL_NAMES: set[str] = set()

# 0 = no limit (process every channel)
COLLECTION_CHANNEL_LIMIT = 0

# ── Bad-word lists ────────────────────────────────────────────────────
BAD_WORDS_EN = ["shit", "fuck", "bitch", "sohai", "babi", "sh!t"]
BAD_WORDS_ID = ["bangsat", "kontol", "memek", "goblok", "anjir"]

# ── State → School mappings (per server) ─────────────────────────────
STATE_SCHOOLS = {
    ENGLISH_SERVER_ID: {
        "Negeri Sembilan": ["Permata Insan"],
        "Kuala Lumpur": ["Bandar Tun Razak", "Tutors in Action", "Desa Petaling", "Sri Eden"],
        "Sarawak": ["St. Joseph", "St. Theresa", "Swinburne", "Sg Tapang"],
        "Kedah": ["Keat Hwa"],
        "Selangor": ["Puchong Utama 1"],
        "NGO": ["Tutor in Action", "Sri Eden", "Teacher"],
        "University": ["Swinburne Uni"],
    },
    INDONESIAN_SERVER_ID: {
        "DKI Jakarta": ["SMAN 40 Jakarta", "SMAN 72 Jakarta", "SMKN 4 Jakarta", "SMKN 12 Jakarta", "SMKN 31 Jakarta"],
        "Jawa Barat": ["SMKN 15 Bandung", "SMKN 4 Bandung", "SMKN 10 Bandung", "SMAN 1 Cililin"],
        "Jawa Timur": ["SMAN 1 Sugihwaras", "SMAN 15 Surabaya", "SMAN 8 Surabaya", "SMAN 2 Surabaya", "SMKN 1 Kamal"],
    },
}

# ── Translated UI messages (per server) ──────────────────────────────
MESSAGES = {
    ENGLISH_SERVER_ID: {
        "welcome": "👋 Welcome to the server! Please take a moment to fill out your demographic information.",
        "intro": (
            "Hi, RakanBot here, could you please answer a few questions for us? Thank you!\n"
            "📍 Choose which best represents your school (if you're from an NGO/Uni, choose that)"
        ),
        "choose_school": "🏫 Select your **school** in {state}:",
        "choose_gender": "👤 Please select your **gender**:",
        "full_name": "📝 Please give us your full name",
        "discord_used": "❓ Have you used Discord before? (If unsure, select 'No')",
        "form": "🎓 What is your current **Form** (year/grade)?",
        "form_other": "📝 Please specify your current Form (year/grade)",
        "thanks": "✅ Thank you for providing your information! Your data has been saved successfully.",
        "timeout1": "⏳ You didn't react in time!",
        "timeout2": "⏳ You didn't reply in time!",
        "name": "{prompt}\n\n✏️ Please reply with your answer (max {max_length} characters).",
        "maxlength": "⚠️ Your message was too long. Please keep it under {max_length} characters.",
        "forbidden1": "❌ Couldn't DM {member_name}. They probably have DMs disabled.",
        "forbidden2": "❌ Couldn't add reaction to message. Missing permissions.",
    },
    INDONESIAN_SERVER_ID: {
        "welcome": "👋 Selamat datang di server! Mohon luangkan waktu untuk mengisi informasi demografi Anda.",
        "intro": (
            "Halo, saya RakanBot. Bisakah Anda menjawab beberapa pertanyaan untuk kami? Terima kasih!\n"
            "📍 Pilih yang paling sesuai dengan sekolah Anda (jika Anda dari NGO/Universitas, pilih itu)"
        ),
        "choose_school": "🏫 Pilih **sekolah** Anda di {state}:",
        "choose_gender": "👤 Silakan pilih **jenis kelamin** Anda:",
        "full_name": "📝 Mohon berikan nama lengkap Anda",
        "discord_used": "❓ Apakah Anda pernah menggunakan Discord sebelumnya? (Jika ragu, pilih 'Tidak')",
        "form": "🎓 Anda sekarang berada di **kelas** berapa?",
        "form_other": "📝 Mohon sebutkan kelas/tingkat Anda saat ini",
        "thanks": "✅ Terima kasih telah memberikan informasi Anda! Data Anda berhasil disimpan.",
        "timeout1": "⏳ Anda tidak bereaksi tepat waktu!",
        "timeout2": "⏳ Anda tidak membalas tepat waktu!",
        "name": "{prompt}\n\n✏️ Silakan balas dengan jawaban Anda (maks {max_length} karakter).",
        "maxlength": "⚠️ Pesan anda terlalu panjang. Harap jaga agar tetap di bawah {max_length} karakter.",
        "forbidden1": "❌ Tidak dapat mengirim DM ke {member_name}. Mungkin mereka menonaktifkan DMs.",
        "forbidden2": "❌ Tidak dapat menambahkan reaksi ke pesan. Izin hilang.",
    },
}
