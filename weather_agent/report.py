"""Builds the visual PDF report: dashboard-style stat tiles, key findings and charts per place.

Page 1 per place: header, hero, 8 stat tiles, key findings, temperature & rain chart.
Page 2 per place: storm-risk, donut, 7-day, model comparison and earthquake charts + warnings.
Last pages: hour-by-hour table, the AI article and sources.
"""

import io
import re
from datetime import datetime, timezone

from fpdf import FPDF

from weather_agent import charts
from weather_agent.insights import findings, parse_answer
from weather_agent.quakes import QuakeReport
from weather_agent.sources import MODELS, AlertResult, ModelComparison
from weather_agent.weather import WeatherReport, compass, uv_level

NAVY = (11, 20, 41)
NAVY_2 = (22, 41, 84)
BLUE = (37, 99, 235)
INK = (15, 23, 42)
MUTED = (100, 116, 139)
TILE = (241, 245, 255)
LINE = (226, 232, 240)
GREEN = (22, 163, 74)
RISK_COLORS = {"Low": (34, 197, 94), "Moderate": (245, 158, 11), "High": (239, 68, 68), "Severe": (153, 27, 27),
               "None": (34, 197, 94)}
CONFIDENCE_COLORS = {"High": (34, 197, 94), "Medium": (245, 158, 11), "Low": (239, 68, 68)}
MARGIN = 10
GAP = 4

# Core PDF fonts are Latin-1 only; map common typography and drop the rest (emoji).
_REPLACEMENTS = {"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", "•": "-", "→": "->", "≈": "~"}


def _latin1(text: str) -> str:
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "ignore").decode("latin-1")


def _plain(markdown: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), markdown)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1 (\2)", text)
    text = re.sub(r"^\s*[*-]\s+", "- ", text, flags=re.MULTILINE)
    return _latin1(text.replace("`", ""))


class _Report(FPDF):
    issued = ""

    def header(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 22, "F")
        self.set_fill_color(*BLUE)
        self.rect(0, 22, self.w, 1.2, "F")
        self.set_xy(MARGIN, 6)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 6, "Zentro AI")
        self.set_xy(MARGIN, 12.5)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(165, 180, 210)
        self.cell(0, 5, "Weather, Storm & Earthquake Analysis Report")
        self.set_xy(self.w - MARGIN - 90, 9)
        self.cell(90, 5, _latin1(f"Issued {self.issued}"), align="R")
        self.set_text_color(*INK)
        self.set_y(28)

    def footer(self):
        self.set_y(-11)
        self.set_draw_color(*LINE)
        self.line(MARGIN, self.get_y(), self.w - MARGIN, self.get_y())
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 7, "Zentro AI Weather Agent  |  Data: Open-Meteo, USGS, NWS, RainViewer  |  "
                        "Risk levels are model-based unless marked official", align="L")
        self.cell(0, 7, f"Page {self.page_no()}", align="R")

    @property
    def content_width(self) -> float:
        return self.w - 2 * MARGIN


# ---------- drawing helpers ----------------------------------------------------------


