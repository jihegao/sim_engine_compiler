"""Private, standard-library-only semantic negatives for the independent var06 reader."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import independent_reader as r


def rejects(action):
    try:
        action()
    except (AssertionError, ValueError, TypeError, KeyError, UnicodeDecodeError):
        return
    raise AssertionError('semantic mutation unexpectedly passed')


def render_report(report):
    return (json.dumps(report, ensure_ascii=False, indent=2) + '\n').replace('\n','\r\n').encode('utf-8')


def main():
    count=0
    assert r.source_oracles()=={'authored_cells':203,'export_cells':387}
    for path,pin,cells,rows in [
        (r.PARENT/'native-input.json',r.PARENT_INPUT_SHA,203,20),
        (r.PARENT_RUN/'roundtrip-raw.json',r.PARENT_EXPORT_SHA,387,38),
    ]:
        original=r.strict_json(r.pin(path,pin))
        expected=r.one_xtime(original)
        assert r.compare_model(expected,copy.deepcopy(expected))==(33,rows,cells)
        table=next(t for t in expected['model']['tables'] if t['name']=='UnitGroupMember')
        col=[c['name'] for c in table['columns']].index('XTIME')
        for mutation in ('zero','bool','wrong_unit','row_dict','rows_dict','missing_table','key_bool','key_removed','key_extra'):
            clone=copy.deepcopy(expected)
            table=next(t for t in clone['model']['tables'] if t['name']=='UnitGroupMember')
            if mutation=='zero': table['instances'][0]['rows'][1][col]=0
            elif mutation=='bool': table['instances'][0]['rows'][1][col]=True
            elif mutation=='wrong_unit': table['instances'][0]['rows'][1][1]='TEACH-UNIT'
            elif mutation=='row_dict':
                first=clone['model']['tables'][0]['instances'][0]['rows'][0]
                clone['model']['tables'][0]['instances'][0]['rows'][0]={str(first[0]):'inert'}
            elif mutation=='rows_dict':
                ins=clone['model']['tables'][0]['instances'][0]
                ins['rows']={'0':ins['rows'][0]}
            elif mutation=='missing_table': clone['model']['tables'].pop()
            elif mutation=='key_bool': table['columns'][0]['key']=1
            elif mutation=='key_removed': table['columns'][0].pop('key')
            else: table['columns'][0]['unknown']=True
            rejects(lambda clone=clone,expected=expected:r.compare_model(expected,clone)); count+=1
    control=r.strict_json(r.pin(r.CONTROL,r.CONTROL_SHA))
    report=copy.deepcopy(control)
    fixed=report['report']['tables'][4]
    assert fixed['name']=='FixedMissionResults' and fixed['instances'][0]['rows'][0][22]==0
    fixed['instances'][0]['rows'][0][22]=1
    assert r.compare_report(report,copy.deepcopy(report))==4966
    assert r.selected_report(render_report(report))=={'typed_cells':4966,'stotd':1}
    for mutation in ('stotd_zero','stotd_bool','other_cell','row_dict','rows_dict','missing_table','key_bool','key_removed','key_extra','extra_row','null_cell'):
        clone=copy.deepcopy(report)
        table=clone['report']['tables'][4]
        if mutation=='stotd_zero': table['instances'][0]['rows'][0][22]=0
        elif mutation=='stotd_bool': table['instances'][0]['rows'][0][22]=True
        elif mutation=='other_cell': table['instances'][0]['rows'][0][20]=0
        elif mutation=='row_dict':
            first=clone['report']['tables'][0]['instances'][0]['rows'][0]
            clone['report']['tables'][0]['instances'][0]['rows'][0]={str(first[0]):'inert'}
        elif mutation=='rows_dict':
            ins=clone['report']['tables'][0]['instances'][0]
            ins['rows']={'0':ins['rows'][0]}
        elif mutation=='missing_table': clone['report']['tables'].pop()
        elif mutation=='key_bool': table['columns'][0]['key']=1
        elif mutation=='key_removed': table['columns'][0].pop('key')
        elif mutation=='key_extra': table['columns'][0]['unknown']=True
        elif mutation=='extra_row': table['instances'][0]['rows'].append(copy.deepcopy(table['instances'][0]['rows'][0]))
        else: table['instances'][0]['rows'][0][7]=None
        rejects(lambda clone=clone:r.compare_report(report,clone)); count+=1
    for raw in (b'{"report":1,"report":2}',b'{"report":NaN}',b'\xef\xbb\xbf{"report":1}'):
        rejects(lambda raw=raw:r.strict_json(raw)); count+=1
    for mutant in (render_report(report).replace(b'\r\n',b'\n'),render_report(report)+b'extra'):
        rejects(lambda mutant=mutant:r.selected_report(mutant)); count+=1
    parent=r.pin(r.PARENT_RUN/'model.log',r.PARENT_LOG_SHA)
    assert r.physical_log(parent)=={'physical_lines':60,'timed_lines':52}
    for mutant in (parent.replace(b'<TEACH-AIR-01,1>',b'<TEACH-AIR-01,0>',1),
                   parent.replace(b'\r\n',b'\n'),parent+b'extra'):
        assert mutant!=parent
        rejects(lambda mutant=mutant:r.physical_log(mutant)); count+=1
    print(json.dumps({'schema':'a17-var06-independent-negative-self-check/v100','passed':True,
                      'negative_clones_rejected':count,'authored_cells':203,'export_cells':387,
                      'report_cells':4966,'physical_lines':60,'native_calls':0,
                      'accepted_checker_calls':0},sort_keys=True))


if __name__=='__main__': main()