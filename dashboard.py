from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from rescueroute.config import CASE_LOG_PATH, SNAPSHOT_LOG_PATH

st.set_page_config(page_title="RescueRoute AI Dashboard", layout="wide")
st.title("🚑 RescueRoute AI Dashboard")
st.caption("Live metrics are written by the Pygame simulation to CSV files in the data folder.")


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


snapshots = load_csv(SNAPSHOT_LOG_PATH)
cases = load_csv(CASE_LOG_PATH)

if snapshots.empty:
    st.info("No dashboard data yet. Run `python app.py`, let a few emergencies complete, then refresh this page.")
else:
    latest = snapshots.iloc[-1]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Saved cases", int(latest.get("saved_cases", 0)))
    c2.metric("Delayed cases", int(latest.get("delayed_cases", 0)))
    c3.metric("Active emergencies", int(latest.get("active_emergencies", 0)))
    c4.metric("Avg response", f"{float(latest.get('avg_response_min', 0)):.1f} min")
    c5.metric("Open beds", int(latest.get("open_hospital_beds", 0)))

    st.subheader("Simulation Trends")
    trend_cols = [
        "saved_cases",
        "delayed_cases",
        "active_emergencies",
        "available_ambulances",
        "open_hospital_beds",
        "avg_response_min",
    ]
    trend_data = snapshots[[col for col in trend_cols if col in snapshots.columns]].copy()
    st.line_chart(trend_data)

    st.subheader("Best Route vs Normal Route")
    route_cols = ["last_optimized_route_min", "last_normal_route_min"]
    route_data = snapshots[[col for col in route_cols if col in snapshots.columns]].copy()
    st.line_chart(route_data)

st.subheader("Completed Case Log")
if cases.empty:
    st.write("No completed cases yet.")
else:
    st.dataframe(cases.tail(30), use_container_width=True)

    outcome_counts = cases["outcome"].value_counts().rename_axis("outcome").reset_index(name="cases")
    st.subheader("Outcome Counts")
    st.bar_chart(outcome_counts.set_index("outcome"))

with st.expander("How to use this dashboard"):
    st.markdown(
        """
        1. Start the live simulation with `python app.py`.
        2. Press `SPACE` in the simulation to create emergencies faster.
        3. Run this dashboard in another terminal with `streamlit run dashboard.py`.
        4. Refresh the dashboard to see new CSV data.
        """
    )
