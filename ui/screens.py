"""Page-level screens from the design reference, each rendered as one HTML component.

Live Weather, Rain Forecast, Storm Tracker and Global Weather. They reuse the card
builders in ui.cards; every API-provided string is HTML-escaped.
"""

import json
from datetime import datetime
from html import escape

import streamlit as st

from ui.cards import CSS, clock, days_card, hour_of, icon, rain_chart, strip_card, weather_card
from weather_agent.sources import ModelComparison
from weather_agent.storms import Cyclone
from weather_agent.weather import WeatherReport
from weather_agent.world import GridCell

LEAFLET = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
           '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>')
ESRI_IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_LABELS = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
DARK_BASE = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"

SCREEN_CSS = CSS + """
.r-live{grid-template-columns:1.6fr 1fr}.r-rain{grid-template-columns:1.6fr 1fr}.r-storm{grid-template-columns:2.2fr 1fr}
.week{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;text-align:center}
.week .wd{font-size:12px;color:#c9d4ea}.week .wi{font-size:24px;margin:4px 0}.week .wt{font-size:11.5px;font-weight:600}
.week .wp{font-size:11px;color:#93b4f5}
.checks{list-style:none;padding:0}.checks li{display:flex;gap:8px;font-size:12.5px;margin:7px 0;color:#d6def0}
.ck{background:#16a34a;color:#fff;border-radius:999px;width:16px;height:16px;font-size:10px;display:inline-flex;
 align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}
.wk{background:#f59e0b}.bd{background:#ef4444}
.place-row{display:flex;align-items:center;gap:12px;margin-bottom:12px}.place{font-size:19px;font-weight:700}
.pill{border:1px solid rgba(59,130,246,.5);background:rgba(37,99,235,.18);color:#bfd3ff;border-radius:999px;padding:4px 12px;font-size:12px}
.total{display:flex;flex-direction:column;justify-content:center;gap:6px}.total .big{font-size:34px;font-weight:800}
.total .sub{color:#9fb0d0;font-size:12px}.total .ico{font-size:44px;align-self:flex-end;margin-top:-50px}
table.tb{width:100%;border-collapse:collapse;font-size:12px}table.tb th{color:#8b9bb8;font-weight:600;text-align:left;padding:5px 4px;
 border-bottom:1px solid rgba(96,130,200,.2)}table.tb td{padding:6px 4px;border-bottom:1px solid rgba(96,130,200,.1)}
.scroll{max-height:205px;overflow:auto}
.bigmap{position:relative;height:430px;border-radius:12px;overflow:hidden}#smap,#wmap{position:absolute;inset:0}
.layers{position:absolute;right:10px;top:10px;z-index:500;display:flex;flex-direction:column;gap:6px}
.layers button{background:rgba(8,16,36,.85);color:#dbe4f5;border:1px solid rgba(96,130,200,.3);border-radius:8px;
 padding:6px 12px;font-size:12px;cursor:pointer;text-align:left;min-width:110px}.layers button.on{background:#4f46e5;border-color:#6d63ff}
.storm{border:1px solid rgba(96,130,200,.2);border-radius:10px;padding:10px;margin-bottom:8px;background:rgba(20,34,66,.5)}
.storm .nm{font-weight:700;font-size:14px;display:flex;justify-content:space-between;align-items:center}
.cat{background:#dc2626;color:#fff;font-size:10.5px;border-radius:6px;padding:2px 7px}
.kv{display:flex;justify-content:space-between;font-size:12px;padding:3px 0;color:#c9d4ea}.kv b{color:#fff}
.legend-bar{position:absolute;left:50%;transform:translateX(-50%);bottom:12px;z-index:500;background:rgba(8,16,36,.85);
 border:1px solid rgba(96,130,200,.3);border-radius:10px;padding:8px 12px;font-size:11px;width:330px}
.grad{height:9px;border-radius:5px;margin:4px 0}.ticks{display:flex;justify-content:space-between;color:#c9d4ea}
.city{background:rgba(8,16,36,.85);border:1px solid rgba(255,255,255,.25);border-radius:7px;color:#fff;padding:3px 7px;
 font:600 11px "Segoe UI",sans-serif;white-space:nowrap}
.leaflet-tooltip.city{box-shadow:none}.leaflet-tooltip.city:before{display:none}
"""


def _page(body: str, script: str = "", leaflet: bool = False) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'>{LEAFLET if leaflet else ''}<style>{SCREEN_CSS}</style>"
            f"</head><body>{body}<script>{script}</script></body></html>")


