from uuid import UUID, uuid4
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi.testclient import TestClient
from app import main, auth, provider
from app.config import settings
from app.sessions import SessionStore, SessionRequest

A = UUID('11111111-1111-4111-8111-111111111111')
B = UUID('22222222-2222-4222-8222-222222222222')

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, 'store', SessionStore())
    old = dict(main.app.dependency_overrides)
    main.app.dependency_overrides.clear()
    with TestClient(main.app) as client: yield client
    main.app.dependency_overrides.clear()
    main.app.dependency_overrides.update(old)


def test_all_sensitive_routes_require_sign_in(client, monkeypatch):
    generate = AsyncMock()
    monkeypatch.setattr(provider, 'generate_question', generate)
    id = uuid4()
    for method, url, kwargs in [
        ('get','/api/interviews',{}), ('get',f'/api/interviews/{id}',{}),
        ('post','/api/interviews',{'json':{}}),
        ('post',f'/api/interviews/{id}/answers',{'json':{'question_number':1,'answer':'A queue is FIFO.'}}),
        ('post',f'/api/interviews/{id}/next',{'json':{'question_number':1}}),
        ('post','/api/interview/question',{'json':{}}),
        ('post','/api/speech/transcribe',{'content':b'audio'}),
    ]:
        response = getattr(client,method)(url,**kwargs)
        assert response.status_code == 401, (url,response.text)
    generate.assert_not_called()
    assert client.get('/api/health').status_code == 200


def test_token_is_verified_by_supabase_not_decoded_locally(client, monkeypatch):
    monkeypatch.setattr(settings,'supabase_url','https://example.supabase.co')
    monkeypatch.setattr(settings,'supabase_publishable_key','test-public-key')
    get = AsyncMock(return_value=httpx.Response(401))
    monkeypatch.setattr(httpx.AsyncClient,'get',get)
    assert client.get('/api/interviews',headers={'Authorization':'Bearer forged.jwt.token'}).status_code == 401
    assert get.call_args.kwargs['headers']['Authorization'] == 'Bearer forged.jwt.token'
    get.return_value = httpx.Response(200,json={'id':str(A)})
    assert client.get('/api/interviews',headers={'Authorization':'Bearer verified-token'}).json()['items'] == []
    get.return_value = httpx.Response(503,text='secret internal detail')
    result=client.get('/api/interviews',headers={'Authorization':'Bearer token'})
    assert result.status_code == 503 and 'secret' not in result.text


def test_missing_auth_configuration_fails_closed(client,monkeypatch):
    monkeypatch.setattr(settings,'supabase_url','')
    assert client.get('/api/interviews',headers={'Authorization':'Bearer token'}).status_code == 503


def test_users_cannot_read_answer_or_advance_other_users_interviews(client,monkeypatch):
    store=main.store
    own=store.create(SessionRequest(),'Explain FIFO.','test',A)
    other=store.create(SessionRequest(),'Explain LIFO.','test',B)
    legacy=store.create(SessionRequest(),'Legacy private.','test')
    main.app.dependency_overrides[auth.current_user]=lambda:A
    history=client.get('/api/interviews').json()['items']
    assert [item['id'] for item in history] == [str(own.id)]
    assert client.get(f'/api/interviews/{own.id}').status_code == 200
    assert 'owner_id' not in client.get(f'/api/interviews/{own.id}').json()
    evaluate=AsyncMock(); generate=AsyncMock()
    monkeypatch.setattr(provider,'evaluate_answer',evaluate)
    monkeypatch.setattr(provider,'generate_question',generate)
    for session in [other,legacy]:
        assert client.get(f'/api/interviews/{session.id}').status_code == 404
        assert client.post(f'/api/interviews/{session.id}/answers',json={'question_number':1,'answer':'Attempted answer'}).status_code == 404
        assert client.post(f'/api/interviews/{session.id}/next',json={'question_number':1}).status_code == 404
    evaluate.assert_not_called();generate.assert_not_called()
    main.app.dependency_overrides[auth.current_user]=lambda:B
    assert [item['id'] for item in client.get('/api/interviews').json()['items']] == [str(other.id)]


def test_creation_assigns_server_verified_owner(client,monkeypatch):
    main.app.dependency_overrides[auth.current_user]=lambda:A
    monkeypatch.setattr(provider,'generate_question',AsyncMock(return_value='Explain a queue.'))
    result=client.post('/api/interviews',json={})
    assert result.status_code == 201
    assert main.store.get(UUID(result.json()['id']),A).owner_id == A
    assert main.store.get(UUID(result.json()['id']),B) is None
    assert client.post('/api/interviews',json={'owner_id':str(B)}).status_code == 422
