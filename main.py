# Survey Bot with English + Indonesian Support

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
import uuid
import discord
import datetime

#AI Community manager dependencies
from groq import Groq
import json

#News Fetching dependencies
from fetch_news import fetch_news_with_content_exa

load_dotenv()
Discord_token = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Server IDs
ENGLISH_SERVER_ID = 1345397894030557234
INDONESIAN_SERVER_ID = 1405443776083918900
bad_words_en = ["shit", "fuck", "bitch", "sohai", "babi"]  # Example English list
bad_words_id = ["bangsat", "kontol", "memek", "goblok", "anjir"]  # Example Indonesian list

# Keep a cache of invites
invite_cache = {}

@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")
    for guild in bot.guilds:
        invite_cache[guild.id] = await guild.invites()

# Bad word filter
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check for English bad words
    if any(word in message.content.lower() for word in bad_words_en):
        await message.delete()
        await message.channel.send("That's not a nice word! Please refrain from using offensive language.")

    # Check for Indonesian bad words
    if any(word in message.content.lower() for word in bad_words_id):
        await message.delete()
        await message.channel.send("Itu bukan kata yang baik! Tolong hindari menggunakan bahasa kasar.")

    await bot.process_commands(message)


# ==========================
# State + School Definitions
# ==========================
STATE_SCHOOLS = {
    ENGLISH_SERVER_ID: {
        "Negeri Sembilan": ["Permata Insan"],
        "Kuala Lumpur": ["Bandar Tun Razak", "Tutors in Action", "Desa Petaling", "Sri Eden"],
        "Sarawak": ["St. Joseph", "St. Theresa", "Swinburne", "Sg Tapang"],
        "Kedah": ["Keat Hwa"],
        "Selangor": ["Puchong Utama 1"],
        "NGO": ["Tutor in Action", "Sri Eden"],
        "University": ["Swinburne Uni"]
    },
    INDONESIAN_SERVER_ID: {
        "DKI Jakarta": ["SMAN 40 Jakarta", "SMAN 72 Jakarta", "SMKN 4 Jakarta", "SMKN 12 Jakarta", "SMKN 31 Jakarta"],
        "Jawa Barat": ["SMKN 15 Bandung", "SMKN 4 Bandung", "SMKN 10 Bandung", "SMAN 1 Cililin"],
        "Jawa Timur": ["SMAN 1 Sugihwaras", "SMAN 15 Surabaya", "SMAN 8 Surabaya", "SMAN 2 Surabaya", "SMKN 1 Kamal"]
    }
}


# ======================
# Message Translations
# ======================
MESSAGES = {
    ENGLISH_SERVER_ID: {
        "welcome": "👋 Welcome to the server! Please take a moment to fill out your demographic information.",
        "intro": "Hi, RakanBot here, could you please answer a few questions for us? Thank you!\n📍 Choose which best represents your school (if you're from an NGO/Uni, choose that)",
        "choose_school": "🏫 Select your **school** in {state}:",
        "choose_gender": "👤 Please select your **gender**:",
        "full_name": "📝 Please give us your full name",
        "discord_used": "❓ Have you used Discord before? (If unsure, select 'No')",
        "form": "🎓 What is your current **Form** (year/grade)?",
        "form_other": "📝 Please specify your current Form (year/grade)",
        "thanks": "✅ Thank you for providing your information! Your data has been saved successfully.",
        "timeout1": "⏳ You didn’t react in time!",
        "timeout2": "⏳ You didn’t reply in time!",
        "name": "{prompt}\n\n✏️ Please reply with your answer (max {max_length} characters).",
        "maxlength": "⚠️ Your message was too long. Please keep it under {max_length} characters.",
        "forbidden1": "❌ Couldn't DM {member.name}. They probably have DMs disabled.",
        "forbidden2": "❌ Couldn't add reaction to message. Missing permissions."
    },
    INDONESIAN_SERVER_ID: {
        "welcome": "👋 Selamat datang di server! Mohon luangkan waktu untuk mengisi informasi demografi Anda.",
        "intro": "Halo, saya RakanBot. Bisakah Anda menjawab beberapa pertanyaan untuk kami? Terima kasih!\n📍 Pilih yang paling sesuai dengan sekolah Anda (jika Anda dari NGO/Universitas, pilih itu)",
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
        "forbidden1": "❌ Tidak dapat mengirim DM ke {member.name}. Mungkin mereka menonaktifkan DMs.",
        "forbidden2": "❌ Tidak dapat menambahkan reaksi ke pesan. Izin hilang."
    }
}


