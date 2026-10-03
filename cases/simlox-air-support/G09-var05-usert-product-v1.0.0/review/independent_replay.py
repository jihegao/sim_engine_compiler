"""Independent read-only replay of G09.var05 two-level USERT products."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
OUT = CASE / 'review' / 'independent-validation-2026-10-03.json'
RUNS = {arm: CASE / 'runs' / f'g09-var05-{arm}-v100-ssh-20261003-01'
        for arm in ('factorhalf', 'factorfull')}
EXTERNAL = {
    'python': Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    'exe': Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
    'manual': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
    'dictionary': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path):
    data = path.read_text(encoding='utf-8-sig')
    clean = []
    quoted = escaped = False
    for i, char in enumerate(data):
        if quoted:
            clean.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            clean.append(char)
        elif char == ',':
            j = i + 1
            while j < len(data) and data[j].isspace():
                j += 1
            if j == len(data) or data[j] not in '}]':
                clean.append(char)
        else:
            clean.append(char)
    return json.loads(''.join(clean))


def tables(document, root):
    return {table['name']: table for table in document[root]['tables']}


def rows(table):
    return [row for instance in table['instances'] for row in instance['rows']]


def records(table):
    fields = [column['name'] for column in table['columns']]
    return [dict(zip(fields, row)) for row in rows(table)]


def near(a, b, tolerance=.0007):
    return isinstance(a, (int, float)) and math.isclose(a, b, abs_tol=tolerance)


def occupancy(a, b, start):
    return 2 * max(0, min(b, start + .5) - max(a, start))


checks = 0
failures = []


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


contract = native_json(CASE / 'contract.json')
control_dir = CASES / contract['accepted_parent']['package']
full_file = control_dir / 'use1-input.json'
full_run = control_dir / 'runs' / contract['accepted_parent']['run_id']
half_file = control_dir / 'use05-input.json'
half_run = control_dir / 'runs' / contract['accepted_direct_half_control']['run_id']
parent = tables(native_json(full_file), 'model')
direct_half = tables(native_json(half_file), 'model')
diff = native_json(CASE / 'exact-diff.json')
for path, expected, label in (
    (full_file, contract['accepted_parent']['input_sha256'], 'accepted direct product1 source'),
    (full_run / 'closure.json', contract['accepted_parent']['native_closure_sha256'],
     'accepted direct product1 closure'),
    (half_file, contract['accepted_direct_half_control']['input_sha256'],
     'accepted direct product0.5 source'),
    (half_run / 'closure.json', contract['accepted_direct_half_control']['native_closure_sha256'],
     'accepted direct product0.5 closure'),
    (CASE / 'exact-diff.json', contract['exact_diff_sha256'], 'frozen exact diff'),
):
    check(sha(path) == expected, label + ' SHA-256')
check(diff['parent_sha256'] == sha(full_file) and
      diff['direct_half_sha256'] == sha(half_file) and
      diff['input_sha256'] == contract['input_sha256'], 'diff source SHA binding')
for name in ('exe', 'manual', 'dictionary'):
    check(sha(EXTERNAL[name]) == contract['source'][name + '_sha256'],
          'installed ' + name + ' SHA-256')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
mode_columns = [line.split(';')[2] for line in dictionary.splitlines()
                if line.startswith('MaterielOperationalModes;')]
check(mode_columns == ['MID', 'OPMID', 'RBID', 'NCID', 'USERT', 'NOTE'],
      'installed two-level USERT schema')

sources = {}
logs = {}
reports = {}
closures = {}
for arm, run in RUNS.items():
    source_file = CASE / f'{arm}-input.json'
    source = tables(native_json(source_file), 'model')
    sources[arm] = source
    check(sha(source_file) == contract['input_sha256'][arm], arm + ' frozen source SHA')
    changed = {name: {'before': parent.get(name), 'after': source.get(name)}
               for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
    check(changed == diff['from_parent'][arm] and
          set(changed) == {'ProblemDescription', 'MaterielOperationalModes'},
          arm + ' exact parent delta')
    for name in parent.keys() | source.keys():
        if name not in changed:
            check(parent.get(name) == source.get(name), arm + ' unchanged source table ' + name)
    check(source['Control'] == parent['Control'] and
          source['FailureMode'] == parent['FailureMode'] and
          source['OperationProfile'] == parent['OperationProfile'] and
          source['SystemRepair'] == parent['SystemRepair'] and
          source['MaterielStructure'] == parent['MaterielStructure'],
          arm + ' identical seed/physical failure/mission/CM configuration')
    modes = records(source['MaterielOperationalModes'])
    check([column['name'] for column in source['MaterielOperationalModes']['columns']] == mode_columns,
          arm + ' exact usage-rate columns')
    root = [r for r in modes if r['MID'] == 'TEACH-AIR-01' and r['OPMID'] == 'G09-SER-OPS']
    leaf = [r for r in modes if r['MID'] == 'POS-B' and r['OPMID'] == 'G09-B-USE']
    expected_leaf = 1 if arm == 'factorhalf' else 2
    check(len(root) == len(leaf) == 1 and root[0]['RBID'] == 'G09-SER-RBD' and
          near(root[0]['USERT'], .5) and near(leaf[0]['USERT'], expected_leaf) and
          near(root[0]['USERT'] * leaf[0]['USERT'], .5 if arm == 'factorhalf' else 1),
          arm + ' source-defined two-level product')
    check(any(r['MID'] == 'TEACH-AIR-01' and r['OPMID'] == 'G04-OPS' and r['USERT'] == 1
              for r in modes) and
          any(r['MID'] == 'POS-B' and r['OPMID'] == 'G04-OPS' and r['USERT'] == 1
              for r in modes), arm + ' PAR system and B leaf remain rate1')
    check(source['MissionOperationalModes'] == parent['MissionOperationalModes'] and
          source['RBDSeriesStructure'] == parent['RBDSeriesStructure'] and
          source['RBDParallelStructure'] == parent['RBDParallelStructure'],
          arm + ' mode selectors and RBD structures unchanged')

    invocation = native_json(run / 'invocation.json')
    closure = native_json(run / 'closure.json')
    closures[arm] = closure
    check(sha(run / 'invocation.json') == closure['invocation_sha256'],
          arm + ' invocation SHA seal')
    check(invocation['run_id'] == closure['run_id'] == run.name, arm + ' run identity')
    check(invocation['execution_mode'] == 'session0_ssh_cli' and invocation['session_id'] == 0 and
          'sshd.exe' in invocation['ssh_ancestor_names'], arm + ' SSH session0')
    check(invocation['gui']['pid'] == 13340 and invocation['gui']['session_id'] == 1 and
          invocation['queue_mutex'] == r'Global\SimloxIssue18NativeQueue',
          arm + ' GUI and mutex preserved')
    check(invocation['prelife_log_option_before'] == closure['prelife_log_option_after'] == 'NO',
          arm + ' registry restored')
    check(invocation['source_hashes_before'] == closure['source_hashes_before'] ==
          closure['source_hashes_after'], arm + ' source stable during native run')
    paths = {
        'input': source_file, 'parent': full_file, 'parent_closure': full_run / 'closure.json',
        'direct_half': half_file, 'direct_half_closure': half_run / 'closure.json',
        'contract': CASE / 'contract.json', 'exact_diff': CASE / 'exact-diff.json',
        'builder': CASE / 'build.py', 'diff_builder': CASE / 'describe_diff.py',
        'checker': CASE / 'check_roundtrip.py', 'runner': CASE / 'run_native_ssh.ps1',
        **EXTERNAL,
    }
    for name, path in paths.items():
        check(sha(path) == closure['source_hashes_before'][name], arm + ' frozen seal ' + name)
    check(len(closure['raw']) == 13, arm + ' 13 sealed raw files')
    for name, metadata in closure['raw'].items():
        path = run / name
        check(path.exists() and path.stat().st_size == metadata['bytes'] and
              sha(path) == metadata['sha256'], arm + ' raw bytes/SHA ' + name)
    check(sha(run / 'input.json') == sha(source_file), arm + ' native source copy')
    steps = native_json(run / 'steps.json')
    check([step['name'] for step in steps] ==
          ['import', 'export', 'calc', 'jsonreport', 'check_import_export'],
          arm + ' five native steps')
    for step in steps:
        check(step['exit_code'] == 0 and step['status'] == 'completed' and
              step['gui_preserved'], arm + ' guarded step ' + step['name'])
    check([step['arguments'] for step in steps[:4]] ==
          [command['args'] for command in invocation['planned_commands']],
          arm + ' planned CLI arguments')
    check(closure['conversion']['errors'] == closure['conversion']['notes'] == 0 and
          closure['conversion']['warning_codes'] == ['108'],
          arm + ' zero errors/reviewed warning')
    check(closure['native_outcome'] == 'zero_error_reviewed_warnings' and
          closure['sxo_bytes'] > 4 and closure['report_present'], arm + ' valid SXO/report')
    check(not re.search(r'\berror\s*#', (run / 'run.log').read_text(encoding='utf-8-sig'), re.I),
          arm + ' no converter error text')
    exported = tables(native_json(run / 'roundtrip-raw.json'), 'model')
    populated = [name for name, table in source.items() if rows(table)]
    check(len(populated) == 25, arm + ' 25 populated business tables')
    for name in populated:
        check(name in exported, arm + ' exported ' + name)
        if name in exported:
            check(source[name]['columns'] == exported[name]['columns'],
                  arm + ' exact native columns ' + name)
            check(source[name]['instances'] == exported[name]['instances'],
                  arm + ' exact native rows ' + name)
    logs[arm] = (run / 'model.log').read_text(encoding='utf-8-sig')
    reports[arm] = tables(native_json(run / 'report-raw.json'), 'report')

half_delta = {name: {'before': direct_half.get(name), 'after': sources['factorhalf'].get(name)}
              for name in direct_half.keys() | sources['factorhalf'].keys()
              if direct_half.get(name) != sources['factorhalf'].get(name)}
check(half_delta == diff['from_direct_half'] and
      set(half_delta) == {'ProblemDescription', 'MaterielOperationalModes'},
      'factorhalf exact direct-half contrast')
between = {name: {'before': sources['factorhalf'].get(name),
                  'after': sources['factorfull'].get(name)}
           for name in sources['factorhalf'].keys() | sources['factorfull'].keys()
           if sources['factorhalf'].get(name) != sources['factorfull'].get(name)}
check(between == diff['between_arms'] and
      set(between) == {'ProblemDescription', 'MaterielOperationalModes'},
      'pair differs only B leaf USERT and description')

controls = {'factorhalf': half_run, 'factorfull': full_run}
for arm, control_run in controls.items():
    check(sha(RUNS[arm] / 'model.log') == sha(control_run / 'model.log'),
          arm + ' byte-identical native model log to equal-product direct control')
    control_report = tables(native_json(control_run / 'report-raw.json'), 'report')
    check(set(reports[arm]) == set(control_report) ==
          {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'},
          arm + ' report table set')
    for name in ('ResultSummary', 'SystemResults', 'StockTotalResults'):
        check(reports[arm][name] == control_report[name],
              arm + ' equal non-description report table ' + name)

specs = {
    'factorhalf': {'events': ((9.8829, 'B', 'critical', 0),
                               (21.2333, 'B', 'noncritical', 1)),
                   'returns': (10, 22, 34), 'repairs': ((10, 10.5), (22, 22.5)),
                   'success': (False, True, True), 'mtmf': 1,
                   'markers': (20, 44), 'completions': (21, 45)},
    'factorfull': {'events': ((8.94145, 'B', 'critical', 0),
                               (21.2333, 'B', 'noncritical', 1),
                               (33.6494, 'B', 'critical', 2)),
                   'returns': (9.44145, 22, 34),
                   'repairs': ((9.44145, 9.94145), (22, 22.5), (34, 34.5)),
                   'success': (False, True, False), 'mtmf': .9069082736968994,
                   'markers': (18, 44, 68), 'completions': (19, 45, 69)},
}


def event(arm, hour, fragment):
    return any(line.startswith('Time: ' + str(hour) + ' ') and fragment in line
               for line in logs[arm].splitlines())


for arm, spec in specs.items():
    log = logs[arm]
    event_by_mission = {i: t for t, _, _, i in spec['events']}
    for i, (mission, order, launch) in enumerate((('BASIC-MISSION', 7, 8),
                                                   ('PAR-MISSION', 19, 20),
                                                   ('BASIC-MISSION', 31, 32))):
        identity = f'<{mission},TEACH-UNIT,0,0,{i}>'
        check(event(arm, order, 'mission ordered: ' + mission) and
              event(arm, order, identity + ' mission allocates system: <TEACH-AIR-01,0>') and
              event(arm, launch, identity + ' mission starting, duration: 2'),
              arm + f' mission {i} identity and launch')
        returned = spec['returns'][i]
        if spec['success'][i]:
            check(event(arm, returned, identity + ' mission success:') and
                  event(arm, returned, identity + ' mission completed:') and
                  identity + ' mission aborted:' not in log,
                  arm + f' mission {i} success')
        else:
            check(event(arm, event_by_mission[i], identity + ' mission aborted:') and
                  event(arm, returned, identity + ' aborted mission completed:') and
                  identity + ' mission success:' not in log,
                  arm + f' mission {i} abort and return')
    for time, position, severity, _ in spec['events']:
        prefix = f'Time: {time} <TEACH-AIR-01,0> {severity} CM failure mode added'
        block = log.split(prefix, 1)[1].split('Time:', 1)[0] if prefix in log else ''
        check(f'Failure Mode: FM-POS-{position} on materiel: <POS-{position},0>'
              in block, arm + f' timed B fault identity and severity {time}')
    check(log.count('CM failure mode added') == len(spec['events']) and
          'FM-POS-A' not in log, arm + ' exact B fault count and no A fault')
    for task_id, (begin, end) in enumerate(spec['repairs']):
        label = f'system CM task {task_id} on <TEACH-AIR-01,0>'
        check(event(arm, begin, label + ' started') and
              event(arm, begin, label + ' FMID: FM-POS-B') and
              event(arm, end, label + ' completed'),
              arm + f' system CM {task_id} half-hour B repair')
        check(event(arm, end, 'systems ready: 1'),
              arm + f' readiness after CM {task_id}')
    check('Item demand arrives' not in log, arm + ' no spare demand')

for arm, report in reports.items():
    spec = specs[arm]
    summary = records(report['ResultSummary'])[0]
    for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36),
                           ('MTMF', spec['mtmf']), ('STMF', spec['mtmf']),
                           ('MSTF', 1), ('MSUF', sum(spec['success']) / 3),
                           ('RSMTMF', 0), ('RSMSTF', 0), ('RSMSUF', 0), ('RSSTMF', 0)):
        check(near(summary[name], expected), arm + ' summary ' + name)
    system = records(report['SystemResults'])
    stock = records(report['StockTotalResults'])
    check(len(system) == len(stock) == 72, arm + ' 72 aligned System/Stock bins')
    reservations = ((7, 8), (19, 20), (31, 32))
    flights = ((8, spec['returns'][0]), (20, spec['returns'][1]),
               (32, spec['returns'][2]))
    for index, (entry, stock_entry) in enumerate(zip(system, stock)):
        start = index * .5
        end = start + .5
        check(entry['STINT'] == stock_entry['STINT'] == start and
              entry['ETINT'] == stock_entry['ETINT'] == end,
              arm + f' aligned half-hour interval {index}')
        reserved = sum(occupancy(a, b, start) for a, b in reservations)
        flight = sum(occupancy(a, b, start) for a, b in flights)
        repair = sum(occupancy(a, b, start) for a, b in spec['repairs'])
        expected = {
            'NSYRY': 1 - reserved - flight - repair, 'NSYMA': reserved + flight,
            'NSYMO': flight, 'NSYMR': reserved, 'NSYRP': repair, 'NSYUA': repair,
            'NSYA': 1 - repair, 'FTMO': flight, 'STACC': flight,
            'NFAIL': sum(start <= time < end for time, *_ in spec['events']),
            'NREPT': int(index in spec['completions']),
            'NSYDT': int(index in spec['markers']),
        }
        for name, value in expected.items():
            check(near(entry[name], value), arm + f' SystemResults {name} bin {index}')
        check((near(entry['SYDT'], .5) if index in spec['markers']
               else entry['SYDT'] is None), arm + f' downtime duration bin {index}')
        for name in ('NSYMC', 'NSYMP', 'NSYMT', 'NSYMS', 'NSYAL', 'NSYPM', 'NSYTP',
                     'NSYWR', 'NSYWI', 'NSYLA', 'NSYUH', 'NPMT', 'NDAM', 'NPMS',
                     'NROBT', 'NRCFG', 'STREQ', 'STF', 'STLOW', 'SYDTU', 'NSYSW',
                     'NPSTA', 'NPSUC'):
            check(entry[name] == 0, arm + f' zero SystemResults {name} bin {index}')
        check(stock_entry['PNB'] == 1 and
              all(value is None or value == 0 for name, value in stock_entry.items()
                  if name not in ('STINT', 'ETINT', 'PNB')),
              arm + f' no StockTotalResults movement bin {index}')
    check(near(system[-1]['NSYRY'], 1), arm + ' terminal aircraft ready')
    check(near(sum(entry['NSYMO'] for entry in system) * .5,
               sum(b - a for a, b in flights)), arm + ' operating hours integral')
    check(near(sum(entry['NSYRP'] for entry in system) * .5,
               .5 * len(spec['repairs'])), arm + ' system CM hours integral')

verdict = {
    'schema': 'simlox-g09-var05-independent-readonly/v1',
    'passed': not failures, 'checks_passed': checks - len(failures), 'checks_total': checks,
    'decision': ('GO: bounded equal-product event/report equivalence for two USERT pairs'
                 if not failures else 'NO-GO: independent replay failed'),
    'failures': failures, 'raw_seals': sum(len(c['raw']) for c in closures.values()),
    'runs': {arm: {'source_sha256': sha(CASE / f'{arm}-input.json'),
                   'closure_sha256': sha(run / 'closure.json'),
                   'model_log_sha256': sha(run / 'model.log'),
                   'report_sha256': sha(run / 'report-raw.json')}
             for arm, run in RUNS.items()},
    'observed': {
        'factorhalf': 'System0.5 × B1 equals direct System1 × B0.5: identical log and non-description reports.',
        'factorfull': 'System0.5 × B2 equals direct System1 × B1: identical log and non-description reports.',
        'terminal': 'One ready aircraft, half-hour direct B repairs, no stock movement.'},
    'limits': [
        'Two products (0.5 and 1) in one selected two-level BASIC series path, one aircraft, seed and replication.',
        'Selected USERT and multiplicative interpretation are source/manual/roundtrip-bound; native log does not print usage rates or accumulated operating hours.',
        'Equal logs and reports for this seed do not prove general stochastic coupling, deeper products, other RBDs, PM effects, GUI drawing, or cross-engine parity.'
    ],
}
OUT.write_bytes((json.dumps(verdict, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': verdict['passed'], 'checks_passed': verdict['checks_passed'],
                  'checks_total': checks, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
