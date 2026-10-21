"""Shared local rate permits and conservative, durable promotional reservations."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

CUTOFF = datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp()
MICRO = Decimal(1000000)


class LimitError(RuntimeError):
    pass


def micros(value):
    return int((Decimal(str(value)) * MICRO).to_integral_value(rounding=ROUND_CEILING))


class ProviderLedger:
    def __init__(self, path=None, *, clock=time.time):
        if os.getenv("K_SERVICE"):
            raise LimitError("Cloud Run requires verified global provider accounting; local ledger acquisition is disabled")
        self.path = Path(path or os.getenv("PROVIDER_LEDGER", "artifacts/providers/usage.sqlite3"))
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY, amount INTEGER NOT NULL,
                    actual INTEGER, at REAL NOT NULL, model TEXT NOT NULL, outcome TEXT NOT NULL, request_id TEXT);
                CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, provider TEXT, at REAL, until REAL);
            """)
            if "request_id" not in {r[1] for r in db.execute("PRAGMA table_info(reservations)")}:
                db.execute("ALTER TABLE reservations ADD COLUMN request_id TEXT")

    @contextmanager
    def db(self):
        try:
            with sqlite3.connect(self.path, timeout=10) as db:
                yield db
        except sqlite3.Error:
            raise LimitError("Provider ledger unavailable; acquisition blocked") from None

    def initialize(self, *, balance, observed_at, expires_at=CUTOFF, prior_reserved="0", exclusive=False):
        """Record a user-verified baseline once; never reset existing consumption."""
        if not exclusive or not 0 < Decimal(str(balance)) <= 100:
            raise LimitError("Verified balance and exclusive tracked account use are required")
        if not self.clock() - 86400 <= observed_at <= self.clock() + 60:
            raise LimitError("Balance observation must be current")
        if not self.clock() < expires_at <= CUTOFF:
            raise LimitError("Promo expiry/cutoff is invalid")
        if not 0 <= Decimal(str(prior_reserved)) < Decimal(str(balance)):
            raise LimitError("Prior reservation must fit within verified credit")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM settings WHERE key='baseline'").fetchone():
                raise LimitError("Baseline already exists; consumption cannot be reset")
            data = {"balance": micros(balance), "observed_at": observed_at, "expires_at": expires_at,
                    "prior_reserved": micros(prior_reserved), "exclusive": exclusive}
            db.execute("INSERT INTO settings VALUES ('baseline', ?)", (json.dumps(data),))

    def _baseline(self, db):
        if db.execute("SELECT 1 FROM settings WHERE key='blocked'").fetchone():
            raise LimitError("Nebius accounting is blocked; reconcile before acquisition")
        row = db.execute("SELECT value FROM settings WHERE key='baseline'").fetchone()
        if not row:
            raise LimitError("Nebius baseline missing; acquisition blocked")
        baseline = json.loads(row[0])
        if self.clock() >= min(CUTOFF, baseline["expires_at"]):
            raise LimitError("Nebius promo cutoff reached")
        if self.clock() - baseline["observed_at"] > 86400:
            raise LimitError("Nebius balance verification is stale; reconcile account usage")
        return baseline

    def refresh(self, *, balance, observed_at, exclusive=False):
        """Refresh a dashboard observation without restoring any spent allowance."""
        if not exclusive or not 0 <= Decimal(str(balance)) <= 100:
            raise LimitError("Verified remaining credit and exclusive tracked use are required")
        if not self.clock() - 86400 <= observed_at <= self.clock() + 60:
            raise LimitError("Balance observation must be current")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM settings WHERE key='baseline'").fetchone()
            if not row:
                raise LimitError("Initialize the verified baseline first")
            baseline = json.loads(row[0])
            if observed_at < baseline["observed_at"]:
                raise LimitError("Balance observation predates the existing verification")
            used, uncertain = db.execute("SELECT COALESCE(SUM(COALESCE(actual, amount)),0), "
                                        "COALESCE(SUM(CASE WHEN actual IS NULL THEN amount ELSE 0 END),0) "
                                        "FROM reservations").fetchone()
            original = min(baseline["balance"] - micros(10), micros(90)) - baseline["prior_reserved"]
            # Unsettled calls and pre-ledger reservations can still be charged later.
            remaining_cap = used + micros(balance) - micros(10) - uncertain - baseline["prior_reserved"]
            baseline.update(observed_at=observed_at, verified_remaining=micros(balance),
                            credit_ceiling=min(original, baseline.get("credit_ceiling", original), remaining_cap))
            db.execute("UPDATE settings SET value=? WHERE key='baseline'", (json.dumps(baseline),))

    def reserve(self, amount, model, request_id="direct"):
        amount = micros(amount)
        if amount <= 0:
            raise LimitError("Unknown request cost; acquisition blocked")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            baseline = self._baseline(db)
            used = db.execute("SELECT COALESCE(SUM(COALESCE(actual, amount)),0) FROM reservations").fetchone()[0]
            request_used = db.execute("SELECT COALESCE(SUM(COALESCE(actual, amount)),0) FROM reservations WHERE request_id=?", (request_id,)).fetchone()[0]
            # The campaign ceiling is an application stop, not an authorization to pay.
            campaign = min(micros(os.getenv("NEBIUS_CAMPAIGN_USD", "5")), micros(5))
            allowance = min(baseline["balance"] - micros(10), micros(90)) - baseline["prior_reserved"]
            allowance = min(allowance, baseline.get("credit_ceiling", allowance))
            if used + amount > min(campaign, allowance) or request_used + amount > micros(1):
                raise LimitError("Nebius promotional spending stop reached")
            identity = uuid.uuid4().hex
            db.execute("INSERT INTO reservations VALUES (?, ?, NULL, ?, ?, 'reserved', ?)",
                       (identity, amount, self.clock(), model, request_id))
            return identity

    def settle(self, identity, actual, outcome):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT amount, actual FROM reservations WHERE id=?", (identity,)).fetchone()
            if not row or row[1] is not None:
                raise LimitError("Invalid or duplicate spending settlement")
            value = micros(actual)
            if value < 0 or value > row[0]:
                # Freeze all subsequent Nebius acquisition on an invalid cost bound.
                db.execute("INSERT OR REPLACE INTO settings VALUES ('blocked', 'cost bound violated')")
                db.commit()
                raise LimitError("Provider usage exceeds reserved bound; Nebius disabled")
            db.execute("UPDATE reservations SET actual=?, outcome=? WHERE id=?", (value, outcome, identity))

    def authorize(self, identity):
        """Recheck freshness and cutoff after queueing, before the outbound request."""
        with self.db() as db:
            self._baseline(db)
            row = db.execute("SELECT actual FROM reservations WHERE id=?", (identity,)).fetchone()
            if row is None or row[0] is not None:
                raise LimitError("No outstanding reservation authorizes this request")

    def try_permit(self, provider, *, lease=240):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self.clock()
            db.execute("DELETE FROM calls WHERE at<? AND until<?", (now-60, now))
            count = db.execute("SELECT COUNT(*) FROM calls WHERE provider=? AND at>?", (provider, now-60)).fetchone()[0]
            active = db.execute("SELECT COUNT(*) FROM calls WHERE provider=? AND until>?", (provider, now)).fetchone()[0]
            if active >= 2 or (provider == "nvidia" and count >= 40):
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
            row = db.execute("SELECT value FROM settings WHERE key='baseline'").fetchone()
            used = db.execute("SELECT COALESCE(SUM(COALESCE(actual, amount)),0) FROM reservations").fetchone()[0]
            uncertain = db.execute("SELECT COUNT(*) FROM reservations WHERE actual IS NULL").fetchone()[0]
            return {"baseline": json.loads(row[0]) if row else None,
                    "accounted_usd": str(Decimal(used)/MICRO), "unsettled": uncertain,
                    "reservations": db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]}
