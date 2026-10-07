"""Capture exact independent zero-native candidate replay and mutation probes."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'cases/simlox-air-support/I03-var06-out-ignored-duration-v1.0.0'
OUT = ROOT / 'tmp/i03-var06-root-independent-pure-20261008'
PINS = {
    'review/independent_replay.py': 'c3727fff989fff711482371c89298c4f2b147eea6e07f0610406897459979836',
    'review/independent_self_check.py': '1b0ae63dbf3c829d96024fa13874a9a0bf61038acbac5fbd6b7920f41b7eac0e',
}

def seal(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

assert not OUT.exists()
OUT.mkdir()
receipt = {'schema': 'issue18-i03-var06-root-independent-pure/v1',
           'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'native_process_started': False, 'decision': 'NO_GO', 'calls': [], 'sources': {}}
try:
    for rel, sha in PINS.items():
        receipt['sources'][rel] = seal(CASE / rel)
        assert receipt['sources'][rel]['sha256'] == sha
    for name, rel, args in [('control-only', 'review/independent_replay.py', ['--control-only']),
                            ('mutation-probes', 'review/independent_self_check.py', [])]:
        command = [sys.executable, '-X', 'utf8', '-B', str(CASE / rel), *args]
        so, se = OUT / (name + '-stdout.bin'), OUT / (name + '-stderr.bin')
        with so.open('xb') as out, se.open('xb') as err:
            result = subprocess.run(command, cwd=ROOT, stdout=out, stderr=err)
        receipt['calls'].append({'command': command, 'exit_code': result.returncode,
                                 'stdout': seal(so), 'stderr': seal(se)})
        assert result.returncode == 0 and se.read_bytes() == b''
        print(so.read_bytes().decode('utf-8'))
    for rel in PINS:
        assert seal(CASE / rel) == receipt['sources'][rel]
    assert not (CASE / 'runs/i03-var06-out-dt4-v100-ssh-20261008-01').exists()
    receipt['decision'] = 'INDEPENDENT_PURE_CANDIDATE_REPLAY_PASS'
except BaseException as exc:
    receipt['error'] = f'{type(exc).__name__}: {exc}'
    raise
finally:
    receipt['completed_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    (OUT / 'receipt.json').write_bytes((json.dumps(receipt, indent=2) + '\n').encode('utf-8'))
    for p in OUT.iterdir():
        if p.is_file(): p.chmod(0o444)
    print(json.dumps({'decision': receipt['decision'], 'receipt': str(OUT / 'receipt.json')}))
