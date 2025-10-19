from discord.ext import commands
from ..config import OWNER_ID
from logzero import logger

from .persistent_ui import *


class Meetings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        view = discord.ui.View(timeout=None)
        view.add_item(AddSlotsButton(self.bot))
        view.add_item(RemoveSlotsButton(self.bot))
        view.add_item(ScheduleDaySelect(self.bot))
        self.bot.add_view(view)

    @commands.command()
    async def post_schedule(self, ctx):
        if ctx.author.id != OWNER_ID:
            return
        await ctx.message.delete()

        view = discord.ui.View(timeout=None)
        view.add_item(ScheduleDaySelect(self.bot))

        text = "## Select the schedule date you'd like to see or book"
        await ctx.send(text, view=view)
        print(view.is_persistent())

        logger.info("Schedule selection posted")

    @commands.command()
    async def post_availability(self, ctx):
        if ctx.author.id != OWNER_ID:
            return
        await ctx.message.delete()

        view = discord.ui.View(timeout=None)
        view.add_item(AddSlotsButton(self.bot))
        view.add_item(RemoveSlotsButton(self.bot))

        text = '## Click the buttons below to manage your availability for meetings as a coordinator'
        await ctx.send(text, view=view)
        print(view.is_persistent())

        logger.info("Availability selection posted")
