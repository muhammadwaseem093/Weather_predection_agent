"""Weather Chat: the deep agent answers; every weather answer shows Weather, Rain, Storms and Earthquakes."""

from datetime import datetime
from html import escape

import streamlit as st

from ui import agent_runner, analysis, cards, common, layout

EXAMPLES = [
    "What is the weather in Lahore today and will it rain in the next 24 hours? Also provide a storm risk analysis.",
    "Will there be a thunderstorm in Miami in the next 12 hours?",
    "Any earthquakes near Tokyo this week, and what's the weather there?",
    "Weekly forecast for Dubai with daily rain chances",
    "Country weather news summary for Pakistan",
    "Write a news-ready weather report for Istanbul",
]


def welcome() -> None:
    st.markdown(
        "<div class='welcome'><div class='welcome-icon'>⛈️</div><h2>Ask Zentro AI about the weather</h2>"
        "<p>Every answer covers four things for the place you ask about: up-to-date weather, rain, "
        "storms and earthquakes, with charts, radar and a downloadable PDF report.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='examples-title'>✨ Try these examples</div>", unsafe_allow_html=True)
    cols = st.columns(3)
    for i, text in enumerate(EXAMPLES):
        with cols[i % 3].container(key=f"example_{i}"):
            if st.button(text, width="stretch"):
                st.session_state.pending = text
                st.rerun()


def user_bubble(message: dict) -> None:
    st.markdown(
        f"<div class='msg-user'><div class='bubble-user'>{escape(message['content'])}</div>"
        f"<div class='avatar-user'>👤</div></div><div class='msg-time'>{message.get('time', '')}</div>",
        unsafe_allow_html=True,
    )


def ai_bubble(text: str) -> None:
    st.markdown(f"<div class='msg-ai'><div class='avatar-ai'>AI</div><div class='bubble-ai'>{escape(text)}</div></div>",
                unsafe_allow_html=True)


def place_panel(index: int, report, answer: str, pdf, filename) -> None:
    cards.render(report, report.comparison, report.alerts, report.quakes, common.radar_url())
    # The agent's own wording wins; any compulsory section it skipped is filled from live data.
    bullets = analysis.findings(report, answer)
    analysis.render(f"msg_{index}_{report.location.name}", bullets, pdf, filename)


def assistant_message(index: int, message: dict) -> None:
    parsed = analysis.parse_answer(message["content"])
    ai_bubble(parsed.intro or "Here is my analysis.")
    reports = message.get("reports", [])
    if len(reports) == 1:
        place_panel(index, reports[0], message["content"], message.get("pdf"), message.get("filename"))
    elif reports:
        for tab, report in zip(st.tabs([f"📍 {r.location.label}" for r in reports]), reports):
            with tab:
                place_panel(index, report, message["content"], message.get("pdf"), message.get("filename"))
    with st.expander("📝 Full analysis" + (f" · agent trace ({len(message['steps'])} steps)" if message.get("steps") else ""),
                     expanded=not reports):
        st.markdown(parsed.details if reports else message["content"])
        for step in message.get("steps", []):
            st.caption(f"**{step.title}**" + (f" — {step.detail[:200]}" if step.detail else ""))
        if message.get("pdf") and not reports:
            st.download_button("📄 Download PDF", message["pdf"], file_name=message["filename"],
                               mime="application/pdf", key=f"dl_plain_{index}")


def answer(question: str) -> None:
    messages = st.session_state.messages
    messages.append({"role": "user", "content": question, "time": datetime.now().strftime("%I:%M %p")})
    user_bubble(messages[-1])
    history = [{"role": m["role"], "content": m["content"]} for m in messages]
    reply = agent_runner.run(question, history)
    if reply is not None:
        messages.append(reply)
        st.rerun()


st.session_state.setdefault("messages", [])
st.session_state.setdefault("pending", None)
layout.topbar("AI Weather Agent", "Live weather, forecasts, storm prediction, earthquakes & detailed analysis", "🌦️")

# Read the question before drawing anything: once a chat starts, the welcome screen
# (branding and suggestions) is not drawn, so the conversation begins in a clear area.
typed = st.chat_input("Ask about any city's weather, rain, storms, earthquakes, or get detailed analysis…")
question = (typed or st.session_state.pending or "").strip()
st.session_state.pending = None

if not st.session_state.messages and not question:
    welcome()
for i, message in enumerate(st.session_state.messages):
    if message["role"] == "user":
        user_bubble(message)
    else:
        assistant_message(i, message)
if question:
    answer(question)
