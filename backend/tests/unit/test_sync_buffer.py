import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from core.schemas import Alert, DetectionEvent, DwellEvent, QueueEvent, StockEvent
from storage.sync_buffer import AnyEvent, BufferFullError, SyncBuffer


def test_sync_buffer_basic_enqueue_and_flush() -> None:
    buffer = SyncBuffer(max_buffer_size=100)
    assert buffer.pending_count() == 0

    now = datetime.now(UTC)
    e1 = StockEvent(
        event_id="stk_1",
        shelf_id="shelf_1",
        timestamp=now,
        status="ok",
        confidence=0.9,
    )
    e2 = QueueEvent(
        event_id="q_1",
        counter_id="c_1",
        timestamp=now + timedelta(seconds=1),
        queue_length=2,
    )

    buffer.enqueue(e1)
    buffer.enqueue(e2)
    assert buffer.pending_count() == 2

    delivered: list[list[AnyEvent]] = []

    def mock_sink(batch: list[AnyEvent]) -> bool:
        delivered.append(batch)
        return True

    flushed_count = buffer.flush(mock_sink)
    assert flushed_count == 2
    assert buffer.pending_count() == 0
    assert len(delivered) == 1
    assert delivered[0] == [e1, e2]


def test_sync_buffer_outage_then_flushes_in_order() -> None:
    """Proof point for FR13: buffer survives outage, flushes in original order on reconnect."""
    buffer = SyncBuffer(max_buffer_size=100)

    t0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)
    e1 = DetectionEvent(
        event_id="det_1",
        track_id="tr_1",
        timestamp=t0,
        bbox=(0, 0, 10, 10),
        event_type="enter",
    )
    e2 = DwellEvent(
        event_id="dw_1",
        zone_id="zone_a",
        track_id="tr_1",
        start_ts=t0,
        end_ts=t0 + timedelta(seconds=20),
        duration_sec=20.0,
    )
    e3 = StockEvent(
        event_id="stk_1",
        shelf_id="shelf_a",
        timestamp=t0 + timedelta(seconds=30),
        status="low",
        confidence=0.85,
    )

    buffer.enqueue(e1)
    buffer.enqueue(e2)
    buffer.enqueue(e3)
    assert buffer.pending_count() == 3

    # Phase 1: Sink returns False (outage)
    def failing_sink_false(_batch: list[AnyEvent]) -> bool:
        return False

    flushed = buffer.flush(failing_sink_false)
    assert flushed == 0
    assert buffer.pending_count() == 3

    # Phase 2: Mid-outage enqueues + sink raising network exception
    e4 = QueueEvent(
        event_id="q_1",
        counter_id="counter_1",
        timestamp=t0 + timedelta(seconds=40),
        queue_length=5,
    )
    e5 = Alert(
        alert_id="alt_1",
        alert_type="queue_congestion",
        severity="critical",
        message="Queue limit exceeded",
        created_at=t0 + timedelta(seconds=45),
    )
    buffer.enqueue(e4)
    buffer.enqueue(e5)
    assert buffer.pending_count() == 5

    def failing_sink_exception(_batch: list[AnyEvent]) -> bool:
        raise ConnectionError("Simulated cloud endpoint unreachable")

    flushed = buffer.flush(failing_sink_exception)
    assert flushed == 0
    assert buffer.pending_count() == 5

    # Phase 3: Connectivity restored -> flush succeeds
    flushed_batches: list[list[AnyEvent]] = []

    def successful_sink(batch: list[AnyEvent]) -> bool:
        flushed_batches.append(batch)
        return True

    flushed = buffer.flush(successful_sink)
    assert flushed == 5
    assert buffer.pending_count() == 0
    assert len(flushed_batches) == 1
    assert flushed_batches[0] == [e1, e2, e3, e4, e5]


