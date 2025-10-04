# -*- coding: utf-8 -*-
# RAHA / TANZIM MS — Comprehensive App (EN/AR, RTL, Sensors Explainer, Recovery Learning, OpenAI+DeepSeek)
# -----------------------------------------------------------------------------------------
# Built for people with MS in the Gulf: heat-aware planning, live monitoring, journal, AI companion.

import streamlit as st
import sqlite3, json, requests, random, time, zipfile
from io import BytesIO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
from datetime import datetime as _dt
import re
import statistics

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import pandas as pd
import plotly.graph_objects as go

try:
    from supabase import create_client, Client
except Exception:
    create_client, Client = None, None

# ================== CONFIG ==================
st.set_page_config(page_title="Tanzim MS", page_icon="🌡️", layout="wide")
TZ_DUBAI = ZoneInfo("Asia/Dubai")

# Secrets
OPENAI_API_KEY     = st.secrets.get("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY   = st.secrets.get("DEEPSEEK_API_KEY", "")
OPENWEATHER_API_KEY= st.secrets.get("OPENWEATHER_API_KEY", "")
SUPABASE_URL       = st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY  = st.secrets.get("SUPABASE_ANON_KEY", "")

# Matplotlib: Arabic-safe
matplotlib.rcParams["axes.unicode_minus"] = False
_ARABIC_FONTS_TRY = ["Noto Naskh Arabic", "Amiri", "DejaVu Sans", "Arial"]
for _fname in _ARABIC_FONTS_TRY:
    try:
        matplotlib.rcParams["font.family"] = _fname
        break
    except Exception:
        continue
_AR_FONT = FontProperties(family=matplotlib.rcParams["font.family"])
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    def ar_shape(s: str) -> str:
        return get_display(arabic_reshaper.reshape(s))
    _HAS_AR_SHAPER = True
except Exception:
    def ar_shape(s: str) -> str:
        return s
    _HAS_AR_SHAPER = False

# GCC quick picks
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

# Live config
WEATHER_TTL_SEC = 15 * 60
ALERT_DELTA_C = 0.5

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
        "weather_fail": "Weather lookup failed",
        "ai_unavailable": "AI is unavailable. Add API keys in secrets.",
        "journal_hint": "Use the quick logger or free text. Alerts and plans also save here.",
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
        "symptom":"Symptom",
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
        "assistant_title": "Your AI Companion",
        "assistant_hint": "Ask about cooling, pacing, safe windows, fasting/prayer, travel, etc.",
        "home_city": "Home City",
        "timezone": "Timezone (optional)"
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
        "weather_fail": "فشل جلب الطقس",
        "ai_unavailable": "الخدمة الذكية غير متاحة. أضف مفاتيح API.",
        "journal_hint": "استخدم المُسجّل السريع أو النص الحر. كما تُحفظ التنبيهات والخطط هنا.",
        "daily_logger": "المُسجّل اليومي السريع",
        "mood": "المزاج",
        "hydration": "شرب الماء (أكواب) 💧",
        "sleep": "النوم (ساعات) 🛌",
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
        "symptom":"العارض",
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
        "assistant_title": "مرافقك الذكي",
        "assistant_hint": "اسأل عن التبريد، تنظيم الجهد، النوافذ الآمنة، الصيام/الصلاة، السفر…",
        "home_city": "المدينة الأساسية",
        "timezone": "المنطقة الزمنية (اختياري)"
    }
}

TRIGGERS_EN = [
    "Exercise","Direct sun exposure","Sauna/Hot bath","Spicy food","Hot drinks",
    "Stress/Anxiety","Fever/Illness","Hormonal cycle","Tight clothing","Poor sleep",
    "Dehydration","Crowded place","Cooking heat","Car without AC","Outdoor work","Long prayer standing"
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

# ================== STYLES ==================
ACCESSIBLE_CSS = """
<style>
html, body, [class*="css"] { font-size: 18px; }
/* theme-aware card colors */
:root { --card-bg:#fff; --card-fg:#0f172a; --chip-border:rgba(0,0,0,.12); --muted-fg:rgba(15,23,42,.75); }
@media (prefers-color-scheme: dark) {
  :root { --card-bg:#0b1220; --card-fg:#e5e7eb; --chip-border:rgba(255,255,255,.25); --muted-fg:rgba(229,231,235,.85); }
}
.big-card { background:var(--card-bg); color:var(--card-fg); padding:18px; border-radius:14px; border-left:10px solid var(--left); box-shadow:0 2px 8px rgba(0,0,0,.06); }
.big-card h3, .big-card p, .big-card .small { color:var(--card-fg); }
.badge { display:inline-block; padding:6px 10px; border-radius:999px; border:1px solid var(--chip-border); margin-right:6px; color:var(--card-fg); }
.small { opacity:.9; color:var(--muted-fg); font-size:14px; }
h3 { margin-top:.2rem; } .stButton>button{ padding:.6rem 1.1rem; font-weight:600; }
.stMarkdown ul li, .stMarkdown ol li { margin-bottom:.6em !important; }
.stMarkdown ul, .stMarkdown ol { margin-bottom:.4em !important; }

/* RTL Support */
[dir="rtl"] .stSlider > div:first-child { direction:ltr; }        /* ticks move LTR */
[dir="rtl"] .stSlider label { text-align:right; direction:rtl; }   /* labels RTL */
[dir="rtl"] [data-testid="stAppViewContainer"] { direction:rtl !important; text-align:right !important; }
[dir="rtl"] [data-testid="stSidebar"] { direction:ltr !important; }
[dir="rtl"] [data-testid="stSidebar"] > div { direction:rtl !important; text-align:right !important; }

/* Mobile tabs spacing */
@media (max-width: 640px) {
  div[role="tablist"] { overflow-x:auto !important; white-space:nowrap !important; padding-bottom:6px !important; margin-bottom:8px !important; }
  .stTabs + div, .stTabs + section { margin-top:6px !important; }
}

/* Keep paragraphs theme-aware */
.stMarkdown p, .stMarkdown li { color:inherit !important; }
</style>
"""
st.markdown(ACCESSIBLE_CSS, unsafe_allow_html=True)

# ================== DB ==================
@st.cache_resource
def get_conn():
    conn = sqlite3.connect("raha_ms.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

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
            ai_style TEXT,
            updated_at TEXT,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        )
    """)
    conn.commit()

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS temps(
        username TEXT, date TEXT, body_temp REAL, peripheral_temp REAL,
        weather_temp REAL, feels_like REAL, humidity REAL, status TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS journal(username TEXT, date TEXT, entry TEXT)""")
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

# ================== SUPABASE ==================
@st.cache_resource
def get_supabase():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY or not create_client:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception:
        return None

def fetch_latest_sensor_sample(device_id: str) -> dict | None:
    sb = get_supabase()
    if not sb or not device_id:
        return None
    try:
        res = (sb.table("sensor_readings")
                 .select("core_c,peripheral_c,created_at")
                 .eq("device_id", device_id)
                 .order("created_at", desc=True)
                 .limit(1)
                 .execute())
        data = (res.data or [])
        if not data: return None
        row = data[0]
        return {"core": float(row.get("core_c")), "peripheral": float(row.get("peripheral_c")), "at": row.get("created_at")}
    except Exception:
        return None

# ================== UTILS ==================
def normalize_phone(s: str) -> str:
    if not s: return ""
    s = re.sub(r"[^\d+]", "", s.strip())
    if s.count("+") > 1:
        s = "+" + re.sub(r"\D", "", s)
    return s

def tel_href(s: str) -> str:
    return normalize_phone(s)

def utc_iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

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
            obj = json.loads(raw); parsed.append({"date": dt, **obj})
        except Exception:
            parsed.append({"date": dt, "type": "NOTE", "text": raw})
    return pd.DataFrame(parsed)

def build_export_excel_or_zip(user) -> tuple[bytes, str]:
    temps = fetch_temps_df(user)
    journal = fetch_journal_df(user)
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
    with zipfile.ZipFile(memzip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Temps.csv", temps.to_csv(index=False).encode("utf-8"))
        zf.writestr("Journal.csv", journal.to_csv(index=False).encode("utf-8"))
    memzip.seek(0)
    return memzip.read(), "application/zip"

def dubai_now_str():
    return datetime.now(TZ_DUBAI).strftime("%Y-%m-%d %H:%M")

# ================== WEATHER ==================
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
        temp = float(jn["main"]["temp"])
        feels = float(jn["main"]["feels_like"])
        hum = float(jn["main"]["humidity"])
        desc = jn["weather"][0]["description"]

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
        return {"temp": temp, "feels_like": feels, "humidity": hum, "desc": desc,
                "forecast": forecast, "peak_hours": peak_hours}, None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=600)
def geocode_place(q):
    try:
        url = "https://api.openweathermap.org/geo/1.0/direct"
        r = requests.get(url, params={"q": q, "limit": 1, "appid": OPENWEATHER_API_KEY}, timeout=6)
        r.raise_for_status()
        arr = r.json()
        if not arr:
            return q, None, None
        it = arr[0]
        name = it.get("name") or q
        return name, it.get("lat"), it.get("lon")
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
        return {"temp": float(j["main"]["temp"]),
                "feels_like": float(j["main"]["feels_like"]),
                "humidity": float(j["main"]["humidity"]),
                "desc": j["weather"][0]["description"]}
    except Exception:
        return None

def get_weather_cached(city: str):
    st.session_state.setdefault("_weather_cache", {})
    rec = st.session_state["_weather_cache"].get(city)
    now = time.time()
    needs_refresh = (rec is None) or (now - rec["ts"] > WEATHER_TTL_SEC)
    if needs_refresh:
        data, err = get_weather(city)
        if data is None:
            if rec:
                return rec["data"], None, rec["ts"]
            return None, err, None
        st.session_state["_weather_cache"][city] = {"data": data, "ts": now}
        return data, None, now
    else:
        return rec["data"], None, rec["ts"]

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
    if humidity >= 60 and feels_like_c >= 32:
        score += 1
    return score

def risk_from_person(body_temp: float, baseline: float) -> int:
    delta = (body_temp - baseline) if (body_temp is not None and baseline is not None) else 0.0
    if delta >= 1.0: return 2
    if delta >= 0.5: return 1
    return 0

def compute_risk(feels_like, humidity, body_temp, baseline, triggers, symptoms):
    score = 0
    score += risk_from_env(feels_like or 0.0, humidity or 0.0)
    score += risk_from_person(body_temp, baseline or 37.0)
    score += sum(TRIGGER_WEIGHTS.get(t, 0) for t in (triggers or []))
    score += SYMPTOM_WEIGHT * len(symptoms or [])
    if score >= 7:
        return {"score": score, "status": "Danger", "color": "red", "icon": "🔴",
                "advice": "High risk: stay in AC, avoid exertion, cooling packs, rest; seek clinical advice if severe."}
    elif score >= 5:
        return {"score": score, "status": "High", "color": "orangered", "icon": "🟠",
                "advice": "Elevated: limit outdoor time esp. midday; pre-cool and pace activities."}
    elif score >= 3:
        return {"score": score, "status": "Caution", "color": "orange", "icon": "🟡",
                "advice": "Mild risk: hydrate, take breaks, prefer shade/AC, and monitor symptoms."}
    else:
        return {"score": score, "status": "Safe", "color": "green", "icon": "🟢",
                "advice": "You look safe. Keep cool and hydrated."}

