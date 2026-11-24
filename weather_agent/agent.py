"""The Weather Analysis & Storm Prediction deep agent (LangChain deepagents).

The lead agent plans with write_todos, answers live/daily questions itself and
delegates storm & rain prediction to a storm-analyst sub-agent. Tools are built
per run so every lookup is recorded for that answer's PDF report and usage log.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool

from weather_agent import quakes, sources, weather

DEFAULT_MODEL = "google_genai:gemini-3.1-flash-lite"
TRACE_DETAIL_CHARS = 600

LEAD_PROMPT = """You are Zentro AI, a weather analysis and storm prediction agent. Today is {today}.
You understand natural-language weather questions about any city or country in the world.

COMPULSORY: for every weather-related question about a place, cover all four:
1. Weather - up-to-date conditions (get_live_weather) and the daily outlook (get_daily_forecast).
2. Rain - chance, timing and intensity in the coming hours (storm-analyst).
3. Storms - thunderstorm / severe wind risk with confidence and official warnings (storm-analyst).
4. Earthquakes - recent seismic activity nearby (get_earthquakes). Earthquakes cannot be forecast;
   report recent observed activity only.

How you work:
- Plan multi-step requests with write_todos.
- Delegate storm and rain prediction to the storm-analyst sub-agent with the task tool, naming the
  place and hours (default 24, max 72).
- For a country, choose 3-5 major cities spread across it.
- Use earlier messages to resolve follow-ups ("what about tomorrow?", "and Karachi?").
- Never invent data. If a lookup fails, say so.
- Keep MODEL-BASED risk separate from OFFICIAL verified warnings; when no official feed covers the
  place, say the storm risk is a model-based estimate.
- Times are the place's local time.

ANSWER FORMAT (markdown, follow exactly):
First line: one friendly sentence saying what you analysed (no heading).

## Analysis
- **Weather:** ...
- **Rain Chance:** ...
- **Storm Risk:** ... (level, confidence, official warnings or "model-based")
- **Earthquakes:** ...
- **Impact:** ...
- **Recommendation:** ...

