import streamlit as st
import sqlite3, json, requests, random, time
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
from math import isnan

# ================== CONFIG ==================
st.set_page_config(page_title="Raha MS", page_icon="🌡️", layout="wide")

# Timezones
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

# ===== Live/Alert config (simulation or future sensor) =====
SIM_INTERVAL_SEC = 60            # default realistic sampling every 60s
DB_WRITE_EVERY_N = 3             # write to DB every Nth sample during live
ALERT_DELTA_C = 0.5              # ≥ 0.5°C above baseline
ALERT_CONFIRM = 2                # confirm with N consecutive samples
ALERT_COOLDOWN_SEC = 300         # 5 minutes between alert popups
SMOOTH_WINDOW = 3                # moving average window (samples)

# ================== I18N ==================
TEXTS = {
    "English": {
        "about_title": "About Raha MS",
        "login_title": "Login / Register",
        "username": "Username",
        "password": "Password",
        "login": "Login",
        "register": "Register",
        "temp_monitor": "Heat Safety Monitor",
        "planner": "Planner & Tips",
        "journal": "Journal",
        "assistant": "AI Companion",
        "logout": "Logout",

        "risk_dashboard": "Heat Safety Monitor",
        "enter_temp": "Enter your body temperature (°C):",
        "city": "City (City,CC)",
        "quick_pick": "Quick pick (GCC):",

        "did_today": "Today I did / experienced:",
        "symptoms_today": "Symptoms today:",
        "check_risk": "Check My Heat Risk",
        "personal_baseline": "My usual/normal body temperature (°C):",
        "fasting_today": "Fasting today?",
        "ai_advice_btn": "Get AI Advice",
        "journal_title": "Journal",
        "journal_hint": "Write brief notes. Separate blocks with line breaks.",
        "save": "Save",
        "login_first": "Please login first.",
        "logged_in": "✅ Logged in!",
        "bad_creds": "❌ Invalid credentials",
        "account_created": "✅ Account created! Please login.",
        "user_exists": "❌ Username already exists",
        "logged_out": "✅ Logged out!",
        "weather_fail": "Weather lookup failed",
        "ai_unavailable": "AI is unavailable. Set OPENAI_API_KEY in secrets.",

        # New strings
        "settings": "Settings",
        "baseline_setting": "Baseline body temperature (°C)",
        "use_temp_baseline": "Use this baseline for monitoring",
        "contacts": "Emergency Contacts",
        "primary_phone": "Primary phone",
        "secondary_phone": "Secondary phone",
        "save_settings": "Save settings",
        "saved": "Saved",
        "monitor_now": "Start monitoring",
        "stop": "Stop",
        "reset": "Reset session",
        "sensor_update": "Sensor/sample update (sec)",
        "status": "Status",
        "peak_heat": "Peak heat next 48h",
        "quick_tips": "Quick tips",
        "other": "Other",
        "notes": "Notes",
        "save_entry": "Save to Journal",
        "log_now": "Log what happened?",
        "other_activity": "Other activity (optional)",
        "add_to_journal": "Add to Journal",
        "what_if_tips": "Add your own notes for this plan (optional)",
        "ask_ai_tips": "Ask AI for tailored tips",
        "ai_prompt_hint": "Ask something…",
        "assistant_title": "Your AI Companion",
        "assistant_hint": "I can help with cooling, pacing, planning around prayer/fasting, and more."
    },
    "Arabic": {
        "about_title": "عن تطبيق راحة إم إس",
        "login_title": "تسجيل الدخول / إنشاء حساب",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "login": "تسجيل الدخول",
        "register": "إنشاء حساب",
        "temp_monitor": "مراقبة السلامة الحرارية",
        "planner": "المخطط والنصائح",
        "journal": "اليوميات",
        "assistant": "المساعد الذكي",
        "logout": "تسجيل الخروج",

        "risk_dashboard": "مراقبة السلامة الحرارية",
        "enter_temp": "أدخل حرارة جسمك (°م):",
        "city": "المدينة (City,CC)",
        "quick_pick": "اختيار سريع (الخليج):",

        "did_today": "اليوم قمتُ بـ / تعرضتُ لـ:",
        "symptoms_today": "الأعراض اليوم:",
        "check_risk": "تحقق من خطري الحراري",
        "personal_baseline": "حرارتي المعتادة (°م):",
        "fasting_today": "صائم اليوم؟",
        "ai_advice_btn": "الحصول على نصيحة ذكية",
        "journal_title": "اليوميات",
        "journal_hint": "اكتب ملاحظات قصيرة. افصل بين المقاطع بسطر جديد.",
        "save": "حفظ",
        "login_first": "يرجى تسجيل الدخول أولاً.",
        "logged_in": "✅ تم تسجيل الدخول",
        "bad_creds": "❌ بيانات غير صحيحة",
        "account_created": "✅ تم إنشاء الحساب! الرجاء تسجيل الدخول.",
        "user_exists": "❌ اسم المستخدم موجود",
        "logged_out": "✅ تم تسجيل الخروج!",
        "weather_fail": "فشل جلب الطقس",
        "ai_unavailable": "الخدمة الذكية غير متاحة. أضف مفتاح OPENAI_API_KEY.",

        "settings": "الإعدادات",
        "baseline_setting": "درجة حرارة الجسم الأساسية (°م)",
        "use_temp_baseline": "استخدام هذه القيمة للمراقبة",
        "contacts": "جهات اتصال الطوارئ",
        "primary_phone": "الهاتف الأساسي",
        "secondary_phone": "هاتف إضافي",
        "save_settings": "حفظ الإعدادات",
        "saved": "تم الحفظ",
        "monitor_now": "ابدأ المراقبة",
        "stop": "إيقاف",
        "reset": "إعادة تعيين",
        "sensor_update": "تحديث العينة (ثانية)",
        "status": "الحالة",
        "peak_heat": "ذروة الحر خلال 48 ساعة",
        "quick_tips": "نصائح سريعة",
        "other": "أخرى",
        "notes": "ملاحظات",
        "save_entry": "حفظ في اليوميات",
        "log_now": "تسجيل ما حدث؟",
        "other_activity": "نشاط آخر (اختياري)",
        "add_to_journal": "أضف إلى اليوميات",
        "what_if_tips": "أضف ملاحظاتك لهذا التخطيط (اختياري)",
        "ask_ai_tips": "اسأل الذكاء عن نصائح مخصصة",
        "ai_prompt_hint": "اسأل شيئًا…",
        "assistant_title": "مرافقك الذكي",
        "assistant_hint": "يمكنني المساعدة في التبريد والتنظيم والتخطيط حول الصلاة/الصيام وغير ذلك."
    }
}

