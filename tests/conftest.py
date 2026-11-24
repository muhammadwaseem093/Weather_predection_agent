import pytest


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own SQLite file; never touch the app's real data."""
    monkeypatch.setenv("STORMSIGHT_DB", str(tmp_path / "test.db"))
