"""Analysis Reports: generate a news-ready AI report and preview the latest one."""

from html import escape

import streamlit as st

from ui import agent_runner, layout
from weather_agent import store
from weather_agent.insights import parse_answer

TIME_RANGES = {"Next 6 Hours": "the next 6 hours", "Next 12 Hours": "the next 12 hours", "Next 24 Hours": "the next 24 hours",
               "Next 48 Hours": "the next 48 hours", "Next 72 Hours": "the next 72 hours", "Next 7 Days": "the next 7 days"}
TYPE_PROMPTS = {
    "Weather & Storm Analysis": "a full weather, rain, storm and earthquake analysis",
    "Weather Update": "an up-to-date weather update",
    "Storm Analysis": "a storm and severe-weather risk analysis with forecast confidence and official warnings",
    "Rain Forecast": "an hour-by-hour rain forecast with totals and intensity",
    "Earthquake Report": "a recent earthquake activity report together with current weather",
}
FORMATS = {"Detailed (News)": "Write it as a detailed, news-ready article with a headline.",
           "Summary": "Keep it as a short summary."}

st.markdown("""<style>
div[class*="st-key-gen_form"], div[class*="st-key-latest"] { background:var(--card); border:1px solid var(--border);
  border-radius:14px; padding:1rem 1.1rem; }
div[class*="st-key-gen_form"] .stButton button { background:linear-gradient(135deg,#7c3aed,#4f46e5); border:0; color:#fff;
  font-weight:600; border-radius:10px; padding:.65rem; }
.lr-title { font-size:1.35rem; font-weight:700; color:#fff; } .lr-date { color:var(--muted); font-size:.85rem; }
.done { background:rgba(34,197,94,.15); color:#4ade80; border:1px solid rgba(34,197,94,.35); border-radius:999px;
  padding:.12rem .6rem; font-size:.75rem; font-weight:600; float:right; }
.hero-img { height:190px; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:4.5rem;
  background:radial-gradient(circle at 30% 20%,#3b4f86,#0d1730 70%); border:1px solid var(--border); }
.kf-title { font-weight:700; color:#fff; margin:.2rem 0 .4rem; }
.kf li { list-style:none; margin:.3rem 0; font-size:.9rem; } .kf { padding:0; }
</style>""", unsafe_allow_html=True)

layout.topbar("Analysis Reports", "AI-powered weather analysis, storm assessment and news-ready insights", "📑")
form_col, latest_col = st.columns([1, 1.9], gap="medium")

with form_col.container(key="gen_form"):
    st.markdown("**📝 Generate Analysis Report**")
    location = st.text_input("Location", value=st.session_state.get("active_place") or "Lahore, Pakistan")
    report_type = st.selectbox("Report Type", list(TYPE_PROMPTS))
    time_range = st.selectbox("Time Range", list(TIME_RANGES), index=2)
    fmt = st.radio("Format", list(FORMATS), horizontal=True)
    generate = st.button("Generate with AI ✨", width="stretch")

if generate and location.strip():
    question = f"Create {TYPE_PROMPTS[report_type]} for {location.strip()} covering {TIME_RANGES[time_range]}. {FORMATS[fmt]}"
    reply = agent_runner.run(question, [{"role": "user", "content": question}], report_type)
    if reply is not None:
        st.session_state.latest_report = reply
        st.rerun()

latest = store.list_reports(limit=1)
with latest_col.container(key="latest"):
    head = st.columns([3, 1], vertical_alignment="center")
    head[0].markdown("**📄 Latest Generated Report**")
    if head[1].button("＋ New Analysis", width="stretch", type="primary"):
        st.session_state.messages = []
        st.switch_page("app_pages/chat.py")
    if not latest:
        st.info("No reports yet. Generate one with the form, or ask in Weather Chat.")
    else:
        r = latest[0]
        st.markdown(f"<span class='done'>Completed</span><div class='lr-title'>{escape(r['title'])}</div>"
                    f"<div class='lr-date'>{escape(r['created_at'])} UTC · {escape(r['report_type'])}</div>",
                    unsafe_allow_html=True)
        img, findings = st.columns([1, 1.25], vertical_alignment="top")
        img.markdown("<div class='hero-img'>⛈️</div>", unsafe_allow_html=True)
        bullets = parse_answer(r["answer"]).bullets[:6]
        findings.markdown("<div class='kf-title'>Key Findings</div><ul class='kf'>" + "".join(
            f"<li>✅ <b>{escape(k)}:</b> {escape(v[:140])}</li>" for k, v in bullets) + "</ul>", unsafe_allow_html=True)
        actions = st.columns(3)
        with actions[0].popover("👁 View Report", width="stretch"):
            st.markdown(r["answer"])
        pdf = store.report_pdf(r["id"])
        if pdf:
            actions[1].download_button("⬇ Download PDF", pdf, file_name=f"zentro-report-{r['id']}.pdf",
                                       mime="application/pdf", width="stretch", type="primary")
        with actions[2].popover("🔗 Share", width="stretch"):
            st.caption("Download the PDF and send it, or share the app link from your browser.")
