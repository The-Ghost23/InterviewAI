import json
from pathlib import Path
from quality.run import metrics


def row(level, score, missing=None, repeat=1):
    return {'id':f'g-{level}','group':'g','level':level,'repeat':repeat,'seconds':2.0,'in_band':True,
            'feedback':{'score':score,'missing_concepts':missing or []}}


def test_quality_metrics_count_failures_in_denominator():
    rows=[row('strong',9),row('partial',5),{'id':'g-incorrect','group':'g','level':'incorrect','repeat':1,'seconds':120,'error':'timeout','in_band':False}]
    result=metrics(rows,[{'group':'g'}])
    assert result['requests']==3
    assert result['valid_responses']==2
    assert result['in_band']==2
    assert result['ordering'][0]['correct_order'] is False
    assert result['mean_seconds']==41.33
    assert result['max_seconds']==120


def test_quality_order_requires_strict_separation():
    result=metrics([row('strong',9),row('partial',9),row('incorrect',0)],[{'group':'g'}])
    assert result['ordering'][0]['correct_order'] is False
    assert metrics([row('strong',9),row('partial',5),row('incorrect',0)],[{'group':'g'}])['ordering'][0]['correct_order'] is True


def test_quality_missing_concept_metric_does_not_hide_claims():
    result=metrics([row('strong',9,['An optional detail']),row('partial',5),row('incorrect',0)],[{'group':'g'}])
    assert result['strong_answers']==1
    assert result['strong_answers_without_missing_claims']==0


def test_repeat_ordering_keeps_runs_separate():
    rows=[row('strong',9,repeat=1),row('partial',5,repeat=1),row('incorrect',0,repeat=1),
          row('strong',4,repeat=2),row('partial',6,repeat=2),row('incorrect',0,repeat=2)]
    assert [item['correct_order'] for item in metrics(rows,[{'group':'g'}])['ordering']]==[True,False]


def test_production_prompt_matches_frozen_candidate():
    from app.evaluation_prompt import EVALUATION_PROMPT
    directory=Path(__file__).resolve().parents[1]/'quality'
    assert EVALUATION_PROMPT==json.loads((directory/'prompts.json').read_text())['candidate']


def test_quality_dataset_separates_development_and_holdout_topics():
    directory=Path(__file__).resolve().parents[1]/'quality'
    cases=json.loads((directory/'cases.json').read_text())
    assert len(cases)==len({case['id'] for case in cases})==12
    development={case['group'] for case in cases if case['split']=='development'}
    holdout={case['group'] for case in cases if case['split']=='holdout'}
    assert development.isdisjoint(holdout)
    for group in development|holdout:
        assert {case['level'] for case in cases if case['group']==group}=={'strong','partial','incorrect'}
