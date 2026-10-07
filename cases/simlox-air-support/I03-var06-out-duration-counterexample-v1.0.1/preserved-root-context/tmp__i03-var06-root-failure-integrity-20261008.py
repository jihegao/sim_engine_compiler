"""Exact original failed-run integrity; this never accepts its behavior contract."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'cases/simlox-air-support/I03-var06-out-ignored-duration-v1.0.0'
RUN = CASE / 'runs/i03-var06-out-dt4-v100-ssh-20261008-01'
OUT = ROOT / 'tmp/i03-var06-root-failure-integrity-20261008.json'

def seal(p):
    raw = p.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def read(p):
    return json.loads(p.read_bytes().decode('utf-8-sig'))

assert not OUT.exists()
manifest = read(CASE / 'prelaunch-manifest.json')
source_map = {item['key']: item['sha256'] for item in manifest['source_files']}
assert len(source_map) == 445
for item in manifest['source_files']:
    assert seal(Path(item['path'])) == {k: item[k] for k in ('bytes', 'sha256')}
inv, closure, failure, steps = [read(RUN / name) for name in ('invocation.json', 'closure.json', 'failure-seal.json', 'steps.json')]
assert inv['run_id'] == closure['run_id'] == failure['run_id'] == RUN.name
assert closure['invocation_sha256'] == seal(RUN / 'invocation.json')['sha256']
assert closure['source_hashes_before'] == closure['source_hashes_after'] == inv['source_hashes_before'] == source_map
assert closure['error'] == closure['step_error'] == failure['error'] == 'child OS exit=1'
files = {p.name: seal(p) for p in sorted(RUN.iterdir()) if p.is_file()}
assert len(files) == 26
assert set(closure['raw']) == set(files) - {'invocation.json', 'closure.json', 'failure-seal.json'}
assert set(failure['files']) == set(files) - {'failure-seal.json'}
assert all(files[k] == v for k, v in closure['raw'].items())
assert all(files[k] == v for k, v in failure['files'].items())
assert seal(RUN / 'input.json')['sha256'] == '3ff558fd5389b1d0e67ec93676a79f9cb00f23823f0514bccf5591c90174f694'
names = ['import', 'export', 'check_import_export', 'calc', 'jsonreport', 'check_behavior']
assert [s['name'] for s in steps] == names
plans = {x['name']: x for x in inv['planned_commands'] + inv['planned_checkers']}
prior = dt.datetime.fromisoformat(inv['created_utc'].replace('Z', '+00:00'))
for i, step in enumerate(steps):
    assert type(step['sequence']) is int and step['sequence'] == i
    assert {k: step[k] for k in ('name', 'program', 'arguments')} == plans[step['name']]
    assert type(step['child_pid']) is int and step['child_pid'] > 0
    assert type(step['child_session_id']) is int and step['child_session_id'] == 0
    assert type(step['exit_code']) is int and step['exit_code'] == (1 if i == 5 else 0)
    assert step['status'] == ('failed' if i == 5 else 'completed')
    assert step['error'] == ('child OS exit=1' if i == 5 else None)
    assert step['capture_error'] is None and step['gui_preserved'] is True
    started = dt.datetime.fromisoformat(step['started_utc'].replace('Z', '+00:00'))
    ended = dt.datetime.fromisoformat(step['completed_utc'].replace('Z', '+00:00'))
    assert prior <= started <= ended
    prior = ended
    for stream in ('stdout', 'stderr'):
        p = Path(step[stream + '_path'])
        assert p.parent == RUN and files[p.name] == {'bytes': step[stream + '_bytes'], 'sha256': step[stream + '_sha256']}
    assert step['stderr_bytes'] == 0
author = read(RUN / 'author-validation.json')
assert author['passed'] is False and author['error'] == "AssertionError: (26, 'resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 4')"
assert failure['publication_state'] == 'excluded' and closure['publication_state'] == 'not_published'
result = {'schema': 'issue18-i03-var06-root-failure-integrity/v1',
          'checked_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
          'decision': 'FAILED_RUN_INTEGRITY_PASS_ORIGINAL_BEHAVIOR_NO_GO',
          'native_runs_started_by_audit': 0, 'run_id': RUN.name, 'raw_files': files,
          'manifest': seal(CASE / 'prelaunch-manifest.json'), 'source_records': 445,
          'actual_os_exits': [s['exit_code'] for s in steps],
          'actual_sessions': [s['child_session_id'] for s in steps],
          'failure': author['error'], 'original_run_publication_state': 'excluded'}
OUT.write_bytes((json.dumps(result, indent=2) + '\n').encode('utf-8'))
OUT.chmod(0o444)
print(json.dumps({'decision': result['decision'], 'raw_files': len(files), 'receipt': str(OUT)}))
