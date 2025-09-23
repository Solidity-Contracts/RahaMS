# raha_ms_sqlite_app.py
"""
Raha MS - comprehensive Streamlit PoC with SQLite and login (Single-file)
"""

import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import altair as alt
import requests
import re
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash

# Optional OpenAI import handled dynamically
try:
    import openai
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

# -----------------------
# Config
# -----------------------
APP_NAME = "Raha MS"
DB_PATH = "raha_ms_data.db"
DEFAULT_BASELINE_DAYS = 7
DEFAULT_DELTA_THRESHOLD = 0.5
RECENT_HISTORY_COUNT = 10

# UI strings (Arabic-first)
I18N = {
    "ar": {
        "app_title": "راحة MS",
        "register": "تسجيل",
        "login": "تسجيل الدخول",
        "logout": "تسجيل الخروج",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "home": "الرئيسية",
        "record": "سجل قياس",
        "diary": "اليوميات",
        "graphs": "الرسوم",
        "assistant": "المساعد",
        "about": "عن التطبيق",
        "settings": "الإعدادات",
        "body_temp": "درجة حرارة الجسم (°C)",
        "ambient_temp": "درجة حرارة المحيط (°C)",
        "event": "حدث",
        "notes": "ملاحظات",
        "save": "حفظ",
        "recent_entries": "السجلات الأخيرة",
        "no_data": "لا توجد بيانات",
        "baseline_info": "معايرة القاعدة (أول {n} قياسات)",
        "risk_warn": "⚠️ تحذير: ارتفاع درجة حرارة الجسم ≥ {dt}°C مقارنة بالقاعدة",
        "cooling_tips": "نصائح للتبريد",
        "download_csv": "تحميل CSV",
        "ask_assistant": "اسأل المساعد",
        "placeholder_question": "مثال: هل أخرج الآن؟",
        "share_clinician": "مشاركة مع الطبيب",
        "severity": "شدة",
        "mild": "خفيف",
        "moderate": "متوسط",
        "severe": "شديد",
        "ramadan_mode": "وضع رمضان",
        "fasting_state": "هل تصوم حالياً؟",
        "not_med_device": "هذا التطبيق معلوماتي فقط ولا يعتبر جهازًا طبيًا."
    },
    "en": {
        "app_title": "Raha MS",
        "register": "Register",
        "login": "Log in",
        "logout": "Log out",
        "username": "Username",
        "password": "Password",
        "home": "Home",
        "record": "Record",
        "diary": "Diary",
        "graphs": "Graphs",
        "assistant": "Assistant",
        "about": "About",
        "settings": "Settings",
        "body_temp": "Body temperature (°C)",
        "ambient_temp": "Ambient temperature (°C)",
        "event": "Event",
        "notes": "Notes",
        "save": "Save",
        "recent_entries": "Recent entries",
        "no_data": "No data",
        "baseline_info": "Baseline calibration (first {n} records)",
        "risk_warn": "⚠️ Risk: body temp increased ≥ {dt}°C from baseline",
        "cooling_tips": "Cooling tips",
        "download_csv": "Download CSV",
        "ask_assistant": "Ask assistant",
        "placeholder_question": "e.g.: Is it safe to go outside now?",
        "share_clinician": "Share with clinician",
        "severity": "Severity",
        "mild": "Mild",
        "moderate": "Moderate",
        "severe": "Severe",
        "ramadan_mode": "Ramadan mode",
        "fasting_state": "Fasting now?",
        "not_med_device": "This app is informational only — not a medical device."
    }
}

# Event labels
EVENT_LABELS_EN = [
    "None", "Exercise", "Sauna", "HotFood", "WentOut", "Medication",
    "Period", "HotShower", "Fever", "Dehydration", "HotEnvironment"
]
EVENT_LABELS_AR_MAP = {
    "None": "بدون",
    "Exercise": "تمارين",
    "Sauna": "ساونا",
    "HotFood": "طعام حار",
    "WentOut": "خارج",
    "Medication": "دواء",
    "Period": "حيض",
    "HotShower": "استحمام ساخن",
    "Fever": "حمى/التهاب",
    "Dehydration": "جفاف",
    "HotEnvironment": "حرارة مرتفعة"
}

# -----------------------
# Helpers
# -----------------------
def is_arabic(text: str) -> bool:
    return bool(re.search(r'[\u0600-\u06FF]', text)) if text else False