# Comprehensive lists (editable later)
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

# ================== STYLES (accessibility) ==================
ACCESSIBLE_CSS = """
<style>
html, body, [class*="css"]  { font-size: 18px; }
.big-card {background:#fff;padding:18px;border-radius:14px;border-left:10px solid var(--left);box-shadow:0 2px 8px rgba(0,0,0,0.06);}
.badge {display:inline-block;padding:6px 10px;border-radius:999px;border:1px solid rgba(0,0,0,0.1);margin-right:6px;}
.small {opacity:0.75;font-size:14px;}
h3 { margin-top: 0.2rem; }
.stButton>button { padding: 0.6rem 1.1rem; font-weight: 600; }
.fab-call {
  position: fixed; right: 18px; bottom: 18px; z-index: 9999;
  background: #ef4444; color: white; border-radius: 9999px;
  padding: 14px 18px; font-weight: 700; box-shadow:0 8px 24px rgba(0,0,0,0.18); text-decoration: none;
}
.fab-call:hover { background:#dc2626; text-decoration:none; }
@media (min-width: 992px) { .fab-call { padding: 10px 14px; font-weight: 600; } }
</style>
"""
st.markdown(ACCESSIBLE_CSS, unsafe_allow_html=True)

# ================== DB ==================
@st.cache_resource
def get_conn():
    return sqlite3.connect("raha_ms.db", check_same_thread=False)

def init_db():
    conn = get_conn(); c = conn.cursor()
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
    conn.commit()

def migrate_db():
    conn = get_conn(); c = conn.cursor()
    c.execute("PRAGMA table_info(temps)")
    cols = [r[1] for r in c.fetchall()]
    if "feels_like" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN feels_like REAL")
    if "humidity" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN humidity REAL")
    conn.commit()

init_db(); migrate_db()

def insert_temp_row(u, dt, body, wtemp, feels, hum, status):
    c = get_conn().cursor()
    c.execute("""
      INSERT INTO temps (username, date, body_temp, weather_temp, feels_like, humidity, status)
      VALUES (?,?,?,?,?,?,?)
    """, (u, dt, body, wtemp, feels, hum, status))
    get_conn().commit()

