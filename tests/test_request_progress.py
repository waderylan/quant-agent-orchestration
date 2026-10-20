"""Real Chromium plan card, per-agent sections, reviewed finalization and readable trace."""

import json

import pytest

from tests.test_markdown import page  # noqa: F401  (fixture)

PLAN = {
    "planner": "semantic", "route": "Financial Data → Financial Analysis / Quant → Filings Research → Current Developments",
    "reason": "Calculate supported figures before synthesizing the filing explanation", "companies": ["AMD"], "years": [2024, 2025],
    "outputs": [
        {"id": "R1", "kind": "checked_calculations", "title": "Calculations", "description": "Calculate margins", "owner": "quant", "agent": "Financial Analysis / Quant", "timeframe": None, "assigned": True},
        {"id": "R2", "kind": "filing_explanation", "title": "Explanation from filings", "description": "Explain <script>bad()</script>", "owner": "research", "agent": "Filings Research", "timeframe": None, "assigned": True},
        {"id": "R3", "kind": "public_reaction", "title": "Outside reaction", "description": "Analyst reaction", "owner": "current", "agent": "Current Developments", "timeframe": "reaction", "assigned": True},
    ],
    "steps": [
        {"id": "worker-1", "position": 1, "worker": "data", "agent": "Financial Data", "title": "Reported figures", "output": "financial_inputs", "reason": "Reported figures", "called_by": "Supervisor", "after": [], "serves": [], "feeds": ["worker-2"]},
        {"id": "worker-2", "position": 2, "worker": "quant", "agent": "Financial Analysis / Quant", "title": "Calculations", "output": "checked_calculations", "reason": "Arithmetic", "called_by": "Supervisor", "after": ["worker-1"], "serves": ["R1"], "feeds": ["worker-3"]},
        {"id": "worker-3", "position": 3, "worker": "research", "agent": "Filings Research", "title": "Explanation from filings", "output": "filing_explanation", "reason": "Explain", "called_by": "Supervisor", "after": ["worker-2"], "serves": ["R2"], "feeds": ["worker-4"]},
        {"id": "worker-4", "position": 4, "worker": "current", "agent": "Current Developments", "title": "Outside reaction", "output": "current_developments", "reason": "Outside", "called_by": "Supervisor", "after": ["worker-3"], "serves": ["R3"], "feeds": []},
    ],
}
SECTIONS = {
    "sections": [
        {"id": "worker-3", "worker": "research", "agent": "Filings Research", "label": "From the filings", "labeled": True, "markdown": "Client demand drove the gain [S1].", "removed": []},
        {"id": "worker-4", "worker": "current", "agent": "Current Developments", "label": "Outside research", "labeled": True, "markdown": "Analysts questioned margins [W1].", "removed": ["Unsupported praise."]},
    ],
    "folded": [
        {"id": "worker-1", "worker": "data", "agent": "Financial Data", "reason": "Its figures appear with checked calculations in Financial analysis."},
        {"id": "worker-2", "worker": "quant", "agent": "Financial Analysis / Quant", "reason": "Its calculations are cited in From the filings."},
    ],
    "review": {"status": "partial", "results": [{"id": "R1", "addressed": True}, {"id": "R2", "addressed": True}, {"id": "R3", "addressed": False, "missing": "No named analyst praise"}], "removed_claims": ["Unsupported praise."]},
    "gaps": [{"output": "R3", "text": "No named analyst praise", "source": "Answer Reviewer"}, {"output": None, "text": "Market prices are outside scope", "source": "Supervisor"}],
    "fallback": False,
}


async def run_until_review(page):
    await page.evaluate("""plan => {
      activity.start(); progress.reset(); traceLog.reset();
      event('plan', plan);
      event('activity', {id:'worker-1', agent:'Financial Data', status:'running', task:'Reported figures', elapsed_ms:100});
      event('trace', {agent:'Financial Data', provider:'Codex subscription', model:'fixture-model', reason:'Select observations'});
      event('tool', {name:'query_financials', arguments:{company:'AMD', year:2025, metrics:['revenue','operating_income']}});
    }""", PLAN)


