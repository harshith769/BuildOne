"""Time. Code never calls datetime.now() or date.today() directly; it receives a Clock (.claude/rules/backend.md).

Instants are timezone-aware UTC datetimes. Legal due dates are plain `date` values in the legal timezone
(Asia/Kolkata), because a filing due "on 30 September" means 30 September in India whatever the server's clock says.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

LEGAL_TZ = ZoneInfo("Asia/Kolkata")


class Clock(Protocol):
    def now(self) -> datetime:
        """Current instant, timezone-aware, in UTC."""
        ...

    def legal_today(self) -> date:
        """Today's date in the legal timezone (Asia/Kolkata)."""
        ...


def to_legal_date(instant: datetime, tz: ZoneInfo = LEGAL_TZ) -> date:
    """The calendar date of `instant` in the legal timezone. Rejects naive datetimes."""
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("instant must be timezone-aware")
    return instant.astimezone(tz).date()


class SystemClock:
    """The real clock."""

    def __init__(self, tz: ZoneInfo = LEGAL_TZ) -> None:
        self._tz = tz

    def now(self) -> datetime:
        return datetime.now(UTC)

    def legal_today(self) -> date:
        return to_legal_date(self.now(), self._tz)


class FrozenClock:
    """A clock that only moves when told to. For tests (month-end, financial-year and midnight boundaries)."""

    def __init__(self, instant: datetime, tz: ZoneInfo = LEGAL_TZ) -> None:
        if instant.tzinfo is None:
            raise ValueError("instant must be timezone-aware")
        self._now = instant.astimezone(UTC)
        self._tz = tz

    def now(self) -> datetime:
        return self._now

    def legal_today(self) -> date:
        return to_legal_date(self._now, self._tz)

    def advance(self, delta: timedelta) -> None:
        self._now += delta

    def set(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("instant must be timezone-aware")
        self._now = instant.astimezone(UTC)
