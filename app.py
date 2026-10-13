from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from streamlit_geolocation import streamlit_geolocation
from streamlit_autorefresh import st_autorefresh
import os
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from src.database import init_db, create_sos, list_sos, update_status, get_stats, export_sos_csv
from src.mesh import simulate_relay, priority_score
from src.ai_service import generate_triage_brief, groq_is_configured

load_dotenv()
st.set_page_config(page_title="Crisis ResQ | Command Center", page_icon="🛟", layout="wide", initial_sidebar_state="expanded")
init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
html, body, [class*="css"] {font-family:'DM Sans',sans-serif;}
.block-container {padding-top:1.5rem; padding-bottom:2rem; max-width:1500px;}
.hero {padding:1.5rem 1.7rem; border-radius:18px; background:linear-gradient(120deg,#10253f,#174c62); color:#fff; margin-bottom:1.2rem; border:1px solid #28556a;}
.hero h1 {font-family:'Space Grotesk',sans-serif; font-size:2.25rem; margin:0; color:#fff;}
.hero p {color:#d2e6ed; margin:.4rem 0 0 0; font-size:1rem;}
.kicker {font-size:.72rem; letter-spacing:.16em; font-weight:700; color:#73d5c4; text-transform:uppercase;}
.section-title {font-family:'Space Grotesk',sans-serif; font-size:1.25rem; font-weight:700; margin:.25rem 0 .8rem 0;}
div[data-testid="stMetric"] {background:#f5f8fb; border:1px solid #e3eaf0; padding:14px 16px; border-radius:14px;}
[data-testid="stSidebar"] {border-right:1px solid #e5ebf0;}
.stButton>button[kind="primary"] {background:#dc4b43; border:0; font-weight:700;}
.small-note {font-size:.82rem;color:#64748b;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🛟 Crisis ResQ")
    st.caption("Disaster-resilient communication prototype")
    page = st.radio("COMMAND MENU", ["Overview", "Submit SOS","Live Location", "Mesh Simulator", "AI Triage", "Message Log", "Project Notes"], label_visibility="visible")
    st.divider()
    st.markdown("**System status**")
    st.success("Local database ready")
    st.info("Groq AI: Connected" if groq_is_configured() else "Groq AI: Demo mode (add API key in .env)")
    st.caption("Prototype only · Not an official emergency service")
    


def header(title: str, subtitle: str):
    st.markdown(f'<div class="hero"><div class="kicker">CACHE CUBE · HACK-X</div><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def badge_priority(value: str) -> str:
    return {"CRITICAL":"🔴 CRITICAL", "HIGH":"🟠 HIGH", "MEDIUM":"🟡 MEDIUM", "LOW":"🟢 LOW"}.get(value, value)

DB_PATH = Path("data/crisis_resq.db")


def init_location_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS location_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                accuracy_m REAL,
                recorded_at TEXT NOT NULL
            )
        """)


def save_location(message_id, latitude, longitude, accuracy):
    recorded_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO location_updates
            (message_id, latitude, longitude, accuracy_m, recorded_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            message_id,
            float(latitude),
            float(longitude),
            float(accuracy) if accuracy is not None else None,
            recorded_at,
        ))


def get_latest_locations():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT lu.*
            FROM location_updates lu
            JOIN (
                SELECT message_id, MAX(id) AS latest_id
                FROM location_updates
                GROUP BY message_id
            ) latest ON lu.id = latest.latest_id
            ORDER BY lu.id DESC
        """).fetchall()

    return [dict(row) for row in rows]


init_location_db()
if page == "Overview":
    header("Rescue Command Center", "A Python prototype for SOS intake, store-and-forward mesh simulation, and AI-assisted triage.")
    stats = get_stats()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total SOS alerts", stats["total"])
    c2.metric("Needs attention", stats["active"])
    c3.metric("Critical / high", stats["urgent"])
    c4.metric("Delivered", stats["delivered"])
    st.markdown("<div class='section-title'>Latest SOS alerts</div>", unsafe_allow_html=True)
    records = list_sos(limit=8)
    if records:
        df = pd.DataFrame(records)
        display_cols = [c for c in ["message_id","created_at","victim_name","emergency_type","people_count","priority","status","location_text"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No SOS alerts yet. Open **Submit SOS** to create a sample alert.")
    st.markdown("<div class='section-title'>How this prototype works</div>", unsafe_allow_html=True)
    a,b,c = st.columns(3)
    with a:
        st.markdown("### 01 · Capture")
        st.write("Collect a short SOS, location, emergency category, number of people and battery level.")
    with b:
        st.markdown("### 02 · Relay")
        st.write("Simulate nearby relay nodes, message IDs, hop count and store-and-forward delivery.")
    with c:
        st.markdown("### 03 · Triage")
        st.write("Prioritize alerts using transparent rules and optionally ask a small Groq-hosted LLM for a concise responder brief.")

elif page == "Submit SOS":

    header(
        "Submit an SOS",
        "Create a structured emergency packet. Entries are saved locally in SQLite."
    )

    # Capture GPS outside the form.
    gps = streamlit_geolocation()

    st.write("GPS debug output:", gps)

    if gps and gps.get("latitude") is not None :
        st.success("Latitude received!")
    else:
        st.warning("Waiting for browser location...")

    lat = None
    lon = None

    if (
        gps
        and gps.get("latitude") is not None
        and gps.get("longitude") is not None
    ):
        lat = float(gps["latitude"])
        lon = float(gps["longitude"])

        st.success("GPS location detected.")
        st.caption(f"Coordinates: {lat:.6f}, {lon:.6f}")
    else:
        st.warning(
            "GPS unavailable. Allow location permission in your browser. "
            "You can still submit an SOS without coordinates."
        )

    with st.form("sos_form", clear_on_submit=True):
        left, right = st.columns(2)

        with left:
            victim = st.text_input(
                "Name or alias",
                placeholder="e.g., Victim A"
            )

            emergency = st.selectbox(
                "Emergency type",
                [
                    "Trapped / building collapse",
                    "Medical emergency",
                    "Injury",
                    "Fire",
                    "Flooding",
                    "Missing person",
                    "Food / water needed",
                    "Other",
                ],
            )

            people = st.number_input(
                "People needing help",
                min_value=1,
                max_value=500,
                value=1,
            )

            battery = st.slider(
                "Phone battery (%)",
                0,
                100,
                60,
            )

        with right:
            location_text = st.text_input(
                "Location description",
                placeholder="Landmark, street, floor, nearby building…",
            )

            message = st.text_area(
                "Short SOS message",
                placeholder="Describe immediate danger, injuries, access constraints…",
                max_chars=500,
                height=120,
            )

        submitted = st.form_submit_button(
            "🚨 Save SOS alert",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not message.strip() and not location_text.strip():
            st.error(
                "Please enter at least a short message or a location description."
            )
        else:
            priority = priority_score(
                emergency,
                int(people),
                message,
                int(battery),
            )

            row = create_sos(
                victim_name=victim.strip() or "Anonymous",
                emergency_type=emergency,
                people_count=int(people),
                battery=int(battery),
                latitude=lat,
                longitude=lon,
                location_text=location_text.strip(),
                message=message.strip(),
                priority=priority,
            )

            st.success(
                f"SOS saved. Message ID: {row['message_id']} · "
                f"Priority: {priority}"
            )

            if lat is not None and lon is not None:
                st.map(
                    pd.DataFrame([{
                        "latitude": lat,
                        "longitude": lon,
                    }])
                )

            st.caption(
                "This saves the SOS locally. It does not contact emergency "
                "services or transmit over physical radios."
            )

elif page == "Live Location":
    header(
        "Live Location Tracking",
        "View the latest GPS position associated with an SOS alert."
    )

    rows = list_sos(limit=500)

    if not rows:
        st.warning("Create an SOS alert first using Submit SOS.")
    else:
        options = {
            f"{r['message_id']} · {r['emergency_type']} · {r['priority']}":
                r
            for r in rows
        }

        selected = st.selectbox(
            "Select the SOS to track",
            list(options.keys())
        )
        packet = options[selected]
        message_id = packet["message_id"]

        st.info(
            "Keep this page open. Allow browser location access when "
            "prompted. Location updates require connectivity to reach "
            "this Streamlit session."
        )

        refresh_count = st_autorefresh(
            interval=10000,
            key="crisis_resq_location_refresh"
        )

        # Change the component key to request a fresh browser reading
        # after each automatic page refresh.
        location = streamlit_geolocation()

        if (
            location
            and location.get("latitude") is not None
            and location.get("longitude") is not None
        ):
            latitude = float(location["latitude"])
            longitude = float(location["longitude"])
            accuracy = location.get("accuracy")

            # Basic coordinate validation
            if (
                -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                save_location(
                    message_id,
                    latitude,
                    longitude,
                    accuracy
                )

                st.success("GPS position received and saved.")

                c1, c2, c3 = st.columns(3)
                c1.metric("Latitude", f"{latitude:.6f}")
                c2.metric("Longitude", f"{longitude:.6f}")
                c3.metric(
                    "GPS accuracy",
                    f"{float(accuracy):.1f} m"
                    if accuracy is not None else "Unknown"
                )

                st.map(pd.DataFrame([{
                    "latitude": latitude,
                    "longitude": longitude,
                }]))

                st.link_button(
                    "Open position in Google Maps",
                    f"https://www.google.com/maps?q={latitude},{longitude}"
                )
            else:
                st.error("The browser returned invalid coordinates.")
        else:
            st.warning(
                "Waiting for GPS coordinates. Check browser permission "
                "and location services, then wait for the next refresh."
            )

        # Show the latest saved location for the selected SOS,
        # including when a fresh GPS reading is unavailable.
        saved = [
            r for r in get_latest_locations()
            if r["message_id"] == message_id
        ]

        if saved:
            latest = saved[0]
            st.markdown("### Last saved location")

            st.write(
                f"Recorded at: {latest['recorded_at']}"
            )

            st.map(pd.DataFrame([{
                "latitude": latest["latitude"],
                "longitude": latest["longitude"],
            }]))

            st.caption(
                "A saved coordinate is not necessarily the current "
                "position. Check its timestamp before relying on it."
            )

        st.caption(
            "Prototype limitation: browser polling is best-effort and "
            "may not produce a new GPS fix every 10 seconds. This does "
            "not implement offline mesh delivery."
        )
elif page == "Mesh Simulator":
    header("Mesh Relay Simulator", "Demonstrate multi-hop, store-and-forward behavior when a direct route is unavailable.")
    rows = list_sos(limit=100)
    if not rows:
        st.warning("Create an SOS first, or use the sample packet below.")
    options = {f"{r['message_id']} · {r['emergency_type']} · {r['priority']}": r for r in rows}
    selected = st.selectbox("SOS packet", list(options.keys()) if options else ["DEMO-SOS-001 · Trapped · CRITICAL"])
    l,r = st.columns(2)
    with l:
        nodes = st.text_input("Available relay nodes (comma-separated)", "Victim-Phone, Volunteer-01, Shelter-Gateway, Rescue-Server")
        network = st.selectbox("Connectivity condition", ["Intermittent — eventually connected", "Connected route available", "Network partition — no gateway reachable"])
    with r:
        ttl = st.slider("Maximum hop count (TTL)", 1, 12, 6)
        duplicate = st.checkbox("Simulate duplicate packet reception", value=True)
    if st.button("▶ Simulate message relay", type="primary"):
        packet = options[selected] if options else {"message_id":"DEMO-SOS-001","priority":"CRITICAL","message":"Person trapped after building collapse","location_text":"Demo coordinates"}
        result = simulate_relay(packet, [x.strip() for x in nodes.split(",") if x.strip()], network, ttl, duplicate)
        st.markdown("### Relay trace")
        for i, event in enumerate(result["events"], 1):
            st.markdown(f"**{i}. {event['node']}** — {event['event']}")
        if result["delivered"]:
            st.success(f"Packet delivered to gateway/server in {result['hops']} hop(s). Message ID deduplication prevented duplicate forwarding.")
            if options and selected in options:
                update_status(packet["message_id"], "Delivered")
        else:
            st.warning("No route to gateway. Packet is queued for store-and-forward retry when connectivity returns.")
        st.json({"message_id":packet["message_id"],"delivered":result["delivered"],"hops":result["hops"],"queued_for_retry":not result["delivered"],"ttl":ttl})
    st.caption("This is a software simulation, not real Android BLE/Wi-Fi Direct networking. A production mesh transport would need an Android client and device-level testing.")

elif page == "AI Triage":
    header("AI-assisted Triage", "Generate a short responder brief from selected SOS reports. Human responders remain responsible for decisions.")
    rows = list_sos(limit=100)
    if not rows:
        st.info("Add one or more SOS alerts before running triage.")
    else:
        options = {f"{r['message_id']} · {r['priority']} · {r['emergency_type']}":r for r in rows}
        chosen = st.multiselect("Select alerts", list(options.keys()), default=list(options.keys())[:min(5,len(options))])
        include_ai = st.checkbox("Use Groq LLM when API key is configured", value=True)
        if st.button("Generate triage brief", type="primary", disabled=not chosen):
            packets = [options[x] for x in chosen]
            with st.spinner("Preparing triage brief…"):
                result = generate_triage_brief(packets, use_llm=include_ai)
            st.markdown("### Responder brief")
            st.markdown(result["text"])
            st.caption(f"Method: {result['method']} · Rule-based priority is retained as the baseline. Verify all details before acting.")
            st.download_button("Download brief (.txt)", result["text"], file_name="crisis_resq_triage_brief.txt", mime="text/plain")

elif page == "Message Log":
    header("SOS Message Log", "Review, filter, update status and export locally stored alert records.")
    rows = list_sos(limit=1000)
    if rows:
        df = pd.DataFrame(rows)
        f1,f2 = st.columns(2)
        priorities = f1.multiselect("Priority filter", ["CRITICAL","HIGH","MEDIUM","LOW"])
        statuses = f2.multiselect("Status filter", ["Queued","Relayed","Delivered","Resolved"], default=["Queued","Relayed","Delivered","Resolved"])
        filtered = df.copy()
        if priorities: filtered = filtered[filtered.priority.isin(priorities)]
        if statuses: filtered = filtered[filtered.status.isin(statuses)]
        st.dataframe(filtered, use_container_width=True, hide_index=True)
        st.download_button("Export visible records as CSV", filtered.to_csv(index=False).encode("utf-8"), file_name="crisis_resq_sos_export.csv", mime="text/csv")
        st.markdown("### Update alert status")
        ids = filtered["message_id"].tolist()
        if ids:
            selected_id = st.selectbox("Message ID", ids)
            new_status = st.selectbox("New status", ["Queued","Relayed","Delivered","Resolved"])
            if st.button("Save status"):
                update_status(selected_id, new_status)
                st.success("Status updated. Refresh the page to see the latest value.")
    else:
        st.info("The message log is empty.")

else:
    header("Project Notes & Architecture", "A formal, reproducible Python MVP based on the Cache Cube Crisis ResQ pitch deck.")
    st.markdown("### System architecture")
    st.code("Victim / SOS form → SQLite offline queue → Rule-based priority scoring → Mesh relay simulator → Gateway/server concept → Rescue dashboard → Optional Groq LLM triage brief", language="text")
    st.markdown("### Technology stack")
    st.markdown("- **Python + Streamlit:** web-based demonstration and command dashboard\n- **SQLite:** persistent local SOS storage\n- **Groq API:** optional LLM-generated triage summaries\n- **pandas:** tabular alert review and CSV export\n- **python-dotenv:** secrets loaded from `.env`\n- **pytest:** automated tests for priority scoring and relay simulation")
    st.markdown("### Model constraint")
    st.write("Default model is `openai/gpt-oss-20b` (20B parameters). The model is called through Groq's hosted API; model weights are not downloaded to your laptop. Confirm current model availability in your Groq Console before the demo.")
    st.markdown("### Important scope boundary")
    st.warning("The pitch deck describes Android Kotlin, BLE/Wi-Fi Direct and real device-to-device relaying. This Python MVP demonstrates the dashboard, SOS data model, priority logic and relay behavior in simulation. It does not itself implement physical phone mesh networking, GPS acquisition from a phone, or a certified emergency response service.")
