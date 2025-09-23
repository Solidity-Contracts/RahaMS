import streamlit as st
import datetime
import matplotlib.pyplot as plt
import random
import sqlite3
import openai
import requests

# --- CONFIG ---
st.set_page_config(
    page_title="Raha MS",
    page_icon="☀️",
    layout="wide",
)

# Load API keys from .streamlit/secrets.toml
openai.api_key = st.secrets["OPENAI_API_KEY"]
weather_api_key = st.secrets["OPENWEATHER_API_KEY"]

# --- DATABASE SETUP ---
conn = sqlite3.connect("raha_ms.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS temperature_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    weather_temp REAL,
    body_temp REAL,
    status TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    medications TEXT,
    notes TEXT
)
""")
conn.commit()

# --- AUTHENTICATION ---
users = {"demo": "password123", "admin": "raha2025"}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login to Raha MS")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in users and users[username] == password:
            st.session_state.logged_in = True
            st.success("✅ Login successful!")
        else:
            st.error("❌ Invalid username or password")
    st.stop()

# --- SIDEBAR NAVIGATION ---
pages = ["Home", "Temperature Tracker", "AI Assistant", "Cooling Strategies", "Journal", "About"]
page = st.sidebar.radio("Navigate", pages)

# --- HOME PAGE ---
if page == "Home":
    st.title("☀️ Raha MS")
    st.subheader("Managing Heat Sensitivity in Multiple Sclerosis across the GCC")
    st.markdown("""
    Raha MS is designed for people living with Multiple Sclerosis (MS) in the Gulf region, 
    where high temperatures can worsen symptoms due to heat sensitivity (Uhthoff’s phenomenon).
    
    This app helps track temperature, provides cooling strategies, and enables journaling for better MS management.
    """)

# --- TEMPERATURE TRACKER ---
elif page == "Temperature Tracker":
    st.header("🌡️ Track Your Temperature")

    city = st.text_input("Enter your GCC city:", "Dubai")
    if st.button("Fetch Weather"):
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={weather_api_key}&units=metric"
        res = requests.get(url).json()
        if "main" in res:
            weather_temp = res["main"]["temp"]
            st.info(f"🌤 Current weather in {city}: {weather_temp} °C")
        else:
            st.error("City not found or API error.")

    body_temp = st.number_input("Enter your current body temperature (°C):", 35.0, 42.0, 37.0)

    if st.button("Log Temperature"):
        status = "Elevated" if body_temp - 37.0 >= 0.5 else "Stable"
        c.execute("INSERT INTO temperature_log (date, weather_temp, body_temp, status) VALUES (?, ?, ?, ?)",
                  (str(datetime.date.today()), weather_temp if 'weather_temp' in locals() else None, body_temp, status))
        conn.commit()
        st.success("✅ Temperature logged!")

    # Show history
    st.subheader("📈 Temperature History")
    logs = c.execute("SELECT date, weather_temp, body_temp, status FROM temperature_log ORDER BY id DESC LIMIT 10").fetchall()
    if logs:
        st.table(logs)

# --- AI ASSISTANT ---
elif page == "AI Assistant":
    st.header("🤖 Raha Assistant")
    st.markdown("Ask me about the weather, cooling strategies, or advice on MS in the GCC.")

    user_input = st.text_input("Type your question:")

    if user_input:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Raha, an AI assistant for people with MS in the GCC. You provide culturally relevant, supportive, and medically safe responses. Reply in Arabic if the question is in Arabic."},
                {"role": "user", "content": user_input},
            ]
        )
        reply = response["choices"][0]["message"]["content"]
        st.write("**Raha Assistant:**", reply)

# --- COOLING STRATEGIES ---
elif page == "Cooling Strategies":
    st.header("❄️ Cooling & Heat Management")
    st.markdown("Common heat triggers for MS symptoms include:")
    triggers = [
        "Exercise and physical activity",
        "Hot weather and humidity",
        "Spicy food",
        "Saunas and hot baths",
        "Hormonal changes (e.g., during menstrual cycle)",
        "Fever or illness",
        "Tight or heavy clothing",
    ]
    for t in triggers:
        st.markdown(f"- {t}")

    st.subheader("Cooling Tips:")
    tips = [
        "Stay hydrated with cold water",
        "Use cooling vests or scarves",
        "Avoid peak afternoon heat",
        "Use air conditioning indoors",
        "Take lukewarm showers instead of hot",
        "Rest in shaded or air-conditioned places",
    ]
    for tip in tips:
        st.success(tip)

# --- JOURNAL ---
elif page == "Journal":
    st.header("📔 Personal Journal")
    date = st.date_input("Date", datetime.date.today())
    meds = st.text_area("Medications taken (including herbal remedies):")
    notes = st.text_area("Notes on how you felt today:")

    if st.button("Save Entry"):
        c.execute("INSERT INTO journal (date, medications, notes) VALUES (?, ?, ?)",
                  (str(date), meds, notes))
        conn.commit()
        st.success("✅ Journal entry saved.")

    st.subheader("📖 Journal History")
    entries = c.execute("SELECT date, medications, notes FROM journal ORDER BY id DESC LIMIT 5").fetchall()
    if entries:
        st.table(entries)

# --- ABOUT PAGE ---
elif page == "About":
    st.header("ℹ️ About Raha MS")
    st.markdown("""
    **Why this app?**

    Multiple Sclerosis (MS) patients often experience heat sensitivity, known as Uhthoff’s phenomenon. Even a small increase of **0.5°C** in body temperature can temporarily worsen symptoms.

    **Why the GCC?**

    The Gulf region has extremely high temperatures, making heat sensitivity a serious daily challenge for people with MS. Yet, most MS apps focus on Western populations and do not address heat as a major factor.

    **Our Goal:**
    Raha MS provides culturally relevant, accessible, and GCC-focused tools to help people with MS manage their condition more effectively.
    """)
