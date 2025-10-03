# =========================
# Heat Safety Demo (English/Arabic) — FIXED with live plot + persistent nav
# =========================

import time
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------- CONFIG ----------
st.set_page_config(
    page_title="Heat Safety Demo - تجربة السلامة من الحرارة",
    page_icon="🌡️",
    layout="wide",
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
    "uhthoff_alert": {"en": "UHTHOFF'S PHENOMENON ALERT", "ar": "تنبيه ظاهرة أوتهوف"},
    "trigger": {"en": "Triggers", "ar": "المحفزات"},
    "what_this_means": {"en": "What this means", "ar": "ماذا يعني هذا"},
    "recommended_action": {"en": "Recommended action", "ar": "الإجراء الموصى به"},
    # Scenario names
    "morning_commute": {"en": "Morning commute in Dubai summer", "ar": "الذهاب للعمل صباحاً في صيف دبي"},
    "office_ac_failure": {"en": "Office work with AC failure", "ar": "العمل في المكتب مع عطل في التكييف"},
    "evening_walk_vest": {"en": "Evening walk with cooling vest", "ar": "نزهة مسائية مع سترة تبريد"},
    "ms_flare_up": {"en": "MS flare-up at home", "ar": "نوبة تصلب متعدد في المنزل"},
    "exercise_humid": {"en": "Exercise in humid conditions", "ar": "تمارين في ظروف رطبة"},
    # Interventions
    "try_cooling_vest": {"en": "Try Cooling Vest", "ar": "جرب سترة التبريد"},
    "move_indoors": {"en": "Move Indoors", "ar": "انتقل للداخل"},
    "hydrate_now": {"en": "Hydrate Now", "ar": "اشرب الماء الآن"},
    "rest_in_shade": {"en": "Rest in Shade", "ar": "ارتح في الظل"},
}


def t(key, lang="en"):
    return TRANSLATIONS.get(key, {}).get(lang, key)


# ---------- RISK ENGINE ----------
def calculate_risk_status(core_temp, baseline, environment_temp, language="en"):
    """
    Return (status_key, triggers_list)
    Uhthoff (Δ >= 0.5°C) + absolute core + environment bump.
    Symptoms are not used to score (validation only).
    """
    delta = core_temp - baseline
    level = 0  # 0 Safe, 1 Caution, 2 High, 3 Critical
    triggers = []

    # Uhthoff
    if delta >= 0.5:
        level = max(level, 1)
        triggers.append(
            (t("uhthoff_alert", language),
             f"{t('delta_temp', language)} +{delta:.1f}°C ≥ 0.5°C")
        )

    # Absolute core
    if core_temp >= 38.5:
        level = 3
        triggers.append(("Core ≥ 38.5°C", ""))
    elif core_temp >= 38.0:
        level = max(level, 2)
        triggers.append(("Core ≥ 38.0°C", ""))
    elif core_temp >= 37.8:
        level = max(level, 1)
        triggers.append(("Core ≥ 37.8°C", ""))

    # Environment
    if environment_temp >= 42:
        level = max(level, 2)
        triggers.append(("Feels-like ≥ 42°C", ""))
    elif environment_temp >= 38:
        level = max(level, 1)
        triggers.append(("Feels-like ≥ 38°C", ""))

    status_keys = ["safe", "caution", "high", "critical"]
    return status_keys[level], triggers


def status_color(status_key: str) -> str:
    return {
        "safe": "#E6F4EA",
        "caution": "#FFF8E1",
        "high": "#FFE0E0",
        "critical": "#FFCDD2",
    }.get(status_key, "#EEE")


def status_emoji(status_key: str) -> str:
    return {"safe": "✅", "caution": "⚠️", "high": "🔴", "critical": "🚨"}.get(status_key, "❓")


