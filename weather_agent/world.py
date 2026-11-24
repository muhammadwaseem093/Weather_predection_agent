"""Live worldwide weather grid (one Open-Meteo call) for the Global Weather heat map."""

from dataclasses import dataclass

from weather_agent.weather import FORECAST_URL, WeatherError, http_get

GRID_STEP_DEG = 10
LAT_RANGE = (-60, 71)  # skip Antarctica; covers inhabited latitudes
LAYERS = {
    "temperature": "temperature_2m",
    "precipitation": "precipitation",
    "wind": "wind_speed_10m",
    "clouds": "cloud_cover",
    "pressure": "pressure_msl",
}


@dataclass
class GridCell:
    latitude: float
    longitude: float
    values: dict[str, float]


def grid_points() -> list[tuple[int, int]]:
    return [(lat, lon) for lat in range(LAT_RANGE[0], LAT_RANGE[1], GRID_STEP_DEG)
            for lon in range(-180, 180, GRID_STEP_DEG)]


def world_grid() -> list[GridCell]:
    points = grid_points()
    data = http_get(FORECAST_URL, {
        "latitude": ",".join(str(lat) for lat, _ in points),
        "longitude": ",".join(str(lon) for _, lon in points),
        "current": ",".join(LAYERS.values()), "wind_speed_unit": "kmh",
    }, "Open-Meteo world grid")
    if not isinstance(data, list) or len(data) != len(points):
        raise WeatherError("Unexpected world grid response.")
    cells = []
    for (lat, lon), item in zip(points, data):
        current = item.get("current", {})
        cells.append(GridCell(lat, lon, {layer: float(current.get(key) or 0) for layer, key in LAYERS.items()}))
    return cells


def current_at(points: list[tuple[float, float]]) -> list[dict]:
    """Current temperature and weather code for many places in one call."""
    if not points:
        return []
    data = http_get(FORECAST_URL, {
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
        "current": "temperature_2m,weather_code,is_day",
    }, "Open-Meteo world grid")
    items = data if isinstance(data, list) else [data]
    return [item.get("current", {}) for item in items]
