import streamlit as st
import sqlite3, json, time, random, io, csv
from openai import OpenAI
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict

# ================== CONFIG ==================
st.set_page_config(page_title="Raha MS", page_icon="🌡️", layout="wide")

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Timezone handling
TZ = ZoneInfo("Asia/Dubai")

# Live/alert tuning
SIM_INTERVAL_SEC = 5
DB_WRITE_EVERY_N = 3
ALERT_DELTA_C = 0.5
ALERT_CONFIRM = 2
ALERT_COOLDOWN_SEC = 300
SMOOTH_WINDOW = 3

# GCC quick picks
GCC_CITIES = [
    "Abu Dhabi,AE","Dubai,AE","Sharjah,AE",
    "Doha,QA","Al Rayyan,QA",
    "Kuwait City,KW",
    "Manama,BH",
    "Riyadh,SA","Jeddah,SA","Dammam,SA",
    "Muscat,OM"
]

# ================== I18N ==================
TEXTS = {
    "English": {
        "about_title": "About Raha MS",
        "monitor": "Heat Monitor",
        "planner": "Planner & Forecast",
        "journal_tab": "Journal & History",
        "assistant_tab": "AI Companion",
        "settings": "Settings & Export",
        "login_title": "Login / Register",
        "username": "Username",
        "password": "Password",
        "login": "Login",
        "register": "Register",
        "logged_in": "✅ Logged in!",
        "bad_creds": "❌ Invalid credentials",
        "account_created": "✅ Account created! Please login.",
        "user_exists": "❌ Username already exists",
        "logged_out": "✅ Logged out!",
        "login_first": "Please login first.",
        "weather_fail": "Weather lookup failed",
        "ai_unavailable": "AI is unavailable. Add OPENAI_API_KEY in secrets.",
        "risk_dashboard": "Heat Safety Monitor",
        "personal_baseline": "My baseline (°C)",
        "quick_pick": "Quick pick (GCC)",
        "update_every": "Update every (sec)",
        "start": "▶️ Start",
        "stop": "⏸️ Stop",
        "reset": "🔁 Reset session",
        "status_checked": "Checked",
        "log_now": "Log reason now",
        "triggers_today": "Triggers",
        "symptoms_today": "Symptoms",
        "other": "Other (specify)",
        "notes": "Notes",
        "save_entry": "Save entry",
        "saved": "Saved ✅",
        "weekly_forecast": "Weekly Forecast",
        "peak_heat": "Peak heat next 48h",
        "ask_anything": "Type your message…",
        "baseline_hint": "Baseline is used to detect a rise ≥ 0.5 °C (Uhthoff-aware).",
        "emergency_title": "Emergency Contact",
        "primary_name": "Primary name",
        "primary_phone": "Primary phone",
        "secondary_name": "Secondary name (optional)",
        "secondary_phone": "Secondary phone (optional)",
        "save_contacts": "Save contacts",
        "contacts_saved": "Contacts saved ✅",
        "export_csv": "Export my temps to CSV",
        "download_csv": "Download temps.csv",
        "instant_plan_title": "Instant Cooling Plan",
        "do_now": "Do now",
        "plan_later": "Plan later today",
        "watch_for": "Watch for",
        "temp_trend": "📈 Temperature History",
        "recent_entries": "Recent entries",
        "quick_tips": "Quick tips (today)",
        "mood": "Mood",
        "energy": "Energy",
        "sleep": "Sleep quality",
        "hydration": "Hydration",
        "activity": "Activity",
        "logout": "Logout",
        "quick_menu": "☰ Quick Menu",
        "auto_save_alerts": "Auto-save alerts to Journal",
        "other_activity": "Other activity",
        "add_to_journal": "Add to Journal",
        "what_if_tips": "Other considerations / notes",
        "ask_ai_tips": "Ask AI for tailored tips"
    },
    "Arabic": {
        "about_title": "عن تطبيق راحة إم إس",
        "monitor": "مراقبة الحرارة",
        "planner": "التخطيط والتوقعات",
        "journal_tab": "اليوميات والسجل",
        "assistant_tab": "المساعد الذكي",
        "settings": "الإعدادات والتصدير",
        "login_title": "تسجيل الدخول / إنشاء حساب",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "login": "تسجيل الدخول",
        "register": "إنشاء حساب",
        "logged_in": "✅ تم تسجيل الدخول",
        "bad_creds": "❌ بيانات غير صحيحة",
        "account_created": "✅ تم إنشاء الحساب! الرجاء تسجيل الدخول.",
        "user_exists": "❌ اسم المستخدم موجود",
        "logged_out": "✅ تم تسجيل الخروج!",
        "login_first": "يرجى تسجيل الدخول أولاً.",
        "weather_fail": "فشل جلب الطقس",
        "ai_unavailable": "الخدمة الذكية غير متاحة. أضف مفتاح OPENAI_API_KEY.",
        "risk_dashboard": "مراقبة السلامة الحرارية",
        "personal_baseline": "حرارتي الأساسية (°م)",
        "quick_pick": "اختيار سريع (الخليج)",
        "update_every": "تحديث كل (ثانية)",
        "start": "▶️ بدء",
        "stop": "⏸️ إيقاف",
        "reset": "🔁 إعادة الضبط",
        "status_checked": "تم التحقق",
        "log_now": "سجّل السبب الآن",
        "triggers_today": "المحفزات",
        "symptoms_today": "الأعراض",
        "other": "أخرى (اذكر السبب)",
        "notes": "ملاحظات",
        "save_entry": "حفظ الإدخال",
        "saved": "تم الحفظ ✅",
        "weekly_forecast": "توقعات الأسبوع",
        "peak_heat": "أشد ساعات الحرارة خلال ٤٨ ساعة",
        "ask_anything": "اكتب رسالتك…",
        "baseline_hint": "تُستخدم الحرارة الأساسية لاكتشاف زيادة ≥ 0.5°م (مراعاة ظاهرة أوتهوف).",
        "emergency_title": "جهة اتصال للطوارئ",
        "primary_name": "الاسم الأساسي",
        "primary_phone": "الهاتف الأساسي",
        "secondary_name": "اسم احتياطي (اختياري)",
        "secondary_phone": "هاتف احتياطي (اختياري)",
        "save_contacts": "حفظ جهات الاتصال",
        "contacts_saved": "تم الحفظ ✅",
        "export_csv": "تصدير درجات الحرارة (CSV)",
        "download_csv": "تحميل temps.csv",
        "instant_plan_title": "خطة تبريد فورية",
        "do_now": "افعل الآن",
        "plan_later": "خطط لوقت لاحق اليوم",
        "watch_for": "انتبه إلى",
        "temp_trend": "📈 سجل درجات الحرارة",
        "recent_entries": "أحدث الإدخالات",
        "quick_tips": "نصائح سريعة (اليوم)",
        "mood": "المزاج",
        "energy": "الطاقة",
        "sleep": "جودة النوم",
        "hydration": "الترطيب",
        "activity": "النشاط",
        "logout": "تسجيل الخروج",
        "quick_menu": "☰ قائمة سريعة",
        "auto_save_alerts": "حفظ التنبيهات تلقائيًا في اليوميات",
        "other_activity": "نشاط آخر",
        "add_to_journal": "إضافة إلى اليوميات",
        "what_if_tips": "ملاحظات/اعتبارات أخرى",
        "ask_ai_tips": "اطلب نصائح مخصصة من المساعد"
    }
}

