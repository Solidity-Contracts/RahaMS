import streamlit as st
import sqlite3
from openai import OpenAI
import requests
import matplotlib.pyplot as plt
from datetime import datetime
import time, random
from collections import defaultdict
import json

# ================== CONFIG ==================
st.set_page_config(page_title="Raha MS", page_icon="🌡️", layout="wide")

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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
        "assistant_tab": "AI Assistant",
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
        "ask_anything": "Ask anything:",
        "get_tips": "Get AI tips",
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
        "disclaimer": "Prototype: educational use only. Not medical advice. Data stored locally (SQLite).",
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
        "ask_anything": "اسأل أي شيء:",
        "get_tips": "احصل على نصائح",
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
        "disclaimer": "هذا نموذج أولي للتثقيف فقط وليس نصيحة طبية. البيانات محليًا (SQLite).",
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

init_db()
migrate_db()

# ================== HELPERS: DB OPS ==================
def insert_temp(username, dt, body, weather, feels_like, humidity, status):
    c = get_conn().cursor()
    c.execute("""
        INSERT INTO temps (username, date, body_temp, weather_temp, feels_like, humidity, status)
        VALUES (?,?,?,?,?,?,?)
    """,(username, dt, body, weather, feels_like, humidity, status))
    get_conn().commit()

def insert_journal(username, dt, entry_obj):
    c = get_conn().cursor()
    c.execute("INSERT INTO journal VALUES (?,?,?)", (username, dt, json.dumps(entry_obj, ensure_ascii=False)))
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
        peak_hours = [f'{t["time"][5:16]} (~{round(t["feels_like"])}°C, {int(t["humidity"])}%)' for t in top]

        return {"temp": temp, "feels_like": feels, "humidity": hum, "desc": desc,
                "forecast": forecast, "peak_hours": peak_hours}, None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=600)
def aggregate_week(forecast):
    days = defaultdict(lambda: {"min": 1e9, "max": -1e9, "hums": [], "desc": ""})
    order = []
    for it in forecast:
        day = it["time"][:10]
        if day not in days: order.append(day)
        fl = it["feels_like"]
        days[day]["min"] = min(days[day]["min"], fl)
        if fl > days[day]["max"]:
            days[day]["max"] = fl
            days[day]["desc"] = it["desc"]
        days[day]["hums"].append(it["humidity"])
    out = []
    for d in order[:7]:
        hums = days[d]["hums"]
        out.append({
            "day": d,
            "min": round(days[d]["min"],1) if hums else None,
            "max": round(days[d]["max"],1) if hums else None,
            "humidity": int(sum(hums)/len(hums)) if hums else None,
            "desc": days[d]["desc"]
        })
    return out

@st.cache_data(ttl=600)
def geocode_place(q):
    """Return (name, lat, lon) or (None,None,None)"""
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
    if len(temp_series) < confirm:
        return False
    recent = temp_series[-confirm:]
    return all((t - baseline) >= delta for t in recent)

def simulate_next(prev, baseline):
    drift = random.uniform(-0.05, 0.08)
    surge = random.uniform(0.2, 0.5) if random.random() < 0.12 else 0.0
    next_t = prev + drift + surge
    return max(35.5, min(41.0, round(next_t, 2)))

# Comprehensive lists (EN/AR)
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

