"""Independent, read-only replay of the sealed K01.var04 native run."""
import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'k01-var04-duration-v100-ssh-20261004-01'
PARENT_RUN = Path(r'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A01\a01-bound-final-20260927-03')
OUT = CASE / 'review' / 'independent-verdict.json'
checks = 0
failures = []


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def native_json(path):
    raw = path.read_text(encoding='utf-8-sig')
    out = []
    quoted = escaped = False
    for i, ch in enumerate(raw):
        if quoted:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == ',':
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j < len(raw) and raw[j] in ']}':
                continue
            out.append(ch)
        else:
            out.append(ch)
    return json.loads(''.join(out))


def tables(doc, key):
    return {t['name']: t for t in doc[key]['tables']}


def rows(table):
    return [r for instance in table['instances'] for r in instance['rows']]


def report_rows(table):
    names = [c['name'] for c in table['columns']]
    return [dict(zip(names, r)) for r in rows(table)]


def event_lines(log, phrase):
    return [line for line in log.splitlines() if phrase in line]


def run():
    contract = read(CASE / 'contract.json')
    diff = read(CASE / 'exact-diff.json')
    parent_input = ROOT / 'A01-single-aircraft-single-mission' / 'native-input.json'
    child_input = CASE / 'native-input.json'
    check(contract['parent']['input_sha256'] == sha(parent_input), 'accepted A01 source SHA')
    check(contract['child_input_sha256'] == sha(child_input), 'child source SHA')
    check(contract['parent']['accepted_closure_sha256'] == sha(PARENT_RUN / 'closure.json'), 'accepted closure SHA')
    check(sha(PARENT_RUN / 'model.log') == '6337dc631e574eb9fab1eb24c45b4a3e1568d7e645282051c234a032591887ed', 'accepted parent log SHA')
    check(sha(PARENT_RUN / 'report-raw.json') == 'b9b7d970e7f12763f0098eb2d2c546cc2ed2b68792840e74f2175fcd4ca14099', 'accepted parent report SHA')
    check(contract['expected_converter']['warning_codes_in_order'] == [108, 126], 'frozen warnings')
    check(len(diff['changed_cells']) == 2 and diff['other_cells'] == 'unchanged', 'declared two-cell delta')
    parent = read(parent_input)
    child = read(child_input)
    ptab, ctab = tables(parent, 'model'), tables(child, 'model')
    check(ptab.keys() == ctab.keys(), 'same table topology')
    check(parent['model']['database_version'] == child['model']['database_version'], 'same database version')
    for name in ptab:
        check(ptab[name]['columns'] == ctab[name]['columns'], f'{name} column schema')
        p_rows, c_rows = rows(ptab[name]), rows(ctab[name])
        check(len(p_rows) == len(c_rows), f'{name} row count')
        for i, (a, b) in enumerate(zip(p_rows, c_rows)):
            for col, old, new in zip((x['name'] for x in ptab[name]['columns']), a, b):
                expected = ((name == 'ProblemDescription' and i == 0 and col == 'PDESC') or
                            (name == 'MissionType' and i == 0 and col == 'DURN'))
                check((old != new) == expected, f'{name}[{i}].{col} exact delta')
                if expected:
                    cell = next(x for x in diff['changed_cells'] if x['table'] == name)
                    check(old == cell['from'] and new == cell['to'], f'{name}.{col} declared values')
    check(len([t for t in ctab.values() if rows(t)]) == 13, '13 row-containing source tables')
    check(len([t for t in ctab.values() if any(v is not None for r in rows(t) for v in r)]) == 10, '10 substantive source tables')

    closure = read(RUN / 'closure.json')
    invocation = read(RUN / 'invocation.json')
    steps = read(RUN / 'steps.json')
    check(closure['run_id'] == RUN.name and invocation['run_id'] == RUN.name, 'run identity')
    check(closure['error'] is None, 'closure has no error')
    check(closure['invocation_sha256'] == sha(RUN / 'invocation.json'), 'invocation SHA seal')
    check(closure['source_hashes_before'] == closure['source_hashes_after'] == invocation['source_hashes_before'], 'stable source hashes')
    source_files = {
        'native_input': child_input,
        'contract': CASE / 'contract.json',
        'exact_diff': CASE / 'exact-diff.json',
        'accepted_parent': parent_input,
        'accepted_parent_closure': PARENT_RUN / 'closure.json',
        'accepted_parent_signoff': ROOT / 'A01-single-aircraft-single-mission' / 'cli-scope-signoff-2026-09-29.md',
        'accepted_parent_report': PARENT_RUN / 'report-raw.json',
        'accepted_parent_log': PARENT_RUN / 'model.log',
        'build.py': CASE / 'build.py',
        'check_roundtrip.py': CASE / 'check_roundtrip.py',
        'run_native_ssh.ps1': CASE / 'run_native_ssh.ps1',
        'exe': Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
        'manual': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
        'dictionary': Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),
        'python': Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    }
    for key, path in source_files.items():
        check(sha(path) == closure['source_hashes_before'][key], f'{key} source seal')
    check(invocation['execution_mode'] == 'ssh_cli_v1' and invocation['session_id'] == 0, 'session-0 SSH')
    check('sshd.exe' in invocation['ssh_ancestor_names'], 'sshd ancestry')
    check(invocation['queue_mutex'] == 'Global\\SimloxIssue18NativeQueue', 'host mutex')
    check(invocation['gui']['pid'] == 13340 and invocation['gui']['session_id'] > 0, 'preserved GUI identity')
    check([s['name'] for s in steps] == ['import', 'export', 'calc', 'jsonreport', 'check_import_export'], 'five ordered steps')
    for s in steps:
        check(s['exit_code'] == 0 and s['status'] == 'completed' and s['error'] is None, f"{s['name']} completed")
        if s['name'] != 'check_import_export':
            check(s['gui_preserved'] is True, f"{s['name']} GUI preserved")
    check(len(closure['raw']) == 12, '12 sealed raw files')
    for filename, seal in sorted(closure['raw'].items()):
        path = RUN / filename
        check(path.stat().st_size == seal['bytes'], f'{filename} size')
        check(sha(path) == seal['sha256'], f'{filename} SHA')
    check(sha(RUN / 'input.json') == sha(child_input), 'run input exact child source')
    roundtrip = tables(native_json(RUN / 'roundtrip-raw.json'), 'model')
    for name, authored in ctab.items():
        if rows(authored):
            exported = roundtrip.get(name)
            check(exported is not None, f'{name} exported')
            if exported is not None:
                check(authored['columns'] == exported['columns'], f'{name} roundtrip columns')
                check(rows(authored) == rows(exported), f'{name} roundtrip rows')
    check('Import completed!' in (RUN / 'import.log').read_text(encoding='utf-8-sig'), 'import completion')
    check('Export completed!' in (RUN / 'export.log').read_text(encoding='utf-8-sig'), 'export completion')
    runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig')
    check('Input conversion completed. Errors: 0, Warnings: 2, Notes: 0' in runlog, 'zero converter errors')
    check([int(x) for x in re.findall(r'\(warning #(\d+)\)', runlog)] == [108, 126], 'classified warnings')
    check(not re.search(r'\((?:error|notice) #', runlog), 'no other converter diagnostics')
    check((RUN / 'model.sxo').stat().st_size > 4, 'valid nontrivial SXO')

    child_log = (RUN / 'model.log').read_text(encoding='utf-8-sig')
    parent_log = (PARENT_RUN / 'model.log').read_text(encoding='utf-8-sig')
    identity = '<BASIC-MISSION,TEACH-UNIT,0,0,0>'
    phrases = [
        ('Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION', 1),
        (f'Time: 7 {identity} mission created:', 1),
        (f'Time: 7 {identity} mission activated, systems requested: 1', 1),
        (f'Time: 7 {identity} mission allocates system: <TEACH-AIR-01,0>', 1),
        (f'Time: 8 {identity} mission starting, duration: 3 : <TEACH-AIR-01,0>', 1),
        (f'Time: 11 {identity} mission success:', 1),
        (f'Time: 11 {identity} mission completed: <TEACH-AIR-01,0>', 1),
        ('Time: 11 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, mission success,', 1),
    ]
    for phrase, count in phrases:
        check(child_log.count(phrase) == count, f'child event {phrase}')
    check(f'Time: 8 {identity} mission starting, duration: 2' in parent_log, 'parent launch/duration')
    check(f'Time: 10 {identity} mission success:' in parent_log, 'parent success h10')
    check(f'Time: 10 {identity} mission completed:' in parent_log, 'parent completion h10')
    for forbidden in ('mission cancelled:', 'mission canceled:', 'mission aborted:', 'aborts its mission', 'critical random failure added'):
        check(forbidden not in child_log, f'absent {forbidden}')

    child_report = tables(native_json(RUN / 'report-raw.json'), 'report')
    parent_report = tables(native_json(PARENT_RUN / 'report-raw.json'), 'report')
    check(child_report.keys() == parent_report.keys(), 'report table set')
    for name in ('ResultSummary', 'StockTotalResults'):
        check(child_report[name]['columns'] == parent_report[name]['columns'], f'{name} schema')
        a, b = report_rows(child_report[name]), report_rows(parent_report[name])
        check(len(a) == len(b) == (72 if name == 'StockTotalResults' else 1), f'{name} row count')
        for i, (x, y) in enumerate(zip(a, b)):
            for key in x:
                check(x[key] == y[key], f'{name}[{i}].{key} parent parity')
    sys_child = report_rows(child_report['SystemResults'])
    sys_parent = report_rows(parent_report['SystemResults'])
    check(len(sys_child) == len(sys_parent) == 72, '72 SystemResults bins')
    check(child_report['SystemResults']['columns'] == parent_report['SystemResults']['columns'], 'SystemResults schema')
    shifted = {'NSYRY': (1, 0), 'NSYMA': (0, 1), 'NSYMO': (0, 1), 'FTMO': (0, 1), 'STACC': (0, 1)}
    for i, (x, y) in enumerate(zip(sys_child, sys_parent)):
        check(abs(x['STINT'] - i * .5) < 1e-8 and abs(x['ETINT'] - (i + 1) * .5) < 1e-8, f'SystemResults[{i}] interval')
        for key in x:
            if i in (20, 21) and key in shifted:
                check((y[key], x[key]) == shifted[key], f'SystemResults[{i}].{key} shifted occupancy')
            else:
                check(x[key] == y[key], f'SystemResults[{i}].{key} parent parity')
    check(sum(row['NSYMO'] * .5 for row in sys_child) == 3, 'three child flight hours')
    check(sum(row['NSYMO'] * .5 for row in sys_parent) == 2, 'two parent flight hours')
    check(sum(row['NSYRY'] * .5 for row in sys_child) == 32, '32 child ready hours')
    check(sum(row['NSYRY'] * .5 for row in sys_parent) == 33, '33 parent ready hours')
    check(sys_child[-1]['NSYRY'] == 1 and sys_child[-1]['NSYMO'] == 0, 'ready terminal bin')
    summary = report_rows(child_report['ResultSummary'])[0]
    check(summary['NREP'] == 1 and summary['MTMF'] == summary['MSTF'] == summary['MSUF'] == summary['STMF'] == 1, 'one successful mission summary')
    check(all(row['NBO'] == 0 for row in report_rows(child_report['StockTotalResults'])), 'zero stock backorders')
    check(report_rows(child_report['ProblemDescription'])[0]['PDESC'] == diff['changed_cells'][0]['to'], 'report description')

    return {
        'schema': 'k01-var04-independent-readonly/v1',
        'passed': not failures,
        'verdict': 'GO_BOUNDED' if not failures else 'NO_GO',
        'checks_passed': checks - len(failures),
        'checks_total': checks,
        'failures': failures,
        'run_id': RUN.name,
        'source_sha256': sha(child_input),
        'closure_sha256': sha(RUN / 'closure.json'),
        'report_sha256': sha(RUN / 'report-raw.json'),
        'limits': [
            'Only the installed SIMLOX 2017 CLI and this one A01-derived 36-hour, single-aircraft pair are observed.',
            'K01 Table/Model/Profile views, SXT template authoring, hidden/default/null GUI rendering and cross-engine behavior remain unverified.',
            'A bounded K01.var04 source diff does not automatically satisfy the full K01 prerequisite for K02-K08.',
        ],
    }


if __name__ == '__main__':
    try:
        result = run()
    except Exception as exc:
        result = {'schema': 'k01-var04-independent-readonly/v1', 'passed': False,
                  'verdict': 'NO_GO', 'checks_passed': checks - len(failures),
                  'checks_total': checks + 1, 'failures': failures + [f'checker exception: {exc}']}
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'verdict': result['verdict'], 'checks_passed': result['checks_passed'],
                      'checks_total': result['checks_total'], 'failures': result['failures']}, sort_keys=True))
    raise SystemExit(0 if result['passed'] else 1)
