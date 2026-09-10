"""Artificial data seeding script for EdgeRetail AI (SIH26179).

Generates realistic 24-hour retail telemetry in high-speed batches:
- Footfall enters/exits & multi-zone shopper tracking coordinates for dwell heatmaps.
- Multi-lane checkout queue monitoring and congestion spikes.
- Shelf stock depletion events across multiple store categories.
- Real-time incident alerts with mixed severities and resolution lifecycles.
- Configures realistic store zones in config.yaml.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

# Ensure backend directory is in python search path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from storage.db import get_connection, init_db

DEFAULT_ZONES: list[dict[str, Any]] = [
    {
        "zone_id": "zone_entrance_exit",
        "zone_type": "entry_exit",
        "label": "Main Entrance / Exit",
        "polygon": [[40, 360], [240, 360], [240, 470], [40, 470]],
    },
    {
        "zone_id": "zone_shelf_beverages",
        "zone_type": "shelf",
        "label": "Shelf 1 - Cold Beverages",
        "polygon": [[50, 80], [220, 80], [220, 240], [50, 240]],
    },
    {
        "zone_id": "zone_shelf_snacks",
        "zone_type": "shelf",
        "label": "Shelf 2 - Snacks & Bakery",
        "polygon": [[250, 80], [420, 80], [420, 240], [250, 240]],
    },
    {
        "zone_id": "zone_shelf_electronics",
        "zone_type": "shelf",
        "label": "Shelf 3 - Tech & Accessories",
        "polygon": [[450, 80], [610, 80], [610, 240], [450, 240]],
    },
    {
        "zone_id": "zone_display_promo",
        "zone_type": "product_display",
        "label": "Promotional Island Display",
        "polygon": [[220, 260], [380, 260], [380, 340], [220, 340]],
    },
    {
        "zone_id": "zone_queue_checkout_1",
        "zone_type": "checkout",
        "label": "Checkout Counter 1",
        "polygon": [[300, 350], [440, 350], [440, 460], [300, 460]],
    },
    {
        "zone_id": "zone_queue_checkout_2",
        "zone_type": "checkout",
        "label": "Checkout Counter 2",
        "polygon": [[470, 350], [610, 350], [610, 460], [470, 460]],
    },
]


def update_config_zones(config_path: Path) -> None:
    """Ensure config.yaml has the full multi-zone layout."""
    raw_cfg: dict[str, Any] = {}
    if config_path.is_file():
        with config_path.open("r", encoding="utf-8") as f:
            raw_cfg = yaml.safe_load(f) or {}

    raw_cfg["zones"] = DEFAULT_ZONES
    if "low_stock_confidence_threshold" not in raw_cfg:
        raw_cfg["low_stock_confidence_threshold"] = 0.6
    if "queue_congestion_length" not in raw_cfg:
        raw_cfg["queue_congestion_length"] = 4

    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw_cfg, f, default_flow_style=False, sort_keys=False)
    print(f"Updated store zones in {config_path} ({len(DEFAULT_ZONES)} zones configured)")


def clear_existing_data(db_path: Path) -> None:
    """Clear simulation tables for a fresh seeded run."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM detection_events;")
            conn.execute("DELETE FROM dwell_events;")
            conn.execute("DELETE FROM stock_events;")
            conn.execute("DELETE FROM queue_events;")
            conn.execute("DELETE FROM alerts;")
        print(f"Cleared existing simulation events from {db_path}")
    finally:
        conn.close()


