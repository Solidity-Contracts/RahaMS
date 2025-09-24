import streamlit as st
import sqlite3
from openai import OpenAI
import requests
import matplotlib.pyplot as plt
from datetime import datetime

# ========== CONFIG ==========
st.set_page_config(page_title="Raha MS", page_icon="☀️", layout="wide")

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
        "temp_monitor": "Temperature Monitor",
        "enter_temp": "Enter your current body temperature (°C):",
        "check_weather": "Check Weather & Save",
        "history": "Temperature History",
        "triggers": "Heat Triggers & Lifestyle Factors",
        "assistant": "AI Assistant",
        "ask": "Ask a question about MS, weather, or health:",
        "journal": "Journal & Medications",
        "add_entry": "Add Journal Entry",
        "logout": "Logout"
    },
    "Arabic": {
        "about_title": "عن تطبيق راحة إم إس",
        "login_title": "تسجيل الدخول / إنشاء حساب",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "login": "تسجيل الدخول",
        "register": "إنشاء حساب",
        "temp_monitor": "مراقبة الحرارة",
        "enter_temp": "أدخل درجة حرارة جسمك الحالية (°م):",
        "check_weather": "تحقق من الطقس واحفظ",
        "history": "سجل درجات الحرارة",
        "triggers": "المحفزات والعوامل",
        "assistant": "المساعد الذكي",
        "ask": "اكتب سؤالك عن التصلب المتعدد أو الطقس أو الصحة:",
        "journal": "اليوميات والأدوية",
        "add_entry": "أضف ملاحظة",
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
def get_weather(city="Abu Dhabi"):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    resp = requests.get(url).json()
    if "main" in resp:
        return resp["main"]["temp"]
    return None

def ai_response(prompt, lang):
    sys_prompt = ("You are Raha MS AI Assistant. "
                  "Provide evidence-based responses for MS, especially heat sensitivity, "
                  "based on trusted guidelines (NMSS, MSIF, Mayo Clinic, UAE MOHAP). "
                  "Always include a short citation of source at the end.")
    if lang == "Arabic":
        sys_prompt += " Please respond in Arabic."
    elif lang == "English":
        sys_prompt += " Please respond in English."
    else:
        sys_prompt += " Respond in the same language as the user."

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
        - **Discover** personal heat triggers (like exercise, hot food, or stress).  
        - **Record** your health journey in a private journal.  
        - **Get support** from the AI Assistant with evidence-based tips.  
        """)

        st.subheader("🤝 Our Goal")
        st.success("To give you simple tools that fit your life, reduce uncertainty, and help you feel more in control.")

        st.caption("Raha MS is an innovation prototype, co-created with the MS community in the Gulf.")
    
    else:  # Arabic version
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
        - **اكتشاف** المحفزات الشخصية للحرارة (مثل الرياضة أو الأطعمة الحارة أو التوتر).  
        - **تسجيل** ملاحظاتك اليومية في دفتر خاص.  
        - **الحصول** على دعم من المساعد الذكي بمعلومات موثوقة.  
        """)

        st.subheader("🤝 هدفنا")
        st.success("أن نمنحك أدوات بسيطة تناسب حياتك اليومية وتخفف من القلق وتمنحك شعورًا أكبر بالتحكم.")

        st.caption("راحة إم إس هو نموذج ابتكاري تم تطويره بالتعاون مع مجتمع مرضى التصلب المتعدد في الخليج.")


# ========== SIDEBAR NAVIGATION ==========

# Display the image using st.image()
# Sidebar Logo
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/6512b826bd06f692ad81f896773b44a3b0482001/logo1.png"
st.sidebar.image(logo_url, use_container_width=True)

#st.sidebar.title("Raha MS")

# Language selection
app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English", "Arabic"])
T = TEXTS[app_language]

