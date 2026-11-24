"""Generate the Day 4 comparison from saved measurements (no model calls)."""
import json
from pathlib import Path
from quality.run import metrics

HERE=Path(__file__).parent


def build_report():
    cases=json.loads((HERE/'cases.json').read_text())
    def load(name):
        return json.loads((HERE/'results'/name).read_text())
    baseline=load('baseline-development.json')['rows']+load('baseline-holdout.json')['rows']
    updated=load('candidate-development-v2.json')['rows']+load('candidate-holdout.json')['rows']
    alternate=load('candidate-seed43.json')['rows']
    groups={'Baseline (seed 42)':baseline,'Updated (seed 42)':updated,'Updated (seed 43)':alternate}
    totals={name:metrics(rows,cases) for name,rows in groups.items()}
    (HERE/'results/comparison.json').write_text(json.dumps(totals,indent=2)+'\n')
    lines=['# Day 4 — Feedback quality evaluation','', '23 November 2026 · local Qwen3 4B · 12 authored examples across four beginner topics.', '',
        '## Measured results','',
        '| Metric | Baseline, seed 42 | Updated, seed 42 | Updated, seed 43 |',
        '| --- | ---: | ---: | ---: |']
    selectors=[('Valid feedback',lambda x:f"{x['valid_responses']}/{x['requests']}"),
               ('Within declared score band',lambda x:f"{x['in_band']}/{x['requests']}"),
               ('Topics ordered strong > partial > incorrect',lambda x:f"{sum(item['correct_order'] for item in x['ordering'])}/{len(x['ordering'])}"),
               ('Complete answers without missing-concept claims',lambda x:f"{x['strong_answers_without_missing_claims']}/{x['strong_answers']}"),
               ('Mean request time',lambda x:f"{x['mean_seconds']:.2f} s"),('Slowest request',lambda x:f"{x['max_seconds']:.2f} s")]
    for title,selector in selectors:
        lines.append('| '+title+' | '+' | '.join(selector(value) for value in totals.values())+' |')
    lines += ['', 'The baseline already ranked the three answer levels correctly on all four topics. The observed gains are closer agreement with the proposed score bands and fewer missing-concept claims on complete answers; these measurements do not establish factual reliability.', '',
      '## Development versus held-out check','',
      '| Split | Baseline score-band agreement | Updated score-band agreement |',
      '| --- | ---: | ---: |', '| Development (keys, indexes) | 4/6 | 5/6 |', '| Held-out topics (queues, transactions) | 5/6 | 6/6 |', '',
      'The first candidate prompt reduced missing-concept claims but tied the strong and partial indexing answers. Its development results are preserved in `candidate-development.json` and its prompt in `prompts-v1.json`. Category-specific anchors were then added using only development results. The final candidate was frozen before running the held-out comparison. No expected labels, bands, reference answers, or source material were sent to the model.', '',
      '## Per-answer scores','', '| Example | Split | Proposed range | Baseline | Updated | Updated, seed 43 |', '| --- | --- | --- | ---: | ---: | ---: |']
    for case in cases:
        scores=[]
        for rows in groups.values():
            row=next(row for row in rows if row['id']==case['id'])
            scores.append(str(row.get('feedback',{}).get('score','ERROR')))
        lines.append(f"| {case['id']} | {case['split']} | {case['expected_score'][0]}–{case['expected_score'][1]} | "+' | '.join(scores)+' |')
    lines += ['', '## Remaining problems found in manual review','',
      '- The very brief indexing answer remains over-scored: 8.0 at seed 42 and 8.8 at seed 43, above its predeclared 3–7.9 range. This is not hidden by changing the acceptance band.',
      '- Some suggestions repeat information already present. For example, the complete indexing answer already says an index can be slower on small tables, yet the revised feedback asks for that clarification again.',
      '- One revised partial-key response says a primary key enforces referential integrity. That wording is too broad: primary keys enforce unique/non-null identity; foreign-key constraints enforce references. See the [MySQL constraint documentation](https://dev.mysql.com/doc/refman/8.4/en/create-table.html).',
      '- A complete stack/queue answer received 10/10 but an empty strengths list. The response schema permits that, but it is weak coaching.',
      '- The earlier Day 3 NULL-handling hallucination was not reproduced in these outputs; absence in this small set does not prove it is fixed.', '',
      '## What changed in the application','',
      '`app/evaluation_prompt.py` now holds the frozen `day4-v2` prompt. It emphasizes reading the whole answer, essential coverage, independent category ratings, and not demanding optional advanced material. Evaluation requests use seed 42, matching the primary measurement. Question generation remains unseeded. Feedback schema, routes, frontend, session flow, context size, and token limits are unchanged.', '',
      'The actual production provider was also run on the strong and incorrect key cases. See `production-parity.json` for whether the full feedback matched the benchmark exactly. Run `uv run --locked python -m quality.verify_production` from `backend/` to repeat this check.', '',
      '## Reproduce and inspect','',
      'See [benchmark instructions](../backend/quality/README.md), [reference cases](../backend/quality/cases.json), [frozen prompts](../backend/quality/prompts.json), and [raw results](../backend/quality/results/). Regenerate this report from `backend/` using:', '',
      '```bash', 'uv run --locked python -m quality.report', '```', '',
      'Run the independent seed check using a fresh output filename:', '',
      '```bash', 'uv run --locked python -m quality.run --variant candidate --split all --seed 43 --output quality/results/candidate-seed43.json', '```', '',
      'Offline regression checks: **71 tests passed**. The existing upstream Starlette/httpx TestClient deprecation warning remains. No new dependencies or UI changes were needed.', '',
      '## Limits','',
      'The labels and score bands were authored for this project, not independently validated by expert raters. The set covers only four fixed beginner questions in two subject areas. The revised prompt has one held-out-topic check and one additional random seed, not a broad reliability study. All current benchmark runs use the same model digest and machine. Request wall times include queueing, cache effects, model loading, and overhead; the run order was not randomized, so lower observed latency is not a controlled causal speedup.', '',
      'Further work should add new independently reviewed topics, paraphrased answers/questions, partial-but-correct answers, mixed factual errors, and instruction-injection cases, with multiple raters/seeds. Reusing the current held-out topics for tuning makes them development data for future work. Current feedback remains coaching guidance and can be wrong.']
    path=HERE.parents[1]/'docs/day4-quality-report.md'
    path.write_text('\n'.join(lines)+'\n')
    print(path)
    print(json.dumps(totals))


if __name__=='__main__':
    build_report()
