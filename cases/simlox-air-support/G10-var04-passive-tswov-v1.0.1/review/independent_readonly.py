"""Independent read-only replay of G10.var04 completed PASSIVE 0.05h switch."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'g10-var04-passive-tswov-v101-ssh-20261003-01'
PARENT_DIR = ROOT / 'G10-var02-passive-zero-v1.0.0'
PARENT = PARENT_DIR / 'native-input.json'
PARENT_RUN = PARENT_DIR / 'runs' / 'g10-var02-passive-zero-v100-ssh-20261003-01'
DIAG_RUN = ROOT / 'G10-var04-passive-tswov-v1.0.0' / 'runs' / 'g10-var04-passive-tswov-v100-ssh-20261003-01'
SOURCE = CASE / 'native-input.json'
OUT = Path(__file__).with_name('independent-readonly-2026-10-03.json')
EXTERNAL = {
    'manual': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
    'dictionary': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),
    'python': Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    'simlox_exe': Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
}
count = 0
failures = []


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


contract = load(CASE / 'contract.json')
diff = load(CASE / 'exact-diff.json')
check(sha(PARENT) == contract['parent']['input_sha256'], 'accepted parent input SHA')
check(sha(PARENT_RUN / 'closure.json') == contract['parent']['native_closure_sha256'],
      'accepted parent closure SHA')
check(sha(PARENT_DIR / 'cli-scope-signoff-2026-10-03.md') ==
      contract['parent']['signoff_sha256'], 'accepted parent signoff SHA')
check(sha(DIAG_RUN / 'closure.json') == contract['excluded_diagnostic']['closure_sha256'],
      'excluded one-hour diagnostic closure SHA')
diagnostic_log = (DIAG_RUN / 'model.log').read_text(encoding='utf-8-sig')
check('Will be finished at 10.8829.' in diagnostic_log and
      at(diagnostic_log, 10, 'Switch over aborted.') and
      not at(diagnostic_log, 10.8829, 'Switch over stopped.'),
      'excluded one-hour switch aborted at first return')
check(sha(SOURCE) == contract['native_input_sha256'], 'frozen candidate source SHA')
check(sha(EXTERNAL['manual']) == contract['source']['manual_pdf_sha256'], 'installed manual SHA')
check(sha(EXTERNAL['dictionary']) == contract['source']['installed_dictionary_sha256'],
      'installed dictionary SHA')
check(sha(EXTERNAL['simlox_exe']) == 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0',
      'installed executable SHA')
check(diff['parent_sha256'] == sha(PARENT) and diff['child_sha256'] == sha(SOURCE),
      'diff source fingerprint binding')
parent, child = tables(PARENT, 'model'), tables(SOURCE, 'model')
changed = {name for name in child if child[name] != parent[name]}
check(set(parent) == set(child) and changed == set(diff['changed_tables']) ==
      set(contract['delta']['tables']) == {'ProblemDescription', 'Redundancy'} and
      diff['unchanged_tables'] == len(parent)-2, 'isolated two-table source delta')
for name in changed:
    check(rows(parent[name]) == diff['changes'][name]['before'] and
          rows(child[name]) == diff['changes'][name]['after'] and
          parent[name]['columns'] == child[name]['columns'], 'exact row delta ' + name)
for name in child:
    if name not in changed:
        check(child[name] == parent[name], 'unchanged source table ' + name)
old = records(parent['Redundancy'])[0]
new = records(child['Redundancy'])[0]
check(old['ACPA'] == new['ACPA'] == 'PASSIVE' and
      old['TSWOV'] == 0 and new['TSWOV'] == .05 and
      all(old[key] == new[key] for key in old if key != 'TSWOV') and
      new['RLID'] == 'TEACH-LRU-01' and new['SID'] == 'TEACH-AIR-01' and
      new['NRL'] == 2 and new['NRLRQ'] == 1,
      'only PASSIVE TSWOV0 to 0.05, 1-of-2 link')
check(any(r['IID'] == 'TEACH-LRU-01' and r['MID'] == 'TEACH-AIR-01' and r['QTYPM'] == 2
          for r in records(child['ItemStructure'])), 'two installed LRU copies')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
check([line.split(';')[2] for line in dictionary.splitlines() if line.startswith('Redundancy;')] ==
      [col['name'] for col in child['Redundancy']['columns']], 'installed Redundancy schema')

inv, closure = load(RUN / 'invocation.json'), load(RUN / 'closure.json')
check(inv['run_id'] == closure['run_id'] == RUN.name and closure['error'] is None,
      'run identity/closure')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation SHA seal')
check(inv['input_sha256'] == sha(SOURCE) == sha(RUN / 'input.json') and
      inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'),
      'source/parent/contract invocation pins')
check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and
      inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'],
      'SSH session0 provenance')
check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and
      inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1, 'queue/GUI identity')
check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'],
      'source stable during run')
paths = {'input': SOURCE, 'parent': PARENT,
         'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-10-03.md',
         'parent_closure': PARENT_RUN / 'closure.json',
         'excluded_diagnostic_closure': DIAG_RUN / 'closure.json',
         'contract': CASE / 'contract.json', 'builder': CASE / 'build.py',
         'checker': CASE / 'check_roundtrip.py', 'runner_script': CASE / 'run_native_ssh.ps1',
         **EXTERNAL}
for name, path in paths.items():
    check(sha(path) == closure['source_hashes_before'][name], 'source seal ' + name)
check(len(closure['raw']) == 13, '13 raw SHA seals')
for name, meta in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'],
          'raw bytes/SHA ' + name)
steps = load(RUN / 'steps.json')
check([step['name'] for step in steps] ==
      ['import', 'export', 'calc', 'jsonreport', 'check_import_export'], 'five native steps')
for step in steps:
    check(step['exit_code'] == 0 and step['status'] == 'completed' and
          step['gui_preserved'] and step['error'] is None, 'guarded step ' + step['name'])
check([step['arguments'] for step in steps[:4]] ==
      [command['arguments'] for command in inv['planned_commands']], 'planned CLI commands')
runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig')
check('Input conversion completed. Errors: 0, Warnings: 1, Notes: 0' in runlog and
      re.findall(r'warning #(\d+)', runlog) == ['108'] and
      not re.search(r'\berror\s*#', runlog, re.I), 'zero errors, only warning108')
check((RUN / 'model.sxo').stat().st_size > 100000 and
      (RUN / 'model.log').stat().st_size > 1000 and
      (RUN / 'report-raw.json').stat().st_size > 1000, 'usable native artifacts')
export = tables(RUN / 'roundtrip-raw.json', 'model')
populated = [name for name, table in child.items() if rows(table)]
check(len(populated) == 22, '22 row-containing business tables')
for name in populated:
    check(name in export and child[name]['columns'] == export[name]['columns'] and
          child[name]['instances'] == export[name]['instances'], 'exact roundtrip ' + name)

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
for index, (order, launch, end) in enumerate(((7, 8, 10), (19, 20, 22), (31, 32, 34))):
    ident = f'<BASIC-MISSION,TEACH-UNIT,0,0,{index}>'
    check(at(log, order, 'mission ordered: BASIC-MISSION') and
          at(log, order, ident + ' mission allocates system: <TEACH-AIR-01,0>') and
          at(log, launch, ident + ' mission starting, duration: 2') and
          at(log, end, ident + ' mission success:') and
          at(log, end, ident + ' mission completed:') and
          ident + ' mission aborted:' not in log, f'mission {index} success')
switch_begin = 'Time: 9.8829 <TEACH-AIR-01,0><TEACH-AIR-01\\IMPL_RED_LINK_0 [IMPL_RED_LINK_0<0> -> IMPL_RED_LINK_0<1>]>. switch over started. Will be finished at 9.9329.'
switch_end = 'Time: 9.9329 <TEACH-AIR-01,0><TEACH-AIR-01\\IMPL_RED_LINK_0 [IMPL_RED_LINK_0<0> -> IMPL_RED_LINK_0<1>]>. Switch over stopped.'
check(switch_begin in log and switch_end in log and
      log.index(switch_begin) < log.index(switch_end) and
      'Switch over aborted' not in log and
      log.count('switch over started') == log.count('Switch over stopped') == 1,
      'completed positive 0.05h implicit link0-to-link1 switch')
check(at(log, 9.8829, 'noncritical random failure added') and
      'subitem failed: <TEACH-LRU-01,0,3> connection path: TEACH-AIR-01' in log and
      log.count('random failure added') == 1 and
      not re.search(r'(?<!non)critical random failure added', log),
      'single noncritical physical LRU ID3 failure')
check('Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 2 Items:<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,2>' in log and
      'Stock at: <TEACH-SRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-SRU-01,0,0>' in log,
      'opening LRU/SRU stock identities')
check(at(log, 10, 'Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,3>') and
      at(log, 10, 'Take replacement item <TEACH-LRU-01,0,1> from stock') and
      at(log, 10, 'system SURP task 0 on <TEACH-AIR-01,0> started') and
      at(log, 10.5, 'system SURP task 0 on <TEACH-AIR-01,0> completed'),
      'postreturn half-hour system LRU exchange')
check(at(log, 10.1667, 'Item requiring maintenance arrives <TEACH-LRU-01,0,3>') and
      at(log, 10.1667, 'Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-SRU-01,0,4>') and
      at(log, 10.1667, 'Take replacement item <TEACH-SRU-01,0,0> from stock'),
      'nested SRU physical ID4 exchange')
check(at(log, 10.1667, 'item SURP task 1 on <TEACH-LRU-01,0,3> started') and
      at(log, 10.9167, 'item SURP task 1 on <TEACH-LRU-01,0,3> completed') and
      at(log, 10.9167, 'Put back replacement item <TEACH-LRU-01,0,3> to stock'),
      'LRU repair and return')
check(at(log, 10.5417, 'item DIRP task 2 on <TEACH-SRU-01,0,4> started') and
      at(log, 11.5417, 'item DIRP task 2 on <TEACH-SRU-01,0,4> completed') and
      at(log, 11.5417, 'Put back replacement item <TEACH-SRU-01,0,4> to stock'),
      'one-hour SRU repair and return')
levels = {kind: [int(m.group(1)) for m in re.finditer(
          rf'Stock at: <{kind},0,BASE-01,0> Level: (\d+)', log)]
          for kind in ('TEACH-LRU-01', 'TEACH-SRU-01')}
check(levels == {'TEACH-LRU-01': [2, 1, 2], 'TEACH-SRU-01': [1, 0, 1]},
      'physical stock conservation')
check('Backorder added' not in log and at(log, 34, 'systems ready: 1 :<TEACH-AIR-01,0>'),
      'no backorder and ready terminal system')

report = tables(RUN / 'report-raw.json', 'report')
parent_report = tables(PARENT_RUN / 'report-raw.json', 'report')
check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'},
      'four report tables')
check(set(report) == set(parent_report), 'matched parent report tables')
check(report['StockTotalResults'] == parent_report['StockTotalResults'],
      'all 72 parent/child StockTotalResults rows equal')
summary = records(report['ResultSummary'])[0]
parent_summary = records(parent_report['ResultSummary'])[0]
for field, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36), ('MTMF', 1),
                        ('MSTF', 1), ('MSUF', 1), ('STMF', .991666674613953)):
    check(close(summary[field], expected), 'summary ' + field)
for field in summary:
    if field != 'STMF':
        check(summary[field] == parent_summary[field], 'parent/child summary equal ' + field)
check(parent_summary['STMF'] == 1 and close(summary['STMF'], 1-.05/6),
      'STMF parent-to-delay difference equals .05/6')
system = records(report['SystemResults'])
parent_system = records(parent_report['SystemResults'])
stock = records(report['StockTotalResults'])
check(len(system) == len(stock) == 72, '72 aligned System/Stock bins')
check(len(parent_system) == 72, '72 parent SystemResults bins')
report_differences = []
for index, (s, t) in enumerate(zip(system, stock)):
    h = index / 2
    reserved = int(h in (7, 7.5, 19, 19.5, 31, 31.5))
    flight = int(8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34)
    repair = int(h == 10)
    modeled_flight = flight - (.1 if h == 9.5 else 0)
    expected_s = {'NSYRY': 1-reserved-flight-repair, 'NSYMA': reserved+flight,
                  'NSYMO': modeled_flight, 'NSYMR': reserved, 'NSYUA': repair,
                  'NSYA': 1-repair, 'FTMO': modeled_flight, 'NSYRP': repair,
                  'NREPT': int(h == 10.5), 'NFAIL': int(h == 9.5),
                  'STACC': modeled_flight, 'SYDT': .5 if h == 10 else None,
                  'NSYDT': int(h == 10), 'NSYSW': .1 if h == 9.5 else 0}
    expected_t = {'PNB': 1, 'NDF': int(h == 10), 'NWT': int(h == 10)}
    check((s['STINT'], s['ETINT'], t['STINT'], t['ETINT']) == (h, h+.5, h, h+.5),
          f'aligned report bin {index}')
    for name, value in s.items():
        if name in ('UNID', 'SID', 'STINT', 'ETINT'):
            continue
        target = expected_s.get(name, 0)
        check(value is None if target is None else close(value, target),
              f'SystemResults {name} bin {index}')
        if value != parent_system[index][name]:
            report_differences.append((index, name))
    for name, value in t.items():
        if name in ('STINT', 'ETINT'):
            continue
        target = (None if name in {'NBOU', 'WTS'} or
                  (name in {'ROS', 'ROST', 'WT', 'WTT'} and h != 10)
                  else expected_t.get(name, 0))
        check(value is None if target is None else close(value, target),
              f'StockTotalResults {name} bin {index}')
check(set(report_differences) == {(19, 'NSYMO'), (19, 'FTMO'),
                                  (19, 'STACC'), (19, 'NSYSW')},
      'exact four parent/child SystemResults cell differences')
check(close(sum(s['NSYMO'] for s in system)*.5, 5.95), '5.95 modeled operating hours')
check(close(sum(s['NSYSW'] for s in system)*.5, .05), '0.05 system switchover hours')
check(close(sum(s['NSYRP'] for s in system)*.5, .5), 'half-hour system LRU work')
check(system[-1]['NSYRY'] == 1 and stock[-1]['PNB'] == 1 and stock[-1]['NBO'] == 0,
      'terminal ready/no-backorder')

result = {
    'schema': 'simlox-g10-var04-v101-independent-readonly/v1',
    'passed': not failures, 'verdict': 'GO' if not failures else 'NO-GO',
    'checks_passed': count-len(failures), 'checks_total': count,
    'failures': failures, 'raw_seals': len(closure['raw']),
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'model_log_sha256': sha(RUN / 'model.log'), 'report_sha256': sha(RUN / 'report-raw.json'),
    'observed': 'LRU ID3 fails noncritically at h9.8829; implicit link0-to-link1 switch completes h9.9329; three missions succeed; LRU/SRU repair and stock close; SystemResults has 0.05 switch hours and 5.95 operating hours, with STMF 0.9916667 versus parent1; terminal ready1.',
    'limits': [
        'One PASSIVE 1-of-2 single-item link group, TSWOV0.05, one seed and 36-hour horizon.',
        'The excluded one-hour diagnostic switch was aborted by mission return; no longer completed delay or concurrent two-link failure/NRLRQ crossing is observed.',
        'Link numbering is native implicit-link text; physical LRU ID3 is logged, but no individual initial standby LRU listing is exposed.',
        'No other topology, failure-rate law, GUI-only behavior, or cross-engine parity.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'],
                  'checks_total': count, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
