"""Independent, read-only replay of the G10.var06 on-mission repair run."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'g10-var06-online-repair-v100-ssh-20261003-01'
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
DONOR_DIR = ROOT / 'G05-unavailable-standby-v1.0.3'
DONOR = DONOR_DIR / 'unavailable-input.json'
check(sha(PARENT) == contract['parent']['input_sha256'], 'accepted parent source')
check(sha(PARENT_RUN / 'closure.json') == contract['parent']['native_closure_sha256'], 'accepted parent closure')
check(sha(PARENT_DIR / 'cli-scope-signoff-2026-10-03.md') == contract['parent']['signoff_sha256'], 'accepted parent signoff')
check(sha(DONOR) == contract['mission_recipe_donor']['input_sha256'], 'accepted donor source')
check(sha(DONOR_DIR / 'cli-scope-signoff-2026-10-02.md') == contract['mission_recipe_donor']['signoff_sha256'], 'accepted donor signoff')
check(sha(SOURCE) == contract['native_input_sha256'], 'child source')
check(sha(CASE / 'exact-diff.json') == contract['exact_diff_sha256'], 'frozen diff')
check(sha(EXTERNAL['manual']) == contract['source']['manual_pdf_sha256'], 'manual SHA')
check(sha(EXTERNAL['dictionary']) == contract['source']['installed_dictionary_sha256'], 'dictionary SHA')
check(sha(EXTERNAL['simlox_exe']) == 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0', 'executable SHA')
check(diff['parent_sha256'] == sha(PARENT) and diff['child_sha256'] == sha(SOURCE), 'diff source pins')
parent, child = tables(PARENT, 'model'), tables(SOURCE, 'model')
changed = {name for name in parent if parent[name] != child[name]}
check(set(parent) == set(child) and changed == set(diff['changed_tables']) == {'MissionType', 'OperationProfile', 'ProblemDescription'} and diff['unchanged_tables'] == 29 and not diff['added_tables'] and not diff['removed_tables'], 'exact three-table delta')
for name in changed:
    check(parent[name]['columns'] == child[name]['columns'] and rows(parent[name]) == diff['changes'][name]['before'] and rows(child[name]) == diff['changes'][name]['after'], 'delta rows ' + name)
for name in set(child)-changed:
    check(child[name] == parent[name], 'unchanged source ' + name)
mission = records(child['MissionType'])[0]
check(mission['MPAT'] == 'CONTINUOUS' and close(mission['DURN'], 26) and mission['TFOUT'] is None and mission['TFRET'] is None, 'one 26-hour continuous mission')
profiles = records(child['OperationProfile'])
check(len(profiles) == 1 and profiles[0]['SPRID'] == 'BASIC-MISSION' and close(profiles[0]['STIM'], 8) and profiles[0]['IQTY'] == 1, 'single h8 mission profile')
red = records(child['Redundancy'])[0]
check(red['ACPA'] == 'ACTIVE' and red['NRL'] == 2 and red['NRLRQ'] == 1 and red['RLID'] == 'TEACH-LRU-01', 'inherited ACTIVE 1-of-2 LRU links')
donor_mission = records(tables(DONOR, 'model')['MissionType'])
check(any(r['MPAT'] == 'CONTINUOUS' and r['TFOUT'] is None and r['TFRET'] is None for r in donor_mission), 'donor continuous schema')

inv, closure = load(RUN / 'invocation.json'), load(RUN / 'closure.json')
check(inv['run_id'] == closure['run_id'] == RUN.name and closure['error'] is None, 'run identity')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation seal')
check(inv['input_sha256'] == sha(SOURCE) == sha(RUN / 'input.json') and inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'), 'run source pins')
check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'], 'session zero SSH')
check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1, 'queue and GUI')
check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'], 'source stability')
paths = {'input': SOURCE, 'parent': PARENT, 'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-10-03.md', 'parent_closure': PARENT_RUN / 'closure.json', 'donor': DONOR, 'donor_signoff': DONOR_DIR / 'cli-scope-signoff-2026-10-02.md', 'contract': CASE / 'contract.json', 'builder': CASE / 'build.py', 'checker': CASE / 'check_roundtrip.py', 'runner_script': CASE / 'run_native_ssh.ps1', **EXTERNAL}
for name, path in paths.items():
    check(sha(path) == closure['source_hashes_before'][name], 'source seal ' + name)
check(len(closure['raw']) == 13, '13 raw seals')
for name, meta in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'], 'raw seal ' + name)
steps = load(RUN / 'steps.json')
check([step['name'] for step in steps] == ['import', 'export', 'calc', 'jsonreport', 'check_import_export'], 'five steps')
for step in steps:
    check(step['exit_code'] == 0 and step['status'] == 'completed' and step['gui_preserved'] and step['error'] is None, 'guarded step ' + step['name'])
check([step['arguments'] for step in steps[:4]] == [command['arguments'] for command in inv['planned_commands']], 'planned native commands')
runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig')
check('Input conversion completed. Errors: 0, Warnings: 1, Notes: 0' in runlog and re.findall(r'warning #(\d+)', runlog) == ['108'] and not re.search(r'\berror\s*#', runlog, re.I), 'converter warning108 only')
check(all((RUN / name).stat().st_size > 1000 for name in ('model.sxo', 'model.log', 'report-raw.json')), 'usable native output')
export = tables(RUN / 'roundtrip-raw.json', 'model')
populated = [name for name, table in child.items() if rows(table)]
check(len(populated) == 22, '22 populated source tables')
for name in populated:
    check(name in export and child[name]['columns'] == export[name]['columns'] and child[name]['instances'] == export[name]['instances'], 'exact roundtrip ' + name)

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
ident = '<BASIC-MISSION,TEACH-UNIT,0,0,0>'
check(at(log, 7, ident + ' mission allocates system: <TEACH-AIR-01,0>') and at(log, 8, ident + ' mission starting, duration: 26') and at(log, 34, ident + ' mission success:') and at(log, 34, ident + ' mission completed:') and ' mission aborted:' not in log, 'one active continuous mission succeeds in log')
check(at(log, 8.31382, 'noncritical random failure added') and at(log, 8.31382, 'system SURP task 0 on <TEACH-AIR-01,0> started') and at(log, 8.81382, 'system SURP task 0 on <TEACH-AIR-01,0> completed') and not re.search(r'Time: (?:8\.31382|8\.81382) .*mission aborted', log), 'first fault on-mission positive repair')
faults = [(float(t), severity) for t, severity in re.findall(r'Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) random failure added', log)]
check(len(faults) == 26 and sum(sev == 'critical' for _, sev in faults) == 6 and all(8 < t < 34 for t, _ in faults), '26 in-mission faults, six critical')
starts = {int(task): float(time) for time, task in re.findall(r'Time: ([\d.]+)  system SURP task (\d+) on <TEACH-AIR-01,0> started\s*\n', log)}
ends = {int(task): float(time) for time, task in re.findall(r'Time: ([\d.]+)  system SURP task (\d+) on <TEACH-AIR-01,0> completed\s*\n', log)}
check(len(starts) == len(ends) == 26 and set(starts) == set(ends) and sorted(starts.values()) == sorted(t for t, _ in faults) and all(0 < ends[k]-starts[k] < 2 for k in starts), '26 fault-aligned system repair tasks')
failed_ids = []
for time, _ in faults:
    block = log.split(f'Time: {time} <TEACH-AIR-01,0> ', 1)[1].split('Time:', 1)[0]
    ids = re.findall(r'subitem failed: <TEACH-LRU-01,0,(\d+)>', block)
    check(bool(ids), f'fault {time} physical LRU identity')
    failed_ids.append(int(ids[-1]) if ids else -1)
check(len(set(failed_ids)) == 26, '26 distinct physical failed LRU IDs')
lru_demands = [(float(t), int(item)) for t, item in re.findall(r'Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>', log)]
sru_demands = [(float(t), int(item)) for t, item in re.findall(r'Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-SRU-01,0,(\d+)>', log)]
check(len(lru_demands) == len(sru_demands) == 26 and [item for _, item in lru_demands] == failed_ids and len({item for _, item in sru_demands}) == 26, 'all failed LRU and nested SRU physical demands')
issues = {}
returns = {}
backorders = {}
for kind, expected_issue, expected_bo in (('TEACH-LRU-01', 19, 7), ('TEACH-SRU-01', 8, 18)):
    issue = [(float(t), int(item)) for t, item in re.findall(rf'Time: ([\d.]+) <{kind},0,BASE-01,0> Take replacement item <{kind},0,(\d+)> from stock', log)]
    returned = [(float(t), int(item)) for t, item in re.findall(rf'Time: ([\d.]+) <{kind},0,BASE-01,0> Put back replacement item <{kind},0,(\d+)> to stock', log)]
    added = [float(t) for t in re.findall(rf'Time: ([\d.]+) <{kind},0,BASE-01,0> Backorder added', log)]
    removed = [(float(t), float(wait)) for t, wait in re.findall(rf'Time: ([\d.]+) <{kind},0,BASE-01,0> Backorder removed, waiting time was ([\d.]+)', log)]
    intervals = []
    unmatched = added.copy()
    for end, wait in removed:
        candidates = [a for a in unmatched if abs((end-a)-wait) < .0001]
        check(bool(candidates), kind + f' backorder wait ending {end}')
        if candidates:
            start = candidates[0]
            intervals.append((start, end, wait))
            unmatched.remove(start)
    check(len(issue) == len(returned) == expected_issue and len(added) == len(removed) == len(intervals) == expected_bo and not unmatched, kind + ' issue/return/backorder counts and clearance')
    check(len({item for _, item in issue}) == expected_issue and len({item for _, item in returned}) == expected_issue, kind + ' physical item identity variation')
    issues[kind], returns[kind], backorders[kind] = issue, returned, intervals
check(len(issues['TEACH-LRU-01']) + len(backorders['TEACH-LRU-01']) == 26 and len(issues['TEACH-SRU-01']) + len(backorders['TEACH-SRU-01']) == 26, 'each physical demand gets stock or backorder')
critical = [t for t, severity in faults if severity == 'critical']
ready = [float(t) for t in re.findall(r'Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>', log)]
check(len(critical) == len(ready) == 6 and all(a < b for a, b in zip(critical, ready)), 'six critical unavailability/recovery intervals')
unavailable = list(zip(critical, ready))
check(log.count('aborts its mission') == 6 and log.count(' mission suspended:') == 6 and log.count(' mission resumed:') == 6 and ' mission aborted:' not in log, 'six abort indications become suspensions, no terminal mission abort')
for n, (start, end) in enumerate(unavailable):
    resume = end if n < 5 else 34
    check(at(log, start, ident + ' mission suspended:') and at(log, resume, ident + ' mission resumed:'), f'critical suspension/resumption {n}')
wait_intervals = [(16.0491, 16.1744), (26.5225, 27.0225)]
check(all(any(a <= x < y <= b for a, b in unavailable) for x, y in wait_intervals), 'two waiting periods within unavailable intervals')
check(at(log, 16.0491, 'System partially repaired') and at(log, 26.5225, 'System partially repaired') and all(any(abs(end-y) < .0001 for _, end, _ in backorders['TEACH-LRU-01']) for _, y in wait_intervals), 'waiting endpoints corroborated by LRU clearance')

report = tables(RUN / 'report-raw.json', 'report')
check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'}, 'four report tables')
summary = records(report['ResultSummary'])[0]
for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36), ('MTMF', .853781521320343), ('STMF', .853781521320343), ('MSTF', 0), ('MSUF', 0)):
    check(close(summary[name], expected), 'summary ' + name)
system, stock = records(report['SystemResults']), records(report['StockTotalResults'])
check(len(system) == len(stock) == 72, '72 System/Stock bins')
for index, (s, t) in enumerate(zip(system, stock)):
    h = index/2
    unavailable_part = sum(occupancy(a, b, h) for a, b in unavailable)
    waiting_part = sum(occupancy(a, b, h) for a, b in wait_intervals)
    available = 1-unavailable_part
    operating = occupancy(8, 34, h)*available
    reserved = occupancy(7, 8, h)
    repaired = sum(h <= end < h+.5 for end in ends.values())
    failed = sum(h <= time < h+.5 for time, _ in faults)
    started = [a for a, _ in unavailable if h <= a < h+.5]
    down = sum(b-a for a, b in unavailable if h <= a < h+.5)
    s_expected = {'NSYRY': (1-occupancy(7, 34, h))*available, 'NSYMA': reserved+operating, 'NSYMO': operating, 'NSYMR': reserved, 'NSYUA': unavailable_part, 'NSYA': available, 'FTMO': operating, 'NSYRP': unavailable_part-waiting_part, 'NSYWI': waiting_part, 'NREPT': repaired, 'NFAIL': failed, 'STACC': operating, 'SYDT': down if started else None, 'NSYDT': len(started)}
    lru_nbo = sum(occupancy(a, b, h) for a, b, _ in backorders['TEACH-LRU-01'])
    demand_count = sum(h <= a < h+.5 for a, _ in lru_demands)
    order_waits = [wait for a, _, wait in backorders['TEACH-LRU-01'] if h <= a < h+.5]
    order_count = len(order_waits)
    t_expected = {'NBO': lru_nbo, 'PNB': max(0, 1-lru_nbo), 'NDF': demand_count, 'NWT': demand_count, 'ROS': order_count/demand_count if demand_count else None, 'ROST': order_count/demand_count if demand_count else None, 'WT': sum(order_waits)/demand_count if demand_count else None, 'WTT': sum(order_waits)/demand_count if demand_count else None, 'WTS': sum(order_waits)/order_count if order_count else None}
    check((s['STINT'], s['ETINT'], t['STINT'], t['ETINT']) == (h, h+.5, h, h+.5), f'interval {index}')
    for name, value in s.items():
        if name in ('UNID', 'SID', 'STINT', 'ETINT'):
            continue
        target = s_expected.get(name, 0)
        check(value is None if target is None else close(value, target), f'SystemResults {name} bin {index}')
    for name, value in t.items():
        if name in ('STINT', 'ETINT'):
            continue
        target = None if name in {'NBOU'} else t_expected.get(name, 0)
        check(value is None if target is None else close(value, target), f'StockTotalResults {name} bin {index}')
check(close(sum(s['NSYMO'] for s in system)*.5, 26-sum(max(0, min(b, 34)-max(a, 8)) for a, b in unavailable)), 'operating-hour integral')
check(close(sum(t['NBO'] for t in stock)*.5, sum(b-a for a, b, _ in backorders['TEACH-LRU-01'])), 'LRU waiting-time integral')
check(system[-1]['NSYRY'] == 1 and stock[-1]['PNB'] == 1 and stock[-1]['NBO'] == 0, 'ready terminal state')

result = {
    'schema': 'simlox-g10-var06-independent-readonly/v1',
    'passed': not failures, 'verdict': 'GO' if not failures else 'NO-GO',
    'checks_passed': count-len(failures), 'checks_total': count, 'failures': failures,
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'model_log_sha256': sha(RUN / 'model.log'), 'report_sha256': sha(RUN / 'report-raw.json'),
    'raw_seals': len(closure['raw']), 'faults': len(faults), 'critical_faults': len(critical),
    'lru_issues': len(issues['TEACH-LRU-01']), 'lru_backorders': len(backorders['TEACH-LRU-01']),
    'sru_issues': len(issues['TEACH-SRU-01']), 'sru_backorders': len(backorders['TEACH-SRU-01']),
    'observed': 'During one h8–34 CONTINUOUS mission, the first LRU fault at 8.31382 triggers a local system SURP completed at 8.81382; 26 faults have repair tasks. Six critical faults print abort indications and mission suspension, with subsequent resumption (last at h34), and the event log records mission success at h34. There is no terminal mission-aborted event. Fixed-mission summary MSTF/MSUF remain zero.',
    'limits': [
        'One ACTIVE 1-of-2 single-item LRU topology, seed1/rep1, one 26-hour CONTINUOUS mission in a 36-hour run; schedule and MPAT changed together from the parent.',
        'Stock/resource unavailable, EXTENDABLE, PASSIVE, multi-item links, alternate rate/topology, GUI-only behavior and cross-engine parity were not tested.',
        'The continuous mission success is directly logged; MSTF/MSUF are zero in this report and are not used to negate the log outcome. No general online-repair law is inferred.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'], 'checks_total': count, 'failures': failures[:30], 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
