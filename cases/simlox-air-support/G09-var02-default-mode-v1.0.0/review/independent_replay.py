"""Independent standard-library replay of the sealed G09.var02 native run."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / 'runs' / 'g09-var02-default-v100-ssh-20261003-01'
OUT = CASE / 'review' / 'independent-validation-2026-10-03.json'
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
    quoted = escape = False
    for index, char in enumerate(text):
        if quoted:
            result.append(char)
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            result.append(char)
        elif char == ',':
            next_index = index + 1
            while next_index < len(text) and text[next_index].isspace():
                next_index += 1
            if next_index == len(text) or text[next_index] not in '}]':
                result.append(char)
        else:
            result.append(char)
    return json.loads(''.join(result))


def tables(document, root):
    return {table['name']: table for table in document[root]['tables']}


def rows(table):
    return [row for instance in table['instances'] for row in instance['rows']]


def records(table):
    columns = [column['name'] for column in table['columns']]
    return [dict(zip(columns, row)) for row in rows(table)]


def near(actual, expected, tolerance=.0007):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=tolerance)


def occupancy(left, right, start):
    return 2 * max(0, min(right, start + .5) - max(left, start))


count = 0
failures = []


def check(condition, description):
    global count
    count += 1
    if not condition:
        failures.append(description)


contract = native_json(CASE / 'contract.json')
parent_dir = CASES / contract['accepted_parent']['package']
parent_file = parent_dir / 'mixed-input.json'
parent_run = parent_dir / 'runs' / contract['accepted_parent']['run_id']
series_dir = CASES / contract['series_control']['package']
series_file = series_dir / 'series-input.json'
series_run = series_dir / 'runs' / 'g04-series-v101-ssh-20261002-01'
source_file = CASE / 'default-input.json'
source = tables(native_json(source_file), 'model')
parent = tables(native_json(parent_file), 'model')
series = tables(native_json(series_file), 'model')
diff = native_json(CASE / 'exact-diff.json')
for path, expected, label in (
    (parent_file, contract['accepted_parent']['input_sha256'], 'accepted mixed parent source'),
    (parent_run / 'closure.json', contract['accepted_parent']['native_closure_sha256'],
     'accepted mixed parent closure'),
    (series_file, contract['series_control']['input_sha256'], 'accepted series control source'),
    (series_run / 'closure.json', contract['series_control']['native_closure_sha256'],
     'accepted series control closure'),
    (source_file, contract['input_sha256'], 'frozen child source'),
    (CASE / 'exact-diff.json', contract['exact_diff_sha256'], 'frozen table diff'),
):
    check(sha(path) == expected, label + ' SHA-256')
for key in ('exe', 'manual', 'dictionary'):
    check(sha(EXTERNAL[key]) == contract['source'][key + '_sha256'], 'installed ' + key + ' SHA-256')

changed = {name: {'before': parent.get(name), 'after': source.get(name)}
           for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
check(set(changed) == {'ProblemDescription', 'MissionOperationalModes'} and
      changed == diff['changed'], 'exact two-table parent delta')
check(diff['parent_sha256'] == sha(parent_file) and diff['input_sha256'] == sha(source_file),
      'diff source SHA binding')
for name in parent.keys() | source.keys():
    if name not in changed:
        check(parent.get(name) == source.get(name), 'unchanged table ' + name)
check(records(source['MissionOperationalModes']) ==
      [r for r in records(parent['MissionOperationalModes']) if r['MTID'] == 'BASIC-MISSION'],
      'only PAR-MISSION/TEACH-AIR-01 mapping removed')
check(len(records(source['MissionOperationalModes'])) == 1 and
      records(source['MissionOperationalModes'])[0]['OPMID'] == 'G09-SER-OPS',
      'BASIC retains explicit series mode')
check({r['MTID'] for r in records(source['MissionType'])} ==
      {'BASIC-MISSION', 'PAR-MISSION'} and
      [r['SPRID'] for r in records(source['OperationProfile'])] ==
      ['BASIC-MISSION', 'PAR-MISSION', 'BASIC-MISSION'],
      'mission types and schedule retained')
check(source['RBDSeries'] == parent['RBDSeries'] and
      source['RBDParallel'] == parent['RBDParallel'] and
      source['MaterielOperationalModes'] == parent['MaterielOperationalModes'],
      'both explicit RBDs remain present without source change')
check(parent['Control'] == source['Control'] and parent['FailureMode'] == source['FailureMode'] and
      parent['SystemRepair'] == source['SystemRepair'], 'fixed seed, physical faults and CM')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
fields = [line.split(';')[2] for line in dictionary.splitlines()
          if line.startswith('MissionOperationalModes;')]
check(fields == ['MTID', 'SID', 'OPMID', 'NOTE'], 'installed mission-mode mapping schema')
check([column['name'] for column in source['MissionOperationalModes']['columns']] == fields,
      'authored mission-mode schema')
check('G09-SER-RBD' in {r['RBID'] for r in records(source['RBDSeries'])} and
      'G04-PARALLEL' in {r['RBID'] for r in records(source['RBDParallel'])},
      'source retains both series and parallel block definitions')
check('RBDSeries' in series and 'RBDSeriesStructure' in series,
      'accepted all-series structural control')

inv = native_json(RUN / 'invocation.json')
closure = native_json(RUN / 'closure.json')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation seal')
check(inv['run_id'] == closure['run_id'] == RUN.name, 'run identity')
check(inv['execution_mode'] == 'session0_ssh_cli' and inv['session_id'] == 0 and
      'sshd.exe' in inv['ssh_ancestor_names'], 'guarded SSH session0')
check(inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1 and
      inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue', 'GUI and queue identity')
check(inv['prelife_log_option_before'] == closure['prelife_log_option_after'] == 'NO',
      'registry setting restored')
check(inv['source_hashes_before'] == closure['source_hashes_before'] ==
      closure['source_hashes_after'], 'source seals stable during run')
paths = {
    'input': source_file, 'parent': parent_file, 'parent_closure': parent_run / 'closure.json',
    'series_control': series_file, 'series_control_closure': series_run / 'closure.json',
    'contract': CASE / 'contract.json', 'exact_diff': CASE / 'exact-diff.json',
    'builder': CASE / 'build.py', 'diff_builder': CASE / 'describe_diff.py',
    'checker': CASE / 'check_roundtrip.py', 'runner': CASE / 'run_native_ssh.ps1', **EXTERNAL,
}
for name, path in paths.items():
    check(sha(path) == closure['source_hashes_before'][name], 'run source seal ' + name)
check(len(closure['raw']) == 13, '13 sealed raw files')
for name, expected in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == expected['bytes'] and
          sha(path) == expected['sha256'], 'raw bytes and SHA ' + name)
check(sha(RUN / 'input.json') == sha(source_file), 'native input exact frozen source')
steps = native_json(RUN / 'steps.json')
check([step['name'] for step in steps] ==
      ['import', 'export', 'calc', 'jsonreport', 'check_import_export'], 'five completed steps')
for step in steps:
    check(step['exit_code'] == 0 and step['status'] == 'completed' and step['gui_preserved'],
          'guarded step ' + step['name'])
check([step['arguments'] for step in steps[:4]] ==
      [command['args'] for command in inv['planned_commands']], 'executed CLI args match invocation')
check(closure['conversion']['errors'] == 0 and closure['conversion']['notes'] == 0 and
      closure['conversion']['warning_codes'] == ['108'], 'zero errors and reviewed warning')
check(closure['native_outcome'] == 'zero_error_reviewed_warnings' and
      closure['sxo_bytes'] > 4 and closure['report_present'], 'valid SXO and report')
check(not re.search(r'\berror\s*#', (RUN / 'run.log').read_text(encoding='utf-8-sig'), re.I),
      'no converter error text')
exported = tables(native_json(RUN / 'roundtrip-raw.json'), 'model')
populated = [name for name, table in source.items() if rows(table)]
check(len(populated) == 25, '25 populated business tables')
for name in populated:
    check(name in exported, 'native exported table ' + name)
    if name in exported:
        check(source[name]['columns'] == exported[name]['columns'], 'native columns ' + name)
        check(source[name]['instances'] == exported[name]['instances'], 'native rows ' + name)

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
lines = log.splitlines()
parent_log = (parent_run / 'model.log').read_text(encoding='utf-8-sig')
series_log = (series_run / 'model.log').read_text(encoding='utf-8-sig')


def event(hour, fragment):
    return any(line.startswith('Time: ' + str(hour) + ' ') and fragment in line for line in lines)


check('Time: 20.8222 <TEACH-AIR-01,0> noncritical CM failure mode added' in parent_log and
      'Time: 22 <PAR-MISSION,TEACH-UNIT,0,0,1> mission success:' in parent_log,
      'accepted explicit-parallel parent B noncritical and PAR success')
check('Time: 20.8222 <TEACH-AIR-01,0> critical CM failure mode added' in series_log and
      'Time: 20.8222 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission aborted:' in series_log,
      'accepted all-series control B critical and mission abort')
missions = (
    ('BASIC-MISSION', 0, 7, 8, 8.62763, 9.12763, 9.62763, 'B'),
    ('PAR-MISSION', 1, 19, 20, 20.8222, 21.3222, 21.8222, 'B'),
    ('BASIC-MISSION', 2, 31, 32, 33.0996, 33.5996, 34.0996, 'A'),
)
for mission, index, order, launch, fault, return_at, repair_end, position in missions:
    identity = f'<{mission},TEACH-UNIT,0,0,{index}>'
    check(event(order, 'mission ordered: ' + mission) and
          event(order, identity + ' mission allocates system: <TEACH-AIR-01,0>'),
          f'mission {index} order and aircraft identity')
    check(event(launch, identity + ' mission starting, duration: 2'),
          f'mission {index} launch')
    failure_line = f'Time: {fault} <TEACH-AIR-01,0> critical CM failure mode added'
    block = log.split(failure_line, 1)[1].split('Time:', 1)[0] if failure_line in log else ''
    check('Failure Mode: FM-POS-' + position +
          ' on materiel: <POS-' + position + ',0>' in block,
          f'mission {index} timed physical failure and criticality')
    check(event(fault, identity + ' mission aborted:') and
          event(return_at, identity + ' aborted mission completed:') and
          not any(identity + ' mission success:' in line for line in lines),
          f'mission {index} abort, return, no success')
    task = f'system CM task {index} on <TEACH-AIR-01,0>'
    check(event(return_at, task + ' started') and
          event(return_at, task + ' FMID: FM-POS-' + position) and
          event(repair_end, task + ' completed'),
          f'mission {index} same-mode direct CM task')
    check(f'< {task}, C, 0.5>' in log and event(repair_end, 'systems ready: 1'),
          f'mission {index} half-hour critical repair and readiness')
check(log.count('CM failure mode added') == 3 and 'mission success:' not in log,
      'three failures and zero successes')
check('Item demand arrives' not in log, 'no spare demand event')

report = tables(native_json(RUN / 'report-raw.json'), 'report')
check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'},
      'report table set')
summary = records(report['ResultSummary'])[0]
for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36),
                       ('MTMF', .6748974919319153), ('STMF', .6748974919319153),
                       ('MSTF', 1), ('MSUF', 0), ('RSMTMF', 0), ('RSMSTF', 0),
                       ('RSMSUF', 0), ('RSSTMF', 0)):
    check(near(summary[name], expected), 'summary ' + name)
system = records(report['SystemResults'])
stock = records(report['StockTotalResults'])
check(len(system) == len(stock) == 72, '72 System/Stock half-hour bins')
reserved_periods = ((7, 8), (19, 20), (31, 32))
flight_periods = ((8, 9.12763), (20, 21.3222), (32, 33.5996))
repair_periods = ((9.12763, 9.62763), (21.3222, 21.8222), (33.5996, 34.0996))
failure_times = (8.62763, 20.8222, 33.0996)
for index, (entry, stock_entry) in enumerate(zip(system, stock)):
    start = index * .5
    end = start + .5
    check(entry['STINT'] == stock_entry['STINT'] == start and
          entry['ETINT'] == stock_entry['ETINT'] == end, f'aligned interval {index}')
    reserved = sum(occupancy(a, b, start) for a, b in reserved_periods)
    flight = sum(occupancy(a, b, start) for a, b in flight_periods)
    repair = sum(occupancy(a, b, start) for a, b in repair_periods)
    expectation = {
        'NSYRY': 1 - reserved - flight - repair, 'NSYMA': reserved + flight,
        'NSYMO': flight, 'NSYMR': reserved, 'NSYRP': repair, 'NSYUA': repair,
        'NSYA': 1 - repair, 'FTMO': flight, 'STACC': flight,
        'NFAIL': sum(start <= time < end for time in failure_times),
        'NREPT': int(index in (19, 43, 68)),
        'NSYDT': int(index in (18, 42, 67)),
    }
    for name, value in expectation.items():
        check(near(entry[name], value), f'SystemResults {name} bin {index}')
    check((near(entry['SYDT'], .5) if index in (18, 42, 67)
           else entry['SYDT'] is None), f'half-hour downtime marker bin {index}')
    for name in ('NSYMC', 'NSYMP', 'NSYMT', 'NSYMS', 'NSYAL', 'NSYPM', 'NSYTP',
                 'NSYWR', 'NSYWI', 'NSYLA', 'NSYUH', 'NPMT', 'NDAM', 'NPMS',
                 'NROBT', 'NRCFG', 'STREQ', 'STF', 'STLOW', 'SYDTU', 'NSYSW',
                 'NPSTA', 'NPSUC'):
        check(entry[name] == 0, f'zero SystemResults {name} bin {index}')
    check(stock_entry['PNB'] == 1 and
          all(value is None or value == 0 for name, value in stock_entry.items()
              if name not in ('STINT', 'ETINT', 'PNB')),
          f'unchanged StockTotalResults bin {index}')
check(near(system[-1]['NSYRY'], 1), 'terminal one aircraft ready')
check(near(sum(row['NSYMO'] for row in system) * .5,
           sum(b - a for a, b in flight_periods)), 'integrated abort-limited flight hours')
check(near(sum(row['NSYRP'] for row in system) * .5, 1.5),
      'three half-hour repairs in report')

verdict = {
    'schema': 'simlox-g09-var02-independent-readonly/v1',
    'passed': not failures, 'checks_passed': count - len(failures), 'checks_total': count,
    'decision': ('GO: bounded omitted PAR mode behaves like documented default series'
                 if not failures else 'NO-GO: independent raw replay failed'),
    'failures': failures, 'raw_seals': len(closure['raw']),
    'source_sha256': sha(source_file), 'closure_sha256': sha(RUN / 'closure.json'),
    'model_log_sha256': sha(RUN / 'model.log'), 'report_sha256': sha(RUN / 'report-raw.json'),
    'observed': {
        'source': 'Only PAR MissionOperationalModes row removed; both explicit RBDs remain.',
        'contrast': 'Parent PAR B h20.8222 noncritical/success; omitted PAR B same hour critical/abort.',
        'control': 'Accepted G04 all-series B h20.8222 critical/abort.',
        'terminal': 'All three missions abort; each system CM takes 0.5h; ready1 and no stock movement.'},
    'limits': [
        'Manual p196 states omitted mission mode assumes <DEFAULT> series; native log does not print the selected mode.',
        'One omitted row, one aircraft, two-position model, three missions, one seed/replication; other defaults are untested.',
        'No GUI drawing, population reliability, or cross-engine claim.'
    ],
}
OUT.write_bytes((json.dumps(verdict, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': verdict['passed'], 'checks_passed': verdict['checks_passed'],
                  'checks_total': count, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