def show(html: str) -> None:
    # Safe to embed: every API-provided string in these screens is escaped.
    st.iframe(html, height="content")


# ---------- Live Weather ------------------------------------------------------------


def highlights(report: WeatherReport) -> list[tuple[str, str]]:
    """Today's highlights as (tone, text); tone is ok / warn / bad."""
    items = []
    storms = report.storm_hours
    items.append(("bad", f"{storms[0].risk} storm risk from {clock(storms[0].time)}") if storms
                 else ("ok", "No severe weather expected"))
    rainy = report.rain_hours
    items.append(("warn", f"Rain likely from {clock(rainy[0].time)} ({max(h.rain_probability for h in rainy)}% peak)") if rainy
                 else ("ok", "Dry for the next 24 hours"))
    feels = float(report.current.get("apparent_temperature") or 0)
    items.append(("ok", "Comfortable temperature") if 15 <= feels <= 28 else
                 ("warn", "Cold - dress warmly") if feels < 15 else ("warn", "Hot - stay hydrated"))
    gust = max((h.gusts_kmh for h in report.hours), default=0)
    if gust >= 40:
        items.append(("warn", f"Gusty winds up to {gust:.0f} km/h"))
    return items


def _checks(items: list[tuple[str, str]]) -> str:
    marks = {"ok": ("✓", ""), "warn": ("!", " wk"), "bad": ("!", " bd")}
    return "<ul class='checks'>" + "".join(
        f"<li><span class='ck{marks[t][1]}'>{marks[t][0]}</span>{escape(x)}</li>" for t, x in items) + "</ul>"


def _week(report: WeatherReport, rain_only: bool = False) -> str:
    cells = []
    for d in report.days[:7]:
        day = datetime.strptime(d.date, "%Y-%m-%d")
        bottom = f"<div class='wp'>{d.rain_probability}%</div>" if rain_only else \
            f"<div class='wt'>{round(d.temp_min)}°/{round(d.temp_max)}°</div>"
        top = f"<div class='wp'>{d.rain_probability}%</div>" if rain_only else ""
        cells.append(f"<div><div class='wd'>{day:%a}</div>{top if rain_only else ''}<div class='wi'>{icon(d.condition)}</div>"
                     f"{'' if rain_only else bottom}</div>")
    return "<div class='week'>" + "".join(cells) + "</div>"


def live_html(report: WeatherReport) -> str:
    body = f"""<div class="grid">{weather_card(report)}{strip_card(report)}
      <div class="grid r-live"><div class="card"><div class="ttl">📅 7-Day Forecast</div>{_week(report)}</div>
      <div class="card"><div class="ttl">Today's Highlights</div>{_checks(highlights(report))}</div></div></div>"""
    return _page(body)


# ---------- Rain Forecast -------------------------------------------------------------


def rain_outlook(report: WeatherReport) -> str:
    peak = max((h.rain_probability for h in report.hours[:24]), default=0)
    total = sum(h.precipitation_mm for h in report.hours[:24])
    if peak < 30:
        return "No Significant Rain Expected"
    if total >= 20 or any(h.intensity in ("Heavy", "Violent") for h in report.hours[:24]):
        return "Heavy Rain Expected"
    return "Light to Moderate Rain Expected" if total >= 2 else "Light Rain Possible"


def rain_html(report: WeatherReport, comparison: ModelComparison | None) -> str:
    hours = report.hours[:24]
    total = sum(h.precipitation_mm for h in hours)
    if comparison and comparison.runs:
        low, high = min(r.total_mm for r in comparison.runs), max(r.total_mm for r in comparison.runs)
        amount, note = f"{low:.0f} – {high:.0f} mm" if high >= 1 else f"{total:.1f} mm", f"{len(comparison.runs)} models"
    else:
        amount, note = f"{total:.1f} mm", "Open-Meteo"
    wet = [h for h in hours if h.rain_probability >= 40]
    window = f"Peak: {clock(wet[0].time)} – {clock(wet[-1].time)}" if wet else "No wet window expected"
    rows = "".join(
        f"<tr><td>{clock(h.time)}</td><td>{icon(h.condition, hour_of(h.time))} {escape(h.condition)}</td>"
        f"<td>{h.rain_probability}%</td><td>{'< 0.1' if h.precipitation_mm < 0.1 else f'{h.precipitation_mm:.1f}'}</td></tr>"
        for h in hours)
    body = f"""<div class="place-row"><span class="place">☁️ {escape(report.location.label)}</span>
      <span class="pill">Rain Outlook: {escape(rain_outlook(report))}</span></div>
      <div class="grid"><div class="grid r-rain">{rain_chart(report, width=560)}
        <div class="card total"><div class="ttl">💧 Total Expected Rain</div><div class="big">{amount}</div>
          <div class="ico">🌧️</div><div class="sub">{window} · next 24 h · {note}</div></div></div>
      <div class="grid r-rain"><div class="card"><div class="ttl">⏱️ Hourly Rain Details</div><div class="scroll">
        <table class="tb"><tr><th>Time</th><th>Condition</th><th>Rain Chance</th><th>Rain (mm)</th></tr>{rows}</table></div></div>
        <div class="card"><div class="ttl">📅 7-Day Rain Outlook</div>{_week(report, rain_only=True)}</div></div></div>"""
    return _page(body)


