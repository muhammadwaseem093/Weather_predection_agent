"""Detail widgets for the place pages: charts, tables, confidence and alerts."""

import pandas as pd
import streamlit as st

from weather_agent.sources import AlertResult, ModelComparison
from weather_agent.weather import WeatherReport

BRAND = "#7c5cff"
GUST = "#f59e0b"
RISK_COLORS = {"Low": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444", "Severe": "#991b1b"}


def risk_badge(risk: str, prefix: str = "") -> str:
    return f"<span class='risk risk-{risk}'>{prefix}{risk}</span>"



def hourly_chart(report: WeatherReport) -> None:
    frame = pd.DataFrame({
        "time": pd.to_datetime([h.time for h in report.hours]),
        "Rain chance %": [h.rain_probability for h in report.hours],
        "Gusts km/h": [h.gusts_kmh for h in report.hours],
    }).set_index("time")
    st.area_chart(frame, color=[BRAND, GUST], height=220)


def hourly_table(report: WeatherReport) -> None:
    frame = pd.DataFrame([{
        "Local time": h.time.replace("T", " "), "Condition": h.condition, "Temp °C": h.temperature,
        "Rain %": h.rain_probability, "Rain mm": h.precipitation_mm, "Intensity": h.intensity,
        "Gust km/h": h.gusts_kmh, "Risk": h.risk, "Why": "; ".join(h.reasons),
    } for h in report.hours])
    st.dataframe(frame, hide_index=True, width="stretch", height=320)


def risk_breakdown(report: WeatherReport) -> None:
    counts = pd.Series([h.risk for h in report.hours]).value_counts()
    frame = pd.DataFrame({"Risk": counts.index, "Hours": counts.values})
    st.bar_chart(frame, x="Risk", y="Hours", color="Risk", height=220)


def daily_view(report: WeatherReport) -> None:
    frame = pd.DataFrame([{
        "Date": d.date, "Condition": d.condition, "Min °C": d.temp_min, "Max °C": d.temp_max,
        "Rain mm": d.precipitation_mm, "Rain %": d.rain_probability, "Max gust km/h": d.gusts_kmh, "Risk": d.risk,
    } for d in report.days])
    chart = frame.set_index("Date")[["Rain mm", "Max °C", "Min °C"]]
    st.bar_chart(chart[["Rain mm"]], color=BRAND, height=200)
    st.line_chart(chart[["Max °C", "Min °C"]], color=["#ef4444", "#3b82f6"], height=200)
    st.dataframe(frame, hide_index=True, width="stretch")


def history_view(report: WeatherReport) -> None:
    if not report.history:
        st.info("No recent observations available.")
        return
    frame = pd.DataFrame({
        "time": pd.to_datetime([h.time for h in report.history]),
        "Rain mm": [h.precipitation_mm for h in report.history],
        "Temp °C": [h.temperature for h in report.history],
    }).set_index("time")
    st.bar_chart(frame[["Rain mm"]], color=BRAND, height=180)
    st.line_chart(frame[["Temp °C"]], color="#ef4444", height=180)


def confidence_view(comparison: ModelComparison | None) -> None:
    if comparison is None:
        st.info("Model comparison unavailable.")
        return
    st.markdown(f"**Forecast confidence: {comparison.confidence}** — {len(comparison.runs)} independent models agree "
                f"on rain/no-rain {comparison.agreement:.0%} of the next {comparison.hours} hours.")
    st.dataframe(pd.DataFrame([{
        "Model": r.model, "Total rain mm": round(r.total_mm, 1), "Rain hours": r.rain_hours,
        "Thunderstorm hours": r.storm_hours, "Max gust km/h": round(r.max_gust_kmh),
    } for r in comparison.runs]), hide_index=True, width="stretch")


def alerts_view(result: AlertResult | None) -> None:
    st.markdown("**🛑 Official warnings (verified)**")
    if result is None:
        st.caption("Not checked.")
    elif not result.covered:
        st.warning(f"No official feed: {result.source}. Risk shown here is a **model-based estimate**, "
                   "not an official warning — check the national weather service.")
    elif not result.alerts:
        st.success(f"{result.source}: no active alerts.")
    else:
        for a in result.alerts:
            st.error(f"**{a.event}** [{a.severity}] — {a.headline}  \nUntil {a.expires}")
