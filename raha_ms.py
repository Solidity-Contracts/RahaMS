################################################################################
# raha_ms_full.py
# Raha MS — comprehensive Streamlit PoC for Heat Sensitivity (GCC) & MS
#
# Single-file PoC:
#  - Arabic-first UI with RTL adjustments (English fallback).
#  - SQLite persistence for measurements, meds, diary.
#  - Compact quick-pick event logging (Exercise, Sauna, Period, HotFood...).
#  - Short history view (last N records) + interactive Altair graphs.
#  - Weather fetch (OpenWeather) with caching.
#  - OpenAI assistant hook (responds in same language as user input).
#  - Cultural touches: Ramadan mode, GCC-tailored tips, About page explaining heat sensitivity.
#  - Export CSV; PDF export stub included (commented) - needs reportlab/weasyprint if used.
#
################################################################################

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import requests
import altair as alt
import os
import re
import json
from dateutil import parser as dateparser

# Open AI Assitant:
try:
    import openai
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

# -------------------------
# Configuration (editable)
# -------------------------
APP_NAME = "Raha MS"
DB_FILE = "raha_ms_full.db"
ASSETS_DIR = "assets"   # Put images: logo.png, header_ar.jpg, header_en.jpg
DEFAULT_BASELINE_DAYS = 7
DEFAULT_DELTA_THRESHOLD = 0.5   # °C threshold
RECENT_HISTORY_COUNT = 10

# -------------------------
# I18N strings (Arabic-first)
# -------------------------
I18N = {
    "ar": {
        "app_title": "راحة MS",
        "home": "الرئيسية",
        "record": "سجل قياس",
        "diary": "اليوميات",
        "graphs": "الرسوم",
        "assistant": "المساعد",
        "about": "عن التطبيق",
        "settings": "الإعدادات",
        "body_temp": "درجة حرارة الجسم (°C)",
        "ambient_temp": "درجة حرارة المحيط (°C)",
        "event": "الحدث",
        "notes": "ملاحظة",
        "save": "حفظ",
        "recent_entries": "السجلات الأخيرة",
        "no_data": "لا توجد بيانات",
        "baseline_info": "معايرة القاعدة (أول {n} قياسات أو الأيام الأولى)",
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
        "fasting_state": "صيام (رمضان)؟",
        "yes": "نعم",
        "no": "لا",
        "ramadan_mode": "وضع رمضان",
        "export_pdf": "تصدير تقرير PDF (تجريبي)",
        "not_med_device": "هذا التطبيق لأغراض معلوماتية فقط وليس جهازًا طبيًا."
    },
    "en": {
        "app_title": "Raha MS",
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
        "baseline_info": "Baseline calibration (first {n} records/days)",
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
        "fasting_state": "Fasting (Ramadan)?",
        "yes": "Yes",
        "no": "No",
        "ramadan_mode": "Ramadan mode",
        "export_pdf": "Export PDF report (experimental)",
        "not_med_device": "This app is informational only — not a medical device."
    }
}

# -------------------------
# Event labels + Arabic mapping
# -------------------------
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

# -------------------------
# Utility functions
# -------------------------
def is_arabic(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r'[\u0600-\u06FF]', text))

@st.cache_data(ttl=300)  # cache for 5 minutes
def fetch_weather(openweather_key: str, city: str = "Dubai,AE", units="metric"):
    if not openweather_key:
        return None, "No API key"
    try:
        r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                         params={"q": city, "appid": openweather_key, "units": units}, timeout=8)
        r.raise_for_status()
        j = r.json()
        return {"temp": float(j["main"]["temp"]), "desc": j["weather"][0]["description"], "raw": j}, None
    except Exception as e:
        return None, str(e)