# Database
def init_db(path=DB_PATH):
    conn = sqlite3.connect(path, check_same_thread=False)
    cur = conn.cursor()
    # users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        preferred_lang TEXT DEFAULT 'ar',
        created_at TEXT
    )
    """)
    # measurements
    cur.execute("""
    CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        timestamp TEXT,
        body_temp REAL,
        ambient_temp REAL,
        event_tag TEXT,
        severity TEXT,
        notes TEXT,
        share_with_clinician INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    # diary
    cur.execute("""
    CREATE TABLE IF NOT EXISTS diary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        timestamp TEXT,
        meds TEXT,
        notes TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    conn.commit()
    return conn

# create or get DB
conn = init_db()
cur = conn.cursor()

# Session helpers
def current_user():
    return st.session_state.get("user")  # dict with id, username, preferred_lang

def login_user(user_row):
    st.session_state["user"] = {"id": user_row[0], "username": user_row[1], "preferred_lang": user_row[3]}
    st.session_state["logged_in"] = True

def logout_user():
    st.session_state.pop("user", None)
    st.session_state["logged_in"] = False

# Create user
def create_user(username, password, preferred_lang="ar"):
    pw_hash = generate_password_hash(password)
    try:
        cur.execute("INSERT INTO users (username, password_hash, preferred_lang, created_at) VALUES (?, ?, ?, ?)",
                    (username, pw_hash, preferred_lang, datetime.utcnow().isoformat()))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, "Username already exists."

# Authenticate
def authenticate(username, password):
    cur.execute("SELECT id, username, password_hash, preferred_lang FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if not row:
        return False, "User not found."
    if check_password_hash(row[2], password):
        return True, row
    return False, "Wrong password."

# Data access
def add_measurement(user_id, body_temp, ambient_temp, event_tag, severity, notes, share):
    ts = datetime.utcnow().isoformat()
    cur.execute("""INSERT INTO measurements (user_id, timestamp, body_temp, ambient_temp, event_tag, severity, notes, share_with_clinician)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, ts, body_temp, ambient_temp, event_tag, severity, notes, 1 if share else 0))
    conn.commit()

def get_measurements_df(user_id, limit=None):
    q = "SELECT id, timestamp, body_temp, ambient_temp, event_tag, severity, notes, share_with_clinician FROM measurements WHERE user_id = ? ORDER BY timestamp ASC"
    df = pd.read_sql_query(q, conn, params=(user_id,), parse_dates=["timestamp"])
    if df.empty:
        return df
    if limit:
        return df.tail(limit)
    return df

def add_diary_entry(user_id, meds, notes):
    ts = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO diary (user_id, timestamp, meds, notes) VALUES (?,?,?,?)", (user_id, ts, meds, notes))
    conn.commit()

def get_diary_df(user_id, limit=None):
    df = pd.read_sql_query("SELECT id, timestamp, meds, notes FROM diary WHERE user_id = ? ORDER BY timestamp DESC", conn, params=(user_id,), parse_dates=["timestamp"])
    if df.empty:
        return df
    if limit:
        return df.head(limit)
    return df

# Weather & assistant helpers
def fetch_weather_cached(city="Dubai,AE"):
    # keys are read from st.secrets (not UI)
    openweather_key = st.secrets.get("OPENWEATHER_API_KEY") if st.secrets else None
    if not openweather_key:
        return None, "Missing OpenWeather key in secrets"
    try:
        r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                         params={"q": city, "appid": openweather_key, "units": "metric"}, timeout=6)
        r.raise_for_status()
        j = r.json()
        return {"temp": float(j["main"]["temp"]), "desc": j["weather"][0]["description"], "raw": j}, None
    except Exception as e:
        return None, str(e)

def assistant_reply_openai(user_question, user_lang, context_text=""):
    # system prompt
    system_prompt = (
        "You are 'Raha-MS Assistant', a cautious, culturally-aware assistant for people with Multiple Sclerosis in the GCC. "
        "Reply in the same language the user asks. Prioritize safe, evidence-aligned cooling steps when body temp increase is detected. "
        "Always include a reminder to consult a clinician for serious symptoms. Avoid recommending anything culturally inappropriate."
    )
    openai_key = st.secrets.get("OPENAI_API_KEY") if st.secrets else None
    if not openai_key:
        return ("[Assistant not available — the OpenAI key is missing from app secrets.]", False)
    if not OPENAI_AVAILABLE:
        return ("[Assistant not available — openai package not installed on the runtime.]", False)
    openai.api_key = openai_key
    user_content = f"User language:{user_lang}\nContext:{context_text}\nQuestion:{user_question}"
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system_prompt},
                      {"role":"user","content":user_content}],
            max_tokens=320,
            temperature=0.2
        )
        assistant_text = resp["choices"][0]["message"]["content"]
        return assistant_text, True
    except Exception as e:
        return (f"[Assistant error: {str(e)}]", False)

