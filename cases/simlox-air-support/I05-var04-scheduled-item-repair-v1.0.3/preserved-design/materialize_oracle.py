"""Prospective I05.var04 contract materializer; PURE only, no SIMLOX or accepted checker.

This creates a fixed child input and finite log/report predicate maps before case
construction.  It never consumes a child run.  Original captures and independent
review are required before these outputs can authorize construction.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).resolve().parent
OUT = REPO / 'tmp/e05-i05-var04-oracle-materialization-v101-20261009-01'
PARENT = REPO / 'cases/simlox-air-support/E05-local-repair-reissue-v1.0.0'
INPUT = PARENT / 'native-input.json'
EXPORT = PARENT / 'runs/e05-v100-ssh-20260929-01/roundtrip-raw.json'
LOG = PARENT / 'runs/e05-v100-ssh-20260929-01/model.log'
REPORT = PARENT / 'runs/e05-v100-ssh-20260929-01/report-raw.json'
PINS = {
    INPUT: (43690, 'ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca'),
    EXPORT: (57986, '896387a14791dd6f14ceec9acf6398beca981656fc0656019e7849df2af79b21'),
    LOG: (18758, '3ed9e6a5fc2d66dd8eb5fa4f111bc3baa127dfbfc40aadac639ed55e7f8701f8'),
    REPORT: (104356, 'fcf9a124546e77fb96871b5bf4b5e111774c00616bfed69c19ad7f1b6c08b4bf'),
}
# Filled after the three governing specs are reviewed. This is a hard stop.
SPEC_PINS = {
    'source-delta.json': (5997, 'eb0148601892353a2ebfb1cf43a1a76fc3ac746f2f4ed20d5fb4266d9990bcd8'),
    'event-oracle.json': (6187, '5ad98484b1a926fd8f66d9d9e32e56c07bcaa6a98f3911a7d9ddfad66b064f9b'),
    'report-oracle.json': (6928, 'b340d16af58c78f711d6f0e20d5158d77d206464d4d580e379447d462c2f6167'),
}
NATIVE_TRAILING_COMMA = b',\r\n      ]'


def no_reparse(path: Path) -> None:
    target = path.resolve(strict=False)
    assert target == path.absolute(), ('path aliases or reparse', path, target)
    for part in (path, *path.parents):
        if part.exists():
            assert not part.is_symlink(), ('symlink', part)
            assert not (hasattr(part, 'is_junction') and part.is_junction()), ('junction', part)
            assert not (getattr(part.stat(), 'st_file_attributes', 0) & 0x400), ('reparse', part)


def pinned(path: Path, pair: tuple[int, str]) -> bytes:
    no_reparse(path)
    data = path.read_bytes()
    assert len(data) == pair[0] and hashlib.sha256(data).hexdigest() == pair[1], ('pin', path)
    return data


def strict_json(data: bytes) -> object:
    assert not data.startswith(b'\xef\xbb\xbf'), 'BOM'
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, ('duplicate key', key)
            result[key] = value
        return result
    def constant(value):
        raise AssertionError(('nonfinite', value))
    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)


def load_specs() -> dict[str, dict]:
    result = {}
    for name, pair in SPEC_PINS.items():
        assert pair is not None, ('unfrozen spec pin', name)
        result[name] = strict_json(pinned(SPEC / name, pair))
    return result


def candidate_input(original: dict, source: dict) -> dict:
    base = original['model']
    assert set(original) == {'model'} and set(base) == {'database_version', 'tables'}
    assert base['database_version'] == 20160627 and len(base['tables']) == 31
    assert base['tables'][11]['name'] == 'ItemRepair'
    assert base['tables'][12]['name'] == 'ItemReorder'
    item = base['tables'][11]
    assert len(item['instances']) == 1 and len(item['instances'][0]['rows']) == 1
    row = item['instances'][0]['rows'][0]
    assert row[:6] == ['TEACH-LRU-01', 'BASE-01', 1, 0, 1, 1]
    assert all(value is None for value in row[6:])
    model = copy.deepcopy(original)
    table = {'name': source['new_table']['name'], 'columns': copy.deepcopy(source['new_table']['column_metadata']), 'instances': copy.deepcopy(source['new_table']['instances'])}
    assert table['name'] == 'ChangesItemRepair'
    assert len(table['columns']) == 10 and len(table['instances'][0]['rows'][0]) == 10
    assert table['instances'][0]['rows'][0] == ['TEACH-LRU-01', 'BASE-01', 5.0, 1.5, 0.0, 1.0, 1.0, None, None, None]
    model['model']['tables'].insert(12, table)
    assert len(model['model']['tables']) == 32
    assert sum(bool(i['rows']) for t in model['model']['tables'] for i in t['instances']) == 21
    assert sum(len(i['rows']) * len(t['columns']) for t in model['model']['tables'] for i in t['instances']) == 284
    assert model['model']['tables'][:12] == base['tables'][:12]
    assert model['model']['tables'][13:] == base['tables'][12:]
    return model


# Explicit physical-line numbering is one based. The parent source supplies the
# immutable text skeleton; these ranges declare every permitted clock relocation.
CLOCK_RANGES = (
    (22, 28, 'cycle0.failure'), (29, 53, 'cycle0.arrival'),
    (54, 66, 'cycle0.item_start'), (67, 73, 'cycle0.system_ready'),
    (74, 79, 'cycle0.restock'),
    (94, 99, 'cycle1.failure'), (100, 124, 'cycle1.arrival'),
    (125, 137, 'cycle1.item_start'), (138, 144, 'cycle1.system_ready'),
    (145, 150, 'cycle1.restock'),
    (165, 171, 'cycle2.failure'), (172, 196, 'cycle2.arrival'),
    (197, 209, 'cycle2.item_start'), (210, 216, 'cycle2.system_ready'),
    (217, 222, 'cycle2.restock'),
)
CLOCKS = {line: symbol for first, last, symbol in CLOCK_RANGES for line in range(first, last + 1)}
assert len(CLOCKS) == sum(last - first + 1 for first, last, _ in CLOCK_RANGES)
RANDOM_CLOCKS = {
    18: 'cycle0.failure', 28: 'cycle0.followup_clock',
    89: 'cycle1.failure', 99: 'cycle1.followup_clock',
    161: 'cycle2.failure', 171: 'cycle2.followup_clock',
}
COMPLEXITY = {
    24: 'cycle0.failure_complexity', 35: 'cycle0.failure_complexity',
    60: 'cycle0.repair_complexity',
    96: 'cycle1.failure_complexity', 106: 'cycle1.failure_complexity',
    131: 'cycle1.repair_complexity',
    167: 'cycle2.failure_complexity', 178: 'cycle2.failure_complexity',
    203: 'cycle2.repair_complexity',
}
DIRECT_DURATION = {66, 137, 209}
TIME_RE = re.compile(r'^Time: ([0-9.e+]+)(?= )')
RANDOM_RE = re.compile(r'(Next random failure will occur )([0-9.e+]+)$')
COMPLEXITY_RE = re.compile(r'(complexity: )([0-9.]+)(?= )')


def line_patterns(data: bytes, child: bool = True) -> dict:
    assert b'\n' in data and data.endswith(b'\r\n') and data.count(b'\r\n') == 222
    assert data.count(b'\n') == 222 and not data.startswith(b'\xef\xbb\xbf')
    lines = data[:-2].decode('ascii').split('\r\n')
    assert len(lines) == 222 and lines[:2] == ['SIMLOX LOG FILE', '36']
    assert sum(line.startswith('Time: ') for line in lines) == 186
    out = []
    for line_number, raw in enumerate(lines, 1):
        template = raw
        bindings = []
        if line_number in CLOCKS and raw.startswith('Time: '):
            match = TIME_RE.search(template)
            assert match is not None, ('missing time', line_number)
            symbol = CLOCKS[line_number]
            template = template[:match.start(1)] + '{' + symbol + '}' + template[match.end(1):]
            bindings.append({'field': 'clock', 'symbol': symbol, 'lexical': 'finite decimal display'})
        if line_number in RANDOM_CLOCKS:
            match = RANDOM_RE.search(template)
            assert match is not None, ('missing random clock', line_number)
            symbol = RANDOM_CLOCKS[line_number]
            template = template[:match.start(2)] + '{' + symbol + '}' + template[match.end(2):]
            bindings.append({'field': 'random_clock', 'symbol': symbol, 'lexical': 'finite decimal display'})
        if line_number in COMPLEXITY:
            match = COMPLEXITY_RE.search(template)
            assert match is not None, ('missing complexity', line_number)
            symbol = COMPLEXITY[line_number]
            template = template[:match.start(2)] + '{' + symbol + '}' + template[match.end(2):]
            bindings.append({'field': 'complexity', 'symbol': symbol, 'lexical': 'finite 0..1 decimal'})
        if child and line_number in DIRECT_DURATION:
            assert 'planned to last for 1 hours' in template, line_number
            template = template.replace('planned to last for 1 hours', 'planned to last for 1.5 hours')
        out.append({
            'line': line_number,
            'timed': raw.startswith('Time: '),
            'template': template,
            'bindings': bindings,
            'source_parent_line_sha256': hashlib.sha256(raw.encode('ascii')).hexdigest(),
        })
    assert sum(x['timed'] for x in out) == 186
    assert sum(not x['timed'] for x in out) == 36
    assert [x['line'] for x in out] == list(range(1, 223))
    return {
        'schema': 'i05-var04-log-patterns/v101',
        'status': 'strict prospective hypothesis, not observed child output',
        'physical_lines': 222, 'timed_lines': 186, 'untimed_lines': 36,
        'clock_relations': {
            'cycle0.failure': 'literal displayed 9.25527',
            'cycle0.arrival': 'literal displayed 9.75527',
            'cycle0.item_start': 'literal displayed 9.92193',
            'cycle0.system_ready': 'literal displayed 10.2553',
            'cycle0.restock': 'literal displayed 11.4219',
            'cycle1.failure': 'finite f1 in [20,22), after prior restock',
            'cycle2.failure': 'finite f2 in [32,34), after prior restock',
            'cycle1.arrival': 'display of min(f1+0.5,22)',
            'cycle2.arrival': 'display of min(f2+0.5,34)',
            'cycle1.item_start': 'display of cycle1.arrival+1/6',
            'cycle2.item_start': 'display of cycle2.arrival+1/6',
            'cycle1.system_ready': 'display of cycle1.arrival+0.5',
            'cycle2.system_ready': 'display of cycle2.arrival+0.5',
            'cycle1.restock': 'display of cycle1.item_start+1.5',
            'cycle2.restock': 'display of cycle2.item_start+1.5',
            'followup_clocks': 'finite, source-ordered diagnostic draws; no equality to E05 parent value',
            'complexity': 'finite 0..1, repeated same-cycle failure complexity token exactly equal',
        },
        'lines': out,
    }


def read_report(data: bytes) -> dict:
    assert data.count(NATIVE_TRAILING_COMMA) == 1
    assert data.endswith(b'\r\n') and not data.startswith(b'\xef\xbb\xbf')
    obj = strict_json(data.replace(NATIVE_TRAILING_COMMA, b'\r\n      ]'))
    assert set(obj) == {'report'} and set(obj['report']) == {'tables'}
    return obj


def cell_rules(report: dict, rules: dict) -> dict:
    tables = report['report']['tables']
    assert [t['name'] for t in tables] == ['ProblemDescription', 'ResultSummary', 'SystemResults', 'StockTotalResults']
    formulas = {
        'ProblemDescription': {'PDESC': rules['ProblemDescription']['PDESC']},
        'ResultSummary': rules['ResultSummary'],
        'SystemResults': rules['SystemResults']['formulas'],
        'StockTotalResults': rules['StockTotalResults']['formulas'],
    }
    expected_rows = {'ProblemDescription': 1, 'ResultSummary': 1, 'SystemResults': 72, 'StockTotalResults': 72}
    expected_cols = {'ProblemDescription': 1, 'ResultSummary': 11, 'SystemResults': 40, 'StockTotalResults': 16}
    predicates = []
    metadata = []
    for table in tables:
        name = table['name']
        assert set(table) == {'name', 'columns', 'instances'} and len(table['instances']) == 1
        columns = table['columns']
        names = [c['name'] for c in columns]
        assert len(names) == expected_cols[name] and len(set(names)) == len(names)
        assert set(names) == set(formulas[name]), ('formula coverage', name)
        instance = table['instances'][0]
        assert set(instance) == {'instance_name', 'rows'} and len(instance['rows']) == expected_rows[name]
        metadata.append({'name': name, 'columns': copy.deepcopy(columns), 'instance_name': instance['instance_name'], 'rows': len(instance['rows'])})
        for row_index, row in enumerate(instance['rows']):
            assert type(row) is list and len(row) == len(columns)
            for column_index, column in enumerate(columns):
                predicates.append({
                    'table': name, 'row': row_index, 'column_index': column_index,
                    'column': column['name'], 'datatype': column['datatype'],
                    'rule': formulas[name][column['name']],
                    'comparison': 'exact typed string/integer/null/zero, or displayed-time-derived closed numeric interval plus two binary32 ULPs',
                })
    assert len(predicates) == 4044 and len({(p['table'], p['row'], p['column']) for p in predicates}) == 4044
    return {
        'schema': 'i05-var04-report-predicates/v101',
        'status': 'source-and-event-derived strict prospective hypotheses; no child report read',
        'cell_count': 4044, 'tables': metadata, 'predicates': predicates,
        'numeric_precision': rules['intervals']['comparison'],
    }


def write_once(path: Path, obj: object) -> dict:
    data = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(stat.S_IREAD)
    assert path.read_bytes() == data
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'readonly': True}


def main() -> None:
    specs = load_specs()
    original = strict_json(pinned(INPUT, PINS[INPUT]))
    parent_export = strict_json(pinned(EXPORT, PINS[EXPORT]))
    assert len(parent_export['model']['tables']) == 31
    assert sum(len(i['rows']) * len(t['columns']) for t in parent_export['model']['tables'] for i in t['instances']) == 369
    child = candidate_input(original, specs['source-delta.json'])
    patterns = line_patterns(pinned(LOG, PINS[LOG]))
    predicates = cell_rules(read_report(pinned(REPORT, PINS[REPORT])), specs['report-oracle.json'])
    assert specs['event-oracle.json']['line_grammar']['strict_branch_counts'] == {'physical_crlf_lines': 222, 'timed_lines': 186, 'untimed_continuations': 36}
    no_reparse(OUT)
    assert not OUT.exists(), ('output already exists', OUT)
    assert OUT.parent == REPO / 'tmp' and OUT.parent.is_dir()
    OUT.mkdir(exist_ok=False)
    products = [
        write_once(OUT / 'candidate-input.json', child),
        write_once(OUT / 'log-patterns.json', patterns),
        write_once(OUT / 'report-predicates.json', predicates),
    ]
    receipt = {
        'schema': 'i05-var04-prospective-materialization/v101',
        'contract_only': True, 'native_calls': 0, 'accepted_checker_calls': 0,
        'parent_source_pins': {str(k.relative_to(REPO)): {'bytes': n, 'sha256': h} for k, (n, h) in PINS.items()},
        'spec_pins': {k: {'bytes': n, 'sha256': h} for k, (n, h) in SPEC_PINS.items()},
        'products': products,
        'physical_log_patterns': 222, 'timed_patterns': 186, 'report_cell_predicates': 4044,
        'decision': 'PROSPECTIVE_HYPOTHESES_ONLY_INDEPENDENT_AUDIT_REQUIRED',
    }
    final = write_once(OUT / 'receipt.json', receipt)
    print(json.dumps({'decision': receipt['decision'], 'products': products, 'receipt': final}, separators=(',', ':')))


if __name__ == '__main__':
    main()
