"""Verify report evidence and package only the small evaluation artifacts."""
import base64
import hashlib
import json
import shutil
import zipfile
from prepare import ROOT, OUT, hashes

def load(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
bm=load('basic-memory-results.json'); warm=load('basic-memory-ready-recheck.json'); qmd=load('qmd-results.json')
def pick(rows,scenario,tool,scope=None):
    found=[r for r in rows if r['scenario']==scenario and r['tool']==tool and (scope is None or r['arguments'].get('project')==scope or r['arguments'].get('collections')==[scope])]
    assert len(found)==1,(scenario,tool,scope,len(found))
    return found[0]['response']['result']
def bmdata(result):return result['structuredContent']['result']
def text(result):
    return '\n'.join(c.get('text',c.get('resource',{}).get('text','')) for c in result.get('content',[]))
checks={}
def check(name,condition):
    checks[name]=bool(condition)
    assert condition,name

initial=load('initial-vault-hashes.json')
check('original_nine_note_vault_unchanged',hashes(OUT/'synthetic-vault')==initial and len(initial)==9)
for tool,file in [('bm','basic-memory-source-check.json'),('qmd','qmd-source-check.json')]:
    record=load(file)
    check(tool+'_runtime_started_with_identical_bytes',record['before']==initial)
    check(tool+'_only_intentional_source_change',record['changed_paths']==['atlas/Restart Runbook.md'] and hashes(ROOT/f'{tool}-vault')==record['after'])
check('bm_ready_project_contains_five_fields',all(s in bmdata(pick(warm,'S1-ready','read_note'))['content'] for s in ['Objective:','Current state:','Accepted decision:','Blocker:','Next authorized action:']))
check('qmd_project_contains_five_fields',all(s in text(pick(qmd,'S1','get')) for s in ['Objective:','Current state:','Accepted decision:','Blocker:','Next authorized action:']))
check('bm_status_filter_selects_only_accepted_note',[r['title'] for r in bmdata(pick(warm,'S2-filtered-ready','search_notes'))['results']]==['Queue Decision'])
check('bm_unfiltered_accepted_note_ranks_third',[r['title'] for r in bmdata(pick(warm,'S2-ready','search_notes'))['results']][:3]==['Queue Archive','Queue Proposal','Queue Decision'])
check('qmd_unfiltered_accepted_note_ranks_third',[r['title'] for r in pick(qmd,'S2','query')['structuredContent']['results']][:3]==['Queue Archive','Queue Proposal','Queue Decision'])
for tool,rows,name in [('bm',bm,'search_notes'),('qmd',qmd,'query')]:
    result=pick(rows,'S3',name,'atlas')
    check(tool+'_atlas_scope_excludes_beacon','BEACON-99' not in json.dumps(result) and 'beacon/' not in json.dumps(result).lower())
check('bm_immediate_read_old','REVISION-OLD-15' in bmdata(pick(bm,'S4-immediate','read_note'))['content'])
check('bm_later_read_new','REVISION-NEW-45' in bmdata(pick(bm,'S4-after-3s','read_note'))['content'])
check('qmd_later_read_still_old','REVISION-OLD-15' in text(pick(qmd,'S4-after-3s','get')))
check('qmd_refreshed_read_new','REVISION-NEW-45' in text(pick(qmd,'S4-after-refresh','get')))
check('bm_missing_note_content_null',bmdata(pick(bm,'S5-missing','read_note'))['content'] is None)
check('qmd_missing_note_error',pick(qmd,'S5-missing','get')['isError'] is True)
check('qmd_snippet_label_disagrees_with_file','4: title: Queue Archive' in pick(qmd,'S2','query')['structuredContent']['results'][0]['snippet'] and (OUT/'synthetic-vault'/'atlas'/'Queue Archive.md').read_text().splitlines()[1]=='title: Queue Archive')
qmdmeta=load('qmd-npm.json')
digest=base64.b64encode(hashlib.sha512((ROOT/'packages'/'qmd-2.8.3.tgz').read_bytes()).digest()).decode()
check('qmd_tarball_matches_registry_integrity','sha512-'+digest==qmdmeta['dist']['integrity'])

(OUT/'evidence-verification.json').write_text(json.dumps({'purpose':'Artifact consistency checks, not an accuracy score or additional benchmark cases','checks':checks},indent=2),encoding='utf-8')
deps=(OUT/'basic-memory-dependencies.txt').read_text(encoding='utf-8-sig')
portable='\n'.join('basic-memory==0.23.2' if line.startswith('basic-memory @ ') else line for line in deps.splitlines())+'\n'
(OUT/'basic-memory-requirements.txt').write_text(portable,encoding='utf-8')
for file in ('package.json','package-lock.json'):
    shutil.copyfile(ROOT/'qmd-runtime'/file, OUT/f'qmd-{file}')
archive=OUT.parent/'scoped-evaluation-evidence.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():z.write(p,'outputs/scoped-evaluation/'+p.relative_to(OUT).as_posix())
    for name in ('prepare.py','probe.py','run_bm.py','run_qmd.py','recheck_bm.py','verify_and_package.py'):
        z.write(ROOT/name,'work/scoped-evaluation/'+name)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps({'evidence_checks':len(checks),'passed':sum(checks.values()),'archive_bytes':archive.stat().st_size,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