# -----------------------
# Streamlit UI
# -----------------------
st.set_page_config(page_title=f"{APP_NAME} — Heat Sensitivity for MS (GCC)", layout="wide")

# Top-level - authentication widget
st.sidebar.title(APP_NAME)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# If not logged in --> show register / login
if not st.session_state["logged_in"]:
    auth_mode = st.sidebar.radio("Welcome — اختر", ("تسجيل / Register", "تسجيل الدخول / Login"))
    if auth_mode.startswith("تسجيل") or auth_mode.startswith("Register"):
        st.sidebar.subheader(I18N["en"]["register"] + " / " + I18N["ar"]["register"])
        new_username = st.sidebar.text_input(I18N["en"]["username"])
        new_password = st.sidebar.text_input(I18N["en"]["password"], type="password")
        pref_lang = st.sidebar.selectbox("Preferred language / اللغة", ("Arabic - العربية", "English"))
        pref_code = "ar" if pref_lang.lower().startswith("arab") else "en"
        if st.sidebar.button("Create account"):
            if not new_username or not new_password:
                st.sidebar.error("Please enter username and password.")
            else:
                ok, err = create_user(new_username.strip(), new_password.strip(), preferred_lang=pref_code)
                if ok:
                    st.sidebar.success("Account created. Please log in.")
                else:
                    st.sidebar.error(err)
    else:
        st.sidebar.subheader(I18N["en"]["login"] + " / " + I18N["ar"]["login"])
        login_username = st.sidebar.text_input(I18N["en"]["username"], key="login_user")
        login_password = st.sidebar.text_input(I18N["en"]["password"], type="password", key="login_pw")
        if st.sidebar.button("Login"):
            ok, data = authenticate(login_username.strip(), login_password.strip())
            if ok:
                login_user(data)
                st.success("Logged in as " + data[1])
                st.experimental_rerun()
            else:
                st.sidebar.error(data)

    st.sidebar.markdown("---")
    st.sidebar.markdown("Keys are read from `.streamlit/secrets.toml` — do not put them in the UI.")
    st.sidebar.caption("For deployment, add secrets in your host's secret manager.")
    # Show limited home info while not logged
    st.header(f"{APP_NAME}")
    st.write("This PoC uses SQLite and provides a per-user experience. Please register or log in from the sidebar.")
    st.stop()

# If logged in: main app
user = current_user()
user_id = user["id"]
user_pref_lang = user.get("preferred_lang", "ar")
USE_AR = user_pref_lang == "ar"
STRS = I18N["ar"] if USE_AR else I18N["en"]

# Navigation
pages = [STRS["home"], STRS["record"], STRS["diary"], STRS["graphs"], STRS["assistant"], STRS["about"], STRS["settings"]]
page = st.sidebar.radio("Navigate", pages)

# Logout
if st.sidebar.button(STRS["logout"]):
    logout_user()
    st.experimental_rerun()

# optional header image
if os.path.exists("assets/logo.png"):
    st.image("assets/logo.png", width=140)

st.title(f"{APP_NAME} — {STRS['app_title']}")

# page: Home
if page == STRS["home"]:
    st.subheader(STRS["home"])
    # weather
    weather, werr = fetch_weather_cached()
    if weather:
        st.info(f"{'الطقس الحالي' if USE_AR else 'Current weather'}: {weather['temp']:.1f} °C — {weather['desc']}")
    else:
        st.info(STRS["no_data"] + (f" ({werr})" if werr else ""))

    # summary: recent entries
    df_recent = get_measurements_df(user_id, limit=RECENT_HISTORY_COUNT)
    if df_recent.empty:
        st.info(STRS["no_data"])
    else:
        baseline = df_recent["body_temp"].head(DEFAULT_BASELINE_DAYS).mean() if len(df_recent) > 0 else 36.6
        latest = df_recent.iloc[-1]
        delta = latest["body_temp"] - baseline
        st.metric(label=STRS["body_temp"], value=f"{latest['body_temp']:.1f} °C", delta=f"{delta:+.2f} °C")
        if delta >= DEFAULT_DELTA_THRESHOLD:
            st.error(STRS["risk_warn"].format(dt=DEFAULT_DELTA_THRESHOLD))
            st.write("**" + STRS["cooling_tips"] + "**")
            # GCC tailored tips
            tips = [
                "Move to shaded or air-conditioned place",
                "Apply cool compress to neck/axilla",
                "Hydrate slowly with cool water",
                "Avoid peak sun hours (11:00–16:00)",
                "Delay sauna/hot baths until stable"
            ]
            tips_ar = [
                "الانتقال إلى مكان مظلل أو مكيف",
                "وضع كمادة باردة على الرقبة وتحت الإبط",
                "اشرب ماء بارد ببطء",
                "تجنّب التعرض للخارج خلال ساعات الذروة (11:00–16:00)",
                "تأجيل الساونا أو الاستحمام الساخن حتى تستقر الحرارة"
            ]
            for t in (tips_ar if USE_AR else tips):
                st.write("- " + t)
    st.markdown("---")
    st.write("Quick actions:")
    if st.button("Record quick sample (demo)"):
        # add a demo entry
        add_measurement(user_id, 36.9, 40.5, "HotEnvironment", "Mild", "Demo: walked outside", share=False)
        st.success("Demo sample added")
        st.experimental_rerun()

