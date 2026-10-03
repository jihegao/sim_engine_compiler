"""Independent, read-only replay of the D07.var04 child failure-rate rejection."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'd07-var04-child-frt-v100-ssh-20261003-01'
PARENT_DIR = ROOT / 'D07-var02-dual-opid-v1.0.0'
PARENT = PARENT_DIR / 'native-input.json'
PARENT_RUN = PARENT_DIR / 'runs' / 'd07-var02-dual-opid-v100-ssh-20261003-01'
SOURCE = CASE / 'native-input.json'
OUT = Path(__file__).with_name('independent-readonly-2026-10-03.json')
EXTERNAL = {
    'manual': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
    'dictionary': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),
    'python': Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    'simlox_exe': Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
}
count, failures = 0, []


def check(ok, label):
    global count
    count += 1
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    raw = path.read_text(encoding='utf-8-sig')
    out = []
    quoted = escaped = False
    for pos, char in enumerate(raw):
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif char == ',':
            nxt = pos + 1
            while nxt < len(raw) and raw[nxt].isspace():
                nxt += 1
            if nxt == len(raw) or raw[nxt] not in '}]':
                out.append(char)
        else:
            out.append(char)
    return json.loads(''.join(out))


def tables(path, root):
    return {t['name']: t for t in load(path)[root]['tables']}


def rows(table):
    return [row for instance in table['instances'] for row in instance['rows']]


def records(table):
    fields = [col['name'] for col in table['columns']]
    return [dict(zip(fields, row)) for row in rows(table)]


def at(log, time, fragment):
    return any(line.startswith('Time: ' + str(time) + ' ') and fragment in line
               for line in log.splitlines())


def close(actual, expected):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=.0007)


def occupancy(a, b, start):
    return 2 * max(0, min(b, start + .5) - max(a, start))


contract, diff = load(CASE / 'contract.json'), load(CASE / 'parent-diff.json')
check(sha(PARENT) == contract['parent']['input_sha256'], 'accepted parent source')
check(sha(PARENT_RUN / 'closure.json') == contract['parent']['native_closure_sha256'], 'accepted parent closure')
check(sha(PARENT_DIR / 'cli-scope-signoff-2026-10-03.md') == contract['parent']['signoff_sha256'], 'accepted parent signoff')
check(sha(SOURCE) == contract['native_input_sha256'], 'frozen child source')
check(sha(CASE / 'parent-diff.json') == contract['exact_diff_sha256'], 'frozen exact diff')
check(sha(EXTERNAL['manual']) == contract['source']['manual_pdf_sha256'], 'installed manual')
check(sha(EXTERNAL['dictionary']) == contract['source']['installed_dictionary_sha256'], 'installed dictionary')
check(sha(EXTERNAL['simlox_exe']) == 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0', 'installed executable')
parent, child = tables(PARENT, 'model'), tables(SOURCE, 'model')
changed = {name for name in parent if parent[name] != child[name]}
check(set(parent) == set(child) and changed == set(diff['changed_tables']) == {'ItemFailureRate', 'ProblemDescription'} and not diff['added_tables'] and not diff['removed_tables'], 'exact two-table source delta')
for name in changed:
    check(parent[name] == diff['changed_tables'][name]['before'] and child[name] == diff['changed_tables'][name]['after'], 'exact changed table ' + name)
for name in set(parent)-changed:
    check(parent[name] == child[name], 'unchanged source table ' + name)
item_rates = {(r['IID'], r['OPID']): r['FRT'] for r in records(child['ItemFailureRate'])}
system_rates = {(r['SID'], r['OPID']): r['FRT'] for r in records(child['SystemFailureRate'])}
check(item_rates == {('TEACH-LRU-01', 'KM'): 10000} and system_rates == {('TEACH-AIR-01', 'KM'): 5000}, 'child KM10000 exceeds mother KM5000')
check(records(child['Item'])[0]['FRT'] == records(child['System'])[0]['FRT'] == 300000 and records(child['MissionTypeUtilization']) == records(parent['MissionTypeUtilization']), 'OPHOURS and KM utilization unchanged')

inv, closure = load(RUN / 'invocation.json'), load(RUN / 'closure.json')
check(inv['run_id'] == closure['run_id'] == RUN.name and closure['error'] is None, 'run identity/closure')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation SHA seal')
check(inv['input_sha256'] == sha(SOURCE) == sha(RUN / 'input.json') and inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'), 'source/parent/contract invocation pins')
check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'], 'SSH session zero')
check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1, 'mutex and GUI identity')
check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'], 'source stable throughout run')
runner_text = (CASE / 'run_native_ssh.ps1').read_text(encoding='utf-8-sig')
check("UsePrelifeLog).UsePrelifeLog" in runner_text and "if ($optionOriginal -ne 'NO')" in runner_text and "Prelife Log option changed" in runner_text, 'sealed runner checks and restores NO prelife option')
paths = {'input': SOURCE, 'parent': PARENT, 'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-10-03.md', 'parent_closure': PARENT_RUN / 'closure.json', 'manual': EXTERNAL['manual'], 'dictionary': EXTERNAL['dictionary'], 'contract': CASE / 'contract.json', 'builder': CASE / 'build.py', 'exact_diff': CASE / 'parent-diff.json', 'diff_checker': CASE / 'describe_diff.py', 'checker': CASE / 'check_roundtrip.py', 'python': EXTERNAL['python'], 'runner_script': CASE / 'run_native_ssh.ps1', 'simlox_exe': EXTERNAL['simlox_exe']}
for name, path in paths.items():
    check(sha(path) == closure['source_hashes_before'][name], 'source seal ' + name)
check(len(closure['raw']) == 9, 'nine raw SHA seals')
for name, meta in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'], 'raw SHA/byte seal ' + name)
steps = load(RUN / 'steps.json')
check([step['name'] for step in steps] == ['import', 'export', 'calc', 'check_import_export'], 'four native negative-route steps')
for step in steps:
    check(step['exit_code'] == 0 and step['gui_preserved'] and step['error'] is None and step['status'] == ('calc_observed' if step['name'] == 'calc' else 'completed'), 'guarded step ' + step['name'])
check([step['arguments'] for step in steps[:3]] == [command['arguments'] for command in inv['planned_commands']], 'planned native arguments')
export = tables(RUN / 'roundtrip-raw.json', 'model')
populated = [name for name, table in child.items() if rows(table)]
check(len(populated) == 21, '21 populated authored tables')
for name in populated:
    check(name in export and child[name]['columns'] == export[name]['columns'] and child[name]['instances'] == export[name]['instances'], 'exact populated table roundtrip ' + name)
check(records(export['ItemFailureRate']) == records(child['ItemFailureRate']), 'native export preserves KM10000 item rate')
runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig').replace('\r\n', '\n')
check('Form: Item\nrec 1: (error #2041) The sum of item failure rates exceeds failure rate of system: TEACH-AIR-01 (KM)' in runlog, 'exact relevant Item error #2041 text')
check('Input conversion completed. Errors: 1, Warnings: 1, Notes: 0' in runlog and re.findall(r'warning #(\d+)', runlog) == ['108'] and re.findall(r'error #(\d+)', runlog) == ['2041'], 'Errors1 Warnings108 only Notes0')
check((RUN / 'model.sxo').stat().st_size == 4, 'invalid four-byte SXO')
check(not (RUN / 'model.log').exists() and not (RUN / 'report-raw.json').exists() and not (RUN / 'report-export.log').exists(), 'no event log or valid report')
check('report' not in [step['name'] for step in steps], 'invalid model never reached report export')

result = {
    'schema': 'simlox-d07-var04-independent-readonly/v1',
    'passed': not failures, 'verdict': 'GO' if not failures else 'NO-GO',
    'checks_passed': count-len(failures), 'checks_total': count, 'failures': failures,
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'run_log_sha256': sha(RUN / 'run.log'), 'raw_seals': len(closure['raw']),
    'observed': 'The isolated installed-item KM FRT5000 to10000 change exceeds mother system KM FRT5000. Native import/export preserves 21 authored tables; conversion emits exact Item error #2041, one error and warning108, leaving only a four-byte invalid SXO and no report.',
    'limits': [
        'Converter rejection only for one installed LRU, one mother system and one KM mismatch magnitude on this installed executable; no simulation behavior is accepted.',
        'The accepted D07.var02 source/run is the valid boundary control from a prior guarded run, rather than a fresh simultaneous pair.',
        'Other rates and structures, error precedence, GUI visual behavior and cross-engine parity remain unverified.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'], 'checks_total': count, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