def insert_journal(u, dt, entry_obj):
    c = get_conn().cursor()
    c.execute("INSERT INTO journal VALUES (?,?,?)", (u, dt, json.dumps(entry_obj)))
    get_conn().commit()

def utc_iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def dubai_now_str():
    return datetime.now(TZ_DUBAI).strftime("%Y-%m-%d %H:%M")

# ================== WEATHER & GEO ==================
@st.cache_data(ttl=600)
def get_weather(city="Abu Dhabi,AE"):
    """Return current weather + 48h forecast using 'weather' and 'forecast' endpoints."""
    if not OPENWEATHER_API_KEY:
        return None, "Missing OPENWEATHER_API_KEY"
    try:
        base = "https://api.openweathermap.org/data/2.5/"

        params_now = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "en"}
        r_now = requests.get(base + "weather", params=params_now, timeout=6); r_now.raise_for_status()
        jn = r_now.json()
        temp  = float(jn["main"]["temp"])
        feels = float(jn["main"]["feels_like"])
        hum   = float(jn["main"]["humidity"])
        desc  = jn["weather"][0]["description"]

        params_fc = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "en"}
        r_fc = requests.get(base + "forecast", params=params_fc, timeout=8); r_fc.raise_for_status()
        jf = r_fc.json()
        items = jf.get("list", [])[:16]  # next 48h (16 slots × 3h)
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
    """OpenWeather Direct Geocoding."""
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
    "Exercise": 2, "Sauna": 3, "Spicy food": 1, "Hot drinks": 1,
    "Stress/Anxiety": 1, "Direct sun exposure": 2, "Fever/Illness": 3, "Hormonal cycle": 1,
    "Tight clothing": 1, "Poor sleep": 1, "Dehydration": 2, "Crowded place": 1,
    "Cooking heat": 1, "Car without AC": 2, "Outdoor work": 2, "Long prayer standing": 1
}
SYMPTOM_WEIGHT = 0.5  # per symptom

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

# ================== Live helpers (simulation) ==================
def moving_avg(seq, n):
    if not seq: return 0.0
    if len(seq) < n: return round(sum(seq)/len(seq), 2)
    return round(sum(seq[-n:]) / n, 2)

def should_alert(temp_series, baseline, delta=ALERT_DELTA_C, confirm=ALERT_CONFIRM):
    if len(temp_series) < confirm:
        return False
    recent = temp_series[-confirm:]
    return all((t - baseline) >= delta for t in recent)

def simulate_next(prev):
    drift = random.uniform(-0.05, 0.08)                # small natural noise
    surge = random.uniform(0.2, 0.5) if random.random() < 0.12 else 0.0  # sporadic uptick
    next_t = prev + drift + surge
    return max(35.5, min(41.0, round(next_t, 2)))

# ================== AI ==================
def ai_response(prompt, lang):
    sys_prompt = (
        "You are Raha MS AI Companion. Provide culturally relevant, practical MS heat safety advice for Gulf (GCC) users. "
        "Use calm language and short bullet points. Consider fasting, prayer times, home AC use, cooling garments, and pacing. "
        "This is general education, not medical care."
    )
    sys_prompt += " Respond only in Arabic." if lang == "Arabic" else " Respond only in English."
    if not client:
        return None, "no_key"
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": sys_prompt},
                      {"role": "user", "content": prompt}],
            temperature=0.6,
        )
        return response.choices[0].message.content, None
    except Exception as e:
        return None, str(e)

# ================== ABOUT PAGE ==================
def render_about_page(lang: str = "English"):
    if lang == "English":
        st.title("🧠 Welcome to Raha MS")
        st.markdown("""
Living with **Multiple Sclerosis (MS)** in the GCC can be uniquely challenging due to heat and humidity.  
Raha MS was designed **with and for people living with MS** — to bring comfort, awareness, and support to your daily life.

**🌡️ Why heat matters**  
Even a small rise in body temperature can temporarily worsen MS symptoms (**Uhthoff’s phenomenon**). Cooling and pacing help.

**✨ What you can do here**  
- **Track** your body temperature and local weather  
- **Spot triggers** (exercise, sun, sauna…)  
- **Journal** symptoms & patterns  
- **Get tips** from the AI Companion  

**🔒 Privacy**  
Your data stays on this device (SQLite). This is a prototype for co-design with the GCC MS community.
""")
    else:
        st.title("🧠 مرحبًا بك في راحة إم إس")
        st.markdown("""
إن العيش مع **التصلب المتعدد (MS)** في الخليج قد يكون صعبًا بسبب الحرارة والرطوبة.  
تم تصميم راحة إم إس **بالتعاون مع مرضى التصلب المتعدد** ليمنحك راحة ووعيًا ودعمًا في حياتك اليومية.

**🌡️ لماذا تؤثر الحرارة؟**  
حتى الارتفاع البسيط في حرارة الجسم قد يزيد الأعراض مؤقتًا (**ظاهرة أوتهوف**). التبريد والتنظيم يساعدان.

**✨ ما الذي يقدمه التطبيق؟**  
- **متابعة** حرارة الجسم والطقس  
- **تحديد المحفزات** (رياضة، شمس، ساونا…)  
- **كتابة اليوميات** والأعراض  
- **الحصول على نصائح** من المساعد الذكي  

**🔒 الخصوصية**  
تبقى بياناتك على هذا الجهاز (SQLite). هذا نموذج أولي للتصميم المشترك مع مجتمع مرضى التصلب في الخليج.
""")