# page: Record
elif page == STRS["record"]:
    st.subheader(STRS["record"])
    with st.form("record_form"):
        col1, col2, col3 = st.columns([2,2,2])
        with col1:
            body_temp = st.number_input(STRS["body_temp"], min_value=34.0, max_value=42.0, value=36.6, step=0.1, format="%.1f")
            ambient_temp = st.number_input(STRS["ambient_temp"] + " (optional)", min_value=0.0, max_value=60.0, value=0.0, step=0.1, format="%.1f")
            ambient_temp = None if ambient_temp == 0.0 else ambient_temp
        with col2:
            # show event choices in user's language
            events_display = [EVENT_LABELS_AR_MAP[e] if USE_AR else e for e in EVENT_LABELS_EN]
            event_label = st.selectbox(STRS["event"], events_display)
            # map back
            if USE_AR:
                rev = {v:k for k,v in EVENT_LABELS_AR_MAP.items()}
                event_tag = rev.get(event_label, "None")
            else:
                event_tag = event_label
            severity = st.selectbox(STRS["severity"], [STRS["mild"], STRS["moderate"], STRS["severe"]])
            notes = st.text_input(STRS["notes"])
        with col3:
            share = st.checkbox(STRS["share_clinician"])
            ramadan_mode = st.checkbox(STRS["ramadan_mode"])
            submitted = st.form_submit_button(STRS["save"])
            if submitted:
                add_measurement(user_id, float(body_temp), ambient_temp, event_tag, severity, notes, share)
                st.success("✅ " + ("تم الحفظ" if USE_AR else "Saved"))
                st.experimental_rerun()

    st.markdown("---")
    st.write(STRS["recent_entries"])
    df_recent = get_measurements_df(user_id, limit=RECENT_HISTORY_COUNT)
    if df_recent.empty:
        st.info(STRS["no_data"])
    else:
        df_recent = df_recent.sort_values("timestamp", ascending=False)
        for idx, row in df_recent.iterrows():
            ts = pd.to_datetime(row["timestamp"]).strftime("%Y-%m-%d %H:%M")
            ambient = f" / {row['ambient_temp']:.1f}°C" if pd.notnull(row["ambient_temp"]) else ""
            ev_label = EVENT_LABELS_AR_MAP[row["event_tag"]] if (USE_AR and row["event_tag"] in EVENT_LABELS_AR_MAP) else row["event_tag"]
            summary = f"{ts} — {row['body_temp']:.1f}°C{ambient} — {ev_label} — {row['severity']}"
            with st.expander(summary):
                st.write(STRS["notes"] + ": ", row["notes"])
                if row["share_with_clinician"]:
                    st.info(STRS["share_clinician"])

# page: Diary
elif page == STRS["diary"]:
    st.subheader(STRS["diary"])
    with st.form("diary_form"):
        meds = st.text_input("Medications (prescription/herbal):")
        notes = st.text_area("Notes / الأعراض:")
        if st.form_submit_button("Add"):
            add_diary_entry(user_id, meds, notes)
            st.success("Added")
            st.experimental_rerun()
    df_diary = get_diary_df(user_id, limit=20)
    if df_diary.empty:
        st.info(STRS["no_data"])
    else:
        st.dataframe(df_diary)

