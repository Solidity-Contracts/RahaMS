# =========================
# Heat Safety Demo (English/Arabic)
# =========================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# ---------- CONFIG ----------
st.set_page_config(
    page_title="Heat Safety Demo - تجربة السلامة من الحرارة",
    page_icon="🌡️",
    layout="wide"
)

# ---------- TRANSLATIONS ----------
TRANSLATIONS = {
    # Page header
    "heat_safety_demo": {"en": "Heat Safety Demo", "ar": "تجربة السلامة من الحرارة"},
    "demo_mode": {"en": "DEMO MODE", "ar": "وضع التجربة"},
    
    # Navigation
    "scenarios": {"en": "Scenarios", "ar": "سيناريوهات"},
    "custom": {"en": "Custom", "ar": "مخصص"},
    "live_demo": {"en": "Live Demo", "ar": "تجربة حية"},
    "learn": {"en": "Learn", "ar": "تعلم"},
    
    # Status levels
    "safe": {"en": "Safe", "ar": "آمن"},
    "caution": {"en": "Caution", "ar": "حذر"},
    "high": {"en": "High Risk", "ar": "خطر مرتفع"},
    "critical": {"en": "Critical", "ar": "حرج"},
    
    # Parameters
    "core_temp": {"en": "Core Temperature", "ar": "درجة حرارة الجسم"},
    "baseline": {"en": "Baseline", "ar": "خط الأساس"},
    "delta_temp": {"en": "Δ Temperature", "ar": "فرق الدرجة"},
    "environment": {"en": "Environment", "ar": "البيئة"},
    "symptoms": {"en": "Symptoms", "ar": "الأعراض"},
    "feels_like": {"en": "Feels Like", "ar": "الشعور الحقيقي"},
    
    # Alerts
    "uhthoff_alert": {
        "en": "UHTHOFF'S PHENOMENON ALERT",
        "ar": "تنبيه ظاهرة أوتهوف"
    },
    "trigger": {
        "en": "Trigger", 
        "ar": "المحفز"
    },
    "what_this_means": {
        "en": "What this means", 
        "ar": "ماذا يعني هذا"
    },
    "recommended_action": {
        "en": "Recommended action", 
        "ar": "الإجراء الموصى به"
    },
    
    # Scenario names
    "morning_commute": {
        "en": "Morning commute in Dubai summer",
        "ar": "الذهاب للعمل صباحاً في صيف دبي"
    },
    "office_ac_failure": {
        "en": "Office work with AC failure", 
        "ar": "العمل في المكتب مع عطل في التكييف"
    },
    "evening_walk_vest": {
        "en": "Evening walk with cooling vest",
        "ar": "نزهة مسائية مع سترة تبريد"
    },
    "ms_flare_up": {
        "en": "MS flare-up at home",
        "ar": "نوبة تصلب متعدد في المنزل"
    },
    "exercise_humid": {
        "en": "Exercise in humid conditions",
        "ar": "تمارين في ظروف رطبة"
    },
    
    # Interventions
    "try_cooling_vest": {
        "en": "Try Cooling Vest", 
        "ar": "جرب سترة التبريد"
    },
    "move_indoors": {
        "en": "Move Indoors", 
        "ar": "انتقل للداخل"
    },
    "hydrate_now": {
        "en": "Hydrate Now", 
        "ar": "اشرب الماء الآن"
    },
    "rest_in_shade": {
        "en": "Rest in Shade", 
        "ar": "ارتح في الظل"
    }
}

def get_text(key, lang="en"):
    """Get translated text"""
    return TRANSLATIONS.get(key, {}).get(lang, key)

