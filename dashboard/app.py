import sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import get_session
from src.database.models import VehiclePositionRaw, HeadwayObservation, BunchingEvent
from src.analytics.historical import HistoricalAnalytics
from src.models.predict import BunchingPredictor

st.set_page_config(
    page_title="DBBP - Delhi Bus Bunching Predictor",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("DBBP — Delhi Bus Bunching Prediction & Early Warning System")

# Initialize database session
session = get_session()
analytics = HistoricalAnalytics(session)

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["1. Overview", "2. Live Map", "3. Route Intelligence", "4. Hotspots", "5. Model Explainability"],
)

# -------------------------------------------------------------
# PAGE 1: OVERVIEW
# -------------------------------------------------------------
if page == "1. Overview":
    st.header("Fleet & System Overview")

    total_buses = session.query(VehiclePositionRaw.vehicle_id).distinct().count()
    total_routes = session.query(VehiclePositionRaw.route_id).distinct().count()
    active_bunching = session.query(BunchingEvent).filter(BunchingEvent.severity.in_(["SEVERE", "HIGH"])).count()
    total_headways = session.query(HeadwayObservation).count()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Buses", f"{total_buses:,}")
    col2.metric("Routes Monitored", f"{total_routes:,}")
    col3.metric("Critical Bunching Alerts", f"{active_bunching:,}")
    col4.metric("Headways Logged", f"{total_headways:,}")

    st.subheader("Active Early Warning Alerts (P(Bunching) > 0.80)")
    recent_events = (
        session.query(BunchingEvent)
        .order_by(BunchingEvent.start_time.desc())
        .limit(10)
        .all()
    )

    if recent_events:
        alert_data = []
        for e in recent_events:
            alert_data.append({
                "Event ID": e.event_id,
                "Route": e.route_id,
                "Leading Bus": e.leading_vehicle_id,
                "Trailing Bus": e.trailing_vehicle_id,
                "Observed Gap (min)": round(e.observed_headway / 60.0, 1),
                "Following Gap (min)": round((e.following_gap or 0.0) / 60.0, 1),
                "Severity": e.severity,
                "Timestamp": e.start_time.strftime("%H:%M:%S") if e.start_time else "N/A",
            })
        st.dataframe(pd.DataFrame(alert_data), use_container_width=True)
    else:
        st.info("No critical bunching events detected in recent telemetry.")

# -------------------------------------------------------------
# PAGE 2: LIVE MAP
# -------------------------------------------------------------
elif page == "2. Live Map":
    st.header("Real-Time Vehicle Position & Network Density Map")

    vehicles = (
        session.query(VehiclePositionRaw)
        .order_by(VehiclePositionRaw.timestamp.desc())
        .limit(1000)
        .all()
    )

    if vehicles:
        df_map = pd.DataFrame([{
            "vehicle_id": v.vehicle_id,
            "route_id": v.route_id,
            "latitude": v.latitude,
            "longitude": v.longitude,
            "speed": v.speed or 15.0,
        } for v in vehicles])

        if hasattr(px, "scatter_map"):
            fig = px.scatter_map(
                df_map,
                lat="latitude",
                lon="longitude",
                hover_name="vehicle_id",
                hover_data=["route_id", "speed"],
                color_discrete_sequence=["#2563eb"],
                zoom=10,
                center={"lat": 28.6139, "lon": 77.2090},
                height=650,
            )
            fig.update_layout(map_style="open-street-map")
            st.plotly_chart(fig, use_container_width=True)
        elif hasattr(px, "scatter_mapbox"):
            fig = px.scatter_mapbox(
                df_map,
                lat="latitude",
                lon="longitude",
                hover_name="vehicle_id",
                hover_data=["route_id", "speed"],
                color_discrete_sequence=["#2563eb"],
                zoom=10,
                center={"lat": 28.6139, "lon": 77.2090},
                height=650,
            )
            fig.update_layout(mapbox_style="carto-positron")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.map(df_map.rename(columns={"latitude": "lat", "longitude": "lon"}))
    else:
        st.warning("No vehicle positions currently available in the database. Run the collector first.")

