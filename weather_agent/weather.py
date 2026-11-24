"""Live weather, recent history, hourly/daily forecasts and the storm-risk score.

Data comes from Open-Meteo: free, keyless and worldwide, so the app deploys on
Streamlit Community Cloud with only the LLM key as a secret.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from weather_agent import store

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HTTP_TIMEOUT_SECONDS = 15
MAX_FORECAST_HOURS = 72
HISTORY_HOURS = 12
FORECAST_DAYS = 7
USER_AGENT = "Zentro AI weather app"

CURRENT_FIELDS = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,"
    "wind_speed_10m,wind_gusts_10m,wind_direction_10m,precipitation,rain,pressure_msl,cloud_cover,is_day,"
    "visibility,uv_index"
)
HOURLY_FIELDS = (
    "temperature_2m,precipitation_probability,precipitation,weather_code,"
    "wind_gusts_10m,cape,relative_humidity_2m,pressure_msl"
)
DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "precipitation_probability_max,wind_gusts_10m_max"
)

# Thresholds forecasters use as rough storm indicators.
THUNDERSTORM_CODES = {95, 96, 99}
RAIN_CODES = set(range(51, 68)) | set(range(80, 83))
CAPE_STRONG = 1000  # J/kg: enough instability for thunderstorms
CAPE_SEVERE = 2500  # J/kg: severe thunderstorms possible
GUST_STRONG = 60  # km/h: damaging-gust warning territory
GUST_SEVERE = 90  # km/h
RAIN_LIKELY = 50  # % precipitation probability
HEAVY_RAIN_MM = 7.6  # mm/h, WMO "heavy rain"
DAY_RAIN_HEAVY_MM = 50  # mm/day
DAY_RAIN_NOTABLE_MM = 20  # mm/day

# WMO rain-rate classes (mm/h).
INTENSITY_CLASSES = ((0.1, "None"), (2.5, "Light"), (7.6, "Moderate"), (50.0, "Heavy"))

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Heavy rain showers", 82: "Violent rain showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

RISK_LEVELS = ("Low", "Moderate", "High", "Severe")


class WeatherError(Exception):
    """A city could not be found or a weather service failed."""


@dataclass(frozen=True)
class Location:
    name: str
    country: str
    latitude: float
    longitude: float
    timezone: str = "auto"
    country_code: str = ""
    admin1: str = ""

    @property
    def label(self) -> str:
        return f"{self.name}, {self.country}" if self.country else self.name

    @property
    def full_label(self) -> str:
        parts = [self.name, self.admin1, self.country]
        return ", ".join(p for p in dict.fromkeys(parts) if p)


@dataclass
class HourRisk:
    time: str
    temperature: float
    rain_probability: int
    precipitation_mm: float
    gusts_kmh: float
    cape: float
    condition: str
    risk: str
    reasons: list[str] = field(default_factory=list)

    @property
    def intensity(self) -> str:
        return rain_intensity(self.precipitation_mm)


@dataclass
class DayForecast:
    date: str
    condition: str
    temp_min: float
    temp_max: float
    precipitation_mm: float
    rain_probability: int
    gusts_kmh: float
    risk: str


@dataclass
class WeatherReport:
    location: Location
    current: dict
    hours: list[HourRisk]
    history: list[HourRisk] = field(default_factory=list)
    days: list[DayForecast] = field(default_factory=list)
    fetched_at: str = ""
    # Filled by weather_agent.sources when the agent or dashboard asks for them.
    comparison: object | None = None
    alerts: object | None = None
    quakes: object | None = None

    @property
    def overall_risk(self) -> str:
        return max((h.risk for h in self.hours), key=RISK_LEVELS.index, default="Low")

    @property
    def storm_hours(self) -> list[HourRisk]:
        return [h for h in self.hours if h.risk in ("High", "Severe")]

    @property
    def rain_hours(self) -> list[HourRisk]:
        return [h for h in self.hours if h.rain_probability >= RAIN_LIKELY]


def describe(code: int | None) -> str:
    return WEATHER_CODES.get(int(code or 0), "Unknown")


COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
UV_LEVELS = ((3, "Low"), (6, "Moderate"), (8, "High"), (11, "Very high"))


def compass(degrees: float | None) -> str:
    return COMPASS[round((degrees or 0) / 45) % 8]


def uv_level(index: float | None) -> str:
    for limit, label in UV_LEVELS:
        if (index or 0) < limit:
            return label
    return "Extreme"


def rain_intensity(mm_per_hour: float) -> str:
    for limit, label in INTENSITY_CLASSES:
        if mm_per_hour < limit:
            return label
    return "Violent"


def http_get(url: str, params: dict, service: str) -> dict | list:
    """GET JSON and record the call for the admin dashboard's API-usage view."""
    started = time.perf_counter()
    ok = False
    try:
        response = requests.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        data = response.json()
        ok = True
        return data
    except (requests.RequestException, ValueError) as error:
        raise WeatherError(f"{service} is unavailable ({type(error).__name__}).") from error
    finally:
        store.log_api_call(service, ok, int((time.perf_counter() - started) * 1000))


