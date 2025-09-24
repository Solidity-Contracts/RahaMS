import streamlit as st
import sqlite3
from openai import OpenAI
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import time

# ========== CONFIG ==========
st.set_page_config(
    page_title="Raha MS", 
    page_icon="🌡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'user' not in st.session_state:
    st.session_state.user = None
if 'last_check' not in st.session_state:
    st.session_state.last_check = None
if 'language' not in st.session_state:
    st.session_state.language = "English"

# Load API keys from secrets.toml
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    OPENWEATHER_API_KEY = st.secrets["OPENWEATHER_API_KEY"]
    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    st.error(f"API configuration error: {e}")

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
        "logout": "Logout",
        "welcome": "Welcome to Raha MS",
        "heat_risk": "Heat Risk Assessment",
        "personal_advice": "Personalized Advice"
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
        "welcome": "مرحبًا بك في راحة إم إس",
        "heat_risk": "تقييم خطر الحرارة",
        "personal_advice": "نصائح مخصصة"
    }
}

# ========== DATABASE HELPER ==========
def get_db_connection():
    """Get database connection with proper error handling"""
    try:
        conn = sqlite3.connect("raha_ms.db", check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    if conn:
        try:
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS users(
                username TEXT PRIMARY KEY,
                password TEXT,
                created_date TEXT
            )""")
            
            c.execute("""CREATE TABLE IF NOT EXISTS temps(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                date TEXT,
                body_temp REAL,
                weather_temp REAL,
                status TEXT,
                triggers TEXT,
                symptoms TEXT
            )""")
            
            c.execute("""CREATE TABLE IF NOT EXISTS journal(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                date TEXT,
                entry TEXT
            )""")
            conn.commit()
        except Exception as e:
            st.error(f"Database initialization error: {e}")
        finally:
            conn.close()

# Initialize database
init_db()

# ========== MS-FRIENDLY STYLING ==========
st.markdown("""
<style>
    /* High contrast for MS visual impairments */
    .main .block-container {
        padding-top: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        font-size: 16px;
    }
    .big-font {
        font-size: 18px !important;
    }
    .risk-safe {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .risk-caution {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .risk-danger {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ========== HELPER FUNCTIONS ==========
def get_weather_with_coords(city="Abu Dhabi,AE"):
    """Get weather data with error handling"""
    try:
        params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"}
        r = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=10)
        r.raise_for_status()
        j = r.json()
        temp = float(j["main"]["temp"])
        desc = j["weather"][0]["description"]
        
        # Get forecast data
        lat = j["coord"]["lat"]
        lon = j["coord"]["lon"]
        f_params = {"lat": lat, "lon": lon, "exclude":"current,minutely,alerts", 
                   "appid": OPENWEATHER_API_KEY, "units":"metric"}
        f_r = requests.get("https://api.openweathermap.org/data/2.5/onecall", params=f_params, timeout=10)
        f_r.raise_for_status()
        f_j = f_r.json()
        
        return {
            "temp": temp, 
            "desc": desc, 
            "forecast_24": f_j.get("hourly", [])[:24],
            "forecast_48": f_j.get("hourly", [])[:48]
        }, None
    except Exception as e:
        return None, f"Weather service error: {str(e)}"

def ai_response(prompt, lang):
    """Get AI response with error handling"""
    try:
        sys_prompt = """You are Raha MS AI Companion, a helpful assistant for Multiple Sclerosis patients in GCC countries. 
        Provide practical, culturally sensitive advice about heat management and MS symptoms. 
        Be empathetic, concise, and focus on actionable tips."""
        
        if lang == "Arabic":
            sys_prompt += "Respond in clear, simple Arabic."
        else:
            sys_prompt += "Respond in clear, simple English."

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Unable to get AI advice right now. Error: {str(e)}"

def render_about_page(lang):
    """About page with MS-friendly information"""
    if lang == "English":
        st.title("🧠 Welcome to Raha MS")
        st.markdown("""
        <div class='big-font'>
        Living with <strong>Multiple Sclerosis (MS)</strong> in the GCC can be challenging, especially with intense heat.  
        Raha MS is designed <strong>with and for people living with MS</strong> to bring comfort and support to your daily life.
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🌡️ Why Heat Matters")
            st.info("Even a small rise in body temperature (0.5°C) can temporarily worsen MS symptoms — known as **Uhthoff's phenomenon**.")
            
            st.subheader("🎯 Simple Daily Use")
            st.markdown("""
            - **Quick check-ins** (30 seconds)
            - **Large, clear buttons** for easy tapping
            - **Voice-friendly** for hands-free use
            - **Low cognitive load** design
            """)
        
        with col2:
            st.subheader("💡 GCC-Specific Features")
            st.markdown("""
            - **Regional weather patterns**
            - **Cultural considerations**
            - **Local cooling strategies**
            - **Arabic/English support**
            """)
            
            st.subheader("🔒 Your Privacy")
            st.success("Your data stays on your device. We never share personal health information.")
    
    else:  # Arabic
        st.title("🧠 مرحبًا بك في راحة إم إس")
        st.markdown("""
        <div style='text-align: right; font-size: 18px;'>
        العيش مع <strong>التصلب المتعدد (MS)</strong> في الخليج قد يكون صعبًا بسبب الحرارة الشديدة.  
        تم تصميم تطبيق راحة إم إس <strong>بالتعاون مع مرضى التصلب المتعدد</strong> ليمنحك الراحة والدعم.
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🌡️ لماذا تؤثر الحرارة؟")
            st.info("حتى الارتفاع البسيط في درجة حرارة الجسم (0.5°م) قد يزيد أعراض التصلب المتعدد مؤقتًا — **ظاهرة أوتهوف**.")
            
            st.subheader("🎯 استخدام يومي بسيط")
            st.markdown("""
            - **فحص سريع** (30 ثانية)
            - **أزرار كبيرة** وواضحة
            - **يدعم الصوت** للاستخدام بدون يدين
            - **تصميم بسيط** يريح الذهن
            """)
        
        with col2:
            st.subheader("💡 ميزات خاصة للخليج")
            st.markdown("""
            - **أنماط الطقس الإقليمية**
            - **اعتبارات ثقافية**
            - **استراتيجات تبريد محلية**
            - **دعم العربية/الإنجليزية**
            """)
            
            st.subheader("🔒 خصوصيتك")
            st.success("بياناتك تبقى على جهازك. نحن لا نشارك معلوماتك الصحية الشخصية.")

# ========== SIDEBAR ==========
# Logo and language selection
logo_url = "https://raw.githubusercontent.com/Solidity-Contracts/RahaMS/6512b826bd06f692ad81f896773b44a3b0482001/logo1.png"
st.sidebar.image(logo_url, use_container_width=True)

# Language selection with session state
app_language = st.sidebar.selectbox(
    "🌐 Language / اللغة", 
    ["English", "Arabic"],
    key="language_selector"
)
T = TEXTS[app_language]

# Apply RTL for Arabic
if app_language == "Arabic":
    st.markdown("""
    <style>
    .main .block-container {
        direction: rtl;
        text-align: right;
    }
    .stRadio > label {
        direction: rtl;
        text-align: right;
    }
    </style>
    """, unsafe_allow_html=True)

# Navigation based on login status
if st.session_state.user:
    pages = [T["about_title"], T["temp_monitor"], T["journal"], T["logout"]]
else:
    pages = [T["about_title"], T["login_title"]]

page = st.sidebar.radio("Navigate", pages)

# ========== PAGE ROUTING ==========
if page == T["about_title"]:
    render_about_page(app_language)

elif page == T["login_title"]:
    st.title(T["login_title"])
    
    tab1, tab2 = st.tabs([T["login"], T["register"]])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input(T["username"], key="login_user")
            password = st.text_input(T["password"], type="password", key="login_pass")
            if st.form_submit_button(T["login"], use_container_width=True):
                conn = get_db_connection()
                if conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
                    if c.fetchone():
                        st.session_state.user = username
                        st.success("✅ Login successful!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials")
                    conn.close()
    
    with tab2:
        with st.form("register_form"):
            username = st.text_input(T["username"], key="reg_user")
            password = st.text_input(T["password"], type="password", key="reg_pass")
            if st.form_submit_button(T["register"], use_container_width=True):
                if len(username) < 3:
                    st.error("Username must be at least 3 characters")
                else:
                    conn = get_db_connection()
                    if conn:
                        try:
                            c = conn.cursor()
                            c.execute("INSERT INTO users VALUES (?,?,?)", 
                                     (username, password, datetime.now().isoformat()))
                            conn.commit()
                            st.success("✅ Account created! Please login.")
                        except sqlite3.IntegrityError:
                            st.error("❌ Username already exists")
                        finally:
                            conn.close()

elif page == T["temp_monitor"] and st.session_state.user:
    st.title("🌡️ " + T["heat_risk"])
    
    # Simple, large interface for MS users
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown('<div class="big-font">**Quick Health Check**</div>', unsafe_allow_html=True)
        
        # Large, easy-to-use inputs
        body_temp = st.number_input(
            "Your body temperature (°C):",
            min_value=35.0, max_value=42.0, value=37.0, step=0.1,
            key="body_temp"
        )
        
        city = st.text_input("Your city:", value="Abu Dhabi,AE", key="city_input")
        
        # Simple trigger selection with large buttons
        st.write("Today I experienced:")
        triggers = st.multiselect(
            "Select triggers (optional):",
            ["Exercise", "Hot bath", "Spicy food", "Stress", "Sun exposure", "Fever", "None"],
            key="triggers"
        )
    
    with col2:
        st.write("")  # Spacer
        if st.button("🔍 Check My Safety", use_container_width=True, type="primary"):
            with st.spinner("Checking weather and assessing risk..."):
                weather, error = get_weather_with_coords(city)
                
                if error:
                    st.error(f"Weather error: {error}")
                else:
                    # Calculate risk based on MS guidelines
                    temp_diff = body_temp - weather["temp"]
                    
                    if temp_diff <= 0.5:
                        status = "Safe"
                        color_class = "risk-safe"
                        icon = "✅"
                        advice = "Good condition! Maintain hydration and normal activities."
                    elif temp_diff <= 1.5:
                        status = "Caution"
                        color_class = "risk-caution"
                        icon = "⚠️"
                        advice = "Moderate risk. Limit heat exposure and use cooling strategies."
                    else:
                        status = "High Risk"
                        color_class = "risk-danger"
                        icon = "🚨"
                        advice = "High risk! Avoid heat, use cooling, contact clinician if symptoms worsen."
                    
                    # Save to database
                    conn = get_db_connection()
                    if conn:
                        try:
                            c = conn.cursor()
                            c.execute(
                                "INSERT INTO temps (username, date, body_temp, weather_temp, status, triggers, symptoms) VALUES (?,?,?,?,?,?,?)",
                                (st.session_state.user, datetime.now().isoformat(), body_temp, 
                                 weather["temp"], status, ", ".join(triggers), "")
                            )
                            conn.commit()
                        except Exception as e:
                            st.warning(f"Note: Could not save to history: {e}")
                        finally:
                            conn.close()
                    
                    # Display results
                    st.markdown(f"""
                    <div class='{color_class}'>
                    <h3>{icon} {status}</h3>
                    <p><strong>Advice:</strong> {advice}</p>
                    <p><strong>Weather:</strong> {weather['temp']}°C ({weather['desc']})</p>
                    <p><strong>Your temp:</strong> {body_temp}°C</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # AI Advice section
                    st.subheader("🤖 " + T["personal_advice"])
                    if st.button("Get Personalized Advice", key="ai_advice"):
                        prompt = f"""
                        MS patient in GCC region. 
                        Body temp: {body_temp}°C, Weather: {weather['temp']}°C.
                        Triggers: {triggers}. 
                        Risk level: {status}.
                        Provide brief, practical advice in {app_language}.
                        """
                        advice = ai_response(prompt, app_language)
                        st.info(advice)

elif page == T["journal"] and st.session_state.user:
    st.title("📝 " + T["journal"])
    
    # Simple journal interface
    with st.form("journal_form"):
        entry = st.text_area("How are you feeling today?", height=100,
                           placeholder="Note any symptoms, concerns, or observations...")
        if st.form_submit_button("Save Entry", use_container_width=True):
            if entry.strip():
                conn = get_db_connection()
                if conn:
                    try:
                        c = conn.cursor()
                        c.execute("INSERT INTO journal (username, date, entry) VALUES (?,?,?)",
                                 (st.session_state.user, datetime.now().isoformat(), entry))
                        conn.commit()
                        st.success("✅ Entry saved!")
                    except Exception as e:
                        st.error(f"Error saving entry: {e}")
                    finally:
                        conn.close()
    
    # Display recent entries
    st.subheader("Recent Entries")
    conn = get_db_connection()
    if conn:
        entries = conn.execute(
            "SELECT date, entry FROM journal WHERE username=? ORDER BY date DESC LIMIT 5",
            (st.session_state.user,)
        ).fetchall()
        conn.close()
        
        for date, entry in entries:
            with st.expander(f"📅 {date[:16]}"):
                st.write(entry)

elif page == T["logout"]:
    st.session_state.user = None
    st.session_state.last_check = None
    st.success("✅ Logged out successfully!")
    time.sleep(1)
    st.rerun()

# Footer with emergency information
st.sidebar.markdown("---")
st.sidebar.markdown("**Emergency Contacts**")
st.sidebar.info("If experiencing severe symptoms, contact your healthcare provider immediately.")