## Details
A news-ready write-up: for a news/report request start this section with a headline (### ...)
and a structured article; otherwise give the key numbers and evidence. End with a short Sources line."""

STORM_PROMPT = """You are the storm analyst. For the requested place and window:
1. predict_storms_and_rain - hourly model-based risk, rain probability and intensity, recent history.
2. compare_forecast_models - agreement between ECMWF, GFS and ICON = forecast confidence.
3. get_official_alerts - verified warnings from a national weather service, when available.
Report when rain or storms are expected, likelihood, intensity, risk level and the evidence.
Label model-based estimates and official warnings separately. Be short and factual."""


@dataclass
class RunLog:
    """Everything fetched during one agent run, keyed by place label."""

    reports: dict[str, weather.WeatherReport] = field(default_factory=dict)
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def complete(self) -> None:
        """Make sure every place has all four compulsory sections' data, even if the agent skipped a tool."""
        for report in self.reports.values():
            try:
                if report.quakes is None:
                    report.quakes = quakes.recent_quakes(report.location)
                if report.alerts is None:
                    report.alerts = sources.official_alerts(report.location)
                if report.comparison is None:
                    report.comparison = sources.compare_models(report.location, len(report.hours))
            except weather.WeatherError:
                continue  # the card shows the section as unavailable

    def report(self, place: str, hours: int = 24) -> weather.WeatherReport:
        """Fetch (or reuse) the report for a place; a longer window replaces a shorter one."""
        for existing in self.reports.values():
            if place.lower() in (existing.location.name.lower(), existing.location.label.lower()) and len(existing.hours) >= hours:
                return existing
        fresh = weather.fetch_report(place, hours=hours)
        old = self.reports.get(fresh.location.label)
        if old:
            fresh.comparison, fresh.alerts, fresh.quakes = old.comparison, old.alerts, old.quakes
        self.reports[fresh.location.label] = fresh
        return fresh


def build_tools(log: RunLog):
    @tool
    def get_live_weather(place: str) -> str:
        """Live current weather for any city worldwide, plus the last 12 hours of observations."""
        try:
            report = log.report(place)
        except weather.WeatherError as error:
            return str(error)
        return weather.current_summary(report) + "\n" + weather.history_summary(report)

    @tool
    def get_daily_forecast(place: str, days: int = 7) -> str:
        """Daily forecast for 1-16 days (use 7 for a weekly outlook)."""
        try:
            report = log.report(place)
            if days != len(report.days):
                report.days = weather.fetch_report(report.location, hours=1, days=days).days
        except weather.WeatherError as error:
            return str(error)
        return weather.daily_summary(report)

    @tool
    def predict_storms_and_rain(place: str, hours: int = 24) -> str:
        """Model-based hourly storm/rain prediction for the next `hours` hours (1-72), with recent history."""
        try:
            report = log.report(place, hours=hours)
        except weather.WeatherError as error:
            return str(error)
        return weather.current_summary(report) + "\n\n" + weather.prediction_summary(report)

    @tool
    def compare_forecast_models(place: str, hours: int = 24) -> str:
        """Compare ECMWF, NOAA GFS and DWD ICON forecasts to estimate forecast confidence."""
        try:
            report = log.report(place, hours=hours)
            report.comparison = sources.compare_models(report.location, hours)
        except weather.WeatherError as error:
            return str(error)
        return report.comparison.summary()

    @tool
    def get_official_alerts(place: str) -> str:
        """Active official (verified) severe-weather warnings from a national weather service."""
        try:
            report = log.report(place)
            report.alerts = sources.official_alerts(report.location)
        except weather.WeatherError as error:
            return str(error)
        return report.alerts.summary()

    @tool
    def get_earthquakes(place: str) -> str:
        """Recent earthquakes (USGS) within 500 km of a place over the last 7 days."""
        try:
            report = log.report(place)
            report.quakes = quakes.recent_quakes(report.location)
        except weather.WeatherError as error:
            return str(error)
        return report.quakes.summary(report.location.label)

    return {
        "lead": [get_live_weather, get_daily_forecast, get_earthquakes],
        "storm": [predict_storms_and_rain, compare_forecast_models, get_official_alerts],
    }


def build_agent(api_key: str, model: str, log: RunLog):
    tools = build_tools(log)
    return create_deep_agent(
        model=init_chat_model(model, api_key=api_key),
        tools=tools["lead"],
        system_prompt=LEAD_PROMPT.format(today=date.today().isoformat()),
        subagents=[{
            "name": "storm-analyst",
            "description": "Predicts storms, rain and severe weather for a place over the coming hours, "
                           "with forecast confidence and official warnings. Name the place and hours.",
            "system_prompt": STORM_PROMPT,
            "tools": tools["storm"],
        }],
    )


@dataclass
class Step:
    """One visible step of the agent's work, shown in the trace."""

    kind: str  # "tool" | "result"
    title: str
    detail: str = ""


def _describe_call(call: dict, by_subagent: bool) -> Step:
    args = call.get("args", {})
    who = "storm-analyst → " if by_subagent else ""
    if call["name"] == "task":
        return Step("tool", f"Delegating to {args.get('subagent_type', 'sub-agent')}", args.get("description", ""))
    if call["name"] == "write_todos":
        return Step("tool", "Planning", "\n".join(f"- {t.get('content', '')}" for t in args.get("todos", [])))
    return Step("tool", f"{who}{call['name']}", ", ".join(f"{k}={v}" for k, v in args.items()))


def run(agent, history: list[dict], log: RunLog) -> Iterator[Step | str]:
    """Stream the agent (including sub-agents): yields Steps while it works, then the final answer."""
    final = ""
    for namespace, update in agent.stream({"messages": history}, stream_mode="updates", subgraphs=True):
        in_subagent = bool(namespace)
        for node in update.values():
            if not isinstance(node, dict):
                continue
            for message in node.get("messages", []) or []:
                kind = getattr(message, "type", "")
                if kind == "ai":
                    usage = getattr(message, "usage_metadata", None) or {}
                    log.input_tokens += usage.get("input_tokens", 0)
                    log.output_tokens += usage.get("output_tokens", 0)
                    calls = getattr(message, "tool_calls", None) or []
                    log.tool_calls += len(calls)
                    for call in calls:
                        yield _describe_call(call, in_subagent)
                    if not calls and not in_subagent:
                        final = message.text if isinstance(message.text, str) else str(message.content)
                elif kind == "tool" and not in_subagent:
                    yield Step("result", f"Result from {message.name}", str(message.content)[:TRACE_DETAIL_CHARS])
    yield final
