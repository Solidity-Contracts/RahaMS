import streamlit as st
import sqlite3
from openai import OpenAI
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# ========== CONFIG ==========
st.set_page_config(page_title="Raha MS", page_icon="🌡️", layout="wide")

# Load API keys from secrets.toml
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
OPENWEATHER_API_KEY = st.secrets["OPENWEATHER_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

# ========== TRANSLATION DICTIONARY ==========
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
        "logout": "Logout"
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
        "logout": "تسجيل الخروج"
    }
}

# ========== DATABASE ==========
conn = sqlite3.connect("raha_ms.db")
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
    status TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS journal(
    username TEXT,
    date TEXT,
    entry TEXT
)""")
conn.commit()

# ========== HELPER FUNCTIONS ==========
def get_weather_with_coords(city="Abu Dhabi,AE"):
    try:
        params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"}
        r = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=6)
        r.raise_for_status()
        j = r.json()
        temp = float(j["main"]["temp"])
        desc = j["weather"][0]["description"]
        lat = j.get("coord", {}).get("lat")
        lon = j.get("coord", {}).get("lon")
        # Forecast 24h & 48h
        f_params = {"lat": lat, "lon": lon, "exclude":"current,minutely,alerts", "appid": OPENWEATHER_API_KEY, "units":"metric"}
        f_r = requests.get("https://api.openweathermap.org/data/2.5/onecall", params=f_params)
        f_r.raise_for_status()
        f_j = f_r.json()
        forecast_24 = f_j["hourly"][0:24]
        forecast_48 = f_j["hourly"][0:48]
        return {"temp": temp, "desc": desc, "lat": lat, "lon": lon, "forecast_24": forecast_24, "forecast_48": forecast_48}, None
    except Exception as e:
        return None, str(e)

def ai_response(prompt, lang):
    sys_prompt = ("You are Raha MS AI Companion. "
                  "Analyze the user's temperature, triggers, journal entries, and forecast. "
                  "Provide culturally relevant, practical MS heat safety advice for Arab users. "
                  "Base on NMSS, MSIF, Mayo Clinic, UAE MOHAP. ")
    if lang == "Arabic":
        sys_prompt += "Respond in Arabic."
    else:
        sys_prompt += "Respond in English."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def render_about_page(app_language: str = "English"):
    if app_language == "English":
        st.title("🧠 Welcome to Raha MS")
        st.markdown("""
        Living with **Multiple Sclerosis (MS)** in the GCC can be uniquely challenging, especially with the region’s intense heat.  
        Raha MS was designed **with and for people living with MS** — to bring comfort, awareness, and support to your daily life.
        """)
        
        st.subheader("🌡️ Why Heat Matters in MS")
        st.info("Even a small rise in body temperature (just 0.5°C) can temporarily worsen MS symptoms — this is known as **Uhthoff’s phenomenon**.")

        st.subheader("✨ What This App Offers You")
        st.markdown("""
        - **Track** your body temperature and local weather.  
        - **Discover** personal heat triggers (exercise, hot food, stress, etc.).  
        - **Record** symptoms and health journey in a private journal.  
        - **Get support** from the AI Companion with culturally tailored advice.    
        """)

        st.subheader("🤝 Our Goal")
        st.success("To give you simple tools that fit your life, reduce uncertainty, and help you feel more in control.")

        st.caption("Raha MS is an innovation prototype, co-created with the MS community in the Gulf.")
    
    else:  # Arabic
        st.title("🧠 مرحبًا بك في راحة إم إس")
        st.markdown("""
        إن العيش مع **التصلب المتعدد (MS)** في الخليج قد يكون صعبًا بسبب الحرارة الشديدة.  
        تم تصميم تطبيق راحة إم إس **بالتعاون مع مرضى التصلب المتعدد** ليمنحك راحة ووعيًا ودعمًا في حياتك اليومية.
        """)

        st.subheader("🌡️ لماذا تؤثر الحرارة؟")
        st.info("حتى الارتفاع البسيط في درجة حرارة الجسم (0.5°م فقط) قد يزيد أعراض التصلب المتعدد مؤقتًا — ويعرف ذلك بـ **ظاهرة أوتهوف**.")

        st.subheader("✨ ما الذي يقدمه التطبيق؟")
        st.markdown("""
        - **مراقبة** درجة حرارة جسمك والطقس من حولك.  
        - **اكتشاف** المحفزات الشخصية للحرارة (رياضة، طعام حار، توتر...).  
        - **تسجيل** الأعراض واليوميات في دفتر خاص.  
        - **الحصول** على دعم من المساعد الذكي بنصائح متناسبة ثقافيًا.  
        """)

        st.subheader("🤝 هدفنا")
        st.success("أن نمنحك أدوات بسيطة تناسب حياتك اليومية وتخفف من القلق وتمنحك شعورًا أكبر بالتحكم.")

        st.caption("راحة إم إس هو نموذج ابتكاري تم تطويره بالتعاون مع مجتمع مرضى التصلب المتعدد في الخليج.")


# ========== SIDEBAR ==========
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/6512b826bd06f692ad81f896773b44a3b0482001/logo1.png"
st.sidebar.image(logo_url, use_container_width=True)

app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English", "Arabic"])
T = TEXTS[app_language]

if app_language == "Arabic":
    st.markdown("""
    <style>
    body, .block-container {direction: rtl;text-align: right;}
    [data-testid="stSidebar"] {direction: rtl;text-align: right;}
    </style>
    """, unsafe_allow_html=True)

page = st.sidebar.radio("Navigate", [
    T["about_title"], T["login_title"], T["temp_monitor"], T["journal"], T["logout"]
])

# ========== ABOUT ==========
if page == T["about_title"]:
    render_about_page(app_language)

# ========== LOGIN ==========
elif page == T["login_title"]:
    st.title(T["login_title"])
    username = st.text_input(T["username"])
    password = st.text_input(T["password"], type="password")

    if st.button(T["login"]):
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        if c.fetchone():
            st.session_state["user"] = username
            st.success("✅ Logged in!")
        else:
            st.error("❌ Invalid credentials")

    if st.button(T["register"]):
        try:
            c.execute("INSERT INTO users VALUES (?,?)", (username, password))
            conn.commit()
            st.success("✅ Account created! Please login.")
        except:
            st.error("❌ Username already exists")

# ========== HEAT DASHBOARD ==========
elif page == T["temp_monitor"]:
    if "user" not in st.session_state:
        st.warning("Please login first.")
    else:
        st.title("☀️ Heat Safety Dashboard")
        st.write("🤖 Your Smart Heat Companion: AI analyzes your temperature, forecast, triggers, and journal entries to give culturally tailored MS heat safety advice.")

        colL, colR = st.columns([3,1])
        with colL:
            body_temp = st.number_input("🌡️ Enter your body temperature (°C):", 30.0, 45.0, 37.0)
            city = st.text_input("🏙️ City (City,CC)", value="Abu Dhabi,AE")
            triggers = st.multiselect(
                "✅ Today I did / experienced:",
                ["Exercise", "Sauna", "Spicy food", "Hot drinks", "Stress", "Direct sun exposure", "Fever", "Hormonal cycle"]
            )
            symptoms = st.multiselect(
                "⚕️ Symptoms experienced today:",
                ["Blurred vision","Fatigue","Muscle weakness","Numbness","Coordination issues","Mental fog"]
            )

        with colR:
            delta_setting = 0.5
            check_btn = st.button("🔍 Check My Heat Risk")

        if check_btn:
            weather, err = get_weather_with_coords(city)
            if weather is None:
                st.error(f"Weather lookup failed: {err}")
            else:
                diff = float(body_temp) - float(weather["temp"])
                if diff < delta_setting:
                    status = "Safe"; border = "green"; icon = "🟢"; advice = "You’re safe. Stay hydrated and enjoy your day."
                elif diff < (delta_setting + 0.5):
                    status = "Caution"; border = "orange"; icon = "🟡"; advice = "Caution: mild symptoms possible. Limit outdoor activity and use cooling strategies."
                else:
                    status = "Danger"; border = "red"; icon = "🔴"; advice = "High risk: avoid heat, rest in cooled spaces, use cooling packs, contact your clinician if severe symptoms occur."

                st.session_state["last_check"] = {
                    "city": city, "body_temp": body_temp, "weather_temp": weather["temp"],
                    "weather_desc": weather.get("desc",""), "status": status, "border": border,
                    "icon": icon, "advice": advice, "triggers": triggers, "symptoms": symptoms,
                    "forecast_24": weather["forecast_24"], "forecast_48": weather["forecast_48"],
                    "time": datetime.utcnow().isoformat()
                }

                # Save to DB
                try:
                    c.execute("INSERT INTO temps VALUES (?,?,?,?,?)",
                              (st.session_state["user"], str(datetime.now()), body_temp, float(weather["temp"]), status))
                    conn.commit()
                except Exception as e:
                    st.warning(f"Could not save to DB: {e}")

                st.success(f"{icon} {status} — {advice}")

        if st.session_state.get("last_check"):
            last = st.session_state["last_check"]
            triggers_text = ', '.join(last['triggers']) if last['triggers'] else 'None'
            symptoms_text = ', '.join(last['symptoms']) if last['symptoms'] else 'None'

            st.markdown(f"""
