"""Root-owned one-shot harmless SSH0 byte-capture test; never starts SIMLOX."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'cases/simlox-air-support/I03-var06-out-ignored-duration-v1.0.0'
OUT = ROOT / 'tmp/i03-var06-helper-ssh0-proof-20261008'
FIXTURE_OUT = ROOT / 'tmp/i03-var06-helper-ssh0-fixture-20261008'
GUARD = ROOT / 'tmp/i03-var06-owner-guard-20261008.ps1'
PINS = {
    'captured_process.ps1': '17285b90093c2d80c6241e1345b9926a2e4dd0f0b2b24f831c84c1cfa885b794',
    'test_captured_process.ps1': '22112fc0decf89fa8b704b4c47ea1397f090b6e042895122ca8f28abc94f9ac8',
    'binary_capture_child.py': '52f28d5d705efad0fa035ab5031a96da5fa6a27571a2d9bb8f46648e5800c35e',
    'review/independent-helper-test-only-go-2026-10-08.md': '13c2b365fa918e8279d55747daa22dfd9823d69b3e831c3b22c4b510599063eb',
}

def seal(p):
    b = p.read_bytes()
    return {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}

def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def call(name, file, args=()):
    command = ['ssh', '-n', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
               '-i', 'C:/Users/user/.ssh/id_rsa', 'user@127.0.0.1',
               'powershell.exe', '-NoProfile', '-NonInteractive', '-File',
               file.as_posix(), *args]
    out, err = OUT / (name + '-stdout.bin'), OUT / (name + '-stderr.bin')
    started = utc()
    with out.open('xb') as so, err.open('xb') as se:
        result = subprocess.run(command, cwd=ROOT, stdout=so, stderr=se)
    record = {'command': command, 'started_utc': started, 'completed_utc': utc(),
              'exit_code': result.returncode, 'stdout': seal(out), 'stderr': seal(err)}
    records[name] = record
    assert result.returncode == 0 and err.read_bytes() == b'', record
    return out

def guard(name):
    data = json.loads(call(name, GUARD).read_bytes().decode('utf-8-sig'))
    assert data['ssh_present'] is True and data['self_session'] == 0 and data['powershell_major'] == 5
    assert data['mutex_free'] is True and data['candidate_run_exists'] is False
    assert data['runner_candidates'] == [] and data['active_gui_session1_count'] == 1
    assert len(data['native']) == 1
    gui = data['native'][0]
    assert (gui['pid'], gui['session'], gui['start_ms'], gui['responding']) == (13340, 1, 1790590196826, True)

assert not OUT.exists() and not FIXTURE_OUT.exists()
OUT.mkdir()
records = {}
receipt = {'schema': 'issue18-i03-var06-root-helper-ssh0-proof/v1',
           'started_utc': utc(), 'native_simlox_started': False, 'decision': 'NO_GO',
           'source_pins': {}, 'calls': records}
try:
    assert seal(GUARD)['sha256'] == 'c50ec56b4866f2b982a0d8ecc118afef72c7f9d101a809ce00d42559bed7ea9d'
    for rel, sha in PINS.items():
        observed = seal(CASE / rel)
        assert observed['sha256'] == sha, rel
        receipt['source_pins'][rel] = observed
    guard('guard-before')
    call('helper-test', CASE / 'test_captured_process.ps1', ['-OutputDirectory', FIXTURE_OUT.as_posix()])
    data = json.loads((FIXTURE_OUT / 'receipt.json').read_bytes().decode('utf-8-sig'))
    receipt['fixture_receipt'] = seal(FIXTURE_OUT / 'receipt.json')
    receipt['fixture_summary'] = data
    assert data['session_id'] == 0 and data['passed'] is True
    assert data['native_process_started'] is False and data['semantic_rejections'] == 17
    assert data['helper_sha256'] == PINS['captured_process.ps1']
    assert data['test_sha256'] == PINS['test_captured_process.ps1']
    assert data['child_sha256'] == PINS['binary_capture_child.py']
    assert len(data['records']) == 5
    assert [r['exit_code'] for r in data['records']] == [0, 7, 0, 0, 0]
    assert all(type(r['child_pid']) is int and r['child_pid'] > 0 and r['child_session_id'] == 0 for r in data['records'])
    guard('guard-after')
    for rel, sha in PINS.items():
        assert seal(CASE / rel)['sha256'] == sha, rel
    receipt['fixture_files'] = {p.name: seal(p) for p in sorted(FIXTURE_OUT.iterdir()) if p.is_file()}
    receipt['decision'] = 'SSH0_HELPER_PROOF_PASS'
except BaseException as exc:
    receipt['error'] = f'{type(exc).__name__}: {exc}'
    raise
finally:
    receipt['completed_utc'] = utc()
    (OUT / 'receipt.json').write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    for folder in (OUT, FIXTURE_OUT):
        if folder.exists():
            for p in folder.iterdir():
                if p.is_file():
                    p.chmod(0o444)
    print(json.dumps({'decision': receipt['decision'], 'receipt': str(OUT / 'receipt.json'), 'error': receipt.get('error')}))
