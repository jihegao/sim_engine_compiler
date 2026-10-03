"""Independent, standard-library, read-only replay of sealed G09.var01 evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / 'runs' / 'g09-var01-mixed-v100-ssh-20261003-01'
OUT = CASE / 'review' / 'independent-validation-2026-10-03.json'
TOOLS = {
    'python': Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    'exe': Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
    'manual': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
    'dictionary': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path):
    # SIMLOX's JSON export may contain trailing commas.
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
            out.append(char)
            quoted = True
        elif char == ',':
            next_i = i + 1
            while next_i < len(data) and data[next_i].isspace():
                next_i += 1
            if next_i == len(data) or data[next_i] not in '}]':
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


def close(actual, expected, tolerance=.0007):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=tolerance)


def occupancy(a, b, interval_start):
    return 2 * max(0, min(b, interval_start + .5) - max(a, interval_start))


checks = 0
failures = []


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


contract = native_json(CASE / 'contract.json')
parent_dir = CASES / contract['accepted_parent']['package']
parent_file = parent_dir / 'parallel-input.json'
parent_run = parent_dir / 'runs' / contract['accepted_parent']['run_id']
donor_file = parent_dir / 'series-input.json'
donor_run = parent_dir / 'runs' / 'g04-series-v101-ssh-20261002-01'
source_file = CASE / 'mixed-input.json'
source = tables(native_json(source_file), 'model')
parent = tables(native_json(parent_file), 'model')
donor = tables(native_json(donor_file), 'model')
diff = native_json(CASE / 'exact-diff.json')

for path, expected, label in (
    (parent_file, contract['accepted_parent']['input_sha256'], 'accepted parallel parent source'),
    (parent_run / 'closure.json', contract['accepted_parent']['native_closure_sha256'], 'accepted parallel parent closure'),
    (donor_file, contract['schema_and_control_donor']['input_sha256'], 'accepted series donor source'),
    (donor_run / 'closure.json', contract['schema_and_control_donor']['native_closure_sha256'], 'accepted series donor closure'),
    (source_file, contract['input_sha256'], 'frozen child source'),
    (CASE / 'exact-diff.json', contract['exact_diff_sha256'], 'frozen exact diff'),
):
    check(digest(path) == expected, label + ' SHA-256')
for key in ('exe', 'manual', 'dictionary'):
    check(digest(TOOLS[key]) == contract['source'][key + '_sha256'], 'installed ' + key + ' SHA-256')

changed = {name: {'before': parent.get(name), 'after': source.get(name)}
           for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
expected_changed = {'ProblemDescription', 'MissionType', 'OperationProfile',
                    'OperationalModes', 'MissionOperationalModes',
                    'MaterielOperationalModes', 'RBDSeries', 'RBDSeriesStructure'}
check(set(changed) == expected_changed and changed == diff['changed'],
      'exact eight-table parent/child delta')
check(diff['parent_sha256'] == digest(parent_file) and diff['input_sha256'] == digest(source_file),
      'exact diff parent/child SHA binding')
for name in parent.keys() | source.keys():
    if name not in expected_changed:
        check(parent.get(name) == source.get(name), 'unchanged business table ' + name)
for name in ('FailureMode', 'Control', 'CMLocation', 'SystemRepair', 'MaterielPosition'):
    check(parent[name] == source[name], 'fixed seed/failure/repair/physical source ' + name)

dictionary = TOOLS['dictionary'].read_text(encoding='utf-8-sig')
for name, columns in (
    ('MissionOperationalModes', ['MTID', 'SID', 'OPMID', 'NOTE']),
    ('RBDSeries', ['RBID', 'DESCR', 'NOTE']),
    ('RBDSeriesStructure', ['RBID', 'SRBID', 'OPMID', 'QTYPB', 'NOTE']),
):
    fields = [line.split(';')[2] for line in dictionary.splitlines() if line.startswith(name + ';')]
    check(fields == columns, 'installed dictionary schema ' + name)
    check([column['name'] for column in source[name]['columns']] == columns,
          'authored schema ' + name)
    if name.startswith('RBDSeries'):
        check(source[name]['columns'] == donor[name]['columns'], 'accepted series donor schema ' + name)

mission_modes = records(source['MissionOperationalModes'])
check({(r['MTID'], r['SID'], r['OPMID']) for r in mission_modes} ==
      {('BASIC-MISSION', 'TEACH-AIR-01', 'G09-SER-OPS'),
       ('PAR-MISSION', 'TEACH-AIR-01', 'G04-OPS')}, 'two mission-specific operational modes')
material_modes = records(source['MaterielOperationalModes'])
check({(r['MID'], r['OPMID'], r['RBID']) for r in material_modes if r['RBID']} ==
      {('TEACH-AIR-01', 'G09-SER-OPS', 'G09-SER-RBD'),
       ('TEACH-AIR-01', 'G04-OPS', 'G04-PARALLEL')}, 'mission mode to series/parallel RBD binding')
check({(r['RBID'], r['SRBID'], r['OPMID'], r['QTYPB'])
       for r in records(source['RBDSeriesStructure'])} ==
      {('G09-SER-RBD', 'POS-A', 'G04-OPS', 1),
       ('G09-SER-RBD', 'POS-B', 'G04-OPS', 1)}, 'new series requires A and B')
check(records(source['RBDParallel']) == records(parent['RBDParallel']) and
      records(source['RBDParallelStructure']) == records(parent['RBDParallelStructure']),
      'inherited active parallel block unchanged')
check([(r['SPRID'], r['STIM']) for r in records(source['OperationProfile'])] ==
      [('BASIC-MISSION', 8), ('PAR-MISSION', 20), ('BASIC-MISSION', 32)],
      'series/parallel/series scheduled mission types')
check(len(records(source['MissionType'])) == 2 and
      {r['MTID'] for r in records(source['MissionType'])} == {'BASIC-MISSION', 'PAR-MISSION'} and
      all(r['DURN'] == 2 and r['MSUCPT'] == 1 and r['NOPER'] == 1
          for r in records(source['MissionType'])), 'matched two-hour mission parameters')

invocation = native_json(RUN / 'invocation.json')
closure = native_json(RUN / 'closure.json')
check(digest(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation SHA seal')
check(invocation['run_id'] == closure['run_id'] == RUN.name, 'run identity')
check(invocation['execution_mode'] == 'session0_ssh_cli' and invocation['session_id'] == 0 and
      'sshd.exe' in invocation['ssh_ancestor_names'], 'SSH session-0 execution')
check(invocation['gui']['pid'] == 13340 and invocation['gui']['session_id'] == 1 and
      invocation['queue_mutex'] == r'Global\SimloxIssue18NativeQueue', 'GUI and queue identity')
check(invocation['prelife_log_option_before'] == closure['prelife_log_option_after'] == 'NO',
      'registry option restored')
check(invocation['source_hashes_before'] == closure['source_hashes_before'] ==
      closure['source_hashes_after'], 'source stable before and after native run')
source_paths = {
    'input': source_file, 'parent': parent_file, 'parent_closure': parent_run / 'closure.json',
    'schema_donor': donor_file, 'schema_donor_closure': donor_run / 'closure.json',
    'contract': CASE / 'contract.json', 'exact_diff': CASE / 'exact-diff.json',
    'builder': CASE / 'build.py', 'diff_builder': CASE / 'describe_diff.py',
    'checker': CASE / 'check_roundtrip.py', 'runner': CASE / 'run_native_ssh.ps1', **TOOLS,
}
for name, path in source_paths.items():
    check(digest(path) == closure['source_hashes_before'][name], 'frozen source seal ' + name)
check(len(closure['raw']) == 13, '13 declared raw seals')
for name, metadata in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == metadata['bytes'] and
          digest(path) == metadata['sha256'], 'raw file seal ' + name)
check(digest(RUN / 'input.json') == digest(source_file), 'native input equals frozen source')
steps = native_json(RUN / 'steps.json')
check([step['name'] for step in steps] ==
      ['import', 'export', 'calc', 'jsonreport', 'check_import_export'], 'five native steps')
for step in steps:
    check(step['exit_code'] == 0 and step['status'] == 'completed' and step['gui_preserved'],
          'guarded step ' + step['name'])
check([step['arguments'] for step in steps[:4]] ==
      [command['args'] for command in invocation['planned_commands']], 'executed CLI command binding')
check(closure['conversion']['errors'] == 0 and closure['conversion']['notes'] == 0 and
      closure['conversion']['warning_codes'] == ['108'], 'zero errors, reviewed warning 108')
check(closure['native_outcome'] == 'zero_error_reviewed_warnings' and
      closure['sxo_bytes'] > 4 and closure['report_present'], 'valid calculated result and report')
check(not re.search(r'\berror\s*#', (RUN / 'run.log').read_text(encoding='utf-8-sig'), re.I),
      'no converter error text')
exported = tables(native_json(RUN / 'roundtrip-raw.json'), 'model')
populated = [name for name, table in source.items() if rows(table)]
check(len(populated) == 25, '25 populated authored business tables')
for name in populated:
    check(name in exported, 'exported table ' + name)
    if name in exported:
        check(source[name]['columns'] == exported[name]['columns'], 'exact exported columns ' + name)
        check(source[name]['instances'] == exported[name]['instances'], 'exact exported rows ' + name)

log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
lines = log.splitlines()


def event(hour, fragment):
    return any(line.startswith('Time: ' + str(hour) + ' ') and fragment in line for line in lines)


parallel_log = (parent_run / 'model.log').read_text(encoding='utf-8-sig')
series_log = (donor_run / 'model.log').read_text(encoding='utf-8-sig')
for label, reference in (('parallel', parallel_log), ('series', series_log)):
    for hour, mode, position in ((8.62763, 'noncritical' if label == 'parallel' else 'critical', 'B'),
                                 (20.8222, 'noncritical' if label == 'parallel' else 'critical', 'B'),
                                 (33.0996, 'noncritical' if label == 'parallel' else 'critical', 'A')):
        check('Time: ' + str(hour) + ' <TEACH-AIR-01,0> ' + mode +
              ' CM failure mode added' in reference, label + ' control criticality ' + str(hour))
        check('Failure Mode: FM-POS-' + position + ' on materiel: <POS-' + position + ',0>'
              in reference, label + ' control fault identity ' + position)

mission_specs = (
    ('BASIC-MISSION', 0, 7, 8, 8.62763, 9.12763, 9.62763, 'B', True),
    ('PAR-MISSION', 1, 19, 20, 20.8222, 22, 22.5, 'B', False),
    ('BASIC-MISSION', 2, 31, 32, 33.0996, 33.5996, 34.0996, 'A', True),
)
for mission_type, index, order, launch, fault, ret, repair_end, pos, critical in mission_specs:
    identity = f'<{mission_type},TEACH-UNIT,0,0,{index}>'
    check(event(order, 'mission ordered: ' + mission_type) and
          event(order, identity + ' mission created:') and
          event(order, identity + ' mission allocates system: <TEACH-AIR-01,0>'),
          f'mission {index} order/create/allocation')
    check(event(launch, identity + ' mission starting, duration: 2'),
          f'mission {index} launch')
    check(event(fault, ('critical' if critical else 'noncritical') + ' CM failure mode added'),
          f'mission {index} fault criticality')
    fault_line = ('Time: ' + str(fault) + ' <TEACH-AIR-01,0> ' +
                  ('critical' if critical else 'noncritical') + ' CM failure mode added')
    fault_block = log.split(fault_line, 1)[1].split('Time:', 1)[0] if fault_line in log else ''
    check('Failure Mode: FM-POS-' + pos + ' on materiel: <POS-' + pos + ',0>'
          in fault_block, f'mission {index} timed physical position fault')
    if critical:
        check(event(fault, identity + ' mission aborted:') and
              event(ret, identity + ' aborted mission completed:'),
              f'mission {index} abort and return')
        check(not any(identity + ' mission success:' in line for line in lines),
              f'mission {index} no success')
    else:
        check(event(ret, identity + ' mission success:') and
              event(ret, identity + ' mission completed:'),
              f'mission {index} success and return')
        check(not any(identity + ' mission aborted:' in line for line in lines),
              f'mission {index} no abort')
    task = f'system CM task {index} on <TEACH-AIR-01,0>'
    check(event(ret, task + ' started') and event(ret, task + ' FMID: FM-POS-' + pos) and
          event(repair_end, task + ' completed'), f'mission {index} system CM identity and duration')
    check(f'< {task}, C, 0.5>' in log, f'mission {index} half-hour critical CM')
    check(event(repair_end, 'systems ready: 1'), f'mission {index} repaired readiness')
check(log.count('CM failure mode added') == 3 and
      sum(line.startswith('Time: 9.62763  system CM task 0 on <TEACH-AIR-01,0> completed')
          for line in lines) == 1,
      'three fault events and first CM completion')
check('Item demand arrives' not in log and 'stock item' not in log.lower(),
      'no physical stock activity')

report = tables(native_json(RUN / 'report-raw.json'), 'report')
check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'},
      'native report table set')
summary = records(report['ResultSummary'])[0]
for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36), ('MTMF', .7878668308258057),
                       ('STMF', .7878668308258057), ('MSTF', 1),
                       ('MSUF', 1 / 3), ('RSMTMF', 0), ('RSMSTF', 0), ('RSMSUF', 0), ('RSSTMF', 0)):
    check(close(summary[name], expected), 'summary ' + name)
system = records(report['SystemResults'])
stock = records(report['StockTotalResults'])
check(len(system) == len(stock) == 72, '72 aligned System/Stock half-hour bins')
reserved_intervals = ((7, 8), (19, 20), (31, 32))
flight_intervals = ((8, 9.12763), (20, 22), (32, 33.5996))
repair_intervals = ((9.12763, 9.62763), (22, 22.5), (33.5996, 34.0996))
fault_times = (8.62763, 20.8222, 33.0996)
for index, (record, stock_record) in enumerate(zip(system, stock)):
    start = index * .5
    end = start + .5
    check(record['STINT'] == stock_record['STINT'] == start and
          record['ETINT'] == stock_record['ETINT'] == end,
          f'aligned System/Stock interval {index}')
    reserved = sum(occupancy(a, b, start) for a, b in reserved_intervals)
    flight = sum(occupancy(a, b, start) for a, b in flight_intervals)
    repair = sum(occupancy(a, b, start) for a, b in repair_intervals)
    expected = {'NSYRY': 1 - reserved - flight - repair, 'NSYMA': reserved + flight,
                'NSYMO': flight, 'NSYMR': reserved, 'NSYRP': repair,
                'NSYUA': repair, 'NSYA': 1 - repair, 'FTMO': flight,
                'STACC': flight, 'NFAIL': sum(start <= t < end for t in fault_times),
                'NREPT': int(index in (19, 45, 68)),
                'NSYDT': int(index in (18, 44, 67))}
    for name, value in expected.items():
        check(close(record[name], value), f'SystemResults {name} bin {index}')
    check((close(record['SYDT'], .5) if index in (18, 44, 67)
           else record['SYDT'] is None), f'downtime duration bin {index}')
    for name in ('NSYMC', 'NSYMP', 'NSYMT', 'NSYMS', 'NSYAL', 'NSYPM', 'NSYTP',
                 'NSYWR', 'NSYWI', 'NSYLA', 'NSYUH', 'NPMT', 'NDAM', 'NPMS',
                 'NROBT', 'NRCFG', 'STREQ', 'STF', 'STLOW', 'SYDTU', 'NSYSW',
                 'NPSTA', 'NPSUC'):
        check(record[name] == 0, f'zero SystemResults {name} bin {index}')
    check(stock_record['PNB'] == 1 and
          all(value is None or value == 0 for name, value in stock_record.items()
              if name not in ('STINT', 'ETINT', 'PNB')),
          f'unchanged StockTotalResults bin {index}')
check(close(system[-1]['NSYRY'], 1), 'terminal one aircraft ready')
check(close(sum(record['NSYMO'] for record in system) * .5,
            sum(b - a for a, b in flight_intervals)), 'integrated flight hours')
check(close(sum(record['NSYRP'] for record in system) * .5, 1.5),
      'integrated three half-hour CM tasks')

result = {
    'schema': 'simlox-g09-var01-independent-readonly/v1',
    'passed': not failures, 'checks_passed': checks - len(failures), 'checks_total': checks,
    'decision': ('GO: bounded one-seed mission-specific series/parallel RBD selection'
                 if not failures else 'NO-GO: independent raw replay failed'),
    'failures': failures, 'raw_seals': len(closure['raw']),
    'source_sha256': digest(source_file), 'closure_sha256': digest(RUN / 'closure.json'),
    'model_log_sha256': digest(RUN / 'model.log'),
    'report_sha256': digest(RUN / 'report-raw.json'),
    'observed': {'BASIC_8': 'B h8.62763 critical, abort and CM',
                 'PAR_20': 'B h20.8222 noncritical, success and CM',
                 'BASIC_32': 'A h33.0996 critical, abort and CM',
                 'terminal': 'one aircraft ready, three repaired system faults, no stock movement'},
    'limits': [
        'The log does not name the selected RBID; mapping is source-bound and behavior is compared with accepted series/parallel controls.',
        'One aircraft, two mission types, three scheduled missions, one seed and replication; no general stochastic or population claim.',
        'No inference about other RBDs, mission patterns, GUI drawing, or cross-engine parity.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'],
                  'checks_total': checks, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
