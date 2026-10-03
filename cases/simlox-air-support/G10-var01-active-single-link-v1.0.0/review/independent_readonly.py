"""Independent read-only replay of G10.var01 ACTIVE single-item link evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'g10-var01-active-v100-ssh-20261003-01'
PARENT_DIR = ROOT / 'G01-var05-qty-two-v1.0.0'
PARENT = PARENT_DIR / 'native-input.json'
PARENT_RUN = PARENT_DIR / 'runs' / 'g01-var05-qty-v100-ssh-20261001-01'
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
    # Native SIMLOX JSON sometimes retains commas before closing delimiters.
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
    names = [c['name'] for c in table['columns']]
    return [dict(zip(names, row)) for row in rows(table)]


def at(log, time, fragment):
    return any(line.startswith('Time: ' + str(time) + ' ') and fragment in line
               for line in log.splitlines())


def close(a, b, tolerance=.0007):
    return isinstance(a, (int, float)) and math.isclose(a, b, abs_tol=tolerance)


contract = load(CASE / 'contract.json')
diff = load(CASE / 'exact-diff.json')
check(sha(PARENT) == contract['parent']['input_sha256'], 'accepted parent SHA')
check(sha(SOURCE) == contract['native_input_sha256'], 'frozen native input SHA')
check(sha(EXTERNAL['manual']) == contract['source']['manual_pdf_sha256'], 'installed manual SHA')
check(sha(EXTERNAL['dictionary']) == contract['source']['installed_dictionary_sha256'], 'installed dictionary SHA')
check(sha(EXTERNAL['simlox_exe']) ==
      'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0',
      'installed executable SHA')
check(diff['parent_sha256'] == sha(PARENT) and diff['child_sha256'] == sha(SOURCE),
      'exact-diff SHA bindings')
check(sha(PARENT_RUN / 'closure.json') ==
      '1918f5573953952dae76a5f35631e5c96070b60f5347f914f912f0dca57148c9',
      'accepted G01 native parent closure')
parent, child = tables(PARENT, 'model'), tables(SOURCE, 'model')
changed = {name for name in parent.keys() & child.keys() if parent[name] != child[name]}
added = set(child) - set(parent)
check(changed == set(diff['changed_tables']) == {'Control', 'ProblemDescription'} and
      added == set(diff['added_tables']) == {'Redundancy'} and
      set(parent) - set(child) == set() and diff['unchanged_tables'] == len(parent) - 2,
      'exact two changed and one added business tables')
for name in changed:
    check(rows(parent[name]) == diff['changes'][name]['before'] and
          rows(child[name]) == diff['changes'][name]['after'] and
          parent[name]['columns'] == child[name]['columns'], 'exact delta ' + name)
check(child['Redundancy'] == diff['redundancy'], 'exact added Redundancy table')
control = records(child['Control'])[0]
check(control['RELOP'] == 'REDUNDANCY' and records(parent['Control'])[0]['RELOP'] is None,
      'isolated reliability option')
links = records(child['Redundancy'])
check(len(links) == 1 and links[0] ==
      {'RLID': 'TEACH-LRU-01', 'SID': 'TEACH-AIR-01', 'NRL': 2, 'NRLRQ': 1,
       'ACPA': 'ACTIVE', 'TSWOV': 0, 'NOTE': None}, 'ACTIVE 1-of-2 source row')
check(any(r['IID'] == 'TEACH-LRU-01' and r['MID'] == 'TEACH-AIR-01' and r['QTYPM'] == 2
          for r in records(child['ItemStructure'])), 'two installed LRU links')
check(any(r['IID'] == 'TEACH-SRU-01' and r['MID'] == 'TEACH-LRU-01' and r['QTYPM'] == 1
          for r in records(child['ItemStructure'])), 'nested SRU per LRU')
for name in parent:
    if name not in changed:
        check(child[name] == parent[name], 'unchanged parent table ' + name)
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
check([line.split(';')[2] for line in dictionary.splitlines() if line.startswith('Redundancy;')] ==
      ['RLID', 'SID', 'NRL', 'NRLRQ', 'ACPA', 'TSWOV', 'NOTE'], 'installed Redundancy column schema')

inv, closure = load(RUN / 'invocation.json'), load(RUN / 'closure.json')
check(inv['run_id'] == closure['run_id'] == RUN.name and closure['error'] is None,
      'native run identity and closure')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation seal')
check(inv['input_sha256'] == sha(SOURCE) == sha(RUN / 'input.json') and
      inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'),
      'input, parent, contract invocation pins')
check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and
      inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'],
      'SSH session0 provenance')
check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and
      inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1,
      'native queue and GUI identity')
check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'],
      'source stability during native execution')
paths = {'input': SOURCE, 'parent': PARENT,
         'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-10-01.md',
         'parent_closure': PARENT_RUN / 'closure.json',
         'contract': CASE / 'contract.json', 'builder': CASE / 'build.py',
         'checker': CASE / 'check_roundtrip.py', 'runner_script': CASE / 'run_native_ssh.ps1',
         **EXTERNAL}
for key, path in paths.items():
    check(sha(path) == closure['source_hashes_before'][key], 'source SHA seal ' + key)
check(len(closure['raw']) == 13, '13 raw file seals')
for name, meta in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'],
          'raw bytes/SHA ' + name)
steps = load(RUN / 'steps.json')
check([s['name'] for s in steps] == ['import', 'export', 'calc', 'jsonreport', 'check_import_export'],
      'five guarded steps')
for step in steps:
    check(step['exit_code'] == 0 and step['status'] == 'completed' and
          step['gui_preserved'] and step['error'] is None,
          'guarded step ' + step['name'])
check([s['arguments'] for s in steps[:4]] == [c['arguments'] for c in inv['planned_commands']],
      'planned command arguments')
check((RUN / 'model.sxo').stat().st_size > 100000 and
      (RUN / 'model.log').stat().st_size > 1000 and
      (RUN / 'report-raw.json').stat().st_size > 1000, 'valid native artifacts')
runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig')
check('Input conversion completed. Errors: 0, Warnings: 1, Notes: 0' in runlog and
      'warning #108' in runlog and not re.search(r'\berror\s*#', runlog, re.I),
      'zero conversion errors and reviewed warning')
exported = tables(RUN / 'roundtrip-raw.json', 'model')
populated = [name for name, table in child.items() if rows(table)]
check(len(populated) == 22, '22 row-containing source tables')
for name in populated:
    check(name in exported and child[name]['columns'] == exported[name]['columns'] and
          child[name]['instances'] == exported[name]['instances'], 'exact native roundtrip ' + name)

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
for i, (order, launch, end) in enumerate(((7, 8, 10), (19, 20, 22), (31, 32, 34))):
    ident = f'<BASIC-MISSION,TEACH-UNIT,0,0,{i}>'
    check(at(log, order, 'mission ordered: BASIC-MISSION') and
          at(log, order, ident + ' mission allocates system: <TEACH-AIR-01,0>') and
          at(log, launch, ident + ' mission starting, duration: 2') and
          at(log, end, ident + ' mission success:') and
          at(log, end, ident + ' mission completed:') and
          ident + ' mission aborted:' not in log, f'mission {i} full success')
check(at(log, 8.94145, 'noncritical random failure added') and
      at(log, 21.6494, 'noncritical random failure added') and
      log.count('random failure added') == 2 and
      not re.search(r'(?<!non)critical random failure added', log),
      'exact two noncritical LRU link failures')
check('subitem failed: <TEACH-LRU-01,0,3> connection path: TEACH-AIR-01' in log and
      'subitem failed: <TEACH-LRU-01,0,5> connection path: TEACH-AIR-01' in log and
      log.index('subitem failed: <TEACH-LRU-01,0,3>') <
      log.index('subitem failed: <TEACH-LRU-01,0,5>'),
      'distinct installed link failures 3 and 5')
check('Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 2 Items:<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,2>' in log and
      'Stock at: <TEACH-SRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-SRU-01,0,0>' in log,
      'opening physical spare identities')
for (failed, lru_spare, sru_failed, sru_spare, demand, lru_start, lru_end,
     sru_start, sru_end, system_task, lru_task, sru_task) in (
        (3, 1, 4, 0, 10, 10.1667, 10.9167, 10.5417, 11.5417, 0, 1, 2),
        (5, 2, 6, 4, 22, 22.1667, 22.9167, 22.5417, 23.5417, 3, 4, 5)):
    check(at(log, demand, f'Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,{failed}>') and
          at(log, demand, f'Take replacement item <TEACH-LRU-01,0,{lru_spare}> from stock'),
          f'LRU {failed} demand and spare {lru_spare} issue')
    check(at(log, lru_start, f'Item requiring maintenance arrives <TEACH-LRU-01,0,{failed}>') and
          at(log, lru_start, f'subitem failed: <TEACH-SRU-01,0,{sru_failed}>') and
          at(log, lru_start, f'Take replacement item <TEACH-SRU-01,0,{sru_spare}> from stock'),
          f'LRU {failed} nested SRU failure and issue')
    check(at(log, demand, f'system SURP task {system_task} on <TEACH-AIR-01,0> started') and
          at(log, demand + .5, f'system SURP task {system_task} on <TEACH-AIR-01,0> completed'),
          f'half-hour system SURP {system_task}')
    check(at(log, lru_start, f'item SURP task {lru_task} on <TEACH-LRU-01,0,{failed}> started') and
          at(log, lru_end, f'item SURP task {lru_task} on <TEACH-LRU-01,0,{failed}> completed') and
          at(log, lru_end, f'Put back replacement item <TEACH-LRU-01,0,{failed}> to stock'),
          f'LRU {failed} repair/stock return')
    check(at(log, sru_start, f'item DIRP task {sru_task} on <TEACH-SRU-01,0,{sru_failed}> started') and
          at(log, sru_end, f'item DIRP task {sru_task} on <TEACH-SRU-01,0,{sru_failed}> completed') and
          at(log, sru_end, f'Put back replacement item <TEACH-SRU-01,0,{sru_failed}> to stock'),
          f'SRU {sru_failed} direct repair/stock return')
levels = {kind: [int(m.group(1)) for m in re.finditer(
          rf'Stock at: <{kind},0,BASE-01,0> Level: (\d+)', log)]
          for kind in ('TEACH-LRU-01', 'TEACH-SRU-01')}
check(levels == {'TEACH-LRU-01': [2, 1, 2, 1, 2],
                 'TEACH-SRU-01': [1, 0, 1, 0, 1]}, 'physical stock conservation sequence')
check('Backorder added' not in log and 'transport task' not in log, 'no backorder or transport')
check(at(log, 34, 'systems ready: 1 :<TEACH-AIR-01,0>'), 'terminal ready aircraft')

report = tables(RUN / 'report-raw.json', 'report')
check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'},
      'four report tables')
summary = records(report['ResultSummary'])[0]
for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36), ('MTMF', 1),
                       ('STMF', 1), ('MSTF', 1), ('MSUF', 1), ('RSMTMF', 0),
                       ('RSMSTF', 0), ('RSMSUF', 0), ('RSSTMF', 0)):
    check(close(summary[name], expected), 'summary ' + name)
system = records(report['SystemResults'])
stock = records(report['StockTotalResults'])
check(len(system) == len(stock) == 72, '72 System/Stock bins')
for i, (s, t) in enumerate(zip(system, stock)):
    h = i / 2
    reserved = int(h in (7, 7.5, 19, 19.5, 31, 31.5))
    flight = int(8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34)
    repair = int(h in (10, 22))
    expected_s = {'NSYRY': 1 - reserved - flight - repair,
                  'NSYMA': reserved + flight, 'NSYMO': flight, 'NSYMR': reserved,
                  'NSYUA': repair, 'NSYA': 1 - repair, 'FTMO': flight,
                  'NSYRP': repair, 'NREPT': int(h in (10.5, 22.5)),
                  'NFAIL': int(h in (8.5, 21.5)), 'STACC': flight,
                  'SYDT': .5 if h in (10, 22) else None,
                  'NSYDT': int(h in (10, 22))}
    expected_t = {'PNB': 1, 'NDF': int(h in (10, 22)), 'NWT': int(h in (10, 22))}
    check((s['STINT'], s['ETINT'], t['STINT'], t['ETINT']) == (h, h+.5, h, h+.5),
          f'aligned bin {i}')
    check(s['UNID'] == 'Total over all Units' and s['SID'] == 'Total over all Systems',
          f'aggregate labels bin {i}')
    for name, value in s.items():
        if name in ('UNID', 'SID', 'STINT', 'ETINT'):
            continue
        target = expected_s.get(name, 0)
        check(value is None if target is None else close(value, target), f'SystemResults {name} bin {i}')
    for name, value in t.items():
        if name in ('STINT', 'ETINT'):
            continue
        target = (None if name in {'NBOU', 'WTS'} or
                  (name in {'ROS', 'ROST', 'WT', 'WTT'} and h not in (10, 22))
                  else expected_t.get(name, 0))
        check(value is None if target is None else close(value, target),
              f'StockTotalResults {name} bin {i}')
check(close(sum(s['NSYMO'] for s in system) * .5, 6), 'six aircraft flight-hours')
check(close(sum(s['NSYRP'] for s in system) * .5, 1), 'one hour system SURP work')
check(system[-1]['NSYRY'] == 1 and stock[-1]['PNB'] == 1 and stock[-1]['NBO'] == 0,
      'terminal ready/stock/backorder report')

result = {
    'schema': 'simlox-g10-var01-independent-readonly/v1',
    'passed': not failures, 'verdict': 'GO' if not failures else 'NO-GO',
    'checks_passed': checks - len(failures), 'checks_total': checks,
    'failures': failures, 'raw_seals': len(closure['raw']),
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'model_log_sha256': sha(RUN / 'model.log'), 'report_sha256': sha(RUN / 'report-raw.json'),
    'observed': 'Two distinct installed LRU IDs 3/5 fail noncritically in separate flights; all three missions succeed, two nested LRU/SRU replacement and repair chains return local stock, terminal ready1.',
    'limits': [
        'One fixed seed, one ACTIVE 1-of-2 single-item link group, two successive isolated link failures; no concurrent two-link-failed transition occurs.',
        'Native log does not enumerate both initially installed LRUs together; IDs 3/5 are source-and-sequence-bound inferred originals, while opening spare IDs 1/2 are directly logged.',
        'No two-item series link, PASSIVE switching, nonzero TSWOV, other NRLRQ, stochastic law, GUI-only or cross-engine claim.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'],
                  'checks_total': checks, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
