
class Person:
    def __init__(self, ID: int):
        self.ID = ID

    def __repr__(self):
        return f"Person(id={self.ID})"


class Recruit(Person):
    def __init__(self, ID: int):
        super().__init__(ID)
        self.meeting = None


class Coordinator(Person):
    def __init__(self, ID: int):
        super().__init__(ID)
        self.time_slots = []

    def to_dict(self):
        return {
            'time_slots': [{'date': ts.date, 'hour': ts.hour,
                            'recruit_id': ts.recruit.ID if ts.recruit else None} for ts in self.time_slots]
        }

    def __repr__(self):
        return f"Coordinator(id={self.ID}, time_slots={self.time_slots})"


class TimeSlot:
    def __init__(self, date: str, hour: str):
        self.date = date
        self.hour = hour
        self.is_booked = False
        self.recruit = None
        self.coordinator = None

    def book(self, recruit: Recruit, coordinator: Coordinator):
        self.is_booked = True
        self.recruit = recruit
        recruit.meeting = self
        self.coordinator = coordinator

    def cancel(self):
        if self.recruit:
            self.recruit.meeting = None
        self.is_booked = False
        self.recruit = None
        self.coordinator = None

    def __repr__(self):
        return f"TimeSlot(date={self.date}, hour={self.hour}, is_booked={self.is_booked})"
