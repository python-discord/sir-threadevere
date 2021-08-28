import typing as t
from datetime import datetime

import discord
from aiohttp.client_exceptions import ClientResponseError
from discord.ext import commands

from bot import constants, logger
from bot.bot import ThreadBot
from bot.exts.ban_appeals import BASE_RESPONSE, _api_handlers, _models


class BanAppeals(commands.Cog):
    """Cog for creating and actioning ban appeals threads when a user appeals via forms."""

    def __init__(self, bot: ThreadBot) -> None:
        self.bot = bot
        self.appeal_channel: t.Optional[discord.TextChannel] = None
        self.cookies = {"token": constants.Secrets.forms_token}

        if constants.DEBUG_MODE:
            self.archive_time = constants.ThreadArchiveTimes.DAY.value
        else:
            self.archive_time = constants.ThreadArchiveTimes.WEEK.value

        self.init_task = self.bot.loop.create_task(self.init_cog())

    async def init_cog(self) -> None:
        """Initialise the ban appeals system."""
        logger.info("Waiting for the guild to be available before initialisation.")
        await self.bot.wait_until_guild_available()

        self.appeal_channel = self.bot.get_channel(constants.Channels.appeals)

    async def appeal_thread_check(self, ctx: commands.Context, messages: list[discord.Message]) -> bool:
        """Return True if channel is a Thread, in the appeal channel, with a first message sent from this bot."""
        await self.init_task
        if not isinstance(ctx.channel, discord.Thread):
            # Channel isn't a discord.Thread
            return False
        if not ctx.channel.parent == self.appeal_channel:
            # Thread parent channel isn't the appeal channel.
            return False
        if not messages or not messages[1].author == ctx.guild.me:
            # This aren't messages in the channel, or the first message isn't from this bot.
            # Ignore messages[0], as it refers to the parent message.
            return False
        if messages[1].content.startswith("Actioned"):
            # Ignore appeals that have already been actioned.
            return False
        return True

    @commands.has_any_role(*constants.MODERATION_ROLES, constants.Roles.core_developers)
    @commands.group(name="appeal", invoke_without_command=True)
    async def ban_appeal(self, ctx: commands.Context) -> None:
        """Ban group for the ban appeal commands."""
        await ctx.send_help(ctx.command)

    @commands.has_any_role(*constants.MODERATION_ROLES, constants.Roles.core_developers)
    @ban_appeal.command(name="test")
    async def embed_test(self, ctx: commands.Context) -> None:
        """Send a embed that mocks the ban appeal webhook."""
        await self.init_task

        embed = discord.Embed(
            title="New Form Response",
            description=f"{ctx.author.mention} submitted a response to `​Ban Appeals​`.",
            colour=constants.Colours.info,
            url="https://forms-api.pythondiscord.com/forms/ban-appeals/responses/7fbb1a2e-d910-44bb-bcc7-e9fcfd04f758"
        )
        embed.timestamp = datetime(year=2021, month=8, day=22, hour=12, minute=56, second=14)
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar.url)
        await self.appeal_channel.send("New ban appeal!", embed=embed)
        await ctx.message.add_reaction("✅")

    @commands.has_any_role(constants.Roles.admins)
    @ban_appeal.command(name="respond", aliases=("response",))
    async def appeal_respond(
        self,
        ctx: commands.Context,
        response: _models.AppealResponse,
        *,
        extras: t.Optional[str]
    ) -> None:
        """
        Respond to the appeal with the given response.

        `extras` can be given to add extra content to the email.
        You will be asked to confirm the full email before it is sent.
        """
        # Don't use a discord.py check to avoid fetching first message multiple times.
        messages = await ctx.channel.history(limit=2, oldest_first=True).flatten()
        if not await self.appeal_thread_check(ctx, messages):
            await ctx.message.add_reaction("❌")
            return
        thread_data_message = messages[1]
        response_uuid = thread_data_message.content.split(" ")[0]
        appeal_details: _models.AppealDetails = await _api_handlers.fetch_form_appeal_data(
            response_uuid,
            self.cookies,
            self.bot.http_session
        )

        email_response_content = BASE_RESPONSE.format(
            name=appeal_details.appealer,
            snippet=response,
            extras=f"\n\n{extras}" if extras else ""
        )
        await ctx.send(
            email_response_content,
            # This is commented out awaiting PyDis to get a new mail provider.
            # view=_models.ConfirmAppealResponse(thread_data_message, appeal_details.email)
        )

    @commands.Cog.listener(name="on_message")
    async def ban_appeal_listener(self, message: discord.Message) -> None:
        """Listens for ban appeal embeds to trigger the appeal process."""
        await self.init_task

        if not message.channel == self.appeal_channel:
            # Ignore messages not in the appeal channel
            return

        if not message.author.bot:
            # Ignore messages not from bots
            return

        if not message.embeds or len(message.embeds) != 1:
            # Ignore messages without extact 1 embed
            return

        appeal_details = await self.get_appeal_details_from_embed(message.embeds[0])

        thread: discord.Thread = await message.create_thread(
            name=appeal_details.thread_name,
            auto_archive_duration=self.archive_time
        )
        await thread.send(appeal_details)

    async def get_appeal_details_from_embed(self, embed: discord.Embed) -> _models.AppealDetails:
        """Extract a form response uuid from a ban appeal webhook message."""
        response_uuid = embed.url.split("/")[-1]
        try:
            return await _api_handlers.fetch_form_appeal_data(
                response_uuid,
                self.cookies,
                self.bot.http_session
            )
        except ClientResponseError as e:
            if e.status == 403:
                await self.appeal_channel.send(":x: Forms credentials are invalid, could not initiate appeal flow.")
                raise
