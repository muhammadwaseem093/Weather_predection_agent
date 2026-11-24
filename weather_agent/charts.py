"""Chart images (PNG) for the visual PDF report, rendered with matplotlib in one consistent style."""

import io
from collections import Counter

import matplotlib

matplotlib.use("Agg")  # headless: no display on servers or Streamlit Cloud
import matplotlib.pyplot as plt  # noqa: E402  (backend must be chosen first)

from weather_agent.quakes import QuakeReport  # noqa: E402
from weather_agent.sources import ModelComparison  # noqa: E402
from weather_agent.weather import RISK_LEVELS, WeatherReport  # noqa: E402

NAVY = "#0f1b36"
BLUE = "#2563eb"
LIGHT_BLUE = "#93c5fd"
TEMP = "#ef4444"
COLD = "#3b82f6"
GUST = "#f59e0b"
GRID = "#e2e8f0"
MUTED = "#64748b"
RISK_COLORS = {"Low": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444", "Severe": "#991b1b"}
DPI = 170

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.titleweight": "bold", "axes.titlesize": 10,
    "axes.titlecolor": NAVY, "axes.titlelocation": "left", "axes.titlepad": 10,
})


def _style(ax) -> None:
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


def _png(fig) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buffer.getvalue()


def _labels(report: WeatherReport) -> tuple[list[str], int]:
    labels = [h.time[11:16] for h in report.hours]
    return labels, max(1, len(labels) // 8)


def temp_rain_chart(report: WeatherReport) -> bytes:
    """Hourly temperature (line) over rain probability (bars): the headline chart."""
    labels, step = _labels(report)
    x = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(9.5, 3.1))
    ax.bar(x, [h.rain_probability for h in report.hours], color=LIGHT_BLUE, width=0.75, label="Rain chance %")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Rain chance (%)")
    _style(ax)
    temps = ax.twinx()
    values = [h.temperature for h in report.hours]
    temps.plot(x, values, color=TEMP, linewidth=2.2, marker="o", markersize=2.5, label="Temperature °C")
    temps.fill_between(x, values, min(values) - 2, color=TEMP, alpha=0.06)
    temps.set_ylabel("Temperature (°C)")
    temps.spines[["top"]].set_visible(False)
    ax.set_xticks(x[::step], labels[::step])
    ax.set_title(f"Temperature & rain chance — next {len(labels)} hours")
    handles = ax.get_legend_handles_labels()[0] + temps.get_legend_handles_labels()[0]
    ax.legend(handles, [h.get_label() for h in handles], loc="upper left", fontsize=7.5, frameon=False, ncol=2)
    return _png(fig)


def rain_bar_chart(report: WeatherReport) -> bytes:
    """Hourly rain probability coloured by storm risk, with gusts as a line."""
    labels, step = _labels(report)
    x = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(5.6, 2.9))
    ax.bar(x, [h.rain_probability for h in report.hours], color=[RISK_COLORS[h.risk] for h in report.hours], width=0.8)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Rain chance (%)")
    ax.set_xticks(x[::step], labels[::step], fontsize=7)
    _style(ax)
    gusts = ax.twinx()
    gusts.plot(x, [h.gusts_kmh for h in report.hours], color=GUST, linewidth=1.6)
    gusts.set_ylabel("Gusts (km/h)", color=GUST)
    gusts.spines[["top"]].set_visible(False)
    ax.set_title("Storm risk by hour (bar colour) & gusts")
    return _png(fig)


def risk_pie_chart(report: WeatherReport) -> bytes:
    """Share of forecast hours at each storm-risk level, as a donut."""
    counts = Counter(h.risk for h in report.hours)
    levels = [level for level in RISK_LEVELS if counts[level]]
    total = len(report.hours)
    fig, ax = plt.subplots(figsize=(3.6, 2.9))
    wedges, _ = ax.pie([counts[level] for level in levels], colors=[RISK_COLORS[level] for level in levels],
                       startangle=90, wedgeprops={"width": 0.38, "edgecolor": "white", "linewidth": 2})
    ax.text(0, 0, f"{report.overall_risk}\nrisk", ha="center", va="center", fontsize=10, fontweight="bold",
            color=RISK_COLORS[report.overall_risk])
    # A legend instead of slice labels: small slices would otherwise overlap.
    ax.legend(wedges, [f"{level}: {counts[level]}h ({counts[level] / total:.0%})" for level in levels],
              loc="upper center", bbox_to_anchor=(0.5, 0.02), fontsize=7, frameon=False, ncol=2)
    ax.set_title("Hours by storm risk")
    return _png(fig)


