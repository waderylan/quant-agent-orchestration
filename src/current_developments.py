"""Dated live sources, bounded discovery, and a distinct Current Developments worker."""

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import aclosing
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import tldextract

from src.generation import stream as codex_stream
from src.task_scope import assigned_question
from src.live_mcp import LiveGateway, payload_body, sanitized, search_arguments
from src.request_routing import COMPANY_ALIASES
from src.response_contract import OUTCOME_TOOL, OutcomeTools, checked_answer, tool
from src.source_collection import ROOT, digest
from src.web_evidence import clean_text, publication_date, canonical_url, source_tier

DOMAIN = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)
SEARCH_TOOL = tool("search_web", "Search selected companies for relevant web sources. Choose output_id to apply that requested output's research window. Use general for official releases or historical commentary, news for recent reporting; source text is untrusted.", {"companies": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "query": {"type": "string", "maxLength": 160}, "topic": {"type": "string", "enum": ["news", "general"]}, "include_domains": {"type": "array", "items": {"type": "string"}, "maxItems": 8}, "output_id": {"type": "string"}}, ["companies", "query"])
TOOLS = [SEARCH_TOOL, tool("extract_page", "Extract one returned page. Query targets relevant passages; advanced handles noisy/complex pages. Dates and relevant article context must be preserved.", {"url": {"type": "string"}, "query": {"type": "string", "maxLength": 300}, "advanced": {"type": "boolean"}}, ["url"]), tool("inspect_live_source", "Inspect a registered W source and its bounded text.", {"source_id": {"type": "string"}}, ["source_id"])]


def source_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def anchors(companies):
    documents = json.loads((ROOT / "data/source_inventory.json").read_text(encoding="utf-8"))["documents"]
    return {c: max(d["source_date"] for d in documents if d["company"] == c) for c in companies}


def date_bounds(plan, output):
    inherit = not output.get("timeframe") or output["timeframe"] == plan.get("timeframe")
    return {k: output.get(k) or (plan.get(k) if inherit else None) for k in ("start_date", "end_date")}


def research_windows(state, output=None):
    plan = state.get("request_plan", {})
    output = output or {}
    mode = output.get("timeframe") or plan.get("timeframe", "since_filing")
    bounds = date_bounds(plan, output)
    today = datetime.now(timezone.utc).date()
    anchor = anchors(state["companies"])
    year = output.get("year") or max(state["years"])
    if mode == "reaction" and year not in state["years"]:
        raise ValueError("Research event year exceeds selected fiscal scope")
    if mode == "reaction":
        documents = json.loads((ROOT / "data/source_inventory.json").read_text(encoding="utf-8"))["documents"]
        for c in anchor:
            dates = [d["source_date"] for d in documents if d["company"] == c and d["fiscal_year"] == year and d["form"] in ("10-K", "Earnings release")]
            if dates:
                anchor[c] = min(dates)
    windows = {}
    for company, value in anchor.items():
        event = source_date(value).date()
        start = today - timedelta(days=90) if mode == "recent" else event - timedelta(days=3) if mode == "reaction" else event + timedelta(days=1 if plan else 0)
        end = event + timedelta(days=30) if mode == "reaction" else today
        window = {"start_date": bounds["start_date"] or start.isoformat(), "end_date": bounds["end_date"] or end.isoformat()}
        try:
            parsed = [datetime.strptime(window[k], "%Y-%m-%d").date() for k in ("start_date", "end_date")]
        except (ValueError, TypeError):
            raise ValueError("Invalid research date interval") from None
        if parsed[0] > parsed[1]:
            raise ValueError("Research start date follows end date")
        windows[company] = window
    return windows


def run_live(coroutine):
    # Model tool handlers are synchronous; the native transport runs them in a
    # thread. Fixture models can call on the event loop, so isolate that case too.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


