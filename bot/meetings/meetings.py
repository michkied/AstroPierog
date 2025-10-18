from discord.ext import commands
from ..config import OWNER_ID
from logzero import logger

from .availability_buttons import *


class Meetings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        view = discord.ui.View(timeout=None)
        view.add_item(AddSlotsButton(self.bot))
        view.add_item(RemoveSlotsButton(self.bot))
        self.bot.add_view(view)

    @commands.command()
    async def post_availability(self, ctx):
        if ctx.author.id != OWNER_ID:
            return
        await ctx.message.delete()

        view = discord.ui.View(timeout=None)
        view.add_item(AddSlotsButton(self.bot))
        view.add_item(RemoveSlotsButton(self.bot))

        text = '## Click the buttons below to manage your availability for meetings as a coordinator.'
        await ctx.send(text, view=view)
        print(view.is_persistent())

        logger.info("Availability selection posted")