# -------------------------------------------------------------
# PAGE 3: ROUTE INTELLIGENCE
# -------------------------------------------------------------
elif page == "3. Route Intelligence":
    st.header("Route-Level Bunching & Headway Intelligence")

    routes = [r[0] for r in session.query(VehiclePositionRaw.route_id).distinct().limit(100).all() if r[0]]
    selected_route = st.selectbox("Select Route Identifier:", routes if routes else ["534"])

    route_buses = (
        session.query(VehiclePositionRaw)
        .filter(VehiclePositionRaw.route_id == str(selected_route))
        .all()
    )

    headways = (
        session.query(HeadwayObservation)
        .filter(HeadwayObservation.route_id == str(selected_route))
        .order_by(HeadwayObservation.timestamp.desc())
        .limit(30)
        .all()
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Active Buses on Route", len(route_buses))
    med_hw = round(pd.Series([h.headway_seconds / 60.0 for h in headways]).median(), 1) if headways else 10.0
    c2.metric("Observed Median Headway", f"{med_hw} min")
    c3.metric("Expected Headway", "10.0 min")

    if headways:
        st.subheader("Recent Headway Deviation Pattern")
        hw_df = pd.DataFrame([{
            "Vehicle": h.vehicle_id,
            "Headway (min)": round(h.headway_seconds / 60.0, 1),
            "Expected (min)": round(h.expected_headway_seconds / 60.0, 1),
        } for h in headways])

        fig = px.bar(
            hw_df,
            x="Vehicle",
            y="Headway (min)",
            title=f"Headway Spacing Between Buses on Route {selected_route}",
            color="Headway (min)",
            color_continuous_scale=["#dc2626", "#f59e0b", "#16a34a"],
        )
        fig.add_hline(y=10.0, line_dash="dash", line_color="black", annotation_text="Scheduled (10m)")
        st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------
# PAGE 4: HOTSPOTS
# -------------------------------------------------------------
elif page == "4. Hotspots":
    st.header("Recurrent Bunching Hotspots in Delhi")

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Top High-Risk Routes")
        route_ranks = analytics.get_route_bunching_rankings(limit=10)
        if route_ranks:
            df_rr = pd.DataFrame(route_ranks)
            fig_r = px.bar(
                df_rr,
                x="route_id",
                y="total_events",
                color="severe_events",
                title="Routes with Highest Bunching Incidents",
                labels={"route_id": "Route", "total_events": "Total Incidents"},
            )
            st.plotly_chart(fig_r, use_container_width=True)
        else:
            st.info("No route bunching events logged yet.")

    with col_r:
        st.subheader("Top Recurrent Hotspot Stops")
        stop_ranks = analytics.get_stop_hotspots(limit=10)
        if stop_ranks:
            df_sr = pd.DataFrame(stop_ranks)
            fig_s = px.bar(
                df_sr,
                x="stop_id",
                y="incident_count",
                title="Stops with Frequent Clustering",
                labels={"stop_id": "Stop", "incident_count": "Incidents"},
            )
            st.plotly_chart(fig_s, use_container_width=True)
        else:
            st.info("No stop hotspot records logged yet.")

# -------------------------------------------------------------
# PAGE 5: MODEL EXPLAINABILITY
# -------------------------------------------------------------
elif page == "5. Model Explainability":
    st.header("Explainable AI: Bunching Risk Predictor")

    predictor = BunchingPredictor()

    st.markdown("""
    Select observation parameters to test the trained model and view the mathematical feature contributions
    explaining **why** the system predicts a specific probability of bus bunching.
    """)

    c_a, c_b = st.columns(2)
    with c_a:
        test_hw = st.slider("Current Headway (seconds)", min_value=30, max_value=1200, value=120, step=30)
        test_gap_m = st.slider("Space Gap to Leading Bus (meters)", min_value=50, max_value=5000, value=250, step=50)
    with c_b:
        test_speed = st.slider("Current Bus Speed (km/h)", min_value=5, max_value=60, value=12, step=1)
        test_seq = st.slider("Stop Sequence Difference", min_value=0, max_value=5, value=1, step=1)

    obs = {
        "route_id": "534",
        "headway_seconds": float(test_hw),
        "expected_headway_seconds": 600.0,
        "space_gap_meters": float(test_gap_m),
        "speed": float(test_speed),
        "sequence_diff": float(test_seq),
        "route_progress": 0.5,
        "current_stop_sequence": 12,
    }

    pred = predictor.predict_observation(obs)

    m1, m2, m3 = st.columns(3)
    m1.metric("Predicted Bunching Probability", pred["bunching_percentage"])
    m2.metric("Assigned Risk Level", pred["risk_level"])
    m3.metric("Prediction Horizon", f"{pred['prediction_horizon_minutes']} min")

    st.subheader("Feature Attributions (Contributing Factors)")
    pos_factors = pred["top_contributing_factors"]
    if pos_factors:
        df_expl = pd.DataFrame(pos_factors)
        fig_expl = px.bar(
            df_expl,
            x="contribution",
            y="feature",
            orientation="h",
            title="Model Factors Driving Bunching Risk Up",
            color="contribution",
            color_continuous_scale="Reds",
        )
        st.plotly_chart(fig_expl, use_container_width=True)

    st.caption(f"Note: {pred['disclaimer']}")

session.close()
