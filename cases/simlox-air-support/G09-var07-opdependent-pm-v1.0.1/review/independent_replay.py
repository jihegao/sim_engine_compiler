"""Read-only, independent replay of G09.var07 v1.0.1 native evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OUT = Path(__file__).with_name('independent-validation-2026-10-03.json')
RUNS = {arm: CASE / 'runs' / f'g09-var07-{arm}-v101-ssh-20261003-01'
        for arm in ('syshalf', 'sysfull')}
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
    clean = []
    quoted = escaped = False
    for pos, ch in enumerate(raw):
        if quoted:
            clean.append(ch)
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            clean.append(ch)
        elif ch == ',':
            look = pos + 1
            while look < len(raw) and raw[look].isspace():
                look += 1
            if look == len(raw) or raw[look] not in '}]':
                clean.append(ch)
        else:
            clean.append(ch)
    return json.loads(''.join(clean))


def tables(doc, key):
    return {t['name']: t for t in doc[key]['tables']}


def rows(table):
    return [row for instance in table['instances'] for row in instance['rows']]


def records(table):
    columns = [c['name'] for c in table['columns']]
    return [dict(zip(columns, row)) for row in rows(table)]


def close(actual, expected, tol=.0007):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=tol)


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
parent_pkg = ROOT / contract['accepted_parent']['package']
parent_input = parent_pkg / 'use1-input.json'
parent_closure = parent_pkg / 'runs' / 'g09-var04-use1-v101-ssh-20261003-01' / 'closure.json'
pm_pkg = ROOT / contract['accepted_pm_pattern']['package']
pm_input = pm_pkg / 'native-input.json'
pm_closure = pm_pkg / 'runs' / 'd10-multicounter-v100-ssh-20261001-01' / 'closure.json'
diag_pkg = ROOT / contract['excluded_diagnostic']['package']
diag_paths = {arm: (diag_pkg / f'{arm}-input.json',
                    diag_pkg / 'runs' / f'g09-var07-{arm}-v100-ssh-20261003-01' / 'closure.json')
              for arm in RUNS}
for path, expected, label in (
    (parent_input, contract['accepted_parent']['input_sha256'], 'accepted G09 parent input'),
    (parent_closure, contract['accepted_parent']['native_closure_sha256'], 'accepted G09 parent closure'),
    (pm_input, contract['accepted_pm_pattern']['input_sha256'], 'accepted D10 PM donor'),
    (pm_closure, contract['accepted_pm_pattern']['native_closure_sha256'], 'accepted D10 closure'),
    (CASE / 'exact-diff.json', contract['exact_diff_sha256'], 'exact diff'),
):
    check(sha(path) == expected, label + ' SHA-256')
for arm, (input_path, closure_path) in diag_paths.items():
    check(sha(input_path) == contract['excluded_diagnostic']['input_sha256'][arm], arm + ' excluded v1.0.0 source seal')
    check(sha(closure_path) == contract['excluded_diagnostic']['native_closure_sha256'][arm], arm + ' excluded v1.0.0 closure seal')
    old = tables(native_json(input_path), 'model')
    check(records(old['Control'])[0]['ENPM'] == 'N', arm + ' excluded diagnostic had PM disabled')
    old_report = tables(native_json(closure_path.parent / 'report-raw.json'), 'report')
    check(sum(r['NPMS'] for r in records(old_report['SystemResults'])) == 0,
          arm + ' excluded diagnostic NPMS zero')
check(diff['parent_sha256'] == sha(parent_input) and diff['input_sha256'] == contract['input_sha256'],
      'diff SHA bindings')
for kind in ('exe', 'manual', 'dictionary'):
    check(sha(EXTERNAL[kind]) == contract['source'][kind + '_sha256'], kind + ' installed fingerprint')

parent = tables(native_json(parent_input), 'model')
pm_donor = tables(native_json(pm_input), 'model')
sources, reports, logs, closures = {}, {}, {}, {}
for arm, run in RUNS.items():
    input_path = CASE / f'{arm}-input.json'
    source = tables(native_json(input_path), 'model')
    sources[arm] = source
    check(sha(input_path) == contract['input_sha256'][arm], arm + ' frozen source SHA')
    delta = {n: {'before': parent.get(n), 'after': source.get(n)}
             for n in parent.keys() | source.keys() if parent.get(n) != source.get(n)}
    check(delta == diff['from_parent'][arm], arm + ' exact parent business delta')
    check(set(delta) == ({'ProblemDescription', 'Control', 'Tasks', 'MaterielPM', 'PMLocation',
                          'SubTaskType', 'TaskBreakDown', 'FailureMode', 'MaterielOperationalModes'}
                         if arm == 'syshalf' else
                         {'ProblemDescription', 'Control', 'Tasks', 'MaterielPM', 'PMLocation',
                          'SubTaskType', 'TaskBreakDown', 'FailureMode'}), arm + ' parent changed-table set')
    check(records(source['Control'])[0]['ENPM'] == 'Y', arm + ' PM explicitly enabled')
    fm = records(source['FailureMode'])
    check(len(fm) == 2 and {r['FMID']: r['FRQ'] for r in fm} ==
          {'FM-POS-A': 1e-9, 'FM-POS-B': 1e-9}, arm + ' common near-zero ordinary failure rates')
    pm = records(source['MaterielPM'])
    check(len(pm) == 1 and pm[0]['PMID'] == 'SYS-OP15' and pm[0]['OPID'] == 'OPHOURS' and
          pm[0]['PMINT'] == 1.5, arm + ' system OPHOURS PM threshold')
    check(any(r['PMID'] == 'SYS-OP15' and r['STID'] == 'BASE-01'
              for r in records(source['PMLocation'])), arm + ' PM base location')
    check([c['name'] for c in source['MaterielPM']['columns']] ==
          [c['name'] for c in pm_donor['MaterielPM']['columns']] and
          any(r['MID'] == 'TEACH-AIR-01' for r in records(pm_donor['MaterielPM'])),
          arm + ' D10 system-PM table schema reference')
    check(records(pm_donor['MaterielPM'])[0]['OPID'] == 'MISSIONS' and
          any(r['OPID'] == 'OPHOURS' and r['PMINT'] == 3
              for r in records(pm_donor['MaterielPMInterval'])),
          arm + ' D10 donor base MISSIONS and interval OPHOURS provenance')
    modes = records(source['MaterielOperationalModes'])
    root = [r for r in modes if r['MID'] == 'TEACH-AIR-01' and r['OPMID'] == 'G09-SER-OPS']
    par = [r for r in modes if r['MID'] == 'TEACH-AIR-01' and r['OPMID'] == 'G04-OPS']
    check(len(root) == len(par) == 1 and root[0]['USERT'] == (.5 if arm == 'syshalf' else 1) and
          par[0]['USERT'] == 1, arm + ' BASIC source rate and unchanged PAR rate')
    invocation = native_json(run / 'invocation.json')
    closure = native_json(run / 'closure.json')
    closures[arm] = closure
    check(sha(run / 'invocation.json') == closure['invocation_sha256'], arm + ' invocation SHA seal')
    check(invocation['run_id'] == closure['run_id'] == run.name, arm + ' run identity')
    check(invocation['execution_mode'] == 'session0_ssh_cli' and invocation['session_id'] == 0 and
          'sshd.exe' in invocation['ssh_ancestor_names'], arm + ' SSH session0 provenance')
    check(invocation['gui']['pid'] == 13340 and invocation['gui']['session_id'] == 1 and
          invocation['queue_mutex'] == r'Global\SimloxIssue18NativeQueue', arm + ' GUI and queue guard')
    check(invocation['prelife_log_option_before'] == closure['prelife_log_option_after'] == 'NO',
          arm + ' native option restored')
    check(invocation['source_hashes_before'] == closure['source_hashes_before'] ==
          closure['source_hashes_after'], arm + ' source hash stability')
    sealed = {'input': input_path, 'parent': parent_input, 'parent_closure': parent_closure,
              'pm_pattern': pm_input, 'pm_closure': pm_closure,
              'diagnostic_half': diag_paths['syshalf'][0], 'diagnostic_full': diag_paths['sysfull'][0],
              'diagnostic_half_closure': diag_paths['syshalf'][1],
              'diagnostic_full_closure': diag_paths['sysfull'][1],
              'contract': CASE / 'contract.json', 'exact_diff': CASE / 'exact-diff.json',
              'builder': CASE / 'build.py', 'diff_builder': CASE / 'describe_diff.py',
              'checker': CASE / 'check_roundtrip.py', 'runner': CASE / 'run_native_ssh.ps1', **EXTERNAL}
    for name, path in sealed.items():
        check(sha(path) == closure['source_hashes_before'][name], arm + ' frozen seal ' + name)
    check(len(closure['raw']) == 13, arm + ' thirteen raw SHA seals')
    for name, meta in closure['raw'].items():
        path = run / name
        check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'],
              arm + ' raw seal ' + name)
    steps = native_json(run / 'steps.json')
    check([s['name'] for s in steps] == ['import', 'export', 'calc', 'jsonreport', 'check_import_export'],
          arm + ' five steps')
    for step in steps:
        check(step['exit_code'] == 0 and step['status'] == 'completed' and step['gui_preserved'],
              arm + ' guarded ' + step['name'])
    check([s['arguments'] for s in steps[:4]] == [c['args'] for c in invocation['planned_commands']],
          arm + ' sealed CLI arguments')
    cv = closure['conversion']
    check(cv['errors'] == cv['notes'] == 0 and cv['warning_codes'] == ['108'] and cv['calc_exit_code'] == 0,
          arm + ' zero error diagnostics')
    check(closure['native_outcome'] == 'zero_error_reviewed_warnings' and closure['sxo_bytes'] > 4 and
          closure['report_present'], arm + ' usable SXO/report')
    check(sha(run / 'input.json') == sha(input_path), arm + ' native input copy')
    check(not re.search(r'\berror\s*#', (run / 'run.log').read_text(encoding='utf-8-sig'), re.I),
          arm + ' no converter error text')
    exported = tables(native_json(run / 'roundtrip-raw.json'), 'model')
    populated = [name for name, table in source.items() if rows(table)]
    check(len(populated) == 30, arm + ' thirty row-containing tables')
    for name in populated:
        check(name in exported and source[name]['columns'] == exported[name]['columns'] and
              source[name]['instances'] == exported[name]['instances'], arm + ' exact roundtrip ' + name)
    reports[arm] = tables(native_json(run / 'report-raw.json'), 'report')
    logs[arm] = (run / 'model.log').read_text(encoding='utf-8-sig')

between = {name: {'before': sources['sysfull'].get(name), 'after': sources['syshalf'].get(name)}
           for name in sources['sysfull'].keys() | sources['syshalf'].keys()
           if sources['sysfull'].get(name) != sources['syshalf'].get(name)}
check(between == diff['from_sysfull'] and set(between) == {'ProblemDescription', 'MaterielOperationalModes'},
      'isolated BASIC system usage pair delta')
for name in ('Control', 'FailureMode', 'MaterielPM', 'PMLocation', 'Tasks', 'TaskBreakDown',
             'SubTaskType', 'MissionOperationalModes'):
    check(sources['syshalf'][name] == sources['sysfull'][name], 'paired common ' + name)

SPEC = {'syshalf': {'pms': [(22, 23)], 'markers': [41], 'completions': [46]},
        'sysfull': {'pms': [(10, 11), (22, 23), (34, 35)],
                    'markers': [19, 43, 67], 'completions': [22, 46, 70]}}


def event(log, hour, fragment):
    return any(line.startswith('Time: ' + str(hour) + ' ') and fragment in line
               for line in log.splitlines())


for arm, spec in SPEC.items():
    log = logs[arm]
    for index, (mission, ordered, launched, returned) in enumerate(
            (('BASIC-MISSION', 7, 8, 10), ('PAR-MISSION', 19, 20, 22),
             ('BASIC-MISSION', 31, 32, 34))):
        ident = f'<{mission},TEACH-UNIT,0,0,{index}>'
        check(event(log, ordered, 'mission ordered: ' + mission) and
              event(log, ordered, ident + ' mission allocates system: <TEACH-AIR-01,0>') and
              event(log, launched, ident + ' mission starting, duration: 2') and
              event(log, returned, ident + ' mission success:') and
              event(log, returned, ident + ' mission completed:') and
              ident + ' mission aborted:' not in log, arm + f' mission {index} identity/success')
    check('CM failure mode added' not in log and 'system CM task' not in log,
          arm + ' no ordinary failure or CM')
    check(log.count('system PM task ') > 0 and
          len(re.findall(r'^Time: [0-9.]+  system PM task \d+ on <TEACH-AIR-01,0> started$',
                         log, re.M)) == len(spec['pms']), arm + ' exact PM task count')
    for task, (start, end) in enumerate(spec['pms']):
        label = f'system PM task {task} on <TEACH-AIR-01,0>'
        sub = f'subtask {task} seqno 1 within {label}'
        check(event(log, start, label + ' started') and event(log, start, label + ' PMID: SYS-OP15') and
              event(log, start, sub + ' starts performing, planned to last for 1 hours') and
              event(log, end, sub + ' completed') and event(log, end, label + ' completed') and
              event(log, end, 'systems ready: 1'), arm + f' one-hour system PM {task}')
    check('Item demand arrives' not in log, arm + ' no stock demand')

for arm, report in reports.items():
    spec = SPEC[arm]
    check(set(report) == {'ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults'},
          arm + ' report table set')
    summary = records(report['ResultSummary'])[0]
    for field, expected in (('NREP', 1), ('RTILW', 0), ('RTIUP', 36), ('MTMF', 1), ('STMF', 1),
                            ('MSTF', 1), ('MSUF', 1), ('RSMTMF', 0), ('RSMSTF', 0),
                            ('RSMSUF', 0), ('RSSTMF', 0)):
        check(close(summary[field], expected), arm + ' summary ' + field)
    system = records(report['SystemResults'])
    stock = records(report['StockTotalResults'])
    check(len(system) == len(stock) == 72, arm + ' 72 aligned report rows')
    for i, (s, t) in enumerate(zip(system, stock)):
        start, end = i / 2, (i + 1) / 2
        check(s['STINT'] == t['STINT'] == start and s['ETINT'] == t['ETINT'] == end,
              arm + f' aligned bin {i}')
        reserved = sum(occupancy(a, b, start) for a, b in ((7, 8), (19, 20), (31, 32)))
        flight = sum(occupancy(a, b, start) for a, b in ((8, 10), (20, 22), (32, 34)))
        pm = sum(occupancy(a, b, start) for a, b in spec['pms'])
        expected = {'NSYRY': 1 - reserved - flight - pm, 'NSYMA': reserved + flight,
                    'NSYMO': flight, 'NSYMR': reserved, 'NSYUA': pm, 'NSYPM': pm,
                    'NSYA': 1 - pm, 'FTMO': flight, 'STACC': flight,
                    'NPMS': int(i in spec['markers']), 'NPMT': int(i in spec['completions']),
                    'NSYDT': int(i in [int(a * 2) for a, _ in spec['pms']])}
        for name, value in expected.items():
            check(close(s[name], value), arm + f' SystemResults {name} bin {i}')
        check((close(s['SYDT'], 1) if i in [int(a * 2) for a, _ in spec['pms']]
               else s['SYDT'] is None), arm + f' PM downtime marker bin {i}')
        for name in ('NSYMC', 'NSYMP', 'NSYMT', 'NSYMS', 'NSYAL', 'NSYRP', 'NSYTP',
                     'NSYWR', 'NSYWI', 'NSYLA', 'NSYUH', 'NDAM', 'NFAIL', 'NREPT',
                     'NROBT', 'NRCFG', 'STREQ', 'STF', 'STLOW', 'SYDTU', 'NSYSW',
                     'NPSTA', 'NPSUC'):
            check(s[name] == 0, arm + f' zero SystemResults {name} bin {i}')
        check(t['PNB'] == 1 and all(v is None or v == 0 for name, v in t.items()
                                   if name not in ('STINT', 'ETINT', 'PNB')),
              arm + f' unchanged StockTotalResults bin {i}')
    check(close(sum(s['NSYMO'] for s in system) * .5, 6), arm + ' six aircraft flight-hours')
    check(close(sum(s['NSYPM'] for s in system) * .5, len(spec['pms'])), arm + ' integrated PM hours')
    check(close(system[-1]['NSYRY'], 1), arm + ' terminal ready aircraft')

verdict = {
    'schema': 'simlox-g09-var07-v101-independent-readonly/v1',
    'passed': not failures, 'checks_passed': count - len(failures), 'checks_total': count,
    'decision': ('GO: bounded BASIC system USERT/OPHOURS PM timing contrast'
                 if not failures else 'NO-GO: independent replay failed'),
    'failures': failures, 'raw_seals': sum(len(c['raw']) for c in closures.values()),
    'runs': {arm: {'source_sha256': sha(CASE / f'{arm}-input.json'),
                   'closure_sha256': sha(run / 'closure.json'),
                   'model_log_sha256': sha(run / 'model.log'),
                   'report_sha256': sha(run / 'report-raw.json')}
             for arm, run in RUNS.items()},
    'observed': {'syshalf': 'First SYS-OP15 task h22-23; one PM task; three successful missions.',
                 'sysfull': 'SYS-OP15 tasks h10-11, h22-23, h34-35; three PM tasks; three successful missions.',
                 'report': 'NPMS appears in the in-flight threshold bin, before task start; PM work and completion are distinct report entries.'},
    'finding': 'Frozen contract says D10.var02 donated a system OPHOURS MaterielPM row. The pinned donor has a base MISSIONS=2 MaterielPM row and a separate OPHOURS=3 MaterielPMInterval row. G09 authors a new base OPHOURS=1.5 MaterielPM row; donor supplies PM schema and native control precedent.',
    'limits': [
        'One system OPHOURS1.5 PM, BASIC system USERT0.5/1, PAR USERT1, one seed and aircraft through h36.',
        'Accumulated counter and winning trigger are not printed; interpretation is source/manual/outcome-bound.',
        'No item or NC-set PM, multiple counters, other thresholds, rate law, GUI visuals, or cross-engine parity.',
        'v1.0.0 with ENPM=N is an excluded diagnostic, not evidence of PM behavior.'
    ],
}
OUT.write_bytes((json.dumps(verdict, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': verdict['passed'], 'checks_passed': verdict['checks_passed'],
                  'checks_total': count, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
