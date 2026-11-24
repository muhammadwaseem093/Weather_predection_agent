"""The "AI Analysis & Recommendation" card: parse the agent's answer, or build it from data."""

import re
from html import escape

import streamlit as st

from weather_agent.insights import REQUIRED, ParsedAnswer, data_bullets, findings, parse_answer  # noqa: F401  (re-exported)


def _bold(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(text))


def render(key: str, bullets: list[tuple[str, str]], pdf: bytes | None, filename: str | None) -> None:
    items = "".join(f"<li><span class='an-check'>✓</span><span><b>{escape(k)}:</b> {_bold(v)}</span></li>" for k, v in bullets)
    with st.container(key=f"analysis_{key}"):
        left, right = st.columns([2.3, 1], vertical_alignment="center")
        left.markdown(f"<div class='an-title'>✨ AI Analysis &amp; Recommendation</div><ul class='an-list'>{items}</ul>",
                      unsafe_allow_html=True)
        with right:
            if pdf:
                st.download_button("📄 Download Full Analysis (PDF)", pdf, file_name=filename or "zentro-analysis.pdf",
                                   mime="application/pdf", key=f"dl_{key}", width="stretch")
                st.markdown("<div class='an-note'>(Weather Report • Forecast • Storm Analysis • Earthquakes • Charts)</div>",
                            unsafe_allow_html=True)
