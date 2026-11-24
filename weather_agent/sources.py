"""Second opinions: independent forecast models, official warnings and radar.

Model comparison gives a confidence level for the rain/storm outlook. Official
warnings come from a national weather service and are kept separate from the
model-based risk score so users can tell a verified warning from a prediction.
"""

from dataclasses import dataclass, field

from weather_agent.weather import (
    FORECAST_URL, GUST_STRONG, THUNDERSTORM_CODES, Location, WeatherError, http_get,
)

MODELS = {
    "ecmwf_ifs025": "ECMWF IFS (Europe)",
    "gfs_seamless": "NOAA GFS (USA)",
    "icon_seamless": "DWD ICON (Germany)",
}
RAIN_MM = 0.1  # mm/h counted as "rain" when models vote
CONFIDENCE_HIGH = 0.85
CONFIDENCE_MEDIUM = 0.65

NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
RAINVIEWER_URL = "https://api.rainviewer.com/public/weather-maps.json"


@dataclass
class ModelRun:
    model: str
    total_mm: float
    rain_hours: int
    storm_hours: int
    max_gust_kmh: float
    strong_gust_hours: int


@dataclass
class ModelComparison:
    hours: int
    runs: list[ModelRun]
    agreement: float  # 0..1, share of models agreeing on rain/no-rain, averaged over hours

    @property
    def confidence(self) -> str:
        if len(self.runs) < 2:
            return "Low"
        if self.agreement >= CONFIDENCE_HIGH:
            return "High"
        return "Medium" if self.agreement >= CONFIDENCE_MEDIUM else "Low"

    def summary(self) -> str:
        lines = [
            f"Forecast confidence: {self.confidence} — {len(self.runs)} independent models agree on "
            f"rain/no-rain {self.agreement:.0%} of the next {self.hours} hours.",
        ]
        for r in self.runs:
            lines.append(
                f"- {r.model}: {r.total_mm:.1f} mm total, rain in {r.rain_hours} h, thunderstorm in "
                f"{r.storm_hours} h, max gust {r.max_gust_kmh:.0f} km/h"
            )
        return "\n".join(lines)


@dataclass
class Alert:
    event: str
    severity: str
    headline: str
    onset: str
    expires: str
    area: str


@dataclass
class AlertResult:
    covered: bool  # True when an official feed exists for this country
    source: str
    alerts: list[Alert] = field(default_factory=list)

    def summary(self) -> str:
        if not self.covered:
            return (f"OFFICIAL WARNINGS: not available — {self.source}. Any risk stated is model-based only, "
                    "not a verified warning; check the national weather service.")
        if not self.alerts:
            return f"OFFICIAL WARNINGS ({self.source}): no active alerts for this location."
        items = "\n".join(f"- {a.event} [{a.severity}]: {a.headline} (until {a.expires})" for a in self.alerts)
        return f"OFFICIAL WARNINGS ({self.source}), verified and active:\n{items}"


def hourly_agreement(votes: list[list[bool]]) -> float:
    """Mean share of models in the majority, per hour. votes[hour] = one bool per model."""
    shares = [max(sum(v), len(v) - sum(v)) / len(v) for v in votes if v]
    return sum(shares) / len(shares) if shares else 0.0


def compare_models(location: Location, hours: int = 24) -> ModelComparison:
    data = http_get(FORECAST_URL, {
        "latitude": location.latitude, "longitude": location.longitude,
        "hourly": "precipitation,weather_code,wind_gusts_10m", "models": ",".join(MODELS),
        "forecast_hours": max(1, min(int(hours), 72)), "timezone": "auto", "wind_speed_unit": "kmh",
    }, "Open-Meteo models")
    hourly = data.get("hourly", {})  # type: ignore[union-attr]
    count = len(hourly.get("time", []))
    runs: list[ModelRun] = []
    rain_series: list[list[float | None]] = []
    for key, name in MODELS.items():
        rain = hourly.get(f"precipitation_{key}") or []
        if not any(v is not None for v in rain):
            continue  # this model does not cover the location
        codes = hourly.get(f"weather_code_{key}") or [None] * count
        gusts = hourly.get(f"wind_gusts_10m_{key}") or [None] * count
        rain_series.append(rain)
        valid_gusts = [g for g in gusts if g is not None]
        runs.append(ModelRun(
            model=name,
            total_mm=sum(v for v in rain if v is not None),
            rain_hours=sum(1 for v in rain if v is not None and v >= RAIN_MM),
            storm_hours=sum(1 for c in codes if c is not None and int(c) in THUNDERSTORM_CODES),
            max_gust_kmh=max(valid_gusts, default=0.0),
            strong_gust_hours=sum(1 for g in valid_gusts if g >= GUST_STRONG),
        ))
    if not runs:
        raise WeatherError("No forecast model covers this location.")
    votes = [[series[i] >= RAIN_MM for series in rain_series if i < len(series) and series[i] is not None]
             for i in range(count)]
    return ModelComparison(hours=count, runs=runs, agreement=hourly_agreement(votes))


def official_alerts(location: Location) -> AlertResult:
    """Active official warnings. Free keyless feed integrated: US National Weather Service."""
    if location.country_code.upper() != "US":
        return AlertResult(False, f"no free official alert feed is integrated for {location.country or 'this country'}")
    data = http_get(NWS_ALERTS_URL, {"point": f"{location.latitude:.4f},{location.longitude:.4f}"}, "NWS alerts")
    alerts = []
    for feature in data.get("features", []):  # type: ignore[union-attr]
        p = feature.get("properties", {})
        alerts.append(Alert(
            event=p.get("event", "Alert"), severity=p.get("severity", "Unknown"),
            headline=p.get("headline") or "", onset=p.get("onset") or p.get("effective") or "",
            expires=p.get("expires") or p.get("ends") or "", area=p.get("areaDesc") or "",
        ))
    return AlertResult(True, "US National Weather Service", alerts)


def radar_tile_url() -> str | None:
    """Latest RainViewer radar tile template, or None when radar is unavailable."""
    try:
        data = http_get(RAINVIEWER_URL, {}, "RainViewer radar")
        frames = data.get("radar", {}).get("past", [])  # type: ignore[union-attr]
        if not frames:
            return None
        return f"{data['host']}{frames[-1]['path']}/256/{{z}}/{{x}}/{{y}}/2/1_1.png"  # type: ignore[index]
    except (WeatherError, KeyError, TypeError):
        return None
