"""Recheck S1/S2 on the populated index; retain the initial-run evidence."""
import json
from prepare import ROOT, OUT
from probe import Client

path=ROOT/'bm-config'/'config.json'
config=json.loads(path.read_text(encoding='utf-8'))
(OUT/'basic-memory-initial-config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
config['default_project']='atlas'
path.write_text(json.dumps(config,indent=2),encoding='utf-8')
client=Client('bm','bm-ready-recheck')
records=[]
try:
    client.initialize()
    actions=[
      ('setup-remedy','list_memory_projects',{'output_format':'json'}),
      ('S1-ready','search_notes',{'query':'Atlas project','project':'atlas','search_type':'text','output_format':'json'}),
      ('S1-ready','read_note',{'identifier':'Atlas Project','project':'atlas','output_format':'json','include_frontmatter':True}),
      ('S1-context-ready','build_context',{'url':'memory://atlas-project','project':'atlas','depth':1,'timeframe':None,'output_format':'json'}),
      ('S2-ready','search_notes',{'query':'queue','project':'atlas','search_type':'text','output_format':'json'}),
      ('S2-filtered-ready','search_notes',{'query':'queue','project':'atlas','status':'accepted','search_type':'text','output_format':'json'}),
    ]
    for scenario,name,args in actions:
        response=client.call('tools/call',{'name':name,'arguments':args})
        records.append({'scenario':scenario,'tool':name,'arguments':args,'response':response})
        print(json.dumps({'scenario':scenario,'error':response.get('error') or response.get('result',{}).get('isError',False),'bytes':len(json.dumps(response).encode())}),flush=True)
    (OUT/'basic-memory-ready-recheck.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
finally:client.close()