# ---------- SCENARIOS ----------
SCENARIOS = {
    "morning_commute": {"core_temp": 37.4, "environment_temp": 41, "desc_en": "Hot car, sun exposure",
                        "desc_ar": "سيارة ساخنة مع تعرض للشمس"},
    "office_ac_failure": {"core_temp": 37.8, "environment_temp": 35, "desc_en": "Indoor heat buildup (AC off)",
                          "desc_ar": "تراكم حرارة داخلية (تعطل المكيف)"},
    "evening_walk_vest": {"core_temp": 37.0, "environment_temp": 38, "desc_en": "Cooling vest helping outdoors",
                          "desc_ar": "سترة تبريد تساعد في الخارج"},
    "ms_flare_up": {"core_temp": 38.2, "environment_temp": 28, "desc_en": "Elevated core with mild ambient",
                    "desc_ar": "ارتفاع داخلي مع بيئة معتدلة"},
    "exercise_humid": {"core_temp": 37.9, "environment_temp": 39, "desc_en": "Exercise in humid conditions",
                       "desc_ar": "تمرين في رطوبة عالية"},
}

SYMPTOM_OPTIONS = [
    "Blurred vision / ضبابية الرؤية",
    "Fatigue / إرهاق",
    "Weakness / ضعف",
    "Balance issues / مشاكل توازن",
    "Sensory changes / تغيرات حسية",
]


# ---------- PLOTTING ----------
def append_history_point():
    """Append the current state to history for plotting."""
    p = st.session_state.demo
    st.session_state.history.append({
        "ts": datetime.now().strftime("%H:%M:%S"),
        "core": float(p["core_temp"]),
        "baseline": float(p["baseline"]),
        "feelslike": float(p["environment_temp"]),
    })


def plot_history(lang_code):
    """Plot Core, Baseline, Feels-like over time with Plotly."""
    if not st.session_state.history:
        st.info("Turn on **Live tracking** to start the plot.")
        return

    df = pd.DataFrame(st.session_state.history)
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=df["ts"], y=df["feelslike"], mode="lines+markers",
                             name=t("feels_like", lang_code)))
    fig.add_trace(go.Scatter(x=df["ts"], y=df["core"], mode="lines+markers",
                             name=t("core_temp", lang_code)))
    fig.add_trace(go.Scatter(x=df["ts"], y=df["baseline"], mode="lines",
                             name=t("baseline", lang_code)))

    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.1),
        xaxis_title="Time",
        yaxis_title="°C",
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------- VIEWS ----------
def view_scenarios(lang_code):
    st.markdown(f"### 🎯 {t('scenarios', lang_code)}")

    # Scenario picker
    names = {
        t("morning_commute", lang_code): "morning_commute",
        t("office_ac_failure", lang_code): "office_ac_failure",
        t("evening_walk_vest", lang_code): "evening_walk_vest",
        t("ms_flare_up", lang_code): "ms_flare_up",
        t("exercise_humid", lang_code): "exercise_humid",
    }
    label = st.selectbox("📋 " + t("scenarios", lang_code), list(names.keys()))
    key = names[label]
    sc = SCENARIOS[key]

    # Apply preset
    if st.button("Apply Scenario / تطبيق السيناريو", use_container_width=True):
        st.session_state.demo["core_temp"] = float(sc["core_temp"])
        st.session_state.demo["environment_temp"] = float(sc["environment_temp"])
        st.success("Applied!")
        # Write one point to history so the plot shows something immediately
        append_history_point()
        st.rerun()

    st.info(sc["desc_en"] if lang_code == "en" else sc["desc_ar"])
    render_risk(lang_code)


def view_custom(lang_code):
    st.markdown(f"### ⚙️ {t('custom', lang_code)}")
    col1, col2 = st.columns(2)

    with col1:
        st.session_state.demo["core_temp"] = st.slider(
            f"🌡️ {t('core_temp', lang_code)} (°C)",
            36.0, 39.5, float(st.session_state.demo["core_temp"]), 0.1,
        )
        st.session_state.demo["baseline"] = st.slider(
            f"📊 {t('baseline', lang_code)} (°C)",
            36.0, 37.5, float(st.session_state.demo["baseline"]), 0.1,
        )

    with col2:
        st.session_state.demo["environment_temp"] = st.slider(
            f"🌡️ {t('feels_like', lang_code)} (°C)",
            25.0, 50.0, float(st.session_state.demo["environment_temp"]), 1.0,
        )
        # Symptoms = validation only
        current = [s for s in st.session_state.demo["symptoms"] if s in SYMPTOM_OPTIONS]
        st.session_state.demo["symptoms"] = st.multiselect(
            f"📋 {t('symptoms', lang_code)}", options=SYMPTOM_OPTIONS, default=current
        )

    # Live tracking controls
    st.markdown("---")
    live_cols = st.columns([0.35, 0.35, 0.3])
    with live_cols[0]:
        st.session_state.live_on = st.toggle("Live tracking (auto-append)", value=st.session_state.live_on)
    with live_cols[1]:
        st.session_state.sample_every = st.select_slider("Sample every (s)", [1, 2, 3, 5, 10], value=st.session_state.sample_every)
    with live_cols[2]:
        if st.button("🧹 Clear plot"):
            st.session_state.history.clear()
            st.toast("Cleared")

    if st.session_state.live_on:
        # Append point each rerun; autorefresh to trigger reruns
        append_history_point()
        try:
            st.autorefresh(interval=st.session_state.sample_every * 1000, key="live_auto")
        except Exception:
            pass

    plot_history(lang_code)
    render_risk(lang_code)


