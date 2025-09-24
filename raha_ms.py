import streamlit as st
import sqlite3
from openai import OpenAI
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from math import isnan

# ================== CONFIG ==================
st.set_page_config(page_title="Raha MS", page_icon="🌡️", layout="wide")

# Secrets (fail gracefully if missing)
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# GCC quick picks
GCC_CITIES = [
    "Abu Dhabi,AE", "Dubai,AE", "Sharjah,AE",
    "Doha,QA", "Al Rayyan,QA",
    "Kuwait City,KW",
    "Manama,BH",
    "Riyadh,SA", "Jeddah,SA", "Dammam,SA",
    "Muscat,OM"
]

# ================== I18N ==================
TEXTS = {
    "English": {
        "about_title": "About Raha MS",
        "login_title": "Login / Register",
        "username": "Username",
        "password": "Password",
        "login": "Login",
        "register": "Register",
        "temp_monitor": "My Heat Safety",
        "assistant": "AI Companion",
        "journal": "Journal & Symptoms",
        "logout": "Logout",
        "risk_dashboard": "Heat Safety Dashboard",
        "enter_temp": "Enter your body temperature (°C):",
        "city": "City (City,CC)",
        "quick_pick": "Quick pick (GCC):",
        "did_today": "Today I did / experienced:",
        "symptoms_today": "Symptoms experienced today:",
        "check_risk": "Check My Heat Risk",
        "personal_baseline": "My usual/normal body temperature (°C):",
        "fasting_today": "Fasting today?",
        "ai_advice_btn": "Get AI Advice",
        "journal_title": "Journal & Symptoms",
        "journal_hint": "Write brief notes. Separate blocks with line breaks.",
        "save": "Save",
        "login_first": "Please login first.",
        "logged_in": "✅ Logged in!",
        "bad_creds": "❌ Invalid credentials",
        "account_created": "✅ Account created! Please login.",
        "user_exists": "❌ Username already exists",
        "logged_out": "✅ Logged out!",
        "weather_fail": "Weather lookup failed",
        "ai_unavailable": "AI is unavailable. Set OPENAI_API_KEY in secrets."
    },
    "Arabic": {
        "about_title": "عن تطبيق راحة إم إس",
        "login_title": "تسجيل الدخول / إنشاء حساب",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "login": "تسجيل الدخول",
        "register": "إنشاء حساب",
        "temp_monitor": "سلامتي من الحرارة",
        "assistant": "المساعد الذكي",
        "journal": "اليوميات والأعراض",
        "logout": "تسجيل الخروج",
        "risk_dashboard": "لوحة سلامة الحرارة",
        "enter_temp": "أدخل حرارة جسمك (°م):",
        "city": "المدينة (City,CC)",
        "quick_pick": "اختيار سريع (الخليج):",
        "did_today": "اليوم قمتُ بـ / تعرضتُ لـ:",
        "symptoms_today": "الأعراض اليوم:",
        "check_risk": "تحقق من خطري الحراري",
        "personal_baseline": "حرارتي المعتادة (°م):",
        "fasting_today": "صائم اليوم؟",
        "ai_advice_btn": "الحصول على نصيحة ذكية",
        "journal_title": "اليوميات والأعراض",
        "journal_hint": "اكتب ملاحظات قصيرة. افصل بين المقاطع بسطر جديد.",
        "save": "حفظ",
        "login_first": "يرجى تسجيل الدخول أولاً.",
        "logged_in": "✅ تم تسجيل الدخول",
        "bad_creds": "❌ بيانات غير صحيحة",
        "account_created": "✅ تم إنشاء الحساب! الرجاء تسجيل الدخول.",
        "user_exists": "❌ اسم المستخدم موجود",
        "logged_out": "✅ تم تسجيل الخروج!",
        "weather_fail": "فشل جلب الطقس",
        "ai_unavailable": "الخدمة الذكية غير متاحة. أضف مفتاح OPENAI_API_KEY."
    }
}

