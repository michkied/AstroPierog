import discord.ui as ui
import discord

from .views import AddDateView, RemoveDateView
from ..entities import *


class AddSlotsButton(ui.Button):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(label="Add slots", style=discord.enums.ButtonStyle.green, custom_id="ADD_SLOTS_BUTTON")

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user

        view = AddDateView()
        content = ("### Select the dates and times you are available for meetings"
                   "\nIf you select multiple dates, the same times will be added to all of them.")
        await interaction.response.send_message(content=content, view=view, ephemeral=True)
        await view.wait()

        for date_str in view.date_select.values:
            for time_str in view.time_select.values:
                if user.id not in self.bot.data.coordinators:
                    self.bot.data.coordinators[user.id] = Coordinator(user.id)
                coordinator = self.bot.data.coordinators[user.id]

                if any(ts.date == date_str and ts.hour == time_str for ts in coordinator.time_slots):
                    continue
                self.bot.data.coordinators[user.id].time_slots.append(TimeSlot(date_str, time_str))

        await view.interaction.response.edit_message(content=":white_check_mark: **Time slots added successfully**", view=None)


class RemoveSlotsButton(ui.Button):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(label="Remove slots", style=discord.enums.ButtonStyle.red, custom_id="REMOVE_SLOTS_BUTTON")

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        if user.id not in self.bot.data.coordinators:
            self.bot.data.coordinators[user.id] = Coordinator(user.id)
        if not self.bot.data.coordinators[user.id].time_slots:
            await interaction.response.send_message(":x: **You have no time slots to remove!**", ephemeral=True)
            return

        view = RemoveDateView(self.bot, user.id)
        await interaction.response.send_message(view=view, ephemeral=True)
        await view.wait()
        interaction = view.interaction
        date_str = view.select.values[0]

        view = RemoveDateView(self.bot, user.id, date_str)
        await interaction.response.edit_message(view=view)
        await view.wait()

        coordinator = self.bot.data.coordinators[user.id]
        for ts in coordinator.time_slots[:]:
            if ts.date == date_str and ts.hour in view.select.values:
                coordinator.time_slots.remove(ts)

        await view.interaction.response.edit_message(content=":white_check_mark: **Time slots removed successfully**", view=None)
