import asyncio
import os
import signal
import logging
import sys
from typing import Any
from itertools import chain

from loguru import logger
from PresenceTracker import PresenceTracker
import discord
from discord.ext.commands import Bot as BotBase
from pathlib import Path

"""
Cases should be considered:
Case 1 None -> Playing
Case 2 Playing -> None
Case 3 Playing -> bot shutdown -> Already stopped playing (just commit last end_time?)
Case 4 None -> bot shutdown -> Already playing (catch on stop playing, so Case 2)
Case 5 Playing -> Gone invisible -> Gone visible with the same activity (handles by Case 1 and Case 2)
Case 6: Playing -> Still playing (for end_time updating)

TODO: Handle negative diff 
"""


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)


class Bot(BotBase):
    def __init__(self, *, intents: discord.Intents, activity_tracker: PresenceTracker, **options: Any):
        super().__init__(intents=intents, **options)
        self.activity_tracker = activity_tracker

    async def setup_hook(self) -> None:
        logger.info(f'Invite URL: {"No self.user" if self.user is None else discord.utils.oauth_url(self.user.id)}')

        for filepath in Path('extensions').glob('*.py'):
            filename = filepath.name
            logger.info(f'Loading extension {filename}')
            await self.load_extension(f"extensions.{filename[:-3]}")

        # self.tree.clear_commands(guild=discord.Object(648268554386407432))
        # await self.tree.sync(guild=discord.Object(648268554386407432))
        #
        # self.tree.copy_global_to(guild=discord.Object(648268554386407432))
        # await self.tree.sync(guild=discord.Object(648268554386407432))

        # await self.tree.sync()


    def signal_handler(self, signame, _):
        logger.info(f'Got {signame} signal, shutting down')
        self.loop.create_task(self.close())

    async def on_ready(self):
        logger.info(f'Ready {self.user}')

    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if before.bot:
            return

        for activity in chain(before.activities, after.activities):
            if activity.type == discord.ActivityType.playing:
                if isinstance(activity, (discord.Game, discord.Activity)):
                    if activity.name is not None and activity.start is not None:
                        self.activity_tracker.log_activity(after.id, activity.name, activity.start, activity.end)
                        self.activity_tracker.saturate_users_cache(after.id, after.name + '#' + after.discriminator)

                    else:
                        logger.warning(f'Got activity with missing name or start: {activity.to_dict()!r}')

                else:
                    logger.warning(
                        f'Got discord.ActivityType.playing with unusual type: {type(activity)}; {activity.to_dict()}')

            else:
                logger.trace(f'Got not playing activity: {activity.to_dict()}')


async def async_main():
    # logger.disable('discord')
    logger.remove()
    logger.add(sink=sys.stderr)  # Use env var LOGURU_LEVEL to set desire level

    intents = discord.Intents.default()
    intents.presences = True
    intents.members = True

    activity_tracker = PresenceTracker()
    bot = Bot(intents=intents, activity_tracker=activity_tracker, command_prefix='')

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, bot.signal_handler)

    await bot.start(os.environ['TOKEN'])


def main():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(async_main())


if __name__ == '__main__':
    main()
