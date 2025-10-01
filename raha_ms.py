# =========================
# Heat Safety Monitor (Raha MS)
# =========================
# Drop this file in your app (e.g., heat_monitor.py) and either:
#  - Put it under a Streamlit `pages/` folder (it becomes its own page), OR
#  - Import and call run() from your main router:  `import heat_monitor; heat_monitor.run()`

import os
import math
import json
import requests
import pandas as pd
import streamlit as st
from collections import deque
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ---------- CONFIG ----------
st.set_page_config(page_title="Heat Safety Monitor", page_icon="🌡️", layout="wide")
TZ_DUBAI = ZoneInfo("Asia/Dubai")

# Secrets (fallbacks for local dev)
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")
DEFAULT_CITY = st.secrets.get("DEFAULT_CITY", "Sharjah,AE")
CSV_PATH = st.secrets.get("JOURNAL_CSV", "temperature_log.csv")

# User setting (baseline core)
DEFAULT_BASELINE_CORE = 36.6  # used if you haven't set this in Settings->session_state
BASELINE_CORE_C = float(st.session_state.get("BASELINE_CORE_C", DEFAULT_BASELINE_CORE))

# ---------- STATE ----------
# Journal DF (shared across pages)
if "journal_df" not in st.session_state:
    if os.path.exists(CSV_PATH) and os.stat(CSV_PATH).st_size > 0:
        try:
            st.session_state.journal_df = pd.read_csv(CSV_PATH)
        except Exception:
            st.session_state.journal_df = pd.DataFrame()
    else:
        st.session_state.journal_df = pd.DataFrame()

# Live chart rolling buffer (fast, lightweight)
if "live_buffer" not in st.session_state:
    st.session_state.live_buffer = deque(maxlen=600)  # ~20 min at 2s sampling

# Cache for weather
st.session_state.setdefault("weather_cache", {})

# Scenario/demo state
st.session_state.setdefault("demo_ticks", 0)   # counts down seconds during demo
st.session_state.setdefault("demo_phase", "up")  # "up" then "down"

# ---------- HELPERS ----------
def fetch_openweather_feels_like(city: str) -> dict:
    """
    Return dict with: feels_like_c, temp_c, humidity_pct, wind_speed_ms, dt_utc, lat, lon
    """
    cache_key = ("ow", city)
    if cache_key in st.session_state["weather_cache"]:
        return st.session_state["weather_cache"][cache_key]

    if not OPENWEATHER_API_KEY:
        return {"error": "Missing OpenWeather API key."}

    try:
        # Geocode
        geo = requests.get(
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": city, "limit": 1, "appid": OPENWEATHER_API_KEY},
            timeout=10,
        ).json()
        if not geo:
            return {"error": f"Could not geocode '{city}'"}
        lat, lon = geo[0]["lat"], geo[0]["lon"]

        # Current weather
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric"},
            timeout=10,
        ).json()

        main = r.get("main", {})
        wind = r.get("wind", {})
        feels_like = main.get("feels_like")
        temp = main.get("temp")
        humidity = main.get("humidity")
        wind_speed = wind.get("speed")

        data = {
            "city": city,
            "lat": lat,
            "lon": lon,
            "feels_like_c": feels_like,
            "temp_c": temp,
            "humidity_pct": humidity,
            "wind_speed_ms": wind_speed,
            "dt_utc": datetime.fromtimestamp(r.get("dt", int(datetime.now().timestamp())), tz=timezone.utc),
        }
        st.session_state["weather_cache"][cache_key] = data
        return data
    except Exception as e:
        return {"error": str(e)}

