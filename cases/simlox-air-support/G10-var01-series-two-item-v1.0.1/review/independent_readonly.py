"""Independent, read-only replay of the G10 two-item series-link run."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'g10-var01-series-two-item-v101-ssh-20261003-01'
PARENT_DIR = ROOT / 'G10-var03-nrlrq-crossing-v1.0.0'
PARENT = PARENT_DIR / 'native-input.json'
PARENT_RUN = PARENT_DIR / 'runs' / 'g10-var03-nrlrq-crossing-v100-ssh-20261003-01'
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


contract, diff = load(CASE / 'contract.json'), load(CASE / 'exact-diff.json')
check(sha(PARENT) == contract['parent']['input_sha256'], 'accepted parent SHA')
check(sha(PARENT_RUN / 'closure.json') == contract['parent']['native_closure_sha256'], 'parent closure SHA')
check(sha(PARENT_DIR / 'cli-scope-signoff-2026-10-03.md') == contract['parent']['signoff_sha256'], 'parent signoff SHA')
check(sha(SOURCE) == contract['native_input_sha256'], 'child input SHA')
check(sha(EXTERNAL['manual']) == contract['source']['manual_pdf_sha256'], 'manual SHA')
check(sha(EXTERNAL['dictionary']) == contract['source']['installed_dictionary_sha256'], 'dictionary SHA')
check(sha(EXTERNAL['simlox_exe']) == 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0', 'executable SHA')
check(diff['parent_sha256'] == sha(PARENT) and diff['child_sha256'] == sha(SOURCE), 'diff pins')
parent, child = tables(PARENT, 'model'), tables(SOURCE, 'model')
changed = {name for name in parent.keys() & child.keys() if parent[name] != child[name]}
added = set(child) - set(parent)
check(changed == set(diff['changed_tables']) == {'Item', 'ItemRepair', 'ItemStructure', 'ProblemDescription', 'Redundancy', 'StockAllocation', 'System'} and added == set(diff['added_tables']) == {'RedundancyLink'} and not set(parent)-set(child) and diff['unchanged_tables'] == 25, 'exact table delta')
for name in changed:
    check(rows(parent[name]) == diff['changes'][name]['before'] and rows(child[name]) == diff['changes'][name]['after'] and parent[name]['columns'] == child[name]['columns'], 'row delta ' + name)
for name in set(parent)-changed:
    check(parent[name] == child[name], 'unchanged table ' + name)
for name in added:
    check(child[name] == diff['additions'][name], 'added table ' + name)
red = records(child['Redundancy'])[0]
check(red['RLID'] == 'G10-SER-LINK' and red['ACPA'] == 'ACTIVE' and red['NRL'] == 2 and red['NRLRQ'] == 1 and red['TSWOV'] == 0, 'ACTIVE one-of-two series links')
links = records(child['RedundancyLink'])
check({(r['RLID'], r['IID'], r['QTYPL']) for r in links} == {('G10-SER-LINK', 'TEACH-LRU-01', 1), ('G10-SER-LINK', 'TEACH-AUX-01', 1)}, 'two item types per link, order independent')
check({(r['IID'], r['QTYPM']) for r in records(child['ItemStructure']) if r['MID'] == 'TEACH-AIR-01'} >= {('TEACH-LRU-01', 2), ('TEACH-AUX-01', 2)}, 'two installed of each link type')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
check([line.split(';')[2] for line in dictionary.splitlines() if line.startswith('RedundancyLink;')] == [c['name'] for c in child['RedundancyLink']['columns']], 'installed link schema')

inv, closure = load(RUN / 'invocation.json'), load(RUN / 'closure.json')
check(inv['run_id'] == closure['run_id'] == RUN.name and closure['error'] is None, 'run closure identity')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation seal')
check(inv['input_sha256'] == sha(SOURCE) == sha(RUN / 'input.json') and inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'), 'invocation source pins')
check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'], 'SSH session zero')
check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1, 'queue and GUI identity')
check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'], 'source stability')
paths = {'input': SOURCE, 'parent': PARENT, 'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-10-03.md', 'parent_closure': PARENT_RUN / 'closure.json', 'contract': CASE / 'contract.json', 'builder': CASE / 'build.py', 'checker': CASE / 'check_roundtrip.py', 'runner_script': CASE / 'run_native_ssh.ps1', **EXTERNAL}
for name, path in paths.items():
    check(sha(path) == closure['source_hashes_before'][name], 'source seal ' + name)
check(len(closure['raw']) == 13, '13 raw seals')
for name, meta in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'], 'raw seal ' + name)
steps = load(RUN / 'steps.json')
check([s['name'] for s in steps] == ['import', 'export', 'calc', 'jsonreport', 'check_import_export'], 'five steps')
for step in steps:
    check(step['exit_code'] == 0 and step['status'] == 'completed' and step['gui_preserved'] and step['error'] is None, 'guarded ' + step['name'])
check([s['arguments'] for s in steps[:4]] == [c['arguments'] for c in inv['planned_commands']], 'planned CLI commands')
runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig')
check('Input conversion completed. Errors: 0, Warnings: 1, Notes: 0' in runlog and re.findall(r'warning #(\d+)', runlog) == ['108'] and not re.search(r'\berror\s*#', runlog, re.I), 'converter only warning108')
check(all((RUN / n).stat().st_size > 1000 for n in ('model.sxo', 'model.log', 'report-raw.json')), 'usable native outputs')
export = tables(RUN / 'roundtrip-raw.json', 'model')
populated = [name for name, table in child.items() if rows(table)]
check(len(populated) == 23, '23 authored populated tables')
for name in populated:
    check(name in export and child[name]['columns'] == export[name]['columns'] and child[name]['instances'] == export[name]['instances'], 'roundtrip ' + name)

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
waves = (
    (0, 7, 8, 8.15691, 8.57314, 9.07314, 9.57314, 'TEACH-LRU-01', 5, 'TEACH-AUX-01', 7, 1, 3, 0, 1),
    (1, 19, 20, 20.1635, 20.6165, 22, 22.5, 'TEACH-AUX-01', 8, 'TEACH-LRU-01', 9, 4, 2, 5, 6),
    (2, 31, 32, 32.2754, 32.3336, 32.6672, 33.1672, 'TEACH-LRU-01', 11, 'TEACH-AUX-01', 13, 5, 7, 10, 11),
)
for mid, order, launch, first, second, returned, ready, kind1, id1, kind2, id2, spare1, spare2, task1, task2 in waves:
    ident = f'<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>'
    success = mid == 1
    check(at(log, order, ident + ' mission allocates system: <TEACH-AIR-01,0>') and at(log, launch, ident + ' mission starting, duration: 2') and at(log, second if not success else 22, ident + (' mission success:' if success else ' mission aborted:')) and at(log, returned, ident + (' mission completed:' if success else ' aborted mission completed:')), f'mission {mid} identity/outcome')
    check(launch < first < second <= returned <= ready, f'mission {mid} chronology')
    first_line = f'Time: {first} <TEACH-AIR-01,0> noncritical random failure added'
    second_line = f'Time: {second} <TEACH-AIR-01,0> ' + ('noncritical' if success else 'critical') + ' random failure added'
    first_block = log.split(first_line, 1)[1].split('Time:', 1)[0] if first_line in log else ''
    second_block = log.split(second_line, 1)[1].split('Time:', 1)[0] if second_line in log else ''
    check(f'subitem failed: <{kind1},0,{id1}>' in first_block and f'subitem failed: <{kind2},0,{id2}>' not in first_block and all(f'subitem failed: <{k},0,{i}>' in second_block for k, i in ((kind1, id1), (kind2, id2))), f'mission {mid} physical first/second fault')
    for kind, failed, spare, task in ((kind1, id1, spare1, task1), (kind2, id2, spare2, task2)):
        check(at(log, returned, f'Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <{kind},0,{failed}>') and at(log, returned, f'Take replacement item <{kind},0,{spare}> from stock') and at(log, returned, f'system SURP task {task} on <TEACH-AIR-01,0> started') and at(log, ready, f'system SURP task {task} on <TEACH-AIR-01,0> completed'), f'mission {mid} {kind} physical exchange and system repair')
    check(at(log, ready, 'System ready <TEACH-AIR-01,0>'), f'mission {mid} terminal system repair')
check(log.count('noncritical random failure added') == 4 and len(re.findall(r'(?<!non)critical random failure added', log)) == 2 and log.count(' mission success:') == 1 and log.count(' mission aborted:') == 2, 'four NC/two C faults, one success/two aborts')
for kind, initial, issues, returns in (
    ('TEACH-LRU-01', 2, [1, 2, 5], [5, 9, 11]),
    ('TEACH-AUX-01', 2, [3, 4, 7], [7, 8, 13]),
    ('TEACH-SRU-01', 1, [0, 6, 10], [6, 10, 12]),
):
    check(at(log, 0, f'<{kind},0,BASE-01,0> Stock initiated'), kind + ' initial stock')
    check(all(re.search(rf'Take replacement item <{kind},0,{item}> from stock', log) for item in issues), kind + ' distinct issues')
    check(all(re.search(rf'Put back replacement item <{kind},0,{item}> to stock', log) for item in returns), kind + ' repaired returns')
    levels = [int(m.group(1)) for m in re.finditer(rf'Stock at: <{kind},0,BASE-01,0> Level: (\d+)', log)]
    check(levels[0] == initial and levels[-1] == initial and min(levels) >= 0, kind + ' terminal stock conservation')

report = tables(RUN / 'report-raw.json', 'report')
check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'}, 'four report tables')
summary = records(report['ResultSummary'])[0]
for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36), ('MSTF', 1), ('MSUF', 0.333333343267441)):
    check(close(summary[name], expected), 'summary ' + name)
system, stock = records(report['SystemResults']), records(report['StockTotalResults'])
check(len(system) == len(stock) == 72, '72 aligned System/Stock bins')
reservations = [(7, 8), (19, 20), (31, 32)]
flights = [(8, 9.07314), (20, 22), (32, 32.6672)]
repairs = [(9.07314, 9.57314), (22, 22.5), (32.6672, 33.1672)]
fail_times = [8.15691, 8.57314, 20.1635, 20.6165, 32.2754, 32.3336]
repair_start_bins = {int(a*2) for a, _ in repairs}
repair_end_bins = {int(b*2) for _, b in repairs}
for index, (s, t) in enumerate(zip(system, stock)):
    h = index / 2
    reserved = sum(occupancy(a, b, h) for a, b in reservations)
    flight = sum(occupancy(a, b, h) for a, b in flights)
    repair = sum(occupancy(a, b, h) for a, b in repairs)
    expected_s = {'NSYRY': 1-reserved-flight-repair, 'NSYMA': reserved+flight, 'NSYMO': flight, 'NSYMR': reserved, 'NSYUA': repair, 'NSYA': 1-repair, 'FTMO': flight, 'NSYRP': repair, 'NREPT': 2 if index in repair_end_bins else 0, 'NFAIL': sum(h <= f < h+.5 for f in fail_times), 'STACC': flight, 'SYDT': .5 if index in repair_start_bins else None, 'NSYDT': int(index in repair_start_bins)}
    expected_t = {'PNB': 1, 'NDF': 2 if index in repair_start_bins else 0, 'NWT': 2 if index in repair_start_bins else 0}
    check((s['STINT'], s['ETINT'], t['STINT'], t['ETINT']) == (h, h+.5, h, h+.5), f'interval {index}')
    for name, value in s.items():
        if name in ('UNID', 'SID', 'STINT', 'ETINT'):
            continue
        target = expected_s.get(name, 0)
        check(value is None if target is None else close(value, target), f'SystemResults {name} bin {index}')
    for name, value in t.items():
        if name in ('STINT', 'ETINT'):
            continue
        target = (None if name in {'NBOU', 'WTS'} or (name in {'ROS', 'ROST', 'WT', 'WTT'} and index not in repair_start_bins) else expected_t.get(name, 0))
        check(value is None if target is None else close(value, target), f'StockTotalResults {name} bin {index}')
check(close(sum(s['NSYMO'] for s in system)*.5, sum(b-a for a, b in flights)), 'flight-hour integral')
check(close(sum(s['NSYRP'] for s in system)*.5, 1.5), 'system repair-hour integral')
check(system[-1]['NSYRY'] == 1 and stock[-1]['PNB'] == 1 and stock[-1]['NBO'] == 0, 'terminal ready and no aggregate backorder')

result = {
    'schema': 'simlox-g10-var01-series-v101-independent-readonly/v1',
    'passed': not failures, 'verdict': 'GO' if not failures else 'NO-GO',
    'checks_passed': count-len(failures), 'checks_total': count, 'failures': failures,
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'model_log_sha256': sha(RUN / 'model.log'), 'report_sha256': sha(RUN / 'report-raw.json'),
    'raw_seals': len(closure['raw']),
    'observed': 'One seeded ACTIVE 1-of-2 series-link run: LRU then AUX faults abort missions 1 and 3; AUX then LRU noncritical faults allow mission 2 success. System, nested item repairs and stock returns reconcile to ready state.',
    'limits': [
        'Two item types per logical link are source-bound; the native event log identifies failed physical item IDs but does not print their redundant-link pairing. No physical link assignment is inferred from row order.',
        'One seed, one installation, three missions, 36-hour horizon. No general rate law, link independence, PASSIVE behavior, GUI-only behavior or cross-engine parity.',
        'Aggregate StockTotalResults cannot identify each item type or physical item; those identities are checked in model.log.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'], 'checks_total': count, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
