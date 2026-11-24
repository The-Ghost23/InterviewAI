"""Supabase PostgreSQL storage. Credentials and SQL stay in the backend."""
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import ValidationError
from sqlalchemy import (MetaData, Table, Column, String, Integer, DateTime, Text, ForeignKey,
                        CheckConstraint, Index, select, insert, update, func, create_engine)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from .sessions import InterviewSession, SessionRequest, SessionStore

SCHEMA = 'interviewai'
metadata = MetaData(schema=SCHEMA)
interviews = Table('interviews', metadata,
    Column('id', PGUUID(as_uuid=True), primary_key=True),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False),
    Column('role', String(100), nullable=False), Column('topic', String(100), nullable=False),
    Column('difficulty', String(20), nullable=False), Column('question_count', Integer, nullable=False),
    Column('question_number', Integer, nullable=False), Column('question', Text, nullable=False),
    Column('model', String(128), nullable=False), Column('status', String(20), nullable=False),
    Column('revision', Integer, nullable=False, server_default='0'),
    CheckConstraint('question_count BETWEEN 1 AND 10', name='question_count_range'),
    CheckConstraint('question_number BETWEEN 1 AND question_count', name='question_number_range'),
    CheckConstraint("status IN ('awaiting_answer', 'feedback', 'completed')", name='status_values'),
    CheckConstraint("difficulty IN ('Beginner', 'Intermediate', 'Advanced')", name='difficulty_values'),
    CheckConstraint('char_length(question) BETWEEN 1 AND 600', name='question_length'),
    CheckConstraint('revision >= 0', name='nonnegative_revision'),
)
Index('ix_interviews_created_id', interviews.c.created_at.desc(), interviews.c.id.desc())
turns = Table('interview_turns', metadata,
    Column('interview_id', PGUUID(as_uuid=True), ForeignKey(f'{SCHEMA}.interviews.id', ondelete='CASCADE'), primary_key=True),
    Column('question_number', Integer, primary_key=True), Column('question', Text, nullable=False),
    Column('answer', Text, nullable=False), Column('feedback', JSONB, nullable=False),
    CheckConstraint('question_number BETWEEN 1 AND 10', name='turn_number_range'),
    CheckConstraint('char_length(answer) BETWEEN 2 AND 4000', name='answer_length'),
    CheckConstraint('char_length(question) BETWEEN 1 AND 600', name='turn_question_length'),
    CheckConstraint("jsonb_typeof(feedback) = 'object'", name='feedback_object'),
)


class StorageUnavailable(Exception):
    pass


class RevisionConflict(Exception):
    pass


def make_database_engine(connection_string: str):
    url = make_url(connection_string)
    if url.drivername not in ('postgres', 'postgresql', 'postgresql+psycopg'):
        raise ValueError('DATABASE_URL must be a PostgreSQL connection string.')
    url = url.set(drivername='postgresql+psycopg')
    # Session pooler (5432) is recommended for the long-running FastAPI process.
    args = {'connect_timeout': 10, 'prepare_threshold': None}
    if 'sslmode' not in url.query:
        args['sslmode'] = 'require'
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2,
                         hide_parameters=True, connect_args=args)


def session_values(session: InterviewSession) -> dict:
    return {key: getattr(session, key) for key in
            ('id', 'created_at', 'role', 'topic', 'difficulty', 'question_count',
             'question_number', 'question', 'model', 'status', 'revision')}


def turn_values(session: InterviewSession) -> list[dict]:
    return [{'interview_id': session.id, 'question_number': turn.question_number,
             'question': turn.question, 'answer': turn.answer,
             'feedback': turn.feedback.model_dump(exclude_computed_fields=True)} for turn in session.history]


class DatabaseStore:
    persistent = True
    backend = 'supabase'

    def __init__(self, engine):
        self.engine = engine
        self._operations = SessionStore()

    def operation(self, session_id):
        return self._operations.operation(session_id)

    @contextmanager
    def transaction(self):
        try:
            with self.engine.begin() as connection:
                yield connection
        except SQLAlchemyError as exc:
            # Never return driver errors containing connection details to the browser.
            raise StorageUnavailable('Supabase storage is unavailable. Check the backend connection and migrations, then retry.') from exc

    def check(self):
        with self.transaction() as connection:
            connection.execute(select(interviews.c.id).limit(0))
            connection.execute(select(turns.c.interview_id).limit(0))

    def create(self, request: SessionRequest, question: str, model: str) -> InterviewSession:
        session = InterviewSession(**request.model_dump(), id=uuid4(), created_at=datetime.now(timezone.utc), question=question, model=model)
        with self.transaction() as connection:
            connection.execute(insert(interviews).values(**session_values(session), updated_at=session.created_at))
        return session

    def get(self, session_id: UUID) -> InterviewSession | None:
        try:
            with self.transaction() as connection:
                # A consistent snapshot: the row lock prevents a concurrent save
                # from changing question/status between reading the row and turns.
                row = connection.execute(select(interviews).where(interviews.c.id == session_id).with_for_update(read=True)).mappings().first()
                if row is None:
                    return None
                history = connection.execute(select(turns).where(turns.c.interview_id == session_id).order_by(turns.c.question_number)).mappings().all()
                data = dict(row); data.pop('updated_at')
                data['history'] = [dict(question_number=turn['question_number'], question=turn['question'], answer=turn['answer'], feedback=turn['feedback']) for turn in history]
                return InterviewSession.model_validate(data)
        except ValidationError as exc:
            raise StorageUnavailable('The saved interview could not be loaded. Check its stored data.') from exc

    def save(self, session: InterviewSession) -> InterviewSession:
        updated = session.model_copy(update={'revision': session.revision + 1})
        values = session_values(updated); values.pop('id'); values.pop('created_at')
        with self.transaction() as connection:
            result = connection.execute(update(interviews).where(interviews.c.id == session.id,
                interviews.c.revision == session.revision).values(**values, updated_at=datetime.now(timezone.utc)))
            if result.rowcount != 1:
                raise RevisionConflict('This interview changed in another request. Refresh to load the latest saved progress.')
            # Persist only the newly added turn. All prior turns are immutable.
            existing = set(connection.execute(select(turns.c.question_number).where(turns.c.interview_id == session.id)).scalars())
            additions = [turn for turn in turn_values(updated) if turn['question_number'] not in existing]
            if additions:
                connection.execute(insert(turns), additions)
        return updated

    def list(self, limit: int, offset: int) -> list[InterviewSession]:
        # Keep history responses bounded; each session has at most ten turns.
        with self.transaction() as connection:
            ids = connection.execute(select(interviews.c.id).order_by(interviews.c.created_at.desc(), interviews.c.id.desc()).limit(limit).offset(offset)).scalars().all()
        return [session for session_id in ids if (session := self.get(session_id)) is not None]
