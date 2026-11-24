# InterviewAI — Days 1–5

A mock-interview application with local AI feedback and optional browser voice built with React, TypeScript, Vite, Tailwind CSS, FastAPI, and Ollama Qwen3 4B.

Project location: `/Users/dipyamanbhowmick/Desktop/Personal/Projects/InterviewAI`

## What works

- Interview setup with role, topic, difficulty, and 3, 5, or 10 planned questions.
- Start interview opens a room with a generated first question, selected settings, session ID, and current-question indicator.
- Typed answers receive AI feedback with validated response structure and score ranges for technical accuracy, completeness, clarity, and reasoning.
- Next question preserves session settings and sends previously asked questions to the model to discourage repeats.
- The final answer completes the session with an overall score, category averages, practice suggestions, and expandable question/answer/feedback reviews.
- Refresh reopens the current question, submitted answers, feedback, or completed summary using the session ID in the URL; Back to setup retains your settings.
- Independent backend health and model readiness indicators.
- Create an interview and generate its first question through React → FastAPI → Ollama.
- Sessions are local and temporary: held in backend memory for up to four hours, with the oldest removed once 100 sessions are retained. A backend restart, including automatic reload after a Python edit, clears them.
- Clear loading states, validation, model failures, and retry controls.
- Backend tests for input validation, CORS, unavailable models, and malformed/truncated model responses.

Day 3 supports the full typed flow: start → answer → feedback → next question → final summary. Optional browser dictation and question read-aloud are available in Day 5. User accounts and database persistence are later milestones. Scores are AI coaching estimates, not validated assessments; feedback can still be imperfect and a small Day 4 reference benchmark exists, but broad scoring consistency is not validated.

## Start the app

Use three Terminal tabs. Stop each process with Control+C when finished.

**Terminal 1 — Ollama**

```bash
ollama serve
```

This starts the local AI service on `127.0.0.1:11434`. If it says the address is already in use, Ollama may already be running. Check `curl http://127.0.0.1:11434/api/tags` before starting another instance.

Download the model once, in a separate Terminal tab:

```bash
ollama pull qwen3:4b
```

The model is approximately 2.5 GB and is stored in `~/.ollama/models`, outside this repository. It runs locally after downloading. The API disables thinking for short questions, limits context to 4,096 tokens, requests validated JSON output and caps question output at 256 tokens and evaluation output at 1,000 tokens, and lets Ollama unload the model after five idle minutes. This is a conservative starting configuration for the 16 GB Mac M5; it is not a full performance benchmark.

**Terminal 2 — Python backend**

```bash
cd /Users/dipyamanbhowmick/Desktop/Personal/Projects/InterviewAI/backend
uv sync --locked
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`uv sync --locked` installs the versions recorded in `uv.lock` into the project’s `.venv`. The project uses Python 3.14 (`.python-version`); `uv` can obtain it if needed. `uvicorn` serves the API; `--reload` reloads it when Python files change.

Optional settings: copy `.env.example` to `.env` in `backend/` and adjust `OLLAMA_BASE_URL` or `OLLAMA_MODEL`. Defaults already work without this file. Restart the backend after changing settings.

**Terminal 3 — React frontend**

```bash
cd /Users/dipyamanbhowmick/Desktop/Personal/Projects/InterviewAI/frontend
npm ci
npm run dev
```

`npm ci` installs the versions in `package-lock.json`. `npm run dev` serves React on `http://127.0.0.1:5173`. Open that URL and click **Check connection**, choose your interview settings, then **Start interview**. The room displays **Question 1 of 5** (or your selected count). Type an answer and choose **Submit answer** to receive feedback. Choose **Next question** after reviewing it. The final submitted answer opens the summary. Refresh to restore submitted progress, or use **Back to setup** to start another interview. Unsubmitted text is not saved across refresh.

Vite forwards `/api` requests to FastAPI on port 8000. For interview API requests, the browser talks to Vite and FastAPI calls Ollama. Optional browser speech recognition may contact the browser vendor’s speech service separately. No AI API keys are needed. Both app servers bind to your Mac’s loopback interface. They are not published online.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Backend liveness; stays OK if Ollama is offline |
| GET | `/api/ai/status` | `ready`, `missing`, or `unavailable` for the configured model |
| POST | `/api/interview/question` | Day 1 standalone question endpoint (retained) |
| POST | `/api/interviews` | Create a session and generate its first question; returns 201 |
| GET | `/api/interviews/{session_id}` | Retrieve current question, status, history, feedback, and summary |
| POST | `/api/interviews/{session_id}/answers` | Evaluate and save the current answer |
| POST | `/api/interviews/{session_id}/next` | Generate the next question after feedback |

