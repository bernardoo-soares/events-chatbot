from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def now_in_timezone(timezone: str) -> datetime:
    return datetime.now(ZoneInfo(timezone))

