"""Saved Reports: view, download and manage every generated weather analysis report."""

from html import escape

import streamlit as st

from ui import layout
from weather_agent import store

TABS = ("All Reports", "Weather & Storm Analysis", "Weather Update", "Storm Analysis", "Rain Forecast", "Earthquake Report")
TYPE_STYLE = {"Weather & Storm Analysis": "sa", "Storm Analysis": "sa", "Rain Forecast": "rf",
              "Weather Update": "wu", "Earthquake Report": "eq"}

st.markdown("""<style>
.rt-head, .rt-row { display:grid; grid-template-columns:3.0fr 1.3fr 1.5fr 2.31fr; gap:.6rem; align-items:center; }
.rt-head { color:var(--muted); font-size:.8rem; font-weight:600; padding:.4rem .2rem; border-bottom:1px solid var(--border); }
.rt-title { display:flex; align-items:center; gap:.6rem; font-weight:600; font-size:.9rem; }
.pdf-ico { background:#dc2626; color:#fff; font-size:.6rem; font-weight:800; border-radius:4px; padding:.25rem .3rem; }
.tb { border-radius:999px; padding:.15rem .6rem; font-size:.75rem; font-weight:600; }
.tb.sa { background:rgba(239,68,68,.15); color:#f87171; } .tb.rf { background:rgba(59,130,246,.18); color:#93c5fd; }
.tb.wu { background:rgba(34,197,94,.15); color:#4ade80; } .tb.eq { background:rgba(245,158,11,.15); color:#fbbf24; }
.rt-cell { font-size:.85rem; color:#c9d4ea; }
div[class*="st-key-row_"] { border-bottom:1px solid var(--border); padding:.2rem 0; }
div[class*="st-key-row_"] button { background:transparent; border:0; min-height:0; padding:.2rem .4rem; }
</style>""", unsafe_allow_html=True)

query = layout.topbar("Saved Reports", "View, download and manage your weather analysis reports", "🔖",
                      search="Search reports…", search_key="search_saved")
counts = store.report_counts()
total = sum(counts.values())
top = st.columns([6, 1.3], vertical_alignment="center")
labels = [f"{t} ({total if t == 'All Reports' else counts.get(t, 0)})" for t in TABS]
chosen = top[0].segmented_control("Type", labels, default=labels[0], label_visibility="collapsed") or labels[0]
if top[1].button("＋ New Report", type="primary", width="stretch"):
    st.switch_page("app_pages/reports.py")
report_type = TABS[labels.index(chosen)]
rows = store.list_reports(query or "", report_type="" if report_type == "All Reports" else report_type)

st.markdown("<div class='rt-head'><span>Report Title</span><span>Location</span><span>Type</span>"
            "<span>Generated On · Actions</span></div>", unsafe_allow_html=True)
if not rows:
    st.info("No reports here yet. Generate one in Analysis Reports or ask in Weather Chat.")
for r in rows:
    with st.container(key=f"row_{r['id']}"):
        cols = st.columns([3.0, 1.3, 1.5, 1.05, 0.42, 0.42, 0.42], vertical_alignment="center")
        cols[0].markdown(f"<div class='rt-title'><span class='pdf-ico'>PDF</span>{escape(r['title'])}</div>",
                         unsafe_allow_html=True)
        cols[1].markdown(f"<span class='rt-cell'>{escape(r['places'])}</span>", unsafe_allow_html=True)
        cols[2].markdown(f"<span class='tb {TYPE_STYLE.get(r['report_type'], 'wu')}'>{escape(r['report_type'])}</span>",
                         unsafe_allow_html=True)
        cols[3].markdown(f"<span class='rt-cell'>{escape(r['created_at'][:16])}</span>", unsafe_allow_html=True)
        with cols[4].popover("👁", help="View"):
            st.markdown(r["answer"])
        pdf = store.report_pdf(r["id"])
        if pdf:
            cols[5].download_button("⬇", pdf, file_name=f"zentro-report-{r['id']}.pdf", mime="application/pdf",
                                    key=f"dl_{r['id']}", help="Download PDF")
        with cols[6].popover("⋮", help="More"):
            st.caption(r["question"])
            if st.button("🗑 Delete report", key=f"del_{r['id']}"):
                st.session_state.confirm_delete = r["id"]
            if st.session_state.get("confirm_delete") == r["id"]:
                st.warning("Delete this report permanently?")
                if st.button("Yes, delete", key=f"yes_{r['id']}", type="primary"):
                    store.delete_report(r["id"])
                    st.session_state.confirm_delete = None
                    st.rerun()
