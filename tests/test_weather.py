from weather_agent.report import build_pdf
from weather_agent.sources import Alert, AlertResult, ModelComparison, ModelRun, hourly_agreement
from weather_agent.weather import DayForecast, HourRisk, Location, WeatherReport, rain_intensity, score_day, score_hour

PLACE = Location("Karachi", "Pakistan", 24.8, 67.0, "Asia/Karachi", "PK", "Sindh")


def hour(time="2026-11-23T18:00", risk="Severe", rain=80, mm=9.0):
    return HourRisk(time, 21.0, rain, mm, 70, 1200, "Thunderstorm", risk, ["thunderstorm"])


def test_clear_hour_is_low_risk():
    assert score_hour(0, 5, 0.0, 15, 50) == ("Low", [])


def test_thunderstorm_with_hail_is_severe():
    risk, reasons = score_hour(96, 80, 3.0, 30, 500)
    assert risk == "Severe" and "Thunderstorm with hail" in reasons


def test_unstable_wet_air_is_high_but_dry_instability_is_not():
    assert score_hour(3, 70, 1.0, 20, 1500)[0] == "High"
    assert score_hour(1, 10, 0.0, 20, 3000)[0] == "Low"


def test_likely_rain_is_moderate_and_strong_gusts_high():
    assert score_hour(61, 60, 1.0, 20, 0)[0] == "Moderate"
    assert score_hour(3, 0, 0.0, 65, 0)[0] == "High"


def test_daily_risk_levels():
    assert score_day(0, 10, 0.0, 20) == "Low"
    assert score_day(61, 70, 5.0, 20) == "Moderate"
    assert score_day(63, 90, 60.0, 30) == "High"
    assert score_day(99, 90, 10.0, 30) == "Severe"


def test_rain_intensity_boundaries():
    assert [rain_intensity(v) for v in (0, 0.1, 2.5, 7.6, 50)] == ["None", "Light", "Moderate", "Heavy", "Violent"]


def test_model_agreement_and_confidence():
    assert hourly_agreement([[True, True, True], [False, False, False]]) == 1.0
    assert round(hourly_agreement([[True, False, False]]), 2) == 0.67
    assert hourly_agreement([]) == 0.0
    run = ModelRun("A", 1.0, 1, 0, 20, 0)
    assert ModelComparison(24, [run, run, run], 0.9).confidence == "High"
    assert ModelComparison(24, [run, run, run], 0.7).confidence == "Medium"
    assert ModelComparison(24, [run], 1.0).confidence == "Low"  # a single model cannot confirm itself


def test_uncovered_country_is_labelled_model_based_only():
    text = AlertResult(False, "no feed for Pakistan").summary()
    assert "model-based" in text and "not a verified warning" in text


def test_full_pdf_with_unicode_alerts_confidence_and_daily():
    report = WeatherReport(
        PLACE, {"condition": "Rain", "temperature_2m": 21, "time": "2026-11-23T18:00"},
        [hour(), hour("2026-11-23T19:00", "Low", 10, 0.0)],
        history=[hour("2026-11-23T10:00", "Low", 0, 0.0)],
        days=[DayForecast("2026-11-23", "Rain", 18, 25, 12.0, 80, 40, "Moderate")],
        fetched_at="2026-11-23 13:00 UTC",
        comparison=ModelComparison(24, [ModelRun("ECMWF", 3.0, 4, 1, 50, 0)], 1.0),
        alerts=AlertResult(True, "NWS", [Alert("Flood Watch", "Severe", "Flooding — likely", "", "tonight", "")]),
    )
    pdf = build_pdf("Storm? ⛈️", "# Headline — storms\n- **Rain** 80% 🌧️", [report])
    assert pdf.startswith(b"%PDF") and len(pdf) > 20_000  # charts embedded


def test_pdf_without_weather_data():
    assert build_pdf("hello", "Just a greeting.", []).startswith(b"%PDF")


def test_quake_distance_and_levels():
    from weather_agent.quakes import Quake, QuakeReport, distance_km
    assert round(distance_km(31.55, 74.34, 24.86, 67.0)) in range(1000, 1060)  # Lahore -> Karachi ~1030 km
    quiet = QuakeReport(500, 7, [])
    assert quiet.level == "None" and "none recorded" in quiet.summary("X")
    strong = QuakeReport(500, 7, [Quake(5.4, "near X", "2026-11-22 10:00", 10, 120, "", False)])
    assert strong.level == "Moderate" and "cannot be predicted" in strong.summary("X")


def test_answer_parsing_and_data_bullets_cover_four_sections():
    from ui.analysis import REQUIRED, data_bullets, parse_answer
    text = "Here is Lahore.\n\n## Analysis\n- **Weather:** Sunny\n- **Rain Chance:** 10%\n\n## Details\n### Headline\nBody"
    parsed = parse_answer(text)
    assert parsed.intro == "Here is Lahore." and dict(parsed.bullets)["Weather"] == "Sunny"
    assert parsed.details.startswith("### Headline")
    report = WeatherReport(PLACE, {"condition": "Clear sky", "temperature_2m": 20, "time": "2026-11-23T10:00"},
                           [hour(), hour("2026-11-23T11:00", "Low", 0, 0.0)])
    assert [k for k, _ in data_bullets(report, None, None, None)] == list(REQUIRED)


def test_card_grid_escapes_external_text():
    from ui.cards import grid_html
    from weather_agent.quakes import Quake, QuakeReport
    evil = Location("<script>x</script>", "Pakistan", 24.8, 67.0, "Asia/Karachi", "PK", "")
    report = WeatherReport(evil, {"condition": "Clear sky", "temperature_2m": 20, "time": "2026-11-23T10:00"},
                           [hour()] * 24, days=[DayForecast("2026-11-23", "Rain", 18, 25, 12.0, 80, 40, "Moderate")])
    quakes = QuakeReport(500, 7, [Quake(4.0, "<img src=x onerror=alert(1)>", "2026-11-22 10:00", 10, 50, "", False)])
    html = grid_html(report, None, None, quakes, None)
    assert "<script>x</script>" not in html and "<img src=x" not in html
