# --- Heat Safety Monitor (Raha MS) ---
import streamlit as st
import pandas as pd
import requests, json, os, math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Heat Safety Monitor", page_icon="🌡️", layout="wide")
TZ_DUBAI = ZoneInfo("Asia/Dubai")

OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")
# You can pass lat/lon via query params or keep simple and use a city name you already store.
DEFAULT_CITY = st.secrets.get("DEFAULT_CITY", "Sharjah,AE")  # adjust to your app
CSV_PATH = st.secrets.get("JOURNAL_CSV", "temperature_log.csv")

# Settings: user baseline core temp (°C)
BASELINE_CORE_C = float(st.session_state.get("BASELINE_CORE_C", 36.6))  # fallback if not set in Settings

# ---------------- STATE ----------------
if "journal_df" not in st.session_state:
    # Load existing CSV if available; else initialize empty
    if os.path.exists(CSV_PATH):
        try:
            st.session_state.journal_df = pd.read_csv(CSV_PATH)
        except Exception:
            st.session_state.journal_df = pd.DataFrame()
    else:
        st.session_state.journal_df = pd.DataFrame()

# For live weather cache per run
st.session_state.setdefault("weather_cache", {})

# ---------------- HELPERS ----------------
def fetch_openweather_feels_like(city: str) -> dict:
    """
    Returns a dict with feels_like (°C), temp (°C), humidity (%), wind_speed (m/s), and optional UV if available.
    Uses Current Weather endpoint for simplicity.
    """
    cache_key = ("ow", city)
    if cache_key in st.session_state["weather_cache"]:
        return st.session_state["weather_cache"][cache_key]

    if not OPENWEATHER_API_KEY:
        return {"error": "Missing OpenWeather API key."}

    try:
        # 1) Geocode city -> lat/lon
        geo = requests.get(
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": city, "limit": 1, "appid": OPENWEATHER_API_KEY},
            timeout=10,
        ).json()
        if not geo:
            return {"error": f"Could not geocode '{city}'"}

        lat, lon = geo[0]["lat"], geo[0]["lon"]

        # 2) Current weather
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric"},
            timeout=10,
        ).json()

        main = r.get("main", {})
        wind = r.get("wind", {})
        feels_like = main.get("feels_like")  # °C
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

def classify_status(core_c: float, delta_core_c: float, feels_like_c: float, ctx: dict) -> tuple[str, list]:
    """
    Returns (status_str, why_rules_list)
    Levels: Safe < Caution < High < Critical
    Rules are intentionally transparent (Uhthoff-first; env bump; absolute core; context escalators/mitigators)
    """
    level_order = ["Safe", "Caution", "High", "Critical"]
    level = 0
    why = []

    # 1) Uhthoff primary (Δ from baseline)
    if delta_core_c >= 0.5:
        level = max(level, 1)
        why.append(f"ΔCore = +{delta_core_c:.1f} °C ≥ 0.5 °C → Caution (Uhthoff)")

    # 2) Absolute core gates (conservative)
    if core_c >= 38.5:
        level = max(level, 3); why.append("Core ≥ 38.5 °C → Critical")
    elif core_c >= 38.0:
        level = max(level, 2); why.append("Core ≥ 38.0 °C → High")
    elif core_c >= 37.8:
        level = max(level, 1); why.append("Core ≥ 37.8 °C → Caution")

    # 3) Environment bump (Feels-Like proxy)
    if feels_like_c is not None:
        if feels_like_c >= 42:
            level = max(level, 2); why.append("Feels-Like ≥ 42 °C → High (environment)")
        elif feels_like_c >= 38:
            level = max(level, 1); why.append("Feels-Like ≥ 38 °C → Caution (environment)")

    # 4) Context escalators/mitigators
    # Escalators
    if ctx.get("sun_exposure", False):
        level = min(3, level + 1); why.append("Direct sun → +1 level")
    if ctx.get("dehydrated", False):
        level = min(3, level + 1); why.append("Dehydration → +1 level")
    if ctx.get("fever", False):
        level = min(3, level + 1); why.append("Fever → +1 level")

    # Mitigators
    down = 0
    if ctx.get("cooling_vest", False): down += 1
    if ctx.get("fan_or_ac", False):    down += 1
    if down:
        prev = level
        level = max(0, level - down)
        why.append(f"Cooling (vest/fan/AC) → −{min(prev, down)} level(s)")

    return level_order[level], why

def write_journal_row(row: dict):
    """Append a single row to session DF + CSV (write-through)."""
    df = st.session_state.get("journal_df", pd.DataFrame())
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    st.session_state["journal_df"] = df

    # Append to CSV safely
    header = not os.path.exists(CSV_PATH) or os.stat(CSV_PATH).st_size == 0
    df.tail(1).to_csv(CSV_PATH, mode="a", header=header, index=False)

