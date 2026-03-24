from datetime import date, datetime, timedelta, timezone

import pytest

from pantry_server.core.datetime_formatting import (
    ensure_timezone_aware,
    format_datetime_display,
    format_days_until,
    format_display_date,
    format_iso_date,
    format_iso_datetime,
    format_relative_time,
    format_time,
)


def test_format_iso_date_formats_date() -> None:
    assert format_iso_date(value=date(2026, 3, 24)) == "2026-03-24"


def test_format_iso_date_raises_for_non_date() -> None:
    with pytest.raises(TypeError):
        format_iso_date(value="2026-03-24")  # type: ignore[arg-type]


def test_format_iso_datetime_without_timezone() -> None:
    value = datetime(2026, 3, 24, 15, 30, 45)
    assert format_iso_datetime(value=value) == "2026-03-24T15:30:45"


def test_format_iso_datetime_with_timezone_when_requested() -> None:
    value = datetime(2026, 3, 24, 15, 30, 45, tzinfo=timezone.utc)
    assert format_iso_datetime(value=value, include_timezone=True) == "2026-03-24T15:30:45+0000"


def test_format_iso_datetime_raises_for_non_datetime() -> None:
    with pytest.raises(TypeError):
        format_iso_datetime(value="bad")  # type: ignore[arg-type]


def test_format_display_date_styles() -> None:
    value = date(2026, 3, 24)
    assert format_display_date(value=value, style="full") == "March 24, 2026"
    assert format_display_date(value=value, style="short") == "Mar 24, 2026"
    assert format_display_date(value=value, style="verbose") == "Tuesday, March 24, 2026"


def test_format_display_date_raises_for_non_date() -> None:
    with pytest.raises(TypeError):
        format_display_date(value="bad")  # type: ignore[arg-type]


def test_format_time_default_and_24h() -> None:
    value = datetime(2026, 3, 24, 15, 5)
    assert format_time(value=value) == "03:05 PM"
    assert format_time(value=value, use_24h=True) == "15:05"


def test_format_time_raises_for_date_without_time_component() -> None:
    with pytest.raises(ValueError):
        format_time(value=date(2026, 3, 24))


def test_format_time_raises_for_invalid_type() -> None:
    with pytest.raises(TypeError):
        format_time(value=123)  # type: ignore[arg-type]


def test_format_relative_time_for_recent_seconds_future_and_past() -> None:
    reference = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    assert format_relative_time(value=reference + timedelta(seconds=30), reference=reference) == "just now"
    assert (
        format_relative_time(value=reference - timedelta(seconds=30), reference=reference)
        == "a moment ago"
    )


def test_format_relative_time_minutes_hours_days_weeks_months_years() -> None:
    reference = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    assert format_relative_time(value=reference + timedelta(minutes=1), reference=reference) == "1 minute from now"
    assert format_relative_time(value=reference - timedelta(minutes=2), reference=reference) == "2 minutes ago"
    assert format_relative_time(value=reference + timedelta(hours=1), reference=reference) == "1 hour from now"
    assert format_relative_time(value=reference - timedelta(hours=3), reference=reference) == "3 hours ago"
    assert format_relative_time(value=reference + timedelta(days=1), reference=reference) == "1 day from now"
    assert format_relative_time(value=reference - timedelta(days=8), reference=reference) == "1 week ago"
    assert format_relative_time(value=reference + timedelta(days=40), reference=reference) == "1 month from now"
    assert format_relative_time(value=reference - timedelta(days=400), reference=reference) == "1 year ago"


def test_format_relative_time_handles_naive_datetimes() -> None:
    reference = datetime(2026, 3, 24, 12, 0)
    value = datetime(2026, 3, 24, 12, 1)
    assert format_relative_time(value=value, reference=reference) == "1 minute from now"


def test_format_relative_time_raises_for_invalid_inputs() -> None:
    with pytest.raises(TypeError):
        format_relative_time(value="bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        format_relative_time(value=datetime(2026, 3, 24, 12, 0), reference="bad")  # type: ignore[arg-type]


def test_format_days_until_expired_today_tomorrow_and_future() -> None:
    ref = date(2026, 3, 24)
    assert format_days_until(expiry_date=ref - timedelta(days=2), reference=ref) == "expired 2 days ago"
    assert format_days_until(expiry_date=ref, reference=ref) == "expires today"
    assert format_days_until(expiry_date=ref + timedelta(days=1), reference=ref) == "expires tomorrow"
    assert format_days_until(expiry_date=ref + timedelta(days=5), reference=ref) == "expires in 5 days"


def test_format_days_until_raises_for_invalid_inputs() -> None:
    with pytest.raises(TypeError):
        format_days_until(expiry_date="bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        format_days_until(expiry_date=date(2026, 3, 24), reference="bad")  # type: ignore[arg-type]


def test_format_datetime_display_with_and_without_time() -> None:
    value = datetime(2026, 3, 24, 15, 5)
    assert format_datetime_display(value=value) == "March 24, 2026 at 03:05 PM"
    assert format_datetime_display(value=value, include_time=False) == "March 24, 2026"
    assert (
        format_datetime_display(value=value, date_style="short", use_24h=True)
        == "Mar 24, 2026 at 15:05"
    )


def test_format_datetime_display_raises_for_invalid_value() -> None:
    with pytest.raises(TypeError):
        format_datetime_display(value="bad")  # type: ignore[arg-type]


def test_ensure_timezone_aware_adds_default_timezone_and_preserves_existing() -> None:
    naive = datetime(2026, 3, 24, 15, 5)
    aware = datetime(2026, 3, 24, 15, 5, tzinfo=timezone.utc)

    result_naive = ensure_timezone_aware(value=naive)
    result_aware = ensure_timezone_aware(value=aware)

    assert result_naive.tzinfo == timezone.utc
    assert result_aware is aware


def test_ensure_timezone_aware_raises_for_invalid_value() -> None:
    with pytest.raises(TypeError):
        ensure_timezone_aware(value="bad")  # type: ignore[arg-type]
