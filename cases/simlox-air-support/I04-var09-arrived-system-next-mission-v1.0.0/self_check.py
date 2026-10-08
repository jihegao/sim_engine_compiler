"""PURE mutation checks beneath original-file SHA custody; no native or parent checker calls."""
from __future__ import annotations
import copy
import json

import classify
import source_gate


def rejects(label, function, *args):
    try:
        function(*args)
    except (AssertionError, ValueError, KeyError, IndexError, TypeError, UnicodeError):
        return label
    raise AssertionError(f'mutation accepted: {label}')


def changed_line(source: bytes, index: int, old: str, new: str) -> bytes:
    lines = source.decode('utf-8-sig').splitlines()
    assert lines[index] == old, (index, lines[index])
    lines[index] = new
    return ('\r\n'.join(lines) + '\r\n').encode('utf-8')


def changed_fragment(source: bytes, index: int, old: str, new: str) -> bytes:
    lines = source.decode('utf-8-sig').splitlines()
    assert lines[index].count(old) == 1
    lines[index] = lines[index].replace(old, new)
    return ('\r\n'.join(lines) + '\r\n').encode('utf-8')


def swap_lines(source: bytes, a: int, b: int) -> bytes:
    lines = source.decode('utf-8-sig').splitlines()
    lines[a], lines[b] = lines[b], lines[a]
    return ('\r\n'.join(lines) + '\r\n').encode('utf-8')


def changed_report(source, row_number, column, value):
    report = copy.deepcopy(source)
    table = report['report']['tables'][2]
    names = [c['name'] for c in table['columns']]
    table['instances'][0]['rows'][row_number][names.index(column)] = value
    return report


def run() -> dict:
    log = (classify.RUN / 'model.log').read_bytes()
    report_raw = (classify.RUN / 'report-raw.json').read_bytes()
    baseline = classify.parse_log(log)
    report = classify.parse_native_report(report_raw)
    baseline_report = classify.validate_selected_report(report)
    assert baseline['lines'] == 118 and baseline['timed_records'] == 104
    assert baseline_report['prior_accepted_cells'] == 4044
    labels = []
    negatives = [
        ('wrong-transfer-id', changed_fragment(log, 60, '<TEACH-AIR-01,0>.', '<TEACH-AIR-01,1>.')),
        ('wrong-transfer-source', changed_fragment(log, 60, 'TEACH-UNIT at <BASE-01,0>', 'TEACH-UNIT-2 at <BASE-02,0>')),
        ('wrong-transfer-target', changed_fragment(log, 61, 'TEACH-UNIT-2 at <BASE-02,0>', 'TEACH-UNIT at <BASE-01,0>')),
        ('wrong-transfer-in-id', changed_fragment(log, 61, '<TEACH-AIR-01,0>.', '<TEACH-AIR-01,1>.')),
        ('early-arrival', changed_fragment(log, 61, 'Time: 11 ', 'Time: 10.5 ')),
        ('wrong-mission-id', changed_fragment(log, 73, '0,0,1>', '0,0,0>')),
        ('wrong-mission-aircraft', changed_fragment(log, 73, '<TEACH-AIR-01,0>', '<TEACH-AIR-01,1>')),
        ('wrong-assigned-owner', changed_fragment(log, 74, 'TEACH-UNIT-2 at <BASE-02,0>', 'TEACH-UNIT at <BASE-01,0>')),
        ('wrong-second-mission-order', changed_fragment(log, 86, '<TEACH-AIR-01,1>,<TEACH-AIR-01,0>', '<TEACH-AIR-01,0>,<TEACH-AIR-01,1>')),
        ('wrong-task-time', changed_fragment(log, 87, 'Time: 20.5 ', 'Time: 20.0 ')),
        ('wrong-completion-time', changed_fragment(log, 90, 'Time: 22 ', 'Time: 21.5 ')),
        ('ready-before-receipt', swap_lines(log, 61, 63)),
        ('mission-before-arrival', swap_lines(log, 61, 73)),
        ('return-before-turnround-end', swap_lines(log, 107, 108)),
        ('duplicate-transfer', changed_line(log, 61,
            'Time: 11 <TEACH-UNIT-2 at <BASE-02,0>> system transfered in: <TEACH-AIR-01,0>.',
            'Time: 11 <TEACH-UNIT at <BASE-01,0>> system transfered out: <TEACH-AIR-01,0>.')),
        ('unknown-line', changed_fragment(log, 62, 'Next random failure', 'Unexpected diagnostic')),
        ('wrong-ready-list', changed_fragment(log, 66, '<TEACH-AIR-01,1>,<TEACH-AIR-01,0>', '<TEACH-AIR-01,1>,<TEACH-AIR-01,1>')),
        ('missing-physical-id', changed_fragment(log, 108, 'System arrives <TEACH-AIR-01,0>', 'System arrives <TEACH-AIR-01,1>')),
        ('wrong-station-descriptor', changed_fragment(log, 108, 'BASE-02,0', 'BASE-01,0')),
        ('wrong-priority-station', changed_fragment(log, 105, 'BASE-02,0', 'BASE-01,0')),
        ('duplicate-ready-increment', changed_line(log, 64,
            'Time: 11 <TEACH-AIR-01,BASE-02,0> System ready <TEACH-AIR-01,0>',
            'Time: 11 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT-2 at <BASE-02,0>>')),
    ]
    for label, mutation in negatives:
        assert mutation != log
        labels.append(rejects(label, classify.parse_log, mutation))
    for label, row, field, value in (
        ('boolean-ready-cell', 22, 'NSYRY', True),
        ('wrong-ready-cell', 22, 'NSYRY', 1),
        ('wrong-assigned-cell', 38, 'NSYMA', 1),
        ('wrong-row-identity', 38, 'SID', 'Wrong system'),
        ('wrong-time-cell', 21, 'STINT', 10.0),
    ):
        labels.append(rejects(label, classify.validate_selected_report,
                              changed_report(report, row, field, value)))
    extra = copy.deepcopy(report)
    extra['report']['tables'].append(copy.deepcopy(extra['report']['tables'][0]))
    labels.append(rejects('extra-report-table', classify.validate_selected_report, extra))
    extra_field = copy.deepcopy(report)
    extra_field['report']['tables'][2]['unexpected'] = True
    labels.append(rejects('extra-report-metadata', classify.validate_selected_report, extra_field))
    labels.append(rejects('duplicate-json-key', source_gate.decode, b'{"x":1,"x":2}'))
    labels.append(rejects('overflow-json-number', source_gate.decode, b'{"x":1e999}'))
    assert len(labels) == len(set(labels)) == 30
    return {'schema':'i04-var09-pure-self-check/v1', 'decision':'PASS',
            'accepted_log_lines':118, 'accepted_timed_records':104,
            'previously_accepted_report_cells':4044,
            'semantic_rejections':len(labels), 'rejected_labels':labels,
            'new_native_runs':0, 'accepted_checker_reruns':0}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True, separators=(',', ':')))
