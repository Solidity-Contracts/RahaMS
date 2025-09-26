import streamlit as st
import sqlite3, json, requests, random, time, zipfile, io
import matplotlib.pyplot as plt
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
from datetime import datetime as _dt
import json

# ================== CONFIG ==================
st.set_page_config(page_title="Raha MS", page_icon="🌡️", layout="wide")
TZ_DUBAI = ZoneInfo("Asia/Dubai")

# Secrets (fail gracefully if missing)
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")

# OpenAI (optional)
try:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    client = None

# GCC quick picks
GCC_CITIES = [
    "Abu Dhabi,AE", "Dubai,AE", "Sharjah,AE",
    "Doha,QA", "Al Rayyan,QA",
    "Kuwait City,KW",
    "Manama,BH",
    "Riyadh,SA", "Jeddah,SA", "Dammam,SA",
    "Muscat,OM"
]

# ===== Live/Alert config =====
SIM_INTERVAL_SEC = 60      # default sensor/sample update (sec)
DB_WRITE_EVERY_N = 3
ALERT_DELTA_C = 0.5
ALERT_CONFIRM = 2
ALERT_COOLDOWN_SEC = 300
SMOOTH_WINDOW = 3

# ================== I18N ==================
TEXTS = {
    "English": {
        "about_title": "About Raha MS",
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
        "export_desc": "Download your data for your own records or to share with your clinician.",

        "baseline_setting": "Baseline body temperature (°C)",
        "use_temp_baseline": "Use this baseline for monitoring alerts",
        "contacts": "Emergency Contacts",
        "primary_phone": "Primary phone",
        "secondary_phone": "Secondary phone",
        "save_settings": "Save settings",
        "saved": "Saved",
        "weather_fail": "Weather lookup failed",
        "ai_unavailable": "AI is unavailable. Set OPENAI_API_KEY in secrets.",
        "journal_hint": "Use the quick logger or free text. Reasons from Monitor and plans from Planner also save here.",

        "daily_logger": "Daily quick logger",
        "mood": "Mood",
        "hydration": "Hydration (glasses)",
        "sleep": "Sleep (hours)",
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
        "symptom":"Symptom",
        
        # NEW ADDITIONS
        "start_monitoring": "▶️ Start monitoring",
        "pause": "⏸️ Pause",
        "refresh_weather": "🔄 Refresh weather now",
        "temperature_trend": "📈 Temperature Trend",
        "filter_by_type": "Filter by type",
        "newer": "⬅️ Newer",
        "older": "Older ➡️",
        "reset_chat": "🧹 Reset chat",
        "thinking": "Thinking...",
        "ask_me_anything": "Ask me anything...",
        
        # Planner specific
        "choose_slot": "Choose a slot",
        "plan": "Plan",
        "activity": "Activity",
        "duration": "Duration (minutes)",
        "location": "Location",
        "add_plan": "Add this as a plan",
        "planned_saved": "Planned & saved",
        "place_name": "Place name (e.g., Saadiyat Beach)",
        "plan_here": "Plan here for the next hour",
        "best_windows": "Best windows",
        "what_if": "What-if",
        "places": "Places",
    },
    "Arabic": {
        "about_title": "عن تطبيق راحة إم إس",
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
        "use_temp_baseline": "استخدام هذه القيمة لتنبيهات المراقبة",
        "contacts": "جهات اتصال الطوارئ",
        "primary_phone": "الهاتف الأساسي",
        "secondary_phone": "هاتف إضافي",
        "save_settings": "حفظ الإعدادات",
        "saved": "تم الحفظ",
        "weather_fail": "فشل جلب الطقس",
        "ai_unavailable": "الخدمة الذكية غير متاحة. أضف مفتاح OPENAI_API_KEY.",
        "journal_hint": "استخدم المُسجّل السريع أو النص الحر. كما تُحفظ الأسباب من المراقبة والخطط من المخطط هنا.",

        "daily_logger": "المُسجّل اليومي السريع",
        "mood": "المزاج",
        "hydration": "شرب الماء (أكواب)",
        "sleep": "النوم (ساعات)",
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
        "symptom":"الأعراض",
        
        # NEW ARABIC ADDITIONS
        "start_monitoring": "▶️ بدء المراقبة",
        "pause": "⏸️ إيقاف مؤقت",
        "refresh_weather": "🔄 تحديث الطقس الآن",
        "temperature_trend": "📈 اتجاه درجة الحرارة",
        "filter_by_type": "تصفية حسب النوع",
        "newer": "⬅️ الأحدث",
        "older": "الأقدم ➡️",
        "reset_chat": "🧹 إعادة تعيين المحادثة",
        "thinking": "جاري التفكير...",
        "ask_me_anything": "اسألني أي شيء...",
        
        # Planner specific Arabic
        "choose_slot": "اختر فترة",
        "plan": "خطة",
        "activity": "النشاط",
        "duration": "المدة (دقائق)",
        "location": "الموقع",
        "add_plan": "أضف هذه كخطة",
        "planned_saved": "تم التخطيط والحفظ",
        "place_name": "اسم المكان (مثال: شاطئ السعديات)",
        "plan_here": "خطط هنا للساعة القادمة",
        "best_windows": "أفضل الأوقات",
        "what_if": "ماذا لو",
        "places": "الأماكن",
    }
}

