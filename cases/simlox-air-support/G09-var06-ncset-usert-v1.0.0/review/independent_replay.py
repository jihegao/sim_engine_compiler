"""Independent standard-library, read-only G09.var06 evidence replay."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OUT = Path(__file__).with_name('independent-validation-2026-10-03.json')
RUNS = {a: CASE / 'runs' / f'g09-var06-{a}-v100-ssh-20261003-01'
        for a in ('ncuse0', 'ncuse1')}
EXTERNAL = {
    'python': Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    'exe': Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
    'manual': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
    'dictionary': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path):
    raw = path.read_text(encoding='utf-8-sig')
    output = []
    quoted = escaped = False
    for pos, char in enumerate(raw):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            output.append(char)
        elif char == ',':
            next_pos = pos + 1
            while next_pos < len(raw) and raw[next_pos].isspace():
                next_pos += 1
            if next_pos == len(raw) or raw[next_pos] not in '}]':
                output.append(char)
        else:
            output.append(char)
    return json.loads(''.join(output))


def tables(doc, root):
    return {table['name']: table for table in doc[root]['tables']}


def rows(table):
    return [row for instance in table['instances'] for row in instance['rows']]


def records(table):
    fields = [c['name'] for c in table['columns']]
    return [dict(zip(fields, row)) for row in rows(table)]


def near(a, b, tol=.0007):
    return isinstance(a, (int, float)) and math.isclose(a, b, abs_tol=tol)


def occupancy(a, b, start):
    return 2 * max(0, min(b, start + .5) - max(a, start))


count = 0
failures = []


def check(ok, label):
    global count
    count += 1
    if not ok:
        failures.append(label)


contract = native_json(CASE / 'contract.json')
diff = native_json(CASE / 'exact-diff.json')
parent_file = ROOT / contract['accepted_parent']['package'] / 'omitted-nc-b1-input.json'
parent_closure = ROOT / contract['accepted_parent']['package'] / 'runs' / 'g09-var03-omitted-nc-b1-v101-ssh-20261003-01' / 'closure.json'
check(sha(parent_file) == contract['accepted_parent']['input_sha256'], 'accepted parent source seal')
check(sha(parent_closure) == contract['accepted_parent']['native_closure_sha256'], 'accepted parent run seal')
check(sha(CASE / 'exact-diff.json') == contract['exact_diff_sha256'], 'frozen exact diff seal')
check(diff['parent_sha256'] == sha(parent_file) and diff['input_sha256'] == contract['input_sha256'], 'diff hash bindings')
for kind in ('exe', 'manual', 'dictionary'):
    check(sha(EXTERNAL[kind]) == contract['source'][kind + '_sha256'], kind + ' installed source fingerprint')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
nc_columns = [line.split(';')[2] for line in dictionary.splitlines() if line.startswith('RBDNonCriticalSetItems;')]
check(nc_columns == ['NCID', 'MID', 'QTYNC', 'USERT', 'NOTE'], 'native NC-set column schema')

parent = tables(native_json(parent_file), 'model')
sources, reports, logs, closures = {}, {}, {}, {}
for arm, run in RUNS.items():
    source_file = CASE / f'{arm}-input.json'
    source = tables(native_json(source_file), 'model')
    sources[arm] = source
    check(sha(source_file) == contract['input_sha256'][arm], arm + ' source SHA')
    delta = {name: {'before': parent.get(name), 'after': source.get(name)}
             for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
    check(delta == diff['from_parent'][arm], arm + ' exact parent table delta')
    check(set(delta) == ({'ProblemDescription', 'FailureMode', 'RBDNonCriticalSetItems'}
                         if arm == 'ncuse0' else {'ProblemDescription', 'FailureMode'}),
          arm + ' exact parent changed-table set')
    for name in parent.keys() | source.keys():
        if name not in delta:
            check(parent.get(name) == source.get(name), arm + ' unchanged table ' + name)
    fm = records(source['FailureMode'])
    check(len(fm) == 2 and {r['FMID']: r['FRQ'] for r in fm} ==
          {'FM-POS-A': 1e-9, 'FM-POS-B': 600000}, arm + ' common A and B failure rates')
    nc = records(source['RBDNonCriticalSetItems'])
    check([c['name'] for c in source['RBDNonCriticalSetItems']['columns']] == nc_columns and
          len(nc) == 1 and nc[0]['NCID'] == 'G09-NC-B' and nc[0]['MID'] == 'POS-B' and
          nc[0]['QTYNC'] == 1 and nc[0]['USERT'] == (0 if arm == 'ncuse0' else 1),
          arm + ' source-defined NC-set usage')
    invocation = native_json(run / 'invocation.json')
    closure = native_json(run / 'closure.json')
    closures[arm] = closure
    check(sha(run / 'invocation.json') == closure['invocation_sha256'], arm + ' invocation seal')
    check(invocation['run_id'] == closure['run_id'] == run.name, arm + ' run identity')
    check(invocation['execution_mode'] == 'session0_ssh_cli' and invocation['session_id'] == 0 and
          'sshd.exe' in invocation['ssh_ancestor_names'], arm + ' session0 SSH')
    check(invocation['gui']['pid'] == 13340 and invocation['gui']['session_id'] == 1 and
          invocation['queue_mutex'] == r'Global\SimloxIssue18NativeQueue', arm + ' GUI and mutex guard')
    check(invocation['prelife_log_option_before'] == closure['prelife_log_option_after'] == 'NO', arm + ' registry restored')
    check(invocation['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'], arm + ' source stability')
    sealed_paths = {'input': source_file, 'parent': parent_file, 'parent_closure': parent_closure,
                    'contract': CASE / 'contract.json', 'exact_diff': CASE / 'exact-diff.json',
                    'builder': CASE / 'build.py', 'diff_builder': CASE / 'describe_diff.py',
                    'checker': CASE / 'check_roundtrip.py', 'runner': CASE / 'run_native_ssh.ps1',
                    **EXTERNAL}
    for key, path in sealed_paths.items():
        check(sha(path) == closure['source_hashes_before'][key], arm + ' source seal ' + key)
    check(len(closure['raw']) == 13, arm + ' thirteen raw seals')
    for name, metadata in closure['raw'].items():
        path = run / name
        check(path.exists() and path.stat().st_size == metadata['bytes'] and sha(path) == metadata['sha256'],
              arm + ' raw seal ' + name)
    steps = native_json(run / 'steps.json')
    check([s['name'] for s in steps] == ['import', 'export', 'calc', 'jsonreport', 'check_import_export'], arm + ' five steps')
    for s in steps:
        check(s['exit_code'] == 0 and s['status'] == 'completed' and s['gui_preserved'], arm + ' guarded step ' + s['name'])
    check([s['arguments'] for s in steps[:4]] == [c['args'] for c in invocation['planned_commands']], arm + ' planned CLI args')
    cv = closure['conversion']
    check(cv['errors'] == cv['notes'] == 0 and cv['warning_codes'] == ['108'] and cv['calc_exit_code'] == 0,
          arm + ' zero-error diagnostics')
    check(closure['native_outcome'] == 'zero_error_reviewed_warnings' and closure['sxo_bytes'] > 4 and
          closure['report_present'], arm + ' valid output')
    check(sha(run / 'input.json') == sha(source_file), arm + ' copied native input')
    exported = tables(native_json(run / 'roundtrip-raw.json'), 'model')
    populated = [name for name, table in source.items() if rows(table)]
    check(len(populated) == 27, arm + ' 27 row-containing source tables')
    for name in populated:
        check(name in exported and source[name]['columns'] == exported[name]['columns'] and
              source[name]['instances'] == exported[name]['instances'], arm + ' exact native roundtrip ' + name)
    check(not re.search(r'\berror\s*#', (run / 'run.log').read_text(encoding='utf-8-sig'), re.I), arm + ' no converter error')
    reports[arm] = tables(native_json(run / 'report-raw.json'), 'report')
    logs[arm] = (run / 'model.log').read_text(encoding='utf-8-sig')

pair_delta = {name: {'before': sources['ncuse1'].get(name), 'after': sources['ncuse0'].get(name)}
              for name in sources['ncuse1'].keys() | sources['ncuse0'].keys()
              if sources['ncuse1'].get(name) != sources['ncuse0'].get(name)}
check(pair_delta == diff['from_ncuse1'] and set(pair_delta) == {'ProblemDescription', 'RBDNonCriticalSetItems'},
      'isolated within-panel NC-set USERT contrast')
check(sources['ncuse0']['MaterielOperationalModes'] == sources['ncuse1']['MaterielOperationalModes'] and
      sources['ncuse0']['MissionOperationalModes'] == sources['ncuse1']['MissionOperationalModes'],
      'PAR and BASIC selectors unchanged')

SPEC = {
    'ncuse0': {'faults': [21.5663], 'repair': [(22, 22.5)], 'markers': [44], 'completed': [45]},
    'ncuse1': {'faults': [8.94145, 21.2333, 33.6494],
               'repair': [(10, 10.5), (22, 22.5), (34, 34.5)],
               'markers': [20, 44, 68], 'completed': [21, 45, 69]},
}


def event(log, hour, fragment):
    return any(line.startswith('Time: ' + str(hour) + ' ') and fragment in line
               for line in log.splitlines())


for arm, spec in SPEC.items():
    log = logs[arm]
    for mid, (mission, order, start, end) in enumerate((('BASIC-MISSION', 7, 8, 10),
                                                        ('PAR-MISSION', 19, 20, 22),
                                                        ('BASIC-MISSION', 31, 32, 34))):
        identity = f'<{mission},TEACH-UNIT,0,0,{mid}>'
        check(event(log, order, 'mission ordered: ' + mission) and
              event(log, order, identity + ' mission allocates system: <TEACH-AIR-01,0>') and
              event(log, start, identity + ' mission starting, duration: 2') and
              event(log, end, identity + ' mission success:') and
              event(log, end, identity + ' mission completed:'), arm + f' mission {mid} full success')
        check(identity + ' mission aborted:' not in log, arm + f' mission {mid} no abort')
    for hour in spec['faults']:
        prefix = f'Time: {hour} <TEACH-AIR-01,0> noncritical CM failure mode added'
        block = log.split(prefix, 1)[1].split('Time:', 1)[0] if prefix in log else ''
        check('Failure Mode: FM-POS-B on materiel: <POS-B,0>' in block,
              arm + f' noncritical physical B fault {hour}')
    check(log.count('CM failure mode added') == len(spec['faults']) and 'FM-POS-A' not in log,
          arm + ' exact fault count, no A fault')
    check((not event(log, 8.94145, 'CM failure mode added')) if arm == 'ncuse0' else True,
          arm + ' BASIC B exposure contrast')
    for task_id, (start, end) in enumerate(spec['repair']):
        label = f'system CM task {task_id} on <TEACH-AIR-01,0>'
        check(event(log, start, label + ' started') and event(log, start, label + ' FMID: FM-POS-B') and
              event(log, end, label + ' completed') and event(log, end, 'systems ready: 1'),
              arm + f' postmission half-hour repair {task_id}')
    check('Item demand arrives' not in log, arm + ' no physical stock demand')

for arm, report in reports.items():
    spec = SPEC[arm]
    check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'},
          arm + ' report table set')
    summary = records(report['ResultSummary'])[0]
    for name, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36), ('MTMF', 1), ('STMF', 1),
                           ('MSTF', 1), ('MSUF', 1), ('RSMTMF', 0), ('RSMSTF', 0),
                           ('RSMSUF', 0), ('RSSTMF', 0)):
        check(near(summary[name], expected), arm + ' summary ' + name)
    system = records(report['SystemResults'])
    stock = records(report['StockTotalResults'])
    check(len(system) == len(stock) == 72, arm + ' 72 aligned System/Stock rows')
    for index, (s, t) in enumerate(zip(system, stock)):
        start = index / 2
        end = start + .5
        check(s['STINT'] == t['STINT'] == start and s['ETINT'] == t['ETINT'] == end,
              arm + f' aligned bin {index}')
        reserved = sum(occupancy(a, b, start) for a, b in ((7, 8), (19, 20), (31, 32)))
        flight = sum(occupancy(a, b, start) for a, b in ((8, 10), (20, 22), (32, 34)))
        repair = sum(occupancy(a, b, start) for a, b in spec['repair'])
        expected = {'NSYRY': 1 - reserved - flight - repair, 'NSYMA': reserved + flight,
                    'NSYMO': flight, 'NSYMR': reserved, 'NSYRP': repair, 'NSYUA': repair,
                    'NSYA': 1 - repair, 'FTMO': flight, 'STACC': flight,
                    'NFAIL': sum(start <= f < end for f in spec['faults']),
                    'NREPT': int(index in spec['completed']), 'NSYDT': int(index in spec['markers'])}
        for name, value in expected.items():
            check(near(s[name], value), arm + f' SystemResults {name} bin {index}')
        check((near(s['SYDT'], .5) if index in spec['markers'] else s['SYDT'] is None),
              arm + f' SYDT bin {index}')
        for name in ('NSYMC', 'NSYMP', 'NSYMT', 'NSYMS', 'NSYAL', 'NSYPM', 'NSYTP',
                     'NSYWR', 'NSYWI', 'NSYLA', 'NSYUH', 'NPMT', 'NDAM', 'NPMS',
                     'NROBT', 'NRCFG', 'STREQ', 'STF', 'STLOW', 'SYDTU', 'NSYSW',
                     'NPSTA', 'NPSUC'):
            check(s[name] == 0, arm + f' zero SystemResults {name} bin {index}')
        check(t['PNB'] == 1 and all(v is None or v == 0 for name, v in t.items()
                                   if name not in ('STINT', 'ETINT', 'PNB')),
              arm + f' zero StockTotalResults movement bin {index}')
    check(near(system[-1]['NSYRY'], 1), arm + ' terminal ready aircraft')
    check(near(sum(s['NSYMO'] for s in system) * .5, 6), arm + ' six flight hours')
    check(near(sum(s['NSYRP'] for s in system) * .5, .5 * len(spec['repair'])),
          arm + ' CM work hours')

verdict = {
    'schema': 'simlox-g09-var06-independent-readonly/v1',
    'passed': not failures, 'checks_passed': count - len(failures), 'checks_total': count,
    'decision': ('GO: bounded NC-set USERT 0 versus 1 source-bound native contrast'
                 if not failures else 'NO-GO: independent replay failed'),
    'failures': failures, 'raw_seals': sum(len(c['raw']) for c in closures.values()),
    'runs': {arm: {'source_sha256': sha(CASE / f'{arm}-input.json'),
                   'closure_sha256': sha(run / 'closure.json'),
                   'model_log_sha256': sha(run / 'model.log'),
                   'report_sha256': sha(run / 'report-raw.json')}
             for arm, run in RUNS.items()},
    'observed': {'ncuse0': 'BASIC faults 0; PAR B fault h21.5663 NC; three missions succeed; one half-hour B CM.',
                 'ncuse1': 'BASIC B faults h8.94145 and h33.6494 NC; PAR B h21.2333 NC; three missions succeed; three half-hour B CM tasks.',
                 'terminal': 'One ready aircraft in both arms; no stock demand.'},
    'limits': [
        'One seed and replication, QTYNC1, one omitted POS-B under BASIC, positive B rate and common near-zero A rate.',
        'NCID and usage rates are source/manual/roundtrip-bound; native log does not print selected NCID or rate.',
        'No fractional or above-one NC-set USERT law, other quantities/hierarchies, PM, GUI drawing, or cross-engine parity.'
    ],
}
OUT.write_bytes((json.dumps(verdict, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': verdict['passed'], 'checks_passed': verdict['checks_passed'],
                  'checks_total': count, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