def classify_status(core_c: float, delta_core_c: float, feels_like_c: float | None, ctx: dict) -> tuple[str, list]:
    """
    Return (status_str, why_rules_list)
    Levels: Safe < Caution < High < Critical
    Uhthoff (Δ from baseline) + absolute core + environment bump + context modifiers
    """
    level_order = ["Safe", "Caution", "High", "Critical"]
    level = 0
    why = []

    # 1) Uhthoff primary
    if delta_core_c >= 0.5:
        level = max(level, 1)
        why.append(f"ΔCore = +{delta_core_c:.1f} °C ≥ 0.5 °C → Caution (Uhthoff)")

    # 2) Absolute core
    if core_c >= 38.5:
        level = max(level, 3); why.append("Core ≥ 38.5 °C → Critical")
    elif core_c >= 38.0:
        level = max(level, 2); why.append("Core ≥ 38.0 °C → High")
    elif core_c >= 37.8:
        level = max(level, 1); why.append("Core ≥ 37.8 °C → Caution")

    # 3) Environment bump
    if feels_like_c is not None:
        if feels_like_c >= 42:
            level = max(level, 2); why.append("Feels-Like ≥ 42 °C → High (environment)")
        elif feels_like_c >= 38:
            level = max(level, 1); why.append("Feels-Like ≥ 38 °C → Caution (environment)")

    # 4) Context escalators/mitigators
    if ctx.get("sun_exposure", False):
        level = min(3, level + 1); why.append("Direct sun → +1 level")
    if ctx.get("dehydrated", False):
        level = min(3, level + 1); why.append("Dehydration → +1 level")
    if ctx.get("fever", False):
        level = min(3, level + 1); why.append("Fever → +1 level")

    down = 0
    if ctx.get("cooling_vest", False): down += 1
    if ctx.get("fan_or_ac", False):    down += 1
    if down:
        prev = level
        level = max(0, level - down)
        why.append(f"Cooling (vest/fan/AC) → −{min(prev, down)} level(s)")

    return level_order[level], why

def write_journal_row(row: dict):
    """Append one row to in-memory journal DF and to CSV (write-through)."""
    df = st.session_state.get("journal_df", pd.DataFrame())
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    st.session_state["journal_df"] = df

    header = not os.path.exists(CSV_PATH) or os.stat(CSV_PATH).st_size == 0
    df.tail(1).to_csv(CSV_PATH, mode="a", header=header, index=False)

def _status_color(status: str) -> str:
    return {"Safe": "#E6F4EA", "Caution": "#FFF8E1", "High": "#FFE0E0", "Critical": "#FFCDD2"}.get(status, "#EEE")