# ---------- CORE LOGIC ----------
def calculate_risk_status(core_temp, baseline, environment_temp, has_symptoms, language="en"):
    """
    Calculate risk status based on multiple factors
    Returns: status_level, triggers, explanations, recommendations
    """
    delta_temp = core_temp - baseline
    triggers = []
    explanations = []
    recommendations = []
    
    # Determine risk level
    risk_level = 0  # 0: Safe, 1: Caution, 2: High, 3: Critical
    
    # Uhthoff's phenomenon check
    if delta_temp >= 0.5:
        risk_level = max(risk_level, 1)
        triggers.append(get_text("uhthoff_alert", language))
        explanations.append(
            get_text("what_this_means", language) + ": " + 
            ("Core temperature increased by +{:.1f}°C above baseline".format(delta_temp) if language == "en" 
             else "ارتفاع درجة حرارة الجسم بمقدار +{:.1f}°C فوق خط الأساس".format(delta_temp))
        )
        recommendations.append(
            get_text("recommended_action", language) + ": " +
            ("Move to cooler environment, use cooling strategies" if language == "en"
             else "انتقل إلى بيئة أكثر برودة، استخدم استراتيجيات التبريد")
        )
    
    # Absolute core temperature checks
    if core_temp >= 38.5:
        risk_level = 3
        triggers.append("Core ≥ 38.5°C" if language == "en" else "درجة الحرارة ≥ 38.5°C")
    elif core_temp >= 38.0:
        risk_level = max(risk_level, 2)
        triggers.append("Core ≥ 38.0°C" if language == "en" else "درجة الحرارة ≥ 38.0°C")
    elif core_temp >= 37.8:
        risk_level = max(risk_level, 1)
        triggers.append("Core ≥ 37.8°C" if language == "en" else "درجة الحرارة ≥ 37.8°C")
    
    # Environment impact
    if environment_temp >= 42:
        risk_level = max(risk_level, 2)
        triggers.append("Feels-like ≥ 42°C" if language == "en" else "الشعور الحقيقي ≥ 42°C")
    elif environment_temp >= 38:
        risk_level = max(risk_level, 1)
        triggers.append("Feels-like ≥ 38°C" if language == "en" else "الشعور الحقيقي ≥ 38°C")
    
    # Symptoms impact
    if has_symptoms:
        risk_level = min(3, risk_level + 1)
        triggers.append("Symptoms present" if language == "en" else "وجود أعراض")
    
    # Map to status levels
    status_levels = ["safe", "caution", "high", "critical"]
    status = status_levels[risk_level] if risk_level < len(status_levels) else "critical"
    
    return status, triggers, explanations, recommendations

def get_status_color(status):
    """Get color for status level"""
    colors = {
        "safe": "#E6F4EA",      # Light green
        "caution": "#FFF8E1",   # Light yellow
        "high": "#FFE0E0",      # Light red
        "critical": "#FFCDD2"   # Red
    }
    return colors.get(status, "#EEE")

def get_status_emoji(status):
    """Get emoji for status level"""
    emojis = {
        "safe": "✅",
        "caution": "⚠️",
        "high": "🔴",
        "critical": "🚨"
    }
    return emojis.get(status, "❓")

# ---------- SCENARIO PRESETS ----------
SCENARIOS = {
    "morning_commute": {
        "core_temp": 37.4,
        "environment_temp": 41,
        "symptoms": ["Blurred vision", "Fatigue"],
        "description_en": "Hot car, sun exposure, typical commute",
        "description_ar": "سيارة ساخنة، تعرض للشمس، ذهاب نموذجي للعمل"
    },
    "office_ac_failure": {
        "core_temp": 37.8,
        "environment_temp": 35,
        "symptoms": ["Fatigue", "Weakness"],
        "description_en": "AC system failure, indoor heat buildup",
        "description_ar": "عطل في نظام التكييف، تراكم الحرارة داخل المبني"
    },
    "evening_walk_vest": {
        "core_temp": 37.0,
        "environment_temp": 38,
        "symptoms": [],
        "description_en": "Cooling vest effectively managing temperature",
        "description_ar": "سترة التبريد تدير درجة الحرارة بفعالية"
    },
    "ms_flare_up": {
        "core_temp": 38.2,
        "environment_temp": 28,
        "symptoms": ["Blurred vision", "Weakness", "Balance issues", "Sensory changes"],
        "description_en": "MS flare-up with elevated core temperature",
        "description_ar": "نوبة تصلب متعدد مع ارتفاع درجة حرارة الجسم"
    },
    "exercise_humid": {
        "core_temp": 37.9,
        "environment_temp": 39,
        "symptoms": ["Fatigue", "Weakness"],
        "description_en": "Physical activity in high humidity conditions",
        "description_ar": "نشاط بدني في ظروف رطوبة عالية"
    }
}

