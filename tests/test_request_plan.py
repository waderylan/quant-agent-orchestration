"""Request coverage stays independent of worker selection and citation presence."""

import pytest

from src.request_plan import decompose, coverage, remove_unsupported
from src.research_workflow import events
from tests.test_supervisor import source


def test_repair_removes_a_partial_unsupported_claim_as_a_sentence():
    answer = 'Analysts raised concentration concerns. [W1]\nDemand was strong, while an unsupported forecast was asserted. This suggests execution risk. [W1]'
    repaired = remove_unsupported(answer, ['an unsupported forecast was asserted'])
    assert repaired == 'Analysts raised concentration concerns. [W1]\nThis suggests execution risk. [W1]'


@pytest.mark.parametrize('prefix', ['Qualcomm Inc.', 'The U.S. company'])
def test_repair_keeps_abbreviations_inside_the_removed_sentence(prefix):
    answer = prefix + ' reported an unsupported acquisition completion. Supported revenue [F1].'
    assert remove_unsupported(answer, ['an unsupported acquisition completion']) == 'Supported revenue [F1].'


@pytest.mark.asyncio
async def test_review_requires_explicit_omission_and_claim_checks():
    async def model(prompt, tools, handler, **kwargs):
        handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': True, 'citations': ['S1'], 'missing': ''}]})
        yield {'type': 'token', 'data': ''}
    with pytest.raises(ValueError, match='missing_requests'):
        await coverage('Explain filings', [{'id': 'R1', 'kind': 'filing_explanation', 'description': 'Explain filings'}], 'Filed fact [S1].', {'S1': source('S1')}, model, lambda e: None)


@pytest.mark.asyncio
async def test_decomposition_preserves_the_casual_external_reaction_clause():
    async def model(prompt, tools, handler, **kwargs):
        assert 'public thought' in prompt
        handler('submit_plan', {'outputs': [{'kind': 'filing_explanation', 'description': 'Explain revenue change'}, {'kind': 'public_reaction', 'description': 'Research outside reaction'}], 'timeframe': 'reaction', 'start_date': None, 'end_date': None})
        yield {'type': 'token', 'data': ''}
    plan = await decompose({'question': 'explain qualcomms revenue change then research what the public thought', 'companies': ['QCOM'], 'years': [2024, 2025]}, model, lambda e: None)
    assert [o['kind'] for o in plan['outputs']] == ['filing_explanation', 'public_reaction']
    assert [o['id'] for o in plan['outputs']] == ['R1', 'R2']


@pytest.mark.asyncio
async def test_reviewer_cannot_confirm_external_reaction_with_only_a_filing_citation():
    async def model(prompt, tools, handler, **kwargs):
        handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': True, 'citations': ['S1'], 'missing': ''}], 'missing_requests': [], 'unsupported_claims': []})
        yield {'type': 'token', 'data': ''}
    outputs = [{'id': 'R1', 'kind': 'public_reaction', 'description': 'Outside reaction'}]
    result = await coverage('What did people think?', outputs, 'Management described growth [S1].', {'S1': source()}, model, lambda e: None)
    assert result['missing'] == ['Outside reaction: Not supported in the answer']


@pytest.mark.asyncio
async def test_supervisor_retains_an_unanswered_output_even_when_workers_finish(monkeypatch):
    monkeypatch.setenv('REQUEST_PLANNER', 'semantic')
    class Index:
        def coverage(self):
            return {'QCOM': [2025]}
    async def model(prompt, tools, handler, **kwargs):
        if kwargs['agent'] == 'Request Planner':
            handler('submit_plan', {'outputs': [{'kind': 'filing_explanation', 'description': 'Explain growth'}, {'kind': 'public_reaction', 'description': 'Outside reaction'}], 'timeframe': 'reaction', 'start_date': None, 'end_date': None})
        else:
            handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': True, 'citations': ['S1'], 'missing': ''}, {'id': 'R2', 'addressed': False, 'citations': [], 'missing': 'No outside viewpoints established'}], 'missing_requests': [], 'unsupported_claims': []})
        yield {'type': 'token', 'data': ''}
    async def research(state, writer):
        return {'answer': 'Filed explanation [S1].', 'research_sources': {'S1': source(company='QCOM')}}
    async def current(state, writer):
        assert state['request_plan']['timeframe'] == 'reaction'
        return {'answer': 'Company announcement [W1].', 'live_sources': {'W1': {'source_id': 'W1', 'kind': 'live_source', 'company': 'QCOM', 'text': 'Company announcement', 'url': 'https://qualcomm.com/fixture'}}}
    result = [e async for e in events(Index(), 'Explain Qualcomm growth then research what the public thought', ['QCOM'], [2025], model_stream=model, worker_overrides={'research': research, 'current': current})]
    assert result[-1]['data']['status'] == 'partial'
    assert any('Outside reaction' in gap for gap in result[-1]['data']['missing_outputs'])
    selection = next(e['data'] for e in result if e['type'] == 'trace' and e['data'].get('node') == 'task_selection')
    assert selection['task']['required_workers'] == ['research', 'current']