# ================== STYLES ==================
ACCESSIBLE_CSS = """
<style>
html, body, [class*="css"]  { font-size: 18px; }
.big-card {background:#fff;padding:18px;border-radius:14px;border-left:10px solid var(--left);box-shadow:0 2px 8px rgba(0,0,0,0.06);}
.badge {display:inline-block;padding:6px 10px;border-radius:999px;border:1px solid rgba(0,0,0,0.1);margin-right:6px;}
.small {opacity:0.75;font-size:14px;}
h3 { margin-top: 0.2rem; }
.stButton>button { padding: 0.6rem 1.1rem; font-weight: 600; }
</style>
"""
st.markdown(ACCESSIBLE_CSS, unsafe_allow_html=True)

# ================== UTIL: time ==================
def utc_iso_now():
    return datetime.now(timezone.utc).isoformat()

def as_dubai_label(utc_iso: str):
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z","")).astimezone(TZ) if "Z" in utc_iso or "+" in utc_iso else datetime.fromisoformat(utc_iso).astimezone(TZ)
    except:
        try:
            dt = datetime.fromisoformat(utc_iso).replace(tzinfo=timezone.utc).astimezone(TZ)
        except:
            return utc_iso
    return dt.strftime("%Y-%m-%d %H:%M")

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
    c.execute("""CREATE TABLE IF NOT EXISTS emergency_contacts(
        username TEXT PRIMARY KEY,
        primary_name TEXT,
        primary_phone TEXT,
        secondary_name TEXT,
        secondary_phone TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        username TEXT PRIMARY KEY,
        baseline REAL
    )""")
    conn.commit()

def migrate_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(temps)")
    cols = [r[1] for r in c.fetchall()]
    if "feels_like" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN feels_like REAL")
    if "humidity" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN humidity REAL")
    conn.commit()

init_db(); migrate_db()

# ================== HELPERS: DB OPS ==================
def upsert_baseline(username, baseline):
    c = get_conn().cursor()
    c.execute("""INSERT INTO settings (username, baseline) VALUES (?,?)
                 ON CONFLICT(username) DO UPDATE SET baseline=excluded.baseline
              """, (username, baseline))
    get_conn().commit()

def load_baseline(username, default=37.0):
    c = get_conn().cursor()
    c.execute("SELECT baseline FROM settings WHERE username=?", (username,))
    row = c.fetchone()
    return float(row[0]) if row and row[0] is not None else default

def insert_temp(username, dt_utc, body, weather, feels_like, humidity, status):
    c = get_conn().cursor()
    c.execute("""
        INSERT INTO temps (username, date, body_temp, weather_temp, feels_like, humidity, status)
        VALUES (?,?,?,?,?,?,?)
    """,(username, dt_utc, body, weather, feels_like, humidity, status))
    get_conn().commit()

def insert_journal(username, dt_utc, entry_obj):
    c = get_conn().cursor()
    c.execute("INSERT INTO journal VALUES (?,?,?)", (username, dt_utc, json.dumps(entry_obj, ensure_ascii=False)))
    get_conn().commit()

def get_recent_temps(username, limit=50):
    c = get_conn().cursor()
    c.execute("""SELECT date, body_temp, feels_like, status
                 FROM temps WHERE username=? ORDER BY date DESC LIMIT ?""",
              (username, limit))
    return c.fetchall()

def get_recent_journal(username, limit=30):
    c = get_conn().cursor()
    c.execute("""SELECT date, entry FROM journal
                 WHERE username=? ORDER BY date DESC LIMIT ?""",
              (username, limit))
    return c.fetchall()

def get_contacts(username):
    c = get_conn().cursor()
    c.execute("SELECT primary_name, primary_phone, secondary_name, secondary_phone FROM emergency_contacts WHERE username=?",
              (username,))
    row = c.fetchone()
    return row if row else ("","","","")

def save_contacts(username, pn, pp, sn, sp):
    c = get_conn().cursor()
    c.execute("""INSERT INTO emergency_contacts (username, primary_name, primary_phone, secondary_name, secondary_phone)
                 VALUES (?,?,?,?,?)
                 ON CONFLICT(username) DO UPDATE SET
                 primary_name=excluded.primary_name,
                 primary_phone=excluded.primary_phone,
                 secondary_name=excluded.secondary_name,
                 secondary_phone=excluded.secondary_phone
              """, (username, pn, pp, sn, sp))
    get_conn().commit()

# ================== WEATHER & GEO ==================
@st.cache_data(ttl=600)
def get_weather(city="Abu Dhabi,AE"):
    if not OPENWEATHER_API_KEY:
        return None, "Missing OPENWEATHER_API_KEY"
    try:
        base = "https://api.openweathermap.org/data/2.5/"
        params_now = {"q": city, "appid": OPENWEATHER_API_KEY, "units":"metric", "lang":"en"}
        r_now = requests.get(base+"weather", params=params_now, timeout=6); r_now.raise_for_status()
        jn = r_now.json()
        temp  = float(jn["main"]["temp"])
        feels = float(jn["main"]["feels_like"])
        hum   = float(jn["main"]["humidity"])
        desc  = jn["weather"][0]["description"]

        params_fc = {"q": city, "appid": OPENWEATHER_API_KEY, "units":"metric", "lang":"en"}
        r_fc = requests.get(base+"forecast", params=params_fc, timeout=8); r_fc.raise_for_status()
        jf = r_fc.json()
        items = jf.get("list", [])[:16]
        forecast = [{
            "time": it["dt_txt"],
            "feels_like": float(it["main"]["feels_like"]),
            "humidity": float(it["main"]["humidity"]),
            "desc": it["weather"][0]["description"]
        } for it in items]
        top = sorted(forecast, key=lambda x: x["feels_like"], reverse=True)[:4]
        peak_hours = [f'{t["time"][5:16]} (~{round(t["feels_like"],1)}°C, {int(t["humidity"])}%)' for t in top]
        return {"temp": temp, "feels_like": feels, "humidity": hum, "desc": desc,
                "forecast": forecast, "peak_hours": peak_hours}, None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=600)
def geocode_place(q):
    if not OPENWEATHER_API_KEY:
        return None, None, None
    try:
        r = requests.get("http://api.openweathermap.org/geo/1.0/direct",
                         params={"q": q, "limit": 1, "appid": OPENWEATHER_API_KEY}, timeout=6)
        r.raise_for_status()
        arr = r.json()
        if not arr: return None, None, None
        it = arr[0]
        label = f"{it.get('name','')}, {it.get('country','')}"
        return label, it.get("lat"), it.get("lon")
    except:
        return None, None, None

@st.cache_data(ttl=300)
def get_weather_by_coords(lat, lon):
    if not OPENWEATHER_API_KEY or lat is None or lon is None:
        return None
    try:
        r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                         params={"lat":lat,"lon":lon,"appid":OPENWEATHER_API_KEY,"units":"metric"}, timeout=6)
        r.raise_for_status()
        j = r.json()
        return {
            "temp": float(j["main"]["temp"]),
            "feels_like": float(j["main"]["feels_like"]),
            "humidity": float(j["main"]["humidity"]),
            "desc": j["weather"][0]["description"]
        }
    except:
        return None