# ---------------- UI ----------------
st.title("Heat Safety Monitor 🌡️")

# Purpose statement (short, user-facing)
st.info(
    "Adjust your **Core** and **Peripheral (skin)** temperatures **continuously** to see how the app reacts—"
    "using **real-time weather** and your **baseline core temperature** (from Settings). "
    "Pick an **activity** to shape the curve; alerts are triggered mainly by your **change from baseline (Uhthoff)**."
)

with st.sidebar:
    st.header("Environment")
    city = st.text_input("City", value=DEFAULT_CITY, help="Used to fetch live Feels-Like from OpenWeather")
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
    st.caption("Feels-Like comes from your weather API and is a practical proxy for ambient heat.")

    st.divider()
    st.header("Context")
    activity = st.select_slider("Activity (shapes core rise)", options=[
        "Resting", "Light walk", "Household chores", "Moderate exercise", "Vigorous exercise"
    ], value="Resting")
    sun_exposure = st.toggle("Direct sun", value=False)
    dehydrated = st.toggle("Dehydrated", value=False)
    cooling_vest = st.toggle("Cooling vest", value=False)
    fan_or_ac = st.toggle("Fan / AC", value=False)
    fever = st.toggle("Fever", value=False)

# Main controls (continuous)
c1, c2, c3 = st.columns([1.1, 1, 1])
with c1:
    st.subheader("Body Temps (continuous)")
    # Basic activity-driven suggestion for core trajectory speed (for projection UI hint)
    activity_speed = {
        "Resting": 0.00, "Light walk": 0.02, "Household chores": 0.03,
        "Moderate exercise": 0.05, "Vigorous exercise": 0.08,
    }[activity]

    core_c = st.slider("Core (°C)", 36.0, 39.5, value=float(BASELINE_CORE_C), step=0.1)
    peripheral_c = st.slider("Peripheral / Skin (°C)", 30.0, 38.0, value=33.0, step=0.1)

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
        f"border-radius:0.4rem; display:inline-block; "
        f"background:{ {'Safe':'#E6F4EA','Caution':'#FFF8E1','High':'#FFE0E0','Critical':'#FFCDD2'}[status]};'>"
        f"{status}</div>",
        unsafe_allow_html=True
    )
    with st.expander("Why this status? (rules firing)"):
        for rule in why:
            st.write("• " + rule)
        st.caption(
            "Alerts are based on your **ΔCore** (Uhthoff), absolute core, and an environment bump from Feels-Like; "
            "context toggles can nudge the level up/down."
        )

with c3:
    st.subheader("Symptoms (optional)")
    symptoms = st.multiselect(
        "Tick any symptoms you notice now (for your journal; not used to compute status):",
        ["Blurred vision / optic", "Fatigue", "Weakness", "Balance", "Sensory changes", "Cognition", "Bladder urgency"],
        default=[],
    )
    note = st.text_input("Notes (optional)", "")

st.divider()

# Timeline / Plot (lightweight, built-in)
st.subheader("Timeline")
if "timeline_df" not in st.session_state:
    st.session_state.timeline_df = pd.DataFrame(columns=[
        "timestamp_local", "core_c", "peripheral_c", "feels_like_c", "status"
    ])

plot_cols = st.columns([1, 0.35])
with plot_cols[0]:
    # Append live point to a small rolling buffer for visualization (not journal)
    live_row = {
        "timestamp_local": datetime.now(TZ_DUBAI).strftime("%Y-%m-%d %H:%M:%S"),
        "core_c": core_c,
        "peripheral_c": peripheral_c,
        "feels_like_c": feels_like_c if feels_like_c is not None else float("nan"),
        "status": status
    }
    # Show chart using a tiny DataFrame of last N interactions
    tmp_df = pd.concat([st.session_state.timeline_df, pd.DataFrame([live_row])], ignore_index=True).tail(60)
    st.line_chart(
        tmp_df[["core_c", "peripheral_c", "feels_like_c"]].rename(
            columns={"core_c":"Core °C","peripheral_c":"Peripheral °C","feels_like_c":"Feels-Like °C"}
        ),
        height=260,
    )

