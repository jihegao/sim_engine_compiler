"""Independent read-only replay of G10.var03 ACTIVE NRLRQ crossing."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'g10-var03-nrlrq-crossing-v100-ssh-20261003-01'
PARENT_DIR = ROOT / 'G10-var01-active-single-link-v1.0.0'
PARENT = PARENT_DIR / 'native-input.json'
PARENT_RUN = PARENT_DIR / 'runs' / 'g10-var01-active-v100-ssh-20261003-01'
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
      set(contract['delta']['tables']) == {'Item', 'ProblemDescription', 'System'} and
      diff['unchanged_tables'] == len(parent)-3, 'exact three-table source delta')
for name in changed:
    check(rows(parent[name]) == diff['changes'][name]['before'] and
          rows(child[name]) == diff['changes'][name]['after'] and
          parent[name]['columns'] == child[name]['columns'], 'exact row delta ' + name)
for name in child:
    if name not in changed:
        check(child[name] == parent[name], 'unchanged source table ' + name)
link = records(child['Redundancy'])[0]
check(link['ACPA'] == 'ACTIVE' and link['RLID'] == 'TEACH-LRU-01' and
      link['SID'] == 'TEACH-AIR-01' and link['NRL'] == 2 and
      link['NRLRQ'] == 1 and link['TSWOV'] == 0,
      'unchanged ACTIVE 1-of-2 single-item link')
items = records(child['Item'])
check({r['IID']: (r['FRT'], r['OPID']) for r in items} ==
      {'TEACH-LRU-01': (900000, 'OPHOURS'), 'TEACH-SRU-01': (900000, 'OPHOURS')},
      'two matched item FRT inputs tripled')
check(records(child['System'])[0]['FRT'] == 1800000 and
      records(child['System'])[0]['OPID'] == 'OPHOURS',
      'system FRT equals two LRU FRT sum')
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


def occupancy(a, b, start):
    return 2 * max(0, min(b, start + .5) - max(a, start))


log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
waves = (
    {'mission': 0, 'order': 7, 'launch': 8, 'first': 8.31382, 'second': 9.56251,
     'returned': 10, 'repair_end': 10.5, 'links': (3, 5), 'srus': (4, 6),
     'lru_spares': (1, 2), 'sru_spare': 0, 'tasks': (0, 1),
     'sru_demand': 10.1667, 'backorder_clear': 11.5417,
     'lru_returns': (10.9167, 11.9167), 'sru_return': 11.5417},
    {'mission': 1, 'order': 19, 'launch': 20, 'first': 20.4287, 'second': 20.4361,
     'returned': 20.8722, 'repair_end': 21.3722, 'links': (7, 9), 'srus': (8, 10),
     'lru_spares': (3, 5), 'sru_spare': 6, 'tasks': (6, 7),
     'sru_demand': 21.0388, 'backorder_clear': 22.4138,
     'lru_returns': (21.7888, 22.7888), 'sru_return': 22.4138},
    {'mission': 2, 'order': 31, 'launch': 32, 'first': 32.1791, 'second': 32.4288,
     'returned': 32.8576, 'repair_end': 33.3576, 'links': (11, 13), 'srus': (12, 14),
     'lru_spares': (7, 9), 'sru_spare': 10, 'tasks': (12, 13),
     'sru_demand': 33.0243, 'backorder_clear': 34.3993,
     'lru_returns': (33.7743, 34.7743), 'sru_return': 34.3993},
)
for wave in waves:
    mid = wave['mission']
    ident = f'<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>'
    check(at(log, wave['order'], 'mission ordered: BASIC-MISSION') and
          at(log, wave['order'], ident + ' mission allocates system: <TEACH-AIR-01,0>') and
          at(log, wave['launch'], ident + ' mission starting, duration: 2') and
          at(log, wave['second'], ident + ' mission aborted:') and
          at(log, wave['returned'], ident + ' aborted mission completed:') and
          ident + ' mission success:' not in log,
          f'mission {mid} allocation, abort, return')
    check(wave['launch'] < wave['first'] < wave['second'] < wave['returned'],
          f'mission {mid} first/second-failure chronology')
    first_prefix = f'Time: {wave["first"]} <TEACH-AIR-01,0> noncritical random failure added'
    second_prefix = f'Time: {wave["second"]} <TEACH-AIR-01,0> critical random failure added'
    first_block = log.split(first_prefix, 1)[1].split('Time:', 1)[0] if first_prefix in log else ''
    second_block = log.split(second_prefix, 1)[1].split('Time:', 1)[0] if second_prefix in log else ''
    left, right = wave['links']
    check(f'subitem failed: <TEACH-LRU-01,0,{left}>' in first_block and
          f'subitem failed: <TEACH-LRU-01,0,{right}>' not in first_block and
          f'subitem failed: <TEACH-LRU-01,0,{left}>' in second_block and
          f'subitem failed: <TEACH-LRU-01,0,{right}>' in second_block,
          f'mission {mid} first one NC, then two distinct failed physical links C')
    for failed, spare, task, sru in zip(wave['links'], wave['lru_spares'],
                                        wave['tasks'], wave['srus']):
        check(at(log, wave['returned'], f'Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,{failed}>') and
              at(log, wave['returned'], f'Take replacement item <TEACH-LRU-01,0,{spare}> from stock') and
              at(log, wave['returned'], f'system SURP task {task} on <TEACH-AIR-01,0> started') and
              at(log, wave['repair_end'], f'system SURP task {task} on <TEACH-AIR-01,0> completed'),
              f'mission {mid} LRU {failed} physical replacement and half-hour system repair')
        check(at(log, wave['sru_demand'], f'Item requiring maintenance arrives <TEACH-LRU-01,0,{failed}>') and
              at(log, wave['sru_demand'], f'subitem failed: <TEACH-SRU-01,0,{sru}>') and
              at(log, wave['sru_demand'], f'Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-SRU-01,0,{sru}>'),
              f'mission {mid} nested SRU {sru} failure/demand')
    check(at(log, wave['sru_demand'], f'Take replacement item <TEACH-SRU-01,0,{wave["sru_spare"]}> from stock') and
          at(log, wave['sru_demand'], '<TEACH-SRU-01,0,BASE-01,0> Backorder added') and
          at(log, wave['backorder_clear'], '<TEACH-SRU-01,0,BASE-01,0> Backorder removed, waiting time was 1.375'),
          f'mission {mid} SRU first spare and second-demand backorder/clearance')
    for item, hour in zip(wave['links'], wave['lru_returns']):
        check(at(log, hour, f'Put back replacement item <TEACH-LRU-01,0,{item}> to stock'),
              f'mission {mid} repaired LRU {item} stock return')
    check(at(log, wave['sru_return'],
             f'Put back replacement item <TEACH-SRU-01,0,{wave["srus"][1]}> to stock'),
          f'mission {mid} second repaired SRU stock return')
    check(at(log, wave['repair_end'], 'systems ready: 1 :<TEACH-AIR-01,0>'),
          f'mission {mid} readiness after two system repairs')
check(log.count('noncritical random failure added') == 3 and
      len(re.findall(r'(?<!non)critical random failure added', log)) == 3 and
      log.count('Backorder added') == log.count('Backorder removed') == 3,
      'three NC/C link pairs and three resolved SRU backorders')
levels = {kind: [int(m.group(1)) for m in re.finditer(
          rf'Stock at: <{kind},0,BASE-01,0> Level: (\d+)', log)]
          for kind in ('TEACH-LRU-01', 'TEACH-SRU-01')}
check(levels == {
    'TEACH-LRU-01': [2, 1, 0, 1, 2, 1, 0, 1, 2, 1, 0, 1, 2],
    'TEACH-SRU-01': [1, 0, 1, 0, 1, 0, 1]},
    'physical LRU/SRU on-hand sequence across three waves')

report = tables(RUN / 'report-raw.json', 'report')
check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'},
      'four native report tables')
summary = records(report['ResultSummary'])[0]
for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36),
                       ('MTMF', .62163233757019), ('STMF', .62163233757019),
                       ('MSTF', 1), ('MSUF', 0), ('RSMTMF', 0), ('RSMSTF', 0),
                       ('RSMSUF', 0), ('RSSTMF', 0)):
    check(close(summary[name], expected), 'ResultSummary ' + name)
system = records(report['SystemResults'])
stock = records(report['StockTotalResults'])
check(len(system) == len(stock) == 72, '72 aligned System/Stock bins')
reservations = [(7, 8), (19, 20), (31, 32)]
flights = [(w['launch'], w['returned']) for w in waves]
repairs = [(w['returned'], w['repair_end']) for w in waves]
fail_times = [t for w in waves for t in (w['first'], w['second'])]
repair_start_bins = {int(w['returned']*2) for w in waves}
repair_end_bins = {int(w['repair_end']*2) for w in waves}
for index, (s, t) in enumerate(zip(system, stock)):
    h = index / 2
    reserved = sum(occupancy(a, b, h) for a, b in reservations)
    flight = sum(occupancy(a, b, h) for a, b in flights)
    repair = sum(occupancy(a, b, h) for a, b in repairs)
    expected_s = {'NSYRY': 1-reserved-flight-repair, 'NSYMA': reserved+flight,
                  'NSYMO': flight, 'NSYMR': reserved, 'NSYUA': repair,
                  'NSYA': 1-repair, 'FTMO': flight, 'NSYRP': repair,
                  'NREPT': 2 if index in repair_end_bins else 0,
                  'NFAIL': sum(h <= f < h+.5 for f in fail_times),
                  'STACC': flight, 'SYDT': .5 if index in repair_start_bins else None,
                  'NSYDT': int(index in repair_start_bins)}
    expected_t = {'PNB': 1, 'NDF': 2 if index in repair_start_bins else 0,
                  'NWT': 2 if index in repair_start_bins else 0}
    check((s['STINT'], s['ETINT'], t['STINT'], t['ETINT']) == (h, h+.5, h, h+.5),
          f'aligned report interval {index}')
    for name, value in s.items():
        if name in ('UNID', 'SID', 'STINT', 'ETINT'):
            continue
        target = expected_s.get(name, 0)
        check(value is None if target is None else close(value, target),
              f'SystemResults {name} bin {index}')
    for name, value in t.items():
        if name in ('STINT', 'ETINT'):
            continue
        target = (None if name in {'NBOU', 'WTS'} or
                  (name in {'ROS', 'ROST', 'WT', 'WTT'} and index not in repair_start_bins)
                  else expected_t.get(name, 0))
        check(value is None if target is None else close(value, target),
              f'StockTotalResults {name} bin {index}')
check(close(sum(s['NSYMO'] for s in system)*.5,
            sum(w['returned']-w['launch'] for w in waves)),
      'operating-hour integral from three aborted flights')
check(close(sum(s['NSYRP'] for s in system)*.5, 1.5),
      'three half-hour system repairs')
check(all(t['NBO'] == 0 for t in stock),
      'aggregate StockTotalResults NBO does not expose physical SRU backorders')
check(system[-1]['NSYRY'] == 1 and stock[-1]['PNB'] == 1 and stock[-1]['NBO'] == 0,
      'terminal ready and no open backorder')

result = {
    'schema': 'simlox-g10-var03-independent-readonly/v1',
    'passed': not failures, 'verdict': 'GO' if not failures else 'NO-GO',
    'checks_passed': count-len(failures), 'checks_total': count,
    'failures': failures, 'raw_seals': len(closure['raw']),
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'model_log_sha256': sha(RUN / 'model.log'), 'report_sha256': sha(RUN / 'report-raw.json'),
    'observed': 'Three missions each show a first noncritical failed LRU then a distinct second critical LRU failure and abort; paired system SURP, nested SRU issue/backorder/repair and final ready state reconcile.',
    'limits': [
        'One ACTIVE 1-of-2 single-item group with LRU and nested SRU FRT tripled and system FRT raised, one seed through 36 hours.',
        'The log directly shows link IDs/fault severity; the 1-of-2 boundary interpretation is source/manual/outcome bound.',
        'Physical SRU backorders appear in model.log, while aggregate StockTotalResults.NBO remains zero in all bins; no claim that aggregate NBO exposes those internal requests.',
        'No general rate law, PASSIVE crossing, series links, online repair, GUI-only behavior or cross-engine parity.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'],
                  'checks_total': count, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
