"""Temporary, single-process interview sessions. A restart clears all data."""
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict, computed_field
from .main_types import QuestionRequest
from .evaluation import Feedback


class SessionRequest(QuestionRequest):
    question_count: int = Field(default=5, ge=1, le=10, strict=True)


class AnswerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    question_number: int = Field(ge=1, le=10, strict=True)
    answer: str = Field(min_length=2, max_length=4000)


class NextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_number: int = Field(ge=1, le=10, strict=True)


class Turn(BaseModel):
    model_config = ConfigDict(frozen=True)
    question_number: int
    question: str
    answer: str
    feedback: Feedback


class InterviewSession(SessionRequest):
    model_config = ConfigDict(frozen=True)
    owner_id: UUID | None = Field(default=None, exclude=True)
    id: UUID
    created_at: datetime
    question_number: int = 1
    question: str
    model: str
    status: Literal["awaiting_answer", "feedback", "completed"] = "awaiting_answer"
    history: tuple[Turn, ...] = ()
    revision: int = Field(default=0, ge=0)

    @computed_field
    @property
    def summary(self) -> dict | None:
        if self.status != "completed":
            return None
        categories = ("technical_accuracy", "completeness", "clarity", "reasoning")
        return {
            "answered": len(self.history),
            "overall_score": round(sum(turn.feedback.score for turn in self.history) / len(self.history), 1),
            "category_scores": {key: round(sum(getattr(turn.feedback, key) for turn in self.history) / len(self.history), 1) for key in categories},
            "suggestions": list(dict.fromkeys(note for turn in self.history for note in turn.feedback.suggestions))[:5],
        }


class SessionBusy(Exception):
    pass


class SessionStore:
    persistent = False
    backend = 'memory'

    def __init__(self, capacity: int = 100, ttl: timedelta = timedelta(hours=4)):
        self.capacity = capacity
        self.ttl = ttl
        self._sessions: OrderedDict[UUID, InterviewSession] = OrderedDict()
        self._busy: set[UUID] = set()

    def create(self, request: SessionRequest, question: str, model: str, owner_id: UUID | None = None) -> InterviewSession:
        session = InterviewSession(**request.model_dump(), owner_id=owner_id, id=uuid4(),
                                   created_at=datetime.now(timezone.utc), question=question, model=model)
        self._sessions[session.id] = session
        while len(self._sessions) > self.capacity:
            self._sessions.popitem(last=False)
        return session

    def get(self, session_id: UUID, owner_id: UUID | None = None) -> InterviewSession | None:
        session = self._sessions.get(session_id)
        if session and datetime.now(timezone.utc) - session.created_at >= self.ttl:
            del self._sessions[session_id]
            return None
        return session if session and session.owner_id == owner_id else None

    def save(self, session: InterviewSession) -> InterviewSession:
        # Never resurrect a session that expired or was evicted during inference.
        if self.get(session.id, session.owner_id) is None:
            raise KeyError(session.id)
        saved = session.model_copy(update={'revision': session.revision + 1})
        self._sessions[session.id] = saved
        return saved

    def check(self):
        return None

    def list(self, limit: int, offset: int, owner_id: UUID | None = None) -> list[InterviewSession]:
        sessions = [session for key in list(self._sessions) if (session := self.get(key, owner_id)) is not None]
        return sorted(sessions, key=lambda session: (session.created_at, session.id), reverse=True)[offset:offset + limit]

    @contextmanager
    def operation(self, session_id: UUID):
        if session_id in self._busy:
            raise SessionBusy()
        self._busy.add(session_id)
        try:
            yield
        finally:
            self._busy.discard(session_id)


store = SessionStore()