TRIGGERS_EN = [
    "Exercise", "Direct sun exposure", "Sauna/Hot bath", "Spicy food",
    "Hot drinks", "Stress/Anxiety", "Fever/Illness", "Hormonal cycle",
    "Tight clothing", "Poor sleep", "Dehydration", "Crowded place",
    "Cooking heat", "Car without AC", "Outdoor work", "Long prayer standing"
]
TRIGGERS_AR = [
    "رياضة", "تعرض مباشر للشمس", "ساونا/حمام ساخن", "طعام حار",
    "مشروبات ساخنة", "توتر/قلق", "حمّى/مرض", "الدورة الشهرية",
    "ملابس ضيقة", "نوم غير كاف", "جفاف", "ازدحام",
    "حرارة المطبخ", "سيارة بدون تكييف", "عمل خارجي", "وقوف طويل في الصلاة"
]

SYMPTOMS_EN = [
    "Blurred vision", "Fatigue", "Weakness", "Numbness",
    "Coordination issues", "Spasticity", "Heat intolerance",
    "Cognitive fog", "Dizziness", "Headache", "Pain", "Tingling"
]
SYMPTOMS_AR = [
    "تشوش الرؤية", "إرهاق", "ضعف", "خدر",
    "مشاكل توازن", "تشنج", "حساسية للحرارة",
    "تشوش إدراكي", "دوخة", "صداع", "ألم", "وخز"
]

# ================== STYLES ==================
ACCESSIBLE_CSS = """
<style>
html, body, [class*="css"]  { font-size: 18px; }
.big-card {
    background:#fff;
    padding:18px;
    border-radius:14px;
    border-left:10px solid var(--left);
    box-shadow:0 2px 8px rgba(0,0,0,0.06);
    color: #000000 !important; /* Force black text for better visibility */
    border: 1px solid #e0e0e0;
}
.big-card h3, .big-card div {
    color: #000000 !important; /* Force black text for all content */
}
.badge {
    display:inline-block;
    padding:6px 10px;
    border-radius:999px;
    border:1px solid rgba(0,0,0,0.1);
    margin-right:6px;
    color: #000000 !important; /* Force black text in badges */
}
.small {opacity:0.75;font-size:14px;}
h3 { margin-top: 0.2rem; color: #000000 !important; }
.stButton>button { padding: 0.6rem 1.1rem; font-weight: 600; }
.fab-call {
  position: fixed; right: 18px; bottom: 18px; z-index: 9999;
  background: #ef4444; color: white; border-radius: 9999px;
  padding: 14px 18px; font-weight: 700; box-shadow:0 8px 24px rgba(0,0,0,0.18); text-decoration: none;
}
.fab-call:hover { background:#dc2626; text-decoration:none; }
@media (min-width: 992px) { .fab-call { padding: 10px 14px; font-weight: 600; } }

/* Dark mode support for cards */
@media (prefers-color-scheme: dark) {
    .big-card {
        background: #f8f9fa !important; /* Light gray background in dark mode */
        color: #000000 !important; /* Keep black text */
        border: 1px solid #495057;
    }
    .big-card h3, .big-card div {
        color: #000000 !important; /* Keep black text in dark mode */
    }
}

/* RTL Support */
[dir="rtl"] .stSlider > div:first-child {
    direction: ltr;
}
[dir="rtl"] .stSlider label {
    text-align: right;
    direction: rtl;
}
[dir="rtl"] .stSelectbox label,
[dir="rtl"] .stTextInput label,
[dir="rtl"] .stTextArea label {
    text-align: right;
    direction: rtl;
}
[dir="rtl"] .stRadio > label {
    direction: rtl;
    text-align: right;
}
[dir="rtl"] .stMultiSelect label {
    text-align: right;
    direction: rtl;
}

/* Icons for sliders */
.slider-with-icon {
    display: flex;
    align-items: center;
    gap: 10px;
}
.slider-icon {
    font-size: 24px;
    min-width: 30px;
}

/* Ensure text visibility in all modes */
[data-testid="stAppViewContainer"] {
    color: #000000;
}
.stMarkdown {
    color: #000000 !important;
}
</style>
"""
st.markdown(ACCESSIBLE_CSS, unsafe_allow_html=True)

