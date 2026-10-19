"""The suite cannot connect to Tavily or reserve live credits."""

import pytest


@pytest.fixture(autouse=True)
def frozen_live(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_MODE", "frozen")
    monkeypatch.setenv("LIVE_LEDGER", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setenv("LIVE_CACHE", str(tmp_path / "cache"))
    from src.live_mcp import LiveGateway
    async def forbidden(*args, **kwargs):
        pytest.fail("Tests cannot connect to Tavily")
    monkeypatch.setattr(LiveGateway, "_session", forbidden)
    monkeypatch.setattr(LiveGateway, "tavily_usage", forbidden)
