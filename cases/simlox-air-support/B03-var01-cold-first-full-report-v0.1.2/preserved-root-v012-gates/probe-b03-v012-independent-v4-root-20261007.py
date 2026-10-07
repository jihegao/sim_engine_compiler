from pathlib import Path
import copy,hashlib,importlib.util,json,math,subprocess,sys,stat
from datetime import datetime,timezone
r=Path(__file__).resolve().parents[1];p=r/'cases/simlox-air-support/B03-var01-cold-first-full-report-v0.1.2'
method=p/'review/independent_replay_v4.py';h='37d781293f2f6c9892598239296b18ac3c4d2e10473d042d74a2c3527fe3507f'
assert hashlib.sha256(method.read_bytes()).hexdigest()==h;method.chmod(stat.S_IREAD)
out=r/'tmp/b03-v012-independent-v4-root-gates-20261007.json';assert not out.exists()
proc=subprocess.run([sys.executable,'-X','utf8','-B',str(method)],cwd=r,capture_output=True)
streams={}
for name,data in [('stdout',proc.stdout),('stderr',proc.stderr)]:
    f=r/f'tmp/b03-v012-independent-v4-root-baseline-{name}-20261007.txt';assert not f.exists();f.write_bytes(data);f.chmod(stat.S_IREAD)
    streams[name]={'path':f.relative_to(r).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
assert proc.returncode==0 and not proc.stderr,(proc.returncode,streams)
baseline=json.loads(proc.stdout)
s=importlib.util.spec_from_file_location('b03_v012_root_independent',method);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
c=json.loads((p/'contract.json').read_bytes());src,availability=m.source_and_provenance(c);d=m.run_evidence(c);plan=m.expected_plan(src)
log=(d/'model.log').read_bytes();gate=c['full_report_gate'];expected=m.expected_report(src,plan,gate);report=m.native_json_bytes((d/'report-raw.json').read_bytes())
_,unc=m.physical(log,plan);bounds={math.floor(plan[i]['prep_end']*2):u/.5+5e-7 for i,u in unc.items() if plan[i]['prep_end']%.5!=0};results=[]
def probe(name,fn):
    try:fn()
    except (AssertionError,ValueError,KeyError,TypeError):result='REJECTED'
    else:result='ESCAPED'
    results.append({'probe':name,'result':result})
def lp(name,before,after):
    assert before in log;probe(name,lambda:m.physical(log.replace(before,after,1),plan))
for name,before,after in [
 ('wrong_planned_work',b'planned to last for 0.166667 hours',b'planned to last for 0.9 hours'),
 ('coarse_planned_work',b'planned to last for 0.166667 hours',b'planned to last for 0 hours'),
 ('availability_test_suffix',b'resource availability test',b'resource availability test failed'),
 ('requested_aircraft_count_suffix',b'mission activated, systems requested: 1',b'mission activated, systems requested: 10'),
 ('ordered_mission_id_suffix',b'mission ordered: COLD-FIRST',b'mission ordered: COLD-FIRSTX'),
 ('turnround_reduction_factor',b'turnround started, mission: <COLD-FIRST,TEACH-UNIT,0,0,0> reduction factor: 1',b'turnround started, mission: <COLD-FIRST,TEACH-UNIT,0,0,0> reduction factor: 2'),
 ('monotonic_diagnostic_wrong_time',b'Time: 7.16667 <TEACH-AIR-01,0> Next random failure',b'Time: 7.16 <TEACH-AIR-01,0> Next random failure'),
 ('wrong_on_station_start',b'Time: 8.5 <COLD-FIRST,TEACH-UNIT,0,0,0> task starting:',b'Time: 8.6 <COLD-FIRST,TEACH-UNIT,0,0,0> task starting:'),
 ('coarsened_hot_completion',b'Time: 11.1667 <TEACH-AIR-01,0> preparation ended',b'Time: 11.2 <TEACH-AIR-01,0> preparation ended'),
 ('invented_failure_continuation',b' no failures ',b' one failure '),
 ('wrong_terminal_horizon',b'SIMLOX LOG FILE\r\n36',b'SIMLOX LOG FILE\r\n35')]:lp(name,before,after)
probe('extra_unknown_timed_edge',lambda:m.physical(log+b'Time: 25 <TEACH-AIR-01,0> item delivered: FAKE\r\n',plan))
probe('extra_subtask_completion',lambda:m.physical(log+b'Time: 25 subtask 3 seqno 1 within system preparation task 2 on <TEACH-AIR-01,0> completed\r\n',plan))
for level in ['root','report','table','instance','column']:
    test=copy.deepcopy(report);t=test['report']['tables'][2]
    target={'root':test,'report':test['report'],'table':t,'instance':t['instances'][0],'column':t['columns'][0]}[level]
    target['unexpected']='hours';probe('extra_'+level+'_metadata',lambda test=test:m.compare_report(test,expected,gate,bounds))
def rp(name,table,row,field,value):
    test=copy.deepcopy(report);t=next(t for t in test['report']['tables'] if t['name']==table);col=[x['name'] for x in t['columns']].index(field);t['instances'][0]['rows'][row][col]=value
    probe(name,lambda:m.compare_report(test,expected,gate,bounds))
for f in ['NSYAL','STREQ','STF','STLOW','SYDTU']:rp('presentation_zero_'+f,'SystemResults',16,f,1e-12)
rp('source_zero_tiny_residue','SystemResults',0,'NSYMP',1e-12)
rp('boolean_zero_substitution','SystemResults',0,'NSYMP',False)
rp('undefined_SYDT_zero','SystemResults',0,'SYDT',0)
rp('stock_ROS_null_zero','StockTotalResults',0,'ROS',0)
rp('stock_PNB_quantity','StockTotalResults',0,'PNB',0)
rp('fraction_outside_actual_token_bound','SystemResults',22,'NSYMP',expected['SystemResults'][22][gate['column_order_exact']['SystemResults'].index('NSYMP')]+bounds[22]+1e-6)
rp('nonfinite_fraction','SystemResults',22,'NSYMP',float('nan'))
badgate=copy.deepcopy(gate);badgate['system_integrals_h']['NSYRY_unassigned_ready']=29+1/6
probe('wrong_ready_integral_contract_constant',lambda:m.expected_report(src,plan,badgate))
original_parser=m.native_json_bytes
for level in ['database_version','instance_name','table_metadata','instance_metadata']:
    test=m.native_json_bytes((d/'roundtrip-raw.json').read_bytes())
    if level=='database_version':test['model']['database_version']='incorrect'
    elif level=='instance_name':test['model']['tables'][0]['instances'][0]['instance_name']='incorrect'
    elif level=='table_metadata':test['model']['tables'][0]['unexpected']='hours'
    else:test['model']['tables'][0]['instances'][0]['unexpected']='hours'
    try:
        m.native_json_bytes=lambda raw,test=test:test
        probe('roundtrip_'+level,lambda:m.roundtrip(src,d))
    finally:m.native_json_bytes=original_parser
duplicate=original_parser((d/'roundtrip-raw.json').read_bytes())
duplicate['model']['tables'].append(copy.deepcopy(duplicate['model']['tables'][0]))
probe('roundtrip_duplicate_table',lambda:m.roundtrip(src,d,duplicate))
missing=p/'review/__root_absent_archive_origin_probe__';assert not missing.exists()
assert m.archived_pin(c['excluded_v010']['files'][0],missing) is False
badpin=copy.deepcopy(c['excluded_v010']['files'][0]);badpin['sha256']='0'*64
probe('missing_original_still_requires_inert_copy_pin',lambda:m.archived_pin(badpin,missing))
assert hashlib.sha256(method.read_bytes()).hexdigest()==h
v={'decision':'ROOT_TARGETED_GATES_PASS' if all(x['result']=='REJECTED' for x in results) else 'NO_GO_ROOT_MUTATION_ESCAPE','utc':datetime.now(timezone.utc).isoformat(),'method_sha256':h,'baseline':baseline,'baseline_streams':streams,'probes':results,'actual_fraction_bounds':bounds,'new_native_runs':0,'final_publication_go':False}
out.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');out.chmod(stat.S_IREAD)
print(json.dumps({'receipt':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'decision':v['decision'],'probes':len(results),'escapes':[x for x in results if x['result']=='ESCAPED'],'baseline':baseline},indent=2))
assert v['decision']=='ROOT_TARGETED_GATES_PASS'