# ======================
# Question Helpers
# ======================
async def ask_question(member, guild_id, question_text, options, timeout=60):
    messages = MESSAGES[guild_id]
    option_text = "\n".join([f"{emoji} {text}" for emoji, text in options])
    msg = await member.send(f"{question_text}\n\n{option_text}")

    for emoji, _ in options:
        try:
            await msg.add_reaction(emoji)
        except discord.Forbidden:
            print(messages["forbidden2"].format(member=member))

    def check(reaction, user):
        return user == member and reaction.message.id == msg.id and str(reaction.emoji) in dict(options)

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=timeout, check=check)
        return dict(options)[str(reaction.emoji)]
    except asyncio.TimeoutError:
        await member.send(messages["timeout1"])
        return None


async def ask_text_response(member, guild_id, prompt, max_length=64, timeout=60):
    messages = MESSAGES[guild_id]
    await member.send(messages["name"].format(prompt=prompt, max_length=max_length))

    def check(message):
        return message.author == member and isinstance(message.channel, discord.DMChannel)
    
    while True:
     try:
        msg = await bot.wait_for("message", timeout=timeout, check=check)
        if len(msg.content) <= max_length:
            return msg.content
        await member.send(messages["maxlength"].format(max_length=max_length))
     except asyncio.TimeoutError:
        await member.send(messages["timeout2"])
        return None

#Create role / add role helper
async def get_or_create_role(guild, role_name):
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        role = await guild.create_role(name=role_name)
    return role

# ======================
# Main Student Info Flow
# ======================
async def studentInfo(member, guild_id):
    try:
        messages = MESSAGES[guild_id]
        state_schools = STATE_SCHOOLS[guild_id]

        # 1. Ask for State
        STATES = list(state_schools.keys())
        state_emojis = [chr(0x1F1E6 + i) for i in range(len(STATES))]  # 🇦, 🇧, ...
        state_options = list(zip(state_emojis, STATES))
        selected_state = await ask_question(member, guild_id, messages["intro"], state_options)
        if not selected_state:
            return

        # 2. Ask for School
        schools = state_schools[selected_state]
        school_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        school_options = list(zip(school_emojis[:len(schools)], schools))
        selected_school = await ask_question(member, guild_id, messages["choose_school"].format(state=selected_state), school_options)
        if not selected_school:
            return

        # 3. Ask for Gender
        gender_options = [("1️⃣", "Male" if guild_id == ENGLISH_SERVER_ID else "Laki-laki"),
                          ("2️⃣", "Female" if guild_id == ENGLISH_SERVER_ID else "Perempuan")]
        selected_gender = await ask_question(member, guild_id, messages["choose_gender"], gender_options)
        if not selected_gender:
            return

        # 4. Ask for Name
        student_name = await ask_text_response(member, guild_id, messages["full_name"])
        if not student_name:
            return

        # 5. Discord Used?
        yes_no = [("👍", "Yes" if guild_id == ENGLISH_SERVER_ID else "Ya"),
                  ("👎", "No" if guild_id == ENGLISH_SERVER_ID else "Tidak")]
        used_discord_response = await ask_question(member, guild_id, messages["discord_used"], yes_no)
        if not used_discord_response:
            return
        used_discord = used_discord_response in ["Yes", "Ya"]

        # 6. Form
        form_options = [
            ("1️⃣", "Form 1" if guild_id == ENGLISH_SERVER_ID else "13 tahun"),
            ("2️⃣", "Form 2" if guild_id == ENGLISH_SERVER_ID else "14 tahun"),
            ("3️⃣", "Form 3" if guild_id == ENGLISH_SERVER_ID else "15 tahun"),
            ("4️⃣", "Form 4" if guild_id == ENGLISH_SERVER_ID else "16 tahun"),
            ("5️⃣", "Form 5" if guild_id == ENGLISH_SERVER_ID else "17 tahun"),
            ("6️⃣", "Form 6" if guild_id == ENGLISH_SERVER_ID else "18 tahun"),
            ("❓", "Other" if guild_id == ENGLISH_SERVER_ID else "Lainnya")
        ]
        selected_form = await ask_question(member, guild_id, messages["form"], form_options)
        if selected_form in ["Other", "Lainnya"]:
            selected_form = await ask_text_response(member, guild_id, messages["form_other"])
        if not selected_form:
            return

        # Save to Sheets
        from datetime import datetime, timedelta, timezone
        malaysia_tz = timezone(timedelta(hours=8))
        timestamp = datetime.now(malaysia_tz).strftime('%Y-%m-%d %H:%M:%S')

        used_invite_code = None
        if hasattr(member, 'guild') and member.guild is not None:
            invites_before = invite_cache.get(member.guild.id, [])
            invites_after = await member.guild.invites()
            for after in invites_after:
                before = next((i for i in invites_before if i.code == after.code), None)
                if before and before.uses < after.uses:
                    used_invite_code = after.code
                    break
            invite_cache[member.guild.id] = invites_after

        import RakanSheets
        RakanSheets.save_to_google_sheets([[student_name, member.name, member.id, selected_state, selected_school, selected_gender, used_discord, selected_form, timestamp, used_invite_code, guild_id]])
        await member.send(messages["thanks"])

    except discord.Forbidden:
        print(messages["forbidden1"].format(member=member))