# ================== PREFERENCES & CONTACTS ==================
def save_emergency_contacts(username, primary_phone, secondary_phone):
    conn = get_conn(); c = conn.cursor()
    p1 = tel_href(primary_phone); p2 = tel_href(secondary_phone); now = utc_iso_now()
    try:
        c.execute("""
            INSERT INTO emergency_contacts (username, primary_phone, secondary_phone, updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(username) DO UPDATE SET
                primary_phone=excluded.primary_phone,
                secondary_phone=excluded.secondary_phone,
                updated_at=excluded.updated_at
        """, (username, p1, p2, now))
        conn.commit(); return True, None
    except Exception as e:
        return False, str(e)

def load_emergency_contacts(username):
    c = get_conn().cursor()
    try:
        c.execute("SELECT primary_phone, secondary_phone FROM emergency_contacts WHERE username=?", (username,))
        row = c.fetchone()
        if row: return row[0] or "", row[1] or ""
        return "", ""
    except Exception:
        return "", ""

def load_user_prefs(username):
    if not username: return {}
    c = get_conn().cursor()
    c.execute("SELECT home_city, timezone, language, ai_style FROM user_prefs WHERE username=?", (username,))
    row = c.fetchone()
    if not row: return {}
    return {"home_city": row[0], "timezone": row[1], "language": row[2], "ai_style": row[3]}

def save_user_prefs(username, home_city=None, timezone=None, language=None, ai_style=None):
    conn = get_conn(); c = conn.cursor()
    prev = load_user_prefs(username)
    home_city = home_city if home_city is not None else prev.get("home_city")
    timezone = timezone if timezone is not None else prev.get("timezone")
    language  = language  if language  is not None else prev.get("language")
    ai_style  = ai_style  if ai_style  is not None else prev.get("ai_style")
    now = utc_iso_now()
    c.execute("""
        INSERT INTO user_prefs (username, home_city, timezone, language, ai_style, updated_at)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(username) DO UPDATE SET
          home_city=excluded.home_city,
          timezone=excluded.timezone,
          language=excluded.language,
          ai_style=excluded.ai_style,
          updated_at=excluded.updated_at
    """, (username, home_city, timezone, language, ai_style, now))
    conn.commit()

# ================== AI HELPERS ==================
ACTIONS_EN = [
    "Moved indoors/AC","Cooling vest","Cool shower","Rested 15–20 min","Drank water",
    "Electrolyte drink","Fan airflow","Stayed in shade","Wet towel/neck wrap","Lowered intensity / paused",
    "Pre‑cooled car","Changed to light clothing","Wrist/forearm cooling","Ice pack"
]
ACTIONS_AR = [
    "الانتقال إلى الداخل/مكيف","سترة تبريد","دش بارد","راحة 15–20 دقيقة","شرب ماء",
    "مشروب إلكتروليت","مروحة","الظل","منشفة مبللة/لف الرقبة","خفض الشدة / توقف",
    "تبريد السيارة مسبقًا","ملابس خفيفة","تبريد المعصم/الساعد","كمادة ثلج"
]
def _actions_for_lang(lang):
    return ACTIONS_AR if lang == "Arabic" else ACTIONS_EN

def get_top_actions_counts(username: str, lookback_days: int = 30) -> list[tuple[str,int]]:
    try:
        c = get_conn().cursor()
        c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC LIMIT 500", (username,))
        rows = c.fetchall()
    except Exception:
        rows = []
    counts = {}
    cutoff = _dt.now(timezone.utc) - timedelta(days=lookback_days)
    for dt_raw, raw in rows:
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if obj.get("type") != "RECOVERY": continue
        try:
            ts = _dt.fromisoformat(dt_raw.replace("Z","+00:00"))
        except Exception:
            ts = _dt.now(timezone.utc)
        if ts < cutoff: continue
        for a in obj.get("actions", []):
            a = str(a).strip()
            if a: counts[a] = counts.get(a, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:6]

def _format_top_actions_str(username: str, lang: str) -> str:
    tops = get_top_actions_counts(username, 60)
    if not tops: return ""
    if lang == "Arabic":
        lines = ["إجراءات فعّالة مؤخرًا لهذا المستخدم:"]
        lines += [f"- {a} ×{n}" for a,n in tops]
    else:
        lines = ["Top effective actions for this user recently:"]
        lines += [f"- {a} ×{n}" for a,n in tops]
    return "\n".join(lines)

def get_recent_journal_context(username: str, max_entries: int = 5) -> str:
    try:
        c = get_conn().cursor()
        c.execute("""
            SELECT date, entry FROM journal 
            WHERE username=? ORDER BY date DESC LIMIT ?
        """, (username, max_entries))
        rows = c.fetchall()
    except Exception:
        rows = []
    if not rows:
        return "No recent journal entries."
    lines = []
    for dt, raw in rows:
        try: entry = json.loads(raw)
        except Exception: 
            entry = {"type":"NOTE", "text":str(raw)}
        t = entry.get("type","NOTE")
        if t == "DAILY":
            lines.append(f"Daily: mood={entry.get('mood','?')}, hydration={entry.get('hydration_glasses','?')}g, sleep={entry.get('sleep_hours','?')}h, fatigue={entry.get('fatigue','?')}")
        elif t in ("ALERT","ALERT_AUTO"):
            core = entry.get("core_temp") or entry.get("body_temp"); base = entry.get("baseline")
            delta = f"+{round(core-base,1)}°C" if (core is not None and base is not None) else ""
            lines.append(f"Alert: core={core}°C {delta}; reasons={entry.get('reasons',[])}; symptoms={entry.get('symptoms',[])}")
        elif t == "PLAN":
            lines.append(f"Plan: {entry.get('activity','?')} in {entry.get('city','?')} ({entry.get('start','?')}→{entry.get('end','?')})")
        elif t == "RECOVERY":
            from_s = entry.get("from_status","?"); to_s = entry.get("to_status","?")
            acts = entry.get("actions",[])
            core_b = entry.get("core_before"); core_a = entry.get("core_after")
            d = None
            try:
                if core_a is not None and core_b is not None:
                    d = round(core_a - core_b,1)
            except Exception:
                pass
            tail = f" Δcore {d:+.1f}°C" if d is not None else ""
            lines.append(f"Recovery: {from_s}→{to_s}; actions={acts}{tail}")
        else:
            note = (entry.get("text") or entry.get("note") or "").strip()
            if note: lines.append("Note: " + note[:100] + ("..." if len(note)>100 else ""))
    return "\n".join(lines[:10])

def get_weather_context(city: str | None):
    if not city: return None
    try:
        weather_data, error = get_weather(city)
        if weather_data is None: return None
        city_name = city.split(",")[0]
        return (f"REAL-TIME WEATHER FOR {city_name.upper()}:\n"
                f"• Current: {weather_data['temp']}°C\n"
                f"• Feels-like: {weather_data['feels_like']}°C\n"
                f"• Humidity: {weather_data['humidity']}%\n"
                f"• Conditions: {weather_data['desc']}\n"
                f"• Peak Heat Times: {', '.join(weather_data.get('peak_hours', []))}")
    except Exception:
        return None

def resolve_city_for_chat(prompt_text: str | None) -> str | None:
    """Try to infer a city from prompt or user prefs; avoid defaulting to Dubai unless chosen."""
    txt = (prompt_text or "").lower()
    mapping = {
        "abu dhabi": "Abu Dhabi,AE","abudhabi":"Abu Dhabi,AE","أبوظبي":"Abu Dhabi,AE",
        "dubai":"Dubai,AE","دبي":"Dubai,AE","sharjah":"Sharjah,AE","الشارقة":"Sharjah,AE",
        "doha":"Doha,QA","qatar":"Doha,QA","الدوحة":"Doha,QA","قطر":"Doha,QA",
        "kuwait":"Kuwait City,KW","الكويت":"Kuwait City,KW",
        "manama":"Manama,BH","المنامة":"Manama,BH",
        "riyadh":"Riyadh,SA","الرياض":"Riyadh,SA","jeddah":"Jeddah,SA","جدة":"Jeddah,SA",
        "dammam":"Dammam,SA","الدمام":"Dammam,SA","muscat":"Muscat,OM","مسقط":"Muscat,OM",
        "al rayyan":"Al Rayyan,QA","الريان":"Al Rayyan,QA"
    }
    for k,v in mapping.items():
        if k in txt: return v
    # state or prefs
    if st.session_state.get("current_city"): return st.session_state["current_city"]
    if "user" in st.session_state:
        prefs = load_user_prefs(st.session_state["user"])
        if prefs.get("home_city"): return prefs["home_city"]
    return None  # no default

def get_fallback_response(prompt, lang, journal_context="", weather_context=""):
    prompt_lower = (prompt or "").lower()
    fb = {
        "English": {
            "weather": "I’d normally check real-time weather, but I’m offline. In the Gulf, prefer AC in peak (11–16h), hydrate, and use light cooling.",
            "journal": "I’d normally review your journal now. Common MS tips: hydrate, pace activities, and cool early after heat exposure.",
            "travel": "For trips: cooling garments, indoor activities at peak heat, hydrate, and pre‑cool before outings.",
            "symptoms": "Common heat triggers: sun, dehydration, high humidity. Cool wrists/neck, move to AC, and rest when fatigued.",
            "general": "I’m here to help you manage heat with MS. Basics: stay cool, hydrate, pace, and listen to your body."
        },
        "Arabic": {
            "weather": "كنت سأتحقق من الطقس الآن، لكنني غير متصل. في الخليج، فضّل المكيف وقت الذروة (11–16)، رطّب نفسك، واستخدم تبريدًا خفيفًا.",
            "journal": "كنت سأراجع اليوميات الآن. نصائح شائعة: الترطيب، تنظيم الجهد، والتبريد المبكر بعد التعرض للحرارة.",
            "travel": "للسفر: ملابس تبريد، أنشطة داخلية وقت الذروة، ترطيب، وتبريد مسبق قبل الخروج.",
            "symptoms": "محفزات شائعة: الشمس، الجفاف، رطوبة عالية. برّد المعصم/الرقبة، انتقل للمكيف، وارتح عند التعب.",
            "general": "أنا هنا لمساعدتك في إدارة الحرارة مع التصلب المتعدد. الأساسيات: ابقَ باردًا، رطّب، نظّم جهدك، واستمع لجسدك."
        }
    }
    if any(w in prompt_lower for w in ['weather','temperature','hot','heat','طقس','حرارة','حر']): k = "weather"
    elif any(w in prompt_lower for w in ['journal','entry','log','اليوميات','المذكرات','السجل']): k = "journal"
    elif any(w in prompt_lower for w in ['travel','trip','سفر','رحلة']): k = "travel"
    elif any(w in prompt_lower for w in ['symptom','pain','fatigue','numb','أعراض','ألم','تعب','خدر']): k = "symptoms"
    else: k = "general"
    base = fb["Arabic" if lang=="Arabic" else "English"][k]
    if weather_context and k=="weather": base += f"\n\n{weather_context}"
    return base

