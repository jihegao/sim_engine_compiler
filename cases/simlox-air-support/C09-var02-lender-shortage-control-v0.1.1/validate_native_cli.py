"""Read-only C09.var02 retrospective ordinary-control validator.

This never invokes SIMLOX or edits any accepted/frozen source or raw evidence.
It does not accept the failed v1.0.2 prospective pair or an unrun shortage arm.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse
from numeric_bounds import compare
from physical_ledger import physical
from report_oracle import (RESOURCE_FIELDS, RESOURCE_TOTAL_FIELDS, STOCK_FIELDS,
                           SUMMARY_FIELDS, SYSTEM_FIELDS, derive)
from verify_sources import verify as verify_sources

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'C09-var02-lender-shortage-v1.0.2'
RUN=OLD/'runs'/'c09-var02-v102-ordinary-ssh-20261007-01'
INPUT_SHA='b971efb41492789f32475aae7fa9f37c0e30e9461203b48d37e08e2747e8d2e3'
TABLE_COLUMNS={'ProblemDescription':['PDESC'],'ResultSummary':SUMMARY_FIELDS,
               'SystemResults':SYSTEM_FIELDS,'StockTotalResults':STOCK_FIELDS,
               'ResourceResults':RESOURCE_FIELDS,'ResourceResultsTotal':RESOURCE_TOTAL_FIELDS}

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def output_tables_doc(doc:dict)->dict[str,list[dict]]:
    assert set(doc)=={'report'}
    tables=doc['report']['tables']
    assert [t['name'] for t in tables]==list(TABLE_COLUMNS)
    out={}
    for t in tables:
        name=t['name'];fields=[c['name'] for c in t['columns']]
        assert fields==TABLE_COLUMNS[name],name
        instance={'ProblemDescription':'','ResultSummary':'',
                  'SystemResults':'Total over all Units;Total over all Systems;0.00;12.00',
                  'StockTotalResults':'0.00;12.00;',
                  'ResourceResults':'Total over all Resources;Total over all Stations;0.00;12.00',
                  'ResourceResultsTotal':'Total over all Resources;Total over all Stations;0.00;12.00'}[name]
        assert len(t['instances'])==1 and t['instances'][0]['instance_name']==instance,name
        rows=t['instances'][0]['rows']
        assert len(rows)==(24 if name in {'SystemResults','StockTotalResults','ResourceResults'} else 1)
        assert all(len(r)==len(fields) for r in rows)
        out[name]=[dict(zip(fields,r)) for r in rows]
    assert sum(len(r) for rows in out.values() for r in rows)==1754
    return out

def diagnostics(text:str)->None:
    assert 'Input conversion completed. Errors: 0, Warnings: 3, Notes: 1' in text
    form='';seen=[]
    for line in text.splitlines():
        if line.startswith('Form: '):form=line.removeprefix('Form: ').strip()
        m=re.match(r'rec (\d+): \((warning|notice) #(\d+)\)',line)
        if m:seen.append((form,int(m.group(1)),m.group(2),int(m.group(3))))
    assert seen==[('Control',1,'warning',108),('ResourceRemoteSupport',1,'notice',292),
                  ('System',1,'warning',126),('System',2,'warning',126)],seen
    assert not re.search(r'\(error #\d+\)',text,re.I)

def source_shape()->str:
    assert sha(OLD/'ordinary-input.json')==sha(RUN/'input.json')==INPUT_SHA
    authored=parse(RUN/'input.json')
    assert len(authored['model']['tables'])==32
    tm={t['name']:t for t in authored['model']['tables']}
    assert sum(any(i['rows'] for i in t['instances']) for t in tm.values())==25
    def row(name,key,value):
        t=tm[name];cols=[c['name'] for c in t['columns']]
        matches=[dict(zip(cols,r)) for i in t['instances'] for r in i['rows'] if r[cols.index(key)]==value]
        assert len(matches)==1,(name,key,value)
        return matches[0]
    control=row('Control','RSEED','1')
    assert control['SIMPE']==control['RCEND']==12 and control['ENPM']=='Y'
    assert row('System','SID','HOME-AIR')['FRT']==0
    assert row('SystemDeployment','SID','HOME-AIR')['QTYPS']==1
    assert row('Unit','UNID','HOME-UNIT')['STID']=='BASE-02'
    assert row('OperationProfile','PRID','HOME-ZERO')['IQTY']==0
    assert row('MaterielPM','PMID','HOME-PM9')['PMINT']==9
    assert row('PMLocation','PMID','HOME-PM9')['STID']=='BASE-02'
    assert row('SubTaskResource','TID','HOME-PM')['RID']=='P-MECH'
    route=row('ResourceRemoteSupport','RID','P-MECH')
    assert route['TTRS']==route['TTRSS']==0.5 and route['TFRS']==0.25
    return tm['ProblemDescription']['instances'][0]['rows'][0][0]

def provenance()->dict:
    invocation=json.loads((RUN/'invocation.json').read_text(encoding='utf-8-sig'))
    closure=json.loads((RUN/'closure.json').read_text(encoding='utf-8-sig'))
    failure=json.loads((RUN/'failure-seal.json').read_text(encoding='utf-8-sig'))
    steps=json.loads((RUN/'steps.json').read_text(encoding='utf-8-sig'))
    assert invocation['run_id']==closure['run_id']==failure['run_id']==RUN.name
    assert invocation['session_id']==0 and invocation['queue_mutex']==r'Global\SimloxIssue18NativeQueue'
    assert any('sshd.exe' in str(x).lower() for x in invocation['ssh_ancestors'])
    gui={'pid':13340,'session_id':1,'start_unix_ms':1790590196826,'responding':True}
    assert invocation['gui']==gui
    assert invocation['input_sha256']==INPUT_SHA
    assert invocation['manifest_sha256']==closure['manifest_sha256']
    assert closure['source_hashes_before']==closure['source_hashes_after']==invocation['source_hashes_before']
    assert closure['invocation_sha256']==sha(RUN/'invocation.json')
    assert closure['error']==failure['error']=='check_behavior rejected native result'
    assert [s['name'] for s in steps]==['import','export','check_import_export','calc','jsonreport','check_behavior']
    assert [s['exit_code'] for s in steps]==[0,0,0,0,0,1]
    assert all(s['status']=='completed' and s['gui_preserved'] for s in steps[:5])
    assert steps[5]['status']=='failed' and steps[5]['gui_preserved']
    assert all(s['child_session_id']==0 for s in steps if s['name'] in {'import','export','calc','jsonreport'})
    assert len(closure['raw'])==13 and set(closure['raw'])==set(json.loads((HERE/'contract.json').read_text(encoding='utf-8'))['excluded_v102']['ordinary_run']['raw'])
    assert not (RUN.parent/'c09-var02-v102-shortage-ssh-20261007-01').exists()
    return {'run_id':RUN.name,'closure_sha256':sha(RUN/'closure.json'),
            'failure_seal_sha256':sha(RUN/'failure-seal.json'),'original_check_behavior':'FAILED'}

def validate()->dict:
    source=verify_sources()
    description=source_shape()
    prov=provenance()
    rt=json.loads((RUN/'roundtrip-validation.json').read_text(encoding='utf-8-sig'))
    assert rt['passed'] and rt['authored_row_tables']==25 and not rt['issues']
    diagnostics((RUN/'run.log').read_text(encoding='utf-8-sig',errors='replace'))
    log=(RUN/'model.log').read_text(encoding='utf-8-sig',errors='replace')
    ledger=physical(log,'ordinary')
    want,edges=derive(log,horizon=12,fleet=3,description=description,with_edges=True)
    actual=output_tables_doc(parse(RUN/'report-raw.json'))
    errors,cells=compare(want,actual,edges=edges,log=log)
    assert cells==1754 and not errors,errors[:12]
    assert ledger['pm_wait_started']==9 and ledger['pm_work_started']==9.96988
    assert ledger['pm_completed']==10.2199 and ledger['qualifying_return_hours']==[0.5]
    assert ledger['outward_count']==ledger['return_count']==1
    assert (ledger['outward_start'],ledger['outward_arrival'],
            ledger['return_start'],ledger['return_arrival'])==(8.71988,8.96988,9.46988,9.96988)
    return {'schema':'c09-var02-lender-shortage-control-v011-author-verdict/v1',
            'decision':'GO_BOUNDED_RETROSPECTIVE_CONTROL','original_pair_decision':'NO_GO_PROSPECTIVE_PAIR',
            'positive_pair_accepted':False,'shortage_arm':'not_started_not_tested',
            'native_runs_added':0,'full_report_cells_checked':cells,
            'source_verification':source['counts'],'physical_ledger':ledger,'provenance':prov,
            'contract_sha256':sha(HERE/'contract.json'),'failures':[]}

if __name__=='__main__':
    try:r=validate()
    except Exception as exc:r={'schema':'c09-var02-lender-shortage-control-v011-author-verdict/v1',
                              'decision':'NO_GO','error':f'{type(exc).__name__}: {exc}'}
    print(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True))
    sys.exit(0 if r['decision'].startswith('GO_') else 1)
