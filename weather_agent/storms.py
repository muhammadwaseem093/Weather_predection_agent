"""Active tropical cyclones worldwide from GDACS (UN/EC Global Disaster Alert, free, keyless)."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from weather_agent.quakes import distance_km
from weather_agent.weather import Location, WeatherError, http_get

EVENTS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
GEOMETRY_URL = "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry"
LOOKBACK_DAYS = 10
# Saffir-Simpson thresholds (km/h, 1-minute sustained wind).
CATEGORIES = ((119, "Tropical Storm"), (154, "Category 1"), (178, "Category 2"), (209, "Category 3"), (252, "Category 4"))


@dataclass
class Cyclone:
    event_id: str
    episode_id: str
    name: str
    alert: str  # GDACS alert level: Green / Orange / Red
    countries: str
    latitude: float
    longitude: float
    wind_kmh: float
    description: str
    report_url: str
    track: list[list[float]] = field(default_factory=list)  # [[lat, lon], ...]
    distance_km: float | None = None

    @property
    def category(self) -> str:
        for limit, label in CATEGORIES:
            if self.wind_kmh < limit:
                return label
        return "Category 5"


def active_cyclones(near: Location | None = None, with_tracks: bool = True) -> list[Cyclone]:
    today = datetime.now(timezone.utc)
    data = http_get(EVENTS_URL, {
        "eventlist": "TC", "alertlevel": "green;orange;red",
        "fromdate": (today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d"), "todate": today.strftime("%Y-%m-%d"),
    }, "GDACS cyclones")
    storms = []
    for feature in data.get("features", []):  # type: ignore[union-attr]
        p = feature.get("properties", {})
        if str(p.get("iscurrent", "")).lower() != "true":
            continue
        lon, lat = (feature.get("geometry", {}).get("coordinates") or [0, 0])[:2]
        severity = p.get("severitydata") or {}
        storm = Cyclone(
            event_id=str(p.get("eventid", "")), episode_id=str(p.get("episodeid", "")),
            name=p.get("eventname") or p.get("name") or "Cyclone", alert=p.get("alertlevel") or "Green",
            countries=p.get("country") or "Open ocean", latitude=float(lat), longitude=float(lon),
            wind_kmh=float(severity.get("severity") or 0), description=severity.get("severitytext") or "",
            report_url=(p.get("url") or {}).get("report", ""),
        )
        if near is not None:
            storm.distance_km = distance_km(near.latitude, near.longitude, storm.latitude, storm.longitude)
        if with_tracks:
            storm.track = _track(storm)
        storms.append(storm)
    storms.sort(key=lambda s: (s.distance_km if s.distance_km is not None else 0, -s.wind_kmh))
    return storms


def _track(storm: Cyclone) -> list[list[float]]:
    """The storm's path (observed + forecast) as [lat, lon] points; empty if unavailable."""
    try:
        data = http_get(GEOMETRY_URL, {"eventtype": "TC", "eventid": storm.event_id, "episodeid": storm.episode_id},
                        "GDACS cyclones")
    except WeatherError:
        return []
    lines = [f for f in data.get("features", []) if f.get("geometry", {}).get("type") == "LineString"]  # type: ignore[union-attr]
    lines.sort(key=lambda f: str(f.get("properties", {}).get("Class", "")))
    return [[lat, lon] for f in lines for lon, lat, *_ in f["geometry"]["coordinates"]]


def summary(storms: list[Cyclone], place: str) -> str:
    if not storms:
        return f"No active tropical cyclones worldwide (GDACS). No cyclone threat to {place}."
    lines = [f"Active tropical cyclones (GDACS, verified): {len(storms)}."]
    for s in storms[:5]:
        away = f", {s.distance_km:.0f} km from {place}" if s.distance_km is not None else ""
        lines.append(f"- {s.name}: {s.category}, max wind {s.wind_kmh:.0f} km/h, alert {s.alert}, {s.countries}{away}")
    return "\n".join(lines)