API explorer: `http://127.0.0.1:8000/docs`

Example request:

```bash
curl http://127.0.0.1:8000/api/interviews \
  -H 'Content-Type: application/json' \
  -d '{"role":"Software Engineer","topic":"Data Structures","difficulty":"Beginner","question_count":5}'
```

The create response includes `id`, `created_at`, `role`, `topic`, `difficulty`, `question_count`, `question_number`, `question`, and `model`, plus `status`, `history`, and `summary`. Open the room at `http://127.0.0.1:5173/#session/ID`, replacing ID with that response’s `id`.

The API accepts an integer `question_count` between 1 and 10; the UI offers 3, 5, and 10. Missing or expired session IDs return 404; malformed UUIDs return 422. Sessions are scoped to one backend process; keep a single worker during this milestone.

Accepted difficulties: `Beginner`, `Intermediate`, `Advanced`. Roles and topics must be 2–100 characters after trimming. Failures return 422 for invalid input, 503 for an unavailable model service, or 502 for an incomplete model response. Requests to Ollama time out after 120 seconds. Out-of-order, conflicting, or concurrent session actions return 409; missing sessions return 404.

## Verification commands

From `backend/`:

```bash
uv run --locked pytest -q
```

From `frontend/`:

```bash
npm run build
```

The backend tests mock model calls, so they can run offline. Test actual model inference with the page or the example request above. The frontend build checks TypeScript and creates `dist/`; production hosting will need an API routing configuration because the Vite development proxy does not ship with `dist/`.

## Folder guide

```text
InterviewAI/
├── frontend/              React, Vite, Tailwind, npm lockfile
│   ├── src/App.tsx        Setup and session URL handling
│   ├── src/InterviewRoom.tsx  Answers, feedback, next question, and summary
│   ├── src/types.ts       Shared frontend data types
│   ├── src/api.ts         API requests and timeouts
│   └── vite.config.ts     Tailwind plugin and local API proxy
├── backend/
│   ├── app/main.py        Routes and input validation
│   ├── app/main_types.py  Shared request/response validation
│   ├── app/sessions.py    Temporary session models and bounded store
│   ├── app/provider.py    Structured question generation and answer evaluation
│   ├── app/evaluation.py  Feedback validation and score calculation
│   ├── app/config.py      Environment settings
│   ├── tests/            API, session, validation, and model failure tests
│   └── uv.lock            Pinned Python dependencies
└── README.md
```

## References

