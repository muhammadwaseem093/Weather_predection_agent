"""Global Weather: live worldwide heat map (temperature, precipitation, wind, clouds, pressure) with city labels."""

from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from ui import cards, common, layout, screens
from weather_agent import world
from weather_agent.weather import Location, WeatherError, describe

WORLD_CITIES = ["London, United Kingdom", "New York, United States", "Beijing, China", "Sydney, Australia",
                "Sao Paulo, Brazil", "Cairo, Egypt", "Moscow, Russia", "Tokyo, Japan"]

query = layout.topbar("Global Weather", "Live weather conditions, temperature, precipitation and storms worldwide", "🌍",
                      search="Search any city, country or region", search_key="search_global")


def _first_place(name: str) -> Location | None:
    try:
        results = common.search(name)
    except WeatherError:
        return None
    return results[0] if results else None


names = list(dict.fromkeys(st.session_state.get("locations", []) + WORLD_CITIES + ([query] if query else [])))

with st.spinner("Loading live global weather…"):
    try:
        cells = common.world_grid()
    except WeatherError as error:
        st.error(str(error))
        st.stop()
    with ThreadPoolExecutor(max_workers=8) as pool:  # geocoding is cached; first load runs in parallel
        found = list(pool.map(_first_place, names))
    places = [p for p in found if p is not None]
    try:
        now = world.current_at([(p.latitude, p.longitude) for p in places])
    except WeatherError:
        now = []
    cities = [{"name": p.name, "lat": p.latitude, "lon": p.longitude, "temp": float(c.get("temperature_2m") or 0),
               "icon": cards.icon(describe(c.get("weather_code")), 12 if c.get("is_day", 1) else 0)}
              for p, c in zip(places, now)]

if query and not any(c["name"].lower() in query.lower() for c in cities):
    st.warning(f"No place found for '{query}'.")
screens.show(screens.world_html(cells, cities, 10))
choice = st.selectbox("Open a full AI analysis for", [c["name"] for c in cities])
if st.button("Analyse with AI", type="primary"):
    layout.ask(layout.QUICK_QUESTION.format(place=choice), choice)
