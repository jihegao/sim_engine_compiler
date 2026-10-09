"""Private negative controls for the independent I05 byte and semantic reader.

The controls read sealed parent artifacts. They do not invoke SIMLOX or any
accepted or author checker, and they write no artifact.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
if HERE.name=='tmp':
    READER=HERE/'i05-var04-independent-reader-v103-final-20261009.py'
elif HERE.name=='review':
    READER=HERE/'independent_reader.py'
else:
    raise AssertionError('private check outside approved review source location')

spec=importlib.util.spec_from_file_location('i05_independent_reader_for_selfcheck',READER)
assert spec and spec.loader
reader=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def rejected(label, fn):
    try:
        fn()
    except (AssertionError, ValueError, UnicodeError, KeyError, TypeError, IndexError):
        return label
    raise AssertionError('negative accepted: '+label)


def change_once(data:bytes, old:bytes, new:bytes)->bytes:
    assert data.count(old)>=1
    return data.replace(old,new,1)


def verify():
    receipt_controls=[]
    for kind,path,size,digest in reader.CONTEXT[1:]:
        body=reader.exact(path,{'bytes':size,'sha256':digest})
        assert body.startswith(b'\xef\xbb\xbf') and not body.startswith(b'\xef\xbb\xbf\xef\xbb\xbf')
        decoded=reader.accepted_powershell_receipt_json(body)
        assert type(decoded) is dict and decoded['run_id']=='e05-v100-ssh-20260929-01'
        receipt_controls.append(rejected(kind+'_missing_bom',
            lambda b=body:reader.accepted_powershell_receipt_json(b[3:])))
        receipt_controls.append(rejected(kind+'_double_bom',
            lambda b=body:reader.accepted_powershell_receipt_json(b'\xef\xbb\xbf'+b)))
        receipt_controls.append(rejected(kind+'_strict_parser',
            lambda b=body:reader.strict_json(b)))
    receipt_controls.append(rejected('model_bom',lambda:reader.strict_json(b'\xef\xbb\xbf'+
        reader.exact(reader.PARENT/'native-input.json',{'bytes':43690,'sha256':reader.PARENT_INPUT_SHA}))))
    receipt_controls.append(rejected('accepted_receipt_duplicate_key',
        lambda:reader.accepted_powershell_receipt_json(b'\xef\xbb\xbf{"x":1,"x":2}')))
    receipt_controls.append(rejected('accepted_receipt_nonfinite',
        lambda:reader.accepted_powershell_receipt_json(b'\xef\xbb\xbf{"x":NaN}')))
    assert len(receipt_controls)==9
    authored,exported=reader.source_oracles()
    assert reader.count_tables(authored['model']['tables'])==(32,25,284)
    assert reader.count_tables(exported['model']['tables'])==(32,36,379)
    patterns=reader.strict_json(reader.exact(reader.CASE/'preserved-oracle/log-patterns.json',
        {'bytes':87444,'sha256':reader.PATTERN_SHA},readonly=True))
    rules=reader.strict_json(reader.exact(reader.CASE/'preserved-oracle/report-predicates.json',
        {'bytes':1380881,'sha256':reader.REPORT_RULES_SHA},readonly=True))
    log=reader.exact(reader.PARENT_RUN/'model.log',{'bytes':18758,'sha256':reader.PARENT_LOG_SHA})
    report=reader.exact(reader.PARENT_RUN/'report-raw.json',
        {'bytes':104356,'sha256':'fcf9a124546e77fb96871b5bf4b5e111774c00616bfed69c19ad7f1b6c08b4bf'})
    observed=reader.read_log(log,patterns,child=False)
    assert reader.check_report(report,rules,observed)==4044
    parent_control=reader.parent_control_catalog(patterns)
    assert {n for n,(a,b) in enumerate(zip(patterns['lines'],parent_control['lines'],strict=True),1)
            if not reader.typed(a,b)}=={66,137,209}
    assert log.endswith(b'\r\n')
    parent_lines=log[:-2].split(b'\r\n')
    assert len(parent_lines)==222
    child_lines=parent_lines.copy()
    restocks=(
        (b'10.9219',b'11.4219',{74,75,76,77,78}),
        (b'23.1667',b'23.6667',{145,146,147,148,149}),
        (b'34.9746',b'35.4746',{217,218,219,220,221}),
    )
    for old,new,positions in restocks:
        assert {n for n,line in enumerate(child_lines,1) if old in line}==positions
        for n in positions:
            assert child_lines[n-1].count(old)==1
            child_lines[n-1]=child_lines[n-1].replace(old,new)
    for n in (66,137,209):
        assert child_lines[n-1].count(b'planned to last for 1 hours')==1
        child_lines[n-1]=child_lines[n-1].replace(b'planned to last for 1 hours',
                                                  b'planned to last for 1.5 hours')
    assert {n for n,(a,b) in enumerate(zip(parent_lines,child_lines,strict=True),1) if a!=b}==(
        {66,137,209}|{74,75,76,77,78,145,146,147,148,149,217,218,219,220,221})
    child_log=b'\r\n'.join(child_lines)+b'\r\n'
    child_observed=reader.read_log(child_log,patterns,child=True)
    assert reader.check_report(report,rules,child_observed)==4044
    negatives=[]
    negatives.append(rejected('parent_dirpt_under_child',lambda:reader.read_log(log,patterns,child=True)))
    negatives.append(rejected('child_dirpt_under_parent',lambda:reader.read_log(child_log,patterns,child=False)))
    wrong_child=child_lines.copy()
    wrong_child[137-1]=parent_lines[137-1]
    negatives.append(rejected('child_one_wrong_duration',lambda:reader.read_log(
        b'\r\n'.join(wrong_child)+b'\r\n',patterns,child=True)))
    wrong_parent=parent_lines.copy()
    wrong_parent[209-1]=child_lines[209-1]
    negatives.append(rejected('parent_one_wrong_duration',lambda:reader.read_log(
        b'\r\n'.join(wrong_parent)+b'\r\n',patterns,child=False)))
    partial_child=child_lines.copy()
    partial_child[74-1]=parent_lines[74-1]
    negatives.append(rejected('child_one_old_restock',lambda:reader.read_log(
        b'\r\n'.join(partial_child)+b'\r\n',patterns,child=True)))
    bad_logs=[
        ('log_header',change_once(log,b'SIMLOX LOG FILE',b'SIMLOX LOG FAIL')),
        ('log_lf',change_once(log,b'\r\n',b'\n')),
        ('log_terminal_crlf',log[:-2]),
        ('log_repeated_failure',change_once(log,b'9.25527',b'9.25528')),
        ('log_nonfinite',change_once(log,b'9.25527',b'NaN')),
    ]
    for label,mutant in bad_logs:
        negatives.append(rejected(label,lambda m=mutant:reader.read_log(m,patterns,child=False)))
    bad_patterns=copy.deepcopy(patterns)
    bad_patterns['lines'][0]['timed']=True
    negatives.append(rejected('timed_grammar',lambda:reader.read_log(log,bad_patterns,child=False)))
    bad_patterns=copy.deepcopy(patterns)
    bad_patterns['lines'][1]['line']=3
    negatives.append(rejected('pattern_reorder',lambda:reader.read_log(log,bad_patterns,child=False)))
    bad_report=change_once(report,b'E05 local LRU repair, stock return and second issue',
                           b'E05 local LRU repair, stock return and second fail')
    negatives.append(rejected('report_string_cell',lambda:reader.check_report(bad_report,rules,observed)))
    bad_report=change_once(report,b'"key" : true',b'"key" : 1')
    negatives.append(rejected('report_key_metadata_type',lambda:reader.check_report(bad_report,rules,observed)))
    bad_report=change_once(report,b'null',b'false')
    negatives.append(rejected('report_null_type',lambda:reader.check_report(bad_report,rules,observed)))
    assert report.count(b'0.92719858884811401')==2
    bad_report=change_once(report,b'0.92719858884811401',b'0.5')
    negatives.append(rejected('report_mtmf_numeric',lambda:reader.check_report(bad_report,rules,observed)))
    wrong=copy.deepcopy(exported)
    row=wrong['model']['tables'][17]['instances'][0]['rows'][0]
    row[3]=1.0
    negatives.append(rejected('export_dirpt_delta',lambda:reader.compare_tables(exported['model']['tables'],wrong['model']['tables'])))
    wrong=copy.deepcopy(exported)
    wrong['model']['tables'][17]['columns'][0]['key']=1
    negatives.append(rejected('export_key_bool_type',lambda:reader.compare_tables(exported['model']['tables'],wrong['model']['tables'])))
    assert authored['model']['tables'][12]['name']=='ChangesItemRepair'
    assert exported['model']['tables'][16]['name']=='Operations'
    assert exported['model']['tables'][17]['name']=='ChangesItemRepair'
    assert exported['model']['tables'][18]['name']=='Unit'
    wrong=copy.deepcopy(exported)
    moved=wrong['model']['tables'].pop(17)
    wrong['model']['tables'].insert(12,moved)
    negatives.append(rejected('export_old_index12',lambda:reader.compare_tables(exported['model']['tables'],wrong['model']['tables'])))
    wrong=copy.deepcopy(exported)
    wrong['model']['tables'][18],wrong['model']['tables'][19]=wrong['model']['tables'][19],wrong['model']['tables'][18]
    negatives.append(rejected('export_unrelated_reorder',lambda:reader.compare_tables(exported['model']['tables'],wrong['model']['tables'])))
    wrong=copy.deepcopy(exported)
    wrong['model']['tables'].pop(17)
    negatives.append(rejected('export_missing_new_table',lambda:reader.compare_tables(exported['model']['tables'],wrong['model']['tables'])))
    wrong=copy.deepcopy(exported)
    wrong['model']['tables'].insert(18,copy.deepcopy(wrong['model']['tables'][17]))
    negatives.append(rejected('export_duplicate_new_table',lambda:reader.compare_tables(exported['model']['tables'],wrong['model']['tables'])))
    wrong=copy.deepcopy(authored)
    moved=wrong['model']['tables'].pop(12)
    wrong['model']['tables'].insert(17,moved)
    negatives.append(rejected('authored_wrong_index17',lambda:reader.compare_tables(authored['model']['tables'],wrong['model']['tables'])))
    assert len(negatives)==23
    return {'decision':'PASS_INDEPENDENT_PRIVATE_NEGATIVES','parent_positive_report_cells':4044,
            'parent_positive_log_lines':222,'synthetic_child_positive_report_cells':4044,
            'synthetic_child_positive_log_lines':222,'rejected_mutants':negatives,
            'receipt_parser_rejected_mutants':receipt_controls,
            'native_calls':0,'accepted_checker_calls':0}


if __name__=='__main__':
    print(json.dumps(verify(),sort_keys=True))
