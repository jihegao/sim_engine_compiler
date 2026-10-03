"""Independent, read-only replay of the G10.var08 quantity overflow rejection."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / 'runs' / 'g10-var08-qty-overflow-v100-ssh-20261003-01'
PARENT_DIR = ROOT / 'G10-var01-series-two-item-v1.0.1'
PARENT = PARENT_DIR / 'native-input.json'
PARENT_RUN = PARENT_DIR / 'runs' / 'g10-var01-series-two-item-v101-ssh-20261003-01'
SOURCE = CASE / 'native-input.json'
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
check(sha(PARENT) == contract['parent']['input_sha256'], 'accepted parent input SHA')
check(sha(PARENT_RUN / 'closure.json') == contract['parent']['native_closure_sha256'], 'accepted parent closure SHA')
check(sha(PARENT_DIR / 'cli-scope-signoff-2026-10-03.md') == contract['parent']['signoff_sha256'], 'accepted parent signoff SHA')
check(sha(SOURCE) == contract['native_input_sha256'], 'frozen child source SHA')
check(sha(CASE / 'exact-diff.json') == contract['exact_diff_sha256'], 'frozen diff SHA')
check(sha(EXTERNAL['manual']) == contract['source']['manual_pdf_sha256'], 'manual SHA')
check(sha(EXTERNAL['dictionary']) == contract['source']['installed_dictionary_sha256'], 'dictionary SHA')
check(sha(EXTERNAL['simlox_exe']) == 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0', 'installed executable SHA')
check(diff['parent_sha256'] == sha(PARENT) and diff['child_sha256'] == sha(SOURCE), 'diff source bindings')
parent, child = tables(PARENT, 'model'), tables(SOURCE, 'model')
changed = {name for name in parent if parent[name] != child[name]}
check(set(parent) == set(child) and changed == set(diff['changed_tables']) == {'ProblemDescription', 'RedundancyLink'}, 'only two source tables change')
for name in set(parent)-changed:
    check(parent[name] == child[name], 'unchanged table ' + name)
links_before, links_after = parent['RedundancyLink'], child['RedundancyLink']
check([c['name'] for c in links_after['columns']] == diff['link_columns'] and rows(links_before) == diff['link_before'] and rows(links_after) == diff['link_after'] and links_before['columns'] == links_after['columns'], 'exact RedundancyLink one-field delta')
red = records(child['Redundancy'])[0]
check(red['RLID'] == 'G10-SER-LINK' and red['NRL'] == diff['nrl'] == 2 and red['ACPA'] == 'ACTIVE', 'unchanged ACTIVE two-link source')
installed = [r for r in records(child['ItemStructure']) if r['IID'] == 'TEACH-LRU-01' and r['MID'] == 'TEACH-AIR-01']
check(len(installed) == 1 and installed[0]['QTYPM'] == diff['installed_lru_qtypm'] == 2, 'two installed LRU positions')
link = {r['IID']: r['QTYPL'] for r in records(child['RedundancyLink'])}
check(link == {'TEACH-LRU-01': 2, 'TEACH-AUX-01': 1} and diff['valid_total_lru'] == 2 and diff['invalid_total_lru'] == link['TEACH-LRU-01']*red['NRL'] == 4, 'LRU link quantity overflow 4 > 2')
dictionary = EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
check([line.split(';')[2] for line in dictionary.splitlines() if line.startswith('RedundancyLink;')] == [c['name'] for c in links_after['columns']], 'installed link schema')

inv, closure = load(RUN / 'invocation.json'), load(RUN / 'closure.json')
check(inv['run_id'] == closure['run_id'] == RUN.name and closure['error'] is None, 'run identity and closure')
check(sha(RUN / 'invocation.json') == closure['invocation_sha256'], 'invocation SHA seal')
check(inv['input_sha256'] == sha(SOURCE) == sha(RUN / 'input.json') and inv['parent_sha256'] == sha(PARENT) and inv['contract_sha256'] == sha(CASE / 'contract.json'), 'run input/parent/contract pins')
check(inv['execution_mode'] == 'ssh_cli_v1' and inv['session_id'] == 0 and inv['ssh_connection_present'] and 'sshd.exe' in inv['ssh_ancestor_names'], 'SSH session zero')
check(inv['queue_mutex'] == r'Global\SimloxIssue18NativeQueue' and inv['gui']['pid'] == 13340 and inv['gui']['session_id'] == 1, 'serial queue and preserved GUI identity')
check(inv['source_hashes_before'] == closure['source_hashes_before'] == closure['source_hashes_after'], 'before/after source stability')
paths = {'input': SOURCE, 'parent': PARENT, 'parent_signoff': PARENT_DIR / 'cli-scope-signoff-2026-10-03.md', 'parent_closure': PARENT_RUN / 'closure.json', 'manual': EXTERNAL['manual'], 'dictionary': EXTERNAL['dictionary'], 'contract': CASE / 'contract.json', 'builder': CASE / 'build.py', 'exact_diff': CASE / 'exact-diff.json', 'diff_checker': CASE / 'describe_diff.py', 'checker': CASE / 'check_roundtrip.py', 'python': EXTERNAL['python'], 'runner_script': CASE / 'run_native_ssh.ps1', 'simlox_exe': EXTERNAL['simlox_exe']}
for name, path in paths.items():
    check(sha(path) == closure['source_hashes_before'][name], 'source seal ' + name)
check(len(closure['raw']) == 9, 'nine sealed raw files')
for name, meta in closure['raw'].items():
    path = RUN / name
    check(path.exists() and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'], 'raw seal ' + name)
steps = load(RUN / 'steps.json')
check([step['name'] for step in steps] == ['import', 'export', 'calc', 'check_import_export'], 'negative four-step route')
for step in steps:
    check(step['exit_code'] == 0 and step['gui_preserved'] and step['error'] is None and step['status'] == ('calc_observed' if step['name'] == 'calc' else 'completed'), 'guarded step ' + step['name'])
check([step['arguments'] for step in steps[:3]] == [command['arguments'] for command in inv['planned_commands']], 'planned native arguments')
export = tables(RUN / 'roundtrip-raw.json', 'model')
populated = [name for name, table in child.items() if rows(table)]
check(len(populated) == 23, '23 populated authored tables')
for name in populated:
    check(name in export and child[name]['columns'] == export[name]['columns'] and child[name]['instances'] == export[name]['instances'], 'exact populated-table roundtrip ' + name)
check(records(export['RedundancyLink']) == records(links_after), 'native export preserves invalid LRU QTYPL2')
runlog = (RUN / 'run.log').read_text(encoding='utf-8-sig')
error = 'Form: System\nrec 1: (error #283) Total number of the item in redundancies exceeds the number of available in the system: TEACH-LRU-01'
check(error in runlog.replace('\r\n', '\n'), 'exact relevant error #283 and item name')
check('Input conversion completed. Errors: 1, Warnings: 1, Notes: 0' in runlog and re.findall(r'warning #(\d+)', runlog) == ['108'] and re.findall(r'error #(\d+)', runlog) == ['283'], 'one error, only warning108')
check((RUN / 'model.sxo').stat().st_size == 4, 'invalid four-byte SXO')
check(not (RUN / 'model.log').exists() and not (RUN / 'report-raw.json').exists() and not (RUN / 'report-export.log').exists(), 'no simulation event log or report')
check('jsonreport' not in [step['name'] for step in steps], 'no report export attempted for invalid conversion')

result = {
    'schema': 'simlox-g10-var08-independent-readonly/v1',
    'passed': not failures, 'verdict': 'GO' if not failures else 'NO-GO',
    'checks_passed': count-len(failures), 'checks_total': count, 'failures': failures,
    'source_sha256': sha(SOURCE), 'closure_sha256': sha(RUN / 'closure.json'),
    'run_log_sha256': sha(RUN / 'run.log'), 'raw_seals': len(closure['raw']),
    'observed': 'For one ACTIVE two-link series redundancy, authored LRU QTYPL2 with NRL2 exceeds installed QTYPM2. Native import/export preserves the source, then calculation emits System error #283 naming TEACH-LRU-01, one conversion error, warning108, four-byte SXO and no simulation report.',
    'limits': [
        'Bounded converter rejection only, on one installed SIMLOX executable and one item type; no simulation behavior is accepted from this invalid SXO.',
        'The valid boundary is the previously accepted parent run, not a new simultaneous paired control.',
        'Other quantity ratios, error precedence, PASSIVE topology, GUI-only behavior and cross-engine parity remain unverified.'
    ],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'], 'checks_total': count, 'failures': failures, 'output': str(OUT)}))
raise SystemExit(0 if not failures else 1)
