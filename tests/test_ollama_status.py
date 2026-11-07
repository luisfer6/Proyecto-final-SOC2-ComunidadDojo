import asyncio

import httpx
import pytest

from app.assistant import ollama_status
from app.selection import selection_request, selected_narrative


@pytest.mark.parametrize('models,available', [([], False), ([{'name':'qwen3:4b'}], True)])
def test_health_checks_model_presence(monkeypatch, models, available):
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3:4b')
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(**kw, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'models':models}))))
    assert asyncio.run(ollama_status())['ollama_available'] is available


def test_health_model_configured_but_server_offline(monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3:4b')
    original = httpx.AsyncClient
    def offline(request):
        raise httpx.ConnectError('offline', request=request)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(**kw, transport=httpx.MockTransport(offline)))
    status = asyncio.run(ollama_status())
    assert status['ollama_configured'] and not status['ollama_available']


def test_shared_selection_excludes_raw_content_and_rejects_unknown_ids():
    finding = {'id':'H-001','rule':'AUTH-01','severity':'Alto','evidence':['S1-R2'],'title':'Titulo','observation':'sensitive-log-marker'}
    request = selection_request([finding], 'qwen3:4b')
    assert 'sensitive-log-marker' not in str(request)
    assert request['think'] is False
    result = {'findings':[finding],'narrative':{'facts':['base']}}
    with pytest.raises(ValueError, match='inexistentes'):
        selected_narrative(result, {'selected_ids':['H-999']}, 'qwen3:4b')
    assert result['narrative']['facts'] == ['base']
