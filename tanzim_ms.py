# =========================
# Heat Safety Simulator (Educational Sandbox) — English / العربية
# =========================
# - Simulator-only: no journal, no live-demo tab, no data saving
# - Many scenarios to apply, then tweak with sliders
# - Continuous Plotly chart (Core / Baseline / Feels-like) via Live tracking
# - Status + Why panel uses Uhthoff (Δ >= 0.5 °C), absolute core, env bump
# - "Simulate ..." buttons are what-if actions (change numbers only)

import time
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ---------- CONFIG ----------
st.set_page_config(page_title="Heat Safety Simulator", page_icon="🌡️", layout="wide")

# ---------- TRANSLATIONS ----------
T = {
    "title": {"en": "Heat Safety Simulator", "ar": "محاكاة السلامة من الحرارة"},
    "demo_banner": {"en": "DEMO MODE — Educational only. Nothing is saved.", "ar": "وضع التجربة — لأغراض تعليمية فقط. لا يتم حفظ أي بيانات."},

    "simulator": {"en": "Simulator", "ar": "المحاكاة"},
    "learn": {"en": "Learn", "ar": "تعلم"},

    "scenarios": {"en": "Scenarios", "ar": "السيناريوهات"},
    "apply": {"en": "Apply Scenario", "ar": "تطبيق السيناريو"},
    "custom": {"en": "Custom", "ar": "مخصص"},
    "core_temp": {"en": "Core Temperature", "ar": "درجة حرارة الجسم"},
    "baseline": {"en": "Baseline", "ar": "خط الأساس"},
    "feels_like": {"en": "Feels Like (ambient)", "ar": "الشعور الحقيقي (البيئة)"},
    "symptoms": {"en": "Symptoms (validation only — not used for scoring)", "ar": "الأعراض (للتحقق فقط — لا تدخل في التقييم)"},
    "live_tracking": {"en": "Live tracking (auto-append)", "ar": "تتبع مباشر (إضافة تلقائية)"},
    "sample_every": {"en": "Sample every (s)", "ar": "التسجيل كل (ثانية)"},
    "clear_plot": {"en": "Clear plot", "ar": "مسح الرسم"},
    "simulate_actions": {"en": "Simulate actions (what-if, changes numbers only)", "ar": "محاكاة الإجراءات (للتجربة فقط، تغيّر القيم فقط)"},
    "simulate_vest": {"en": "Simulate Cooling Vest", "ar": "محاكاة سترة التبريد"},
    "simulate_indoors": {"en": "Simulate Moving Indoors", "ar": "محاكاة الانتقال للداخل"},
    "simulate_hydrate": {"en": "Simulate Hydration", "ar": "محاكاة الترطيب"},
    "simulate_shade": {"en": "Simulate Rest in Shade", "ar": "محاكاة الراحة في الظل"},

    "status": {"en": "Status", "ar": "الحالة"},
    "safe": {"en": "Safe", "ar": "آمن"},
    "caution": {"en": "Caution", "ar": "حذر"},
    "high": {"en": "High Risk", "ar": "خطر مرتفع"},
    "critical": {"en": "Critical", "ar": "حرج"},
    "why": {"en": "Why this status (rules firing)", "ar": "سبب الحالة (القواعد المفعّلة)"},
    "triggers": {"en": "Triggers", "ar": "المحفزات"},

    "delta": {"en": "Δ vs baseline", "ar": "فرق عن خط الأساس"},
    "recommend": {"en": "Recommended action", "ar": "الإجراء الموصى به"},

    # Learn text (kept concise)
    "learn_md_en": {
        "en": """
### Uhthoff’s phenomenon
- Small rises in **core temp (~+0.5°C)** can temporarily worsen MS symptoms.
- Usually **reverses** after cooling.

### App thresholds (heuristics)
- **ΔCore ≥ 0.5°C** → *Caution*
- **Core ≥ 37.8°C** → *Caution*
- **Core ≥ 38.0°C** → *High*
- **Core ≥ 38.5°C** → *Critical*
- **Feels-like ≥ 38°C** → bump
- **Feels-like ≥ 42°C** → high bump

### Helpful “what-ifs”
Cooling garments, AC/fans/shade, hydration, timing (avoid peak heat), pre-cooling.
        """,
        "ar": ""
    },
    "learn_md_ar": {
        "en": "",
        "ar": """
### ظاهرة أوتهوف
- ارتفاع بسيط في **حرارة الجسم (~+0.5°C)** قد يسبب تدهورًا مؤقتًا للأعراض.
- عادة **يتحسن** عند التبريد.

### عتبات التطبيق (إرشادية)
- **فرق درجة ≥ 0.5°C** → *حذر*
- **حرارة ≥ 37.8°C** → *حذر*
- **حرارة ≥ 38.0°C** → *خطر مرتفع*
- **حرارة ≥ 38.5°C** → *حرج*
- **الشعور الحقيقي ≥ 38°C** → زيادة
- **الشعور الحقيقي ≥ 42°C** → زيادة كبيرة

### محاكاة مفيدة
سترات تبريد، تكييف/مراوح/ظل، ترطيب، توقيت مناسب، تبريد مسبق.
        """
    }
}

