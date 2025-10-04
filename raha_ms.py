# -*- coding: utf-8 -*-
# Tanzim MS — Comprehensive App (English/Arabic)
# Features: Heat Monitor, Planner, Journal, AI Companion, Exports, Settings
# AI: DeepSeek primary + OpenAI fallback, bilingual, city-aware, chat history
# Security: bcrypt password hashing (with migration from plaintext)
# UI: Accessible styles + targeted RTL fixes (sliders)

import streamlit as st
import sqlite3, json, requests, random, time, zipfile, io, re
from io import BytesIO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import pandas as pd

# Optional sensors via Supabase
try:
    from supabase import create_client, Client
except Exception:
    Client = None
    def create_client(*args, **kwargs): return None

# ================== APP CONFIG ==================
st.set_page_config(page_title="Tanzim MS", page_icon="🌡️", layout="wide")
TZ_DUBAI = ZoneInfo("Asia/Dubai")

# Secrets
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY   = st.secrets.get("OPENAI_API_KEY", "")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", "")

# ================== MATPLOTLIB ARABIC ==================
matplotlib.rcParams["axes.unicode_minus"] = False
_ARABIC_FONTS_TRY = ["Noto Naskh Arabic", "Amiri", "DejaVu Sans", "Arial"]
for _fname in _ARABIC_FONTS_TRY:
    try:
        matplotlib.rcParams["font.family"] = _fname
        break
    except Exception:
        continue

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    def ar_shape(s: str) -> str:
        return get_display(arabic_reshaper.reshape(s))
    _HAS_AR_SHAPER = True
except Exception:
    def ar_shape(s: str) -> str: return s
    _HAS_AR_SHAPER = False

_AR_FONT = FontProperties(family=matplotlib.rcParams["font.family"])

# ================== CONSTANTS ==================
GCC_CITIES = [
    "Abu Dhabi,AE", "Dubai,AE", "Sharjah,AE",
    "Doha,QA", "Al Rayyan,QA", "Kuwait City,KW",
    "Manama,BH", "Riyadh,SA", "Jeddah,SA", "Dammam,SA",
    "Muscat,OM"
]
CITY_LABELS = {
    "Abu Dhabi,AE": {"en": "Abu Dhabi", "ar": "أبوظبي"},
    "Dubai,AE": {"en": "Dubai", "ar": "دبي"},
    "Sharjah,AE": {"en": "Sharjah", "ar": "الشارقة"},
    "Doha,QA": {"en": "Doha", "ar": "الدوحة"},
    "Al Rayyan,QA": {"en": "Al Rayyan", "ar": "الريان"},
    "Kuwait City,KW": {"en": "Kuwait City", "ar": "مدينة الكويت"},
    "Manama,BH": {"en": "Manama", "ar": "المنامة"},
    "Riyadh,SA": {"en": "Riyadh", "ar": "الرياض"},
    "Jeddah,SA": {"en": "Jeddah", "ar": "جدة"},
    "Dammam,SA": {"en": "Dammam", "ar": "الدمام"},
    "Muscat,OM": {"en": "Muscat", "ar": "مسقط"},
}
def city_label(code: str, lang: str) -> str:
    rec = CITY_LABELS.get(code, {})
    return rec.get("ar" if lang == "Arabic" else "en", code.split(",")[0])

# ================== STYLES ==================
ACCESSIBLE_CSS = """
<style>
html, body, [class*="css"] { font-size: 18px; }
:root {
  --card-bg: #ffffff;
  --card-fg: #0f172a;
  --chip-border: rgba(0,0,0,0.12);
  --muted-fg: rgba(15,23,42,0.75);
}
@media (prefers-color-scheme: dark) {
  :root {
    --card-bg: #0b1220;
    --card-fg: #e5e7eb;
    --chip-border: rgba(255,255,255,0.25);
    --muted-fg: rgba(229,231,235,0.85);
  }
}
.big-card {
  background: var(--card-bg); color: var(--card-fg);
  padding: 18px; border-radius: 14px;
  border-left: 10px solid var(--left);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.big-card h3, .big-card p, .big-card .small { color: var(--card-fg); }
.badge {
  display:inline-block; padding:6px 10px; border-radius:999px;
  border:1px solid var(--chip-border); margin-right:6px; color:var(--card-fg);
}
.small { opacity:1; color:var(--muted-fg); font-size:14px; }
h3 { margin-top: 0.2rem; }
.stButton>button { padding: 0.6rem 1.1rem; font-weight: 600; }

/* Lists */
.stMarkdown ul li, .stMarkdown ol li { margin-bottom: 0.6em !important; }
.stMarkdown ul, .stMarkdown ol { margin-bottom: 0.4em !important; }

/* RTL Support (safe; do not flip sidebar container) */
[dir="rtl"] [data-testid="stAppViewContainer"] { direction: rtl !important; text-align: right !important; }
[dir="rtl"] [data-testid="stSidebar"] { direction: ltr !important; text-align: left !important; }
[dir="rtl"] [data-testid="stSidebar"] > div { direction: rtl !important; text-align: right !important; }

/* Sliders: keep mechanics LTR in RTL to feel natural */
[dir="rtl"] [data-testid="stSlider"] { direction: ltr !important; }
[dir="rtl"] [data-testid="stSlider"] > label { direction: rtl !important; text-align: right !important; }
[dir="rtl"] [data-testid="stSlider"] [data-testid="stTickBar"] { direction: ltr !important; }
[dir="rtl"] [data-testid="stSlider"] [data-baseweb="slider"] { direction: ltr !important; }
[dir="rtl"] [data-testid="stThumbValue"] { direction: ltr !important; text-align: center !important; }

/* Mobile tab polish */
@media (max-width: 640px) {
  div[role="tablist"] { overflow-x: auto !important; white-space: nowrap !important; padding-bottom: 6px !important; margin-bottom: 8px !important; }
  .stTabs + div, .stTabs + section { margin-top: 6px !important; }
}
.stMarkdown p, .stMarkdown li { color: inherit !important; }
</style>
"""
st.markdown(ACCESSIBLE_CSS, unsafe_allow_html=True)

