import asyncio,json
from pathlib import Path
from app.provider import evaluate_answer
from app.evaluation_prompt import EVALUATION_PROMPT_VERSION

async def main():
    directory=Path('quality')
    cases=json.loads((directory/'cases.json').read_text())
    expected=json.loads((directory/'results/candidate-development-v2.json').read_text())['rows']
    rows=[]
    for case_id in ('keys-strong','keys-incorrect'):
        case=next(case for case in cases if case['id']==case_id)
        feedback=await evaluate_answer(case['role'],case['topic'],case['difficulty'],case['question'],case['answer'])
        reference=next(row['feedback'] for row in expected if row['id']==case_id)
        rows.append({'id':case_id,'feedback':feedback.model_dump(),'matches_benchmark':feedback.model_dump()==reference})
    result={'prompt_version':EVALUATION_PROMPT_VERSION,'rows':rows}
    (directory/'results/production-parity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if not all(row['matches_benchmark'] for row in rows):
        raise SystemExit('Live production feedback differs from the benchmark; review results before claiming parity.')
asyncio.run(main())