# ================== DB ==================
@st.cache_resource
def get_conn():
    return sqlite3.connect("raha_ms.db", check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY,
        password TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS temps(
        username TEXT,
        date TEXT,
        body_temp REAL,
        peripheral_temp REAL,
        weather_temp REAL,
        feels_like REAL,
        humidity REAL,
        status TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS journal(
        username TEXT,
        date TEXT,
        entry TEXT
    )""")
    conn.commit()

def migrate_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(temps)")
    cols = [r[1] for r in c.fetchall()]
    if "peripheral_temp" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN peripheral_temp REAL")
    if "feels_like" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN feels_like REAL")
    if "humidity" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN humidity REAL")
    conn.commit()

init_db()
migrate_db()

def insert_temp_row(u, dt, body, peripheral, wtemp, feels, hum, status):
    c = get_conn().cursor()
    c.execute("""
      INSERT INTO temps (username, date, body_temp, peripheral_temp, weather_temp, feels_like, humidity, status)
      VALUES (?,?,?,?,?,?,?,?)
    """, (u, dt, body, peripheral, wtemp, feels, hum, status))
    get_conn().commit()

def insert_journal(u, dt, entry_obj):
    c = get_conn().cursor()
    c.execute("INSERT INTO journal VALUES (?,?,?)", (u, dt, json.dumps(entry_obj)))
    get_conn().commit()

def fetch_temps_df(user):
    c = get_conn().cursor()
    c.execute("""
        SELECT date, body_temp, peripheral_temp, weather_temp, feels_like, humidity, status
        FROM temps
        WHERE username=?
        ORDER BY date ASC
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
    """Return (bytes, mime) for Excel if engine available, else a ZIP of CSVs."""
    temps = fetch_temps_df(user)
    journal = fetch_journal_df(user)

    output = BytesIO()
    engine = None
    try:
        import xlsxwriter  # noqa: F401
        engine = "xlsxwriter"
    except Exception:
        try:
            import openpyxl  # noqa: F401
            engine = "openpyxl"
        except Exception:
            engine = None

    if engine:
        with pd.ExcelWriter(output, engine=engine) as writer:
            temps.to_excel(writer, index=False, sheet_name="Temps")
            journal.to_excel(writer, index=False, sheet_name="Journal")
        output.seek(0)
        return output.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # Fallback: ZIP with CSVs
    memzip = BytesIO()
    with zipfile.ZipFile(memzip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        t_csv = temps.to_csv(index=False).encode("utf-8")
        j_csv = journal.to_csv(index=False).encode("utf-8")
        zf.writestr("Temps.csv", t_csv)
        zf.writestr("Journal.csv", j_csv)
    memzip.seek(0)
    return memzip.read(), "application/zip"

def utc_iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def dubai_now_str():
    return datetime.now(TZ_DUBAI).strftime("%Y-%m-%d %H:%M")

# ================== WEATHER & GEO ==================
@st.cache_data(ttl=600)
def get_weather(city="Abu Dhabi,AE"):
    if not OPENWEATHER_API_KEY:
        return None, "Missing OPENWEATHER_API_KEY"
    try:
        base = "https://api.openweathermap.org/data/2.5/"

        params_now = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "en"}
        r_now = requests.get(base + "weather", params=params_now, timeout=6)
        r_now.raise_for_status()
        jn = r_now.json()
        temp  = float(jn["main"]["temp"])
        feels = float(jn["main"]["feels_like"])
        hum   = float(jn["main"]["humidity"])
        desc  = jn["weather"][0]["description"]

        params_fc = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "en"}
        r_fc = requests.get(base + "forecast", params=params_fc, timeout=8)
        r_fc.raise_for_status()
        jf = r_fc.json()
        items = jf.get("list", [])[:16]
        forecast = [{
            "dt": it["dt"],
            "time": it["dt_txt"],
            "temp": float(it["main"]["temp"]),
            "feels_like": float(it["main"]["feels_like"]),
            "humidity": float(it["main"]["humidity"]),
            "desc": it["weather"][0]["description"]
        } for it in items]

        top = sorted(forecast, key=lambda x: x["feels_like"], reverse=True)[:4]
        peak_hours = [f'{t["time"][5:16]} (~{round(t["feels_like"])}°C, {int(t["humidity"])}%)' for t in top]

        return {
            "temp": temp, "feels_like": feels, "humidity": hum, "desc": desc,
            "forecast": forecast, "peak_hours": peak_hours
        }, None
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
        name = it.get("name") or q
        lat, lon = it.get("lat"), it.get("lon")
        return name, lat, lon
    except Exception:
        return q, None, None

@st.cache_data(ttl=600)
def get_weather_by_coords(lat, lon):
    if not OPENWEATHER_API_KEY or lat is None or lon is None:
        return None
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        r = requests.get(url, params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units":"metric"}, timeout=6)
        r.raise_for_status()
        j = r.json()
        return {
            "temp": float(j["main"]["temp"]),
            "feels_like": float(j["main"]["feels_like"]),
            "humidity": float(j["main"]["humidity"]),
            "desc": j["weather"][0]["description"]
        }
    except Exception:
        return None

# ================== RISK MODEL ==================
TRIGGER_WEIGHTS = {
    "Exercise": 2, "Sauna/Hot bath": 3, "Spicy food": 1, "Hot drinks": 1,
    "Stress/Anxiety": 1, "Direct sun exposure": 2, "Fever/Illness": 3, "Hormonal cycle": 1,
    "Tight clothing": 1, "Poor sleep": 1, "Dehydration": 2, "Crowded place": 1,
    "Cooking heat": 1, "Car without AC": 2, "Outdoor work": 2, "Long prayer standing": 1
}
SYMPTOM_WEIGHT = 0.5

def risk_from_env(feels_like_c: float, humidity: float) -> int:
    score = 0
    if feels_like_c >= 39: score += 3
    elif feels_like_c >= 35: score += 2
    elif feels_like_c >= 32: score += 1
    if humidity >= 60 and feels_like_c >= 32:
        score += 1
    return score

def risk_from_person(body_temp: float, baseline: float) -> int:
    try:
        delta = body_temp - baseline
    except Exception:
        delta = 0.0
    if delta >= 1.0: return 2
    if delta >= 0.5: return 1
    return 0

def compute_risk(feels_like, humidity, body_temp, baseline, triggers, symptoms):
    score = 0
    score += risk_from_env(feels_like, humidity)
    score += risk_from_person(body_temp, baseline or 37.0)
    score += sum(TRIGGER_WEIGHTS.get(t, 0) for t in triggers)
    score += SYMPTOM_WEIGHT * len(symptoms)
    if score >= 7:  status, color, icon, text = "Danger", "red", "🔴", "High risk: stay in cooled spaces, avoid exertion, use cooling packs, and rest. Seek clinical advice for severe symptoms."
    elif score >= 5: status, color, icon, text = "High", "orangered", "🟠", "Elevated risk: limit time outside (esp. midday), pre-cool and pace activities."
    elif score >= 3: status, color, icon, text = "Caution", "orange", "🟡", "Mild risk: hydrate, take breaks, prefer shade/AC, and monitor symptoms."
    else:            status, color, icon, text = "Safe", "green", "🟢", "You look safe. Keep cool and hydrated."
    return {"score": score, "status": status, "color": color, "icon": icon, "advice": text}

# ================== NAVIGATION FIX ==================
# Use query parameters for reliable navigation
def get_current_page():
    """Get current page from query parameters with fallback"""
    query_params = st.query_params
    page = query_params.get("page", ["about"])[0]
    
    # Validate page exists
    PAGE_IDS = ["about", "monitor", "planner", "journal", "assistant", "exports", "settings"]
    if page not in PAGE_IDS:
        page = "about"
        st.query_params["page"] = page
    
    return page

def set_current_page(page):
    """Set current page in query parameters"""
    st.query_params["page"] = page

# ================== SIDEBAR ==================
# --- Sidebar: logo ---
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/6512b826bd06f692ad81f896773b44a3b0482001/logo1.png"
st.sidebar.image(logo_url, use_container_width=True)

# --- Sidebar: language selector ---
app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English", "Arabic"], key="language_selector")
T = TEXTS[app_language]

# RTL for Arabic
if app_language == "Arabic":
    st.markdown("""
    <style>
    body, .block-container { direction: rtl; text-align: right; }
    [data-testid="stSidebar"] { direction: rtl; text-align: right; }
    </style>
    """, unsafe_allow_html=True)

# --- Navigation with query parameters (FIX for double-click issue) ---
PAGE_IDS = ["about", "monitor", "planner", "journal", "assistant", "exports", "settings"]
PAGE_LABELS = {
    "about": T["about_title"],
    "monitor": T["temp_monitor"],
    "planner": T["planner"],
    "journal": T["journal"],
    "assistant": T["assistant"],
    "exports": T["exports"],
    "settings": T["settings"],
}

# Get current page from query params
current_page = get_current_page()

# Navigation using buttons instead of radio for better control
st.sidebar.markdown("### 📑 " + ("التنقل" if app_language == "Arabic" else "Navigation"))

# Create navigation buttons
for page_id in PAGE_IDS:
    if st.sidebar.button(PAGE_LABELS[page_id], use_container_width=True, 
                        type="primary" if page_id == current_page else "secondary"):
        set_current_page(page_id)
        st.rerun()

# --- Login/Register + Logout (expander) ---
exp_title = (f"{T['login_title']} — {st.session_state['user']}" if "user" in st.session_state else T["login_title"])
with st.sidebar.expander(exp_title, expanded=True):
    if "user" not in st.session_state:
        username = st.text_input(T["username"], key="sb_user")
        password = st.text_input(T["password"], type="password", key="sb_pass")
        col1, col2 = st.columns(2)
        with col1:
            if st.button(T["login"], key="sb_login_btn"):
                c = get_conn().cursor()
                c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
                if c.fetchone():
                    st.session_state["user"] = username
                    st.success(T["logged_in"])
                    st.rerun()
                else:
                    st.error(T["bad_creds"])
        with col2:
            if st.button(T["register"], key="sb_reg_btn"):
                try:
                    c = get_conn().cursor()
                    c.execute("INSERT INTO users VALUES (?,?)", (username, password))
                    get_conn().commit()
                    st.success(T["account_created"])
                except Exception:
                    st.error(T["user_exists"])
    else:
        st.write(f"**{st.session_state['user']}**")
        if st.button(T["logout"], key="sb_logout_btn"):
            st.session_state.pop("user", None)
            st.success(T["logged_out"])
            st.rerun()

# Emergency in sidebar (click-to-call)
with st.sidebar.expander("📞 " + T["emergency"], expanded=False):
    st.session_state.setdefault("primary_phone", "")
    st.session_state.setdefault("secondary_phone", "")
    if st.session_state["primary_phone"]:
        st.markdown(f"**{'Primary' if app_language == 'English' else 'الهاتف الأساسي'}:** [{st.session_state['primary_phone']}](tel:{st.session_state['primary_phone']})")
    if st.session_state["secondary_phone"]:
        st.markdown(f"**{'Secondary' if app_language == 'English' else 'هاتف إضافي'}:** [{st.session_state['secondary_phone']}](tel:{st.session_state['secondary_phone']})")
    if not (st.session_state["primary_phone"] or st.session_state["secondary_phone"]):
        st.caption("Set numbers in Settings to enable quick call." if app_language == "English" else "اضبط الأرقام في الإعدادات لتمكين الاتصال السريع.")

# ================== PAGE ROUTING ==================
if current_page == "about":
    if app_language == "English":
        st.title("🧠 Welcome to Raha MS")
        st.markdown("""
Living with **Multiple Sclerosis (MS)** in the GCC can be uniquely challenging, especially with the region's intense heat.  
**Raha MS** was designed **with and for people living with MS** — to bring comfort, awareness, and support to your daily life.
""")
        st.subheader("🌡️ Why Heat Matters in MS")
        st.info("Even a small rise in **core body temperature** (as little as **0.5°C**) can temporarily worsen MS symptoms — this is known as **Uhthoff's phenomenon**.")
        st.subheader("✨ What This App Offers You")
        st.markdown("""
- **Track** your body temperature and local weather.  
- **Discover** personal heat triggers (exercise, hot food, stress, etc.).  
- **Record** symptoms and your health journey in a private journal.  
- **Get support** from the AI Companion with culturally tailored advice for life in the Gulf.  
""")
        st.subheader("🤝 Our Goal")
        st.success("To give you simple tools that fit your life, reduce uncertainty, and help you feel more in control.")
        st.caption("Raha MS is a co-created prototype with the MS community in the Gulf. Your feedback shapes what comes next.")
        st.caption("Privacy: Your data is stored locally (SQLite). This is for prototyping and education — not a medical device.")
    else:
        st.title("🧠 مرحبًا بك في راحة إم إس")
        st.markdown("""
العيش مع **التصلب المتعدد (MS)** في الخليج قد يكون صعبًا بسبب الحرارة والرطوبة.  
تم تصميم **راحة إم إس** **بالتعاون مع مرضى التصلب المتعدد** ليمنحك راحة ووعيًا ودعمًا في حياتك اليومية.
""")
        st.subheader("🌡️ لماذا تؤثر الحرارة؟")
        st.info("حتى الارتفاع البسيط في حرارة الجسم (**0.5°م**) قد يزيد الأعراض مؤقتًا — ويعرف ذلك بـ **ظاهرة أوتهوف**.")
        st.subheader("✨ ما الذي يقدمه التطبيق؟")
        st.markdown("""
- **مراقبة** حرارة جسمك والطقس من حولك.  
- **اكتشاف** المحفزات الشخصية للحرارة (رياضة، طعام حار، توتر...).  
- **تسجيل** الأعراض ورحلتك الصحية في يوميات خاصة.  
- **الحصول** على دعم من المساعد الذكي بنصائح متناسبة مع بيئة الخليج.  
""")
        st.subheader("🤝 هدفنا")
        st.success("أن نمنحك أدوات بسيطة تناسب حياتك اليومية وتخفف القلق وتمنحك شعورًا أكبر بالتحكم.")
        st.caption("راحة إم إس نموذج أولي تم تطويره بالتعاون مع مجتمع مرضى التصلب المتعدد في الخليج. رأيك يهمنا.")
        st.caption("الخصوصية: بياناتك محفوظة محليًا (SQLite). هذا لأغراض النمذجة والتعليم — وليس جهازًا طبيًا.")

elif current_page == "monitor":
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("☀️ " + T["risk_dashboard"])

        # Session defaults
        st.session_state.setdefault("live_running", False)
        st.session_state.setdefault("live_core_smoothed", [])
        st.session_state.setdefault("live_core_raw", [])
        st.session_state.setdefault("live_periph_smoothed", [])
        st.session_state.setdefault("live_periph_raw", [])
        st.session_state.setdefault("live_tick", 0)
        st.session_state.setdefault("last_db_write_tick", -999)
        st.session_state.setdefault("last_alert_ts", 0.0)
        st.session_state.setdefault("_last_tick_ts", 0.0)
        st.session_state.setdefault("baseline", 37.0)
        st.session_state.setdefault("interval_slider", SIM_INTERVAL_SEC)

        # Top: city + sampling + baseline badges
        colA, colB, colC, colD = st.columns([1.2, 1, 1, 1.2])
        with colA:
            city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0, key="monitor_city")
        with colB:
            interval = st.slider("⏱️ " + T["sensor_update"], 30, 300, st.session_state["interval_slider"], 15, key="interval_slider")
        with colC:
            if not st.session_state["live_running"] and st.button(T["start_monitoring"], use_container_width=True):
                st.session_state["live_running"] = True
                core_start = round(st.session_state["baseline"] + random.uniform(-0.2, 0.2), 2)
                periph_start = round(core_start - random.uniform(0.5, 0.9), 2)
                st.session_state["live_core_smoothed"] = [core_start]
                st.session_state["live_core_raw"] = [core_start]
                st.session_state["live_periph_smoothed"] = [periph_start]
                st.session_state["live_periph_raw"] = [periph_start]
                st.session_state["live_tick"] = 0
                st.session_state["last_db_write_tick"] = -999
                st.session_state["last_alert_ts"] = 0.0
                st.session_state["_last_tick_ts"] = 0.0
                st.rerun()
            if st.session_state["live_running"] and st.button(T["pause"], use_container_width=True, key="pause_btn"):
                st.session_state["live_running"] = False
                st.rerun()
        with colD:
            # Baseline & hint
            baseline_text = "الأساس" if app_language == "Arabic" else "Baseline"
            change_text = "(التغيير في الإعدادات)" if app_language == "Arabic" else "(change in Settings)"
            st.markdown(f"<div class='badge'>{baseline_text}: <strong>{st.session_state['baseline']:.1f}°C</strong>"
                        f" <span class='small'>{change_text}</span></div>", unsafe_allow_html=True)

        # Weather (with visible last updated + refresh)
        weather, w_err = get_weather(city)
        colW1, colW2 = st.columns([1, 1])
        with colW1:
            if weather is None:
                st.error(f"{T['weather_fail']}: {w_err or '—'}")
                st.stop()
            else:
                st.caption("Weather last updated: " + datetime.now(TZ_DUBAI).strftime("%H:%M"))
        with colW2:
            if st.button(T["refresh_weather"], use_container_width=True):
                st.rerun()

        # Ticking the simulation according to the chosen interval
        now = time.time()
        last_tick_ts = st.session_state.get("_last_tick_ts", 0.0)
        if st.session_state["live_running"] and (now - last_tick_ts) >= st.session_state["interval_slider"]:
            st.session_state["_last_tick_ts"] = now

            prev_core = st.session_state["live_core_raw"][-1] if st.session_state["live_core_raw"] else st.session_state["baseline"]
            core_raw = random.uniform(st.session_state["baseline"] - 0.2, st.session_state["baseline"] + 0.5)
            st.session_state["live_core_raw"].append(core_raw)
            core_smoothed = sum(st.session_state["live_core_raw"][-3:]) / min(3, len(st.session_state["live_core_raw"]))
            st.session_state["live_core_smoothed"].append(core_smoothed)

            prev_periph = st.session_state["live_periph_raw"][-1] if st.session_state["live_periph_raw"] else (core_smoothed - 0.7)
            periph_raw = core_smoothed - random.uniform(0.4, 1.0)
            st.session_state["live_periph_raw"].append(periph_raw)
            periph_smoothed = sum(st.session_state["live_periph_raw"][-3:]) / min(3, len(st.session_state["live_periph_raw"]))
            st.session_state["live_periph_smoothed"].append(periph_smoothed)

            st.session_state["live_tick"] += 1

            # Update last_check snapshot
            latest_body = core_smoothed
            risk = compute_risk(weather["feels_like"], weather["humidity"],
                                latest_body, st.session_state["baseline"], [], [])
            st.session_state["last_check"] = {
                "city": city,
                "body_temp": latest_body,
                "peripheral_temp": periph_smoothed,
                "baseline": st.session_state['baseline'],
                "weather_temp": weather["temp"],
                "feels_like": weather["feels_like"],
                "humidity": weather["humidity"],
                "weather_desc": weather["desc"],
                "status": risk["status"], "color": risk["color"], "icon": risk["icon"],
                "advice": risk["advice"], "triggers": [], "symptoms": [],
                "peak_hours": weather["peak_hours"], "forecast": weather["forecast"],
                "time": utc_iso_now()
            }

            # Alert rule
            if len(st.session_state["live_core_smoothed"]) >= 2:
                recent = st.session_state["live_core_smoothed"][-2:]
                if all((t - st.session_state["baseline"]) >= ALERT_DELTA_C for t in recent):
                    if (now - st.session_state["last_alert_ts"]) >= ALERT_COOLDOWN_SEC:
                        st.session_state["last_alert_ts"] = now
                        alert_msg = "⚠️ Core temperature has risen ≥ 0.5°C above your baseline. Consider cooling and rest."
                        if app_language == "Arabic":
                            alert_msg = "⚠️ ارتفعت درجة حرارة الجسم الأساسية بمقدار ≥ 0.5°م فوق المستوى الأساسي. فكر في التبريد والراحة."
                        st.warning(alert_msg)

            # Save to DB every Nth sample
            if st.session_state["live_tick"] - st.session_state["last_db_write_tick"] >= DB_WRITE_EVERY_N:
                try:
                    insert_temp_row(
                        st.session_state.get("user", "guest"), dubai_now_str(),
                        latest_body, periph_smoothed,
                        weather["temp"], weather["feels_like"], weather["humidity"], risk["status"]
                    )
                    st.session_state["last_db_write_tick"] = st.session_state["live_tick"]
                except Exception as e:
                    st.warning(f"Could not save to DB: {e}")

            st.rerun()

        # Status card
        if st.session_state.get("last_check"):
            last = st.session_state["last_check"]
            lang_key = "AR" if app_language == "Arabic" else "EN"

            chips = []
            chips.append(f'<span class="badge"><strong>{"City" if lang_key=="EN" else "المدينة"}:</strong> {last["city"]}</span>')
            chips.append(f'<span class="badge"><strong>{"Feels-like" if lang_key=="EN" else "الإحساس الحراري"}:</strong> {round(last["feels_like"],1)}°C</span>')
            chips.append(f'<span class="badge"><strong>{"Humidity" if lang_key=="EN" else "الرطوبة"}:</strong> {int(last["humidity"])}%</span>')
            chips.append(f'<span class="badge"><strong>{"Core" if lang_key=="EN" else "الأساسية"}:</strong> {round(last["body_temp"],1)}°C</span>')
            chips.append(f'<span class="badge"><strong>{"Peripheral" if lang_key=="EN" else "الطرفية"}:</strong> {round(last["peripheral_temp"],1)}°C</span>')
            chips.append(f'<span class="badge"><strong>{"Baseline" if lang_key=="EN" else "الأساس"}:</strong> {round(last["baseline"],1)}°C</span>')

            st.markdown(f"""
<div class="big-card" style="--left:{last['color']}">
  <h3>{last['icon']} <strong>Status: {last['status']}</strong></h3>
  <p style="margin:6px 0 0 0; color: #000000 !important;">{last['advice']}</p>
  <div class="small" style="margin-top:8px">{''.join(chips)}</div>
  <p class="small" style="margin-top:6px"><strong>{T['peak_heat']}:</strong> {("; ".join(last.get('peak_hours', []))) if last.get('peak_hours') else "—"}</p>
</div>
""", unsafe_allow_html=True)

        # If above threshold, show "log reason" form
        if st.session_state["live_core_smoothed"]:
            latest = st.session_state["live_core_smoothed"][-1]
            delta = latest - st.session_state["baseline"]

            if delta >= ALERT_DELTA_C:
                st.markdown(f"### {T['log_now']}")

                with st.form("log_reason_form", clear_on_submit=True):
                    trigger_options = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
                    chosen = st.multiselect(T["triggers_today"], trigger_options, max_selections=6)
                    other_text = st.text_input(T["other"], "")
                    symptoms_list = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
                    selected_symptoms = st.multiselect(T["symptoms_today"], symptoms_list)
                    note_text = st.text_input(T["notes"], "")

                    if st.form_submit_button(T["save_entry"]):
                        st.session_state["live_running"] = False
                        entry = {
                            "type":"ALERT",
                            "at": utc_iso_now(),
                            "body_temp": round(latest,1),
                            "baseline": round(st.session_state['baseline'],1),
                            "reasons": chosen + ([f"Other: {other_text.strip()}"] if other_text.strip() else []),
                            "symptoms": selected_symptoms,
                            "note": note_text.strip()
                        }
                        try:
                            insert_journal(st.session_state.get("user","guest"), utc_iso_now(), entry)
                            st.success(T["saved"])
                        except Exception as e:
                            st.warning(f"Could not save note: {e}")

        # Trend chart
        st.markdown("---")
        st.subheader(T["temperature_trend"])
        
        if st.session_state["live_core_smoothed"]:
            # Create a simple chart from live data
            fig, ax = plt.subplots(figsize=(10,4))
            x = range(len(st.session_state["live_core_smoothed"]))
            ax.plot(x, st.session_state["live_core_smoothed"], marker='o', label="Core", linewidth=2)
            ax.plot(x, st.session_state["live_periph_smoothed"], marker='o', label="Peripheral", linewidth=1.8)
            ax.axhline(y=st.session_state["baseline"], color='r', linestyle='--', label="Baseline")
            ax.set_xlabel("Sample")
            ax.set_ylabel("°C")
            ax.legend()
            ax.grid(True, alpha=0.3)
            chart_title = "Core vs Peripheral Temperature"
            if app_language == "Arabic":
                chart_title = "الأساسية مقابل الطرفية درجة الحرارة"
            ax.set_title(chart_title)
            st.pyplot(fig)

        if app_language == "Arabic":
            st.caption(f"فترة أخذ العينات: **{st.session_state['interval_slider']} ثانية**")
        else:
            st.caption(f"Sampling interval: **{st.session_state['interval_slider']} sec**")

elif current_page == "planner":
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("🗺️ " + T["planner"])
        
        city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0, key="planner_city")
        weather, err = get_weather(city)
        
        if weather is None:
            st.error(f"{T['weather_fail']}: {err}")
        else:
            st.success(f"Current in {city}: {round(weather['feels_like'],1)}°C feels-like, {weather['desc']}")
            
            # Simple planner interface
            st.subheader("Quick Plan")
            col1, col2 = st.columns(2)
            
            with col1:
                activity = st.text_input(T["activity"], "Walk in park")
                duration = st.slider(T["duration"], 15, 120, 30)
                
            with col2:
                location_type = st.radio(T["location"], ["Outdoor", "Indoor"], horizontal=True)
                planned_time = st.time_input("Plan for time", datetime.now(TZ_DUBAI).time())
            
            if st.button(T["add_plan"]):
                entry = {
                    "type": "PLAN",
                    "at": utc_iso_now(),
                    "city": city,
                    "activity": activity,
                    "duration": duration,
                    "location": location_type,
                    "planned_time": planned_time.strftime("%H:%M"),
                    "feels_like": round(weather['feels_like'], 1)
                }
                insert_journal(st.session_state["user"], utc_iso_now(), entry)
                st.success("Plan saved to journal!")
            
            # Show upcoming peak heat
            if weather.get('peak_hours'):
                st.subheader(T["peak_heat"])
                for hour in weather['peak_hours'][:3]:
                    st.write(f"• {hour}")