# ================== PLANNER HELPERS ==================
from datetime import datetime as _dt

def best_windows_from_forecast(
    forecast, window_hours=2, top_k=8, max_feels_like=35.0, max_humidity=65, avoid_hours=(10,16)
):
    """
    Returns a list of windows with parsed start_dt/end_dt for robust sorting.
    Each item: {start_dt, end_dt, avg_feels, avg_hum}
    """
    slots = []
    for it in forecast[:16]:
        t = it["time"]  # 'YYYY-MM-DD HH:MM:SS'
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
        if len(group) > 1:
            end_raw = group[-1]["time"][:16]
            end_dt = _dt.strptime(end_raw, "%Y-%m-%d %H:%M") + timedelta(hours=3)
        else:
            end_dt = start_dt + timedelta(hours=3)

        cand.append({
            "start_dt": start_dt,
            "end_dt": end_dt,
            "avg_feels": avg_feels,
            "avg_hum": avg_hum
        })

    cand.sort(key=lambda x: x["start_dt"])
    return cand[:top_k]

def tailored_tips(reasons, feels_like, humidity, delta, lang="English"):
    """Simple tailored tips block."""
    do_now, plan_later, watch_for = [], [], []
    # general
    if delta >= 0.5:
        do_now += ["Cool down (AC/cool shower)", "Sip cool water", "Rest 15–20 min"]
    if feels_like >= 36:
        do_now += ["Use cooling scarf/pack", "Stay in shade/indoors"]
        plan_later += ["Shift activity to cooler window"]
    if humidity >= 60:
        plan_later += ["Prefer AC over fan", "Add electrolytes if sweating"]
    for r in reasons:
        rl = r.lower()
        if "exercise" in rl:
            do_now += ["Stop/pause activity", "Pre-cool next time 15 min"]
            plan_later += ["Shorter intervals, more breaks"]
        if "sun" in rl:
            do_now += ["Move to shade/indoors"]
        if "sauna" in rl or "hot bath" in rl:
            do_now += ["Cool shower afterwards", "Avoid for now"]
        if "car" in rl:
            do_now += ["Pre-cool car 5–10 min"]
        if "kitchen" in rl or "cooking" in rl:
            plan_later += ["Ventilate kitchen, cook earlier"]
        if "fever" in rl or "illness" in rl:
            watch_for += ["Persistent high temp", "New neuro symptoms"]
    # de-dup + limits
    do_now = list(dict.fromkeys(do_now))[:6]
    plan_later = list(dict.fromkeys(plan_later))[:6]
    watch_for = list(dict.fromkeys(watch_for))[:6]
    return do_now, plan_later, watch_for

# ================== SIDEBAR ==================
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/6512b826bd06f692ad81f896773b44a3b0482001/logo1.png"
st.sidebar.image(logo_url, use_container_width=True)

app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English", "Arabic"])
T = TEXTS[app_language]

# RTL for Arabic
if app_language == "Arabic":
    st.markdown("""
    <style>
    body, .block-container { direction: rtl; text-align: right; }
    [data-testid="stSidebar"] { direction: rtl; text-align: right; }
    </style>
    """, unsafe_allow_html=True)

