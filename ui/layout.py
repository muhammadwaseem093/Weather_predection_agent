"""App shell from the design reference: sidebar (brand, nav, quick locations, plan card) and top bar."""

from html import escape

import streamlit as st

from ui.common import secret
from weather_agent import agent

NAV = [
    ("app_pages/chat.py", "Weather Chat", ":material/chat_bubble:"),
    ("app_pages/live.py", "Live Weather", ":material/partly_cloudy_day:"),
    ("app_pages/storm.py", "Storm Tracker", ":material/cyclone:"),
    ("app_pages/rain.py", "Rain Forecast", ":material/rainy:"),
    ("app_pages/global_weather.py", "Global Weather", ":material/public:"),
    ("app_pages/reports.py", "Analysis Reports", ":material/description:"),
    ("app_pages/saved.py", "Saved Reports", ":material/bookmark:"),
]
ADMIN = ("app_pages/admin.py", "Admin", ":material/admin_panel_settings:")
DEFAULT_LOCATIONS = ["Lahore, Pakistan", "Karachi, Pakistan", "Islamabad, Pakistan", "Riyadh, Saudi Arabia", "Dubai, UAE"]
QUICK_QUESTION = "What is the weather in {place} today and will it rain in the next 24 hours? Also provide a storm risk analysis."


def ask(question: str, place: str | None = None) -> None:
    """Send a question to the chat page (used by quick locations and page actions)."""
    st.session_state.pending = question
    if place:
        st.session_state.active_place = place
        st.session_state.dash_query = place
    st.switch_page("app_pages/chat.py")


def sidebar(current: str) -> None:
    st.session_state.setdefault("locations", list(DEFAULT_LOCATIONS))
    with st.sidebar:
        st.markdown(
            "<div class='brand'><div class='brand-icon'>⛈️</div><div><div class='brand-name'>Zentro AI</div>"
            "<div class='brand-sub'>Weather Agent <span class='ai-chip'>AI</span></div></div></div>",
            unsafe_allow_html=True,
        )
        if st.button("＋  New Query", key="new_query", width="stretch"):
            st.session_state.messages = []
            st.session_state.active_place = None
            st.switch_page("app_pages/chat.py")
        for path, title, icon in NAV:
            slug = title.lower().replace(" ", "_")
            with st.container(key=f"nav_active_{slug}" if title == current else f"nav_{slug}"):
                st.page_link(path, label=title, icon=icon)

        st.markdown("<div class='side-title'>Quick Locations</div>", unsafe_allow_html=True)
        active = st.session_state.get("active_place")
        for i, place in enumerate(st.session_state.locations):
            key = f"quick_active_{i}" if place == active else f"quick_{i}"
            if st.button(f"📍  {place}", key=key, width="stretch"):
                ask(QUICK_QUESTION.format(place=place), place)
        with st.popover("＋  Add Location", width="stretch"):
            new = st.text_input("City, Country", placeholder="e.g. Tokyo, Japan", key="new_location")
            if st.button("Add", key="add_location", type="primary") and new.strip():
                if new.strip() not in st.session_state.locations:
                    st.session_state.locations.append(new.strip())
                st.rerun()

        with st.container(key=f"nav_active_admin" if current == ADMIN[1] else "nav_admin"):
            st.page_link(ADMIN[0], label=ADMIN[1], icon=ADMIN[2])
        st.markdown(
            "<div class='pro-card'><div class='pro-row'><span>👑 Pro Plan</span><span class='pro-active'>Active</span></div>"
            "<div class='pro-feat'>AI Forecast • Storm Alerts • Earthquakes • PDF Reports</div></div>",
            unsafe_allow_html=True,
        )


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return ("".join(p[0] for p in parts[:2]) or "U").upper()


def _settings() -> None:
    st.markdown("**Profile & settings**")
    st.session_state.user_name = st.text_input("Your name", value=st.session_state.get("user_name") or secret("USER_NAME") or "User")
    st.session_state.api_key = st.text_input(
        "Google Gemini API key", value=st.session_state.get("api_key") or secret("GOOGLE_API_KEY"), type="password",
        help="Get one at https://aistudio.google.com/apikey",
    )
    st.session_state.model = st.text_input("Model", value=st.session_state.get("model") or secret("MODEL") or agent.DEFAULT_MODEL)
    st.caption("Data: Open-Meteo · USGS · NWS · RainViewer · Esri")


def topbar(title: str, subtitle: str, icon: str = "⛈️", search: str | None = None,
           search_key: str = "top_search", default: str = "") -> str | None:
    """Page header. With `search` (a placeholder) it shows a search box like the design's data pages,
    otherwise Export PDF and Share. Always: notifications and the profile menu. Returns the search text."""
    st.session_state.setdefault("api_key", secret("GOOGLE_API_KEY"))
    st.session_state.setdefault("model", secret("MODEL") or agent.DEFAULT_MODEL)
    if search is not None:
        cols = st.columns([5.2, 3.5, .55, .55], vertical_alignment="center")
        with cols[1].container(key="top_searchbox"):
            query = st.text_input("Search", placeholder=f"🔍  {search}", key=search_key,
                                  value=st.session_state.get(search_key, default), label_visibility="collapsed")
        _title(cols[0], title, subtitle, icon)
        _bell_and_avatar(cols[2], cols[3])
        st.markdown("<hr class='topbar-sep'>", unsafe_allow_html=True)
        return query
    cols = st.columns([6.2, 1.45, 1.05, .55, .55], vertical_alignment="center")
    _title(cols[0], title, subtitle, icon)
    _export_and_share(cols[1], cols[2])
    _bell_and_avatar(cols[3], cols[4])
    st.markdown("<hr class='topbar-sep'>", unsafe_allow_html=True)
    return None


def _title(col, title: str, subtitle: str, icon: str) -> None:
    col.markdown(
        f"<div class='topbar-title'><div class='topbar-icon'>{icon}</div><div><div class='topbar-name'>{escape(title)}</div>"
        f"<div class='topbar-sub'>{escape(subtitle)}</div></div></div>",
        unsafe_allow_html=True,
    )


def _export_and_share(export_col, share_col) -> None:
    latest = st.session_state.get("latest_pdf")
    with export_col.container(key="top_export"):
        if latest:
            st.download_button("📄 Export PDF", latest[0], file_name=latest[1], mime="application/pdf", width="stretch")
        else:
            st.button("📄 Export PDF", disabled=True, width="stretch", help="Ask a question first")
    with share_col.container(key="top_share"), st.popover("🔗 Share", width="stretch"):
        url = getattr(st.context, "url", "") or ""
        st.markdown("Share this app:")
        st.code(url or "Copy the address from your browser bar", language=None)
        if latest:
            st.caption("Or download the latest PDF report with Export PDF and send it.")


def _bell_and_avatar(bell_col, avatar_col) -> None:
    notes = st.session_state.get("notifications", [])
    with bell_col.container(key="top_bell"), st.popover("🔔" + (" •" if notes else "")):
        st.markdown("**Notifications**")
        for note in notes[-6:][::-1] or ["No alerts yet. Official warnings and strong earthquakes appear here."]:
            st.markdown(f"- {note}")
    with avatar_col.container(key="top_avatar"), st.popover(_initials(st.session_state.get("user_name") or "User")):
        _settings()
