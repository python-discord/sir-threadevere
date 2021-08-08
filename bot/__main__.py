import bot
from bot import constants, logger
from bot.bot import ThreadBot


@logger.catch()
def start() -> None:
    """Entrypoint for Thread Bot."""
    bot.instance = ThreadBot.create()
    bot.instance.load_extensions()
    bot.instance.run(constants.Bot.token)


if __name__ == "__main__":
    start()