# Apply RTL layout if Arabic is chosen
if app_language == "Arabic":
    st.markdown(
        """
        <style>
        /* Make whole app RTL */
        body, .block-container {
            direction: rtl;
            text-align: right;
        }
        /* Sidebar also RTL */
        [data-testid="stSidebar"] {
            direction: rtl;
            text-align: right;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


page = st.sidebar.radio("Navigate", [
    T["about_title"], T["login_title"], T["temp_monitor"], 
    T["triggers"], T["assistant"], T["journal"], T["logout"]
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

# ========== TEMP MONITOR ==========
elif page == T["temp_monitor"]:
    if "user" not in st.session_state:
        st.warning("Please login first.")
    else:
        st.title("☀️ Heat Safety Check")
        st.write("This page helps you understand how the heat may affect your MS symptoms today.")

        # Input section
        body_temp = st.number_input("🌡️ Enter your body temperature (°C):", 30.0, 45.0, 37.0)
        city = st.text_input("🏙️ Enter your city:", "Abu Dhabi")

        if st.button("🔍 Check My Heat Risk"):
            weather = get_weather(city)
            if weather:
                diff = body_temp - weather
                if diff < 0.5:
                    status, color, advice = "Safe", "🟢", "You’re safe! Stay hydrated and enjoy your day."
                elif diff < 1:
                    status, color, advice = "Caution", "🟡", "Be careful: you might notice mild symptoms in this heat."
                else:
                    status, color, advice = "Danger", "🔴", "High risk: avoid heat exposure, stay indoors, and use cooling strategies."

                # Show safety card
                st.markdown(f"""
                <div style="background-color:#f9f9f9;padding:20px;border-radius:15px;
                            border-left:10px solid {'green' if status=='Safe' else 'orange' if status=='Caution' else 'red'};">
                <h3>{color} Status: {status}</h3>
                <p>{advice}</p>
                <p><b>Weather:</b> {weather} °C | <b>Your body:</b> {body_temp} °C</p>
                </div>
                """, unsafe_allow_html=True)

                # Save to DB
                c.execute("INSERT INTO temps VALUES (?,?,?,?,?)",
                          (st.session_state["user"], str(datetime.now()), body_temp, weather, status))
                conn.commit()

                # Interactive heat map
                try:
                    import folium
                    from streamlit_folium import st_folium
                    geocode_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
                    geo_resp = requests.get(geocode_url).json()
                    if geo_resp:
                        lat, lon = geo_resp[0]["lat"], geo_resp[0]["lon"]
                        m = folium.Map(location=[lat, lon], zoom_start=10)
                        folium.Marker([lat, lon], popup=f"{city}: {weather} °C").add_to(m)
                        st.subheader("🗺️ Heat Map of Your Location")
                        st_folium(m, width=700, height=500)
                except Exception as e:
                    st.warning("Map could not be loaded. Please install `folium` and `streamlit-folium`.")

        # Historical trends
        st.subheader("📈 Your Heat Trends")
        c.execute("SELECT date, body_temp, weather_temp, status FROM temps WHERE username=?",
                  (st.session_state["user"],))
        rows = c.fetchall()
        if rows:
            dates, bt, wt, status = zip(*rows)
            fig, ax = plt.subplots()
            ax.plot(dates, bt, label="Body Temp", marker="o")
            ax.plot(dates, wt, label="Weather Temp", marker="s")
            ax.set_ylabel("Temperature (°C)")
            ax.set_xlabel("Date")
            ax.legend()
            st.pyplot(fig)

            # Color-coded timeline
            st.subheader("🕒 Past Safety Checks")
            for d, s in zip(dates, status):
                icon = "🟢" if s=="Safe" else "🟡" if s=="Caution" else "🔴"
                st.write(f"{icon} {d}: {s}")


# ========== TRIGGERS ==========
elif page == T["triggers"]:
    if "user" not in st.session_state:
        st.warning("Please login first.")
    else:
        st.title(T["triggers"])
        st.write("✅ Exercise, sauna, spicy food, hot drinks, hormonal cycle, fever, direct sun exposure.")
        st.write("You can use this page to reflect on what factors worsened your symptoms.")

# ========== AI ASSISTANT ==========
elif page == T["assistant"]:
    if "user" not in st.session_state:
        st.warning("Please login first.")
    else:
        st.title(T["assistant"])
        query = st.text_area(T["ask"])
        if st.button("Send"):
            reply = ai_response(query, app_language)
            st.write(reply)

# ========== JOURNAL ==========
elif page == T["journal"]:
    if "user" not in st.session_state:
        st.warning("Please login first.")
    else:
        st.title(T["journal"])
        entry = st.text_area(T["add_entry"])
        if st.button("Save"):
            c.execute("INSERT INTO journal VALUES (?,?,?)",
                      (st.session_state["user"], str(datetime.now()), entry))
            conn.commit()
            st.success("✅ Saved")

        c.execute("SELECT date, entry FROM journal WHERE username=?", (st.session_state["user"],))
        rows = c.fetchall()
        for r in rows:
            st.write(f"📅 {r[0]} → {r[1]}")

# ========== LOGOUT ==========
elif page == T["logout"]:
    st.session_state.pop("user", None)
    st.success("✅ Logged out!")
