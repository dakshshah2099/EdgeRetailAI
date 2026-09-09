import math
import uuid
from typing import Literal

from core.schemas import Alert, QueueEvent, StockEvent


class AlertEngine:
    """Turns threshold breaches into Alerts. Debounced: a condition that
    stays breached across many consecutive events does not re-fire a new
    Alert every time — it fires once, then stays open until the condition
    clears, at which point resolved_at is set on the existing Alert.

    Supports severity escalation: if an already-open warning alert experiences
    a critical breach, it escalates in-place (retaining alert_id and created_at).
    """

    def __init__(
        self,
        low_stock_threshold: float,
        queue_congestion_length: int,
        queue_critical_margin: float = 1.5,
    ) -> None:
        self.low_stock_threshold = float(low_stock_threshold)
        self.queue_congestion_length = int(queue_congestion_length)
        self.queue_critical_margin = float(queue_critical_margin)

        # Mapping of shelf_id -> open Alert
        self._open_stock_alerts: dict[str, Alert] = {}
        # Mapping of counter_id -> open Alert
        self._open_queue_alerts: dict[str, Alert] = {}

    def process_stock_event(self, event: StockEvent) -> Alert | None:
        """Returns a new Alert if this event causes a low_stock condition
        to newly open (not already open for this shelf_id), or escalates
        an existing warning alert to critical if status drops to empty."""
        if event.confidence < self.low_stock_threshold:
            return None

        if event.shelf_id in self._open_stock_alerts:
            open_alert = self._open_stock_alerts[event.shelf_id]
            # Escalate warning -> critical if stock is now completely empty
            if open_alert.severity == "warning" and event.status == "empty":
                escalated = Alert(
                    alert_id=open_alert.alert_id,
                    alert_type=open_alert.alert_type,
                    severity="critical",
                    zone_id=open_alert.zone_id,
                    message=f"Shelf {event.shelf_id} is out of stock",
                    created_at=open_alert.created_at,
                    resolved_at=None,
                )
                self._open_stock_alerts[event.shelf_id] = escalated
                return escalated
            # Already open and not escalating: debounce
            return None

        if event.status == "empty":
            severity: Literal["warning", "critical"] = "critical"
            message = f"Shelf {event.shelf_id} is out of stock"
        elif event.status == "low":
            severity = "warning"
            message = f"Shelf {event.shelf_id} is low on stock"
        else:
            return None

        alert = Alert(
            alert_id=f"alert_{uuid.uuid4().hex[:12]}",
            alert_type="low_stock",
            severity=severity,
            zone_id=event.shelf_id,
            message=message,
            created_at=event.timestamp,
            resolved_at=None,
        )
        self._open_stock_alerts[event.shelf_id] = alert
        return alert

    def process_queue_event(self, event: QueueEvent) -> Alert | None:
        """Returns a new Alert if queue_length >= queue_congestion_length or if
        congestion is predicted (predicted_queue_length >= queue_congestion_length)
        and no congestion alert is currently open for this counter_id.
        Escalates predicted warnings to actual congestion, or warning to critical."""
        critical_threshold = math.ceil(self.queue_congestion_length * self.queue_critical_margin)
        is_actual_breach = event.queue_length >= self.queue_congestion_length
        is_critical = event.queue_length >= critical_threshold
        is_predicted_breach = (
            event.predicted_queue_length is not None
            and event.predicted_queue_length >= self.queue_congestion_length
        )

        if not is_actual_breach and not is_predicted_breach:
            return None

        if event.counter_id in self._open_queue_alerts:
            open_alert = self._open_queue_alerts[event.counter_id]
            # Escalate warning -> critical if queue length exceeds critical threshold
            if open_alert.severity == "warning" and is_critical:
                escalated = Alert(
                    alert_id=open_alert.alert_id,
                    alert_type=open_alert.alert_type,
                    severity="critical",
                    zone_id=open_alert.zone_id,
                    message=(
                        f"Checkout counter {event.counter_id} has {event.queue_length} people"
                        " waiting — consider opening another counter"
                    ),
                    created_at=open_alert.created_at,
                    resolved_at=None,
                )
                self._open_queue_alerts[event.counter_id] = escalated
                return escalated

            # Escalate predictive warning -> active actual congestion alert
            if is_actual_breach and "predicted to congest" in open_alert.message:
                actual_severity: Literal["warning", "critical"] = (
                    "critical" if is_critical else "warning"
                )
                updated = Alert(
                    alert_id=open_alert.alert_id,
                    alert_type=open_alert.alert_type,
                    severity=actual_severity,
                    zone_id=open_alert.zone_id,
                    message=(
                        f"Checkout counter {event.counter_id} has {event.queue_length} people"
                        " waiting — consider opening another counter"
                    ),
                    created_at=open_alert.created_at,
                    resolved_at=None,
                )
                self._open_queue_alerts[event.counter_id] = updated
                return updated

            # Already open and not escalating: debounce
            return None

        if is_actual_breach:
            severity: Literal["warning", "critical"] = "critical" if is_critical else "warning"
            message = (
                f"Checkout counter {event.counter_id} has {event.queue_length} people waiting"
                " — consider opening another counter"
            )
        else:
            severity = "warning"
            pred_count = event.predicted_queue_length
            message = (
                f"Checkout counter {event.counter_id} predicted to congest"
                f" (~{pred_count} people in ~3m) — recommend opening another counter"
            )

        alert = Alert(
            alert_id=f"alert_{uuid.uuid4().hex[:12]}",
            alert_type="queue_congestion",
            severity=severity,
            zone_id=event.counter_id,
            message=message,
            created_at=event.timestamp,
            resolved_at=None,
        )
        self._open_queue_alerts[event.counter_id] = alert
        return alert

    def check_resolutions(
        self,
        latest_stock_events: dict[str, StockEvent],
        latest_queue_events: dict[str, QueueEvent],
    ) -> list[Alert]:
        """Given the latest known state per shelf_id/counter_id, return
        updated (resolved) Alert objects for any previously-open alert
        whose condition has cleared.

        Resolution requires status == "ok"; low-confidence uncertainty on
        bad states does not clear an alert.
        """
        resolved: list[Alert] = []

        # Check stock alert resolutions
        for shelf_id in list(self._open_stock_alerts.keys()):
            if shelf_id in latest_stock_events:
                stock_ev = latest_stock_events[shelf_id]
                is_cleared = (
                    stock_ev.status == "ok"
                    and stock_ev.confidence >= self.low_stock_threshold
                )
                if is_cleared:
                    open_alert = self._open_stock_alerts.pop(shelf_id)
                    resolved_alert = Alert(
                        alert_id=open_alert.alert_id,
                        alert_type=open_alert.alert_type,
                        severity=open_alert.severity,
                        zone_id=open_alert.zone_id,
                        message=open_alert.message,
                        created_at=open_alert.created_at,
                        resolved_at=stock_ev.timestamp,
                    )
                    resolved.append(resolved_alert)

        # Check queue alert resolutions
        for counter_id in list(self._open_queue_alerts.keys()):
            if counter_id in latest_queue_events:
                queue_ev = latest_queue_events[counter_id]
                is_cleared = queue_ev.queue_length < self.queue_congestion_length and (
                    queue_ev.predicted_queue_length is None
                    or queue_ev.predicted_queue_length < self.queue_congestion_length
                )
                if is_cleared:
                    open_alert = self._open_queue_alerts.pop(counter_id)
                    resolved_alert = Alert(
                        alert_id=open_alert.alert_id,
                        alert_type=open_alert.alert_type,
                        severity=open_alert.severity,
                        zone_id=open_alert.zone_id,
                        message=open_alert.message,
                        created_at=open_alert.created_at,
                        resolved_at=queue_ev.timestamp,
                    )
                    resolved.append(resolved_alert)

        return resolved

    def get_open_alerts(self) -> list[Alert]:
        """Return list of all currently active/open alerts."""
        return list(self._open_stock_alerts.values()) + list(self._open_queue_alerts.values())

    def reset(self) -> None:
        """Clear all internal tracking states for open alerts."""
        self._open_stock_alerts.clear()
        self._open_queue_alerts.clear()
