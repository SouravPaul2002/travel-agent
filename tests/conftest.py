"""Shared pytest fixtures."""

import pytest
from app.config import settings
from app.tools._http import init_cache_db


@pytest.fixture(autouse=True)
def isolate_test_cache(tmp_path, monkeypatch):
    """Ensure every test runs with an isolated temporary SQLite cache."""
    test_db = str(tmp_path / "pytest_cache.db")
    init_cache_db(test_db)
    monkeypatch.setattr(settings, "cache_db_path", test_db)
    yield test_db
