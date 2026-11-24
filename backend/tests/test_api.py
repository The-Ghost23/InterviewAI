import json
from fastapi.testclient import TestClient
import httpx
import pytest
from app.main import app
from app import provider

client = TestClient(app)


def test_health_is_independent_of_model():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_question_success(monkeypatch):
    async def generate(role, topic, difficulty):
        assert (role, topic, difficulty) == ('Software Engineer', 'Data Structures', 'Beginner')
        return 'How does a stack differ from a queue?'
    monkeypatch.setattr(provider, 'generate_question', generate)
    response = client.post('/api/interview/question', json={})
    assert response.status_code == 200
    assert response.json()['question'] == 'How does a stack differ from a queue?'


@pytest.mark.parametrize('payload', [
    {'role': ' '}, {'topic': 'a'}, {'difficulty': 'Impossible'}, {'role': 'x' * 101}, {'unexpected': True},
])
def test_invalid_preferences(payload):
    assert client.post('/api/interview/question', json=payload).status_code == 422


@pytest.mark.parametrize('error,code', [(provider.ModelUnavailable, 503), (provider.InvalidModelResponse, 502)])
def test_provider_errors(monkeypatch, error, code):
    async def fail(*args):
        raise error('Please retry')
    monkeypatch.setattr(provider, 'generate_question', fail)
    response = client.post('/api/interview/question', json={})
    assert response.status_code == code
    assert response.json()['detail'] == 'Please retry'


def test_cors():
    allowed = client.options('/api/interview/question', headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST',
    })
    assert allowed.headers['access-control-allow-origin'] == 'http://localhost:5173'
    blocked = client.options('/api/interview/question', headers={
        'Origin': 'https://example.com', 'Access-Control-Request-Method': 'POST',
    })
    assert 'access-control-allow-origin' not in blocked.headers


@pytest.mark.parametrize('models,status', [([{'name': 'qwen3:4b'}], 'ready'), ([], 'missing')])
def test_model_status(monkeypatch, models, status):
    async def fake_get(self, url):
        return httpx.Response(200, json={'models': models}, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx.AsyncClient, 'get', fake_get)
    assert client.get('/api/ai/status').json()['status'] == status


def test_model_offline(monkeypatch):
    async def fake_get(*args):
        raise httpx.ConnectError('Offline')
    monkeypatch.setattr(httpx.AsyncClient, 'get', fake_get)
    assert client.get('/api/ai/status').json()['status'] == 'unavailable'


@pytest.mark.parametrize('payload,code', [
    ({'message': {'content': json.dumps({'question': 'Explain a queue.'})}, 'done_reason': 'stop'}, 200),
    ({'message': {'content': ''}}, 502),
    ({'message': {'content': 'Explain'}, 'done_reason': 'length'}, 502),
    ({'bad': 'shape'}, 502),
    ({'message': {'content': json.dumps({'question': 123})}}, 502),
    ({'message': {'content': json.dumps({'question': 'x' * 601})}}, 502),
])
def test_ollama_response_handling(monkeypatch, payload, code):
    async def fake_post(self, url, json):
        assert json['model'] == 'qwen3:4b'
        assert json['think'] is False
        assert json['format']['required'] == ['question']
        assert json['options']['num_ctx'] == 4096
        return httpx.Response(200, json=payload, request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_post)
    assert client.post('/api/interview/question', json={}).status_code == code


def test_ollama_connection_failure(monkeypatch):
    async def fake_post(*args, **kwargs):
        raise httpx.ConnectError('Offline')
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_post)
    assert client.post('/api/interview/question', json={}).status_code == 503