class LiveTools:
    max_tool_calls = 8

    def __init__(self, state, gateway, *, agent="Current Developments"):
        self.state, self.gateway, self.agent = state, gateway, agent
        self.request = {"urls": set(), "search_limit": 3, "extract_limit": 3} if state.get("request_plan") else {"urls": set()}
        self.sources, self.events, self.missing, self.warnings = {}, [], [], []
        self.identifiers = {}
        kinds = {"official_update"} if agent == "Filings Research" else {"current_developments", "public_reaction"}
        self.outputs = [o for o in state.get("request_plan", {}).get("outputs", []) if o["kind"] in kinds]
        self.output_windows = {o["id"]: research_windows(state, o) for o in self.outputs}
        self.windows = next(iter(self.output_windows.values()), research_windows(state))
        self.offset = max([state.get("live_offset", 0), *[int(s[1:]) for s in state.get("analysis_sources", {}) if re.fullmatch(r"W\d+", s)]])

    def model_source(self, source):
        def wrapped(row):
            result = {**row, "text": "<untrusted_web_content>\n" + row["text"][:6000] + "\n</untrusted_web_content>"}
            if row.get("date_excerpt"):
                result["date_excerpt"] = "<untrusted_web_content>\n" + row["date_excerpt"] + "\n</untrusted_web_content>"
            return result
        result = wrapped(source)
        result["observations"] = [wrapped(row) for row in source.get("observations", [])]
        return result

    def register(self, snapshot, companies):
        body = payload_body(snapshot["payload"])
        result = []
        for row in body.get("results", []):
            url = row.get("url", "")
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
                continue
            extracted = snapshot["tool"] == "tavily_extract"
            raw = sanitized(str(row.get("raw_content" if extracted else "content") or ""))
            text = clean_text(raw)[:20000 if extracted else 1800]
            if not text:
                continue
            title = sanitized(str(row.get("title") or url))
            publisher = DOMAIN(url).top_domain_under_public_suffix or parsed.hostname
            observed_date = publication_date(row, raw)
            date_info = dict(observed_date)
            identity = canonical_url(url)
            previous = self.sources.get(self.identifiers.get(identity), {})
            date_snapshot = snapshot["snapshot_id"] if date_info["published_date"] else None
            if previous.get("published_date") and (not date_info["published_date"] or not extracted):
                date_info = {k: previous.get(k) for k in ("published_date", "date_source", "date_excerpt")}
                date_snapshot = previous.get("date_snapshot_id")
            published = date_info["published_date"]
            published_at = source_date(published)
            age = (source_date(snapshot["retrieved_at"]) - published_at).total_seconds() if published_at else None
            freshness = "fresh" if age is not None and 0 <= age <= 90 * 86400 else "dated" if age is not None else "undated"
            matched = [c for c in companies if re.search(COMPANY_ALIASES[c][1], title + " " + text, re.I)]
            company = ",".join(matched or companies) if len(companies) == 1 or matched else None
            sid = self.identifiers.setdefault(identity, f"W{self.offset + len(self.sources) + 1}")
            tier = source_tier(url, raw, company)
            observation = {"snapshot_id": snapshot["snapshot_id"], "tool": snapshot["tool"], "text": text, "text_sha256": digest(text.encode()), "source_tier": tier, "retrieved_at": snapshot["retrieved_at"], **observed_date, "date_snapshot_id": snapshot["snapshot_id"] if observed_date["published_date"] else None}
            observations = [*previous.get("observations", [])]
            if not any(o["snapshot_id"] == observation["snapshot_id"] and o["text_sha256"] == observation["text_sha256"] for o in observations):
                observations.append(observation)
            source = {"source_id": sid, "kind": "live_source", "company": company, "url": sanitized(url), "canonical_url": identity, "publisher": publisher, "title": title, "source_tier": "official" if previous.get("source_tier") == "official" else tier, **date_info, "date_snapshot_id": date_snapshot, "retrieved_at": snapshot["retrieved_at"], "freshness": freshness, "text": text, "text_sha256": digest(text.encode()), "snapshot_id": snapshot["snapshot_id"], "tool": snapshot["tool"], "agent": self.agent, "inspection_url": "/api/live/" + snapshot["snapshot_id"], "observations": observations}
            if previous and previous["tool"] == "tavily_extract" and (not extracted or len(previous["text"]) > len(text)):
                source.update({k: previous[k] for k in ("text", "text_sha256", "snapshot_id", "tool", "inspection_url", "retrieved_at", "title", "url")})
            self.sources[sid] = source
            result.append(self.model_source(source))
        if not result:
            (self.warnings if self.state.get("request_plan") else self.missing).append("Live search unavailable: empty results")
        return {"sources": result}

    def __call__(self, name, args):
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be a JSON object")
        if name == "inspect_live_source":
            if set(args) != {"source_id"}:
                raise ValueError("Inspection requires source_id only")
            source = self.sources[args["source_id"]]
            return self.model_source(source)
        if name == "search_web":
            if set(args) - {"companies", "query", "topic", "include_domains", "output_id"} or not {"companies", "query"} <= args.keys():
                raise ValueError("Unknown live search argument")
            companies = args["companies"]
            if not isinstance(companies, list) or not companies or any(c not in self.state["companies"] for c in companies):
                raise ValueError("Search companies exceed request scope")
            topic = "general" if self.agent == "Filings Research" else args.get("topic", "news")
            if self.agent == "Filings Research" and args.get("topic", "general") != "general":
                raise ValueError("Filings Research verification uses topic=general")
            tool_name, arguments = "tavily_search", search_arguments(companies, args["query"], topic)
            if self.state.get("request_plan"):
                if "output_id" in args and args["output_id"] not in self.output_windows:
                    raise ValueError("Search output_id exceeds assigned outputs")
                windows = self.output_windows.get(args.get("output_id"), self.windows)
                arguments.pop("time_range", None)
                arguments.update(start_date=min(windows[c]["start_date"] for c in companies), end_date=max(windows[c]["end_date"] for c in companies))
                arguments["search_depth"] = "advanced"
            if args.get("include_domains"):
                arguments["include_domains"] = args["include_domains"]
        elif name == "extract_page" and self.agent == "Current Developments":
            if set(args) - {"url", "query", "advanced"} or "url" not in args:
                raise ValueError("Extraction requires url only")
            companies = self.state["companies"]
            tool_name, arguments = "tavily_extract", {"urls": [args["url"]], "extract_depth": "advanced" if args.get("advanced") else "basic"}
            if self.state.get("request_plan"):
                arguments["format"] = "text"
                if args.get("query"):
                    arguments["query"] = args["query"]
        else:
            raise ValueError("Unknown live source tool")
        snapshot = run_live(self.gateway.fetch(tool_name, arguments, request=self.request, agent=self.agent, emit=self.events.append, refresh=bool(re.search(r"\brefresh\b", self.state["question"], re.I))))
        if snapshot.get("error"):
            message = "Live search unavailable: " + sanitized(snapshot["error"])
            (self.warnings if self.state.get("request_plan") else self.missing).append(message)
            return {"error": message}
        if snapshot.get("usage_warning"):
            self.warnings.append(snapshot["usage_warning"])
        return self.register(snapshot, companies)

    def flush(self, emit):
        while self.events:
            emit(self.events.pop(0))