# Sidebar: Settings & Contacts
with st.sidebar.expander(T["settings"], expanded=True):
    st.session_state.setdefault("baseline", 37.0)
    st.session_state.setdefault("use_temp_baseline", True)

    base = st.number_input(T["baseline_setting"], 35.5, 38.5, float(st.session_state["baseline"]), step=0.1, key="baseline_setting_input")
    useb = st.checkbox(T["use_temp_baseline"], value=st.session_state["use_temp_baseline"])
    if st.button(T["save_settings"], key="save_settings_btn"):
        st.session_state["baseline"] = float(base)
        st.session_state["use_temp_baseline"] = bool(useb)
        st.success(T["saved"])

with st.sidebar.expander(T["contacts"], expanded=False):
    st.session_state.setdefault("primary_phone", "")
    st.session_state.setdefault("secondary_phone", "")
    p1 = st.text_input(T["primary_phone"], st.session_state["primary_phone"])
    p2 = st.text_input(T["secondary_phone"], st.session_state["secondary_phone"])
    if st.button(T["save_settings"], key="save_contacts_btn"):
        st.session_state["primary_phone"] = p1.strip()
        st.session_state["secondary_phone"] = p2.strip()
        st.success(T["saved"])

# Floating emergency button (optional)
call_number = st.session_state.get("primary_phone") or st.session_state.get("secondary_phone")
if call_number:
    emergency_label = "اتصال طوارئ" if app_language == "Arabic" else "Emergency Call"
    st.markdown(f'<a class="fab-call" href="tel:{call_number}">📞 {emergency_label}</a>', unsafe_allow_html=True)

# Navigation
page = st.sidebar.radio("Navigate", [
    T["about_title"], T["login_title"], T["temp_monitor"], T["planner"], T["journal"], T["assistant"], T["logout"]
])

# ================== PAGES ==================
# ABOUT
if page == T["about_title"]:
    render_about_page(app_language)

