from pathlib import Path
import copy,hashlib,importlib.util,json,math,subprocess,sys,stat
from datetime import datetime,timezone
r=Path(__file__).resolve().parents[1];p=r/'cases/simlox-air-support/B03-var01-cold-first-full-report-v0.1.2'
pins={'replay_v2.py':'d6d1798c7cb2428a59a70cf3040cbbe39af11fc79dfef5ca8624cbbe2018bcb9','self_check_v2.py':'1ac865b65ad83f009a3f3753db87368ed2364d5615abdbbb7b369b4d0d7e0bc7','METHOD-v2.md':'5fd93e80d75de41090d828f372d8b9e3d7d35b21b5f9f253174e7319c34a3a69'}
for n,h in pins.items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h;(p/n).chmod(stat.S_IREAD)
out=r/'tmp/b03-v012-author-v2-root-gates-20261007.json';assert not out.exists()
baselines={};streams={}
for n in ['replay_v2.py','self_check_v2.py']:
    proc=subprocess.run([sys.executable,'-X','utf8','-B',str(p/n)],cwd=r,capture_output=True)
    for stream,data in [('stdout',proc.stdout),('stderr',proc.stderr)]:
        f=r/f'tmp/b03-v012-author-v2-root-{n}-{stream}-20261007.txt';assert not f.exists();f.write_bytes(data);f.chmod(stat.S_IREAD)
        streams[n+'/'+stream]={'path':f.relative_to(r).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    assert proc.returncode==0 and not proc.stderr,(n,proc.returncode,streams)
    baselines[n]=json.loads(proc.stdout)
s=importlib.util.spec_from_file_location('b03_v012_root_author',p/'replay_v2.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
c=json.loads((p/'contract.json').read_bytes());d=Path(c['parent_runs'][1]['original_directory']);src=json.loads((d/'input.json').read_text(encoding='utf-8-sig'));export=m.parse_native((d/'roundtrip-raw.json').read_bytes());schedule,_=m.check_source_and_roundtrip(c,src,export)
mt=m.source_rows(src,'MissionType');bd=m.source_rows(src,'TaskBreakDown');log=(d/'model.log').read_bytes();gate=c['full_report_gate'];records=m.events(log)
def physical(data):return m.check_events(m.events(data),schedule,mt,bd,gate['system_integrals_h'])
intervals=physical(log);expected=m.report_expected(c,src,intervals);report=m.parse_native((d/'report-raw.json').read_bytes());results=[]
def probe(name,fn):
    try:fn()
    except (AssertionError,ValueError,KeyError,TypeError):result='REJECTED'
    else:result='ESCAPED'
    results.append({'probe':name,'result':result})
def lp(name,before,after):
    assert before in log;probe(name,lambda:physical(log.replace(before,after,1)))
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
probe('extra_unknown_timed_edge',lambda:physical(log+b'Time: 25 <TEACH-AIR-01,0> item delivered: FAKE\r\n'))
probe('extra_subtask_completion',lambda:physical(log+b'Time: 25 subtask 3 seqno 1 within system preparation task 2 on <TEACH-AIR-01,0> completed\r\n'))
for level in ['root','report','table','instance','column']:
    test=copy.deepcopy(report);t=test['report']['tables'][2];target={'root':test,'report':test['report'],'table':t,'instance':t['instances'][0],'column':t['columns'][0]}[level];target['unexpected']='hours'
    probe('extra_'+level+'_metadata',lambda test=test:m.compare_report(c,test,expected,records))
def rp(name,table,row,field,value):
    test=copy.deepcopy(report);t=next(t for t in test['report']['tables'] if t['name']==table);col=[x['name'] for x in t['columns']].index(field);t['instances'][0]['rows'][row][col]=value
    probe(name,lambda:m.compare_report(c,test,expected,records))
for f in ['NSYAL','STREQ','STF','STLOW','SYDTU']:rp('presentation_zero_'+f,'SystemResults',16,f,1e-12)
rp('source_zero_tiny_residue','SystemResults',0,'NSYMP',1e-12)
rp('boolean_zero_substitution','SystemResults',0,'NSYMP',False)
rp('undefined_SYDT_zero','SystemResults',0,'SYDT',0)
rp('stock_ROS_null_zero','StockTotalResults',0,'ROS',0)
rp('stock_PNB_quantity','StockTotalResults',0,'PNB',0)
bound=m.field_bound('SystemResults','NSYMP',expected['SystemResults'][22]['NSYMP'],22,records)
rp('fraction_outside_actual_token_bound','SystemResults',22,'NSYMP',expected['SystemResults'][22]['NSYMP']+bound+1e-6)
rp('nonfinite_fraction','SystemResults',22,'NSYMP',float('nan'))
for field,value in [('database_version','incorrect'),('instance_name','incorrect')]:
    test=copy.deepcopy(export)
    if field=='database_version':test['model'][field]=value
    else:test['model']['tables'][0]['instances'][0][field]=value
    probe('wrong_roundtrip_'+field,lambda test=test:m.check_source_and_roundtrip(c,src,test))
for n,h in pins.items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
v={'decision':'ROOT_TARGETED_GATES_PASS' if all(x['result']=='REJECTED' for x in results) else 'NO_GO_ROOT_MUTATION_ESCAPE','utc':datetime.now(timezone.utc).isoformat(),'method_pins':pins,'baselines':baselines,'baseline_streams':streams,'probes':results,'actual_fraction_bound':bound,'new_native_runs':0,'final_publication_go':False}
out.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');out.chmod(stat.S_IREAD)
print(json.dumps({'receipt':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'decision':v['decision'],'probes':len(results),'escapes':[x for x in results if x['result']=='ESCAPED']},indent=2))
assert v['decision']=='ROOT_TARGETED_GATES_PASS'