# ================== RISK & TIPS ==================
def risk_from_env(feels_like_c, humidity):
    score = 0
    if feels_like_c >= 39: score += 3
    elif feels_like_c >= 35: score += 2
    elif feels_like_c >= 32: score += 1
    if humidity >= 60 and feels_like_c >= 32: score += 1
    return score

def risk_from_person(body_temp, baseline):
    delta = (body_temp - baseline) if (body_temp is not None and baseline is not None) else 0.0
    if delta >= 1.0: return 2
    if delta >= 0.5: return 1
    return 0

def compute_risk(feels_like, humidity, body_temp, baseline):
    score = risk_from_env(feels_like, humidity) + risk_from_person(body_temp, baseline)
    if score >= 7:  return {"status":"Danger","color":"red","icon":"🔴","advice":"High risk: stay in AC, avoid exertion, use cooling packs, rest. Seek clinical advice if symptoms worsen."}
    if score >= 5:  return {"status":"High","color":"orangered","icon":"🟠","advice":"Elevated risk: limit midday, pre-cool, pace, shade/AC."}
    if score >= 3:  return {"status":"Caution","color":"orange","icon":"🟡","advice":"Mild risk: hydrate, take breaks, prefer shade/AC, monitor symptoms."}
    return {"status":"Safe","color":"green","icon":"🟢","advice":"You look safe. Keep cool and hydrated."}

def moving_avg(seq, n):
    if not seq: return 0.0
    if len(seq) < n: return round(sum(seq)/len(seq), 2)
    return round(sum(seq[-n:]) / n, 2)

def should_alert(temp_series, baseline, delta=ALERT_DELTA_C, confirm=ALERT_CONFIRM):
    if len(temp_series) < confirm: return False
    recent = temp_series[-confirm:]
    return all((t - baseline) >= delta for t in recent)

def simulate_next(prev, baseline):
    drift = random.uniform(-0.05, 0.08)
    surge = random.uniform(0.2, 0.5) if random.random() < 0.12 else 0.0
    next_t = prev + drift + surge
    return max(35.5, min(41.0, round(next_t, 2)))

TRIGGERS_EN = [
    "Direct sun","Hot car","Sauna/Hot shower","Cooking steam","Crowded place",
    "Exercise (light)","Exercise (moderate)","Exercise (intense)","Housework","Long walk",
    "Hot drinks","Hot/spicy food","Alcohol","Large meal",
    "Fever/illness","Menstrual cycle","Poor sleep","Dehydration",
    "High humidity","Poor AC/ventilation","Tight clothing",
    "Stress/anxiety","Overstimulation (noise/lights)"
]
TRIGGERS_AR = [
    "شمس مباشرة","سيارة حارة","ساونا/حمام ساخن","بخار الطبخ","مكان مزدحم",
    "تمارين (خفيفة)","تمارين (متوسطة)","تمارين (شديدة)","أعمال منزلية","مشي طويل",
    "مشروبات ساخنة","طعام حار","كحول","وجبة كبيرة",
    "حمّى/مرض","الدورة الشهرية","نوم سيئ","جفاف",
    "رطوبة مرتفعة","تكييف/تهوية ضعيفة","ملابس ضيقة",
    "توتر/قلق","تحفيز زائد (ضوضاء/أضواء)"
]
SYMPTOMS_EN = [
    "Blurred vision","Double vision","Eye pain",
    "Fatigue","Brain fog","Memory issues",
    "Muscle weakness","Spasticity","Tremor","Coordination issues","Balance problems",
    "Numbness","Tingling","Burning sensation","Heat sensitivity",
    "Gait difficulty","Leg heaviness",
    "Dizziness/lightheadedness",
    "Urgency","Frequency","Constipation",
    "Low mood","Anxiety","Poor sleep"
]
SYMPTOMS_AR = [
    "رؤية ضبابية","ازدواج الرؤية","ألم بالعين",
    "إرهاق","ضبابية ذهنية","مشاكل ذاكرة",
    "ضعف عضلي","تشنج","رجفة","مشاكل التناسق","مشاكل التوازن",
    "خدر","وخز","إحساس بالحرق","حساسية للحرارة",
    "صعوبة بالمشي","ثقل الساق",
    "دوار/خفة الرأس",
    "إلحاح بولي","كثرة تبول","إمساك",
    "مزاج منخفض","قلق","نوم سيئ"
]

TIP_RULES_EN = {
    "Direct sun": ["Delay to early/late hours", "Shade + UV hat/umbrella", "Cooling scarf/bandana"],
    "Hot car": ["Pre-cool car (AC) 5–10 min", "Use reflective sunshade", "Cold water ready before entering"],
    "Sauna/Hot shower": ["Switch to lukewarm", "Shorter duration", "Cool rinse at end"],
    "Cooking steam": ["Ventilation/hood on", "Prep in cooler hours", "Take short breaks to AC"],
    "Crowded place": ["Choose off-peak hours", "Cool pack (neck/wrist)", "Hydrate before/after"],
    "Exercise (light)": ["Intervals with rest", "Cool towel between sets", "Hydration plan (sips every 10–15 min)"],
    "Exercise (moderate)": ["Move session to dawn/evening", "Pre-cool 15 min", "Electrolytes if >45 min"],
    "Exercise (intense)": ["Consider indoor/AC gym", "Short blocks (5–8 min)", "Cooling vest if available"],
    "Housework": ["Split tasks across day", "Fan + AC together", "Frequent cool breaks"],
    "Long walk": ["Shaded route", "Light clothing", "Carry cold water"],
    "Hot drinks": ["Switch to iced/room-temp", "Small sips slowly"],
    "Hot/spicy food": ["Pick mild options", "Cool beverage with meal"],
    "Alcohol": ["Extra water 1:1", "Avoid midday outdoors"],
    "Large meal": ["Smaller portions", "Rest in cool room after"],
    "Fever/illness": ["Rest; call clinician if worse", "Keep room cool", "Fluids + electrolytes"],
    "Menstrual cycle": ["Plan lighter load", "Extra hydration", "Cooling pad for comfort"],
    "Poor sleep": ["Lower intensity day", "Nap/quiet rest", "Keep bedroom cool tonight"],
    "Dehydration": ["Oral rehydration salts", "Steady sips—not chugging"],
    "High humidity": ["Prefer AC over fan", "Limit outdoor time", "Loose, wicking fabrics"],
    "Poor AC/ventilation": ["Close doors to cool one room", "Use curtains/shades", "Service filter if dusty"],
    "Tight clothing": ["Switch to looser layers", "Breathable fabric"],
    "Stress/anxiety": ["Slow breathing (4-6/min)", "Short pause in AC", "Light movement, not vigorous"],
    "Overstimulation (noise/lights)": ["Quieter space", "Sunglasses/earbuds", "Short reset breaks"]
}