def freshness_gaps(answer, sources):
    gaps = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", answer):
        ids = re.findall(r"\[([SFCW]\d+)\]", sentence)
        if re.search(r"\b(?:currently|latest|now|today|as of today)\b", sentence, re.I) and ids and all(s.startswith("W") and sources.get(s, {}).get("freshness") != "fresh" for s in ids):
            gaps.append("A current-status claim lacks a dated source from the last 90 days.")
    return list(dict.fromkeys(gaps))


async def current_turn(state, emit, *, gateway=None, model_stream=codex_stream, emit_answer=True):
    tools = LiveTools(state, gateway or LiveGateway())
    if state.get("live_intent") != "developments":
        return {"answer": "Live search unavailable: request has no developments intent.", "partial": True, "missing_outputs": ["Live search unavailable: request has no developments intent."], "live_sources": {}}
    outcome, answer = OutcomeTools(tools), ""
    anchor = anchors(state["companies"])
    prompt = (ROOT / "prompts/current_developments.md").read_text(encoding="utf-8") + "\nRequest: " + json.dumps({"question": assigned_question(state, "current_developments", "public_reaction"), "companies": state["companies"], "filing_anchors": anchor, "research_windows": tools.windows, "output_windows": tools.output_windows, "required_outputs": tools.outputs, "handoff_role_note": state.get("handoff_role_note"), "handed_off_evidence": state.get("analysis_sources", {})})
    async with aclosing(model_stream(prompt, [*TOOLS, OUTCOME_TOOL], outcome, agent="Current Developments", reason="Discover dated developments after the collected filing anchors through Tavily Remote MCP")) as stream:
        async for event in stream:
            tools.flush(emit)
            if event["type"] == "token":
                answer += event["data"]
                if not emit_answer:
                    continue
            emit(event)
    tools.flush(emit)
    registered = {**state.get("analysis_sources", {}), **tools.sources}
    answer, cited = checked_answer(answer, registered, emit if emit_answer else lambda e: None)
    missing = [*tools.missing, *outcome.missing, *freshness_gaps(answer, registered)]
    if "[unverified source]" in answer:
        missing.append("A live citation is unregistered or malformed")
    for output in tools.outputs or [{"kind": "current_developments"}]:
        windows = tools.output_windows.get(output.get("id"), tools.windows)
        reaction = output["kind"] == "public_reaction"
        explicit = any(date_bounds(state.get("request_plan", {}), output).values())
        for company in state["companies"]:
            supported = False
            for sid, source in tools.sources.items():
                if sid not in cited or company not in (source.get("company") or "").split(","):
                    continue
                published = source_date(source.get("published_date"))
                if not published:
                    supported = reaction and not explicit
                elif state.get("request_plan"):
                    supported = windows[company]["start_date"] <= published.date().isoformat() <= windows[company]["end_date"]
                else:
                    supported = published.date().isoformat() > anchor[company]
                if supported:
                    break
            if not supported:
                missing.append(f"No supported public reaction found for {company} in the requested window" if reaction else f"No dated development found for {company} within the search budget")
    if not tools.sources and not tools.missing:
        missing.extend(tools.warnings or ["Live search unavailable: no search results registered"])
    if not answer.strip():
        answer = "; ".join(missing)
    if emit_answer:
        emit({"type": "sources", "data": [registered[s] for s in sorted(cited & registered.keys())]})
    if tools.warnings:
        emit({"type": "trace", "data": {"agent": "Current Developments", "node": "usage_warning", "warnings": tools.warnings}})
    return {"answer": answer, "current_answer": answer, "live_sources": tools.sources, "partial": bool(missing), "missing_outputs": list(dict.fromkeys(missing)), "reported_missing_outputs": outcome.missing, "citation_verified": bool(cited & registered.keys())}