# ================== STYLES (accessibility) ==================
ACCESSIBLE_CSS = """
<style>
/* larger targets & font, high contrast */
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
    # check_same_thread=False to avoid thread issues on rerun
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
    conn.commit()


def migrate_db():
    conn = get_conn() if 'get_conn' in globals() else sqlite3.connect("raha_ms.db", check_same_thread=False)
    c = conn.cursor()
    # What columns do we have now?
    c.execute("PRAGMA table_info(temps)")
    cols = [r[1] for r in c.fetchall()]

    # Add new columns if they don't exist (SQLite appends them at the end)
    if "feels_like" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN feels_like REAL")
    if "humidity" not in cols:
        c.execute("ALTER TABLE temps ADD COLUMN humidity REAL")

    conn.commit()

# call on every run (safe if run repeatedly)
migrate_db()

init_db()

# ================== WEATHER ==================
@st.cache_data(ttl=600)  # 10 minutes
def get_weather(city="Abu Dhabi,AE"):
    """Return current weather + 48h forecast windows using OWM 'weather' and 'forecast' endpoints."""
    if not OPENWEATHER_API_KEY:
        return None, "Missing OPENWEATHER_API_KEY"

    try:
        base = "https://api.openweathermap.org/data/2.5/"
        # current
        params_now = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "en"}
        r_now = requests.get(base + "weather", params=params_now, timeout=6)
        r_now.raise_for_status()
        jn = r_now.json()

        temp = float(jn["main"]["temp"])
        feels = float(jn["main"]["feels_like"])
        hum = float(jn["main"]["humidity"])
        desc = jn["weather"][0]["description"]
        lat = jn.get("coord", {}).get("lat")
        lon = jn.get("coord", {}).get("lon")

        # 5-day / 3h forecast (pick next 48h)
        params_fc = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "en"}
        r_fc = requests.get(base + "forecast", params=params_fc, timeout=8)
        r_fc.raise_for_status()
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

        # derive simple "peak heat hours": top 4 feels_like in the next 48h
        top = sorted(forecast, key=lambda x: x["feels_like"], reverse=True)[:4]
        peak_hours = [f'{t["time"][5:16]} (~{round(t["feels_like"])}°C, {int(t["humidity"])}%)' for t in top]

        return {
            "temp": temp, "feels_like": feels, "humidity": hum, "desc": desc,
            "lat": lat, "lon": lon, "forecast": forecast, "peak_hours": peak_hours
        }, None
    except Exception as e:
        return None, str(e)

# ================== RISK MODEL ==================
TRIGGER_WEIGHTS = {
    "Exercise": 2, "Sauna": 3, "Spicy food": 1, "Hot drinks": 1,
    "Stress": 1, "Direct sun exposure": 2, "Fever": 3, "Hormonal cycle": 1
}
SYMPTOM_WEIGHT = 0.5  # per symptom selected

def risk_from_env(feels_like_c: float, humidity: float) -> int:
    """Return base environmental risk points from apparent temp + humidity."""
    # coarse bands tailored for GCC humidity; keep simple & explainable
    score = 0
    if feels_like_c >= 39:          # very hot
        score += 3
    elif feels_like_c >= 35:
        score += 2
    elif feels_like_c >= 32:
        score += 1
    # humidity amplifies heat retention
    if humidity >= 60 and feels_like_c >= 32:
        score += 1
    return score

def risk_from_person(body_temp: float, baseline: float) -> int:
    """Uhthoff-aware: +1 if ≥0.5°C above baseline, +2 if ≥1.0°C."""
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
    elif score >= 5: status, color, icon, text = "High", "orangered", "🟠", "Elevated risk: limit time outside (esp. midday), pre‑cool and pace activities."
    elif score >= 3: status, color, icon, text = "Caution", "orange", "🟡", "Mild risk: hydrate, take breaks, prefer shade/AC, and monitor symptoms."
    else:            status, color, icon, text = "Safe", "green", "🟢", "You look safe. Keep cool and hydrated."
    return {"score": score, "status": status, "color": color, "icon": icon, "advice": text}

# ================== AI ==================
def ai_response(prompt, lang):
    sys_prompt = (
        "You are Raha MS AI Companion. Provide culturally relevant, practical MS heat safety advice for Gulf (GCC) users. "
        "Use calm language and short bullet points. Consider fasting, prayer times, home AC use, cooling garments, and pacing. "
        "This is general education, not medical care."
    )
    if lang == "Arabic":
        sys_prompt += " Respond only in Arabic."
    else:
        sys_prompt += " Respond only in English."

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
    T = TEXTS[lang]
    if lang == "English":
        st.title("🧠 Welcome to Raha MS")
        st.markdown("""
