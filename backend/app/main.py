from uuid import UUID
from fastapi import FastAPI, HTTPException, Request, Query, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from .auth import current_user
from . import transcription
from . import provider
from .config import settings
from .main_types import QuestionRequest, QuestionResponse
from .database import DatabaseStore, StorageUnavailable, RevisionConflict, make_database_engine
from .sessions import SessionRequest, InterviewSession, AnswerRequest, NextRequest, Turn, SessionBusy, store

if settings.database_url:
    store = DatabaseStore(make_database_engine(settings.database_url.get_secret_value()))

app = FastAPI(title="InterviewAI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/health")
async def health():
    # Liveness stays independent of the model server.
    return {"status": "ok", "service": "InterviewAI API"}


@app.get("/api/ai/status")
async def ai_status():
    return {"status": await provider.model_status(), "model": settings.active_model}


@app.post("/api/interview/question", dependencies=[Depends(current_user)], response_model=QuestionResponse)
async def question(request: QuestionRequest):
    try:
        content = await provider.generate_question(request.role, request.topic, request.difficulty)
        return QuestionResponse(question=content, model=settings.active_model)
    except provider.ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except provider.InvalidModelResponse as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/interviews", response_model=InterviewSession, status_code=201)
async def create_interview(request: SessionRequest, user: UUID = Depends(current_user)):
    # Only commit a session once generation succeeds. Failures can be retried.
    await run_in_threadpool(store.check)
    generated = await question(request)
    return await run_in_threadpool(store.create, request, generated.question, generated.model, user)


@app.get("/api/interviews/{session_id}", response_model=InterviewSession)
async def get_interview(session_id: UUID, user: UUID = Depends(current_user)):
    session = await run_in_threadpool(store.get, session_id, user)
    if session is None:
        raise HTTPException(status_code=404, detail="This interview was not found or has expired. Please start a new interview.")
    return session

@app.exception_handler(provider.ModelUnavailable)
async def unavailable_handler(request: Request, exc: provider.ModelUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(provider.InvalidModelResponse)
async def invalid_model_handler(request: Request, exc: provider.InvalidModelResponse):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(SessionBusy)
async def busy_handler(request: Request, exc: SessionBusy):
    return JSONResponse(status_code=409, content={"detail": "This interview is processing another request. Please wait and retry."})


async def require_session(session_id: UUID, user: UUID) -> InterviewSession:
    session = await run_in_threadpool(store.get, session_id, user)
    if session is None:
        raise HTTPException(status_code=404, detail="This interview was not found or has expired. Please start a new interview.")
    return session


async def save_session(session: InterviewSession):
    try:
        return await run_in_threadpool(store.save, session)
    except KeyError:
        raise HTTPException(status_code=404, detail="This interview expired during processing. Please start a new interview.")


@app.post("/api/interviews/{session_id}/answers", response_model=InterviewSession)
async def submit_answer(session_id: UUID, request: AnswerRequest, user: UUID = Depends(current_user)):
    with store.operation(session_id):
        session = await require_session(session_id, user)
        previous = next((turn for turn in session.history if turn.question_number == request.question_number), None)
        if previous:
            if previous.answer == request.answer:
                return session  # Retried response after a timeout: don't evaluate twice.
            raise HTTPException(status_code=409, detail="This question already has a submitted answer.")
        if session.status != "awaiting_answer" or request.question_number != session.question_number:
            raise HTTPException(status_code=409, detail="This is not the current unanswered question. Refresh the interview.")
        feedback = await provider.evaluate_answer(session.role, session.topic, session.difficulty, session.question, request.answer)
        turn = Turn(question_number=session.question_number, question=session.question, answer=request.answer, feedback=feedback)
        updated = session.model_copy(update={
            "history": (*session.history, turn),
            "status": "completed" if session.question_number == session.question_count else "feedback",
        })
        return await save_session(updated)


@app.post("/api/interviews/{session_id}/next", response_model=InterviewSession)
async def next_question(session_id: UUID, request: NextRequest, user: UUID = Depends(current_user)):
    with store.operation(session_id):
        session = await require_session(session_id, user)
        if request.question_number == session.question_number - 1:
            return session  # A retry must not skip forward again.
        if request.question_number != session.question_number or session.status != "feedback":
            raise HTTPException(status_code=409, detail="Submit the current answer before continuing. If the interview is complete, start a new one.")
        content = await provider.generate_question(session.role, session.topic, session.difficulty,
                                                   previous_questions=[turn.question for turn in session.history])
        updated = session.model_copy(update={"question_number": session.question_number + 1, "question": content, "status": "awaiting_answer"})
        return await save_session(updated)


@app.get("/api/speech/status")
async def speech_status():
    return {"status": "ready" if transcription.speech_ready() else "unavailable", "max_seconds": transcription.MAX_SECONDS}


@app.post("/api/speech/transcribe", dependencies=[Depends(current_user)])
async def transcribe_recording(request: Request):
    content_type = request.headers.get('content-type', '').split(';')[0].lower()
    if not content_type.startswith('audio/') and content_type != 'application/octet-stream':
        raise HTTPException(status_code=415, detail="Please upload an audio recording.")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > transcription.MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Recordings must be smaller than 15 MB.")
        content.extend(chunk)
    if not content:
        raise HTTPException(status_code=400, detail="The recording is empty. Please record again.")
    try:
        return await run_in_threadpool(transcription.transcribe, bytes(content))
    except transcription.AudioTooLong as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except transcription.InvalidAudio as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except transcription.SpeechUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.exception_handler(StorageUnavailable)
async def storage_error(request: Request, exc: StorageUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RevisionConflict)
async def revision_error(request: Request, exc: RevisionConflict):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/api/storage/status")
async def storage_status():
    try:
        await run_in_threadpool(store.check)
        ready = True
    except StorageUnavailable:
        ready = False
    return {"backend": store.backend, "persistent": store.persistent, "ready": ready}


@app.get("/api/interviews")
async def list_interviews(limit: int = Query(default=10, ge=1, le=25), offset: int = Query(default=0, ge=0), user: UUID = Depends(current_user)):
    sessions = await run_in_threadpool(store.list, limit + 1, offset, user)
    return {"items": [{"id": session.id, "created_at": session.created_at, "role": session.role,
            "topic": session.topic, "difficulty": session.difficulty, "question_count": session.question_count,
            "question_number": session.question_number, "status": session.status,
            "answered": len(session.history), "score": session.summary['overall_score'] if session.summary else None}
            for session in sessions[:limit]], "has_more": len(sessions) > limit}