# page: Graphs
elif page == STRS["graphs"]:
    st.subheader(STRS["graphs"])
    df_all = get_measurements_df(user_id)
    if df_all.empty:
        st.info(STRS["no_data"])
    else:
        df_all["timestamp"] = pd.to_datetime(df_all["timestamp"])
        df_all["ambient_temp"] = df_all["ambient_temp"].astype(float)
        base = alt.Chart(df_all).encode(x=alt.X("timestamp:T", title="Time"))
        body_line = base.mark_line(point=True).encode(y=alt.Y("body_temp:Q", title="Body °C"))
        amb_line = base.mark_line(strokeDash=[4,2]).encode(y=alt.Y("ambient_temp:Q", title="Ambient °C"))
        chart = alt.layer(body_line, amb_line).resolve_scale(y="independent").properties(height=420)
        st.altair_chart(chart.interactive(), use_container_width=True)
        # flagged events
        baseline = df_all["body_temp"].head(DEFAULT_BASELINE_DAYS).mean() if len(df_all)>0 else 36.6
        df_all["delta"] = df_all["body_temp"] - baseline
        flagged = df_all[df_all["delta"] >= DEFAULT_DELTA_THRESHOLD].sort_values("timestamp", ascending=False)
        st.markdown("Flagged events (Δ≥{:.2f}°C):".format(DEFAULT_DELTA_THRESHOLD))
        if flagged.empty:
            st.write("None")
        else:
            st.dataframe(flagged[["timestamp","body_temp","ambient_temp","event_tag","severity","delta","notes"]])
        csv = df_all.to_csv(index=False)
        st.download_button(STRS["download_csv"], data=csv, file_name=f"{user['username']}_measurements.csv", mime="text/csv")

# page: Assistant
elif page == STRS["assistant"]:
    st.subheader(STRS["assistant"])
    st.write("Ask the assistant in Arabic or English. It will reply in the same language.")
    user_q = st.text_input(STRS["placeholder_question"])
    if st.button(STRS["ask_assistant"]) and user_q.strip():
        # Build some context
        dfm = get_measurements_df(user_id, limit=DEFAULT_BASELINE_DAYS)
        latest_temp = dfm.iloc[-1]["body_temp"] if (not dfm.empty) else None
        weather, _ = fetch_weather_cached()
        ambient_now = weather["temp"] if weather else "unknown"
        context_txt = f"Latest body temp: {latest_temp}; Ambient now: {ambient_now}"
        lang_ar = is_arabic(user_q)
        reply, ok = assistant_reply_openai(user_q, "ar" if lang_ar else "en", context_text=context_txt)
        if ok:
            st.info(reply)
        else:
            st.warning(reply)

# page: About
elif page == STRS["about"]:
    st.subheader(STRS["about"])
    if USE_AR:
        st.markdown("""
        ### ما هو تطبيق راحة MS؟
        تطبيق لدعم مرضى التصلّب المتعدد في دول الخليج بالتعامل مع حساسية الحرارة (ظاهرة Uhthoff).
        - يكتشف زيادات طفيفة في الحرارة (≥ 0.5°C) ويقدّم نصائح تبريد فورية.
        - يضم يوميات أدوية وأعراض، مناسب للسياق الخليجي (الصيام، الملابس التقليدية).
        """)
    else:
        st.markdown("""
        ### What is Raha MS?
        Raha MS is designed to help people with Multiple Sclerosis in the GCC monitor and cope with heat sensitivity (Uhthoff phenomenon).
        - Detects small temperature rises (≥ 0.5°C) and offers immediate cooling actions.
        - Journal for meds and symptoms with export for clinician review.
        """)
    st.write(STRS["not_med_device"])

# page: Settings
elif page == STRS["settings"]:
    st.subheader(STRS["settings"])
    st.write("Adjustable (session-only for PoC):")
    new_baseline_days = st.number_input("Baseline days for average", min_value=1, max_value=30, value=DEFAULT_BASELINE_DAYS)
    new_delta = st.number_input("Delta threshold (°C)", min_value=0.1, max_value=2.0, value=DEFAULT_DELTA_THRESHOLD, step=0.1)
    ramadan_enabled = st.checkbox("Enable Ramadan-aware tips", value=False)
    if st.button("Save (session)"):
        # For PoC store in session state
        st.session_state["baseline_days"] = int(new_baseline_days)
        st.session_state["delta_threshold"] = float(new_delta)
        st.session_state["ramadan_mode"] = bool(ramadan_enabled)
        st.success("Saved (session-only)")

# Footer / credits
st.markdown("---")
st.caption("Raha MS — PoC for Medical Device Innovation. For research & prototyping only.")