# ---------- Storm Tracker --------------------------------------------------------------


def storm_html(report: WeatherReport, storms: list[Cyclone], radar_url: str | None, impacts: list[tuple[str, str]]) -> str:
    loc = report.location
    cards_html = "".join(
        f"""<div class="storm"><div class="nm">🌀 {escape(s.name)}<span class="cat">{escape(s.category)}</span></div>
        <div class="kv">Region<b>{escape(s.countries[:28])}</b></div><div class="kv">Max wind<b>{s.wind_kmh:.0f} km/h</b></div>
        <div class="kv">GDACS alert<b>{escape(s.alert)}</b></div>
        <div class="kv">Distance from {escape(loc.name)}<b>~{(s.distance_km or 0):,.0f} km</b></div></div>"""
        for s in storms[:3]) or "<p class='muted'>No active tropical cyclones worldwide right now (GDACS).</p>"
    data = json.dumps([{"name": s.name, "lat": s.latitude, "lon": s.longitude, "track": s.track,
                        "label": f"{s.name} · {s.category}"} for s in storms])
    body = f"""<div class="grid r-storm">
      <div class="card"><div class="bigmap"><div id="smap"></div><div class="layers">
        <button id="b-sat" class="on" onclick="tog('sat')">🛰️ Satellite</button>
        <button id="b-radar" class="{'on' if radar_url else ''}" onclick="tog('radar')">📡 Radar</button>
        <button id="b-lab" class="on" onclick="tog('lab')">🏷️ Labels</button></div></div>
        <div class="foot">Cyclone positions & tracks: GDACS · radar: RainViewer · imagery: Esri</div></div>
      <div><div class="card" style="margin-bottom:12px"><div class="ttl">Active Storms ({len(storms)})</div>{cards_html}</div>
        <div class="card"><div class="ttl">⚠️ Risk &amp; Impact</div>{_checks(impacts)}</div></div></div>"""
    script = f"""
const m=L.map('smap',{{zoomControl:true}});const storms={data};
const L_={{sat:L.tileLayer({ESRI_IMAGERY!r}).addTo(m),lab:L.tileLayer({ESRI_LABELS!r}).addTo(m),
 radar:{f"L.tileLayer({radar_url!r},{{opacity:.7,maxNativeZoom:7,maxZoom:12}}).addTo(m)" if radar_url else "null"}}};
function tog(k){{const l=L_[k];if(!l)return;const b=document.getElementById('b-'+k);
 if(m.hasLayer(l)){{m.removeLayer(l);b.classList.remove('on')}}else{{l.addTo(m);b.classList.add('on')}}}}
const home=[{loc.latitude},{loc.longitude}];const pts=[home];
L.circleMarker(home,{{radius:7,color:'#fff',weight:2,fillColor:'#ef4444',fillOpacity:1}}).addTo(m)
 .bindTooltip({escape(loc.name)!r},{{permanent:true,direction:'right',className:'city'}});
storms.forEach(s=>{{if(s.track.length>1)L.polyline(s.track,{{color:'#f87171',weight:2.5,dashArray:'6 6'}}).addTo(m);
 L.marker([s.lat,s.lon],{{icon:L.divIcon({{html:'<div style="font-size:30px;filter:drop-shadow(0 0 8px #f00)">🌀</div>',
 className:'',iconSize:[30,30],iconAnchor:[15,15]}})}}).addTo(m).bindTooltip(s.label.replace(/</g,'&lt;'),{{className:'city'}});
 pts.push([s.lat,s.lon]);}});
if(pts.length>1){{const near=storms.length?[[storms[0].lat,storms[0].lon],home]:pts;m.fitBounds(near,{{padding:[40,40],maxZoom:6}})}}else m.setView(home,6);"""
    return _page(body, script, leaflet=True)


