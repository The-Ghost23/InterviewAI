from datetime import timedelta
from pathlib import Path
from io import StringIO
import os
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from app import main, provider
from app.config import settings
from app.database import DatabaseStore, RevisionConflict, make_database_engine, turn_values, SCHEMA, interviews, turns
from app.evaluation import Feedback
from app.sessions import InterviewSession, SessionRequest, SessionStore, Turn


def feedback():
    return Feedback(technical_accuracy=8,completeness=6,clarity=8,reasoning=6,strengths=['Good definition.'],missing_concepts=['Example.'],suggestions=['Give an example.'])


def test_feedback_storage_excludes_computed_score():
    store=SessionStore();session=store.create(SessionRequest(),'Explain a stack.','test')
    turn=Turn(question_number=1,question=session.question,answer='LIFO means last in first out.',feedback=feedback())
    values=turn_values(session.model_copy(update={'history':(turn,)}))
    assert 'score' not in values[0]['feedback']
    assert Feedback.model_validate(values[0]['feedback']).score==7


def test_invalid_database_url_does_not_echo_secret():
    with pytest.raises(ValueError) as error:make_database_engine('invalid-secret-value')
    assert 'invalid-secret-value' not in str(error.value)
    with pytest.raises(ValueError):make_database_engine('sqlite:///example.db')


def test_migration_compiles_for_private_postgresql_schema():
    buffer=StringIO()
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'),output_buffer=buffer)
    command.upgrade(config,'head',sql=True)
    sql=buffer.getvalue()
    assert 'CREATE SCHEMA IF NOT EXISTS interviewai' in sql
    assert 'CREATE TABLE interviewai.interviews' in sql
    assert 'CREATE TABLE interviewai.interview_turns' in sql
    assert 'JSONB' in sql
    assert 'ENABLE ROW LEVEL SECURITY' in sql
    assert 'REVOKE ALL ON SCHEMA interviewai FROM PUBLIC' in sql


def test_history_page_is_bounded_and_does_not_expose_answer_text(monkeypatch):
    store=SessionStore();monkeypatch.setattr(main,'store',store)
    for i in range(3):store.create(SessionRequest(role=f'Engineer {i}'),'Question?','test')
    with TestClient(main.app) as client:
        first=client.get('/api/interviews?limit=2').json()
        second=client.get('/api/interviews?limit=2&offset=2').json()
        assert len(first['items'])==2 and first['has_more'] is True
        assert len(second['items'])==1 and second['has_more'] is False
        assert first['items'][0]['role']=='Engineer 2'
        assert 'history' not in first['items'][0]
        assert 'answer' not in first['items'][0]
        assert client.get('/api/interviews?limit=26').status_code==422
        assert client.get('/api/interviews?offset=-1').status_code==422
        assert client.get('/api/storage/status').json()=={'backend':'memory','persistent':False,'ready':True}


def test_storage_failures_are_reported_without_fallback(monkeypatch):
    from app.database import StorageUnavailable
    store=SessionStore();store.backend='supabase';store.persistent=True
    def fail():raise StorageUnavailable('Storage unavailable')
    store.check=fail;monkeypatch.setattr(main,'store',store)
    async def unexpected(*args):pytest.fail('Do not generate when storage is down')
    monkeypatch.setattr(provider,'generate_question',unexpected)
    with TestClient(main.app) as client:
        assert client.get('/api/storage/status').json()=={'backend':'supabase','persistent':True,'ready':False}
        assert client.post('/api/interviews',json={}).status_code==503
    assert not store._sessions


@pytest.mark.skipif(os.getenv('RUN_SUPABASE_TESTS')!='1',reason='Opt-in real PostgreSQL integration check')
def test_real_supabase_roundtrip_restart_and_conflict():
    assert settings.database_url
    from sqlalchemy import delete, text
    connection=settings.database_url.get_secret_value()
    engine=make_database_engine(connection)
    store=DatabaseStore(engine)
    session=None
    try:
        store.check()
        session=store.create(SessionRequest(role='Integration test',question_count=1),'Explain a stack.','test-fixture')
        turn=Turn(question_number=1,question=session.question,answer='A stack is last in first out.',feedback=feedback())
        completed=store.save(session.model_copy(update={'history':(turn,),'status':'completed'}))
        assert completed.revision==1
        with pytest.raises(RevisionConflict):store.save(session.model_copy(update={'status':'feedback'}))
        engine.dispose()
        restarted=DatabaseStore(make_database_engine(connection))
        try:
            restored=restarted.get(session.id)
            assert restored==completed
            assert restored.summary['overall_score']==7
            assert any(item.id==session.id for item in restarted.list(25,0))
            with restarted.engine.begin() as c:
                policies=c.execute(text("select relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='interviewai' and c.relname in ('interviews','interview_turns')")).scalars().all()
                assert policies==[True,True]
        finally:restarted.engine.dispose()
    finally:
        if session:
            with engine.begin() as c:c.execute(delete(interviews).where(interviews.c.id==session.id))
        engine.dispose()