def L(text, lang):
    if lang == "Arabic":
        dict_ar = {
            "Delay to early/late hours":"قم بالنشاط صباحًا أو مساءً",
            "Shade + UV hat/umbrella":"استخدم الظل وقبعة/مظلّة",
            "Cooling scarf/bandana":"وشاح/رباط تبريد",
            "Pre-cool car (AC) 5–10 min":"تبريد السيارة بالمكيف ٥–١٠ دقائق",
            "Use reflective sunshade":"استخدم عاكس شمس",
            "Cold water ready before entering":"أحضر ماءً باردًا قبل الدخول",
            "Switch to lukewarm":"استبدل بالماء الفاتر",
            "Shorter duration":"مدة أقصر",
            "Cool rinse at end":"شطف بارد في النهاية",
            "Ventilation/hood on":"تشغيل الشفاط/التهوية",
            "Prep in cooler hours":"التجهيز في ساعات أبرد",
            "Take short breaks to AC":"استراحات قصيرة على المكيف",
            "Choose off-peak hours":"اختيار أوقات أقل ازدحامًا",
            "Cool pack (neck/wrist)":"كمادة تبريد (الرقبة/المعصم)",
            "Hydrate before/after":"ترطيب قبل/بعد",
            "Intervals with rest":"فترات متقطعة مع راحة",
            "Cool towel between sets":"منشفة باردة بين التمارين",
            "Hydration plan (sips every 10–15 min)":"ترطيب برشفات كل 10–15 دقيقة",
            "Move session to dawn/evening":"انقل التمرين للفجر/المساء",
            "Pre-cool 15 min":"تبريد مسبق ١٥ دقيقة",
            "Electrolytes if >45 min":"محاليل أملاح إن تجاوزت ٤٥ دقيقة",
            "Consider indoor/AC gym":"فضّل الصالة المكيّفة",
            "Short blocks (5–8 min)":"فترات قصيرة (٥–٨ دقائق)",
            "Cooling vest if available":"سترة تبريد إن توفرت",
            "Split tasks across day":"قسّم الأعمال على اليوم",
            "Fan + AC together":"مروحة + مكيف معًا",
            "Frequent cool breaks":"استراحات باردة متكررة",
            "Shaded route":"مسار مظلل",
            "Light clothing":"ملابس خفيفة",
            "Carry cold water":"احمل ماءً بارداً",
            "Switch to iced/room-temp":"استبدل بمشروبات باردة/فاترة",
            "Small sips slowly":"رشفة صغيرة ببطء",
            "Pick mild options":"اختر طعامًا أقل حدة",
            "Cool beverage with meal":"مشروب بارد مع الوجبة",
            "Extra water 1:1":"ماء إضافي بنسبة ١:١",
            "Avoid midday outdoors":"تجنب الظهيرة خارجًا",
            "Smaller portions":"حصص أصغر",
            "Rest in cool room after":"استرح في غرفة مكيّفة",
            "Rest; call clinician if worse":"استرح واتصل بالطبيب عند التدهور",
            "Keep room cool":"حافظ على برودة الغرفة",
            "Fluids + electrolytes":"سوائل + أملاح",
            "Plan lighter load":"خفف الجهد اليوم",
            "Extra hydration":"ترطيب إضافي",
            "Cooling pad for comfort":"وسادة تبريد للراحة",
            "Lower intensity day":"خفّض شدة نشاطك اليوم",
            "Nap/quiet rest":"غفوة/راحة هادئة",
            "Keep bedroom cool tonight":"برّد غرفة النوم الليلة",
            "Oral rehydration salts":"محاليل أملاح فموية",
            "Steady sips—not chugging":"رشفة ثابتة وليس دفعة واحدة",
            "Prefer AC over fan":"استخدم المكيف بدلاً من المروحة",
            "Limit outdoor time":"قلّل الخروج",
            "Loose, wicking fabrics":"أقمشة خفيفة ماصّة",
            "Close doors to cool one room":"أغلق الأبواب لتبريد غرفة واحدة",
            "Use curtains/shades":"استخدم ستائر/مظلّات",
            "Service filter if dusty":"نظّف الفلتر إن كان مغبرًا",
            "Switch to looser layers":"اختر ملابس أوسع",
            "Breathable fabric":"قماش قابل للتنفس",
            "Slow breathing (4-6/min)":"تنفس ببطء (٤–٦/د)",
            "Short pause in AC":"استراحة قصيرة على المكيف",
            "Light movement, not vigorous":"حركة خفيفة وليست شديدة",
            "Quieter space":"مكان أهدأ",
            "Sunglasses/earbuds":"نظارات شمس/سماعات",
            "Short reset breaks":"استراحات قصيرة لإعادة التوازن",
            "Hydration boost (electrolytes)":"ترطيب مع أملاح",
            "Cooling pack (neck/wrists)":"كمادة تبريد (الرقبة/المعصم)",
            "Rest; monitor symptoms":"استرح وراقب الأعراض",
            "Red flags: confusion, chest pain, fainting → seek care":"أعراض خطرة: ارتباك، ألم صدري، إغماء → اطلب الرعاية"
        }
        return dict_ar.get(text, text)
    return text

def tailored_tips(selected_triggers, feels_like, humidity, delta, lang="English"):
    tips_now, tips_later, tips_watch = [], [], []
    for trig in selected_triggers:
        key = trig if lang=="English" else None
        if lang=="Arabic" and trig in TRIGGERS_AR:
            idx = TRIGGERS_AR.index(trig)
            key = TRIGGERS_EN[min(idx, len(TRIGGERS_EN)-1)]
        if key and key in TIP_RULES_EN:
            for t in TIP_RULES_EN[key]:
                tips_now.append(L(t, lang))
    if feels_like >= 38:
        tips_now += [L("Cooling pack (neck/wrists)", lang)]
        tips_later += [L("Prefer AC over fan", lang)]
    if humidity >= 60:
        tips_now += [L("Prefer AC over fan", lang), L("Hydration boost (electrolytes)", lang)]
    if delta >= 0.5:
        tips_now += [L("Rest; monitor symptoms", lang)]
    tips_watch = [L("Red flags: confusion, chest pain, fainting → seek care", lang)]
    def dedup(seq):
        seen=set(); out=[]
        for s in seq:
            if s not in seen:
                seen.add(s); out.append(s)
        return out
    return dedup(tips_now)[:6], dedup(tips_later)[:4], tips_watch[:1]

# ================== AI (Chat) ==================
def ai_response(prompt, lang):
    sys_prompt = ("You are Raha MS AI Companion. Warm, brief, practical, culturally aware tips for GCC climate. "
                  "Use friendly, supportive tone. Consider humidity, cooling, hydration, pacing, prayer/errand timing. "
                  "Not medical care.")
    sys_prompt += " Respond only in Arabic." if lang == "Arabic" else " Respond only in English."
    if not client:
        return None, "no_key"
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":sys_prompt},
                      {"role":"user","content":prompt}],
            temperature=0.6
        )
        return resp.choices[0].message.content, None
    except Exception as e:
        return None, str(e)

