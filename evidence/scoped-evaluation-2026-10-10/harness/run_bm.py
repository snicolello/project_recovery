import json
import time
from prepare import ROOT, OUT, hashes
from probe import Client

client=Client('bm','bm-five-scenarios')
records=[]
def call(scenario,name,arguments):
    start=time.perf_counter()
    response=client.call('tools/call',{'name':name,'arguments':arguments})
    record={'scenario':scenario,'tool':name,'arguments':arguments,'response':response,'seconds':round(time.perf_counter()-start,4)}
    records.append(record)
    (OUT/'basic-memory-results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(json.dumps({'scenario':scenario,'tool':name,'error':response.get('error') or response.get('result',{}).get('isError',False),'bytes':len(json.dumps(response).encode()),'seconds':record['seconds']}),flush=True)
    return response
def search(scenario,query,scope,**extra):
    return call(scenario,'search_notes',{'query':query,'project':scope,'search_type':'text','page_size':10,'output_format':'json',**extra})
def get(scenario,name,scope='atlas'):
    return call(scenario,'read_note',{'identifier':name,'project':scope,'output_format':'json','include_frontmatter':True})

before=hashes(ROOT/'bm-vault')
try:
    client.initialize()
    call('setup','list_memory_projects',{'output_format':'json'})
    search('S1','Atlas project','atlas')
    get('S1','Atlas Project')
    call('S1-context','build_context',{'url':'memory://atlas-project','project':'atlas','depth':1,'timeframe':None,'output_format':'json'})
    search('S2','queue','atlas')
    for name in ('Queue Decision','Queue Proposal','Queue Archive'):get('S2',name)
    search('S2-filtered','queue','atlas',status='accepted')
    search('S3','restart','atlas')
    get('S3','Restart Runbook')
    search('S3','restart','beacon')
    get('S3','Restart Runbook','beacon')
    path=ROOT/'bm-vault'/'atlas'/'Restart Runbook.md'
    text=path.read_text(encoding='utf-8')
    path.write_text(text.replace('local-r1','local-r2').replace('15 seconds','45 seconds').replace('REVISION-OLD-15','REVISION-NEW-45'),encoding='utf-8')
    search('S4-immediate','restart','atlas')
    get('S4-immediate','Restart Runbook')
    time.sleep(3)
    search('S4-after-3s','restart','atlas')
    get('S4-after-3s','Restart Runbook')
    search('S5','rollout','atlas')
    get('S5','Release Checklist')
    get('S5-missing','Rollout Approval')
finally:
    client.close()
    after=hashes(ROOT/'bm-vault')
    (OUT/'basic-memory-source-check.json').write_text(json.dumps({'before':before,'after':after,'changed_paths':[k for k in set(before)|set(after) if before.get(k)!=after.get(k)],'intentional_change':'atlas/Restart Runbook.md'},indent=2),encoding='utf-8')
