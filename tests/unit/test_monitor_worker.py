from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from patientcapital.config import Settings
from patientcapital.marketdata.errors import MarketDataError
from patientcapital.monitoring import worker as worker_module
from patientcapital.monitoring.worker import (
    latest_due_slot,
    next_scheduled_slot,
    parse_monitor_schedule,
    scheduled_slots_for_day,
)


def test_monitor_schedule_has_four_moscow_observations_per_day() -> None:
    schedule = parse_monitor_schedule("06:00,10:00,14:00,18:00")
    timezone = ZoneInfo("Europe/Moscow")
    slots = scheduled_slots_for_day(date(2026, 8, 16), schedule, timezone)

    assert len(slots) == 4
    assert [slot.hour for slot in slots] == [6, 10, 14, 18]
    assert all(slot.utcoffset() is not None for slot in slots)


def test_monitor_schedule_resolves_latest_due_and_next_slot_across_day_boundary() -> None:
    schedule = parse_monitor_schedule("06:00,10:00,14:00,18:00")
    timezone = ZoneInfo("Europe/Moscow")
    current = datetime(2026, 8, 16, 9, 30, tzinfo=UTC)  # 12:30 Moscow

    assert latest_due_slot(current, schedule, timezone).isoformat() == "2026-08-16T10:00:00+03:00"
    assert next_scheduled_slot(current, schedule, timezone).isoformat() == (
        "2026-08-16T14:00:00+03:00"
    )
    after_last = datetime(2026, 8, 16, 16, 0, tzinfo=UTC)  # 19:00 Moscow
    assert next_scheduled_slot(after_last, schedule, timezone).isoformat() == (
        "2026-08-17T06:00:00+03:00"
    )


@pytest.mark.parametrize("value", ["", "06:00", "06:00,10:00,14:00,14:00", "25:00,a,14:00,18:00"])
def test_monitor_schedule_rejects_any_shape_other_than_four_unique_times(value: str) -> None:
    with pytest.raises(ValueError):
        parse_monitor_schedule(value)


def test_monitor_schedule_and_slots_reject_ambiguous_inputs() -> None:
    with pytest.raises(ValueError, match="HH:MM"):
        parse_monitor_schedule("06:00:01,10:00,14:00,18:00")
    with pytest.raises(ValueError, match="ascending"):
        parse_monitor_schedule("10:00,06:00,14:00,18:00")
    schedule = parse_monitor_schedule("06:00,10:00,14:00,18:00")
    timezone = ZoneInfo("Europe/Moscow")
    with pytest.raises(ValueError, match="timezone-aware"):
        latest_due_slot(datetime(2026, 8, 16, 10), schedule, timezone)
    with pytest.raises(ValueError, match="timezone-aware"):
        next_scheduled_slot(datetime(2026, 8, 16, 10), schedule, timezone)
    before_first = datetime(2026, 8, 16, 1, 0, tzinfo=UTC)
    assert latest_due_slot(before_first, schedule, timezone).isoformat() == (
        "2026-08-15T18:00:00+03:00"
    )


def test_worker_runs_latest_slot_once_and_closes_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[datetime, datetime]] = []

    class WorkerStopped(RuntimeError):
        pass

    class FakeResult:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            return {"status": "no_change"}

    class FakeDatabase:
        closed = False

        def __init__(self, url: str) -> None:
            assert url.endswith("/patientcapital")

        @contextmanager
        def sessions(self) -> Iterator[object]:
            yield object()

        def close(self) -> None:
            FakeDatabase.closed = True

    class FakeProvider:
        name = "fake-provider"

        def __init__(self, **kwargs: object) -> None:
            assert kwargs["max_age_seconds"] == 345_600

    class FakeAcquired:
        class Record:
            provider = "fake-provider"

        record = Record()
        candidates = ()

    def fake_acquire(
        session: object,
        provider: object,
        **kwargs: object,
    ) -> FakeAcquired:
        assert session is not None and provider is not None
        assert kwargs["cache_seconds"] == 14_400
        assert kwargs["force"] is True
        assert str(kwargs["idempotency_key"]).startswith("monitor-slot:")
        return FakeAcquired()

    def fake_run_monitor(
        session: object,
        provider: object,
        *,
        scheduled_for: datetime,
        observed_at: datetime,
    ) -> FakeResult:
        assert session is not None and provider is not None
        calls.append((scheduled_for, observed_at))
        return FakeResult()

    current = datetime(2026, 8, 16, 9, 30, tzinfo=UTC)
    monkeypatch.setattr(worker_module, "Database", FakeDatabase)
    monkeypatch.setattr(worker_module, "MoexIssProvider", FakeProvider)
    monkeypatch.setattr(worker_module, "acquire_market_research", fake_acquire)
    monkeypatch.setattr(worker_module, "run_monitor", fake_run_monitor)
    with pytest.raises(WorkerStopped):
        worker_module.run_worker(
            Settings(),
            clock=lambda: current,
            sleeper=lambda _: (_ for _ in ()).throw(WorkerStopped()),
        )

    assert calls == [
        (datetime(2026, 8, 16, 10, 0, tzinfo=ZoneInfo("Europe/Moscow")), current)
    ]
    assert FakeDatabase.closed is True


def test_snapshot_provider_wrappers_preserve_candidates_and_provider_errors() -> None:
    snapshot = worker_module._SnapshotProvider("snapshot-provider", ())
    assert snapshot.name == "snapshot-provider"
    assert snapshot.discover(calculated_at=datetime.now(UTC)) == ()

    source_error = MarketDataError("MOEX_UNAVAILABLE", "market source is unavailable")
    failed = worker_module._FailedSnapshotProvider("failed-provider", source_error)
    assert failed.name == "failed-provider"
    with pytest.raises(MarketDataError) as raised:
        failed.discover(calculated_at=datetime.now(UTC))
    assert raised.value is source_error
