"""Runs the deep agent for one question: live trace, usage logging, PDF report and storage.

Shared by Weather Chat and the Analysis Reports generator.
"""

import time
from datetime import datetime

import streamlit as st

from ui import cards
from weather_agent import agent as storm_agent
from weather_agent import store
from weather_agent.quakes import STRONG_MAGNITUDE
from weather_agent.report import build_pdf


def _notify(reports) -> None:
    notes = st.session_state.setdefault("notifications", [])
    for r in reports:
        if r.alerts is not None and r.alerts.covered:
            notes += [f"🛑 {r.location.label}: {a.event} ({a.severity})" for a in r.alerts.alerts]
        if r.quakes is not None and r.quakes.strongest and r.quakes.strongest.magnitude >= STRONG_MAGNITUDE:
            q = r.quakes.strongest
            notes.append(f"🌐 M{q.magnitude:.1f} earthquake {q.distance_km:.0f} km from {r.location.label}")
        if r.overall_risk in ("High", "Severe"):
            notes.append(f"⛈️ {r.overall_risk} storm risk for {r.location.label} (model-based)")


def run(question: str, history: list[dict], report_type: str = store.REPORT_TYPES[0]) -> dict | None:
    """Run the agent with a live status box. Returns the assistant message, or None on failure."""
    api_key = st.session_state.get("api_key", "")
    model = st.session_state.get("model") or storm_agent.DEFAULT_MODEL
    if not api_key:
        st.error("Add your Google Gemini API key: click your avatar (top right) → Profile & settings.")
        return None
    log = storm_agent.RunLog()
    steps: list[storm_agent.Step] = []
    final = ""
    started = time.perf_counter()
    with st.status("Analysing weather, rain, storms and earthquakes…", expanded=True) as status:
        try:
            agent = storm_agent.build_agent(api_key, model, log)
            for item in storm_agent.run(agent, history, log):
                if isinstance(item, storm_agent.Step):
                    steps.append(item)
                    status.update(label=item.title + "…")
                    st.markdown(f"**{item.title}**")
                else:
                    final = item
            status.update(label="Collecting radar, model and earthquake data…")
            log.complete()
            status.update(label="Building the visual PDF report…")
            reports = list(log.reports.values())
            pdf = build_pdf(question, final, reports) if final else None
            status.update(label="Done", state="complete", expanded=False)
        except Exception as error:  # noqa: BLE001 - surface model/provider failures to the user
            status.update(label="The agent failed", state="error")
            st.error(f"The agent could not finish: {type(error).__name__}. Check the API key and model name.")
            store.log_run(question, report_type, model, "error", int((time.perf_counter() - started) * 1000),
                          log.tool_calls, log.input_tokens, log.output_tokens, type(error).__name__)
            return None
    store.log_run(question, report_type, model, "ok", int((time.perf_counter() - started) * 1000),
                  log.tool_calls, log.input_tokens, log.output_tokens)
    _notify(reports)
    filename = report_id = None
    if pdf:
        places = ", ".join(r.location.name for r in reports) or "General"
        title = f"{places} {report_type}" if reports else report_type
        report_id = store.save_report(title, question, final, places, cards.overall(reports), model, pdf, report_type)
        filename = f"zentro-{report_type.lower().replace(' & ', '-').replace(' ', '-')}-{datetime.now():%Y%m%d-%H%M%S}.pdf"
        st.session_state.latest_pdf = (pdf, filename)
    if reports:
        st.session_state.active_place = reports[0].location.label
    return {"role": "assistant", "content": final or "_No answer was produced._", "steps": steps,
            "reports": reports, "pdf": pdf, "filename": filename, "report_id": report_id}