# ======================
# Event Triggers
# ======================
@bot.event
async def on_member_join(member):
    guild_id = member.guild.id
    if guild_id not in MESSAGES:
        return
    try:
        await member.send(MESSAGES[guild_id]["welcome"])
        await studentInfo(member, guild_id)
    except discord.Forbidden:
        print(MESSAGES[guild_id]["forbidden2"].format(member=member))


@bot.command(name="studentInfo")
async def student_info_command(ctx):
    await studentInfo(ctx.author, ctx.guild.id)


#==============================================
# AI Community Manager Integration
#==============================================

load_dotenv()
token = os.getenv('GROQ_API_KEY')

with open("Sys_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

client = Groq(
    api_key=token, 
)

def generate_engagement_question():
    # Fetch recent news (returns list of dicts)
    news_results = fetch_news_with_content_exa(query="Recent news", location="Malaysia", num_results=3, max_characters=500)
    # Combine news snippets/titles for the prompt
    news_summaries = []
    for item in news_results:
        title = item.get("title", "")
        content = item.get("text", "")
        news_summaries.append(f"{title}: {content}")
    news_context = "\n".join(news_summaries) if news_summaries else "No recent news found."

    ENGAGEMENT_PROMPT = (
        "You are an AI tutor. Here is some recent news:\n"
        f"{news_context}\n"
        "First, only choose ONE news to cover briefly. Then explain the news in simple terms for students. "
        "Then, ask one creative, open-ended question about AI or machine learning connected to it. "
        "Keep it under 2000 characters, preferably around 1000."
    )
    messages = [
        {"role": "system", "content": ENGAGEMENT_PROMPT},
        {"role": "user", "content": "Explain the news simply, then ask one related AI/ML question."}
    ]

    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        temperature=1.2
    )
    return chat_completion.choices[0].message.content

def generate_engagement_question_indonesian():
    # Ambil berita terbaru (mengembalikan list of dicts)
    news_results = fetch_news_with_content_exa(query="Berita AI", location="Indonesia", num_results=3, max_characters=500)
    # Gabungkan ringkasan berita/judul untuk prompt
    news_summaries = []
    for item in news_results:
        title = item.get("title", "")
        content = item.get("text", "")
        news_summaries.append(f"{title}: {content}")
    news_context = "\n".join(news_summaries) if news_summaries else "Tidak ada berita terbaru yang ditemukan."

    ENGAGEMENT_PROMPT = (
        "Anda adalah seorang tutor AI. Berikut adalah beberapa berita terbaru:\n"
        f"{news_context}\n"
        "Pertama, pilih hanya SATU berita untuk dibahas secara singkat. Kemudian jelaskan berita tersebut dengan sederhana untuk siswa. "
        "Setelah itu, ajukan satu pertanyaan kreatif dan terbuka tentang AI atau machine learning yang berhubungan dengan berita tersebut. "
        "Jaga agar jawaban di bawah 2000 karakter, idealnya sekitar 1000 karakter. Tulis dalam Bahasa Indonesia."
    )
    messages = [
        {"role": "system", "content": ENGAGEMENT_PROMPT},
        {"role": "user", "content": "Jelaskan berita tersebut dengan sederhana, lalu ajukan satu pertanyaan AI/ML yang relevan."}
    ]

    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        temperature=1.2
    )
    return chat_completion.choices[0].message.content

# Just a function to get answers from LLM with system prompt
with open("Sys_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

def LLM(user_input):  # Takes in text/Json, appends sys prompt
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ],
        model="llama-3.3-70b-versatile",
    )
    assistant_message = chat_completion.choices[0].message.content
    return assistant_message

# ============================== Engagement system ==============================
ENGAGE_ACTIVITY_FILE = "engage_activity.json"

