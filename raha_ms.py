import streamlit as st
import sqlite3, json, requests, random, time, zipfile, io
import matplotlib.pyplot as plt
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
from datetime import datetime as _dt

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
        "emergency": "Emergency"
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
        "hydration": "ترطيب (أكواب)",
        "sleep": "النوم (ساعات)",
        "fatigue": "التعب",
        "free_note": "ملاحظة حرة (اختياري)",
        "emergency": "الطوارئ"
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
    conn = get_conn(); c = conn.cursor()
    c.execute("PRAGMA table_info(temps)")
    cols = [r[1] for r in c.fetchall()]
    if "peripheral_temp" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN peripheral_temp REAL")
    if "feels_like" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN feels_like REAL")
    if "humidity" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN humidity REAL")
    conn.commit()

init_db(); migrate_db()

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
        r_now = requests.get(base + "weather", params=params_now, timeout=6); r_now.raise_for_status()
        jn = r_now.json()
        temp  = float(jn["main"]["temp"])
        feels = float(jn["main"]["feels_like"])
        hum   = float(jn["main"]["humidity"])
        desc  = jn["weather"][0]["description"]

        params_fc = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "en"}
        r_fc = requests.get(base + "forecast", params=params_fc, timeout=8); r_fc.raise_for_status()
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

# ================== Live helpers ==================
def moving_avg(seq, n):
    if not seq: return 0.0
    if len(seq) < n: return round(sum(seq)/len(seq), 2)
    return round(sum(seq[-n:]) / n, 2)

def should_alert(temp_series, baseline, delta=ALERT_DELTA_C, confirm=ALERT_CONFIRM):
    if len(temp_series) < confirm:
        return False
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

# ================== AI ==================
def ai_response(prompt, lang):
    sys_prompt = (
        "You are Raha MS AI Companion. Answer as a warm, supportive companion. "
        "Provide culturally relevant, practical MS heat safety advice for Gulf (GCC) users. "
        "Use short bullets when listing actions. Consider fasting, prayer times, home AC, cooling garments, pacing. "
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
            temperature=0.7,
        )
        return response.choices[0].message.content, None
    except Exception:
        return None, "err"

# ================== ABOUT (friendly) ==================
def render_about_page(lang: str = "English"):
    if lang == "English":
        st.title("🧠 Welcome to Raha MS")
        st.markdown("""
Living with **Multiple Sclerosis (MS)** in the GCC can be uniquely challenging, especially with the region’s intense heat.  
**Raha MS** was designed **with and for people living with MS** — to bring comfort, awareness, and support to your daily life.
""")
        st.subheader("🌡️ Why Heat Matters in MS")
        st.info("Even a small rise in body temperature (as little as **0.5°C**) can temporarily worsen MS symptoms — this is known as **Uhthoff’s phenomenon**. Cooling and pacing help.")
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
        st.info("حتى الارتفاع البسيط في حرارة الجسم (**0.5°م**) قد يزيد الأعراض مؤقتًا — ويعرف ذلك بـ **ظاهرة أوتهوف**. التبريد والتنظيم يساعدان.")
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

# ================== PLANNER HELPERS ==================
def best_windows_from_forecast(
    forecast, window_hours=2, top_k=8, max_feels_like=35.0, max_humidity=65, avoid_hours=(10,16)
):
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
        end_dt = ( _dt.strptime(group[-1]["time"][:16], "%Y-%m-%d %H:%M") + timedelta(hours=3) ) if len(group)>1 else (start_dt + timedelta(hours=3))

        cand.append({
            "start_dt": start_dt,
            "end_dt": end_dt,
            "avg_feels": avg_feels,
            "avg_hum": avg_hum
        })

    cand.sort(key=lambda x: x["start_dt"])
    return cand[:top_k]

