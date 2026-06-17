from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import time
import json
import random
from rescueroute.config import CASE_LOG_PATH, SNAPSHOT_LOG_PATH, EXTERNAL_TRIGGER_PATH
from rescueroute.simulation import Simulation
from rescueroute.entities import Emergency
from rescueroute.config import EMERGENCY_TYPES

# Page config
st.set_page_config(
    page_title="RescueRoute AI | Smart Emergency Dispatch",
    layout="wide",
    page_icon="🚑",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main {
        background: linear-gradient(135deg, #f0f4f8 0%, #d9e2ec 100%);
    }
    
    .hero-section {
        background: linear-gradient(90deg, #1e3a8a 0%, #2563eb 100%);
        padding: 40px;
        border-radius: 20px;
        color: white;
        margin-bottom: 30px;
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
    }
    
    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.15);
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 15px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 12px;
        padding: 10px 20px;
        background: white;
        border: 1px solid #e2e8f0;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background: #2563eb !important;
        color: white !important;
        border: none !important;
    }
    
    .request-item {
        background: white;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .request-item:hover {
        border-color: #2563eb;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# Define paths
TRACKING_DATA_PATH = Path(__file__).parent / "data" / "tracking_requests.json"

# Helper functions to load/save tracking data
def load_tracking_data():
    if not TRACKING_DATA_PATH.exists():
        return {}
    try:
        with open(TRACKING_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_tracking_data(data):
    TRACKING_DATA_PATH.parent.mkdir(exist_ok=True)
    with open(TRACKING_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)

# Load tracking data initially
tracking_data = load_tracking_data()

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/ambulance.png", width=80)
    st.title("RescueRoute AI")
    st.markdown("---")
    
    user_mode = st.radio(
        "Select Mode",
        ["👤 Citizen", "📊 Admin Dashboard"],
        index=0
    )
    
    st.markdown("---")
    
    if st.button("🔄 Refresh", type="primary", width="stretch"):
        st.rerun()
    
    if user_mode == "📊 Admin Dashboard":
        if st.button("🗑️ Clear Logs", width="stretch"):
            if CASE_LOG_PATH.exists():
                CASE_LOG_PATH.unlink()
            if SNAPSHOT_LOG_PATH.exists():
                SNAPSHOT_LOG_PATH.unlink()
            if EXTERNAL_TRIGGER_PATH.exists():
                EXTERNAL_TRIGGER_PATH.unlink()
            st.success("Logs cleared!")
            st.rerun()


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


# --- CITIZEN MODE ---
if user_mode == "👤 Citizen":
    st.markdown("""
        <div class="hero-section">
            <h1 style="font-size: 3rem; font-weight: 800; margin: 0;">🚨 Emergency Help Center</h1>
            <p style="font-size: 1.25rem; opacity: 0.9; margin-top: 10px;">Get emergency assistance in seconds with AI-powered dispatch</p>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🚑 Send SOS", "🔍 Track My Request"])
    
    with tab1:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            with st.container(border=True):
                st.subheader("Emergency Details")
                emergency_type = st.selectbox(
                    "What's the emergency?",
                    list(EMERGENCY_TYPES.keys()),
                    index=0
                )
                
                severity = st.select_slider(
                    "How critical is it?",
                    options=["Low", "Medium", "High", "Critical"],
                    value="High"
                )
                
                st.divider()
                
                if st.button("🚨 SEND SOS NOW", type="primary", width="stretch"):
                    # Generate unique tracking ID
                    track_id = f"RR-{int(time.time())}-{random.randint(1000,9999)}"
                    
                    # Write to external trigger file (for simulation)
                    new_request = {
                        "id": track_id,
                        "type": emergency_type,
                        "time": time.time()
                    }
                    existing_requests = []
                    if EXTERNAL_TRIGGER_PATH.exists():
                        try:
                            with open(EXTERNAL_TRIGGER_PATH, "r") as f:
                                existing_requests = json.load(f)
                        except Exception:
                            pass
                    existing_requests.append(new_request)
                    with open(EXTERNAL_TRIGGER_PATH, "w") as f:
                        json.dump(existing_requests, f)
                    
                    # Save to persistent tracking data
                    tracking_data[track_id] = {
                        "type": emergency_type,
                        "time": time.time(),
                        "status": "Dispatched",
                        "severity": severity
                    }
                    save_tracking_data(tracking_data)
                    
                    st.success(f"SOS Sent! Your Tracking ID: **{track_id}**")
                    st.balloons()
                    
                    # Show confirmation card
                    st.markdown(f"""
                        <div style="background: #f0fdf4; padding: 24px; border-radius: 16px; border: 2px solid #10b981; margin-top: 20px;">
                            <h3 style="color: #166534; margin-bottom: 12px;">🚑 Ambulance On The Way!</h3>
                            <p style="font-size: 1.8rem; font-weight: 800; color: #166534; margin: 8px 0;">Estimated Arrival: ~{5 if severity == 'Critical' else 8} Minutes</p>
                            <p style="color: #166534;">Please save your tracking ID for updates</p>
                        </div>
                    """, unsafe_allow_html=True)
        
        with col2:
            with st.container(border=True):
                st.subheader("💡 What Happens Next?")
                st.markdown("""
                    1. Our AI system immediately analyzes live traffic and weather
                    2. The nearest available ambulance is dispatched automatically
                    3. The fastest route is calculated in real-time
                    4. The best hospital is selected based on specialty and bed availability
                    5. You can track your request with your unique ID
                """)
                st.image("https://img.icons8.com/fluency/200/map-marker.png", width=200)
    
    with tab2:
        # Refresh button at top
        if st.button("🔄 Refresh Tracking Data", type="primary"):
            st.rerun()
        
        # Always reload fresh data
        current_tracking = load_tracking_data()
        
        with st.container(border=True):
            st.subheader("Track Your Request")
            
            # Show active requests as dropdown
            if current_tracking:
                # Create options for dropdown
                options = list(current_tracking.keys())
                option_labels = [f"{req_id} - {current_tracking[req_id]['type']}" for req_id in options]
                
                selected_index = st.selectbox(
                    "Select Active Request:",
                    range(len(options)),
                    format_func=lambda i: option_labels[i]
                )
                dropdown_selected_id = options[selected_index]
            else:
                st.info("No active requests yet. Send an SOS first!")
                dropdown_selected_id = ""
            
            st.divider()
            
            # Search or select an ID
            selected_id = st.text_input(
                "Enter your Tracking ID (e.g., RR-123456-7890)",
                placeholder="RR-XXXXXX-XXXX",
                value=dropdown_selected_id if dropdown_selected_id else ""
            )
            
            if selected_id:
                if selected_id in current_tracking:
                    req = current_tracking[selected_id]
                    time_passed = int(time.time() - req["time"])
                    eta_min = 5 if req.get('severity') == 'Critical' else 8
                    
                    # Severity color
                    severity_colors = {
                        "Low": "#06b6d4",
                        "Medium": "#f59e0b",
                        "High": "#ef4444",
                        "Critical": "#dc2626"
                    }
                    severity_color = severity_colors.get(req.get('severity', 'Medium'), '#f59e0b')
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.subheader(f"Request Status: {selected_id}")
                        with col2:
                            st.markdown(f"""
                                <span style="background-color: {severity_color}; color: white; padding: 8px 20px; border-radius: 20px; font-weight: 700;">{req.get('severity', 'Medium')}</span>
                            """, unsafe_allow_html=True)
                        
                        st.divider()
                        
                        # Info cards
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("Emergency Type", req['type'])
                        with c2:
                            st.metric("Time Since Request", f"{time_passed} seconds")
                        with c3:
                            st.metric("Estimated Arrival", f"~{eta_min} minutes")
                        
                        st.divider()
                        
                        st.subheader("Status Timeline")
                        st.markdown("✅ **Request Received** - Just now")
                        st.markdown(f"✅ **AI Dispatcher Assigned Ambulance** - {time_passed}s ago")
                        st.markdown(f"🚑 **Ambulance En Route** - ETA: ~{eta_min} mins")
                elif selected_id:
                    st.error("Tracking ID not found. Please check and try again!")
                    st.write("Debug - Available IDs:", list(current_tracking.keys()))
            else:
                st.warning("Please select a request from the dropdown or enter an ID!")


# --- ADMIN DASHBOARD MODE ---
else:
    st.markdown("""
        <div class="hero-section">
            <h1 style="font-size: 3rem; font-weight: 800; margin: 0;">📊 Control Center</h1>
            <p style="font-size: 1.25rem; opacity: 0.9; margin-top: 10px;">Real-time emergency management and AI dispatch monitoring</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Load data
    snapshots = load_csv(SNAPSHOT_LOG_PATH)
    cases = load_csv(CASE_LOG_PATH)
    
    if snapshots.empty:
        st.info("No dashboard data yet. Run `python app.py` to start the live simulation, then refresh this page!")
    else:
        latest = snapshots.iloc[-1]
        
        # Metrics
        c1, c2, c3, c4, c5 = st.columns(5)
        metrics = [
            ("Saved Cases", int(latest.get("saved_cases", 0)), "#10b981"),
            ("Delayed Cases", int(latest.get("delayed_cases", 0)), "#ef4444"),
            ("Active Emergencies", int(latest.get("active_emergencies", 0)), "#f59e0b"),
            ("Avg Response", f"{float(latest.get('avg_response_min', 0)):.1f} min", "#3b82f6"),
            ("Open Beds", int(latest.get("open_hospital_beds", 0)), "#06b6d4"),
        ]
        
        for col, (label, value, color) in zip([c1, c2, c3, c4, c5], metrics):
            col.markdown(f"""
                <div class="metric-card">
                    <div style="color: #64748b; font-size: 0.875rem; font-weight: 700; text-transform: uppercase;">{label}</div>
                    <div style="color: {color}; font-size: 2.5rem; font-weight: 800; margin-top: 8px;">{value}</div>
                </div>
            """, unsafe_allow_html=True)
        
        # Tabs
        tab1, tab2, tab3 = st.tabs(["📈 Trends", "⚡ Route Comparison", "📋 Case Logs"])
        
        with tab1:
            st.subheader("Simulation Trends")
            trend_cols = [
                "saved_cases",
                "delayed_cases",
                "active_emergencies",
                "available_ambulances",
                "open_hospital_beds",
            ]
            trend_data = snapshots[[col for col in trend_cols if col in snapshots.columns]].copy()
            
            fig = px.line(
                trend_data,
                title="System Metrics Over Time",
                template="plotly_white",
                color_discrete_sequence=["#10b981", "#ef4444", "#f59e0b", "#3b82f6", "#06b6d4"]
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.subheader("AI Optimized Route vs Normal Route")
            route_cols = ["last_optimized_route_min", "last_normal_route_min"]
            route_data = snapshots[[col for col in route_cols if col in snapshots.columns]].copy()
            route_data.columns = ["AI Optimized (min)", "Normal Route (min)"]
            
            fig = px.line(
                route_data,
                title="Route Time Comparison",
                template="plotly_white",
                color_discrete_sequence=["#3b82f6", "#64748b"]
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            st.subheader("Completed Case Log")
            if cases.empty:
                st.write("No completed cases yet.")
            else:
                st.dataframe(
                    cases.sort_values('sim_time_seconds', ascending=False),
                    width="stretch",
                    hide_index=True
                )
                
                outcome_counts = cases["outcome"].value_counts().rename_axis("outcome").reset_index(name="cases")
                st.subheader("Outcome Counts")
                fig = px.bar(
                    outcome_counts,
                    x="outcome",
                    y="cases",
                    color="outcome",
                    color_discrete_map={"Saved": "#10b981", "Delayed": "#ef4444"},
                    template="plotly_white"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)


with st.expander("📖 How to Use This System"):
    st.markdown("""
        ### For Citizens:
        1. Go to **👤 Citizen** mode
        2. Fill in emergency details and click *SEND SOS NOW*
        3. Save your tracking ID
        4. Use the *Track My Request* tab to see updates
        
        ### For Admins:
        1. Go to **📊 Admin Dashboard** mode
        2. First, start the live simulation: Run `python app.py` in your terminal
        3. Press `SPACE` in the simulation window to create emergencies
        4. Refresh the dashboard to see live metrics
        5. Use the sidebar to refresh data or clear logs
        
        ### Simulation Controls (in Pygame window):
        - `SPACE`: Create a new emergency immediately
        - `T`: Randomize traffic conditions
        - `B`: Block/unblock a random road
        - `C`: Clear all roads to low traffic
        - `ESC`: Quit the simulation
    """)
