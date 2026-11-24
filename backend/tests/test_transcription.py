from io import BytesIO
from types import SimpleNamespace
import threading
import wave
import pytest
from fastapi.testclient import TestClient
from app import transcription
from app.main import app


def wav(seconds=0.2):
    output=BytesIO()
    with wave.open(output,'wb') as file:
        file.setnchannels(1);file.setsampwidth(2);file.setframerate(16000)
        file.writeframes(b'\x00\x00'*int(seconds*16000))
    return output.getvalue()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(transcription,'speech_ready',lambda:True)
    monkeypatch.setattr(transcription,'_gate',threading.Lock())
    monkeypatch.setattr(transcription,'_model',SimpleNamespace(transcribe=lambda *a,**kw:(iter([SimpleNamespace(text=' A stack uses LIFO. ')]),None)))
    with TestClient(app) as client: yield client


def test_audio_decoding_uses_real_wav_samples():
    data=transcription.decode_audio(wav())
    assert len(data)==3200
    assert str(data.dtype)=='float32'


def test_transcription_endpoint(client):
    response=client.post('/api/speech/transcribe',content=wav(),headers={'content-type':'audio/wav'})
    assert response.status_code==200
    assert response.json()=={'text':'A stack uses LIFO.','duration_seconds':0.2}


def test_status_does_not_download_models(client,monkeypatch):
    monkeypatch.setattr(transcription,'speech_ready',lambda:False)
    assert client.get('/api/speech/status').json()=={'status':'unavailable','max_seconds':180}
    assert client.post('/api/speech/transcribe',content=wav(),headers={'content-type':'audio/wav'}).status_code==503


def test_empty_upload(client):
    assert client.post('/api/speech/transcribe',content=b'',headers={'content-type':'audio/webm'}).status_code==400


def test_non_audio_content_type(client):
    assert client.post('/api/speech/transcribe',json={'anything':'else'}).status_code==415


def test_invalid_audio(client):
    assert client.post('/api/speech/transcribe',content=b'not audio',headers={'content-type':'audio/webm'}).status_code==422


def test_bounded_upload(client,monkeypatch):
    monkeypatch.setattr(transcription,'MAX_AUDIO_BYTES',5)
    assert client.post('/api/speech/transcribe',content=b'123456',headers={'content-type':'audio/webm'}).status_code==413


def test_bounded_decoded_duration(client,monkeypatch):
    monkeypatch.setattr(transcription,'MAX_SECONDS',1)
    assert client.post('/api/speech/transcribe',content=wav(2),headers={'content-type':'audio/wav'}).status_code==413


def test_no_speech_is_not_invented(client,monkeypatch):
    monkeypatch.setattr(transcription,'_model',SimpleNamespace(transcribe=lambda *a,**kw:(iter([]),None)))
    assert client.post('/api/speech/transcribe',content=wav(),headers={'content-type':'audio/wav'}).status_code==422


def test_inference_failure_releases_worker(client,monkeypatch):
    def fail(*args,**kwargs):raise RuntimeError('failed')
    monkeypatch.setattr(transcription,'_model',SimpleNamespace(transcribe=fail))
    assert client.post('/api/speech/transcribe',content=wav(),headers={'content-type':'audio/wav'}).status_code==503
    assert transcription._gate.acquire(blocking=False)
    transcription._gate.release()


def test_busy_worker_keeps_requests_bounded(client):
    transcription._gate.acquire()
    try: assert client.post('/api/speech/transcribe',content=wav(),headers={'content-type':'audio/wav'}).status_code==503
    finally:transcription._gate.release()
