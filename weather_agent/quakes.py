"""Recent earthquakes near a place, from the USGS (free, keyless, worldwide)."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

from weather_agent.weather import Location, http_get

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
RADIUS_KM = 500
LOOKBACK_DAYS = 7
MIN_MAGNITUDE = 2.5
MAX_EVENTS = 20
STRONG_MAGNITUDE = 5.0
SEVERE_MAGNITUDE = 6.5
EARTH_RADIUS_KM = 6371


@dataclass
class Quake:
    magnitude: float
    place: str
    time: str  # UTC, "YYYY-MM-DD HH:MM"
    depth_km: float
    distance_km: float
    url: str
    tsunami: bool


@dataclass
class QuakeReport:
    radius_km: int
    days: int
    events: list[Quake] = field(default_factory=list)

    @property
    def strongest(self) -> Quake | None:
        return max(self.events, key=lambda q: q.magnitude, default=None)

    @property
    def level(self) -> str:
        top = self.strongest
        if top is None:
            return "None"
        if top.magnitude >= SEVERE_MAGNITUDE:
            return "High"
        return "Moderate" if top.magnitude >= STRONG_MAGNITUDE else "Low"

    def summary(self, place: str) -> str:
        head = f"Earthquakes (USGS, verified) within {self.radius_km} km of {place}, last {self.days} days, M{MIN_MAGNITUDE}+:"
        if not self.events:
            return f"{head} none recorded. Earthquakes cannot be forecast; this is recent activity only."
        lines = [head + f" {len(self.events)} event(s); activity level {self.level}."]
        for q in self.events[:8]:
            lines.append(f"- M{q.magnitude:.1f} {q.place}, {q.time} UTC, depth {q.depth_km:.0f} km, "
                         f"{q.distance_km:.0f} km away{' (tsunami flag)' if q.tsunami else ''}")
        lines.append("Earthquakes cannot be predicted; this is observed recent activity, not a forecast.")
        return "\n".join(lines)


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def recent_quakes(location: Location, radius_km: int = RADIUS_KM, days: int = LOOKBACK_DAYS) -> QuakeReport:
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    data = http_get(USGS_URL, {
        "format": "geojson", "latitude": location.latitude, "longitude": location.longitude,
        "maxradiuskm": radius_km, "starttime": start, "minmagnitude": MIN_MAGNITUDE,
        "orderby": "magnitude", "limit": MAX_EVENTS,
    }, "USGS earthquakes")
    events = []
    for feature in data.get("features", []):  # type: ignore[union-attr]
        p, coords = feature.get("properties", {}), feature.get("geometry", {}).get("coordinates", [0, 0, 0])
        when = datetime.fromtimestamp((p.get("time") or 0) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        events.append(Quake(
            magnitude=float(p.get("mag") or 0), place=p.get("place") or "Unknown", time=when,
            depth_km=float(coords[2] if len(coords) > 2 else 0),
            distance_km=distance_km(location.latitude, location.longitude, coords[1], coords[0]),
            url=p.get("url") or "", tsunami=bool(p.get("tsunami")),
        ))
    return QuakeReport(radius_km, days, events)
