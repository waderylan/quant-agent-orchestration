"""Post-filing context for every registered risk finding; filed evidence stays immutable."""

import os
import re
from datetime import datetime, timezone, timedelta

from src.current_developments import LiveTools, run_live, source_date
from src.live_mcp import LiveGateway, sanitized, search_arguments
from src.request_routing import web_prohibited


class RiskLiveChecks:
    """One automatic shared-MCP search per distinct registered risk finding."""

    def __init__(self, state, risk_tools, gateway=None):
        self.state, self.risks = state, risk_tools
        self.web = LiveTools(state, gateway or LiveGateway(), agent="Risk Summary", windows={})
        self.checks, self.missing = [], []
        self.enabled = state.get("risk_live_check", os.getenv("RISK_LIVE_CHECK", "on") != "off")
        self.prohibited = web_prohibited(state["question"])

    def check(self, change, query=None):
        old, new = (self.risks.sources[change[k]] for k in ("before", "after"))
        key = (old["document_id"], old["start"], old["end"], new["document_id"], new["start"], new["end"], change["classification"], " ".join(change["rationale"].casefold().split()))
        prior = next((row for row in self.checks if row["key"] == key), None)
        if prior:
            return prior
        row = {"key": key, "classification": change["classification"], "before": change["before"], "after": change["after"], "company": new["company"], "filed": new.get("filed"), "fiscal_end": new.get("fiscal_end"), "source_ids": []}
        self.checks.append(row)
        if not self.enabled or self.prohibited:
            row.update(status="skipped", reason="Explicit no-web instruction" if self.prohibited else "Risk live comparison disabled")
            return row
        filed = source_date(new.get("filed"))
        today = datetime.now(timezone.utc).date()
        if not filed or filed.date() >= today:
            return self.unavailable(row, "Post-filing window unavailable: newer source has no usable filing date")
        window = {"start_date": (filed.date() + timedelta(days=1)).isoformat(), "end_date": today.isoformat()}
        row["window"] = window
        # A model supplies the risk subject, never dates, scope or acquisition policy.
        query = query or change["rationale"]
        query = re.sub(r"\[[SFCW]\d+\]", "", query)
        query = " ".join(query.split())[:130]
        arguments = search_arguments([new["company"]], query, "news")
        arguments.pop("time_range", None)
        arguments.update(window, search_depth="advanced")
        row["arguments"] = arguments
        try:
            snapshot = run_live(self.web.gateway.fetch("tavily_search", arguments, request={"search_limit": 1, "extract_limit": 0}, agent="Risk Summary", emit=self.web.events.append, refresh=bool(re.search(r"\brefresh\b", self.state["question"], re.I))))
            if snapshot.get("error"):
                return self.unavailable(row, "Risk live check unavailable: " + sanitized(snapshot["error"]))
            result = self.web.register(snapshot, [new["company"]])
            eligible = [source for source in result["sources"] if (published := source_date(source.get("published_date"))) and window["start_date"] <= published.date().isoformat() <= window["end_date"]]
            row.update(status="results" if eligible else "no_dated_evidence", source_ids=[s["source_id"] for s in eligible], snapshot_id=snapshot["snapshot_id"], cache=snapshot.get("cache", False))
            return {**row, "sources": eligible, "use": "Post-filing context only. Check the risk subject and event date in each excerpt; publication alone does not date an event. Dated official evidence may confirm an event; independent evidence supports attributed reporting. No match is not proof the risk did not occur. Never change the filed classification."}
        except Exception as error:
            return self.unavailable(row, "Risk live check unavailable: " + sanitized(str(error) or type(error).__name__))

    def unavailable(self, row, reason):
        row.update(status="unavailable", reason=reason)
        self.missing.append(f"{row['company']} risk {row['before']}/{row['after']}: {reason}")
        return row

    def flush(self, writer):
        self.web.flush(writer)