def build_context(username, last_check):
    rows = get_recent_journal(username, limit=7)
    lines = []
    for d, e in rows[::-1]:
        d_local = as_dubai_label(d)
        try:
            obj = json.loads(e)
            t = obj.get("type","NOTE")
            if t=="ALERT":
                lines.append(f"{d_local} ALERT: reasons={obj.get('reasons', [])}, note={obj.get('note','')}")
            elif t=="ALERT_AUTO":
                lines.append(f"{d_local} ALERT_AUTO: body={obj.get('body_temp')} baseline={obj.get('baseline')}")
            elif t=="DAILY":
                lines.append(f"{d_local} DAILY: triggers={obj.get('triggers', [])}, symptoms={obj.get('symptoms', [])}")
            elif t=="PLAN":
                lines.append(f"{d_local} PLAN: {obj.get('activity','')} {obj.get('start','')}→{obj.get('end','')}")
            else:
                lines.append(f"{d_local} NOTE")
        except:
            lines.append(f"{d_local} RAW")
    vitals = ""
    if last_check:
        vitals = (f"Latest: body {round(last_check['body_temp'],1)}°C vs baseline {round(last_check['baseline'],1)}°C; "
                  f"Feels-like {round(last_check['feels_like'],1)}°C, humidity {int(last_check['humidity'])}%. "
                  f"Status {last_check['status']}.")
    return (("\n".join(lines) if lines else "(no recent journal entries)") +
            ("\n"+vitals if vitals else ""))

# ================== SIDEBAR ==================
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/6512b826bd06f692ad81f896773b44a3b0482001/logo1.png"
st.sidebar.image(logo_url, use_container_width=True)

app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English","Arabic"])
T = TEXTS[app_language]

# RTL for Arabic
if app_language == "Arabic":
    st.markdown("""
    <style>
    body, .block-container { direction: rtl; text-align: right; }
    [data-testid="stSidebar"] { direction: rtl; text-align: right; }
    </style>
    """, unsafe_allow_html=True)

# Auth
with st.sidebar.expander(T["login_title"], expanded=False):
    username_in = st.text_input(T["username"], key="user_in")
    password_in = st.text_input(T["password"], type="password", key="pass_in")
    c1, c2 = st.columns(2)
    with c1:
        if st.button(T["login"], key="login_btn"):
            cdb = get_conn().cursor()
            cdb.execute("SELECT * FROM users WHERE username=? AND password=?", (username_in, password_in))
            if cdb.fetchone():
                st.session_state["user"] = username_in
                # initialize baseline record if missing
                upsert_baseline(username_in, load_baseline(username_in))
                st.success(T["logged_in"])
            else:
                st.error(T["bad_creds"])
    with c2:
        if st.button(T["register"], key="register_btn"):
            try:
                cdb = get_conn().cursor()
                cdb.execute("INSERT INTO users VALUES (?,?)", (username_in, password_in))
                get_conn().commit()
                # create default baseline
                upsert_baseline(username_in, 37.0)
                st.success(T["account_created"])
            except Exception:
                st.error(T["user_exists"])
    if st.button(T["logout"], key="logout_btn"):
        st.session_state.pop("user", None)
        st.success(T["logged_out"])

# Sidebar: Emergency pull-down
st.sidebar.markdown(f"### 🚑 {T['emergency_title']}")
if "user" in st.session_state:
    saved_pn, saved_pp, saved_sn, saved_sp = get_contacts(st.session_state["user"])
else:
    saved_pn, saved_pp, saved_sn, saved_sp = ("","","","")

options = []
if saved_pn and saved_pp: options.append(f"{saved_pn} — {saved_pp}")
if saved_sn and saved_sp: options.append(f"{saved_sn} — {saved_sp}")
if options:
    st.sidebar.selectbox("Who to call quickly?", options, index=0)
    st.sidebar.caption("Tip: long-press to copy number on mobile")

with st.sidebar.expander("Edit emergency contacts", expanded=False):
    pn = st.text_input(T["primary_name"], saved_pn, key="pn")
    pp = st.text_input(T["primary_phone"], saved_pp, key="pp")
    sn = st.text_input(T["secondary_name"], saved_sn, key="sn")
    sp = st.text_input(T["secondary_phone"], saved_sp, key="sp")
    if "user" in st.session_state and st.button(T["save_contacts"]):
        save_contacts(st.session_state["user"], pn, pp, sn, sp)
        st.success(T["contacts_saved"])

st.sidebar.caption("If unwell: move to AC • drink cool water • cooling pack • call emergency")

# ===== NEW: Top Quick Menu for mobile discoverability =====
with st.expander(T["quick_menu"], expanded=False):
    st.caption("Most features live in the left menu. On phones, tap the menu icon or use this quick menu.")
    if options:
        st.selectbox("🚑 Quick dial", options, index=0, key="quick_dial_clone")
    else:
        st.text("Add an emergency contact in the sidebar settings.")

# Navigation
page = st.sidebar.radio("Navigate", [
    T["about_title"], T["monitor"], T["planner"], T["journal_tab"], T["assistant_tab"], T["settings"]
])

# ================== ABOUT ==================
def render_about_page(lang: str = "English"):
    if lang == "English":
        st.title("🧠 Welcome to Raha MS")
        st.markdown("""
Raha MS was designed **with and for people living with MS in the Gulf**.  
Life here is hot and humid—we get it. This app is meant to be a calm, simple companion that helps you feel more in control each day.
""")
        st.subheader("🌡️ Why heat matters in MS")
        st.info("Even a small rise in body temperature (about 0.5°C) can temporarily worsen MS symptoms — this is called **Uhthoff’s phenomenon**. Knowing your own patterns helps you plan smart and feel safer.")
        st.subheader("✨ What Raha MS can do for you")
        st.markdown("""
- **See your heat risk at a glance** — track your body temperature against your personal baseline.  
- **Notice your triggers** — sun, exercise, spicy food, stress, crowded places, and more.  
- **Write your journey** — short, private notes about symptoms and what helped.  
- **Get gentle, culturally aware tips** — hydration, cooling, timing around prayer and errands, fasting considerations.
""")
        st.subheader("🤝 Our intention")
        st.success("To offer simple, practical support that fits the Gulf climate and your daily life — so you can pace yourself, reduce uncertainty, and keep doing what matters to you.")
        st.caption("**Prototype notice:** This is a prototype for education only, not medical advice. Your data stays on your device (SQLite).")
    else:
        st.title("🧠 مرحبًا بك في راحة إم إس")
        st.markdown("""
تم تصميم راحة إم إس **مع وبالتعاون مع أشخاص يعيشون مع التصلب المتعدد في الخليج**.  
نعرف حرارة ورطوبة منطقتنا، وهذا التطبيق رفيق بسيط وهادئ ليساعدك على الشعور بسيطرة أكبر كل يوم.
""")
        st.subheader("🌡️ لماذا تؤثر الحرارة في أعراض التصلب المتعدد؟")
        st.info("حتى الارتفاع البسيط (حوالي 0.5°م) قد يزيد الأعراض مؤقتًا — وتُسمّى **ظاهرة أوتهوف**. فهم نمطك الشخصي يساعدك على التخطيط براحة وأمان.")
        st.subheader("✨ ماذا يقدّم لك راحة إم إس؟")
        st.markdown("""
- **رؤية سريعة لمستوى الخطر الحراري** — نتابع حرارة جسمك مقارنة بقاعدتك الشخصية.  
- **التعرّف على المحفزات** — الشمس، التمرين، الطعام الحار، التوتر، الأماكن المزدحمة.. وغيرها.  
- **تدوين رحلتك** — ملاحظات قصيرة وخاصة عن الأعراض وما ساعدك.  
- **نصائح لطيفة ومناسبة ثقافيًا** — الترطيب، التبريد، تنظيم الوقت مع الصلاة والمشاوير، ومراعاة الصيام.
""")
        st.subheader("🤝 نيتنا")
        st.success("أن نقدّم دعمًا بسيطًا وعمليًا يناسب مناخ الخليج وحياتك اليومية — لتُنظّم مجهودك وتخفّف القلق وتستمر في ما يهمك.")
        st.caption("**ملاحظة النموذج الأولي:** هذا للتثقيف فقط وليس نصيحة طبية. تبقى بياناتك على جهازك (SQLite).")