def view_live_demo(lang_code):
    st.markdown(f"### 🎬 {t('live_demo', lang_code)}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Heat Exposure / بدء التعرض للحرارة", use_container_width=True):
            st.session_state.demo_running = True
            st.session_state.demo_start = datetime.now()
            st.session_state.demo.update({"core_temp": 36.6, "environment_temp": 35})
    with col2:
        if st.button("Stop / إيقاف", use_container_width=True):
            st.session_state.demo_running = False

    # Sim loop
    if st.session_state.demo_running:
        secs = (datetime.now() - st.session_state.demo_start).seconds
        if secs < 30:  # warm up
            st.session_state.demo["core_temp"] = min(38.5, 36.6 + secs * 0.06)
            st.session_state.demo["environment_temp"] = min(45, 35 + secs * 0.3)
        elif secs < 45:  # symptoms period (for validation only)
            if len(st.session_state.demo["symptoms"]) < 2:
                st.session_state.demo["symptoms"] = ["Fatigue / إرهاق", "Blurred vision / ضبابية الرؤية"]
        else:  # plateau
            st.session_state.demo["core_temp"] = min(39.0, st.session_state.demo["core_temp"] + 0.02)

        append_history_point()
        try:
            st.autorefresh(interval=500, key="demo_auto")
        except Exception:
            time.sleep(0.5)
            st.rerun()

    plot_history(lang_code)
    render_risk(lang_code)


def view_learn(lang_code):
    st.markdown(f"### 📚 {t('learn', lang_code)}")
    if lang_code == "en":
        st.markdown("""
### 🤒 Uhthoff's Phenomenon
- Temporary worsening of MS symptoms with small increases in body temperature
- Often triggered at **~+0.5°C above baseline**
- Usually reversible once you cool down

### 🌡️ Key thresholds (app heuristics)
- +0.5°C above baseline → **Caution**
- 37.8°C → **Caution**
- 38.0°C → **High**
- 38.5°C → **Critical**

### ❄️ Helpful actions
Cooling garments, AC/fans/shade, hydration, timing (avoid peak heat), and pre-cooling.
""")
    else:
        st.markdown("""
### 🤒 ظاهرة أوتهوف
- تدهور مؤقت في الأعراض مع ارتفاع بسيط في درجة حرارة الجسم
- غالبًا يحدث عند **+0.5°C تقريبًا فوق خط الأساس**
- يتحسن عادة عند التبريد

### 🌡️ عتبات رئيسية (في التطبيق)
- +0.5°C فوق خط الأساس → **حذر**
- 37.8°C → **حذر**
- 38.0°C → **خطر مرتفع**
- 38.5°C → **حرج**

### ❄️ إجراءات مفيدة
سترات تبريد، تكييف/مراوح/ظل، ترطيب، توقيت مناسب، وتبريد مسبق.
""")


