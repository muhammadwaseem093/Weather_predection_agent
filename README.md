# Zentro AI — Weather Analysis & Storm Prediction Agent

An AI weather agent built with **LangChain Deep Agents** and **Streamlit**. It answers
natural-language weather questions for any city or country, predicts storms and rain for the
coming hours, explains risks and forecast confidence, and writes news-ready PDF reports that
are stored and downloadable from the web app.

## Features

| Area | What you get |
|---|---|
| Four compulsory sections | Every weather answer covers **Weather** (up-to-date), **Rain**, **Storms** and **Earthquakes** (USGS), shown as a visual card grid with an AI Analysis & Recommendation card and PDF |
| AI agent | Deep agent that plans (`write_todos`) and delegates to a `storm-analyst` sub-agent; follow-up questions; hourly, daily and weekly forecasts; confidence and evidence in every answer |
| Live monitoring | Search any city worldwide; temperature, humidity, wind, rainfall, pressure, cloud; map with live radar; auto-refresh (5–30 min) |
| Storm & rain prediction | Last 12 h observed + next 1–72 h forecast; rain probability and intensity (WMO classes); thunderstorm, heavy-rain and damaging-wind detection |
| Multiple sources | ECMWF, NOAA GFS and DWD ICON compared; their agreement gives High/Medium/Low confidence |
| Official vs model-based | Verified warnings from the US National Weather Service, always shown apart from the model-based risk score; other countries are clearly marked "model-based only" |
| Reports | News headline and structured article; PDF with statistics, bar, pie and daily charts, hour-by-hour and 7-day tables, timestamps and sources; saved to the database |
| Web app | Weather Chat, Live Weather, Storm Tracker, Rain Forecast, Global Weather, Analysis Reports, Saved Reports, password-protected Admin; quick locations, notifications, Export PDF |

## How the risk score works

Each forecast hour is rated **Low / Moderate / High / Severe** from: WMO thunderstorm codes
(95/96/99), CAPE instability (≥1000 / ≥2500 J/kg with rain likely), wind gusts (≥60 / ≥90 km/h),
rain rate (≥7.6 mm/h heavy) and rain probability (≥50 %). This is a model-based estimate, not an
official warning.

## Project layout

```
streamlit_app.py          entry point: navigation, theme, settings
app_pages/                chat, live, storm, rain, global_weather, reports, saved, admin
ui/                       layout (sidebar, top bar), cards (weather grid), analysis card, place view, widgets
weather_agent/
  agent.py                deep agent, tools, streaming trace, token tracking
  weather.py              Open-Meteo: geocoding, live, history, hourly/daily, risk scoring
  sources.py              multi-model comparison, NWS alerts, RainViewer radar
  quakes.py               USGS earthquakes near a place
  storms.py               active tropical cyclones and tracks (GDACS)
  world.py                live worldwide grid for the Global Weather heat map
  insights.py             the six key findings (Weather, Rain, Storms, Earthquakes, Impact, Recommendation)
  report.py, charts.py    PDF report and its charts
  store.py                SQLite: reports, agent runs, API usage
tests/                    unit tests (pytest)
```

## Run locally

```bash
uv sync
copy .env.example .env          # set GOOGLE_API_KEY (and ADMIN_PASSWORD for the admin page)
uv run streamlit run streamlit_app.py
uv run pytest                   # tests
```

Without uv: `python -m venv .venv`, activate it, `pip install -r requirements.txt`,
`streamlit run streamlit_app.py`. Get a Gemini key at https://aistudio.google.com/apikey.

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. On https://share.streamlit.io choose **Create app → From GitHub**, pick the repo, branch
   `main`, main file `streamlit_app.py`.
3. **Advanced settings → Secrets**:
   ```toml
   GOOGLE_API_KEY = "your-key"
   ADMIN_PASSWORD = "a-strong-password"
   # MODEL = "google_genai:gemini-3.1-flash-lite"
   ```
4. Deploy.

**Storage note:** reports are stored in SQLite (`data/stormsight.db`). On Streamlit Community
Cloud that file survives across sessions but is reset when the app is redeployed or rebuilt.
Set `STORMSIGHT_DB` to a persistent path when self-hosting.

## Data sources

Open-Meteo (forecasts, models, geocoding, world grid) · USGS (earthquakes) · GDACS (tropical cyclones) · US National Weather Service
(official alerts) · RainViewer (radar) · Esri World Imagery (satellite map). All free and keyless.
