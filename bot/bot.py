import asyncio
import logging
import socket

import discord
from discord import Embed
from discord.ext import commands

from bot import async_stats, constants

log = logging.getLogger(__name__)
LOCALHOST = "127.0.0.1"


class ThreadBot(commands.Bot):
    """Base bot instance."""

    name = constants.Bot.name

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._guild_available = asyncio.Event()

        statsd_url = constants.Stats.statsd_host

        if constants.DEBUG_MODE:
            # Since statsd is UDP, there are no errors for sending to a down port.
            # For this reason, setting the statsd host to 127.0.0.1 for development
            # will effectively disable stats.
            statsd_url = LOCALHOST

        self._statsd_timerhandle: asyncio.TimerHandle = None
        self.stats = async_stats.AsyncStatsClient(self.loop, LOCALHOST)
        self._connect_statsd(statsd_url)

        self.loop.create_task(self.check_channels())
        self.loop.create_task(self.send_log(self.name, "Connected!"))

    def _connect_statsd(self, statsd_url: str, retry_after: int = 2, attempt: int = 1) -> None:
        """Callback used to retry a connection to statsd if it should fail."""
        if attempt >= 8:
            log.error("Reached 8 attempts trying to reconnect AsyncStatsClient. Aborting")
            return

        try:
            self.stats = async_stats.AsyncStatsClient(self.loop, statsd_url, 8125, prefix="bot")
        except socket.gaierror:
            log.warning(f"Statsd client failed to connect (Attempt(s): {attempt})")
            # Use a fallback strategy for retrying, up to 8 times.
            self._statsd_timerhandle = self.loop.call_later(
                retry_after,
                self._connect_statsd,
                statsd_url,
                retry_after * 2,
                attempt + 1
            )

        # All tasks that need to block closing until finished
        self.closing_tasks: list[asyncio.Task] = []

    @classmethod
    def create(cls) -> "ThreadBot":
        """Create and return an instance of a Bot."""
        loop = asyncio.get_event_loop()
        allowed_roles = [discord.Object(id_) for id_ in constants.staff_roles]

        intents = discord.Intents.default()
        intents.bans = False
        intents.integrations = False
        intents.invites = False
        intents.typing = False
        intents.webhooks = False

        return cls(
            loop=loop,
            command_prefix=commands.when_mentioned_or(constants.Bot.prefix),
            case_insensitive=True,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=allowed_roles),
            intents=intents,
        )

    def load_extensions(self) -> None:
        """Load all enabled extensions."""
        # Must be done here to avoid a circular import.
        from bot.utils.extensions import EXTENSIONS

        extensions = set(EXTENSIONS)  # Create a mutable copy.
        for extension in extensions:
            self.load_extension(extension)

    def add_cog(self, cog: commands.Cog) -> None:
        """Adds a "cog" to the bot and logs the operation."""
        super().add_cog(cog)
        log.info(f"Cog loaded: {cog.qualified_name}")

    async def check_channels(self) -> None:
        """Verifies that all channel constants refer to channels which exist."""
        await self.wait_until_guild_available()

        if constants.DEBUG_MODE:
            log.info("Skipping Channels Check.")
            return

        all_channels_ids = [channel.id for channel in self.get_all_channels()]
        for name, channel_id in vars(constants.Channels).items():
            if name.startswith("_"):
                continue
            if channel_id not in all_channels_ids:
                log.error(f'Channel "{name}" with ID {channel_id} missing')

    async def send_log(self, title: str, details: str = None) -> None:
        """Send an embed message to the dev_log channel."""
        await self.wait_until_guild_available()
        dev_log = self.get_channel(constants.Channels.dev_log)

        if not dev_log:
            log.info(f"Fetching dev_log channel as it wasn't found in the cache (ID: {constants.Channels.dev_log})")
            try:
                dev_log = await self.fetch_channel(constants.Channels.dev_log)
            except discord.HTTPException as discord_exc:
                log.exception("Fetch failed", exc_info=discord_exc)
                return

        embed = Embed(description=details)
        embed.set_author(name=title, icon_url=self.user.avatar.url)

        await dev_log.send(embed=embed)

    async def on_guild_available(self, guild: discord.Guild) -> None:
        """
        Set the internal `_guild_available` event when PyDis guild becomes available.

        If the cache appears to still be empty (no members, no channels, or no roles), the event
        will not be set.
        """
        if guild.id != constants.Guild.id:
            return

        if not guild.roles or not guild.members or not guild.channels:
            log.warning("Guild available event was dispatched but the cache appears to still be empty!")
            return

        self._guild_available.set()

    async def on_guild_unavailable(self, guild: discord.Guild) -> None:
        """Clear the internal `_guild_available` event when PyDis guild becomes unavailable."""
        if guild.id != constants.Guild.id:
            return

        self._guild_available.clear()

    async def wait_until_guild_available(self) -> None:
        """
        Wait until the PyDis guild becomes available (and the cache is ready).

        The on_ready event is inadequate because it only waits 2 seconds for a GUILD_CREATE
        gateway event before giving up and thus not populating the cache for unavailable guilds.
        """
        await self._guild_available.wait()

    async def close(self) -> None:
        """Close the Discord connection and statsd client."""
        # Wait until all tasks that have to be completed before bot is closing is done
        log.trace("Waiting for tasks before closing.")
        await asyncio.gather(*self.closing_tasks)

        await super().close()

        if self.stats._transport:
            self.stats._transport.close()

        if self._statsd_timerhandle:
            self._statsd_timerhandle.cancel()

    async def login(self, *args, **kwargs) -> None:
        """Re-create the stats socket before logging into Discord."""
        await self.stats.create_socket()
        await super().login(*args, **kwargs)