def load_engage_activity():
    if os.path.exists(ENGAGE_ACTIVITY_FILE):
        with open(ENGAGE_ACTIVITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_engage_activity(activity):
    with open(ENGAGE_ACTIVITY_FILE, "w", encoding="utf-8") as f:
        json.dump(activity, f, ensure_ascii=False, indent=2)

engage_activity = load_engage_activity()
engage_questions_by_id = {}

@bot.command(name="engage")
async def engage(ctx):
    # Notification line based on language
    if ctx.guild.id == ENGLISH_SERVER_ID:
        notif_line = "If you enjoy these challenges, react to this message to get notified of more!"
    else:
        notif_line = "Jika kamu suka tantangan seperti ini, beri reaksi pada pesan ini untuk mendapatkan notifikasi tantangan berikutnya!"

    # Get or create the "enthusiast" role
    role = await get_or_create_role(ctx.guild, "enthusiast")
    # Send the role mention (ping)
    await ctx.send(f"{role.mention}")
    
    question = generate_engagement_question() if ctx.guild.id == ENGLISH_SERVER_ID else generate_engagement_question_indonesian()
    full_message = f"{question}\n\n{notif_line}"
    
    sent_msgs = []
    for i in range(0, len(full_message), 2000):
        sent_msg = await ctx.send(full_message[i:i+2000])
        sent_msgs.append(sent_msg)
    engage_entry = {
        "channel_id": str(ctx.channel.id),
        "question": question,
        "timestamp": str(sent_msgs[0].created_at),
        "message_id": str(sent_msgs[0].id),
        "responses": []
    }
    engage_activity.append(engage_entry)
    save_engage_activity(engage_activity)
    engage_questions_by_id[str(sent_msgs[0].id)] = engage_entry

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    message_id = str(reaction.message.id)
    if message_id in engage_questions_by_id:
        guild = reaction.message.guild
        if guild is None:
            return  # Only assign roles in guilds
        role = await get_or_create_role(guild, "enthusiast")
        member = guild.get_member(user.id)
        if member and role not in member.roles:
            await member.add_roles(role)
            try:
                await user.send("You've been given the 'enthusiast' role for engaging with the AI question!" if guild.id == ENGLISH_SERVER_ID else "Anda telah diberikan peran 'enthusiast' karena berinteraksi dengan pertanyaan AI!")
            except discord.Forbidden:
                pass  # Can't DM user

@bot.command(name="respond")
async def respond(ctx, *, answer: str):
    user_id = str(ctx.author.id)
    channel_id = str(ctx.channel.id)
    timestamp = str(ctx.message.created_at)
    replied_to_id = None
    if ctx.message.reference and ctx.message.reference.message_id:
        replied_to_id = str(ctx.message.reference.message_id)
    engage_entry = None
    if replied_to_id and replied_to_id in engage_questions_by_id:
        engage_entry = engage_questions_by_id[replied_to_id]
    else:
        for entry in reversed(engage_activity):
            if entry.get("channel_id") == channel_id and "question" in entry:
                engage_entry = entry
                break
    if not engage_entry:
        await ctx.send("No engage question found to group your response.")
        return

    # Add student response
    engage_entry.setdefault("responses", []).append({
        "user_id": user_id,
        "response": answer,
        "timestamp": timestamp
    })

    # Prepare LLM context: system prompt, question, last 8 responses
    messages = [
        {"role": "system", "content": "You are an AI tutor reviewing student engagement. Here is the question and student responses."},
        {"role": "user", "content": engage_entry["question"]}
    ] if ctx.guild.id == ENGLISH_SERVER_ID else [
        {"role": "system", "content": "Anda adalah seorang tutor AI yang meninjau keterlibatan siswa. Berikut adalah pertanyaan dan tanggapan siswa."},
        {"role": "user", "content": engage_entry["question"]}
    ]

    # Get the last 8 responses (excluding any previous assistant responses)
    user_responses = [r for r in engage_entry["responses"] if r.get("role", "user") == "user"]
    for resp in user_responses[-8:]:
        messages.append({"role": "user", "content": resp["response"]})

    # Call LLM
    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        temperature=1.0
    )
    llm_response = chat_completion.choices[0].message.content

    # Send LLM response to channel
    for i in range(0, len(llm_response), 2000):
        await ctx.send(llm_response[i:i+2000])

    # Save LLM response to engage_activity.json
    engage_entry["responses"].append({
        "role": "assistant",
        "response": llm_response,
        "timestamp": str(ctx.message.created_at)
    })
    save_engage_activity(engage_activity)
    await ctx.send("Your response and the AI's reply have been recorded!")