def _system_prompt(lang: str, username: str | None, prompt_text: str):
    """Builds a complete system prompt with prefs, journal, weather, and learned actions."""
    city_code = resolve_city_for_chat(prompt_text)
    wx = get_weather_context(city_code)
    journal = get_recent_journal_context(username, max_entries=5) if username else ""
    prefs = load_user_prefs(username) if username else {}
    ai_style = (prefs.get("ai_style") or "Concise")

    sys = (
        "You are Raha MS AI Companion — a warm, empathetic assistant for people with Multiple Sclerosis in the Gulf. "
        "Be practical, culturally aware (Arabic/English; prayer/fasting context), and action‑oriented. "
        "Never diagnose; focus on cooling, pacing, hydration, timing, and safety. "
        "Structure answers into three sections named exactly: 'Do now', 'Plan later', 'Watch for'. "
    )
    if (ai_style or "").lower().startswith("concise"):
        sys += "Start with one‑line summary. Keep each section ≤3 short bullets (≤12 words each). "
    else:
        sys += "Start with one‑line summary, then up to 5 bullets per section with brief rationale. "

    if journal and "No recent journal" not in journal:
        sys += f"\n\nUser's recent journal (summarized):\n{journal}"
    if wx:
        sys += f"\n\nWeather context:\n{wx}"
    if username:
        tops = _format_top_actions_str(username, lang)
        if tops:
            sys += f"\n\nPersonalized prior success:\n{tops}\nPrioritize these when appropriate."

    sys += " Respond only in Arabic." if lang == "Arabic" else " Respond only in English."
    return sys, (city_code or ""), wx

def ai_chat(prompt_text: str, lang: str):
    """OpenAI primary; DeepSeek fallback. Returns (text, error_str|None)."""
    username = st.session_state.get("user")
    sys, _, _ = _system_prompt(lang, username, prompt_text)
    messages = [{"role":"system","content":sys},{"role":"user","content":prompt_text}]
    st.session_state["ai_provider_last"] = None
    st.session_state["ai_last_error"] = None
    st.session_state["ai_last_finish_reason"] = None

    # Try OpenAI first
    if OPENAI_API_KEY:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type":"application/json"}
            data = {"model":"gpt-4o-mini","messages":messages,"temperature":0.7,"max_tokens":600,"stream":False}
            r = requests.post(url, headers=headers, json=data, timeout=20)
            r.raise_for_status()
            j = r.json()
            text = j["choices"][0]["message"]["content"]
            st.session_state["ai_provider_last"] = "OpenAI"
            st.session_state["ai_last_finish_reason"] = j["choices"][0].get("finish_reason","")
            return text, None
        except Exception as e:
            st.session_state["ai_last_error"] = f"OpenAI: {e}"

    # Fallback to DeepSeek
    if DEEPSEEK_API_KEY:
        try:
            url = "https://api.deepseek.com/chat/completions"
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type":"application/json"}
            data = {"model":"deepseek-chat","messages":messages,"temperature":0.7,"max_tokens":600,"stream":False}
            r = requests.post(url, headers=headers, json=data, timeout=20)
            r.raise_for_status()
            j = r.json()
            text = j["choices"][0]["message"]["content"]
            st.session_state["ai_provider_last"] = "DeepSeek"
            st.session_state["ai_last_finish_reason"] = j["choices"][0].get("finish_reason","")
            return text, None
        except Exception as e:
            st.session_state["ai_last_error"] = f"DeepSeek: {e}"

    # Nothing worked
    return None, "ai_unavailable"

# ================== ABOUT PAGE ==================
def render_about_page(lang: str = "English"):
    is_ar = (lang == "Arabic")
    def T_(en, ar): return ar if is_ar else en

    st.markdown(f"""
    <div style="padding:10px 12px;border:1px solid rgba(0,0,0,.06);border-radius:12px;background:
      linear-gradient(90deg, rgba(34,197,94,.10), rgba(14,165,233,.10));">
      <h2 style="margin:0">{'👋 أهلاً بك في' if is_ar else '👋 Welcome to'} <b>Tanzim MS</b></h2>
      <p style="margin:.2rem 0 0 0">
        {T_(
          "A Gulf‑aware companion that helps people with MS stay safer in the heat — by matching your readings to your personal baseline and actual local weather.",
          "رفيق مُصمَّم للخليج يساعد أشخاص التصلب المتعدد على الأمان في الحر — بمقارنة قراءاتك بخطّك الأساسي وطقسك المحلي الفعلي."
        )}
      </p>
    </div>
    """, unsafe_allow_html=True)

    colA, colB = st.columns([1,1])
    with colA:
        st.markdown("### " + T_("Why heat matters in MS", "لماذا تؤثر الحرارة في التصلب المتعدد"))
        st.markdown(T_(
            "- Even a ~0.5°C rise can worsen symptoms (Uhthoff’s phenomenon).\n"
            "- Humidity in the Gulf makes heat feel heavier and recovery slower.\n"
            "- Small, early actions (pre‑cool, shade/AC, pacing) prevent bad days.",
            "- حتى زيادة ≈ 0.5°م قد تُفاقم الأعراض (ظاهرة أوتهوف).\n"
            "- رطوبة الخليج تجعل الحر أثقل والتعافي أبطأ.\n"
            "- خطوات صغيرة مبكرة (تبريد مسبق، ظل/مكيّف، تنظيم الجهد) تمنع سوء الأيام."
        ))
    with colB:
        st.markdown("### " + T_("Start in 60 seconds", "ابدأ خلال 60 ثانية"))
        st.markdown(T_(
            "1. Open **Settings** → set *Baseline* and **Home City**.\n"
            "2. Visit **Monitor** → see core/peripheral vs feels‑like/humidity.\n"
            "3. Log one **Daily** entry in **Journal**.\n"
            "4. Ask the **AI Companion** for a safe window today.",
            "1. افتح **الإعدادات** → اضبط *الأساس* و**المدينة الأساسية**.\n"
            "2. زر **المراقبة** → شاهد الأساسية/الطرفية مقابل المحسوس/الرطوبة.\n"
            "3. سجّل **مدخلة يومية** في **اليوميات**.\n"
            "4. اسأل **المساعد** عن نافذة آمنة اليوم."
        ))

    st.markdown("---")
    st.markdown("### " + T_("What’s inside", "ماذا ستجد"))
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**📊 " + T_("Monitor", "المراقبة") + "**")
        st.caption(T_("Live temps vs baseline + alerts, written simply.", "قراءات مباشرة مقابل الأساس + تنبيهات، بشرح مبسط."))
        #if st.button(T_("Open Monitor", "افتح المراقبة"), key="go_monitor"): 
            #st.session_state["nav_radio"] = "monitor"; st.session_state["current_page"] = "monitor"; st.rerun()
    with c2:
        st.markdown("**🧭 " + T_("Planner", "المخطط") + "**")
        st.caption(T_("Safest 2‑hour windows for your city; instant tips.", "أفضل فترات لساعتين في مدينتك؛ نصائح فورية."))
        #if st.button(T_("Open Planner", "افتح المخطط"), key="go_planner"): 
            #st.session_state["nav_radio"] = "planner"; st.session_state["current_page"] = "planner"; st.rerun()
    with c3:
        st.markdown("**📒 " + T_("Journal", "اليوميات") + "**")
        st.caption(T_("Quick daily logs; export to share with your clinician.", "تسجيلات يومية سريعة؛ تصدير للمشاركة مع طبيبك."))
        #if st.button(T_("Open Journal", "افتح اليوميات"), key="go_journal"): 
            #st.session_state["nav_radio"] = "journal"; st.session_state["current_page"] = "journal"; st.rerun()
    with c4:
        st.markdown("**🤖 " + T_("AI Companion", "المرافق الذكي") + "**")
        st.caption(T_("Personal, bilingual guidance; aware of your city & logs.", "إرشاد شخصي ثنائي اللغة؛ واعٍ بمدينتك وسجلّك."))
        #if st.button(T_("Open Companion", "افتح المساعد"), key="go_assistant"): 
            #st.session_state["nav_radio"] = "assistant"; st.session_state["current_page"] = "assistant"; st.rerun()

    st.markdown("---")
    st.caption(T_(
        "Privacy: Your data stays on this device/database for your care. This app gives general wellness guidance — for severe or unusual symptoms, seek urgent medical care.",
        "الخصوصية: تبقى بياناتك على هذا الجهاز/قاعدة البيانات لرعايتك. يقدم التطبيق إرشادًا عامًا — عند أعراض شديدة أو غير معتادة، اطلب رعاية طبية فورية."
    ))

# ================== PLANNER ==================
def best_windows_from_forecast(forecast, window_hours=2, top_k=8, max_feels_like=35.0, max_humidity=65, avoid_hours=(10,16)):
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
        start_dt = _dt.strptime(group[0]["time"][:16], "%Y-%m-%d %H:%M")
        end_dt = (_dt.strptime(group[-1]["time"][:16], "%Y-%m-%d %H:%M") + timedelta(hours=3)) if len(group)>1 else (start_dt + timedelta(hours=3))
        cand.append({ "start_dt": start_dt, "end_dt": end_dt, "avg_feels": avg_feels, "avg_hum": avg_hum })
    cand.sort(key=lambda x: x["start_dt"])
    return cand[:top_k]

