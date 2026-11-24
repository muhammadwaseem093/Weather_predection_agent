"""Shared app plumbing: secrets, settings and cached weather lookups."""

import os

import streamlit as st

from weather_agent import quakes as quake_source
from weather_agent import sources, weather, world
from weather_agent import storms as storm_source

CACHE_SECONDS = 240  # below the shortest auto-refresh interval, so a refresh fetches fresh data


def secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except FileNotFoundError:  # no secrets.toml locally
        value = ""
    return str(value or os.getenv(name, ""))


@st.cache_data(ttl=3600, show_spinner=False)
def search(query: str) -> list[weather.Location]:
    return weather.search_locations(query)


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def report(location: weather.Location, hours: int = 24) -> weather.WeatherReport:
    return weather.fetch_report(location, hours=hours)


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def comparison(location: weather.Location, hours: int = 24) -> sources.ModelComparison:
    return sources.compare_models(location, hours)


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def alerts(location: weather.Location) -> sources.AlertResult:
    return sources.official_alerts(location)


@st.cache_data(ttl=600, show_spinner=False)
def radar_url() -> str | None:
    return sources.radar_tile_url()


@st.cache_data(ttl=600, show_spinner=False)
def quakes(location: weather.Location) -> quake_source.QuakeReport:
    return quake_source.recent_quakes(location)


@st.cache_data(ttl=900, show_spinner=False)
def cyclones(location: weather.Location) -> list[storm_source.Cyclone]:
    return storm_source.active_cyclones(location)


@st.cache_data(ttl=1800, show_spinner=False)
def world_grid() -> list[world.GridCell]:
    return world.world_grid()