def seed_database(db_path: Path, hours: int = 24) -> None:
    """Generate and insert realistic 24-hour retail telemetry in high-speed batches."""
    init_db(db_path)
    rng = random.Random(42)

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    print(f"Generating synthetic telemetry from {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} to {now.strftime('%Y-%m-%d %H:%M:%S UTC')}...")

    detection_rows: list[tuple] = []
    dwell_rows: list[tuple] = []
    queue_rows: list[tuple] = []
    stock_rows: list[tuple] = []
    alert_rows: list[tuple] = []

    shopper_idx = 1000
    total_enters = 0
    total_exits = 0

    # Zone centroids & bounds for jittered detection points
    zone_centers = {
        "zone_shelf_beverages": (135, 160, 80, 140),
        "zone_shelf_snacks": (335, 160, 80, 140),
        "zone_shelf_electronics": (530, 160, 80, 140),
        "zone_display_promo": (300, 300, 60, 120),
        "zone_queue_checkout_1": (370, 405, 50, 100),
        "zone_queue_checkout_2": (540, 405, 50, 100),
    }

    # 1. Simulate hourly shoppers
    for h in range(hours):
        hour_start = start_time + timedelta(hours=h)
        hour_of_day = hour_start.hour

        # Realistic retail shopping volume curve
        if 0 <= hour_of_day < 7:
            shopper_rate = rng.randint(0, 3)
        elif 7 <= hour_of_day < 11:
            shopper_rate = rng.randint(25, 45)
        elif 11 <= hour_of_day < 14:
            shopper_rate = rng.randint(70, 120)  # lunch peak
        elif 14 <= hour_of_day < 17:
            shopper_rate = rng.randint(40, 65)
        elif 17 <= hour_of_day < 21:
            shopper_rate = rng.randint(80, 135)  # evening rush
        else:
            shopper_rate = rng.randint(15, 30)

        for _ in range(shopper_rate):
            shopper_idx += 1
            track_id = f"trk_{shopper_idx:05d}"
            enter_minute = rng.randint(0, 59)
            enter_second = rng.randint(0, 59)
            enter_ts = hour_start + timedelta(minutes=enter_minute, seconds=enter_second)
            if enter_ts > now:
                continue

            # Enter event at entrance
            detection_rows.append((
                f"det_ent_{shopper_idx}",
                track_id,
                enter_ts.isoformat(),
                rng.randint(60, 180),
                rng.randint(370, 440),
                rng.randint(50, 75),
                rng.randint(120, 160),
                "zone_entrance_exit",
                "enter",
            ))
            total_enters += 1

            # Browsing stops (1 to 3 zones visited)
            num_stops = rng.choices([1, 2, 3], weights=[0.4, 0.4, 0.2])[0]
            visited_zones = rng.sample(list(zone_centers.keys()), num_stops)

            current_shopper_ts = enter_ts
            for z_id in visited_zones:
                dwell_sec = round(rng.uniform(20.0, 140.0), 1)
                current_shopper_ts += timedelta(seconds=rng.uniform(15.0, 60.0))
                if current_shopper_ts > now:
                    break

                # Detections inside zone for heatmap clustering
                cx, cy, std_w, std_h = zone_centers[z_id]
                for p_idx in range(rng.randint(2, 3)):
                    det_ts = current_shopper_ts + timedelta(seconds=p_idx * 10)
                    if det_ts > now:
                        break
                    detection_rows.append((
                        f"det_in_{shopper_idx}_{z_id}_{p_idx}",
                        track_id,
                        det_ts.isoformat(),
                        max(20, int(rng.gauss(cx, 18))),
                        max(20, int(rng.gauss(cy, 18))),
                        max(40, int(rng.gauss(std_w, 8))),
                        max(80, int(rng.gauss(std_h, 12))),
                        z_id,
                        "in_zone",
                    ))

                # Save dwell record
                dwell_end = current_shopper_ts + timedelta(seconds=dwell_sec)
                dwell_rows.append((
                    f"dwl_{shopper_idx}_{z_id}",
                    z_id,
                    track_id,
                    current_shopper_ts.isoformat(),
                    min(dwell_end, now).isoformat(),
                    dwell_sec,
                ))
                current_shopper_ts = dwell_end

            # Exit simulation: 88% leave if visited > 15 mins ago
            is_recent = (now - enter_ts).total_seconds() < 900
            should_exit = (not is_recent and rng.random() < 0.92) or (is_recent and rng.random() < 0.25)
            if should_exit:
                exit_ts = current_shopper_ts + timedelta(seconds=rng.uniform(20.0, 90.0))
                if exit_ts <= now:
                    detection_rows.append((
                        f"det_ext_{shopper_idx}",
                        track_id,
                        exit_ts.isoformat(),
                        rng.randint(70, 190),
                        rng.randint(370, 440),
                        rng.randint(50, 75),
                        rng.randint(120, 160),
                        "zone_entrance_exit",
                        "exit",
                    ))
                    total_exits += 1

    # 2. Simulate Queue Telemetry
    print("Generating multi-lane checkout queue telemetry...")
    snapshot_intervals = []
    t = start_time
    while t <= now:
        snapshot_intervals.append(t)
        t += timedelta(minutes=15)
    for m in range(10, 0, -1):
        snapshot_intervals.append(now - timedelta(minutes=m))
    snapshot_intervals.append(now)

    for idx, snap_ts in enumerate(sorted(set(snapshot_intervals))):
        hr = snap_ts.hour
        is_peak = (11 <= hr < 14) or (17 <= hr < 21)

        # Counter 1 (Primary Lane)
        q1_len = rng.choices([3, 4, 5], weights=[0.4, 0.4, 0.2])[0] if is_peak else rng.randint(0, 2)
        q1_wait = float(q1_len * rng.uniform(28.0, 36.0))
        queue_rows.append((
            f"q_ev_c1_{idx}",
            "zone_queue_checkout_1",
            snap_ts.isoformat(),
            q1_len,
            round(q1_wait, 1),
            min(6, q1_len + rng.choice([0, 1])),
            round(q1_wait + 15.0, 1),
        ))

        # Counter 2 (Secondary Lane)
        q2_len = rng.randint(1, 3) if is_peak else rng.choice([0, 1])
        q2_wait = float(q2_len * rng.uniform(25.0, 32.0))
        queue_rows.append((
            f"q_ev_c2_{idx}",
            "zone_queue_checkout_2",
            snap_ts.isoformat(),
            q2_len,
            round(q2_wait, 1),
            q2_len,
            round(q2_wait + 5.0, 1),
        ))

    # 3. Simulate Shelf Stock Events
    print("Generating category shelf stock events...")
    stock_records = [
        (
            "zone_shelf_beverages",
            [
                (20, "ok", 0.96),
                (12, "low", 0.81),
                (5, "low", 0.76),
                (1, "ok", 0.95),  # restocked 1 hr ago
            ],
        ),
        (
            "zone_shelf_snacks",
            [
                (22, "ok", 0.94),
                (10, "ok", 0.89),
                (4, "low", 0.82),
                (0.2, "low", 0.79),  # currently LOW
            ],
        ),
        (
            "zone_shelf_electronics",
            [
                (24, "ok", 0.98),
                (12, "ok", 0.97),
                (0.1, "ok", 0.96),  # currently OK
            ],
        ),
        (
            "zone_shelf_bakery",
            [
                (18, "ok", 0.91),
                (8, "low", 0.83),
                (2, "empty", 0.93),
                (0.05, "empty", 0.94),  # currently EMPTY
            ],
        ),
    ]

    for s_idx, (shelf_id, timeline) in enumerate(stock_records):
        for t_idx, (hrs_ago, st, conf) in enumerate(timeline):
            ev_ts = now - timedelta(hours=hrs_ago)
            stock_rows.append((
                f"stk_{s_idx}_{t_idx}_{int(ev_ts.timestamp())}",
                shelf_id,
                ev_ts.isoformat(),
                st,
                conf,
            ))

    # 4. Simulate Operational Alerts
    print("Generating operational incident alerts...")
    alert_rows.extend([
        # Open alerts
        (
            "alert_bakery_empty",
            "low_stock",
            "critical",
            "zone_shelf_bakery",
            "Critical out-of-stock: Fresh Bakery Shelf depleted (0 units detected)",
            (now - timedelta(minutes=28)).isoformat(),
            None,
        ),
        (
            "alert_queue1_surge",
            "queue_congestion",
            "warning",
            "zone_queue_checkout_1",
            "Checkout Lane 1 congested: 4+ customers waiting (est. wait 140s)",
            (now - timedelta(minutes=14)).isoformat(),
            None,
        ),
        (
            "alert_snacks_low",
            "low_stock",
            "warning",
            "zone_shelf_snacks",
            "Low inventory alert: Snacks & Confectionery shelf below safety threshold",
            (now - timedelta(minutes=42)).isoformat(),
            None,
        ),
        # Resolved historical alerts
        (
            "alert_hist_beverages",
            "low_stock",
            "warning",
            "zone_shelf_beverages",
            "Cold Beverages shelf depleted during midday rush",
            (now - timedelta(hours=6)).isoformat(),
            (now - timedelta(hours=4, minutes=45)).isoformat(),
        ),
        (
            "alert_hist_queue2",
            "queue_congestion",
            "warning",
            "zone_queue_checkout_2",
            "Checkout Lane 2 congestion spike resolved by opening secondary register",
            (now - timedelta(hours=4, minutes=30)).isoformat(),
            (now - timedelta(hours=3, minutes=50)).isoformat(),
        ),
        (
            "alert_hist_promo",
            "custom",
            "info",
            "zone_display_promo",
            "Shopper dwell density surge detected at Promotional Island Display",
            (now - timedelta(hours=8)).isoformat(),
            (now - timedelta(hours=6, minutes=30)).isoformat(),
        ),
    ])

    # 5. Fast batch commit to SQLite
    print("Writing batch records to SQLite database...")
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executemany(
                """
                INSERT INTO detection_events (
                    event_id, track_id, timestamp,
                    bbox_x, bbox_y, bbox_w, bbox_h,
                    zone_id, event_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                detection_rows,
            )
            conn.executemany(
                """
                INSERT INTO dwell_events (
                    event_id, zone_id, track_id, start_ts, end_ts, duration_sec
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                dwell_rows,
            )
            conn.executemany(
                """
                INSERT INTO queue_events (
                    event_id, counter_id, timestamp, queue_length, avg_wait_est_sec,
                    predicted_queue_length, predicted_wait_sec
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                queue_rows,
            )
            conn.executemany(
                """
                INSERT INTO stock_events (
                    event_id, shelf_id, timestamp, status, confidence
                ) VALUES (?, ?, ?, ?, ?);
                """,
                stock_rows,
            )
            conn.executemany(
                """
                INSERT INTO alerts (
                    alert_id, alert_type, severity, zone_id, message, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                alert_rows,
            )
    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("[OK] Synthetic Retail Data Seeding Completed Successfully!")
    print("=" * 60)
    print(f"- Footfall: Enters={total_enters} | Exits={total_exits} | Net Occupancy={total_enters - total_exits}")
    print(f"- Detection events: {len(detection_rows)} coordinates for 2D dwell heatmap")
    print(f"- Dwell records: {len(dwell_rows)}")
    print(f"- Queue snapshots: {len(queue_rows)} across 2 checkout lanes")
    print(f"- Shelf stock evaluations: {len(stock_rows)} across 4 store categories")
    print(f"- Operational alerts: {len(alert_rows)} (3 Open / 3 Resolved)")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed artificial retail telemetry for EdgeRetail AI.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=BACKEND_DIR / "retail.db",
        help="Path to SQLite database file (default: backend/retail.db)",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=BACKEND_DIR / "config.yaml",
        help="Path to runtime configuration YAML (default: backend/config.yaml)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Number of hours of historical telemetry to generate (default: 24)",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not wipe existing events before seeding",
    )

    args = parser.parse_args()

    update_config_zones(args.config_path)
    if not args.keep_existing:
        clear_existing_data(args.db_path)
    seed_database(args.db_path, hours=args.hours)

    root_db = BACKEND_DIR.parent / "retail.db"
    if root_db.resolve() != args.db_path.resolve():
        import shutil
        shutil.copyfile(args.db_path, root_db)

    root_cfg = BACKEND_DIR.parent / "config.yaml"
    if root_cfg.resolve() != args.config_path.resolve():
        import shutil
        shutil.copyfile(args.config_path, root_cfg)


if __name__ == "__main__":
    main()
