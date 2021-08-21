import re
from typing import Optional

import discord
from discord.ext import commands

from bot import constants, logger
from bot.bot import ThreadBot
from bot.utils.helpers import get_thread_from_message_id

NOMINATION_MESSAGE_REGEX = re.compile(
    r"<@!?\d+> \((.+)#\d{4}\) for Helper!\n\n\*\*Nominated by:\*\*",
    re.MULTILINE
)

# When nominations are posted manually, the Discord message box standarises the unicode emojis to :thumbsup:
NOMINATION_ENDING_TEXT = "react 👍 for approval, or 👎 for disapproval*."


class Nominations(commands.Cog):
    """Cog for creating and archiving nomination threads when votes are posted/archived."""

    def __init__(self, bot: ThreadBot) -> None:
        self.bot = bot
        # Temporarily stores the name of the member who's vote just got posted.
        # Need to cache this as votes can span multiple messages (due to long nomination reasons).
        self.nominated_member_name: Optional[str] = None

        if constants.DEBUG_MODE:
            self.archive_time = constants.ThreadArchiveTimes.DAY.value
        else:
            self.archive_time = constants.ThreadArchiveTimes.WEEK.value

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Create a thread on votes sent in the nominations voting channel."""
        if message.channel.id != constants.Channels.nomination_voting:
            return  # Ignore messages not in the voting channel

        if match := NOMINATION_MESSAGE_REGEX.match(message.content):
            if self.nominated_member_name:
                logger.error("New vote found, but we still have a name cached! Did two votes come in at the same time?")
            self.nominated_member_name = match.group(1)

        if not message.content.endswith(NOMINATION_ENDING_TEXT):
            return  # Votes could be split into multiple messages, create the thread on the final message
        elif not self.nominated_member_name:
            logger.error("Valid end message found, but no cached member name to create thread!")

        thread = await message.create_thread(
            name=f"Nomination - {self.nominated_member_name}",
            auto_archive_duration=self.archive_time
        )
        logger.info(f"Created thread {thread.name}")
        self.nominated_user_id = None
        await thread.send(fr"<@&{constants.Roles.mod_team}> <@&{constants.Roles.admins}>")
        self.bot.stats.incr("thread.nomination.open")

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Archive threads linked to nomination votes when the vote is archived."""
        message_id, channel_id = payload.message_id, payload.channel_id

        if channel_id != constants.Channels.nomination_voting:
            return  # Ignore messages deleted in other channels

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
