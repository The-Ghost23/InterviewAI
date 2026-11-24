# Feedback-quality benchmark

This is a small, authored regression set, not a validated interview assessment or a comprehensive model benchmark.

## Cases and sources

`cases.json` contains 12 synthetic answers: strong, partial, and incorrect for each of four fixed beginner questions. Cases and score bands were written before either prompt was measured. The evaluator receives only role/topic/difficulty/question/answer, never the expected label, band, split, or reference answer.

- Development: primary versus unique keys; index query performance.
- Held-out check: stack versus queue; transaction consistency. Do not revise the prompt in response to this check and still call it held out; use new topics for any later independent check.
- Strong target overall score: 8–10. Partial: 3–7.9. Incorrect: 0–3.5. These are proposed product acceptance bands, not objective gold-standard scores. The mean of four categories can mask differences between correctness and communication.
- A strong, complete answer should not receive claims of missing required concepts.

Reference facts were checked against primary documentation:

- [MySQL CREATE TABLE](https://dev.mysql.com/doc/refman/8.4/en/create-table.html): primary key and unique constraints, including nullable unique indexes. Primary keys do not require auto-increment.
- [MySQL CREATE INDEX](https://dev.mysql.com/doc/refman/8.4/en/create-index.html): uniqueness and NULL behavior.
- [PostgreSQL indexes](https://www.postgresql.org/docs/18/indexes.html): locating rows and the overhead of maintaining indexes.
- [Python data structures tutorial](https://docs.python.org/3/tutorial/datastructures.html): LIFO stacks and FIFO queues.
- [PostgreSQL transactions tutorial](https://www.postgresql.org/docs/15/tutorial-transactions.html): all-or-nothing operations, transaction boundaries, and rollback.

No sources or expected answers are supplied to the model during inference. This comparison tests prompt behavior, not retrieval-augmented generation. It does not independently verify every generated statement.

## Run

From `backend/`, with Ollama running and the existing project dependencies installed:

```bash
uv run --locked python -m quality.run --variant baseline --split development --output quality/results/baseline-development.json
uv run --locked python -m quality.run --variant candidate --split development --output quality/results/candidate-development-v2.json
uv run --locked python -m quality.run --variant baseline --split holdout --output quality/results/baseline-holdout.json
uv run --locked python -m quality.run --variant candidate --split holdout --output quality/results/candidate-holdout.json
```

The runner sends requests sequentially, saves after every result, and resumes matching output files. It refuses files with a different run fingerprint. To run fresh measurements, choose a new filename. `--repeats 2` runs each case twice; the output must also use a new filename. Errors remain recorded as failures rather than silently retried. These inference runs are separate from offline `pytest`.

Both prompts use the same Qwen3 4B model, JSON schema, 4,096-token context, 1,000-token output cap, temperature 0.3, seed 42, and disabled thinking. The seed helps reproducibility but does not guarantee identical output across hardware/runtime versions. Results include model digest, Ollama version, full feedback, validation errors, token counts, and wall-clock response times (including loading, queueing, and overhead). Time measurements depend on other work running on the Mac.

## Metrics and review

- Response validity: parseable feedback passing the application's schema.
- Score-band agreement: overall score within the predeclared interval; failures count against it.
- Within-topic ordering: strong > partial > incorrect, with all three responses valid.
- Strong-answer missing claims: how many complete reference answers receive no missing-concept claims. This does not prove that all other notes are factual.
- Latency: arithmetic mean and maximum request wall time; these small samples are not percentile or production latency estimates.

Read the feedback manually for factual errors, unearned praise, already-covered concepts, and optional details presented as required. High score-band agreement alone is not a factual-quality pass. Development improvements and held-out outcomes must be reported separately.

## Current application version

The production evaluator uses the frozen candidate in `prompts.json` (`app/evaluation_prompt.py`, version `day4-v2`) with seed 42. The initial unsuccessful candidate remains in `prompts-v1.json` and `results/candidate-development.json`. The selected development result is `candidate-development-v2.json`. Production question generation remains unseeded.

An additional check used `--seed 43` on all 12 cases and is stored in `results/candidate-seed43.json`. Changing the seed is a variation check, not independent validation on new content. Regenerate the comparison using `uv run --locked python -m quality.report`.
