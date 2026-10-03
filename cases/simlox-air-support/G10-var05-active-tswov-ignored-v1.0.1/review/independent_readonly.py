"""Independent read-only replay of G10.var05 positive TSWOV on an ACTIVE link."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'g10-var05-active-tswov-v101-ssh-20261003-01'
PARENT_DIR = ROOT / 'G10-var01-active-single-link-v1.0.0'
PARENT = PARENT_DIR / 'native-input.json'
PARENT_RUN = PARENT_DIR / 'runs' / 'g10-var01-active-v100-ssh-20261003-01'
DIAG_RUN = ROOT / 'G10-var05-active-tswov-ignored-v1.0.0' / 'runs' / 'g10-var05-active-tswov-v100-ssh-20261003-01'
SOURCE = CASE / 'native-input.json'
OUT = Path(__file__).with_name('independent-readonly-2026-10-03.json')
EXTERNAL = {
    'manual': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
    'dictionary': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),
    'python': Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    'simlox_exe': Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
}
checks = 0
failures = []


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    raw = path.read_text(encoding='utf-8-sig')
    output = []
    quoted = escaped = False
    for pos, char in enumerate(raw):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            output.append(char)
        elif char == ',':
            nxt = pos + 1
            while nxt < len(raw) and raw[nxt].isspace():
                nxt += 1
            if nxt == len(raw) or raw[nxt] not in '}]':
                output.append(char)
        else:
            output.append(char)
    return json.loads(''.join(output))


def tables(path, root):
    return {table['name']: table for table in load(path)[root]['tables']}


def rows(table):
    return [row for instance in table['instances'] for row in instance['rows']]


def records(table):
    names = [column['name'] for column in table['columns']]
    return [dict(zip(names, row)) for row in rows(table)]


def at(log, time, fragment):
    return any(line.startswith('Time: ' + str(time) + ' ') and fragment in line
               for line in log.splitlines())


def close(a, b):
    return isinstance(a, (int, float)) and math.isclose(a, b, abs_tol=.0007)


contract = load(CASE / 'contract.json')
diff = load(CASE / 'exact-diff.json')
for path, expected, label in (
    (PARENT, contract['parent']['input_sha256'], 'accepted parent input'),
    (PARENT_RUN / 'closure.json', contract['parent']['native_closure_sha256'], 'accepted parent closure'),
    (PARENT_DIR / 'cli-scope-signoff-2026-10-03.md', contract['parent']['signoff_sha256'], 'accepted parent signoff'),
    (PARENT_RUN / 'model.log', contract['parent']['model_log_sha256'], 'accepted parent log'),
    (PARENT_RUN / 'report-raw.json', contract['parent']['report_sha256'], 'accepted parent report'),
    (DIAG_RUN / 'closure.json', contract['prior_diagnostic']['closure_sha256'], 'excluded v1.0.0 closure'),
    (SOURCE, contract['native_input_sha256'], 'frozen child input'),
    (EXTERNAL['manual'], contract['source']['manual_pdf_sha256'], 'installed manual'),
    (EXTERNAL['dictionary'], contract['source']['installed_dictionary_sha256'], 'installed dictionary'),
):
    check(sha(path) == expected, label + ' SHA-256')
check(sha(EXTERNAL['simlox_exe']) == 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0',
      'installed executable SHA-256')
old_steps = load(DIAG_RUN / 'steps.json')
check([step['name'] for step in old_steps] == ['import', 'export', 'calc'] and
      all(step['exit_code'] == 0 for step in old_steps), 'excluded diagnostic stopped after calc')
old_runlog = (DIAG_RUN / 'run.log').read_text(encoding='utf-8-sig')
check('warning #282' in old_runlog and 'Errors: 0, Warnings: 2, Notes: 0' in old_runlog,
      'excluded diagnostic conversion showed ignored TSWOV warning')
parent, child = tables(PARENT, 'model'), tables(SOURCE, 'model')
changed = {name for name in child if child[name] != parent[name]}
check(set(child) == set(parent) and changed == set(diff['changed_tables']) ==
      set(contract['delta']['tables']) == {'ProblemDescription', 'Redundancy'} and
      diff['unchanged_tables'] == len(parent)-2 and
      diff['parent_sha256'] == sha(PARENT) and diff['child_sha256'] == sha(SOURCE),
      'exact two-table source contrast and hash pins')
for name in changed:
    check(rows(parent[name]) == diff['changes'][name]['before'] and
          rows(child[name]) == diff['changes'][name]['after'] and
          parent[name]['columns'] == child[name]['columns'], 'exact changed rows ' + name)
for name in child:
    if name not in changed:
        check(child[name] == parent[name], 'unchanged business table ' + name)
old = records(parent['Redundancy'])[0]
new = records(child['Redundancy'])[0]
check(old['TSWOV'] == 0 and new['TSWOV'] == 1 and
      all(old[key] == new[key] for key in old if key != 'TSWOV') and
      new['RLID'] == 'TEACH-LRU-01' and new['SID'] == 'TEACH-AIR-01' and
      new['NRL'] == 2 and new['NRLRQ'] == 1 and new['ACPA'] == 'ACTIVE',
      'isolated positive TSWOV on ACTIVE 1-of-2 link')
check(records(child['Control'])[0]['RELOP'] == 'REDUNDANCY', 'reliability mode remains REDUNDANCY')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
check([line.split(';')[2] for line in dictionary.splitlines() if line.startswith('Redundancy;')] ==
      [c['name'] for c in child['Redundancy']['columns']], 'installed Redundancy schema')

inv, closure = load(RUN / 'invocation.json'), load(RUN / 'closure.json')
check(inv['run_id'] == closure['run_id'] == RUN.name and closure['error'] is None,
      'fresh run identity/closure')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation SHA seal')
check(inv['input_sha256'] == sha(SOURCE) == sha(RUN / 'input.json') and
      inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'),
      'run input/parent/contract pins')
check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and
      inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'],
      'guarded SSH session0')
check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and
      inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1, 'queue and GUI preserved')
check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'],
      'source hashes stable during run')
sealed_paths = {'input': SOURCE, 'parent': PARENT,
                'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-10-03.md',
                'parent_closure': PARENT_RUN / 'closure.json',
                'parent_model_log': PARENT_RUN / 'model.log',
                'parent_report': PARENT_RUN / 'report-raw.json',
                'diagnostic_closure': DIAG_RUN / 'closure.json',
                'contract': CASE / 'contract.json', 'builder': CASE / 'build.py',
                'checker': CASE / 'check_roundtrip.py',
                'runner_script': CASE / 'run_native_ssh.ps1', **EXTERNAL}
for name, path in sealed_paths.items():
    check(sha(path) == closure['source_hashes_before'][name], 'source seal ' + name)
check(len(closure['raw']) == 13, '13 sealed raw files')
for name, meta in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'],
          'raw bytes/SHA ' + name)
steps = load(RUN / 'steps.json')
check([step['name'] for step in steps] ==
      ['import', 'export', 'calc', 'jsonreport', 'check_import_export'], 'five successful native steps')
for step in steps:
    check(step['exit_code'] == 0 and step['status'] == 'completed' and
          step['gui_preserved'] and step['error'] is None, 'guarded step ' + step['name'])
check([step['arguments'] for step in steps[:4]] ==
      [command['arguments'] for command in inv['planned_commands']], 'sealed CLI arguments')
runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig')
check('Input conversion completed. Errors: 0, Warnings: 2, Notes: 0' in runlog and
      re.findall(r'warning #(\d+)', runlog) == ['108', '282'] and
      'Switch over time (TSWOV) ignored' in runlog and
      not re.search(r'\berror\s*#', runlog, re.I), 'exact zero-error 108/282 diagnostics')
check((RUN / 'model.sxo').stat().st_size > 100000 and
      (RUN / 'model.log').stat().st_size > 1000 and
      (RUN / 'report-raw.json').stat().st_size > 1000, 'usable native outputs')
export = tables(RUN / 'roundtrip-raw.json', 'model')
populated = [name for name, table in child.items() if rows(table)]
check(len(populated) == 22, '22 populated authored tables')
for name in populated:
    check(name in export and child[name]['columns'] == export[name]['columns'] and
          child[name]['instances'] == export[name]['instances'], 'exact native roundtrip ' + name)

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
check(sha(RUN / 'model.log') == sha(PARENT_RUN / 'model.log'), 'byte-identical accepted parent model log')
check('switchover' not in log.lower() and 'switch over' not in log.lower(),
      'no logged ACTIVE switchover event')
for i, (order, launch, end) in enumerate(((7, 8, 10), (19, 20, 22), (31, 32, 34))):
    ident = f'<BASIC-MISSION,TEACH-UNIT,0,0,{i}>'
    check(at(log, order, 'mission ordered: BASIC-MISSION') and
          at(log, launch, ident + ' mission starting, duration: 2') and
          at(log, end, ident + ' mission success:') and
          ident + ' mission aborted:' not in log, f'mission {i} success')
check(at(log, 8.94145, 'noncritical random failure added') and
      at(log, 21.6494, 'noncritical random failure added') and
      log.count('random failure added') == 2 and
      'subitem failed: <TEACH-LRU-01,0,3>' in log and
      'subitem failed: <TEACH-LRU-01,0,5>' in log, 'matched noncritical link failure IDs/times')
for demand, failure, spare, task in ((10, 3, 1, 0), (22, 5, 2, 3)):
    check(at(log, demand, f'Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,{failure}>') and
          at(log, demand, f'Take replacement item <TEACH-LRU-01,0,{spare}> from stock') and
          at(log, demand, f'system SURP task {task} on <TEACH-AIR-01,0> started') and
          at(log, demand+.5, f'system SURP task {task} on <TEACH-AIR-01,0> completed'),
          f'LRU {failure} replacement path')
for time, item in ((10.9167, 3), (22.9167, 5)):
    check(at(log, time, f'Put back replacement item <TEACH-LRU-01,0,{item}> to stock'),
          f'LRU {item} repair return')
for time, item in ((11.5417, 4), (23.5417, 6)):
    check(at(log, time, f'Put back replacement item <TEACH-SRU-01,0,{item}> to stock'),
          f'SRU {item} repair return')
check('Backorder added' not in log and at(log, 34, 'systems ready: 1 :<TEACH-AIR-01,0>'),
      'no backorder and ready terminal system')

report = tables(RUN / 'report-raw.json', 'report')
parent_report = tables(PARENT_RUN / 'report-raw.json', 'report')
check(set(report) == set(parent_report) ==
      {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'},
      'equal report table sets')
for name in ('ResultSummary', 'SystemResults', 'StockTotalResults'):
    check(report[name] == parent_report[name], 'equal non-description report table ' + name)
check(report['ProblemDescription'] != parent_report['ProblemDescription'],
      'description alone differs in report')
summary = records(report['ResultSummary'])[0]
for key, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36), ('MTMF', 1),
                      ('STMF', 1), ('MSTF', 1), ('MSUF', 1)):
    check(close(summary[key], expected), 'summary ' + key)
system = records(report['SystemResults'])
stock = records(report['StockTotalResults'])
check(len(system) == len(stock) == 72, '72 System/Stock bins')
for i, (s, t) in enumerate(zip(system, stock)):
    h = i / 2
    reserved = int(h in (7, 7.5, 19, 19.5, 31, 31.5))
    flight = int(8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34)
    repair = int(h in (10, 22))
    expected_s = {'NSYRY': 1-reserved-flight-repair, 'NSYMA': reserved+flight,
                  'NSYMO': flight, 'NSYMR': reserved, 'NSYUA': repair,
                  'NSYA': 1-repair, 'FTMO': flight, 'NSYRP': repair,
                  'NREPT': int(h in (10.5, 22.5)),
                  'NFAIL': int(h in (8.5, 21.5)), 'STACC': flight,
                  'SYDT': .5 if h in (10, 22) else None,
                  'NSYDT': int(h in (10, 22))}
    expected_t = {'PNB': 1, 'NDF': int(h in (10, 22)), 'NWT': int(h in (10, 22))}
    check((s['STINT'], s['ETINT'], t['STINT'], t['ETINT']) == (h, h+.5, h, h+.5),
          f'aligned report bin {i}')
    for name, value in s.items():
        if name in ('UNID', 'SID', 'STINT', 'ETINT'):
            continue
        target = expected_s.get(name, 0)
        check(value is None if target is None else close(value, target),
              f'SystemResults {name} bin {i}')
    for name, value in t.items():
        if name in ('STINT', 'ETINT'):
            continue
        target = (None if name in {'NBOU', 'WTS'} or
                  (name in {'ROS', 'ROST', 'WT', 'WTT'} and h not in (10, 22))
                  else expected_t.get(name, 0))
        check(value is None if target is None else close(value, target),
              f'StockTotalResults {name} bin {i}')
check(system[-1]['NSYRY'] == 1 and stock[-1]['PNB'] == 1 and stock[-1]['NBO'] == 0,
      'terminal ready/no-backorder report')

result = {
    'schema': 'simlox-g10-var05-independent-readonly/v1',
    'passed': not failures, 'verdict': 'GO' if not failures else 'NO-GO',
    'checks_passed': checks-len(failures), 'checks_total': checks,
    'failures': failures, 'raw_seals': len(closure['raw']),
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'model_log_sha256': sha(RUN / 'model.log'), 'report_sha256': sha(RUN / 'report-raw.json'),
    'observed': 'Native converter explicitly warns #282 that TSWOV is ignored for ACTIVE; positive TSWOV=1 retains byte-identical event log and equal non-description report tables versus accepted TSWOV=0 control.',
    'limits': [
        'One positive TSWOV value, one ACTIVE 1-of-2 single-item link group, fixed seed/horizon; no PASSIVE inference.',
        'The parent has no simultaneous two-link-failed interval, so NRLRQ crossing remains untested.',
        'v1.0.0 is excluded because its runner stopped after reviewing only warning #108; it is not an accepted behavior run.',
        'No other switch delays/topologies, GUI-only behavior or cross-engine parity.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'],
                  'checks_total': checks, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
