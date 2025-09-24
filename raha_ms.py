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
        "about_desc": """**Raha MS** is designed to support people living with Multiple Sclerosis (MS) in the GCC region.  
Heat sensitivity, known as **Uhthoff’s phenomenon**, can worsen MS symptoms with just a 0.5°C rise in body temperature.  
The GCC’s hot and humid climate makes this especially challenging.  
This app helps monitor temperature, log triggers, provide coping strategies, and offer AI support.  

**References:**  
- National MS Society: Heat & Temperature Sensitivity  
- MS International Federation  
- Mayo Clinic MS Guidelines  
""",
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
        "about_desc": """تم تصميم **راحة إم إس** لمساعدة مرضى التصلب المتعدد في منطقة الخليج.  
حساسية الحرارة، المعروفة باسم **ظاهرة أوتهوف**، يمكن أن تزيد الأعراض سوءًا بارتفاع طفيف في درجة حرارة الجسم (0.5 درجة مئوية).  
وبسبب المناخ الحار والرطب في الخليج، فإن هذه المشكلة أكثر بروزًا.  
يتيح التطبيق مراقبة درجة الحرارة، وتسجيل المحفزات، وتقديم استراتيجيات للتكيف، بالإضافة إلى مساعد ذكي.  

**المراجع:**  
- الجمعية الوطنية للتصلب المتعدد: حساسية الحرارة  
- الاتحاد الدولي للتصلب المتعدد  
- مايو كلينك: إرشادات التصلب المتعدد  
""",
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

# ========== SIDEBAR NAVIGATION ==========

# Display the image using st.image()
# Sidebar Logo
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/6512b826bd06f692ad81f896773b44a3b0482001/logo1.png"
st.sidebar.image(logo_url, use_container_width=True)

#st.sidebar.title("Raha MS")

# Language selection
app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English", "Arabic"])
T = TEXTS[app_language]

page = st.sidebar.radio("Navigate", [
    T["about_title"], T["login_title"], T["temp_monitor"], 
    T["triggers"], T["assistant"], T["journal"], T["logout"]
])

# ========== ABOUT ==========
if page == T["about_title"]:
    st.title(T["about_title"])
    st.markdown(T["about_desc"])

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
        st.title(T["temp_monitor"])
        body_temp = st.number_input(T["enter_temp"], 30.0, 45.0, 37.0)
        city = st.text_input("City", "Abu Dhabi")

        if st.button(T["check_weather"]):
            weather = get_weather(city)
            if weather:
                diff = body_temp - weather
                status = "Safe" if diff < 0.5 else "Caution" if diff < 1 else "Danger"
                st.write(f"🌡️ Weather: {weather} °C | Body: {body_temp} °C → Status: **{status}**")

                c.execute("INSERT INTO temps VALUES (?,?,?,?,?)",
                          (st.session_state["user"], str(datetime.now()), body_temp, weather, status))
                conn.commit()

        st.subheader(T["history"])
        c.execute("SELECT date, body_temp, weather_temp, status FROM temps WHERE username=?",
                  (st.session_state["user"],))
        rows = c.fetchall()
        if rows:
            dates, bt, wt, status = zip(*rows)
            fig, ax = plt.subplots()
            ax.plot(dates, bt, label="Body Temp")
            ax.plot(dates, wt, label="Weather Temp")
            ax.legend()
            st.pyplot(fig)

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