def daily_chart(report: WeatherReport) -> bytes:
    """Daily rain totals (bars, coloured by risk) with min/max temperature lines."""
    labels = [d.date[5:] for d in report.days]
    x = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(5.6, 2.9))
    ax.bar(x, [d.precipitation_mm for d in report.days], color=[RISK_COLORS[d.risk] for d in report.days], width=0.6)
    ax.set_ylabel("Rain (mm/day)")
    ax.set_xticks(x, labels, fontsize=7.5)
    _style(ax)
    temps = ax.twinx()
    temps.plot(x, [d.temp_max for d in report.days], color=TEMP, marker="o", linewidth=1.8, label="Max °C")
    temps.plot(x, [d.temp_min for d in report.days], color=COLD, marker="o", linewidth=1.8, label="Min °C")
    temps.set_ylabel("Temperature (°C)")
    temps.spines[["top"]].set_visible(False)
    temps.legend(loc="upper right", fontsize=7, frameon=False)
    ax.set_title(f"{len(report.days)}-day outlook")
    return _png(fig)


def models_chart(comparison: ModelComparison) -> bytes:
    """Independent forecast models side by side: total rain and max gust."""
    names = [r.model.split(" (")[0] for r in comparison.runs]
    x = list(range(len(names)))
    fig, ax = plt.subplots(figsize=(3.6, 2.9))
    ax.bar([i - 0.2 for i in x], [r.total_mm for r in comparison.runs], width=0.4, color=BLUE, label="Rain mm")
    ax.set_ylabel("Total rain (mm)")
    ax.set_xticks(x, names, fontsize=7.5)
    _style(ax)
    gusts = ax.twinx()
    gusts.bar([i + 0.2 for i in x], [r.max_gust_kmh for r in comparison.runs], width=0.4, color=GUST, label="Max gust")
    gusts.set_ylabel("Max gust (km/h)")
    gusts.spines[["top"]].set_visible(False)
    ax.set_title(f"Model agreement {comparison.agreement:.0%}")
    handles = ax.get_legend_handles_labels()[0] + gusts.get_legend_handles_labels()[0]
    ax.legend(handles, [h.get_label() for h in handles], loc="upper center", bbox_to_anchor=(0.5, -0.12),
              fontsize=7, frameon=False, ncol=2)
    return _png(fig)


def quake_chart(quakes: QuakeReport) -> bytes:
    """Recent earthquakes: distance from the place vs magnitude (bubble size = magnitude)."""
    fig, ax = plt.subplots(figsize=(5.6, 2.6))
    if quakes.events:
        mags = [q.magnitude for q in quakes.events]
        ax.scatter([q.distance_km for q in quakes.events], mags, s=[(m ** 2.4) * 6 for m in mags],
                   c=["#ef4444" if m >= 5 else "#f59e0b" if m >= 4 else "#facc15" for m in mags],
                   alpha=0.75, edgecolors="white", linewidths=1)
        ax.set_ylim(2, max(mags) + 1)
    else:
        ax.text(0.5, 0.5, f"No M2.5+ earthquakes within {quakes.radius_km} km in {quakes.days} days",
                transform=ax.transAxes, ha="center", va="center", color=MUTED, fontsize=9)
        ax.set_ylim(2, 7)
    ax.set_xlim(0, quakes.radius_km)
    ax.set_xlabel("Distance from location (km)")
    ax.set_ylabel("Magnitude")
    _style(ax)
    ax.set_title(f"Earthquakes — last {quakes.days} days (USGS)")
    return _png(fig)
