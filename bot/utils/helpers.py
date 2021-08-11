import asyncio
from typing import Any, Callable, Iterable, Optional, TypeVar

import discord
import more_itertools

from bot import constants, logger

T = TypeVar('T')


async def chunked_find(
    predicate: Callable[[T], Any],
    seq: Iterable[T],
    *,
    chunk_size: Optional[int] = None
) -> Optional[T]:
    """
    A helper to return the first element found in the sequence that meets the predicate.

    If chunk_size is specified, chunked_find() will yield control to the event loop between each chunk.
    """
    for chunk in more_itertools.chunked(seq, chunk_size):
        for element in chunk:
            if predicate(element):
                return element

        if chunk_size:
            await asyncio.sleep(0)  # Yield to the event loop
    return None


async def _check_first_message_referencing(thread: discord.Thread, message_id: int) -> bool:
    """Check if the thread_starter_message of `thread` references the given `message_id`."""
    messages = await thread.history(limit=1, oldest_first=True).flatten()
    return messages[0].reference.message_id == message_id


async def get_thread_from_message_id(
    message_id: int,
    channel: discord.TextChannel,
    cached_messages: list[discord.Message]
) -> Optional[discord.Thread]:
    """Attempt to find the thread linked to the given message id."""
    def predicate(message: discord.Message) -> bool:
        """Checks if `message` is the thread_starter_message for the `message_id`."""
        return (
            message.reference
            and message.reference.message_id == message_id
            and isinstance(message.channel, discord.Thread)
        )

    # Try and find the thread start message in message cache.
    # Use a chunked find as this many checks could block for too long.
    if message := await chunked_find(predicate, cached_messages, chunk_size=constants.CHUNKED_FIND_CHUNK_SIZE):
        logger.info("Thread found in message cache!")
        return message.channel

    for thread in channel.threads:  # Thread may be in cache
        if await _check_first_message_referencing(thread, message_id):
            logger.info("Thread found in thread cache!")
            return thread

    logger.info("Message not found in either cache, fetching all threads...")
    for thread in await channel.active_threads():
        if await _check_first_message_referencing(thread, message_id):
            logger.info("Thread found in fetched threads!")
            return thread

    return None
