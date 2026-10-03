"""Independent, read-only replay of the D07.var03 same-key override."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'd07-var03-same-key-v100-ssh-20261003-01'
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
CUSTOM = ROOT / 'A15-custom-utilization-v1.0.0' / 'per-hour-input.json'
RATE = ROOT / 'D02-var06-traditional-clock-inputs-v1.0.0' / 'native-input-rate-ophours.json'
SETTINGS = ROOT / 'A15-custom-operation-report-v1.0.0' / 'runs' / 'report-settings' / 'operation-remapped-enabled.sxs'
check(sha(PARENT) == contract['parent_input_sha256'], 'accepted D07.var02 source')
check(sha(SOURCE) == contract['input_sha256'], 'frozen same-key child source')
check(sha(CASE / 'parent-diff.json') == contract['exact_diff_sha256'], 'exact diff SHA')
check(sha(EXTERNAL['manual']) == contract['manual_sha256'], 'manual SHA')
check(sha(EXTERNAL['dictionary']) == '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0', 'dictionary SHA')
check(sha(EXTERNAL['simlox_exe']) == 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0', 'executable SHA')
check(sha(CUSTOM) == '2100f7d1ae7725962483419571433d64c6ef92f8fb69078dd58f6835d90ed084', 'custom OPID donor')
check(sha(RATE) == 'b76dd77056378ca06c0134ddd363816d9c9ac211e4f36181fb597eca0e9b4797', 'rate schema donor')
check(sha(SETTINGS) == 'c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7', 'selected report settings')
check(sha(PARENT_DIR / 'cli-scope-signoff-2026-10-03.md') == '3962859086bae82a79c8fad64517bf8598a2956536e0c0ee3a83e72dcf997119', 'accepted parent signoff')
check(sha(PARENT_RUN / 'closure.json') == 'd9099af3d6d8c2d935a2c50f4aebdd217fa8e85fc84fd46d7d7dcdb1a6c152cd', 'accepted parent closure')
parent, child = tables(PARENT, 'model'), tables(SOURCE, 'model')
changed = {name for name in parent if parent[name] != child[name]}
check(set(parent) == set(child) and changed == set(diff['changed_tables']) == {'ProblemDescription', 'ItemFailureRate', 'SystemFailureRate'} and not diff['added_tables'] and not diff['removed_tables'], 'exact three-table source delta')
for name in changed:
    check(parent[name] == diff['changed_tables'][name]['before'] and child[name] == diff['changed_tables'][name]['after'], 'exact changed table ' + name)
for name in set(parent)-changed:
    check(parent[name] == child[name], 'unchanged parent table ' + name)
for name, key, ident in (('SystemFailureRate', 'SID', 'TEACH-AIR-01'), ('ItemFailureRate', 'IID', 'TEACH-LRU-01')):
    source_rates = {(r[key], r['OPID']): r['FRT'] for r in records(child[name])}
    check(source_rates == {(ident, 'KM'): 5000, (ident, 'OPHOURS'): 100000}, name + ' KM preserved, OPHOURS same-key 100000')
check(records(child['System'])[0]['FRT'] == records(child['Item'])[0]['FRT'] == 300000 and records(child['System'])[0]['OPID'] == records(child['Item'])[0]['OPID'] == 'OPHOURS', 'base OPHOURS 300000 rows unchanged')
check(records(child['MissionTypeUtilization']) == records(parent['MissionTypeUtilization']) and records(child['OperationParameter']) == records(parent['OperationParameter']), 'KM utilization/source unchanged')

inv, closure = load(RUN / 'invocation.json'), load(RUN / 'closure.json')
check(inv['run_id'] == closure['run_id'] == RUN.name and closure['error'] is None, 'run identity')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation SHA seal')
check(inv['input_sha256'] == sha(SOURCE) == sha(RUN / 'input.json') and inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'), 'source/parent/contract invocation pins')
check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'], 'SSH session zero')
check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1, 'serial queue and GUI preserved')
check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'], 'source stable during run')
paths = {'input': SOURCE, 'parent': PARENT, 'custom': CUSTOM, 'rate': RATE, 'report_settings': SETTINGS, 'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-10-03.md', 'parent_closure': PARENT_RUN / 'closure.json', 'manual': EXTERNAL['manual'], 'dictionary': EXTERNAL['dictionary'], 'exact_diff': CASE / 'parent-diff.json', 'contract': CASE / 'contract.json', 'builder': CASE / 'build.py', 'checker': CASE / 'check_roundtrip.py', 'diff_script': CASE / 'describe_diff.py', 'python': EXTERNAL['python'], 'runner_script': CASE / 'run_native_ssh.ps1', 'simlox_exe': EXTERNAL['simlox_exe']}
for name, path in paths.items():
    check(sha(path) == closure['source_hashes_before'][name], 'source seal ' + name)
check(len(closure['raw']) == 12, 'twelve raw seals')
for name, meta in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'], 'raw seal ' + name)
steps = load(RUN / 'steps.json')
check([step['name'] for step in steps] == ['import', 'export', 'calc', 'report', 'check_import_export'], 'five guarded steps')
for step in steps:
    check(step['exit_code'] == 0 and step['status'] == 'completed' and step['gui_preserved'] and step['error'] is None, 'guarded step ' + step['name'])
check([step['arguments'] for step in steps[:4]] == [cmd['arguments'] for cmd in inv['planned_commands']], 'planned command arguments')
report_cmd = steps[3]['arguments']
check('-report -rpts' in report_cmd and str(SETTINGS) in report_cmd and '-rjexport' in report_cmd and '-jsonreport' not in report_cmd, 'selected report-only settings used')
reportlog = (RUN / 'report-export.log').read_text(encoding='utf-8-sig')
check('Report completed' in reportlog and 'Export completed!' in reportlog and not re.search(r'fallback|failed to load|error', reportlog, re.I), 'report export completed, no fallback indication')
runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig')
warnings = re.findall(r'Form: ([^\r\n]+)\s+rec (\d+): \(warning #(\d+)\) ([^\r\n]+)', runlog)
check(warnings == [('Control', '1', '108', 'Enabling simulation log may generate extensive data in log file'), ('ItemFailureRate', '2', '2058', 'Data overrides previous data: TEACH-LRU-01/OPHOURS'), ('SystemFailureRate', '2', '2058', 'Data overrides previous data: TEACH-AIR-01/OPHOURS')], 'two row-specific #2058 override warnings and #108')
check('Input conversion completed. Errors: 0, Warnings: 3, Notes: 0' in runlog and not re.search(r'\berror\s*#', runlog, re.I), 'Errors0 Warnings3 Notes0')
check(all((RUN / name).stat().st_size > 1000 for name in ('model.sxo', 'model.log', 'report-raw.json')), 'valid calculated model and report')
export = tables(RUN / 'roundtrip-raw.json', 'model')
populated = [name for name, table in child.items() if rows(table)]
check(len(populated) == 21, '21 populated authored tables')
for name in populated:
    check(name in export and child[name]['columns'] == export[name]['columns'] and child[name]['instances'] == export[name]['instances'], 'exact native roundtrip ' + name)

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
for mid, start, end, success in ((0, 8, 10, True), (1, 20, 22, True), (2, 52, 53.8952, False)):
    ident = f'<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>'
    check(at(log, start, ident + ' mission starting, duration: 2') and at(log, end, ident + (' mission completed:' if success else ' aborted mission completed:')), f'mission {mid} start/return')
    check(at(log, 10 if mid == 0 else 22 if mid == 1 else 53.3952, ident + (' mission success:' if success else ' mission aborted:')), f'mission {mid} outcome')
check(log.count(' mission success:') == 2 and log.count(' mission aborted:') == 1 and at(log, 53.3952, 'critical random failure added'), 'third-mission critical abort, two successes')
report = tables(RUN / 'report-raw.json', 'report')
expected_names = {'ProblemDescription', 'ResultSummary', 'MissionOperationAccumulated', 'MissionOperationTotalAccumulated', 'MissionOperation', 'MissionOperationTotal', 'SystemResults', 'StockTotalResults'}
check(set(report) == expected_names, 'selected report exposes both operation parameters')
summary = records(report['ResultSummary'])[0]
for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 60), ('MTMF', .982530653476715), ('STMF', .982530653476715), ('MSTF', 1), ('MSUF', 2/3)):
    check(close(summary[name], expected), 'summary ' + name)
totals = {r['OPID']: r['SOACC'] for r in records(report['MissionOperationTotalAccumulated'])}
check(close(totals.get('OPHOURS'), 5.895183563232422) and close(totals.get('KM'), 353.7110290527344) and close(totals['KM']/totals['OPHOURS'], 60), 'native accumulated exposure totals and 60:1 ratio')
rate_totals = {r['OPID']: r['SOACC'] for r in records(report['MissionOperationTotal'])}
check(close(rate_totals['OPHOURS']*60, totals['OPHOURS']) and close(rate_totals['KM']*60, totals['KM']), 'MissionOperationTotal is normalized, not accumulated')
intervals = {}
for name in ('MissionOperation', 'MissionOperationAccumulated'):
    data = records(report[name])
    check(len(data) == 224 and all(r['ETINT']-r['STINT'] == .5 for r in data), name + ' 224 half-hour rows')
    by_opid = {(r['OPID'], r['STINT']): r['SOACC'] for r in data}
    check(len(by_opid) == len(data) and {opid for opid, _ in by_opid} == {'KM', 'OPHOURS'}, name + ' distinct OPID/interval rows')
    intervals[name] = by_opid
rate, accumulated = intervals['MissionOperation'], intervals['MissionOperationAccumulated']
third_return_precise = 52 + totals['OPHOURS'] - 4
check(abs(third_return_precise - 53.8952) < .0001, 'report precision agrees with rounded logged third return')
flights = ((8, 10), (20, 22), (52, third_return_precise))
for index in range(120):
    h = index/2
    fraction = sum(occupancy(a, b, h) for a, b in flights)
    check(close(rate[('OPHOURS', h)], fraction), f'OPHOURS interval {index}')
    if h < 8:
        check(('KM', h) not in rate and ('KM', h) not in accumulated, f'custom KM row absent before first use {index}')
    else:
        check(close(rate[('KM', h)], 60*fraction), f'KM interval rate {index}')
        if fraction:
            check(close(rate[('KM', h)]/rate[('OPHOURS', h)], 60), f'active interval 60:1 ratio {index}')
        elapsed = sum(max(0, min(h+.5, b)-a) for a, b in flights)
        check(close(accumulated[('OPHOURS', h)], elapsed) and close(accumulated[('KM', h)], 60*elapsed), f'accumulated interval {index}')
system, stock = records(report['SystemResults']), records(report['StockTotalResults'])
check(len(system) == len(stock) == 120, '120 System and Stock bins')
for index, (s, t) in enumerate(zip(system, stock)):
    h = index/2
    check((s['STINT'], s['ETINT'], t['STINT'], t['ETINT']) == (h, h+.5, h, h+.5), f'System/Stock bin alignment {index}')
    check(close(s['FTMO'], rate[('OPHOURS', h)]) and close(s['STACC'], rate[('OPHOURS', h)]), f'SystemResults operating exposure bin {index}')
check(close(sum(s['FTMO'] for s in system)*.5, totals['OPHOURS']), 'integrated SystemResults operating hours')

result = {
    'schema': 'simlox-d07-var03-independent-readonly/v1', 'passed': not failures,
    'verdict': 'GO' if not failures else 'NO-GO', 'checks_passed': count-len(failures),
    'checks_total': count, 'failures': failures, 'raw_seals': len(closure['raw']),
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'model_log_sha256': sha(RUN / 'model.log'), 'report_sha256': sha(RUN / 'report-raw.json'),
    'observed': 'Two optional OPHOURS FRT100000 rows override same-key base 300000 inputs with distinct ItemFailureRate and SystemFailureRate warning #2058. KM exposure stays at 60 per operating hour. Third mission aborts at 53.3952 and returns 53.8952, yielding native accumulated OPHOURS5.895183563232422 and KM353.7110290527344.',
    'limits': [
        'One installed executable, one seed and one system/item pair. Row-specific native warning supports bounded same-key override diagnostics; the realized failure count is not an empirical hazard-rate estimate.',
        'The early third-mission return, not a fixed 6-hour schedule assumption, defines observed exposure. MissionOperationTotal uses a normalized denominator and is not the accumulated SOACC table.',
        'No inconsistent mother-child rate, unsupported OPID, GUI-only or cross-engine claim.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'], 'checks_total': count, 'failures': failures[:25], 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