elif current_page == "journal":
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("📒 " + T["journal"])
        st.caption(T["journal_hint"])

        # Quick logger
        st.subheader(T["daily_logger"])
        col1, col2 = st.columns(2)
        
        with col1:
            mood = st.selectbox(T["mood"], ["😊 Good", "😐 Okay", "😟 Low", "😖 Stressed"])
            hydration = st.slider(T["hydration"], 0, 12, 6)
            sleep = st.slider(T["sleep"], 0, 12, 7)
            
        with col2:
            fatigue = st.slider(T["fatigue"], 1, 10, 5)
            triggers = st.multiselect(T["triggers_today"], 
                                    TRIGGERS_EN if app_language == "English" else TRIGGERS_AR)
            symptoms = st.multiselect(T["symptoms_today"],
                                    SYMPTOMS_EN if app_language == "English" else SYMPTOMS_AR)
        
        note = st.text_area(T["free_note"], placeholder="How are you feeling today?")
        
        if st.button(T["save_entry"]):
            entry = {
                "type": "DAILY",
                "at": utc_iso_now(),
                "mood": mood,
                "hydration": hydration,
                "sleep": sleep,
                "fatigue": fatigue,
                "triggers": triggers,
                "symptoms": symptoms,
                "note": note
            }
            insert_journal(st.session_state["user"], utc_iso_now(), entry)
            st.success("Daily log saved!")

        st.markdown("---")
        
        # Journal entries display
        st.subheader("Your Entries")
        
        # Fetch and display entries
        try:
            c = get_conn().cursor()
            c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC LIMIT 20", 
                     (st.session_state["user"],))
            entries = c.fetchall()
            
            if not entries:
                st.info("No journal entries yet. Start by adding one above!")
            else:
                for date_str, entry_json in entries:
                    try:
                        entry = json.loads(entry_json)
                        entry_type = entry.get("type", "NOTE")
                        
                        if entry_type == "DAILY":
                            icon = "📅"
                            title = f"Daily Log - {date_str[:16]}"
                            content = f"Mood: {entry.get('mood', 'N/A')} | Hydration: {entry.get('hydration', 'N/A')} glasses | Sleep: {entry.get('sleep', 'N/A')} hrs"
                            if entry.get('note'):
                                content += f" | Note: {entry.get('note')}"
                                
                        elif entry_type == "PLAN":
                            icon = "🗓️"
                            title = f"Plan - {date_str[:16]}"
                            content = f"Activity: {entry.get('activity', 'N/A')} | Duration: {entry.get('duration', 'N/A')} min"
                            
                        elif entry_type == "ALERT":
                            icon = "⚠️"
                            title = f"Alert - {date_str[:16]}"
                            content = f"Temp: {entry.get('body_temp', 'N/A')}°C | Reasons: {', '.join(entry.get('reasons', []))}"
                            
                        else:
                            icon = "📝"
                            title = f"Note - {date_str[:16]}"
                            content = entry.get('text', entry_json)[:100] + "..." if len(entry_json) > 100 else entry_json
                        
                        # Render the card with black text
                        st.markdown(f"""
                        <div class="big-card" style="--left:#94a3b8;margin-bottom:12px;">
                          <h3 style="margin:0; color: #000000 !important;">{icon} {title}</h3>
                          <div style="margin-top:6px; color: #000000 !important;">{content}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.markdown(f"""
                        <div class="big-card" style="--left:#94a3b8;margin-bottom:12px;">
                          <h3 style="margin:0; color: #000000 !important;">📝 Entry - {date_str[:16]}</h3>
                          <div style="margin-top:6px; color: #000000 !important;">{entry_json[:100]}...</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
        except Exception as e:
            st.error(f"Error loading journal: {e}")

elif current_page == "assistant":
    st.title("🤝 " + T["assistant_title"])
    
    if not client:
        st.warning(T["ai_unavailable"])
    else:
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input(T["ask_me_anything"]):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate AI response
            with st.chat_message("assistant"):
                with st.spinner(T["thinking"]):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                            temperature=0.7
                        )
                        ai_response = response.choices[0].message.content
                    except Exception as e:
                        ai_response = "I'm sorry, I encountered an error. Please try again."
                    
                    st.markdown(ai_response)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
        
        # Clear chat button
        if st.button(T["reset_chat"]):
            st.session_state.messages = []
            st.rerun()

