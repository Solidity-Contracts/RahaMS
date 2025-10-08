# -*- coding: utf-8 -*-
# TANZIM MS — Comprehensive App (EN/AR, RTL, Sensors Explainer, Recovery Learning, OpenAI+DeepSeek)
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
from typing import Dict, Any, Optional 
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import pandas as pd
import plotly.graph_objects as go

#try:
#    from supabase import create_client, Client
#except Exception:
#    create_client, Client = None, None

from supabase import create_client

# ================== CONFIG ==================
st.set_page_config(page_title="Tanzim MS", page_icon="🌡️", layout="wide")

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

# ---------- GCC city → timezone (fallback to UTC) ----------
GCC_CITY_TZ = {
    "Abu Dhabi,AE":"Asia/Dubai", "Dubai,AE":"Asia/Dubai", "Sharjah,AE":"Asia/Dubai",
    "Doha,QA":"Asia/Qatar", "Al Rayyan,QA":"Asia/Qatar",
    "Kuwait City,KW":"Asia/Kuwait", "Manama,BH":"Asia/Bahrain",
    "Riyadh,SA":"Asia/Riyadh", "Jeddah,SA":"Asia/Riyadh", "Dammam,SA":"Asia/Riyadh",
    "Muscat,OM":"Asia/Muscat"
}
def get_active_tz() -> ZoneInfo:
    """Use user's saved timezone if set; else infer from current city; else UTC."""
    user = st.session_state.get("user")
    prefs = load_user_prefs(user) if user else {}
    tz_pref = (prefs.get("timezone") or "").strip()
    if tz_pref:
        try:
            return ZoneInfo(tz_pref)
        except Exception:
            st.warning(f"Unknown timezone '{tz_pref}', falling back to city.")
    city_code = st.session_state.get("current_city")
    tz_code = GCC_CITY_TZ.get(city_code, "UTC")
    try:
        return ZoneInfo(tz_code)
    except Exception:
        return ZoneInfo("UTC")

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
        "status": "Status",
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
        "status": "الحالة",
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
def get_supabase(url: str, key: str):
    return create_client(url, key)

sb = get_supabase(SUPABASE_URL, SUPABASE_ANON_KEY)

# ================== Your fetchers (no silent fails) ==================
def fetch_latest_sensor_sample(device_id: str) -> dict | None:
    if not device_id:
        st.error("Device id missing"); return None
    try:
        res = (sb.table("sensor_readings")
                 .select("core_c,peripheral_c,created_at")
                 .eq("device_id", device_id)
                 .order("created_at", desc=True)
                 .limit(1)
                 .execute())
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        core = row.get("core_c")
        per  = row.get("peripheral_c")
        return {
            "core": float(core) if core is not None else None,
            "peripheral": float(per) if per is not None else None,
            "at": row.get("created_at"),
        }
    except Exception as e:
        # Show the actual cause instead of pretending "no data"
        st.error(f"Supabase error while fetching latest sample: {e}")
        return None

@st.cache_data(ttl=30)
def fetch_sensor_series(device_id: str, limit: int = 240):
    try:
        res = (
            sb.table("sensor_readings")
              .select("core_c,peripheral_c,created_at")
              .eq("device_id", device_id)
              .order("created_at", desc=True)
              .limit(limit)
              .execute()
        )
        data = res.data or []
        data = sorted(data, key=lambda r: r["created_at"])
        return data
    except Exception as e:
        st.error(f"Supabase error while fetching series: {e}")
        return []


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

# ================== ABOUT — First‑time friendly, action‑first, 4 safety cards, EN/AR ==================