def instant_tips(selected_triggers, feels_like, humidity, delta_from_baseline, lang="English"):
    # Simple rule engine → 3 lists
    def L(x): return x if lang=="English" else {
        "Delay + shade":"أجّل واستخدم الظل",
        "Pre-cool + short blocks":"تبريد مسبق + فترات قصيرة",
        "Light/loose clothing":"ملابس خفيفة وفضفاضة",
        "Cold fluids + electrolytes":"سوائل باردة + أملاح",
        "Switch to early/late":"القيام بالنشاط صباحًا/مساءً",
        "Intervals + breaks":"تمارين متقطعة + فواصل راحة",
        "Cooling pack (neck/wrists)":"كمادات تبريد (الرقبة/المعصم)",
        "Prefer AC over fan":"استخدم المكيف بدل المروحة",
        "Reduce indoor exertion":"قلل الجهد داخل المنزل",
        "Smaller meals / avoid hot":"وجبات أصغر / تجنب الحار",
        "Rest; monitor symptoms":"استرح وراقب الأعراض",
        "Red flags: confusion, chest pain, fainting → seek care":"أعراض خطرة: ارتباك، ألم صدري، إغماء → اطلب الرعاية"
    }[x]

    do_now, plan_later, watch_for = [], [], []
    hot = feels_like >= 38
    humid = humidity >= 60

    if any("Direct sun" in t or "شمس" in t for t in selected_triggers) or hot:
        do_now += [L("Delay + shade"), L("Pre-cool + short blocks"), L("Light/loose clothing")]
    if any("Exercise" in t or "تمارين" in t for t in selected_triggers):
        do_now += [L("Switch to early/late"), L("Intervals + breaks"), L("Cold fluids + electrolytes")]
    if humid:
        do_now += [L("Prefer AC over fan")]
        plan_later += [L("Reduce indoor exertion")]
    if any(("Hot" in t or "حار" in t) for t in selected_triggers):
        do_now += [L("Smaller meals / avoid hot")]
    if delta_from_baseline >= 0.5:
        do_now += [L("Cooling pack (neck/wrists)"), L("Rest; monitor symptoms")]
    watch_for = [L("Red flags: confusion, chest pain, fainting → seek care")]
    # De-duplicate keeping order
    def dedup(seq):
        seen=set(); out=[]
        for i in seq:
            if i not in seen:
                seen.add(i); out.append(i)
        return out
    return dedup(do_now)[:5], dedup(plan_later)[:4], dedup(watch_for)

# ================== AI ==================
def ai_response(prompt, lang):
    sys_prompt = ("You are Raha MS AI Companion. Short, practical, culturally aware tips for GCC climate. "
                  "Consider humidity, cooling, hydration, pacing, prayer/errand timing. Not medical care.")
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

def build_context(username):
    rows = get_recent_journal(username, limit=7)
    lines = []
    for d, e in rows[::-1]:
        try:
            obj = json.loads(e)
            t = obj.get("type","NOTE")
            if t=="ALERT":
                lines.append(f"{d[:16]} ALERT: reasons={obj.get('reasons', [])}, note={obj.get('note','')}")
            elif t=="DAILY":
                lines.append(f"{d[:16]} DAILY: mood={obj.get('mood','')}, energy={obj.get('energy','')}, "
                             f"triggers={obj.get('triggers', [])}, symptoms={obj.get('symptoms', [])}")
            else:
                lines.append(f"{d[:16]} NOTE: {e[:120]}")
        except:
            lines.append(f"{d[:16]} RAW: {e[:120]}")
    return "\n".join(lines) if lines else "(no recent journal entries)"

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

# Auth (simple prototype)
with st.sidebar.expander(T["login_title"], expanded=False):
    username = st.text_input(T["username"], key="user_in")
    password = st.text_input(T["password"], type="password", key="pass_in")
    c1, c2 = st.columns(2)
    with c1:
        if st.button(T["login"], key="login_btn"):
            cdb = get_conn().cursor()
            cdb.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            if cdb.fetchone():
                st.session_state["user"] = username
                st.success(T["logged_in"])
            else:
                st.error(T["bad_creds"])
    with c2:
        if st.button(T["register"], key="register_btn"):
            try:
                cdb = get_conn().cursor()
                cdb.execute("INSERT INTO users VALUES (?,?)", (username, password))
                get_conn().commit()
                st.success(T["account_created"])
            except Exception:
                st.error(T["user_exists"])
    if st.button("Logout", key="logout_btn"):
        st.session_state.pop("user", None)
        st.success(T["logged_out"])

# Emergency contact (persistent)
st.sidebar.markdown(f"### 🚑 {T['emergency_title']}")
if "user" in st.session_state:
    pn, pp, sn, sp = get_contacts(st.session_state["user"])
else:
    pn, pp, sn, sp = ("","","","")
pn = st.sidebar.text_input(T["primary_name"], pn, key="pn")
pp = st.sidebar.text_input(T["primary_phone"], pp, key="pp")
sn = st.sidebar.text_input(T["secondary_name"], sn, key="sn")
sp = st.sidebar.text_input(T["secondary_phone"], sp, key="sp")
if "user" in st.session_state and st.sidebar.button(T["save_contacts"]):
    save_contacts(st.session_state["user"], pn, pp, sn, sp)
    st.sidebar.success(T["contacts_saved"])
