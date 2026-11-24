from weather_agent import store


def test_report_round_trip_search_and_delete():
    report_id = store.save_report("Karachi · Storm", "storm?", "answer", "Karachi", "High", "m", b"%PDF-1")
    assert store.report_pdf(report_id) == b"%PDF-1"
    assert [r["id"] for r in store.list_reports("karachi")] == [report_id]
    assert store.list_reports("london") == []
    assert store.report_counts() == {"Weather & Storm Analysis": 1}
    store.delete_report(report_id)
    assert store.report_pdf(report_id) is None


def test_search_treats_sql_characters_as_text():
    store.save_report("a", "q", "x", "Lahore", "Low", "m", b"1")
    assert store.list_reports("' OR 1=1 --") == []


def test_usage_stats_count_runs_and_api_calls():
    store.log_run("q", "storm", "m", "ok", 1000, 3, 100, 50)
    store.log_run("q", "storm", "m", "error", 500, 0, 0, 0, "Boom")
    store.log_api_call("Open-Meteo forecast", True, 200)
    store.log_api_call("Open-Meteo forecast", False, 900)
    stats = store.usage_stats()
    assert (stats["runs"], stats["ok"], stats["input_tokens"], stats["api_calls"], stats["api_failed"]) == (2, 1, 100, 2, 1)
    assert store.api_usage_by_service()[0]["calls"] == 2
    assert len(store.recent_runs()) == 2