def render_risk(lang_code):
    p = st.session_state.demo
    status_key, trig = calculate_risk_status(
        p["core_temp"], p["baseline"], p["environment_temp"], lang_code
    )
    col = status_color(status_key)
    emoji = status_emoji(status_key)

    st.markdown(
        f"""
<div style='background:{col};padding:14px;border-radius:10px;margin-top:10px'>
  <h3 style='margin:0'>{emoji} {t(status_key, lang_code).upper()}</h3>
</div>
""",
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        delta = p["core_temp"] - p["baseline"]
        st.metric(t("core_temp", lang_code), f"{p['core_temp']:.1f}°C", f"Δ{delta:+.1f}°C")
    with m2:
        st.metric(t("feels_like", lang_code), f"{p['environment_temp']:.1f}°C")
    with m3:
        st.metric(t("symptoms", lang_code), f"{len(p['symptoms'])}", "active" if p["symptoms"] else "none")

    if trig:
        st.markdown("---")
        st.markdown(f"### 🚨 {t('trigger', lang_code)}")
        for title, detail in trig:
            if detail:
                st.write(f"• **{title}** — {detail}")
            else:
                st.write(f"• **{title}**")

    # Status-specific guidance (short and clear)
    if status_key in ("caution", "high", "critical"):
        st.markdown("---")
        st.markdown(f"### 💡 {t('recommended_action', lang_code)}")
        act_cols = st.columns(4)
        with act_cols[0]:
            if st.button(f"❄️ {t('try_cooling_vest', lang_code)}", use_container_width=True):
                p["core_temp"] = max(p["baseline"], p["core_temp"] - 0.6); st.rerun()
        with act_cols[1]:
            if st.button(f"🏠 {t('move_indoors', lang_code)}", use_container_width=True):
                p["environment_temp"] = 25; p["core_temp"] = max(p["baseline"], p["core_temp"] - 0.3); st.rerun()
        with act_cols[2]:
            if st.button(f"💧 {t('hydrate_now', lang_code)}", use_container_width=True):
                p["core_temp"] = max(p["baseline"], p["core_temp"] - 0.2); st.rerun()
        with act_cols[3]:
            if st.button(f"🌳 {t('rest_in_shade', lang_code)}", use_container_width=True):
                p["environment_temp"] = max(20, p["environment_temp"] - 8); p["core_temp"] = max(p["baseline"], p["core_temp"] - 0.4); st.rerun()


# ---------- APP ----------
def main():
    # Language selector
    top, langc = st.columns([3, 1])
    with langc:
        language = st.radio("Language / اللغة", ["English", "العربية"], horizontal=True)
    lang_code = "en" if language == "English" else "ar"

    # Header
    st.markdown(
        f"""
<div style='background:linear-gradient(45deg,#FF6B6B,#4ECDC4);padding:18px;border-radius:10px;text-align:center;color:white'>
  <h1 style='margin:0'>{t('heat_safety_demo', lang_code)}</h1>
  <h3 style='margin:0'>🚨 {t('demo_mode', lang_code)} — FOR EDUCATIONAL PURPOSES ONLY 🚨</h3>
</div>
""",
        unsafe_allow_html=True,
    )

    # ---- Session defaults ----
    if "demo" not in st.session_state:
        st.session_state.demo = {
            "core_temp": 36.6,
            "baseline": 36.6,
            "environment_temp": 32.0,
            "symptoms": [],
        }
    if "history" not in st.session_state:
        st.session_state.history = []
    if "live_on" not in st.session_state:
        st.session_state.live_on = False
    if "sample_every" not in st.session_state:
        st.session_state.sample_every = 2
    if "view" not in st.session_state:
        st.session_state.view = "scenarios"
    if "demo_running" not in st.session_state:
        st.session_state.demo_running = False

    # ---- Navigation (persistent) ----
    st.markdown("<br>", unsafe_allow_html=True)
    nav = st.columns(4)
    with nav[0]:
        if st.button(f"🎯 {t('scenarios', lang_code)}", use_container_width=True):
            st.session_state.view = "scenarios"
    with nav[1]:
        if st.button(f"⚙️ {t('custom', lang_code)}", use_container_width=True):
            st.session_state.view = "custom"
    with nav[2]:
        if st.button(f"🎬 {t('live_demo', lang_code)}", use_container_width=True):
            st.session_state.view = "live"
    with nav[3]:
        if st.button(f"📚 {t('learn', lang_code)}", use_container_width=True):
            st.session_state.view = "learn"

    # ---- Route ----
    if st.session_state.view == "scenarios":
        view_scenarios(lang_code)
    elif st.session_state.view == "custom":
        view_custom(lang_code)
    elif st.session_state.view == "live":
        view_live_demo(lang_code)
    else:
        view_learn(lang_code)


if __name__ == "__main__":
    main()