st.sidebar.caption("• Move to AC • Sip cool water • Use cooling pack • Call local emergency if severe")

# Navigation
page = st.sidebar.radio("Navigate", [
    T["about_title"], T["monitor"], T["planner"], T["journal_tab"], T["assistant_tab"], T["settings"]
])

# ================== PAGES ==================

# TAB 1 — ABOUT
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

        # Small CTA to help new users
        st.link_button("➡️ Start Heat Monitor", "")

    else:  # Arabic
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

        st.link_button("➡️ ابدأ مراقبة الحرارة", "")

# TAB 2 — HEAT MONITOR (live only)
def render_monitor():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    st.title("☀️ " + T["risk_dashboard"])

    # Session defaults
    st.session_state.setdefault("baseline", 37.0)
    st.session_state.setdefault("city", "Abu Dhabi,AE")
    st.session_state.setdefault("live_running", False)
    st.session_state.setdefault("live_raw", [])
    st.session_state.setdefault("live_smoothed", [])
    st.session_state.setdefault("live_tick", 0)
    st.session_state.setdefault("last_db_write_tick", -999)
    st.session_state.setdefault("last_alert_ts", 0.0)
    st.session_state.setdefault("_last_tick_ts", 0.0)
    st.session_state.setdefault("last_check", None)

    colA, colB, colC = st.columns([1.2,1,1])
    st.session_state["baseline"] = colA.number_input("🧭 " + T["personal_baseline"], 35.5, 38.5, st.session_state["baseline"], 0.1)
    st.session_state["city"] = colB.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0)
    interval = colC.slider("⏱️ " + T["update_every"], 2, 20, SIM_INTERVAL_SEC, 1)
    st.caption(T["baseline_hint"])

    weather, err = get_weather(st.session_state["city"])
    if weather is None:
        st.error(f"{T['weather_fail']}: {err}")
        return

    b1, b2, b3 = st.columns([1,1,1])
    with b1:
        if not st.session_state["live_running"] and st.button(T["start"], use_container_width=True):
            st.session_state["live_running"] = True
            start = round(st.session_state["baseline"] + random.uniform(-0.2, 0.2), 2)
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

    # Tick loop
    now = time.time()
    if st.session_state["live_running"] and (now - st.session_state["_last_tick_ts"]) >= interval:
        st.session_state["_last_tick_ts"] = now
        prev = st.session_state["live_raw"][-1] if st.session_state["live_raw"] else st.session_state["baseline"]
        raw = simulate_next(prev, st.session_state["baseline"])
        st.session_state["live_raw"].append(raw)
        smoothed = moving_avg(st.session_state["live_raw"], SMOOTH_WINDOW)
        st.session_state["live_smoothed"].append(smoothed)
        st.session_state["live_tick"] += 1

        risk = compute_risk(weather["feels_like"], weather["humidity"], smoothed, st.session_state["baseline"])
        st.session_state["last_check"] = {
            "city": st.session_state["city"], "body_temp": smoothed, "baseline": st.session_state["baseline"],
            "weather_temp": weather["temp"], "feels_like": weather["feels_like"],
            "humidity": weather["humidity"], "weather_desc": weather["desc"],
            "status": risk["status"], "color": risk["color"], "icon": risk["icon"],
            "advice": risk["advice"], "time": datetime.utcnow().isoformat()
        }

        # Alert logic
        if should_alert(st.session_state["live_smoothed"], st.session_state["baseline"], ALERT_DELTA_C, ALERT_CONFIRM):
            if (now - st.session_state["last_alert_ts"]) >= ALERT_COOLDOWN_SEC:
                st.session_state["last_alert_ts"] = now
                st.warning("⚠️ Rise ≥ 0.5 °C above baseline detected. Consider cooling and rest. See tips below.")

        # DB write every Nth
        if st.session_state["live_tick"] - st.session_state["last_db_write_tick"] >= DB_WRITE_EVERY_N:
            try:
                insert_temp(st.session_state.get("user","guest"), str(datetime.now()),
                            smoothed, weather["temp"], weather["feels_like"], weather["humidity"], risk["status"])
                st.session_state["last_db_write_tick"] = st.session_state["live_tick"]
            except Exception as e:
                st.warning(f"Could not save to DB: {e}")

        st.rerun()

    # Risk card
    if st.session_state["last_check"]:
        last = st.session_state["last_check"]
        left_color = last["color"]
        st.markdown(f"""
<div class="big-card" style="--left:{left_color}">
  <h3>{last['icon']} <strong>Status: {last['status']}</strong></h3>
  <p style="margin:6px 0 0 0">{last['advice']}</p>
  <div class="small" style="margin-top:8px">
    <span class="badge">Feels-like: {round(last['feels_like'],1)}°C</span>
    <span class="badge">Humidity: {int(last['humidity'])}%</span>
    <span class="badge">Body: {round(last['body_temp'],1)}°C</span>
    <span class="badge">Baseline: {round(last['baseline'],1)}°C</span>
    <span class="badge">{T['status_checked']}: {last['time'][:16]}Z</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # If over-threshold, show instant logging + tips
    if st.session_state["live_smoothed"]:
        latest = st.session_state["live_smoothed"][-1]
        delta = latest - st.session_state["baseline"]
        if delta >= ALERT_DELTA_C:
            st.markdown(f"### {T['log_now']}")
            trigger_options = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
            chosen = st.multiselect(T["triggers_today"], trigger_options, max_selections=6)
            other_text = st.text_input(T["other"], "")
            # symptom severity (optional quick)
            symptoms_list = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
            selected_symptoms = st.multiselect(T["symptoms_today"], symptoms_list)
            sev_map = {}
            for s in selected_symptoms:
                sev_map[s] = st.select_slider(s, ["Mild","Moderate","Severe"], value="Moderate", key=f"sev_{s}")

            # Instant tips card
            do_now, plan_later, watch_for = instant_tips(chosen + ([other_text] if other_text.strip() else []),
                                                         weather["feels_like"], weather["humidity"], delta, app_language)
            st.markdown(f"#### 🧊 {T['instant_plan_title']}")
            st.write(f"**{T['do_now']}**")
            st.write("- " + "\n- ".join(do_now))
            st.write(f"**{T['plan_later']}**")
            st.write("- " + "\n- ".join(plan_later))
            st.write(f"**{T['watch_for']}**")
            st.write("- " + "\n- ".join(watch_for))

            note_text = st.text_input(T["notes"], "")
            if st.button(T["save_entry"]):
                entry = {
                    "type":"ALERT",
                    "at": datetime.now().isoformat(),
                    "body_temp": round(latest,1),
                    "baseline": round(st.session_state["baseline"],1),
                    "reasons": chosen + ([f"Other: {other_text.strip()}"] if other_text.strip() else []),
                    "symptom_severity": sev_map,
                    "note": note_text.strip()
                }
                try:
                    insert_journal(st.session_state.get("user","guest"), str(datetime.now()), entry)
                    st.success(T["saved"])
                except Exception as e:
                    st.warning(f"Could not save note: {e}")

    # Live chart
    st.markdown("---")
    st.subheader(T["temp_trend"])
    rows = get_recent_temps(st.session_state.get("user","guest"), limit=50)
    if rows:
        rows = rows[::-1]
        dates = [r[0][5:16] for r in rows]
        bt = [r[1] for r in rows]
        ft = [r[2] for r in rows]
        fig, ax = plt.subplots(figsize=(10,4))
        ax.plot(range(len(dates)), bt, marker='o', label="Body", linewidth=2, color='red')
        ax.plot(range(len(dates)), ft, marker='s', label="Feels-like", linewidth=2)
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, fontsize=9)
        ax.set_ylabel("°C"); ax.legend(); ax.grid(True, alpha=0.3)
        st.pyplot(fig)
    else:
        st.info("No temperature data yet.")

# TAB 3 — PLANNER & FORECAST
def render_planner():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    st.title("🗺️ " + T["planner"])
    col1, col2 = st.columns([1.5,1])
    city = col1.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0, key="planner_city")
    col2.caption("Plan errands for cooler hours.")

    weather, err = get_weather(city)
    if weather is None:
        st.error(f"{T['weather_fail']}: {err}")
        return

    st.subheader(T["weekly_forecast"])
    week = aggregate_week(weather["forecast"])
    cols = st.columns(len(week) if week else 1)
    import datetime as _dt
    for i, d in enumerate(week):
        with cols[i]:
            y,m,dd = map(int, d["day"].split("-"))
            wkday = _dt.date(y,m,dd).strftime("%a") if app_language=="English" else ["الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"][_dt.date(y,m,dd).weekday()]
            st.markdown(f"**{wkday}**")
            st.write(d["desc"].capitalize() if d["desc"] else "")
            st.write(f"↑ {d['max']}°C  ↓ {d['min']}°C")
            st.caption(f"Hum: {d['humidity']}%")

    st.caption(f"**{T['peak_heat']}:** " + ("; ".join(weather["peak_hours"]) if weather.get("peak_hours") else "—"))

    st.subheader(T["quick_tips"])
    st.markdown("""- Avoid 10–4 peak heat; use shaded parking.\n- Pre-cool before errands; carry cool water.\n- Prefer AC indoors; wear light, loose clothing.""")

    st.markdown("---")
    st.subheader("📝 " + T["journal_tab"])
    # Daily quick log
    trigger_options = TRIGGERS_EN if app_language=="English" else TRIGGERS_AR
    day_triggers = st.multiselect(T["triggers_today"], trigger_options)
    other_tr = st.text_input(T["other"], "")
    symptoms_list = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
    day_symptoms = st.multiselect(T["symptoms_today"], symptoms_list)
    sev_map = {}
    for s in day_symptoms:
        sev_map[s] = st.select_slider(s, ["Mild","Moderate","Severe"], value="Moderate", key=f"day_sev_{s}")
    notes = st.text_area(T["notes"], height=100)
    if st.button(T["save_entry"]):
        entry = {
            "type":"DAILY",
            "at": datetime.now().isoformat(),
            "triggers": day_triggers + ([f"Other: {other_tr.strip()}"] if other_tr.strip() else []),
            "symptoms": [{"name":k,"severity":v} for k,v in sev_map.items()],
            "notes": notes.strip()
        }
        try:
            insert_journal(st.session_state["user"], str(datetime.now()), entry)
            st.success(T["saved"])
        except Exception as e:
            st.warning(f"Save failed: {e}")

# TAB 4 — JOURNAL & HISTORY
def render_journal():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    st.title("📒 " + T["journal_tab"])

    # Structured composer
    mood = st.select_slider(T["mood"], ["😔","😐","🙂","😄"], value="🙂")
    energy = st.select_slider(T["energy"], ["Low","Medium","High"], value="Medium")
    sleep = st.select_slider(T["sleep"], ["Poor","Okay","Good"], value="Good")
    hydration = st.select_slider(T["hydration"], ["Low","Medium","High"], value="Medium")
    activity = st.text_input(T["activity"], placeholder="e.g., short walk, groceries" if app_language=="English" else "مثلًا: مشي قصير، تسوق")
    symptoms_list = SYMPTOMS_EN if app_language=="English" else SYMPTOMS_AR
    sel_symptoms = st.multiselect(T["symptoms_today"], symptoms_list)
    sym_map = {}
    for s in sel_symptoms:
        sym_map[s] = st.select_slider(s, ["Mild","Moderate","Severe"], value="Moderate", key=f"jh_{s}")
    triggers = st.multiselect(T["triggers_today"], TRIGGERS_EN if app_language=="English" else TRIGGERS_AR)
    other_tr = st.text_input(T["other"], "")
    notes = st.text_area(T["notes"], height=100)

    if st.button(T["save_entry"]):
        entry = {
            "type":"DAILY",
            "at": datetime.now().isoformat(),
            "mood": mood, "energy": energy, "sleep": sleep, "hydration": hydration,
            "activity": activity.strip(),
            "symptoms": [{"name":k,"severity":v} for k,v in sym_map.items()],
            "triggers": triggers + ([f"Other: {other_tr.strip()}"] if other_tr.strip() else []),
            "notes": notes.strip()
        }
        try:
            insert_journal(st.session_state["user"], str(datetime.now()), entry)
            st.success(T["saved"])
        except Exception as e:
            st.warning(f"Save failed: {e}")

    st.markdown("---")
    st.subheader(T["recent_entries"])
    rows = get_recent_journal(st.session_state["user"], limit=30)
    if rows:
        for d, e in rows:
            try:
                obj = json.loads(e); label = obj.get("type","NOTE")
                if label=="ALERT":
                    st.write(f"📅 {d[:16]} — ALERT: {', '.join(obj.get('reasons', []))} • {obj.get('note','')}")
                elif label=="DAILY":
                    t = obj.get('triggers', [])
                    s = obj.get('symptoms', [])
                    s_short = ", ".join(f"{x['name']}({x['severity'][0]})" if isinstance(x, dict) else str(x) for x in s)
                    st.write(f"📅 {d[:16]} — DAILY: mood {obj.get('mood','')} • energy {obj.get('energy','')} • triggers: {', '.join(t)} • symptoms: {s_short}")
                else:
                    st.write(f"📅 {d[:16]} → {e}")
            except:
                st.write(f"📅 {d[:16]} → {e}")
    else:
        st.info("No entries yet.")

    # Temperature history (same as monitor)
    st.markdown("---")
    st.subheader(T["temp_trend"])
    rows = get_recent_temps(st.session_state["user"], limit=50)
    if rows:
        rows = rows[::-1]
        dates = [r[0][5:16] for r in rows]
        bt = [r[1] for r in rows]
        ft = [r[2] for r in rows]
        fig, ax = plt.subplots(figsize=(10,4))
        ax.plot(range(len(dates)), bt, marker='o', label="Body", linewidth=2, color='red')
        ax.plot(range(len(dates)), ft, marker='s', label="Feels-like", linewidth=2)
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, fontsize=9)
        ax.set_ylabel("°C"); ax.legend(); ax.grid(True, alpha=0.3)
        st.pyplot(fig)
    else:
        st.info("No temperature history recorded yet.")

    # Weekly recap (AI)
    if client and st.button("🧠 Summarize my week"):
        ctx = build_context(st.session_state["user"])
        ans, err = ai_response("Summarize key patterns and give 3 suggestions:\n"+ctx, app_language)
        st.info(ans if ans else "AI error.")

# TAB 5 — AI ASSISTANT
def render_assistant():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    st.title("🤖 " + T["assistant_tab"])
    st.caption("I’ll use your recent entries and can check a specific place’s weather.")

    question = st.text_area(T["ask_anything"], "I want to go to Saadiyat Beach this afternoon—what should I consider?")
    if st.button(T["get_tips"]):
        if not client:
            st.warning(T["ai_unavailable"]); return

        # Try to detect a place by geocoding the whole question
        place, lat, lon = geocode_place(question)
        place_weather = get_weather_by_coords(lat, lon) if lat and lon else None

        ctx = build_context(st.session_state["user"])
        extra = ""
        if place_weather:
            extra = f"\nPlace weather ({place}): feels-like {round(place_weather['feels_like'],1)}°C, humidity {int(place_weather['humidity'])}% ({place_weather['desc']})."
        prompt = f"Recent journal:\n{ctx}\n\nQuestion: {question}{extra}\nProvide short, practical recommendations."
        ans, err = ai_response(prompt, app_language)
        if err:
            st.error("AI error.")
        else:
            st.info(ans)

# TAB 6 — SETTINGS & EXPORT
def render_settings():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return

    st.title("⚙️ " + T["settings"])
    st.session_state.setdefault("baseline", 37.0)
    st.session_state["baseline"] = st.number_input(T["personal_baseline"], 35.5, 38.5, st.session_state["baseline"], 0.1)
    st.caption(T["baseline_hint"])

    st.subheader(T["export_csv"])
    if st.button(T["export_csv"]):
        import csv, io
        c = get_conn().cursor()
        c.execute("""SELECT date, body_temp, weather_temp, feels_like, humidity, status
                     FROM temps WHERE username=? ORDER BY date ASC""",
                  (st.session_state["user"],))
        rows = c.fetchall()
        buff = io.StringIO(); w = csv.writer(buff)
        w.writerow(["date","body_temp","weather_temp","feels_like","humidity","status"])
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
