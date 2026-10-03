"""Independent read-only replay of sealed G09.var03 QTYNC1/2 evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
OUT = CASE / 'review' / 'verdict.json'
RUNS = {arm: CASE / 'runs' / f'g09-var03-{arm}-v103-ssh-20261003-01'
        for arm in ('qty1', 'qty2')}
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
    result = []
    quoted = escaped = False
    for i, char in enumerate(text):
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            result.append(char)
        elif char == ',':
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j == len(text) or text[j] not in '}]':
                result.append(char)
        else:
            result.append(char)
    return json.loads(''.join(result))


def tables(document, root):
    return {table['name']: table for table in document[root]['tables']}


def rows(table):
    return [row for instance in table['instances'] for row in instance['rows']]


def records(table):
    fields = [column['name'] for column in table['columns']]
    return [dict(zip(fields, row)) for row in rows(table)]


def near(actual, expected, tolerance=.0007):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=tolerance)


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
parent_file = parent_dir / 'omitted-nc-b1-input.json'
parent_run = parent_dir / 'runs' / 'g09-var03-omitted-nc-b1-v101-ssh-20261003-01'
control_file = parent_dir / 'omitted-control-input.json'
control_run = parent_dir / 'runs' / 'g09-var03-omitted-control-v101-ssh-20261003-01'
diagnostic_dir = CASES / contract['excluded_diagnostic']['package']
diagnostic_files = {arm: diagnostic_dir / f'{arm}-input.json' for arm in RUNS}
diagnostic_runs = {arm: diagnostic_dir / 'runs' /
                   f'g09-var03-{arm}-v102-ssh-20261003-01' for arm in RUNS}
parent = tables(native_json(parent_file), 'model')
diff = native_json(CASE / 'exact-diff.json')
for path, expected, label in (
    (parent_file, contract['accepted_parent']['input_sha256'], 'accepted QTYNC1 parent source'),
    (parent_run / 'closure.json', contract['accepted_parent']['native_closure_sha256'],
     'accepted QTYNC1 parent closure'),
    (control_file, contract['accepted_control']['input_sha256'],
     'accepted no-NCID control source'),
    (control_run / 'closure.json', contract['accepted_control']['native_closure_sha256'],
     'accepted no-NCID control closure'),
    (CASE / 'exact-diff.json', contract['exact_diff_sha256'], 'frozen paired diff'),
):
    check(sha(path) == expected, label + ' SHA-256')
for arm in RUNS:
    check(sha(diagnostic_files[arm]) ==
          contract['excluded_diagnostic']['input_sha256'][arm],
          arm + ' excluded v1.0.2 source SHA')
    check(sha(diagnostic_runs[arm] / 'closure.json') ==
          contract['excluded_diagnostic']['native_closure_sha256'][arm],
          arm + ' excluded v1.0.2 closure SHA')
for key in ('exe', 'manual', 'dictionary'):
    check(sha(EXTERNAL[key]) == contract['source'][key + '_sha256'],
          'installed ' + key + ' SHA-256')
check(diff['parent_sha256'] == sha(parent_file) and
      diff['input_sha256'] == contract['input_sha256'], 'exact diff source pins')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
fields = [line.split(';')[2] for line in dictionary.splitlines()
          if line.startswith('RBDNonCriticalSetItems;')]
check(fields == ['NCID', 'MID', 'QTYNC', 'USERT', 'NOTE'], 'installed QTYNC schema')
for arm in RUNS:
    diagnostic = tables(native_json(diagnostic_files[arm]), 'model')
    check(records(diagnostic['OperationProfile'])[1]['SPRID'] == 'PAR-MISSION',
          arm + ' excluded diagnostic h20 used PAR instead of NCID BASIC mode')
    dlog = (diagnostic_runs[arm] / 'model.log').read_text(encoding='utf-8-sig')
    check('Time: 21.742 <PAR-MISSION,TEACH-UNIT,0,0,1> mission aborted:' in dlog,
          arm + ' excluded diagnostic h20 PAR abort')
check(sha(diagnostic_runs['qty1'] / 'model.log') ==
      sha(diagnostic_runs['qty2'] / 'model.log'),
      'excluded diagnostic QTYNC arms have identical native event logs')

sources = {}
logs = {}
reports = {}
closures = {}
for arm, run in RUNS.items():
    source_file = CASE / f'{arm}-input.json'
    source = tables(native_json(source_file), 'model')
    sources[arm] = source
    check(sha(source_file) == contract['input_sha256'][arm], arm + ' source SHA')
    actual = {name: {'before': parent.get(name), 'after': source.get(name)}
              for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
    expected_names = ({'ProblemDescription', 'OperationProfile', 'MaterielStructure'}
                      if arm == 'qty1' else
                      {'ProblemDescription', 'OperationProfile', 'MaterielStructure',
                       'RBDNonCriticalSetItems'})
    check(actual == diff['from_parent'][arm] and set(actual) == expected_names,
          arm + ' exact parent source delta')
    for name in parent.keys() | source.keys():
        if name not in expected_names:
            check(parent.get(name) == source.get(name), arm + ' unchanged source table ' + name)
    structure = records(source['MaterielStructure'])
    check(any(r['MID'] == 'POS-B' and r['MMID'] == 'TEACH-AIR-01' and r['QTYPM'] == 2
              for r in structure), arm + ' two source POS-B copies')
    profile = records(source['OperationProfile'])
    check([(r['SPRID'], r['STIM']) for r in profile] ==
          [('BASIC-MISSION', 8), ('BASIC-MISSION', 20), ('BASIC-MISSION', 32)],
          arm + ' all three scheduled BASIC missions')
    nc = records(source['RBDNonCriticalSetItems'])
    check(len(nc) == 1 and nc[0]['NCID'] == 'G09-NC-B' and nc[0]['MID'] == 'POS-B' and
          nc[0]['QTYNC'] == (1 if arm == 'qty1' else 2) and nc[0]['USERT'] == 1,
          arm + ' isolated positive QTYNC value')
    check([c['name'] for c in source['RBDNonCriticalSetItems']['columns']] == fields,
          arm + ' native QTYNC column schema')
    check(source['MissionOperationalModes'] == parent['MissionOperationalModes'] and
          source['RBDSeriesStructure'] == parent['RBDSeriesStructure'] and
          source['FailureMode'] == parent['FailureMode'] and
          source['Control'] == parent['Control'],
          arm + ' fixed NCID mode, RBD, failure rates and seed')

    invocation = native_json(run / 'invocation.json')
    closure = native_json(run / 'closure.json')
    closures[arm] = closure
    check(sha(run / 'invocation.json') == closure['invocation_sha256'], arm + ' invocation seal')
    check(invocation['run_id'] == closure['run_id'] == run.name, arm + ' run identity')
    check(invocation['execution_mode'] == 'session0_ssh_cli' and
          invocation['session_id'] == 0 and 'sshd.exe' in invocation['ssh_ancestor_names'],
          arm + ' SSH session0')
    check(invocation['gui']['pid'] == 13340 and invocation['gui']['session_id'] == 1 and
          invocation['queue_mutex'] == r'Global\SimloxIssue18NativeQueue', arm + ' GUI/mutex')
    check(invocation['prelife_log_option_before'] == closure['prelife_log_option_after'] == 'NO',
          arm + ' registry option restored')
    check(invocation['source_hashes_before'] == closure['source_hashes_before'] ==
          closure['source_hashes_after'], arm + ' frozen source stability')
    paths = {
        'input': source_file, 'parent': parent_file,
        'parent_closure': parent_run / 'closure.json',
        'control': control_file, 'control_closure': control_run / 'closure.json',
        'diagnostic_qty1': diagnostic_files['qty1'],
        'diagnostic_qty1_closure': diagnostic_runs['qty1'] / 'closure.json',
        'diagnostic_qty2': diagnostic_files['qty2'],
        'diagnostic_qty2_closure': diagnostic_runs['qty2'] / 'closure.json',
        'contract': CASE / 'contract.json', 'exact_diff': CASE / 'exact-diff.json',
        'builder': CASE / 'build.py', 'diff_builder': CASE / 'describe_diff.py',
        'checker': CASE / 'check_roundtrip.py', 'runner': CASE / 'run_native_ssh.ps1',
        **EXTERNAL,
    }
    for name, path in paths.items():
        check(sha(path) == closure['source_hashes_before'][name], arm + ' source seal ' + name)
    check(len(closure['raw']) == 13, arm + ' 13 raw file seals')
    for name, metadata in closure['raw'].items():
        path = run / name
        check(path.exists() and path.stat().st_size == metadata['bytes'] and
              sha(path) == metadata['sha256'], arm + ' raw bytes and SHA ' + name)
    check(sha(run / 'input.json') == sha(source_file), arm + ' native input source copy')
    steps = native_json(run / 'steps.json')
    check([step['name'] for step in steps] ==
          ['import', 'export', 'calc', 'jsonreport', 'check_import_export'],
          arm + ' five guarded native steps')
    for step in steps:
        check(step['exit_code'] == 0 and step['status'] == 'completed' and
              step['gui_preserved'], arm + ' step success ' + step['name'])
    check([step['arguments'] for step in steps[:4]] ==
          [command['args'] for command in invocation['planned_commands']],
          arm + ' executed CLI arguments')
    check(closure['conversion']['errors'] == closure['conversion']['notes'] == 0 and
          closure['conversion']['warning_codes'] == ['108'],
          arm + ' zero errors and reviewed warning')
    check(closure['native_outcome'] == 'zero_error_reviewed_warnings' and
          closure['sxo_bytes'] > 4 and closure['report_present'], arm + ' valid output')
    check(not re.search(r'\berror\s*#', (run / 'run.log').read_text(encoding='utf-8-sig'), re.I),
          arm + ' no converter error text')
    exported = tables(native_json(run / 'roundtrip-raw.json'), 'model')
    populated = [name for name, table in source.items() if rows(table)]
    check(len(populated) == 27, arm + ' 27 populated business tables')
    for name in populated:
        check(name in exported, arm + ' exported ' + name)
        if name in exported:
            check(source[name]['columns'] == exported[name]['columns'],
                  arm + ' exact exported columns ' + name)
            check(source[name]['instances'] == exported[name]['instances'],
                  arm + ' exact exported rows ' + name)
    logs[arm] = (run / 'model.log').read_text(encoding='utf-8-sig')
    reports[arm] = tables(native_json(run / 'report-raw.json'), 'report')

pair = {name: {'before': sources['qty1'].get(name), 'after': sources['qty2'].get(name)}
        for name in sources['qty1'].keys() | sources['qty2'].keys()
        if sources['qty1'].get(name) != sources['qty2'].get(name)}
check(pair == diff['between_arms'] and
      set(pair) == {'ProblemDescription', 'RBDNonCriticalSetItems'},
      'exact within-pair QTYNC-only business contrast')
for name in sources['qty1'].keys() | sources['qty2'].keys():
    if name not in pair:
        check(sources['qty1'].get(name) == sources['qty2'].get(name),
              'identical within-pair source table ' + name)


def event(arm, hour, fragment):
    return any(line.startswith('Time: ' + str(hour) + ' ') and fragment in line
               for line in logs[arm].splitlines())


for arm, log in logs.items():
    for index, ordered, launched, returned in ((0, 7, 8, 10),
                                               (1, 19, 20, 22),
                                               (2, 31, 32, 34)):
        identity = f'<BASIC-MISSION,TEACH-UNIT,0,0,{index}>'
        check(event(arm, ordered, 'mission ordered: BASIC-MISSION') and
              event(arm, ordered, identity + ' mission allocates system: <TEACH-AIR-01,0>') and
              event(arm, launched, identity + ' mission starting, duration: 2'),
              arm + f' mission {index} order/aircraft/launch')
        if index != 1 or arm == 'qty2':
            check(event(arm, returned, identity + ' mission success:') and
                  event(arm, returned, identity + ' mission completed:') and
                  identity + ' mission aborted:' not in log,
                  arm + f' mission {index} successful outcome')
        else:
            check(event(arm, 21.742, identity + ' mission aborted:') and
                  event(arm, 22, identity + ' aborted mission completed:') and
                  identity + ' mission success:' not in log,
                  arm + ' second mission critical abort, return h22')
    for time, severity, complexity in ((8.37658, 'noncritical', '0.0683225'),
                                       (20.4933, 'noncritical', '0.414003'),
                                       (21.742, 'critical' if arm == 'qty1' else 'noncritical',
                                        '0.0982378')):
        prefix = f'Time: {time} <TEACH-AIR-01,0> {severity} CM failure mode added'
        block = log.split(prefix, 1)[1].split('Time:', 1)[0] if prefix in log else ''
        check('Failure Mode: FM-POS-B on materiel: <POS-B,0>' in block and
              complexity in block, arm + f' B fault identity/severity {time}')
    check(log.count('CM failure mode added') == 3 and
          'Failure Mode: FM-POS-A' not in log,
          arm + ' exactly three B failures, no A fault')
    check(log.count('mission success:') == (2 if arm == 'qty1' else 3),
          arm + ' mission success count')
    for task, started, ended in ((0, 10, 10.5), (1, 22, 22.5), (2, 22, 22.5)):
        label = f'system CM task {task} on <TEACH-AIR-01,0>'
        check(event(arm, started, label + ' started') and
              event(arm, started, label + ' FMID: FM-POS-B') and
              event(arm, ended, label + ' completed'),
              arm + f' CM task {task} direct half-hour')
    check(event(arm, 10.5, 'systems ready: 1') and
          event(arm, 22.5, 'systems ready: 1') and
          event(arm, 34, 'systems ready: 1'), arm + ' readiness and terminal event')
    check('Item demand arrives' not in log, arm + ' no stock demand')
    check('<POS-B,1>' not in log,
          arm + ' no separately printed physical B-copy identifier')

for arm, report in reports.items():
    check(set(report) == {'ProblemDescription', 'ResultSummary',
                          'SystemResults', 'StockTotalResults'}, arm + ' report tables')
    summary = records(report['ResultSummary'])[0]
    for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36),
                           ('MTMF', 1), ('STMF', 1), ('MSTF', 1),
                           ('MSUF', 2 / 3 if arm == 'qty1' else 1),
                           ('RSMTMF', 0), ('RSMSTF', 0), ('RSMSUF', 0), ('RSSTMF', 0)):
        check(near(summary[name], expected), arm + ' summary ' + name)
    system = records(report['SystemResults'])
    stock = records(report['StockTotalResults'])
    check(len(system) == len(stock) == 72, arm + ' 72 System/Stock bins')
    for i, (entry, stock_entry) in enumerate(zip(system, stock)):
        start = i * .5
        end = start + .5
        check(entry['STINT'] == stock_entry['STINT'] == start and
              entry['ETINT'] == stock_entry['ETINT'] == end,
              arm + f' half-hour interval {i}')
        reserve = sum(occupancy(a, b, start) for a, b in ((7, 8), (19, 20), (31, 32)))
        flight = sum(occupancy(a, b, start) for a, b in ((8, 10), (20, 22), (32, 34)))
        repair = sum(occupancy(a, b, start) for a, b in ((10, 10.5), (22, 22.5)))
        expected = {
            'NSYRY': 1 - reserve - flight - repair, 'NSYMA': reserve + flight,
            'NSYMO': flight, 'NSYMR': reserve, 'NSYRP': repair, 'NSYUA': repair,
            'NSYA': 1 - repair, 'FTMO': flight, 'STACC': flight,
            'NFAIL': sum(start <= time < end for time in (8.37658, 20.4933, 21.742)),
            'NREPT': 1 if i == 21 else 2 if i == 45 else 0,
            'NSYDT': int(i in (20, 44)),
        }
        for name, value in expected.items():
            check(near(entry[name], value), arm + f' SystemResults {name} bin {i}')
        check((near(entry['SYDT'], .5) if i in (20, 44) else entry['SYDT'] is None),
              arm + f' downtime duration bin {i}')
        for name in ('NSYMC', 'NSYMP', 'NSYMT', 'NSYMS', 'NSYAL', 'NSYPM', 'NSYTP',
                     'NSYWR', 'NSYWI', 'NSYLA', 'NSYUH', 'NPMT', 'NDAM', 'NPMS',
                     'NROBT', 'NRCFG', 'STREQ', 'STF', 'STLOW', 'SYDTU', 'NSYSW',
                     'NPSTA', 'NPSUC'):
            check(entry[name] == 0, arm + f' zero SystemResults {name} bin {i}')
        check(stock_entry['PNB'] == 1 and
              all(value is None or value == 0 for name, value in stock_entry.items()
                  if name not in ('STINT', 'ETINT', 'PNB')),
              arm + f' no StockTotalResults movement bin {i}')
    check(near(system[-1]['NSYRY'], 1), arm + ' terminal aircraft ready')
    check(near(sum(entry['NSYMO'] for entry in system) * .5, 6),
          arm + ' six flight hours')
    check(near(sum(entry['NSYRP'] for entry in system) * .5, 1),
          arm + ' one hour pooled CM occupancy with concurrent B tasks')
check(reports['qty1']['SystemResults'] == reports['qty2']['SystemResults'] and
      reports['qty1']['StockTotalResults'] == reports['qty2']['StockTotalResults'],
      'pair aggregate System/Stock bins byte-semantic equality')
summary1 = records(reports['qty1']['ResultSummary'])[0]
summary2 = records(reports['qty2']['ResultSummary'])[0]
check({key for key in summary1 if summary1[key] != summary2[key]} == {'MSUF'},
      'only report summary MSUF distinguishes mission outcomes')

verdict = {
    'schema': 'simlox-g09-var03-qtypnc-v103-independent-readonly/v1',
    'passed': not failures, 'checks_passed': checks - len(failures), 'checks_total': checks,
    'decision': ('GO: bounded QTYNC1 versus2 observed two-copy B-fault contrast'
                 if not failures else 'NO-GO: independent raw replay failed'),
    'failures': failures, 'raw_seals': sum(len(c['raw']) for c in closures.values()),
    'runs': {arm: {'source_sha256': sha(CASE / f'{arm}-input.json'),
                   'closure_sha256': sha(run / 'closure.json'),
                   'model_log_sha256': sha(run / 'model.log'),
                   'report_sha256': sha(run / 'report-raw.json')}
             for arm, run in RUNS.items()},
    'observed': {
        'both': 'B faults h8.37658, h20.4933, h21.742; h20 mission BASIC in both.',
        'qty1': 'Second h20 B fault critical, mission abort h21.742, completed return h22; MSUF2/3.',
        'qty2': 'Second h20 B fault noncritical, mission success h22; MSUF1.',
        'terminal': 'Three direct half-hour B CM tasks; two overlap h22-22.5; ready1, zero stock movement.'},
    'limits': [
        'Only source QTYPM2 and QTYNC1/2 with one BASIC mode, one seed and replication are tested.',
        'Native log records two distinct h20 POS-B failures but prints <POS-B,0> for both; separate physical copy IDs are not directly exposed.',
        'At h22 both arms print task 2 with priority C despite qty2 in-flight second fault being noncritical; task priority is not used as severity evidence.',
        'No generic copy assignment law, population estimate, GUI drawing or cross-engine parity claim.'
    ],
}
OUT.write_bytes((json.dumps(verdict, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': verdict['passed'], 'checks_passed': verdict['checks_passed'],
                  'checks_total': checks, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