# ---------- PAGE RENDER ----------
def main():
    # Language selection
    col1, col2 = st.columns([3, 1])
    with col2:
        language = st.radio("Language / اللغة", ["English", "العربية"], horizontal=True)
        lang_code = "en" if language == "English" else "ar"
    
    # Initialize session state for demo parameters - FIXED: ensure proper types
    if 'demo_params' not in st.session_state:
        st.session_state.demo_params = {
            'core_temp': 36.6,
            'baseline': 36.6,
            'environment_temp': 32.0,  # Ensure float
            'symptoms': [],
            'history': []
        }
    
    # Ensure all numeric parameters are floats
    for key in ['core_temp', 'baseline', 'environment_temp']:
        if key in st.session_state.demo_params:
            st.session_state.demo_params[key] = float(st.session_state.demo_params[key])
    
    # Page header with demo mode banner
    st.markdown(f"""
    <div style='background: linear-gradient(45deg, #FF6B6B, #4ECDC4); padding: 20px; border-radius: 10px; text-align: center; color: white;'>
        <h1 style='margin: 0;'>{get_text('heat_safety_demo', lang_code)}</h1>
        <h3 style='margin: 0;'>🚨 {get_text('demo_mode', lang_code)} - FOR EDUCATIONAL PURPOSES ONLY 🚨</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation
    st.markdown("<br>", unsafe_allow_html=True)
    
    nav_cols = st.columns(4)
    with nav_cols[0]:
        nav_scenarios = st.button(f"🎯 {get_text('scenarios', lang_code)}", use_container_width=True)
    with nav_cols[1]:
        nav_custom = st.button(f"⚙️ {get_text('custom', lang_code)}", use_container_width=True)
    with nav_cols[2]:
        nav_live = st.button(f"🎬 {get_text('live_demo', lang_code)}", use_container_width=True)
    with nav_cols[3]:
        nav_learn = st.button(f"📚 {get_text('learn', lang_code)}", use_container_width=True)
    
    # Default to scenarios view
    current_view = "scenarios"
    if nav_custom:
        current_view = "custom"
    elif nav_live:
        current_view = "live"
    elif nav_learn:
        current_view = "learn"
    
    # Initialize session state for demo parameters
    if 'demo_params' not in st.session_state:
        st.session_state.demo_params = {
            'core_temp': 36.6,
            'baseline': 36.6,
            'environment_temp': 32,
            'symptoms': [],
            'history': []
        }
    
    # SCENARIOS VIEW
    if current_view == "scenarios":
        render_scenarios_view(lang_code)
    
    # CUSTOM VIEW  
    elif current_view == "custom":
        render_custom_view(lang_code)
    
    # LIVE DEMO VIEW
    elif current_view == "live":
        render_live_demo_view(lang_code)
    
    # LEARN VIEW
    else:
        render_learn_view(lang_code)

def render_scenarios_view(lang_code):
    """Render the scenarios selection view"""
    st.markdown(f"### 🎯 {get_text('scenarios', lang_code)}")
    
    # Scenario selection
    scenario_options = {
        get_text("morning_commute", lang_code): "morning_commute",
        get_text("office_ac_failure", lang_code): "office_ac_failure", 
        get_text("evening_walk_vest", lang_code): "evening_walk_vest",
        get_text("ms_flare_up", lang_code): "ms_flare_up",
        get_text("exercise_humid", lang_code): "exercise_humid"
    }
    
    selected_scenario_name = st.selectbox(
        f"📋 {get_text('scenarios', lang_code)}" if lang_code == "en" else "📋 السيناريوهات",
        list(scenario_options.keys())
    )
    
    scenario_key = scenario_options[selected_scenario_name]
    scenario = SCENARIOS[scenario_key]
    
    # Apply scenario button
    if st.button("Apply Scenario / تطبيق السيناريو", use_container_width=True):
        st.session_state.demo_params.update({
            'core_temp': scenario['core_temp'],
            'environment_temp': scenario['environment_temp'],
            'symptoms': scenario['symptoms']
        })
        st.success("Scenario applied! / تم تطبيق السيناريو!")
    
    # Display scenario description
    st.info(scenario['description_en'] if lang_code == "en" else scenario['description_ar'])
    
    # Show current parameters and risk assessment
    render_risk_assessment(lang_code)

def render_custom_view(lang_code):
    """Render the custom parameters view"""
    st.markdown(f"### ⚙️ {get_text('custom', lang_code)}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Core temperature control
        st.session_state.demo_params['core_temp'] = st.slider(
            f"🌡️ {get_text('core_temp', lang_code)} (°C)",
            min_value=36.0,
            max_value=39.5,
            value=float(st.session_state.demo_params['core_temp']),
            step=0.1,
            help="Adjust core body temperature" if lang_code == "en" else "اضبط درجة حرارة الجسم"
        )
        
        # Baseline display
        st.session_state.demo_params['baseline'] = st.slider(
            f"📊 {get_text('baseline', lang_code)} (°C)",
            min_value=36.0,
            max_value=37.5,
            value=float(st.session_state.demo_params['baseline']),
            step=0.1,
            help="Your normal baseline temperature" if lang_code == "en" else "درجة حرارتك الطبيعية الأساسية"
        )
    
    with col2:
        # Environment control - FIXED: proper parameter structure
        st.session_state.demo_params['environment_temp'] = st.slider(
            f"🌡️ {get_text('feels_like', lang_code)} (°C)",
            min_value=25.0,
            max_value=50.0,
            value=float(st.session_state.demo_params['environment_temp']),
            step=1.0,
            help="How hot it feels with humidity and sun" if lang_code == "en" else "شدة الحرارة مع الرطوبة والشمس"
        )
        
        # Symptoms selection
        symptom_options = [
            "Blurred vision / ضبابية الرؤية",
            "Fatigue / إرهاق", 
            "Weakness / ضعف",
            "Balance issues / مشاكل توازن",
            "Sensory changes / تغيرات حسية"
        ]
        
        selected_symptoms = st.multiselect(
            f"📋 {get_text('symptoms', lang_code)}",
            symptom_options,
            default=st.session_state.demo_params['symptoms'],
            help="Select any current symptoms" if lang_code == "en" else "اختر أي أعراض حالية"
        )
        st.session_state.demo_params['symptoms'] = selected_symptoms
    
    # Show risk assessment
    render_risk_assessment(lang_code)
def render_live_demo_view(lang_code):
    """Render the live automated demo view"""
    st.markdown(f"### 🎬 {get_text('live_demo', lang_code)}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Demo controls
        if st.button("Start Heat Exposure Demo / بدء تجربة التعرض للحرارة", use_container_width=True):
            st.session_state.demo_running = True
            st.session_state.demo_start_time = datetime.now()
            st.session_state.demo_params['core_temp'] = 36.6
            st.session_state.demo_params['environment_temp'] = 35
        
        if st.button("Start MS Flare-up Demo / بدء تجربة نوبة التصلب", use_container_width=True):
            st.session_state.demo_running = True  
            st.session_state.demo_start_time = datetime.now()
            st.session_state.demo_params['core_temp'] = 36.6
            st.session_state.demo_params['environment_temp'] = 28
            st.session_state.demo_params['symptoms'] = []
    
    with col2:
        if st.button("Stop Demo / إيقاف التجربة", use_container_width=True):
            st.session_state.demo_running = False
        
        if st.button("Apply Intervention / تطبيق تدخل", use_container_width=True) and st.session_state.get('demo_running'):
            # Simulate intervention effect
            st.session_state.demo_params['core_temp'] = max(36.6, st.session_state.demo_params['core_temp'] - 0.8)
            st.session_state.demo_params['environment_temp'] = 25
            st.session_state.demo_params['symptoms'] = []
    
    # Demo simulation logic
    if st.session_state.get('demo_running'):
        # Simulate temperature rise over time
        time_running = (datetime.now() - st.session_state.demo_start_time).seconds
        if time_running < 30:  # First 30 seconds - temperature rises
            st.session_state.demo_params['core_temp'] = min(38.5, 36.6 + (time_running * 0.06))
            st.session_state.demo_params['environment_temp'] = min(45, 35 + (time_running * 0.3))
        elif time_running < 45:  # Next 15 seconds - symptoms appear
            if len(st.session_state.demo_params['symptoms']) < 3:
                st.session_state.demo_params['symptoms'].extend(["Blurred vision / ضبابية الرؤية", "Fatigue / إرهاق"])
        else:  # After 45 seconds - critical
            st.session_state.demo_params['core_temp'] = min(39.0, st.session_state.demo_params['core_temp'] + 0.02)
        
        # Auto-refresh
        time.sleep(0.5)
        st.rerun()
    
    render_risk_assessment(lang_code)

def render_learn_view(lang_code):
    """Render the educational content view"""
    st.markdown(f"### 📚 {get_text('learn', lang_code)}")
    
    if lang_code == "en":
        st.markdown("""
        ## Understanding Heat Sensitivity in MS
        
        ### 🤒 Uhthoff's Phenomenon
        - **What**: Temporary worsening of MS symptoms with small increases in body temperature
        - **Trigger**: As little as +0.5°C above your normal baseline  
        - **Why**: Heat affects nerve conduction in already damaged nerves
        - **Duration**: Symptoms usually improve when body temperature returns to normal
        
        ### 🌡️ Key Temperature Thresholds
        - **+0.5°C above baseline**: First alert level - caution needed
        - **37.8°C**: Moderate risk - consider cooling strategies
        - **38.0°C**: High risk - implement cooling immediately
        - **38.5°C**: Critical risk - seek medical attention if symptoms severe
        
        ### ❄️ Effective Cooling Strategies
        - **Cooling garments**: Vests, bandanas, wristbands
        - **Environmental**: Air conditioning, fans, shade
        - **Hydration**: Drink cool water regularly
        - **Timing**: Avoid peak heat hours (11AM-3PM)
        - **Pre-cooling**: Cool down before going into heat
        
        ### 📊 Personal Baseline
        - Your normal body temperature when feeling well
        - Typically between 36.0°C - 37.0°C
        - Important to know for detecting meaningful changes
        """)
    else:
        st.markdown("""
        ## فهم الحساسية للحرارة في التصلب المتعدد
        
        ### 🤒 ظاهرة أوتهوف
        - **ما هي**: تدهور مؤقت في أعراض التصلب المتعدد مع ارتفاع طفيف في درجة حرارة الجسم
        - **المحفز**: ارتفاع بسيط يصل إلى +0.5°C فوق خط الأساس الطبيعي
        - **السبب**: الحرارة تؤثر على التوصيل العصبي في الأعصاب التالفة أصلاً
        - **المدة**: تتحسن الأعراض عادة عند عودة درجة حرارة الجسم إلى المعدل الطبيعي
        
        ### 🌡️ عتبات درجة الحرارة الرئيسية
        - **+0.5°C فوق خط الأساس**: مستوى التنبيه الأول - الحذر مطلوب
        - **37.8°C**: خطر متوسط - فكر في استراتيجيات التبريد
        - **38.0°C**: خطر مرتفع - نفذ التبريد فوراً
        - **38.5°C**: خطر حرج - اطلب الرعاية الطبية إذا كانت الأعراض شديدة
        
        ### ❄️ استراتيجيات التبريد الفعالة
        - **ملابس التبريد**: سترات، مناديل، أساور تبريد
        - **البيئة**: مكيفات هواء، مراوح، ظل
        - **ترطيب**: اشرب ماءً بارداً بانتظام
        - **التوقيت**: تجنب ساعات الذروة الحرارية (11 صباحاً - 3 عصراً)
        - **التبريد المسبق**: برد جسمك قبل الخروج للحرارة
        
        ### 📊 خط الأساس الشخصي
        - درجة حرارة جسمك الطبيعية عندما تشعر بأنك بحالة جيدة
        - عادة بين 36.0°C - 37.0°C
        - مهم معرفته للكشف عن التغيرات ذات المعنى
        """)

def render_risk_assessment(lang_code):
    """Render the current risk assessment and alerts"""
    params = st.session_state.demo_params
    
    # Calculate current risk status
    status, triggers, explanations, recommendations = calculate_risk_status(
        params['core_temp'], 
        params['baseline'],
        params['environment_temp'],
        len(params['symptoms']) > 0,
        lang_code
    )
    
    # Display current status banner
    status_color = get_status_color(status)
    status_emoji = get_status_emoji(status)
    
    st.markdown(f"""
    <div style='background: {status_color}; padding: 15px; border-radius: 10px; border-left: 5px solid {status_color}; margin: 20px 0;'>
        <h2 style='margin: 0;'>{status_emoji} {get_text(status, lang_code).upper()}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Display current parameters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        delta_temp = params['core_temp'] - params['baseline']
        st.metric(
            get_text("core_temp", lang_code), 
            f"{params['core_temp']:.1f}°C",
            f"Δ{delta_temp:+.1f}°C"
        )
    
    with col2:
        st.metric(
            get_text("feels_like", lang_code),
            f"{params['environment_temp']:.1f}°C"
        )
    
    with col3:
        symptom_count = len(params['symptoms'])
        st.metric(
            get_text("symptoms", lang_code),
            f"{symptom_count}",
            "active" if symptom_count > 0 else "none"
        )
    
    # Display alerts if any triggers
    if triggers:
        st.markdown("---")
        st.markdown(f"### 🚨 {get_text('trigger', lang_code)}")
        
        for i, (trigger, explanation, recommendation) in enumerate(zip(triggers, explanations, recommendations)):
            with st.expander(f"🔔 {trigger}", expanded=True):
                st.write(explanation)
                st.info(recommendation)
    
    # Intervention buttons
    if status in ["caution", "high", "critical"]:
        st.markdown("---")
        st.markdown(f"### 💡 {get_text('recommended_action', lang_code)}")
        
        int_cols = st.columns(4)
        with int_cols[0]:
            if st.button(f"❄️ {get_text('try_cooling_vest', lang_code)}", use_container_width=True):
                # Simulate cooling vest effect
                st.session_state.demo_params['core_temp'] = max(
                    st.session_state.demo_params['baseline'],
                    st.session_state.demo_params['core_temp'] - 0.6
                )
                st.session_state.demo_params['environment_temp'] -= 5
                st.rerun()
        
        with int_cols[1]:
            if st.button(f"🏠 {get_text('move_indoors', lang_code)}", use_container_width=True):
                # Simulate moving indoors effect
                st.session_state.demo_params['environment_temp'] = 25
                st.session_state.demo_params['core_temp'] = max(
                    st.session_state.demo_params['baseline'],
                    st.session_state.demo_params['core_temp'] - 0.3
                )
                st.rerun()
        
        with int_cols[2]:
            if st.button(f"💧 {get_text('hydrate_now', lang_code)}", use_container_width=True):
                # Simulate hydration effect
                st.session_state.demo_params['core_temp'] = max(
                    st.session_state.demo_params['baseline'], 
                    st.session_state.demo_params['core_temp'] - 0.2
                )
                st.rerun()
        
        with int_cols[3]:
            if st.button(f"🌳 {get_text('rest_in_shade', lang_code)}", use_container_width=True):
                # Simulate rest in shade effect
                st.session_state.demo_params['environment_temp'] -= 8
                st.session_state.demo_params['core_temp'] = max(
                    st.session_state.demo_params['baseline'],
                    st.session_state.demo_params['core_temp'] - 0.4
                )
                st.rerun()

if __name__ == "__main__":
    main()
