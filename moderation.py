"""
Moderation Cog — lightweight bad-word filter.

Deletes messages containing blacklisted words and warns the author.
"""

import discord
from discord.ext import commands

from config import BAD_WORDS_EN, BAD_WORDS_ID


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        content_lower = message.content.lower()

        if any(word in content_lower for word in BAD_WORDS_EN):
            await message.delete()
            await message.channel.send(
                "That's not a nice word! Please refrain from using offensive language."
            )
            return

        if any(word in content_lower for word in BAD_WORDS_ID):
            await message.delete()
            await message.channel.send(
                "Itu bukan kata yang baik! Tolong hindari menggunakan bahasa kasar."
            )
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