# LOGIN
elif page == T["login_title"]:
    st.title(T["login_title"])
    username = st.text_input(T["username"])
    password = st.text_input(T["password"], type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button(T["login"]):
            c = get_conn().cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            if c.fetchone():
                st.session_state["user"] = username
                st.success(T["logged_in"])
            else:
                st.error(T["bad_creds"])
    with col2:
        if st.button(T["register"]):
            try:
                c = get_conn().cursor()
                c.execute("INSERT INTO users VALUES (?,?)", (username, password))
                get_conn().commit()
                st.success(T["account_created"])
            except Exception:
                st.error(T["user_exists"])
    st.caption("⚠️ Prototype note: passwords are stored in plain text. For a pilot, switch to a hashed scheme (bcrypt/PBKDF2).")

# HEAT MONITOR (continuous)
elif page == T["temp_monitor"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("☀️ " + T["risk_dashboard"])
        st.write(f"**{T['status']}** — {dubai_now_str()} (Dubai time)")

        # Session defaults
        st.session_state.setdefault("live_running", False)
        st.session_state.setdefault("live_smoothed", [])
        st.session_state.setdefault("live_raw", [])
        st.session_state.setdefault("live_tick", 0)
        st.session_state.setdefault("last_db_write_tick", -999)
        st.session_state.setdefault("last_alert_ts", 0.0)
        st.session_state.setdefault("_last_tick_ts", 0.0)

        colA, colB, colC = st.columns([1.2, 1, 1])
        with colA:
            city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0, key="monitor_city")
        with colB:
            interval = st.slider("⏱️ " + T["sensor_update"], 10, 120, SIM_INTERVAL_SEC, 5, key="interval_slider")
        with colC:
            if not st.session_state["live_running"] and st.button("▶️ " + T["monitor_now"], use_container_width=True):
                st.session_state["live_running"] = True
                start = round(st.session_state["baseline"] + random.uniform(-0.2, 0.2), 2)
                st.session_state["live_smoothed"] = [start]
                st.session_state["live_raw"] = [start]
                st.session_state["live_tick"] = 0
                st.session_state["last_db_write_tick"] = -999
                st.session_state["last_alert_ts"] = 0.0
                st.session_state["_last_tick_ts"] = 0.0
                st.rerun()
            if st.session_state["live_running"] and st.button("⏸️ " + T["stop"], use_container_width=True):
                st.session_state["live_running"] = False
                st.rerun()
            if st.button("🔁 " + T["reset"], use_container_width=True):
                st.session_state["live_smoothed"] = []
                st.session_state["live_raw"] = []
                st.session_state["live_tick"] = 0
                st.session_state["last_db_write_tick"] = -999
                st.session_state["last_alert_ts"] = 0.0

        weather, err = get_weather(city)
        if weather is None:
            st.error(f"{T['weather_fail']}: {err}")
        else:
            # Live tick
            now = time.time()
            last_tick_ts = st.session_state.get("_last_tick_ts", 0.0)
            if st.session_state["live_running"] and (now - last_tick_ts) >= st.session_state["interval_slider"]:
                st.session_state["_last_tick_ts"] = now
                prev = st.session_state["live_raw"][-1] if st.session_state["live_raw"] else st.session_state["baseline"]
                raw = simulate_next(prev)
                st.session_state["live_raw"].append(raw)
                smoothed = moving_avg(st.session_state["live_raw"], SMOOTH_WINDOW)
                st.session_state["live_smoothed"].append(smoothed)
                st.session_state["live_tick"] += 1

                # Risk update
                latest_body = smoothed
                risk = compute_risk(weather["feels_like"], weather["humidity"],
                                    latest_body, st.session_state["baseline"], [], [])
                st.session_state["last_check"] = {
                    "city": city, "body_temp": latest_body, "baseline": st.session_state["baseline"],
                    "weather_temp": weather["temp"], "feels_like": weather["feels_like"],
                    "humidity": weather["humidity"], "weather_desc": weather["desc"],
                    "status": risk["status"], "color": risk["color"], "icon": risk["icon"],
                    "advice": risk["advice"], "triggers": [], "symptoms": [],
                    "peak_hours": weather["peak_hours"], "forecast": weather["forecast"],
                    "time": utc_iso_now()
                }

                # Alert condition: baseline+0.5°C for 2 samples, cooldown 5 min
                if should_alert(st.session_state["live_smoothed"], st.session_state["baseline"], ALERT_DELTA_C, ALERT_CONFIRM):
                    if (now - st.session_state["last_alert_ts"]) >= ALERT_COOLDOWN_SEC:
                        st.session_state["last_alert_ts"] = now
                        st.warning("⚠️ Temperature has risen ≥ 0.5°C above your baseline. Consider cooling and rest.")

                # DB write every Nth sample
                if st.session_state["live_tick"] - st.session_state["last_db_write_tick"] >= DB_WRITE_EVERY_N:
                    try:
                        insert_temp_row(
                            st.session_state.get("user", "guest"), dubai_now_str(),
                            latest_body, weather["temp"], weather["feels_like"], weather["humidity"], risk["status"]
                        )
                        st.session_state["last_db_write_tick"] = st.session_state["live_tick"]
                    except Exception as e:
                        st.warning(f"Could not save to DB: {e}")

                st.rerun()

            # Results card
            if st.session_state.get("last_check"):
                last = st.session_state["last_check"]
                left_color = last["color"]
                st.markdown(f"""
<div class="big-card" style="--left:{left_color}">
  <h3>{last['icon']} <strong>Status: {last['status']}</strong></h3>
  <p style="margin:6px 0 0 0">{last['advice']}</p>
  <div class="small" style="margin-top:8px">
    <span class="badge">Weather: {last['city']}</span>
    <span class="badge">Feels-like: {round(last['feels_like'],1)}°C</span>
    <span class="badge">Humidity: {int(last['humidity'])}%</span>
    <span class="badge">Body: {round(last['body_temp'],1)}°C</span>
    <span class="badge">Baseline: {round(last['baseline'],1)}°C</span>
  </div>
  <p class="small" style="margin-top:6px"><strong>{T['peak_heat']}:</strong> {("; ".join(last['peak_hours'])) if last.get('peak_hours') else "—"}</p>
</div>
""", unsafe_allow_html=True)

            # Log reason form when above threshold (robust save)
            if st.session_state["live_smoothed"]:
                latest = st.session_state["live_smoothed"][-1]
                delta = latest - st.session_state["baseline"]
                if delta >= ALERT_DELTA_C:
                    st.markdown(f"### {T['log_now']}")
                    with st.form("log_reason_form", clear_on_submit=True):
                        trigger_options = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
                        chosen = st.multiselect(T["did_today"], trigger_options, max_selections=6)
                        other_text = st.text_input(T["other"], "")
                        symptoms_list = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
                        selected_symptoms = st.multiselect(T["symptoms_today"], symptoms_list)
                        note_text = st.text_input(T["notes"], "")

                        has_reason = (len(chosen) > 0) or (other_text.strip() != "")
                        if has_reason and st.session_state.get("last_check"):
                            do_now, plan_later, watch_for = tailored_tips(
                                chosen + ([other_text] if other_text.strip() else []),
                                st.session_state["last_check"]["feels_like"],
                                st.session_state["last_check"]["humidity"],
                                delta, app_language
                            )
                            with st.expander("🧊 Instant tips", expanded=False):
                                st.write("**Do now**")
                                st.write("- " + "\n- ".join(do_now) if do_now else "—")
                                st.write("**Plan later**")
                                st.write("- " + "\n- ".join(plan_later) if plan_later else "—")
                                st.write("**Watch for**")
                                st.write("- " + "\n- ".join(watch_for) if watch_for else "—")

                        submitted = st.form_submit_button(T["save_entry"])

                    if submitted:
                        # pause live so we don't race with reruns
                        st.session_state["live_running"] = False
                        entry = {
                            "type":"ALERT",
                            "at": utc_iso_now(),
                            "body_temp": round(latest,1),
                            "baseline": round(st.session_state["baseline"],1),
                            "reasons": chosen + ([f"Other: {other_text.strip()}"] if other_text.strip() else []),
                            "symptoms": selected_symptoms,
                            "note": note_text.strip()
                        }
                        try:
                            insert_journal(st.session_state.get("user","guest"), utc_iso_now(), entry)
                            st.success(T["saved"])
                        except Exception as e:
                            st.warning(f"Could not save note: {e}")

            # Temperature Chart (only here)
            st.markdown("---")
            st.subheader("📈 Temperature Trend")
            c = get_conn().cursor()
            try:
                query = "SELECT date, body_temp, weather_temp, feels_like, status FROM temps WHERE username=? ORDER BY date DESC LIMIT 60"
                c.execute(query, (st.session_state.get("user","guest"),))
                rows = c.fetchall()
                if rows:
                    rows = rows[::-1]
                    dates = [r[0] for r in rows]
                    bt = [r[1] for r in rows]
                    ft = [(r[3] if r[3] is not None else r[2]) for r in rows]
                    status_colors = ["green" if r[4]=="Safe" else "orange" if r[4] in ("Caution","High") else "red" for r in rows]

                    fig, ax = plt.subplots(figsize=(10,4))
                    ax.plot(range(len(dates)), bt, marker='o', label="Body Temp", linewidth=2)
                    ax.plot(range(len(dates)), ft, marker='s', label="Feels-like", linewidth=2)
                    for i, color in enumerate(status_colors):
                        ax.scatter(i, bt[i], s=100, edgecolor="black", zorder=5)
                    ax.set_xticks(range(len(dates)))
                    # Display Dubai local minute precision
                    ax.set_xticklabels([d[5:16] for d in dates], rotation=45, fontsize=9)
                    ax.set_ylabel("°C")
                    ax.legend()
                    ax.grid(True, alpha=0.3)
                    ax.set_title("Body vs Feels-like (Dubai time)")
                    st.pyplot(fig)
                else:
                    st.info("No data yet. Start monitoring to build your trend.")
            except Exception as e:
                st.error(f"Chart error: {e}")

# PLANNER
elif page == T["planner"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("🗺️ " + T["planner"])
        city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0, key="planner_city")
        weather, err = get_weather(city)
        if weather is None:
            st.error(f"{T['weather_fail']}: {err}")
        else:
            st.subheader("✅ Recommended cooler windows")
            windows = best_windows_from_forecast(
                weather["forecast"], window_hours=2, top_k=8, max_feels_like=35.0, max_humidity=65
            )

            if not windows:
                st.info("No optimal windows found; consider early morning or after sunset.")
            else:
                by_day = defaultdict(list)
                for w in windows:
                    day_key = w["start_dt"].strftime("%a %d %b")
                    by_day[day_key].append(w)

                for day in sorted(by_day.keys(), key=lambda d: _dt.strptime(d, "%a %d %b")):
                    st.markdown(f"#### {day}")
                    day_windows = by_day[day]
                    cols = st.columns(min(3, len(day_windows)))
                    for i, w in enumerate(day_windows):
                        with cols[i % len(cols)]:
                            st.markdown(f"**{w['start_dt'].strftime('%H:%M')} → {w['end_dt'].strftime('%H:%M')}**")
                            st.caption(f"Feels-like ~{w['avg_feels']}°C • Humidity {w['avg_hum']}%")
                            act = st.selectbox("Plan:", ["Walk","Groceries","Beach","Errand"], key=f"plan_{day}_{i}")
                            other_act = st.text_input(T["other_activity"], key=f"plan_other_{day}_{i}")
                            final_act = other_act.strip() if other_act.strip() else act
                            if st.button(T["add_to_journal"], key=f"add_{day}_{i}"):
                                entry = {
                                    "type":"PLAN", "at": utc_iso_now(),
                                    "city": city,
                                    "start": w["start_dt"].strftime("%Y-%m-%d %H:%M"),
                                    "end": w["end_dt"].strftime("%Y-%m-%d %H:%M"),
                                    "activity": final_act,
                                    "feels_like": w["avg_feels"], "humidity": w["avg_hum"]
                                }
                                insert_journal(st.session_state["user"], utc_iso_now(), entry)
                                st.success("Saved to Journal")

            st.markdown("---")
            st.subheader("🤔 What-if planner")
            act = st.selectbox("Activity type", [
                "Light walk (20–30 min)","Moderate exercise (45 min)","Outdoor errand (30–60 min)","Beach (60–90 min)"
            ], key="what_if")
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
                    st.warning("Couldn't fetch that place's weather.")

            st.caption(f"**{T['peak_heat']}:** " + ("; ".join(weather["peak_hours"]) if weather.get("peak_hours") else "—"))
            with st.expander(T["quick_tips"], expanded=False):
                st.markdown("""- Avoid 10–4 peak heat; use shaded parking.
- Pre-cool before errands; carry cool water.
- Prefer AC indoors; wear light, loose clothing.""")

# JOURNAL
elif page == T["journal"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("📒 " + T["journal_title"])
        st.caption(TEXTS[app_language]["journal_hint"])

        # Add a quick free-form entry
        entry_blocks = st.text_area("✍️", height=140)
        if st.button(TEXTS[app_language]["save"]):
            if entry_blocks.strip():
                entry = {
                    "type": "NOTE",
                    "at": utc_iso_now(),
                    "text": entry_blocks.strip()
                }
                insert_journal(st.session_state["user"], utc_iso_now(), entry)
                st.success("✅ Saved")

        # List entries
        c = get_conn().cursor()
        c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC", (st.session_state["user"],))
        rows = c.fetchall()
        if not rows:
            st.info("No journal entries yet.")
        for r in rows:
            try:
                obj = json.loads(r[1])
            except Exception:
                obj = {"type":"NOTE", "text": r[1]}
            when_local = datetime.fromisoformat(r[0].replace("Z","")).astimezone(TZ_DUBAI) if "Z" in r[0] else datetime.now(TZ_DUBAI)
            st.markdown(f"**{when_local.strftime('%Y-%m-%d %H:%M')}** — {obj.get('type','NOTE')}")
            st.write(obj)

# AI COMPANION
elif page == T["assistant"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("🤖 " + T["assistant_title"])
        st.caption(T["assistant_hint"])

        # Build light context from recent items
        c = get_conn().cursor()
        c.execute("SELECT entry FROM journal WHERE username=? ORDER BY date DESC LIMIT 5", (st.session_state["user"],))
        jr = c.fetchall()
        recent_journal = []
        for (e,) in jr:
            try:
                recent_journal.append(json.loads(e))
            except Exception:
                recent_journal.append({"type":"NOTE","text":e})

        last_check = st.session_state.get("last_check")
        context_blurb = {
            "recent_journal": recent_journal,
            "last_check": last_check
        }

        # Conversation
        st.session_state.setdefault("chat", [])
        # Show conversation
        for m in st.session_state["chat"][-8:]:
            if m["role"] == "user":
                st.markdown(f"**You:** {m['content']}")
            else:
                st.markdown(f"**Assistant:** {m['content']}")

        user_q = st.text_input(T["ai_prompt_hint"], key="assistant_input")
        if user_q:
            st.session_state["chat"].append({"role":"user","content":user_q})
            if client:
                with st.spinner("Thinking…"):
                    prompt = f"""
Context:
{json.dumps(context_blurb, ensure_ascii=False)}

User question:
{user_q}
"""
                    ans, err = ai_response(prompt, app_language)
                    if err:
                        ans = TEXTS[app_language]["ai_unavailable"]
                    st.session_state["chat"].append({"role":"assistant","content":ans})
                st.experimental_rerun()
            else:
                st.warning(TEXTS[app_language]["ai_unavailable"])

        if st.button("🗑️ Clear", type="secondary"):
            st.session_state["chat"] = []
            st.experimental_rerun()

# LOGOUT
elif page == T["logout"]:
    st.session_state.pop("user", None)
    st.success(TEXTS[app_language]["logged_out"])
