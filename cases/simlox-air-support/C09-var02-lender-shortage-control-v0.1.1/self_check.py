"""In-memory adversarial checks for the frozen retrospective gates.

No accepted source or raw artifact is modified. The source verifier runs first;
mutations below are injected only into parsed copies to exercise semantic gates.
"""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys

from check_roundtrip import parse
from numeric_bounds import compare, cell_bound, printed_time_uncertainty
from physical_ledger import physical
from report_oracle import derive
from validate_native_cli import RUN, output_tables_doc, source_shape, validate

def run()->dict:
    baseline=validate()
    assert baseline['decision']=='GO_BOUNDED_RETROSPECTIVE_CONTROL'
    log=(RUN/'model.log').read_text(encoding='utf-8-sig')
    expected,edges=derive(log,horizon=12,fleet=3,description=source_shape(),with_edges=True)
    observed=output_tables_doc(parse(RUN/'report-raw.json'))
    uncertainty=printed_time_uncertainty(log)
    failures=[];accepted=[]
    def rejects_report(label,table,row,field,value):
        changed=deepcopy(observed);changed[table][row][field]=value
        errors,n=compare(expected,changed,edges=edges,log=log)
        assert n==1754 and any(f'{table}[{row}].{field}' in e for e in errors),label
        failures.append(label)
    def accepts_report(label,table,row,field,value):
        changed=deepcopy(observed);changed[table][row][field]=value
        errors,n=compare(expected,changed,edges=edges,log=log)
        assert n==1754 and not errors,(label,errors[:3])
        accepted.append(label)
    def rejects_log(label,change,*,ledger=False):
        changed=change(log);assert changed!=log,label
        try:
            if ledger:physical(changed,'ordinary')
            else:derive(changed,horizon=12,fleet=3,description=source_shape(),with_edges=True)
        except (AssertionError,ValueError):failures.append(label)
        else:raise AssertionError('mutation escaped: '+label)
    rejects_report('HOME wait residue high','SystemResults',18,'NSYWR',1.00001)
    rejects_report('HOME wait residue low','SystemResults',18,'NSYWR',0.99999)
    rejects_report('typed NRW residue high','ResourceResults',18,'NRW',1.00001)
    rejects_report('typed NRW residue low','ResourceResults',18,'NRW',0.99999)
    accepts_report('named HOME residue','SystemResults',18,'NSYWR',0.9999978542327881)
    rejects_report('source exact NSYMO near zero','SystemResults',15,'NSYMO',0.00001)
    rejects_report('source exact NSYMO near two','SystemResults',16,'NSYMO',2.00001)
    rejects_report('discrete counter subepsilon','SystemResults',18,'NPMS',1.000000001)
    rejects_report('null to zero','SystemResults',0,'SYDT',0)
    rejects_report('boolean count','SystemResults',18,'NPMS',True)
    rejects_report('wrong stock baseline','StockTotalResults',18,'PNB',1.000000001)
    # FTMO at h8–8.5 is a source-exact 2/3 fleet ratio.
    accepts_report('native FTMO 0.6666667','SystemResults',16,'FTMO',0.6666667)
    rejects_report('exact whole-bin FTMO zero subepsilon','SystemResults',0,'FTMO',0.000000001)
    rejects_report('interior FTMO outside serialization','SystemResults',16,'FTMO',2/3+0.00001)
    pm_bound=cell_bound('SystemResults',19,'NSYPM',expected['SystemResults'][19]['NSYPM'],edges,uncertainty)
    assert 0<pm_bound<0.00035
    rejects_report('PM fractional beyond edge bound','SystemResults',19,'NSYPM',expected['SystemResults'][19]['NSYPM']+pm_bound*1.1)
    sy_bound=cell_bound('SystemResults',18,'SYDT',expected['SystemResults'][18]['SYDT'],edges,uncertainty)
    assert 0.00005<sy_bound<0.00010
    rejects_report('elapsed downtime beyond endpoint bound','SystemResults',18,'SYDT',expected['SystemResults'][18]['SYDT']+sy_bound*1.1)
    total_bound=cell_bound('ResourceResultsTotal',0,'NRUM',expected['ResourceResultsTotal'][0]['NRUM'],edges,uncertainty)
    assert 0<total_bound<0.00005
    rejects_report('resource mean beyond horizon bound','ResourceResultsTotal',0,'NRUM',expected['ResourceResultsTotal'][0]['NRUM']+total_bound*1.1)
    summary_bound=cell_bound('ResultSummary',0,'MTMF',expected['ResultSummary'][0]['MTMF'],edges,uncertainty)
    assert 0<summary_bound<0.00005
    rejects_report('mission duration beyond DURN bound','ResultSummary',0,'MTMF',expected['ResultSummary'][0]['MTMF']+summary_bound*1.1)
    rejects_log('missing plain PM work start',lambda s:s.replace('subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing','subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> stage omitted'))
    rejects_log('missing plain PM work completion',lambda s:s.replace('subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> completed','subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> stage omitted'))
    rejects_log('wrong HOME physical ID',lambda s:s.replace('system PM task 3 on <HOME-AIR,2> started','system PM task 3 on <HOME-AIR,7> started'),ledger=True)
    rejects_log('failed availability removed',lambda s:s.replace('request for: 1 failed','request for: 1 OK'),ledger=True)
    rejects_log('return station swap',lambda s:s.replace('aiming for  <P-MECH at <BASE-02,0>>','aiming for  <P-MECH at <BASE-01,0>>'),ledger=True)
    rejects_log('resource overbooking',lambda s:s.replace('allocated to maintenance task: 1  available now: 0','allocated to maintenance task: 2  available now: 0'))
    rejects_log('missing PM release',lambda s:s.replace('deallocated from  maintenance task: 1  available now: 1','deallocation omitted  available now: 1'))
    assert len(failures)==23 and len(accepted)==2,(len(failures),len(accepted))
    return {'schema':'c09-var02-control-self-check/v1','passed':True,'rejected_mutations':failures,
            'within_bound_acceptances':accepted,'rejected_count':len(failures),'accepted_count':len(accepted),
            'raw_files_modified':0,'native_calls':0}

if __name__=='__main__':
    try:r=run()
    except Exception as exc:r={'schema':'c09-var02-control-self-check/v1','passed':False,'error':f'{type(exc).__name__}: {exc}'}
    print(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True))
    sys.exit(0 if r['passed'] else 1)
