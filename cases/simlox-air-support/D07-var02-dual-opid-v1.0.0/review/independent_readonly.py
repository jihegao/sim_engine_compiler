"""Independent, read-only replay of the D07.var02 dual-OPID diagnostic."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'd07-var02-dual-opid-v100-ssh-20261003-01'
PARENT_DIR = ROOT / 'D02-var01-traditional-op-hours-v1.0.0'
PARENT = PARENT_DIR / 'native-input.json'
PARENT_RUN = PARENT_DIR / 'runs' / 'd02-var01-traditional-op-v100-ssh-20260930-01'
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
check(sha(PARENT) == contract['parent_input_sha256'], 'accepted D02 parent input')
check(sha(SOURCE) == contract['input_sha256'], 'frozen child input')
check(sha(EXTERNAL['manual']) == contract['manual_sha256'], 'manual SHA')
check(sha(EXTERNAL['dictionary']) == '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0', 'dictionary SHA')
check(sha(EXTERNAL['simlox_exe']) == 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0', 'executable SHA')
check(sha(CUSTOM) == '2100f7d1ae7725962483419571433d64c6ef92f8fb69078dd58f6835d90ed084', 'A15 custom parameter schema donor')
check(sha(RATE) == 'b76dd77056378ca06c0134ddd363816d9c9ac211e4f36181fb597eca0e9b4797', 'D02 rate schema donor')
check(sha(SETTINGS) == 'c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7', 'selected report settings')
check(sha(PARENT_DIR / 'cli-scope-signoff-2026-09-30.md') == '966b487623a2fa18ec3fa1d239e84b39fcb5c690b29567d2e0c9e8f07088f99c', 'accepted parent signoff')
check(sha(PARENT_RUN / 'closure.json') == 'fdb0c93c2a59313392587378665115baa26cb23de01e48d543b56eaa33abfbb8', 'accepted parent closure')
parent, child = tables(PARENT, 'model'), tables(SOURCE, 'model')
changed = {name for name in parent.keys() & child.keys() if parent[name] != child[name]}
added = set(child)-set(parent)
check(changed == set(diff['changed_tables']) == {'OperationParameter', 'ProblemDescription'} and added == set(diff['added_tables']) == {'ItemFailureRate', 'MissionTypeUtilization', 'SystemFailureRate'} and not set(parent)-set(child) and not diff['removed_tables'], 'exact source table delta')
for name in changed:
    check(parent[name] == diff['changed_tables'][name]['before'] and child[name] == diff['changed_tables'][name]['after'], 'source changed table ' + name)
for name in added:
    check(child[name] == diff['added_tables'][name], 'source added table ' + name)
for name in set(parent)-changed:
    check(parent[name] == child[name], 'unchanged parent table ' + name)
check(records(child['OperationParameter'])[0]['OPID'] == 'KM', 'custom KM OPID')
check(records(child['MissionTypeUtilization']) == [{'MTID': 'BASIC-MISSION', 'SID': 'TEACH-AIR-01', 'OPID': 'KM', 'UTIL': 60, 'UTILU': '1/HOUR', 'NOTE': None}], '60 KM per mission hour source')
check({(r['SID'], r['OPID'], r['FRT']) for r in records(child['SystemFailureRate'])} == {('TEACH-AIR-01', 'KM', 5000)}, 'system KM failure rate')
check({(r['IID'], r['OPID'], r['FRT']) for r in records(child['ItemFailureRate'])} == {('TEACH-LRU-01', 'KM', 5000)}, 'installed LRU KM failure rate')
check(records(child['System'])[0]['FRT'] == 300000 and records(child['System'])[0]['OPID'] == 'OPHOURS' and records(child['Item'])[0]['FRT'] == 300000 and records(child['Item'])[0]['OPID'] == 'OPHOURS', 'retained OPHOURS traditional inputs')

inv, closure = load(RUN / 'invocation.json'), load(RUN / 'closure.json')
check(inv['run_id'] == closure['run_id'] == RUN.name and closure['error'] is None, 'native identity and closure')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation SHA seal')
check(inv['input_sha256'] == sha(SOURCE) == sha(RUN / 'input.json') and inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'), 'invocation input/parent/contract pins')
check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'], 'SSH session zero')
check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1, 'queue and GUI preservation')
check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'], 'before/after source stability')
paths = {'input': SOURCE, 'parent': PARENT, 'custom': CUSTOM, 'rate': RATE, 'report_settings': SETTINGS, 'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-09-30.md', 'parent_closure': PARENT_RUN / 'closure.json', 'manual': EXTERNAL['manual'], 'dictionary': EXTERNAL['dictionary'], 'exact_diff': CASE / 'parent-diff.json', 'contract': CASE / 'contract.json', 'builder': CASE / 'build.py', 'checker': CASE / 'check_roundtrip.py', 'diff_script': CASE / 'describe_diff.py', 'python': EXTERNAL['python'], 'runner_script': CASE / 'run_native_ssh.ps1', 'simlox_exe': EXTERNAL['simlox_exe']}
for name, path in paths.items():
    check(sha(path) == closure['source_hashes_before'][name], 'source seal ' + name)
check(len(closure['raw']) == 12, 'twelve raw seals')
for name, meta in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'], 'raw seal ' + name)
steps = load(RUN / 'steps.json')
check([s['name'] for s in steps] == ['import', 'export', 'calc', 'report', 'check_import_export'], 'five guarded native steps')
for step in steps:
    check(step['exit_code'] == 0 and step['status'] == 'completed' and step['gui_preserved'] and step['error'] is None, 'guarded step ' + step['name'])
check([s['arguments'] for s in steps[:4]] == [command['arguments'] for command in inv['planned_commands']], 'planned native command bindings')
report_cmd = steps[3]['arguments']
check('-report -rpts' in report_cmd and str(SETTINGS) in report_cmd and '-rjexport' in report_cmd and '-jsonreport' not in report_cmd, 'selected remapped report command, no default report switch')
reportlog = (RUN / 'report-export.log').read_text(encoding='utf-8-sig')
check('Report completed' in reportlog and 'Export completed!' in reportlog and not re.search(r'fallback|failed to load|error', reportlog, re.I), 'selected settings report completed without fallback')
runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig')
check('Input conversion completed. Errors: 0, Warnings: 1, Notes: 0' in runlog and re.findall(r'warning #(\d+)', runlog) == ['108'] and not re.search(r'\berror\s*#', runlog, re.I), 'zero conversion errors, only warning108')
check(all((RUN / name).stat().st_size > 1000 for name in ('model.sxo', 'model.log', 'report-raw.json')), 'valid calculated model and report')
export = tables(RUN / 'roundtrip-raw.json', 'model')
populated = [name for name, table in child.items() if rows(table)]
check(len(populated) == 21, '21 populated authored tables')
for name in populated:
    check(name in export and child[name]['columns'] == export[name]['columns'] and child[name]['instances'] == export[name]['instances'], 'exact native roundtrip ' + name)

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
for mid, start, end, success in ((0, 8, 10, False), (1, 20, 22, True), (2, 52, 54, True)):
    ident = f'<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>'
    check(at(log, start, ident + ' mission starting, duration: 2') and at(log, end, ident + (' mission success:' if success else ' aborted mission completed:')), f'mission {mid} operating interval/outcome')
check(log.count(' mission starting, duration: 2') == 3 and log.count(' mission success:') == 2 and log.count(' mission aborted:') == 1, 'three missions, two successes and one abort')
report = tables(RUN / 'report-raw.json', 'report')
expected_names = {'ProblemDescription', 'ResultSummary', 'MissionOperationAccumulated', 'MissionOperationTotalAccumulated', 'MissionOperation', 'MissionOperationTotal', 'SystemResults', 'StockTotalResults'}
check(set(report) == expected_names, 'selected report contains both MissionOperation and accumulated tables')
summary = records(report['ResultSummary'])[0]
for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 60), ('MTMF', 1), ('STMF', 1), ('MSTF', 1), ('MSUF', 2/3)):
    check(close(summary[name], expected), 'summary ' + name)
total_acc = {r['OPID']: r['SOACC'] for r in records(report['MissionOperationTotalAccumulated'])}
check(total_acc == {'OPHOURS': 6, 'KM': 360}, 'six OPHOURS and 360 KM accumulated')
total_rate = {r['OPID']: r['SOACC'] for r in records(report['MissionOperationTotal'])}
check(close(total_rate.get('OPHOURS'), .1) and close(total_rate.get('KM'), 6) and close(total_rate['KM']/total_rate['OPHOURS'], 60), 'total rate denominator distinct from accumulated exposure')
intervals = {}
for name in ('MissionOperation', 'MissionOperationAccumulated'):
    data = records(report[name])
    check(len(data) == 224, name + ' 224 native interval rows')
    check(all(r['UNID'] == 'Total over all Units' and r['MTID'] == 'Total over all Missions' and r['ETINT']-r['STINT'] == .5 for r in data), name + ' aggregate half-hour intervals')
    by_opid = {(r['OPID'], r['STINT']): r['SOACC'] for r in data}
    check(len(by_opid) == len(data), name + ' unique OPID/interval keys')
    check({opid for opid, _ in by_opid} == {'OPHOURS', 'KM'}, name + ' two operation parameters')
    intervals[name] = by_opid
rate, accumulated = intervals['MissionOperation'], intervals['MissionOperationAccumulated']
for index in range(120):
    h = index/2
    active = int(any(start <= h < end for start, end in ((8, 10), (20, 22), (52, 54))))
    check(close(rate[('OPHOURS', h)], active), f'OPHOURS rate bin {index}')
    if h < 8:
        check(('KM', h) not in rate and ('KM', h) not in accumulated, f'KM rows absent before first exposure bin {index}')
    else:
        check(close(rate[('KM', h)], 60*active) and close(rate[('KM', h)]/rate[('OPHOURS', h)], 60) if active else close(rate[('KM', h)], 0), f'KM interval rate/ratio bin {index}')
        elapsed = sum(max(0, min(h+.5, end)-start) for start, end in ((8, 10), (20, 22), (52, 54)))
        check(close(accumulated[('OPHOURS', h)], elapsed) and close(accumulated[('KM', h)], 60*elapsed), f'accumulated exposure bin {index}')
system, stock = records(report['SystemResults']), records(report['StockTotalResults'])
check(len(system) == len(stock) == 120, '120 System/Stock bins through 60 hours')
for index, (s, t) in enumerate(zip(system, stock)):
    h = index/2
    check((s['STINT'], s['ETINT'], t['STINT'], t['ETINT']) == (h, h+.5, h, h+.5), f'System/Stock interval {index}')
    check(close(s['FTMO'], rate[('OPHOURS', h)]) and close(s['STACC'], rate[('OPHOURS', h)]), f'operating report matches OPHOURS bin {index}')
check(close(sum(s['FTMO'] for s in system)*.5, 6), 'six SystemResults operating hours')

result = {
    'schema': 'simlox-d07-var02-independent-readonly/v1', 'passed': not failures,
    'verdict': 'GO' if not failures else 'NO-GO', 'checks_passed': count-len(failures),
    'checks_total': count, 'failures': failures, 'raw_seals': len(closure['raw']),
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'model_log_sha256': sha(RUN / 'model.log'), 'report_sha256': sha(RUN / 'report-raw.json'),
    'observed': 'Accepted D02 OPHOURS source retained; KM custom utilization and equal system/item KM failure-rate rows added. Selected native report has 6 OPHOURS and 360 KM accumulated, with 60:1 interval rate during the three observed two-hour mission intervals.',
    'limits': [
        'One seed and one installed executable. Stochastic fault events do not identify the additive hazard exactly or isolate which OPID caused a failure.',
        'MissionOperationTotal reports normalized rates (0.1 OPHOURS and 6 KM) and must not be mistaken for accumulated exposure totals (6 and 360).',
        'No claim about same-key override, unsupported OPIDs, inconsistent mother-child FRT, GUI-only behavior or cross-engine parity.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'], 'checks_total': count, 'failures': failures[:25], 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
