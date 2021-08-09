import re

import discord
from discord.ext import commands

from bot import constants
from bot.bot import ThreadBot

NOMINATION_MESSAGE_REGEX = re.compile(
    fr"<@(\d+)> \(.+#\d{4}\) for Helper!\n\n"
    "**Nominated by:**"
)
NOMINATION_ENDING_TEXT = "react :+1: for approval, or :-1: for disapproval*."


class Nominations(commands.Cog):
    """Cog for getting information about PyPi packages."""

    def __init__(self, bot: ThreadBot):
        self.bot = bot
        # Stores the user id of the recently posted nomination as,
        # nomiantion messages can be split into multiple messages.
        self.nominated_user_id: int = None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Creates a thread whenever a vote is sent in the nominations voting channel."""
        if not message.author.bot:
            return  # Ignore messages not sent by bots.

        if message.channel.id != constants.Channels.nomination_voting:
            return  # Ignore messages not in voting channel.

        if match := NOMINATION_MESSAGE_REGEX.match(message.content):
            self.nominated_user_id = match.group(1)

        if not message.content.endswith(NOMINATION_ENDING_TEXT):
            # Only create thread on final message, as a vote could be split into multiple messages.
            return

        thread = await message.start_thread(
            name=f"Nomination - {message.guild.get_member(self.nominated_user_id).nick}",
            auto_archive_duration=1440
        )
        self.nominated_user_id = None
        await thread.send(f"<@&{constants.Roles.mod_team}> <@&{constants.Roles.admins}>")
        self.bot.stats.incr("thread.nomination.open")


def setup(bot: ThreadBot) -> None:
    """Load the Nominations cog."""
    bot.add_cog(Nominations(bot))
