"""Live Weather, Rain Forecast and Storm Tracker pages: search, the page screen, AI analysis and PDF."""

from datetime import datetime

import streamlit as st

from ui import analysis, common, layout, screens
from weather_agent.report import build_pdf
from weather_agent.storms import Cyclone
from weather_agent.weather import Location, WeatherError, WeatherReport

REFRESH_SECONDS = 600  # live data refresh while the page is open
STORM_WINDOWS = {"Next 6h": 6, "12h": 12, "24h": 24, "48h": 48, "72h": 72}
NEAR_STORM_KM = 1500
PLACEHOLDERS = {
    "live": "Search city (e.g. Lahore, Dubai, London)",
    "rain": "Search city (e.g. Lahore, Karachi)",
    "storm": "Search city (e.g. Lahore, Dubai)",
}


def _resolve(query: str) -> Location:
    try:
        places = common.search(query) if query.strip() else []
    except WeatherError as error:
        st.error(str(error))
        st.stop()
    if not places:
        st.warning("No matching place. Try another spelling or add the country, e.g. 'Paris, France'.")
        st.stop()
    return places[0]


def storm_impacts(report: WeatherReport, storms: list[Cyclone]) -> list[tuple[str, str]]:
    near = [s for s in storms if s.distance_km is not None and s.distance_km <= NEAR_STORM_KM]
    items = []
    if near:
        s = near[0]
        items.append(("bad", f"{s.name} ({s.category}) is ~{s.distance_km:,.0f} km away - follow official guidance"))
    else:
        items.append(("ok", f"No direct cyclone threat to {report.location.name}"))
    storm_hours = report.storm_hours
    if storm_hours:
        items.append(("bad", f"{storm_hours[0].risk} local storm risk from {storm_hours[0].time[11:16]}: "
                             f"{'; '.join(storm_hours[0].reasons)}"))
    else:
        items.append(("ok", f"No severe local storms in the next {len(report.hours)} hours (model-based)"))
    if report.rain_hours:
        items.append(("warn", f"Rain likely for {len(report.rain_hours)} of the next {len(report.hours)} hours"))
    items.append(("warn", f"Monitor updates for the next {max(48, len(report.hours))} hours"))
    return items


def _analysis(focus: str, location: Location, report: WeatherReport) -> None:
    bullets = analysis.data_bullets(report, report.comparison, report.alerts, report.quakes)  # type: ignore[arg-type]
    answer = "## Analysis\n" + "\n".join(f"- **{k}:** {v}" for k, v in bullets)
    pdf = build_pdf(f"{focus.title()} analysis for {location.full_label}", answer, [report])
    filename = f"zentro-{focus}-{location.name.lower().replace(' ', '-')}-{datetime.now():%Y%m%d-%H%M}.pdf"
    st.session_state.latest_pdf = (pdf, filename)
    analysis.render(f"place_{focus}", bullets, pdf, filename)


def render(focus: str, title: str, subtitle: str, icon: str) -> None:
    default = st.session_state.get("active_place") or "Lahore, Pakistan"
    query = layout.topbar(title, subtitle, icon, search=PLACEHOLDERS[focus], search_key=f"search_{focus}", default=default)
    location = _resolve(query or default)
    st.session_state.active_place = location.label
    hours = 24
    if focus == "storm":
        window = st.segmented_control("Forecast window", list(STORM_WINDOWS), default="24h", label_visibility="collapsed")
        hours = STORM_WINDOWS[window or "24h"]

    @st.fragment(run_every=REFRESH_SECONDS)
    def live() -> None:
        try:
            report = common.report(location, hours)
            report.comparison = common.comparison(location, hours)
            report.alerts = common.alerts(location)
            report.quakes = common.quakes(location)
        except WeatherError as error:
            st.error(str(error))
            return
        if focus == "live":
            screens.show(screens.live_html(report))
        elif focus == "rain":
            screens.show(screens.rain_html(report, report.comparison))  # type: ignore[arg-type]
        else:
            try:
                storms = common.cyclones(location)
            except WeatherError:
                storms = []
                st.caption("Active-cyclone feed (GDACS) is unavailable right now.")
            screens.show(screens.storm_html(report, storms, common.radar_url(), storm_impacts(report, storms)))
        _analysis(focus, location, report)
        st.caption(f"Live data · refreshes every {REFRESH_SECONDS // 60} min · last fetch {report.fetched_at}")

    live()
    st.markdown("**🤖 Ask the AI agent about this place**")
    actions = st.columns(3)
    prompts = [
        ("📰 City news report", f"Write a professional news weather report for {location.full_label}."),
        ("🌐 Country summary", f"Write a country-specific weather news summary for {location.country}."),
        ("⛈️ Full AI analysis", f"Full weather, rain, storm and earthquake analysis for {location.full_label} "
                               f"for the next {hours} hours."),
    ]
    for col, (label, prompt) in zip(actions, prompts):
        if col.button(label, width="stretch", key=f"ask_{focus}_{label}"):
            layout.ask(prompt, location.label)
