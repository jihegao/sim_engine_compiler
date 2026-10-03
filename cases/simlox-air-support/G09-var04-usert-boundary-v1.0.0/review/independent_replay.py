"""Independent read-only replay of four sealed G09.var04 USERT runs."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
OUT = CASE / 'review' / 'independent-validation-2026-10-03.json'
ARMS = ('use0', 'use05', 'use1', 'use2')
RUNS = {arm: CASE / 'runs' / f'g09-var04-{arm}-v100-ssh-20261003-01' for arm in ARMS}
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
    out = []
    quoted = escaped = False
    for i, char in enumerate(data):
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
            j = i + 1
            while j < len(data) and data[j].isspace():
                j += 1
            if j == len(data) or data[j] not in '}]':
                out.append(char)
        else:
            out.append(char)
    return json.loads(''.join(out))


def tables(document, root):
    return {table['name']: table for table in document[root]['tables']}


def rows(table):
    return [row for instance in table['instances'] for row in instance['rows']]


def records(table):
    names = [column['name'] for column in table['columns']]
    return [dict(zip(names, row)) for row in rows(table)]


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
parent_dir = CASES / contract['accepted_parent']['package']
parent_file = parent_dir / 'mixed-input.json'
parent_run = parent_dir / 'runs' / 'g09-var01-mixed-v100-ssh-20261003-01'
parent = tables(native_json(parent_file), 'model')
diff = native_json(CASE / 'exact-diff.json')
check(sha(parent_file) == contract['accepted_parent']['input_sha256'], 'accepted parent source SHA')
check(sha(parent_run / 'closure.json') ==
      contract['accepted_parent']['native_closure_sha256'], 'accepted parent closure SHA')
check(sha(CASE / 'exact-diff.json') == contract['exact_diff_sha256'], 'frozen exact diff SHA')
check(diff['parent_sha256'] == sha(parent_file) and
      diff['input_sha256'] == contract['input_sha256'], 'diff parent/arm source binding')
for name in ('exe', 'manual', 'dictionary'):
    check(sha(EXTERNAL[name]) == contract['source'][name + '_sha256'],
          'installed ' + name + ' SHA')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
fields = [line.split(';')[2] for line in dictionary.splitlines()
          if line.startswith('MaterielOperationalModes;')]
check(fields == ['MID', 'OPMID', 'RBID', 'NCID', 'USERT', 'NOTE'],
      'installed MaterielOperationalModes USERT schema')

sources = {}
logs = {}
reports = {}
closures = {}
rates = {'use0': 0, 'use05': .5, 'use1': 1, 'use2': 2}
for arm, run in RUNS.items():
    source_file = CASE / f'{arm}-input.json'
    source = tables(native_json(source_file), 'model')
    sources[arm] = source
    check(sha(source_file) == contract['input_sha256'][arm], arm + ' frozen source SHA')
    delta = {name: {'before': parent.get(name), 'after': source.get(name)}
             for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
    changed_names = {'ProblemDescription', 'OperationalModes',
                     'MaterielOperationalModes', 'RBDSeriesStructure'}
    check(delta == diff['from_parent'][arm] and set(delta) == changed_names,
          arm + ' exact four-table parent delta')
    for name in parent.keys() | source.keys():
        if name not in changed_names:
            check(parent.get(name) == source.get(name), arm + ' fixed source table ' + name)
    check(source['Control'] == parent['Control'] and source['OperationProfile'] == parent['OperationProfile']
          and source['FailureMode'] == parent['FailureMode'] and source['SystemRepair'] == parent['SystemRepair'],
          arm + ' common seed/schedule/fault/CM')
    modes = records(source['MaterielOperationalModes'])
    check([column['name'] for column in source['MaterielOperationalModes']['columns']] == fields,
          arm + ' authored usage schema')
    selected = [r for r in modes if r['MID'] == 'POS-B' and r['OPMID'] == 'G09-B-USE']
    check(len(selected) == 1 and near(selected[0]['USERT'], rates[arm]) and
          selected[0]['RBID'] is None and selected[0]['NCID'] is None,
          arm + ' sole variable selected B relative rate')
    check(any(r['MID'] == 'POS-B' and r['OPMID'] == 'G04-OPS' and r['USERT'] == 1
              for r in modes), arm + ' PAR B retains G04-OPS rate1')
    check({r['OPMID'] for r in records(source['OperationalModes'])} ==
          {'G04-OPS', 'G09-SER-OPS', 'G09-B-USE'}, arm + ' added B mode definition')
    edges = records(source['RBDSeriesStructure'])
    check({(r['SRBID'], r['OPMID']) for r in edges} ==
          {('POS-A', 'G04-OPS'), ('POS-B', 'G09-B-USE')},
          arm + ' selected B usage only in BASIC series block')
    check(source['MissionOperationalModes'] == parent['MissionOperationalModes'] and
          source['RBDParallel'] == parent['RBDParallel'] and
          source['RBDParallelStructure'] == parent['RBDParallelStructure'],
          arm + ' mission mapping and PAR parallel block unchanged')

    invocation = native_json(run / 'invocation.json')
    closure = native_json(run / 'closure.json')
    closures[arm] = closure
    check(sha(run / 'invocation.json') == closure['invocation_sha256'],
          arm + ' invocation SHA seal')
    check(invocation['run_id'] == closure['run_id'] == run.name, arm + ' run identity')
    check(invocation['execution_mode'] == 'session0_ssh_cli' and
          invocation['session_id'] == 0 and 'sshd.exe' in invocation['ssh_ancestor_names'],
          arm + ' session0 SSH execution')
    check(invocation['gui']['pid'] == 13340 and invocation['gui']['session_id'] == 1 and
          invocation['queue_mutex'] == r'Global\SimloxIssue18NativeQueue',
          arm + ' GUI and queue identity')
    check(invocation['prelife_log_option_before'] == closure['prelife_log_option_after'] == 'NO',
          arm + ' registry option restoration')
    check(invocation['source_hashes_before'] == closure['source_hashes_before'] ==
          closure['source_hashes_after'], arm + ' source before/after stable')
    source_paths = {
        'input': source_file, 'parent': parent_file,
        'parent_closure': parent_run / 'closure.json',
        'contract': CASE / 'contract.json', 'exact_diff': CASE / 'exact-diff.json',
        'builder': CASE / 'build.py', 'diff_builder': CASE / 'describe_diff.py',
        'checker': CASE / 'check_roundtrip.py', 'runner': CASE / 'run_native_ssh.ps1',
        **EXTERNAL,
    }
    for name, path in source_paths.items():
        check(sha(path) == closure['source_hashes_before'][name], arm + ' frozen seal ' + name)
    check(len(closure['raw']) == 13, arm + ' 13 raw SHA seals')
    for name, metadata in closure['raw'].items():
        path = run / name
        check(path.exists() and path.stat().st_size == metadata['bytes'] and
              sha(path) == metadata['sha256'], arm + ' raw bytes/SHA ' + name)
    check(sha(run / 'input.json') == sha(source_file), arm + ' native input exact source copy')
    steps = native_json(run / 'steps.json')
    check([step['name'] for step in steps] ==
          ['import', 'export', 'calc', 'jsonreport', 'check_import_export'],
          arm + ' five native steps')
    for step in steps:
        check(step['exit_code'] == 0 and step['status'] == 'completed' and step['gui_preserved'],
              arm + ' guarded step ' + step['name'])
    check([step['arguments'] for step in steps[:4]] ==
          [command['args'] for command in invocation['planned_commands']],
          arm + ' CLI command binding')
    check(closure['conversion']['errors'] == closure['conversion']['notes'] == 0 and
          closure['conversion']['warning_codes'] == ['108'],
          arm + ' zero errors and reviewed warning')
    check(closure['native_outcome'] == 'zero_error_reviewed_warnings' and
          closure['sxo_bytes'] > 4 and closure['report_present'], arm + ' valid outputs')
    check(not re.search(r'\berror\s*#', (run / 'run.log').read_text(encoding='utf-8-sig'), re.I),
          arm + ' no converter error text')
    exported = tables(native_json(run / 'roundtrip-raw.json'), 'model')
    populated = [name for name, table in source.items() if rows(table)]
    check(len(populated) == 25, arm + ' 25 populated business tables')
    for name in populated:
        check(name in exported, arm + ' exported ' + name)
        if name in exported:
            check(source[name]['columns'] == exported[name]['columns'],
                  arm + ' exact columns ' + name)
            check(source[name]['instances'] == exported[name]['instances'],
                  arm + ' exact rows ' + name)
    logs[arm] = (run / 'model.log').read_text(encoding='utf-8-sig')
    reports[arm] = tables(native_json(run / 'report-raw.json'), 'report')

check(sha(RUNS['use1'] / 'model.log') == sha(parent_run / 'model.log'),
      'use1 event log byte-identical to accepted full-rate parent')
parent_report = tables(native_json(parent_run / 'report-raw.json'), 'report')
for name in ('ResultSummary', 'SystemResults', 'StockTotalResults'):
    check(reports['use1'][name] == parent_report[name],
          'use1 equals parent business report table ' + name)
for arm in ('use0', 'use05', 'use2'):
    changed = {name: {'before': sources['use1'].get(name), 'after': sources[arm].get(name)}
               for name in sources['use1'].keys() | sources[arm].keys()
               if sources['use1'].get(name) != sources[arm].get(name)}
    check(changed == diff['from_use1'][arm] and
          set(changed) == {'ProblemDescription', 'MaterielOperationalModes'},
          arm + ' pairwise rate-only business delta from use1')

specs = {
    'use0': {'events': ((9.8829, 'A', 'critical', 0),),
             'returns': (10, 22, 34), 'repairs': ((10, 10.5),),
             'success': (False, True, True), 'mtmf': 1,
             'markers': (20,), 'completions': (21,)},
    'use05': {'events': ((8.94145, 'A', 'critical', 0),
                         (20.8222, 'B', 'noncritical', 1),
                         (33.6494, 'A', 'critical', 2)),
              'returns': (9.44145, 22, 34),
              'repairs': ((9.44145, 9.94145), (22, 22.5), (34, 34.5)),
              'success': (False, True, False), 'mtmf': .9069082736968994,
              'markers': (18, 44, 68), 'completions': (19, 45, 69)},
    'use1': {'events': ((8.62763, 'B', 'critical', 0),
                        (20.8222, 'B', 'noncritical', 1),
                        (33.0996, 'A', 'critical', 2)),
             'returns': (9.12763, 22, 33.5996),
             'repairs': ((9.12763, 9.62763), (22, 22.5), (33.5996, 34.0996)),
             'success': (False, True, False), 'mtmf': .7878668308258057,
             'markers': (18, 44, 67), 'completions': (19, 45, 68)},
    'use2': {'events': ((8.37658, 'B', 'critical', 0),
                        (20.8222, 'B', 'noncritical', 1),
                        (32.6597, 'A', 'critical', 2)),
             'returns': (8.75316, 22, 33.1597),
             'repairs': ((8.75316, 9.25316), (22, 22.5), (33.1597, 33.6597)),
             'success': (False, True, False), 'mtmf': .6521500945091248,
             'markers': (17, 44, 66), 'completions': (18, 45, 67)},
}


def event(arm, hour, fragment):
    return any(line.startswith('Time: ' + str(hour) + ' ') and fragment in line
               for line in logs[arm].splitlines())


for arm, spec in specs.items():
    log = logs[arm]
    event_by_mission = {index: (time, pos, severity)
                        for time, pos, severity, index in spec['events']}
    for i, (mission, ordered, launched) in enumerate((('BASIC-MISSION', 7, 8),
                                                       ('PAR-MISSION', 19, 20),
                                                       ('BASIC-MISSION', 31, 32))):
        identity = f'<{mission},TEACH-UNIT,0,0,{i}>'
        check(event(arm, ordered, 'mission ordered: ' + mission) and
              event(arm, ordered, identity + ' mission allocates system: <TEACH-AIR-01,0>') and
              event(arm, launched, identity + ' mission starting, duration: 2'),
              arm + f' mission {i} order/aircraft/launch')
        returned = spec['returns'][i]
        if spec['success'][i]:
            check(event(arm, returned, identity + ' mission success:') and
                  event(arm, returned, identity + ' mission completed:') and
                  identity + ' mission aborted:' not in log,
                  arm + f' mission {i} success')
        else:
            failure_at = event_by_mission[i][0]
            check(event(arm, failure_at, identity + ' mission aborted:') and
                  event(arm, returned, identity + ' aborted mission completed:') and
                  identity + ' mission success:' not in log,
                  arm + f' mission {i} abort and return')
    for time, pos, severity, index in spec['events']:
        prefix = f'Time: {time} <TEACH-AIR-01,0> {severity} CM failure mode added'
        block = log.split(prefix, 1)[1].split('Time:', 1)[0] if prefix in log else ''
        check(f'Failure Mode: FM-POS-{pos} on materiel: <POS-{pos},0>' in block,
              arm + f' fault {time} identity/severity')
    check(log.count('CM failure mode added') == len(spec['events']),
          arm + ' exact fault-event count')
    for task_id, (begin, end) in enumerate(spec['repairs']):
        label = f'system CM task {task_id} on <TEACH-AIR-01,0>'
        pos = spec['events'][task_id][1]
        check(event(arm, begin, label + ' started') and
              event(arm, begin, label + ' FMID: FM-POS-' + pos) and
              event(arm, end, label + ' completed'),
              arm + f' half-hour CM task {task_id}')
        check(event(arm, end, 'systems ready: 1'),
              arm + f' post-CM ready task {task_id}')
    check('Item demand arrives' not in log, arm + ' no spare demand')
    if arm == 'use0':
        check('FM-POS-B' not in log and
              all(not (8 <= float(line.split()[1]) < 10 or 32 <= float(line.split()[1]) < 34)
                      for line in log.splitlines() if line.startswith('Time:') and
                      'FM-POS-B' in line), 'use0 no BASIC B failure')

for arm, report in reports.items():
    spec = specs[arm]
    check(set(report) == {'ProblemDescription', 'ResultSummary',
                          'SystemResults', 'StockTotalResults'}, arm + ' report table set')
    summary = records(report['ResultSummary'])[0]
    for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36),
                           ('MTMF', spec['mtmf']), ('STMF', spec['mtmf']),
                           ('MSTF', 1), ('MSUF', sum(spec['success']) / 3),
                           ('RSMTMF', 0), ('RSMSTF', 0), ('RSMSUF', 0), ('RSSTMF', 0)):
        check(near(summary[name], expected), arm + ' summary ' + name)
    system = records(report['SystemResults'])
    stock = records(report['StockTotalResults'])
    check(len(system) == len(stock) == 72, arm + ' 72 System/Stock bins')
    reservations = ((7, 8), (19, 20), (31, 32))
    flights = ((8, spec['returns'][0]), (20, spec['returns'][1]),
               (32, spec['returns'][2]))
    for index, (entry, stock_entry) in enumerate(zip(system, stock)):
        start = index * .5
        end = start + .5
        check(entry['STINT'] == stock_entry['STINT'] == start and
              entry['ETINT'] == stock_entry['ETINT'] == end,
              arm + f' aligned half-hour bin {index}')
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
              arm + f' no stock movement bin {index}')
    check(near(system[-1]['NSYRY'], 1), arm + ' terminal ready aircraft')
    check(near(sum(row['NSYMO'] for row in system) * .5,
               sum(b - a for a, b in flights)), arm + ' integrated operating hours')
    check(near(sum(row['NSYRP'] for row in system) * .5,
               .5 * len(spec['repairs'])), arm + ' integrated CM hours')

verdict = {
    'schema': 'simlox-g09-var04-independent-readonly/v1',
    'passed': not failures, 'checks_passed': checks - len(failures), 'checks_total': checks,
    'decision': ('GO RESTRICTED: frozen four-arm source acceptance and observed zero-versus-nonzero BASIC B boundary'
                 if not failures else 'NO-GO: independent raw replay failed'),
    'failures': failures, 'raw_seals': sum(len(c['raw']) for c in closures.values()),
    'runs': {arm: {'source_sha256': sha(CASE / f'{arm}-input.json'),
                   'closure_sha256': sha(run / 'closure.json'),
                   'model_log_sha256': sha(run / 'model.log'),
                   'report_sha256': sha(run / 'report-raw.json')}
             for arm, run in RUNS.items()},
    'observed': {
        'use0': 'No BASIC B fault; A critical h9.8829; PAR and final BASIC succeed.',
        'use05': 'A critical h8.94145 and h33.6494; no BASIC B fault observed; PAR B noncritical h20.8222.',
        'use1': 'Byte-identical accepted parent log and equal business reports.',
        'use2': 'B critical h8.37658; PAR B noncritical h20.8222; A critical h32.6597.',
        'terminal': 'Every arm ready1 and no stock movement at h36.'},
    'limits': [
        'Selected B USERT is source/roundtrip-bound; native event log does not print the selected rate.',
        'The zero arm still has an A fault in the first BASIC mission; its no-B claim is not a no-failure claim.',
        'The USERT0.5 arm has no observed BASIC B fault: competing A failures abort both BASIC missions. This does not establish a positive fractional B exposure effect. A targeted model or seed panel with B exposure before competing A failure is needed for that claim.',
        'Across changed rates, event times and identities are empirical for one seed; no common draw, monotonic timing law, population reliability or PM effect is established.',
        'Only one BASIC POS-B series block and four rates; PAR remains at rate1. No GUI drawing or cross-engine claim.'
    ],
}
OUT.write_bytes((json.dumps(verdict, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': verdict['passed'], 'checks_passed': verdict['checks_passed'],
                  'checks_total': checks, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