@pytest.mark.asyncio
async def test_sections_stream_per_agent_and_finalize_in_place(page):
    await run_until_review(page)
    assert await page.locator('.step-now').inner_text() == 'Now: Looking up AMD FY2025 revenue, operating income'
    assert 'Step 1 of 4 · Financial Data is working' in await page.locator('#status').inner_text()
    assert 'Model: fixture-model · Codex subscription' in await page.locator('#request-plan').inner_text()
    await page.evaluate("""() => {
      event('draft', {step:'worker-1', agent:'Financial Data', delta:'Inputs '});
      event('draft', {step:'worker-1', agent:'Financial Data', delta:'[F1].'});
      event('draft_final', {step:'worker-1', agent:'Financial Data', markdown:'Inputs [F1].', outcome:'completed', evidence:['F1']});
      event('activity', {id:'worker-1', agent:'Financial Data', status:'completed', elapsed_ms:900});
      event('activity', {id:'worker-3', agent:'Filings Research', status:'running', elapsed_ms:1000});
      event('trace', {agent:'Supervisor', node:'handoff', decision:'Filings Research', evidence:['F1','F2','F3','F4','C1'].map(source_id => ({source_id}))});
      event('draft', {step:'worker-3', agent:'Filings Research', delta:'Client <script>bad()</script> demand [S1].'});
    }""")
    await page.wait_for_function("document.querySelector('[data-step=\"worker-3\"] .section-body').textContent.includes('Client')")
    assert await page.locator('.answer-section').count() == 2
    assert await page.locator('[data-step="worker-1"] h3').inner_text() == 'Inputs for Step 2 · Financial Analysis / Quant'
    assert await page.locator('[data-step="worker-1"] .section-inputs').get_attribute('open') is None
    assert await page.locator('[data-step="worker-3"] .section-badge').inner_text() == 'Draft · writing'
    assert await page.locator('.step-now').inner_text() == 'Now: Writing its answer'
    assert 'Received 5 evidence items: F1–F4, C1' in await page.locator('#request-plan').inner_text()
    await page.evaluate("window.draftNode = document.querySelector('.answer-section[data-step=\"worker-3\"]')")
    await page.evaluate("""() => {
      event('draft_final', {step:'worker-3', agent:'Filings Research', markdown:'Client demand drove the gain [S1].', outcome:'completed', evidence:['S1']});
      event('activity', {id:'worker-3', agent:'Filings Research', status:'completed', elapsed_ms:2000});
      event('activity', {id:'review', agent:'Answer Reviewer', status:'running', elapsed_ms:2100});
    }""")
    assert await page.locator('[data-step="worker-3"] .section-badge').inner_text() == 'Draft · being checked'

    await page.evaluate("""sections => {
      event('answer_sections', sections);
      event('answer', 'Client demand drove the gain [S1].\\n\\nUnresolved outputs:\\n- R3: No named analyst praise');
      event('sources', [{source_id:'S1', kind:'filing_passage', company:'AMD', fiscal_year:2025, form:'10-K', version:'original', section:'mda', inspection_url:'/api/sources/recorded'}]);
      event('activity', {id:'review', agent:'Answer Reviewer', status:'partial', elapsed_ms:2500});
      event('complete', {status:'partial', missing_outputs:['R3: No named analyst praise', 'Market prices are outside scope']});
    }""", SECTIONS)
    # The reviewed text replaced the draft inside the same node, in final order.
    assert await page.evaluate("document.querySelector('#answer .answer-section[data-step=\"worker-3\"]') === window.draftNode")
    assert await page.locator('#answer > .answer-section').evaluate_all('nodes => nodes.map(n => n.dataset.step)') == ['worker-3', 'worker-4']
    assert await page.locator('[data-step="worker-3"] .section-badge').inner_text() == 'Reviewed'
    assert await page.locator('[data-step="worker-4"] .section-badge').inner_text() == 'Reviewed · gap noted above'
    removed = page.locator('[data-step="worker-4"] .section-removed')
    assert await removed.locator('summary').inner_text() == '1 sentence removed by the Answer Reviewer'
    assert await removed.locator('del').text_content() == 'Unsupported praise.'
    drafts = page.locator('#intermediate-drafts')
    assert await drafts.locator(':scope > summary').inner_text() == 'Intermediate drafts (1)'
    assert 'Its figures appear with checked calculations' in await drafts.text_content()

    # The answer opens with one banner that names it final and explains each gap once.
    summary = page.locator('#answer > .final-summary')
    assert await page.locator('#answer > *').first.get_attribute('class') == 'final-summary'
    assert await summary.locator('h3').inner_text() == 'Final answer · partly complete'
    assert await summary.locator('.final-gaps > li > strong').all_text_contents() == ['Part 3 · Outside reaction', 'Other limits']
    assert await summary.locator('.gap-kind').all_text_contents() == ['Not fully answered', 'Outside what this tool covers']
    assert await summary.locator('.gap-text').all_text_contents() == ['No named analyst praise', 'Market prices are outside scope']
    assert 'checked this part against its cited sources' in await summary.locator('[data-output="R3"] .gap-why').inner_text()
    assert await page.locator('[data-output="R3"] .part-status').inner_text() == 'Gap noted · see answer'
    assert await page.locator('[data-output="R1"] .part-status').inner_text() == 'Confirmed'
    assert 'No named analyst praise' not in await page.locator('#request-plan').inner_text()
    assert 'Unresolved outputs' not in await page.locator('#answer').inner_text()
    assert 'Still needed' not in await page.locator('#scope-help').inner_text()
    assert await page.locator('#status').inner_text() == "Final answer ready · 2 notes on what's missing"
    assert await page.locator('.agent-call', has_text='Answer Reviewer').locator('.agent-status').inner_text() == 'Found a gap'
    assert not await page.locator('#answer script, #request-plan script').count()

    await page.locator('[data-step="worker-3"] .section-body a').click()
    await page.wait_for_function("document.getElementById('passage').textContent.includes('150.25')")
    await page.locator('#intermediate-drafts > summary').click()
    await page.locator('[data-step="worker-1"] .agent-chip').click()
    assert await page.locator('.agent-call[data-call="worker-1"]').get_attribute('aria-expanded') == 'true'

    await page.locator('details:has(#trace) > summary').click()
    handoff = page.locator('#trace summary', has_text='handoff → Filings Research · 5 evidence items (F1–F4, C1)')
    await handoff.click()
    assert '"node": "handoff"' in await page.locator('#trace pre').inner_text()
    assert await page.locator('#trace summary', has_text='Codex subscription · fixture-model').count() == 1
    async with page.expect_download() as info:
        await page.locator('#trace-download').click()
    raw = json.loads(open(await (await info.value).path(), encoding='utf-8').read())
    assert [e['type'] for e in raw].count('draft') == 3 and raw[0]['type'] == 'plan'

    await page.set_viewport_size({'width': 390, 'height': 844})
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')


@pytest.mark.asyncio
async def test_stream_without_reviewed_sections_keeps_the_latest_answer_marked_unreviewed(page):
    await run_until_review(page)
    await page.evaluate("""() => {
      event('draft', {step:'worker-1', agent:'Financial Data', delta:'Partial inputs [F1].'});
      event('answer', 'Latest supervisor answer.');
      event('complete', {status:'partial'});
    }""")
    final = page.locator('#answer > .answer-section[data-step="unreviewed"]')
    assert await final.locator('.section-body').inner_text() == 'Latest supervisor answer.'
    assert await final.locator('.section-badge').inner_text() == 'Not reviewed · review unavailable'
    assert 'was not checked' in await page.locator('#answer > .final-summary').inner_text()
    assert await page.locator('#intermediate-drafts .answer-section[data-step="worker-1"]').count() == 1
