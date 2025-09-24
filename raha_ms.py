import streamlit as st
import sqlite3
from openai import OpenAI
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

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
        "temp_monitor": "Heat Safety Dashboard",
        "community": "Community Resources",
        "journal": "Journal & Medications",
        "logout": "Logout",
        "add_entry": "Add Journal Entry",
        "ask": "Ask a question about MS, weather, or health:"
    },
    "Arabic": {
        "about_title": "عن تطبيق راحة إم إس",
        "login_title": "تسجيل الدخول / إنشاء حساب",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "login": "تسجيل الدخول",
        "register": "إنشاء حساب",
        "temp_monitor": "لوحة سلامة الحرارة",
        "community": "موارد المجتمع",
        "journal": "اليوميات والأدوية",
        "logout": "تسجيل الخروج",
        "add_entry": "أضف ملاحظة",
        "ask": "اكتب سؤالك عن التصلب المتعدد أو الطقس أو الصحة:"
    }
}

# ========== DATABASE ==========
conn = sqlite3.connect("raha_ms.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS temps(username TEXT, date TEXT, body_temp REAL, weather_temp REAL, status TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS journal(username TEXT, date TEXT, entry TEXT)""")
conn.commit()

# ========== HELPER FUNCTIONS ==========
def get_weather_with_coords(place="Abu Dhabi,AE"):
    if not OPENWEATHER_API_KEY:
        return None, "Missing OpenWeather API key."
    try:
        params = {"q": place, "appid": OPENWEATHER_API_KEY, "units": "metric"}
        r = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=6)
        r.raise_for_status()
        j = r.json()
        temp = float(j["main"]["temp"])
        desc = j["weather"][0]["description"]
        lat = j.get("coord", {}).get("lat")
        lon = j.get("coord", {}).get("lon")
        return {"temp": temp, "desc": desc, "lat": lat, "lon": lon, "raw": j}, None
    except Exception as e:
        return None, str(e)

def get_forecast(place="Abu Dhabi,AE"):
    try:
        params = {"q": place, "appid": OPENWEATHER_API_KEY, "units": "metric"}
        r = requests.get("https://api.openweathermap.org/data/2.5/forecast", params=params, timeout=6)
        r.raise_for_status()
        j = r.json()
        forecast_list = []
        for item in j["list"][:8]:  # next 24 hours, 3h interval
            dt_txt = item["dt_txt"]
            temp = float(item["main"]["temp"])
            desc = item["weather"][0]["description"]
            forecast_list.append({"datetime": dt_txt, "temp": temp, "desc": desc})
        return forecast_list, None
    except Exception as e:
        return None, str(e)

def ai_response(prompt, lang):
    sys_prompt = ("You are Raha MS AI Assistant. "
                  "Provide evidence-based responses for MS, especially heat sensitivity, "
                  "based on trusted guidelines (NMSS, MSIF, Mayo Clinic, UAE MOHAP). "
                  "Always include a short citation at the end.")
    if lang == "Arabic":
        sys_prompt += " Please respond in Arabic."
    elif lang == "English":
        sys_prompt += " Please respond in English."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def render_about_page(lang="English"):
    if lang=="English":
        st.title("🧠 Welcome to Raha MS")
        st.markdown("""
        Living with **Multiple Sclerosis (MS)** in the GCC can be challenging due to intense heat.  
        Raha MS provides tools to **track heat risk, log symptoms, and get culturally relevant advice**.
        """)
        st.info("Even a small rise in body temperature (0.5°C) can temporarily worsen MS symptoms — Uhthoff’s phenomenon.")
    else:
        st.title("🧠 مرحبًا بك في راحة إم إس")
        st.markdown("""
        العيش مع **التصلب المتعدد (MS)** في الخليج صعب بسبب الحرارة الشديدة.  
        يوفر تطبيق راحة إم إس أدوات **لمتابعة مخاطر الحرارة، تسجيل الأعراض، والحصول على نصائح ملائمة ثقافيًا**.
        """)
        st.info("ارتفاع درجة حرارة الجسم حتى 0.5°م قد يزيد أعراض التصلب المتعدد مؤقتًا — ظاهرة أوتهوف.")

# ========== SIDEBAR ==========
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/6512b826bd06f692ad81f896773b44a3b0482001/logo1.png"
st.sidebar.image(logo_url, use_container_width=True)

app_language = st.sidebar.selectbox("🌐 Language / اللغة", ["English", "Arabic"])
T = TEXTS[app_language]

if app_language == "Arabic":
    st.markdown("""
    <style>
    body, .block-container { direction: rtl; text-align: right; }
    [data-testid="stSidebar"] { direction: rtl; text-align: right; }
    </style>""", unsafe_allow_html=True)

