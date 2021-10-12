import json

from bot.bot import ThreadBot

with open("bot/exts/ban_appeals/responses.json") as f:
    APPEAL_RESPONSES = json.load(f)

BASE_RESPONSE = "Hi {name},{snippet}{extras}\n\nKind regards,\nPython Discord Appeals Team."


def setup(bot: ThreadBot) -> None:
    """Load the ban appeals cog."""
    # Defer import to reduce side effects from importing the ban_appeals package.
    from bot.exts.ban_appeals._cog import BanAppeals

    bot.add_cog(BanAppeals(bot))
