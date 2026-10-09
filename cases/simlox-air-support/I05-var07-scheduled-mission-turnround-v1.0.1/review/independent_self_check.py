"""In-memory independent I05.var07 reader controls; no native or author imports."""
from __future__ import annotations

import copy
import json

from independent_reader import (PARENT_PINS, PARENT_RUN, CASE, RUN, converter_bytes,
    converter_fixture, exact, integer, native_report_json, physical_lines,
    projected_log, source_oracles, strict_json, table_counts, typed)

def reject(label,callback):
    try: callback()
    except (AssertionError,ValueError,TypeError,KeyError,IndexError,UnicodeError): return label
    raise AssertionError(('negative escaped',label))

def require(value): assert value

def clone(doc,mutate):
    result=copy.deepcopy(doc)
    mutate(result)
    return result

def run():
    authored,exported,child_log,child_report,parent=source_oracles()
    parent_log=parent['log']
    parent_lines=physical_lines(parent_log)
    child_lines=physical_lines(child_log)
    assert len(parent_lines)==len(child_lines)==115
    assert sum(s.startswith('Time: ') for s in parent_lines)==sum(s.startswith('Time: ') for s in child_lines)==107
    assert 'planned to last for 1 hours' in parent_lines[46]
    assert 'planned to last for 1 hours' in parent_lines[101]
    assert 'planned to last for 1 hours' in child_lines[46]
    assert 'planned to last for 1.5 hours' in child_lines[101]
    assert projected_log(parent_log)==child_log
    assert table_counts(authored,'model')==(33,23,211)
    assert table_counts(exported,'model')==(33,37,374)
    assert table_counts(child_report,'report')==(4,146,4044)
    assert type(authored['model']['tables'][32]['instances'][0]['rows'][0][3]) is float
    assert type(exported['model']['tables'][32]['instances'][0]['rows'][0][3]) is int
    converter=converter_fixture()
    assert converter_bytes(converter)==17
    rejected=[]
    def bad(label,action): rejected.append(reject(label,action))
    def model_equal(actual,expected): require(typed(actual,expected))
    def log_equal(actual): require(actual==child_log)
    def report_equal(actual): require(typed(actual,child_report))
    def conv_equal(actual): require(converter_bytes(actual)==17)
    bad('authored wrong insertion',lambda:model_equal(clone(authored,lambda d:d['model']['tables'].insert(17,d['model']['tables'].pop())),authored))
    bad('export adjacent insertion',lambda:model_equal(clone(exported,lambda d:d['model']['tables'].insert(31,d['model']['tables'].pop())),exported))
    bad('export unrelated swap',lambda:model_equal(clone(exported,lambda d:d['model']['tables'].insert(5,d['model']['tables'].pop(4))),exported))
    bad('export missing table',lambda:model_equal(clone(exported,lambda d:d['model']['tables'].pop()),exported))
    bad('export duplicate table',lambda:model_equal(clone(exported,lambda d:d['model']['tables'].append(copy.deepcopy(d['model']['tables'][-1]))),exported))
    bad('authored old duration',lambda:model_equal(clone(authored,lambda d:d['model']['tables'][32]['instances'][0]['rows'][0].__setitem__(4,1.0)),authored))
    bad('export integral double as float',lambda:model_equal(clone(exported,lambda d:d['model']['tables'][32]['instances'][0]['rows'][0].__setitem__(3,25.0)),exported))
    bad('export bool duration',lambda:model_equal(clone(exported,lambda d:d['model']['tables'][32]['instances'][0]['rows'][0].__setitem__(4,True)),exported))
    bad('export key bool alias',lambda:model_equal(clone(exported,lambda d:d['model']['tables'][32]['columns'][0].__setitem__('key',1)),exported))
    bad('export missing TIMEC key',lambda:model_equal(clone(exported,lambda d:d['model']['tables'][32]['columns'][3].pop('key')),exported))
    bad('child old second duration',lambda:log_equal(child_log.replace(b'planned to last for 1.5 hours',b'planned to last for 1 hours',1)))
    bad('child wrong first duration',lambda:log_equal(child_log.replace(b'planned to last for 1 hours',b'planned to last for 1.5 hours',1)))
    bad('child extra h25 marker',lambda:log_equal(child_log.replace(b'Time: 25 ',b'Time: 25 unexpected marker\r\nTime: 25 ',1)))
    bad('child missing terminal CRLF',lambda:log_equal(child_log[:-2]))
    bad('child LF-only',lambda:log_equal(child_log.replace(b'\r\n',b'\n')))
    bad('report wrong interval bin',lambda:report_equal(clone(child_report,lambda d:d['report']['tables'][2]['instances'][0]['rows'][55].__setitem__(4,1))))
    bad('report wrong child count',lambda:report_equal(clone(child_report,lambda d:d['report']['tables'][2]['instances'][0]['rows'][56].__setitem__(4,1))))
    bad('report bool count',lambda:report_equal(clone(child_report,lambda d:d['report']['tables'][2]['instances'][0]['rows'][56].__setitem__(4,False))))
    bad('report int/float alias',lambda:report_equal(clone(child_report,lambda d:d['report']['tables'][2]['instances'][0]['rows'][56].__setitem__(4,0.0))))
    bad('report metadata key alias',lambda:report_equal(clone(child_report,lambda d:d['report']['tables'][2]['columns'][0].__setitem__('key',1))))
    bad('converter warning 108',lambda:conv_equal(converter.replace(b'warning #108',b'warning #109',1)))
    bad('converter warning 126',lambda:conv_equal(converter.replace(b'warning #126',b'warning #127',1)))
    bad('converter wrong summary',lambda:conv_equal(converter.replace(b'Warnings: 2',b'Warnings: 1',1)))
    bad('converter missing terminal',lambda:conv_equal(converter[:-2]))
    bad('converter BOM',lambda:conv_equal(b'\xef\xbb\xbf'+converter))
    bad('receipt bool/int alias',lambda:integer(True,1))
    bad('source map bool/int alias',lambda:require(typed({'n':1},{'n':True})))
    bad('duplicate JSON',lambda:strict_json(b'{"a":1,"a":2}'))
    bad('nonfinite JSON',lambda:strict_json(b'{"a":NaN}'))
    bad('model BOM',lambda:strict_json(b'\xef\xbb\xbf{"a":1}'))
    assert len(rejected)==30 and len(set(rejected))==30
    return {'schema':'i05-var07-independent-private-check/v101','passed':True,
            'parent_physical_lines':115,'child_physical_lines':115,'timed_lines':107,
            'authored_cells':211,'export_cells':374,'report_cells':4044,
            'converter_lines':17,'rejected_mutants':len(rejected),
            'native_calls':0,'accepted_checker_calls':0}

if __name__=='__main__': print(json.dumps(run(),sort_keys=True))
