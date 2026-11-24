"""SQLite store for saved reports, agent runs and weather-API usage.

On Streamlit Community Cloud the file lives on the app's disk: it survives
reruns and sessions but is reset when the app is rebuilt or redeployed. Set
STORMSIGHT_DB to point somewhere persistent when self-hosting.
"""

import logging
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "stormsight.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    title TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    places TEXT NOT NULL,
    overall_risk TEXT NOT NULL,
    model TEXT NOT NULL,
    pdf BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    question TEXT NOT NULL,
    mode TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    duration_ms INTEGER NOT NULL,
    tool_calls INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    error TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    service TEXT NOT NULL,
    ok INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at);
CREATE INDEX IF NOT EXISTS idx_api_calls_created ON api_calls(created_at);
"""


def db_path() -> Path:
    return Path(os.getenv("STORMSIGHT_DB") or DEFAULT_PATH)


@cache
def _ensure_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(reports)")}
        if "saved" not in columns:  # added after the first release
            conn.execute("ALTER TABLE reports ADD COLUMN saved INTEGER NOT NULL DEFAULT 0")
        if "report_type" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN report_type TEXT NOT NULL DEFAULT 'Weather & Storm Analysis'")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = db_path()
    _ensure_schema(path)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_api_call(service: str, ok: bool, duration_ms: int) -> None:
    # Usage logging must never break a weather lookup.
    try:
        with connect() as conn:
            conn.execute("INSERT INTO api_calls (service, ok, duration_ms) VALUES (?, ?, ?)", (service, int(ok), duration_ms))
    except sqlite3.Error as error:
        logger.warning("Could not log API call: %s", error)


def log_run(question: str, mode: str, model: str, status: str, duration_ms: int,
            tool_calls: int, input_tokens: int, output_tokens: int, error: str = "") -> None:
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO agent_runs (question, mode, model, status, duration_ms, tool_calls, input_tokens, "
                "output_tokens, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (question, mode, model, status, duration_ms, tool_calls, input_tokens, output_tokens, error),
            )
    except sqlite3.Error as error_:
        logger.warning("Could not log agent run: %s", error_)


REPORT_TYPES = ("Weather & Storm Analysis", "Weather Update", "Storm Analysis", "Rain Forecast", "Earthquake Report")


def save_report(title: str, question: str, answer: str, places: str, overall_risk: str, model: str, pdf: bytes,
                report_type: str = REPORT_TYPES[0]) -> int:
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO reports (title, question, answer, places, overall_risk, model, pdf, report_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, question, answer, places, overall_risk, model, pdf, report_type),
        )
        return int(cursor.lastrowid or 0)


def list_reports(search: str = "", limit: int = 200, report_type: str = "") -> list[dict]:
    pattern = f"%{search.strip()}%"
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, title, question, answer, places, overall_risk, model, report_type, "
            "length(pdf) AS size FROM reports WHERE (title LIKE ? OR question LIKE ? OR places LIKE ?) "
            "AND (report_type = ? OR ? = '') ORDER BY id DESC LIMIT ?",
            (pattern, pattern, pattern, report_type, report_type, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def report_pdf(report_id: int) -> bytes | None:
    with connect() as conn:
        row = conn.execute("SELECT pdf FROM reports WHERE id = ?", (report_id,)).fetchone()
    return bytes(row["pdf"]) if row else None


def report_counts() -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute("SELECT report_type, count(*) AS n FROM reports GROUP BY report_type").fetchall()
    return {r["report_type"]: r["n"] for r in rows}


def delete_report(report_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))


def usage_stats() -> dict:
    with connect() as conn:
        runs = conn.execute(
            "SELECT count(*) AS runs, coalesce(sum(status = 'ok'), 0) AS ok, coalesce(avg(duration_ms), 0) AS avg_ms, "
            "coalesce(sum(input_tokens), 0) AS input_tokens, coalesce(sum(output_tokens), 0) AS output_tokens, "
            "coalesce(sum(tool_calls), 0) AS tool_calls FROM agent_runs"
        ).fetchone()
        api = conn.execute("SELECT count(*) AS calls, coalesce(sum(ok = 0), 0) AS failed FROM api_calls").fetchone()
        reports = conn.execute("SELECT count(*) AS n, coalesce(sum(length(pdf)), 0) AS bytes FROM reports").fetchone()
    return {**dict(runs), "api_calls": api["calls"], "api_failed": api["failed"],
            "reports": reports["n"], "report_bytes": reports["bytes"]}


def api_usage_by_service() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT service, count(*) AS calls, sum(ok = 0) AS failed, round(avg(duration_ms)) AS avg_ms "
            "FROM api_calls GROUP BY service ORDER BY calls DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def api_usage_by_day(days: int = 14) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT date(created_at) AS day, service, count(*) AS calls FROM api_calls "
            "WHERE created_at >= datetime('now', ?) GROUP BY day, service ORDER BY day",
            (f"-{int(days)} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def recent_runs(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT created_at, question, mode, model, status, duration_ms, tool_calls, input_tokens, "
            "output_tokens, error FROM agent_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