Living with **Multiple Sclerosis (MS)** in the GCC can be uniquely challenging due to heat and humidity.  
Raha MS helps you **see heat risk at a glance**, **track your body temp**, and get **gentle, culturally aware tips**.
""")
        st.subheader("🌡️ Why heat matters")
        st.info("Even a small rise in body temperature can temporarily worsen MS symptoms (Uhthoff’s phenomenon). Cooling and pacing help.")
        st.subheader("✨ What you can do here")
        st.markdown("- **Track** body temperature and local weather\n- **Spot triggers** (exercise, sun, sauna…)\n- **Journal** symptoms & patterns\n- **Get tips** from the AI Companion")
        st.caption("Privacy: Your data stays on this device (SQLite). No sharing.")
    else:
        st.title("🧠 مرحبًا بك في راحة إم إس")
        st.markdown("""
العيش مع **التصلب المتعدد** في الخليج صعب بسبب الحرارة والرطوبة.  
يساعدك التطبيق على **رؤية الخطر الحراري بسرعة**، و**تسجيل حرارة جسمك**، والحصول على **نصائح لطيفة ومناسبة ثقافيًا**.
""")
        st.subheader("🌡️ لماذا تؤثر الحرارة؟")
        st.info("ارتفاع بسيط في حرارة الجسم قد يزيد الأعراض مؤقتًا (ظاهرة أوتهوف). التبريد والتنظيم يساعدان.")
        st.subheader("✨ ماذا يوفر التطبيق؟")
        st.markdown("- **متابعة** حرارة الجسم والطقس\n- **تحديد المحفزات** (رياضة، شمس، ساونا…)\n- **كتابة اليوميات** والأعراض\n- **الحصول على نصائح** من المساعد الذكي")
        st.caption("الخصوصية: بياناتك تبقى على هذا الجهاز (SQLite). لا يتم مشاركتها.")

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

page = st.sidebar.radio("Navigate", [
    T["about_title"], T["login_title"], T["temp_monitor"], T["journal"], T["logout"]
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

# HEAT DASHBOARD
elif page == T["temp_monitor"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("☀️ " + T["risk_dashboard"])
        st.write("Your AI Companion analyzes **apparent temperature, humidity, your body temp, triggers, and journal context** to offer gentle, GCC‑aware tips.")

        with st.form("risk_form", clear_on_submit=False):
            colL, colR = st.columns([3,1])
            with colL:
                body_temp = st.number_input("🌡️ " + T["enter_temp"], 30.0, 45.0, 37.0, step=0.1)
                baseline = st.number_input("🧭 " + T["personal_baseline"], 35.5, 38.5, st.session_state.get("baseline", 37.0), step=0.1)
                # city inputs
                quick = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0)
                city = st.text_input("🏙️ " + T["city"], value=quick)
                triggers = st.multiselect(
                    "✅ " + T["did_today"],
                    ["Exercise", "Sauna", "Spicy food", "Hot drinks", "Stress", "Direct sun exposure", "Fever", "Hormonal cycle"]
                )
                symptoms = st.multiselect(
                    "⚕️ " + T["symptoms_today"],
                    ["Blurred vision","Fatigue","Muscle weakness","Numbness","Coordination issues","Mental fog"]
                )
                fasting = st.checkbox("🕋 " + T["fasting_today"], value=False)
                with st.expander("Why fasting matters in the heat (open)"):
                    st.markdown("""
