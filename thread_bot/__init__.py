from functools import partial
from typing import TYPE_CHECKING

import loguru

if TYPE_CHECKING:
    from thread_bot.thread_bot import ThreadBot

logger = loguru.logger.opt(colors=True)
logger.opt = partial(logger.opt, colors=True)

instance: "ThreadBot" = None  # Global ThreadBot instance.