def _location(item: dict) -> Location:
    return Location(
        name=item["name"], country=item.get("country", ""), latitude=item["latitude"],
        longitude=item["longitude"], timezone=item.get("timezone", "auto"),
        country_code=item.get("country_code", ""), admin1=item.get("admin1", ""),
    )


def search_locations(query: str, count: int = 8) -> list[Location]:
    """Find places by name. 'City, Country' narrows the match to that country."""
    name, _, country = (part.strip() for part in query.partition(","))
    if not name:
        return []
    data = http_get(GEOCODE_URL, {"name": name, "count": 20 if country else count, "language": "en"}, "Open-Meteo geocoding")
    places = [_location(item) for item in data.get("results") or []]  # type: ignore[union-attr]
    if country:
        wanted = country.lower()
        places = [p for p in places if wanted in (p.country.lower(), p.country_code.lower())] or places
    return places[:count]


def geocode(city: str) -> Location:
    places = search_locations(city.strip(), count=1)
    if not places:
        raise WeatherError(f"Could not find a place called '{city}'.")
    return places[0]


def score_hour(code: int, rain_probability: int, precipitation: float, gusts: float, cape: float) -> tuple[str, list[str]]:
    """Classify one forecast hour into a storm-risk level with the reasons why."""
    level = 0
    reasons: list[str] = []
    if code in THUNDERSTORM_CODES:
        level = max(level, 3 if code in (96, 99) else 2)
        reasons.append(describe(code))
    if cape >= CAPE_SEVERE and rain_probability >= RAIN_LIKELY:
        level = max(level, 3)
        reasons.append(f"very unstable air (CAPE {cape:.0f} J/kg)")
    elif cape >= CAPE_STRONG and rain_probability >= RAIN_LIKELY:
        level = max(level, 2)
        reasons.append(f"unstable air (CAPE {cape:.0f} J/kg)")
    if gusts >= GUST_SEVERE:
        level = max(level, 3)
        reasons.append(f"severe gusts {gusts:.0f} km/h")
    elif gusts >= GUST_STRONG:
        level = max(level, 2)
        reasons.append(f"strong gusts {gusts:.0f} km/h")
    if precipitation >= HEAVY_RAIN_MM:
        level = max(level, 2)
        reasons.append(f"heavy rain {precipitation:.1f} mm/h")
    elif rain_probability >= RAIN_LIKELY or code in RAIN_CODES:
        level = max(level, 1)
        reasons.append(f"rain likely ({rain_probability}%)")
    return RISK_LEVELS[level], reasons


def score_day(code: int, rain_probability: int, precipitation_sum: float, gusts: float) -> str:
    level = 0
    if code in THUNDERSTORM_CODES:
        level = 3 if code in (96, 99) else 2
    if gusts >= GUST_SEVERE:
        level = max(level, 3)
    elif gusts >= GUST_STRONG:
        level = max(level, 2)
    if precipitation_sum >= DAY_RAIN_HEAVY_MM:
        level = max(level, 2)
    elif precipitation_sum >= DAY_RAIN_NOTABLE_MM or rain_probability >= RAIN_LIKELY:
        level = max(level, 1)
    return RISK_LEVELS[level]


def _num(values: list, i: int) -> float:
    value = values[i] if i < len(values) else None
    return float(value) if value is not None else 0.0


def _hours(hourly: dict) -> list[HourRisk]:
    rows = []
    for i, stamp in enumerate(hourly["time"]):
        code = int(_num(hourly["weather_code"], i))
        probability = int(_num(hourly["precipitation_probability"], i))
        precipitation = _num(hourly["precipitation"], i)
        gusts = _num(hourly["wind_gusts_10m"], i)
        cape = _num(hourly["cape"], i)
        risk, reasons = score_hour(code, probability, precipitation, gusts, cape)
        rows.append(HourRisk(stamp, _num(hourly["temperature_2m"], i), probability, precipitation,
                             gusts, cape, describe(code), risk, reasons))
    return rows


