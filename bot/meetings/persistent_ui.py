import discord.ui as ui
import discord

from .views import *
from ..entities import *
from datetime import datetime, timedelta

from ..config import LAST_DAY


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


class ScheduleDaySelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(placeholder="Select date", custom_id="SCHEDULE_DAY_SELECT")

        top_day = datetime.now()
        while len(self.options) < 25 and top_day <= LAST_DAY:
            date = top_day.strftime("%d.%m")
            self.add_option(label=date, value=date)
            top_day += timedelta(days=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.message.edit(embed=None)  # editing removes the selected menu option
        date_str = self.values[0]
        schedule_text = f"## Meeting Schedule for {date_str}\n"
        coordinators = []
        for coordinator in self.bot.data.coordinators.values():
            coordinators.append(self.bot.get_user(coordinator.ID))
            booked = sorted((ts for ts in coordinator.time_slots if ts.date == date_str and ts.is_booked), key=lambda ts: ts.hour)
            free = sorted((ts for ts in coordinator.time_slots if ts.date == date_str and not ts.is_booked), key=lambda ts: ts.hour)
            if not booked and not free:
                continue
            schedule_text += f"### Coordinator <@{coordinator.ID}>\n"
            if booked:
                for ts in booked:
                    schedule_text += f"- {ts.hour}: Meeting with <@{ts.recruit.ID}>\n"
            if free:
                schedule_text += "Free slots:"
                for ts in free:
                    schedule_text += f" {ts.hour},"
                schedule_text = schedule_text[:-1] + "\n"
            else:
                schedule_text += "No free slots\n"
        if schedule_text.strip() == f"## Meeting Schedule for {date_str}":
            schedule_text += "No meetings scheduled for this day."
            await interaction.response.send_message(content=schedule_text, ephemeral=True, delete_after=90)
            return

        if interaction.user.id not in self.bot.data.recruits:
            self.bot.data.recruits[interaction.user.id] = Recruit(interaction.user.id)
        recruit = self.bot.data.recruits[interaction.user.id]

        if recruit.meeting is not None:
            await interaction.response.send_message(content=schedule_text, ephemeral=True, delete_after=90)
            return

        schedule_text += "\n\n## Book a meeting:"
        view = BookMeetingView(self.bot, date_str)
        await interaction.response.send_message(content=schedule_text, view=view, ephemeral=True, delete_after=90)
        await view.wait()
        interaction = view.interaction

        coordinator_id = view.select.values[0]
        view = BookMeetingView(self.bot, date_str, int(coordinator_id))
        await interaction.response.edit_message(view=view, delete_after=90)
        await view.wait()

        coordinator = self.bot.data.coordinators[int(coordinator_id)]
        for ts in coordinator.time_slots:
            if ts.date == date_str and ts.hour == view.select.values[0]:  # Book the selected time slot
                if interaction.user.id not in self.bot.data.recruits:
                    self.bot.data.recruits[interaction.user.id] = Recruit(interaction.user.id)
                recruit = self.bot.data.recruits[interaction.user.id]
                ts.book(recruit, coordinator)
                break

        await view.interaction.response.edit_message(content=":white_check_mark: **Booking successful!**", view=None, delete_after=90)