with plot_cols[1]:
    st.caption("**Mark point** snapshots the current state to your Timeline and Journal.")
    btn_mark = st.button("📍 Mark point", use_container_width=True)
    if btn_mark:
        st.session_state.timeline_df = pd.concat(
            [st.session_state.timeline_df, pd.DataFrame([live_row])], ignore_index=True
        )
        # Write-through to Journal CSV + session state
        journal_row = {
            "timestamp_local": live_row["timestamp_local"],
            "city": city,
            "baseline_core_c": f"{BASELINE_CORE_C:.1f}",
            "core_c": round(core_c, 1),
            "peripheral_c": round(peripheral_c, 1),
            "delta_core_c": round(delta_core, 1),
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
        write_journal_row(journal_row)
        st.success("Saved to Journal & CSV")
        st.rerun()  # make sure other tabs reflect the new row immediately

st.divider()

# Scenario presets (load + apply instantly)
st.subheader("Scenarios")
colL, colR = st.columns([1,1])
with colL:
    scenario = st.selectbox(
        "Choose a preset to apply:",
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
    if st.button("Apply scenario", use_container_width=True, disabled=(scenario == "— Select —")):
        # Apply simple representative values; users can tweak continuously after applying
        if scenario == "AC office, resting":
            st.session_state["core_c"] = BASELINE_CORE_C
            st.session_state["peripheral_c"] = 33.0
            st.session_state["sun_exposure"] = False
            st.session_state["dehydrated"] = False
            st.session_state["cooling_vest"] = False
            st.session_state["fan_or_ac"] = True
            st.session_state["fever"] = False
            st.session_state["activity"] = "Resting"
        elif scenario == "Hot commute (sun), light walk":
            st.session_state["core_c"] = BASELINE_CORE_C + 0.4
            st.session_state["peripheral_c"] = 35.0
            st.session_state["sun_exposure"] = True
            st.session_state["dehydrated"] = False
            st.session_state["fan_or_ac"] = False
            st.session_state["cooling_vest"] = False
            st.session_state["fever"] = False
            st.session_state["activity"] = "Light walk"
        elif scenario == "Moderate exercise outdoors (humid)":
            st.session_state["core_c"] = BASELINE_CORE_C + 0.6
            st.session_state["peripheral_c"] = 36.0
            st.session_state["sun_exposure"] = True
            st.session_state["dehydrated"] = True
            st.session_state["fan_or_ac"] = False
            st.session_state["cooling_vest"] = False
            st.session_state["fever"] = False
            st.session_state["activity"] = "Moderate exercise"
        elif scenario == "Fever at home":
            st.session_state["core_c"] = 38.1
            st.session_state["peripheral_c"] = 36.5
            st.session_state["sun_exposure"] = False
            st.session_state["dehydrated"] = False
            st.session_state["fan_or_ac"] = True
            st.session_state["cooling_vest"] = False
            st.session_state["fever"] = True
            st.session_state["activity"] = "Resting"
        elif scenario == "Cooling vest intervention":
            st.session_state["core_c"] = BASELINE_CORE_C + 0.6
            st.session_state["peripheral_c"] = 35.8
            st.session_state["sun_exposure"] = True
            st.session_state["dehydrated"] = False
            st.session_state["fan_or_ac"] = False
            st.session_state["cooling_vest"] = True
            st.session_state["fever"] = False
            st.session_state["activity"] = "Moderate exercise"
        elif scenario == "Evening stroll, breezy/shade":
            st.session_state["core_c"] = BASELINE_CORE_C + 0.2
            st.session_state["peripheral_c"] = 33.5
            st.session_state["sun_exposure"] = False
            st.session_state["dehydrated"] = False
            st.session_state["fan_or_ac"] = True
            st.session_state["cooling_vest"] = False
            st.session_state["fever"] = False
            st.session_state["activity"] = "Light walk"
        st.success(f"Applied: {scenario} — tweak sliders to explore")
        st.rerun()

# Tiny Rules drawer (for transparency)
with st.expander("Heat rules (how this page decides)"):
    st.markdown("""
**Primary (Uhthoff):** If your **ΔCore ≥ ~0.5 °C** above your baseline → at least **Caution**.  
**Absolute core:** ≥ 37.8 → Caution; ≥ 38.0 → High; ≥ 38.5 → Critical.  
**Environment bump (Feels-Like):** ≥ 38 °C → Caution; ≥ 42 °C → High.  
**Context escalators:** Direct sun / dehydration / fever → +1 level each.  
**Mitigations:** Cooling vest, fan/AC can bring the level down.
    """)
    st.caption("This page is an educational planner, not a medical device. If symptoms persist or are new, seek medical advice.")

# Expose current values in session_state so Scenarios can set them
# (Streamlit sliders don't accept programmatic updates directly; we mirror via session_state as needed)
if "core_c" in st.session_state:
    core_c = st.session_state.pop("core_c")
    st.slider("Core (°C)", 36.0, 39.5, value=core_c, step=0.1, key="__core_display", disabled=True)
if "peripheral_c" in st.session_state:
    peripheral_c = st.session_state.pop("peripheral_c")
    st.slider("Peripheral / Skin (°C)", 30.0, 38.0, value=peripheral_c, step=0.1, key="__peri_display", disabled=True)
if "activity" in st.session_state:
    st.caption(f"Scenario set activity → **{st.session_state.pop('activity')}**")