# -------------
# weekly reaction logger
# -------------
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# Initialize discord (i scared so i type whole thing again) 
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
import discord
from discord.ext import commands

# Create intents object
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

# Create bot with intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Create APScheduler
scheduler = AsyncIOScheduler()

# List of channels to track (since we wanna know more on student engagement so priority are the student-accessible channels/not admin ones)
CHANNEL_IDS_TO_TRACK = [
    1345397894030557238,  # general
    1363897375990747157,  # discussion
    1378669054285582427,  #ai-jokes and memes
    1349385352313442385,  #1a
    1351537746149244939,  #1b
    1349385520639381607,  #1c
    1349385551987478559,  #1d --will update the other modules in future
    1374554509845598228,  #further resources
    
]

# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = 'https://docs.google.com/spreadsheets/d/1m1X3-VW8dXwRe2-PCRhxKkHi_-fKLFzOqIKOgfwAg4k/edit?gid=0#gid=0'
RANGE_NAME = 'Sheet1!A2:K2'  # Adjust range from sheets

# Credentials for Google Sheets API
creds = Credentials.from_service_account_file('path-to-credentials.json', scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Function to append data to Google Sheets
def append_to_sheet(data):
    """Appends a row to the Google Sheet"""
    request = sheet.values().append(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
                                     valueInputOption="RAW", body={"values": [data]})
    response = request.execute()

# Event: Called when a user adds a reaction
@bot.event
async def weekly_log_reactions():
    # Loop through each guild (server) the bot is in
    for guild in bot.guilds:
        # Loop through only the channels in `CHANNEL_IDS_TO_TRACK`
        for channel in guild.text_channels:
            if channel.id in CHANNEL_IDS_TO_TRACK:  # Check if the channel is in the list
                try:
                    print(f"Fetching messages from channel: {channel.name}")
                    # Fetch the most recent 150 messages from the channel
                    messages = await channel.history(limit=150).flatten()

                    # Loop through each message
                    for message in messages:
                        # Check if the message has reactions
                        if message.reactions:
                            for reaction in message.reactions:
                                # Log each reaction (this can be customized to log to Google Sheets)
                                print(f"Logged reaction: {reaction.emoji} on message: {message.id} in channel {channel.name}")

                                # Retrieve necessary data from the reaction event
                                action_id = str(reaction.message.id) + str(reaction.emoji)
                                user_id = user.id
                                action_type = 'reaction_add'
                                channel_id = str(message.channel.id)
                                occurred_at = datetime.datetime.utcnow().isoformat()
                                message_id = str(message.id)
                                message_text = message.content
                                reaction_emoji = str(reaction.emoji)
                                url = message.jump_url  # URL of the message
                                bot_command = ''  # Placeholder for bot commands if any
                                created_at = datetime.datetime.utcnow().isoformat()

                                # Here you would replace this print with Google Sheets logging
                                data = [action_id, user_id, action_type, channel_id, occurred_at, message_id, message_text, 
                                        reaction_emoji, url, bot_command, created_at]
                                append_to_sheet(data)  # Replace this function with your Google Sheets code

                except Exception as e:
                    print(f"Error in channel {channel.name}: {e}")

# Schedule the task to run weekly
scheduler.add_job(weekly_log_reactions, 'interval', weeks=1, start_date=datetime.datetime.now())

# Discord bot event: Called when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    # Start the scheduler when the bot is ready
    scheduler.start()
    # check the channels in the server dynamically (just optional stuff)
    #for guild in client.guilds:
        #print(f"Connected to guild: {guild.name}")
        #for channel in guild.text_channels:
            #print(f"Channel: {channel.name}, Channel ID: {channel.id}")




bot.run(Discord_token)

#Use venv 32: .\myenv32\Scripts\Activate.ps1
#Pyinstaller guide for running on local old PC: Using pyenv, 3.8.0, need win32 version; might need to delete "dist or build"
# Run this: python -m PyInstaller main.py
# TAKE THE ONE IN DIST!
# USE WIN 32, since old PC is 32bit, you have to be in the venv running the 32 bit python

# to create the venv 32: C:\Users\Aiden\AppData\Local\Programs\Python\Python38-32\python.exe -m venv myenv32

#Current (1/9) LLM Version: Need to put in Sys_prompt.txt
'''
python -m PyInstaller main.py `
  "--add-data=myenv32\Lib\site-packages\setuptools\_vendor\jaraco\text\Lorem ipsum.txt;setuptools/_vendor/jaraco/text"
'''