def tr(key, lang="en"):
    return T.get(key, {}).get(lang, key)

# ---------- RISK ENGINE ----------
def classify_status(core_c: float, baseline_c: float, feels_c: float):
    """
    Levels by rules (in order of importance):
      - Uhthoff: ΔCore >= 0.5°C -> at least Caution
      - Absolute core: 37.8 / 38.0 / 38.5 -> Caution / High / Critical
      - Environment bump: Feels-like 38 / 42 -> Caution / High
    Returns (status_key, triggers_list)
    """
    delta = core_c - baseline_c
    level = 0
    triggers = []

    # Uhthoff
    if delta >= 0.5:
        level = max(level, 1)
        triggers.append(f"ΔCore +{delta:.1f}°C ≥ 0.5°C")

    # Absolute core
    if core_c >= 38.5:
        level = 3
        triggers.append("Core ≥ 38.5°C")
    elif core_c >= 38.0:
        level = max(level, 2)
        triggers.append("Core ≥ 38.0°C")
    elif core_c >= 37.8:
        level = max(level, 1)
        triggers.append("Core ≥ 37.8°C")

    # Environment bump
    if feels_c >= 42.0:
        level = max(level, 2)
        triggers.append("Feels-like ≥ 42°C")
    elif feels_c >= 38.0:
        level = max(level, 1)
        triggers.append("Feels-like ≥ 38°C")

    status_keys = ["safe", "caution", "high", "critical"]
    return status_keys[level], triggers

def status_color(key: str) -> str:
    return {"safe": "#E6F4EA", "caution": "#FFF8E1", "high": "#FFE0E0", "critical": "#FFCDD2"}.get(key, "#EEE")

def status_emoji(key: str) -> str:
    return {"safe": "✅", "caution": "⚠️", "high": "🔴", "critical": "🚨"}.get(key, "❓")

# ---------- SCENARIOS (many, meaningful) ----------
# Each scenario sets starting values; users can tweak
SCENARIOS = {
    # Daily life
    "Morning commute (Dubai summer)":        {"core": 37.4, "feels": 41.0, "desc": "Hot car, sun exposure"},
    "School pickup (mid-afternoon sun)":     {"core": 37.5, "feels": 40.0, "desc": "Short walk + parking lot heat"},
    "Grocery run (indoor AC)":               {"core": 37.0, "feels": 26.0, "desc": "Cool indoor environment"},
    "Office day (normal AC)":                {"core": 36.8, "feels": 24.0, "desc": "Steady cool conditions"},
    "Office AC failure":                     {"core": 37.8, "feels": 35.0, "desc": "Indoor heat buildup"},
    "Night AC outage":                       {"core": 37.6, "feels": 33.0, "desc": "Poor sleep + warm room"},

    # Exercise & activity
    "Light walk (shade, breezy)":            {"core": 37.2, "feels": 33.0, "desc": "Shaded path + airflow"},
    "Moderate exercise (humid)":             {"core": 37.9, "feels": 39.0, "desc": "Humidity slows cooling"},
    "Vigorous exercise (direct sun)":        {"core": 38.0, "feels": 42.0, "desc": "High heat load outdoors"},
    "Treadmill (gym, with fan)":             {"core": 37.6, "feels": 28.0, "desc": "Cooling airflow helps"},
    "Treadmill (no fan)":                    {"core": 37.7, "feels": 31.0, "desc": "Less convective cooling"},
    "Outdoor chores (midday)":               {"core": 37.8, "feels": 40.0, "desc": "Sun + exertion"},
    "Beach at noon (sun + sand)":            {"core": 37.6, "feels": 43.0, "desc": "High radiant heat from sand"},

    # Health / internal load
    "Fever at home":                         {"core": 38.2, "feels": 28.0, "desc": "Elevated core despite mild ambient"},
    "Hot bath / sauna":                      {"core": 38.3, "feels": 45.0, "desc": "Rapid heating"},
    "MS flare-up at rest":                   {"core": 38.1, "feels": 27.0, "desc": "Internal rise, quiet environment"},

    # Cooling strategies & timing
    "Evening stroll (cooler hours)":         {"core": 37.0, "feels": 34.0, "desc": "Better timing"},
    "Evening walk (cooling vest)":           {"core": 37.0, "feels": 38.0, "desc": "Vest blunts rise outdoors"},
    "Move to mall (pre-cool)":               {"core": 36.9, "feels": 24.0, "desc": "Pre-cool before activity"},

    # Transport / incidents
    "Car breakdown (direct sun)":            {"core": 37.8, "feels": 44.0, "desc": "Trapped heat, high risk"},
    "Short taxi ride (AC on)":               {"core": 37.1, "feels": 26.0, "desc": "Brief exposure then cool"},
}