@pytest.mark.asyncio
async def test_composition_preserves_calculations_without_repeating_the_quant_brief():
    class Index:
        def coverage(self):
            return {'QCOM': [2024, 2025]}
    async def data(state, writer):
        return {'answer': 'Inputs [F1].', 'financial_sources': {'F1': source()}}
    async def quant(state, writer):
        return {'answer': 'Quant-only boilerplate and growth [C1].', 'analysis_sources': {'C1': source('C1')}}
    async def research(state, writer):
        return {'answer': 'Growth and its filed drivers [C1][S1].', 'research_sources': {'S1': source('S1')}}
    async def current(state, writer):
        return {'answer': 'Outside development [W1].', 'live_sources': {'W1': source('W1')}}
    result = [e async for e in events(Index(), 'Explain Qualcomm revenue change and what has happened since the filing', ['QCOM'], [2024, 2025], worker_overrides={'data': data, 'quant': quant, 'research': research, 'current': current})]
    answer = next(e['data'] for e in reversed(result) if e['type'] == 'answer')
    assert 'Quant-only boilerplate' not in answer and '[C1]' in answer
    assert 'From the filings:' in answer and 'Outside research:' in answer


@pytest.mark.asyncio
async def test_reviewer_reads_late_cited_evidence_and_reports_an_unplanned_clause():
    async def model(prompt, tools, handler, **kwargs):
        assert 'Independent analyst explained the reaction' in prompt
        assert 'Focused second extraction supports the explanation' in prompt
        assert 'Unused candidate' not in prompt
        handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': True, 'citations': ['W1'], 'missing': ''}], 'missing_requests': ['The separate official verification was omitted'], 'unsupported_claims': []})
        yield {'type': 'token', 'data': ''}
    result = await coverage('Explain reactions and verify the official update', [{'id': 'R1', 'kind': 'public_reaction', 'description': 'Outside reaction'}], 'Reaction [W1].', {'W1': {**source('W1'), 'text': 'Context. ' * 300 + 'Independent analyst explained the reaction', 'observations': [{'text': 'Focused second extraction supports the explanation'}]}, 'W2': {**source('W2'), 'text': 'Unused candidate'}}, model, lambda e: None)
    assert result['missing'] == ['The separate official verification was omitted']


@pytest.mark.asyncio
async def test_unsupported_claim_is_removed_from_authoritative_answer(monkeypatch):
    monkeypatch.setenv('REQUEST_PLANNER', 'semantic')
    class Index:
        def coverage(self):
            return {'QCOM': [2025]}
    unsupported = 'The acquisition has already doubled revenue. [W1]'
    async def model(prompt, tools, handler, **kwargs):
        if kwargs['agent'] == 'Request Planner':
            handler('submit_plan', {'outputs': [{'kind': 'current_developments', 'description': 'Acquisition update'}], 'timeframe': 'recent', 'start_date': None, 'end_date': None})
        else:
            handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': False, 'citations': ['W1'], 'missing': 'Revenue effect not established'}], 'missing_requests': [], 'unsupported_claims': [unsupported]})
        yield {'type': 'token', 'data': ''}
    async def current(state, writer):
        return {'answer': 'An acquisition was announced. [W1]\n\n' + unsupported, 'live_sources': {'W1': source('W1')}}
    result = [e async for e in events(Index(), 'Qualcomm acquisition update lately', ['QCOM'], [2025], model_stream=model, worker_overrides={'current': current})]
    answer = next(e['data'] for e in reversed(result) if e['type'] == 'answer')
    assert unsupported not in answer and 'An acquisition was announced. [W1]' in answer
    assert result[-1]['data']['status'] == 'partial'