- [Tailwind with Vite](https://tailwindcss.com/docs/installation/using-vite)
- [Vite guide](https://vite.dev/guide/)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Ollama chat API](https://docs.ollama.com/api/chat)
- [Qwen3 4B model](https://ollama.com/library/qwen3:4b)

## Day 2 verification

See Day 2 verification (local file: `docs/day2-verification.md`; excluded from Git) for checks and browser screenshots. Day 1’s original verification remains in `docs/day1-verification.md`.

## Day 3 answer and progression API

Submit an answer with the number of the question currently displayed:

```json
{"question_number": 1, "answer": "A stack follows last-in, first-out order..."}
```

Send this body to `POST /api/interviews/ID/answers`. Answers are trimmed and must contain 2–4,000 characters. The backend stores the answer only after complete, valid feedback is returned. The model receives the question, answer, role, topic, and difficulty as data.

Feedback includes four integer ratings (0–10), strengths, missing concepts, suggestions, and `score`, the equal-weight mean of the four ratings rounded to one decimal. The model does not choose that overall score.

After feedback, send `{"question_number": 1}` to `POST /api/interviews/ID/next`. The backend refuses to skip unanswered questions. Repeating an identical answer submission or the same next-question request returns the saved result instead of advancing twice. Another in-flight session action returns 409. Failed model requests leave the saved state unchanged, allowing retries. If the browser times out after the server saved a result, refresh to retrieve it.

Session states: `awaiting_answer` → `feedback` → `awaiting_answer`; the final answer goes directly to `completed`. The summary is computed from saved feedback, with the average of per-question scores, per-category averages, and up to five deduplicated practice suggestions. All question/answer/feedback records remain available in `history` until the temporary session expires or the backend restarts.

Day 3 verification (local file: `docs/day3-verification.md`; excluded from Git) records automated tests and real local-model browser checks. Startup commands are unchanged; no new dependencies are required.

Known quality limit: the Day 3 local-model smoke test produced an incorrect MySQL NULL-handling suggestion and some suggestions that repeated concepts already in the answer. These are recorded in the verification report. Schema validation does not verify factual correctness. Evaluate coaching quality on a curated reference set before treating the ratings as dependable.

## Day 4 feedback-quality checks

The evaluator now uses the measured `day4-v2` prompt and a fixed evaluation seed (42). Startup commands and the interface are unchanged. Question generation remains unseeded.

On 12 authored beginner examples, score-band agreement improved from 9/12 to 11/12; complete answers receiving no missing-concept claims improved from 1/4 to 4/4. The revised prompt met all six score bands on the held-out-topic check. A second seed also met 11/12 bands. These are small-sample regression measurements, not validated grading accuracy. One brief indexing answer is still over-scored, and some suggestions are redundant or too broad.

Read the full Day 4 comparison and limitations (local file: `docs/day4-quality-report.md`; excluded from Git), [reference cases and methods](backend/quality/README.md), and saved raw feedback under `backend/quality/results/`.

To run a new local quality check from `backend/` (Ollama must be running):

```bash
uv run --locked python -m quality.run --variant candidate --split all --seed 42 --output quality/results/my-check.json
```

Results are saved after every answer and matching runs can resume. Use a new output filename for a fresh run. These model measurements are separate from the offline regression tests.

## Day 5 — Record and transcribe on the server

The original browser speech-recognition experiment has been replaced. Visitors do **not** download a speech model, enable Brave on-device speech, or depend on the browser vendor's recognition service.

1. Open the app, start an interview, and click **Record answer**. Allow microphone access if prompted.
2. Speak your answer in English, keeping this tab visible. The recording timer stays active until you stop or the three-minute limit is reached.
3. Click **Stop and transcribe**. The microphone turns off and the audio is sent to InterviewAI's backend for transcription. At three minutes this happens automatically.
4. Review and edit the resulting text, then click **Submit answer** to request evaluation. Transcription does not automatically submit an answer for scoring.

Typed answers and **Read question aloud** remain available. A failed transcription retains the browser's in-memory clip for **Retry transcription**. Beginning a new recording replaces that clip. Leaving the question or hiding the tab cancels an unfinished capture. Transcripts append to existing text and respect the 4,000-character answer limit. Recognition can mishear technical terms, so review before submitting.

### Backend setup (already completed on this Mac)

The Python dependencies now include `faster-whisper`, which uses PyAV and CTranslate2. The server runs the English `base.en` Whisper model with CPU int8 inference. On this Mac its model directory occupies approximately 141 MiB. This installation is on the backend host, not in each visitor's browser.

For a new developer machine or backend host, run once from `backend/`:

```bash
uv sync --locked
uv run --locked python -m app.setup_speech
```

The weights are stored in `backend/.models/whisper-base.en/`, ignored by Git. Override `SPEECH_MODEL_DIR` in `backend/.env` if needed. Runtime inference uses local files only; a missing model produces a server-unavailable message instead of downloading during a visitor request. The existing three startup commands are unchanged on this Mac.

### Audio API and privacy

- `GET /api/speech/status`: reports readiness and the 180-second recording limit.
- `POST /api/speech/transcribe`: accepts raw audio bytes with an `audio/*` content type (or `application/octet-stream`). It returns `text` and `duration_seconds`.
- The server caps uploads at 15 MiB and decoded audio at 180 seconds. It rejects empty, invalid, video-containing, or unintelligible uploads. A busy transcription worker returns a retryable 503.
- Audio is uploaded only to the app's backend. The raw body and decoded samples are processed in memory; no audio recording is persisted by application code. The app does not send it to a third-party speech API. The one-time model download fetches model files only.
- On a future hosted deployment, visitors' audio will go to that hosted backend. Server compute/model storage and a suitable request timeout must be provisioned there; this local setup is not an online deployment.

Browser capture requires localhost or HTTPS and microphone permission. The browser selects a supported recording format; WebM/Opus and MP4/AAC were exercised through the local API.

From `frontend/`, run `npm test` and `npm run build`. From `backend/`, run `uv run --locked pytest -q`. See server transcription verification (local file: `docs/day5-server-transcription.md`; excluded from Git) for test results and the remaining real-microphone check.

## Supabase preparation status

PostgreSQL dependencies and a backend storage adapter have been scaffolded for the next milestone. Supabase is not connected and database migrations/history UI are not finalized or verified yet. Leave `DATABASE_URL` unset while publishing the current working local app to GitHub; it continues using temporary in-memory sessions. Do not treat this as completed persistent storage. We will finish the migration and connect the selected Supabase project after the repository is uploaded.

The repository excludes local environment files, model weights, dependencies, build output, and audio/video recordings. Commit `.env.example` files as templates, not real credentials. Uploading source to GitHub does not deploy the running frontend/backend or local models.
