"""Key findings for a place: parse the agent's answer, or derive them from live data."""

import re
from dataclasses import dataclass

from weather_agent.quakes import QuakeReport
from weather_agent.sources import AlertResult, ModelComparison
from weather_agent.weather import WeatherReport

BULLET = re.compile(r"^\s*[-*]\s*\*\*(.+?):?\*\*:?\s*(.+)$")
REQUIRED = ("Weather", "Rain Chance", "Storm Risk", "Earthquakes", "Impact", "Recommendation")


@dataclass
class ParsedAnswer:
    intro: str
    bullets: list[tuple[str, str]]
    details: str


def parse_answer(answer: str) -> ParsedAnswer:
    """Split the agent's answer into its intro line, '## Analysis' bullets and the rest."""
    lines = answer.strip().splitlines()
    intro = next((l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")), "")
    bullets = [(m.group(1).strip(), m.group(2).strip()) for l in lines if (m := BULLET.match(l))]
    bullets = [b for b in bullets if b[0] in REQUIRED] or bullets[:6]
    details = answer.split("## Details", 1)[1].strip() if "## Details" in answer else answer
    return ParsedAnswer(intro, bullets, details)


def data_bullets(report: WeatherReport, comparison: ModelComparison | None, alerts: AlertResult | None,
                 quakes: QuakeReport | None) -> list[tuple[str, str]]:
    """Rule-based bullets from live data, used when there is no agent answer (or it skipped some)."""
    c = report.current
    rainy = report.rain_hours
    peak = max(report.hours, key=lambda h: h.rain_probability)
    storms = report.storm_hours
    risk = report.overall_risk
    official = "no official feed for this country (model-based)" if not alerts or not alerts.covered else (
        f"official: {alerts.alerts[0].event}" if alerts.alerts else "no official warnings active")
    conf = f", confidence {comparison.confidence.lower()}" if comparison else ""
    if quakes is None:
        quake_text = "data unavailable."
    elif quakes.strongest is None:
        quake_text = f"no M2.5+ events within {quakes.radius_km} km in {quakes.days} days."
    else:
        q = quakes.strongest
        quake_text = f"{len(quakes.events)} event(s); strongest M{q.magnitude:.1f}, {q.distance_km:.0f} km away ({q.time} UTC)."
    impact = {"Low": "Minimal disruption expected.", "Moderate": "Minor; showers may cause brief waterlogging.",
              "High": "Travel disruption and local flooding possible.", "Severe": "Dangerous conditions; damage possible."}[risk]
    advice = {"Low": "Normal plans are fine; stay updated.",
              "Moderate": "Keep an umbrella and plan travel with caution.",
              "High": "Avoid unnecessary travel during storm hours and secure loose objects.",
              "Severe": "Stay indoors during peak hours and follow official guidance."}[risk]
    return [
        ("Weather", f"{c['condition']}, {c.get('temperature_2m')}°C (feels {c.get('apparent_temperature')}°C), "
                    f"humidity {c.get('relative_humidity_2m')}%."),
        ("Rain Chance", f"~{peak.rain_probability}% peak around {peak.time[11:16]}; rain likely in {len(rainy)} of the next "
                        f"{len(report.hours)} hours."),
        ("Storm Risk", f"{risk}{conf}; {len(storms)} high-risk hour(s); {official}."),
        ("Earthquakes", quake_text),
        ("Impact", impact),
        ("Recommendation", advice),
    ]


def findings(report: WeatherReport, answer: str = "") -> list[tuple[str, str]]:
    """The six compulsory findings: the agent's wording where given, live data for the rest."""
    given = dict(parse_answer(answer).bullets) if answer else {}
    fallback = data_bullets(report, report.comparison, report.alerts, report.quakes)  # type: ignore[arg-type]
    return [(k, given.get(k, v)) for k, v in fallback]
