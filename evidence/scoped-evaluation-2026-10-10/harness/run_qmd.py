import json
import time
from prepare import ROOT, OUT, hashes, cli
from probe import Client

client=Client('qmd','qmd-five-scenarios')
records=[]
def call(scenario,name,arguments):
    start=time.perf_counter()
    response=client.call('tools/call',{'name':name,'arguments':arguments})
    record={'scenario':scenario,'tool':name,'arguments':arguments,'response':response,'seconds':round(time.perf_counter()-start,4)}
    records.append(record)
    (OUT/'qmd-results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(json.dumps({'scenario':scenario,'tool':name,'error':response.get('error') or response.get('result',{}).get('isError',False),'bytes':len(json.dumps(response).encode()),'seconds':record['seconds']}),flush=True)
    return response
def search(scenario,query,scope):
    return call(scenario,'query',{'searches':[{'type':'lex','query':query}],'collections':[scope],'limit':10,'rerank':False})
def get(scenario,file):return call(scenario,'get',{'file':f'qmd://{file}','maxLines':60,'lineNumbers':True})

before=hashes(ROOT/'qmd-vault')
try:
    client.initialize()
    call('setup','status',{})
    search('S1','Atlas project','atlas')
    get('S1','atlas/Project.md')
    search('S2','queue','atlas')
    for name in ('Queue Decision','Queue Proposal','Queue Archive'):get('S2',f'atlas/{name}.md')
    search('S3','restart','atlas')
    get('S3','atlas/Restart Runbook.md')
    search('S3','restart','beacon')
    get('S3','beacon/Restart Runbook.md')
    path=ROOT/'qmd-vault'/'atlas'/'Restart Runbook.md'
    text=path.read_text(encoding='utf-8')
    path.write_text(text.replace('local-r1','local-r2').replace('15 seconds','45 seconds').replace('REVISION-OLD-15','REVISION-NEW-45'),encoding='utf-8')
    call('S4-immediate','status',{})
    search('S4-immediate','restart','atlas')
    get('S4-immediate','atlas/Restart Runbook.md')
    time.sleep(3)
    get('S4-after-3s','atlas/Restart Runbook.md')
    cli('qmd',['update'],'qmd-explicit-refresh')
    search('S4-after-refresh','restart','atlas')
    get('S4-after-refresh','atlas/Restart Runbook.md')
    search('S5','rollout','atlas')
    get('S5','atlas/Release Checklist.md')
    get('S5-missing','atlas/Rollout Approval.md')
finally:
    client.close()
    after=hashes(ROOT/'qmd-vault')
    (OUT/'qmd-source-check.json').write_text(json.dumps({'before':before,'after':after,'changed_paths':[k for k in set(before)|set(after) if before.get(k)!=after.get(k)],'intentional_change':'atlas/Restart Runbook.md'},indent=2),encoding='utf-8')