# ---------- Global Weather -------------------------------------------------------------

LAYER_SCALES = {  # (min, max, gradient stops, unit)
    "temperature": (-30, 45, ["#7c3aed", "#2563eb", "#06b6d4", "#22c55e", "#facc15", "#f97316", "#dc2626"], "°C"),
    "precipitation": (0, 5, ["#0b1429", "#1e3a8a", "#2563eb", "#22c55e", "#facc15", "#dc2626"], "mm/h"),
    "wind": (0, 60, ["#0b1429", "#155e75", "#06b6d4", "#a3e635", "#facc15", "#dc2626"], "km/h"),
    "clouds": (0, 100, ["#0b1429", "#334155", "#64748b", "#cbd5e1", "#f8fafc"], "%"),
    "pressure": (980, 1040, ["#7c3aed", "#2563eb", "#22c55e", "#facc15", "#dc2626"], "hPa"),
}


def world_html(cells: list[GridCell], cities: list[dict], step: int) -> str:
    grid = json.dumps([[c.latitude, c.longitude, c.values] for c in cells])
    scales = json.dumps(LAYER_SCALES)
    safe_cities = json.dumps([{**c, "name": escape(c["name"])} for c in cities])
    buttons = "".join(f"<button id='l-{k}' class='{'on' if k == 'temperature' else ''}' onclick=\"show('{k}')\">"
                      f"{label}</button>" for k, label in (("temperature", "🌡️ Temperature"), ("precipitation", "🌧️ Precipitation"),
                                                         ("wind", "💨 Wind"), ("clouds", "☁️ Clouds"), ("pressure", "⏲️ Pressure")))
    body = f"""<div class="card"><div class="bigmap" style="height:470px"><div id="wmap"></div>
      <div class="layers">{buttons}</div><div class="legend-bar"><div id="lg-t"></div><div class="grad" id="lg-g"></div>
      <div class="ticks" id="lg-k"></div></div></div><div class="foot">Live Open-Meteo data on a {step}° grid · tap a city for details</div></div>"""
    script = f"""
const m=L.map('wmap',{{worldCopyJump:true,zoomControl:true,minZoom:2}}).setView([25,20],2);
L.tileLayer({DARK_BASE!r},{{attribution:'Base map © Esri'}}).addTo(m);
const G={grid},S={scales},C={safe_cities},step={step};let layer=L.layerGroup().addTo(m);
function hex(h){{return [1,3,5].map(i=>parseInt(h.slice(i,i+2),16))}}
function col(v,k){{const [lo,hi,st]=S[k];let t=Math.max(0,Math.min(1,(v-lo)/(hi-lo)))*(st.length-1);const i=Math.min(Math.floor(t),st.length-2),f=t-i;
 const a=hex(st[i]),b=hex(st[i+1]);return 'rgb('+a.map((x,j)=>Math.round(x+(b[j]-x)*f)).join(',')+')'}}
function show(k){{layer.clearLayers();G.forEach(([la,lo,v])=>L.rectangle([[la-step/2,lo-step/2],[la+step/2,lo+step/2]],
 {{stroke:false,fillColor:col(v[k],k),fillOpacity:.62}}).addTo(layer));
 C.forEach(c=>L.marker([c.lat,c.lon],{{icon:L.divIcon({{className:'',html:'<div class="city">'+c.name+'<br>'+c.icon+' '+
  Math.round(c.temp)+'°C</div>',iconSize:null}})}}).addTo(layer));
 document.querySelectorAll('.layers button').forEach(b=>b.classList.toggle('on',b.id==='l-'+k));
 const [lo,hi,st,u]=S[k];document.getElementById('lg-g').style.background='linear-gradient(90deg,'+st.join(',')+')';
 document.getElementById('lg-t').textContent=k.charAt(0).toUpperCase()+k.slice(1)+' ('+u+')';
 document.getElementById('lg-k').innerHTML=[lo,(lo+hi)/2,hi].map(x=>'<span>'+Math.round(x)+'</span>').join('');}}
show('temperature');"""
    return _page(body, script, leaflet=True)
