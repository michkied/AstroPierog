from select import select

from .views import *
from ..entities import *
from datetime import datetime, timedelta

from ..config import *
from ..helpers import is_within_24_hours


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
        if view.interaction is None:
            return

        for date_str in view.date_select.values:
            for time_str in view.time_select.values:
                if user.id not in self.bot.data.coordinators:
                    self.bot.data.coordinators[user.id] = Coordinator(user.id)
                coordinator = self.bot.data.coordinators[user.id]

                if any(ts.date == date_str and ts.hour == time_str for ts in coordinator.time_slots):
                    continue
                self.bot.data.coordinators[user.id].time_slots.append(TimeSlot(date_str, time_str))

        await self.bot.data.store()
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
        if view.interaction is None:
            return
        interaction = view.interaction
        date_str = view.select.values[0]

        view = RemoveDateView(self.bot, user.id, date_str)
        await interaction.response.edit_message(view=view)
        await view.wait()
        if view.interaction is None:
            return
        interaction = view.interaction
        selected = view.select.values

        coordinator = self.bot.data.coordinators[user.id]
        for ts in coordinator.time_slots[:]:
            if ts.date == date_str and ts.hour in selected:
                if not ts.is_booked:
                    coordinator.time_slots.remove(ts)
                    continue

                view = ConfirmDateRemovalView()
                text = (f"## :warning: The time slot on {ts.date} at {ts.hour} is booked by <@{ts.recruit.ID}>."
                        "\nWhat would you like to do with it?")
                await interaction.response.edit_message(content=text, view=view)
                await view.wait()
                if view.interaction is None:
                    return
                interaction = view.interaction
                if view.keep:
                    continue
                coordinator_name = self.bot.get_guild(GUILD).get_member(coordinator.ID).display_name
                recruit = self.bot.get_guild(GUILD).get_member(ts.recruit.ID)
                if recruit is not None:
                    recruit_name = recruit.display_name
                else:
                    recruit_name = "Unknown Recruit"
                await self.bot.get_user(ts.recruit.ID).send(f":warning: Your meeting on **{ts.date}** at **{ts.hour}** with **{coordinator_name}** (<@{coordinator.ID}>) has been cancelled. If you have any questions, please contact the coordinator.")
                await self.bot.get_user(coordinator.ID).send(f":white_check_mark: You have successfully removed the booked time slot on **{ts.date}** at **{ts.hour}** with **{recruit_name}** (<@{ts.recruit.ID}>).**")
                ts.cancel()
                coordinator.time_slots.remove(ts)

        await self.bot.data.store()
        await interaction.response.edit_message(content=":white_check_mark: **Time slots removed successfully**", view=None)


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
        free_hours = set()
        guild = self.bot.get_guild(GUILD)
        division_roles = list(map(lambda x: guild.get_role(x), DIVISION_ROLES))

        if not self.bot.data.coordinators:
            schedule_text += "No meetings scheduled for this day."
            await interaction.response.send_message(content=schedule_text, ephemeral=True, delete_after=90)
            return

        for coordinator in self.bot.data.coordinators.values():
            coordinators.append(self.bot.get_user(coordinator.ID))
            booked = sorted((ts for ts in coordinator.time_slots if ts.date == date_str and ts.is_booked), key=lambda ts: ts.hour)
            free = sorted((ts for ts in coordinator.time_slots if ts.date == date_str and not ts.is_booked), key=lambda ts: ts.hour)
            if not booked and not free:
                continue

            role_str = ""
            for role in division_roles:
                if role in guild.get_member(coordinator.ID).roles:
                    role_str += f"{role.mention} "

            schedule_text += f"### <@{coordinator.ID}> - {role_str}\n"
            if booked:
                for ts in booked:
                    schedule_text += f"- {ts.hour}: Meeting with <@{ts.recruit.ID}>\n"
            if free:
                schedule_text += "Free slots:"
                for ts in free:
                    free_hours.add(ts.hour)
                    schedule_text += f" {ts.hour},"
                schedule_text = schedule_text[:-1] + "\n"
            else:
                schedule_text += "No free slots\n"
            schedule_text += "\n"

        for role in division_roles:
            if role in guild.get_member(interaction.user.id).roles:
                await interaction.response.send_message(content=schedule_text, ephemeral=True, delete_after=90)
                return

        if interaction.user.id not in self.bot.data.recruits:
            self.bot.data.recruits[interaction.user.id] = Recruit(interaction.user.id)
        recruit = self.bot.data.recruits[interaction.user.id]

        if not free_hours:
            await interaction.response.send_message(content=schedule_text, ephemeral=True, delete_after=90)
            return

        if recruit.meeting is None:
            if is_within_24_hours(date_str, max(free_hours)):
                schedule_text += "\n:warning: **You cannot book meetings less than 24 hours before they are scheduled.**"
                await interaction.response.send_message(content=schedule_text, ephemeral=True, delete_after=90)
                return
            await self.book_sequence(schedule_text, interaction, date_str)
            return

        if is_within_24_hours(recruit.meeting.date, recruit.meeting.hour):
            if recruit.meeting.date != date_str:
                await interaction.response.send_message(content=schedule_text, ephemeral=True, delete_after=90)
                return
            schedule_text += "\n:warning: **You cannot cancel meetings less than 24 hours before they are scheduled.**"
            await interaction.response.send_message(content=schedule_text, ephemeral=True, delete_after=90)
            return

        await self.cancel_sequence(schedule_text, interaction, recruit)

    async def book_sequence(self, schedule_text: str, interaction: discord.Interaction, date_str: str):
        schedule_text += "\n## Book a meeting:"
        view = BookMeetingView(self.bot, date_str)
        await interaction.response.send_message(content=schedule_text, view=view, ephemeral=True, delete_after=90)
        await view.wait()
        if view.interaction is None:
            return
        interaction = view.interaction

        coordinator_id = view.select.values[0]
        view = BookMeetingView(self.bot, date_str, int(coordinator_id))
        await interaction.response.edit_message(view=view, delete_after=90)
        await view.wait()
        if view.interaction is None:
            return

        coordinator = self.bot.data.coordinators[int(coordinator_id)]
        slot = None
        for ts in coordinator.time_slots:
            if ts.date == date_str and ts.hour == view.select.values[0]:  # Book the selected time slot
                slot = ts
                break

        if interaction.user.id not in self.bot.data.recruits:
            self.bot.data.recruits[interaction.user.id] = Recruit(interaction.user.id)
        recruit = self.bot.data.recruits[interaction.user.id]
        slot.book(recruit, coordinator)

        await self.bot.data.store()
        coordinator_name = self.bot.get_guild(GUILD).get_member(coordinator.ID).display_name
        recruit_name = self.bot.get_guild(GUILD).get_member(recruit.ID).display_name
        await interaction.user.send(f":white_check_mark: You have successfully booked a meeting on **{slot.date}** at **{slot.hour}** with **{coordinator_name}** (<@{coordinator.ID}>).")
        await self.bot.get_user(coordinator.ID).send(f"{recruit_name} (<@{recruit.ID}>) has booked a meeting with you on **{slot.date}** at **{slot.hour}**.")
        await view.interaction.response.edit_message(content=":white_check_mark: **Booking successful!**", view=None, delete_after=90)

    async def cancel_sequence(self, schedule_text: str, interaction: discord.Interaction, recruit: Recruit):
        schedule_text += f"\nYou already have a meeting booked on {recruit.meeting.date} at {recruit.meeting.hour} with <@{recruit.meeting.coordinator.ID}>.\n"
        view = CancelMeetingView(self.bot)
        await interaction.response.send_message(content=schedule_text, view=view, ephemeral=True, delete_after=90)
        await view.wait()
        if view.interaction is None:
            return
        interaction = view.interaction

        view = CancelMeetingView(self.bot, True)
        text = f"## You are about to cancel your meeting on {recruit.meeting.date} at {recruit.meeting.hour} with <@{recruit.meeting.coordinator.ID}>."
        await interaction.response.edit_message(content=text, view=view, delete_after=90)
        await view.wait()
        if view.interaction is None:
            return
        interaction = view.interaction

        coordinator_name = self.bot.get_guild(GUILD).get_member(recruit.meeting.coordinator.ID).display_name
        recruit_name = self.bot.get_guild(GUILD).get_member(recruit.ID).display_name
        await self.bot.data.store()
        await interaction.user.send(f":white_check_mark: You have successfully cancelled your meeting on **{recruit.meeting.date}** at **{recruit.meeting.hour}** with **{coordinator_name}** (<@{recruit.meeting.coordinator.ID}>).**")
        await self.bot.get_user(recruit.meeting.coordinator.ID).send(f"{recruit_name} (<@{recruit.ID}>) has cancelled their meeting with you on **{recruit.meeting.date}** at **{recruit.meeting.hour}**.")
        recruit.meeting.cancel()
        await interaction.response.edit_message(content=":white_check_mark: **Meeting cancelled successfully!**", view=None, delete_after=90)
