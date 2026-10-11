"""Prepare only synthetic data and isolated per-process configuration."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'outputs' / 'scoped-evaluation'

NOTES = {
 'atlas/Project.md': '''---
title: Atlas Project
type: note
permalink: atlas-project
project: atlas
status: active
---
# Atlas Project
Objective: Build an offline field-report queue for one laptop.
Current state: Parser complete; retry behavior not yet tested.
Accepted decision: Use SQLite for the queue; see [[Queue Decision]].
Blocker: Missing sample for an empty report.
Next authorized action: Add the empty-report fixture and run the parser tests.
Deployment is not authorized.
Recovery marker: ATLAS-42.
Related: [[Queue Decision]], [[Restart Runbook]], [[Release Checklist]].
''',
 'atlas/Queue Decision.md': '''---
title: Queue Decision
type: note
permalink: queue-decision
project: atlas
status: accepted
source_revision: fixture-commit-a1
accepted_at: 2026-10-01
---
# Queue Decision
Atlas queue uses SQLite. This is the accepted source decision at fixture-commit-a1.
Authority fixture: https://github.example.test/portfolio/atlas/pull/7
This reserved-domain URL is synthetic, not a real GitHub acceptance record.
The owner accepted SQLite for a single offline laptop on October 1.
Supersedes [[Queue Archive]]. [[Queue Proposal]] is unapproved.
No live verification of current GitHub approval is available in this vault.
''',
 'atlas/Queue Proposal.md': '''---
title: Queue Proposal
type: note
permalink: queue-proposal
project: atlas
status: draft
updated: 2026-10-09
---
# Queue Proposal
Atlas queue should use PostgreSQL. This newer proposal is NOT approved.
It conflicts with [[Queue Decision]]. Newer timestamp does not grant authority.
Do not treat this proposal as an accepted source decision.
''',
 'atlas/Queue Archive.md': '''---
title: Queue Archive
type: note
permalink: queue-archive
project: atlas
status: superseded
---
# Queue Archive
Atlas queue originally used Redis in an abandoned prototype.
This decision is superseded by [[Queue Decision]] and must not govern current work.
''',
 'atlas/Restart Runbook.md': '''---
title: Restart Runbook
type: note
permalink: restart-runbook
project: atlas
revision: local-r1
---
# Restart Runbook
Atlas restart instruction: use retry-window 15 seconds.
Runbook marker: REVISION-OLD-15.
This is a local operating note, not a source approval.
''',
 'atlas/Release Checklist.md': '''---
title: Release Checklist
type: note
permalink: release-checklist
project: atlas
---
# Release Checklist
Atlas rollout approval: UNKNOWN. No approval evidence is recorded.
Rollout owner: UNKNOWN. No owner is assigned.
Pending: [[Rollout Approval]] is a missing note, not an approval.
Next permitted action: request approval after the parser tests pass.
Do not infer approval from a checklist or from successful tests.
''',
 'atlas/Meeting Notes.md': '''---
title: Meeting Notes
type: note
permalink: meeting-notes
project: atlas
---
# Meeting Notes
Someone suggested deploying Atlas on Friday, but no decision was made.
The current blocker is still the missing empty-report sample.
''',
 'beacon/Project.md': '''---
title: Beacon Project
type: note
permalink: beacon-project
project: beacon
status: active
---
# Beacon Project
Objective: Build a hosted alert relay for a demo team.
Current state: Load test complete.
Accepted decision: Use PostgreSQL.
Blocker: None recorded.
Next authorized action: Prepare the demo recording.
Recovery marker: BEACON-99.
''',
 'beacon/Restart Runbook.md': '''---
title: Restart Runbook
type: note
permalink: restart-runbook
project: beacon
---
# Restart Runbook
Beacon restart instruction: use retry-window 99 seconds.
Runbook marker: BEACON-99.
''',
}

SCENARIOS = [
 {'id':'S1','name':'Project restart','query':'Atlas project','scope':'atlas','expected':'Recover objective, parser-complete state, SQLite decision, missing empty-report blocker, and add fixture/run tests next action. No deployment authorization.'},
 {'id':'S2','name':'Conflicting decisions','query':'queue','scope':'atlas','expected':'Return accepted SQLite, unapproved newer PostgreSQL, and superseded Redis with statuses. Report current live GitHub approval unverified.'},
 {'id':'S3','name':'Project isolation','query':'restart','scope':'atlas','expected':'Only Atlas retry-window 15; no Beacon 99. Repeat with beacon scope and get Beacon 99.'},
 {'id':'S4','name':'Changed source','query':'restart','scope':'atlas','expected':'After changing Atlas runbook from 15 to 45 seconds, return new content or clearly flag stale data. Inspect immediate state, state after 3 seconds, and state after explicit index refresh.'},
 {'id':'S5','name':'Missing approval','query':'rollout','scope':'atlas','expected':'Return approval UNKNOWN and owner UNKNOWN; missing Rollout Approval note must not become permission to deploy.'},
]

def hashes(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*.md'))}

def environment(tool):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('BASIC_MEMORY_', 'QMD_')) or key in ('INDEX_PATH',):
            del env[key]
    env.update({'PYTHONUTF8':'1','NO_COLOR':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
                'XDG_CONFIG_HOME':str(ROOT/'xdg-config'), 'XDG_CACHE_HOME':str(ROOT/'xdg-cache'),
                'UV_CACHE_DIR':str(ROOT/'uv-cache')})
    if tool == 'bm':
        env.update({'BASIC_MEMORY_CONFIG_DIR':str(ROOT/'bm-config'), 'BASIC_MEMORY_FORCE_LOCAL':'true',
                    'BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED':'false', 'BASIC_MEMORY_AUTO_UPDATE':'false',
                    'BASIC_MEMORY_LOGFIRE_ENABLED':'false','BASIC_MEMORY_LOGFIRE_SEND_TO_LOGFIRE':'false'})
    else:
        env.update({'QMD_CONFIG_DIR':str(ROOT/'qmd-config'), 'INDEX_PATH':str(ROOT/'qmd-state'/'index.sqlite'),
                    'QMD_FORCE_CPU':'1'})
    return env

def command(tool):
    return [str(ROOT/'bm-venv'/'Scripts'/'python.exe'),'-c','import faulthandler; faulthandler.dump_traceback_later(20, repeat=True); from basic_memory.cli.main import app; app()'] if tool=='bm' else [shutil.which('node'),str(ROOT/'qmd-runtime'/'node_modules'/'@tobilu'/'qmd'/'bin'/'qmd')]

def cli(tool,args,label,timeout=120):
    start=time.perf_counter()
    result=subprocess.run(command(tool)+args,env=environment(tool),cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=timeout)
    record={'tool':tool,'args':args,'exit_code':result.returncode,'elapsed_seconds':round(time.perf_counter()-start,3),'stdout':result.stdout,'stderr':result.stderr}
    (ROOT/'logs').mkdir(exist_ok=True)
    (ROOT/'logs'/f'{label}.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({'label':label,'exit_code':result.returncode,'seconds':record['elapsed_seconds'],'stdout_tail':result.stdout[-1700:],'stderr_tail':result.stderr[-700:]}),flush=True)
    return record

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    for name,body in NOTES.items():
        path=OUT/'synthetic-vault'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(body,encoding='utf-8')
    for tool in ('bm','qmd'):
        copy=ROOT/f'{tool}-vault'
        if copy.exists():
            raise RuntimeError('Refusing to replace an existing test vault')
        shutil.copytree(OUT/'synthetic-vault',copy)
    for d in ('bm-config','qmd-config','qmd-state','logs'):
        (ROOT/d).mkdir(exist_ok=True)
    config={'projects':{p:{'path':str(ROOT/'bm-vault'/p),'mode':'local'} for p in ('atlas','beacon')},
            'default_project':None,'semantic_search_enabled':False,'auto_update':False,
            'logfire_enabled':False,'logfire_send_to_logfire':False,'index_changes':True,
            'disable_permalinks':True,'project_root':str(ROOT/'bm-vault'),'log_level':'WARNING'}
    (ROOT/'bm-config'/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    (OUT/'scenario-plan.json').write_text(json.dumps(SCENARIOS,indent=2),encoding='utf-8')
    (OUT/'initial-vault-hashes.json').write_text(json.dumps(hashes(OUT/'synthetic-vault'),indent=2),encoding='utf-8')
    print('Prepared nine Markdown notes, two independent runtime copies, and five frozen scenario expectations.')

if __name__=='__main__':
    if len(sys.argv)==1:
        prepare()
    else:
        cli(sys.argv[1],sys.argv[3:],sys.argv[2])