# ---------- PAGE ----------
def run():
    st.title("Heat Safety Monitor 🌡️")

    # Purpose
    st.info(
        "Adjust your **Core** and **Peripheral (skin)** temperatures **continuously** to see how the app reacts—"
        "using **real-time weather** and your **baseline core** (Settings). "
        "Pick an **activity** to shape the curve; alerts trigger mainly from your **ΔCore (Uhthoff)**."
    )

    # ----- SIDEBAR: Environment + Context -----
    with st.sidebar:
        st.header("Environment")
        city = st.text_input("City", value=DEFAULT_CITY, help="Used to fetch Feels-Like from OpenWeather")
        wx = fetch_openweather_feels_like(city)
        if "error" in wx:
            st.error(wx["error"])
            feels_like_c = None
            humidity = None
            wind = None
        else:
            feels_like_c = wx["feels_like_c"]
            humidity = wx["humidity_pct"]
            wind = wx["wind_speed_ms"]

        colA, colB = st.columns(2)
        colA.metric("Feels-Like (°C)", f"{feels_like_c:.1f}" if feels_like_c is not None else "—")
        colB.metric("Humidity (%)", f"{humidity:.0f}" if humidity is not None else "—")
        st.caption("Feels-Like is a practical proxy for ambient heat from your weather API.")

        st.divider()
        st.header("Context")
        activity = st.select_slider(
            "Activity (shapes core rise)",
            options=["Resting", "Light walk", "Household chores", "Moderate exercise", "Vigorous exercise"],
            value="Resting",
        )
        sun_exposure = st.toggle("Direct sun", value=False)
        dehydrated = st.toggle("Dehydrated", value=False)
        cooling_vest = st.toggle("Cooling vest", value=False)
        fan_or_ac = st.toggle("Fan / AC", value=False)
        fever = st.toggle("Fever", value=False)

    # ----- MAIN: Controls -----
    c1, c2, c3 = st.columns([1.15, 1.0, 1.1])

    with c1:
        st.subheader("Body Temps (continuous)")
        # store sliders with stable keys so scenarios can update values via session_state
        if "core_slider" not in st.session_state:
            st.session_state.core_slider = BASELINE_CORE_C
        if "peri_slider" not in st.session_state:
            st.session_state.peri_slider = 33.0

        core_c = st.slider("Core (°C)", 36.0, 39.5, value=float(st.session_state.core_slider), step=0.1, key="core_slider")
        peripheral_c = st.slider("Peripheral / Skin (°C)", 30.0, 38.0, value=float(st.session_state.peri_slider), step=0.1, key="peri_slider")

        delta_core = core_c - BASELINE_CORE_C
        st.caption(f"Baseline: {BASELINE_CORE_C:.1f} °C → ΔCore: **+{delta_core:.1f} °C**")

    with c2:
        st.subheader("Status")
        ctx = {
            "sun_exposure": sun_exposure,
            "dehydrated": dehydrated,
            "cooling_vest": cooling_vest,
            "fan_or_ac": fan_or_ac,
            "fever": fever,
        }
        status, why = classify_status(core_c, delta_core, feels_like_c, ctx)
        st.markdown(
            f"<div style='font-size:1.4rem; font-weight:700; padding:0.4rem 0.6rem; "
            f"border-radius:0.5rem; display:inline-block; background:{_status_color(status)};'>{status}</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Why this status? (rules firing)"):
            for rule in why:
                st.write("• " + rule)
            st.caption(
                "Alerts are based on **ΔCore (Uhthoff)**, absolute core, and an environment bump (Feels-Like); "
                "context toggles can nudge the level up/down."
            )

    with c3:
        st.subheader("Symptoms (optional)")
        symptoms = st.multiselect(
            "Tick any that apply (saved to Journal; not used for scoring):",
            ["Blurred vision / optic", "Fatigue", "Weakness", "Balance", "Sensory changes", "Cognition", "Bladder urgency"],
            default=[],
        )
        note = st.text_input("Notes (optional)", "")

    st.divider()

    # ----- TIMELINE: Live tracking + Plot + Mark point -----
    st.subheader("Timeline")

    col_live1, col_live2, col_live3 = st.columns([0.35, 0.35, 0.3])
    with col_live1:
        live_on = st.toggle("Live tracking (auto-sample)", value=False, help="Append a point every few seconds")
    with col_live2:
        sample_every = st.select_slider("Sample every (s)", options=[1, 2, 3, 5, 10], value=2)
    with col_live3:
        if st.button("🧹 Clear live buffer"):
            st.session_state.live_buffer.clear()
            st.toast("Live buffer cleared", icon="🧹")

    # Auto-refresh while live tracking (best-effort depending on Streamlit version)
    if live_on:
        try:
            st.autorefresh(interval=sample_every * 1000, key="live_refresh")
        except Exception:
            pass  # older Streamlit: page still reruns on interactions

        # Append current point into rolling buffer on each render while live_on
        st.session_state.live_buffer.append({
            "timestamp_local": datetime.now(TZ_DUBAI).strftime("%Y-%m-%d %H:%M:%S"),
            "core_c": core_c,
            "peripheral_c": peripheral_c,
            "feels_like_c": feels_like_c if feels_like_c is not None else float("nan"),
            "status": status,
        })

    # Optional demo playback (animate core up then down)
    if st.session_state.demo_ticks > 0:
        if st.session_state.demo_phase == "up":
            st.session_state.core_slider = min(39.5, st.session_state.core_slider + 0.05)
            st.session_state.demo_ticks -= 1
            if st.session_state.demo_ticks == 10:  # halfway switch
                st.session_state.demo_phase = "down"
        else:  # "down"
            st.session_state.core_slider = max(36.0, st.session_state.core_slider - 0.05)
            st.session_state.demo_ticks -= 1
            if st.session_state.demo_ticks == 0:
                st.session_state.demo_phase = "up"
        try:
            st.autorefresh(interval=1000, key="demo_refresh")
        except Exception:
            pass

    # Build DataFrame for chart
    live_df = pd.DataFrame(list(st.session_state.live_buffer))
    if not live_df.empty:
        st.line_chart(
            live_df[["core_c", "peripheral_c", "feels_like_c"]].rename(
                columns={"core_c": "Core °C", "peripheral_c": "Peripheral °C", "feels_like_c": "Feels-Like °C"}
            ),
            height=280,
        )
    else:
        st.info("Turn on **Live tracking** (top of this section) or click **Mark point** to build a timeline.")

    # Mark point = snapshot to Journal/CSV
    st.caption("**Mark point** saves this moment to your Journal/CSV (use it for key events like symptoms or threshold crossings).")
    btn_mark = st.button("📍 Mark point", use_container_width=True)
    if btn_mark:
        ts_local = datetime.now(TZ_DUBAI).strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "timestamp_local": ts_local,
            "city": city,
            "baseline_core_c": round(BASELINE_CORE_C, 1),
            "core_c": round(core_c, 1),
            "peripheral_c": round(peripheral_c, 1),
            "delta_core_c": round(core_c - BASELINE_CORE_C, 1),
            "feels_like_c": round(feels_like_c, 1) if feels_like_c is not None else None,
            "activity": activity,
            "sun_exposure": sun_exposure,
            "dehydrated": dehydrated,
            "cooling_vest": cooling_vest,
            "fan_or_ac": fan_or_ac,
            "fever": fever,
            "status": status,
            "why": " | ".join(why),
            "symptoms": ", ".join(symptoms) if symptoms else "",
            "note": note,
        }
        write_journal_row(row)
        st.success("Saved to Journal & CSV")
        st.rerun()  # keep Journal/Exports tabs in sync immediately

    st.divider()

    # ----- SCENARIOS -----
    st.subheader("Scenarios")
    colL, colR, colP = st.columns([0.5, 0.5, 0.4])

    with colL:
        scenario = st.selectbox(
            "Apply a preset:",
            [
                "— Select —",
                "AC office, resting",
                "Hot commute (sun), light walk",
                "Moderate exercise outdoors (humid)",
                "Fever at home",
                "Cooling vest intervention",
                "Evening stroll, breezy/shade",
            ],
            index=0,
        )

    with colR:
        apply_disabled = (scenario == "— Select —")
        if st.button("Apply scenario", use_container_width=True, disabled=apply_disabled):
            # Set representative starting values; you can tweak immediately after
            if scenario == "AC office, resting":
                st.session_state.core_slider = BASELINE_CORE_C
                st.session_state.peri_slider = 33.0
                st.session_state["sun_exposure"] = False
                st.session_state["dehydrated"] = False
                st.session_state["fan_or_ac"] = True
                st.session_state["cooling_vest"] = False
                st.session_state["fever"] = False
            elif scenario == "Hot commute (sun), light walk":
                st.session_state.core_slider = BASELINE_CORE_C + 0.4
                st.session_state.peri_slider = 35.0
                st.session_state["sun_exposure"] = True
                st.session_state["dehydrated"] = False
                st.session_state["fan_or_ac"] = False
                st.session_state["cooling_vest"] = False
                st.session_state["fever"] = False
            elif scenario == "Moderate exercise outdoors (humid)":
                st.session_state.core_slider = BASELINE_CORE_C + 0.6
                st.session_state.peri_slider = 36.0
                st.session_state["sun_exposure"] = True
                st.session_state["dehydrated"] = True
                st.session_state["fan_or_ac"] = False
                st.session_state["cooling_vest"] = False
                st.session_state["fever"] = False
            elif scenario == "Fever at home":
                st.session_state.core_slider = 38.1
                st.session_state.peri_slider = 36.5
                st.session_state["sun_exposure"] = False
                st.session_state["dehydrated"] = False
                st.session_state["fan_or_ac"] = True
                st.session_state["cooling_vest"] = False
                st.session_state["fever"] = True
            elif scenario == "Cooling vest intervention":
                st.session_state.core_slider = BASELINE_CORE_C + 0.6
                st.session_state.peri_slider = 35.8
                st.session_state["sun_exposure"] = True
                st.session_state["dehydrated"] = False
                st.session_state["fan_or_ac"] = False
                st.session_state["cooling_vest"] = True
                st.session_state["fever"] = False
            elif scenario == "Evening stroll, breezy/shade":
                st.session_state.core_slider = BASELINE_CORE_C + 0.2
                st.session_state.peri_slider = 33.5
                st.session_state["sun_exposure"] = False
                st.session_state["dehydrated"] = False
                st.session_state["fan_or_ac"] = True
                st.session_state["cooling_vest"] = False
                st.session_state["fever"] = False
            st.success(f"Applied: {scenario} — tweak sliders or turn **Live tracking** ON to watch it evolve")
            st.rerun()

    with colP:
        if st.button("▶ Play demo (20s)", use_container_width=True):
            st.session_state.demo_ticks = 20
            st.session_state.demo_phase = "up"
            st.toast("Demo playing: warming up for ~10s, then cooling for ~10s", icon="▶")

    # ----- RULES -----
    with st.expander("Heat rules (how this page decides)"):
        st.markdown("""
**Primary (Uhthoff):** If your **ΔCore ≥ ~0.5 °C** above baseline → at least **Caution**.  
**Absolute core:** ≥ 37.8 → Caution; ≥ 38.0 → High; ≥ 38.5 → Critical.  
**Environment bump (Feels-Like):** ≥ 38 °C → Caution; ≥ 42 °C → High.  
**Context escalators:** Sun / dehydration / fever → +1 level each.  
**Mitigations:** Cooling vest, fan/AC can bring the level down.
        """)
        st.caption("Educational planner, not a medical device. If symptoms persist or are new, seek medical advice.")

# If you placed this under pages/, Streamlit will run top-level code automatically.
# If you are using a custom router, call run().
if __name__ == "__main__":
    run()
