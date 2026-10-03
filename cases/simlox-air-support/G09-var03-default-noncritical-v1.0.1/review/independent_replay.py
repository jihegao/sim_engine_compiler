"""Independent, read-only raw replay of the G09.var03 v1.0.1 pair."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
OUT = CASE / 'review' / 'independent-validation-2026-10-03.json'
RUNS = {arm: CASE / 'runs' / f'g09-var03-{arm}-v101-ssh-20261003-01'
        for arm in ('omitted-control', 'omitted-nc-b1')}
EXTERNAL = {
    'python': Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    'exe': Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
    'manual': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
    'dictionary': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path):
    text = path.read_text(encoding='utf-8-sig')
    clean = []
    quoted = escaped = False
    for i, character in enumerate(text):
        if quoted:
            clean.append(character)
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
            clean.append(character)
        elif character == ',':
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j == len(text) or text[j] not in '}]':
                clean.append(character)
        else:
            clean.append(character)
    return json.loads(''.join(clean))


def tables(document, root):
    return {table['name']: table for table in document[root]['tables']}


def rows(table):
    return [row for instance in table['instances'] for row in instance['rows']]


def records(table):
    names = [column['name'] for column in table['columns']]
    return [dict(zip(names, row)) for row in rows(table)]


def near(actual, expected, tolerance=.0007):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=tolerance)


def occupancy(a, b, start):
    return 2 * max(0, min(b, start + .5) - max(a, start))


checks = 0
failures = []


def check(condition, name):
    global checks
    checks += 1
    if not condition:
        failures.append(name)


contract = native_json(CASE / 'contract.json')
parent_dir = CASES / contract['accepted_parent']['package']
parent_file = parent_dir / 'mixed-input.json'
parent_run = parent_dir / 'runs' / 'g09-var01-mixed-v100-ssh-20261003-01'
series_dir = CASES / contract['series_control']['package']
series_file = series_dir / 'series-input.json'
series_run = series_dir / 'runs' / 'g04-series-v101-ssh-20261002-01'
diagnostic_dir = CASES / contract['excluded_diagnostic']['package']
diagnostic_file = diagnostic_dir / 'nc-b1-input.json'
diagnostic_run = diagnostic_dir / 'runs' / 'g09-var03-nc-b1-v100-ssh-20261003-01'
parent = tables(native_json(parent_file), 'model')
diff = native_json(CASE / 'exact-diff.json')
for path, expected, label in (
    (parent_file, contract['accepted_parent']['input_sha256'], 'accepted G09 parent source'),
    (parent_run / 'closure.json', contract['accepted_parent']['native_closure_sha256'],
     'accepted G09 parent closure'),
    (series_file, contract['series_control']['input_sha256'], 'accepted G04 series source'),
    (series_run / 'closure.json', contract['series_control']['native_closure_sha256'],
     'accepted G04 series closure'),
    (diagnostic_file, contract['excluded_diagnostic']['input_sha256'],
     'excluded v1.0.0 source'),
    (diagnostic_run / 'closure.json', contract['excluded_diagnostic']['native_closure_sha256'],
     'excluded v1.0.0 closure'),
    (CASE / 'exact-diff.json', contract['exact_diff_sha256'], 'frozen paired diff'),
):
    check(sha(path) == expected, label + ' SHA-256')
for key in ('exe', 'manual', 'dictionary'):
    check(sha(EXTERNAL[key]) == contract['source'][key + '_sha256'],
          'installed ' + key + ' SHA-256')

check(diff['parent_sha256'] == sha(parent_file) and
      diff['input_sha256'] == contract['input_sha256'], 'paired diff SHA binding')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
for name, fields in (
    ('RBDNonCriticalSet', ['NCID', 'DESCR', 'NOTE']),
    ('RBDNonCriticalSetItems', ['NCID', 'MID', 'QTYNC', 'USERT', 'NOTE']),
):
    installed = [line.split(';')[2] for line in dictionary.splitlines()
                 if line.startswith(name + ';')]
    check(installed == fields, 'installed dictionary schema ' + name)
diagnostic = tables(native_json(diagnostic_file), 'model')
diag_modes = records(diagnostic['MaterielOperationalModes'])
check(any(r['RBID'] == 'G09-SER-RBD' and r['NCID'] == 'G09-NC-B'
          for r in diag_modes), 'excluded diagnostic simultaneously bound RBID and NCID')
diag_log = (diagnostic_run / 'model.log').read_text(encoding='utf-8-sig')
check('Time: 8.62763 <TEACH-AIR-01,0> critical CM failure mode added' in diag_log and
      'Time: 8.62763 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:' in diag_log,
      'excluded diagnostic contradicts positive NC hypothesis')

sources = {}
logs = {}
reports = {}
closures = {}
for arm, run in RUNS.items():
    source_file = CASE / (arm + '-input.json')
    source = tables(native_json(source_file), 'model')
    sources[arm] = source
    check(sha(source_file) == contract['input_sha256'][arm], arm + ' frozen source SHA')
    actual = {name: {'before': parent.get(name), 'after': source.get(name)}
              for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
    expected_names = ({'ProblemDescription', 'RBDSeriesStructure'} if arm == 'omitted-control'
                      else {'ProblemDescription', 'MaterielOperationalModes',
                            'RBDNonCriticalSet', 'RBDNonCriticalSetItems', 'RBDSeriesStructure'})
    check(actual == diff['from_parent'][arm] and set(actual) == expected_names,
          arm + ' exact parent delta')
    for name in parent.keys() | source.keys():
        if name not in expected_names:
            check(parent.get(name) == source.get(name), arm + ' unchanged ' + name)
    edges = records(source['RBDSeriesStructure'])
    check(len(edges) == 1 and edges[0]['RBID'] == 'G09-SER-RBD' and
          edges[0]['SRBID'] == 'POS-A', arm + ' one-leaf series block omits B')
    check(source['MaterielStructure'] == parent['MaterielStructure'] and
          source['MaterielPosition'] == parent['MaterielPosition'] and
          source['FailureMode'] == parent['FailureMode'] and
          source['Control'] == parent['Control'],
          arm + ' physical B/fault/seed unchanged')
    if arm == 'omitted-control':
        check('RBDNonCriticalSet' not in source and 'RBDNonCriticalSetItems' not in source,
              'control has no noncritical set')
        check(records(source['MaterielOperationalModes']) ==
              records(parent['MaterielOperationalModes']), 'control has no NCID')
    else:
        check([c['name'] for c in source['RBDNonCriticalSet']['columns']] ==
              ['NCID', 'DESCR', 'NOTE'] and
              [c['name'] for c in source['RBDNonCriticalSetItems']['columns']] ==
              ['NCID', 'MID', 'QTYNC', 'USERT', 'NOTE'], 'NC authored dictionary columns')
        check(len(records(source['RBDNonCriticalSet'])) == 1 and
              records(source['RBDNonCriticalSet'])[0]['NCID'] == 'G09-NC-B',
              'one named noncritical set')
        check(records(source['RBDNonCriticalSetItems']) ==
              [dict(NCID='G09-NC-B', MID='POS-B', QTYNC=1, USERT=1.0, NOTE=None)],
              'only B QTYNC1 USERT1')
        modes = records(source['MaterielOperationalModes'])
        check(len(modes) == len(records(parent['MaterielOperationalModes'])) and
              any(r['MID'] == 'TEACH-AIR-01' and r['OPMID'] == 'G09-SER-OPS' and
                  r['RBID'] == 'G09-SER-RBD' and r['NCID'] == 'G09-NC-B' for r in modes),
              'B set linked to BASIC system mode')

    inv = native_json(run / 'invocation.json')
    closure = native_json(run / 'closure.json')
    closures[arm] = closure
    check(sha(run / 'invocation.json') == closure['invocation_sha256'],
          arm + ' invocation seal')
    check(inv['run_id'] == closure['run_id'] == run.name, arm + ' run identity')
    check(inv['execution_mode'] == 'session0_ssh_cli' and inv['session_id'] == 0 and
          'sshd.exe' in inv['ssh_ancestor_names'], arm + ' guarded SSH session0')
    check(inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1 and
          inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue', arm + ' GUI/mutex')
    check(inv['prelife_log_option_before'] == closure['prelife_log_option_after'] == 'NO',
          arm + ' registry restored')
    check(inv['source_hashes_before'] == closure['source_hashes_before'] ==
          closure['source_hashes_after'], arm + ' source stable during run')
    source_paths = {
        'input': source_file, 'parent': parent_file,
        'parent_closure': parent_run / 'closure.json',
        'series_control': series_file,
        'series_control_closure': series_run / 'closure.json',
        'diagnostic': diagnostic_file,
        'diagnostic_closure': diagnostic_run / 'closure.json',
        'contract': CASE / 'contract.json', 'exact_diff': CASE / 'exact-diff.json',
        'builder': CASE / 'build.py', 'diff_builder': CASE / 'describe_diff.py',
        'checker': CASE / 'check_roundtrip.py', 'runner': CASE / 'run_native_ssh.ps1',
        **EXTERNAL,
    }
    for name, path in source_paths.items():
        check(sha(path) == closure['source_hashes_before'][name], arm + ' source seal ' + name)
    check(len(closure['raw']) == 13, arm + ' 13 raw seals')
    for name, metadata in closure['raw'].items():
        path = run / name
        check(path.exists() and path.stat().st_size == metadata['bytes'] and
              sha(path) == metadata['sha256'], arm + ' raw bytes/SHA ' + name)
    check(sha(run / 'input.json') == sha(source_file), arm + ' run input equals source')
    steps = native_json(run / 'steps.json')
    check([s['name'] for s in steps] ==
          ['import', 'export', 'calc', 'jsonreport', 'check_import_export'],
          arm + ' five native steps')
    for step in steps:
        check(step['exit_code'] == 0 and step['status'] == 'completed' and
              step['gui_preserved'], arm + ' guarded ' + step['name'])
    check([s['arguments'] for s in steps[:4]] ==
          [s['args'] for s in inv['planned_commands']], arm + ' executed CLI args')
    check(closure['conversion']['errors'] == closure['conversion']['notes'] == 0 and
          closure['conversion']['warning_codes'] == ['108'], arm + ' converter diagnostics')
    check(closure['sxo_bytes'] > 4 and closure['report_present'] and
          closure['native_outcome'] == 'zero_error_reviewed_warnings', arm + ' valid result')
    check(not re.search(r'\berror\s*#', (run / 'run.log').read_text(encoding='utf-8-sig'), re.I),
          arm + ' no converter error text')
    exported = tables(native_json(run / 'roundtrip-raw.json'), 'model')
    populated = [name for name, table in source.items() if rows(table)]
    check(len(populated) == (25 if arm == 'omitted-control' else 27),
          arm + ' populated table count')
    for name in populated:
        check(name in exported, arm + ' exported ' + name)
        if name in exported:
            check(source[name]['columns'] == exported[name]['columns'],
                  arm + ' exact exported columns ' + name)
            check(source[name]['instances'] == exported[name]['instances'],
                  arm + ' exact exported rows ' + name)
    logs[arm] = (run / 'model.log').read_text(encoding='utf-8-sig')
    reports[arm] = tables(native_json(run / 'report-raw.json'), 'report')

actual_pair = {name: {'before': sources['omitted-control'].get(name),
                      'after': sources['omitted-nc-b1'].get(name)}
               for name in sources['omitted-control'].keys() | sources['omitted-nc-b1'].keys()
               if sources['omitted-control'].get(name) != sources['omitted-nc-b1'].get(name)}
check(actual_pair == diff['between_arms'] and set(actual_pair) ==
      {'ProblemDescription', 'MaterielOperationalModes',
       'RBDNonCriticalSet', 'RBDNonCriticalSetItems'}, 'exact within-pair NCID contrast')
for name in sources['omitted-control'].keys() | sources['omitted-nc-b1'].keys():
    if name not in actual_pair:
        check(sources['omitted-control'].get(name) == sources['omitted-nc-b1'].get(name),
              'identical within-pair table ' + name)
check(logs['omitted-control'] == (parent_run / 'model.log').read_text(encoding='utf-8-sig'),
      'omitted control event log byte-identical to accepted parent')


def event(arm, hour, fragment):
    return any(line.startswith('Time: ' + str(hour) + ' ') and fragment in line
               for line in logs[arm].splitlines())


specs = {
    'omitted-control': ((8.62763, 9.12763, 9.62763, True, 'B'),
                        (20.8222, 22, 22.5, False, 'B'),
                        (33.0996, 33.5996, 34.0996, True, 'A')),
    'omitted-nc-b1': ((8.62763, 10, 10.5, False, 'B'),
                      (20.8222, 22, 22.5, False, 'B'),
                      (33.0996, 33.5996, 34.0996, True, 'A')),
}
for arm in RUNS:
    log = logs[arm]
    for i, (failure, returned, repaired, critical, position) in enumerate(specs[arm]):
        mission = ('PAR-MISSION' if i == 1 else 'BASIC-MISSION')
        order = (7, 19, 31)[i]
        launch = (8, 20, 32)[i]
        identity = f'<{mission},TEACH-UNIT,0,0,{i}>'
        check(event(arm, order, 'mission ordered: ' + mission) and
              event(arm, order, identity + ' mission allocates system: <TEACH-AIR-01,0>') and
              event(arm, launch, identity + ' mission starting, duration: 2'),
              f'{arm} mission {i} identity and launch')
        severity = 'critical' if critical else 'noncritical'
        prefix = f'Time: {failure} <TEACH-AIR-01,0> {severity} CM failure mode added'
        block = log.split(prefix, 1)[1].split('Time:', 1)[0] if prefix in log else ''
        check(f'Failure Mode: FM-POS-{position} on materiel: <POS-{position},0>'
              in block, f'{arm} timed failure {i} position and severity')
        if critical:
            check(event(arm, failure, identity + ' mission aborted:') and
                  event(arm, returned, identity + ' aborted mission completed:') and
                  identity + ' mission success:' not in log,
                  f'{arm} mission {i} abort and return')
        else:
            check(event(arm, returned, identity + ' mission success:') and
                  event(arm, returned, identity + ' mission completed:') and
                  identity + ' mission aborted:' not in log,
                  f'{arm} mission {i} success and return')
        cm = f'system CM task {i} on <TEACH-AIR-01,0>'
        check(event(arm, returned, cm + ' started') and
              event(arm, returned, cm + ' FMID: FM-POS-' + position) and
              event(arm, repaired, cm + ' completed'), f'{arm} CM task {i} same fault')
        task_class = 'NC' if arm == 'omitted-nc-b1' and not critical else 'C'
        check(f'< {cm}, {task_class}, 0.5>' in log and
              event(arm, repaired, 'systems ready: 1'),
              f'{arm} CM task {i} half-hour and readiness')
    check(log.count('CM failure mode added') == 3, arm + ' three individual faults')
    check('Item demand arrives' not in log, arm + ' no stock demand')

for arm, report in reports.items():
    check(set(report) == {'ProblemDescription', 'ResultSummary',
                          'SystemResults', 'StockTotalResults'}, arm + ' report tables')
    summary = records(report['ResultSummary'])[0]
    expected_factor = (.7878668308258057 if arm == 'omitted-control'
                       else .9332613348960876)
    for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36),
                           ('MTMF', expected_factor), ('STMF', expected_factor),
                           ('MSTF', 1), ('MSUF', 1 / 3 if arm == 'omitted-control' else 2 / 3),
                           ('RSMTMF', 0), ('RSMSTF', 0), ('RSMSUF', 0), ('RSSTMF', 0)):
        check(near(summary[name], expected), arm + ' summary ' + name)
    system = records(report['SystemResults'])
    stock = records(report['StockTotalResults'])
    check(len(system) == len(stock) == 72, arm + ' 72 System/Stock bins')
    periods = specs[arm]
    reservations = ((7, 8), (19, 20), (31, 32))
    flights = tuple(((8, periods[0][1]), (20, periods[1][1]), (32, periods[2][1])))
    repairs = tuple((item[1], item[2]) for item in periods)
    failures_at = tuple(item[0] for item in periods)
    downtime_bins = (18, 44, 67) if arm == 'omitted-control' else (20, 44, 67)
    completed_bins = (19, 45, 68) if arm == 'omitted-control' else (21, 45, 68)
    for i, (entry, stock_entry) in enumerate(zip(system, stock)):
        start = i * .5
        end = start + .5
        check(entry['STINT'] == stock_entry['STINT'] == start and
              entry['ETINT'] == stock_entry['ETINT'] == end, arm + f' bin {i} alignment')
        reserved = sum(occupancy(a, b, start) for a, b in reservations)
        flight = sum(occupancy(a, b, start) for a, b in flights)
        repair = sum(occupancy(a, b, start) for a, b in repairs)
        expected = {
            'NSYRY': 1 - reserved - flight - repair, 'NSYMA': reserved + flight,
            'NSYMO': flight, 'NSYMR': reserved, 'NSYRP': repair, 'NSYUA': repair,
            'NSYA': 1 - repair, 'FTMO': flight, 'STACC': flight,
            'NFAIL': sum(start <= t < end for t in failures_at),
            'NREPT': int(i in completed_bins), 'NSYDT': int(i in downtime_bins),
        }
        for name, value in expected.items():
            check(near(entry[name], value), arm + f' SystemResults {name} bin {i}')
        check((near(entry['SYDT'], .5) if i in downtime_bins else entry['SYDT'] is None),
              arm + f' half-hour downtime duration bin {i}')
        for name in ('NSYMC', 'NSYMP', 'NSYMT', 'NSYMS', 'NSYAL', 'NSYPM', 'NSYTP',
                     'NSYWR', 'NSYWI', 'NSYLA', 'NSYUH', 'NPMT', 'NDAM', 'NPMS',
                     'NROBT', 'NRCFG', 'STREQ', 'STF', 'STLOW', 'SYDTU', 'NSYSW',
                     'NPSTA', 'NPSUC'):
            check(entry[name] == 0, arm + f' zero SystemResults {name} bin {i}')
        check(stock_entry['PNB'] == 1 and
              all(value is None or value == 0 for name, value in stock_entry.items()
                  if name not in ('STINT', 'ETINT', 'PNB')),
              arm + f' no stock movement bin {i}')
    check(near(system[-1]['NSYRY'], 1), arm + ' terminal ready one')
    check(near(sum(entry['NSYMO'] for entry in system) * .5,
               sum(b - a for a, b in flights)), arm + ' flight hours integral')
    check(near(sum(entry['NSYRP'] for entry in system) * .5, 1.5),
          arm + ' three half-hour system repairs')

verdict = {
    'schema': 'simlox-g09-var03-v101-independent-readonly/v1',
    'passed': not failures, 'checks_passed': checks - len(failures), 'checks_total': checks,
    'decision': ('GO: bounded one-member noncritical set effect in omitted-position BASIC mode'
                 if not failures else 'NO-GO: independent replay failed'),
    'failures': failures, 'raw_seals': sum(len(c['raw']) for c in closures.values()),
    'runs': {arm: {'source_sha256': sha(CASE / (arm + '-input.json')),
                   'closure_sha256': sha(run / 'closure.json'),
                   'model_log_sha256': sha(run / 'model.log'),
                   'report_sha256': sha(run / 'report-raw.json')}
             for arm, run in RUNS.items()},
    'observed': {
        'control': 'POS-B h8.62763 critical; BASIC abort; PAR h20 success; BASIC h32 A abort.',
        'nc_b1': 'Same B h8.62763 noncritical; BASIC succeeds h10; PAR h20 success; BASIC h32 A abort.',
        'terminal': 'Three half-hour system CM tasks, ready1, no stock movement in each arm.',
        'excluded_v100': 'RBID+NCID simultaneous binding retained critical B and abort; excluded.'},
    'limits': [
        'Only POS-B QTYNC1 USERT1 in one BASIC system mode is tested; QTYNC>1 and overlap are open.',
        'Native log does not print selected NCID; attribution uses isolated source pair and matched fault/outcome.',
        'The control PAR fault is logged noncritical while its later CM priority row says C; CM task class is not used as the in-flight severity measure.',
        'One aircraft, one seed/replication, three missions; no population, GUI drawing, or cross-engine claim.'
    ],
}
OUT.write_bytes((json.dumps(verdict, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': verdict['passed'], 'checks_passed': verdict['checks_passed'],
                  'checks_total': checks, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