def render_planner():
    st.title("🗺️ " + T["planner"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return
    # Determine city: use current or prefs
    default_city = st.session_state.get("current_city")
    if not default_city:
        prefs = load_user_prefs(st.session_state["user"])
        default_city = prefs.get("home_city") or "Abu Dhabi,AE"
    city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=GCC_CITIES.index(default_city) if default_city in GCC_CITIES else 0,
                        key="planner_city", format_func=lambda c: city_label(c, app_language))
    weather, err = get_weather(city)
    if weather is None:
        st.error(f"{T['weather_fail']}: {err}"); return

    tabs = st.tabs(["✅ " + ("Best windows" if app_language=="English" else "أفضل الأوقات"),
                    "🤔 " + ("What‑if" if app_language=="English" else "ماذا لو"),
                    "📍 " + ("Places" if app_language=="English" else "الأماكن")])

    with tabs[0]:
        st.caption("We scanned the next 48h for cooler 2‑hour windows." if app_language=="English" else "فحصنا الـ48 ساعة القادمة للعثور على فترات أكثر برودة (ساعتين).")
        windows = best_windows_from_forecast(weather["forecast"], window_hours=2, top_k=12, max_feels_like=35.0, max_humidity=65)
        if not windows:
            st.info("No optimal windows found; consider early morning or after sunset."
                    if app_language == "English" else "لم يتم العثور على فترات مثالية؛ فكر في الصباح الباكر أو بعد الغروب.")
        else:
            # Localized headers
            if app_language == "Arabic":
                COL_DATE, COL_START, COL_END, COL_FEELS, COL_HUM = "التاريخ","البداية","النهاية","المحسوسة (°م)","الرطوبة (%)"
            else:
                COL_DATE, COL_START, COL_END, COL_FEELS, COL_HUM = "Date","Start","End","Feels-like (°C)","Humidity (%)"
            windows_sorted = sorted(windows, key=lambda x: x["start_dt"])
            rows = [{"idx":i,
                     COL_DATE: w["start_dt"].strftime("%a %d %b"),
                     COL_START: w["start_dt"].strftime("%H:%M"),
                     COL_END: w["end_dt"].strftime("%H:%M"),
                     COL_FEELS: round(w["avg_feels"],1),
                     COL_HUM: int(w["avg_hum"])} for i,w in enumerate(windows_sorted)]
            df = pd.DataFrame(rows)
            st.dataframe(df.drop(columns=["idx"]), hide_index=True, use_container_width=True)

            st.markdown("##### " + ("Add a plan" if app_language=="English" else "أضف خطة"))
            colA, colB = st.columns([2,1])
            with colA:
                def labeler(r):
                    if app_language == "Arabic":
                        return f"{r[COL_DATE]} • {r[COL_START]}–{r[COL_END]} (≈{r[COL_FEELS]}°م, {r[COL_HUM]}%)"
                    else:
                        return f"{r[COL_DATE]} • {r[COL_START]}–{r[COL_END]} (≈{r[COL_FEELS]}°C, {r[COL_HUM]}%)"
                options = [labeler(r) for r in rows]
                pick_label = st.selectbox(("Choose a slot" if app_language=="English" else "اختر فترة"), options, index=0, key="plan_pick")
                pick_idx = rows[options.index(pick_label)]["idx"]; chosen = windows_sorted[pick_idx]
            with colB:
                activities = ["Walk","Groceries","Beach","Errand"] if app_language=="English" else ["مشي","تسوق","شاطئ","مهمة"]
                act = st.selectbox(("Plan" if app_language=="English" else "خطة"), activities, key="plan_act")
                other_act = st.text_input(("Other activity (optional)" if app_language=="English" else "نشاط آخر (اختياري)"), key="plan_act_other")
                final_act = other_act.strip() if other_act.strip() else act
                if st.button(("Add to Journal" if app_language=="English" else "أضف إلى اليوميات"), key="btn_add_plan"):
                    entry = {
                        "type":"PLAN","at": utc_iso_now(),"city": city,
                        "start": chosen["start_dt"].strftime("%Y-%m-%d %H:%M"),
                        "end": chosen["end_dt"].strftime("%Y-%m-%d %H:%M"),
                        "activity": final_act,
                        "feels_like": round(chosen["avg_feels"], 1),
                        "humidity": int(chosen["avg_hum"])
                    }
                    insert_journal(st.session_state["user"], utc_iso_now(), entry)
                    st.success("Saved to Journal" if app_language=="English" else "تم الحفظ في اليوميات")

    with tabs[1]:
        st.caption("Try a plan now and get instant tips." if app_language=="English" else "جرب خطة الآن واحصل على نصائح فورية.")
        col1, col2 = st.columns([2,1])
        with col1:
            activity_options = ["Light walk (20–30 min)", "Moderate exercise (45 min)", "Outdoor errand (30–60 min)", "Beach (60–90 min)"] \
                if app_language=="English" else ["مشي خفيف (20-30 دقيقة)", "تمرين متوسط (45 دقيقة)", "مهمة خارجية (30-60 دقيقة)", "شاطئ (60-90 دقيقة)"]
            what_act = st.selectbox(("Activity" if app_language=="English" else "النشاط"), activity_options, key="what_if_act")
            dur = st.slider(("Duration (minutes)" if app_language=="English" else "المدة (دقائق)"), 10, 120, 45, 5, key="what_if_dur")
            indoor = st.radio(("Location" if app_language=="English" else "الموقع"), ["Outdoor","Indoor/AC"] if app_language=="English" else ["خارجي","داخلي/مكيف"], horizontal=True, key="what_if_loc")
            other_notes = st.text_area(("Add notes (optional)" if app_language=="English" else "أضف ملاحظات (اختياري)"), height=80, key="what_if_notes")
        with col2:
            fl = weather["feels_like"]; hum = weather["humidity"]
            go_badge = ("🟢 Go" if (fl < 34 and hum < 60) else ("🟡 Caution" if (fl < 37 and hum < 70) else "🔴 Avoid now")) \
                        if app_language=="English" else ("🟢 اذهب" if (fl < 34 and hum < 60) else ("🟡 احترس" if (fl < 37 and hum < 70) else "🔴 تجنب الآن"))
            st.markdown(f"**{'Now' if app_language=='English' else 'الآن'}:** {go_badge} — feels‑like {round(fl,1)}°C, humidity {int(hum)}%")
            tips_now = []
            low = what_act.lower()
            if "walk" in low or "مشي" in low:
                tips_now += ["Shaded route","Carry cool water","Light clothing"] if app_language=="English" else ["مسار مظلل","احمل ماءً باردًا","ملابس خفيفة"]
            if "exercise" in low or "تمرين" in low or "تمري" in low:
                tips_now += ["Pre‑cool 15 min","Prefer indoor/AC","Electrolytes if >45 min"] if app_language=="English" else ["تبريد مسبق 15 دقيقة","افضل الداخلي/مكيف","إلكتروليتات إذا المدة >45 دقيقة"]
            if "errand" in low or "مهمة" in low:
                tips_now += ["Park in shade","Shortest route","Pre‑cool car 5–10 min"] if app_language=="English" else ["اركن في الظل","أقصر طريق","تبريد السيارة مسبقًا 5–10 دقائق"]
            if "beach" in low or "شاطئ" in low:
                tips_now += ["Umbrella & UV hat","Cooling towel","Rinse to cool"] if app_language=="English" else ["مظلة وقبعة واقية","منشفة تبريد","اشطف للتبريد"]
            if fl >= 36:
                tips_now += ["Cooling scarf/bandana","Use a cooler window"] if app_language=="English" else ["وشاح تبريد","اختر نافذة أبرد"]
            if hum >= 60:
                tips_now += ["Prefer AC over fan","Extra hydration"] if app_language=="English" else ["افضل المكيف على المروحة","ترطيب إضافي"]
            tips_now = list(dict.fromkeys(tips_now))[:8]
            st.markdown("**" + ("Tips" if app_language=="English" else "نصائح") + ":**")
            st.markdown("- " + "\n- ".join(tips_now) if tips_now else "—")
            if (OPENAI_API_KEY or DEEPSEEK_API_KEY) and st.button(("Ask AI for tailored tips" if app_language=="English" else "اسأل الذكاء لنصائح مخصصة"), key="what_if_ai"):
                q = f"My plan: {what_act} for {dur} minutes. Location: {indoor}. Notes: {other_notes}. Current feels-like {round(fl,1)}°C, humidity {int(hum)}%."
                ans, _ = ai_chat(q, app_language)
                st.info(ans if ans else (T["ai_unavailable"]))

    with tabs[2]:
        st.caption("Check a specific place in your city, like a beach or park." if app_language=="English" else "تحقق من مكان محدد في مدينتك، مثل شاطئ أو حديقة.")
        place_q = st.text_input(("Place name (e.g., Saadiyat Beach)" if app_language=="English" else "اسم المكان (مثال: شاطئ السعديات)"), key="place_q")
        if place_q:
            place, lat, lon = geocode_place(place_q)
            pw = get_weather_by_coords(lat, lon) if (lat and lon) else None
            if pw:
                st.info(f"**{place}** — feels‑like {round(pw['feels_like'],1)}°C • humidity {int(pw['humidity'])}% • {pw['desc']}")
                better = "place" if pw["feels_like"] < weather["feels_like"] else "city"
                st.caption(f"{'Cooler now' if app_language=='English' else 'أبرد الآن'}: **{place if better=='place' else city}**")
                if st.button(("Plan here for the next hour" if app_language=="English" else "خطط هنا للساعة القادمة"), key="place_plan"):
                    now_dxb = datetime.now(TZ_DUBAI)
                    entry = {
                        "type":"PLAN","at": utc_iso_now(),"city": place,
                        "start": now_dxb.strftime("%Y-%m-%d %H:%M"),
                        "end": (now_dxb + timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M"),
                        "activity": "Visit" if app_language=="English" else "زيارة",
                        "feels_like": round(pw['feels_like'],1),"humidity": int(pw['humidity'])
                    }
                    insert_journal(st.session_state["user"], utc_iso_now(), entry)
                    st.success(("Planned & saved" if app_language=="English" else "تم التخطيط والحفظ"))
            else:
                st.warning(("Couldn't fetch that place's weather." if app_language=="English" else "تعذر جلب طقس هذا المكان."))
        st.caption(f"**Peak heat next 48h:** " + ("; ".join(weather.get('peak_hours', [])) if weather.get('peak_hours') else "—"))

# ================== MONITOR (with Sensors Explainer + Recovery Logger) ==================
_LEVEL_BY_STATUS = {"Safe":0,"Caution":1,"High":2,"Danger":3}
def _risk_level(status: str) -> int:
    return _LEVEL_BY_STATUS.get(str(status), 0)

def render_monitor():
    st.title("☀️ " + T["risk_dashboard"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    tabs = st.tabs(["📡 " + ("Live Sensor Data" if app_language=="English" else "بيانات مباشرة"),
                    "🔬 " + ("Learn & Practice" if app_language=="English" else "تعلّم وتدرّب")])

    with tabs[0]:
        with st.expander("🔎 " + ("About sensors & temperatures" if app_language=="English" else "عن المستشعرات والقراءات"), expanded=False):
            if app_language=="English":
                st.markdown("""
**Hardware (what’s collecting data):**
- **MAX30205** — medical‑grade digital thermometer on skin → **Peripheral** temperature (±0.1°C).
- **MLX90614** — infrared sensor estimating internal body temp → **Core** (±0.5°C typical).
- **ESP8266** — small Wi‑Fi board that reads sensors and sends data to the app.

**The 4 temperatures you’ll see:**
- **Core** — internal body temp; most linked to heat stress. *Typical resting ~36.5–37.2°C*.
- **Peripheral** — skin temp; responds quickly to the environment. *Usually < Core indoors*.
- **Feels‑like** — what the weather *feels* like outdoors (air + humidity). *High humidity makes cooling harder*.
- **Baseline** — **your** usual core temperature (set in **Settings**). We flag rises **≥0.5°C** above this.

**How to use them together:**
- If **Core ↑ ~0.5°C** vs **Baseline** → pre‑cool, AC/shade, water, rest **15–20 min**.
- If **Feels‑like ≥ 38–42°C** or **Humidity ≥ 60%** → shorten outings; choose cooler windows.
- Improving from **High/Danger → Caution/Safe**? Use **“Log what helped”** to teach the app what works **for you**.
""")
            else:
                st.markdown("""
**العتاد (ما الذي يجمع البيانات):**
- **MAX30205** — ميزان حرارة رقمي طبي على الجلد → **الطرفية** (±0.1°م).
- **MLX90614** — مستشعر تحت الحمراء يقدّر الحرارة الداخلية → **الأساسية** (±0.5°م تقريبيًا).
- **ESP8266** — لوحة Wi‑Fi صغيرة تقرأ المستشعرات وترسل البيانات للتطبيق.

**القراءات الأربع التي تراها:**
- **الأساسية** — حرارة الجسم الداخلية؛ الأكثر ارتباطًا بالإجهاد الحراري. *الراحة ~36.5–37.2°م*.
- **الطرفية** — حرارة الجلد؛ تتأثر بسرعة بالبيئة. *غالبًا أقل من الأساسية داخل المباني*.
- **المحسوسة** — ما **نشهده** في الخارج (هواء + رطوبة). *الرطوبة العالية تصعّب التبريد*.
- **خط الأساس** — حرارتك المعتادة (**اضبطها في الإعدادات**). ننبه عند الارتفاع **≥0.5°م** فوقها.

**كيف تستخدمها معًا:**
- إذا **ارتفعت الأساسية ~0.5°م** فوق **الأساس** → تبريد مسبق، مكيّف/ظل، ماء، راحة **15–20 دقيقة**.
- إذا **المحسوسة ≥ 38–42°م** أو **الرطوبة ≥ 60%** → قِصّر الخروج؛ اختر أوقاتًا أبرد.
- تحسّن من **مرتفع/حرج → حذر/آمن**؟ استخدم **“سجّل ما ساعدك”** ليَتعلَّم التطبيق ما يناسبك.
""")

        # Top row
        # City: prefer current session city or user home city
        default_city = st.session_state.get("current_city")
        if not default_city and "user" in st.session_state:
            prefs = load_user_prefs(st.session_state["user"])
            default_city = prefs.get("home_city") or "Abu Dhabi,AE"
        colA, colB, colC, colD = st.columns([1.3,1.1,1,1.3])
        with colA:
            city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=GCC_CITIES.index(default_city) if default_city in GCC_CITIES else 0,
                                key="monitor_city", format_func=lambda c: city_label(c, app_language))
            st.session_state["current_city"] = city
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
                    st.session_state["live_running"] = True
                else:
                    st.error("❌ No sensor data found. Check device/Supabase." if app_language=="English"
                             else "❌ لا توجد بيانات مستشعر. تحقق من الجهاز/Supabase.")
        with colD:
            st.markdown(f"<div class='badge'>{'Baseline' if app_language=='English' else 'الأساس'}: "
                        f"<strong>{st.session_state.get('baseline', 37.0):.1f}°C</strong></div>", unsafe_allow_html=True)

        # Weather & sample
        weather, w_err, fetched_ts = get_weather_cached(city)
        sample = fetch_latest_sensor_sample("esp8266-01")

        col1, col2, col3, col4 = st.columns(4)
        if sample:
            with col1:
                delta = sample['core'] - st.session_state.get('baseline', 37.0)
                st.metric("Core" if app_language=="English" else "الأساسية",
                          f"{sample['core']:.1f}°C", f"{delta:+.1f}°C",
                          delta_color="inverse" if delta>=0.5 else "normal")
            with col2:
                st.metric("Peripheral" if app_language=="English" else "الطرفية",
                          f"{sample['peripheral']:.1f}°C")
        else:
            with col1:
                st.info("🔌 No live sensor data" if app_language=="English" else "🔌 لا توجد بيانات مباشرة")
        with col3:
            st.metric(("Feels‑like" if app_language=="English" else "المحسوسة"),
                      f"{weather['feels_like']:.1f}°C" if weather else "—")
        with col4:
            st.metric(("Humidity" if app_language=="English" else "الرطوبة"),
                      f"{int(weather['humidity'])}%" if weather else "—")

        # Risk + alerts
        risk = None
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
            st.error(f"{T['weather_fail']}: {w_err or '—'}")

        if st.button(T["refresh_weather"], key="refresh_weather_btn"):
            get_weather.clear(); st.session_state["_weather_cache"] = {}; st.rerun()

        # ----- Recovery Logger (manual + automatic on improvement) -----
        if weather and sample:
            curr = {
                "status": risk["status"] if risk else "Safe",
                "level": _risk_level(risk["status"] if risk else "Safe"),
                "time_iso": utc_iso_now(),
                "core": float(sample["core"]),
                "periph": float(sample.get("peripheral", 0.0)),
                "feels": float(weather["feels_like"]),
                "humidity": float(weather["humidity"]),
                "city": city
            }
            prev = st.session_state.get("_risk_track")

            # Manual logging
            with st.expander(("Log a cooling action" if app_language=="English" else "سجّل إجراء تبريد"), expanded=False):
                with st.form("manual_recovery_form", clear_on_submit=True):
                    acts = st.multiselect(("What did you do?" if app_language=="English" else "ماذا فعلت؟"), _actions_for_lang(app_language))
                    note = st.text_area(("Details (optional)" if app_language=="English" else "تفاصيل (اختياري)"), height=70)
                    if st.form_submit_button("Save" if app_language=="English" else "حفظ"):
                        entry = {"type":"RECOVERY","at": utc_iso_now(),"from_status": curr["status"],"to_status": curr["status"],
                                 "actions": acts,"note": note.strip(),
                                 "core_before": None,"core_after": curr["core"],
                                 "peripheral_before": None,"peripheral_after": curr["periph"],
                                 "feels_like_before": None,"feels_like_after": curr["feels"],
                                 "humidity_before": None,"humidity_after": curr["humidity"],
                                 "city": city,"duration_min": None}
                        insert_journal(st.session_state["user"], utc_iso_now(), entry)
                        st.success("Saved" if app_language=="English" else "تم الحفظ")

            # Automatic prompt if risk improved
            if prev and (curr["level"] < prev["level"]):
                st.success(("✅ Improved: {0} → {1}. What helped?".format(prev["status"], curr["status"])
                            if app_language=="English" else
                            f"✅ تحسُّن: {prev['status']} ← {curr['status']}. ما الذي ساعد؟"))
                with st.form("auto_recovery_form", clear_on_submit=True):
                    acts2 = st.multiselect(("Choose actions" if app_language=="English" else "اختر الإجراءات"), _actions_for_lang(app_language))
                    note2 = st.text_area(("Details (optional)" if app_language=="English" else "تفاصيل (اختياري)"), height=70)
                    colx, coly = st.columns([1,1])
                    with colx:
                        save_clicked = st.form_submit_button("Save" if app_language=="English" else "حفظ")
                    with coly:
                        dismiss_clicked = st.form_submit_button("Dismiss" if app_language=="English" else "تجاهل")
                if save_clicked:
                    t1 = _dt.fromisoformat(prev["time_iso"].replace("Z","+00:00"))
                    t2 = _dt.fromisoformat(curr["time_iso"].replace("Z","+00:00"))
                    dur = int((t2 - t1).total_seconds() // 60) if t2 and t1 else None
                    entry = {"type":"RECOVERY","at": utc_iso_now(),
                             "from_status": prev["status"],"to_status": curr["status"],
                             "actions": acts2,"note": note2.strip(),
                             "core_before": round(prev["core"],2) if prev.get("core") is not None else None,
                             "core_after": round(curr["core"],2),
                             "peripheral_before": round(prev.get("periph",0.0),2) if prev.get("periph") is not None else None,
                             "peripheral_after": round(curr["periph"],2),
                             "feels_like_before": round(prev.get("feels",0.0),2) if prev.get("feels") is not None else None,
                             "feels_like_after": round(curr["feels"],2),
                             "humidity_before": int(prev.get("humidity",0)) if prev.get("humidity") is not None else None,
                             "humidity_after": int(curr["humidity"]),
                             "city": city,"duration_min": dur}
                    insert_journal(st.session_state["user"], utc_iso_now(), entry)
                    st.success("✅ Saved — thanks! This teaches your assistant what works for you."
                               if app_language=="English" else "✅ تم الحفظ — شكرًا! هذا يعلّم مساعدك ما يناسبك.")
                    st.session_state["_risk_track"] = curr
                elif dismiss_clicked:
                    st.session_state["_risk_track"] = curr
            else:
                st.session_state["_risk_track"] = curr

        # Show top actions
        if "user" in st.session_state:
            tops = get_top_actions_counts(st.session_state["user"], 30)
            if tops:
                st.markdown("---")
                st.markdown("**💡 " + ("What helps you most (last 30 days)" if app_language=="English" else "ما يساعدك غالبًا (آخر 30 يومًا)") + "**")
                chip_css = """
                <style>.chip { display:inline-block; padding:6px 10px; margin:4px 6px; border:1px solid rgba(0,0,0,.15);
                               border-radius:999px; font-size:0.95em; }
                @media (prefers-color-scheme: dark){ .chip { border-color: rgba(255,255,255,.25); } }
                </style>"""
                st.markdown(chip_css, unsafe_allow_html=True)
                html = "".join([f"<span class='chip'>{a} ×{n}</span>" for a,n in tops])
                st.markdown(html, unsafe_allow_html=True)

        # Trend chart with sampling interval
        st.markdown("---"); st.subheader(T["temperature_trend"])
        label_mode = st.radio(("X‑axis" if app_language=="English" else "المحور السيني"),
                              options=(["Time only","Date & Time"] if app_language=="English" else ["الوقت فقط","التاريخ + الوقت"]),
                              horizontal=True, key="trend_label_mode")
        c = get_conn().cursor()
        c.execute("""
            SELECT date, body_temp, peripheral_temp, weather_temp, feels_like, status
            FROM temps WHERE username=? ORDER BY date DESC LIMIT 50
        """, (st.session_state.get("user","guest"),))
        rows = c.fetchall()
        if rows:
            rows = rows[::-1]
            ts = []
            for d in [r[0] for r in rows]:
                try: dt = _dt.fromisoformat(d.replace("Z","+00:00"))
                except Exception: dt = _dt.now(timezone.utc)
                ts.append(dt.astimezone(TZ_DUBAI))
            if len(ts) >= 2:
                gaps = [(ts[i]-ts[i-1]).total_seconds()/60 for i in range(1,len(ts))]
                median_gap = statistics.median(gaps)
            else:
                median_gap = None
            core  = [r[1] for r in rows]
            perph = [r[2] for r in rows]
            feels = [(r[4] if r[4] is not None else r[3]) for r in rows]
            fig, ax = plt.subplots(figsize=(10,4))
            if app_language=="Arabic":
                lbl_core, lbl_peri, lbl_feels = ar_shape("الأساسية"), ar_shape("الطرفية"), ar_shape("المحسوسة")
            else:
                lbl_core, lbl_peri, lbl_feels = "Core","Peripheral","Feels‑like"
            ax.plot(range(len(ts)), core, marker='o', label=lbl_core, linewidth=2)
            ax.plot(range(len(ts)), perph, marker='o', label=lbl_peri, linewidth=1.8)
            ax.plot(range(len(ts)), feels, marker='s', label=lbl_feels, linewidth=1.8)
            ax.set_xticks(range(len(ts)))
            xt = [t.strftime("%d %b • %H:%M") for t in ts] if ((label_mode == "Date & Time") or (label_mode == "التاريخ + الوقت")) \
                 else [t.strftime("%H:%M") for t in ts]
            ax.set_xticklabels(xt, rotation=45, fontsize=9)
            ax.set_ylabel("°C" if app_language=="English" else "°م", fontproperties=_AR_FONT)
            ax.legend(prop=_AR_FONT); ax.grid(True, alpha=0.3)
            ax.set_title(ar_shape("الأساسية مقابل الطرفية مقابل المحسوسة") if app_language=="Arabic" else "Core vs Peripheral vs Feels‑like", fontproperties=_AR_FONT)
            st.pyplot(fig)
            cap = "Timezone: Asia/Dubai"
            if median_gap is not None:
                cap = (f"Sampling: ~{median_gap:.0f} min between points • " + cap) if app_language=="English" \
                      else (f"التقاط: ~{median_gap:.0f} دقيقة بين النقاط • " + cap)
            st.caption(cap)
        else:
            st.info("No temperature history to chart yet." if app_language=="English" else "لا يوجد سجل درجات لعرضه.")

    with tabs[1]:
        if app_language == "English":
            st.info("🎯 **Interactive Learning** - Practice recognizing temperature patterns and learn effective cooling strategies")
        else:
            st.info("🎯 **تعلم تفاعلي** - تدرب على التعرف على أنماط درجة الحرارة وتعلم استراتيجيات التبريد الفعالة")
        
        # Initialize session state for simulator
        if "sim" not in st.session_state:
            st.session_state.sim = {"core": 36.6, "baseline": st.session_state.get("baseline", 36.8), "feels": 32.0}
        if "sim_history" not in st.session_state:
            st.session_state.sim_history = []
        if "sim_live" not in st.session_state:
            st.session_state.sim_live = False

        # Scenarios with explanations
        if app_language == "English":
            scenarios = {
                "Morning commute (Dubai summer)": {
                    "core": 37.4, 
                    "feels": 41.0,
                    "desc": "Hot car, sun exposure through windows, limited airflow"
                },
                "Moderate exercise (humid day)": {
                    "core": 37.9, 
                    "feels": 39.0,
                    "desc": "Physical activity + high humidity impairs cooling"
                },
                "Office AC failure": {
                    "core": 37.8, 
                    "feels": 35.0,
                    "desc": "Indoor heat buildup without ventilation"
                },
                "Evening walk (cooler hours)": {
                    "core": 37.0, 
                    "feels": 34.0,
                    "desc": "Better timing, but still warm"
                },
                "Fever at home": {
                    "core": 38.2, 
                    "feels": 28.0,
                    "desc": "Internal rise despite cool environment"
                },
                "Car breakdown (direct sun)": {
                    "core": 37.8, 
                    "feels": 44.0,
                    "desc": "Trapped heat, high radiant temperature"
                },
            }
        else:
            scenarios = {
                "تنقل الصباح (صيف دبي)": {
                    "core": 37.4, 
                    "feels": 41.0,
                    "desc": "سيارة ساخنة، تعرض للشمس من النوافذ، تدفق هواء محدود"
                },
                "تمارين متوسطة (يوم رطب)": {
                    "core": 37.9, 
                    "feels": 39.0,
                    "desc": "نشاط بدني + رطوبة عالية تعيق التبريد"
                },
                "عطل في مكيف المكتب": {
                    "core": 37.8, 
                    "feels": 35.0,
                    "desc": "تراكم الحرارة الداخلية بدون تهوية"
                },
                "مشي المساء (ساعات أكثر برودة)": {
                    "core": 37.0, 
                    "feels": 34.0,
                    "desc": "توقيت أفضل، لكن لا يزال دافئًا"
                },
                "حمى في المنزل": {
                    "core": 38.2, 
                    "feels": 28.0,
                    "desc": "ارتفاع داخلي رغم البيئة الباردة"
                },
                "عطل سيارة ( تحت الشمس المباشرة)": {
                    "core": 37.8, 
                    "feels": 44.0,
                    "desc": "حرارة محبوسة، درجة حرارة إشعاعية عالية"
                },
            }

        col1, col2 = st.columns([1, 1])
        
        with col1:
            if app_language == "English":
                st.subheader("🔍 Try Different Scenarios")
                scenario_label = "Choose a scenario"
                apply_label = "Apply Scenario"
            else:
                st.subheader("🔍 جرب سيناريوهات مختلفة")
                scenario_label = "اختر سيناريو"
                apply_label = "تطبيق السيناريو"
                
            pick = st.selectbox(scenario_label, list(scenarios.keys()))
            
            st.caption(scenarios[pick]["desc"])
            
            if st.button(apply_label, use_container_width=True):
                st.session_state.sim["core"] = scenarios[pick]["core"]
                st.session_state.sim["feels"] = scenarios[pick]["feels"]
                st.session_state.sim_history.append({
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "core": float(st.session_state.sim["core"]),
                    "baseline": float(st.session_state.sim["baseline"]),
                    "feels": float(st.session_state.sim["feels"]),
                })
                st.rerun()

        with col2:
            if app_language == "English":
                st.subheader("⚙️ Adjust Values")
                core_label = "Core Temperature (°C)"
                baseline_label = "Baseline (°C)"
                feels_label = "Feels-like (°C)"
                core_help = "Your internal body temperature"
                baseline_help = "Your personal normal temperature"
                feels_help = "Combined effect of temperature + humidity"
            else:
                st.subheader("⚙️ ضبط القيم")
                core_label = "درجة الحرارة الأساسية (°م)"
                baseline_label = "خط الأساس (°م)"
                feels_label = "درجة الحرارة المحسوسة (°م)"
                core_help = "درجة حرارة جسمك الداخلية"
                baseline_help = "درجة حرارتك الطبيعية الشخصية"
                feels_help = "التأثير المشترك لدرجة الحرارة والرطوبة"
                
            s = st.session_state.sim
            
            s["core"] = st.slider(core_label, 36.0, 39.5, float(s["core"]), 0.1, help=core_help)
            s["baseline"] = st.slider(baseline_label, 36.0, 37.5, float(s["baseline"]), 0.1, help=baseline_help)
            s["feels"] = st.slider(feels_label, 25.0, 50.0, float(s["feels"]), 1.0, help=feels_help)

        # =========================
        # INTERACTIVE SOLUTIONS
        # =========================
        st.markdown("---")
        if app_language == "English":
            st.subheader("🛠️ Try Cooling Solutions")
            st.info("Click on solutions below to see how they affect your temperature:")
        else:
            st.subheader("🛠️ جرب حلول التبريد")
            st.info("انقر على الحلول أدناه لترى كيف تؤثر على درجة حرارتك:")
        
        sol_col1, sol_col2, sol_col3, sol_col4 = st.columns(4)
        
        with sol_col1:
            if app_language == "English":
                btn_label = "❄️ Cooling Vest"
                success_msg = "Cooling vest applied! Core ↓0.6°C, Feels-like ↓3°C"
            else:
                btn_label = "❄️ سترة تبريد"
                success_msg = "تم تطبيق سترة التبريد! الأساسية ↓0.6°C, المحسوسة ↓3°C"
                
            if st.button(btn_label, use_container_width=True):
                st.session_state.sim["core"] = max(st.session_state.sim["baseline"], 
                                                 st.session_state.sim["core"] - 0.6)
                st.session_state.sim["feels"] = max(25.0, st.session_state.sim["feels"] - 3.0)
                st.success(success_msg)
                st.rerun()
                
        with sol_col2:
            if app_language == "English":
                btn_label = "🏠 Move Indoors"
                success_msg = "Moved to AC! Feels-like →26°C, Core ↓0.4°C"
            else:
                btn_label = "🏠 الانتقال للداخل"
                success_msg = "انتقلت إلى المكيف! المحسوسة →26°C, الأساسية ↓0.4°C"
                
            if st.button(btn_label, use_container_width=True):
                st.session_state.sim["feels"] = 26.0
                st.session_state.sim["core"] = max(st.session_state.sim["baseline"], 
                                                 st.session_state.sim["core"] - 0.4)
                st.success(success_msg)
                st.rerun()
                
        with sol_col3:
            if app_language == "English":
                btn_label = "💧 Hydrate"
                success_msg = "Hydrated! Core ↓0.3°C"
            else:
                btn_label = "💧 ترطيب"
                success_msg = "تم الترطيب! الأساسية ↓0.3°C"
                
            if st.button(btn_label, use_container_width=True):
                st.session_state.sim["core"] = max(st.session_state.sim["baseline"], 
                                                 st.session_state.sim["core"] - 0.3)
                st.success(success_msg)
                st.rerun()
                
        with sol_col4:
            if app_language == "English":
                btn_label = "🌳 Rest in Shade"
                success_msg = "Resting in shade! Feels-like ↓8°C, Core ↓0.5°C"
            else:
                btn_label = "🌳 الراحة في الظل"
                success_msg = "الراحة في الظل! المحسوسة ↓8°C, الأساسية ↓0.5°C"
                
            if st.button(btn_label, use_container_width=True):
                st.session_state.sim["feels"] = max(25.0, st.session_state.sim["feels"] - 8.0)
                st.session_state.sim["core"] = max(st.session_state.sim["baseline"], 
                                                 st.session_state.sim["core"] - 0.5)
                st.success(success_msg)
                st.rerun()

        # Additional solutions
        sol_col5, sol_col6, sol_col7, sol_col8 = st.columns(4)
        
        with sol_col5:
            if app_language == "English":
                btn_label = "🚿 Cool Shower"
                success_msg = "Cool shower! Core ↓0.8°C, Feels-like ↓2°C"
            else:
                btn_label = "🚿 دش بارد"
                success_msg = "دش بارد! الأساسية ↓0.8°C, المحسوسة ↓2°C"
                
            if st.button(btn_label, use_container_width=True):
                st.session_state.sim["core"] = max(st.session_state.sim["baseline"], 
                                                 st.session_state.sim["core"] - 0.8)
                st.session_state.sim["feels"] = max(25.0, st.session_state.sim["feels"] - 2.0)
                st.success(success_msg)
                st.rerun()
                
        with sol_col6:
            if app_language == "English":
                btn_label = "🍃 Use Fan"
                success_msg = "Fan running! Feels-like ↓4°C, Core ↓0.2°C"
            else:
                btn_label = "🍃 استخدام مروحة"
                success_msg = "المروحة تعمل! المحسوسة ↓4°C, الأساسية ↓0.2°C"
                
            if st.button(btn_label, use_container_width=True):
                st.session_state.sim["feels"] = max(25.0, st.session_state.sim["feels"] - 4.0)
                st.session_state.sim["core"] = max(st.session_state.sim["baseline"], 
                                                 st.session_state.sim["core"] - 0.2)
                st.success(success_msg)
                st.rerun()
                
        with sol_col7:
            if app_language == "English":
                btn_label = "⏰ Rest 30min"
                success_msg = "Rested! Core ↓0.7°C"
            else:
                btn_label = "⏰ راحة 30 دقيقة"
                success_msg = "تمت الراحة! الأساسية ↓0.7°C"
                
            if st.button(btn_label, use_container_width=True):
                st.session_state.sim["core"] = max(st.session_state.sim["baseline"], 
                                                 st.session_state.sim["core"] - 0.7)
                st.success(success_msg)
                st.rerun()
                
        with sol_col8:
            if app_language == "English":
                btn_label = "🔄 Reset"
                success_msg = "Reset to normal values"
            else:
                btn_label = "🔄 إعادة تعيين"
                success_msg = "تم إعادة التعيين إلى القيم الطبيعية"
                
            if st.button(btn_label, use_container_width=True, type="secondary"):
                st.session_state.sim_history.clear()
                st.session_state.sim = {"core": 36.6, "baseline": st.session_state.get("baseline", 36.8), "feels": 32.0}
                st.success(success_msg)
                st.rerun()

        # =========================
        # STATUS AND VISUALIZATION
        # =========================
        st.markdown("---")
        
        col_status, col_chart = st.columns([1, 2])
        
        with col_status:
            if app_language == "English":
                st.subheader("📊 Current Status")
            else:
                st.subheader("📊 الحالة الحالية")
            
            # Classification logic
            def _classify(core, base, feels):
                delta = core - base
                level = 0
                trig = []
                if delta >= 0.5: 
                    level = max(level, 1)
                    trig.append(f"ΔCore +{delta:.1f}°C ≥ 0.5°C")
                if core >= 38.5: 
                    level = 3
                    trig.append("Core ≥ 38.5°C")
                elif core >= 38.0: 
                    level = max(level, 2)
                    trig.append("Core ≥ 38.0°C")
                elif core >= 37.8: 
                    level = max(level, 1)
                    trig.append("Core ≥ 37.8°C")
                if feels >= 42.0: 
                    level = max(level, 2)
                    trig.append("Feels-like ≥ 42°C")
                elif feels >= 38.0: 
                    level = max(level, 1)
                    trig.append("Feels-like ≥ 38°C")
                return ["safe", "caution", "high", "critical"][level], trig

            key, trig = _classify(st.session_state.sim["core"], 
                                st.session_state.sim["baseline"], 
                                st.session_state.sim["feels"])
            
            colors = {"safe": "#E6F4EA", "caution": "#FFF8E1", "high": "#FFE0E0", "critical": "#FFCDD2"}
            emojis = {"safe": "✅", "caution": "⚠️", "high": "🔴", "critical": "🚨"}
            
            if app_language == "English":
                status_labels = {
                    "safe": "Safe", "caution": "Caution", "high": "High Risk", "critical": "Critical"
                }
            else:
                status_labels = {
                    "safe": "آمن", "caution": "حذر", "high": "خطر مرتفع", "critical": "حرج"
                }
            
            st.markdown(f"<div class='badge' style='background:{colors[key]}'>{emojis[key]} {status_labels[key]}</div>", 
                       unsafe_allow_html=True)
            
            # Metrics
            delta = st.session_state.sim["core"] - st.session_state.sim["baseline"]
            
            if app_language == "English":
                core_label = "Core Temperature"
                feels_label = "Feels-like"
                baseline_label = "Baseline"
            else:
                core_label = "درجة الحرارة الأساسية"
                feels_label = "درجة الحرارة المحسوسة"
                baseline_label = "خط الأساس"
                
            st.metric(core_label, f"{st.session_state.sim['core']:.1f}°C", f"{delta:+.1f}°C")
            st.metric(feels_label, f"{st.session_state.sim['feels']:.1f}°C")
            st.metric(baseline_label, f"{st.session_state.sim['baseline']:.1f}°C")
            
            # Why this status
            if app_language == "English":
                expander_label = "Why this status?"
            else:
                expander_label = "لماذا هذه الحالة؟"
                
            with st.expander(expander_label, expanded=True):
                if trig:
                    for t in trig: 
                        st.write("• " + t)
                else:
                    if app_language == "English":
                        st.write("• No thresholds triggered yet")
                    else:
                        st.write("• لم يتم تفعيل أي عتبات بعد")

        with col_chart:
            if app_language == "English":
                st.subheader("📈 Temperature Trend")
                toggle_label = "Record changes automatically"
                clear_label = "Clear Chart"
                no_data_msg = "Apply a scenario or enable recording to see the chart"
            else:
                st.subheader("📈 اتجاه درجة الحرارة")
                toggle_label = "تسجيل التغييرات تلقائيًا"
                clear_label = "مسح الرسم البياني"
                no_data_msg = "طبق سيناريو أو فعّل التسجيل لرؤية الرسم البياني"
            
            # Live tracking toggle
            live_toggle = st.toggle(toggle_label, value=st.session_state.sim_live)
            if live_toggle and not st.session_state.sim_live:
                st.session_state.sim_live = True
                st.session_state.sim_history.append({
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "core": float(st.session_state.sim["core"]),
                    "baseline": float(st.session_state.sim["baseline"]),
                    "feels": float(st.session_state.sim["feels"]),
                })
            st.session_state.sim_live = live_toggle
            
            # Removed "Add Manual Point" button as requested
            
            if st.button(clear_label):
                st.session_state.sim_history.clear()
                st.rerun()

            # Plot
            if not st.session_state.sim_history:
                st.info(no_data_msg)
            else:
                df = pd.DataFrame(st.session_state.sim_history)
                fig = go.Figure()
                
                if app_language == "English":
                    feels_name = "Feels-like"
                    core_name = "Core"
                    baseline_name = "Baseline"
                else:
                    feels_name = "المحسوسة"
                    core_name = "الأساسية"
                    baseline_name = "خط الأساس"
                    
                fig.add_trace(go.Scatter(x=df["ts"], y=df["feels"], mode="lines+markers", name=feels_name))
                fig.add_trace(go.Scatter(x=df["ts"], y=df["core"], mode="lines+markers", name=core_name))
                fig.add_trace(go.Scatter(x=df["ts"], y=df["baseline"], mode="lines", name=baseline_name))
                
                fig.update_layout(
                    height=300, 
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", y=1.1), 
                    xaxis_title="Time" if app_language == "English" else "الوقت", 
                    yaxis_title="°C"
                )
                st.plotly_chart(fig, use_container_width=True)

# ================== JOURNAL (includes RECOVERY) ==================
def render_journal():
    st.title("📒 " + T["journal"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    st.caption(T["journal_hint"])
    # Daily quick logger
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
    tr_other = st.text_input(f"{'Other' if app_language=='English' else 'أخرى'} ({T['trigger']})", "")
    chosen_sy = st.multiselect(("Symptoms (optional)" if app_language=="English" else "الأعراض (اختياري)"), symptom_options)
    sy_other = st.text_input(f"{'Other' if app_language=='English' else 'أخرى'} ({T['symptom']})", "")
    free_note = st.text_area(T["free_note"], height=100)

    if st.button(("Save to Journal" if app_language=="English" else "حفظ في اليوميات"), key="journal_save"):
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

    available_types = ["PLAN","ALERT","ALERT_AUTO","RECOVERY","DAILY","NOTE"]
    type_filter = st.multiselect(T["filter_by_type"], options=available_types, default=available_types)
    page_size = 12
    st.session_state.setdefault("journal_offset", 0)
    start = st.session_state["journal_offset"]; end = start + 200
    chunk = rows[start:end]

    def _render_entry(raw_entry_json):
        try: obj = json.loads(raw_entry_json)
        except Exception: obj = {"type":"NOTE","at": utc_iso_now(), "text": str(raw_entry_json)}
        t = obj.get("type","NOTE")
        when = obj.get("at", utc_iso_now())
        try:
            dt = _dt.fromisoformat(when.replace("Z","+00:00"))
        except Exception:
            dt = _dt.now(timezone.utc)
        when_label = dt.astimezone(TZ_DUBAI).strftime("%Y-%m-%d %H:%M")
        if t == "RECOVERY":
            from_s = obj.get("from_status","?"); to_s = obj.get("to_status","?")
            acts   = obj.get("actions", []); dur = obj.get("duration_min", None)
            core_b = obj.get("core_before"); core_a = obj.get("core_after")
            delta  = (round((core_a - core_b),1) if (core_a is not None and core_b is not None) else None)
            if app_language=="Arabic":
                header = f"**{when_label}** — **تعافٍ** ({from_s} → {to_s})"
                lines = []
                if acts: lines.append("**الإجراءات:** " + ", ".join(map(str,acts)))
                meta = []
                if dur is not None: meta.append(f"{dur} دقيقة")
                if delta is not None: meta.append(f"Δ الأساسية {delta:+.1f}°م")
                if meta: lines.append("**المدة/التغير:** " + " • ".join(meta))
                note = (obj.get("note") or "").strip()
                if note: lines.append("**ملاحظة:** " + note)
                return header, "\n\n".join(lines), "🧊", t
            else:
                header = f"**{when_label}** — **Recovery** ({from_s} → {to_s})"
                lines = []
                if acts: lines.append("**Actions:** " + ", ".join(map(str,acts)))
                meta = []
                if dur is not None: meta.append(f"{dur} min")
                if delta is not None: meta.append(f"Δ core {delta:+.1f}°C")
                if meta: lines.append("**Duration/Change:** " + " • ".join(meta))
                note = (obj.get("note") or "").strip()
                if note: lines.append("**Note:** " + note)
                return header, "\n\n".join(lines), "🧊", t
        elif t == "PLAN":
            city = obj.get("city","—"); act = obj.get("activity","—")
            start_t = obj.get("start","—"); end_t = obj.get("end","—")
            fl = obj.get("feels_like"); hum = obj.get("humidity")
            meta = f"Feels‑like {round(fl,1)}°C • Humidity {int(hum)}%" if (fl is not None and hum is not None) else ""
            if app_language=="Arabic":
                header = f"**{when_label}** — **خطة** ({city})"
                body = f"**النشاط:** {act}\n\n**الوقت:** {start_t} → {end_t}\n\n{meta}"
            else:
                header = f"**{when_label}** — **Plan** ({city})"
                body = f"**Activity:** {act}\n\n**Time:** {start_t} → {end_t}\n\n{meta}"
            return header, body, "🗓️", t
        elif t in ("ALERT","ALERT_AUTO"):
            core = obj.get("core_temp") or obj.get("body_temp"); periph = obj.get("peripheral_temp"); base = obj.get("baseline")
            delta = (core - base) if (core is not None and base is not None) else None
            reasons = obj.get("reasons") or []; symptoms = obj.get("symptoms") or []
            if app_language=="Arabic":
                header = f"**{when_label}** — **تنبيه حراري**"
                lines = []
                if core is not None: lines.append(f"**الأساسية:** {core}°م")
                if periph is not None: lines.append(f"**الطرفية:** {periph}°م")
                if base is not None: lines.append(f"**الأساس:** {base}°م")
                if delta is not None: lines.append(f"**الفرق عن الأساس:** +{round(delta,1)}°م")
                if reasons: lines.append(f"**الأسباب:** " + ", ".join(map(str,reasons)))
                if symptoms: lines.append(f"**الأعراض:** " + ", ".join(map(str,symptoms)))
                return header, "\n\n".join(lines), "🚨", t
            else:
                header = f"**{when_label}** — **Heat alert**"
                lines = []
                if core is not None: lines.append(f"**Core:** {core}°C")
                if periph is not None: lines.append(f"**Peripheral:** {periph}°C")
                if base is not None: lines.append(f"**Baseline:** {base}°C")
                if delta is not None: lines.append(f"**Δ from baseline:** +{round(delta,1)}°C")
                if reasons: lines.append(f"**Reasons:** " + ", ".join(map(str,reasons)))
                if symptoms: lines.append(f"**Symptoms:** " + ", ".join(map(str,symptoms)))
                return header, "\n\n".join(lines), "🚨", t
        elif t == "DAILY":
            mood = obj.get("mood","—"); hyd = obj.get("hydration_glasses","—")
            sleep = obj.get("sleep_hours","—"); fat = obj.get("fatigue","—")
            if app_language=="Arabic":
                header = f"**{when_label}** — **مُسجّل يومي**"
                lines = [f"**المزاج:** {mood}", f"**الترطيب:** {hyd}", f"**النوم:** {sleep}س", f"**التعب:** {fat}"]
            else:
                header = f"**{when_label}** — **Daily log**"
                lines = [f"**Mood:** {mood}", f"**Hydration:** {hyd}", f"**Sleep:** {sleep}h", f"**Fatigue:** {fat}"]
            note = (obj.get("note") or "").strip()
            if note: lines.append(("**Note:** " if app_language=="English" else "**ملاحظة:** ") + note)
            return header, "\n\n".join(lines), "🧩", t
        else:
            text = obj.get("text") or obj.get("note") or "—"
            header = f"**{when_label}** — **Note**" if app_language=="English" else f"**{when_label}** — **ملاحظة**"
            return header, text, "📝", t

    parsed = []
    for dt_raw, raw_json in chunk:
        title, body, icon, t = _render_entry(raw_json)
        if t not in type_filter: continue
        try:
            dt = _dt.fromisoformat(dt_raw.replace("Z","+00:00"))
        except Exception:
            dt = _dt.now(timezone.utc)
        day_key = dt.astimezone(TZ_DUBAI).strftime("%A, %d %B %Y")
        parsed.append((day_key, title, body, icon))

    current_day = None; shown = 0
    for day, title, body, icon in parsed:
        if shown >= page_size: break
        if day != current_day:
            st.markdown(f"## {day}"); current_day = day
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
            if st.button(T["newer"], key="jr_newer"):
                st.session_state["journal_offset"] = max(0, st.session_state["journal_offset"] - page_size); st.rerun()
    with colp2:
        if (start + shown) < len(rows):
            if st.button(T["older"], key="jr_older"):
                st.session_state["journal_offset"] += page_size; st.rerun()

# ================== ASSISTANT ==================
def render_assistant():
    st.title("🤝 " + T["assistant_title"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return
    st.caption(T["assistant_hint"])
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("_asked_city_once", False)

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
        if city_code is None and not st.session_state["_asked_city_once"]:
            st.session_state["_asked_city_once"] = True
            with st.chat_message("assistant"):
                st.info("I don’t know your city yet. Pick one to tailor advice:" if app_language=="English"
                        else "لا أعرف مدينتك بعد. اختر مدينة لتخصيص الإرشاد:")
                pick = st.selectbox("📍 City", GCC_CITIES, index=0, key="assistant_city_pick",
                                    format_func=lambda c: city_label(c, app_language))
                if st.button("Use this city" if app_language=="English" else "استخدام هذه المدينة", key="use_city_btn"):
                    st.session_state["current_city"] = pick
                    st.rerun()

        with st.chat_message("assistant"):
            ph = st.empty(); ph.markdown("💭 " + T["thinking"])
            text, err = ai_chat(prompt, app_language)
            prefs = load_user_prefs(st.session_state["user"])
            ai_style_pref = (prefs.get("ai_style") or "Concise")
            if err:
                ph.markdown(get_fallback_response(prompt, app_language))
                st.session_state["chat_history"].append({"role":"assistant","content": get_fallback_response(prompt, app_language)})
            else:
                # Concise mode: show summary line + collapsible details if long
                if ai_style_pref == "Concise" and text and len(text) > 800 and ("\n" in text):
                    first, rest = text.split("\n", 1)
                    ph.markdown(first.strip())
                    with st.expander("Details" if app_language=="English" else "التفاصيل", expanded=False):
                        st.markdown(rest.strip())
                else:
                    ph.markdown(text)
                st.session_state["chat_history"].append({"role":"assistant","content": text})

    # Status
    bits = []
    prov = st.session_state.get("ai_provider_last")
    if prov: bits.append(("✅ " if not st.session_state.get("ai_last_error") else "⚠️ ") + f"Provider: {prov}")
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

# ================== EXPORTS ==================
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
    st.markdown("— or download raw CSVs —" if app_language=="English" else "— أو حمّل ملفات CSV خام —")
    st.download_button("Temps.csv", data=df_t.to_csv(index=False).encode("utf-8"), file_name="Temps.csv", mime="text/csv", use_container_width=True)
    st.download_button("Journal.csv", data=df_j.to_csv(index=False).encode("utf-8"), file_name="Journal.csv", mime="text/csv", use_container_width=True)

# ================== SETTINGS ==================
def render_settings():
    st.title("⚙️ " + T["settings"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    # Load existing contacts
    if "primary_phone" not in st.session_state or "secondary_phone" not in st.session_state:
        p1, p2 = load_emergency_contacts(st.session_state["user"])
        st.session_state["primary_phone"], st.session_state["secondary_phone"] = p1, p2

    # Load prefs
    prefs = load_user_prefs(st.session_state["user"])

    st.subheader(T["baseline_setting"])
    st.session_state.setdefault("baseline", 37.0)
    st.session_state.setdefault("use_temp_baseline", True)
    base = st.number_input(T["baseline_setting"], 35.5, 38.5, float(st.session_state["baseline"]), step=0.1, key="settings_baseline")
    useb = st.checkbox(T["use_temp_baseline"], value=st.session_state["use_temp_baseline"], key="settings_useb")
    st.caption("ℹ️ Baseline is used by the Heat Safety Monitor to decide when to alert (≥ 0.5°C above your baseline)." if app_language=="English"
               else "ℹ️ يُستخدم خط الأساس بواسطة مراقب السلامة الحرارية لتحديد وقت التنبيه (≥ ‎0.5°م فوق الأساس).")

    st.subheader(T["contacts"])
    p1 = st.text_input(T["primary_phone"], st.session_state["primary_phone"], key="settings_p1")
    p2 = st.text_input(T["secondary_phone"], st.session_state["secondary_phone"], key="settings_p2")

    st.subheader(T.get("home_city","Home City"))
    home_city = st.selectbox(T.get("home_city","Home City"), GCC_CITIES,
                             index=(GCC_CITIES.index(prefs["home_city"]) if prefs.get("home_city") in GCC_CITIES else 0),
                             format_func=lambda c: city_label(c, app_language), key="settings_home_city")
    tz = st.text_input(T.get("timezone","Timezone (optional)"), prefs.get("timezone") or "", key="settings_tz")

    st.subheader("🤖 " + ("AI answer style" if app_language=="English" else "أسلوب إجابات المساعد"))
    ai_style = st.radio(("Answer length" if app_language=="English" else "طول الإجابة"),
                        ["Concise","Detailed"], index=(0 if (prefs.get("ai_style") or "Concise")=="Concise" else 1),
                        horizontal=True, key="settings_ai_style")

    if st.button(T["save_settings"], key="settings_save_btn"):
        st.session_state["baseline"] = float(base)
        st.session_state["use_temp_baseline"] = bool(useb)
        st.session_state["primary_phone"] = (p1 or "").strip()
        st.session_state["secondary_phone"] = (p2 or "").strip()

        ok, err = save_emergency_contacts(st.session_state["user"], p1, p2)
        save_user_prefs(st.session_state["user"], home_city=home_city, timezone=tz, language=app_language, ai_style=ai_style)
        st.session_state["current_city"] = home_city  # also set session city
        if ok: st.success("✅ " + T["saved"])
        else: st.error(f"Failed to save contacts: {err}")

    st.markdown("---")
    if st.button(T["logout"], type="secondary", key="settings_logout"):
        for k in ["user", "primary_phone", "secondary_phone", "current_city"]:
            st.session_state.pop(k, None)
        st.success(T["logged_out"]); st.rerun()

# ================== SIDEBAR / APP SHELL ==================
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/a361daf5636e2f1dcbfb457b52691198cea1e95f/logo.png"
st.sidebar.image(logo_url, use_container_width=True)

# Language picker
prev_lang = st.session_state.get("_prev_lang", None)
app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English", "عربي"], key="language_selector")
app_language = "English" if "English" in app_language else "Arabic"
T = TEXTS[app_language]
st.session_state["_prev_lang"] = app_language

# Force RTL for Arabic main content while keeping sidebar mechanics LTR
if app_language == "Arabic":
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { direction: rtl !important; text-align: right !important; }
    [data-testid="stSidebar"] { direction: ltr !important; }
    [data-testid="stSidebar"] > div { direction: rtl !important; text-align: right !important; }
    [data-testid="stSlider"] { direction: ltr !important; }
    [data-testid="stSlider"] > label { direction: rtl !important; text-align: right !important; }
    [data-testid="stSlider"] [data-testid="stTickBar"] { direction: ltr !important; }
    [data-testid="stSlider"] [data-baseweb="slider"] { direction: ltr !important; }
    [data-testid="stThumbValue"] { direction: ltr !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# Navigation
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
st.session_state.setdefault("current_page", "about")
if "nav_radio" not in st.session_state:
    st.session_state["nav_radio"] = st.session_state["current_page"]
if prev_lang is not None and prev_lang != app_language:
    if st.session_state.get("current_page") in PAGE_IDS:
        st.session_state["nav_radio"] = st.session_state["current_page"]
page_id = st.sidebar.radio("📑 " + ("Navigate" if app_language=="English" else "التنقل"),
                           options=PAGE_IDS, format_func=lambda pid: PAGE_LABELS[pid], key="nav_radio")
st.session_state["current_page"] = page_id

# Login/Register box
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
                    # Load contacts and prefs
                    primary, secondary = load_emergency_contacts(username)
                    st.session_state["primary_phone"] = primary
                    st.session_state["secondary_phone"] = secondary
                    prefs = load_user_prefs(username)
                    if prefs.get("home_city"):
                        st.session_state["current_city"] = prefs["home_city"]
                    st.success(T["logged_in"]); st.rerun()
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
            for k in ["user","primary_phone","secondary_phone","current_city"]:
                st.session_state.pop(k, None)
            st.success(T["logged_out"]); st.rerun()

# ================== ROUTING ==================
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

# Emergency in sidebar (click-to-call)
with st.sidebar.expander("📞 " + T["emergency"], expanded=False):
    if "user" in st.session_state:
        if "primary_phone" not in st.session_state or "secondary_phone" not in st.session_state:
            primary, secondary = load_emergency_contacts(st.session_state["user"])
            st.session_state["primary_phone"], st.session_state["secondary_phone"] = primary, secondary
        if st.session_state["primary_phone"]:
            href = tel_href(st.session_state["primary_phone"])
            st.markdown(f"**{'Primary' if app_language=='English' else 'الهاتف الأساسي'}:** [{st.session_state['primary_phone']}](tel:{href})")
        if st.session_state["secondary_phone"]:
            href = tel_href(st.session_state["secondary_phone"])
            st.markdown(f"**{'Secondary' if app_language=='English' else 'هاتف إضافي'}:** [{st.session_state['secondary_phone']}](tel:{href})")
        if not (st.session_state["primary_phone"] or st.session_state["secondary_phone"]):
            st.caption("Set numbers in Settings to enable quick call." if app_language=="English" else "اضبط الأرقام في الإعدادات لتمكين الاتصال السريع.")
    else:
        st.caption("Please log in to see emergency contacts" if app_language=="English" else "يرجى تسجيل الدخول لعرض جهات الاتصال للطوارئ")
