import thread_bot
from thread_bot import constants, logger
from thread_bot.thread_bot import ThreadBot


@logger.catch()
def start() -> None:
    """Entrypoint for Thread Bot."""
    thread_bot.instance = ThreadBot.create()
    thread_bot.instance.load_extensions()
    thread_bot.instance.run(constants.Bot.token)


if __name__ == "__main__":
    start()
