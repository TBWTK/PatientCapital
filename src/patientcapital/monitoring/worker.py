"""Four-slot scheduled monitor worker with an injectable clock."""

from __future__ import annotations

import json
import time as time_module
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from patientcapital.config import Settings
from patientcapital.marketdata.moex import MoexIssProvider
from patientcapital.monitoring.service import run_monitor
from patientcapital.persistence.database import Database

Clock = Callable[[], datetime]
Sleeper = Callable[[float], None]


def parse_monitor_schedule(value: str) -> tuple[time, ...]:
    parts = [item.strip() for item in value.split(",") if item.strip()]
    if len(parts) != 4:
        raise ValueError("monitor schedule must contain exactly four times")
    try:
        parsed = tuple(time.fromisoformat(item) for item in parts)
    except ValueError as error:
        raise ValueError("monitor schedule contains an invalid time") from error
    if any(item.second or item.microsecond or item.tzinfo is not None for item in parsed):
        raise ValueError("monitor schedule accepts local HH:MM values only")
    if len(set(parsed)) != 4 or tuple(sorted(parsed)) != parsed:
        raise ValueError("monitor schedule times must be unique and ascending")
    return parsed


def scheduled_slots_for_day(
    day: date,
    schedule: tuple[time, ...],
    timezone: ZoneInfo,
) -> tuple[datetime, ...]:
    return tuple(datetime.combine(day, item, tzinfo=timezone) for item in schedule)


def latest_due_slot(
    current: datetime,
    schedule: tuple[time, ...],
    timezone: ZoneInfo,
) -> datetime:
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("current time must be timezone-aware")
    local = current.astimezone(timezone)
    due = [
        slot
        for slot in scheduled_slots_for_day(local.date(), schedule, timezone)
        if slot <= local
    ]
    if due:
        return due[-1]
    return scheduled_slots_for_day(local.date() - timedelta(days=1), schedule, timezone)[-1]


def next_scheduled_slot(
    current: datetime,
    schedule: tuple[time, ...],
    timezone: ZoneInfo,
) -> datetime:
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("current time must be timezone-aware")
    local = current.astimezone(timezone)
    future = [
        slot for slot in scheduled_slots_for_day(local.date(), schedule, timezone) if slot > local
    ]
    if future:
        return future[0]
    return scheduled_slots_for_day(local.date() + timedelta(days=1), schedule, timezone)[0]


def run_worker(
    settings: Settings,
    *,
    clock: Clock = lambda: datetime.now(UTC),
    sleeper: Sleeper = time_module.sleep,
) -> None:
    schedule = parse_monitor_schedule(settings.monitor_schedule)
    timezone = ZoneInfo(settings.monitor_timezone)
    provider = MoexIssProvider(
        base_url=settings.moex_iss_base_url,
        timeout_seconds=settings.moex_timeout_seconds,
        max_age_seconds=settings.moex_max_age_seconds,
    )
    database = Database(settings.database_url)
    try:
        while True:
            observed_at = clock()
            scheduled_for = latest_due_slot(observed_at, schedule, timezone)
            with database.sessions() as session:
                result = run_monitor(
                    session,
                    provider,
                    scheduled_for=scheduled_for,
                    observed_at=observed_at,
                )
            print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False), flush=True)
            next_slot = next_scheduled_slot(clock(), schedule, timezone)
            seconds = max(
                1.0,
                (next_slot.astimezone(UTC) - clock().astimezone(UTC)).total_seconds(),
            )
            sleeper(seconds)
    finally:
        database.close()


def main() -> None:
    run_worker(Settings())


if __name__ == "__main__":
    main()
