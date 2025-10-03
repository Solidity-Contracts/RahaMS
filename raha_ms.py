import streamlit as st
import sqlite3, json, requests, random, time, zipfile, io
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
from datetime import datetime as _dt
import json
import re
from supabase import create_client, Client

# Make sure minus signs render with Arabic fonts too
matplotlib.rcParams["axes.unicode_minus"] = False

# Pick an Arabic-capable font (first available)
from matplotlib.font_manager import FontProperties
_ARABIC_FONTS_TRY = ["Noto Naskh Arabic", "Amiri", "DejaVu Sans", "Arial"]
for _fname in _ARABIC_FONTS_TRY:
    try:
        # If font is installed, set it globally and stop
        matplotlib.rcParams["font.family"] = _fname
        break
    except Exception:
        continue

# ---- Arabic text shaping for Matplotlib (safe fallback if libs missing)
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    def ar_shape(s: str) -> str:
        # reshape + apply bidi so Arabic displays connected and RTL
        return get_display(arabic_reshaper.reshape(s))
    _HAS_AR_SHAPER = True
except Exception:
    def ar_shape(s: str) -> str:
        return s
    _HAS_AR_SHAPER = False

# Convenience: font props for titles/legends using whatever we picked
_AR_FONT = FontProperties(family=matplotlib.rcParams["font.family"])

# ================== CONFIG ==================
st.set_page_config(page_title="Tanzim MS", page_icon="🌡️", layout="wide")
TZ_DUBAI = ZoneInfo("Asia/Dubai")

# Secrets (fail gracefully if missing)
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", "")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", "")

# GCC quick picks
GCC_CITIES = [
    "Abu Dhabi,AE", "Dubai,AE", "Sharjah,AE",
    "Doha,QA", "Al Rayyan,QA", "Kuwait City,KW",
    "Manama,BH", "Riyadh,SA", "Jeddah,SA", "Dammam,SA",
    "Muscat,OM"
]

# GCC quick picks (display labels by language)
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