elif current_page == "exports":
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("📦 " + T["export_title"])
        st.caption(T["export_desc"])
        
        # Create export data
        try:
            # Export temperatures
            temps_df = fetch_temps_df(st.session_state["user"])
            journal_df = fetch_journal_df(st.session_state["user"])
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Temperature Data")
                st.dataframe(temps_df.tail(10) if not temps_df.empty else pd.DataFrame())
                
                # Download temps as CSV
                csv_temps = temps_df.to_csv(index=False)
                st.download_button(
                    label="Download Temperatures CSV",
                    data=csv_temps,
                    file_name="raha_temperatures.csv",
                    mime="text/csv",
                )
            
            with col2:
                st.subheader("Journal Data")
                st.dataframe(journal_df.tail(10) if not journal_df.empty else pd.DataFrame())
                
                # Download journal as CSV
                csv_journal = journal_df.to_csv(index=False)
                st.download_button(
                    label="Download Journal CSV",
                    data=csv_journal,
                    file_name="raha_journal.csv",
                    mime="text/csv",
                )
            
            # Combined Excel export
            if st.button(T["export_excel"]):
                try:
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        temps_df.to_excel(writer, sheet_name='Temperatures', index=False)
                        journal_df.to_excel(writer, sheet_name='Journal', index=False)
                    
                    output.seek(0)
                    st.download_button(
                        label="Download Excel File",
                        data=output.read(),
                        file_name="raha_data.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                except Exception as e:
                    st.error(f"Error creating Excel file: {e}")
                    
        except Exception as e:
            st.error(f"Error exporting data: {e}")

elif current_page == "settings":
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("⚙️ " + T["settings"])
        
        # Baseline settings
        st.subheader(T["baseline_setting"])
        baseline = st.number_input(
            T["baseline_setting"], 
            min_value=35.5, 
            max_value=38.5, 
            value=float(st.session_state.get("baseline", 37.0)),
            step=0.1,
            key="baseline_input"
        )
        use_baseline = st.checkbox(T["use_temp_baseline"], value=True)
        
        # Emergency contacts
        st.subheader(T["contacts"])
        col1, col2 = st.columns(2)
        with col1:
            primary_phone = st.text_input(T["primary_phone"], value=st.session_state.get("primary_phone", ""))
        with col2:
            secondary_phone = st.text_input(T["secondary_phone"], value=st.session_state.get("secondary_phone", ""))
        
        # Save settings
        if st.button(T["save_settings"]):
            st.session_state["baseline"] = baseline
            st.session_state["use_temp_baseline"] = use_baseline
            st.session_state["primary_phone"] = primary_phone
            st.session_state["secondary_phone"] = secondary_phone
            st.success(T["saved"])
        
        # Logout
        st.markdown("---")
        if st.button(T["logout"], type="secondary"):
            st.session_state.pop("user", None)
            st.success(T["logged_out"])
            st.rerun()

# ---- Global session defaults ----
st.session_state.setdefault("baseline", 37.0)
st.session_state.setdefault("use_temp_baseline", True)
st.session_state.setdefault("primary_phone", "")
st.session_state.setdefault("secondary_phone", "")

# RTL for Arabic - Enhanced CSS for better slider alignment
if app_language == "Arabic":
    st.markdown("""
    <style>
    body, .block-container { 
        direction: rtl; 
        text-align: right; 
    }
    [data-testid="stSidebar"] { 
        direction: rtl; 
        text-align: right; 
    }
    .stSlider > div:first-child {
        direction: ltr;
    }
    .stSlider label {
        text-align: right;
        direction: rtl;
        display: block;
    }
    .stSelectbox label,
    .stTextInput label,
    .stTextArea label {
        text-align: right;
        direction: rtl;
    }
    .stRadio > label {
        direction: rtl;
        text-align: right;
    }
    .stMultiSelect label {
        text-align: right;
        direction: rtl;
    }
    /* Ensure slider values display correctly in RTL */
    .stSlider > div > div > div {
        direction: ltr;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    body, .block-container { 
        direction: ltr; 
        text-align: left; 
    }
    [data-testid="stSidebar"] { 
        direction: ltr; 
        text-align: left; 
    }
    </style>
    """, unsafe_allow_html=True)