- In MS, heat can temporarily worsen symptoms (Uhthoff's phenomenon).
  **National MS Society**: https://www.nationalmssociety.org/managing-ms/living-with-ms/diet-exercise-and-healthy-behaviors/heat-temperature
- Fasting during Ramadan means no fluids between dawn and sunset; in hot climates this raises **dehydration risk**.
  **Hamad Medical Corporation**: https://www.hamad.qa/en/your%20health/ramadan%20health/health%20information/pages/dehydration.aspx
- Dehydration reduces your body's ability to cool itself and increases heat strain.
  **CDC – Heat and Your Health**: https://www.cdc.gov/heat-health/about/index.html
""")


            with colR:
                submitted = st.form_submit_button("🔍 " + T["check_risk"])

        if submitted:
            # remember baseline
            st.session_state["baseline"] = baseline

            weather, err = get_weather(city)
            if weather is None:
                st.error(f"{T['weather_fail']}: {err}")
            else:
                # compute risk using feels_like & humidity + personal/triggers
                risk = compute_risk(
                    weather["feels_like"], weather["humidity"],
                    float(body_temp), float(baseline), triggers, symptoms
                )

                # save to session + DB
                checkpoint = {
                    "city": city,
                    "body_temp": float(body_temp),
                    "baseline": float(baseline),
                    "weather_temp": weather["temp"],
                    "feels_like": weather["feels_like"],
                    "humidity": weather["humidity"],
                    "weather_desc": weather["desc"],
                    "status": risk["status"],
                    "color": risk["color"],
                    "icon": risk["icon"],
                    "advice": risk["advice"],
                    "triggers": triggers, "symptoms": symptoms,
                    "peak_hours": weather["peak_hours"],
                    "forecast": weather["forecast"],
                    "fasting": fasting,
                    "time": datetime.utcnow().isoformat()
                }
                st.session_state["last_check"] = checkpoint

                try:
                    c = get_conn().cursor()
                    c.execute("INSERT INTO temps VALUES (?,?,?,?,?,?,?)",
                              (st.session_state["user"], str(datetime.now()),
                               checkpoint["body_temp"], checkpoint["weather_temp"],
                               checkpoint["feels_like"], checkpoint["humidity"], checkpoint["status"]))
                    get_conn().commit()
                except Exception as e:
                    st.warning(f"Could not save to DB: {e}")

        # render last check if any
        if st.session_state.get("last_check"):
            last = st.session_state["last_check"]
            triggers_text = ', '.join(last['triggers']) if last['triggers'] else 'None'
            symptoms_text = ', '.join(last['symptoms']) if last['symptoms'] else 'None'
            left_color = last['color']

            st.markdown(f"""
<div class="big-card" style="--left:{left_color}">
  <h3>{last['icon']} <strong>Status: {last['status']}</strong></h3>
  <p style="margin:6px 0 0 0">{last['advice']}</p>
  <div class="small" style="margin-top:8px">
    <span class="badge">Weather: {last['city']}</span>
    <span class="badge">Feels-like: {round(last['feels_like'],1)}°C</span>
    <span class="badge">Humidity: {int(last['humidity'])}%</span>
    <span class="badge">Body: {round(last['body_temp'],1)}°C (baseline {round(last['baseline'],1)}°C)</span>
    <span class="badge">Checked: {last['time'][:16]}</span>
  </div>
  <p class="small" style="margin-top:6px">Triggers: {triggers_text} • Symptoms: {symptoms_text}</p>
  <p class="small" style="margin-top:6px">Peak heat next 48h: {"; ".join(last['peak_hours'])}</p>
</div>
""", unsafe_allow_html=True)

            # Chart
st.subheader("📈 Recent temperature trend")
conn = get_conn() if 'get_conn' in globals() else sqlite3.connect("raha_ms.db", check_same_thread=False)
c = conn.cursor()

# Figure out which columns exist
c.execute("PRAGMA table_info(temps)")
cols = {r[1] for r in c.fetchall()}

if "feels_like" in cols:
    c.execute("""
        SELECT date, body_temp, weather_temp, feels_like, status
        FROM temps
        WHERE username=?
        ORDER BY date DESC LIMIT 20
    """, (st.session_state["user"],))
    rows = c.fetchall()
else:
    # Fallback for very old DBs (should be rare after migrate_db)
    c.execute("""
        SELECT date, body_temp, weather_temp, status
        FROM temps
        WHERE username=?
        ORDER BY date DESC LIMIT 20
    """, (st.session_state["user"],))
    rows = [ (d, bt, wt, wt, st) for (d, bt, wt, st) in c.fetchall() ]  # use weather_temp as proxy feels_like

if rows:
    rows = rows[::-1]
    dates = [r[0][5:16] for r in rows]
    bt = [r[1] for r in rows]
    wt = [r[2] for r in rows]
    ft = [ (r[3] if r[3] is not None else r[2]) for r in rows ]  # fallback if feels_like is NULL in older rows
    status_colors = ["green" if r[4]=="Safe" else "orange" if r[4] in ("Caution","High") else "red" for r in rows]

    fig, ax = plt.subplots(figsize=(9,3))
    ax.plot(range(len(dates)), bt, marker='o', label="Body", linewidth=2)
    ax.plot(range(len(dates)), ft, marker='s', label="Feels-like", linewidth=2)
    for i, color in enumerate(status_colors):
        ax.scatter(i, bt[i], s=110, edgecolor="black", zorder=5, color=color)
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(dates, rotation=30, fontsize=8)
    ax.set_ylabel("°C")
    ax.legend()
    st.pyplot(fig)

            # --- AI Companion (always visible at the bottom) ---
st.markdown("---")
st.subheader("🤖 AI Companion")

if not client:
    st.warning("AI is unavailable. Set OPENAI_API_KEY in secrets.")
else:
    default_q = "How can I stay cool and pace activities in the GCC this week?"
    user_q = st.text_area("Ask anything (English or Arabic):", value=default_q, height=90)
    use_ctx = st.checkbox("Use my latest heat check as context", value=True)

    if st.button("Ask the assistant"):
        context = ""
        last = st.session_state.get("last_check")
        if use_ctx and last:
            context = (
                f"City: {last['city']}. Now feels-like {round(last['feels_like'],1)}°C, "
                f"humidity {int(last['humidity'])}%. Body temp {round(last['body_temp'],1)}°C "
                f"(baseline {round(last.get('baseline', 37.0),1)}°C). "
                f"Triggers: {', '.join(last['triggers']) if last['triggers'] else 'None'}. "
                f"Symptoms: {', '.join(last['symptoms']) if last['symptoms'] else 'None'}. "
                f"Peak heat: {', '.join(last.get('peak_hours', [])) or 'n/a'}. "
                f"Fasting today: {last.get('fasting', False)}."
            )
        prompt = (context + "\n\nQuestion: " + user_q).strip()
        reply, err = ai_response(prompt, app_language)
        if err:
            st.error(f"AI error: {err}")
        else:
            st.info(reply)

# JOURNAL
elif page == T["journal"]:
    if "user" not in st.session_state:
        st.warning(T["login_first"])
    else:
        st.title("📒 " + T["journal_title"])
        st.write(TEXTS[app_language]["journal_hint"])

        entry_blocks = st.text_area("✍️", height=160)
        if st.button(TEXTS[app_language]["save"]):
            if entry_blocks.strip():
                lines = [line.strip() for line in entry_blocks.split("\n") if line.strip()]
                c = get_conn().cursor()
                for line in lines:
                    c.execute("INSERT INTO journal VALUES (?,?,?)", (st.session_state["user"], str(datetime.now()), line))
                get_conn().commit()
                st.success("✅ Saved")

        # Display existing entries
        c = get_conn().cursor()
        c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC", (st.session_state["user"],))
        rows = c.fetchall()
        for r in rows:
            st.write(f"📅 {r[0][:16]} → {r[1]}")

# LOGOUT
elif page == T["logout"]:
    st.session_state.pop("user", None)
    st.success(TEXTS[app_language]["logged_out"])
