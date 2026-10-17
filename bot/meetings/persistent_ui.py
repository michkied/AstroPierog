from logzero import logger
from datetime import datetime, timedelta
import copy

from .views import *
from ..entities import *
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
        if await view.wait():
            return
        if view.interaction is None:
            return

        async with self.bot.data.lock:
            for date_str in view.date_select.values:
                for time_str in view.time_select.values:
                    if user.id not in self.bot.data.coordinators:
                        self.bot.data.coordinators[user.id] = Coordinator(user.id)
                    coordinator = self.bot.data.coordinators[user.id]

                    if any(ts.date == date_str and ts.hour == time_str for ts in coordinator.time_slots):
                        continue
                    self.bot.data.coordinators[user.id].time_slots.append(TimeSlot(date_str, time_str))
            await self.bot.data.store()

        logger.info(f"Coordinator {user.id} added time slots: Dates {view.date_select.values}, Times {view.time_select.values}")
        await view.interaction.response.edit_message(content=":white_check_mark: **Time slots added successfully**", view=None)


class RemoveSlotsButton(ui.Button):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(label="Remove slots", style=discord.enums.ButtonStyle.red, custom_id="REMOVE_SLOTS_BUTTON")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        if user.id not in self.bot.data.coordinators:
            self.bot.data.coordinators[user.id] = Coordinator(user.id)
        if not self.bot.data.coordinators[user.id].time_slots:
            await interaction.followup.send(":x: **You have no time slots to remove!**", ephemeral=True)
            return

        view = RemoveDateView(self.bot, user.id)
        await interaction.followup.send(view=view, ephemeral=True)
        if await view.wait():
            return
        if view.interaction is None:
            return
        interaction = view.interaction
        date_str = view.select.values[0]

        view = RemoveDateView(self.bot, user.id, date_str)
        await interaction.response.edit_message(view=view)
        if await view.wait():
            return
        if view.interaction is None:
            return
        interaction = view.interaction
        selected = view.select.values

        coordinator = self.bot.data.coordinators[user.id]
        to_remove = []
        for ts in coordinator.time_slots[:]:
            if ts.date == date_str and ts.hour in selected:
                if not ts.is_booked:
                    to_remove.append((ts, False))
                    continue

                view = ConfirmDateRemovalView()
                text = (f"## :warning: The time slot on {ts.date} at {ts.hour} is booked by <@{ts.recruit.ID}>."
                        "\nWhat would you like to do with it?")
                await interaction.response.edit_message(content=text, view=view)
                if await view.wait() or view.interaction is None:
                    return
                interaction = view.interaction
                if view.keep:
                    logger.info(f"Coordinator {user.id} kept booked time slot on {ts.date} at {ts.hour} booked by {ts.recruit.ID}")
                    continue
                to_remove.append((ts, True))

        warn = False
        cancelled_dms = []
        async with self.bot.data.lock:
            for ts, was_booked_confirmed in to_remove:
                if ts not in coordinator.time_slots:
                    continue
                if ts.is_booked and not was_booked_confirmed:
                    warn = True
                    continue
                if ts.is_booked and ts.recruit is not None:
                    cancelled_dms.append((ts.date, ts.hour, ts.recruit.ID))
                    ts.cancel()
                coordinator.time_slots.remove(ts)
            await self.bot.data.store()

        if warn:
            await interaction.response.edit_message(
                content=":white_check_mark: :warning: **Some time slots were not removed because someone booked them in the meantime. Please try again.**",
                view=None
            )
        else:
            await interaction.response.edit_message(content=":white_check_mark: **Time slots removed successfully**", view=None)

        for dm in cancelled_dms:
            date, hour, recruit_id = dm
            try:
                coordinator_name = self.bot.get_guild(GUILD).get_member(coordinator.ID).display_name
                await self.bot.get_user(recruit_id).send(
                    f":warning: Your meeting on **{date}** at **{hour}** with **{coordinator_name}** (<@{coordinator.ID}>) has been cancelled. If you have any questions, please contact the coordinator."
                )
            except:
                logger.info(f"Could not send DM to recruit {recruit_id} about meeting cancellation.")
            try:
                await self.bot.get_user(coordinator.ID).send(
                    f":white_check_mark: You have successfully removed the booked time slot on **{date}** at **{hour}** with <@{recruit_id}>."
                )
            except:
                logger.info(f"Could not send DM to coordinator {coordinator.ID} about booked time slot removal.")


class ScheduleDaySelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(placeholder="Select date", custom_id="SCHEDULE_DAY_SELECT")

        top_day = datetime.date(datetime.now())
        if top_day < FIRST_DAY:
            top_day = FIRST_DAY
        while len(self.options) < 25 and top_day <= LAST_DAY:
            date = top_day.strftime("%d.%m")
            self.add_option(label=date, value=date)
            top_day += timedelta(days=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.message.edit(embed=None)  # editing removes the selected menu option
        date_str = self.values[0]
        schedule_text = f"## Meeting Schedule for {date_str}\n"
        coordinators = []
        free_hours = set()
        guild = self.bot.get_guild(GUILD)
        division_roles = list(map(lambda x: guild.get_role(x), DIVISION_ROLES))

        logger.info(f"User {interaction.user.id} requested meeting schedule for {date_str}")

        for coordinator in self.bot.data.coordinators.values():
            coordinators.append(self.bot.get_user(coordinator.ID))
            booked = sorted((ts for ts in coordinator.time_slots if ts.date == date_str and ts.is_booked), key=lambda ts: ts.hour)
            free = sorted((ts for ts in coordinator.time_slots if ts.date == date_str and not ts.is_booked), key=lambda ts: ts.hour)
            if not booked and not free:
                continue

            coord_member = guild.get_member(coordinator.ID)
            role_str = ""
            for role in division_roles:
                if coord_member and role in coord_member.roles:
                    role_str += f"{role.mention}"

            coord_text = f"### <@{coordinator.ID}>\n{role_str}\n"
            if booked:
                for ts in booked:
                    coord_text += f"- {ts.hour}: Meeting with <@{ts.recruit.ID}>\n"
            if free:
                coord_text += "Free slots:"
                for ts in free:
                    free_hours.add(ts.hour)
                    coord_text += f" {ts.hour},"
                coord_text = coord_text[:-1] + "\n"
            else:
                coord_text += "No free slots\n"
            coord_text += "\n"

            if len(schedule_text) + len(coord_text) > 1800:
                await interaction.followup.send(content=schedule_text, ephemeral=True, delete_after=90)
                schedule_text = ""
            schedule_text += coord_text

        if schedule_text.strip() == f"## Meeting Schedule for {date_str}":
            schedule_text += "No meetings scheduled for this day."
            await interaction.followup.send(content=schedule_text, ephemeral=True, delete_after=90)
            return

        user_member = guild.get_member(interaction.user.id)
        for role in division_roles:
            if user_member and role in user_member.roles:
                await interaction.followup.send(content=schedule_text, ephemeral=True, delete_after=90)
                return

        if interaction.user.id not in self.bot.data.recruits:
            self.bot.data.recruits[interaction.user.id] = Recruit(interaction.user.id)
        recruit = self.bot.data.recruits[interaction.user.id]

        if not free_hours:
            await interaction.followup.send(content=schedule_text, ephemeral=True, delete_after=90)
            return

        if recruit.meeting is None:
            if is_within_24_hours(date_str, max(free_hours)):
                schedule_text += "\n:warning: **You cannot book meetings less than 24 hours before they are scheduled.**"
                await interaction.followup.send(content=schedule_text, ephemeral=True, delete_after=90)
                return
            await self.book_sequence(schedule_text, interaction, date_str)
            return

        if is_within_24_hours(recruit.meeting.date, recruit.meeting.hour):
            if recruit.meeting.date != date_str:
                await interaction.followup.send(content=schedule_text, ephemeral=True, delete_after=90)
                return
            schedule_text += "\n:warning: **You cannot cancel meetings less than 24 hours before they are scheduled.**"
            await interaction.followup.send(content=schedule_text, ephemeral=True, delete_after=90)
            return

        await self.cancel_sequence(schedule_text, interaction, recruit)

    async def book_sequence(self, schedule_text: str, interaction: discord.Interaction, date_str: str):
        schedule_text += "\n## Book a meeting:"
        view = BookMeetingView(self.bot, date_str)
        await interaction.followup.send(content=schedule_text, view=view, ephemeral=True, delete_after=90)
        if await view.wait():
            return
        if view.interaction is None:
            return
        interaction = view.interaction

        coordinator_id = view.select.values[0]
        view = BookMeetingView(self.bot, date_str, int(coordinator_id))
        await interaction.response.edit_message(view=view, delete_after=90)
        if await view.wait():
            return
        if view.interaction is None:
            return
        interaction = view.interaction
        await interaction.response.defer()

        async with self.bot.data.lock:
            coordinator = self.bot.data.coordinators[int(coordinator_id)]
            slot = None
            for ts in coordinator.time_slots:
                if ts.date == date_str and ts.hour == view.select.values[0] and not ts.is_booked:  # Book the selected time slot
                    slot = ts
                    break
            if slot is None:
                await interaction.edit_original_response(content=":x: **The selected time slot is no longer available. Please try again.**", view=None, delete_after=90)
                return
            recruit = self.bot.data.recruits.setdefault(interaction.user.id, Recruit(interaction.user.id))
            if recruit.meeting is not None:
                await interaction.edit_original_response(content=":x: **You already have a meeting booked!**", view=None, delete_after=90)
                return

            slot.book(recruit, coordinator)
            await self.bot.data.store()

        logger.info(f"Recruit {recruit.ID} booked meeting on {slot.date} at {slot.hour} with coordinator {coordinator.ID}")
        await interaction.edit_original_response(content=":white_check_mark: **Booking successful!**", view=None, delete_after=90)

        try:
            recruit_name = self.bot.get_guild(GUILD).get_member(recruit.ID).display_name
            await self.bot.get_user(coordinator.ID).send(f"{recruit_name} (<@{recruit.ID}>) has booked a meeting with you on **{slot.date}** at **{slot.hour}**.")
        except:
            logger.info(f"Could not send DM to coordinator {coordinator.ID} about new meeting booking.")
        try:
            coordinator_name = self.bot.get_guild(GUILD).get_member(coordinator.ID).display_name
            await interaction.user.send(f":white_check_mark: You have successfully booked a meeting on **{slot.date}** at **{slot.hour}** with **{coordinator_name}** (<@{coordinator.ID}>).")
        except:
            logger.info(f"Could not send DM to recruit {recruit.ID} about successful meeting booking.")

    async def cancel_sequence(self, schedule_text: str, interaction: discord.Interaction, recruit: Recruit):
        schedule_text += f"\nYou already have a meeting booked on {recruit.meeting.date} at {recruit.meeting.hour} with <@{recruit.meeting.coordinator.ID}>.\n"
        view = CancelMeetingView(self.bot)
        await interaction.followup.send(content=schedule_text, view=view, ephemeral=True, delete_after=90)
        if await view.wait():
            return
        if view.interaction is None:
            return
        interaction = view.interaction

        if recruit.meeting is None:
            await interaction.response.edit_message(content=":x: **You have no meeting to cancel!**", view=None, delete_after=90)
            return
        view = CancelMeetingView(self.bot, True)
        text = f"## You are about to cancel your meeting on {recruit.meeting.date} at {recruit.meeting.hour} with <@{recruit.meeting.coordinator.ID}>."
        await interaction.response.edit_message(content=text, view=view, delete_after=90)
        if await view.wait():
            return
        if view.interaction is None:
            return
        interaction = view.interaction
        await interaction.response.defer()

        async with self.bot.data.lock:
            if recruit.meeting is None:
                await interaction.edit_original_response(content=":x: **You have no meeting to cancel!**", view=None, delete_after=90)
                return

            date, hour, coordinator_id = recruit.meeting.date, recruit.meeting.hour, recruit.meeting.coordinator.ID
            recruit.meeting.cancel()
            await self.bot.data.store()

        logger.info(f"Recruit {recruit.ID} cancelled meeting on {date} at {hour} with coordinator {coordinator_id}")
        await interaction.edit_original_response(content=":white_check_mark: **Meeting cancelled successfully!**", view=None, delete_after=90)

        try:
            coordinator_name = self.bot.get_guild(GUILD).get_member(coordinator_id).display_name
            await interaction.user.send(f":white_check_mark: You have successfully cancelled your meeting on **{date}** at **{hour}** with **{coordinator_name}** (<@{coordinator_id}>).")
        except:
            logger.info(f"Could not send DM to recruit {recruit.ID} about successful meeting cancellation.")
        try:
            recruit_name = self.bot.get_guild(GUILD).get_member(recruit.ID).display_name
            await self.bot.get_user(coordinator_id).send(f"{recruit_name} (<@{recruit.ID}>) has cancelled their meeting with you on **{date}** at **{hour}**.")
        except:
            logger.info(f"Could not send DM to coordinator {coordinator_id} about meeting cancellation.")