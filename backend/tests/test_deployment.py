import json
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from app import provider, main
from app.config import settings, Settings

@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setattr(settings,'ai_provider','runpod')
    monkeypatch.setattr(settings,'runpod_base_url','https://api.runpod.ai/v2/test-endpoint/openai/v1')
    monkeypatch.setattr(settings,'runpod_api_key',SecretStr('test-only-runpod-key'))
    monkeypatch.setattr(settings,'runpod_model','Qwen/Qwen3-4B')


def response(payload,status=200):
    return httpx.Response(status,json=payload,request=httpx.Request('POST','https://api.runpod.ai/test'))


def test_hosted_request_uses_auth_schema_and_non_thinking_mode(remote,monkeypatch):
    post=AsyncMock(return_value=response({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'question':'Explain FIFO.'})}}]}))
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    with TestClient(main.app) as client:
        result=client.post('/api/interview/question',json={})
    assert result.status_code==200
    assert result.json()=={'question':'Explain FIFO.','model':'Qwen/Qwen3-4B'}
    args=post.call_args
    assert args.args[0].endswith('/openai/v1/chat/completions')
    assert args.kwargs['headers']=={'Authorization':'Bearer test-only-runpod-key'}
    body=args.kwargs['json']
    assert body['response_format']['json_schema']['strict'] is True
    assert body['chat_template_kwargs']=={'enable_thinking':False}
    assert body['model']=='Qwen/Qwen3-4B' and body['stream'] is False


@pytest.mark.parametrize('status',[401,429,500])
def test_hosted_provider_errors_do_not_expose_secrets(remote,monkeypatch,status):
    monkeypatch.setattr(httpx.AsyncClient,'post',AsyncMock(return_value=response({'detail':'test-only-runpod-key'},status)))
    with TestClient(main.app) as client: result=client.post('/api/interview/question',json={})
    assert result.status_code==503
    assert 'test-only-runpod-key' not in result.text


@pytest.mark.parametrize('payload',[
    {'choices':[]},
    {'choices':[{'finish_reason':'length','message':{'content':'{"question":"partial"}'}}]},
    {'choices':[{'finish_reason':'stop','message':{'content':'not json'}}]},
    {'choices':[{'finish_reason':'stop','message':{'content':'[]'}}]},
    {'choices':[{'finish_reason':'stop','message':{'content':None}}]},
])
def test_hosted_malformed_or_truncated_responses(remote,monkeypatch,payload):
    monkeypatch.setattr(httpx.AsyncClient,'post',AsyncMock(return_value=response(payload)))
    with TestClient(main.app) as client: assert client.post('/api/interview/question',json={}).status_code==502


def test_hosted_timeout_and_missing_key_fail_without_local_fallback(remote,monkeypatch):
    post=AsyncMock(side_effect=httpx.ReadTimeout('private endpoint detail'))
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    with TestClient(main.app) as client:
        result=client.post('/api/interview/question',json={})
        assert result.status_code==503 and 'private endpoint detail' not in result.text
        monkeypatch.setattr(settings,'runpod_api_key',None)
        assert client.post('/api/interview/question',json={}).status_code==503
    assert post.call_count==1


@pytest.mark.parametrize('models,status',[([{'id':'Qwen/Qwen3-4B'}],'ready'),([],'missing')])
def test_hosted_model_readiness(remote,monkeypatch,models,status):
    get=AsyncMock(return_value=response({'data':models}))
    monkeypatch.setattr(httpx.AsyncClient,'get',get)
    with TestClient(main.app) as client:
        assert client.get('/api/ai/status').json()=={'status':status,'model':'Qwen/Qwen3-4B'}
    assert get.call_args.kwargs['headers']['Authorization']=='Bearer test-only-runpod-key'


def production(**changes):
    values=dict(_env_file=None,app_env='production',database_url='postgresql://fixture',
        supabase_url='https://example.supabase.co',supabase_publishable_key='public-fixture',
        ai_provider='runpod',runpod_base_url='https://api.runpod.ai/v2/fixture/openai/v1',
        runpod_api_key='test-fixture',cors_origins=['https://interviewai.example'])
    values.update(changes)
    return Settings(**values)


def test_production_configuration_validates_before_serving():
    assert production().active_model=='Qwen/Qwen3-4B'
    for changes in [dict(database_url=None),dict(ai_provider='ollama'),dict(runpod_api_key=None),
                    dict(cors_origins=['*']),dict(cors_origins=['http://localhost:5173']),
                    dict(cors_origins=['https://example.com/path']),dict(runpod_base_url='http://api.runpod.ai/v2/test/openai/v1')]:
        with pytest.raises(ValidationError):production(**changes)


def test_auth_header_cors_preflight():
    with TestClient(main.app) as client:
        result=client.options('/api/interviews',headers={'Origin':'http://localhost:5173',
            'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
    assert result.status_code==200
    assert 'authorization' in result.headers['access-control-allow-headers'].lower()


def test_speech_build_uses_existing_complete_model_without_network(tmp_path,monkeypatch):
    from scripts import prepare_speech
    for name in prepare_speech.REQUIRED_FILES:(tmp_path/name).write_bytes(b'fixture')
    def unexpected(*args,**kwargs):pytest.fail('Do not redownload a complete model')
    monkeypatch.setattr(prepare_speech,'download_model',unexpected)
    prepare_speech.prepare_model(tmp_path)


def test_speech_build_rejects_incomplete_download(tmp_path,monkeypatch):
    from scripts import prepare_speech
    monkeypatch.setattr(prepare_speech,'download_model',lambda *args,**kwargs:None)
    with pytest.raises(RuntimeError):prepare_speech.prepare_model(tmp_path/'missing-model')