@pytest.mark.asyncio
async def test_casual_capability_question_does_not_invoke_a_research_worker(monkeypatch):
    monkeypatch.setenv('REQUEST_PLANNER', 'semantic')
    class Index:
        def coverage(self):
            return {'QCOM': [2025]}
    async def model(prompt, tools, handler, **kwargs):
        if kwargs['agent'] == 'Request Planner':
            handler('submit_plan', {'outputs': [{'kind': 'capabilities', 'description': 'Explain application source access'}], 'timeframe': 'recent', 'start_date': None, 'end_date': None})
        else:
            handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': True, 'citations': [], 'missing': ''}], 'missing_requests': [], 'unsupported_claims': []})
        yield {'type': 'token', 'data': ''}
    async def forbidden(state, writer):
        raise AssertionError('A local capability answer invoked an external worker')
    result = [e async for e in events(Index(), 'do u actually look online or just read saved reports', ['QCOM'], [2025], model_stream=model, worker_overrides={'research': forbidden, 'current': forbidden})]
    selection = next(e['data'] for e in result if e['type'] == 'trace' and e['data'].get('node') == 'task_selection')
    assert selection['task']['required_workers'] == []
    assert result[-1]['data'] == {'status': 'completed', 'verified_citations': False, 'coverage_checked': True}


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['research', 'look up'])
async def test_capability_prefix_cannot_swallow_a_casual_research_clause(monkeypatch, action):
    monkeypatch.setenv('REQUEST_PLANNER', 'semantic')
    class Index:
        def coverage(self):
            return {'QCOM': [2025]}
    async def model(prompt, tools, handler, **kwargs):
        if kwargs['agent'] == 'Request Planner':
            assert 'Qualcomm acquisitions lately' in prompt
            handler('submit_plan', {'outputs': [{'kind': 'capabilities', 'description': 'Describe app'}, {'kind': 'current_developments', 'description': 'Acquisitions'}], 'timeframe': 'recent', 'start_date': None, 'end_date': None})
        else:
            handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': True, 'citations': [], 'missing': ''}, {'id': 'R2', 'addressed': True, 'citations': ['W1'], 'missing': ''}], 'missing_requests': [], 'unsupported_claims': []})
        yield {'type': 'token', 'data': ''}
    async def current(state, writer):
        return {'answer': 'Acquisition update [W1].', 'live_sources': {'W1': source('W1')}}
    result = [e async for e in events(Index(), f'What can you do and {action} Qualcomm acquisitions lately?', ['QCOM'], [2025], model_stream=model, worker_overrides={'current': current})]
    answer = next(e['data'] for e in reversed(result) if e['type'] == 'answer')
    assert '**Scope:**' in answer and 'Acquisition update [W1]' in answer
    assert result[-1]['data']['status'] == 'completed'


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled', [False, True])
async def test_official_check_can_share_a_mixed_request_but_respects_no_web(monkeypatch, disabled):
    monkeypatch.setenv('REQUEST_PLANNER', 'semantic')
    class Index:
        def coverage(self):
            return {'QCOM': [2025]}
    async def model(prompt, tools, handler, **kwargs):
        if kwargs['agent'] == 'Request Planner':
            handler('submit_plan', {'outputs': [{'kind': 'official_update', 'description': 'Verify filed update'}, {'kind': 'current_developments', 'description': 'Recent news'}], 'timeframe': 'recent', 'start_date': None, 'end_date': None})
        else:
            handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': False, 'citations': [], 'missing': 'Fixture has no update'}, {'id': 'R2', 'addressed': False, 'citations': [], 'missing': 'Fixture has no news'}], 'missing_requests': [], 'unsupported_claims': []})
        yield {'type': 'token', 'data': ''}
    async def research(state, writer):
        assert state['live_check'] is not disabled
        return {'answer': 'Filed statement [S1].', 'research_sources': {'S1': source('S1')}}
    async def current(state, writer):
        assert not disabled
        return {'answer': 'No current findings', 'partial': True}
    result = [e async for e in events(Index(), 'Verify Qualcomm official update and recent news' + ('; no web search' if disabled else ''), ['QCOM'], [2025], model_stream=model, worker_overrides={'research': research, 'current': current})]
    assert result[-1]['data']['status'] == 'partial'


