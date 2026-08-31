from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Intelligent Retail Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🛒 Intelligent Retail Analytics Dashboard")
st.caption("Edge-AI Shopper Analytics, Inventory Monitoring & Queue Intelligence (SIH26179)")

# Sidebar Settings
st.sidebar.header("⚙️ Configuration")
api_base_url = st.sidebar.text_input("API Base URL", value="http://localhost:8000")

time_filter = st.sidebar.selectbox(
    "Time Range",
    options=["All Time", "Last 1 Hour", "Last 6 Hours", "Last 24 Hours"],
    index=0,
)
zone_filter = st.sidebar.text_input("Zone ID Filter (optional)", value="")
group_by = st.sidebar.selectbox("Footfall Grouping", options=["none", "hour", "day"], index=1)

since_iso: str | None = None
if time_filter == "Last 1 Hour":
    since_iso = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
elif time_filter == "Last 6 Hours":
    since_iso = (datetime.now(UTC) - timedelta(hours=6)).isoformat()
elif time_filter == "Last 24 Hours":
    since_iso = (datetime.now(UTC) - timedelta(hours=24)).isoformat()

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()


def fetch_api(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    """Helper to fetch JSON data from backend API with error handling."""
    url = f"{api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API Error ({url}): {e}")
        return None


# Fetch data
footfall_params: dict[str, Any] = {"group_by": group_by}
if zone_filter:
    footfall_params["zone_id"] = zone_filter
if since_iso:
    footfall_params["since"] = since_iso

footfall_data = fetch_api("kpi/footfall", footfall_params)
queue_data = fetch_api("kpi/queue")
stock_data = fetch_api("kpi/stock")
alerts_data = fetch_api("alerts", {"status": "all"})
heatmap_params: dict[str, Any] = {"cell_size": 20}
if zone_filter:
    heatmap_params["zone_id"] = zone_filter
if since_iso:
    heatmap_params["since"] = since_iso
heatmap_data = fetch_api("heatmap", heatmap_params)

# ============================================================================
# KPI Overview Metrics
# ============================================================================
st.subheader("📊 Key Performance Indicators")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    enters = footfall_data.get("total_enters", 0) if footfall_data else 0
    st.metric(label="Total Visitors (In)", value=enters)

with col2:
    exits = footfall_data.get("total_exits", 0) if footfall_data else 0
    st.metric(label="Total Exited (Out)", value=exits)

with col3:
    occupancy = footfall_data.get("net_occupancy", 0) if footfall_data else 0
    st.metric(label="Current Occupancy", value=occupancy)

with col4:
    active_queues = len(queue_data) if queue_data else 0
    max_queue = max([q["queue_length"] for q in queue_data], default=0) if queue_data else 0
    st.metric(
        label="Max Queue Length",
        value=f"{max_queue} persons",
        delta=f"{active_queues} active",
    )

with col5:
    low_stock_count = (
        sum(1 for s in stock_data if s.get("status") in ("empty", "low")) if stock_data else 0
    )
    total_shelves = len(stock_data) if stock_data else 0
    st.metric(
        label="Shelf Alerts",
        value=f"{low_stock_count} low/empty",
        delta=f"{total_shelves} monitored",
        delta_color="inverse" if low_stock_count > 0 else "normal",
    )

st.divider()

# ============================================================================
# Alerts Section
# ============================================================================
st.subheader("🚨 Real-Time Alerts")
alert_status_filter = st.radio(
    "Alert Status Filter",
    options=["Open Only", "Resolved Only", "All Alerts"],
    horizontal=True,
)

if alerts_data is not None:
    filtered_alerts = alerts_data
    if alert_status_filter == "Open Only":
        filtered_alerts = [a for a in alerts_data if a.get("resolved_at") is None]
    elif alert_status_filter == "Resolved Only":
        filtered_alerts = [a for a in alerts_data if a.get("resolved_at") is not None]

    if not filtered_alerts:
        st.info("No alerts matching the selected filter.")
    else:
        for alert in filtered_alerts:
            severity = alert.get("severity", "info")
            is_resolved = alert.get("resolved_at") is not None
            icon = "🔴" if severity == "critical" else ("🟡" if severity == "warning" else "ℹ️")
            status_badge = "✅ Resolved" if is_resolved else "⚠️ Open"

            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 4, 2])
                with c1:
                    st.markdown(f"**{icon} {severity.upper()}**")
                    st.caption(status_badge)
                with c2:
                    st.markdown(f"**{alert.get('message')}**")
                    type_str = alert.get("alert_type")
                    zone_str = alert.get("zone_id") or "N/A"
                    st.caption(f"Type: `{type_str}` | Zone: `{zone_str}`")
                with c3:
                    st.caption(f"Created: {alert.get('created_at')}")
                    if is_resolved:
                        st.caption(f"Resolved: {alert.get('resolved_at')}")
else:
    st.warning("Could not load alerts from API.")

st.divider()

# ============================================================================
# Heatmap & Footfall Trends
# ============================================================================
tab1, tab2, tab3, tab4 = st.tabs(
    ["🔥 Zone Heatmap", "📈 Footfall Trends", "👥 Queue Monitoring", "📦 Shelf Inventory"]
)

with tab1:
    st.write("### Traffic & Dwell Heatmap")
    if heatmap_data and "grid" in heatmap_data:
        rows = heatmap_data.get("rows", 0)
        cols = heatmap_data.get("cols", 0)
        total_pts = heatmap_data.get("total_points", 0)
        c_sz = heatmap_data.get("cell_size")
        st.caption(
            f"Grid Size: {rows}x{cols} (cell: {c_sz}px) | Accumulated detections: {total_pts}"
        )

        grid_df = pd.DataFrame(heatmap_data["grid"])
        st.dataframe(
            grid_df.style.background_gradient(cmap="YlOrRd", axis=None),
            use_container_width=True,
        )
    else:
        st.info("No heatmap data available.")

with tab2:
    st.write("### Footfall Aggregations")
    if footfall_data and footfall_data.get("buckets"):
        buckets = footfall_data["buckets"]
        df_buckets = pd.DataFrame(buckets)
        df_buckets["bucket_start"] = pd.to_datetime(df_buckets["bucket_start"])
        st.line_chart(df_buckets.set_index("bucket_start")[["enters", "exits", "net"]])
        st.dataframe(df_buckets, use_container_width=True)
    else:
        st.info("No bucketed trend data available for current settings.")

with tab3:
    st.write("### Checkout Queue Status")
    if queue_data:
        df_queue = pd.DataFrame(queue_data)
        st.dataframe(df_queue, use_container_width=True)
    else:
        st.info("No checkout queue events recorded.")

with tab4:
    st.write("### Shelf Stock Levels")
    if stock_data:
        df_stock = pd.DataFrame(stock_data)
        st.dataframe(df_stock, use_container_width=True)
    else:
        st.info("No shelf stock events recorded.")