def test_sync_buffer_capacity_drop_oldest_eviction_asserted() -> None:
    """Enqueuing past max_buffer_size drops specifically the oldest items in FIFO order."""
    buffer = SyncBuffer(max_buffer_size=3, overflow_strategy="drop_oldest")

    now = datetime.now(UTC)
    events = [
        StockEvent(
            event_id=f"stk_{i}",
            shelf_id="shelf_1",
            timestamp=now + timedelta(seconds=i),
            status="ok",
            confidence=0.9,
        )
        for i in range(5)
    ]

    for ev in events:
        buffer.enqueue(ev)

    # Buffer capped at 3
    assert buffer.pending_count() == 3

    delivered: list[list[AnyEvent]] = []

    def sink(batch: list[AnyEvent]) -> bool:
        delivered.append(batch)
        return True

    flushed = buffer.flush(sink)
    assert flushed == 3
    assert len(delivered) == 1

    # Explicit assertion: stk_0 and stk_1 were evicted; stk_2, stk_3, stk_4 preserved
    received_ids = [getattr(e, "event_id", "") for e in delivered[0]]
    assert "stk_0" not in received_ids
    assert "stk_1" not in received_ids
    assert received_ids == ["stk_2", "stk_3", "stk_4"]
    assert delivered[0] == [events[2], events[3], events[4]]


def test_sync_buffer_non_blocking_enqueue_during_slow_sink() -> None:
    """flush() must not hold buffer lock during sink(); enqueue() stays non-blocking."""
    buffer = SyncBuffer(max_buffer_size=10)

    now = datetime.now(UTC)
    e1 = StockEvent(
        event_id="stk_1",
        shelf_id="shelf_1",
        timestamp=now,
        status="ok",
        confidence=0.9,
    )
    buffer.enqueue(e1)

    sink_entered = threading.Event()
    release_sink = threading.Event()
    flush_done = threading.Event()

    def slow_sink(batch: list[AnyEvent]) -> bool:
        sink_entered.set()
        release_sink.wait(timeout=2.0)
        return True

    def run_flush() -> None:
        buffer.flush(slow_sink)
        flush_done.set()

    t = threading.Thread(target=run_flush)
    t.start()

    assert sink_entered.wait(timeout=1.0), "Sink should be entered"

    # Enqueue a new event while sink is actively running (simulating CV loop)
    start_time = time.perf_counter()
    e2 = StockEvent(
        event_id="stk_2",
        shelf_id="shelf_1",
        timestamp=now + timedelta(seconds=1),
        status="low",
        confidence=0.8,
    )
    buffer.enqueue(e2)
    enqueue_duration = time.perf_counter() - start_time

    # enqueue should return immediately without waiting for slow_sink
    assert enqueue_duration < 0.1, f"Enqueue was blocked for {enqueue_duration}s"
    assert buffer.pending_count() == 2

    # Allow sink to finish
    release_sink.set()
    flush_done.wait(timeout=1.0)
    t.join()

    # e1 was flushed; e2 was enqueued concurrently and remains in buffer
    assert buffer.pending_count() == 1

    remaining: list[list[AnyEvent]] = []

    def sink_remaining(batch: list[AnyEvent]) -> bool:
        remaining.append(batch)
        return True

    buffer.flush(sink_remaining)
    assert len(remaining) == 1
    assert remaining[0] == [e2]


def test_sync_buffer_capacity_reject_new() -> None:
    """When configured with reject_new, overflow raises BufferFullError."""
    buffer = SyncBuffer(max_buffer_size=3, overflow_strategy="reject_new")

    now = datetime.now(UTC)
    events = [
        StockEvent(
            event_id=f"stk_{i}",
            shelf_id="shelf_1",
            timestamp=now + timedelta(seconds=i),
            status="ok",
            confidence=0.9,
        )
        for i in range(3)
    ]

    for ev in events:
        buffer.enqueue(ev)

    assert buffer.pending_count() == 3

    extra_event = StockEvent(
        event_id="stk_overflow",
        shelf_id="shelf_1",
        timestamp=now + timedelta(seconds=10),
        status="ok",
        confidence=0.9,
    )

    with pytest.raises(BufferFullError):
        buffer.enqueue(extra_event)

    assert buffer.pending_count() == 3


def test_sync_buffer_empty_flush() -> None:
    buffer = SyncBuffer(max_buffer_size=10)
    calls: list[list[AnyEvent]] = []

    def sink(batch: list[AnyEvent]) -> bool:
        calls.append(batch)
        return True

    flushed = buffer.flush(sink)
    assert flushed == 0
    assert len(calls) == 0


def test_sync_buffer_invalid_size() -> None:
    with pytest.raises(ValueError):
        SyncBuffer(max_buffer_size=0)
    with pytest.raises(ValueError):
        SyncBuffer(max_buffer_size=-5)