@pytest.mark.asyncio
@pytest.mark.parametrize('hard_gap', [False, True])
async def test_full_coverage_can_clear_model_doubt_but_not_a_structural_gap(monkeypatch, hard_gap):
    monkeypatch.setenv('REQUEST_PLANNER', 'semantic')
    class Index:
        def coverage(self):
            return {'QCOM': [2025]}
    async def model(prompt, tools, handler, **kwargs):
        if kwargs['agent'] == 'Request Planner':
            handler('submit_plan', {'outputs': [{'kind': 'current_developments', 'description': 'Recent developments'}], 'timeframe': 'recent', 'start_date': None, 'end_date': None})
        else:
            handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': True, 'citations': ['W1'], 'missing': ''}], 'missing_requests': [], 'unsupported_claims': []})
        yield {'type': 'token', 'data': ''}
    async def current(state, writer):
        return {'answer': 'Reported development [W1].', 'live_sources': {'W1': source('W1')}, 'partial': True, 'missing_outputs': ['Model requested unnecessary corroboration'] + (['No dated source in the requested window'] if hard_gap else []), 'reported_missing_outputs': ['Model requested unnecessary corroboration']}
    result = [e async for e in events(Index(), 'What has happened at Qualcomm lately?', ['QCOM'], [2025], model_stream=model, worker_overrides={'current': current})]
    assert result[-1]['data']['status'] == ('partial' if hard_gap else 'completed')
    assert 'Model requested unnecessary corroboration' not in result[-1]['data'].get('missing_outputs', [])


@pytest.mark.asyncio
async def test_derived_answer_review_receives_its_inputs_without_printing_them():
    async def model(prompt, tools, handler, **kwargs):
        assert 'Reported revenue input' in prompt and 'Reported gross profit input' in prompt
        handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': True, 'citations': ['C1', 'F1', 'F2'], 'missing': ''}], 'missing_requests': [], 'unsupported_claims': []})
        yield {'type': 'token', 'data': ''}
    result = await coverage('What was gross margin?', [{'id': 'R1', 'kind': 'checked_calculations', 'description': 'Gross margin'}], 'Gross margin was 50% [C1].', {'C1': {**source('C1'), 'source_ids': ['F1', 'F2']}, 'F1': {**source('F1'), 'text': 'Reported revenue input'}, 'F2': {**source('F2'), 'text': 'Reported gross profit input'}}, model, lambda e: None)
    assert not result['missing']


@pytest.mark.asyncio
@pytest.mark.parametrize('historical', [False, True])
async def test_calendar_year_scope_is_independent_but_filing_year_scope_is_enforced(monkeypatch, historical):
    monkeypatch.setenv('REQUEST_PLANNER', 'semantic')
    class Index:
        def coverage(self):
            return {'QCOM': [2025]}
    async def model(prompt, tools, handler, **kwargs):
        if kwargs['agent'] == 'Request Planner':
            handler('submit_plan', {'outputs': [{'kind': 'filing_explanation' if historical else 'current_developments', 'description': 'Requested research'}], 'timeframe': 'recent', 'start_date': None, 'end_date': None})
        else:
            handler('submit_coverage', {'results': [{'id': 'R1', 'addressed': True, 'citations': ['W1'], 'missing': ''}], 'missing_requests': [], 'unsupported_claims': []})
        yield {'type': 'token', 'data': ''}
    async def current(state, writer):
        return {'answer': 'Calendar-year event [W1].', 'live_sources': {'W1': source('W1')}}
    result = [e async for e in events(Index(), 'Explain Qualcomm FY2026 filing strategy' if historical else 'What happened at Qualcomm in summer 2026?', ['QCOM'], [2025], model_stream=model, worker_overrides={'current': current})]
    assert result[-1]['data']['status'] == ('coverage_gap' if historical else 'completed')