def render_about_page(lang: str = "English"):
    """
    Updated, action-first About page:
    - Clear roadmap (first-time setup + quick checklist)
    - Explains the 4 temperatures (Baseline, Core, Peripheral, Feels‑like)
    - Explains risk cards (green, yellow, orange, red) and what to expect
    - Navigation guide for every page and each tab
    - Arabic/English with RTL support
    """
    is_ar = (lang == "Arabic")

    def T_(en: str, ar: str) -> str:
        return ar if is_ar else en

    # ------------------------ Scoped styles ------------------------
    st.markdown(
        (
            """
            <style>
              .about-wrap { direction: rtl; text-align: right; }
              .hero { border: 1px solid rgba(0,0,0,.08); border-radius: 14px; padding: 14px;
                      background: linear-gradient(90deg, rgba(14,165,233,.08), rgba(34,197,94,.08)); }
              .pill { display:inline-block; padding: .15rem .6rem; border: 1px solid rgba(0,0,0,.12);
                      border-radius: 999px; background: rgba(0,0,0,.03); font-size: .85rem; margin-inline: .25rem 0; }
              .grid { display:grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap:12px; }
              @media (max-width: 820px){ .grid { grid-template-columns: 1fr; } }
              .card { background: var(--card-bg,#fff); color: var(--card-fg,#0f172a); border:1px solid rgba(0,0,0,.08);
                      border-radius: 12px; padding: 12px; }
              .risk-card { border-left: 10px solid var(--left); padding-left: 12px; }
              .muted { opacity: .85; font-size: 0.95rem; }
              .kbd { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
                     border:1px solid rgba(0,0,0,.15); border-bottom-width: 2px; padding: 2px 6px; border-radius: 6px; background: rgba(0,0,0,.04); }
              .step-ok { color: #16a34a; font-weight: 600; }
              .step-need { color: #b45309; font-weight: 600; }
            </style>
            """
            if is_ar else
            """
            <style>
              .hero { border: 1px solid rgba(0,0,0,.08); border-radius: 14px; padding: 14px;
                      background: linear-gradient(90deg, rgba(14,165,233,.08), rgba(34,197,94,.08)); }
              .pill { display:inline-block; padding: .15rem .6rem; border: 1px solid rgba(0,0,0,.12);
                      border-radius: 999px; background: rgba(0,0,0,.03); font-size: .85rem; margin-right: .25rem; }
              .grid { display:grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap:12px; }
              @media (max-width: 820px){ .grid { grid-template-columns: 1fr; } }
              .card { background: var(--card-bg,#fff); color: var(--card-fg,#0f172a); border:1px solid rgba(0,0,0,.08);
                      border-radius: 12px; padding: 12px; }
              .risk-card { border-left: 10px solid var(--left); padding-left: 12px; }
              .muted { opacity: .85; font-size: 0.95rem; }
              .kbd { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
                     border:1px solid rgba(0,0,0,.15); border-bottom-width: 2px; padding: 2px 6px; border-radius: 6px; background: rgba(0,0,0,.04); }
              .step-ok { color: #16a34a; font-weight: 600; }
              .step-need { color: #b45309; font-weight: 600; }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )

    wrap_open = '<div class="about-wrap">' if not is_ar else '<div class="about-wrap">'
    st.markdown(wrap_open, unsafe_allow_html=True)

    # ------------------------ HERO ------------------------
    st.markdown(
        f"""
        <div class="hero">
          <h2 style="margin:0">{T_("👋 Welcome to", "👋 أهلاً بك في")} <b>Tanzim MS</b></h2>
          <p class="muted" style="margin:.25rem 0 0 0">
            {T_(
                "A bilingual, Gulf‑aware heat‑safety companion for people with MS. It compares your readings to your baseline and real local weather, then gives early, simple actions.",
                "رفيق ثنائي اللغة ومراعي لبيئة الخليج للأمان الحراري لمرضى التصلّب المتعدّد. يقارن قراءاتك بخطّك الأساسي وبالطقس المحلي الفعلي ثم يقدّم خطوات مبكرة وبسيطة."
            )}
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------ TABS ------------------------
    tab_labels_en = [
        "🧭 Overview & roadmap",
        "🌡️ Temperatures & risk",
        "🚀 First‑time setup",
        "📑 Page & tab guide",
    ]
    tab_labels_ar = [
        "🧭 نظرة عامة وخارطة طريق",
        "🌡️ الحرارات والتقييم",
        "🚀 التهيئة لأول مرة",
        "📑 دليل الصفحات والتبويبات",
    ]
    
    t_overview, t_temps, t_start, t_guide = st.tabs(tab_labels_ar if is_ar else tab_labels_en)

    # ---------- TAB: Overview & roadmap ----------
    with t_overview:
        # ————————————————————————————————
        # Overview 
        # ————————————————————————————————
        st.markdown("### " + T_("Overview", "نظرة عامة"))
        st.markdown(T_(
            """**What’s in the app**
    - **Monitor — Live:** Real sensor or manual entry; alerts save to Journal.
    - **Learn & Practice:** Simulate values to see how alerts would react (no saving).
    - **Planner:** Safer 2‑hour windows for your city; add plans to Journal.
    - **Journal:** One quick daily note; alerts/plans appear here.
    - **AI Companion:** Short, bilingual guidance aware of your city and logs.""",
            """**مكوّنات التطبيق**
    - **المراقبة — مباشر:** حساس فعلي أو إدخال يدوي؛ تُحفَظ التنبيهات في اليوميات.
    - **تعلّم وتدرّب:** حاكِ القيم لترى تفاعل التنبيهات (من دون حفظ).
    - **المخطّط:** فترات ساعتين أكثر أمانًا في مدينتك؛ أضف خططًا لليوميات.
    - **اليوميّات:** ملاحظة يومية سريعة؛ تظهر هنا التنبيهات والخطط.
    - **المرافق الذكي:** إرشاد قصير ثنائي اللغة واعٍ بمدينتك وسجلك."""
        ))
    
        st.markdown("---")
    
        # ————————————————————————————————
        # Quick roadmap (no duplication with other tabs)
        # ————————————————————————————————
        st.markdown("### " + T_("Quick roadmap (60 seconds)", "خارطة سريعة (60 ثانية)"))
    
        st.markdown(
            T_(
                """
    <div class="panel road">
      <div><b>1)</b> Create an account <span class="pill">Sidebar → Login / Register</span></div>
      <div><b>2)</b> Set your Baseline & Home City <span class="pill">Settings → Baseline & City</span></div>
      <div><b>3)</b> Try alerts safely <span class="pill">Monitor → Learn & Practice</span></div>
      <div><b>4)</b> Use Live day‑to‑day; add a quick Journal note daily</div>
    </div>
    """,
                """
    <div class="panel road" style="text-align:right">
      <div><b>1)</b> أنشئ حسابًا <span class="pill">الشريط الجانبي ← تسجيل الدخول/إنشاء حساب</span></div>
      <div><b>2)</b> اضبط خطّ الأساس والمدينة <span class="pill">الإعدادات ← الأساس والمدينة</span></div>
      <div><b>3)</b> تعرّف على التنبيهات بأمان <span class="pill">المراقبة ← تعلّم وتدرّب</span></div>
      <div><b>4)</b> استخدم «مباشر» يوميًا؛ وأضف ملاحظة سريعة في اليوميات</div>
    </div>
    """
            ),
            unsafe_allow_html=True
        )
    
        st.markdown("---")
    
        # ————————————————————————————————
        # Where to go next (pointers, not duplication)
        # ————————————————————————————————
        st.markdown("### " + T_("Where next?", "إلى أين بعد ذلك؟"))
        st.markdown(T_(
            """- **Temperatures & risk:** Learn the numbers and see the risk cards.
    - **First‑time setup:** A guided checklist to finish setup.
    - **Page & tab guide:** A map of each page and its tabs.""",
            """- **الحرارات والتقييم:** تعرّف على القيم وشاهد بطاقات التقييم.
    - **البدء لأول مرة:** قائمة إرشادية لإكمال الإعداد.
    - **دليل الصفحات والتبويبات:** خريطة مبسطة لكل صفحة وتبويب."""
        ))
    
        st.caption(T_(
            "Your data stays in your local database; guidance is general wellness only. Seek medical care for severe or unusual symptoms.",
            "تبقى بياناتك محليًا؛ الإرشاد عام للصحة فقط. اطلب رعاية طبية عند أعراض شديدة أو غير معتادة."
        ))
    

    

    # ---------- TAB: Temperatures & risk ----------
    with t_temps:
        st.markdown("### " + T_("The Four Temperatures", "الحرارات الأربع"))
        st.markdown(T_(
            "These appear across the app and in alerts:",
            "تظهر هذه القيم في التطبيق وفي التنبيهات:"
        ))
        with st.container():
            st.markdown(
                f"""
                <div class="grid">
                  <div class="card"><b>🌡️ {T_('Baseline', 'خط الأساس')}</b><br>
                    <span class="muted">{T_('Your usual body temperature. We compare Core against this to detect rises.',
                                             'حرارتك المعتادة. نقارن «الأساسية» بها لاكتشاف الارتفاعات.')}</span>
                  </div>
                  <div class="card"><b>🔥 {T_('Core', 'الأساسية')}</b><br>
                    <span class="muted">{T_('Internal body temperature — most relevant for heat stress.',
                                             'حرارة الجسم الداخلية — الأهم في الإجهاد الحراري.')}</span>
                  </div>
                  <div class="card"><b>🖐️ {T_('Peripheral', 'الطرفية')}</b><br>
                    <span class="muted">{T_('Skin temperature; changes quickly with the environment.',
                                             'حرارة الجلد؛ تتغيّر سريعًا مع البيئة.')}</span>
                  </div>
                  <div class="card"><b>🌬️ {T_('Feels‑like', 'المحسوسة')}</b><br>
                    <span class="muted">{T_('Weather effect combining heat, humidity, and wind; high values increase risk.',
                                             'تأثير الطقس (حرارة/رطوبة/رياح)؛ القيم المرتفعة تزيد الخطر.')}</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### " + T_("How risk is calculated (simplified)", "كيف نحتسب التقييم (مختصر)"))
        st.markdown(T_(
            "- **Environment:** Higher **Feels‑like** adds risk; **Humidity ≥ 60%** adds extra risk when hot.\n"
            "- **Uhthoff (ΔCore):** If **Core − Baseline ≥ 0.5 °C** ⇒ at least **Caution**; **≥ 1.0 °C** ⇒ at least **High**.\n"
            "- The status never lowers while ΔCore is high (a small **hysteresis** for safety).",
            "- **البيئة:** ارتفاع **المحسوسة** يزيد الخطر؛ **الرطوبة ≥ 60%** تضيف خطرًا إضافيًا عند الحر.\n"
            "- **أوتهوف (Δالأساسية):** إذا **الأساسية − الأساس ≥ ‎0.5°م** ⇒ على الأقل **حذر**؛ **≥ ‎1.0°م** ⇒ على الأقل **مرتفع**.\n"
            "- لا ينخفض المستوى ما دامت Δالأساسية مرتفعة (بعض **العطالة** للسلامة)."
        ))

        st.markdown("### " + T_("What you’ll see — risk cards", "ما الذي ستراه — بطاقات التقييم"))
        cA, cB = st.columns(2)
        with cA:
            st.markdown(
                f"""
                <div class="card risk-card" style="--left: green">
                  <b>🟢 {T_('Safe (green)', 'آمنة (أخضر)')}</b><br>
                  <span class="muted">{T_('Keep cool and hydrated; proceed as planned.',
                                           'ابْقَ باردًا ورطّب؛ تابع خطّتك.')}</span>
                </div>
                <div class="card risk-card" style="--left: orange; margin-top:8px">
                  <b>🟡 {T_('Caution (yellow)', 'حذر (أصفر)')}</b><br>
                  <span class="muted">{T_('Hydrate, slow down, prefer shade/AC, consider pre‑cooling.',
                                           'رطّب، خفّف الجهد، فضّل الظل/المكيّف، فكّر بالتبريد المسبق.')}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cB:
            st.markdown(
                f"""
                <div class="card risk-card" style="--left: orangered">
                  <b>🟠 {T_('High (orange)', 'مرتفع (برتقالي)')}</b><br>
                  <span class="muted">{T_('Limit outdoor time, pre‑cool, frequent rests, prefer AC.',
                                           'قلّل الوقت خارجًا، برّد مسبقًا، استراحات متكررة، وفضّل المكيّف.')}</span>
                </div>
                <div class="card risk-card" style="--left: red; margin-top:8px">
                  <b>🔴 {T_('Danger (red)', 'خطر (أحمر)')}</b><br>
                  <span class="muted">{T_('Go indoors/AC now, stop exertion, use active cooling; seek care if severe.',
                                           'ادخل إلى مكان مكيّف الآن، أوقف الجهد، استخدم تبريدًا نشطًا؛ اطلب رعاية عند الشدة.')}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.caption(T_(
            "Your actual status depends on your readings versus baseline and current weather.",
            "تختلف حالتك فعليًا حسب قراءاتك مقابل الأساس والطقس الحالي."
        ))

    # ---------- TAB: First‑time setup ----------
    with t_start:
        # Work out current completion from session + prefs (safe fallbacks if logged out)
        user = st.session_state.get("user")
        prefs = load_user_prefs(user) if user else {}
        baseline = st.session_state.get("baseline")
        home_city = prefs.get("home_city") or st.session_state.get("current_city")
        tz = prefs.get("timezone") or ""
        ai_style = prefs.get("ai_style") or ""
        try:
            p1, p2 = load_emergency_contacts(user) if user else ("","")
        except Exception:
            p1, p2 = "",""

        def _line(ok: bool, where_en: str, where_ar: str):
            badge = f"<span class='step-ok'>✅ {T_('Complete','مكتمل')}</span>" if ok else f"<span class='step-need'>⭕️ {T_('Needed','مطلوب')}</span>"
            where = T_(where_en, where_ar)
            st.markdown(f"{badge} <span class='pill'>{where}</span>", unsafe_allow_html=True)

        st.markdown("### " + T_("New user checklist", "قائمة البدء للمستخدم"))
        with st.container(border=True):
            st.markdown("**1) " + T_("Register / Log in", "التسجيل / الدخول") + "**")
            st.caption(T_("Create your account from the **sidebar** Login/Register box.",
                          "أنشئ حسابك من مربع **تسجيل الدخول/إنشاء حساب** في الشريط الجانبي."))
            _line(bool(user), "Sidebar → Login / Register", "الشريط الجانبي ← تسجيل الدخول / إنشاء حساب")

        with st.container(border=True):
            st.markdown("**2) " + T_("Set Baseline & Home City", "اضبط خط الأساس والمدينة") + "**")
            st.caption(T_("Baseline powers alerts; Home City powers weather and planning.",
                          "خط الأساس يحرّك التنبيهات؛ المدينة تُستخدم للطقس والتخطيط."))
            _line(bool(baseline) and bool(home_city), "Settings → Baseline & Home City", "الإعدادات ← خط الأساس والمدينة")

        with st.container(border=True):
            st.markdown("**3) " + T_("Set Timezone (optional)", "اضبط المنطقة الزمنية (اختياري)") + "**")
            st.caption(T_("Only needed if your device/city differ or you travel.",
                          "مطلوبة فقط إذا اختلف جهازك/مدينتك أو عند السفر."))
            _line(bool(tz), "Settings → Timezone", "الإعدادات ← المنطقة الزمنية")

        with st.container(border=True):
            st.markdown("**4) " + T_("Add Emergency contacts", "أضف جهات اتصال للطوارئ") + "**")
            st.caption(T_("Enables quick tap‑to‑call in the sidebar.",
                          "يُمكّن الاتصال السريع من الشريط الجانبي."))
            _line(bool((p1 or "").strip() or (p2 or "").strip()),
                  "Settings → Emergency contacts", "الإعدادات ← جهات اتصال الطوارئ")

        with st.container(border=True):
            st.markdown("**5) " + T_("Choose AI answer style", "اختر أسلوب إجابات المساعد") + "**")
            st.caption(T_("Concise (short bullets) or Detailed (more context).",
                          "مختصر (نقاط قصيرة) أو مفصّل (سياق أكثر)."))
            _line(bool(ai_style), "Settings → AI style", "الإعدادات ← أسلوب إجابات المساعد")

        with st.container(border=True):
            st.markdown("**6) " + T_("Open Monitor — Learn & Practice first", "افتح المراقبة — تعلّم وتدرّب أولًا") + "**")
            st.caption(T_("Understand alerts safely; then use Live day‑to‑day.",
                          "تعرّف على التنبيهات بأمان؛ ثم استخدم «مباشر» يوميًا."))
            _line(True, "Monitor → Learn & Practice", "المراقبة ← تعلّم وتدرّب")

        with st.container(border=True):
            st.markdown("**7) " + T_("(Optional) Pair sensors", "(اختياري)اربط الحساسات") + "**")
            st.caption(T_("You can use the app fully without hardware, using Learn & Practice.",
                          "يمكنك استخدام التطبيق كاملًا دون عتاد عبر تعلّم وتدرّب."))
            _line(bool(st.session_state.get("sensors_paired")) or True, T_("Optional step","خطوة اختيارية"), T_("اختيارية","اختيارية"))

        st.markdown("---")
        st.markdown("### " + T_("Privacy & safety", "الخصوصية والسلامة"))
        st.write(T_(
            "Your data stays in your local database for your care. Tanzim MS provides general wellness guidance only. For severe or unusual symptoms, seek urgent medical care.",
            "تبقى بياناتك محليًا لرعايتك. يقدم تنظيم إم إس إرشادات عامة للصحة فقط. عند أعراض شديدة أو غير معتادة، اطلب رعاية طبية فورية."
        ))

    # ---------- TAB: Page & tab guide ----------
    with t_guide:
        st.markdown("### " + T_("How the app is organized", "كيفية تنظيم التطبيق"))
        st.markdown(T_(
            "Use the **sidebar** to navigate between pages. Here’s what each page (and its tabs) does:",
            "استخدم **الشريط الجانبي** للتنقل بين الصفحات. وظيفة كل صفحة وتبويب:"
        ))

        # Monitor
        with st.container(border=True):
            st.markdown("**☀️ " + T_("Heat Safety Monitor", "مراقبة السلامة الحرارية") + "**")
            st.markdown(T_(
                "- **📡 Live Sensor Data:** Real readings. Saves alerts to **Journal**; drives recommendations.\n"
                "- **🔬 Learn & Practice:** Simulate Core/Baseline/Feels‑like/Humidity to learn how alerts react — **does not save**.",
                "- **📡 بيانات مباشرة:** قراءات حقيقية. تحفظ التنبيهات في **اليوميات** وتؤثر على الإرشادات.\n"
                "- **🔬 تعلّم وتدرّب:** حاكِ الأساسية/الأساس/المحسوسة/الرطوبة لفهم التنبيهات — **لا يُحفَظ**."
            ))

        # Planner
        with st.container(border=True):
            st.markdown("**🗺️ " + T_("Planner & Tips", "المخطّط والنصائح") + "**")
            st.markdown(T_(
                "- **✅ Best windows:** Scans next 48h for cooler 2‑hour slots in your city.\n"
                "- **🤔 What‑if:** Enter an activity and duration; get instant tips (and ask AI).\n"
                "- **📍 Places:** Check a specific beach/park and plan an hour there.",
                "- **✅ أفضل الأوقات:** يفحص 48 ساعة القادمة لفترات ساعتين أكثر برودة في مدينتك.\n"
                "- **🤔 ماذا لو:** أدخل نشاطًا ومدة؛ احصل على نصائح فورية (واسأل المرافق).\n"
                "- **📍 الأماكن:** تحقق من شاطئ/حديقة محددة وخطّط لساعة هناك."
            ))

        # Journal
        with st.container(border=True):
            st.markdown("**📒 " + T_("Journal", "اليوميّات") + "**")
            st.markdown(T_(
                "- **Daily quick logger:** mood, hydration, sleep, fatigue, triggers, symptoms.\n"
                "- **Filters & paging:** view **PLAN / ALERT / RECOVERY / DAILY / NOTE** entries.\n"
                "- **Auto‑entries:** Live alerts and recoveries are saved with details.",
                "- **المسجل اليومي السريع:** المزاج، الترطيب، النوم، التعب، المحفزات، الأعراض.\n"
                "- **التصفية والتنقل:** عرض مدخلات **خطة / تنبيه / تعافٍ / يومي / ملاحظة**.\n"
                "- **مدخلات تلقائية:** تُحفظ تنبيهات «مباشر» والتعافي مع التفاصيل."
            ))

        # Assistant
        with st.container(border=True):
            st.markdown("**🤝 " + T_("AI Companion", "المرافق الذكي") + "**")
            st.markdown(T_(
                "- Short, bilingual answers with sections **Do now / Plan later / Watch for**.\n"
                "- Uses your **city**, **baseline**, **recent journal**, and **weather** when available.",
                "- إجابات قصيرة ثنائية اللغة بأقسام **افعل الآن / خطط لاحقًا / انتبه إلى**.\n"
                "- يستخدم **مدينتك** و**الأساس** و**اليوميات الحديثة** و**الطقس** عند توفرها."
            ))

        # Exports
        with st.container(border=True):
            st.markdown("**📦 " + T_("Exports", "التصدير") + "**")
            st.markdown(T_(
                "- Download **Excel/CSV** of your temperatures and journal to share or keep.",
                "- نزّل **Excel/CSV** لدرجات الحرارة واليوميات للمشاركة أو الحفظ."
            ))

        # Settings
        with st.container(border=True):
            st.markdown("**⚙️ " + T_("Settings", "الإعدادات") + "**")
            st.markdown(T_(
                "- Set **Baseline**, **Home City**, **Timezone**, **Emergency contacts**, and **AI style** (Concise/Detailed).\n"
                "- You can also **log out** here.",
                "- اضبط **خط الأساس** و**المدينة** و**المنطقة الزمنية** و**جهات الطوارئ** و**أسلوب المساعد** (مختصر/مفصل).\n"
                "- يمكنك أيضًا **تسجيل الخروج** هنا."
            ))

    st.markdown("</div>", unsafe_allow_html=True)

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

# =========================
# Heat Monitor — Minimal model (Env + ΔCore) with Uhthoff floor
# Live: 2 charts (Core+Periph) and (Core+Periph+Feels-like)
# Demo: Core + Feels-like + Baseline only; no journaling, but same UI experience
# =========================

# ---------- Status scale ----------
_STATUS_LEVEL = {"Safe": 0, "Caution": 1, "High": 2, "Danger": 3}

# ---------- Utilities ----------
def _is_ar() -> bool:
    return (app_language == "Arabic")

def _L(en: str, ar: str) -> str:
    return ar if _is_ar() else en

def _status_label() -> str:
    # Uses your T dict if available; otherwise localized fallback.
    return T.get("status", _L("Status", "الحالة"))

def get_active_tz():
    """Use user's saved timezone if available; fallback to Asia/Dubai; then UTC."""
    tz_code = None
    try:
        if "user" in st.session_state:
            prefs = load_user_prefs(st.session_state["user"]) or {}
            tz_code = prefs.get("timezone") or st.session_state.get("settings_tz")
    except Exception:
        pass
    try:
        return ZoneInfo(tz_code) if tz_code else ZoneInfo("Asia/Dubai")
    except Exception:
        # Fallbacks if zoneinfo not available or invalid code
        try:
            return TZ_DUBAI   # if you defined it elsewhere
        except Exception:
            return timezone.utc

# ---------- Cooling actions (use app lists if present; else defaults) ----------
def _actions_for_ui(lang: str):
    ae = list(globals().get("ACTIONS_EN", [])) or [
        "Move indoors / AC","Cooling vest","Cool shower","Hydrate (water)","Electrolyte drink",
        "Rest 15–20 min","Fan airflow","Shade / umbrella","Cooling towel/scarf",
        "Wrist/forearm cooling","Ice pack","Light clothing","Pre‑cool car","Misting water"
    ]
    aa = list(globals().get("ACTIONS_AR", [])) or [
        "الانتقال للداخل/مكيّف","سترة تبريد","دش بارد","ترطيب (ماء)","مشروب إلكتروليت",
        "راحة 15–20 دقيقة","مروحة هواء","ظل/مظلة","منشفة/وشاح تبريد",
        "تبريد المعصم/الساعد","كمادة ثلج","ملابس خفيفة","تبريد السيارة مسبقًا","رذاذ ماء"
    ]
    return aa if lang == "Arabic" else ae

# ---------- Triggers wording with your context fix ----------
def _triggers_for_ui(lang: str):
    if lang == "Arabic":
        base = list(globals().get("TRIGGERS_AR", []))
        lbl = "وقوف طويل للصلاة في الحر (خارج المسجد)"
        if "وقوف طويل في الصلاة" in base:
            i = base.index("وقوف طويل في الصلاة"); base[i] = lbl
        elif lbl not in base:
            base.append(lbl)
        return base
    else:
        base = list(globals().get("TRIGGERS_EN", []))
        lbl = "Long prayer standing in heat (outdoor)"
        if "Long prayer standing" in base:
            i = base.index("Long prayer standing"); base[i] = lbl
        elif lbl not in base:
            base.append(lbl)
        return base

# ---------- Symptoms (fallback if app constants missing) ----------
def _symptoms_for_ui(lang: str):
    if lang == "Arabic":
        return list(globals().get("SYMPTOMS_AR", [
            "تشوش الرؤية","إرهاق","ضعف","خدر","مشاكل توازن","تشنج","حساسية للحرارة",
            "تشوش إدراكي","دوخة","صداع","ألم","وخز"
        ]))
    else:
        return list(globals().get("SYMPTOMS_EN", [
            "Blurred vision","Fatigue","Weakness","Numbness","Coordination issues",
            "Spasticity","Heat intolerance","Cognitive fog","Dizziness","Headache","Pain","Tingling"
        ]))

# ---------- Minimal risk model: Environment (FL/H) + ΔCore only ----------
def compute_risk_minimal(feels_like, humidity, core, baseline, lang: str = "English") -> Dict[str, Any]:
    """
    Score uses only environment + ΔCore (Uhthoff).
    Status: Safe <3; Caution 3–4.5; High 5–6.5; Danger ≥7.
    Localized advice.
    """
    score = 0.0

    # Environment (feels-like tiers)
    if feels_like is not None:
        fl = float(feels_like)
        if   fl >= 42: score += 4
        elif fl >= 39: score += 3
        elif fl >= 35: score += 2
        elif fl >= 32: score += 1

    # Humidity penalty when hot
    if humidity is not None and feels_like is not None:
        if float(humidity) >= 60 and float(feels_like) >= 32:
            score += 1

    # Uhthoff (ΔCore)
    if core is not None and baseline is not None:
        delta = float(core) - float(baseline)
        if   delta >= 1.0: score += 2
        elif delta >= 0.5: score += 1

    # Localized advice text
    texts = {
        "Danger": {
            "en": "High risk: move to AC, stop exertion, active cooling, hydrate; seek care if severe.",
            "ar": "خطر مرتفع: انتقل إلى المكيّف، أوقف الجهد، استخدم تبريدًا نشطًا، رطّب؛ اطلب رعاية عند الأعراض الشديدة."
        },
        "High": {
            "en": "Elevated: limit outdoor time, pre‑cool, frequent rests, hydrate.",
            "ar": "مرتفع: قلّل الوقت خارجًا، برّد مسبقًا، خذ فترات راحة متكررة، ورطّب."
        },
        "Caution": {
            "en": "Mild risk: hydrate, pace yourself, prefer shade/AC.",
            "ar": "حذر: رطّب، نظّم جهدك، فضّل الظل/المكيّف."
        },
        "Safe": {
            "en": "Safe window. Keep cool and hydrated.",
            "ar": "فترة آمنة. ابقَ باردًا ورطّب جيدًا."
        }
    }
    if score >= 7:
        return {"score": score, "status": "Danger", "color": "red", "icon": "🔴",
                "advice": texts["Danger"]["ar" if lang=="Arabic" else "en"]}
    elif score >= 5:
        return {"score": score, "status": "High", "color": "orangered", "icon": "🟠",
                "advice": texts["High"]["ar" if lang=="Arabic" else "en"]}
    elif score >= 3:
        return {"score": score, "status": "Caution", "color": "orange", "icon": "🟡",
                "advice": texts["Caution"]["ar" if lang=="Arabic" else "en"]}
    else:
        return {"score": score, "status": "Safe", "color": "green", "icon": "🟢",
                "advice": texts["Safe"]["ar" if lang=="Arabic" else "en"]}

# ---------- Uhthoff floor: enforce minimum severity from ΔCore ----------
def apply_uhthoff_floor(risk: Dict[str, Any],
                        core: Optional[float],
                        baseline: Optional[float],
                        lang: str = "English") -> Dict[str, Any]:
    """ΔCore ≥0.5°C => ≥Caution; ΔCore ≥1.0°C => ≥High; never lowers severity. Localized advice."""
    if core is None or baseline is None:
        return risk
    try:
        delta = float(core) - float(baseline)
    except Exception:
        return risk

    texts = {
        "High": {
            "en": "Core ≥ 1.0°C above baseline (Uhthoff). Move to AC, pre‑cool, hydrate, rest 15–20 min.",
            "ar": "الأساسية ≥ 1.0°م فوق الأساس (أوتهوف). انتقل للمكيّف، برّد مسبقًا، رطّب، استرح 15–20 دقيقة."
        },
        "Caution": {
            "en": "Core ≥ 0.5°C above baseline (Uhthoff). Pre‑cool, limit exertion, hydrate, rest 15–20 min.",
            "ar": "الأساسية ≥ 0.5°م فوق الأساس (أوتهوف). برّد مسبقًا، قلّل الجهد، رطّب، واسترح 15–20 دقيقة."
        }
    }

    level = _STATUS_LEVEL.get(risk.get("status", "Safe"), 0)
    if delta >= 1.0 and level < _STATUS_LEVEL["High"]:
        risk.update({
            "status": "High", "color": "orangered", "icon": "🟠",
            "advice": texts["High"]["ar" if lang=="Arabic" else "en"]
        })
    elif delta >= 0.5 and level < _STATUS_LEVEL["Caution"]:
        risk.update({
            "status": "Caution", "color": "orange", "icon": "🟡",
            "advice": texts["Caution"]["ar" if lang=="Arabic" else "en"]
        })
    return risk

# ---------- Uhthoff hysteresis / latch ----------
UHTHOFF_RAISE = 0.5  # raise at +0.5°C
UHTHOFF_CLEAR = 0.3  # clear only once below +0.3°C

def update_uhthoff_latch(core: Optional[float], baseline: Optional[float]):
    """Live tab latch."""
    st.session_state.setdefault("_uhthoff_active", False)
    st.session_state.setdefault("_uhthoff_started_iso", None)
    st.session_state.setdefault("_uhthoff_alert_journaled", False)
    if core is None or baseline is None:
        return
    delta = float(core) - float(baseline)
    active_prev = st.session_state["_uhthoff_active"]
    if (not active_prev) and (delta >= UHTHOFF_RAISE):
        st.session_state["_uhthoff_active"] = True
        st.session_state["_uhthoff_started_iso"] = utc_iso_now()
        st.session_state["_uhthoff_alert_journaled"] = False
    if active_prev and (delta < UHTHOFF_CLEAR):
        st.session_state["_uhthoff_active"] = False
        st.session_state["_uhthoff_started_iso"] = None
        st.session_state["_uhthoff_alert_journaled"] = False

def update_demo_uhthoff_latch(core: Optional[float], baseline: Optional[float]):
    """Demo tab latch (no journaling)."""
    st.session_state.setdefault("_demo_uhthoff_active", False)
    if core is None or baseline is None:
        return
    delta = float(core) - float(baseline)
    if (not st.session_state["_demo_uhthoff_active"]) and (delta >= UHTHOFF_RAISE):
        st.session_state["_demo_uhthoff_active"] = True
    if st.session_state["_demo_uhthoff_active"] and (delta < UHTHOFF_CLEAR):
        st.session_state["_demo_uhthoff_active"] = False

def _L(en: str, ar: str) -> str:
    return ar if (app_language == "Arabic") else en

def _status_label():
    return T.get("status", _L("Status", "الحالة"))

# -----------------------------------------------------------
#                      TABS VERSION
# -----------------------------------------------------------
def render_monitor():
    st.title("☀️ " + T["risk_dashboard"])
    if "user" not in st.session_state:
        st.warning(T["login_first"])
        return

    tabs = st.tabs([
        _L("📡 Live Sensor Data", "📡 بيانات مباشرة"),
        _L("🔬 Learn & Practice", "🔬 تعلّم وتدرّب")
    ])

    # =========================================================
    # TAB 1 — LIVE SENSOR DATA
    # =========================================================
    with tabs[0]:
        # Intro
        with st.expander("🔎 About sensors & temperatures" if app_language=="English" else "🔎 عن المستشعرات والقراءات", expanded=False):
            if app_language == "English":
                st.markdown("""
        **We use medical‑grade sensors connected to an ESP8266 microcontroller:**
        
        - **MAX30205**: Clinical‑grade digital sensor for **peripheral (skin) temperature**  
          (±0.1 °C accuracy; ideal for wearable health monitoring)
        
        - **MLX90614**: Infrared sensor for **core body temperature**  
          (non‑contact measurement with ±0.5 °C accuracy; estimates internal temperature)
        
        - **ESP8266 microcontroller**: Reads both sensors and sends data to the cloud
        """)
            else:
                st.markdown("""
        **نستخدم مستشعرات بدرجة طبية موصولة بوحدة ESP8266:**
        
        - **MAX30205**: مستشعر رقمي سريري لقياس **حرارة الجلد (الطرفية)**  
          (بدقة ±0.1°م، مناسب للمراقبة القابلة للارتداء)
        
        - **MLX90614**: مستشعر بالأشعة تحت الحمراء لقياس **الحرارة الأساسية**  
          (قياس غير تلامسي بدقة ±0.5°م، يقدّر الحرارة الداخلية)
        
        - **المتحكم الدقيق ESP8266**: يقرأ المستشعرين ويرسل البيانات إلى السحابة  
        """)

        # City / device
        default_city = st.session_state.get("current_city")
        if not default_city:
            prefs = load_user_prefs(st.session_state["user"])
            default_city = (prefs.get("home_city") or "Abu Dhabi,AE")
        col_city, col_dev = st.columns([2, 1])
        with col_city:
            city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES,
                                index=(GCC_CITIES.index(default_city) if default_city in GCC_CITIES else 0),
                                key="monitor_city",
                                format_func=lambda c: city_label(c, app_language))
            st.session_state["current_city"] = city
        with col_dev:
            st.session_state.setdefault("device_id", "esp8266-01")
            st.session_state["device_id"] = st.text_input(_L("🔌 Device ID", "🔌 معرّف الجهاز"),
                                                          st.session_state["device_id"])

        # Weather + baseline
        weather, w_err, _ = get_weather_cached(city)
        baseline = float(st.session_state.get("baseline", 37.0))
        st.caption(_L(f"Baseline: **{baseline:.1f}°C**", f"خط الأساس: **{baseline:.1f}°م**"))

        # Latest + time window
        device_id = st.session_state["device_id"]
        sample = fetch_latest_sensor_sample(device_id)
        series = fetch_sensor_series(device_id, limit=240)

        # Recency
        last_update_label, is_stale = "—", True
        active_tz = get_active_tz()
        if sample and sample.get("at"):
            try:
                dt = datetime.fromisoformat(sample["at"].replace("Z","+00:00"))
                mins = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
                last_update_label = dt.astimezone(active_tz).strftime("%Y-%m-%d %H:%M") + \
                                    (_L(f" • {mins}m ago", f" • قبل {mins} دقيقة"))
                is_stale = mins >= 3
            except Exception:
                pass

        # Top strip
        colA, colB, colC, colD = st.columns([1.6,1,1,1.4])
        with colA:
            st.markdown(_L("**🔌 Sensor Hub**", "**🔌 محور المستشعرات**"))
            st.caption(_L(
                f"Device: {device_id} • Last: {last_update_label}",
                f"الجهاز: {device_id} • آخر تحديث: {last_update_label}"
            ) + ( _L(" • ⚠️ stale", " • ⚠️ قديمة") if is_stale else "" ))
        with colB:
            fl = weather.get("feels_like") if weather else None
            st.metric(_L("Feels‑like", "المحسوسة"), f"{fl:.1f}°C" if fl is not None else "—")
        with colC:
            hum = weather.get("humidity") if weather else None
            st.metric(_L("Humidity", "الرطوبة"), f"{int(hum)}%" if hum is not None else "—")
        with colD:
            if st.button(T.get("refresh_weather", _L("🔄 Refresh weather now", "🔄 تحديث الطقس الآن"))):
                try: get_weather.clear()
                except Exception: pass
                st.session_state["_weather_cache"] = {}
                st.rerun()

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        core_val = sample.get("core") if sample else None
        peri_val = sample.get("peripheral") if sample else None
        with col1:
            if core_val is not None:
                delta = core_val - baseline
                st.metric(_L("Core", "الأساسية"), f"{core_val:.1f}°C", f"{delta:+.1f}°C",
                          delta_color=("inverse" if delta >= 0.5 else "normal"))
            else:
                st.info(_L("Core: —", "الأساسية: —"))
        with col2:
            if peri_val is not None:
                st.metric(_L("Peripheral", "الطرفية"), f"{peri_val:.1f}°C")
            else:
                st.info(_L("Peripheral: —", "الطرفية: —"))
        with col3:
            if core_val is not None:
                st.caption(_L(f"ΔCore from baseline: {core_val - baseline:+.1f}°C",
                              f"Δالأساسية عن الأساس: {core_val - baseline:+.1f}°م"))
            else:
                st.caption(_L("ΔCore: —", "Δالأساسية: —"))
        with col4:
            if is_stale:
                st.error(_L("⚠️ Readings stale (>3 min). Check power/Wi‑Fi.",
                            "⚠️ القراءات قديمة (>3 دقائق). تحقق من الطاقة/الواي فاي."))
            else:
                st.success(_L("Live", "مباشر"))

        # Risk + Uhthoff + logging
        risk = None
        if weather and (core_val is not None):
            risk = compute_risk_minimal(weather["feels_like"], weather["humidity"], core_val, baseline, app_language)
            risk = apply_uhthoff_floor(risk, core_val, baseline, app_language)

            st.markdown(f"""
            <div class="big-card" style="--left:{risk['color']}">
              <h3>{risk['icon']} <strong>{_status_label()}: {risk['status']}</strong></h3>
              <p style="margin:6px 0 0 0">{risk['advice']}</p>
            </div>
            """, unsafe_allow_html=True)

            update_uhthoff_latch(core_val, baseline)
            if st.session_state["_uhthoff_active"] and not st.session_state["_uhthoff_alert_journaled"]:
                entry = {
                    "type":"ALERT_AUTO","at": utc_iso_now(),
                    "core_temp": round(core_val,2), "baseline": round(baseline,2),
                    "delta_core": round(core_val - baseline,2),
                    "reasons": ["ΔCore ≥ 0.5°C (Uhthoff)"],
                    "symptoms": [],
                    "city": city,
                    "feels_like": float(weather["feels_like"]),
                    "humidity": float(weather["humidity"]),
                    "device_id": device_id
                }
                insert_journal(st.session_state.get("user","guest"), utc_iso_now(), entry)
                st.session_state["_uhthoff_alert_journaled"] = True
                st.warning(_L("⚠️ Uhthoff trigger logged to Journal", "⚠️ تم تسجيل تنبيه أوتهوف في اليوميات"))

            # Alert details (only when active)
            if st.session_state["_uhthoff_active"]:
                sym_opts  = _symptoms_for_ui(app_language)
                trig_opts = _triggers_for_ui(app_language)
                with st.expander(_L("Add symptoms/notes to this alert", "أضف أعراض/ملاحظات لهذا التنبيه")):
                    sel_sym = st.multiselect(_L("Symptoms", "الأعراض"), sym_opts, key="alert_sym_ms")
                    sym_other = st.text_input(_L("Other symptom (optional)", "أعراض أخرى (اختياري)"), key="alert_sym_other")
                    sel_trig = st.multiselect(_L("Triggers / Activity", "محفزات / نشاط"), trig_opts, key="alert_trig_ms")
                    trig_other = st.text_input(_L("Other trigger/activity (optional)", "محفز/نشاط آخر (اختياري)"), key="alert_trig_other")
                    note = st.text_area(_L("Notes (optional)", "ملاحظات (اختياري)"), height=60, key="alert_note")
                    if st.button(_L("Append to Journal alert", "إضافة إلى اليوميات"), key="alert_append_btn"):
                        symptoms_final = sel_sym + ([f"{_L('Other','أخرى')}: {sym_other.strip()}"] if sym_other.strip() else [])
                        triggers_final = sel_trig + ([f"{_L('Other','أخرى')}: {trig_other.strip()}"] if trig_other.strip() else [])
                        insert_journal(
                            st.session_state.get("user","guest"), utc_iso_now(),
                            {"type":"NOTE","at": utc_iso_now(),
                             "text": _L(
                                 f"Alert details — Symptoms: {symptoms_final}; Triggers/Activity: {triggers_final}; Note: {note.strip()}",
                                 f"تفاصيل التنبيه — الأعراض: {symptoms_final}; المحفزات/النشاط: {triggers_final}; ملاحظة: {note.strip()}"
                             )}
                        )
                        st.success(_L("Added to Journal", "تمت الإضافة"))

        elif not weather:
            st.error(f"{T['weather_fail']}: {w_err or '—'}")

        # Manual alert
        with st.expander(_L("Log alert manually", "سجّل تنبيهًا يدويًا")):
            sym_opts  = _symptoms_for_ui(app_language)
            trig_opts = _triggers_for_ui(app_language)
            sel_sym = st.multiselect(_L("Symptoms", "الأعراض"), sym_opts, key="man_sym_ms")
            sym_other = st.text_input(_L("Other symptom (optional)", "أعراض أخرى (اختياري)"), key="man_sym_other")
            sel_trig = st.multiselect(_L("Triggers / Activity", "محفزات / نشاط"), trig_opts, key="man_trig_ms")
            trig_other = st.text_input(_L("Other trigger/activity (optional)", "محفز/نشاط آخر (اختياري)"), key="man_trig_other")
            mnote = st.text_area(_L("Notes", "ملاحظات"), height=70, key="man_note")
            if st.button(_L("Save manual alert", "حفظ التنبيه"), key="man_alert_btn"):
                symptoms_final = sel_sym + ([f"{_L('Other','أخرى')}: {sym_other.strip()}"] if sym_other.strip() else [])
                triggers_final = sel_trig + ([f"{_L('Other','أخرى')}: {trig_other.strip()}"] if trig_other.strip() else [])
                entry = {
                    "type":"ALERT","at": utc_iso_now(),
                    "core_temp": round(core_val,2) if core_val is not None else None,
                    "baseline": round(baseline,2),
                    "delta_core": round(core_val - baseline,2) if core_val is not None else None,
                    "reasons": ["Manual"],
                    "symptoms": symptoms_final,
                    "triggers": triggers_final,
                    "city": city,
                    "feels_like": float(weather["feels_like"]) if weather else None,
                    "humidity": float(weather["humidity"]) if weather else None,
                    "device_id": device_id
                }
                insert_journal(st.session_state.get("user","guest"), utc_iso_now(), entry)
                st.success(_L("Saved", "تم الحفظ"))

        # Recovery log on improvement
        if weather and ('risk' in locals() and risk is not None):
            curr = {
                "status": risk["status"],
                "level": {"Safe":0,"Caution":1,"High":2,"Danger":3}[risk["status"]],
                "time_iso": utc_iso_now(),
                "core": float(core_val) if core_val is not None else None,
                "periph": float(peri_val) if peri_val is not None else None,
                "feels": float(weather["feels_like"]),
                "humidity": float(weather["humidity"]),
                "city": city
            }
            prev = st.session_state.get("_risk_track")
            st.session_state["_risk_track"] = curr
            if prev and (curr["level"] < prev["level"]):
                st.success(_L(f"✅ Improved: {prev['status']} → {curr['status']}. What helped?",
                              f"✅ تحسّن: {prev['status']} → {curr['status']}. ما الذي ساعد؟"))
                with st.form("recovery_form_live", clear_on_submit=True):
                    acts = st.multiselect(_L("Cooling actions used", "إجراءات التبريد التي استُخدمت"),
                                          _actions_for_ui(app_language))
                    act_other = st.text_input(_L("Other action (optional)", "إجراء آخر (اختياري)"))
                    note = st.text_area(_L("Details (optional)", "تفاصيل (اختياري)"), height=70)
                    saved = st.form_submit_button(_L("Save Recovery", "حفظ التعافي"))
                if saved:
                    actions_final = acts + ([f"{_L('Other','أخرى')}: {act_other.strip()}"] if act_other.strip() else [])
                    try:
                        t1 = datetime.fromisoformat(prev["time_iso"].replace("Z","+00:00"))
                        t2 = datetime.fromisoformat(curr["time_iso"].replace("Z","+00:00"))
                        dur = int((t2 - t1).total_seconds() // 60)
                    except Exception:
                        dur = None
                    entry = {
                        "type":"RECOVERY","at": utc_iso_now(),
                        "from_status": prev["status"], "to_status": curr["status"],
                        "actions": actions_final, "note": note.strip(),
                        "core_before": round(prev["core"],2) if prev.get("core") is not None else None,
                        "core_after": round(curr["core"],2) if curr.get("core") is not None else None,
                        "peripheral_before": round(prev.get("periph",0.0),2) if prev.get("periph") is not None else None,
                        "peripheral_after": round(curr.get("periph",0.0),2) if curr.get("periph") is not None else None,
                        "feels_like_before": round(prev.get("feels",0.0),2) if prev.get("feels") is not None else None,
                        "feels_like_after": round(curr.get("feels",0.0),2) if curr.get("feels") is not None else None,
                        "humidity_before": int(prev.get("humidity",0)) if prev.get("humidity") is not None else None,
                        "humidity_after": int(curr.get("humidity",0)) if curr.get("humidity") is not None else None,
                        "city": city, "duration_min": dur
                    }
                    insert_journal(st.session_state.get("user","guest"), utc_iso_now(), entry)
                    st.success(_L("Recovery saved", "تم حفظ التعافي"))

        # Charts (Live)
        st.markdown("---")
        if series:
            times  = [datetime.fromisoformat(r["created_at"].replace("Z","+00:00")).astimezone(active_tz) for r in series]
            core_s = [float(r["core_c"]) if r.get("core_c") is not None else None for r in series]
            peri_s = [float(r["peripheral_c"]) if r.get("peripheral_c") is not None else None for r in series]
            fl_s   = [float(r["feels_like"]) if ("feels_like" in r and r["feels_like"] is not None) else None for r in series]

            # 1) Core & Peripheral
            st.subheader(_L("Core & Peripheral (Live)", "الأساسية والطرفية (مباشر)"))
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=times, y=core_s, mode="lines+markers", name=_L("Core","الأساسية")))
            fig1.add_trace(go.Scatter(x=times, y=peri_s, mode="lines+markers", name=_L("Peripheral","الطرفية")))
            fig1.update_layout(height=300, margin=dict(l=10,r=10,t=10,b=10),
                               xaxis_title=_L("Time (Local)","الوقت (المحلي)"),
                               yaxis_title=_L("Temperature (°C)","درجة الحرارة (°م)"),
                               legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig1, use_container_width=True)

            # Raw data (after chart 1)
            with st.expander(_L("Raw data","البيانات الخام"), expanded=False):
                df = pd.DataFrame({
                    _L("Time (Local)","الوقت (المحلي)"): [t.strftime("%Y-%m-%d %H:%M:%S") for t in times],
                    _L("Core (°C)","الأساسية (°م)"): core_s,
                    _L("Peripheral (°C)","الطرفية (°م)"): peri_s,
                })
                st.dataframe(df.iloc[::-1], use_container_width=True)

            # sampling caption
            if len(times) >= 2:
                gaps_sec = [(times[i]-times[i-1]).total_seconds() for i in range(1, len(times))]
                med_gap = statistics.median(gaps_sec)
                hours = (times[-1] - times[0]).total_seconds() / 3600
                st.caption(_L(f"Sampling: ~{med_gap/60:.1f} min between points • Window: ~{hours:.1f} h",
                              f"التقاط: ~{med_gap/60:.1f} دقيقة بين النقاط • نافذة: ~{hours:.1f} ساعة"))

            # 2) Core, Peripheral & Feels-like
            st.subheader(_L("Core, Peripheral & Feels‑like (Live)",
                            "الأساسية، الطرفية والمحسوسة (مباشر)"))
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=times, y=core_s, mode="lines+markers", name=_L("Core","الأساسية")))
            fig2.add_trace(go.Scatter(x=times, y=peri_s, mode="lines+markers", name=_L("Peripheral","الطرفية")))
            if any(v is not None for v in fl_s):
                fig2.add_trace(go.Scatter(x=times, y=fl_s, mode="lines+markers", name=_L("Feels‑like","المحسوسة")))
            else:
                fl_now = float(weather["feels_like"]) if (weather and weather.get("feels_like") is not None) else None
                if fl_now is not None and len(times) > 0:
                    fig2.add_trace(go.Scatter(
                        x=times, y=[fl_now]*len(times), mode="lines",
                        name=_L("Feels‑like (current)","المحسوسة (الحالية)"),
                        line=dict(dash="dash")
                    ))
            fig2.update_layout(height=300, margin=dict(l=10,r=10,t=10,b=10),
                               xaxis_title=_L("Time (Local)","الوقت (المحلي)"),
                               yaxis_title=_L("Temperature (°C)","درجة الحرارة (°م)"),
                               legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info(_L("No recent Supabase readings yet. Once your device uploads, you’ll see a live chart here.",
                       "لا توجد قراءات حديثة من Supabase بعد. عند رفع الجهاز للبيانات ستظهر الرسوم هنا."))

    # =========================================================
    # TAB 2 — DEMO / LEARN (simulation only; no journaling)
    # =========================================================
    with tabs[1]:
        st.info(_L(
            "Adjust the Core body temperature, Baseline, and Feels‑like temperature. "
            "The risk assessment uses the same calculation method as Live. "
            "Humidity is under Advanced options. Demo does not save to Journal.",
            "اضبط الحرارة الأساسية، خط الأساس، والمحسوسة. "
            "يعتمد التقييم على نفس منطق الوضع المباشر. "
            "الرطوبة ضمن الخيارات المتقدمة. الوضع التجريبي لا يحفظ في اليوميات."
        ))

        st.session_state.setdefault("sim_core", 36.8)
        st.session_state.setdefault("sim_base", st.session_state.get("baseline", 37.0))
        st.session_state.setdefault("sim_feels", 32.0)
        st.session_state.setdefault("sim_hum", 50.0)  # risk only
        st.session_state.setdefault("sim_history", [])
        st.session_state.setdefault("sim_live", False)
        st.session_state.setdefault("_demo_risk_track", None)
        st.session_state.setdefault("_demo_uhthoff_active", False)

        colL, colR = st.columns([1,1])
        with colL:
            st.subheader(_L("Inputs", "المدخلات"))
            st.session_state["sim_core"]  = st.slider(_L("Core (°C)", "الأساسية (°م)"), 36.0, 39.5, float(st.session_state["sim_core"]), 0.1)
            st.session_state["sim_base"]  = st.slider(_L("Baseline (°C)", "خط الأساس (°م)"), 36.0, 37.5, float(st.session_state["sim_base"]), 0.1)
            st.session_state["sim_feels"] = st.slider(_L("Feels‑like (°C)", "المحسوسة (°م)"), 25.0, 50.0, float(st.session_state["sim_feels"]), 0.5)
            with st.expander(_L("Advanced (Humidity)", "خيارات متقدمة (الرطوبة)")):
                st.session_state["sim_hum"] = st.slider(_L("Humidity (%)", "الرطوبة (%)"), 10, 95, int(st.session_state["sim_hum"]), 1)

            live_toggle = st.toggle(_L("Record changes automatically","تسجيل التغييرات تلقائيًا"), value=st.session_state["sim_live"])
            if live_toggle and not st.session_state["sim_live"]:
                st.session_state["sim_history"].append({
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "core": float(st.session_state["sim_core"]),
                    "baseline": float(st.session_state["sim_base"]),
                    "feels": float(st.session_state["sim_feels"])
                })
            st.session_state["sim_live"] = live_toggle

            if st.button(_L("Clear chart", "مسح الرسم")):
                st.session_state["sim_history"].clear()
                st.success(_L("Cleared", "تم المسح"))

        with colR:
            sim_core   = float(st.session_state["sim_core"])
            sim_base   = float(st.session_state["sim_base"])
            sim_feels  = float(st.session_state["sim_feels"])
            sim_hum    = float(st.session_state["sim_hum"])

            sim_risk   = compute_risk_minimal(sim_feels, sim_hum, sim_core, sim_base, app_language)
            sim_risk   = apply_uhthoff_floor(sim_risk, sim_core, sim_base, app_language)

            st.subheader(_status_label())
            st.markdown(f"""
            <div class="big-card" style="--left:{sim_risk['color']}">
              <h3>{sim_risk['icon']} <strong>{_status_label()}: {sim_risk['status']}</strong></h3>
              <p style="margin:6px 0 0 0">{sim_risk['advice']}</p>
            </div>
            """, unsafe_allow_html=True)
            st.caption(_L(
                f"ΔCore from baseline: {sim_core - sim_base:+.1f}°C  •  Humidity (demo): {int(sim_hum)}%",
                f"Δالأساسية عن الأساس: {sim_core - sim_base:+.1f}°م  •  الرطوبة (تجريبي): {int(sim_hum)}%"
            ))

            update_demo_uhthoff_latch(sim_core, sim_base)
            curr_demo = {
                "status": sim_risk["status"],
                "level": {"Safe":0,"Caution":1,"High":2,"Danger":3}[sim_risk["status"]],
                "time_iso": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
                "core": sim_core, "feels": sim_feels, "humidity": sim_hum
            }
            prev_demo = st.session_state.get("_demo_risk_track")
            st.session_state["_demo_risk_track"] = curr_demo

            # Same UI affordances (no saves in demo)
            if st.session_state["_demo_uhthoff_active"]:
                sym_opts  = _symptoms_for_ui(app_language)
                trig_opts = _triggers_for_ui(app_language)
                with st.expander(_L("Alert details (demo — not saved)", "تفاصيل التنبيه (تجريبي — لا يُحفَظ)")):
                    st.multiselect(_L("Symptoms", "الأعراض"), sym_opts, key="demo_alert_sym_ms")
                    st.text_input(_L("Other symptom (optional)", "أعراض أخرى (اختياري)"), key="demo_alert_sym_other")
                    st.multiselect(_L("Triggers / Activity", "محفزات / نشاط"), trig_opts, key="demo_alert_trig_ms")
                    st.text_input(_L("Other trigger/activity (optional)", "محفز/نشاط آخر (اختياري)"), key="demo_alert_trig_other")
                    st.text_area(_L("Notes (optional)", "ملاحظات (اختياري)"), height=60, key="demo_alert_note")
                    if st.button(_L("Simulate append (not saved)", "محاكاة إضافة (لن تُحفَظ)"), key="demo_alert_append_btn"):
                        st.info(_L("Demo: In Live, this would append to the active alert in Journal.",
                                   "تجريبي: في الوضع المباشر سيتم إلحاق التفاصيل بتنبيه اليوميات الحالي."))

            if prev_demo and (curr_demo["level"] < prev_demo["level"]):
                st.success(_L("✅ Improved (demo). What helped?", "✅ تحسّن (تجريبي). ما الذي ساعد؟"))
                with st.form("recovery_form_demo", clear_on_submit=True):
                    st.multiselect(_L("Cooling actions used", "إجراءات التبريد التي استُخدمت"), _actions_for_ui(app_language))
                    st.text_input(_L("Other action (optional)", "إجراء آخر (اختياري)"))
                    st.text_area(_L("Details (optional)", "تفاصيل (اختياري)"), height=70)
                    save_demo = st.form_submit_button(_L("Simulate save (not saved)", "حفظ تجريبي (لن يُحفَظ)"))
                if save_demo:
                    st.info(_L("Demo: In Live, this would save a RECOVERY entry with your actions and notes.",
                               "تجريبي: في الوضع المباشر سيتم حفظ مدخلة تعافٍ بهذه الإجراءات والملاحظات."))

            if st.session_state["sim_live"]:
                st.session_state["sim_history"].append({
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "core": sim_core, "baseline": sim_base, "feels": sim_feels
                })

        # Demo chart
        st.markdown("---")
        if st.session_state["sim_history"]:
            df = pd.DataFrame(st.session_state["sim_history"])
            st.subheader(_L("Core, Feels‑like & Baseline (Demo)", "الأساسية، المحسوسة، وخط الأساس (تجريبي)"))
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["ts"], y=df["core"], mode="lines+markers", name=_L("Core","الأساسية")))
            fig.add_trace(go.Scatter(x=df["ts"], y=df["feels"], mode="lines+markers", name=_L("Feels‑like","المحسوسة")))
            fig.add_trace(go.Scatter(x=df["ts"], y=df["baseline"], mode="lines", name=_L("Baseline","خط الأساس")))
            fig.update_layout(height=300, margin=dict(l=10,r=10,t=10,b=10),
                              legend=dict(orientation="h", y=1.1),
                              xaxis_title=_L("Time (Demo session)","الوقت (جلسة تجريبية)"),
                              yaxis_title=_L("Temperature (°C)","درجة الحرارة (°م)"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(_L("Adjust the sliders (and enable recording) to see the chart.",
                       "حرّك المنزلقات (وفعِّل التسجيل) لرؤية الرسم."))



# ================== JOURNAL (includes RECOVERY) ==================
def render_journal():
    st.title("📒 " + T["journal"])
    if "user" not in st.session_state:
        st.warning(T["login_first"])
        return

    # Use the dynamic timezone (same behavior as Monitor)
    active_tz = get_active_tz()

    st.caption(T["journal_hint"])

    # Daily quick logger
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        mood_options = (
            ["🙂 Okay", "😌 Calm", "😕 Low", "😣 Stressed", "😴 Tired"]
            if app_language=="English" else
            ["🙂 بخير", "😌 هادئ", "😕 منخفض", "😣 متوتر", "😴 متعب"]
        )
        mood = st.selectbox(T["mood"], mood_options, key="jr_mood")
    with col2:
        hydration = st.slider(T["hydration"], 0, 12, 6, key="jr_hydration_slider")
    with col3:
        sleep = st.slider(T["sleep"], 0, 12, 7, key="jr_sleep_slider")
    with col4:
        fatigue_options = [f"{i}/10" for i in range(0,11)]
        fatigue = st.selectbox(T["fatigue"], fatigue_options, index=4, key="jr_fatigue_sel")

    trigger_options = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
    symptom_options = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
    chosen_tr = st.multiselect(("Triggers (optional)" if app_language=="English" else "المحفزات (اختياري)"),
                               trigger_options, key="jr_triggers_ms")
    tr_other = st.text_input(f"{'Other' if app_language=='English' else 'أخرى'} ({T['trigger']})", "", key="jr_trigger_other")
    chosen_sy = st.multiselect(("Symptoms (optional)" if app_language=="English" else "الأعراض (اختياري)"),
                               symptom_options, key="jr_symptoms_ms")
    sy_other = st.text_input(f"{'Other' if app_language=='English' else 'أخرى'} ({T['symptom']})", "", key="jr_symptom_other")
    free_note = st.text_area(T["free_note"], height=100, key="jr_free_note")

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

    # Load rows (SQLite as per your current implementation)
    c = get_conn().cursor()
    c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC", (st.session_state["user"],))
    rows = c.fetchall()
    if not rows:
        st.info("No journal entries yet." if app_language=="English" else "لا توجد مدخلات بعد.")
        return

    available_types = ["PLAN","ALERT","ALERT_AUTO","RECOVERY","DAILY","NOTE"]
    type_filter = st.multiselect(T["filter_by_type"], options=available_types, default=available_types, key="jr_type_filter")
    page_size = 12
    st.session_state.setdefault("journal_offset", 0)
    start = st.session_state["journal_offset"]; end = start + 200
    chunk = rows[start:end]

    def _render_entry(raw_entry_json):
        try:
            obj = json.loads(raw_entry_json)
        except Exception:
            obj = {"type":"NOTE","at": utc_iso_now(), "text": str(raw_entry_json)}
        t = obj.get("type","NOTE")
        when = obj.get("at", utc_iso_now())
        try:
            dt = _dt.fromisoformat(when.replace("Z","+00:00"))
        except Exception:
            dt = _dt.now(timezone.utc)

        # >>> replaced TZ_DUBAI with active_tz
        when_label = dt.astimezone(active_tz).strftime("%Y-%m-%d %H:%M")

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
            meta = (f"Feels‑like {round(fl,1)}°C • Humidity {int(hum)}%" if (fl is not None and hum is not None) else "")
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
        if t not in type_filter:
            continue
        try:
            dt = _dt.fromisoformat(dt_raw.replace("Z","+00:00"))
        except Exception:
            dt = _dt.now(timezone.utc)
        # >>> replaced TZ_DUBAI with active_tz
        day_key = dt.astimezone(active_tz).strftime("%A, %d %B %Y")
        parsed.append((day_key, title, body, icon))

    current_day = None; shown = 0
    for day, title, body, icon in parsed:
        if shown >= page_size:
            break
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
            if st.button(T["newer"], key="jr_newer"):
                st.session_state["journal_offset"] = max(0, st.session_state["journal_offset"] - page_size)
                st.rerun()
    with colp2:
        if (start + shown) < len(rows):
            if st.button(T["older"], key="jr_older"):
                st.session_state["journal_offset"] += page_size
                st.rerun()


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
