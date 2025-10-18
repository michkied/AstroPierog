from abc import ABC
from datetime import datetime
import discord
from discord.ext import commands

from bot.meetings import Meetings
from bot.projects import Projects
from bot.config import TOKEN, GUILD


class AstroPierog(commands.Bot, ABC):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or('?'),
            intents=discord.Intents.all(),
            debug_guilds=[GUILD]
        )

        self.remove_command('help')
        self.add_cog(Meetings(self))
        self.add_cog(Projects(self))
        self.run(TOKEN)

    async def on_ready(self):
        date = datetime.now()
        print(f'Logged in as {self.user}')
        print(self.user.display_name)
        print(self.user.id)
        print(date.strftime('%d.%m.%Y  %H:%M'))
        print('by Michał Kiedrzyński\n\n')


if __name__ == '__main__':
    AstroPierog()