# ===== Live/Alert config =====
SIM_INTERVAL_SEC = 60  # default sensor/sample update (sec)
DB_WRITE_EVERY_N = 3
ALERT_DELTA_C = 0.5
ALERT_CONFIRM = 2
ALERT_COOLDOWN_SEC = 300
SMOOTH_WINDOW = 3

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
        "baseline_caption": "ℹ️ Baseline is used by the Heat Safety Monitor to decide when to alert (≥ 0.5°C above your baseline).",
        # Monitor specific
        "current_readings": "Current Sensor Readings",
        "log_health_event": "Log Health Event",
        "temperature_alert": "Temperature Alert",
        "health_log": "Health Log",
        "event_description": "Event description (optional)",
        "log_event": "Log Event",
        "event_logged": "Event logged to journal",
    },
    "Arabic": {
        "about_title": "عن تطبيق تنظيم إم إس",
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
        "baseline_caption": "ℹ️ تُستخدم القيمة الأساسية بواسطة مراقب السلامة الحرارية لتحديد وقت التنبيه (≥ ‎0.5°م فوق خطك الأساسي).",
        # Monitor specific Arabic
        "current_readings": "قراءات المستشعرات الحالية",
        "log_health_event": "تسجيل حدث صحي",
        "temperature_alert": "تنبيه درجة الحرارة",
        "health_log": "سجل الصحة",
        "event_description": "وصف الحدث (اختياري)",
        "log_event": "تسجيل الحدث",
        "event_logged": "تم تسجيل الحدث في اليوميات",
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

# ================== STYLES ==================
ACCESSIBLE_CSS = """
<style>
html, body, [class*="css"] { font-size: 18px; }

/* THEME-AWARE COLORS FOR CARDS & BADGES (fix dark mode contrast) */
:root {
  --card-bg: #ffffff;
  --card-fg: #0f172a;          /* slate-900 */
  --chip-border: rgba(0,0,0,0.12);
  --muted-fg: rgba(15,23,42,0.75);
}
@media (prefers-color-scheme: dark) {
  :root {
    --card-bg: #0b1220;        /* dark card */
    --card-fg: #e5e7eb;        /* slate-200 */
    --chip-border: rgba(255,255,255,0.25);
    --muted-fg: rgba(229,231,235,0.85);
  }
}
.big-card {
  background: var(--card-bg);
  color: var(--card-fg);
  padding: 18px;
  border-radius: 14px;
  border-left: 10px solid var(--left);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.big-card h3, .big-card p, .big-card .small { color: var(--card-fg); }

.badge {
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--chip-border);
  margin-right: 6px;
  color: var(--card-fg);
}
.small { opacity: 1; color: var(--muted-fg); font-size: 14px; }

h3 { margin-top: 0.2rem; }
.stButton>button { padding: 0.6rem 1.1rem; font-weight: 600; }

/* Global list spacing for readability (EN + AR, light + dark) */
.stMarkdown ul li, .stMarkdown ol li { margin-bottom: 0.6em !important; }
.stMarkdown ul, .stMarkdown ol { margin-bottom: 0.4em !important; }

/* RTL Support (safe: do NOT touch the sidebar container here) */
[dir="rtl"] .stSlider > div:first-child { direction: ltr; }
[dir="rtl"] .stSlider label { text-align: right; direction: rtl; }
[dir="rtl"] .stSelectbox label, [dir="rtl"] .stTextInput label, [dir="rtl"] .stTextArea label { text-align: right; direction: rtl; }
[dir="rtl"] .stRadio > label { direction: rtl; text-align: right; }
[dir="rtl"] .stMultiSelect label { text-align: right; direction: rtl; }

/* Icons for sliders */
.slider-with-icon { display: flex; align-items: center; gap: 10px; }
.slider-icon { font-size: 24px; min-width: 30px; }
</style>
"""
st.markdown(ACCESSIBLE_CSS, unsafe_allow_html=True)

# -# ---------- RTL SIDEBAR FIX (Arabic mobile + desktop) ----------
SAFE_RTL_CSS = """
<style>
/* Make the MAIN CONTENT RTL; do NOT touch the sidebar container here */
[dir="rtl"] [data-testid="stAppViewContainer"] {
  direction: rtl !important;
  text-align: right !important;
}

/* Sidebar container stays LTR so its slide animation/collapse works */
[dir="rtl"] [data-testid="stSidebar"] {
  direction: ltr !important;
  text-align: left !important;
}

/* Flip ONLY the sidebar inner content to RTL for reading order */
[dir="rtl"] [data-testid="stSidebar"] > div {
  direction: rtl !important;
  text-align: right !important;
}

/* Mobile polish: scrollable tab headers; avoid overlap after tabs */
@media (max-width: 640px) {
  div[role="tablist"] {
    overflow-x: auto !important;
    white-space: nowrap !important;
    padding-bottom: 6px !important;
    margin-bottom: 8px !important;
  }
  .stTabs + div, .stTabs + section {
    margin-top: 6px !important;
  }
}

/* Ensure bullets/paragraphs keep theme contrast */
.stMarkdown p, .stMarkdown li { color: inherit !important; }
</style>
"""
st.markdown(SAFE_RTL_CSS, unsafe_allow_html=True)

# ================== DB ==================
@st.cache_resource
def get_conn():
    conn = sqlite3.connect("raha_ms.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def ensure_emergency_contacts_schema():
    """Make sure emergency_contacts has all expected columns."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(emergency_contacts)")
    cols = [r[1] for r in c.fetchall()]

    # Add missing updated_at column
    if "updated_at" not in cols:
        c.execute("ALTER TABLE emergency_contacts ADD COLUMN updated_at TEXT")
        # backfill existing rows
        c.execute("UPDATE emergency_contacts SET updated_at = ?", (utc_iso_now(),))
        conn.commit()

def init_db():
    conn = get_conn()
    c = conn.cursor()
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

    # 🔧 Ensure columns exist even if the table was created before updated_at was added
    ensure_emergency_contacts_schema()
    
# ================== SUPABASE ==================
@st.cache_resource
def get_supabase() -> Client | None:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception:
        return None

def fetch_latest_sensor_sample(device_id: str) -> dict | None:
    """
    Returns: {"core": float, "peripheral": float, "at": iso_str} or None
    Expects Supabase table: sensor_readings(device_id text, core_c float8, peripheral_c float8, created_at timestamptz)
    """
    sb = get_supabase()
    if not sb or not device_id:
        return None
    try:
        res = (
            sb.table("sensor_readings")
              .select("core_c,peripheral_c,created_at")
              .eq("device_id", device_id)
              .order("created_at", desc=True)
              .limit(1)
              .execute()
        )
        data = res.data or []
        if not data:
            return None
        row = data[0]
        core = float(row.get("core_c"))
        peri = float(row.get("peripheral_c"))
        ts = row.get("created_at")
        return {"core": core, "peripheral": peri, "at": ts}
    except Exception:
        return None

def normalize_phone(s: str) -> str:
    """Keep digits and leading +; collapse spaces/dashes."""
    if not s:
        return ""
    s = s.strip()
    # allow one leading +, then digits
    s = re.sub(r"[^\d+]", "", s)
    # if multiple + signs slipped in, keep only the first and digits
    if s.count("+") > 1:
        s = "+" + re.sub(r"\D", "", s)
    # If no + and looks like local UAE 05..., you may optionally add +971 logic here.
    return s

def tel_href(s: str) -> str:
    """Safe value for tel: link (already normalized)."""
    return s

def utc_iso_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def save_emergency_contacts(username, primary_phone, secondary_phone):
    """Insert or update a single row per user. Returns (ok: bool, err: str|None)."""
    conn = get_conn()
    c = conn.cursor()
    p1 = normalize_phone(primary_phone)
    p2 = normalize_phone(secondary_phone)
    now = utc_iso_now()

    def _upsert():
        try:
            c.execute("""
                INSERT INTO emergency_contacts (username, primary_phone, secondary_phone, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    primary_phone=excluded.primary_phone,
                    secondary_phone=excluded.secondary_phone,
                    updated_at=excluded.updated_at
            """, (username, p1, p2, now))
        except sqlite3.OperationalError as oe:
            # Fallback for older SQLite without DO UPDATE
            if "ON CONFLICT" in str(oe):
                c.execute("""
                    INSERT OR REPLACE INTO emergency_contacts (username, primary_phone, secondary_phone, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (username, p1, p2, now))
            else:
                raise

    try:
        try:
            _upsert()
        except sqlite3.OperationalError as oe:
            # If the column doesn't exist yet, migrate and retry once
            if "no column named updated_at" in str(oe):
                ensure_emergency_contacts_schema()
                _upsert()
            else:
                raise
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
        
def load_emergency_contacts(username):
    """Return (primary, secondary) or ('','')."""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT primary_phone, secondary_phone
            FROM emergency_contacts
            WHERE username=?
        """, (username,))
        row = c.fetchone()
        if row:
            return row[0] or "", row[1] or ""
        return "", ""
    except Exception as e:
        print(f"❌ Error loading emergency contacts: {e}")
        return "", ""
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

#migrate_db()

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
        import xlsxwriter  # noqa
        engine = "xlsxwriter"
    except Exception:
        try:
            import openpyxl  # noqa
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
        if not arr:
            return q, None, None
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
    if score >= 7:
        status, color, icon, text = "Danger", "red", "🔴", "High risk: stay in cooled spaces, avoid exertion, use cooling packs, and rest. Seek clinical advice for severe symptoms."
    elif score >= 5:
        status, color, icon, text = "High", "orangered", "🟠", "Elevated risk: limit time outside (esp. midday), pre-cool and pace activities."
    elif score >= 3:
        status, color, icon, text = "Caution", "orange", "🟡", "Mild risk: hydrate, take breaks, prefer shade/AC, and monitor symptoms."
    else:
        status, color, icon, text = "Safe", "green", "🟢", "You look safe. Keep cool and hydrated."
    return {"score": score, "status": status, "color": color, "icon": icon, "advice": text}

# ---------- Heat Monitor helpers ----------
WEATHER_TTL_SEC = 15 * 60  # 15 minutes between weather refreshes unless user clicks Refresh

def get_weather_cached(city: str):
    """Session-scoped cache with visible 'last updated' time for the monitor."""
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

# ---------- Inline badge tooltips ----------
def _badge(label: str, value: str, tooltip: str) -> str:
    return ( f'<span class="badge" title="{tooltip}">'
             f'<strong>{label}:</strong> {value}</span>' )

EXPLAIN = {
    "EN": {
        "city": "Your selected city for weather.",
        "feels_like": "How the weather actually feels on your body (air temp plus humidity/wind).",
        "humidity": "Moisture in the air; higher humidity makes heat feel heavier.",
        "core": "Close to your internal body temperature. Can rise with exertion or heat.",
        "peripheral": "Skin/limb temperature. Often lower than core and moves with outdoor heat.",
        "baseline": "Your usual/normal body temperature used for alerts. You can change this in Settings."
    },
    "AR": {
        "city": "المدينة المختارة للطقس.",
        "feels_like": "كيف نشعر بالطقس فعليًا (درجة الهواء مع الرطوبة/الرياح).",
        "humidity": "كمية الرطوبة في الجو؛ كلما زادت شعرنا بالحرارة أكثر.",
        "core": "قريبة من حرارة الجسم الداخلية. قد ترتفع مع الجهد أو الحرارة.",
        "peripheral": "حرارة الجلد/الأطراف. غالبًا أقل من الأساسية وتتغير مع حرارة الجو.",
        "baseline": "حرارتك المعتادة المستخدمة للتنبيهات. يمكنك تعديلها من الإعدادات."
    }
}

# ================== Live helpers ==================
def moving_avg(seq, n):
    if not seq: return 0.0
    if len(seq) < n: return round(sum(seq)/len(seq), 2)
    return round(sum(seq[-n:]) / n, 2)

def should_alert(temp_series, baseline, delta=ALERT_DELTA_C, confirm=ALERT_CONFIRM):
    if len(temp_series) < confirm: return False
    recent = temp_series[-confirm:]
    return all((t - baseline) >= delta for t in recent)

def simulate_core_next(prev):
    drift = random.uniform(-0.05, 0.08)
    surge = random.uniform(0.2, 0.5) if random.random() < 0.12 else 0.0
    next_t = prev + drift + surge
    return max(35.5, min(41.0, round(next_t, 2)))

def simulate_peripheral_next(prev_core, prev_periph, feels_like):
    target = prev_core - random.uniform(0.4, 1.0)
    ambient_push = (feels_like - 32.0) * 0.02
    noise = random.uniform(-0.10, 0.10)
    next_p = prev_periph + (target - prev_periph) * 0.3 + ambient_push + noise
    return max(32.0, min(40.0, round(next_p, 2)))


# ====AI JOURNAL ENTRY ======

def get_recent_journal_context(username: str, max_entries: int = 5) -> str:
    """Get recent journal entries as context for AI"""
    try:
        c = get_conn().cursor()
        c.execute("""
            SELECT date, entry FROM journal 
            WHERE username=? 
            ORDER BY date DESC 
            LIMIT ?
        """, (username, max_entries))
        rows = c.fetchall()
        
        if not rows:
            return "No journal entries found."
        
        context_lines = []
        for date_str, entry_json in rows:
            try:
                entry_data = json.loads(entry_json)
                entry_type = entry_data.get('type', 'NOTE')
                
                if entry_type == 'DAILY':
                    mood = entry_data.get('mood', 'Unknown')
                    hydration = entry_data.get('hydration_glasses', 'Unknown')
                    sleep = entry_data.get('sleep_hours', 'Unknown')
                    fatigue = entry_data.get('fatigue', 'Unknown')
                    triggers = entry_data.get('triggers', [])
                    symptoms = entry_data.get('symptoms', [])
                    
                    context_lines.append(f"Daily Log: Mood={mood}, Hydration={hydration} glasses, Sleep={sleep} hrs, Fatigue={fatigue}")
                    if triggers:
                        context_lines.append(f"  Triggers: {', '.join(triggers)}")
                    if symptoms:
                        context_lines.append(f"  Symptoms: {', '.join(symptoms)}")
                        
                elif entry_type == 'ALERT':
                    body_temp = entry_data.get('body_temp')
                    baseline = entry_data.get('baseline')
                    reasons = entry_data.get('reasons', [])
                    symptoms = entry_data.get('symptoms', [])
                    
                    context_lines.append(f"Alert: Body temp={body_temp}°C, Baseline={baseline}°C")
                    if reasons:
                        context_lines.append(f"  Reasons: {', '.join(reasons)}")
                    if symptoms:
                        context_lines.append(f"  Symptoms: {', '.join(symptoms)}")
                        
                elif entry_type == 'PLAN':
                    activity = entry_data.get('activity', 'Unknown')
                    location = entry_data.get('city', 'Unknown')
                    feels_like = entry_data.get('feels_like')
                    
                    context_lines.append(f"Plan: {activity} in {location}, Feels-like={feels_like}°C")
                    
                elif entry_type == 'NOTE':
                    note_text = entry_data.get('text') or entry_data.get('note', '')
                    if note_text and len(note_text) > 10:  # Only include substantial notes
                        context_lines.append(f"Note: {note_text[:100]}...")
                        
            except Exception as e:
                # If JSON parsing fails, include raw text
                context_lines.append(f"Entry: {str(entry_json)[:100]}...")
        
        return "\n".join(context_lines) if context_lines else "No recent journal entries."
        
    except Exception as e:
        return f"Error reading journal: {str(e)}"
# ============AI-GET WEATHER CONTEXT============

def get_weather_context(city="Dubai,AE"):
    """Get current weather data formatted for AI context"""
    try:
        weather_data, error = get_weather(city)
        if weather_data is None:
            return None  # Return None so we know weather failed
        
        # Extract city name for display
        city_name = city.split(",")[0]
        
        return (
            f"REAL-TIME WEATHER DATA FOR {city_name.upper()}:\n"
            f"• Current Temperature: {weather_data['temp']}°C\n"
            f"• Feels Like: {weather_data['feels_like']}°C\n"
            f"• Humidity: {weather_data['humidity']}%\n"
            f"• Conditions: {weather_data['desc']}\n"
            f"• Peak Heat Times: {', '.join(weather_data.get('peak_hours', []))}"
        )
    except Exception as e:
        return None

# =========== 
def get_fallback_response(prompt, lang, journal_context="", weather_context=""):
    """Provide intelligent fallback responses when API fails"""
    
    prompt_lower = prompt.lower()
    
    # MS-specific fallback responses
    fallback_responses = {
        "English": {
            "weather": "I'd normally check real-time weather for you, but I'm having connection issues. Generally in the Gulf, remember to stay in AC during peak heat (11 AM-4 PM), hydrate well, and use cooling accessories.",
            "journal": "I'd typically review your journal entries now, but I'm temporarily offline. Based on common MS patterns, focus on hydration, pacing activities, and monitoring symptoms after heat exposure.",
            "travel": "For Gulf travel with MS, always pack cooling garments, plan indoor activities during peak heat, stay hydrated, and pre-cool before outings.",
            "symptoms": "With MS heat sensitivity, common triggers are direct sun, dehydration, and high humidity. Cool down with wrist baths, stay in AC, and rest when fatigued.",
            "general": "I'm here to help with MS heat management. While I'm having temporary connection issues, remember the basics: stay cool, hydrate, pace yourself, and listen to your body's signals."
        },
        "Arabic": {
            "weather": "كنت سأتحقق من الطقس لك، لكنني أواجه مشاكل في الاتصال. بشكل عام في الخليج، تذكر البقاء في المكيف خلال ساعات الذروة (11 صباحًا-4 عصرًا)، حافظ على الترطيب، واستخدم ملحقات التبريد.",
            "journal": "كنت سأراجع مدخلات اليوميات الآن، لكنني غير متصل مؤقتًا. بناءً على أنماط التصلب المتعدد الشائعة، ركز على الترطيب، تنظيم الأنشطة، ومراقبة الأعراض بعد التعرض للحرارة.",
            "travel": "لسفر الخليج مع التصلب المتعدد، احزم دائمًا ملابس التبريد، خطط للأنشطة الداخلية خلال ذروة الحر، حافظ على الترطيب، وبرد جسمك مسبقًا قبل الخروج.",
            "symptoms": "مع حساسية الحرارة في التصلب المتعدد، المحفزات الشائعة هي الشمس المباشرة، الجفاف، والرطوبة العالية. برد جسمك بحمامات المعصم، ابق في المكيف، وارتح عند الشعور بالتعب.",
            "general": "أنا هنا للمساعدة في إدارة حرارة التصلب المتعدد. بينما أواجه مشاكل اتصال مؤقتة، تذكر الأساسيات: ابق باردًا، رطب نفسك، نظم طاقتك، واستمع لإشارات جسدك."
        }
    }
    
    lang_dict = fallback_responses[lang]
    
    # Determine response type based on prompt
    if any(word in prompt_lower for word in ['weather', 'temperature', 'hot', 'heat', 'طقس', 'حرارة', 'حر']):
        response_type = "weather"
    elif any(word in prompt_lower for word in ['journal', 'entry', 'log', 'اليوميات', 'المذكرات', 'السجل']):
        response_type = "journal" 
    elif any(word in prompt_lower for word in ['travel', 'trip', 'سفر', 'رحلة']):
        response_type = "travel"
    elif any(word in prompt_lower for word in ['symptom', 'pain', 'fatigue', 'numbness', 'أعراض', 'ألم', 'تعب', 'خدر']):
        response_type = "symptoms"
    else:
        response_type = "general"
    
    # Add specific context if available
    base_response = lang_dict[response_type]
    
    if weather_context and "weather" in response_type:
        base_response += f"\n\n{weather_context}"
    
    return base_response
        
# ================== AI - DEEPSEEK ==================
def ai_response(prompt, lang, journal_context="", weather_context=""):
    if not DEEPSEEK_API_KEY:
        return None, "no_api_key"
    
    # Base system prompt
    sys_prompt = (
        "You are Raha MS AI Companion - a warm, empathetic assistant for people with Multiple Sclerosis in the Gulf region. "
        "Provide practical, culturally relevant advice for heat management and daily living with MS. "
        "Be supportive and understanding. Respond in a conversational, caring tone."
    )
    
    # Add contexts
    if journal_context:
        sys_prompt += f"\n\nUser's journal context:\n{journal_context}"
    if weather_context:
        sys_prompt += f"\n\nCurrent weather:\n{weather_context}"
    
    sys_prompt += " Respond only in Arabic." if lang == "Arabic" else " Respond only in English."
    
    # Try multiple attempts with shorter timeout
    max_retries = 2
    for attempt in range(max_retries):
        try:
            import requests
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500,
                "stream": False
            }
            
            # Shorter timeout for faster failure
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'], None
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                continue  # Try again
            else:
                return None, "timeout_error"
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                continue  # Try again  
            else:
                return None, "connection_error"
        except Exception as e:
            return None, f"api_error: {str(e)}"
    
    return None, "max_retries_exceeded"
        
# ================== ABOUT (EN/AR, user-friendly) ==================
def render_about_page(lang: str = "English"):
    # ====== Styles (aligned with other pages, but with a standout ribbon) ======
    st.markdown("""
    <style>
      .page-head { margin: 6px 0 10px 0; }
      .page-head h2 { margin: 0 0 6px 0; font-weight: 800; }
      .sub { opacity: .9; margin: 0; }
      .ribbon {
        border: 1px solid rgba(0,0,0,.06);
        background: linear-gradient(90deg, rgba(34,197,94,.10), rgba(14,165,233,.10));
        padding: 10px 12px; border-radius: 12px; margin-top: 10px;
      }
      .pill {
        display:inline-block; padding: 3px 10px; border-radius: 999px;
        background: var(--pill-bg, #f5f5f5); border: 1px solid rgba(0,0,0,.08);
        font-weight:600; margin-right:6px; margin-top:6px; font-size: .92em;
      }
      .grid { display:grid; grid-template-columns: repeat(1, minmax(0,1fr)); gap: 10px; }
      @media (min-width: 900px) { .grid { grid-template-columns: repeat(4, minmax(0,1fr)); } }
      .tile {
        background: var(--card-bg, #fff); border-radius: 14px; padding: 16px;
        border: 1px solid rgba(0,0,0,.06); box-shadow: 0 2px 10px rgba(0,0,0,0.04);
        height: 100%;
      }
      .tile h3 { margin: 0 0 6px 0; font-size: 1.05rem; }
      .tile p { margin: 0; opacity: .9; }
      .callout {
        background: #f9fafb; border-left: 6px solid #22c55e; padding: 12px 14px;
        border-radius: 10px; margin: 12px 0;
      }
      .footnote { font-size: .9em; opacity: .8; margin-top: 8px; }
      .cta.is-static {
        display:inline-block; padding: 8px 12px; border-radius: 10px; font-weight:700;
        border: 1px solid #d4d4d8; color: inherit; background: #fafafa; margin-right:8px; margin-top:6px;
        pointer-events:none; cursor:default;
      }
      @media (prefers-color-scheme: dark) {
        .tile { background: #0b1220; border-color: rgba(255,255,255,.06); }
        .callout { background: #0b1220; border-left-color: #22c55e; }
        .pill { background: rgba(255,255,255,.06); border-color: rgba(255,255,255,.12); }
        .cta.is-static { background:#0b1220; border-color: rgba(255,255,255,.12); }
      }
    </style>
    """, unsafe_allow_html=True)

    if lang == "Arabic":
        # ====== Header ======
        st.markdown("""
<div class="page-head">
  <h2>👋 أهلاً بك في <strong>تنظيم إم إس</strong></h2>
  <p class="sub">هو <strong>تطبيق</strong> لمساعدة أشخاص التصلّب المتعدد على إدارة الحرارة بذكاء، عبر مقارنة قراءاتك بخطّك الأساسي ومواءمتها مع الطقس.</p>
  <div class="ribbon">🌍 مصمّم للخليج وبواجهتين <strong>العربية والإنجليزية</strong> — من أوائل التطبيقات التي تركّز على احتياجات المنطقة حيث التطبيقات الصحية قليلة التخصّص.</div>
  <div style="margin-top:6px;">
    <span class="pill">تخطيط ذكي</span>
    <span class="pill">متابعة سهلة</span>
    <span class="pill">🤖 رفيق شخصي</span>
    <span class="pill">🔒 خصوصية أولاً</span>
  </div>
</div>
""", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["📖 ما هو تنظيم إم إس؟", "🚀 كيف يساعدك؟"])

        # ====== Tab 1: What is Tanzim? ======
        with tab1:
            st.subheader("الفكرة باختصار")
            st.markdown("""
- مع التصلّب المتعدد، حتى **ارتفاع بسيط (≈ نصف درجة)** قد يسبّب **تعبًا أو ضبابية رؤية** — وهذا يُعرف بـ **ظاهرة أوتهوف**.
- تنظيم إم إس يقرأ حرارة الجسم (داخلية + الجلد) ويقارنها بـ **خطّك الأساسي** ليكشف الفروق الصغيرة التي قد لا تلاحظها.
- يدمج ذلك مع **الإحساس الحراري والرطوبة** ليعكس واقع الطقس في الخليج.
""")
            st.markdown('<div class="callout">🎯 الهدف: أن تلاحظ الفرق مبكرًا وتتخذ خطوة بسيطة قبل أن تتفاقم الأعراض.</div>', unsafe_allow_html=True)
            st.caption("المكوّنات: حساس لدرجة الحرارة الداخلية (الأساسية) + حساس لحرارة الجلد (الطرفية). التفاصيل التقنية تظهر في الصفحات المتقدمة.")

            st.subheader("ماذا ستجد في الصفحات القادمة")
            st.markdown('<div class="grid">', unsafe_allow_html=True)
            st.markdown('<div class="tile"><h3>📊 المراقبة</h3><p>عرض مباشر لحرارتك مقابل خطّك الأساسي، مع تبويب <strong>عرض تجريبي</strong> لفهم سلوك النظام تحت سيناريوهات مختلفة.</p></div>', unsafe_allow_html=True)
            st.markdown('<div class="tile"><h3>🧭 المخطِّط</h3><p>اقتراح <strong>نوافذ تبريد لساعتين</strong> خلال ٤٨ ساعة، بناءً على الطقس المحلي.</p></div>', unsafe_allow_html=True)
            st.markdown('<div class="tile"><h3>📝 الملاحظات</h3><p>توثيق الأعراض والأحداث بسرعة وتصديرها كملف <strong>CSV</strong> للمشاركة مع طبيبك.</p></div>', unsafe_allow_html=True)
            st.markdown('<div class="tile"><h3>🤖 الرفيق الشخصي</h3><p>يستخدم ملاحظاتك وأعراضك للإجابة المخصّصة (مثل التخطيط لرحلة أو نزهة بحسب تعبك الأخير).</p></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            
            st.markdown('<div class="footnote">🧪 لماذا العرض التجريبي؟ لأن الوصول إلى "ذروة" الارتفاع صعب بدون مجهود كبير؛ العرض يُحاكي حالات مختلفة (نشاط، جوّ حار، إضافة تبريد مثل مروحة) لتشاهد كيف يستجيب النظام.</div>', unsafe_allow_html=True)

        # ====== Tab 2: How it helps (action verbs) ======
        with tab2:
            st.subheader("أفعال واضحة — نتائج ملموسة")
            st.markdown("""
- **يُراقب حرارتك باستمرار** ويقارنها بخطّك الأساسي.
- **يُطابق الطقس الفعلي** في الخليج (إحساس حراري + رطوبة) ليجعل النصيحة واقعية.
- **يقترح خطوات عملية**: ترطيب، إبطاء، الانتقال لظل/مكيّف، تبريد بسيط.
- **يُخطّط لك بذكاء**: أفضل **نوافذ تبريد لساعتين** خلال الـ٤٨ ساعة القادمة.
- **يُسهّل المشاركة**: تصدير بياناتك كـ <strong>CSV</strong> لمراجعتها مع طبيبك.
- **يُشخصن تجربتك بالذكاء الاصطناعي**: رفيق يطّلع على ملاحظاتك/أعراضك ويجيب على أسئلة التخطيط (مثل السفر أو التخييم وفق حالتك).
- **يُريك السلوك من دون عناء** عبر **العرض التجريبي**: اختبر سيناريوهات وتدخّلات مثل إضافة مروحة أو تبريد موضعي لترى التأثير فورًا.
""")
            st.markdown('<div class="footnote">🔒 <strong>الخصوصية:</strong> بياناتك تبقى محمية، لا تُباع ولا تُشارك، وتُستخدم فقط لدعمك.</div>', unsafe_allow_html=True)

    else:
        # ====== Header ======
        st.markdown("""
<div class="page-head">
  <h2>👋 Welcome to <strong>Tanzim MS</strong></h2>
  <p class="sub">It's an <strong>app</strong> that helps people with Multiple Sclerosis manage heat intelligently by comparing your readings to your baseline and aligning them with real weather.</p>
  <div class="ribbon">🌍 Designed for the Gulf (GCC) and fully <strong>bilingual (Arabic & English)</strong> — one of the first apps focused on this region, where few health tools are localized.</div>
  <div style="margin-top:6px;">
    <span class="pill">Smart planning</span>
    <span class="pill">Easy tracking</span>
    <span class="pill">🤖 Personalized companion</span>
    <span class="pill">🔒 Privacy-first</span>
  </div>
</div>
""", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["📖 What is Tanzim?", "🚀 How it helps you"])

        # ====== Tab 1: What is Tanzim? ======
        with tab1:
            st.subheader("The idea in simple words")
            st.markdown("""
- With MS, even a **~0.5°C rise** can trigger symptoms like fatigue or blurry vision — this is known as **Uhthoff's phenomenon**.
- Tanzim reads core + skin temperatures and compares them to **your personal baseline** to surface subtle changes you might miss.
- It pairs that with **feels-like & humidity**, tuned for Gulf conditions.
""")
            st.markdown('<div class="callout">🎯 Goal: notice the change early and take a simple step before symptoms snowball.</div>', unsafe_allow_html=True)
            st.caption("We use two sensors: one for core (internal) temperature and one for skin (peripheral). Model names appear on advanced pages.")

            st.subheader("What to expect next")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                with st.container():
                    st.markdown("### 📊 Monitor")
                    st.markdown("Live readings vs. your baseline — plus a dedicated **Demo** tab to explore how the system behaves.")
            with col2:
                with st.container():
                    st.markdown("### 🧭 Planner")
                    st.markdown("**Coolest 2-hour windows** across the next 48 hours for your location.")
            with col3:
                with st.container():
                    st.markdown("### 📝 Journal")
                    st.markdown("Log symptoms/events quickly and export your data as a **CSV** to share with your clinician.")
            with col4:
                with st.container():
                    st.markdown("### 🤖 Companion")
                    st.markdown("Personalized answers that use your journal & symptoms (e.g., is a short trip or beach day wise given last week's fatigue?).")

            st.markdown('<div class="footnote">🧪 Why a Demo? Hitting a real "spike" can require heavy exertion. The demo simulates conditions (hot weather, activity) and interventions (e.g., a cooling fan) so you can see how Tanzim would respond—without stressing your body.</div>', unsafe_allow_html=True)

        # ====== Tab 2: How it helps (action verbs) ======
        with tab2:
            st.subheader("Actions that make a difference")
            st.markdown("""
- **Monitors your temperature** continuously vs. your baseline.
- **Matches real Gulf weather** (feels-like + humidity) so guidance fits your day.
- **Suggests practical steps**: hydrate, slow down, find shade/AC, light cooling.
- **Predicts 48-hour cooling windows**: best two-hour slots for planning.
- **Exports your data as CSV** so you can review it with your clinician.
- **Gives personalized AI guidance**: uses your journal & symptoms to help plan trips, outings, and daily routines.
- **Shows behavior safely via the Demo**: test scenarios and interventions (like adding a fan) and see the impact instantly.
""")
            st.markdown('<div class="footnote">🔒 <strong>Privacy:</strong> your data stays private, never sold or shared, and is only used to support you.</div>', unsafe_allow_html=True)

# ================== PLANNER HELPERS ==================
def best_windows_from_forecast(forecast, window_hours=2, top_k=8, max_feels_like=35.0, max_humidity=65, avoid_hours=(10,16)):
    slots = []
    for it in forecast[:16]:
        t = it["time"]
        hour = int(t[11:13])
        if avoid_hours[0] <= hour < avoid_hours[1]:
            continue
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

def tailored_tips(reasons, feels_like, humidity, delta, lang="English"):
    do_now, plan_later, watch_for = [], [], []
    if delta >= 0.5:
        do_now += ["Cool down (AC/cool shower)", "Sip cool water", "Rest 15–20 min"] if lang == "English" else ["تبرد (مكيف/دش بارد)", "اشرب ماءً باردًا", "ارتح 15-20 دقيقة"]
    if feels_like >= 36:
        do_now += ["Use cooling scarf/pack", "Stay in shade/indoors"] if lang == "English" else ["استخدم وشاح/حزمة تبريد", "ابق في الظل/داخل المباني"]
        plan_later += ["Shift activity to a cooler window"] if lang == "English" else ["انقل النشاط إلى نافذة أكثر برودة"]
    if humidity >= 60:
        plan_later += ["Prefer AC over fan", "Add electrolytes if sweating"] if lang == "English" else ["افضل التكييف على المروحة", "أضف إلكتروليتات إذا كنت تتعرق"]
    for r in reasons:
        rl = r.lower()
        if "exercise" in rl or "رياضة" in rl:
            do_now += ["Stop/pause activity", "Pre-cool next time 15 min"] if lang == "English" else ["أوقف/أجل النشاط", "تبرد مسبقًا المرة القادمة 15 دقيقة"]
            plan_later += ["Shorter intervals, more breaks"] if lang == "English" else ["فترات أقصر، فترات راحة أكثر"]
        if "sun" in rl or "شمس" in rl:
            do_now += ["Move to shade/indoors"] if lang == "English" else ["انتقل إلى الظل/داخل المباني"]
        if "sauna" in rl or "hot bath" in rl or "ساونا" in rl:
            do_now += ["Cool shower afterwards", "Avoid for now"] if lang == "English" else ["دش بارد بعد ذلك", "تجنب الآن"]
        if "car" in rl or "سيارة" in rl:
            do_now += ["Pre-cool car 5–10 min"] if lang == "English" else ["تبريد السيارة مسبقًا 5-10 دقائق"]
        if "kitchen" in rl or "cooking" in rl or "مطبخ" in rl:
            plan_later += ["Ventilate kitchen, cook earlier"] if lang == "English" else ["تهوية المطبخ، طهي مبكر"]
        if "fever" in rl or "illness" in rl or "حمّى" in rl:
            watch_for += ["Persistent high temp", "New neurological symptoms"] if lang == "English" else ["ارتفاع درجة الحرارة المستمر", "أعراض عصبية جديدة"]
    do_now = list(dict.fromkeys(do_now))[:6]
    plan_later = list(dict.fromkeys(plan_later))[:6]
    watch_for = list(dict.fromkeys(watch_for))[:6]
    return do_now, plan_later, watch_for

def get_recent_journal_context(username: str, max_items: int = 3) -> list[dict]:
    try:
        c = get_conn().cursor()
        c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC LIMIT ?", (username, max_items))
        rows = c.fetchall()
    except Exception:
        rows = []
    bullets = []
    for dt_raw, raw_json in rows:
        try:
            obj = json.loads(raw_json)
        except Exception:
            obj = {"type":"NOTE","text":str(raw_json)}
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

def build_personal_context(app_language: str) -> str:
    hc = st.session_state.get("last_check", {})
    hc_line = ""
    if hc:
        hc_line = (
            f"HeatCheck: body {hc.get('body_temp','?')}°C (baseline {hc.get('baseline','?')}°C), "
            f"feels-like {hc.get('feels_like','?')}°C, humidity {hc.get('humidity','?')}%, "
            f"status {hc.get('status','?')} in {hc.get('city','?')}."
        )
    bullets = []
    if "user" in st.session_state:
        bullets = get_recent_journal_context(st.session_state["user"], max_items=3)

    if app_language == "Arabic":
        header = "استخدم هذه الخلفية لتخصيص النصيحة (لا تكررها للمستخدم):"
        items = "\n".join([f"- {b}" for b in bullets]) if bullets else "- —"
        return f"{header}\n{hc_line}\nالسجل:\n{items}"
    else:
        header = "Use this background to personalize advice (do not repeat verbatim):"
        items = "\n".join([f"- {b}" for b in bullets]) if bullets else "- —"
        return f"{header}\n{hc_line}\nJournal:\n{items}"

TYPE_ICONS_EN = {"PLAN":"🗓️","ALERT":"🚨","ALERT_AUTO":"🚨","DAILY":"🧩","NOTE":"📝"}
TYPE_ICONS_AR = TYPE_ICONS_EN

def _to_dubai_label(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        try:
            dt = datetime.strptime(iso_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
    return dt.astimezone(TZ_DUBAI).strftime("%Y-%m-%d %H:%M")

def _as_list(v):
    if v is None: return []
    if isinstance(v, list): return [str(x) for x in v]
    if isinstance(v, str):
        s = v.strip()
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
            try:
                parsed = json.loads(s.replace("(", "[").replace(")", "]"))
                if isinstance(parsed, list): return [str(x) for x in parsed]
            except Exception:
                pass
        return [v]
    return [str(v)]

def pretty_plan(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    city = entry.get("city", "—")
    act = entry.get("activity", "—")
    start = entry.get("start", "—")
    end = entry.get("end", "—")
    fl = entry.get("feels_like", None)
    hum = entry.get("humidity", None)
    meta = f"Feels-like {round(fl,1)}°C • Humidity {int(hum)}%" if (fl is not None and hum is not None) else ""
    if lang == "Arabic":
        header = f"**{when}** — **خطة** ({city})"
        body = f"**النشاط:** {act}\n\n**الوقت:** {start} → {end}\n\n{meta}"
    else:
        header = f"**{when}** — **Plan** ({city})"
        body = f"**Activity:** {act}\n\n**Time:** {start} → {end}\n\n{meta}"
    return header, body

def pretty_alert(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    core = entry.get("core_temp") or entry.get("body_temp")
    periph = entry.get("peripheral_temp")
    base = entry.get("baseline")
    delta = (core - base) if (core is not None and base is not None) else None
    reasons = _as_list(entry.get("reasons"))
    symptoms = _as_list(entry.get("symptoms"))
    note = entry.get("note", "")
    if lang == "Arabic":
        header = f"**{when}** — **تنبيه حراري**"
        lines = []
        if core is not None: lines.append(f"**الأساسية:** {core}°م")
        if periph is not None: lines.append(f"**الطرفية:** {periph}°م")
        if base is not None: lines.append(f"**الأساس:** {base}°م")
        if delta is not None: lines.append(f"**الفرق عن الأساس:** +{round(delta,1)}°م")
        if reasons: lines.append(f"**الأسباب:** " + ", ".join(reasons))
        if symptoms: lines.append(f"**الأعراض:** " + ", ".join(symptoms))
        if note: lines.append(f"**ملاحظة:** {note}")
        body = "\n\n".join(lines)
    else:
        header = f"**{when}** — **Heat alert**"
        lines = []
        if core is not None: lines.append(f"**Core:** {core}°C")
        if periph is not None: lines.append(f"**Peripheral:** {periph}°C")
        if base is not None: lines.append(f"**Baseline:** {base}°C")
        if delta is not None: lines.append(f"**Δ from baseline:** +{round(delta,1)}°C")
        if reasons: lines.append(f"**Reasons:** " + ", ".join(reasons))
        if symptoms: lines.append(f"**Symptoms:** " + ", ".join(symptoms))
        if note: lines.append(f"**Note:** {note}")
        body = "\n\n".join(lines)
    return header, body

def pretty_daily(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    mood = entry.get("mood", "—")
    hyd = entry.get("hydration_glasses", "—")
    sleep = entry.get("sleep_hours", "—")
    fatigue = entry.get("fatigue", "—")
    triggers = _as_list(entry.get("triggers"))
    symptoms = _as_list(entry.get("symptoms"))
    note = entry.get("note", "")
    if lang == "Arabic":
        header = f"**{when}** — **مُسجّل يومي**"
        lines = [f"**المزاج:** {mood}", f"**الترطيب (أكواب):** {hyd}", f"**النوم (ساعات):** {sleep}", f"**التعب:** {fatigue}"]
        if triggers: lines.append(f"**المحفزات:** " + ", ".join(triggers))
        if symptoms: lines.append(f"**الأعراض:** " + ", ".join(symptoms))
        if note: lines.append(f"**ملاحظة:** {note}")
        body = "\n\n".join(lines)
    else:
        header = f"**{when}** — **Daily log**"
        lines = [f"**Mood:** {mood}", f"**Hydration (glasses):** {hyd}", f"**Sleep (hrs):** {sleep}", f"**Fatigue:** {fatigue}"]
        if triggers: lines.append(f"**Triggers:** " + ", ".join(triggers))
        if symptoms: lines.append(f"**Symptoms:** " + ", ".join(symptoms))
        if note: lines.append(f"**Note:** {note}")
        body = "\n\n".join(lines)
    return header, body

def pretty_note(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    text = entry.get("text") or entry.get("note") or "—"
    if lang == "Arabic":
        header = f"**{when}** — **ملاحظة**"
        body = text
    else:
        header = f"**{when}** — **Note**"
        body = text
    return header, body

def render_entry_card(raw_entry_json, lang="English"):
    try:
        obj = json.loads(raw_entry_json)
    except Exception:
        obj = {"type":"NOTE", "at": utc_iso_now(), "text": str(raw_entry_json)}
    t = obj.get("type", "NOTE")
    icon = (TYPE_ICONS_AR if lang=="Arabic" else TYPE_ICONS_EN).get(t, "📝")
    if t == "PLAN":
        header, body = pretty_plan(obj, lang)
    elif t in ("ALERT","ALERT_AUTO"):
        header, body = pretty_alert(obj, lang)
    elif t == "DAILY":
        header, body = pretty_daily(obj, lang)
    else:
        header, body = pretty_note(obj, lang)
    return header, body, icon, t, obj

def render_planner():
    st.title("🗺️ " + T["planner"])
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return
    
    city = st.selectbox(
        "📍 " + T["quick_pick"],
        GCC_CITIES,
        index=0,
        key="planner_city",
        format_func=lambda code: city_label(code, app_language),
    )
    weather, err = get_weather(city)
    if weather is None:
        st.error(f"{T['weather_fail']}: {err}"); return

    # tabs
    if app_language == "Arabic":
        tabs = st.tabs(["✅ " + T["best_windows"], "🤔 " + T["what_if"], "📍 " + T["places"]])
    else:
        tabs = st.tabs(["✅ " + T["best_windows"], "🤔 " + T["what_if"], "📍 " + T["places"]])

    # TAB 1
    with tabs[0]:
        if app_language == "Arabic":
            st.caption("فحصنا الـ48 ساعة القادمة للعثور على فترات أكثر برودة (ساعتين).")
        else:
            st.caption("We scanned the next 48h for cooler 2-hour windows.")

        windows = best_windows_from_forecast(
            weather["forecast"], window_hours=2, top_k=12, max_feels_like=35.0, max_humidity=65
        )
        if not windows:
            st.info("No optimal windows found; consider early morning or after sunset."
                    if app_language == "English" else "لم يتم العثور على فترات مثالية؛ فكر في الصباح الباكر أو بعد الغروب.")
        else:
                    # Localized headers
                    if app_language == "Arabic":
                        COL_DATE = "التاريخ"
                        COL_START = "البداية"
                        COL_END = "النهاية"
                        COL_FEELS = "الإحساس الحراري (°م)"
                        COL_HUM = "الرطوبة (%)"
                    else:
                        COL_DATE = "Date"
                        COL_START = "Start"
                        COL_END = "End"
                        COL_FEELS = "Feels-like (°C)"
                        COL_HUM = "Humidity (%)"
                    
                    windows_sorted = sorted(windows, key=lambda x: x["start_dt"])
                    rows = [{
                        "idx": i,
                        COL_DATE: w["start_dt"].strftime("%a %d %b"),
                        COL_START: w["start_dt"].strftime("%H:%M"),
                        COL_END: w["end_dt"].strftime("%H:%M"),
                        COL_FEELS: round(w["avg_feels"], 1),
                        COL_HUM: int(w["avg_hum"]),
                    } for i, w in enumerate(windows_sorted)]
                    
                    df = pd.DataFrame(rows)
                    st.dataframe(df.drop(columns=["idx"]), hide_index=True, use_container_width=True)
                    
                    st.markdown("##### " + ( "Add a plan" if app_language == "English" else "أضف خطة"))
                    
                    colA, colB = st.columns([2,1])
                    with colA:
                        # Localized option labels for the slot picker
                        def labeler(r):
                            if app_language == "Arabic":
                                # Example: "الجمعة 07 حز • 07:00–10:00 (≈35.5°م, 58%)"
                                return f"{r[COL_DATE]} • {r[COL_START]}–{r[COL_END]} (≈{r[COL_FEELS]}°م, {r[COL_HUM]}%)"
                            else:
                                return f"{r[COL_DATE]} • {r[COL_START]}–{r[COL_END]} (≈{r[COL_FEELS]}°C, {r[COL_HUM]}%)"
                    
                        options = [labeler(r) for r in rows]
                        pick_label = st.selectbox(T["choose_slot"], options, index=0, key="plan_pick")
                        pick_idx = rows[options.index(pick_label)]["idx"]
                        chosen = windows_sorted[pick_idx]

                    with colB:
                        if app_language == "English":
                            activities = ["Walk", "Groceries", "Beach", "Errand"]
                        else:
                            activities = ["مشي", "تسوق", "شاطئ", "مهمة"]
                        act = st.selectbox(T["plan"], activities, key="plan_act")
                        other_act = st.text_input(T["other_activity"], key="plan_act_other")
                        final_act = other_act.strip() if other_act.strip() else act
                        if st.button(T["add_to_journal"], key="btn_add_plan"):
                            entry = {
                                "type":"PLAN", "at": utc_iso_now(), "city": city,
                                "start": chosen["start_dt"].strftime("%Y-%m-%d %H:%M"),
                                "end": chosen["end_dt"].strftime("%Y-%m-%d %H:%M"),
                                "activity": final_act,
                                "feels_like": round(chosen["avg_feels"], 1),
                                "humidity": int(chosen["avg_hum"])
                            }
                            insert_journal(st.session_state["user"], utc_iso_now(), entry)
                            st.success("Saved to Journal" if app_language == "English" else "تم الحفظ في اليوميات")

    # TAB 2
    with tabs[1]:
        st.caption("Try a plan now and get instant tips." if app_language == "English" else "جرب خطة الآن واحصل على نصائح فورية.")
        col1, col2 = st.columns([2,1])
        with col1:
            if app_language == "English":
                activity_options = ["Light walk (20–30 min)", "Moderate exercise (45 min)", "Outdoor errand (30–60 min)", "Beach (60–90 min)"]
            else:
                activity_options = ["مشي خفيف (20-30 دقيقة)", "تمريين متوسط (45 دقيقة)", "مهمة خارجية (30-60 دقيقة)", "شاطئ (60-90 دقيقة)"]
            what_act = st.selectbox(T["activity"], activity_options, key="what_if_act")
            dur = st.slider(T["duration"], 10, 120, 45, 5, key="what_if_dur")
            if app_language == "English":
                location_options = ["Outdoor", "Indoor/AC"]
            else:
                location_options = ["خارجي", "داخلي/مكيف"]
            indoor = st.radio(T["location"], location_options, horizontal=True, key="what_if_loc")
            other_notes = st.text_area(T["what_if_tips"], height=80, key="what_if_notes")
        with col2:
            fl = weather["feels_like"]; hum = weather["humidity"]
            if app_language == "English":
                go_badge = "🟢 Go" if (fl < 34 and hum < 60) else ("🟡 Caution" if (fl < 37 and hum < 70) else "🔴 Avoid now")
            else:
                go_badge = "🟢 اذهب" if (fl < 34 and hum < 60) else ("🟡 احترس" if (fl < 37 and hum < 70) else "🔴 تجنب الآن")
            st.markdown(f"**{'Now' if app_language == 'English' else 'الآن'}:** {go_badge} — feels-like {round(fl,1)}°C, humidity {int(hum)}%")

            tips_now = []
            low = what_act.lower()
            if "walk" in low or "مشي" in low:
                tips_now += ["Shaded route" if app_language == "English" else "مسار مظلل",
                             "Carry cool water" if app_language == "English" else "احمل ماءً باردًا",
                             "Light clothing" if app_language == "English" else "ملابس خفيفة"]
            if "exercise" in low or "تمريين" in low:
                tips_now += ["Pre-cool 15 min" if app_language == "English" else "تبريد مسبق 15 دقيقة",
                             "Prefer indoor/AC" if app_language == "English" else "افضل الداخلي/مكيف",
                             "Electrolytes if >45 min" if app_language == "English" else "إلكتروليتات إذا كانت المدة >45 دقيقة"]
            if "errand" in low or "مهمة" in low:
                tips_now += ["Park in shade" if app_language == "English" else "اركن في الظل",
                             "Shortest route" if app_language == "English" else "أقصر طريق",
                             "Pre-cool car 5–10 min" if app_language == "English" else "تبريد السيارة مسبقًا 5-10 دقائق"]
            if "beach" in low or "شاطئ" in low:
                tips_now += ["Umbrella & UV hat" if app_language == "English" else "مظلة وقبعة للأشعة فوق البنفسجية",
                             "Cooling towel" if app_language == "English" else "منشفة تبريد",
                             "Rinse to cool" if app_language == "English" else "اشطف لتبريد"]
            if fl >= 36:
                tips_now += ["Cooling scarf/bandana" if app_language == "English" else "وشاح/باندانا للتبريد",
                             "Use a cooler window" if app_language == "English" else "استخدم نافذة أكثر برودة"]
            if hum >= 60:
                tips_now += ["Prefer AC over fan" if app_language == "English" else "افضل التكييف على المروحة",
                             "Extra hydration" if app_language == "English" else "ترطيب إضافي"]
            tips_now = list(dict.fromkeys(tips_now))[:8]
            st.markdown("**" + ("Tips" if app_language == "English" else "نصائح") + ":**")
            st.markdown("- " + "\n- ".join(tips_now) if tips_now else "—")

            if st.button(T["add_plan"], key="what_if_add_plan"):
                now_dxb = datetime.now(TZ_DUBAI)
                entry = {
                    "type":"PLAN","at": utc_iso_now(), "city": city,
                    "start": now_dxb.strftime("%Y-%m-%d %H:%M"),
                    "end": (now_dxb + timedelta(minutes=dur)).strftime("%Y-%m-%d %H:%M"),
                    "activity": what_act + (f" — {other_notes.strip()}" if other_notes.strip() else ""),
                    "feels_like": round(fl, 1), "humidity": int(hum),
                    "indoor": (indoor == ("Indoor/AC" if app_language == "English" else "داخلي/مكيف"))
                }
                insert_journal(st.session_state["user"], utc_iso_now(), entry)
                st.success(T["planned_saved"])

            if DEEPSEEK_API_KEY and st.button(T["ask_ai_tips"], key="what_if_ai"):
                q = f"My plan: {what_act} for {dur} minutes. Location: {indoor}. Notes: {other_notes}. Current feels-like {round(fl,1)}°C, humidity {int(hum)}%."
                ans, _ = ai_response(q, app_language)
                st.info(ans if ans else (T["ai_unavailable"]))

    # TAB 3
    with tabs[2]:
        st.caption("Check a specific place in your city, like a beach or a park."
                   if app_language == "English" else "تحقق من مكان محدد في مدينتك، مثل شاطئ أو حديقة.")
        place_q = st.text_input(T["place_name"], key="place_q")
        if place_q:
            place, lat, lon = geocode_place(place_q)
            pw = get_weather_by_coords(lat, lon) if (lat and lon) else None
            if pw:
                st.info(f"**{place}** — feels-like {round(pw['feels_like'],1)}°C • humidity {int(pw['humidity'])}% • {pw['desc']}")
                better = "place" if pw["feels_like"] < weather["feels_like"] else "city"
                st.caption(f"{'Cooler now' if app_language == 'English' else 'أبرد الآن'}: **{place if better=='place' else city}**")
                if st.button(T["plan_here"], key="place_plan"):
                    now_dxb = datetime.now(TZ_DUBAI)
                    entry = {
                        "type": "PLAN", "at": utc_iso_now(), "city": place,
                        "start": now_dxb.strftime("%Y-%m-%d %H:%M"),
                        "end": (now_dxb + timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M"),
                        "activity": "Visit" if app_language == "English" else "زيارة",
                        "feels_like": round(pw['feels_like'], 1), "humidity": int(pw['humidity'])
                    }
                    insert_journal(st.session_state["user"], utc_iso_now(), entry)
                    st.success(T["planned_saved"])
            else:
                st.warning("Couldn't fetch that place's weather." if app_language == "English" else "تعذر جلب طقس هذا المكان.")
        st.caption(f"**{T['peak_heat']}:** " + ("; ".join(weather.get('peak_hours', [])) if weather.get('peak_hours') else "—"))

# ================== SIDEBAR ==================
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/fba65899690870f1231741f068bf4d4b31e79363/logo1.PNG"
st.sidebar.image(logo_url, use_container_width=True)

# ---------- LANGUAGE (read previous -> pick new -> save new) ----------
# 1) Read previously stored language (may be None on first run)
prev_lang = st.session_state.get("_prev_lang", None)

# 2) Let the user pick the current language
app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English", "Arabic"], key="language_selector")

# 3) Use texts for the CURRENT language
T = TEXTS[app_language]

# 4) Save the CURRENT language for the NEXT rerun
st.session_state["_prev_lang"] = app_language

# ---------- RTL tweak (optional) ----------
if app_language == "Arabic":
    st.markdown("""
    <style>
      /* Make the main content RTL */
      body, .block-container { direction: rtl; text-align: right; }
      /* Do NOT flip the sidebar container here (the fix above handles it). */
    </style>
    """, unsafe_allow_html=True)

# ---------- NAVIGATION (LANG-SWITCH SAFE) ----------
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

# Single source of truth for current page
st.session_state.setdefault("current_page", "about")

# Seed radio state once (do NOT pass `index` ever again)
if "nav_radio" not in st.session_state:
    st.session_state["nav_radio"] = st.session_state["current_page"]

# If language changed this rerun, keep the same page selection
if prev_lang is not None and prev_lang != app_language:
    if st.session_state.get("current_page") in PAGE_IDS:
        st.session_state["nav_radio"] = st.session_state["current_page"]

page_id = st.sidebar.radio(
    "📑 " + ("التنقل" if app_language == "Arabic" else "Navigate"),
    options=PAGE_IDS,                          # stable IDs
    format_func=lambda pid: PAGE_LABELS[pid],  # localized labels
    key="nav_radio",
)

# Keep single source of truth synced
st.session_state["current_page"] = page_id

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
                    # LOAD EMERGENCY CONTACTS WHEN USER LOGS IN
                    primary, secondary = load_emergency_contacts(username)
                    st.session_state["primary_phone"] = primary
                    st.session_state["secondary_phone"] = secondary
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
            # CLEAR ALL USER DATA WHEN LOGGING OUT
            st.session_state.pop("user", None)
            st.session_state.pop("primary_phone", None)
            st.session_state.pop("secondary_phone", None)
            st.success(T["logged_out"])
            st.rerun()

# ================== ROUTING ==================
if page_id == "about":
    render_about_page(app_language)

elif page_id == "monitor":
    st.title("☀️ " + T["risk_dashboard"])
    if "user" not in st.session_state:
        st.warning(T["login_first"])
        st.stop()

    # =========================
    # SENSOR EXPLANATION SECTION
    # =========================
    with st.expander("🔬 " + ("About Our Temperature Sensors" if app_language == "English" else "عن مستشعرات درجة الحرارة"), expanded=True):
        if app_language == "English":
            st.markdown("""
            **We use medical-grade sensors connected to an ESP8266 microcontroller:**
            
            - **MAX30205**: Clinical-grade digital temperature sensor for **peripheral (skin) temperature** 
              (measures with ±0.1°C accuracy, ideal for wearable health monitoring)
            
            - **MLX90614**: Infrared sensor for **core body temperature**
              (non-contact measurement with ±0.5°C accuracy, estimates internal temperature)
                          (non-contact measurement of surface temperature with ±0.5°C accuracy)

            - **ESP8266 Microcontroller**: Reads both sensors and sends data to the cloud
            
            - **Feels-like temperature**: Provided by **OpenWeather API** - combines air temperature with humidity 
              to show how hot it actually feels on your body
            
            **What these temperatures mean:**
            - **Core Temperature**: Your internal body temperature - the most important indicator of heat stress
            - **Peripheral Temperature**: Your skin temperature - reacts quickly to environmental changes
            - **Feels-like**: Combined effect of air temperature + humidity from weather data
            - **Baseline**: Your personal normal temperature (set in Settings) used for alert thresholds
            """)
        else:
            st.markdown("""
            **نستخدم مستشعرات طبية لمراقبة درجة الحرارة بدقة:**
            
            - **MAX30205**: مستشعر رقمي بدرجة طبية لـ **درجة حرارة الجلد (الطرفية)**
              (يقيس بدقة ±0.1°C، مثالي لمراقبة الصحة القابلة للارتداء)
            
            - **MLX90614**: مستشعر بالأشعة تحت الحمراء لـ **درجة حرارة الجسم الأساسية**
              (قياس بدون تلامس بدقة ±0.5°C، يقدر درجة الحرارة الداخلية)

            - **متحكم ESP8266 الدقيق**: يقرأ كلا المستشعرين ويرسل البيانات إلى السحابة
            
            - **درجة الحرارة المحسوسة**: مقدمة من **OpenWeather API** - تجمع بين درجة حرارة الهواء والرطوبة
              لتظهر مدى الشعور الحقيقي بالحرارة على جسمك
            
            **ماذا تعني هذه الدرجات:**
            - **درجة الحرارة الأساسية**: درجة حرارة جسمك الداخلية - المؤشر الأهم للإجهاد الحراري
            - **درجة الحرارة الطرفية**: درجة حرارة جلدك - تتفاعل بسرعة مع التغيرات البيئية
            - **درجة الحرارة المحسوسة**: التأثير المشترك لدرجة حرارة الهواء والرطوبة من بيانات الطقس
            - **خط الأساس**: درجة حرارتك الطبيعية الشخصية (تم ضبطها في الإعدادات) تُستخدم لعتبات التنبيه
            """)

    # Sub-tabs
    if app_language == "English":
        tabs = st.tabs(["📡 Live Sensor Data", "🧪 Learn & Practice"])
    else:
        tabs = st.tabs(["📡 بيانات المستشعرات المباشرة", "🧪 تعلم وتدرب"])

    # =========================
    # TAB 1 — LIVE SENSOR DATA
    # =========================
    with tabs[0]:
        if app_language == "English":
            st.info("🔌 **Connected to real sensors** - Displaying live data from your MAX30205 and MLX90614 sensors")
        else:
            st.info("🔌 **متصل بمستشعرات حقيقية** - عرض البيانات المباشرة من مستشعرات MAX30205 و MLX90614")
        
        colA, colB, colC, colD = st.columns([1.2, 1.1, 1, 1.3])
        with colA:
            city = st.selectbox(
                "📍 " + T["quick_pick"],
                GCC_CITIES,
                index=0,
                key="monitor_city",
                format_func=lambda code: city_label(code, app_language),
            )
            
        with colB:
            if app_language == "English":
                st.markdown("**🔌 Sensor Hub**")
                st.info("ESP8266 with MAX30205 + MLX90614")
                st.caption("Pre-configured sensor device - contact admin for changes")
            else:
                st.markdown("**🔌 محور المستشعرات**")
                st.info("ESP8266 مع MAX30205 + MLX90614")
                st.caption("جهاز مستشعر مُهيأ مسبقًا - اتصل بالمسؤول للتغييرات")
        
        with colC:
            connect_label = "🔄 الاتصال بالمستشعرات" if app_language == "Arabic" else "🔄 Connect to Sensors"
            if st.button(connect_label, use_container_width=True, type="primary"):
                # Test connection to Supabase
                sample = fetch_latest_sensor_sample(device_id or "esp8266-01")
                if sample:
                    if app_language == "English":
                        st.success(f"✅ Connected! Last reading: {sample['core']}°C core, {sample['peripheral']}°C peripheral")
                    else:
                        st.success(f"✅ متصل! آخر قراءة: {sample['core']}°C أساسية, {sample['peripheral']}°C طرفية")
                    # Initialize with real data
                    st.session_state["live_core_smoothed"] = [sample['core']]
                    st.session_state["live_periph_smoothed"] = [sample['peripheral']]
                    st.session_state["live_running"] = True
                else:
                    if app_language == "English":
                        st.error("❌ No sensor data found. Check device ID or sensor connection.")
                    else:
                        st.error("❌ لم يتم العثور على بيانات المستشعر. تحقق من معرف الجهاز أو اتصال المستشعر.")
        with colD:
            baseline_text = "الأساس" if app_language == "Arabic" else "Baseline"
            st.markdown(
                f"<div class='badge'>{baseline_text}: <strong>{st.session_state.get('baseline', 37.0):.1f}°C</strong></div>", 
                unsafe_allow_html=True
            )

        # Weather data
        weather, w_err, fetched_ts = get_weather_cached(city)
        if weather is None:
            st.error(f"{T['weather_fail']}: {w_err or '—'}")
        else:
            fetched_label = datetime.fromtimestamp(fetched_ts, TZ_DUBAI).strftime("%H:%M") if fetched_ts else "—"
            if app_language == "English":
                weather_text = "Weather last updated"
                st.caption(f"{weather_text}: {fetched_label}")
            else:
                weather_text = "آخر تحديث للطقس"
                st.caption(f"{weather_text}: {fetched_label}")

        # Real-time data display
        if app_language == "English":
            st.subheader("📊 Live Sensor Readings")
        else:
            st.subheader("📊 قراءات المستشعرات المباشرة")
        
        # Get latest sensor data
        sample = fetch_latest_sensor_sample("esp8266-01")
        if sample:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                delta = sample['core'] - st.session_state.get('baseline', 37.0)
                core_label = "درجة الحرارة الأساسية" if app_language == "Arabic" else "Core Temperature"
                st.metric(
                    core_label, 
                    f"{sample['core']:.1f}°C", 
                    f"{delta:+.1f}°C",
                    delta_color="inverse" if delta >= 0.5 else "normal"
                )
                
            with col2:
                peri_label = "درجة الحرارة الطرفية" if app_language == "Arabic" else "Peripheral Temperature"
                st.metric(peri_label, f"{sample['peripheral']:.1f}°C")
                
            with col3:
                feels_label = "درجة الحرارة المحسوسة" if app_language == "Arabic" else "Feels-like"
                st.metric(feels_label, f"{weather['feels_like']:.1f}°C" if weather else "—")
                
            with col4:
                humidity_label = "الرطوبة" if app_language == "Arabic" else "Humidity"
                st.metric(humidity_label, f"{weather['humidity']}%" if weather else "—")
            
            # Risk assessment
            risk = compute_risk(
                weather["feels_like"] if weather else 30, 
                weather["humidity"] if weather else 50,
                sample['core'], 
                st.session_state.get('baseline', 37.0), 
                [], []
            )
            
            # Status display
            status_text = "الحالة" if app_language == "Arabic" else "Status"
            st.markdown(f"""
            <div class="big-card" style="--left:{risk['color']}">
              <h3>{risk['icon']} <strong>{status_text}: {risk['status']}</strong></h3>
              <p style="margin:6px 0 0 0">{risk['advice']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Alert for significant temperature rise
            if sample['core'] - st.session_state.get('baseline', 37.0) >= 0.5:
                if app_language == "English":
                    st.warning("""
                    ⚠️ **Temperature Alert**: Your core temperature has risen 0.5°C above baseline. 
                    Consider cooling measures and monitor for symptoms.
                    """)
                else:
                    st.warning("""
                    ⚠️ **تنبيه درجة الحرارة**: ارتفعت درجة حرارتك الأساسية 0.5°C فوق خط الأساس. 
                    فكر في إجراءات التبريد وراقب الأعراض.
                    """)
                
        else:
            if app_language == "English":
                st.info("""
                🔌 **No sensor data available**
                - Make sure your sensors are connected and powered on
                - Check your Device ID matches your sensor setup
                - Sensors should be sending data to Supabase
                """)
            else:
                st.info("""
                🔌 **لا توجد بيانات مستشعر متاحة**
                - تأكد من أن المستشعرات متصلة ومشغلة
                - تحقق من تطابق معرف الجهاز مع إعدادات المستشعر
                - يجب أن ترسل المستشعرات البيانات إلى Supabase
                """)

        # =========================
        # HEALTH EVENT LOGGING SECTION
        # =========================
        st.markdown("---")
        if app_language == "English":
            st.subheader("📝 Log Health Event")
        else:
            st.subheader("📝 تسجيل حدث صحي")
        
        with st.form("health_event_form", clear_on_submit=True):
            # Current sensor data context
            if sample:
                current_temp = sample['core']
                delta = current_temp - st.session_state.get('baseline', 37.0)
                if app_language == "English":
                    st.info(f"**Current Reading:** Core: {current_temp:.1f}°C | Δ: {delta:+.1f}°C | Peripheral: {sample['peripheral']:.1f}°C")
                else:
                    st.info(f"**القراءة الحالية:** الأساسية: {current_temp:.1f}°C | الفرق: {delta:+.1f}°C | الطرفية: {sample['peripheral']:.1f}°C")
            
            if app_language == "English":
                st.markdown("#### Triggers & Symptoms")
            else:
                st.markdown("#### المحفزات والأعراض")
            
            col1, col2 = st.columns(2)
            
            with col1:
                trigger_options = TRIGGERS_EN if app_language == "English" else TRIGGERS_AR
                chosen_triggers = st.multiselect(
                    T["triggers_today"],
                    trigger_options,
                    help="What might have triggered symptoms?" if app_language == "English" else "ما الذي قد يكون سبب الأعراض؟"
                )
                other_trigger = st.text_input(f"{T['other']} ({T['trigger']})")
                
            with col2:
                symptom_options = SYMPTOMS_EN if app_language == "English" else SYMPTOMS_AR
                chosen_symptoms = st.multiselect(
                    T["symptoms_today"],
                    symptom_options,
                    help="Symptoms you're experiencing" if app_language == "English" else "الأعراض التي تعاني منها"
                )
                other_symptom = st.text_input(f"{T['other']} ({T['symptom']})")
            
            if app_language == "English":
                event_placeholder = "Describe what happened, how you're feeling, or any other details..."
            else:
                event_placeholder = "صف ما حدث، كيف تشعر، أو أي تفاصيل أخرى..."
                
            event_description = st.text_area(
                T["notes"] if app_language == "English" else "ملاحظات",
                placeholder=event_placeholder,
                height=80
            )
            
            # Combine all data
            all_triggers = chosen_triggers + ([f"Other: {other_trigger.strip()}"] if other_trigger.strip() else [])
            all_symptoms = chosen_symptoms + ([f"Other: {other_symptom.strip()}"] if other_symptom.strip() else [])
            
            if app_language == "English":
                submit_label = "💾 Save to Journal"
            else:
                submit_label = "💾 حفظ في اليوميات"
                
            submitted = st.form_submit_button(submit_label)
            if submitted:
                if sample:
                    entry = {
                        "type": "ALERT",
                        "at": utc_iso_now(),
                        "core_temp": round(sample['core'], 1),
                        "peripheral_temp": round(sample['peripheral'], 1),
                        "baseline": round(st.session_state.get('baseline', 37.0), 1),
                        "reasons": all_triggers,
                        "symptoms": all_symptoms,
                        "note": event_description.strip(),
                        "city": city,
                        "feels_like": weather["feels_like"] if weather else None,
                        "humidity": weather["humidity"] if weather else None
                    }
                    
                    try:
                        insert_journal(st.session_state.get("user", "guest"), utc_iso_now(), entry)
                        if app_language == "English":
                            st.success("✅ Event saved to journal!")
                        else:
                            st.success("✅ تم حفظ الحدث في اليوميات!")
                    except Exception as e:
                        st.warning(f"Could not save event: {e}")
                else:
                    if app_language == "English":
                        st.error("No sensor data available to log")
                    else:
                        st.error("لا توجد بيانات مستشعر متاحة للتسجيل")

        # =========================
        # TEMPERATURE TREND PLOT
        # =========================
        if sample:  # Only show plot if we have sensor data
            st.markdown("---")
            if app_language == "English":
                st.subheader("📈 Temperature Trend")
            else:
                st.subheader("📈 اتجاه درجة الحرارة")
            
            # Fetch historical data for plotting
            c = get_conn().cursor()
            try:
                query = """
                    SELECT date, body_temp, peripheral_temp, weather_temp, feels_like, status
                    FROM temps WHERE username=? ORDER BY date DESC LIMIT 50
                """
                c.execute(query, (st.session_state.get("user","guest"),))
                rows = c.fetchall()
                if rows:
                    rows = rows[::-1]  # Reverse to show chronological order
                    dates = [r[0] for r in rows]
                    core = [r[1] for r in rows]
                    periph = [r[2] for r in rows]
                    feels = [(r[4] if r[4] is not None else r[3]) for r in rows]

                    fig, ax = plt.subplots(figsize=(10, 4))
                    if app_language == "Arabic":
                        lbl_core  = ar_shape("الأساسية")
                        lbl_peri  = ar_shape("الطرفية")
                        lbl_feels = ar_shape("الإحساس الحراري")
                    else:
                        lbl_core, lbl_peri, lbl_feels = "Core", "Peripheral", "Feels-like"
                    ax.plot(range(len(dates)), core,   marker='o', label=lbl_core,  linewidth=2)
                    ax.plot(range(len(dates)), periph, marker='o', label=lbl_peri,  linewidth=1.8)
                    ax.plot(range(len(dates)), feels,  marker='s', label=lbl_feels, linewidth=1.8)
                    ax.set_xticks(range(len(dates)))
                    ax.set_xticklabels([d[11:16] if len(d) >= 16 else d for d in dates], rotation=45, fontsize=9)
                    ax.set_ylabel("°C" if app_language == "English" else "°م", fontproperties=_AR_FONT)
                    ax.legend(prop=_AR_FONT)
                    ax.grid(True, alpha=0.3)
                    if app_language == "Arabic":
                        title_ar = ar_shape("الأساسية مقابل الطرفية مقابل الإحساس الحراري")
                        ax.set_title(title_ar, fontproperties=_AR_FONT, loc="center")
                    else:
                        ax.set_title("Core vs Peripheral vs Feels-like")
                    st.pyplot(fig)
            except Exception as e:
                st.error(f"Chart error: {e}")

    # =========================
    # TAB 2 — LEARN & PRACTICE (DEMO)
    # =========================
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
                st.subheader("🎯 Try Different Scenarios")
                scenario_label = "Choose a scenario"
                apply_label = "Apply Scenario"
            else:
                st.subheader("🎯 جرب سيناريوهات مختلفة")
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
                
elif page_id == "planner":
    render_planner()

elif page_id == "journal":
    st.title("📒 " + T["journal"])
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        
        st.caption(T["journal_hint"])

        st.markdown("### " + T["daily_logger"])
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            mood_options = ["🙂 Okay", "😌 Calm", "😕 Low", "😣 Stressed", "😴 Tired"] if app_language == "English" else ["🙂 بخير", "😌 هادئ", "😕 منخفض", "😣 متوتر", "😴 متعب"]
            mood = st.selectbox(T["mood"], mood_options)
        with col2:
            hydration = st.slider(T["hydration"], 0, 12, 6, key="hydration_slider")
        with col3:
            sleep = st.slider(T["sleep"], 0, 12, 7, key="sleep_slider")
        with col4:
            fatigue_options = [f"{i}/10" for i in range(0, 11)]
            fatigue = st.selectbox(T["fatigue"], fatigue_options, index=4)

        trigger_options = TRIGGERS_EN if app_language == "English" else TRIGGERS_AR
        symptom_options = SYMPTOMS_EN if app_language == "English" else SYMPTOMS_AR
        trigger_label = "Triggers (optional)" if app_language == "English" else "المحفزات (اختياري)"
        symptom_label = "Symptoms (optional)" if app_language == "English" else "الأعراض (اختياري)"
        chosen_tr = st.multiselect(trigger_label, trigger_options)
        tr_other = st.text_input(f"{T['other']} ({T['trigger']})", "")
        chosen_sy = st.multiselect(symptom_label, symptom_options)
        sy_other = st.text_input(f"{T['other']} ({T['symptom']})", "")
        free_note = st.text_area(T["free_note"], height=100)

        if st.button(T["save_entry"], key="journal_save"):
            entry = {
                "type": "DAILY", "at": utc_iso_now(),
                "mood": mood, "hydration_glasses": hydration, "sleep_hours": sleep, "fatigue": fatigue,
                "triggers": chosen_tr + ([f"Other: {tr_other.strip()}"] if tr_other.strip() else []),
                "symptoms": chosen_sy + ([f"Other: {sy_other.strip()}"] if sy_other.strip() else []),
                "note": free_note.strip()
            }
            insert_journal(st.session_state["user"], utc_iso_now(), entry)
            st.success("✅ " + ("Saved" if app_language == "English" else "تم الحفظ"))

        st.markdown("---")

        c = get_conn().cursor()
        c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC", (st.session_state["user"],))
        rows = c.fetchall()
        if not rows:
            st.info("No journal entries yet." if app_language == "English" else "لا توجد مدخلات في اليوميات بعد.")
        else:
            available_types = ["PLAN","ALERT","ALERT_AUTO","DAILY","NOTE"]
            type_filter = st.multiselect(
                T["filter_by_type"],
                options=available_types,
                default=["PLAN","ALERT","ALERT_AUTO","DAILY","NOTE"],
                help="Show only selected entry types" if app_language == "English" else "إظهار أنواع المدخلات المحددة فقط"
            )

            st.session_state.setdefault("journal_offset", 0)
            page_size = 12
            start = st.session_state["journal_offset"]
            end = start + 200
            chunk = rows[start:end]

            parsed = []
            for r in chunk:
                dt_raw, raw_json = r
                title, body, icon, t, obj = render_entry_card(raw_json, app_language)
                if t not in type_filter: continue
                try:
                    dt = datetime.fromisoformat(dt_raw.replace("Z","+00:00"))
                except Exception:
                    dt = datetime.now(timezone.utc)
                day_key = dt.astimezone(TZ_DUBAI).strftime("%A, %d %B %Y")
                parsed.append((day_key, title, body, icon, obj, raw_json))

            current_day = None
            shown = 0
            for day, title, body, icon, obj, raw_json in parsed:
                if shown >= page_size: break
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
                        st.session_state["journal_offset"] = max(0, st.session_state["journal_offset"] - page_size)
                        st.rerun()
            with colp2:
                if (start + shown) < len(rows):
                    if st.button(T["older"]):
                        st.session_state["journal_offset"] += page_size
                        st.rerun()

# Replace just the AI Companion section (page_id == "assistant") with this improved version:

elif page_id == "assistant":
    st.title("🤝 " + T["assistant_title"])

    if "user" not in st.session_state:
        st.warning(T["login_first"])
        st.stop()

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display chat messages from history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input(T["ask_me_anything"]):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": prompt})

        # Display assistant response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("💭 " + T["thinking"])
            
            # Get context (this part still works)
            journal_context = ""
            weather_context = ""
            
            prompt_lower = prompt.lower()
            
            # Get journal context if needed
            if any(keyword in prompt_lower for keyword in ['journal', 'entry', 'log', 'اليوميات', 'المذكرات', 'السجل']):
                journal_context = get_recent_journal_context(st.session_state["user"])
            
            # Get weather context if needed  
            if any(keyword in prompt_lower for keyword in ['weather', 'temperature', 'hot', 'heat', 'طقس', 'حرارة', 'حر']):
                # City detection logic here (same as before)
                city_mapping = {
                    "kuwait": "Kuwait City,KW", "الكويت": "Kuwait City,KW",
                    "dubai": "Dubai,AE", "دبي": "Dubai,AE", 
                    "oman": "Muscat,OM", "عمان": "Muscat,OM",
                    # ... other cities
                }
                city_found = None
                for city_key, city_api in city_mapping.items():
                    if city_key in prompt_lower:
                        city_found = city_api
                        break
                weather_context = get_weather_context(city_found if city_found else "Dubai,AE")
            
            # Try to get AI response
            full_response, error = ai_response(prompt, app_language, journal_context, weather_context)
            
            # If API fails, use fallback
            if error:
                st.warning(f"⚠️ Connection issue: {error}. Using fallback response.")
                full_response = get_fallback_response(prompt, app_language, journal_context, weather_context)
            
            # Display the response
            message_placeholder.markdown(full_response)

        # Add assistant response to chat history
        st.session_state.chat_history.append({"role": "assistant", "content": full_response})

    # Connection status indicator
    if st.session_state.chat_history:
        st.caption("🔁 Connection: Auto-fallback enabled | DeepSeek API may be experiencing issues")
        
    # Reset chat button
    st.markdown("---")
    col1, col2 = st.columns([1, 5])
      
    with col1:
        if st.button(T["reset_chat"], key="reset_chat_btn"):
            st.session_state.chat_history = []
            st.rerun()
    
    with col2:
        disclaimer = "This chat provides general wellness information only. Always consult your healthcare provider for medical advice." if app_language == "English" else "هذه المحادثة تقدم معلومات عامة عن الصحة فقط. استشر مقدم الرعاية الصحية الخاص بك دائمًا للحصول على المشورة الطبية."
        st.caption(disclaimer)

# =====================================
elif page_id == "exports":
    st.title("📦 " + T["export_title"])
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        
        st.caption(T["export_desc"])
        df_t = fetch_temps_df(st.session_state["user"])
        df_j = fetch_journal_df(st.session_state["user"])
        st.subheader("Preview — Temps" if app_language == "English" else "معاينة — درجات الحرارة")
        st.dataframe(df_t.tail(20), use_container_width=True)
        st.subheader("Preview — Journal" if app_language == "English" else "معاينة — اليوميات")
        st.dataframe(df_j.tail(20), use_container_width=True)
        blob, mime = build_export_excel_or_zip(st.session_state["user"])
        st.download_button(
            label=T["export_excel"],
            data=blob,
            file_name=f"raha_ms_{st.session_state['user']}.xlsx" if mime.endswith("sheet") else f"raha_ms_{st.session_state['user']}.zip",
            mime=mime, use_container_width=True
        )
        st.markdown("— or download raw CSVs —" if app_language == "English" else "— أو حمل ملفات CSV خام —")
        temp_label = "درجات الحرارة.csv" if app_language == "Arabic" else "Temps.csv"
        st.download_button(temp_label, data=df_t.to_csv(index=False).encode("utf-8"), file_name="Temps.csv", mime="text/csv", use_container_width=True)
        journal_label = "اليوميات.csv" if app_language == "Arabic" else "Journal.csv"
        st.download_button(journal_label, data=df_j.to_csv(index=False).encode("utf-8"), file_name="Journal.csv", mime="text/csv", use_container_width=True)

elif page_id == "settings":
    st.title("⚙️ " + T["settings"])
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        # Load contacts if they're not in session state (page refresh scenario)
        if "primary_phone" not in st.session_state or "secondary_phone" not in st.session_state:
            primary, secondary = load_emergency_contacts(st.session_state["user"])
            st.session_state["primary_phone"] = primary
            st.session_state["secondary_phone"] = secondary
        
        st.subheader(T["baseline_setting"])
        st.session_state.setdefault("baseline", 37.0)
        st.session_state.setdefault("use_temp_baseline", True)
        base = st.number_input(T["baseline_setting"], 35.5, 38.5, float(st.session_state["baseline"]), step=0.1, key="settings_baseline")
        useb = st.checkbox(T["use_temp_baseline"], value=st.session_state["use_temp_baseline"], key="settings_useb")

        st.caption(T["baseline_caption"])

        st.subheader(T["contacts"])
        p1 = st.text_input(T["primary_phone"], st.session_state["primary_phone"], key="settings_p1")
        p2 = st.text_input(T["secondary_phone"], st.session_state["secondary_phone"], key="settings_p2")

        if st.button(T["save_settings"], key="settings_save_btn"):
            st.session_state["baseline"] = float(base)
            st.session_state["use_temp_baseline"] = bool(useb)
        
            p1 = st.session_state["primary_phone"] = (p1 or "").strip()
            p2 = st.session_state["secondary_phone"] = (p2 or "").strip()
        
            ok, err = save_emergency_contacts(st.session_state["user"], p1, p2)
            if ok:
                st.success("✅ " + T["saved"])
                
                #st.rerun()
            else:
                st.error(f"Failed to save contacts to database: {err}")
                
        

        st.markdown("---")
        if st.button(T["logout"], type="secondary", key="settings_logout"):
            # Clear all user data when logging out
            st.session_state.pop("user", None)
            st.session_state.pop("primary_phone", None)
            st.session_state.pop("secondary_phone", None)
            st.success(T["logged_out"])
            st.rerun()

# Emergency in sidebar (click-to-call)
with st.sidebar.expander("📞 " + T["emergency"], expanded=False):
    if "user" in st.session_state:
        if "primary_phone" not in st.session_state or "secondary_phone" not in st.session_state:
            primary, secondary = load_emergency_contacts(st.session_state["user"])
            st.session_state["primary_phone"], st.session_state["secondary_phone"] = primary, secondary

        if st.session_state["primary_phone"]:
            href = tel_href(st.session_state["primary_phone"])
            st.markdown(f"**{'Primary' if app_language == 'English' else 'الهاتف الأساسي'}:** [{st.session_state['primary_phone']}](tel:{href})")
        if st.session_state["secondary_phone"]:
            href = tel_href(st.session_state["secondary_phone"])
            st.markdown(f"**{'Secondary' if app_language == 'English' else 'هاتف إضافي'}:** [{st.session_state['secondary_phone']}](tel:{href})")

        if not (st.session_state["primary_phone"] or st.session_state["secondary_phone"]):
            st.caption("Set numbers in Settings to enable quick call." if app_language == "English" else "اضبط الأرقام في الإعدادات لتمكين الاتصال السريع.")
    else:
        st.caption("Please log in to see emergency contacts" if app_language == "English" else "يرجى تسجيل الدخول لعرض جهات الاتصال للطوارئ")