def tailored_tips(reasons, feels_like, humidity, delta, lang="English"):
    do_now, plan_later, watch_for = [], [], []
    if delta >= 0.5:
        do_now += ["Cool down (AC/cool shower)", "Sip cool water", "Rest 15–20 min"]
    if feels_like >= 36:
        do_now += ["Use cooling scarf/pack", "Stay in shade/indoors"]
        plan_later += ["Shift activity to a cooler window"]
    if humidity >= 60:
        plan_later += ["Prefer AC over fan", "Add electrolytes if sweating"]

    for r in reasons:
        rl = r.lower()
        if "exercise" in rl or "رياضة" in rl:
            do_now += ["Stop/pause activity", "Pre-cool next time 15 min"]
            plan_later += ["Shorter intervals, more breaks"]
        if "sun" in rl or "شمس" in rl:
            do_now += ["Move to shade/indoors"]
        if "sauna" in rl or "hot bath" in rl or "ساونا" in rl:
            do_now += ["Cool shower afterwards", "Avoid for now"]
        if "car" in rl or "سيارة" in rl:
            do_now += ["Pre-cool car 5–10 min"]
        if "kitchen" in rl or "cooking" in rl or "مطبخ" in rl:
            plan_later += ["Ventilate kitchen, cook earlier"]
        if "fever" in rl or "illness" in rl or "حمّى" in rl:
            watch_for += ["Persistent high temp", "New neurological symptoms"]

    do_now = list(dict.fromkeys(do_now))[:6]
    plan_later = list(dict.fromkeys(plan_later))[:6]
    watch_for = list(dict.fromkeys(watch_for))[:6]
    return do_now, plan_later, watch_for

# ---------- Journal formatting helpers ----------

TYPE_ICONS_EN = {
    "PLAN": "🗓️", "ALERT": "🚨", "ALERT_AUTO": "🚨", "DAILY": "🧩", "NOTE": "📝"
}
TYPE_ICONS_AR = TYPE_ICONS_EN  # same icons

