import logging
import threading
from collections import deque
from collections.abc import Callable
from typing import Literal

from schemas import Alert, DetectionEvent, DwellEvent, QueueEvent, StockEvent

logger = logging.getLogger(__name__)

AnyEvent = DetectionEvent | DwellEvent | StockEvent | QueueEvent | Alert


class BufferFullError(Exception):
    """Raised when SyncBuffer is full and configured with reject_new strategy."""


def _get_event_id(event: AnyEvent) -> str:
    """Extract event_id or alert_id identifier from an event model."""
    return getattr(event, "event_id", getattr(event, "alert_id", ""))


class SyncBuffer:
    """Queues outbound events when the cloud endpoint is unreachable.

    Flushes events in strict FIFO order once connectivity returns.
    `flush()` executes `sink()` outside the buffer lock so `enqueue()`
    never blocks during slow or hanging network requests.
    """

    def __init__(
        self,
        max_buffer_size: int = 10_000,
        overflow_strategy: Literal["drop_oldest", "reject_new"] = "drop_oldest",
    ) -> None:
        if max_buffer_size <= 0:
            raise ValueError(f"max_buffer_size must be positive, got {max_buffer_size}")
        self.max_buffer_size = max_buffer_size
        self.overflow_strategy = overflow_strategy
        self._buffer: deque[AnyEvent] = deque()
        self._lock = threading.Lock()
        self._flush_lock = threading.Lock()

    def enqueue(self, event: AnyEvent) -> None:
        """Enqueue an event.

        If capacity is reached, either evicts the oldest event or rejects the
        new event based on overflow_strategy.
        """
        with self._lock:
            if len(self._buffer) >= self.max_buffer_size:
                if self.overflow_strategy == "drop_oldest":
                    dropped = self._buffer.popleft()
                    dropped_id = _get_event_id(dropped)
                    logger.warning(
                        "SyncBuffer capacity reached (%d); dropping oldest event: %s",
                        self.max_buffer_size,
                        dropped_id,
                    )
                    self._buffer.append(event)
                else:
                    event_id = _get_event_id(event)
                    logger.warning(
                        "SyncBuffer capacity reached (%d); rejecting new event: %s",
                        self.max_buffer_size,
                        event_id,
                    )
                    raise BufferFullError(
                        f"SyncBuffer is at capacity ({self.max_buffer_size}) "
                        "and cannot accept new events."
                    )
            else:
                self._buffer.append(event)

    def flush(self, sink: Callable[[list[AnyEvent]], bool]) -> int:
        """Attempt to send all buffered events via sink (returns True on success).

        Returns count of successfully flushed events.
        Executes sink outside the buffer lock to prevent blocking enqueue calls.
        On sink failure (returns False or raises), buffered events remain queued in original order.
        """
        with self._flush_lock:
            with self._lock:
                if not self._buffer:
                    return 0
                batch = list(self._buffer)

            # sink executes OUTSIDE self._lock
            try:
                success = sink(batch)
            except Exception as exc:
                logger.warning("SyncBuffer sink invocation failed: %s", exc)
                success = False

            if success:
                with self._lock:
                    batch_ids = {_get_event_id(item) for item in batch}
                    while self._buffer and _get_event_id(self._buffer[0]) in batch_ids:
                        popped = self._buffer.popleft()
                        batch_ids.remove(_get_event_id(popped))
                return len(batch)

            return 0

    def pending_count(self) -> int:
        """Return the number of events waiting in the buffer."""
        with self._lock:
            return len(self._buffer)

    def clear(self) -> None:
        """Clear all buffered events."""
        with self._lock:
            self._buffer.clear()
