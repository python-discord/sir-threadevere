import re
import typing as t

import discord
from discord.ext import commands

from bot import constants, logger
from bot.bot import ThreadBot

NOMINATION_MESSAGE_REGEX = re.compile(
    r"<@!?\d+> \((.+)#\d{4}\) for Helper!\n\n\*\*Nominated by:\*\*",
    re.MULTILINE
)

# When nominations are posted manually, the Discord message box converts +1/-1 to the thumbs emojis
NOMINATION_ENDING_TEXT = "react 👍 for approval, or 👎 for disapproval*."


class Nominations(commands.Cog):
    """Cog for getting information about PyPi packages."""

    def __init__(self, bot: ThreadBot):
        self.bot = bot
        # Stores the name of the member recently posted nomination as,
        # nomiantion messages can be split into multiple messages.
        self.nominated_member_name: int = None

        if constants.DEBUG_MODE:
            self.archive_time = constants.ThreadArchiveTimes.DAY.value
        else:
            self.archive_time = constants.ThreadArchiveTimes.WEEK.value

    async def get_thread_from_message_id(self, message_id: int, channel_id: int) -> t.Optional[discord.Thread]:
        """Returns the thread linked to the given message id."""
        channel: discord.TextChannel = self.bot.get_channel(channel_id)

        for thread in await channel.active_threads():
            messages = await thread.history(limit=1, oldest_first=True).flatten()
            if messages[0].reference.message_id == message_id:
                return thread
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Creates a thread whenever a vote is sent in the nominations voting channel."""
        if message.channel.id != constants.Channels.nomination_voting:
            return  # Ignore messages not in voting channel.

        if match := NOMINATION_MESSAGE_REGEX.match(message.content):
            self.nominated_member_name = match.group(1)

        if not message.content.endswith(NOMINATION_ENDING_TEXT):
            # Only create thread on final message, as a vote could be split into multiple messages.
            return
        elif not self.nominated_member_name:
            logger.error("Valid end message found, but no cached member name to create thread!")

        thread = await message.start_thread(
            name=f"Nomination - {self.nominated_member_name}",
            auto_archive_duration=self.archive_time
        )
        logger.info(f"Created thread {thread.name}")
        self.nominated_user_id = None
        await thread.send(f"<@&{constants.Roles.mod_team}> <@&{constants.Roles.admins}>")
        self.bot.stats.incr("thread.nomination.open")

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Archives a thread linked to a nomination vote when the nomination is archived."""
        message_id, channel_id = payload.message_id, payload.channel_id

        if channel_id != constants.Channels.nomination_voting:
            return  # Ingore messages deleted in other channels

        channel: discord.TextChannel = self.bot.get_channel(channel_id)
        thread = await get_thread_from_message_id(message_id, channel, self.bot.cached_messages)
        if not thread:
            logger.info(f"Could not find a thread linked to {channel_id}-{message_id}")
            return

        logger.info(f"Archiving thread {thread.name}")
        await thread.edit(archived=True)
        self.bot.stats.incr("thread.nomination.archive")


def setup(bot: ThreadBot) -> None:
    """Load the Nominations cog."""
    bot.add_cog(Nominations(bot))
