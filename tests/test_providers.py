"""Protect provider boundaries, accounting stops, and real streamed tool behavior."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from src import generation, provider_client
from src.provider_limits import ProviderLedger
from src.provider_policy import route
from src.generation_context import RoutingContext
from src.provider_models import NVIDIA_SUPER as SUPER, NEBIUS_DEEPSEEK as DEEPSEEK
from src.response_contract import OUTCOME_TOOL, OutcomeTools

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp()
SEARCH = {"type":"function", "name":"search", "inputSchema":{"type":"object", "properties":{"query":{"type":"string"}}, "required":["query"], "additionalProperties":False}}


def sse(*deltas, finish="stop", usage=True, done=True):
    rows = [{"choices":[{"delta":delta,"finish_reason":None}]} for delta in deltas]
    rows.append({"choices":[{"delta":{},"finish_reason":finish}]})
    if usage:
        rows.append({"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":20}})
    text = "".join("data: " + json.dumps(row) + "\n\n" for row in rows)
    return httpx.Response(200, text=text + ("data: [DONE]\n\n" if done else ""))


def tool(name, args, identity="one", *, finish="tool_calls"):
    encoded = json.dumps(args)
    return sse({"tool_calls":[{"index":0,"id":identity,"function":{"name":name,"arguments":encoded[:5]}}]},
               {"tool_calls":[{"index":0,"function":{"arguments":encoded[5:]}}]}, finish=finish)


class Handler:
    max_tool_calls = 3
    def __init__(self):
        self.executed = []
    def __call__(self, name, args):
        self.executed.append((name,args))
        return {"sources":[{"source_id":"S1","text":"Supported fact"}]}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("GENERATION_PROFILE","api")
    monkeypatch.setenv("NVIDIA_API_KEY","fixture-nvidia-secret")
    monkeypatch.setenv("NEBIUS_API_KEY","fixture-nebius-secret")
    for name in ("NVIDIA_BASE_URL","NEBIUS_BASE_URL"):
        monkeypatch.delenv(name,raising=False)
    requests = []
    def install(respond):
        async def transport(request):
            requests.append(request)
            return respond(request)
        monkeypatch.setattr(provider_client,"client",lambda: httpx.AsyncClient(transport=httpx.MockTransport(transport)))
        return requests
    return install


def test_routing_uses_task_complexity_and_independent_review():
    assert route(RoutingContext(phase="planner",companies=4),agent="Request Planner",input_bound=500).model==DEEPSEEK
    assert route(RoutingContext(output="financial_inputs"),agent="Financial Data",input_bound=500).model==SUPER
    assert route(RoutingContext(phase="reviewer"),agent="Answer Reviewer",input_bound=500).model==SUPER
    for context in (RoutingContext(companies=2),RoutingContext(years=2),RoutingContext(source_conflict=True),RoutingContext(output="risk_changes"),RoutingContext(evidence_kinds=("S","F"))):
        assert route(context,agent="Filings Research",input_bound=500).model==DEEPSEEK
    assert route(RoutingContext(),agent="Filings Research",input_bound=65000).model==DEEPSEEK


def test_shared_nvidia_pacing_window_and_unlimited_recorded_usage(tmp_path):
    now=[NOW]
    ledger=ProviderLedger(tmp_path/"limits.sqlite3",clock=lambda:now[0])
    for _ in range(3):
        ledger.record("nebius",DEEPSEEK,"same-request","0.6")
    assert ledger.status()["nebius"]=={"calls":3,"estimated_usd":"1.8","unknown_cost_calls":0}
    one,two=ledger.try_permit("nvidia"),ledger.try_permit("nvidia")
    assert one and two and ledger.try_permit("nvidia") is None
    ledger.release(one)
    ledger.release(two)
    for _ in range(38):
        identity=ledger.try_permit("nvidia")
        assert identity
        ledger.release(identity)
    assert ProviderLedger(ledger.path,clock=lambda:now[0]).try_permit("nvidia") is None
    now[0]+=61
    assert ledger.try_permit("nvidia")


@pytest.mark.asyncio
async def test_invalid_structured_arguments_are_corrected_before_submission(api):
    calls = [0]
    def respond(request):
        calls[0] += 1
        payload = json.loads(request.content)
        assert payload["tool_choice"]["function"]["name"] == "submit_plan"
        return tool("submit_plan", {"ready": "wrong"} if calls[0] == 1 else {"ready": True, "note": None}, str(calls[0]))
    api(respond)
    schema = {"name": "submit_plan", "inputSchema": {"type": "object", "properties": {
        "ready": {"type": "boolean"}, "note": {"type": "string"}}, "required": ["ready"], "additionalProperties": False}}
    handler = Handler()
    _ = [e async for e in generation.stream("question", [schema], handler)]
    assert calls[0] == 2 and handler.executed == [("submit_plan", {"ready": True})]


@pytest.mark.asyncio
async def test_fragmented_tools_completion_slot_and_final_stream(api):
    step=[0]
    def respond(request):
        payload=json.loads(request.content)
        step[0]+=1
        if step[0]==1:
            return tool("search",{"query":"filed fact"})
        if step[0]==2:
            assert any(m.get("role")=="tool" for m in payload["messages"])
            return tool("report_outcome",{"status":"complete","missing":[]},"two")
        assert "tools" not in payload
        assert payload["tool_choice"] == "none"
        return sse({"reasoning_content":"never show this"},{"content":"Supported "},{"content":"fact [S1]."})
    requests=api(respond)
    handler=Handler()
    outcome=OutcomeTools(handler)
    events=[e async for e in generation.stream("question",[SEARCH,OUTCOME_TOOL],outcome)]
    assert handler.executed==[("search",{"query":"filed fact"})] and outcome.status=="complete"
    assert "".join(e["data"] for e in events if e["type"]=="token")=="Supported fact [S1]."
    assert len(requests)==3 and all(json.loads(r.content)["chat_template_kwargs"]["enable_thinking"] is False for r in requests)
    assert len([e for e in events if e["type"]=="trace" and e["data"]["node"]=="provider_usage"])==3


@pytest.mark.asyncio
async def test_tool_call_with_stop_finish_still_executes_and_accounts(api):
    def respond(request):
        payload=json.loads(request.content)
        if "tools" in payload:
            return tool("report_outcome",{"status":"complete","missing":[]},finish="stop")
        return sse({"content":"Supported fact [S1]."})
    requests=api(respond)
    events=[e async for e in generation.stream("question",[OUTCOME_TOOL],OutcomeTools(Handler()),routing_context=RoutingContext(companies=2))]
    assert any(e["type"]=="token" for e in events)
    assert Decimal(ProviderLedger().status()["nebius"]["estimated_usd"])>0
    assert len(requests)==2


@pytest.mark.asyncio
async def test_deepseek_nulls_parse_and_transient_failure_retries_before_downgrade(api):
    posts=[0]
    def respond(request):
        assert request.url.host=="api.tokenfactory.nebius.com"
        posts[0]+=1
        if posts[0]==1:
            return httpx.Response(503)
        # DeepSeek streams explicit nulls for absent tool calls and functions.
        return sse({"reasoning_content":"hidden","tool_calls":None},{"content":"Fact [S1].","tool_calls":None})
    api(respond)
    events=[e async for e in generation.stream("question",[],Handler(),routing_context=RoutingContext(companies=2))]
    assert posts[0]==2 and "".join(e["data"] for e in events if e["type"]=="token")=="Fact [S1]."
    assert [e["data"]["node"] for e in events if e["type"]=="trace" and e["data"]["node"] in ("provider_retry","provider_fallback")]==["provider_retry"]


@pytest.mark.asyncio
async def test_missing_nebius_key_never_contacts_nebius_and_falls_back(api, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    def respond(request):
        assert request.url.host=="integrate.api.nvidia.com"
        return tool("submit_plan",{"ready":True},finish="stop")
    requests=api(respond)
    schema={"name":"submit_plan","inputSchema":{"type":"object","properties":{"ready":{"type":"boolean"}},"required":["ready"]}}
    handler=Handler()
    events=[e async for e in generation.stream("question",[schema],handler,routing_context=RoutingContext(companies=2))]
    assert len(requests)==1 and handler.executed==[("submit_plan",{"ready":True})]
    assert any(e["type"]=="trace" and e["data"]["node"]=="provider_fallback" for e in events)


@pytest.mark.asyncio
async def test_context_selection_does_not_consume_http_recovery_or_fallback_to_a_smaller_limit(api):
    calls = [0]
    def respond(request):
        assert request.url.host == "integrate.api.nvidia.com"
        calls[0] += 1
        return httpx.Response(500) if calls[0] == 1 else tool("submit_plan", {"ready": True})
    api(respond)
    schema = {"name": "submit_plan", "inputSchema": {"type": "object", "properties": {"ready": {"type": "boolean"}}, "required": ["ready"]}}
    handler = Handler()
    events = [e async for e in generation.stream("e" * 1030000, [schema], handler, agent="Risk Summary")]
    assert calls[0] == 2 and handler.executed == [("submit_plan", {"ready": True})]
    assert len([e for e in events if e["type"] == "trace" and e["data"]["node"] == "provider_retry"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("fault",["unknown","bad_json","length","missing_done","auth"])
async def test_invalid_provider_results_do_not_execute_tools_or_leak_errors(api,fault):
    def respond(request):
        if fault=="auth":
            return httpx.Response(401,text="fixture-nvidia-secret")
        if fault=="length":
            return tool("search",{"query":"x"},finish="length")
        if fault=="missing_done":
            return sse({"content":"Incomplete"},done=False)
        if fault=="bad_json":
            return sse({"tool_calls":[{"index":0,"id":"one","function":{"name":"search","arguments":"{"}}]},finish="tool_calls")
        return tool("not_a_tool",{})
    requests=api(respond)
    handler=Handler()
    with pytest.raises(RuntimeError) as error:
        _=[e async for e in generation.stream("question",[SEARCH,OUTCOME_TOOL],OutcomeTools(handler))]
    assert not handler.executed and "fixture-nvidia-secret" not in str(error.value)
    if fault=="auth":
        assert [r.url.host for r in requests]==["integrate.api.nvidia.com","api.tokenfactory.nebius.com"]


@pytest.mark.asyncio
async def test_nvidia_rate_limit_reroutes_to_deepseek_and_reuses_completed_tools(api):
    count=[0]
    def respond(request):
        count[0]+=1
        if count[0]==1:
            return tool("report_outcome",{"status":"complete","missing":[]})
        if count[0]==2:
            return httpx.Response(429,headers={"retry-after":"0.01"})
        assert len([m for m in json.loads(request.content)["messages"] if m["role"]=="tool"])==1
        return sse({"content":"Fact [S1]."})
    requests=api(respond)
    outcome=OutcomeTools(Handler())
    events=[e async for e in generation.stream("question",[OUTCOME_TOOL],outcome)]
    assert [r.url.host for r in requests][-1]=="api.tokenfactory.nebius.com" and outcome.status=="complete"
    assert len([e for e in events if e["type"]=="tool"])==1
    assert any(e["type"]=="trace" and e["data"]["node"]=="provider_fallback" and e["data"]["model"]==DEEPSEEK for e in events)


@pytest.mark.asyncio
async def test_full_nvidia_pacing_window_reroutes_instead_of_waiting(api):
    ledger=ProviderLedger()
    for _ in range(40):
        ledger.release(ledger.try_permit("nvidia"))
    requests=api(lambda request: sse({"content":"Fact [S1]."}))
    events=[e async for e in generation.stream("question",[],Handler())]
    assert [r.url.host for r in requests]==["api.tokenfactory.nebius.com"]
    assert "pacing" in next(e["data"]["reason"] for e in events if e["type"]=="trace" and e["data"]["node"]=="provider_fallback")


def test_retry_after_does_not_retry_earlier_than_the_provider_requests(monkeypatch):
    monkeypatch.setattr(provider_client.time, "time", lambda: NOW)
    assert provider_client.retry_delay("30") == 30
    assert provider_client.retry_delay("Tue, 20 Oct 2026 00:00:40 GMT") == 40
    assert provider_client.retry_delay("invalid") == 0


@pytest.mark.asyncio
async def test_cancellation_closes_stream_and_releases_permit(api,monkeypatch):
    entered,closed=asyncio.Event(),asyncio.Event()
    class Waiting(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b""
        async def aclose(self):
            closed.set()
    api(lambda request:httpx.Response(200,stream=Waiting()))
    async def run():
        return [e async for e in generation.stream("question",[OUTCOME_TOOL],OutcomeTools(Handler()))]
    task=asyncio.create_task(run())
    await asyncio.wait_for(entered.wait(),2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()
    ledger=ProviderLedger()
    with ledger.db() as db:
        assert db.execute("SELECT COUNT(*) FROM calls WHERE until>0").fetchone()[0]==0


@pytest.mark.asyncio
async def test_concurrent_profile_selection_is_request_local(api, monkeypatch):
    api(lambda request: sse({"content": "Hosted answer"}))
    monkeypatch.setenv("GENERATION_PROFILE", "codex")
    async def local(*args, **kwargs):
        await asyncio.sleep(0)
        yield {"type": "trace", "data": {"agent": "Filings Research", "provider": "Codex subscription", "model": "local-model", "reason": "Local development"}}
        yield {"type": "token", "data": "Local answer"}
    monkeypatch.setattr(generation.codex_model, "stream", local)
    async def collect(profile):
        return [e async for e in generation.stream("question", [], Handler(), profile=profile)]
    local_events, hosted_events = await asyncio.gather(collect("codex"), collect("api"))
    assert [e["data"] for e in local_events if e["type"] == "token"] == ["Local answer"]
    assert [e["data"] for e in hosted_events if e["type"] == "token"] == ["Hosted answer"]
    local_route = next(e["data"] for e in local_events if e["type"] == "trace")
    assert local_route["node"] == "provider_route" and local_route["model"] == "local-model"
    assert generation.os.getenv("GENERATION_PROFILE") == "codex"


@pytest.mark.asyncio
async def test_batched_tools_cannot_consume_the_reserved_completion_slot():
    from src.generation_tools import ToolConversation
    handler = Handler()
    conversation = ToolConversation([SEARCH, OUTCOME_TOOL], OutcomeTools(handler), "Fixture")
    calls = [{"id": str(i), "type": "function", "function": {"name": "search", "arguments": '{"query":"x"}'}} for i in range(3)]
    messages = []
    events = [e async for e in conversation.execute(calls, messages, "", conversation.available())]
    assert events[0]["data"]["node"] == "provider_tool_rejected" and conversation.calls == 0
    assert len([m for m in messages if m["role"] == "tool"]) == 3
    assert not handler.executed


@pytest.mark.asyncio
async def test_completion_waits_until_the_model_reads_its_tool_results():
    from src.generation_tools import ToolConversation
    outcome = OutcomeTools(Handler())
    conversation = ToolConversation([SEARCH, OUTCOME_TOOL], outcome, "Fixture")
    search = {"id": "search", "type": "function", "function": {"name": "search", "arguments": '{"query":"x"}'}}
    report = {"id": "report", "type": "function", "function": {"name": "report_outcome", "arguments": '{"status":"complete","missing":[]}'}}
    messages = []
    _ = [e async for e in conversation.execute([search, report], messages, "", conversation.available())]
    assert outcome.status is None and outcome.handler.executed == [("search", {"query": "x"})]
    assert "Submit report_outcome alone" in messages[-1]["content"]
    report["id"] = "confirmed"
    _ = [e async for e in conversation.execute([report], messages, "", conversation.available())]
    assert outcome.status == "complete"


@pytest.mark.asyncio
async def test_repeated_full_sections_keep_one_complete_copy_and_full_inspection_evidence():
    from src.generation_tools import ToolConversation
    text = "Original complete risk wording. " * 400
    prompt = json.dumps({"source_id": "S1", "untrusted_complete_original_section": text})
    handler = lambda name, args: {"source_id": "S1", "text": text}
    conversation = ToolConversation([SEARCH], handler, "Risk Summary", supplied_prompt=prompt)
    call = {"id": "inspect", "function": {"name": "search", "arguments": '{"query":"risk"}'}}
    messages = []
    events = [e async for e in conversation.execute([call], messages, "", conversation.available())]
    assert next(e["data"] for e in events if e["type"] == "evidence")["text"] == text
    result = json.loads(messages[-1]["content"])
    assert result["source_id"] == "S1" and result["text_reference"]["characters"] == len(text)
    assert text in json.loads(prompt)["untrusted_complete_original_section"]


def test_null_words_mean_absent_only_where_the_schema_allows_absence():
    from src.tool_arguments import normalize
    schema = {"type": "object", "required": ["outputs", "start_date", "kind"],
              "properties": {"outputs": {"type": "array", "items": {"$ref": "#/$defs/Output"}},
                             "start_date": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                             "kind": {"type": "string"},
                             "section": {"type": "string", "enum": ["mda", "risk_factors"]}},
              "$defs": {"Output": {"type": "object", "required": ["description"],
                                   "properties": {"description": {"type": "string"},
                                                  "end_date": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}}}}}
    args = {"outputs": [{"description": "Revenue", "end_date": "null"}], "start_date": "None", "kind": "null", "section": "null"}
    assert normalize(args, schema) == {"outputs": [{"description": "Revenue"}], "start_date": None, "kind": "null"}


@pytest.mark.asyncio
async def test_malformed_arguments_are_not_echoed_back_to_the_provider():
    from src.generation_tools import ToolConversation
    conversation = ToolConversation([SEARCH], Handler(), "Fixture")
    call = {"id": "bad", "function": {"name": "search", "arguments": '{"query": "x" "y"}'}}
    messages = []
    _ = [e async for e in conversation.execute([call], messages, "", conversation.available())]
    assert messages[0]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert "Expecting" in json.loads(messages[1]["content"])["error"]
