from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.platform.clock import FrozenClock, SystemClock, to_legal_date
from app.platform.context import request_id_from_header
from app.platform.ids import is_uuid7, new_id
from app.platform.logging import safe_path


def test_new_id_is_uuid7_and_time_ordered() -> None:
    ids = [new_id() for _ in range(1000)]
    assert all(is_uuid7(i) for i in ids)
    assert ids == sorted(ids), "UUIDv7 values generated in sequence must sort in creation order"
    assert len(set(ids)) == len(ids)


def test_is_uuid7_rejects_other_versions() -> None:
    assert not is_uuid7(uuid.uuid4())


def test_legal_date_crosses_midnight_in_india_not_utc() -> None:
    # 18:29 UTC on 31 Mar is 23:59 IST (still FY 2025-26); 18:30 UTC is 00:00 IST on 1 Apr (FY 2026-27).
    assert to_legal_date(datetime(2026, 3, 31, 18, 29, tzinfo=UTC)) == date(2026, 3, 31)
    assert to_legal_date(datetime(2026, 3, 31, 18, 30, tzinfo=UTC)) == date(2026, 4, 1)


def test_legal_date_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        to_legal_date(datetime(2026, 1, 1, 12, 0))  # noqa: DTZ001 - deliberately naive


@given(st.datetimes(timezones=st.just(UTC)))
def test_legal_date_is_never_behind_utc_date(instant: datetime) -> None:
    # India is UTC+05:30, so the legal date equals the UTC date or the day after.
    assert (to_legal_date(instant) - instant.date()).days in (0, 1)


def test_frozen_clock_advances_only_when_told() -> None:
    clock = FrozenClock(datetime(2026, 9, 30, 18, 0, tzinfo=UTC))
    assert clock.legal_today() == date(2026, 9, 30)  # 23:30 IST
    clock.advance(timedelta(minutes=30))
    assert clock.legal_today() == date(2026, 10, 1)
    assert clock.now().tzinfo is UTC


def test_frozen_clock_normalises_other_timezones_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    clock = FrozenClock(datetime(2026, 10, 1, 0, 15, tzinfo=ist))
    assert clock.now() == datetime(2026, 9, 30, 18, 45, tzinfo=UTC)


def test_system_clock_is_aware_utc() -> None:
    assert SystemClock().now().tzinfo is UTC


@pytest.mark.parametrize(
    ("header", "kept"),
    [
        ("01J9ZKQ7Y8ABCDEF", True),
        ("abc", False),
        ("x" * 65, False),
        ("bad id with spaces", False),
        (None, False),
    ],
)
def test_request_id_reuses_only_well_formed_headers(header: str | None, kept: bool) -> None:
    value = request_id_from_header(header)
    assert (value == header) is kept
    if not kept:
        assert is_uuid7(uuid.UUID(value))


def test_calendar_paths_are_redacted_in_logs() -> None:
    assert safe_path("/v1/calendar/secret-token.ics") == "/v1/calendar/[redacted]"
    assert safe_path("/v1/me") == "/v1/me"
