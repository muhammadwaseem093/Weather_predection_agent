"""Zentro AI Weather Agent (Streamlit entry point): theme, navigation and the app shell."""

import streamlit as st
from dotenv import load_dotenv

from ui import layout
from weather_agent.styles import CSS

load_dotenv()

st.set_page_config(page_title="Zentro AI · Weather Agent", page_icon="⛈️", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

pages = [st.Page(path, title=title, icon=icon, default=path == layout.NAV[0][0])
         for path, title, icon in [*layout.NAV, layout.ADMIN]]
# The sidebar menu is drawn by layout.sidebar to match the design, so Streamlit's own menu is hidden.
page = st.navigation(pages, position="hidden")
layout.sidebar(page.title)
page.run()