page = st.sidebar.radio("Navigate", [
    T["about_title"], T["login_title"], T["temp_monitor"], T["community"], T["journal"], T["logout"]
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

# ========== HEAT SAFETY DASHBOARD ==========
elif page == T["temp_monitor"]:
    if "user" not in st.session_state:
        st.warning("Please login first.")
    else:
        st.title("☀️ " + T["temp_monitor"])
        st.write("Track your heat risk, log triggers, and get advice.")

        col1, col2 = st.columns([3,1])
        with col1:
            body_temp = st.number_input("🌡️ Body Temp (°C):", 30.0, 45.0, 37.0)
            city = st.text_input("🏙️ City (City,CC):", "Abu Dhabi,AE")
            triggers = st.multiselect("✅ Today's triggers:", 
                                     ["Exercise","Sauna","Spicy food","Hot drinks","Stress","Direct sun","Fever","Hormonal cycle"])
        with col2:
            st.write("⚠️ Threshold: 0.5°C difference")
            check_btn = st.button("🔍 Check Heat Risk")

        if check_btn:
            weather, err = get_weather_with_coords(city)
            forecast, f_err = get_forecast(city)
            if weather is None:
                st.error(f"Weather lookup failed: {err}")
            else:
                diff = body_temp - weather["temp"]
                if diff < 0.5:
                    status, border, icon, advice = "Safe","green","🟢","Stay hydrated and enjoy your day."
                elif diff < 1.0:
                    status, border, icon, advice = "Caution","orange","🟡","Mild symptoms possible. Limit outdoor activity."
                else:
                    status, border, icon, advice = "Danger","red","🔴","High risk: avoid heat, rest in cool spaces."

                st.session_state["last_check"] = {
                    "city": city, "body_temp": body_temp, "weather_temp": weather["temp"],
                    "weather_desc": weather["desc"], "status": status, "border": border,
                    "icon": icon, "advice": advice, "triggers": triggers,
                    "forecast": forecast, "time": datetime.utcnow().isoformat()
                }

                # save to DB
                try:
                    c.execute("INSERT INTO temps VALUES (?,?,?,?,?)",
                              (st.session_state["user"], str(datetime.now()), body_temp, weather["temp"], status))
                    conn.commit()
                except: pass
                st.success(f"{icon} {status} — {advice}")

        if st.session_state.get("last_check"):
            last = st.session_state["last_check"]
            st.markdown(f"""
            <div style="background:#fff;padding:18px;border-radius:12px;border-left:10px solid {last['border']};
                        box-shadow:0 2px 6px rgba(0,0,0,0.06);">
            <h3>{last['icon']} <strong>{last['status']}</strong></h3>
            <p>{last['advice']}</p>
            <p><small>Weather ({last['city']}): {last['weather_temp']} °C — {last['weather_desc']}</small></p>
            <p><small>Your body: {last['body_temp']} °C • checked at {last['time']}</small></p>
            <p><small>Triggers today: {', '.join(last['triggers']) if last['triggers'] else 'None'}</small></p>
            </div>
            """, unsafe_allow_html=True)

            # Forecast table
            if last.get("forecast"):
                st.subheader("🌤️ Forecast next 24h / توقعات 24 ساعة القادمة")
                for f in last["forecast"]:
                    st.write(f"{f['datetime']}: {f['temp']} °C — {f['desc']}")

            # AI personalized advice
            st.subheader("🤖 Personalized Advice")
            if st.button("Get Personalized Advice"):
                prompt = (f"My body temp is {last['body_temp']}°C, weather in {last['city']} is {last['weather_temp']}°C "
                          f"({last['weather_desc']}), triggers: {', '.join(last['triggers'])}. What precautions for MS today?")
                advice_text = ai_response(prompt, app_language)
                st.info(advice_text)

# ========== COMMUNITY RESOURCES ==========
elif page == T["community"]:
    if "user" not in st.session_state:
        st.warning("Please login first.")
    else:
        st.title("🌍 " + T["community"])
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🥛 Drinks / مشروبات")
            st.markdown("- Laban, mint water, hibiscus, fresh fruits")
            st.subheader("🍽️ Food / الطعام")
            st.markdown("- Light meals, hydrating foods, avoid hot/spicy heavy meals")
            st.subheader("👗 Clothing / الملابس")
            st.markdown("- Loose, light-colored, breathable fabrics, avoid peak sun")
        with col2:
            st.subheader("🏠 Home / المنزل")
            st.markdown("- Fans, AC, cold compresses, rest in shaded areas")
            st.subheader("🌿 Herbs / الأعشاب")
            st.markdown("- Mint, basil, hibiscus, rose water cold drinks")
            st.subheader("🏥 UAE Health / الصحة")
            st.markdown("- MS clinics: Mediclinic Dubai, Burjeel Abu Dhabi, MOHAP guidelines, cooling products")
        with st.expander("💡 Cultural Notes / ملاحظات ثقافية"):
            st.markdown("- Drinking laban in afternoons is traditional. Herbs like mint/basil are cooling. Avoid heat during midday prayer outdoors.")

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