<div style="background:#fff;padding:18px;border-radius:12px;border-left:10px solid {last['border']};box-shadow:0 2px 6px rgba(0,0,0,0.06);">
<h3 style="margin:0">{last['icon']} <strong>Status: {last['status']}</strong></h3>
<p style="margin:6px 0 0 0">{last['advice']}</p>
<p style="margin:6px 0 0 0"><small>Weather ({last['city']}): {last['weather_temp']} °C — {last['weather_desc']}</small></p>
<p style="margin:6px 0 0 0"><small>Your body: {last['body_temp']} °C • checked at {last['time']}</small></p>
<p style="margin:6px 0 0 0"><small>Triggers today: {triggers_text}</small></p>
<p style="margin:6px 0 0 0"><small>Symptoms today: {symptoms_text}</small></p>
</div>
""", unsafe_allow_html=True)

            # Graph
            st.subheader("📈 Recent temperature trend")
            c.execute("SELECT date, body_temp, weather_temp, status FROM temps WHERE username=? ORDER BY date DESC LIMIT 20",
                      (st.session_state["user"],))
            rows = c.fetchall()
            if rows:
                rows = rows[::-1]
                dates = [r[0] for r in rows]
                bt = [r[1] for r in rows]
                wt = [r[2] for r in rows]
                status_colors = ["green" if r[3]=="Safe" else "orange" if r[3]=="Caution" else "red" for r in rows]

                fig, ax = plt.subplots(figsize=(8,3))
                ax.plot(dates, bt, marker='o', label="Body Temp", color="tab:blue")
                ax.plot(dates, wt, marker='s', label="Weather Temp", color="tab:orange")
                for i, color in enumerate(status_colors):
                    ax.scatter(i, bt[i], s=100, color=color, edgecolor="black", zorder=5)
                ax.set_xticks(range(len(dates)))
                ax.set_xticklabels(dates, rotation=30, fontsize=8)
                ax.set_ylabel("°C")
                ax.legend()
                st.pyplot(fig)

            # AI advice
            st.subheader("🤖 Personalized Heat Advice")
            if st.button("Get AI Advice"):
                user_prompt = f"My body temp: {last['body_temp']}°C, weather: {last['weather_temp']}°C ({last['weather_desc']}), triggers: {triggers_text}, symptoms: {symptoms_text}. Forecast next 48h: {last['forecast_48']}. Provide culturally tailored advice for Arab MS patient."
                advice_text = ai_response(user_prompt, app_language)
                st.info(advice_text)

# ========== JOURNAL ==========
elif page == T["journal"]:
    if "user" not in st.session_state:
        st.warning("Please login first.")
    else:
        st.title(T["journal"])
        st.write("Write short blocks of text for your symptoms, observations, or thoughts. The AI uses this to provide better advice.")

        entry_blocks = st.text_area("Add entry (separate blocks with line breaks)")
        if st.button("Save"):
            if entry_blocks.strip():
                lines = [line.strip() for line in entry_blocks.split("\n") if line.strip()]
                for line in lines:
                    c.execute("INSERT INTO journal VALUES (?,?,?)", (st.session_state["user"], str(datetime.now()), line))
                conn.commit()
                st.success("✅ Saved")

        # Display existing entries
        c.execute("SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC", (st.session_state["user"],))
        rows = c.fetchall()
        for r in rows:
            st.write(f"📅 {r[0]} → {r[1]}")

# ========== LOGOUT ==========
elif page == T["logout"]:
    st.session_state.pop("user", None)
    st.success("✅ Logged out!")
