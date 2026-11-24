from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app import main, provider
from app.sessions import SessionRequest, SessionStore


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, 'store', SessionStore())
    with TestClient(main.app) as client:
        yield client


def test_create_and_reopen_preserves_preferences_and_question(client, monkeypatch):
    calls = []
    async def generate(role, topic, difficulty):
        calls.append((role, topic, difficulty))
        return 'How does Python handle concurrent I/O?'
    monkeypatch.setattr(provider, 'generate_question', generate)
    response = client.post('/api/interviews', json={
        'role': ' Backend Engineer ', 'topic': 'Python', 'difficulty': 'Intermediate', 'question_count': 3,
    })
    assert response.status_code == 201
    session = response.json()
    assert session['role'] == 'Backend Engineer'
    assert session['topic'] == 'Python'
    assert session['difficulty'] == 'Intermediate'
    assert session['question_count'] == 3
    assert session['question_number'] == 1
    assert session['question'] == 'How does Python handle concurrent I/O?'
    assert session['model'] == 'qwen3:4b'
    assert session['created_at']
    assert client.get(f"/api/interviews/{session['id']}").json() == session
    assert calls == [('Backend Engineer', 'Python', 'Intermediate')]


def test_sessions_have_unique_ids_and_independent_settings(client, monkeypatch):
    async def generate(*args):
        return 'Explain a queue.'
    monkeypatch.setattr(provider, 'generate_question', generate)
    first = client.post('/api/interviews', json={}).json()
    second = client.post('/api/interviews', json={'question_count': 10, 'topic': 'DBMS'}).json()
    assert first['id'] != second['id']
    assert first['question_count'] == 5
    assert client.get(f"/api/interviews/{first['id']}").json()['topic'] == 'Data Structures'
    assert client.get(f"/api/interviews/{second['id']}").json()['topic'] == 'DBMS'


@pytest.mark.parametrize('payload', [
    {'question_count': 0}, {'question_count': 11}, {'question_count': 3.5},
    {'question_count': True}, {'question_count': '5'}, {'role': ' '},
    {'topic': 'a'}, {'difficulty': 'Expert'}, {'unknown': 'value'},
])
def test_session_validation_prevents_generation(client, monkeypatch, payload):
    async def unexpected(*args):
        pytest.fail('Invalid input must not call the model')
    monkeypatch.setattr(provider, 'generate_question', unexpected)
    assert client.post('/api/interviews', json=payload).status_code == 422
    assert not main.store._sessions


@pytest.mark.parametrize('error,code', [(provider.ModelUnavailable, 503), (provider.InvalidModelResponse, 502)])
def test_failed_generation_does_not_create_session(client, monkeypatch, error, code):
    async def fail(*args):
        raise error('Please retry')
    monkeypatch.setattr(provider, 'generate_question', fail)
    assert client.post('/api/interviews', json={}).status_code == code
    assert not main.store._sessions


def test_unknown_and_invalid_session_ids(client):
    assert client.get(f'/api/interviews/{uuid4()}').status_code == 404
    assert client.get('/api/interviews/not-a-uuid').status_code == 422


def test_sessions_expire():
    store = SessionStore(ttl=timedelta(seconds=-1))
    session = store.create(SessionRequest(), 'Explain a queue.', 'qwen3:4b')
    assert store.get(session.id) is None
    assert not store._sessions


def test_store_limits_retained_sessions():
    store = SessionStore(capacity=1)
    old = store.create(SessionRequest(), 'First?', 'qwen3:4b')
    current = store.create(SessionRequest(), 'Second?', 'qwen3:4b')
    assert store.get(old.id) is None
    assert store.get(current.id) == current
