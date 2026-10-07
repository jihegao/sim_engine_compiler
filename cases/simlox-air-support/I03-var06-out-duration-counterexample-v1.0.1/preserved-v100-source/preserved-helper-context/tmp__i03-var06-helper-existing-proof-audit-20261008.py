"""Adjudicate existing SSH0 fixture bytes after root wrapper assertion failure.

No test is repeated. The intentional session observation failure must stay null
and rejected; no observation is invented for that PID.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'tmp/i03-var06-helper-ssh0-proof-20261008'
FIXTURE = ROOT / 'tmp/i03-var06-helper-ssh0-fixture-20261008'
OUT = ROOT / 'tmp/i03-var06-helper-existing-proof-audit-20261008'
GUARD = ROOT / 'tmp/i03-var06-owner-guard-20261008.ps1'

def seal(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

assert not OUT.exists()
OUT.mkdir()
receipt = {'schema': 'issue18-i03-var06-existing-helper-proof-audit/v1',
           'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'helper_test_repeated': False, 'native_simlox_started': False, 'decision': 'NO_GO'}
try:
    original = json.loads((OLD / 'receipt.json').read_bytes())
    assert original['decision'] == 'NO_GO' and original['error'] == 'AssertionError: '
    test_call = original['calls']['helper-test']
    assert test_call['exit_code'] == 0 and test_call['stderr']['bytes'] == 0
    for stem, key in [('helper-test-stdout.bin', 'stdout'), ('helper-test-stderr.bin', 'stderr')]:
        assert seal(OLD / stem) == test_call[key]
    data = json.loads((FIXTURE / 'receipt.json').read_bytes().decode('utf-8-sig'))
    assert seal(FIXTURE / 'receipt.json') == original['fixture_receipt']
    assert data['passed'] is True and data['native_process_started'] is False
    assert data['session_id'] == 0 and data['semantic_rejections'] == 17
    assert len(data['records']) == 5
    assert [r['exit_code'] for r in data['records']] == [0, 7, 0, 0, 0]
    assert data['injected_observation_joined'] is True
    assert data['injected_drain_setup_joined'] is True and data['injected_async_drain_large_joined'] is True
    for i, row in enumerate(data['records']):
        assert type(row['child_pid']) is int and row['child_pid'] > 0
        assert type(row['exit_code']) is int
        assert row['child_session_id'] == (None if i == 2 else 0)
        assert (row['capture_error'] is None) if i < 2 else bool(row['capture_error'])
        if i == 2:
            assert 'injected post-Start session observation failure' in row['capture_error']
        for stream, expected in [('stdout', bytes([79,85,84,255,0,13,10,65,128,10])),
                                 ('stderr', bytes([69,82,82,254,0,13,10,66,129,10]))]:
            path = Path(row[stream + '_path'])
            assert path.parent == FIXTURE
            assert path.read_bytes() == expected * (131072 if i == 4 else 1)
            assert seal(path) == {'bytes': row[stream + '_bytes'], 'sha256': row[stream + '_sha256']}
    command = ['ssh', '-n', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
               '-i', 'C:/Users/user/.ssh/id_rsa', 'user@127.0.0.1',
               'powershell.exe', '-NoProfile', '-NonInteractive', '-File', GUARD.as_posix()]
    with (OUT / 'guard-after-stdout.bin').open('xb') as so, (OUT / 'guard-after-stderr.bin').open('xb') as se:
        result = subprocess.run(command, cwd=ROOT, stdout=so, stderr=se)
    assert result.returncode == 0 and (OUT / 'guard-after-stderr.bin').read_bytes() == b''
    guard = json.loads((OUT / 'guard-after-stdout.bin').read_bytes().decode('utf-8-sig'))
    assert guard['ssh_present'] is True and guard['self_session'] == 0 and guard['powershell_major'] == 5
    assert guard['mutex_free'] is True and guard['candidate_run_exists'] is False
    assert guard['runner_candidates'] == [] and guard['active_gui_session1_count'] == 1
    assert len(guard['native']) == 1
    gui = guard['native'][0]
    assert (gui['pid'], gui['session'], gui['start_ms'], gui['responding']) == (13340, 1, 1790590196826, True)
    receipt['original_files'] = {str(p.relative_to(ROOT)): seal(p) for folder in (OLD, FIXTURE)
                                 for p in sorted(folder.iterdir()) if p.is_file()}
    receipt['guard_after'] = {'command': command, 'exit_code': result.returncode,
                              'stdout': seal(OUT / 'guard-after-stdout.bin'), 'stderr': seal(OUT / 'guard-after-stderr.bin')}
    receipt['decision'] = 'EXISTING_SSH0_FIXTURE_BYTES_PASS_ROOT_WRAPPER_FAILURE_RETAINED'
    receipt['limit'] = 'Injected observation failure PID session remains unobserved and rejected. This does not authorize case preflight or native execution.'
except BaseException as exc:
    receipt['error'] = f'{type(exc).__name__}: {exc}'
    raise
finally:
    receipt['completed_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    (OUT / 'receipt.json').write_bytes((json.dumps(receipt, indent=2) + '\n').encode('utf-8'))
    for p in OUT.iterdir():
        if p.is_file():
            p.chmod(0o444)
    print(json.dumps({'decision': receipt['decision'], 'receipt': str(OUT / 'receipt.json'), 'error': receipt.get('error')}))
