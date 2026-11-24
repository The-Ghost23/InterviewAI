"""Run sequential, resumable local-model quality measurements; never a CI test."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import time
from datetime import datetime, timezone
import httpx
from app.config import settings
from app.evaluation import Feedback

HERE = Path(__file__).parent


def metrics(rows, cases):
    bands = sum(row.get('in_band', False) for row in rows)
    valid = sum('feedback' in row for row in rows)
    strong = [row for row in rows if row['level'] == 'strong']
    clean = sum('feedback' in row and not row['feedback']['missing_concepts'] for row in strong)
    order = []
    for repeat in sorted({row['repeat'] for row in rows}):
        for group in sorted({case['group'] for case in cases}):
            group_rows = {row['level']:row for row in rows if row['group']==group and row['repeat']==repeat}
            if len(group_rows)==3:
                ok=all('feedback' in row for row in group_rows.values()) and group_rows['strong']['feedback']['score'] > group_rows['partial']['feedback']['score'] > group_rows['incorrect']['feedback']['score']
                order.append({'group':group,'repeat':repeat,'correct_order':ok})
    latencies=sorted(row['seconds'] for row in rows)
    return {'requests':len(rows),'valid_responses':valid,'in_band':bands,'strong_answers_without_missing_claims':clean,'strong_answers':len(strong),'ordering':order,'mean_seconds':round(sum(latencies)/len(latencies),2) if latencies else None,'max_seconds':max(latencies,default=None)}


async def run(args):
    cases=json.loads((HERE/'cases.json').read_text())
    if args.split != 'all':
        cases=[case for case in cases if case['split']==args.split]
    prompt=json.loads((HERE/'prompts.json').read_text())[args.variant]
    fingerprint=hashlib.sha256(json.dumps({'cases':cases,'prompt':prompt,'model':settings.ollama_model,'repeats':args.repeats,'seed':args.seed},sort_keys=True).encode()).hexdigest()
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    result={'created_at':datetime.now(timezone.utc).isoformat(),'variant':args.variant,'split':args.split,'fingerprint':fingerprint,'model':settings.ollama_model,'options':{'num_ctx':4096,'num_predict':1000,'temperature':0.3,'seed':args.seed},'rows':[]}
    if path.exists():
        result=json.loads(path.read_text())
        if result['fingerprint']!=fingerprint:
            raise SystemExit('Output belongs to a different run. Choose a new output filename.')
    async with httpx.AsyncClient(timeout=httpx.Timeout(120,connect=5)) as client:
        for endpoint,key in [('version','ollama_version'),('tags','installed_models')]:
            response=await client.get(f'{settings.ollama_base_url}/api/{endpoint}')
            response.raise_for_status()
            result[key]=response.json()
        for repeat in range(1,args.repeats+1):
            for case in cases:
                if any(row['id']==case['id'] and row['repeat']==repeat for row in result['rows']):
                    continue
                row={key:case[key] for key in ('id','group','split','level','expected_score')}
                row['repeat']=repeat
                start=time.perf_counter()
                try:
                    response=await client.post(f'{settings.ollama_base_url}/api/chat',json={
                        'model':settings.ollama_model,'stream':False,'think':False,'format':Feedback.model_json_schema(),
                        'keep_alive':'5m','options':result['options'],
                        'messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'role':case['role'],'topic':case['topic'],'difficulty':case['difficulty'],'question':case['question'],'candidate_answer':case['answer']})}],
                    })
                    response.raise_for_status()
                    payload=response.json()
                    row['done_reason']=payload.get('done_reason')
                    row['tokens']=payload.get('eval_count')
                    row['raw_content']=payload['message']['content']
                    if payload.get('done_reason')=='length':
                        raise ValueError('Truncated feedback')
                    feedback=Feedback.model_validate_json(row['raw_content'])
                    row['feedback']=feedback.model_dump()
                    row['in_band']=case['expected_score'][0]<=feedback.score<=case['expected_score'][1]
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    row['error']=f'{type(exc).__name__}: {exc}'
                    row['in_band']=False
                row['seconds']=round(time.perf_counter()-start,3)
                result['rows'].append(row)
                result['metrics']=metrics(result['rows'],cases)
                path.write_text(json.dumps(result,indent=2)+'\n')
                print(f"{args.variant} {case['id']} repeat={repeat} score={row.get('feedback',{}).get('score','ERROR')} seconds={row['seconds']} band={row['in_band']}",flush=True)
    print(json.dumps(result['metrics']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',choices=['baseline','candidate'],required=True)
    parser.add_argument('--split',choices=['development','holdout','all'],default='all')
    parser.add_argument('--repeats',type=int,choices=range(1,6),default=1)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--output',required=True)
    asyncio.run(run(parser.parse_args()))