# ================== DB ==================
@st.cache_resource
def get_conn():
    conn = sqlite3.connect("raha_ms.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def utc_iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def ensure_emergency_contacts_schema():
    conn = get_conn(); c = conn.cursor()
    c.execute("PRAGMA table_info(emergency_contacts)")
    cols = [r[1] for r in c.fetchall()]
    if "updated_at" not in cols:
        c.execute("ALTER TABLE emergency_contacts ADD COLUMN updated_at TEXT")
        c.execute("UPDATE emergency_contacts SET updated_at = ?", (utc_iso_now(),))
        conn.commit()

def ensure_user_prefs_schema():
    conn = get_conn(); c = conn.cursor()
    c.execute("""
      CREATE TABLE IF NOT EXISTS user_prefs(
        username TEXT PRIMARY KEY,
        home_city TEXT,
        timezone TEXT,
        language TEXT,
        updated_at TEXT
      )
    """); conn.commit()

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY, password TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS temps(
        username TEXT, date TEXT, body_temp REAL, peripheral_temp REAL,
        weather_temp REAL, feels_like REAL, humidity REAL, status TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS journal(
        username TEXT, date TEXT, entry TEXT
    )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS emergency_contacts(
            username TEXT PRIMARY KEY,
            primary_phone TEXT,
            secondary_phone TEXT,
            updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        )
    """)
    conn.commit()
    ensure_emergency_contacts_schema()
    ensure_user_prefs_schema()

init_db()

# Password hashing (bcrypt)
try:
    import bcrypt
    _HAS_BCRYPT = True
except Exception:
    _HAS_BCRYPT = False

def _hash_pw(pw: str) -> str:
    if not _HAS_BCRYPT: return pw
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def _check_pw(pw: str, hashed: str) -> bool:
    if not _HAS_BCRYPT:  # legacy plain text
        return pw == hashed
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

# ================== SUPABASE (optional) ==================
@st.cache_resource
def get_supabase() -> Client | None:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY: return None
    try: return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception: return None

def fetch_latest_sensor_sample(device_id: str) -> dict | None:
    sb = get_supabase()
    if not sb or not device_id: return None
    try:
        res = (sb.table("sensor_readings")
                 .select("core_c,peripheral_c,created_at")
                 .eq("device_id", device_id)
                 .order("created_at", desc=True)
                 .limit(1)
                 .execute())
        data = res.data or []
        if not data: return None
        row = data[0]
        return {"core": float(row["core_c"]), "peripheral": float(row["peripheral_c"]), "at": row["created_at"]}
    except Exception:
        return None

# ================== HELPERS ==================
def tel_href(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^\d+]", "", s)
    if s.count("+") > 1:
        s = "+" + re.sub(r"\D", "", s)
    return s

def insert_journal(u, dt, entry_obj):
    c = get_conn().cursor()
    c.execute("INSERT INTO journal VALUES (?,?,?)", (u, dt, json.dumps(entry_obj)))
    get_conn().commit()

def fetch_temps_df(user):
    c = get_conn().cursor()
    c.execute("""
        SELECT date, body_temp, peripheral_temp, weather_temp, feels_like, humidity, status
        FROM temps WHERE username=? ORDER BY date ASC
    """, (user,))
    rows = c.fetchall()
    cols = ["date","core_temp","peripheral_temp","weather_temp","feels_like","humidity","status"]
    return pd.DataFrame(rows, columns=cols)

def fetch_journal_df(user):
    c = get_conn().cursor()
    c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date ASC", (user,))
    rows = c.fetchall()
    parsed = []
    for dt, raw in rows:
        try:
            obj = json.loads(raw)
            parsed.append({"date": dt, **obj})
        except Exception:
            parsed.append({"date": dt, "type": "NOTE", "text": raw})
    return pd.DataFrame(parsed)

def build_export_excel_or_zip(user) -> tuple[bytes, str]:
    temps = fetch_temps_df(user); journal = fetch_journal_df(user)
    output = BytesIO()
    engine = None
    try:
        import xlsxwriter; engine = "xlsxwriter"
    except Exception:
        try:
            import openpyxl; engine = "openpyxl"
        except Exception:
            engine = None
    if engine:
        with pd.ExcelWriter(output, engine=engine) as writer:
            temps.to_excel(writer, index=False, sheet_name="Temps")
            journal.to_excel(writer, index=False, sheet_name="Journal")
        output.seek(0)
        return output.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    memzip = BytesIO()
    with zipfile.ZipFile(memzip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Temps.csv", temps.to_csv(index=False).encode("utf-8"))
        zf.writestr("Journal.csv", journal.to_csv(index=False).encode("utf-8"))
    memzip.seek(0)
    return memzip.read(), "application/zip"

def dubai_now_str():
    return datetime.now(TZ_DUBAI).strftime("%Y-%m-%d %H:%M")

# ================== WEATHER ==================
@st.cache_data(ttl=600)
def get_weather(city="Abu Dhabi,AE"):
    if not OPENWEATHER_API_KEY: return None, "Missing OPENWEATHER_API_KEY"
    try:
        base = "https://api.openweathermap.org/data/2.5/"
        r_now = requests.get(base + "weather", params={"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang":"en"}, timeout=7)
        r_now.raise_for_status()
        jn = r_now.json()
        temp = float(jn["main"]["temp"]); feels = float(jn["main"]["feels_like"]); hum = float(jn["main"]["humidity"])
        desc = jn["weather"][0]["description"]

        r_fc = requests.get(base + "forecast", params={"q": city, "appid": OPENWEATHER_API_KEY, "units":"metric","lang":"en"}, timeout=9)
        r_fc.raise_for_status()
        jf = r_fc.json()
        items = jf.get("list", [])[:16]
        forecast = [{
            "dt": it["dt"], "time": it["dt_txt"], "temp": float(it["main"]["temp"]),
            "feels_like": float(it["main"]["feels_like"]), "humidity": float(it["main"]["humidity"]),
            "desc": it["weather"][0]["description"]
        } for it in items]
        top = sorted(forecast, key=lambda x: x["feels_like"], reverse=True)[:4]
        peak_hours = [f'{t["time"][5:16]} (~{round(t["feels_like"])}°C, {int(t["humidity"])}%)' for t in top]
        return {"temp":temp, "feels_like":feels, "humidity":hum, "desc":desc, "forecast":forecast, "peak_hours":peak_hours}, None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=600)
def geocode_place(q):
    try:
        url = "https://api.openweathermap.org/geo/1.0/direct"
        r = requests.get(url, params={"q": q, "limit": 1, "appid": OPENWEATHER_API_KEY}, timeout=6)
        r.raise_for_status()
        arr = r.json()
        if not arr: return q, None, None
        it = arr[0]
        return it.get("name") or q, it.get("lat"), it.get("lon")
    except Exception:
        return q, None, None

@st.cache_data(ttl=600)
def get_weather_by_coords(lat, lon):
    if not OPENWEATHER_API_KEY or lat is None or lon is None: return None
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        r = requests.get(url, params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units":"metric"}, timeout=6)
        r.raise_for_status()
        j = r.json()
        return {"temp": float(j["main"]["temp"]), "feels_like": float(j["main"]["feels_like"]), "humidity": float(j["main"]["humidity"]), "desc": j["weather"][0]["description"]}
    except Exception:
        return None

# ================== RISK MODEL ==================
TRIGGER_WEIGHTS = {
    "Exercise": 2, "Sauna/Hot bath": 3, "Spicy food": 1, "Hot drinks": 1, "Stress/Anxiety": 1,
    "Direct sun exposure": 2, "Fever/Illness": 3, "Hormonal cycle": 1, "Tight clothing": 1,
    "Poor sleep": 1, "Dehydration": 2, "Crowded place": 1, "Cooking heat": 1, "Car without AC": 2,
    "Outdoor work": 2, "Long prayer standing": 1
}
SYMPTOM_WEIGHT = 0.5

def risk_from_env(feels_like_c: float, humidity: float) -> int:
    score = 0
    if feels_like_c >= 39: score += 3
    elif feels_like_c >= 35: score += 2
    elif feels_like_c >= 32: score += 1
    if humidity >= 60 and feels_like_c >= 32: score += 1
    return score

def risk_from_person(body_temp: float, baseline: float) -> int:
    delta = (body_temp - baseline) if (body_temp is not None and baseline is not None) else 0
    if delta >= 1.0: return 2
    if delta >= 0.5: return 1
    return 0

def compute_risk(feels_like, humidity, body_temp, baseline, triggers, symptoms):
    score = 0
    score += risk_from_env(feels_like, humidity)
    score += risk_from_person(body_temp, baseline or 37.0)
    score += sum(TRIGGER_WEIGHTS.get(t, 0) for t in (triggers or []))
    score += SYMPTOM_WEIGHT * len(symptoms or [])
    if score >= 7:
        status, color, icon, text = "Danger", "red", "🔴", "High risk: stay in cooled spaces, avoid exertion, use cooling packs, and rest. Seek clinical advice for severe symptoms."
    elif score >= 5:
        status, color, icon, text = "High", "orangered", "🟠", "Elevated risk: limit time outside (esp. midday), pre-cool and pace activities."
    elif score >= 3:
        status, color, icon, text = "Caution", "orange", "🟡", "Mild risk: hydrate, take breaks, prefer shade/AC, and monitor symptoms."
    else:
        status, color, icon, text = "Safe", "green", "🟢", "You look safe. Keep cool and hydrated."
    return {"score": score, "status": status, "color": color, "icon": icon, "advice": text}

# ================== JOURNAL CONTEXT ==================
def get_recent_journal_context(username: str, max_entries: int = 5) -> str:
    """Summarized text for system prompt."""
    try:
        c = get_conn().cursor()
        c.execute("""
            SELECT date, entry FROM journal 
            WHERE username=? ORDER BY date DESC LIMIT ?
        """, (username, max_entries))
        rows = c.fetchall()
    except Exception:
        rows = []

    if not rows: return "No recent journal entries."
    lines = []
    for dt, raw in rows:
        try: entry = json.loads(raw)
        except Exception: entry = {"type":"NOTE", "text":str(raw)}
        t = entry.get("type", "NOTE")
        if t == "DAILY":
            lines.append(f"Daily: mood={entry.get('mood','?')}, hydration={entry.get('hydration_glasses','?')}g, sleep={entry.get('sleep_hours','?')}h, fatigue={entry.get('fatigue','?')}")
            if entry.get("triggers"): lines.append("  Triggers: " + ", ".join(map(str, entry["triggers"]))[:200])
            if entry.get("symptoms"): lines.append("  Symptoms: " + ", ".join(map(str, entry["symptoms"]))[:200])
        elif t in ("ALERT","ALERT_AUTO"):
            core = entry.get("core_temp") or entry.get("body_temp"); base = entry.get("baseline")
            delta = f"+{round(core-base,1)}°C" if (core is not None and base is not None) else ""
            lines.append(f"Alert: core={core}°C {delta}; reasons={entry.get('reasons',[])}; symptoms={entry.get('symptoms',[])}")
        elif t == "PLAN":
            lines.append(f"Plan: {entry.get('activity','?')} in {entry.get('city','?')} ({entry.get('start','?')}→{entry.get('end','?')})")
        else:
            note = (entry.get("text") or entry.get("note") or "").strip()
            if note: lines.append("Note: " + note[:100] + ("..." if len(note)>100 else ""))
    return "\n".join(lines[:10])

def get_recent_journal_bullets(username: str, max_items: int = 3) -> list[str]:
    """Bullets for UI-only uses."""
    try:
        c = get_conn().cursor()
        c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC LIMIT ?", (username, max_items))
        rows = c.fetchall()
    except Exception:
        rows = []
    bullets = []
    for dt_raw, raw_json in rows:
        try: obj = json.loads(raw_json)
        except Exception: obj = {"type":"NOTE","text":str(raw_json)}
        t = obj.get("type","NOTE")
        if t == "PLAN":
            bullets.append(f"PLAN {obj.get('activity','')} {obj.get('start','')}→{obj.get('end','')} @ {obj.get('city','')}")
        elif t in ("ALERT","ALERT_AUTO"):
            core = obj.get("core_temp") or obj.get("body_temp")
            base = obj.get("baseline")
            d = f"+{round(core-base,1)}°C" if (core is not None and base is not None) else ""
            bullets.append(f"ALERT core {core}°C {d}")
        elif t == "DAILY":
            bullets.append(f"DAILY mood {obj.get('mood','-')} hydration {obj.get('hydration_glasses','-')} sleep {obj.get('sleep_hours','-')}h")
        else:
            bullets.append(f"NOTE {obj.get('text','').strip()[:60]}")
    return bullets

# ================== CITY RESOLUTION ==================
CITY_ALIASES = {
    # English
    "abu dhabi":"Abu Dhabi,AE","dubai":"Dubai,AE","sharjah":"Sharjah,AE","doha":"Doha,QA",
    "qatar":"Doha,QA","al rayyan":"Al Rayyan,QA","kuwait city":"Kuwait City,KW","kuwait":"Kuwait City,KW",
    "manama":"Manama,BH","riyadh":"Riyadh,SA","jeddah":"Jeddah,SA","dammam":"Dammam,SA","muscat":"Muscat,OM",
    # Arabic
    "أبوظبي":"Abu Dhabi,AE","دبي":"Dubai,AE","الشارقة":"Sharjah,AE","الدوحة":"Doha,QA","قطر":"Doha,QA",
    "الريان":"Al Rayyan,QA","مدينة الكويت":"Kuwait City,KW","الكويت":"Kuwait City,KW","المنامة":"Manama,BH",
    "الرياض":"Riyadh,SA","جدة":"Jeddah,SA","الدمام":"Dammam,SA","مسقط":"Muscat,OM",
}
def extract_city_from_text(text: str) -> str | None:
    t = (text or "").lower()
    for name, code in CITY_ALIASES.items():
        if name.lower() in t:
            return code
    return None

def recent_journal_city(username: str) -> str | None:
    try:
        c = get_conn().cursor()
        c.execute("""
            SELECT json_extract(entry, '$.city') AS city
            FROM journal WHERE username=? AND city IS NOT NULL
            ORDER BY date DESC LIMIT 1
        """, (username,))
        row = c.fetchone()
        if row and row[0]: return row[0]
    except Exception:
        pass
    return None

def load_user_prefs(username):
    try:
        c = get_conn().cursor()
        c.execute("SELECT home_city, timezone, language FROM user_prefs WHERE username=?", (username,))
        row = c.fetchone()
        return {"home_city": row[0], "timezone": row[1], "language": row[2]} if row else {}
    except Exception:
        return {}

def save_user_prefs(username, **kwargs):
    now = utc_iso_now()
    prefs = load_user_prefs(username); prefs.update({k:v for k,v in kwargs.items() if v is not None})
    c = get_conn().cursor()
    c.execute("""
      INSERT INTO user_prefs (username, home_city, timezone, language, updated_at)
      VALUES (?,?,?,?,?)
      ON CONFLICT(username) DO UPDATE SET
        home_city=excluded.home_city, timezone=excluded.timezone,
        language=excluded.language, updated_at=excluded.updated_at
    """, (username, prefs.get("home_city"), prefs.get("timezone"), prefs.get("language"), now))
    get_conn().commit()

def resolve_city_for_chat(prompt: str) -> str | None:
    # 1) in the prompt
    city = extract_city_from_text(prompt)
    if city:
        st.session_state["current_city"] = city
        return city
    # 2) last in journal
    if "user" in st.session_state:
        city = recent_journal_city(st.session_state["user"])
        if city:
            st.session_state["current_city"] = city
            return city
    # 3) user prefs
    if "user" in st.session_state:
        prefs = load_user_prefs(st.session_state["user"])
        if prefs.get("home_city"):
            st.session_state["current_city"] = prefs["home_city"]
            return prefs["home_city"]
    # 4) session
    if st.session_state.get("current_city"):
        return st.session_state["current_city"]
    # 5) planner/monitor pick
    for key in ("planner_city", "monitor_city"):
        if st.session_state.get(key):
            st.session_state["current_city"] = st.session_state[key]
            return st.session_state[key]
    return None

def get_weather_context(city_code: str | None):
    if not city_code: return ""
    weather_data, _ = get_weather(city_code)
    if not weather_data: return ""
    city_name = city_code.split(",")[0]
    return (
        f"REAL-TIME WEATHER FOR {city_name.upper()}:\n"
        f"• Temp: {weather_data['temp']}°C\n"
        f"• Feels-like: {weather_data['feels_like']}°C\n"
        f"• Humidity: {weather_data['humidity']}%\n"
        f"• Conditions: {weather_data['desc']}\n"
        f"• Peak Heat Times: {', '.join(weather_data.get('peak_hours', []))}"
    )

# ================== AI (DeepSeek → OpenAI; bilingual; history) ==================
def detect_lang_from_text(text: str) -> str:
    return "Arabic" if re.search(r'[\u0600-\u06FF]', text or "") else "English"

def _system_prompt(lang: str, username: str | None, prompt_text: str) -> tuple[str, str, str]:
    city_code = resolve_city_for_chat(prompt_text)
    wx = get_weather_context(city_code)
    journal = get_recent_journal_context(username, max_entries=5) if username else ""
    sys = (
        "You are Raha MS AI Companion — a warm, empathetic assistant for people with Multiple Sclerosis in the Gulf. "
        "Be practical, culturally aware (Arabic/English; prayer/fasting context), and action‑oriented. "
        "Never diagnose; focus on cooling, pacing, hydration, timing, and safety. "
        "Structure your answers in three short sections: 'Do now', 'Plan later', and 'Watch for'. "
        "If the city/time are known, acknowledge them in your opening line."
    )
    if journal and "No recent journal" not in journal:
        sys += f"\n\nUser's recent journal (summarized):\n{journal}"
    if wx:
        sys += f"\n\nWeather context:\n{wx}"
    sys += " Respond only in Arabic." if lang == "Arabic" else " Respond only in English."
    return sys, (city_code or ""), wx

def _build_messages(prompt: str, lang: str, username: str | None, use_history: bool = True) -> list[dict]:
    sys, _, _ = _system_prompt(lang, username, prompt)
    msgs = [{"role":"system","content":sys}]
    if use_history:
        for m in st.session_state.get("chat_history", [])[-8:]:
            if m["role"] in ("user","assistant"):
                msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role":"user","content":prompt})
    return msgs

def _ai_call_deepseek(messages: list[dict]):
    if not DEEPSEEK_API_KEY: return None, None, "no_key"
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    for attempt in range(1, 4):
        try:
            resp = requests.post(url, headers=headers, json={
                "model":"deepseek-chat","messages":messages,"temperature":0.7,"max_tokens":700,"stream":False
            }, timeout=(6, 30))
            if resp.status_code == 200:
                js = resp.json()
                ch = (js.get("choices") or [{}])[0]
                text = (ch.get("message") or {}).get("content") or ch.get("text") or ""
                finish = ch.get("finish_reason")
                if text.strip(): return text, finish, None
                return None, None, "deepseek empty_response"
            transient = resp.status_code in (429,500,502,503,504)
            try:
                err_json = resp.json()
                if "insufficient_system_resource" in str(err_json).lower():
                    transient = True
            except Exception:
                err_json = {"error": resp.text[:200]}
            if transient and attempt < 3: time.sleep(0.6*attempt); continue
            return None, None, f"deepseek {resp.status_code}: {err_json}"
        except requests.exceptions.Timeout:
            if attempt < 3: time.sleep(0.5*attempt); continue
            return None, None, "deepseek timeout"
        except requests.exceptions.RequestException as e:
            return None, None, f"deepseek connection_error: {e}"

def _ai_call_openai(messages: list[dict]):
    if not OPENAI_API_KEY: return None, None, "no_key"
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    for attempt in range(1, 3):
        try:
            resp = requests.post(url, headers=headers, json={
                "model":"gpt-4o-mini","messages":messages,"temperature":0.7,"max_tokens":700,"stream":False
            }, timeout=(6, 30))
            if resp.status_code == 200:
                js = resp.json()
                ch = (js.get("choices") or [{}])[0]
                text = (ch.get("message") or {}).get("content") or ""
                finish = ch.get("finish_reason")
                if text.strip(): return text, finish, None
                return None, None, "openai empty_response"
            if resp.status_code in (429,500,502,503,504) and attempt < 2:
                time.sleep(0.6*attempt); continue
            return None, None, f"openai {resp.status_code}: {resp.text[:200]}"
        except requests.exceptions.Timeout:
            if attempt < 2: time.sleep(0.5*attempt); continue
            return None, None, "openai timeout"
        except requests.exceptions.RequestException as e:
            return None, None, f"openai connection_error: {e}"

def ai_chat(prompt: str, lang: str) -> tuple[str | None, str | None]:
    if not (DEEPSEEK_API_KEY or OPENAI_API_KEY): return None, "no_api_key"
    effective_lang = lang
    if detect_lang_from_text(prompt) == "Arabic": effective_lang = "Arabic"
    messages = _build_messages(prompt, effective_lang, st.session_state.get("user"), use_history=True)
    text, finish, err = _ai_call_deepseek(messages)
    provider = "deepseek"
    if text is None:
        text, finish, err = _ai_call_openai(messages)
        provider = "openai" if text else "deepseek→openai_failed"
    st.session_state["ai_provider_last"] = provider
    st.session_state["ai_last_finish_reason"] = finish
    st.session_state["ai_last_error"] = err
    return (text, None) if text else (None, err or "all_providers_failed")

def ai_response(prompt: str, lang: str, *_args, **_kwargs) -> tuple[str | None, str | None]:
    """Kept for compatibility (Planner calls)."""
    return ai_chat(prompt, lang)

def get_fallback_response(prompt, lang, journal_context="", weather_context=""):
    city_code = resolve_city_for_chat(prompt)
    city_name = city_label(city_code, lang) if city_code else ("your city" if lang=="English" else "مدينتك")
    wx = get_weather_context(city_code) if city_code else ""
    base_en = f"I'm momentarily offline. For {city_name}, stay in AC at peak (11:00–16:00), hydrate, and pace."
    base_ar = f"أنا غير متصل مؤقتًا. في {city_name}، التزم بالمكيف وقت الذروة (11:00–16:00)، رطّب ونظّم نشاطك."
    base = base_ar if lang=="Arabic" else base_en
    if wx: base += "\n\n" + wx
    return base

# ================== I18N ==================
TEXTS = {
    "English": {
        "about_title": "About Tanzim MS",
        "temp_monitor": "Heat Safety Monitor",
        "planner": "Planner & Tips",
        "journal": "Journal",
        "assistant": "AI Companion",
        "settings": "Settings",
        "exports": "Exports",
        "login_title": "Login / Register",
        "username": "Username",
        "password": "Password",
        "login": "Login",
        "register": "Register",
        "logged_in": "✅ Logged in!",
        "bad_creds": "❌ Invalid credentials",
        "account_created": "✅ Account created! Please login.",
        "user_exists": "❌ Username already exists",
        "login_first": "Please login first.",
        "logged_out": "✅ Logged out!",
        "logout": "Logout",
        "risk_dashboard": "Heat Safety Monitor",
        "quick_pick": "Quick pick (GCC):",
        "sensor_update": "Sensor/sample update (sec)",
        "status": "Status",
        "peak_heat": "Peak heat next 48h",
        "quick_tips": "Quick tips",
        "other": "Other",
        "notes": "Notes",
        "save": "Save",
        "save_entry": "Save to Journal",
        "log_now": "Log what happened?",
        "other_activity": "Other activity (optional)",
        "add_to_journal": "Add to Journal",
        "add_selected": "Add selected to Journal",
        "what_if_tips": "Add your own notes for this plan (optional)",
        "ask_ai_tips": "Ask AI for tailored tips",
        "ai_prompt_hint": "Ask something…",
        "assistant_title": "Your AI Companion",
        "assistant_hint": "I can help with cooling, pacing, planning around prayer/fasting, and more.",
        "export_excel": "📥 Export all data (Excel/CSV)",
        "export_title": "Exports",
        "export_desc": "Download your data for your notes or to share with your clinician.",
        "baseline_setting": "Baseline body temperature (°C)",
        "use_temp_baseline": "Use this baseline for monitoring alerts",
        "contacts": "Emergency Contacts",
        "primary_phone": "Primary phone",
        "secondary_phone": "Secondary phone",
        "home_city": "Home City",
        "timezone": "Timezone (optional)",
        "save_settings": "Save settings",
        "saved": "Saved",
        "weather_fail": "Weather lookup failed",
        "ai_unavailable": "AI is unavailable. Add DEEPSEEK_API_KEY (and optionally OPENAI_API_KEY) in secrets.",
        "journal_hint": "Quick logger or free text. Alerts and plans also save here.",
        "daily_logger": "Daily quick logger",
        "mood": "Mood",
        "hydration": "💧 Hydration (glasses)",
        "sleep": "🛌 Sleep (hours)",
        "fatigue": "Fatigue",
        "free_note": "Free note (optional)",
        "emergency": "Emergency",
        "triggers_today": "Triggers today",
        "symptoms_today": "Symptoms today",
        "instant_plan_title": "Instant plan",
        "do_now": "Do now",
        "plan_later": "Plan later",
        "watch_for": "Watch for",
        "trigger": "Trigger",
        "symptom": "Symptom",
        "start_monitoring": "▶️ Start monitoring",
        "pause": "⏸️ Pause",
        "refresh_weather": "🔄 Refresh weather",
        "temperature_trend": "📈 Temperature Trend",
        "filter_by_type": "Filter by type",
        "newer": "⬅️ Newer",
        "older": "Older ➡️",
        "reset_chat": "🧹 Reset chat",
        "thinking": "Thinking...",
        "ask_me_anything": "Ask me anything...",
    },
    "Arabic": {
        "about_title": "عن تنظيم إم إس",
        "temp_monitor": "مراقبة السلامة الحرارية",
        "planner": "المخطط والنصائح",
        "journal": "اليوميات",
        "assistant": "المساعد الذكي",
        "settings": "الإعدادات",
        "exports": "التصدير",
        "login_title": "تسجيل الدخول / إنشاء حساب",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "login": "تسجيل الدخول",
        "register": "إنشاء حساب",
        "logged_in": "✅ تم تسجيل الدخول",
        "bad_creds": "❌ بيانات غير صحيحة",
        "account_created": "✅ تم إنشاء الحساب! الرجاء تسجيل الدخول.",
        "user_exists": "❌ اسم المستخدم موجود",
        "login_first": "يرجى تسجيل الدخول أولاً.",
        "logged_out": "✅ تم تسجيل الخروج!",
        "logout": "تسجيل الخروج",
        "risk_dashboard": "مراقبة السلامة الحرارية",
        "quick_pick": "اختيار سريع (الخليج):",
        "sensor_update": "تحديث العينة (ثانية)",
        "status": "الحالة",
        "peak_heat": "ذروة الحر خلال 48 ساعة",
        "quick_tips": "نصائح سريعة",
        "other": "أخرى",
        "notes": "ملاحظات",
        "save": "حفظ",
        "save_entry": "حفظ في اليوميات",
        "log_now": "تسجيل ما حدث؟",
        "other_activity": "نشاط آخر (اختياري)",
        "add_to_journal": "أضف إلى اليوميات",
        "add_selected": "أضف المحدد إلى اليوميات",
        "what_if_tips": "أضف ملاحظاتك لهذا التخطيط (اختياري)",
        "ask_ai_tips": "اسأل الذكاء عن نصائح مخصصة",
        "ai_prompt_hint": "اسأل شيئًا…",
        "assistant_title": "مرافقك الذكي",
        "assistant_hint": "أساعدك في التبريد والتنظيم والتخطيط حول الصلاة/الصيام وغيرها.",
        "export_excel": "📥 تصدير كل البيانات (Excel/CSV)",
        "export_title": "التصدير",
        "export_desc": "نزّل بياناتك لسجلاتك أو لمشاركتها مع طبيبك.",
        "baseline_setting": "درجة حرارة الجسم الأساسية (°م)",
        "use_temp_baseline": "استخدم هذه القيمة لتنبيهات المراقبة",
        "contacts": "جهات اتصال الطوارئ",
        "primary_phone": "الهاتف الأساسي",
        "secondary_phone": "هاتف إضافي",
        "home_city": "المدينة الأساسية",
        "timezone": "المنطقة الزمنية (اختياري)",
        "save_settings": "حفظ الإعدادات",
        "saved": "تم الحفظ",
        "weather_fail": "فشل جلب الطقس",
        "ai_unavailable": "الخدمة الذكية غير متاحة. أضف DEEPSEEK_API_KEY (و OPENAI_API_KEY اختياريًا) في الأسرار.",
        "journal_hint": "استخدم المُسجّل السريع أو النص الحر. كما تُحفظ التنبيهات والخطط هنا.",
        "daily_logger": "المُسجّل اليومي السريع",
        "mood": "المزاج",
        "hydration": "💧 شرب الماء (أكواب)",
        "sleep": "🛌 النوم (ساعات)",
        "fatigue": "التعب",
        "free_note": "ملاحظة حرة (اختياري)",
        "emergency": "الطوارئ",
        "triggers_today": "المحفزات اليوم",
        "symptoms_today": "الأعراض اليوم",
        "instant_plan_title": "خطة فورية",
        "do_now": "افعل الآن",
        "plan_later": "خطط لاحقًا",
        "watch_for": "انتبه إلى",
        "trigger": "محفز",
        "symptom": "عرض",
        "start_monitoring": "▶️ بدء المراقبة",
        "pause": "⏸️ إيقاف مؤقت",
        "refresh_weather": "🔄 تحديث الطقس",
        "temperature_trend": "📈 اتجاه درجة الحرارة",
        "filter_by_type": "تصفية حسب النوع",
        "newer": "⬅️ الأحدث",
        "older": "الأقدم ➡️",
        "reset_chat": "🧹 إعادة تعيين المحادثة",
        "thinking": "جاري التفكير...",
        "ask_me_anything": "اسألني أي شيء...",
    }
}

TRIGGERS_EN = [
    "Exercise", "Direct sun exposure", "Sauna/Hot bath", "Spicy food", "Hot drinks",
    "Stress/Anxiety", "Fever/Illness", "Hormonal cycle", "Tight clothing", "Poor sleep",
    "Dehydration", "Crowded place", "Cooking heat", "Car without AC", "Outdoor work",
    "Long prayer standing"
]
TRIGGERS_AR = [
    "رياضة","تعرض مباشر للشمس","ساونا/حمام ساخن","طعام حار","مشروبات ساخنة",
    "توتر/قلق","حمّى/مرض","الدورة الشهرية","ملابس ضيقة","نوم غير كاف",
    "جفاف","ازدحام","حرارة المطبخ","سيارة بدون تكييف","عمل خارجي","وقوف طويل في الصلاة"
]
SYMPTOMS_EN = [
    "Blurred vision","Fatigue","Weakness","Numbness","Coordination issues",
    "Spasticity","Heat intolerance","Cognitive fog","Dizziness","Headache","Pain","Tingling"
]
SYMPTOMS_AR = [
    "تشوش الرؤية","إرهاق","ضعف","خدر","مشاكل توازن","تشنج","حساسية للحرارة",
    "تشوش إدراكي","دوخة","صداع","ألم","وخز"
]

# ================== SIDEBAR / NAV ==================
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/a361daf5636e2f1dcbfb457b52691198cea1e95f/logo.png"
st.sidebar.image(logo_url, use_container_width=True)

prev_lang = st.session_state.get("_prev_lang", None)
app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English", "Arabic"], index=0)
T = TEXTS[app_language]
st.session_state["_prev_lang"] = app_language

PAGE_IDS = ["about", "monitor", "planner", "journal", "assistant", "exports", "settings"]
PAGE_LABELS = {
    "about": T["about_title"], "monitor": T["temp_monitor"], "planner": T["planner"],
    "journal": T["journal"], "assistant": T["assistant"], "exports": T["exports"], "settings": T["settings"]
}
st.session_state.setdefault("current_page", "about")
if "nav_radio" not in st.session_state:
    st.session_state["nav_radio"] = st.session_state["current_page"]
if prev_lang is not None and prev_lang != app_language:
    if st.session_state.get("current_page") in PAGE_IDS:
        st.session_state["nav_radio"] = st.session_state["current_page"]

page_id = st.sidebar.radio("📑 " + ("Navigate" if app_language=="English" else "التنقل"),
                           options=PAGE_IDS,
                           format_func=lambda pid: PAGE_LABELS[pid],
                           key="nav_radio")
st.session_state["current_page"] = page_id

# --- Auth box ---
exp_title = (f"{T['login_title']} — {st.session_state['user']}" if "user" in st.session_state else T["login_title"])
with st.sidebar.expander(exp_title, expanded=True):
    if "user" not in st.session_state:
        username = st.text_input(T["username"], key="sb_user")
        password = st.text_input(T["password"], type="password", key="sb_pass")
        col1, col2 = st.columns(2)
        with col1:
            if st.button(T["login"], key="sb_login_btn"):
                c = get_conn().cursor()
                c.execute("SELECT password FROM users WHERE username=?", (username,))
                row = c.fetchone()
                if row:
                    hashed = row[0]
                    if _check_pw(password, hashed):
                        st.session_state["user"] = username
                        st.success(T["logged_in"]); st.rerun()
                    else:
                        # Legacy plaintext migration: allow login if stored plaintext equals provided password
                        if password == hashed:
                            c.execute("UPDATE users SET password=? WHERE username=?", (_hash_pw(password), username))
                            get_conn().commit()
                            st.session_state["user"] = username
                            st.success(T["logged_in"]); st.rerun()
                        else:
                            st.error(T["bad_creds"])
                else:
                    st.error(T["bad_creds"])
        with col2:
            if st.button(T["register"], key="sb_reg_btn"):
                try:
                    c = get_conn().cursor()
                    c.execute("INSERT INTO users VALUES (?,?)", (username, _hash_pw(password)))
                    get_conn().commit()
                    st.success(T["account_created"])
                except Exception:
                    st.error(T["user_exists"])
    else:
        st.write(f"**{st.session_state['user']}**")
        if st.button(T["logout"], key="sb_logout_btn"):
            # Clear user data
            for k in ["user", "primary_phone", "secondary_phone", "current_city"]:
                st.session_state.pop(k, None)
            st.success(T["logged_out"]); st.rerun()

# ================== PAGES ==================

def render_about_page(lang="English"):
    st.markdown(f"## 👋 {'Welcome to' if lang=='English' else 'أهلاً بك في'} **Tanzim MS**")
    if lang == "English":
        st.markdown("""
- With MS, even a ~0.5°C rise can trigger symptoms (Uhthoff's phenomenon).
- Tanzim compares **core + skin** temps to **your baseline** and pairs them with **feels‑like & humidity** for GCC realities.
- Pages you'll use:
  - **Monitor**: live readings vs baseline + alerts
  - **Planner**: safest 2‑hour windows next 48h
  - **Journal**: quick logs & export for clinician
  - **AI Companion**: personal, culturally aware guidance

> **Safety**: This app offers general wellness guidance only. For severe/unusual symptoms, seek urgent medical care.
""")
    else:
        st.markdown("""
- مع التصلب المتعدد، حتى ارتفاع ≈ 0.5°م قد يسبب أعراضًا (ظاهرة أوتهوف).
- يقارن تنظيم إم إس حرارة **الأساسية + الطرفية** بخطك **الأساسي** ويضيف **الإحساس الحراري والرطوبة** بما يناسب الخليج.
- الصفحات:
  - **المراقبة**: قراءات مباشرة مقارنة بالأساس + تنبيهات
  - **المخطط**: أفضل فترات لساعتين خلال 48 ساعة
  - **اليوميات**: تسجيل سريع وتصدير للطبيب
  - **الرفيق الذكي**: إرشاد شخصي ملائم ثقافيًا

> **تنبيه**: يقدم التطبيق توجيهات عامة. عند أعراض شديدة/غير معتادة اذهب للرعاية الطبية فورًا.
""")

def render_planner():
    st.title("🗺️ " + T["planner"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return
    city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0,
                        key="planner_city",
                        format_func=lambda code: city_label(code, app_language))
    weather, err = get_weather(city)
    if not weather:
        st.error(f"{T['weather_fail']}: {err or '—'}"); return

    def best_windows_from_forecast(forecast, window_hours=2, top_k=12, max_feels_like=35.0, max_humidity=65, avoid_hours=(10,16)):
        slots = []
        for it in forecast[:16]:
            t = it["time"]; hour = int(t[11:13])
            if avoid_hours[0] <= hour < avoid_hours[1]: continue
            if it["feels_like"] <= max_feels_like and it["humidity"] <= max_humidity:
                slots.append(it)
        cand = []
        for i in range(len(slots)):
            group = [slots[i]]
            if i+1 < len(slots):
                t1, t2 = slots[i]["time"], slots[i+1]["time"]
                if t1[:10] == t2[:10] and (int(t2[11:13]) - int(t1[11:13]) == 3):
                    group.append(slots[i+1])
            avg_feels = round(sum(g["feels_like"] for g in group)/len(group), 1)
            avg_hum = int(sum(g["humidity"] for g in group)/len(group))
            start_dt = datetime.strptime(group[0]["time"][:16], "%Y-%m-%d %H:%M")
            end_dt = (datetime.strptime(group[-1]["time"][:16], "%Y-%m-%d %H:%M") + timedelta(hours=3)) if len(group)>1 else (start_dt + timedelta(hours=3))
            cand.append({ "start_dt": start_dt, "end_dt": end_dt, "avg_feels": avg_feels, "avg_hum": avg_hum })
        cand.sort(key=lambda x: x["start_dt"])
        return cand[:top_k]

    tabs = st.tabs(["✅ " + ("Best windows" if app_language=="English" else "أفضل الأوقات"),
                    "🤔 " + ("What‑if" if app_language=="English" else "ماذا لو"),
                    "📍 " + ("Places" if app_language=="English" else "الأماكن")])

    # Tab 1: Best windows
    with tabs[0]:
        st.caption("We scanned the next 48h for cooler 2‑hour windows." if app_language=="English"
                   else "فحصنا الـ48 ساعة القادمة لإيجاد فترات أبرد لساعتين.")
        windows = best_windows_from_forecast(weather["forecast"])
        if not windows:
            st.info("No optimal windows; try early morning or after sunset." if app_language=="English"
                    else "لا توجد فترات مثالية؛ جرّب الصباح الباكر أو بعد الغروب.")
        else:
            rows = [{
                "Date": w["start_dt"].strftime("%a %d %b"),
                "Start": w["start_dt"].strftime("%H:%M"),
                "End": w["end_dt"].strftime("%H:%M"),
                "Feels-like (°C)": round(w["avg_feels"], 1),
                "Humidity (%)": int(w["avg_hum"]),
            } for w in windows]
            df = pd.DataFrame(rows)
            if app_language == "Arabic":
                df.columns = ["التاريخ","البداية","النهاية","الإحساس الحراري (°م)","الرطوبة (%)"]
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("##### " + ("Add a plan" if app_language=="English" else "أضف خطة"))
            options = [f"{r['Date']} • {r['Start']}–{r['End']} (≈{r[df.columns[3]]}{'°C' if app_language=='English' else '°م'}, {r[df.columns[4]]}%)" for r in rows]
            pick_label = st.selectbox(("Choose a slot" if app_language=="English" else "اختر فترة"), options, index=0, key="plan_pick")
            chosen = windows[options.index(pick_label)]
            acts = ["Walk", "Groceries", "Beach", "Errand"] if app_language=="English" else ["مشي","تسوق","شاطئ","مهمة"]
            act = st.selectbox(("Activity" if app_language=="English" else "النشاط"), acts, key="plan_act")
            other_act = st.text_input(("Other activity (optional)" if app_language=="English" else "نشاط آخر (اختياري)"), key="plan_act_other")
            final_act = other_act.strip() if other_act.strip() else act
            if st.button(("Add to Journal" if app_language=="English" else "أضف إلى اليوميات"), key="btn_add_plan"):
                entry = {
                    "type":"PLAN","at": utc_iso_now(),"city": city,
                    "start": chosen["start_dt"].strftime("%Y-%m-%d %H:%M"),
                    "end": chosen["end_dt"].strftime("%Y-%m-%d %H:%M"),
                    "activity": final_act, "feels_like": round(chosen["avg_feels"],1),
                    "humidity": int(chosen["avg_hum"])
                }
                insert_journal(st.session_state["user"], utc_iso_now(), entry)
                st.success("Saved" if app_language=="English" else "تم الحفظ")

    # Tab 2: What‑if
    with tabs[1]:
        st.caption("Try a plan now and get instant tips." if app_language=="English" else "جرّب خطة الآن واحصل على نصائح فورية.")
        col1, col2 = st.columns([2,1])
        with col1:
            activity_options = ["Light walk (20–30 min)", "Moderate exercise (45 min)", "Outdoor errand (30–60 min)", "Beach (60–90 min)"] \
                if app_language=="English" else ["مشي خفيف (20-30 دقيقة)", "تمرين متوسط (45 دقيقة)", "مهمة خارجية (30-60 دقيقة)", "شاطئ (60-90 دقيقة)"]
            what_act = st.selectbox(("Activity" if app_language=="English" else "النشاط"), activity_options, key="what_if_act")
            dur = st.slider(("Duration (minutes)" if app_language=="English" else "المدة (دقائق)"), 10, 120, 45, 5, key="what_if_dur")
            loc_opts = ["Outdoor","Indoor/AC"] if app_language=="English" else ["خارجي","داخلي/مكيف"]
            indoor = st.radio(("Location" if app_language=="English" else "الموقع"), loc_opts, horizontal=True, key="what_if_loc")
            other_notes = st.text_area(("Add your own notes (optional)" if app_language=="English" else "أضف ملاحظاتك (اختياري)"), height=80, key="what_if_notes")
        with col2:
            fl = weather["feels_like"]; hum = weather["humidity"]
            go_badge = ("🟢 Go" if (fl < 34 and hum < 60) else ("🟡 Caution" if (fl < 37 and hum < 70) else "🔴 Avoid now")) \
                       if app_language=="English" else ("🟢 اذهب" if (fl < 34 and hum < 60) else ("🟡 احترس" if (fl < 37 and hum < 70) else "🔴 تجنب الآن"))
            st.markdown(f"**{'Now' if app_language=='English' else 'الآن'}:** {go_badge} — feels‑like {round(fl,1)}°C, humidity {int(hum)}%")
            tips_now = []
            low = what_act.lower()
            if "walk" in low or "مشي" in low:
                tips_now += ["Shaded route","Carry cool water","Light clothing"] if app_language=="English" else ["مسار مظلل","احمل ماءً باردًا","ملابس خفيفة"]
            if "exercise" in low or "تمرين" in low:
                tips_now += ["Pre‑cool 15 min","Prefer indoor/AC","Electrolytes if >45 min"] if app_language=="English" else ["تبريد مسبق 15 دقيقة","افضل الداخلي/مكيف","إلكتروليتات إذا >45 دقيقة"]
            if "errand" in low or "مهمة" in low:
                tips_now += ["Park in shade","Shortest route","Pre‑cool car 5–10 min"] if app_language=="English" else ["اركن في الظل","أقصر طريق","تبريد السيارة مسبقًا 5‑10 دقائق"]
            if "beach" in low or "شاطئ" in low:
                tips_now += ["Umbrella & UV hat","Cooling towel","Rinse to cool"] if app_language=="English" else ["مظلة وقبعة UV","منشفة تبريد","اشطف للتبريد"]
            if fl >= 36: tips_now += ["Cooling scarf/bandana","Use a cooler window"] if app_language=="English" else ["وشاح تبريد","اختر وقتًا أبرد"]
            if hum >= 60: tips_now += ["Prefer AC over fan","Extra hydration"] if app_language=="English" else ["افضل التكييف على المروحة","ترطيب إضافي"]
            tips_now = list(dict.fromkeys(tips_now))[:8]
            st.markdown("**" + ("Tips" if app_language=="English" else "نصائح") + ":**")
            st.markdown("- " + "\n- ".join(tips_now) if tips_now else "—")
            if st.button(("Add plan" if app_language=="English" else "أضف خطة"), key="what_if_add_plan"):
                now_dxb = datetime.now(TZ_DUBAI)
                entry = {
                    "type":"PLAN","at": utc_iso_now(), "city": city,
                    "start": now_dxb.strftime("%Y-%m-%d %H:%M"),
                    "end": (now_dxb + timedelta(minutes=dur)).strftime("%Y-%m-%d %H:%M"),
                    "activity": what_act + (f" — {other_notes.strip()}" if other_notes.strip() else ""),
                    "feels_like": round(fl, 1), "humidity": int(hum),
                    "indoor": (indoor == ("Indoor/AC" if app_language=="English" else "داخلي/مكيف"))
                }
                insert_journal(st.session_state["user"], utc_iso_now(), entry)
                st.success(T["saved"])
            if (DEEPSEEK_API_KEY or OPENAI_API_KEY) and st.button(T["ask_ai_tips"], key="what_if_ai"):
                q = f"My plan: {what_act} for {dur} minutes. Location: {indoor}. Notes: {other_notes}. Current feels-like {round(fl,1)}°C, humidity {int(hum)}%."
                ans, _ = ai_response(q, app_language)
                st.info(ans if ans else (T["ai_unavailable"]))

    # Tab 3: Places
    with tabs[2]:
        st.caption("Check a specific place (beach/park) in your city." if app_language=="English" else "تحقق من مكان محدد (شاطئ/حديقة) في مدينتك.")
        place_q = st.text_input(("Place name" if app_language=="English" else "اسم المكان"), key="place_q")
        if place_q:
            place, lat, lon = geocode_place(place_q)
            pw = get_weather_by_coords(lat, lon) if (lat and lon) else None
            if pw:
                st.info(f"**{place}** — feels‑like {round(pw['feels_like'],1)}°C • humidity {int(pw['humidity'])}% • {pw['desc']}")
                better = "place" if pw["feels_like"] < weather["feels_like"] else "city"
                st.caption(f"{'Cooler now' if app_language=='English' else 'أبرد الآن'}: **{place if better=='place' else city}**")
                if st.button(("Plan here (next hour)" if app_language=="English" else "خطط هنا للساعة القادمة"), key="place_plan"):
                    now_dxb = datetime.now(TZ_DUBAI)
                    entry = {
                        "type":"PLAN","at": utc_iso_now(), "city": place,
                        "start": now_dxb.strftime("%Y-%m-%d %H:%M"),
                        "end": (now_dxb + timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M"),
                        "activity": "Visit" if app_language=="English" else "زيارة",
                        "feels_like": round(pw["feels_like"],1), "humidity": int(pw["humidity"])
                    }
                    insert_journal(st.session_state["user"], utc_iso_now(), entry)
                    st.success(T["saved"])
            else:
                st.warning(T["weather_fail"])
        st.caption(f"**{T['peak_heat']}:** " + ("; ".join(weather.get('peak_hours', [])) if weather.get('peak_hours') else "—"))

def render_monitor():
    st.title("☀️ " + T["risk_dashboard"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    tabs = st.tabs(["📡 " + ("Live Sensor Data" if app_language=="English" else "بيانات مباشرة"),
                    "🔬 " + ("Learn & Practice" if app_language=="English" else "تعلّم وتدرّب")])

    # Tab 1 — Live data
    with tabs[0]:
        with st.expander("🌡️ " + ("About the sensors" if app_language=="English" else "عن المستشعرات"), expanded=False):
            if app_language=="English":
                st.markdown("""
- **MAX30205**: skin/peripheral temperature (±0.1°C)
- **MLX90614**: infrared, estimates core/body (±0.5°C)
- **ESP8266**: sends readings to cloud
- **Feels‑like/humidity** via **OpenWeather**.
- **Baseline**: your normal temp (set in Settings).
""")
            else:
                st.markdown("""
- **MAX30205**: حرارة الجلد/الطرفية (±0.1°م)
- **MLX90614**: بالأشعة تحت الحمراء، تقدير الحرارة الأساسية (±0.5°م)
- **ESP8266**: يرسل القراءات للسحابة
- **الإحساس الحراري/الرطوبة** عبر OpenWeather.
- **خط الأساس**: حرارتك الطبيعية (اضبطها من الإعدادات).
""")

        colA, colB, colC, colD = st.columns([1.3,1.1,1,1.3])
        with colA:
            city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0,
                                key="monitor_city", format_func=lambda c: city_label(c, app_language))
        with colB:
            st.markdown("**🔌 Sensor Hub**" if app_language=="English" else "**🔌 محور المستشعرات**")
            st.caption("ESP8266 + MAX30205 + MLX90614")
        with colC:
            if st.button(("🔄 Connect to Sensors" if app_language=="English" else "🔄 الاتصال بالمستشعرات"), use_container_width=True, type="primary"):
                sample = fetch_latest_sensor_sample("esp8266-01")
                if sample:
                    msg = f"✅ Connected! Last: {sample['core']:.1f}°C core, {sample['peripheral']:.1f}°C peripheral" \
                          if app_language=="English" else f"✅ متصل! آخر قراءة: {sample['core']:.1f}°م أساسية، {sample['peripheral']:.1f}°م طرفية"
                    st.success(msg)
                    st.session_state["live_core_smoothed"] = [sample['core']]
                    st.session_state["live_periph_smoothed"] = [sample['peripheral']]
                    st.session_state["live_running"] = True
                else:
                    st.error("❌ No sensor data found. Check device and Supabase configuration." if app_language=="English"
                             else "❌ لا توجد بيانات مستشعر. تحقق من الجهاز وإعداد Supabase.")
        with colD:
            st.markdown(f"<div class='badge'>{'Baseline' if app_language=='English' else 'الأساس'}: <strong>{st.session_state.get('baseline', 37.0):.1f}°C</strong></div>", unsafe_allow_html=True)

        # Weather metrics
        weather, err = get_weather(city)
        col1, col2, col3, col4 = st.columns(4)
        sample = fetch_latest_sensor_sample("esp8266-01")
        if sample:
            with col1:
                delta = sample['core'] - st.session_state.get('baseline', 37.0)
                label = "Core Temperature" if app_language=="English" else "درجة الحرارة الأساسية"
                st.metric(label, f"{sample['core']:.1f}°C", f"{delta:+.1f}°C", delta_color="inverse" if delta>=0.5 else "normal")
            with col2:
                label = "Peripheral Temperature" if app_language=="English" else "درجة الحرارة الطرفية"
                st.metric(label, f"{sample['peripheral']:.1f}°C")
        else:
            with col1:
                st.info("🔌 No live sensor data" if app_language=="English" else "🔌 لا توجد بيانات مباشرة")
        with col3:
            st.metric(("Feels‑like" if app_language=="English" else "الإحساس الحراري"), f"{(weather or {}).get('feels_like','—')}°C" if weather else "—")
        with col4:
            st.metric(("Humidity" if app_language=="English" else "الرطوبة"), f"{(weather or {}).get('humidity','—')}%" if weather else "—")

        # Risk card
        if weather and sample:
            risk = compute_risk(weather["feels_like"], weather["humidity"], sample['core'], st.session_state.get('baseline', 37.0), [], [])
            st.markdown(f"""
            <div class="big-card" style="--left:{risk['color']}">
              <h3>{risk['icon']} <strong>{T['status']}: {risk['status']}</strong></h3>
              <p style="margin:6px 0 0 0">{risk['advice']}</p>
            </div>
            """, unsafe_allow_html=True)
            if (sample['core'] - st.session_state.get('baseline', 37.0)) >= 0.5:
                st.warning(
                    "⚠️ Temperature Alert: core is 0.5°C above baseline. Cool down and monitor symptoms.\n\nIf severe/unusual symptoms occur, seek urgent care."
                    if app_language=="English" else
                    "⚠️ تنبيه: الأساسية أعلى بـ 0.5°م من الأساس. تبرد وراقب الأعراض.\n\nإذا ظهرت أعراض شديدة/غير معتادة فاطلب رعاية عاجلة."
                )
        elif weather and not sample:
            st.info("Live sensor data not available; showing weather-based context." if app_language=="English"
                    else "لا توجد بيانات مستشعر؛ عرض سياق الطقس فقط.")
        else:
            st.error(f"{T['weather_fail']}: {err or '—'}")

        # Refresh weather
        if st.button(T["refresh_weather"], key="refresh_weather_btn"):
            get_weather.clear()  # clear cache
            st.rerun()

        # Health Event Logging
        st.markdown("---")
        st.subheader("📝 " + ( "Log Health Event" if app_language=="English" else "تسجيل حدث صحي"))
        with st.form("health_event_form", clear_on_submit=True):
            if sample:
                current_temp = sample['core']
                delta = current_temp - st.session_state.get('baseline', 37.0)
                st.info(
                    f"**Current:** Core {current_temp:.1f}°C | Δ {delta:+.1f}°C | Peripheral {sample['peripheral']:.1f}°C" if app_language=="English"
                    else f"**الحالي:** الأساسية {current_temp:.1f}°م | الفرق {delta:+.1f}°م | الطرفية {sample['peripheral']:.1f}°م"
                )
            trigger_opts = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
            symptom_opts = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
            colA, colB = st.columns(2)
            with colA:
                chosen_tr = st.multiselect(T["triggers_today"], trigger_opts)
                tr_other = st.text_input(f"{T['other']} ({T['trigger']})")
            with colB:
                chosen_sy = st.multiselect(T["symptoms_today"], symptom_opts)
                sy_other = st.text_input(f"{T['other']} ({T['symptom']})")
            event_description = st.text_area(T["notes"], height=80)
            all_triggers = chosen_tr + ([f"Other: {tr_other.strip()}"] if tr_other.strip() else [])
            all_symptoms = chosen_sy + ([f"Other: {sy_other.strip()}"] if sy_other.strip() else [])
            submitted = st.form_submit_button("💾 " + ( "Save to Journal" if app_language=="English" else "حفظ في اليوميات"))
            if submitted:
                entry = {
                    "type":"ALERT","at": utc_iso_now(),
                    "core_temp": round(sample['core'],1) if sample else None,
                    "peripheral_temp": round(sample['peripheral'],1) if sample else None,
                    "baseline": round(st.session_state.get('baseline', 37.0),1),
                    "reasons": all_triggers, "symptoms": all_symptoms, "note": event_description.strip(),
                    "city": city, "feels_like": (weather or {}).get("feels_like"), "humidity": (weather or {}).get("humidity")
                }
                insert_journal(st.session_state.get("user","guest"), utc_iso_now(), entry)
                st.success("✅ Saved!" if app_language=="English" else "✅ تم الحفظ!")

        # Trend
        st.markdown("---")
        st.subheader(T["temperature_trend"])
        c = get_conn().cursor()
        c.execute("""
            SELECT date, body_temp, peripheral_temp, weather_temp, feels_like, status
            FROM temps WHERE username=? ORDER BY date DESC LIMIT 50
        """, (st.session_state.get("user","guest"),))
        rows = c.fetchall()
        if rows:
            rows = rows[::-1]
            dates = [r[0] for r in rows]
            core = [r[1] for r in rows]; periph = [r[2] for r in rows]
            feels = [(r[4] if r[4] is not None else r[3]) for r in rows]
            fig, ax = plt.subplots(figsize=(10, 4))
            if app_language=="Arabic":
                lbl_core  = ar_shape("الأساسية")
                lbl_peri  = ar_shape("الطرفية")
                lbl_feels = ar_shape("الإحساس الحراري")
            else:
                lbl_core, lbl_peri, lbl_feels = "Core", "Peripheral", "Feels‑like"
            ax.plot(range(len(dates)), core,   marker='o', label=lbl_core,  linewidth=2)
            ax.plot(range(len(dates)), periph, marker='o', label=lbl_peri,  linewidth=1.8)
            ax.plot(range(len(dates)), feels,  marker='s', label=lbl_feels, linewidth=1.8)
            ax.set_xticks(range(len(dates)))
            ax.set_xticklabels([d[11:16] if len(d)>=16 else d for d in dates], rotation=45, fontsize=9)
            ax.set_ylabel("°C" if app_language=="English" else "°م", fontproperties=_AR_FONT)
            ax.legend(prop=_AR_FONT); ax.grid(True, alpha=0.3)
            if app_language=="Arabic":
                ax.set_title(ar_shape("الأساسية مقابل الطرفية مقابل الإحساس الحراري"), fontproperties=_AR_FONT, loc="center")
            else:
                ax.set_title("Core vs Peripheral vs Feels‑like")
            st.pyplot(fig)
        else:
            st.info("No temperature history to chart yet." if app_language=="English" else "لا يوجد سجل درجات لعرضه.")

    # Tab 2 — Learn & Practice (kept concise)
    with tabs[1]:
        st.info("🎯 Practice recognizing patterns and cooling strategies." if app_language=="English"
                else "🎯 تدرب على التعرف على الأنماط واستراتيجيات التبريد.")
        st.write("Try scenarios and see how solutions (cooling vest, AC, hydration) change core/feels‑like.")

def render_journal():
    st.title("📒 " + T["journal"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    st.caption(T["journal_hint"])
    st.markdown("### " + T["daily_logger"])
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        mood_options = ["🙂 Okay", "😌 Calm", "😕 Low", "😣 Stressed", "😴 Tired"] if app_language=="English" else ["🙂 بخير", "😌 هادئ", "😕 منخفض", "😣 متوتر", "😴 متعب"]
        mood = st.selectbox(T["mood"], mood_options)
    with col2:
        hydration = st.slider(T["hydration"], 0, 12, 6, key="hydration_slider")
    with col3:
        sleep = st.slider(T["sleep"], 0, 12, 7, key="sleep_slider")
    with col4:
        fatigue_options = [f"{i}/10" for i in range(0,11)]
        fatigue = st.selectbox(T["fatigue"], fatigue_options, index=4)

    trigger_options = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
    symptom_options = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
    chosen_tr = st.multiselect(("Triggers (optional)" if app_language=="English" else "المحفزات (اختياري)"), trigger_options)
    tr_other = st.text_input(f"{T['other']} ({T['trigger']})", "")
    chosen_sy = st.multiselect(("Symptoms (optional)" if app_language=="English" else "الأعراض (اختياري)"), symptom_options)
    sy_other = st.text_input(f"{T['other']} ({T['symptom']})", "")
    free_note = st.text_area(T["free_note"], height=100)

    if st.button(T["save_entry"], key="journal_save"):
        entry = {
            "type":"DAILY","at": utc_iso_now(),
            "mood": mood, "hydration_glasses": hydration, "sleep_hours": sleep, "fatigue": fatigue,
            "triggers": chosen_tr + ([f"Other: {tr_other.strip()}"] if tr_other.strip() else []),
            "symptoms": chosen_sy + ([f"Other: {sy_other.strip()}"] if sy_other.strip() else []),
            "note": free_note.strip()
        }
        insert_journal(st.session_state["user"], utc_iso_now(), entry)
        st.success("✅ " + T["saved"])

    st.markdown("---")
    c = get_conn().cursor()
    c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC", (st.session_state["user"],))
    rows = c.fetchall()
    if not rows:
        st.info("No journal entries yet." if app_language=="English" else "لا توجد مدخلات بعد.")
        return

    available_types = ["PLAN","ALERT","ALERT_AUTO","DAILY","NOTE"]
    type_filter = st.multiselect(T["filter_by_type"], options=available_types, default=available_types)
    page_size = 12
    st.session_state.setdefault("journal_offset", 0)
    start = st.session_state["journal_offset"]; end = start + 200
    chunk = rows[start:end]

    def render_entry_card(raw_entry_json):
        try: obj = json.loads(raw_entry_json)
        except Exception: obj = {"type":"NOTE","at": utc_iso_now(), "text": str(raw_entry_json)}
        t = obj.get("type","NOTE")
        when = obj.get("at", utc_iso_now())
        try:
            dt = datetime.fromisoformat(when.replace("Z","+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
        when_label = dt.astimezone(TZ_DUBAI).strftime("%Y-%m-%d %H:%M")
        if t == "PLAN":
            city = obj.get("city","—"); act = obj.get("activity","—")
            start_t = obj.get("start","—"); end_t = obj.get("end","—")
            fl = obj.get("feels_like"); hum = obj.get("humidity")
            meta = f"Feels‑like {round(fl,1)}°C • Humidity {int(hum)}%" if (fl is not None and hum is not None) else ""
            header = f"**{when_label}** — **Plan** ({city})" if app_language=="English" else f"**{when_label}** — **خطة** ({city})"
            body = (f"**Activity:** {act}\n\n**Time:** {start_t} → {end_t}\n\n{meta}") if app_language=="English" else (f"**النشاط:** {act}\n\n**الوقت:** {start_t} → {end_t}\n\n{meta}")
            icon = "🗓️"
        elif t in ("ALERT","ALERT_AUTO"):
            core = obj.get("core_temp") or obj.get("body_temp"); periph = obj.get("peripheral_temp"); base = obj.get("baseline")
            delta = (core - base) if (core is not None and base is not None) else None
            reasons = obj.get("reasons") or []; symptoms = obj.get("symptoms") or []
            header = f"**{when_label}** — **Heat alert**" if app_language=="English" else f"**{when_label}** — **تنبيه حراري**"
            lines = []
            if core is not None: lines.append(("**Core:** " if app_language=="English" else "**الأساسية:** ") + f"{core}°C")
            if periph is not None: lines.append(("**Peripheral:** " if app_language=="English" else "**الطرفية:** ") + f"{periph}°C")
            if base is not None: lines.append(("**Baseline:** " if app_language=="English" else "**الأساس:** ") + f"{base}°C")
            if delta is not None: lines.append(("**Δ from baseline:** " if app_language=="English" else "**الفرق عن الأساس:** ") + f"+{round(delta,1)}°C")
            if reasons: lines.append(("**Reasons:** " if app_language=="English" else "**الأسباب:** ") + ", ".join(map(str,reasons)))
            if symptoms: lines.append(("**Symptoms:** " if app_language=="English" else "**الأعراض:** ") + ", ".join(map(str,symptoms)))
            body = "\n\n".join(lines); icon = "🚨"
        elif t == "DAILY":
            mood = obj.get("mood","—"); hyd = obj.get("hydration_glasses","—")
            sleep = obj.get("sleep_hours","—"); fat = obj.get("fatigue","—")
            header = f"**{when_label}** — **Daily log**" if app_language=="English" else f"**{when_label}** — **مُسجّل يومي**"
            lines = [f"**Mood:** {mood}", f"**Hydration:** {hyd}", f"**Sleep:** {sleep}h", f"**Fatigue:** {fat}"] if app_language=="English" \
                else [f"**المزاج:** {mood}", f"**الترطيب:** {hyd}", f"**النوم:** {sleep}س", f"**التعب:** {fat}"]
            note = (obj.get("note") or "").strip()
            if note: lines.append(("**Note:** " if app_language=="English" else "**ملاحظة:** ") + note)
            body = "\n\n".join(lines); icon = "🧩"
        else:
            text = obj.get("text") or obj.get("note") or "—"
            header = f"**{when_label}** — **Note**" if app_language=="English" else f"**{when_label}** — **ملاحظة**"
            body = text; icon = "📝"
        return header, body, icon, t, obj, when_label

    parsed = []
    for dt_raw, raw_json in chunk:
        title, body, icon, t, obj, when_label = render_entry_card(raw_json)
        if t not in type_filter: continue
        try:
            dt = datetime.fromisoformat(dt_raw.replace("Z","+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
        day_key = dt.astimezone(TZ_DUBAI).strftime("%A, %d %B %Y")
        parsed.append((day_key, title, body, icon, obj, raw_json))
    current_day = None; shown = 0
    for day, title, body, icon, obj, raw_json in parsed:
        if shown >= 12: break
        if day != current_day:
            st.markdown(f"## {day}")
            current_day = day
        st.markdown(f"""
        <div class="big-card" style="--left:#94a3b8;margin-bottom:12px;">
          <h3 style="margin:0">{icon} {title}</h3>
          <div style="margin-top:6px">{body}</div>
        </div>
        """, unsafe_allow_html=True)
        shown += 1

    colp1, colp2, colp3 = st.columns([1,1,4])
    with colp1:
        if st.session_state["journal_offset"] > 0:
            if st.button(T["newer"]):
                st.session_state["journal_offset"] = max(0, st.session_state["journal_offset"] - 12); st.rerun()
    with colp2:
        if (start + shown) < len(rows):
            if st.button(T["older"]):
                st.session_state["journal_offset"] += 12; st.rerun()

def render_assistant():
    st.title("🤝 " + T["assistant_title"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    st.caption(T["assistant_hint"])
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("ai_provider_last", None)
    st.session_state.setdefault("ai_last_error", None)
    st.session_state.setdefault("ai_last_finish_reason", None)

    # Show history
    for m in st.session_state["chat_history"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    prompt = st.chat_input(T["ask_me_anything"])
    if prompt:
        with st.chat_message("user"): st.markdown(prompt)
        st.session_state["chat_history"].append({"role":"user","content":prompt})

        # Ask for city once if unknown
        city_code = resolve_city_for_chat(prompt)
        if city_code is None and not st.session_state.get("_asked_city_once"):
            st.session_state["_asked_city_once"] = True
            with st.chat_message("assistant"):
                st.info("I don’t know your city yet. Pick one to tailor advice:" if app_language=="English"
                        else "لا أعرف مدينتك بعد. اختر مدينة لتخصيص الإرشاد:")
                pick = st.selectbox("📍 City", GCC_CITIES, index=0, key="assistant_city_pick",
                                    format_func=lambda c: city_label(c, app_language))
                colx, coly = st.columns([1,2])
                with colx:
                    if st.button("Use this city" if app_language=="English" else "استخدام هذه المدينة", key="use_city_btn"):
                        st.session_state["current_city"] = pick
                        st.rerun()

        with st.chat_message("assistant"):
            placeholder = st.empty(); placeholder.markdown("💭 " + T["thinking"])
            text, err = ai_chat(prompt, app_language)
            if err:
                fallback = get_fallback_response(prompt, app_language)
                placeholder.markdown(fallback)
                st.session_state["chat_history"].append({"role":"assistant","content":fallback})
            else:
                placeholder.markdown(text)
                st.session_state["chat_history"].append({"role":"assistant","content":text})

    # Status caption
    bits = []
    prov = st.session_state.get("ai_provider_last")
    if prov:
        bits.append(("✅ " if not st.session_state.get("ai_last_error") else "⚠️ ") + f"Provider: {prov}")
    err = st.session_state.get("ai_last_error")
    if err: bits.append(f"Last error: {err}")
    fin = st.session_state.get("ai_last_finish_reason")
    if fin: bits.append(f"finish_reason: {fin}")
    if bits: st.caption(" • ".join(bits))

    st.markdown("---")
    col1, col2 = st.columns([1,5])
    with col1:
        if st.button(T["reset_chat"], key="reset_chat_btn"):
            for k in ["chat_history","ai_last_error","ai_provider_last","ai_last_finish_reason","_asked_city_once"]:
                st.session_state.pop(k, None)
            st.rerun()
    with col2:
        disclaimer = ("This chat provides general wellness information only. Always consult your healthcare provider for medical advice."
                      if app_language=="English" else "هذه المحادثة تقدم معلومات عامة. استشر مقدم الرعاية الصحية دائمًا.")
        st.caption(disclaimer)

def render_exports():
    st.title("📦 " + T["export_title"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return
    st.caption(T["export_desc"])
    df_t = fetch_temps_df(st.session_state["user"])
    df_j = fetch_journal_df(st.session_state["user"])
    st.subheader("Preview — Temps" if app_language=="English" else "معاينة — درجات الحرارة")
    st.dataframe(df_t.tail(20), use_container_width=True)
    st.subheader("Preview — Journal" if app_language=="English" else "معاينة — اليوميات")
    st.dataframe(df_j.tail(20), use_container_width=True)
    blob, mime = build_export_excel_or_zip(st.session_state["user"])
    st.download_button(label=T["export_excel"],
                       data=blob,
                       file_name=f"raha_ms_{st.session_state['user']}.xlsx" if mime.endswith("sheet") else f"raha_ms_{st.session_state['user']}.zip",
                       mime=mime, use_container_width=True)
    st.markdown("— or download raw CSVs —" if app_language=="English" else "— أو حمل ملفات CSV خام —")
    st.download_button("Temps.csv", data=df_t.to_csv(index=False).encode("utf-8"), file_name="Temps.csv", mime="text/csv", use_container_width=True)
    st.download_button("Journal.csv", data=df_j.to_csv(index=False).encode("utf-8"), file_name="Journal.csv", mime="text/csv", use_container_width=True)

def render_settings():
    st.title("⚙️ " + T["settings"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    # Load emergency contacts if missing
    def load_emergency_contacts(username):
        try:
            c = get_conn().cursor()
            c.execute("SELECT primary_phone, secondary_phone FROM emergency_contacts WHERE username=?", (username,))
            row = c.fetchone()
            if row: return row[0] or "", row[1] or ""
            return "", ""
        except Exception:
            return "", ""

    def save_emergency_contacts(username, p1, p2):
        conn = get_conn(); c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO emergency_contacts (username, primary_phone, secondary_phone, updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(username) DO UPDATE SET
                  primary_phone=excluded.primary_phone,
                  secondary_phone=excluded.secondary_phone,
                  updated_at=excluded.updated_at
            """, (username, tel_href(p1), tel_href(p2), utc_iso_now()))
            conn.commit()
            return True, None
        except Exception as e:
            return False, str(e)

    if "primary_phone" not in st.session_state or "secondary_phone" not in st.session_state:
        p1, p2 = load_emergency_contacts(st.session_state["user"])
        st.session_state["primary_phone"], st.session_state["secondary_phone"] = p1, p2

    st.subheader(T["baseline_setting"])
    st.session_state.setdefault("baseline", 37.0)
    st.session_state.setdefault("use_temp_baseline", True)
    base = st.number_input(T["baseline_setting"], 35.5, 38.5, float(st.session_state["baseline"]), step=0.1, key="settings_baseline")
    useb = st.checkbox(T["use_temp_baseline"], value=st.session_state["use_temp_baseline"], key="settings_useb")

    st.subheader(T["contacts"])
    p1 = st.text_input(T["primary_phone"], st.session_state["primary_phone"], key="settings_p1")
    p2 = st.text_input(T["secondary_phone"], st.session_state["secondary_phone"], key="settings_p2")

    st.subheader(T["home_city"])
    prefs = load_user_prefs(st.session_state["user"])
    home_city = st.selectbox(T["home_city"], GCC_CITIES, index=0,
                             format_func=lambda c: city_label(c, app_language),
                             key="settings_home_city") if not prefs.get("home_city") else \
                             st.selectbox(T["home_city"], GCC_CITIES, index=GCC_CITIES.index(prefs["home_city"]) if prefs["home_city"] in GCC_CITIES else 0,
                                          format_func=lambda c: city_label(c, app_language), key="settings_home_city")
    tz = st.text_input(T["timezone"], prefs.get("timezone") or "", key="settings_tz")

    if st.button(T["save_settings"], key="settings_save_btn"):
        st.session_state["baseline"] = float(base)
        st.session_state["use_temp_baseline"] = bool(useb)
        st.session_state["primary_phone"] = (p1 or "").strip()
        st.session_state["secondary_phone"] = (p2 or "").strip()

        ok, err = save_emergency_contacts(st.session_state["user"], p1, p2)
        save_user_prefs(st.session_state["user"], home_city=home_city, timezone=tz, language=app_language)
        if ok:
            st.success("✅ " + T["saved"])
        else:
            st.error(f"Failed to save contacts: {err}")

    st.markdown("---")
    if st.button(T["logout"], type="secondary", key="settings_logout"):
        for k in ["user", "primary_phone", "secondary_phone", "current_city"]:
            st.session_state.pop(k, None)
        st.success(T["logged_out"]); st.rerun()

# ================== ROUTER ==================
if page_id == "about":
    render_about_page(app_language)
elif page_id == "monitor":
    render_monitor()
elif page_id == "planner":
    render_planner()
elif page_id == "journal":
    render_journal()
elif page_id == "assistant":
    render_assistant()
elif page_id == "exports":
    render_exports()
elif page_id == "settings":
    render_settings()

# ================== EMERGENCY IN SIDEBAR ==================
with st.sidebar.expander("📞 " + T["emergency"], expanded=False):
    if "user" in st.session_state:
        def _load_contacts(u):
            try:
                c = get_conn().cursor()
                c.execute("SELECT primary_phone, secondary_phone FROM emergency_contacts WHERE username=?", (u,))
                row = c.fetchone(); return (row[0] or "", row[1] or "") if row else ("","")
            except Exception:
                return "",""
        if "primary_phone" not in st.session_state or "secondary_phone" not in st.session_state:
            p1, p2 = _load_contacts(st.session_state["user"])
            st.session_state["primary_phone"], st.session_state["secondary_phone"] = p1, p2
        if st.session_state["primary_phone"]:
            href = tel_href(st.session_state["primary_phone"])
            st.markdown(f"**{'Primary' if app_language=='English' else 'الأساسي'}:** [{st.session_state['primary_phone']}](tel:{href})")
        if st.session_state["secondary_phone"]:
            href = tel_href(st.session_state["secondary_phone"])
            st.markdown(f"**{'Secondary' if app_language=='English' else 'إضافي'}:** [{st.session_state['secondary_phone']}](tel:{href})")
        if not (st.session_state["primary_phone"] or st.session_state["secondary_phone"]):
            st.caption("Set numbers in Settings." if app_language=="English" else "أضف الأرقام من الإعدادات.")
    else:
        st.caption("Login to view quick‑dial contacts." if app_language=="English" else "سجّل الدخول لعرض جهات الاتصال.")
