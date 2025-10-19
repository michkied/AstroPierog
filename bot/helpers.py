from datetime import datetime, timedelta


def is_within_24_hours(date_str: str, hour_str: str) -> bool:
    now = datetime.now()
    day, month = map(int, date_str.split("."))
    hour, minute = map(int, hour_str.split(":"))
    target = datetime(year=now.year, month=month, day=day, hour=hour, minute=minute)
    return target - now <= timedelta(hours=24)

