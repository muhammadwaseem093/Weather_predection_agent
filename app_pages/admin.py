"""Admin dashboard: agent runs, token use, weather-API usage and generated content.

Protected by the ADMIN_PASSWORD secret; without it the page stays locked.
"""

import hmac

import pandas as pd
import streamlit as st

from ui import layout
from ui.common import secret
from weather_agent import store

layout.topbar("Admin Dashboard", "Monitor agent runs, API usage and generated content", "🛡️")

expected = secret("ADMIN_PASSWORD")
if not expected:
    st.warning("The admin dashboard is locked. Set the `ADMIN_PASSWORD` secret (or environment variable) to enable it.")
    st.stop()
if not st.session_state.get("admin_ok"):
    with st.form("admin_login"):
        password = st.text_input("Admin password", type="password")
        if st.form_submit_button("Sign in", type="primary"):
            if hmac.compare_digest(password.encode(), expected.encode()):
                st.session_state.admin_ok = True
                st.rerun()
            st.error("Wrong password.")
    st.stop()

if st.sidebar.button("Sign out of admin", width="stretch"):
    st.session_state.admin_ok = False
    st.rerun()

stats = store.usage_stats()
runs = stats["runs"] or 0
cols = st.columns(6)
cols[0].metric("Agent runs", runs)
cols[1].metric("Success rate", f"{(stats['ok'] / runs):.0%}" if runs else "–")
cols[2].metric("Avg run time", f"{stats['avg_ms'] / 1000:.1f} s" if runs else "–")
cols[3].metric("Tokens (in / out)", f"{stats['input_tokens']:,} / {stats['output_tokens']:,}")
cols[4].metric("Weather API calls", stats["api_calls"], f"{stats['api_failed']} failed", delta_color="inverse")
cols[5].metric("Reports", stats["reports"], f"{stats['report_bytes'] / 1_048_576:.1f} MB", delta_color="off")

tab_runs, tab_api, tab_content = st.tabs(["🤖 Agent runs", "🔌 API usage", "📄 Generated content"])

with tab_runs:
    recent = pd.DataFrame(store.recent_runs())
    if recent.empty:
        st.info("No agent runs yet.")
    else:
        st.bar_chart(recent.groupby("mode").size().rename("runs"), color="#7c5cff", height=200)
        st.dataframe(recent, hide_index=True, width="stretch")

with tab_api:
    by_service = pd.DataFrame(store.api_usage_by_service())
    if by_service.empty:
        st.info("No API calls yet.")
    else:
        st.dataframe(by_service, hide_index=True, width="stretch")
        daily = pd.DataFrame(store.api_usage_by_day())
        if not daily.empty:
            st.bar_chart(daily, x="day", y="calls", color="service", height=260)

with tab_content:
    reports = store.list_reports()
    if not reports:
        st.info("No reports yet.")
    for r in reports:
        row = st.columns([5, 1])
        row[0].markdown(f"**#{r['id']} {r['title']}** · {r['created_at']} UTC · {r['overall_risk']}")
        if row[1].button("Delete", key=f"del_{r['id']}", width="stretch"):
            st.session_state.confirm_delete = r["id"]
        if st.session_state.get("confirm_delete") == r["id"]:
            st.warning(f"Delete report #{r['id']} permanently?")
            yes, no = st.columns(2)
            if yes.button("Yes, delete", key=f"yes_{r['id']}", type="primary"):
                store.delete_report(r["id"])
                st.session_state.confirm_delete = None
                st.rerun()
            if no.button("Cancel", key=f"no_{r['id']}"):
                st.session_state.confirm_delete = None
                st.rerun()