def _days(daily: dict) -> list[DayForecast]:
    rows = []
    for i, day in enumerate(daily["time"]):
        code = int(_num(daily["weather_code"], i))
        probability = int(_num(daily["precipitation_probability_max"], i))
        precipitation = _num(daily["precipitation_sum"], i)
        gusts = _num(daily["wind_gusts_10m_max"], i)
        rows.append(DayForecast(day, describe(code), _num(daily["temperature_2m_min"], i),
                                _num(daily["temperature_2m_max"], i), precipitation, probability, gusts,
                                score_day(code, probability, precipitation, gusts)))
    return rows


def fetch_report(place: str | Location, hours: int = 24, days: int = FORECAST_DAYS) -> WeatherReport:
    """Current conditions, the last 12 hours, the next `hours` hours and `days` daily forecasts."""
    hours = max(1, min(int(hours), MAX_FORECAST_HOURS))
    days = max(1, min(int(days), 16))
    location = place if isinstance(place, Location) else geocode(place)
    data = http_get(FORECAST_URL, {
        "latitude": location.latitude, "longitude": location.longitude,
        "current": CURRENT_FIELDS, "hourly": HOURLY_FIELDS, "daily": DAILY_FIELDS,
        "past_hours": HISTORY_HOURS, "forecast_hours": hours, "forecast_days": days,
        "timezone": "auto", "wind_speed_unit": "kmh",
    }, "Open-Meteo forecast")
    try:
        current = dict(data["current"])  # type: ignore[call-overload]
        current["condition"] = describe(current.get("weather_code"))
        all_hours = _hours(data["hourly"])  # type: ignore[call-overload]
        days_rows = _days(data["daily"])  # type: ignore[call-overload]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise WeatherError(f"Unexpected weather data ({type(error).__name__}).") from error
    this_hour = str(current.get("time", ""))[:13]
    history = [h for h in all_hours if h.time[:13] < this_hour]
    upcoming = [h for h in all_hours if h.time[:13] >= this_hour][:hours]
    return WeatherReport(location, current, upcoming, history, days_rows,
                         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))


def current_summary(report: WeatherReport) -> str:
    c = report.current
    return (
        f"Live weather in {report.location.full_label} (local time {c.get('time', '?')}): {c['condition']}, "
        f"{c.get('temperature_2m')}°C (feels like {c.get('apparent_temperature')}°C), "
        f"humidity {c.get('relative_humidity_2m')}%, wind {c.get('wind_speed_10m')} km/h "
        f"(gusts {c.get('wind_gusts_10m')} km/h), rainfall {c.get('precipitation')} mm in the last hour, "
        f"pressure {c.get('pressure_msl')} hPa, cloud cover {c.get('cloud_cover')}%."
    )


def history_summary(report: WeatherReport) -> str:
    if not report.history:
        return "No recent observations available."
    total = sum(h.precipitation_mm for h in report.history)
    wet = [h.time[11:16] for h in report.history if h.precipitation_mm >= 0.1]
    first, last = report.history[0], report.history[-1]
    trend = last.temperature - first.temperature
    return (
        f"Last {len(report.history)} hours: {total:.1f} mm of rain"
        f"{' (at ' + ', '.join(wet) + ')' if wet else ' (dry)'}; temperature changed {trend:+.1f}°C; "
        f"max gust {max(h.gusts_kmh for h in report.history):.0f} km/h."
    )


def prediction_summary(report: WeatherReport) -> str:
    lines = [
        f"MODEL-BASED storm & rain outlook for {report.location.label}, next {len(report.hours)} hours "
        f"(overall risk: {report.overall_risk}). {history_summary(report)}",
    ]
    flagged = [h for h in report.hours if h.risk != "Low"]
    if not flagged:
        lines.append("No rain or storm signals in this window.")
    for h in flagged:
        lines.append(
            f"- {h.time}: {h.risk} risk — {h.condition}, rain {h.rain_probability}% / {h.precipitation_mm} mm "
            f"({h.intensity}), gusts {h.gusts_kmh:.0f} km/h, CAPE {h.cape:.0f} ({'; '.join(h.reasons)})"
        )
    return "\n".join(lines)


def daily_summary(report: WeatherReport) -> str:
    lines = [f"{len(report.days)}-day forecast for {report.location.label}:"]
    for d in report.days:
        lines.append(
            f"- {d.date}: {d.condition}, {d.temp_min:.0f}–{d.temp_max:.0f}°C, rain {d.precipitation_mm:.1f} mm "
            f"(chance {d.rain_probability}%), max gust {d.gusts_kmh:.0f} km/h, risk {d.risk}"
        )
    return "\n".join(lines)