# ---------- PLOTTING ----------
def append_history_point():
    p = st.session_state.sim
    st.session_state.history.append({
        "ts": datetime.now().strftime("%H:%M:%S"),
        "core": float(p["core"]),
        "baseline": float(p["baseline"]),
        "feels": float(p["feels"]),
    })

def plot_history(lang):
    if not st.session_state.history:
        st.info("Turn on **Live tracking** to start the plot.")
        return
    df = pd.DataFrame(st.session_state.history)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["ts"], y=df["feels"], mode="lines+markers", name=tr("feels_like", lang)))
    fig.add_trace(go.Scatter(x=df["ts"], y=df["core"], mode="lines+markers", name=tr("core_temp", lang)))
    fig.add_trace(go.Scatter(x=df["ts"], y=df["baseline"], mode="lines", name=tr("baseline", lang)))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12), xaxis_title="Time", yaxis_title="°C")
    st.plotly_chart(fig, use_container_width=True)

# ---------- STATUS RENDER ----------
def render_status(lang):
    p = st.session_state.sim
    key, trig = classify_status(p["core"], p["baseline"], p["feels"])
    badge = f"<div style='display:inline-block;padding:6px 10px;border-radius:8px;background:{status_color(key)};font-weight:700'>{status_emoji(key)} {tr(key, lang)}</div>"
    st.markdown(badge, unsafe_allow_html=True)

    # Metrics
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric(tr("core_temp", lang), f"{p['core']:.1f}°C", f"Δ{(p['core']-p['baseline']):+.1f}°C")
    with m2:
        st.metric(tr("baseline", lang), f"{p['baseline']:.1f}°C")
    with m3:
        st.metric(tr("feels_like", lang), f"{p['feels']:.1f}°C")

    with st.expander(tr("why", lang), expanded=True):
        if trig:
            for tline in trig:
                st.write("• " + tline)
        else:
            st.write("• No thresholds tripped yet.")

