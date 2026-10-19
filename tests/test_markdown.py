"""Real Chromium rendering of untrusted Markdown and registered citations."""

from urllib.parse import urlsplit

import httpx
import pytest
import pytest_asyncio
from playwright.async_api import async_playwright

from main import app


@pytest_asyncio.fixture
async def page():
    errors, unexpected = [], []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://markdown.test") as client, async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def local_route(route):
            path = urlsplit(route.request.url).path
            if path == "/api/coverage":
                await route.fulfill(json={"QCOM": [2025]})
            elif path == "/api/sources/recorded":
                await route.fulfill(json={"kind": "filing_passage", "text": "150.25", "context": "150.25", "start": 0, "context_start": 0})
            elif path == "/api/live/recorded":
                await route.fulfill(json={"kind": "live_source", "payload": {}})
            elif path == "/" or path.startswith("/static/vendor/"):
                response = await client.get(path)
                assert response.status_code == 200
                await route.fulfill(status=response.status_code, content_type=response.headers["content-type"], body=response.content)
            else:
                unexpected.append(route.request.url)
                await route.abort()

        await page.route("**/*", local_route)
        await page.goto("http://markdown.test")
        await page.wait_for_function("typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined'")
        yield page
        await browser.close()
    assert not errors
    assert not unexpected, "Markdown must not load remote content"


@pytest.mark.asyncio
async def test_request_checklist_and_completion_are_separate_from_citation_registration(page):
    await page.evaluate("""() => {
      event('trace', {node:'request_understanding', plan:{outputs:[{id:'R1',description:'Filing explanation'},{id:'R2',description:'Outside reaction <script>bad()</script>'}]}});
      event('trace', {node:'answer_coverage', results:[{id:'R1',addressed:true},{id:'R2',addressed:false}]});
      event('complete', {status:'partial',verified_citations:true});
    }""")
    assert await page.locator('#request-coverage li').all_text_contents() == ['Addressed: Filing explanation', 'Still needed: Outside reaction <script>bad()</script>']
    assert not await page.locator('#request-coverage script').count()
    assert 'Partial answer' in await page.locator('#status').inner_text()


@pytest.mark.asyncio
async def test_markdown_streams_and_replaces_answers_with_normal_formatting(page):
    await page.evaluate("""() => event('token', '# Overview\\n\\n**Strong** and *emphasis* with `EPS`.\\n\\n- First\\n  - Nested\\n\\n1. Ordered\\n\\n> Dated evidence\\n\\n```python\\nvalue = 180\\n```\\n\\n| Company | Price |\\n|---|---:|\\n| QCOM | **150.25** |')""")
    await page.wait_for_selector("#answer table strong")
    assert await page.locator("#answer h1").inner_text() == "Overview"
    assert await page.locator("#answer p strong").inner_text() == "Strong"
    assert await page.locator("#answer em").inner_text() == "emphasis"
    assert await page.locator("#answer ul ul li").inner_text() == "Nested"
    assert await page.locator("#answer ol li").inner_text() == "Ordered"
    assert await page.locator("#answer blockquote").inner_text() == "Dated evidence"
    assert "value = 180" in await page.locator("#answer pre code").inner_text()
    await page.evaluate("""() => { event('answer', '## Final\\n\\nA **replacement**, not appended text.'); event('complete', {status:'completed'}); }""")
    assert await page.locator("#answer h2").inner_text() == "Final"
    assert await page.locator("#answer strong").inner_text() == "replacement"
    assert not await page.locator("#answer table").count()


@pytest.mark.asyncio
async def test_citations_survive_rerenders_and_cannot_be_redirected(page):
    await page.evaluate("""() => {
      event('answer', '**Evidence [W1]**; [W1](https://evil.test/forged). `Example [W1]`.\\n\\n| Source | Value |\\n|---|---|\\n| [W1] | dated event |');
      const sources = [{source_id:'W1',kind:'live_source',publisher:'qualcomm.com',published_date:'2026-10-18',source_tier:'official',retrieved_at:'2026-10-19',text:'Dated event <script>attack</script>',url:'https://qualcomm.com/event',company:'QCOM',inspection_url:'/api/live/recorded'}];
      event('sources', sources); event('sources', sources);
    }""")
    links = page.locator("#answer a")
    assert await links.count() == 3
    assert all([await link.get_attribute("href") == "/api/live/recorded" for link in await links.all()])
    assert await page.locator("#answer table tr").count() == 2
    assert await page.locator("#answer code").inner_text() == "Example [W1]"
    await links.first.click()
    await page.wait_for_function("document.getElementById('passage').textContent.includes('Dated event')")
    assert not await page.locator("#passage script").count()
    assert "qualcomm.com · 2026-10-18 · Primary source · Retrieved 2026-10-19" in await page.locator("#source-label").inner_text()
    external = page.locator("#source-label a")
    assert await external.get_attribute("target") == "_blank"
    assert await external.get_attribute("rel") == "noopener noreferrer"


@pytest.mark.asyncio
async def test_markdown_blocks_html_unsafe_urls_and_remote_images(page):
    await page.evaluate("""() => {
      event('answer', '<script>window.__attack=1<\\/script>\\n\\n<img src="https://evil.test/pixel" onerror="window.__attack=1">\\n\\n[unsafe](javascript:window.__attack=1) [data](data:text/html,attack) [broken](http://[) [source](https://example.org/filing)\\n\\n![tracking](https://evil.test/image)\\n\\n```html\\n<img onerror=window.__attack=1>\\n```');
      event('complete', {status:'completed'});
    }""")
    assert not await page.locator("#answer script, #answer img, #answer iframe").count()
    assert not await page.evaluate("Boolean(window.__attack)")
    for label in ("unsafe", "data", "broken"):
        assert await page.locator("#answer a").filter(has_text=label).get_attribute("href") is None
    external = page.locator('#answer a[href="https://example.org/filing"]')
    assert await external.get_attribute("rel") == "noopener noreferrer"
    assert await external.get_attribute("target") == "_blank"
    assert "<img onerror" in await page.locator("#answer pre code").inner_text()
