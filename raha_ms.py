def render_planner():
    if "user" not in st.session_state:
        st.warning(T["login_first"]); return
    st.title("🗺️ " + T["planner"])

    city = st.selectbox("📍 " + T["quick_pick"], GCC_CITIES, index=0, key="planner_city")
    weather, err = get_weather(city)
    if weather is None:
        st.error(f"{T['weather_fail']}: {err}"); return

    st.subheader("✅ Recommended cooler windows")  # FIXED: This line was indented incorrectly

    windows = best_windows_from_forecast(
        weather["forecast"],
        window_hours=2, top_k=8, max_feels_like=35.0, max_humidity=65
    )

    if not windows:
        st.info("No optimal windows found; consider early morning or after sunset.")
    else:
        # Group by date for clean headings
        by_day = defaultdict(list)
        for w in windows:
            day_key = w["start_dt"].strftime("%a %d %b")
            by_day[day_key].append(w)

        for day in sorted(by_day.keys(), key=lambda d: _dt.strptime(d, "%a %d %b")):
            st.markdown(f"#### {day}")
            day_windows = by_day[day]
            cols = st.columns(min(3, len(day_windows)))
            for i, w in enumerate(day_windows):
                with cols[i % len(cols)]:
                    st.markdown(f"**{w['start_dt'].strftime('%H:%M')} → {w['end_dt'].strftime('%H:%M')}**")
                    st.caption(f"Feels-like ~{w['avg_feels']}°C • Humidity {w['avg_hum']}%")
                    act = st.selectbox("Plan:", ["Walk","Groceries","Beach","Errand"], key=f"plan_{day}_{i}")
                    other_act = st.text_input(T["other_activity"], key=f"plan_other_{day}_{i}")
                    final_act = other_act.strip() if other_act.strip() else act
                    if st.button(T["add_to_journal"], key=f"add_{day}_{i}"):
                        entry = {
                            "type":"PLAN", "at": utc_iso_now(),
                            "city": city,
                            "start": w["start_dt"].strftime("%Y-%m-%d %H:%M"),
                            "end": w["end_dt"].strftime("%Y-%m-%d %H:%M"),
                            "activity": final_act,
                            "feels_like": w["avg_feels"], "humidity": w["avg_hum"]
                        }
                        insert_journal(st.session_state["user"], utc_iso_now(), entry)
                        st.success("Saved to Journal")
    
    st.markdown("---")
    st.subheader("🤔 What-if planner")
    act = st.selectbox("Activity type", ["Light walk (20–30 min)","Moderate exercise (45 min)","Outdoor errand (30–60 min)","Beach (60–90 min)"], key="what_if")
    fl = weather["feels_like"]; hum = weather["humidity"]
    go_badge = "🟢 Go" if (fl<34 and hum<60) else ("🟡 Caution" if (fl<37 and hum<70) else "🔴 Avoid now")
    st.markdown(f"**Now:** {go_badge} — feels-like {round(fl,1)}°C, humidity {int(hum)}%")

    tips_now = []
    if "walk" in act.lower(): tips_now += ["Shaded route", "Carry cool water", "Light clothing"]
    if "exercise" in act.lower(): tips_now += ["Pre-cool 15 min", "Indoor/AC if possible", "Electrolytes if >45 min"]
    if "errand" in act.lower(): tips_now += ["Park in shade", "Plan shortest path", "Pre-cool car 5–10 min"]
    if "beach" in act.lower(): tips_now += ["Umbrella + UV hat", "Cool pack in bag", "Rinse to cool"]
    if fl >= 36: tips_now += ["Cooling scarf/bandana", "Limit to cooler window"]
    if hum >= 60: tips_now += ["Prefer AC over fan", "Extra hydration"]
    tips_now = list(dict.fromkeys(tips_now))[:8]
    st.write("**Tips:**")
    st.write("- " + "\n- ".join(tips_now) if tips_now else "—")

    other_notes = st.text_area(T["what_if_tips"], height=100)
    if client and st.button(T["ask_ai_tips"]):
        q = f"My plan: {act}. Notes: {other_notes}. Current city feels-like {round(fl,1)}°C, humidity {int(hum)}%."
        ans, err2 = ai_response(q, app_language)
        st.info(ans if ans else (T["ai_unavailable"]))

    st.markdown("---")
    st.subheader("📍 Plan by place")
    place_q = st.text_input("Type a place (e.g., Saadiyat Beach)")
    if place_q:
        place, lat, lon = geocode_place(place_q)
        pw = get_weather_by_coords(lat, lon) if lat and lon else None
        if pw:
            st.info(f"{place}: feels-like {round(pw['feels_like'],1)}°C • humidity {int(pw['humidity'])}% • {pw['desc']}")
            better = "place" if pw["feels_like"] < weather["feels_like"] else "city"
            st.caption(f"Cooler now: **{place if better=='place' else city}**")
        else:
            st.warning("Couldn't fetch that place's weather.")

    st.caption(f"**{T['peak_heat']}:** " + ("; ".join(weather["peak_hours"]) if weather.get("peak_hours") else "—"))
    with st.expander(T["quick_tips"], expanded=False):
        st.markdown("""- Avoid 10–4 peak heat; use shaded parking.
- Pre-cool before errands; carry cool water.
- Prefer AC indoors; wear light, loose clothing.""")