# ---------- APP ----------
def main():
    # Language
    top, langc = st.columns([3, 1])
    with langc:
        lang = "en" if st.radio("Language / اللغة", ["English", "العربية"], horizontal=True) == "English" else "ar"

    # Banner
    st.markdown(
        f"""
<div style='background:linear-gradient(45deg,#FF6B6B,#4ECDC4);padding:16px;border-radius:10px;text-align:center;color:white'>
  <h1 style='margin:0'>{tr("title", lang)}</h1>
  <h4 style='margin:6px 0 0'>{tr("demo_banner", lang)}</h4>
</div>
""",
        unsafe_allow_html=True,
    )

    # Session defaults
    if "sim" not in st.session_state:
        st.session_state.sim = {"core": 36.6, "baseline": 36.6, "feels": 32.0}
    if "history" not in st.session_state:
        st.session_state.history = []
    if "live_on" not in st.session_state:
        st.session_state.live_on = False
    if "sample_every" not in st.session_state:
        st.session_state.sample_every = 2

    # Tabs (Simulator + Learn)
    tabs = st.tabs([tr("simulator", lang), tr("learn", lang)])

    with tabs[0]:
        # Top: Scenarios (left) + Custom sliders (right)
        left, right = st.columns([0.55, 0.45])

        with left:
            st.subheader("🎯 " + tr("scenarios", lang))
            scen_name = st.selectbox("📋", list(SCENARIOS.keys()), index=0)
            sc = SCENARIOS[scen_name]

            if st.button("✅ " + tr("apply", lang), use_container_width=True):
                st.session_state.sim["core"] = float(sc["core"])
                st.session_state.sim["feels"] = float(sc["feels"])
                # keep user's baseline as-is (personal), but you can modify if you prefer:
                # st.session_state.sim["baseline"] = 36.6
                append_history_point()
                st.success(sc.get("desc", "Applied"))
                st.rerun()

            st.caption(sc.get("desc", ""))

        with right:
            st.subheader("⚙️ " + tr("custom", lang))
            st.session_state.sim["core"] = st.slider(f"🌡️ {tr('core_temp', lang)} (°C)", 36.0, 39.5, float(st.session_state.sim["core"]), 0.1)
            st.session_state.sim["baseline"] = st.slider(f"📊 {tr('baseline', lang)} (°C)", 36.0, 37.5, float(st.session_state.sim["baseline"]), 0.1)
            st.session_state.sim["feels"] = st.slider(f"🌡️ {tr('feels_like', lang)} (°C)", 25.0, 50.0, float(st.session_state.sim["feels"]), 1.0)

            # Symptoms (validation only, not in scoring) — optional visual note
            st.multiselect(f"📋 {tr('symptoms', lang)}", options=[
                "Blurred vision / ضبابية الرؤية",
                "Fatigue / إرهاق",
                "Weakness / ضعف",
                "Balance issues / مشاكل توازن",
                "Sensory changes / تغيرات حسية",
            ], default=[])

        st.markdown("---")

        # Live tracking + Plot
        lc1, lc2, lc3 = st.columns([0.35, 0.35, 0.3])
        with lc1:
            st.session_state.live_on = st.toggle(tr("live_tracking", lang), value=st.session_state.live_on, help="Appends a point each refresh")
        with lc2:
            st.session_state.sample_every = st.select_slider(tr("sample_every", lang), options=[1, 2, 3, 5, 10], value=st.session_state.sample_every)
        with lc3:
            if st.button("🧹 " + tr("clear_plot", lang)):
                st.session_state.history.clear()
                st.toast("Cleared")

        # Append + auto-refresh when live
        if st.session_state.live_on:
            append_history_point()
            try:
                st.autorefresh(interval=st.session_state.sample_every * 1000, key="auto_sim")
            except Exception:
                pass

        plot_history(lang)

        # Status + Why
        st.markdown("---")
        st.subheader("🧭 " + tr("status", lang))
        render_status(lang)

        # Simulate actions (what-if only)
        st.markdown("---")
        st.subheader("🧪 " + tr("simulate_actions", lang))
        ac1, ac2, ac3, ac4 = st.columns(4)
        if ac1.button("❄️ " + tr("simulate_vest", lang), use_container_width=True):
            st.session_state.sim["core"] = max(st.session_state.sim["baseline"], st.session_state.sim["core"] - 0.6)
            st.session_state.sim["feels"] = max(20.0, st.session_state.sim["feels"] - 2.0)
            st.rerun()
        if ac2.button("🏠 " + tr("simulate_indoors", lang), use_container_width=True):
            st.session_state.sim["feels"] = 25.0
            st.session_state.sim["core"] = max(st.session_state.sim["baseline"], st.session_state.sim["core"] - 0.3)
            st.rerun()
        if ac3.button("💧 " + tr("simulate_hydrate", lang), use_container_width=True):
            st.session_state.sim["core"] = max(st.session_state.sim["baseline"], st.session_state.sim["core"] - 0.2)
            st.rerun()
        if ac4.button("🌳 " + tr("simulate_shade", lang), use_container_width=True):
            st.session_state.sim["feels"] = max(20.0, st.session_state.sim["feels"] - 5.0)
            st.session_state.sim["core"] = max(st.session_state.sim["baseline"], st.session_state.sim["core"] - 0.4)
            st.rerun()

    with tabs[1]:
        st.subheader("📚 " + tr("learn", lang))
        if lang == "en":
            st.markdown(T["learn_md_en"]["en"])
        else:
            st.markdown(T["learn_md_ar"]["ar"])


if __name__ == "__main__":
    main()
