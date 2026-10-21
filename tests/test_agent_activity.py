"""Real Chromium activity state, timing, source inspection and cancellation."""

import pytest

from tests.test_markdown import page


@pytest.mark.asyncio
async def test_repeated_invocations_keep_timing_selection_and_sources_in_sync(page):
    await page.evaluate("""() => {
      activity.start();
      event('activity', {id:'worker-1', agent:'Filings Research', status:'running', task:'Inspect filing', elapsed_ms:100});
      event('trace', {agent:'Filings Research',provider:'Local subscription',model:'fixture-model'});
      event('tool', {name:'inspect_source'});
      event('activity', {id:'worker-1', agent:'Filings Research', status:'completed', elapsed_ms:1100});
      event('activity', {id:'worker-2', agent:'Filings Research', status:'running', task:'Follow-up <script>bad()</script>', elapsed_ms:1100});
      event('activity', {id:'worker-2', agent:'Filings Research', status:'partial', elapsed_ms:3100, sources:[{source_id:'S2',kind:'filing_passage',inspection_url:'/api/sources/recorded'}]});
      event('complete', {status:'partial'});
    }""")
    calls = page.locator('.agent-call')
    assert await calls.count() == 2
    assert await calls.locator('.agent-duration').all_text_contents() == ['1.0s', '2.0s']
    assert await calls.locator('.agent-status').all_text_contents() == ['Complete', 'Evidence gap']
    await page.locator('#timeline summary').click()
    bars = page.locator('.timeline-bar')
    assert await bars.count() == 2
    assert await bars.nth(1).evaluate('e => parseFloat(e.style.left)') == pytest.approx(1100/3100*100, abs=1)
    assert await bars.nth(0).evaluate('e => getComputedStyle(e).backgroundColor') == await bars.nth(1).evaluate('e => getComputedStyle(e).backgroundColor')
    await page.get_by_role('button', name='Filings Research, Evidence gap', exact=True).click()
    assert await calls.nth(1).get_attribute('aria-expanded') == 'true'
    assert 'Follow-up <script>bad()</script>' in await page.locator('#agent-details').inner_text()
    assert not await page.locator('#agent-details script').count()
    await page.locator('.activity-source').click()
    await page.wait_for_function("document.getElementById('passage').textContent.includes('150.25')")
    await calls.nth(0).click()
    assert 'fixture-model' in await page.locator('#agent-details').inner_text()
    assert 'inspect_source' in await page.locator('#agent-details').inner_text()
    await calls.nth(0).focus()
    await page.evaluate("event('activity', {id:'review',agent:'Answer Reviewer',status:'running',elapsed_ms:3100})")
    assert await page.evaluate("document.activeElement.dataset.call") == 'worker-1'
    await page.evaluate("activity.finish('stopped')")


@pytest.mark.asyncio
async def test_provider_route_attaches_to_its_invocation_during_review(page):
    await page.evaluate("""() => {
      activity.start();
      event('activity', {id:'worker-1',agent:'Filings Research',status:'running',elapsed_ms:0});
      event('activity', {id:'review',agent:'Answer Reviewer',status:'running',elapsed_ms:100});
      event('trace', {node:'provider_route',activity_id:'worker-1',agent:'Filings Research',
        provider:'nebius',model:'DeepSeek-V4-Flash',reason:'Comparison across fiscal years'});
      event('complete', {status:'completed'});
    }""")
    await page.locator('.agent-call').first.click()
    details = await page.locator('#agent-details').inner_text()
    assert 'nebius' in details and 'DeepSeek-V4-Flash' in details and 'Comparison across fiscal years' in details
    await page.locator('.agent-call').nth(1).click()
    assert 'DeepSeek-V4-Flash' not in await page.locator('#agent-details').inner_text()


@pytest.mark.asyncio
async def test_profile_switch_submits_selection_and_uses_shared_model_details(page):
    requests = []
    async def chat(route):
        body = route.request.post_data_json
        requests.append(body)
        model = 'nvidia/hosted-model' if body['generation_profile'] == 'api' else 'codex-model'
        import json
        frames = [('activity', {'id': 'worker', 'agent': 'Financial Data', 'status': 'running'}),
                  ('trace', {'node': 'provider_route', 'activity_id': 'worker', 'provider': body['generation_profile'], 'model': model, 'reason': 'Selected models'}),
                  ('activity', {'id': 'worker', 'agent': 'Financial Data', 'status': 'completed'}),
                  ('complete', {'status': 'completed'})]
        await route.fulfill(content_type='text/event-stream', body=''.join(
            'event: ' + kind + '\ndata: ' + json.dumps(data) + '\n\n' for kind, data in frames))
    await page.route('**/api/chat', chat)
    await page.wait_for_function("!document.getElementById('generation-profile').disabled")
    await page.locator('#question').fill('Show reported revenue')
    for profile, model in [('codex', 'codex-model'), ('api', 'nvidia/hosted-model')]:
        await page.locator('#generation-profile').select_option(profile)
        await page.locator('#ask').click()
        await page.wait_for_function("!document.getElementById('ask').disabled")
        await page.locator('.agent-call').click()
        assert model in await page.locator('#agent-details').inner_text()
    assert [body['generation_profile'] for body in requests] == ['codex', 'api']


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['stopped', 'failed', 'unverified'])
async def test_interrupted_activity_freezes_and_next_request_resets(page, status):
    await page.evaluate("""status => {
      activity.start();
      event('activity', {id:'worker-1',agent:'Financial Data',status:'running',elapsed_ms:0});
      activity.finish(status);
    }""", status)
    assert await page.locator('#agent-activity li').get_attribute('data-status') == status
    frozen = await page.locator('.agent-duration').inner_text()
    await page.wait_for_timeout(350)
    assert await page.locator('.agent-duration').inner_text() == frozen
    await page.evaluate('activity.start()')
    assert not await page.locator('.agent-call').count()
    assert await page.locator('#agent-activity').inner_text() == 'Waiting'
    assert await page.locator('#agent-details').is_hidden()
    await page.evaluate("activity.finish('stopped')")


@pytest.mark.asyncio
async def test_activity_layout_fits_a_phone_and_uses_labeled_distinct_colors(page):
    await page.set_viewport_size({'width': 390, 'height': 844})
    await page.emulate_media(reduced_motion='reduce')
    await page.evaluate("""() => {
      activity.start();
      Object.keys(AgentActivity.colors).forEach((agent, i) => {
        event('activity', {id:String(i),agent,status:'running',elapsed_ms:i*1000});
        event('activity', {id:String(i),agent,status:'completed',elapsed_ms:(i+1)*1000});
      });
      event('complete', {status:'completed'});
    }""")
    assert await page.locator('.agent-name').count() == 5
    colors = await page.locator('.agent-name').evaluate_all('nodes => nodes.map(e => getComputedStyle(e).color)')
    assert len(set(colors)) == 5
    await page.locator('#timeline summary').click()
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert await page.locator('#activity-panel').evaluate('e => e.getBoundingClientRect().top') < await page.locator('.answer-panel').evaluate('e => e.getBoundingClientRect().top')
