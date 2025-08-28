#Survey

import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio 
#import aiofiles #AI said this is better for async file operations, maybe not needed anymore, we want to save to gspreadsheet
import webserver

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Keep a cache of invites
invite_cache = {}

@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")
    for guild in bot.guilds:
        invite_cache[guild.id] = await guild.invites()

#Detect if a user sends a message with the word "shit" or other banned words
banned_words = ["shit", "sh!t","fuck", "sohai"]

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content_lower = message.content.lower()
    if any(bad in content_lower for bad in banned_words):
        await message.delete()
        await message.channel.send(f"That's not a nice word! Please refrain from using offensive language.")
        #await message.author.send(f"Your message was deleted because it contained inappropriate language: {message.content}")

    await bot.process_commands(message)

# Command to create a Student Info Poll
# List of schools (customize this list)
# List of schools
STATE_SCHOOLS = {
    "Negeri Sembilan": [
        "Permata Insan"
    ],
    "Kuala Lumpur": [
        "Bandar Tun Razak",
        "Tutors in Action",
        "Desa Petaling",
        "Sri Eden"
    ],
    "Sarawak": [
        "St. Joseph",
        "St. Theresa",
        "Swinburne",
        "Sg Tapang"
    ],
    "Kedah": [
        "Keat Hwa"
    ],
    "Selangor": [
        "Puchong Utama 1"
    ],
    "NGO": [
        "Tutor in Action",
        "Sri Eden"
    ],
    "University": [
        "Swinburne Uni"
    ]
}

STATES = list(STATE_SCHOOLS.keys())

# === Reusable Question Helper ===
async def ask_question(member, question_text, options, timeout=60):
    """
    Ask a question via DM with emoji options and wait for a valid response.
    options: List of (emoji, option_text)
    Returns: option_text (or None if timed out)
    """
    option_text = "\n".join([f"{emoji} {text}" for emoji, text in options])
    msg = await member.send(f"{question_text}\n\n{option_text}")

    for emoji, _ in options:
        await msg.add_reaction(emoji)

    def check(reaction, user):
        return user == member and reaction.message.id == msg.id and str(reaction.emoji) in dict(options)

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=timeout, check=check)
        return dict(options)[str(reaction.emoji)]
    except asyncio.TimeoutError:
        await member.send("⏳ You didn’t respond in time!")
        return None

# === Ask for Text Response ===
async def ask_text_response(member, prompt, max_length=64, timeout=60):
    await member.send(f"{prompt}\n\n✏️ Please reply with your answer (max {max_length} characters).")

    def check(message):
        return message.author == member and isinstance(message.channel, discord.DMChannel)

    try:
        msg = await bot.wait_for("message", timeout=timeout, check=check)
        if len(msg.content) > max_length:
            await member.send(f"⚠️ Your message was too long. Please keep it under {max_length} characters.")
            return await ask_text_response(member, prompt, max_length, timeout)
        return msg.content
    except asyncio.TimeoutError:
        await member.send("⏳ You didn’t reply in time!")
        return None


# === Main Poll Function ===
async def studentInfo(member):
    try:
        # 1. Ask for State
        state_emojis = [chr(0x1F1E6 + i) for i in range(len(STATES))]  # 🇦, 🇧, ...
        state_options = list(zip(state_emojis, STATES))
        selected_state = await ask_question(member, "Hi, RakanBot here, could you please answer a few questions for us? Thank you!\n📍 Choose which best represents your school (if you're from an NGO/Uni, choose that)", state_options)
        if not selected_state:
            return

        # 2. Ask for School
        schools = STATE_SCHOOLS[selected_state]
        school_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        school_options = list(zip(school_emojis[:len(schools)], schools))
        selected_school = await ask_question(member, f"🏫 Select your **school** in {selected_state}:", school_options)
        if not selected_school:
            return

        # 3. Ask for Gender
        gender_options = [("1️⃣", "Male"), ("2️⃣", "Female")]
        selected_gender = await ask_question(member, "👤 Please select your **gender**:", gender_options)
        if not selected_gender:
            return
        
        # 4. Ask for Nickname
        student_nickname = await ask_text_response(member, "📝 Please give us your full name")
        if not student_nickname:
            return  # exits if timeout or failure
        
        # Ask if used Discord before
        yes_no = [("👍", "Yes"), ("👎", "No")]
        used_discord_response = await ask_question(member, "❓ Have you used Discord before? (If unsure, select 'No')", yes_no)
        if not used_discord_response:
            return  # exits if timeout or failure
        used_discord = used_discord_response == "Yes"


        # Ask for Form (e.g., Form 1, Form 2, etc., or Other)
        form_options = [
            ("1️⃣", "Form 1"),
            ("2️⃣", "Form 2"),
            ("3️⃣", "Form 3"),
            ("4️⃣", "Form 4"),
            ("5️⃣", "Form 5"),
            ("6️⃣", "Form 6"),
            ("❓", "Other")
        ]
        selected_form = await ask_question(member, "🎓 What is your current **Form** (year/grade)?", form_options)
        if selected_form == "Other":
            selected_form = await ask_text_response(member, "📝 Please specify your current Form (year/grade)")
        if not selected_form:
            return

        # Get Malaysia time (UTC+8)
        from datetime import datetime, timedelta, timezone
        malaysia_tz = timezone(timedelta(hours=8))
        timestamp = datetime.now(malaysia_tz).strftime('%Y-%m-%d %H:%M:%S')

        # --------- Get user's discord join method ---------------------------
        used_invite_code = None
        if hasattr(member, 'guild') and member.guild is not None:
            invites_before = invite_cache.get(member.guild.id, [])
            invites_after = await member.guild.invites()

            for after in invites_after:
                before = next((i for i in invites_before if i.code == after.code), None)
                if before and before.uses < after.uses:
                    used_invite_code = after.code
                    break
            # Update cache
            invite_cache[member.guild.id] = invites_after
        # ---------------------------------------------------------------------

        #save user data
        import RakanSheets  # Assuming you have a module for Google Sheets integration
        RakanSheets.save_to_google_sheets([[student_nickname, member.name, member.id, selected_state, selected_school, selected_gender, used_discord, selected_form, timestamp, used_invite_code]])
        await member.send("✅ Thank you for providing your information! Your data has been saved successfully.")
            
        
    except discord.Forbidden:
        print(f"❌ Couldn't DM {member.name}. They probably have DMs disabled.")

# === Trigger on New Join ===
@bot.event
async def on_member_join(member):
    try:
        await member.send("👋 Welcome to the server! Please take a moment to fill out your demographic information.")
        await studentInfo(member)
    except discord.Forbidden:
        print(f"❌ Couldn't DM {member.name} on join.")

# === Manual Command Trigger ===
@bot.command(name="studentInfo")
async def student_info_command(ctx):
    await studentInfo(ctx.author)

webserver.keep_alive()  # Start the web server to keep the bot alive
bot.run(token, log_handler=handler, log_level=logging.DEBUG) 

#Use venv38: "venv38\Scripts\Activate.ps1"    
#Pyinstaller guide for running on local old PC: Using pyenv, 3.8.0, need win32 version; might need to delete "dist or build"
# Run this: C:\Users\Aiden\.pyenv\pyenv-win\versions\3.8.0\python.exe -m PyInstaller main.py

