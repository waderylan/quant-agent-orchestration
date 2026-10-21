"""Shared local provider rate pacing and recorded usage; never blocks spending."""
from __future__ import annotations

import asyncio
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

MICRO = Decimal(1000000)


class LimitError(RuntimeError):
    pass


class ProviderLedger:
    """Credit limits are operating instructions in AGENTS.md, not code stops."""

    def __init__(self, path=None, *, clock=time.time):
        self.path = Path(path or os.getenv("PROVIDER_LEDGER", "artifacts/providers/usage.sqlite3"))
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS usage(id TEXT PRIMARY KEY, at REAL NOT NULL, provider TEXT NOT NULL,
                    model TEXT NOT NULL, request_id TEXT, cost_micros INTEGER);
                CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, provider TEXT, at REAL, until REAL);
            """)

    @contextmanager
    def db(self):
        with sqlite3.connect(self.path, timeout=10) as db:
            yield db

    def record(self, provider, model, request_id, cost):
        """Record a completed call; unknown cost stays null."""
        try:
            with self.db() as db:
                db.execute("INSERT INTO usage VALUES (?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, self.clock(), provider, model,
                           request_id, None if cost is None else int(Decimal(cost) * MICRO)))
        except sqlite3.Error:
            pass  # Usage visibility must not interrupt generation.

    def try_permit(self, provider, *, lease=240):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self.clock()
            db.execute("DELETE FROM calls WHERE at<? AND until<?", (now-60, now))
            count = db.execute("SELECT COUNT(*) FROM calls WHERE provider=? AND at>?", (provider, now-60)).fetchone()[0]
            active = db.execute("SELECT COUNT(*) FROM calls WHERE provider=? AND until>?", (provider, now)).fetchone()[0]
            # NVIDIA allows 40 requests/minute; pacing avoids 429s rather than limiting spend.
            if provider == "nvidia" and (active >= 2 or count >= 40):
                return None
            identity = uuid.uuid4().hex
            db.execute("INSERT INTO calls VALUES (?, ?, ?, ?)", (identity, provider, now, now+lease))
            return identity

    async def permit(self, provider, *, lease=240):
        while True:
            identity = self.try_permit(provider, lease=lease)
            if identity:
                return identity
            await asyncio.sleep(0.25)

    def release(self, identity):
        with self.db() as db:
            db.execute("UPDATE calls SET until=0 WHERE id=?", (identity,))

    def status(self):
        with self.db() as db:
            rows = db.execute("SELECT provider, COUNT(*), COALESCE(SUM(cost_micros),0), SUM(cost_micros IS NULL) "
                              "FROM usage GROUP BY provider").fetchall()
        return {provider: {"calls": calls, "estimated_usd": str(Decimal(cost)/MICRO), "unknown_cost_calls": unknown}
                for provider, calls, cost, unknown in rows}
