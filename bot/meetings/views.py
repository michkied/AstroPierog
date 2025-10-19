from datetime import datetime, timedelta
import discord.ui as ui
import discord
from ..config import LAST_DAY, TIMES, GUILD
from ..helpers import is_within_24_hours


async def ignore_callback(interaction: discord.Interaction):
    await interaction.response.defer()


class AddDateView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.interaction = None

        date_select = ui.Select(placeholder="Select date")
        top_day = datetime.now()
        while len(date_select.options) < 25 and top_day <= LAST_DAY:
            date = top_day.strftime("%d.%m")
            date_select.add_option(label=date, value=date)
            top_day += timedelta(days=1)
        date_select.callback = ignore_callback
        date_select.max_values = len(date_select.options)
        self.add_item(date_select)

        time_select = ui.Select(placeholder="Select time", max_values=len(TIMES))
        for hour in TIMES:
            time_select.add_option(label=hour, value=hour)
        time_select.callback = ignore_callback
        self.add_item(time_select)

        self.btn = ui.Button(label="Done", style=discord.enums.ButtonStyle.green)
        self.add_item(self.btn)
        self.btn.callback = self.stop_callback

        self.time_select = time_select
        self.date_select = date_select

    async def stop_callback(self, interaction: discord.Interaction):
        if self.time_select.values and self.date_select.values:
            self.interaction = interaction
            self.stop()
        else:
            await interaction.response.send_message(":x: **Please select both date and time**", ephemeral=True)


class RemoveDateView(ui.View):
    def __init__(self, bot, coordinator_id, chosen_date: str = None):
        super().__init__(timeout=None)
        self.interaction = None
        self.bot = bot

        coordinator = bot.data.coordinators[coordinator_id]
        if chosen_date is None:
            self.select = ui.Select(placeholder="Select date")
            for date_str in set(ts.date for ts in coordinator.time_slots):
                self.select.add_option(label=date_str, value=date_str)
            self.btn = ui.Button(label="Continue", style=discord.enums.ButtonStyle.grey)
        else:
            self.select = ui.Select(placeholder="Select time")
            for ts in coordinator.time_slots:
                if ts.date == chosen_date:
                    self.select.add_option(label=ts.hour, value=ts.hour)
            self.select.max_values = len(self.select.options)
            self.btn = ui.Button(label="Done", style=discord.enums.ButtonStyle.green)

        self.select.callback = ignore_callback
        self.add_item(self.select)
        self.add_item(self.btn)
        self.btn.callback = self.stop_callback

    async def stop_callback(self, interaction: discord.Interaction):
        if self.select.values:
            self.interaction = interaction
            self.stop()
        else:
            await interaction.response.send_message(":x: **Make a choice first**", ephemeral=True)


class ConfirmDateRemovalView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.interaction = None
        self.keep = None

        self.cancel_btn = ui.Button(label="Remove", style=discord.enums.ButtonStyle.red)
        self.cancel_btn.callback = self.cancel_callback

        self.keep_btn = ui.Button(label="Keep", style=discord.enums.ButtonStyle.green)
        self.keep_btn.callback = self.keep_callback

        self.add_item(self.cancel_btn)
        self.add_item(self.keep_btn)

    async def cancel_callback(self, interaction: discord.Interaction):
        self.keep = False
        self.interaction = interaction
        self.stop()

    async def keep_callback(self, interaction: discord.Interaction):
        self.keep = True
        self.interaction = interaction
        self.stop()


class BookMeetingView(ui.View):
    def __init__(self, bot, date_str: str, chosen_coordinator: int = None):
        super().__init__(timeout=None)
        self.interaction = None
        self.bot = bot
        guild = bot.get_guild(GUILD)

        if chosen_coordinator is None:
            self.select = ui.Select(placeholder="Select coordinator")
            for coordinator in bot.data.coordinators.values():
                if any(ts.date == date_str and not ts.is_booked for ts in coordinator.time_slots):
                    self.select.add_option(value=f"{coordinator.ID}", label=guild.get_member(coordinator.ID).display_name)
            self.btn = ui.Button(label="Continue to booking", style=discord.enums.ButtonStyle.grey)
        else:
            self.select = ui.Select(placeholder="Select time")
            for ts in self.bot.data.coordinators[chosen_coordinator].time_slots:
                if ts.date == date_str and not ts.is_booked and not is_within_24_hours(ts.date, ts.hour):
                    self.select.add_option(label=ts.hour, value=ts.hour)
            self.btn = ui.Button(label="Book", style=discord.enums.ButtonStyle.green)

        self.select.callback = ignore_callback
        self.add_item(self.select)
        self.add_item(self.btn)
        self.btn.callback = self.stop_callback

    async def stop_callback(self, interaction: discord.Interaction):
        if self.select.values:
            self.interaction = interaction
            self.stop()
        else:
            await interaction.response.send_message(":x: **Please select a time slot to book**", ephemeral=True)


class CancelMeetingView(ui.View):
    def __init__(self, bot, confirmation=False):
        super().__init__(timeout=None)
        self.interaction = None
        self.bot = bot

        if not confirmation:
            self.btn = ui.Button(label="Cancel booking", style=discord.enums.ButtonStyle.grey)
        else:
            self.btn = ui.Button(label="Confirm", style=discord.enums.ButtonStyle.red)

        self.add_item(self.btn)
        self.btn.callback = self.stop_callback

    async def stop_callback(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.stop()