def _text(pdf: FPDF, text: str, size: float = 9, style: str = "", color=INK, height: float = 5) -> None:
    pdf.set_font("Helvetica", style, size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, height, _latin1(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)


def _section(pdf: FPDF, title: str) -> None:
    pdf.ln(1.5)
    pdf.set_fill_color(*BLUE)
    pdf.rect(MARGIN, pdf.get_y() + 1, 1.4, 5, "F")
    pdf.set_x(MARGIN + 3.5)
    _text(pdf, title, 11.5, "B", INK, 7)
    pdf.ln(0.5)


def _badge(pdf: FPDF, x: float, y: float, text: str, color: tuple) -> float:
    pdf.set_font("Helvetica", "B", 8)
    width = pdf.get_string_width(text) + 7
    pdf.set_fill_color(*color)
    pdf.rect(x, y, width, 6, "F", round_corners=True, corner_radius=3)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(x, y + 0.5)
    pdf.cell(width, 5, _latin1(text), align="C")
    pdf.set_text_color(*INK)
    return width


def _tile(pdf: FPDF, x: float, y: float, w: float, h: float, label: str, value: str, sub: str, accent: tuple) -> None:
    pdf.set_fill_color(*TILE)
    pdf.rect(x, y, w, h, "F", round_corners=True, corner_radius=2.5)
    pdf.set_fill_color(*accent)
    pdf.rect(x, y, w, 1.4, "F")
    pdf.set_xy(x + 3, y + 3.5)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(w - 6, 4, _latin1(label.upper()))
    pdf.set_xy(x + 3, y + 8.5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*INK)
    pdf.cell(w - 6, 7, _latin1(value))
    pdf.set_xy(x + 3, y + 16)
    pdf.set_font("Helvetica", "", 7.2)
    pdf.set_text_color(*MUTED)
    pdf.cell(w - 6, 4, _latin1(sub[:42]))
    pdf.set_text_color(*INK)


def _image(pdf: FPDF, png: bytes, x: float, y: float, w: float) -> float:
    """Place a chart and return its rendered height."""
    info = pdf.image(io.BytesIO(png), x=x, y=y, w=w)
    return float(info.rendered_height)


def _check_list(pdf: FPDF, items: list[tuple[str, str]], x: float, w: float) -> None:
    for key, value in items:
        y = pdf.get_y()
        pdf.set_fill_color(*GREEN)
        pdf.ellipse(x, y + 0.9, 3.6, 3.6, "F")
        pdf.set_font("ZapfDingbats", "", 6.5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x + 0.55, y + 1.05)
        pdf.cell(2.6, 3.2, "4")  # ZapfDingbats "4" is a check mark
        pdf.set_text_color(*INK)
        pdf.set_xy(x + 5.5, y)
        pdf.set_font("Helvetica", "B", 8.8)
        label = _latin1(f"{key}: ")
        pdf.cell(pdf.get_string_width(label) + 0.5, 5.4, label)
        pdf.set_font("Helvetica", "", 8.8)
        pdf.multi_cell(w - 5.5 - pdf.get_string_width(label), 5.4, _latin1(re.sub(r"\*\*(.+?)\*\*", r"\1", value)),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.6)


# ---------- page 1: dashboard ---------------------------------------------------------


def _hero(pdf: _Report, report: WeatherReport) -> None:
    c = report.current
    y = pdf.get_y()
    pdf.set_xy(MARGIN, y)
    _text(pdf, report.location.full_label, 17, "B", INK, 8)
    _text(pdf, f"Observed {str(c.get('time', '')).replace('T', ' ')} local time  |  {report.location.latitude:.2f}, "
               f"{report.location.longitude:.2f}  |  data fetched {report.fetched_at}", 8, "", MUTED, 4.5)
    x = pdf.w - MARGIN
    for text, color in reversed(_badges(report)):
        pdf.set_font("Helvetica", "B", 8)
        x -= pdf.get_string_width(text) + 7
        _badge(pdf, x, y + 1, text, color)
        x -= 2
    pdf.set_y(y + 16)


def _badges(report: WeatherReport) -> list[tuple[str, tuple]]:
    badges = [(f"{report.overall_risk.upper()} STORM RISK", RISK_COLORS[report.overall_risk])]
    comparison: ModelComparison | None = report.comparison  # type: ignore[assignment]
    if comparison is not None:
        badges.append((f"{comparison.confidence.upper()} CONFIDENCE", CONFIDENCE_COLORS[comparison.confidence]))
    alerts: AlertResult | None = report.alerts  # type: ignore[assignment]
    if alerts is not None and alerts.covered and alerts.alerts:
        badges.append((f"{len(alerts.alerts)} OFFICIAL ALERT(S)", (185, 28, 28)))
    return badges


def _tiles(pdf: _Report, report: WeatherReport) -> None:
    c, hours = report.current, report.hours
    peak = max(hours, key=lambda h: h.rain_probability)
    total = sum(h.precipitation_mm for h in hours)
    quakes: QuakeReport | None = report.quakes  # type: ignore[assignment]
    top = quakes.strongest if quakes else None
    comparison: ModelComparison | None = report.comparison  # type: ignore[assignment]
    rain_range = ""
    if comparison is not None and comparison.runs:
        low, high = min(r.total_mm for r in comparison.runs), max(r.total_mm for r in comparison.runs)
        rain_range = f"models: {low:.1f}-{high:.1f} mm"
    tiles = [
        ("Temperature", f"{c.get('temperature_2m')} °C", f"feels like {c.get('apparent_temperature')} °C, {c['condition']}", (239, 68, 68)),
        ("Humidity", f"{c.get('relative_humidity_2m')}%", f"cloud cover {c.get('cloud_cover')}%", (59, 130, 246)),
        ("Wind", f"{round(float(c.get('wind_speed_10m') or 0))} km/h {compass(c.get('wind_direction_10m'))}",
         f"gusts {c.get('wind_gusts_10m')} km/h", (14, 165, 233)),
        ("Pressure", f"{round(float(c.get('pressure_msl') or 0))} hPa",
         f"visibility {float(c.get('visibility') or 0) / 1000:.0f} km, UV {uv_level(c.get('uv_index'))}", (99, 102, 241)),
        ("Rain chance", f"{peak.rain_probability}%", f"peak at {peak.time[11:16]}, {len(report.rain_hours)} h likely", BLUE),
        ("Expected rain", f"{total:.1f} mm", rain_range or f"next {len(hours)} hours", (6, 182, 212)),
        ("Storm risk", report.overall_risk, f"{len(report.storm_hours)} high-risk hour(s)", RISK_COLORS[report.overall_risk]),
        ("Earthquakes", f"M{top.magnitude:.1f}" if top else "None",
         f"{len(quakes.events)} event(s), {top.distance_km:.0f} km away" if quakes and top else "no M2.5+ in 7 days / 500 km",
         RISK_COLORS[quakes.level] if quakes else MUTED),
    ]
    width = (pdf.content_width - 3 * GAP) / 4
    height = 22
    y = pdf.get_y()
    for i, (label, value, sub, accent) in enumerate(tiles):
        row, col = divmod(i, 4)
        _tile(pdf, MARGIN + col * (width + GAP), y + row * (height + GAP), width, height, label, value, sub, accent)
    pdf.set_y(y + 2 * height + GAP + 4)


def _dashboard_page(pdf: _Report, report: WeatherReport, answer: str) -> None:
    pdf.add_page()
    _hero(pdf, report)
    _tiles(pdf, report)
    _section(pdf, "Key findings")
    _check_list(pdf, findings(report, answer), MARGIN + 1, pdf.content_width - 1)
    pdf.ln(1)
    _image(pdf, charts.temp_rain_chart(report), MARGIN, pdf.get_y(), pdf.content_width)


# ---------- page 2: charts ------------------------------------------------------------


def _charts_page(pdf: _Report, report: WeatherReport) -> None:
    pdf.add_page()
    _section(pdf, f"Forecast & risk charts - {report.location.label}")
    left_w = pdf.content_width * 0.6
    right_w = pdf.content_width - left_w - GAP
    y = pdf.get_y()
    h1 = _image(pdf, charts.rain_bar_chart(report), MARGIN, y, left_w)
    h2 = _image(pdf, charts.risk_pie_chart(report), MARGIN + left_w + GAP, y, right_w)
    y += max(h1, h2) + GAP
    comparison: ModelComparison | None = report.comparison  # type: ignore[assignment]
    h1 = _image(pdf, charts.daily_chart(report), MARGIN, y, left_w) if report.days else 0
    h2 = _image(pdf, charts.models_chart(comparison), MARGIN + left_w + GAP, y, right_w) if comparison else 0
    y += max(h1, h2) + GAP
    quakes: QuakeReport | None = report.quakes  # type: ignore[assignment]
    if quakes is not None:
        h1 = _image(pdf, charts.quake_chart(quakes), MARGIN, y, left_w)
        _quake_panel(pdf, quakes, MARGIN + left_w + GAP, y + 2, right_w, h1 - 4)
        y += h1
    pdf.set_y(y + 2)
    _warnings_box(pdf, report)


def _quake_panel(pdf: _Report, quakes: QuakeReport, x: float, y: float, w: float, h: float) -> None:
    """Earthquake summary beside the bubble chart: count, strongest, nearest."""
    nearest = min(quakes.events, key=lambda q: q.distance_km, default=None)
    top = quakes.strongest
    rows = [
        ("Events (M2.5+)", str(len(quakes.events))),
        ("Strongest", f"M{top.magnitude:.1f}, {top.distance_km:.0f} km" if top else "-"),
        ("Nearest", f"M{nearest.magnitude:.1f}, {nearest.distance_km:.0f} km" if nearest else "-"),
        ("Activity level", quakes.level),
    ]
    pdf.set_fill_color(*TILE)
    pdf.rect(x, y, w, h, "F", round_corners=True, corner_radius=2.5)
    pdf.set_fill_color(*RISK_COLORS.get(quakes.level, MUTED))
    pdf.rect(x, y, w, 1.4, "F")
    pdf.set_xy(x + 4, y + 4)
    _text(pdf, "EARTHQUAKE SUMMARY", 8, "B", MUTED, 5)
    row_y = y + 11
    for label, value in rows:
        pdf.set_xy(x + 4, row_y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(w - 8, 4, _latin1(label))
        pdf.set_xy(x + 4, row_y + 4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*INK)
        pdf.cell(w - 8, 6, _latin1(value))
        row_y += 11.5
    pdf.set_xy(x + 4, y + h - 7)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*MUTED)
    pdf.cell(w - 8, 4, "Observed activity - earthquakes cannot be forecast")
    pdf.set_text_color(*INK)


def _warnings_box(pdf: _Report, report: WeatherReport) -> None:
    alerts: AlertResult | None = report.alerts  # type: ignore[assignment]
    covered = alerts is not None and alerts.covered
    active = covered and bool(alerts.alerts)  # type: ignore[union-attr]
    fill, edge = ((254, 226, 226), (185, 28, 28)) if active else ((236, 253, 245), GREEN) if covered else ((255, 247, 237), (217, 119, 6))
    text = alerts.summary() if alerts else "Official warnings were not checked; risk levels are model-based estimates."
    pdf.set_font("Helvetica", "", 8.3)
    lines = pdf.multi_cell(pdf.content_width - 8, 4.6, _latin1(text), dry_run=True, output="LINES")
    height = 10 + 4.6 * len(lines)
    y = pdf.get_y()
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*edge)
    pdf.rect(MARGIN, y, pdf.content_width, height, "DF", round_corners=True, corner_radius=2.5)
    pdf.set_xy(MARGIN + 4, y + 2.5)
    _text(pdf, "OFFICIAL WARNINGS (VERIFIED)", 8.5, "B", edge, 5)
    pdf.set_x(MARGIN + 4)
    pdf.set_font("Helvetica", "", 8.3)
    pdf.multi_cell(pdf.content_width - 8, 4.6, _latin1(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(y + height + 3)


# ---------- data, article, sources ---------------------------------------------------


def _table(pdf: FPDF, widths: tuple, headers: tuple, rows: list[tuple], risk_column: int | None = None) -> None:
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(*NAVY_2)
    pdf.set_text_color(255, 255, 255)
    for w, h in zip(widths, headers):
        pdf.cell(w, 6.5, h, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 7.2)
    for n, row in enumerate(rows):
        pdf.set_fill_color(*(TILE if n % 2 else (255, 255, 255)))
        for i, (w, value) in enumerate(zip(widths, row)):
            pdf.set_text_color(*(RISK_COLORS.get(str(value), INK) if i == risk_column else INK))
            pdf.set_font("Helvetica", "B" if i == risk_column else "", 7.2)
            pdf.cell(w, 5.2, _latin1(str(value))[: int(w / 1.45)], fill=True)
        pdf.ln()
    pdf.set_text_color(*INK)
    pdf.ln(3)


def _data_page(pdf: _Report, report: WeatherReport) -> None:
    pdf.add_page()
    _section(pdf, f"Hour-by-hour forecast - {report.location.label} (model-based)")
    _table(pdf, (29, 34, 13, 14, 12, 18, 14, 18, 38),
           ("Local time", "Condition", "Temp", "Rain %", "mm", "Intensity", "Gust", "Risk", "Why"),
           [(h.time.replace("T", " "), h.condition, f"{h.temperature:.0f}", h.rain_probability, f"{h.precipitation_mm:.1f}",
             h.intensity, f"{h.gusts_kmh:.0f}", h.risk, "; ".join(h.reasons) or "-") for h in report.hours], risk_column=7)
    if report.days:
        _section(pdf, f"{len(report.days)}-day forecast")
        _table(pdf, (26, 50, 22, 22, 24, 22, 24), ("Date", "Condition", "Min C", "Max C", "Rain mm", "Rain %", "Risk"),
               [(d.date, d.condition, f"{d.temp_min:.0f}", f"{d.temp_max:.0f}", f"{d.precipitation_mm:.1f}",
                 d.rain_probability, d.risk) for d in report.days], risk_column=6)
    quakes: QuakeReport | None = report.quakes  # type: ignore[assignment]
    if quakes is not None and quakes.events:
        _section(pdf, "Recent earthquakes (USGS)")
        _table(pdf, (18, 92, 34, 22, 24), ("Mag", "Location", "Time (UTC)", "Depth km", "Distance km"),
               [(f"M{q.magnitude:.1f}", q.place, q.time, f"{q.depth_km:.0f}", f"{q.distance_km:.0f}") for q in quakes.events])


def _article(pdf: _Report, question: str, answer: str) -> None:
    pdf.add_page()
    _section(pdf, "AI analysis")
    _text(pdf, f"Query: {question}", 8.5, "I", MUTED, 4.8)
    pdf.ln(2)
    details = parse_answer(answer).details
    for line in _plain(details).splitlines():
        heading = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading:
            _text(pdf, heading.group(2), 13 - min(len(heading.group(1)), 3), "B", INK, 6.5)
        elif line.strip():
            _text(pdf, line, 9.5, "", INK, 5.2)
        else:
            pdf.ln(1.5)


def _sources(pdf: _Report, reports: list[WeatherReport]) -> None:
    _section(pdf, "Sources & method")
    lines = [
        "Live conditions, history and forecasts: Open-Meteo (open-meteo.com).",
        f"Forecast confidence: agreement between {', '.join(MODELS.values())}.",
        "Storm risk: model-based score from WMO weather codes, CAPE instability, wind gusts, rain rate and rain probability.",
        "Official warnings: US National Weather Service (api.weather.gov) where covered; elsewhere marked as not covered.",
        "Earthquakes: US Geological Survey, M2.5+ within 500 km over the last 7 days (observed, not forecast).",
        "Narrative analysis: AI agent built with LangChain Deep Agents.",
    ]
    if not reports:
        lines.append("No live weather data was retrieved for this answer.")
    for line in lines:
        _text(pdf, f"- {line}", 8.5, "", MUTED, 4.8)


def build_pdf(question: str, answer: str, reports: list[WeatherReport]) -> bytes:
    pdf = _Report()
    pdf.issued = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.set_margins(MARGIN, 28, MARGIN)
    pdf.set_auto_page_break(auto=True, margin=14)
    for report in reports:
        _dashboard_page(pdf, report, answer)
        _charts_page(pdf, report)
    for report in reports:
        _data_page(pdf, report)
    _article(pdf, question, answer)
    _sources(pdf, reports)
    return bytes(pdf.output())