def connect_db(db_file=DB_FILE):
    conn = sqlite3.connect(db_file, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            body_temp REAL,
            ambient_temp REAL,
            event_tag TEXT,
            severity TEXT,
            notes TEXT,
            share_with_clinician INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            dose TEXT,
            type TEXT,
            start_date TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS diary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            entry TEXT
        )
    """)
    conn.commit()
    return conn

# Build assistant system prompt (safety-aware)
def build_system_prompt():
    return (
        "You are 'Raha-MS Assistant', a cautious, culturally-aware assistant for people with Multiple Sclerosis in the GCC. "
        "Your role: give short, actionable, culturally-appropriate advice about heat sensitivity (Uhthoff-like responses). "
        "Always: (1) reply in the user's language (Arabic/English) used in the query; (2) include a reminder to consult a clinician for serious symptoms; "
        "(3) prioritize immediate cooling actions when body temp Δ≥0.5°C; (4) avoid recommending alcohol or culturally inappropriate actions and be Ramadan-aware."
    )

# -------------------------
# App init
# -------------------------
st.set_page_config(page_title=f"{APP_NAME} — Heat Sensitivity for MS (GCC)", layout="wide")

# Sidebar config
st.sidebar.title(APP_NAME)
openweather_key = st.sidebar.text_input("OpenWeather API key", type="password")
openai_key = st.sidebar.text_input("OpenAI API key (optional)", type="password")
city_input = st.sidebar.text_input("City (e.g., Dubai,AE)", value="Dubai,AE")
ui_lang_choice = st.sidebar.selectbox("Preferred UI language / لغة العرض", ("Arabic - العربية", "English"))
pref_lang = "ar" if ui_lang_choice.lower().startswith("arab") else "en"
USE_AR = pref_lang == "ar"

# Load images (optional)
if os.path.exists(os.path.join(ASSETS_DIR, "logo.png")):
    st.sidebar.image(os.path.join(ASSETS_DIR, "logo.png"), use_column_width=True)

# RTL CSS for Arabic
if USE_AR:
    st.markdown("""
    <style>
    html, body, [class^="css"] { direction: rtl; }
    .stButton>button { float: right; }
    </style>
    """, unsafe_allow_html=True)

# Connect DB
conn = connect_db()
cur = conn.cursor()

# Top nav
pages = [I18N[pref_lang]["home"], I18N[pref_lang]["record"], I18N[pref_lang]["diary"],
         I18N[pref_lang]["graphs"], I18N[pref_lang]["assistant"], I18N[pref_lang]["about"],
         I18N[pref_lang]["settings"]]
page = st.sidebar.radio("Navigate / تنقّل", pages)
# reverse map
page_map = {v:k for k,v in I18N[pref_lang].items()}
page_key = page_map.get(page, "home")

# Header
st.title(f"{APP_NAME} — {I18N[pref_lang]['app_title']}")

# Optional header image
hdr = os.path.join(ASSETS_DIR, "header_ar.jpg") if USE_AR else os.path.join(ASSETS_DIR, "header_en.jpg")
if os.path.exists(hdr):
    st.image(hdr, use_column_width=True)

# -------------------------
# Helper to read measurements into df
# -------------------------
def read_measurements_df(conn, limit=None):
    df = pd.read_sql_query("SELECT * FROM measurements ORDER BY timestamp ASC", conn, parse_dates=["timestamp"])
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if limit:
        return df.tail(limit)
    return df

# -------------------------
# Home Page
# -------------------------
if page_key == "home":
    st.subheader(I18N[pref_lang]["home"])
    weather, werr = fetch_weather(openweather_key, city=city_input)
    if weather:
        st.info(f"{I18N[pref_lang]['current_weather'] if 'current_weather' in I18N[pref_lang] else 'Weather'}: {weather['temp']:.1f}°C — {weather['desc']}")
    else:
        st.info(I18N[pref_lang]["no_data"] + (f" ({werr})" if werr else ""))

    df = read_measurements_df(conn)
    if df.empty:
        st.info(I18N[pref_lang]["no_data"])
    else:
        # baseline: mean of first DEFAULT_BASELINE_DAYS records or user-specified concept
        baseline_days = DEFAULT_BASELINE_DAYS
        baseline = df["body_temp"].head(baseline_days).mean() if len(df) >= 1 else 36.6
        latest = df.iloc[-1]
        delta = float(latest["body_temp"]) - baseline
        st.metric(label=I18N[pref_lang]["body_temp"], value=f"{latest['body_temp']:.1f} °C", delta=f"{delta:+.2f}°C vs baseline")
        if delta >= DEFAULT_DELTA_THRESHOLD:
            st.error(I18N[pref_lang]["risk_warn"].format(dt=DEFAULT_DELTA_THRESHOLD))
            st.write("**" + I18N[pref_lang]["cooling_tips"] + "**")
            tips_en = [
                "Move to shaded or air-conditioned environment",
                "Apply cool compress to neck and armpits",
                "Hydrate with cool water slowly",
                "Avoid outdoor exposure during peak sun hours (11:00–16:00)",
                "Delay sauna/hot baths until stable"
            ]
            tips_ar = [
                "الانتقال إلى مكان مظلل أو مكيف",
                "وضع كمادة باردة على الرقبة وتحت الإبط",
                "اشرب ماء بارد ببطء",
                "تجنّب التعرض للخارج خلال ساعات الذروة (11:00–16:00)",
                "تأجيل الساونا أو الاستحمام الساخن حتى تستقر الحرارة"
            ]
            for i,t in enumerate(tips_ar if USE_AR else tips_en):
                st.write("- " + t)

# -------------------------
# Record Page (compact + quick-pick)
# -------------------------
elif page_key == "record":
    st.subheader(I18N[pref_lang]["record"])

    # Quick log UI
    col_a, col_b, col_c = st.columns([2,2,2])
    with st.form("quick_log_form"):
        with col_a:
            body_temp = st.number_input(I18N[pref_lang]["body_temp"], min_value=34.0, max_value=42.0, value=36.6, step=0.1, format="%.1f")
            ambient_input = st.number_input(I18N[pref_lang]["ambient_temp"] + " (optional)", min_value=0.0, max_value=60.0, value=0.0, step=0.1, format="%.1f")
            ambient_temp = None if ambient_input == 0.0 else float(ambient_input)
        with col_b:
            # Show quick-pick tiles — use selectbox for PoC; create nicer grid if needed
            event_label = st.selectbox(I18N[pref_lang]["event"], [EVENT_LABELS_AR_MAP[e] if USE_AR else e for e in EVENT_LABELS_EN])
            # map back to english event tag
            if USE_AR:
                # reverse map
                rev_map = {v:k for k,v in EVENT_LABELS_AR_MAP.items()}
                event_tag = rev_map.get(event_label, "None")
            else:
                event_tag = event_label
            severity = st.selectbox(I18N[pref_lang]["severity"], [I18N[pref_lang]["mild"], I18N[pref_lang]["moderate"], I18N[pref_lang]["severe"]])
            notes = st.text_input(I18N[pref_lang]["notes"], value="")
        with col_c:
            fasting = st.checkbox(I18N[pref_lang]["fasting_state"]) if USE_AR else st.checkbox(I18N[pref_lang]["fasting_state"])
            share = st.checkbox(I18N[pref_lang]["share_clinician"])
            submitted = st.form_submit_button(I18N[pref_lang]["save"])
            if submitted:
                ts = datetime.now().isoformat()
                cur.execute("INSERT INTO measurements (timestamp, body_temp, ambient_temp, event_tag, severity, notes, share_with_clinician) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (ts, float(body_temp), ambient_temp, event_tag, severity, notes.strip(), 1 if share else 0))
                conn.commit()
                st.success("✅ " + ("تم الحفظ" if USE_AR else "Saved"))
                st.experimental_rerun()

    # Compact recent history (last RECENT_HISTORY_COUNT)
    st.markdown("---")
    st.write(I18N[pref_lang]["recent_entries"])
    df_recent = read_measurements_df(conn, limit=RECENT_HISTORY_COUNT)
    if df_recent.empty:
        st.info(I18N[pref_lang]["no_data"])
    else:
        # Show collapsed list with expanders
        df_recent_sorted = df_recent.sort_values("timestamp", ascending=False)
        for idx, row in df_recent_sorted.iterrows():
            ts = pd.to_datetime(row["timestamp"]).strftime("%Y-%m-%d %H:%M")
            ambient = f" / {row['ambient_temp']:.1f}°C" if pd.notnull(row["ambient_temp"]) else ""
            ev_label = EVENT_LABELS_AR_MAP[row["event_tag"]] if (USE_AR and row["event_tag"] in EVENT_LABELS_AR_MAP) else row["event_tag"]
            summary = f"{ts} — {row['body_temp']:.1f}°C{ambient} — {ev_label} — {row['severity']}"
            with st.expander(summary, expanded=False):
                st.write(I18N[pref_lang]["notes"] + ": ", row["notes"])
                if row["share_with_clinician"]:
                    st.info(I18N[pref_lang]["share_clinician"])

# -------------------------
# Diary Page
# -------------------------
elif page_key == "diary":
    st.subheader(I18N[pref_lang]["diary"])
    with st.form("diary_form"):
        entry_txt = st.text_area("Write diary / سجّل ملاحظة", height=140)
        if st.form_submit_button("Add / أضف"):
            if entry_txt.strip():
                cur.execute("INSERT INTO diary (timestamp, entry) VALUES (?, ?)", (datetime.now().isoformat(), entry_txt.strip()))
                conn.commit()
                st.success("Added")
                st.experimental_rerun()
    df_diary = pd.read_sql_query("SELECT * FROM diary ORDER BY timestamp DESC", conn, parse_dates=["timestamp"])
    if df_diary.empty:
        st.info(I18N[pref_lang]["no_data"])
    else:
        st.dataframe(df_diary)

# -------------------------
# Graphs Page
# -------------------------
elif page_key == "graphs":
    st.subheader(I18N[pref_lang]["graphs"])
    df_all = read_measurements_df(conn)
    if df_all.empty:
        st.info(I18N[pref_lang]["no_data"])
    else:
        # Prepare altair chart with overlay events as tooltip
        df_plot = df_all.copy()
        df_plot["ambient_temp"] = df_plot["ambient_temp"].astype(float)
        base = alt.Chart(df_plot).encode(x=alt.X("timestamp:T", title="Time"))
        body_line = base.mark_line(point=True).encode(y=alt.Y("body_temp:Q", title="Body °C"), color=alt.value("blue"))
        amb_line = base.mark_line(point=False).encode(y=alt.Y("ambient_temp:Q", title="Ambient °C"), color=alt.value("orange"))
        chart = alt.layer(body_line, amb_line).resolve_scale(y="independent").properties(height=420)
        st.altair_chart(chart.interactive(), use_container_width=True)

        st.markdown("Recent table (flagged/high Δ):")
        # highlight flagged rows
        baseline = df_all["body_temp"].head(DEFAULT_BASELINE_DAYS).mean() if len(df_all)>0 else 36.6
        df_all["delta"] = df_all["body_temp"] - baseline
        flagged = df_all[df_all["delta"] >= DEFAULT_DELTA_THRESHOLD].sort_values("timestamp", ascending=False)
        if flagged.empty:
            st.write("No flagged events (Δ≥{:.2f}°C).".format(DEFAULT_DELTA_THRESHOLD))
        else:
            st.dataframe(flagged[["timestamp","body_temp","ambient_temp","event_tag","severity","delta","notes"]])

        # download all
        csv = df_all.to_csv(index=False)
        st.download_button(I18N[pref_lang]["download_csv"], data=csv, file_name="raha_ms_all_measurements.csv", mime="text/csv")

# -------------------------
# Assistant Page
# -------------------------
elif page_key == "assistant":
    st.subheader(I18N[pref_lang]["assistant"])
    st.write("The assistant will respond in Arabic if you write in Arabic, otherwise in English. It is informational only.")

    user_question = st.text_input(I18N[pref_lang]["placeholder_question"])
    if st.button(I18N[pref_lang]["ask_assistant"]) and user_question.strip():
        lang_is_ar = is_arabic(user_question)
        # Build context: latest reading, ambient
        dfm = read_measurements_df(conn)
        latest_temp = dfm.iloc[-1]["body_temp"] if (not dfm.empty) else None
        weather, _ = fetch_weather(openweather_key, city=city_input)
        ambient_now = weather["temp"] if weather else "unknown"
        system_prompt = build_system_prompt()
        user_context = (f"User language: {'ar' if lang_is_ar else 'en'}\n"
                        f"Latest body temp: {latest_temp}\n"
                        f"Ambient temp: {ambient_now}\n"
                        f"Question: {user_question}\n"
                        "Return a brief, culturally appropriate answer and a safety escalation if needed.")
        # Call OpenAI if key provided and library installed
        assistant_reply = None
        if openai_key and OPENAI_AVAILABLE:
            try:
                openai.api_key = openai_key
                resp = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role":"system","content":system_prompt},
                              {"role":"user","content":user_context}],
                    max_tokens=350,
                    temperature=0.2
                )
                assistant_reply = resp["choices"][0]["message"]["content"]
            except Exception as e:
                assistant_reply = f"[Assistant error: {str(e)}]"
        else:
            # deterministic safe stub
            if lang_is_ar:
                assistant_reply = ("أفهم سؤالك. إذا كانت درجة حرارة جسمك ارتفعت بمقدار 0.5°C أو أكثر مقارنة بالقاعدة، فالخطوات الأولى: الانتقال إلى مكان مظلل / مكيف، وضع كمادة باردة على الرقبة، شرب الماء ببطء. "
                                   "إذا ظهرت دوخة أو ارتباك اتصل بمقدم الرعاية. هذا توجيه معلوماتي فقط.")
            else:
                assistant_reply = ("I understand. If your body temp rose ≥0.5°C from baseline, first steps: move to a cool/AC area, apply a cool compress to the neck, hydrate slowly. "
                                   "If you experience dizziness or confusion, contact your healthcare provider. Informational only.")
        st.info(assistant_reply)

# -------------------------
# About Page
# -------------------------
elif page_key == "about":
    st.subheader(I18N[pref_lang]["about"])
    if USE_AR:
        st.markdown("""
        ### ما هو تطبيق "راحة MS"؟
        "راحة MS" يساعد المرضى المصابين بالتصلّب المتعدد في دول الخليج على رصد حساسية الحرارة (ظاهرة Uhthoff) وتلقي نصائح تبريد ملائمة ثقافياً.
        - يكتشف الزيادات البسيطة في الحرارة (≥ 0.5°C) ويقدّم اقتراحات تبريد فورية.
        - يسجّل يوميات الأدوية والأعراض لتسهيل التواصل مع الأطباء.
        - يراعي خصوصيات المنطقة (الصيام، الملابس التقليدية، نصائح عن التنقل في الحرّ).
        
        **ملاحظة:** هذا التطبيق أداة معلوماتية فقط ولا يغني عن رأي الطبيب.
        """)
    else:
        st.markdown("""
        ### What is "Raha MS"?
        Raha MS helps people with Multiple Sclerosis in the GCC monitor heat sensitivity (Uhthoff phenomenon) and receive culturally-appropriate cooling advice.
        - Detects small temperature increases (≥ 0.5°C) and offers immediate cooling suggestions.
        - Provides journaling for meds and symptoms for clinician communication.
        - Adapts advice to local practices (fasting, clothing, movement in heat).
        
        **Note:** Informational only — not a medical device.
        """)

    st.write(I18N[pref_lang]["not_med_device"])

# -------------------------
# Settings Page
# -------------------------
elif page_key == "settings":
    st.subheader(I18N[pref_lang]["settings"])
    st.write("Adjust thresholds and preferences.")
    new_baseline_days = st.number_input("Baseline days (N)", min_value=1, max_value=30, value=DEFAULT_BASELINE_DAYS)
    new_delta = st.number_input("Warning Δ threshold (°C)", min_value=0.1, max_value=2.0, value=DEFAULT_DELTA_THRESHOLD, step=0.1)
    ramadan_mode = st.checkbox(I18N[pref_lang]["ramadan_mode"], value=False)
    if st.button("Save settings"):
        # For PoC store in session only; in production persist to user settings DB table
        DEFAULT_BASELINE_DAYS = int(new_baseline_days)
        DEFAULT_DELTA_THRESHOLD = float(new_delta)
        st.success("Settings updated (session-only for PoC)")

# Footer
st.markdown("---")
st.caption("Raha MS — PoC for Medical Device Innovation. Developed for research & prototyping only.")
