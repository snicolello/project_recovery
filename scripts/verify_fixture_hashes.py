import json, hashlib, pathlib, sys

h = json.load(open('fixtures/synthetic-vault-hashes.json', encoding='utf-8'))
root = pathlib.Path('fixtures/synthetic-vault')
files = {p.relative_to(root).as_posix(): p for p in root.rglob('*.md')}
print('hash entries:', type(h).__name__, len(h))
ok = bad = 0
if isinstance(h, dict):
    items = list(h.items())
else:
    items = [(e.get('path') or e.get('file'), e.get('sha256')) for e in h]
for k, v in items:
    key = str(k).replace(chr(92), '/')
    match = next((p for rel, p in files.items() if key.endswith(rel)), None)
    exp = v if isinstance(v, str) else (v.get('sha256') if isinstance(v, dict) else None)
    if match is None:
        print('no file for', key); bad += 1; continue
    got = hashlib.sha256(match.read_bytes()).hexdigest()
    if got == exp:
        ok += 1
    else:
        bad += 1; print('MISMATCH', key, got[:12], str(exp)[:12])
print('ok', ok, 'bad', bad)
sys.exit(1 if bad else 0)