# ================== MONITOR ==================
def render_monitor():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    # ensure baseline in state from DB
    if "baseline" not in st.session_state:
        st.session_state["baseline"] = load_baseline(st.session_state["user"], 37.0)

    st.title("☀️ " + T["risk_dashboard"])

    # controls (baseline read-only + optional temporary override)
    st.session_state.setdefault("use_temp_baseline", False)
    st.session_state.setdefault("temp_baseline", st.session_state["baseline"])
    st.session_state.setdefault("city", "Abu Dhabi,AE")
    st.session_state.setdefault("auto_save_alerts", True)

    colA, colB, colC = st.columns([1.4,1,1])
    with colA:
        st.markdown(f"**{T['personal_baseline']}:** {round(st.session_state['baseline'],1)}°C  · "
                    f"<span style='opacity:.75'>(Edit in Settings)</span>", unsafe_allow_html=True)
        st.caption(T["baseline_hint"])
    with colB:
        st.session_state["city"] = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0, key="monitor_city")
    with colC:
        interval = st.slider("⏱️ " + T["update_every"], 2, 20, SIM_INTERVAL_SEC, 1)

    c1, c2 = st.columns(2)
    with c1:
        st.session_state["use_temp_baseline"] = st.checkbox("Use a temporary baseline today", value=st.session_state["use_temp_baseline"])
    with c2:
        st.session_state["auto_save_alerts"] = st.checkbox(T["auto_save_alerts"], value=st.session_state["auto_save_alerts"])

    if st.session_state["use_temp_baseline"]:
        st.session_state["temp_baseline"] = st.number_input("Temp baseline (°C)", 35.5, 38.5,
                                                            st.session_state.get("temp_baseline", st.session_state["baseline"]), 0.1)

    active_baseline = st.session_state["temp_baseline"] if st.session_state["use_temp_baseline"] else st.session_state["baseline"]

    # session vars
    st.session_state.setdefault("live_running", False)
    st.session_state.setdefault("live_raw", [])
    st.session_state.setdefault("live_smoothed", [])
    st.session_state.setdefault("live_tick", 0)
    st.session_state.setdefault("last_db_write_tick", -999)
    st.session_state.setdefault("last_alert_ts", 0.0)
    st.session_state.setdefault("_last_tick_ts", 0.0)
    st.session_state.setdefault("last_check", None)
    st.session_state.setdefault("_last_auto_saved_at", 0.0)

    weather, err = get_weather(st.session_state["city"])
    if weather is None:
        st.error(f"{T['weather_fail']}: {err}")
        return

    b1, b2, b3 = st.columns([1,1,1])
    with b1:
        if not st.session_state["live_running"] and st.button(T["start"], use_container_width=True):
            st.session_state["live_running"] = True
            start = round(active_baseline + random.uniform(-0.2, 0.2), 2)
            st.session_state["live_raw"] = [start]
            st.session_state["live_smoothed"] = [start]
            st.session_state["live_tick"] = 0
            st.session_state["last_db_write_tick"] = -999
            st.session_state["last_alert_ts"] = 0.0
            st.session_state["_last_tick_ts"] = 0.0
            st.rerun()
    with b2:
        if st.session_state["live_running"] and st.button(T["stop"], use_container_width=True):
            st.session_state["live_running"] = False
            st.rerun()
    with b3:
        if st.button(T["reset"], use_container_width=True):
            st.session_state["live_raw"] = []
            st.session_state["live_smoothed"] = []
            st.session_state["live_tick"] = 0
            st.session_state["last_db_write_tick"] = -999
            st.session_state["last_alert_ts"] = 0.0

    now = time.time()
    if st.session_state["live_running"] and (now - st.session_state["_last_tick_ts"]) >= interval:
        st.session_state["_last_tick_ts"] = now
        prev = st.session_state["live_raw"][-1] if st.session_state["live_raw"] else active_baseline
        raw = simulate_next(prev, active_baseline)
        st.session_state["live_raw"].append(raw)
        smoothed = moving_avg(st.session_state["live_raw"], SMOOTH_WINDOW)
        st.session_state["live_smoothed"].append(smoothed)
        st.session_state["live_tick"] += 1

        risk = compute_risk(weather["feels_like"], weather["humidity"], smoothed, active_baseline)
        st.session_state["last_check"] = {
            "city": st.session_state["city"], "body_temp": smoothed, "baseline": active_baseline,
            "weather_temp": weather["temp"], "feels_like": weather["feels_like"],
            "humidity": weather["humidity"], "weather_desc": weather["desc"],
            "status": risk["status"], "color": risk["color"], "icon": risk["icon"],
            "advice": risk["advice"], "time": utc_iso_now()
        }

        # Alert handling
        if should_alert(st.session_state["live_smoothed"], active_baseline, ALERT_DELTA_C, ALERT_CONFIRM):
            if (now - st.session_state["last_alert_ts"]) >= ALERT_COOLDOWN_SEC:
                st.session_state["last_alert_ts"] = now
                st.warning("⚠️ Rise ≥ 0.5 °C above baseline detected. Consider cooling and rest. You can log a reason below for tailored tips.")
            # Auto-save minimal alert entry
            if st.session_state["auto_save_alerts"] and (now - st.session_state.get("_last_auto_saved_at", 0.0) >= 180):
                try:
                    entry = {
                        "type":"ALERT_AUTO",
                        "at": utc_iso_now(),
                        "body_temp": round(smoothed,1),
                        "baseline": round(active_baseline,1)
                    }
                    insert_journal(st.session_state.get("user","guest"), utc_iso_now(), entry)
                    st.session_state["_last_auto_saved_at"] = now
                except Exception as e:
                    st.warning(f"Auto-save failed: {e}")

        # DB write every Nth sample
        if st.session_state["live_tick"] - st.session_state["last_db_write_tick"] >= DB_WRITE_EVERY_N:
            try:
                insert_temp(st.session_state.get("user","guest"), utc_iso_now(),
                            smoothed, weather["temp"], weather["feels_like"], weather["humidity"], risk["status"])
                st.session_state["last_db_write_tick"] = st.session_state["live_tick"]
            except Exception as e:
                st.warning(f"Could not save to DB: {e}")

        st.rerun()

    # status card
    if st.session_state["last_check"]:
        last = st.session_state["last_check"]
        st.markdown(f"""
<div class="big-card" style="--left:{last['color']}">
  <h3>{last['icon']} <strong>Status: {last['status']}</strong></h3>
  <p style="margin:6px 0 0 0">{last['advice']}</p>
  <div class="small" style="margin-top:8px">
    <span class="badge">Feels-like: {round(last['feels_like'],1)}°C</span>
    <span class="badge">Humidity: {int(last['humidity'])}%</span>
    <span class="badge">Body: {round(last['body_temp'],1)}°C</span>
    <span class="badge">Baseline: {round(last['baseline'],1)}°C</span>
    <span class="badge">{T['status_checked']}: {as_dubai_label(last['time'])} (Dubai)</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # reason picker + tailored tips when above threshold
    if st.session_state["live_smoothed"]:
        latest = st.session_state["live_smoothed"][-1]
        delta = latest - (st.session_state["temp_baseline"] if st.session_state["use_temp_baseline"] else st.session_state["baseline"])
        if delta >= ALERT_DELTA_C:
            st.markdown(f"### {T['log_now']}")
            trigger_options = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
            chosen = st.multiselect(T["triggers_today"], trigger_options, max_selections=6)
            other_text = st.text_input(T["other"], "")
            symptoms_list = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
            selected_symptoms = st.multiselect(T["symptoms_today"], symptoms_list)

            has_reason = (len(chosen) > 0) or (other_text.strip() != "")
            if has_reason:
                do_now, plan_later, watch_for = tailored_tips(
                    chosen + ([other_text] if other_text.strip() else []),
                    st.session_state["last_check"]["feels_like"],
                    st.session_state["last_check"]["humidity"],
                    delta, app_language
                )
                with st.expander(f"🧊 {T['instant_plan_title']}", expanded=True):
                    st.write(f"**{T['do_now']}**")
                    st.write("- " + "\n- ".join(do_now) if do_now else "—")
                    st.write(f"**{T['plan_later']}**")
                    st.write("- " + "\n- ".join(plan_later) if plan_later else "—")
                    st.write(f"**{T['watch_for']}**")
                    st.write("- " + "\n- ".join(watch_for) if watch_for else "—")

            note_text = st.text_input(T["notes"], "")
            if st.button(T["save_entry"]):
                entry = {
                    "type":"ALERT",
                    "at": utc_iso_now(),
                    "body_temp": round(latest,1),
                    "baseline": round((st.session_state['temp_baseline'] if st.session_state['use_temp_baseline'] else st.session_state['baseline']),1),
                    "reasons": chosen + ([f"Other: {other_text.strip()}"] if other_text.strip() else []),
                    "symptoms": selected_symptoms,
                    "note": note_text.strip()
                }
                try:
                    insert_journal(st.session_state.get("user","guest"), utc_iso_now(), entry)
                    st.success(T["saved"])
                except Exception as e:
                    st.warning(f"Could not save note: {e}")

    # chart (Monitor ONLY)
    st.markdown("---")
    st.subheader(T["temp_trend"])
    rows = get_recent_temps(st.session_state.get("user","guest"), limit=50)
    if rows:
        rows = rows[::-1]
        dates = [as_dubai_label(r[0]) for r in rows]
        bt = [r[1] for r in rows]
        ft = [r[2] for r in rows]
        fig, ax = plt.subplots(figsize=(10,4))
        ax.plot(range(len(dates)), bt, marker='o', label="Body", linewidth=2, color='red')
        ax.plot(range(len(dates)), ft, marker='s', label="Feels-like", linewidth=2)
        ax.set_xticks(range(len(dates))); ax.set_xticklabels(dates, rotation=45, fontsize=9)
        ax.set_ylabel("°C"); ax.legend(); ax.grid(True, alpha=0.3)
        st.pyplot(fig)
    else:
        st.info("No temperature data yet.")

# ================== PLANNER ==================
def best_windows_from_forecast(forecast, window_hours=2, top_k=3,
                               max_feels_like=35.0, max_humidity=65, avoid_hours=(10,16)):
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
            if t1[:10]==t2[:10] and (int(t2[11:13]) - int(t1[11:13]) == 3):
                group.append(slots[i+1])
        avg_feels = sum(g["feels_like"] for g in group)/len(group)
        avg_hum = sum(g["humidity"] for g in group)/len(group)
        start = group[0]["time"][:16]
        end_h = int(group[-1]["time"][11:13]) + 3
        end = group[-1]["time"][:11] + f"{end_h:02d}" + group[-1]["time"][13:16]
        cand.append({"start":start,"end":end,"avg_feels":round(avg_feels,1),"avg_hum":int(avg_hum)})
    cand.sort(key=lambda x: (x["avg_feels"], x["avg_hum"]))
    return cand[:top_k]

def render_planner():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return
    st.title("🗺️ " + T["planner"])

    city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0, key="planner_city")
    weather, err = get_weather(city)
    if weather is None:
        st.error(f"{T['weather_fail']}: {err}"); return

    st.subheader("✅ Recommended cooler windows")
    windows = best_windows_from_forecast(weather["forecast"], window_hours=2, top_k=4, max_feels_like=35.0, max_humidity=65)
    if not windows:
        st.info("No optimal windows found; consider early morning or after sunset.")
    else:
        cols = st.columns(len(windows))
        for i, w in enumerate(windows):
            with cols[i]:
                st.markdown(f"**{w['start'][5:16]} → {w['end'][11:16]}**")
                st.caption(f"Feels-like ~{w['avg_feels']}°C • Humidity {w['avg_hum']}%")
                act = st.selectbox("Plan:", ["Walk","Groceries","Beach","Errand"], key=f"plan_{i}")
                other_act = st.text_input(T["other_activity"], key=f"plan_other_{i}")
                final_act = other_act.strip() if other_act.strip() else act
                if st.button(T["add_to_journal"], key=f"add_{i}"):
                    entry = {"type":"PLAN", "at": utc_iso_now(),
                             "city": city, "start": w["start"], "end": w["end"], "activity": final_act,
                             "feels_like": w["avg_feels"], "humidity": w["avg_hum"]}
                    insert_journal(st.session_state["user"], utc_iso_now(), entry)
                    st.success("Saved to Journal")

    st.markdown("---")
    st.subheader("🤔 What-if planner")
    act = st.selectbox("Activity type", ["Light walk (20–30 min)","Moderate exercise (45 min)","Outdoor errand (30–60 min)","Beach (60–90 min)"], key="what_if")
    fl = weather["feels_like"]; hum = weather["humidity"]
    go_badge = "🟢 Go" if (fl<34 and hum<60) else ("🟡 Caution" if (fl<37 and hum<70) else "🔴 Avoid now")
    st.markdown(f"**Now:** {go_badge} — feels-like {round(fl,1)}°C, humidity {int(hum)}%")

    tips_now = []
    if "walk" in act.lower(): tips_now += ["Shaded route", "Carry cool water", "Light clothing"]
    if "exercise" in act.lower(): tips_now += ["Pre-cool 15 min", "Indoor/AC if possible", "Electrolytes if >45 min"]
    if "errand" in act.lower(): tips_now += ["Park in shade", "Plan shortest path", "Pre-cool car 5–10 min"]
    if "beach" in act.lower(): tips_now += ["Umbrella + UV hat", "Cool pack in bag", "Rinse to cool"]
    if fl >= 36: tips_now += ["Cooling scarf/bandana", "Limit to cooler window"]
    if hum >= 60: tips_now += ["Prefer AC over fan", "Extra hydration"]
    tips_now = list(dict.fromkeys(tips_now))[:8]
    st.write("**Tips:**")
    st.write("- " + "\n- ".join(tips_now) if tips_now else "—")

    other_notes = st.text_area(T["what_if_tips"], height=100)
    if client and st.button(T["ask_ai_tips"]):
        q = f"My plan: {act}. Notes: {other_notes}. Current city feels-like {round(fl,1)}°C, humidity {int(hum)}%."
        ans, err2 = ai_response(q, app_language)
        st.info(ans if ans else (T["ai_unavailable"]))

    st.markdown("---")
    st.subheader("📍 Plan by place")
    place_q = st.text_input("Type a place (e.g., Saadiyat Beach)")
    if place_q:
        place, lat, lon = geocode_place(place_q)
        pw = get_weather_by_coords(lat, lon) if lat and lon else None
        if pw:
            st.info(f"{place}: feels-like {round(pw['feels_like'],1)}°C • humidity {int(pw['humidity'])}% • {pw['desc']}")
            better = "place" if pw["feels_like"] < weather["feels_like"] else "city"
            st.caption(f"Cooler now: **{place if better=='place' else city}**")
        else:
            st.warning("Couldn’t fetch that place’s weather.")

    st.caption(f"**{T['peak_heat']}:** " + ("; ".join(weather["peak_hours"]) if weather.get("peak_hours") else "—"))
    with st.expander(T["quick_tips"], expanded=False):
        st.markdown("""- Avoid 10–4 peak heat; use shaded parking.
- Pre-cool before errands; carry cool water.
- Prefer AC indoors; wear light, loose clothing.""")

# ================== JOURNAL ==================
def render_journal():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return
    st.title("📒 " + T["journal_tab"])

    mood = st.select_slider(T["mood"], ["😔","😐","🙂","😄"], value="🙂")
    energy = st.select_slider(T["energy"], ["Low","Medium","High"], value="Medium")
    sleep = st.select_slider(T["sleep"], ["Poor","Okay","Good"], value="Good")
    hydration = st.select_slider(T["hydration"], ["Low","Medium","High"], value="Medium")
    activity = st.text_input(T["activity"], placeholder="e.g., short walk, groceries" if app_language=="English" else "مثلًا: مشي قصير، تسوق")

    symptoms_list = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
    sel_symptoms = st.multiselect(T["symptoms_today"], symptoms_list)
    sym_map = {s: st.select_slider(s, ["Mild","Moderate","Severe"], value="Moderate", key=f"jh_{s}") for s in sel_symptoms}

    triggers_list = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
    sel_triggers = st.multiselect(T["triggers_today"], triggers_list)
    other_tr = st.text_input(T["other"], "")
    notes = st.text_area(T["notes"], height=100)

    if st.button(T["save_entry"]):
        entry = {
            "type":"DAILY",
            "at": utc_iso_now(),
            "mood": mood, "energy": energy, "sleep": sleep, "hydration": hydration,
            "activity": activity.strip(),
            "symptoms": [{"name":k,"severity":v} for k,v in sym_map.items()],
            "triggers": sel_triggers + ([f"Other: {other_tr.strip()}"] if other_tr.strip() else []),
            "notes": notes.strip()
        }
        try:
            insert_journal(st.session_state["user"], utc_iso_now(), entry)
            st.success(T["saved"])
        except Exception as e:
            st.warning(f"Save failed: {e}")

    st.markdown("---")
    st.subheader(T["recent_entries"])
    rows = get_recent_journal(st.session_state["user"], limit=30)
    if rows:
        for d, e in rows:
            d_local = as_dubai_label(d)
            try:
                obj = json.loads(e); label = obj.get("type","NOTE")
                if label=="ALERT":
                    st.write(f"📅 {d_local} — ALERT: {', '.join(obj.get('reasons', []))} • {obj.get('note','')}")
                elif label=="ALERT_AUTO":
                    st.write(f"📅 {d_local} — ALERT (auto): body {obj.get('body_temp')}°C vs baseline {obj.get('baseline')}°C")
                elif label=="DAILY":
                    t = obj.get('triggers', [])
                    s = obj.get('symptoms', [])
                    s_short = ", ".join(f"{x['name']}({x['severity'][0]})" if isinstance(x, dict) else str(x) for x in s)
                    st.write(f"📅 {d_local} — DAILY: triggers: {', '.join(t)} • symptoms: {s_short}")
                elif label=="PLAN":
                    st.write(f"📅 {d_local} — PLAN: {obj.get('activity','')} {obj.get('start','')}→{obj.get('end','')} @ {obj.get('city','')}")
                else:
                    st.write(f"📅 {d_local} → {e}")
            except:
                st.write(f"📅 {d_local} → {e}")
    else:
        st.info("No entries yet.")

# ================== ASSISTANT ==================
def render_assistant():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    st.title("🤖 " + T["assistant_tab"])
    st.caption("I remember your recent notes and can check a place’s weather if you mention it (e.g., Saadiyat Beach).")

    if "chat_msgs" not in st.session_state:
        st.session_state.chat_msgs = []

    for m in st.session_state.chat_msgs:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_msg = st.chat_input(T["ask_anything"])
    if user_msg:
        st.session_state.chat_msgs.append({"role":"user","content":user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)

        ctx = build_context(st.session_state["user"], st.session_state.get("last_check"))

        place, lat, lon = geocode_place(user_msg)
        place_weather = get_weather_by_coords(lat, lon) if lat and lon else None
        extra = ""
        if place_weather and place:
            extra = f"\nPlace weather ({place}): feels-like {round(place_weather['feels_like'],1)}°C, humidity {int(place_weather['humidity'])}% ({place_weather['desc']})."

        prompt = (f"User said: {user_msg}\n\nRecent journal + latest vitals:\n{ctx}{extra}\n\n"
                  f"Please answer in short, warm paragraphs with a few bullet points when helpful. "
                  f"If planning an outing, propose a specific time window around cooler hours for GCC climate.")

        ans, err = ai_response(prompt, app_language)
        reply = ans if ans else ("⚠️ " + (err or T["ai_unavailable"]))
        st.session_state.chat_msgs.append({"role":"assistant","content":reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

# ================== SETTINGS ==================
def render_settings():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return
    st.title("⚙️ " + T["settings"])

    # load current baseline
    current = load_baseline(st.session_state["user"], 37.0)
    new_base = st.number_input(T["personal_baseline"], 35.5, 38.5, current, 0.1)
    st.caption(T["baseline_hint"])
    if new_base != current and st.button("Save baseline"):
        upsert_baseline(st.session_state["user"], float(new_base))
        st.session_state["baseline"] = float(new_base)
        st.success("Baseline saved")

    st.subheader(T["export_csv"])
    if st.button(T["export_csv"]):
        c = get_conn().cursor()
        c.execute("""SELECT date, body_temp, weather_temp, feels_like, humidity, status
                     FROM temps WHERE username=? ORDER BY date ASC""",
                  (st.session_state["user"],))
        rows = c.fetchall()
        buff = io.StringIO(); w = csv.writer(buff)
        w.writerow(["date_utc","body_temp","weather_temp","feels_like","humidity","status"])
        for r in rows: w.writerow(r)
        st.download_button(T["download_csv"], buff.getvalue(), "temps.csv", "text/csv")

# ============= ROUTER =============
if page == T["about_title"]:
    render_about_page(app_language)
elif page == T["monitor"]:
    render_monitor()
elif page == T["planner"]:
    render_planner()
elif page == T["journal_tab"]:
    render_journal()
elif page == T["assistant_tab"]:
    render_assistant()
elif page == T["settings"]:
    render_settings()
