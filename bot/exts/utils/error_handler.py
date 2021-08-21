import typing as t

from discord import Embed
from discord.ext.commands import Cog, Context, errors

from bot.bot import ThreadBot, logger
from bot.constants import Colours


class ErrorHandler(Cog):
    """Handles errors emitted from commands."""

    def __init__(self, bot: ThreadBot):
        self.bot = bot

    @staticmethod
    def _get_error_embed(title: str, body: str) -> Embed:
        """Return an embed that contains the exception."""
        return Embed(
            title=title,
            colour=Colours.error,
            description=body
        )

    @Cog.listener()
    async def on_command_error(self, ctx: Context, e: errors.CommandError) -> None:
        """
        Provide generic command error handling.

        Error handling is deferred to any local error handler, if present. This is done by
        checking for the presence of a `handled` attribute on the error.

        Error handling emits a single error message in the invoking context `ctx` and a log message,
        prioritised as follows:

        1. UserInputError: see `handle_user_input_error`
        3. CheckFailure: see `handle_check_failure`
        4. CommandOnCooldown: send an error message in the invoking context
        5. ResponseCodeError: see `handle_api_error`
        6. Otherwise, if not a DisabledCommand, handling is deferred to `handle_unexpected_error`
        """
        command = ctx.command

        if hasattr(e, "handled"):
            logger.trace(f"Command {command} had its error already handled locally; ignoring.")
            return

        if isinstance(e, errors.UserInputError):
            await self.handle_user_input_error(ctx, e)
        elif isinstance(e, errors.CheckFailure):
            await self.handle_check_failure(ctx, e)
        elif isinstance(e, errors.CommandOnCooldown):
            await ctx.send(e)
        elif not isinstance(e, errors.DisabledCommand):
            # MaxConcurrencyReached, ExtensionError
            await self.handle_unexpected_error(ctx, e)
            return  # Exit early to avoid logging.

        logger.debug(
            f"Command {command} invoked by {ctx.message.author} with error "
            f"{e.__class__.__name__}: {e}"
        )

    @staticmethod
    def get_help_command(ctx: Context) -> t.Coroutine:
        """Return a prepared `help` command invocation coroutine."""
        if ctx.command:
            return ctx.send_help(ctx.command)

        return ctx.send_help()

    async def handle_user_input_error(self, ctx: Context, e: errors.UserInputError) -> None:
        """
        Send an error message in `ctx` for UserInputError, sometimes invoking the help command too.

        * MissingRequiredArgument: send an error message with arg name and the help command
        * TooManyArguments: send an error message and the help command
        * BadArgument: send an error message and the help command
        * BadUnionArgument: send an error message including the error produced by the last converter
        * ArgumentParsingError: send an error message
        * Other: send an error message and the help command
        """
        if isinstance(e, errors.MissingRequiredArgument):
            embed = self._get_error_embed("Missing required argument", e.param.name)
            await ctx.send(embed=embed)
            await self.get_help_command(ctx)
            self.bot.stats.incr("errors.missing_required_argument")
        elif isinstance(e, errors.TooManyArguments):
            embed = self._get_error_embed("Too many arguments", str(e))
            await ctx.send(embed=embed)
            await self.get_help_command(ctx)
            self.bot.stats.incr("errors.too_many_arguments")
        elif isinstance(e, errors.BadArgument):
            embed = self._get_error_embed("Bad argument", str(e))
            await ctx.send(embed=embed)
            await self.get_help_command(ctx)
            self.bot.stats.incr("errors.bad_argument")
        elif isinstance(e, errors.BadUnionArgument):
            embed = self._get_error_embed("Bad argument", f"{e}\n{e.errors[-1]}")
            await ctx.send(embed=embed)
            await self.get_help_command(ctx)
            self.bot.stats.incr("errors.bad_union_argument")
        elif isinstance(e, errors.ArgumentParsingError):
            embed = self._get_error_embed("Argument parsing error", str(e))
            await ctx.send(embed=embed)
            self.get_help_command(ctx).close()
            self.bot.stats.incr("errors.argument_parsing_error")
        else:
            embed = self._get_error_embed(
                "Input error",
                "Something about your input seems off. Check the arguments and try again."
            )
            await ctx.send(embed=embed)
            await self.get_help_command(ctx)
            self.bot.stats.incr("errors.other_user_input_error")

    @staticmethod
    async def handle_check_failure(ctx: Context, e: errors.CheckFailure) -> None:
        """
        Send an error message in `ctx` for certain types of CheckFailure.

        The following types are handled:

        * BotMissingPermissions
        * BotMissingRole
        * BotMissingAnyRole
        * NoPrivateMessage
        * InWhitelistCheckFailure
        """
        bot_missing_errors = (
            errors.BotMissingPermissions,
            errors.BotMissingRole,
            errors.BotMissingAnyRole
        )

        if isinstance(e, bot_missing_errors):
            ctx.bot.stats.incr("errors.bot_permission_error")
            await ctx.send(
                "Sorry, it looks like I don't have the permissions or roles I need to do that."
            )
        elif isinstance(e, errors.NoPrivateMessage):
            ctx.bot.stats.incr("errors.wrong_channel_or_dm_error")
            await ctx.send(e)

    @staticmethod
    async def handle_unexpected_error(ctx: Context, e: errors.CommandError) -> None:
        """Send a generic error message in `ctx` and log the exception as an error with exc_info."""
        await ctx.send(
            f"Sorry, an unexpected error occurred. Please let us know!\n\n"
            f"```{e.__class__.__name__}: {e}```"
        )

        ctx.bot.stats.incr("errors.unexpected")

        logger.error(f"Error executing command invoked by {ctx.message.author}: {ctx.message.content}", exc_info=e)


def setup(bot: ThreadBot) -> None:
    """Load the ErrorHandler cog."""
    bot.add_cog(ErrorHandler(bot))
