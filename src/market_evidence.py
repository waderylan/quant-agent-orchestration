"""Normalize real MCP schemas without manufacturing accounting or freshness facts."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, ValidationInfo, computed_field


class ValuationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    company: Literal["NVDA", "AMD", "INTC", "QCOM"]
    metric: Literal[
        "price",
        "eps",
        "shares",
        "cash",
        "debt",
        "revenue",
        "ebitda",
        "fcf",
        "multiple",
        "eps_factor",
    ]
    value: str
    currency: str = "unspecified"
    accounting_basis: Literal["GAAP", "adjusted", "assumption", "unspecified"] = (
        "unspecified"
    )
    dilution: str = "unspecified"
    split_basis: str = "unspecified"
    start: str | None = None
    end: str | None = None
    horizon: str | None = None
    as_of: str | None = None
    source_kind: Literal["reported", "consensus", "quote", "user_assumption"]
    source_snapshot: str | None = None
    freshness: Literal["dated", "stale", "unknown"] = "unknown"

    @computed_field
    @property
    def unit(self) -> str:
        if self.metric in ("multiple", "eps_factor"):
            return "multiple"
        if self.metric == "shares":
            return "shares"
        return self.currency + "/share" if self.metric in ("price", "eps") else self.currency

    @field_validator("start", "end", "as_of")
    @classmethod
    def valid_date(cls, value, info: ValidationInfo):
        if value is not None:
            if info.field_name in ("start", "end") and date.fromisoformat(value).isoformat() != value:
                raise ValueError("Fiscal dates require YYYY-MM-DD")
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if len(value) > 10 and parsed.tzinfo is None:
                raise ValueError("Observation timestamps require an explicit timezone")
        return value


def number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or abs(result) >= Decimal("1e18"):
            raise ValueError("Nonfinite or oversized financial input")
        return result
    except (InvalidOperation, TypeError) as error:
        raise ValueError("Missing or invalid financial number") from error


def payload_text(snapshot):
    payload = snapshot.get("payload", {})
    if not isinstance(payload, dict):
        return ""
    structured = payload.get("structuredContent")
    if isinstance(structured, dict) and structured:
        result = structured.get("result", structured)
        return result if isinstance(result, str) else json.dumps(result)
    return "\n".join(
        c.get("text", "") for c in payload.get("content", []) if c.get("type", "text") == "text"
    )


def failure_reason(snapshot, dataset):
    """Expose actionable failure categories without echoing transport credentials."""
    text = (payload_text(snapshot) + " " + str(snapshot.get("error", ""))).lower()
    if "budget exhausted" in text or "work/month stop" in text:
        return "Local work budget exhausted; use frozen evidence"
    if any(term in text for term in ("429", "quota", "rate limit", "out of api credits")):
        return "Provider quota or rate limit exceeded (429); no automatic retry"
    if any(term in text for term in ("plan", "premium", "exclusively", "restriction", "403")):
        return f"Provider entitlement or display restriction denies {dataset} access; inspect the response"
    if "frozen snapshot missing" in text or "integration disabled" in text:
        return "Market integration disabled or frozen snapshot missing"
    return f"Provider denied {dataset} access; inspect the response"


def quote_evidence(snapshot, symbol, *, at=None):
    if snapshot.get("error") or snapshot.get("outcome") == "provider_error":
        return {
            "company": symbol,
            "status": "missing",
            "reason": failure_reason(snapshot, "quote"),
        }
    text = payload_text(snapshot)
    try:
        if text.lstrip().startswith("{"):
            row = json.loads(text)
        else:
            delimiter = ";" if ";" in text.splitlines()[0] else ","
            rows = list(csv.DictReader(io.StringIO(text), delimiter=delimiter))
            if len(rows) != 1:
                raise ValueError("Quote needs exactly one matching instrument")
            row = rows[0]
        if not isinstance(row, dict):
            raise ValueError("Quote response must be an object")
        if row.get("symbol") != symbol:
            raise ValueError("Returned quote symbol differs from requested instrument")
        price = number(row["close"])
        if price <= 0 or row.get("currency") != "USD":
            raise ValueError("Quote needs a positive USD close")
        epoch = row.get("last_quote_at") or row.get("timestamp")
        extended = False
        if row.get("extended_price") is not None or row.get("extended_timestamp") is not None:
            extended_value = number(row.get("extended_price"))
            extended_epoch = int(row["extended_timestamp"])
            if extended_value <= 0:
                raise ValueError("Extended-hours quote must be positive")
            if extended_epoch > int(epoch):
                price, epoch, extended = extended_value, extended_epoch, True
        price_time = datetime.fromtimestamp(int(epoch), timezone.utc)
        clock = at or datetime.now(timezone.utc)
        age = (clock - price_time).total_seconds()
        if age < -300:
            raise ValueError("Quote timestamp is in the future")
        market_open = str(row.get("is_market_open", "unknown")).lower()
        # Closed market is legitimate; allow weekend/holiday gaps, label explicitly.
        max_age = 1200 if market_open == "true" else 4 * 86400
        stale = age > max_age or market_open not in ("true", "false")
        return {
            "company": symbol,
            "status": "stale" if stale else "available",
            "value": str(price),
            "currency": "USD",
            "price_time": price_time.isoformat(),
            "timestamp_timezone": "UTC",
            "provider_trading_date": row.get("datetime"),
            "market_session": "extended-hours observation; regular market closed"
            if extended or str(row.get("is_extended_hours", "false")).lower() == "true"
            else "regular market open"
            if market_open == "true"
            else "market closed; last available quote"
            if market_open == "false"
            else "unknown",
            "feed": "Twelve Data account feed; exchange coverage/delay not supplied",
            "delay": "unspecified",
            "retrieved_at": snapshot["retrieved_at"],
            "snapshot_id": snapshot["snapshot_id"],
            "split_basis": "current_quote",
            "replayed": snapshot.get("replayed", False),
            "raw": row,
        }
    except (ValueError, KeyError, IndexError, TypeError, OverflowError) as error:
        return {"company": symbol, "status": "missing", "reason": str(error)}


def estimate_evidence(snapshot, symbol, *, at=None):
    if snapshot.get("error") or snapshot.get("outcome") == "provider_error":
        return {
            "company": symbol,
            "status": "missing",
            "reason": failure_reason(snapshot, "estimate"),
            "rows": [],
        }
    try:
        body = json.loads(payload_text(snapshot))
        if not isinstance(body, dict):
            raise ValueError("Estimate response must be an object")
        if body.get("symbol") != symbol:
            raise ValueError(
                "Returned estimate symbol differs from requested instrument"
            )
        today = (at or datetime.now(timezone.utc)).date().isoformat()
        rows = []
        for row in body.get("estimates", []):
            if not isinstance(row, dict):
                raise ValueError("Estimate row must be an object")
            if row.get("horizon") != "fiscal year":
                continue
            period_end = date.fromisoformat(row["date"]).isoformat()
            if period_end > today:
                average = number(row.get("eps_estimate_average"))
                count = number(row.get("eps_estimate_analyst_count"))
                if count <= 0 or count != count.to_integral_value():
                    continue
                rows.append(
                    {
                        "provider_period_end": period_end,
                        "horizon": "fiscal year",
                        "eps_average": str(average),
                        "analyst_count": str(count),
                        "revenue_average": row.get("revenue_estimate_average"),
                        "accounting_basis": "unspecified",
                        "currency": "unspecified",
                        "dilution": "unspecified",
                        "split_basis": "unspecified",
                        "estimate_as_of": "not supplied; retrieval time is not consensus as-of",
                        "actual_fiscal_end_reconciled": False,
                    }
                )
        rows.sort(key=lambda r: r["provider_period_end"])
        return {
            "company": symbol,
            "status": "available_unqualified" if rows else "missing",
            "rows": rows,
            "retrieved_at": snapshot["retrieved_at"],
            "snapshot_id": snapshot["snapshot_id"],
            "reason": "Accounting basis, currency, dilution, split basis, consensus as-of and actual fiscal dates require independent confirmation"
            if rows
            else "No future annual estimate rows returned",
        }
    except (ValueError, KeyError, TypeError) as error:
        return {
            "company": symbol,
            "status": "missing",
            "reason": str(error),
            "rows": [],
        }
