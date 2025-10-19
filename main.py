import os
import pathlib
from abc import ABC
from datetime import datetime
import discord
from discord.ext import commands
from logzero import logfile, logger

from bot.data import Data
from bot.meetings import Meetings
from bot.projects import Projects
from bot.config import TOKEN, GUILD

path = str(pathlib.Path(__file__).parent.absolute())


class AstroPierog(commands.Bot, ABC):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or('?'),
            intents=discord.Intents.all(),
            auto_sync_commands=False,
            debug_guilds=[GUILD]
        )

        self.data = Data()
        self.data.load()

        self.remove_command('help')
        logfile(os.path.join(path, "pierog.log"), encoding='UTF-8')
        self.add_cog(Meetings(self))
        self.add_cog(Projects(self))
        self.run(TOKEN)

    async def on_ready(self):
        date = datetime.now()
        logger.info(f'Logged in as {self.user} ({self.user.id})')
        print(f'Logged in as {self.user}')
        print(self.user.display_name)
        print(self.user.id)
        print(date.strftime('%d.%m.%Y  %H:%M'))
        print('by Michał Kiedrzyński\n\n')


if __name__ == '__main__':
    AstroPierog()
