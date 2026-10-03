"""Independent, read-only replay of the G10.var07 return-subtask pair."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUNS = {arm: CASE / 'runs' / f'g10-var07-{arm}-v100-ssh-20261003-01' for arm in ('crew-present', 'crew-absent')}
PARENT_DIR = ROOT / 'G10-var06-online-repair-v1.0.0'
PARENT = PARENT_DIR / 'native-input.json'
PARENT_RUN = PARENT_DIR / 'runs' / 'g10-var06-online-repair-v100-ssh-20261003-01'
SOURCES = {arm: CASE / f'native-input-{arm}.json' for arm in RUNS}
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
DONOR_DIR = ROOT / 'D09-var04-shortage-at-escalation-v1.0.0'
DONOR = DONOR_DIR / 'native-input-supplied.json'
check(sha(PARENT) == contract['parent']['input_sha256'], 'accepted parent SHA')
check(sha(PARENT_RUN / 'closure.json') == contract['parent']['native_closure_sha256'], 'accepted parent closure')
check(sha(PARENT_DIR / 'cli-scope-signoff-2026-10-03.md') == contract['parent']['signoff_sha256'], 'accepted parent signoff')
check(sha(DONOR) == contract['resource_donor']['input_sha256'], 'resource donor input')
check(sha(DONOR_DIR / 'cli-scope-signoff-2026-10-02.md') == contract['resource_donor']['signoff_sha256'], 'resource donor signoff')
check(sha(CASE / 'exact-diff.json') == contract['exact_diff_sha256'], 'frozen exact diff')
check(sha(EXTERNAL['manual']) == contract['source']['manual_pdf_sha256'], 'manual SHA')
check(sha(EXTERNAL['dictionary']) == contract['source']['installed_dictionary_sha256'], 'dictionary SHA')
check(sha(EXTERNAL['simlox_exe']) == 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0', 'executable SHA')
check(diff['parent_sha256'] == sha(PARENT), 'diff parent pin')
for arm in RUNS:
    check(sha(SOURCES[arm]) == contract['arms'][arm]['input_sha256'] == diff[arm.replace('-', '_')+'_sha256'], arm + ' input pin')
parent = tables(PARENT, 'model')
models = {arm: tables(source, 'model') for arm, source in SOURCES.items()}
present, absent = models['crew-present'], models['crew-absent']
parent_changed = {name for name in parent if parent[name] != present[name]}
pair_changed = {name for name in present if present[name] != absent[name]}
check(set(parent) == set(present) == set(absent) and parent_changed == set(diff['parent_changed_tables']) == {'MissionType', 'OperationProfile', 'ProblemDescription', 'Resource', 'ResourceAllocation', 'SubTaskResource', 'SystemRepair', 'TaskBreakDown'}, 'exact parent-to-present table set')
check(pair_changed == set(diff['pair_changed_tables']) == {'ProblemDescription', 'ResourceAllocation'}, 'exact arm table set')
for name in parent_changed:
    check(rows(parent[name]) == diff['parent_changes'][name]['before'] and rows(present[name]) == diff['parent_changes'][name]['after'] and parent[name]['columns'] == present[name]['columns'], 'parent delta ' + name)
for name in set(parent)-parent_changed:
    check(parent[name] == present[name], 'unchanged parent table ' + name)
for name in pair_changed:
    check(rows(present[name]) == diff['pair_changes'][name]['before'] and rows(absent[name]) == diff['pair_changes'][name]['after'] and present[name]['columns'] == absent[name]['columns'], 'pair delta ' + name)
for name in set(present)-pair_changed:
    check(present[name] == absent[name], 'unchanged pair table ' + name)
check(records(present['ResourceAllocation'])[0]['RQTY'] == 1 and records(absent['ResourceAllocation'])[0]['RQTY'] == 0, 'only resource demand changes 1 to 0')
check(records(present['MissionType'])[0]['MPAT'] == 'CONTINUOUS' and close(records(present['MissionType'])[0]['DURN'], 1), 'one-hour continuous mission')
check({r['STIM'] for r in records(present['OperationProfile'])} == {8, 10.5}, 'two mission profile starts')
check(records(present['Redundancy'])[0]['ACPA'] == 'ACTIVE' and records(present['Redundancy'])[0]['NRLRQ'] == 1, 'unchanged active redundancy')
check(any(r['RID'] == 'P-CREW' for r in records(present['Resource'])), 'crew resource source')
check(all(any(r['TID'] == 'E01-SURP' and r['SUTID'] == subtask and r['SEQ'] == seq and close(r['DURN'], duration) for r in records(present['TaskBreakDown'])) for subtask, seq, duration in (('<REMOVE>', 1, 1/6), ('<REPLACE>', 2, 2.83333333333333))), 'first removal and long replacement durations')
check(any(r['TID'] == 'E01-SURP' and r['SEQ'] == 1 and r['RID'] == 'P-CREW' and r['QTY'] == 1 for r in records(present['SubTaskResource'])), 'crew demand belongs to first removal subtask')

results = {}
for arm, run in RUNS.items():
    source = SOURCES[arm]
    model = models[arm]
    inv, closure = load(run / 'invocation.json'), load(run / 'closure.json')
    check(inv['run_id'] == closure['run_id'] == run.name and closure['error'] is None, arm + ' run identity')
    check(sha(run / 'invocation.json') == closure['invocation_sha256'], arm + ' invocation seal')
    check(inv['input_sha256'] == sha(source) == sha(run / 'input.json') and inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'), arm + ' input/parent/contract pins')
    check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'], arm + ' SSH session zero')
    check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1, arm + ' queue/GUI identity')
    check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'], arm + ' source stability')
    paths = {'input': source, 'parent': PARENT, 'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-10-03.md', 'parent_closure': PARENT_RUN / 'closure.json', 'donor': DONOR, 'donor_signoff': DONOR_DIR / 'cli-scope-signoff-2026-10-02.md', 'exact_diff': CASE / 'exact-diff.json', 'contract': CASE / 'contract.json', 'builder': CASE / 'build.py', 'checker': CASE / 'check_roundtrip.py', 'runner_script': CASE / 'run_native_ssh.ps1', **EXTERNAL}
    for name, path in paths.items():
        check(sha(path) == closure['source_hashes_before'][name], arm + ' source seal ' + name)
    check(len(closure['raw']) == 13, arm + ' 13 raw seals')
    for name, meta in closure['raw'].items():
        path = run / name
        check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'], arm + ' raw seal ' + name)
    steps = load(run / 'steps.json')
    check([s['name'] for s in steps] == ['import', 'export', 'calc', 'jsonreport', 'check_import_export'], arm + ' five steps')
    for step in steps:
        check(step['exit_code'] == 0 and step['status'] == 'completed' and step['gui_preserved'] and step['error'] is None, arm + ' guarded ' + step['name'])
    check([s['arguments'] for s in steps[:4]] == [c['arguments'] for c in inv['planned_commands']], arm + ' planned commands')
    runlog = (run / 'run.log').read_text(encoding='utf-8-sig')
    check('Input conversion completed. Errors: 0, Warnings: 1, Notes: 0' in runlog and re.findall(r'warning #(\d+)', runlog) == ['108'] and not re.search(r'\berror\s*#', runlog, re.I), arm + ' converter diagnostics')
    check(all((run / n).stat().st_size > 1000 for n in ('model.sxo', 'model.log', 'report-raw.json')), arm + ' valid outputs')
    export = tables(run / 'roundtrip-raw.json', 'model')
    populated = [name for name, table in model.items() if rows(table)]
    check(len(populated) == 25, arm + ' 25 populated tables')
    for name in populated:
        check(name in export and model[name]['columns'] == export[name]['columns'] and model[name]['instances'] == export[name]['instances'], arm + ' roundtrip ' + name)
    log = (run / 'model.log').read_text(encoding='utf-8-sig')
    first, second = '<BASIC-MISSION,TEACH-UNIT,0,0,0>', '<BASIC-MISSION,TEACH-UNIT,0,0,1>'
    check(at(log, 7, first + ' mission allocates system: <TEACH-AIR-01,0>') and at(log, 8, first + ' mission starting, duration: 1') and at(log, 9, first + ' mission success:') and at(log, 9, first + ' mission completed:'), arm + ' first mission lifecycle')
    check(at(log, 9.5, second + ' mission created:') and at(log, 10.5, second + ' mission starting, duration: 1') and at(log, 11.5, second + ' mission success:') and at(log, 11.5, second + ' mission completed:'), arm + ' second mission lifecycle')
    check(log.count('noncritical random failure added') == 1 and not re.search(r'(?<!non)critical random failure added', log) and at(log, 8.31382, 'noncritical random failure added') and at(log, 8.31382, 'system SURP task 0 on <TEACH-AIR-01,0> started'), arm + ' matched physical fault and repair task')
    check('subitem failed: <TEACH-LRU-01,0,3>' in log and at(log, 8.31382, 'Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,3>') and at(log, 8.31382, 'Take replacement item <TEACH-LRU-01,0,1> from stock'), arm + ' failed LRU3 and issued spare1')
    for kind, expected in (('TEACH-LRU-01', [2, 1, 2] if arm == 'crew-present' else [2, 1]), ('TEACH-SRU-01', [1, 0, 1] if arm == 'crew-present' else [1])):
        levels = [int(x) for x in re.findall(rf'Stock at: <{kind},0,BASE-01,0> Level: (\d+)', log)]
        check(levels == expected, arm + ' physical ' + kind + ' stock sequence')
    check(at(log, 8.31382, 'remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> started') and at(log, 8.31382, 'resource availability test'), arm + ' remove subtask created and tested')
    if arm == 'crew-present':
        check(at(log, 8.31382, 'remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> books resources') and at(log, 8.31382, 'remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> starts performing') and at(log, 8.48048, 'remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> frees resources'), 'present first subtask positive work before return')
        check(at(log, 8.31382, '<P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0') and at(log, 8.48048, '<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1'), 'present typed crew lease and release')
        check('Time: 9 <TEACH-AIR-01,BASE-01,0> System arrives' in log and 'subitemtype failed: TEACH-LRU-01' in log and at(log, 11.3138, 'system SURP task 0 on <TEACH-AIR-01,0> completed') and at(log, 11.3138, 'System ready <TEACH-AIR-01,0>'), 'present return critical unfinished task until 11.3138')
        check(at(log, 10.5, second + ' mission suspended:') and at(log, 11.3138, second + ' mission resumed: <TEACH-AIR-01,0>') and at(log, 11.3138, second + ' mission allocates system: <TEACH-AIR-01,0>'), 'present second mission delayed by repair')
        check(at(log, 8.48048, 'Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-SRU-01,0,4>') and at(log, 8.48048, 'Take replacement item <TEACH-SRU-01,0,0> from stock') and at(log, 9.23048, 'Put back replacement item <TEACH-LRU-01,0,3> to stock') and at(log, 9.85548, 'Put back replacement item <TEACH-SRU-01,0,4> to stock'), 'present nested SRU and item stock return')
        check(log.count('books resources') == log.count('frees resources') == 1 and not re.search(r'Backorder added', log), 'present one crew lease and no backorder')
    else:
        check('Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed' in log and 'books resources' not in log and 'starts performing' not in log, 'absent first subtask never performs')
        check(at(log, 9, 'System NCF ready <TEACH-AIR-01,0>') and at(log, 9.5, second + ' mission allocates system: <TEACH-AIR-01,0>') and at(log, 10.5, second + ' mission starting, duration: 1 : <TEACH-AIR-01,0>') and 'mission suspended:' not in log, 'absent return noncritical and second mission eligible')
        check(at(log, 11.5, 'System NCF ready <TEACH-AIR-01,0>') and at(log, 24, 'resource availability test') and 'system SURP task 0 on <TEACH-AIR-01,0> completed' not in log and 'Put back replacement item' not in log, 'absent open repair at horizon')
        check('Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0>' not in log and 'Backorder added' not in log, 'absent no nested SRU route or backorder')
    report = tables(run / 'report-raw.json', 'report')
    check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults', 'ResourceResults', 'ResourceResultsTotal'}, arm + ' six report tables')
    summary = records(report['ResultSummary'])[0]
    for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36), ('MTMF', .593091726303101 if arm == 'crew-present' else 1), ('STMF', .593091726303101 if arm == 'crew-present' else 1), ('MSTF', 0), ('MSUF', 0)):
        check(close(summary[name], expected), arm + ' summary ' + name)
    system, stock, resource = (records(report[name]) for name in ('SystemResults', 'StockTotalResults', 'ResourceResults'))
    check(len(system) == len(stock) == len(resource) == 72, arm + ' 72 aligned report bins')
    total_resource = records(report['ResourceResultsTotal'])[0]
    for name, expected in (('NR', 1 if arm == 'crew-present' else 0), ('NRUM', (1/6)/36 if arm == 'crew-present' else 0), ('NRW', 0 if arm == 'crew-present' else (36-8.31382)/36)):
        check(close(total_resource[name], expected), arm + ' ResourceResultsTotal ' + name)
    reservations = [(7, 8)] + ([] if arm == 'crew-present' else [(9.5, 10.5)])
    flights = [(8, 9), (11.3138, 11.5)] if arm == 'crew-present' else [(8, 9), (10.5, 11.5)]
    unavailable = (9, 11.3138) if arm == 'crew-present' else None
    for index, (s, t, r) in enumerate(zip(system, stock, resource)):
        h = index/2
        reserve = sum(occupancy(a, b, h) for a, b in reservations)
        flying = sum(occupancy(a, b, h) for a, b in flights)
        down = occupancy(*unavailable, h) if unavailable else 0
        ready = 1-reserve-flying-down
        s_expected = {'NSYRY': ready, 'NSYMA': reserve+flying, 'NSYMO': flying, 'NSYMR': reserve, 'NSYUA': down, 'NSYA': 1-down, 'FTMO': flying, 'NSYRP': down, 'NREPT': int(arm == 'crew-present' and h <= 11.3138 < h+.5), 'NFAIL': int(h <= 8.31382 < h+.5), 'STACC': flying, 'SYDT': 2.3138165473938 if arm == 'crew-present' and h == 9 else None, 'NSYDT': int(arm == 'crew-present' and h == 9)}
        t_expected = {'PNB': 1, 'NDF': int(h <= 8.31382 < h+.5), 'NWT': int(h <= 8.31382 < h+.5)}
        r_expected = {'NR': int(arm == 'crew-present'), 'NRUM': occupancy(8.31382, 8.48048, h) if arm == 'crew-present' else 0, 'NRW': occupancy(8.31382, 36, h) if arm == 'crew-absent' else 0, 'NRA': int(arm == 'crew-present'), 'NRN': int(arm == 'crew-present')}
        check((s['STINT'], s['ETINT'], t['STINT'], t['ETINT'], r['STINT'], r['ETINT']) == (h, h+.5, h, h+.5, h, h+.5), arm + f' aligned interval {index}')
        for name, value in s.items():
            if name in ('UNID', 'SID', 'STINT', 'ETINT'):
                continue
            target = s_expected.get(name, 0)
            check(value is None if target is None else close(value, target), arm + f' SystemResults {name} bin {index}')
        for name, value in t.items():
            if name in ('STINT', 'ETINT'):
                continue
            target = None if name in {'NBOU', 'WTS'} or (name in {'ROS', 'ROST', 'WT', 'WTT'} and h != 8) else t_expected.get(name, 0)
            check(value is None if target is None else close(value, target), arm + f' StockTotalResults {name} bin {index}')
        for name, value in r.items():
            if name in ('RID', 'STID', 'STINT', 'ETINT'):
                continue
            check(close(value, r_expected.get(name, 0)), arm + f' ResourceResults {name} bin {index}')
    check(close(sum(s['NSYMO'] for s in system)*.5, sum(b-a for a, b in flights)), arm + ' flight-hour integral')
    check(close(sum(s['NSYRP'] for s in system)*.5, 2.3138 if arm == 'crew-present' else 0), arm + ' repair-hour integral')
    check(system[-1]['NSYRY'] == 1 and stock[-1]['PNB'] == 1 and resource[-1]['NRW'] == (1 if arm == 'crew-absent' else 0), arm + ' terminal system/resource state')
    results[arm] = {'input_sha256': sha(source), 'closure_sha256': sha(run / 'closure.json'), 'model_log_sha256': sha(run / 'model.log'), 'report_sha256': sha(run / 'report-raw.json'), 'raw_seals': len(closure['raw'])}

result = {
    'schema': 'simlox-g10-var07-independent-readonly/v1', 'passed': not failures,
    'verdict': 'GO' if not failures else 'NO-GO', 'checks_passed': count-len(failures),
    'checks_total': count, 'failures': failures, 'runs': results,
    'observed': 'Matched LRU3 noncritical fault at 8.31382 in both arms. Crew present books P-CREW and starts positive removal before return h9; unfinished system repair makes the second mission suspend at 10.5 until system ready 11.3138, then succeed 11.5. Crew absent never begins work; NCF-ready aircraft is allocated again at 9.5 and flies 10.5–11.5 while the repair waits through horizon.',
    'limits': [
        'Only RQTY1 versus0 is isolated within the pair. Both arms jointly change duration, schedule, replacement task and crew demand from the G10.var06 parent.',
        'One seed, one aircraft, one crew type and local stock; no general rule for different return timing, other resource/stock configurations, EXTENDABLE or PASSIVE missions, GUI-only behavior or cross-engine parity.',
        'A system repair task being created is distinct from its first subtask performing; next-mission eligibility is grounded in allocation and event logs, not source or scheduled time alone.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'], 'checks_total': count, 'failures': failures[:30], 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
