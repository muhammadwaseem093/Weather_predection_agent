"""The weather result card grid from the design reference, rendered as one HTML component.

Weather card, Storm & Rain outlook, 24-hour strip, rain-probability chart, 3-day outlook,
satellite map with live radar, and earthquakes. All text is HTML-escaped: place names and
event descriptions come from external APIs.
"""

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from weather_agent.quakes import QuakeReport
from weather_agent.sources import AlertResult, ModelComparison
from weather_agent.weather import RISK_LEVELS, WeatherReport, compass, uv_level

STRIP_SLOTS = 8
STRIP_STEP_HOURS = 3
RISK_BADGE = {"Low": "Low Risk", "Moderate": "Low–Moderate Risk", "High": "High Risk", "Severe": "Severe Risk"}
RISK_TONES = {"Low": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444", "Severe": "#dc2626", "None": "#22c55e"}


def icon(condition: str, hour: int = 12) -> str:
    c = condition.lower()
    night = hour < 6 or hour >= 19
    if "thunder" in c:
        return "⛈️"
    if "snow" in c:
        return "🌨️"
    if "rain" in c or "drizzle" in c or "shower" in c:
        return "🌧️"
    if "fog" in c:
        return "🌫️"
    if "overcast" in c:
        return "☁️"
    if "partly" in c:
        return "⛅" if not night else "☁️"
    if "mainly" in c:
        return "🌤️" if not night else "🌙"
    return "☀️" if not night else "🌙"


def hour_of(stamp: str) -> int:
    return int(stamp[11:13]) if len(stamp) >= 13 else 12


def clock(stamp: str) -> str:
    h = hour_of(stamp)
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


def _local_now(report: WeatherReport) -> str:
    try:
        now = datetime.now(ZoneInfo(report.location.timezone))
        return f"{now:%a, %b %d, %Y} · {now:%I:%M %p} ({now.tzname()})"
    except (ZoneInfoNotFoundError, ValueError):
        return str(report.current.get("time", "")).replace("T", " ")


def outlook_text(report: WeatherReport, comparison: ModelComparison | None, alerts: AlertResult | None) -> str:
    rainy = report.rain_hours
    if rainy:
        first = rainy[0]
        peak = max(rainy, key=lambda h: h.rain_probability)
        rain = (f"Rain is likely from {clock(first.time)} (peak ≈ {peak.rain_probability}% around "
                f"{clock(peak.time)}, {peak.intensity.lower()} intensity).")
    else:
        top = max(report.hours, key=lambda h: h.rain_probability, default=None)
        rain = f"No significant rain expected (max chance {top.rain_probability if top else 0}%)."
    storms = report.storm_hours
    storm = (f"Storm risk {storms[0].risk.lower()} from {clock(storms[0].time)}: {'; '.join(storms[0].reasons)}."
             if storms else "No severe storm expected.")
    official = ""
    if alerts and alerts.covered and alerts.alerts:
        official = f" Official: {alerts.alerts[0].event}."
    conf = f" Confidence {comparison.confidence.lower()}." if comparison else ""
    return f"{rain} {storm}{official}{conf}"


def weather_card(report: WeatherReport) -> str:
    c = report.current
    vis = float(c.get("visibility") or 0) / 1000
    uv = c.get("uv_index")
    stats = [
        ("💧", "Humidity", f"{c.get('relative_humidity_2m')}%"),
        ("🌬️", "Wind", f"{round(float(c.get('wind_speed_10m') or 0))} km/h ({compass(c.get('wind_direction_10m'))})"),
        ("⏲️", "Pressure", f"{round(float(c.get('pressure_msl') or 0))} hPa"),
        ("👁️", "Visibility", f"{vis:.0f} km"),
        ("☀️", "UV Index", f"{round(float(uv or 0))} ({uv_level(uv)})"),
    ]
    rows = "".join(f"<div class='st'><span class='si'>{i}</span><span class='sl'>{l}</span><b>{escape(v)}</b></div>"
                   for i, l, v in stats)
    cond = escape(c["condition"])
    return f"""
    <div class="card wx">
      <div class="wx-main">
        <div class="loc">📍 {escape(report.location.full_label)}</div>
        <div class="date">{escape(_local_now(report))}</div>
        <div class="wx-now">
          <div class="wx-ico"><div class="big-ico">{icon(c['condition'], hour_of(str(c.get('time', ''))))}</div><span>{cond}</span></div>
          <div><div class="temp">{round(float(c.get('temperature_2m') or 0))}°C</div>
          <div class="cond">{cond}</div><div class="feels">Feels like {round(float(c.get('apparent_temperature') or 0))}°C</div></div>
        </div>
      </div>
      <div class="wx-stats">{rows}</div>
    </div>"""


def outlook_card(report: WeatherReport, comparison: ModelComparison | None, alerts: AlertResult | None) -> str:
    risk = report.overall_risk
    tone = RISK_TONES[risk]
    return f"""
    <div class="card outlook">
      <div class="head"><span class="ttl">⚡ Storm &amp; Rain Outlook</span>
        <span class="badge" style="color:{tone};border-color:{tone}55;background:{tone}22">{RISK_BADGE[risk]}</span></div>
      <div class="outlook-body"><p>{escape(outlook_text(report, comparison, alerts))}</p>
        <div class="bolt">⛈️</div></div>
      <div class="foot">Model-based estimate{' · official alerts checked' if alerts and alerts.covered else ' · no official feed for this country'}</div>
    </div>"""


def strip_card(report: WeatherReport) -> str:
    slots = report.hours[::STRIP_STEP_HOURS][:STRIP_SLOTS]
    items = "".join(
        f"<div class='slot{' now' if i == 0 else ''}'><div class='t'>{'Now' if i == 0 else clock(h.time)}</div>"
        f"<div class='i'>{icon(h.condition, hour_of(h.time))}</div><div class='d'>{round(h.temperature)}°C</div>"
        f"<div class='p'>💧 {h.rain_probability}%</div></div>"
        for i, h in enumerate(slots)
    )
    return f"<div class='card strip'><div class='ttl'>🕘 Next 24 Hours Forecast</div><div class='slots'>{items}</div></div>"


def rain_chart(report: WeatherReport, width: int = 300) -> str:
    hours = report.hours[:24]
    height, left, bottom = 120, 30, 18
    plot_w, plot_h = width - left - 4, height - bottom - 6
    bar_w = plot_w / max(len(hours), 1)
    bars, labels = [], []
    for i, h in enumerate(hours):
        bh = plot_h * h.rain_probability / 100
        x = left + i * bar_w
        bars.append(f"<rect x='{x + 1:.1f}' y='{6 + plot_h - bh:.1f}' width='{bar_w - 2:.1f}' height='{bh:.1f}' "
                    f"rx='1.5' fill='url(#rg)'/>")
        if i % 3 == 0:
            labels.append(f"<text x='{x + bar_w / 2:.1f}' y='{height - 4}' class='ax' text-anchor='middle'>{clock(h.time)}</text>")
    grid = "".join(
        f"<line x1='{left}' x2='{width - 4}' y1='{6 + plot_h * (1 - v / 100):.1f}' y2='{6 + plot_h * (1 - v / 100):.1f}' class='gl'/>"
        f"<text x='{left - 4}' y='{9 + plot_h * (1 - v / 100):.1f}' class='ax' text-anchor='end'>{v}%</text>"
        for v in (0, 25, 50, 75, 100)
    )
    svg = (f"<svg viewBox='0 0 {width} {height}' preserveAspectRatio='none'><defs><linearGradient id='rg' x1='0' y1='0' x2='0' y2='1'>"
           f"<stop offset='0' stop-color='#3b82f6'/><stop offset='1' stop-color='#1d4ed8'/></linearGradient></defs>"
           f"{grid}{''.join(bars)}{''.join(labels)}</svg>")
    empty = "" if any(h.rain_probability for h in hours) else "<div class='nodata'>☀️ No rain expected in the next 24 hours</div>"
    return f"<div class='card rain'><div class='ttl'>☔ Rain Probability (Next 24 Hours)</div>{svg}{empty}</div>"


def days_card(report: WeatherReport) -> str:
    items = []
    for d in report.days[:3]:
        day = datetime.strptime(d.date, "%Y-%m-%d")
        note = f"Rain ({d.rain_probability}%)" if d.rain_probability >= 40 else d.condition
        items.append(f"<div class='day'><div class='dn'>{day:%a, %b %d}</div><div class='di'>{icon(d.condition)}</div>"
                     f"<div class='dt'>{round(d.temp_min)}° / {round(d.temp_max)}°</div><div class='dc'>{escape(note)}</div></div>")
    return f"<div class='card days'><div class='ttl'>📅 3-Day Outlook</div><div class='dayrow'>{''.join(items)}</div></div>"


def radar_card(report: WeatherReport, radar_url: str | None) -> str:
    loc = report.location
    live = f"https://www.rainviewer.com/map.html?loc={loc.latitude:.3f},{loc.longitude:.3f},8&layer=radar"
    return f"""
    <div class="card radar"><div class="ttl">🛰️ Regional Weather &amp; Radar</div>
      <div class="map-wrap"><div id="map"></div>
        <div class="legend"><div><i style="background:#ef4444"></i>Heavy Rain</div><div><i style="background:#f59e0b"></i>Moderate</div>
          <div><i style="background:#22c55e"></i>Light Rain</div><div><i style="background:#3b82f6"></i>Clouds</div>
          <a class="live" href="{escape(live)}" target="_blank" rel="noopener">▶ Live Radar</a></div>
      </div>
      {'' if radar_url else "<div class='foot'>Radar overlay unavailable right now.</div>"}
    </div>"""


def quake_card(quakes: QuakeReport | None) -> str:
    if quakes is None:
        body = "<p class='muted'>Earthquake data unavailable right now.</p>"
        level = "None"
    else:
        level = quakes.level
        top = quakes.strongest
        if top is None:
            body = (f"<div class='qbig'>0</div><p class='muted'>No M2.5+ earthquakes within {quakes.radius_km} km "
                    f"in the last {quakes.days} days.</p>")
        else:
            rows = "".join(f"<div class='qrow'><b>M{q.magnitude:.1f}</b><span>{escape(q.place[:38])}</span>"
                           f"<em>{q.time[5:]} UTC</em></div>" for q in quakes.events[:3])
            body = (f"<div class='qtop'><div class='qbig'>M{top.magnitude:.1f}</div><div class='muted'>strongest · "
                    f"{top.distance_km:.0f} km away<br>{len(quakes.events)} event(s), last {quakes.days} days</div></div>{rows}")
    tone = RISK_TONES.get(level, "#22c55e")
    label = "No activity" if level == "None" else f"{level} activity"
    return f"""
    <div class="card quake"><div class="head"><span class="ttl">🌐 Earthquakes</span>
      <span class="badge" style="color:{tone};border-color:{tone}55;background:{tone}22">{label}</span></div>
      {body}<div class="foot">USGS verified · observed, not forecast</div></div>"""


CSS = """
*{box-sizing:border-box;margin:0;font-family:"Segoe UI",Inter,system-ui,sans-serif}
body{background:transparent;color:#e6ecf8;padding:2px}
.grid{display:grid;gap:12px}
.r1{grid-template-columns:1.55fr 1fr}.r2{grid-template-columns:1.55fr 1fr}.r3{grid-template-columns:1.05fr 1.35fr .9fr}
.card{background:linear-gradient(160deg,#0f1b36,#0b1429);border:1px solid rgba(96,130,200,.2);border-radius:14px;padding:14px 16px}
.ttl{font-weight:700;font-size:14px;color:#fff;margin-bottom:10px}
.head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.head .ttl{margin:0}
.badge{border:1px solid;border-radius:999px;font-size:11.5px;font-weight:700;padding:3px 10px;white-space:nowrap}
.foot{color:#7f8fb0;font-size:11px;margin-top:8px}.muted{color:#8b9bb8;font-size:12.5px}
.wx{display:flex;gap:14px;background:linear-gradient(120deg,#16305f 0%,#10224a 45%,#0c1a3a 100%);position:relative;overflow:hidden}
.wx:after{content:"";position:absolute;right:-60px;bottom:-40px;width:320px;height:180px;
 background:radial-gradient(closest-side,rgba(255,255,255,.12),transparent);filter:blur(6px)}
.wx-main{flex:1;z-index:1}.loc{font-size:17px;font-weight:700}.date{color:#9fb0d0;font-size:12.5px;margin-top:2px}
.wx-now{display:flex;align-items:center;gap:22px;margin-top:10px}
.wx-ico{text-align:center;color:#c4d0ea;font-size:11.5px}.big-ico{font-size:66px;line-height:1.1;filter:drop-shadow(0 4px 10px rgba(0,0,0,.35))}
.temp{font-size:54px;font-weight:700;line-height:1}.cond{font-size:17px;margin-top:4px}.feels{color:#9fb0d0;font-size:12.5px}
.wx-stats{z-index:1;background:rgba(8,16,36,.55);border:1px solid rgba(96,130,200,.22);border-radius:12px;padding:8px 12px;min-width:220px;
 display:flex;flex-direction:column;justify-content:space-around}
.st{display:flex;align-items:center;gap:8px;font-size:12.5px;padding:4px 0}.si{width:18px;text-align:center}.sl{flex:1;color:#b8c5e0}
.outlook-body{display:flex;gap:12px;align-items:center}.outlook-body p{font-size:13px;line-height:1.55;color:#d6def0;flex:1}
.bolt{width:82px;height:96px;border-radius:10px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:44px;
 background:radial-gradient(circle at 50% 30%,#4c3fb4,#141a4a 70%);box-shadow:inset 0 0 18px rgba(147,112,255,.45)}
.slots{display:grid;grid-template-columns:repeat(8,1fr);gap:6px}
.slot{text-align:center;padding:8px 2px;border-radius:10px;border:1px solid transparent}
.slot.now{border-color:#3b82f6;background:rgba(37,99,235,.18)}
.slot .t{font-size:12px;color:#c9d4ea}.slot .i{font-size:24px;margin:4px 0}.slot .d{font-weight:700;font-size:14px}.slot .p{font-size:11px;color:#93b4f5}
.rain svg{width:100%;height:120px}.ax{fill:#8b9bb8;font-size:8px}.gl{stroke:rgba(140,160,200,.15);stroke-width:.6}
.dayrow{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.day{background:rgba(20,34,66,.6);border:1px solid rgba(96,130,200,.16);border-radius:10px;padding:10px 4px;text-align:center}
.dn{font-size:12px;color:#c9d4ea}.di{font-size:30px;margin:6px 0}.dt{font-weight:700;font-size:14px}.dc{font-size:11px;color:#9fb0d0;margin-top:2px}
.map-wrap{position:relative;height:150px;border-radius:10px;overflow:hidden}#map{position:absolute;inset:0 112px 0 0;border-radius:10px}
.legend{position:absolute;right:0;top:0;bottom:0;width:104px;background:rgba(8,16,36,.7);border:1px solid rgba(96,130,200,.2);
 border-radius:10px;padding:8px;font-size:11px;display:flex;flex-direction:column;gap:5px}
.legend i{display:inline-block;width:14px;height:10px;border-radius:2px;margin-right:6px;vertical-align:middle}
.live{margin-top:auto;background:#2563eb;color:#fff;text-decoration:none;text-align:center;border-radius:7px;padding:6px 0;font-weight:600}
.qtop{display:flex;align-items:center;gap:10px;margin-bottom:6px}.qbig{font-size:30px;font-weight:800;color:#fbbf24}
.qrow{display:flex;gap:6px;font-size:11.5px;padding:3px 0;border-top:1px solid rgba(96,130,200,.12);align-items:baseline}
.qrow span{flex:1;color:#c9d4ea;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.qrow em{color:#7f8fb0;font-style:normal}
.leaflet-container{background:#0b1429}.leaflet-control-attribution{font-size:8px!important;background:rgba(8,16,36,.6)!important;color:#8b9bb8!important}.leaflet-control-attribution a{color:#93b4f5!important}.nodata{position:absolute;inset:30px 0 18px 30px;display:flex;align-items:center;justify-content:center;color:#8b9bb8;font-size:12px}.rain{position:relative}
@media(max-width:820px){.r1,.r2,.r3{grid-template-columns:1fr}.slots{grid-template-columns:repeat(4,1fr)}}
"""


def grid_html(report: WeatherReport, comparison: ModelComparison | None, alerts: AlertResult | None,
              quakes: QuakeReport | None, radar_url: str | None) -> str:
    loc = report.location
    radar_layer = (f"L.tileLayer({radar_url!r},{{opacity:.7,maxNativeZoom:7,maxZoom:12,attribution:'Radar © RainViewer'}}).addTo(m);" if radar_url else "")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><style>{CSS}</style></head><body>
<div class="grid">
  <div class="grid r1">{weather_card(report)}{outlook_card(report, comparison, alerts)}</div>
  <div class="grid r2">{strip_card(report)}{rain_chart(report)}</div>
  <div class="grid r3">{days_card(report)}{radar_card(report, radar_url)}{quake_card(quakes)}</div>
</div>
<script>
const m=L.map('map',{{zoomControl:false,attributionControl:true}}).setView([{loc.latitude},{loc.longitude}],8);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{attribution:'Imagery © Esri'}}).addTo(m);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}').addTo(m);
{radar_layer}
L.circleMarker([{loc.latitude},{loc.longitude}],{{radius:7,color:'#fff',weight:2,fillColor:'#ef4444',fillOpacity:1}})
  .addTo(m).bindTooltip({escape(loc.name)!r},{{permanent:true,direction:'right',className:''}});
</script></body></html>"""


def render(report: WeatherReport, comparison: ModelComparison | None, alerts: AlertResult | None,
           quakes: QuakeReport | None, radar_url: str | None) -> None:
    # Safe to embed: every API-provided string in the HTML is escaped (see tests/test_weather.py).
    st.iframe(grid_html(report, comparison, alerts, quakes, radar_url), height="content")


def overall(reports: list[WeatherReport]) -> str:
    return max((r.overall_risk for r in reports), key=RISK_LEVELS.index, default="Low")
