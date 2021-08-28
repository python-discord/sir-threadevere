import asyncio
from dataclasses import dataclass

from discord import ButtonStyle, Interaction, Message, ui
from discord.ext import commands

from bot import constants
from bot.exts.ban_appeals import APPEAL_RESPONSES, _api_handlers


@dataclass(frozen=True)
class AppealDetails:
    """A data class to hold all details about a given appeal."""

    appealer: str
    uuid: str
    email: str
    reason: str
    justification: str

    @property
    def thread_name(self) -> str:
        """The name of the thread to create, based on the appealer."""
        return f"Ban appeal - {self.appealer}"

    def __str__(self) -> str:
        return (
            f"{self.uuid} - {self.appealer}\n\n"
            f"**Their understanding of the ban reason:**\n> {self.reason}\n\n"
            f"**Why they think they should be unbanned**:\n> {self.justification}"
        )


class AppealResponse(commands.Converter):
    """Ensure that the given appeal response exists."""

    async def convert(self, ctx: commands.Context, response: str) -> str:
        """Ensure that the given appeal response exists."""
        response = response.lower()
        if response in APPEAL_RESPONSES:
            return APPEAL_RESPONSES[response]

        raise commands.BadArgument(f":x: Could not find the response `{response}`.")


class ConfirmAppealResponse(ui.View):
    """A confirmation view for responding to ban appeals."""

    def __init__(self, thread_data_message: Message, appealer_email: str) -> None:
        super().__init__()
        self.lock = asyncio.Lock()  # Only process 1 interaction is at a time, to avoid multiple emails being sent.

        # Message storing data about the appeal. Used to mark the appeal as actioned after sending the email.
        self.thread_data_message = thread_data_message
        self.appealer_email = appealer_email

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Check that the interactor is authorised and another interaction isn't being processed."""
        if self.lock.locked():
            await interaction.response.send_message(
                ":x: Processing another user's button press, try again later.",
                ephemeral=True,
            )
            return False

        if constants.Roles.admins in (role.id for role in interaction.user.roles):
            return True

        await interaction.response.send_message(
            ":x: You are not authorized to perform this action.",
            ephemeral=True,
        )

        return False

    async def on_error(self, error: Exception, item: ui.Item, interaction: Interaction) -> None:
        """Release the lock in case of error."""
        if self.lock.locked():
            await self.lock.release()

    async def stop(self, interaction: Interaction, *, actioned: bool = True) -> None:
        """Remove buttons and mark thread as actioned on stop."""
        await interaction.message.edit(view=None)
        if actioned:
            await self.thread_data_message.edit(content=f"Actioned {self.thread_data_message.content}")

    @ui.button(label="Confirm & send", style=ButtonStyle.green, row=0)
    async def confirm(self, _button: ui.Button, interaction: Interaction) -> None:
        """Confirm body and send email to ban appealer."""
        await self.lock.acquire()

        await _api_handlers.post_appeal_respose_email(interaction.message.content, self.appealer_email)

        await interaction.response.send_message(
            f":+1: {interaction.user.mention} Email sent. "
            "Please archive this thread when ready."
        )
        await self.stop(interaction)

    @ui.button(label="Cancel", style=ButtonStyle.gray, row=0)
    async def cancel(self, _button: ui.Button, interaction: Interaction) -> None:
        """Cancel the response email."""
        await self.lock.acquire()
        await interaction.response.send_message(":x: Email aborted.")
        await self.stop(interaction, actioned=False)