def _to_dubai_label(iso_str: str) -> str:
    """Safely convert ISO/any stored date to 'YYYY-MM-DD HH:MM' Dubai."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z","+00:00"))
    except Exception:
        try:
            dt = datetime.strptime(iso_str, "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
    return dt.astimezone(TZ_DUBAI).strftime("%Y-%m-%d %H:%M")

def pretty_plan(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    city = entry.get("city", "—")
    act  = entry.get("activity", "—")
    start = entry.get("start", "—")
    end   = entry.get("end", "—")
    fl    = entry.get("feels_like", None)
    hum   = entry.get("humidity", None)
    meta  = f"Feels-like {round(fl,1)}°C • Humidity {int(hum)}%" if (fl is not None and hum is not None) else ""
    if lang == "Arabic":
        header = f"**{when}** — **خطة** ({city})"
        body   = f"**النشاط:** {act}\n\n**الوقت:** {start} → {end}\n\n{meta}"
    else:
        header = f"**{when}** — **Plan** ({city})"
        body   = f"**Activity:** {act}\n\n**Time:** {start} → {end}\n\n{meta}"
    return header, body

def pretty_alert(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    core = entry.get("core_temp") or entry.get("body_temp")
    periph = entry.get("peripheral_temp")
    base = entry.get("baseline")
    delta = (core - base) if (core is not None and base is not None) else None
    reasons = entry.get("reasons", [])
    symptoms = entry.get("symptoms", [])
    note = entry.get("note", "")
    if lang == "Arabic":
        header = f"**{when}** — **تنبيه حراري**"
        lines = []
        if core is not None:   lines.append(f"**الأساسية:** {core}°م")
        if periph is not None: lines.append(f"**الطرفية:** {periph}°م")
        if base is not None:   lines.append(f"**الأساس:** {base}°م")
        if delta is not None:  lines.append(f"**الفرق عن الأساس:** +{round(delta,1)}°م")
        if reasons:            lines.append(f"**الأسباب:** " + ", ".join(reasons))
        if symptoms:           lines.append(f"**الأعراض:** " + ", ".join(symptoms))
        if note:               lines.append(f"**ملاحظة:** {note}")
        body = "\n\n".join(lines)
    else:
        header = f"**{when}** — **Heat alert**"
        lines = []
        if core is not None:   lines.append(f"**Core:** {core}°C")
        if periph is not None: lines.append(f"**Peripheral:** {periph}°C")
        if base is not None:   lines.append(f"**Baseline:** {base}°C")
        if delta is not None:  lines.append(f"**Δ from baseline:** +{round(delta,1)}°C")
        if reasons:            lines.append(f"**Reasons:** " + ", ".join(reasons))
        if symptoms:           lines.append(f"**Symptoms:** " + ", ".join(symptoms))
        if note:               lines.append(f"**Note:** {note}")
        body = "\n\n".join(lines)
    return header, body

# ---------- Journal formatting helpers ----------

TYPE_ICONS_EN = {
    "PLAN": "🗓️", "ALERT": "🚨", "ALERT_AUTO": "🚨", "DAILY": "🧩", "NOTE": "📝"
}
TYPE_ICONS_AR = TYPE_ICONS_EN  # same icons

def _to_dubai_label(iso_str: str) -> str:
    """Safely convert ISO/any stored date to 'YYYY-MM-DD HH:MM' Dubai."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z","+00:00"))
    except Exception:
        try:
            dt = datetime.strptime(iso_str, "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
    return dt.astimezone(TZ_DUBAI).strftime("%Y-%m-%d %H:%M")

def pretty_plan(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    city = entry.get("city", "—")
    act  = entry.get("activity", "—")
    start = entry.get("start", "—")
    end   = entry.get("end", "—")
    fl    = entry.get("feels_like", None)
    hum   = entry.get("humidity", None)
    meta  = f"Feels-like {round(fl,1)}°C • Humidity {int(hum)}%" if (fl is not None and hum is not None) else ""
    if lang == "Arabic":
        header = f"**{when}** — **خطة** ({city})"
        body   = f"**النشاط:** {act}\n\n**الوقت:** {start} → {end}\n\n{meta}"
    else:
        header = f"**{when}** — **Plan** ({city})"
        body   = f"**Activity:** {act}\n\n**Time:** {start} → {end}\n\n{meta}"
    return header, body

def pretty_alert(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    core = entry.get("core_temp") or entry.get("body_temp")
    periph = entry.get("peripheral_temp")
    base = entry.get("baseline")
    delta = (core - base) if (core is not None and base is not None) else None
    reasons = entry.get("reasons", [])
    symptoms = entry.get("symptoms", [])
    note = entry.get("note", "")
    if lang == "Arabic":
        header = f"**{when}** — **تنبيه حراري**"
        lines = []
        if core is not None:   lines.append(f"**الأساسية:** {core}°م")
        if periph is not None: lines.append(f"**الطرفية:** {periph}°م")
        if base is not None:   lines.append(f"**الأساس:** {base}°م")
        if delta is not None:  lines.append(f"**الفرق عن الأساس:** +{round(delta,1)}°م")
        if reasons:            lines.append(f"**الأسباب:** " + ", ".join(reasons))
        if symptoms:           lines.append(f"**الأعراض:** " + ", ".join(symptoms))
        if note:               lines.append(f"**ملاحظة:** {note}")
        body = "\n\n".join(lines)
    else:
        header = f"**{when}** — **Heat alert**"
        lines = []
        if core is not None:   lines.append(f"**Core:** {core}°C")
        if periph is not None: lines.append(f"**Peripheral:** {periph}°C")
        if base is not None:   lines.append(f"**Baseline:** {base}°C")
        if delta is not None:  lines.append(f"**Δ from baseline:** +{round(delta,1)}°C")
        if reasons:            lines.append(f"**Reasons:** " + ", ".join(reasons))
        if symptoms:           lines.append(f"**Symptoms:** " + ", ".join(symptoms))
        if note:               lines.append(f"**Note:** {note}")
        body = "\n\n".join(lines)
    return header, body

def pretty_daily(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    mood = entry.get("mood", "—")
    hyd  = entry.get("hydration_glasses", "—")
    sleep = entry.get("sleep_hours", "—")
    fatigue = entry.get("fatigue", "—")
    triggers = entry.get("triggers", [])
    symptoms = entry.get("symptoms", [])
    note = entry.get("note", "")
    if lang == "Arabic":
        header = f"**{when}** — **مُسجّل يومي**"
        lines = [
            f"**المزاج:** {mood}",
            f"**الترطيب (أكواب):** {hyd}",
            f"**النوم (ساعات):** {sleep}",
            f"**التعب:** {fatigue}",
        ]
        if triggers: lines.append(f"**المحفزات:** " + ", ".join(triggers))
        if symptoms: lines.append(f"**الأعراض:** " + ", ".join(symptoms))
        if note:     lines.append(f"**ملاحظة:** {note}")
        body = "\n\n".join(lines)
    else:
        header = f"**{when}** — **Daily log**"
        lines = [
            f"**Mood:** {mood}",
            f"**Hydration (glasses):** {hyd}",
            f"**Sleep (hrs):** {sleep}",
            f"**Fatigue:** {fatigue}",
        ]
        if triggers: lines.append(f"**Triggers:** " + ", ".join(triggers))
        if symptoms: lines.append(f"**Symptoms:** " + ", ".join(symptoms))
        if note:     lines.append(f"**Note:** {note}")
        body = "\n\n".join(lines)
    return header, body

def pretty_note(entry, lang="English"):
    when = _to_dubai_label(entry.get("at", utc_iso_now()))
    text = entry.get("text") or entry.get("note") or "—"
    if lang == "Arabic":
        header = f"**{when}** — **ملاحظة**"
        body   = text
    else:
        header = f"**{when}** — **Note**"
        body   = text
    return header, body

def render_entry_card(raw_entry_json, lang="English"):
    """Return (title_line, body_md, icon, type_label, raw_obj)."""
    try:
        obj = json.loads(raw_entry_json)
    except Exception:
        # Plain text fallback
        obj = {"type":"NOTE", "at": utc_iso_now(), "text": raw_entry_json}

    t = obj.get("type", "NOTE")
    icon = (TYPE_ICONS_AR if lang=="Arabic" else TYPE_ICONS_EN).get(t, "📝")

    # route to pretty maker
    if t == "PLAN":
        header, body = pretty_plan(obj, lang)
    elif t in ("ALERT","ALERT_AUTO"):
        header, body = pretty_alert(obj, lang)
    elif t == "DAILY":
        header, body = pretty_daily(obj, lang)
    else:
        header, body = pretty_note(obj, lang)

    return header, body, icon, t, obj


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

# Login/Register + Logout (expander)
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
with st.sidebar.expander("🚑 " + T["emergency"], expanded=False):
    st.session_state.setdefault("primary_phone", "")
    st.session_state.setdefault("secondary_phone", "")
    if st.session_state["primary_phone"]:
        st.markdown(f"**Primary:** [{st.session_state['primary_phone']}](tel:{st.session_state['primary_phone']})")
    if st.session_state["secondary_phone"]:
        st.markdown(f"**Secondary:** [{st.session_state['secondary_phone']}](tel:{st.session_state['secondary_phone']})")
    if not (st.session_state["primary_phone"] or st.session_state["secondary_phone"]):
        st.caption("Set numbers in Settings to enable quick call.")

# Floating emergency call button (if any number set)
call_number = st.session_state.get("primary_phone") or st.session_state.get("secondary_phone")
if call_number:
    emergency_label = "اتصال طوارئ" if app_language == "Arabic" else "Emergency Call"
    st.markdown(f'<a class="fab-call" href="tel:{call_number}">📞 {emergency_label}</a>', unsafe_allow_html=True)

# Navigation (added Exports)
page = st.sidebar.radio(
    "Navigate",
    [T["about_title"], T["temp_monitor"], T["planner"], T["journal"], T["assistant"], T["settings"], T["exports"]]
)

# ================== SETTINGS ==================
def render_settings_page():
    st.title("⚙️ " + T["settings"])
    st.subheader(T["baseline_setting"])
    st.session_state.setdefault("baseline", 37.0)
    st.session_state.setdefault("use_temp_baseline", True)

    base = st.number_input(T["baseline_setting"], 35.5, 38.5, float(st.session_state["baseline"]), step=0.1, key="settings_baseline")
    useb = st.checkbox(T["use_temp_baseline"], value=st.session_state["use_temp_baseline"], key="settings_useb")

    st.subheader(T["contacts"])
    st.session_state.setdefault("primary_phone", "")
    st.session_state.setdefault("secondary_phone", "")
    p1 = st.text_input(T["primary_phone"], st.session_state["primary_phone"], key="settings_p1")
    p2 = st.text_input(T["secondary_phone"], st.session_state["secondary_phone"], key="settings_p2")

    if st.button(T["save_settings"], key="settings_save_btn"):
        st.session_state["baseline"] = float(base)
        st.session_state["use_temp_baseline"] = bool(useb)
        st.session_state["primary_phone"] = p1.strip()
        st.session_state["secondary_phone"] = p2.strip()
        st.success(T["saved"])

    st.caption("ℹ️ Baseline is used by the Heat Safety Monitor to decide when to alert (≥ 0.5°C above your baseline).")
    st.markdown("---")
    if "user" in st.session_state and st.button(T["logout"], type="secondary", key="settings_logout"):
        st.session_state.pop("user", None)
        st.success(T["logged_out"])
        st.rerun()

# ================== PAGES ==================
# ABOUT
if page == T["about_title"]:
    render_about_page(app_language)

# HEAT MONITOR
elif page == T["temp_monitor"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("☀️ " + T["risk_dashboard"])
        st.write(f"**{T['status']}** — {dubai_now_str()} (Dubai time)")

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

        colA, colB, colC = st.columns([1.2, 1, 1])
        with colA:
            city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0, key="monitor_city")
        with colB:
            interval = st.slider("⏱️ " + T["sensor_update"], 10, 120, SIM_INTERVAL_SEC, 5, key="interval_slider")
        with colC:
            if not st.session_state["live_running"] and st.button("▶️ Start monitoring", use_container_width=True):
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
            if st.session_state["live_running"] and st.button("⏸️ Pause", use_container_width=True, key="pause_btn"):
                st.session_state["live_running"] = False
                st.rerun()
            if st.button("🔁 Reset session", use_container_width=True):
                st.session_state["live_core_smoothed"] = []
                st.session_state["live_core_raw"] = []
                st.session_state["live_periph_smoothed"] = []
                st.session_state["live_periph_raw"] = []
                st.session_state["live_tick"] = 0
                st.session_state["last_db_write_tick"] = -999
                st.session_state["last_alert_ts"] = 0.0

        weather, err = get_weather(city)
        if weather is None:
            st.error(f"{T['weather_fail']}: {err}")
        else:
            now = time.time()
            last_tick_ts = st.session_state.get("_last_tick_ts", 0.0)
            if st.session_state["live_running"] and (now - last_tick_ts) >= st.session_state["interval_slider"]:
                st.session_state["_last_tick_ts"] = now

                prev_core = st.session_state["live_core_raw"][-1] if st.session_state["live_core_raw"] else st.session_state["baseline"]
                core_raw = simulate_core_next(prev_core)
                st.session_state["live_core_raw"].append(core_raw)
                core_smoothed = moving_avg(st.session_state["live_core_raw"], SMOOTH_WINDOW)
                st.session_state["live_core_smoothed"].append(core_smoothed)

                prev_periph = st.session_state["live_periph_raw"][-1] if st.session_state["live_periph_raw"] else (core_smoothed - 0.7)
                periph_raw = simulate_peripheral_next(core_smoothed, prev_periph, weather["feels_like"])
                st.session_state["live_periph_raw"].append(periph_raw)
                periph_smoothed = moving_avg(st.session_state["live_periph_raw"], SMOOTH_WINDOW)
                st.session_state["live_periph_smoothed"].append(periph_smoothed)

                st.session_state["live_tick"] += 1

                latest_body = core_smoothed
                risk = compute_risk(weather["feels_like"], weather["humidity"],
                                    latest_body, st.session_state["baseline"], [], [])
                st.session_state["last_check"] = {
                    "city": city,
                    "body_temp": latest_body,
                    "peripheral_temp": periph_smoothed,
                    "baseline": st.session_state["baseline"],
                    "weather_temp": weather["temp"],
                    "feels_like": weather["feels_like"],
                    "humidity": weather["humidity"],
                    "weather_desc": weather["desc"],
                    "status": risk["status"], "color": risk["color"], "icon": risk["icon"],
                    "advice": risk["advice"], "triggers": [], "symptoms": [],
                    "peak_hours": weather["peak_hours"], "forecast": weather["forecast"],
                    "time": utc_iso_now()
                }

                if should_alert(st.session_state["live_core_smoothed"], st.session_state["baseline"], ALERT_DELTA_C, ALERT_CONFIRM):
                    if (now - st.session_state["last_alert_ts"]) >= ALERT_COOLDOWN_SEC:
                        st.session_state["last_alert_ts"] = now
                        st.warning("⚠️ Core temperature has risen ≥ 0.5°C above your baseline. Consider cooling and rest.")

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

            if st.session_state.get("last_check"):
                last = st.session_state["last_check"]
                left_color = last["color"]
                st.markdown(f"""
<div class="big-card" style="--left:{left_color}">
  <h3>{last['icon']} <strong>Status: {last['status']}</strong></h3>
  <p style="margin:6px 0 0 0">{last['advice']}</p>
  <div class="small" style="margin-top:8px">
    <span class="badge">City: {last['city']}</span>
    <span class="badge">Feels-like: {round(last['feels_like'],1)}°C</span>
    <span class="badge">Humidity: {int(last['humidity'])}%</span>
    <span class="badge">Core: {round(last['body_temp'],1)}°C</span>
    <span class="badge">Peripheral: {round(last['peripheral_temp'],1)}°C</span>
    <span class="badge">Baseline: {round(last['baseline'],1)}°C</span>
  </div>
  <p class="small" style="margin-top:6px"><strong>{T['peak_heat']}:</strong> {("; ".join(last['peak_hours'])) if last.get('peak_hours') else "—"}</p>
</div>
""", unsafe_allow_html=True)

            # Log reason only when above threshold
            if st.session_state["live_core_smoothed"]:
                core_latest = st.session_state["live_core_smoothed"][-1]
                delta = core_latest - st.session_state["baseline"]
                if delta >= ALERT_DELTA_C:
                    st.markdown(f"### {T['log_now']}")
                    with st.form("log_reason_form", clear_on_submit=True):
                        trigger_options = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
                        chosen = st.multiselect("Triggers", trigger_options, max_selections=6)
                        other_text = st.text_input(T["other"], "")
                        symptoms_list = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
                        selected_symptoms = st.multiselect("Symptoms", symptoms_list)
                        note_text = st.text_input(T["notes"], "")

                        # Tailored tips preview
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
                        st.session_state["live_running"] = False
                        entry = {
                            "type":"ALERT",
                            "at": utc_iso_now(),
                            "core_temp": round(core_latest,1),
                            "peripheral_temp": round(st.session_state["live_periph_smoothed"][-1],1) if st.session_state["live_periph_smoothed"] else None,
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

            # Trend chart
            st.markdown("---")
            st.subheader("📈 Temperature Trend")
            c = get_conn().cursor()
            try:
                query = """
                    SELECT date, body_temp, peripheral_temp, weather_temp, feels_like, status
                    FROM temps WHERE username=? ORDER BY date DESC LIMIT 60
                """
                c.execute(query, (st.session_state.get("user","guest"),))
                rows = c.fetchall()
                if rows:
                    rows = rows[::-1]
                    dates = [r[0] for r in rows]
                    core = [r[1] for r in rows]
                    periph = [r[2] for r in rows]
                    feels = [(r[4] if r[4] is not None else r[3]) for r in rows]
                    fig, ax = plt.subplots(figsize=(10,4))
                    ax.plot(range(len(dates)), core, marker='o', label="Core", linewidth=2)
                    ax.plot(range(len(dates)), periph, marker='o', label="Peripheral", linewidth=1.8)
                    ax.plot(range(len(dates)), feels, marker='s', label="Feels-like", linewidth=1.8)
                    ax.set_xticks(range(len(dates)))
                    ax.set_xticklabels([d[5:16] for d in dates], rotation=45, fontsize=9)
                    ax.set_ylabel("°C")
                    ax.legend()
                    ax.grid(True, alpha=0.3)
                    ax.set_title("Core vs Peripheral vs Feels-like (Dubai time)")
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
                weather["forecast"], window_hours=2, top_k=12, max_feels_like=35.0, max_humidity=65
            )

            if not windows:
                st.info("No optimal windows found; consider early morning or after sunset.")
            else:
                data = []
                for i, w in enumerate(windows):
                    data.append({
                        "index": i,
                        "Day": w["start_dt"].strftime("%a %d %b"),
                        "Start": w["start_dt"].strftime("%H:%M"),
                        "End": w["end_dt"].strftime("%H:%M"),
                        "Feels-like (°C)": w["avg_feels"],
                        "Humidity (%)": w["avg_hum"]
                    })
                dfw = pd.DataFrame(data)
                st.dataframe(dfw, hide_index=True, use_container_width=True)

                indices = st.multiselect("Select slots to plan", options=list(dfw["index"]), format_func=lambda i: f"{dfw.loc[dfw['index']==i,'Day'].values[0]} {dfw.loc[dfw['index']==i,'Start'].values[0]}–{dfw.loc[dfw['index']==i,'End'].values[0]}")
                plan = st.selectbox("Plan", ["Walk","Groceries","Beach","Errand"])
                other_act = st.text_input(T["other_activity"])
                final_act = other_act.strip() if other_act.strip() else plan

                if st.button(T["add_selected"], disabled=(len(indices)==0)):
                    for i in indices:
                        w = windows[i]
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
                st.info(ans if ans else T["ai_unavailable"])

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
        st.title("📒 " + TEXTS[app_language]["journal"])
        st.caption(TEXTS[app_language]["journal_hint"])

        # --- quick logger (unchanged, keep your existing if you want) ---
        st.markdown("### " + T["daily_logger"])
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            mood = st.selectbox(T["mood"], ["🙂 Okay","😌 Calm","😕 Low","😣 Stressed","😴 Tired"])
        with col2:
            hydration = st.slider(T["hydration"], 0, 12, 6)
        with col3:
            sleep = st.slider(T["sleep"], 0, 12, 7)
        with col4:
            fatigue = st.slider(T["fatigue"], 0, 10, 4)

        trigger_options = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
        chosen_tr = st.multiselect("Triggers (optional)", trigger_options)
        tr_other = st.text_input(T["other"] + " (trigger)", "")
        symptom_options = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
        chosen_sy = st.multiselect("Symptoms (optional)", symptom_options)
        sy_other = st.text_input(T["other"] + " (symptom)", "")

        free_note = st.text_area(T["free_note"], height=100)

        if st.button(T["save_entry"], key="journal_save"):
            entry = {
                "type": "DAILY",
                "at": utc_iso_now(),
                "mood": mood,
                "hydration_glasses": hydration,
                "sleep_hours": sleep,
                "fatigue": fatigue,
                "triggers": chosen_tr + ([f"Other: {tr_other.strip()}"] if tr_other.strip() else []),
                "symptoms": chosen_sy + ([f"Other: {sy_other.strip()}"] if sy_other.strip() else []),
                "note": free_note.strip()
            }
            insert_journal(st.session_state["user"], utc_iso_now(), entry)
            st.success("✅ Saved")

        st.markdown("---")

        # --- filters & listing ---
        # Fetch journal rows
        c = get_conn().cursor()
        c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC", (st.session_state["user"],))
        rows = c.fetchall()

        if not rows:
            st.info("No journal entries yet.")
        else:
            # Filter by type
            available_types = ["PLAN","ALERT","ALERT_AUTO","DAILY","NOTE"]
            type_filter = st.multiselect(
                "Filter by type",
                options=available_types,
                default=["PLAN","ALERT","ALERT_AUTO","DAILY","NOTE"],
                help="Show only selected entry types"
            )

            # Pagination (show N at a time)
            st.session_state.setdefault("journal_offset", 0)
            page_size = 12
            start = st.session_state["journal_offset"]
            end = start + 200  # read a chunk first to group by day
            chunk = rows[start:end]

            # Parse & filter
            parsed = []
            for r in chunk:
                dt_raw, raw_json = r
                title, body, icon, t, obj = render_entry_card(raw_json, app_language)
                # Only include selected types
                if t not in type_filter: 
                    continue
                # day header key
                try:
                    dt = datetime.fromisoformat(dt_raw.replace("Z","+00:00"))
                except Exception:
                    dt = datetime.now(timezone.utc)
                day_key = dt.astimezone(TZ_DUBAI).strftime("%A, %d %B %Y")
                parsed.append((day_key, title, body, icon, obj, raw_json))

            # Group by day and render pretty cards
            current_day = None
            shown = 0
            for day, title, body, icon, obj, raw_json in parsed:
                if shown >= page_size:
                    break
                if day != current_day:
                    st.markdown(f"## {day}")
                    current_day = day
                # Card
                st.markdown(f"""
<div class="big-card" style="--left:#94a3b8;margin-bottom:12px;">
  <h3 style="margin:0">{icon} {title}</h3>
  <div style="margin-top:6px">{body}</div>
</div>
""", unsafe_allow_html=True)
                with st.expander("Details"):
                    st.json(obj)
                shown += 1

            # Pager controls
            colp1, colp2, colp3 = st.columns([1,1,4])
            with colp1:
                if st.session_state["journal_offset"] > 0:
                    if st.button("⬅️ Newer"):
                        st.session_state["journal_offset"] = max(0, st.session_state["journal_offset"] - page_size)
                        st.rerun()
            with colp2:
                if (start + shown) < len(rows):
                    if st.button("Older ➡️"):
                        st.session_state["journal_offset"] += page_size
                        st.rerun()

# AI COMPANION
elif page == T["assistant"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("🤖 " + T["assistant_title"])
        st.caption(T["assistant_hint"])

        # Build light context
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
        context_blurb = {"recent_journal": recent_journal, "last_check": last_check}

        st.session_state.setdefault("chat", [])
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
                    prompt = (
                        "Please respond warmly and practically.\n\n"
                        f"Context JSON:\n{json.dumps(context_blurb, ensure_ascii=False)}\n\n"
                        f"User question:\n{user_q}\n"
                    )
                    ans, err = ai_response(prompt, app_language)
                    if err:
                        ans = T["ai_unavailable"]
                    st.session_state["chat"].append({"role":"assistant","content":ans})
                st.rerun()
            else:
                st.warning(T["ai_unavailable"])

        if st.button("🗑️ Clear", type="secondary"):
            st.session_state["chat"] = []
            st.rerun()

# SETTINGS
elif page == T["settings"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        render_settings_page()

# EXPORTS (new dedicated tab)
elif page == T["exports"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("📦 " + T["export_title"])
        st.caption(T["export_desc"])

        # Build files once for the view
        df_t = fetch_temps_df(st.session_state["user"])
        df_j = fetch_journal_df(st.session_state["user"])

        # Show quick preview
        st.subheader("Preview — Temps")
        st.dataframe(df_t.tail(20), use_container_width=True)
        st.subheader("Preview — Journal")
        st.dataframe(df_j.tail(20), use_container_width=True)

        # Excel or ZIP (auto-fallback)
        blob, mime = build_export_excel_or_zip(st.session_state["user"])
        st.download_button(
            label=T["export_excel"],
            data=blob,
            file_name=f"raha_ms_{st.session_state['user']}.xlsx" if mime.endswith("sheet") else f"raha_ms_{st.session_state['user']}.zip",
            mime=mime,
            use_container_width=True
        )

        # Also offer raw CSVs directly
        st.markdown("— or download raw CSVs —")
        st.download_button(
            "Temps.csv",
            data=df_t.to_csv(index=False).encode("utf-8"),
            file_name="Temps.csv", mime="text/csv",
            use_container_width=True
        )
        st.download_button(
            "Journal.csv",
            data=df_j.to_csv(index=False).encode("utf-8"),
            file_name="Journal.csv", mime="text/csv",
            use_container_width=True
        )
