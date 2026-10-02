"""Independent read-only replay of G04.var03 QTYPB multiplicity evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
CASES=CASE.parent
CHILD=CASE/'runs'/'g04-var03-qtypb2-v100-ssh-20261003-01'
OUT=CASE/'review'/'independent-validation-2026-10-03.json'
EXTERNAL={
 'python':Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
 'exe':Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
 'manual':Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
 'dictionary':Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'),
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def native_json(path):
 data=path.read_text(encoding='utf-8-sig');out=[];quoted=escaped=False
 for i,ch in enumerate(data):
  if quoted:
   out.append(ch)
   if escaped:escaped=False
   elif ch=='\\':escaped=True
   elif ch=='"':quoted=False
  elif ch=='"':out.append(ch);quoted=True
  elif ch==',':
   j=i+1
   while j<len(data) and data[j].isspace():j+=1
   if j==len(data) or data[j] not in '}]':out.append(ch)
  else:out.append(ch)
 return json.loads(''.join(out))
def tables(doc,root):return {t['name']:t for t in doc[root]['tables']}
def rows(table):return [r for x in table['instances'] for r in x['rows']]
def value(table,col,index=0):return rows(table)[index][next(i for i,c in enumerate(table['columns']) if c['name']==col)]
def near(a,b,tol=.0005):return isinstance(a,(int,float)) and math.isclose(a,b,abs_tol=tol)
def overlap(a,b,c,d):return max(0,min(b,d)-max(a,c))/(d-c)
checks=0;failures=[]
def check(ok,label):
 global checks
 checks+=1
 if not ok:failures.append(label)

contract=native_json(CASE/'contract.json')
parent_dir=CASES/contract['accepted_parent']['package']
parent_path=parent_dir/'two-input.json'
parent_run=parent_dir/'runs'/contract['accepted_parent']['run_id']
parent_closure=parent_run/'closure.json'
source_path=CASE/'native-input.json'
parent=tables(native_json(parent_path),'model');source=tables(native_json(source_path),'model')
diff=native_json(CASE/'exact-diff.json')
check(sha(parent_path)==contract['accepted_parent']['input_sha256'],'accepted parent input SHA')
check(sha(parent_closure)==contract['accepted_parent']['native_closure_sha256'],'accepted parent closure SHA')
check(sha(source_path)==contract['input_sha256'],'frozen child source SHA')
check(sha(CASE/'exact-diff.json')==contract['exact_diff_sha256'],'frozen diff SHA')
for name in ('exe','manual','dictionary'):
 check(sha(EXTERNAL[name])==contract['source'][f'{name}_sha256'],f'installed {name} SHA')
changed={name:{'before':parent.get(name),'after':source.get(name)} for name in parent.keys()|source.keys() if parent.get(name)!=source.get(name)}
check(changed==diff['changed'],'exact four-table parent delta')
check(set(changed)=={'ProblemDescription','MaterielStructure','RBDParallel','RBDParallelStructure'},'four changed business tables')
check(value(parent['MaterielStructure'],'QTYPM',2)==1 and value(source['MaterielStructure'],'QTYPM',2)==2 and value(source['MaterielStructure'],'MID',2)=='POS-C','installed C quantity one to two')
check(value(parent['RBDParallelStructure'],'QTYPB',2)==1 and value(source['RBDParallelStructure'],'QTYPB',2)==2 and value(source['RBDParallelStructure'],'SRBID',2)=='POS-C','RBD C block quantity one to two')
check(value(parent['RBDParallel'],'NBOP')==3 and value(source['RBDParallel'],'NBOP')==4 and value(source['RBDParallel'],'NBREQ')==2,'active 2-of-4 child vs 2-of-3 parent')
for name in ('FailureMode','MaterielFailureMode','MissionType','OperationProfile','Control'):
 if name in source and name in parent:check(source[name]==parent[name],f'{name} unchanged')

inv=native_json(CHILD/'invocation.json');closure=native_json(CHILD/'closure.json')
check(sha(CHILD/'invocation.json')==closure['invocation_sha256'],'invocation SHA seal')
check(inv['run_id']==closure['run_id']==CHILD.name,'run ID')
check(inv['execution_mode']=='session0_ssh_cli' and inv['session_id']==0 and 'sshd.exe' in inv['ssh_ancestor_names'],'guarded SSH session0')
check(inv['gui']['pid']==13340 and inv['gui']['session_id']==1 and inv['queue_mutex']==r'Global\SimloxIssue18NativeQueue','GUI identity and mutex')
check(inv['prelife_log_option_before']==closure['prelife_log_option_after']=='NO','registry option restored')
check(inv['source_hashes_before']==closure['source_hashes_before']==closure['source_hashes_after'],'run source stability')
paths={'input':source_path,'parent':parent_path,'parent_closure':parent_closure,'contract':CASE/'contract.json',
       'exact_diff':CASE/'exact-diff.json','builder':CASE/'build.py','diff_builder':CASE/'describe_diff.py',
       'checker':CASE/'check_roundtrip.py','runner':CASE/'run_native_ssh.ps1',**EXTERNAL}
for name,path in paths.items():check(sha(path)==closure['source_hashes_before'][name],f'sealed source {name}')
check(len(closure['raw'])==13,'13 sealed raw files')
for name,meta in closure['raw'].items():
 path=CHILD/name
 check(path.exists() and path.stat().st_size==meta['bytes'] and sha(path)==meta['sha256'],f'sealed raw {name}')
check(sha(CHILD/'input.json')==sha(source_path),'run input is frozen source')
steps=native_json(CHILD/'steps.json')
check([s['name'] for s in steps]==['import','export','calc','jsonreport','check_import_export'],'five native steps')
for step in steps:check(step['exit_code']==0 and step['status']=='completed' and step['gui_preserved'],f'guarded {step["name"]}')
check([s['arguments'] for s in steps[:4]]==[s['args'] for s in inv['planned_commands']],'executed planned CLI arguments')
check(closure['conversion']['errors']==0 and closure['conversion']['notes']==0 and closure['conversion']['warning_codes']==['108'],'converter zero errors/reviewed warning')
check(closure['native_outcome']=='zero_error_reviewed_warnings' and closure['sxo_bytes']>4 and closure['report_present'],'usable SXO and report')
check(not re.search(r'\berror\s*#',(CHILD/'run.log').read_text(encoding='utf-8-sig'),re.I),'native run log no numbered error')
export=tables(native_json(CHILD/'roundtrip-raw.json'),'model')
populated=[name for name,t in source.items() if rows(t)]
check(len(populated)==23,'23 authored row-containing tables')
for name in populated:
 check(name in export,f'exported {name}')
 if name in export:
  check(export[name]['columns']==source[name]['columns'],f'authored columns {name}')
  check(export[name]['instances']==source[name]['instances'],f'authored rows {name}')

child_log=(CHILD/'model.log').read_text(encoding='utf-8-sig')
parent_log=(parent_run/'model.log').read_text(encoding='utf-8-sig')
def event(log,t,frag):return any(line.startswith(f'Time: {t} ') and frag in line for line in log.splitlines())
for log,label in ((child_log,'child'),(parent_log,'parent')):
 for time,mode,pos in ((8.62763,'FM-POS-B','POS-B'),(16.7498,'FM-POS-A','POS-A')):
  check(event(log,time,'CM failure mode added'),f'{label} failure at {time}')
  check(f'Failure Mode: {mode} on materiel: <{pos},0>' in log,f'{label} {mode} physical identity')
 check(log.count('CM failure mode added')==2,f'{label} exactly two failures')
check(event(child_log,8,'mission starting, duration: 26') and event(parent_log,8,'mission starting, duration: 26'),'matched long mission launch')
check(event(child_log,34,'mission success') and event(child_log,34,'mission completed: <TEACH-AIR-01,0>'),'2-of-4 mission succeeds h34')
check('mission aborted' not in child_log and '< system CM task 0 on <TEACH-AIR-01,0>, NC, 0.5>' in child_log and '< system CM task 1 on <TEACH-AIR-01,0>, NC, 0.5>' in child_log,'child noncritical failures and no abort')
check(event(parent_log,16.7498,'mission aborted') and event(parent_log,23.2498,'aborted mission completed') and '< system CM task 0 on <TEACH-AIR-01,0>, C, 0.5>' in parent_log,'2-of-3 parent abort and critical CM')
for log,label,start,end in ((child_log,'child',34,34.5),(parent_log,'parent',23.2498,23.7498)):
 for task,mode in ((0,'FM-POS-B'),(1,'FM-POS-A')):
  phrase=f'system CM task {task} on <TEACH-AIR-01,0>'
  check(event(log,start,f'{phrase} started') and event(log,start,f'{phrase} FMID: {mode}') and event(log,end,f'{phrase} completed'),f'{label} CM task {task} interval/identity')
check(event(child_log,34.5,'systems ready: 1') and event(parent_log,23.7498,'systems ready: 1'),'both terminal ready after CM')
check('Item demand arrives' not in child_log and 'Take replacement item' not in child_log,'child no stock demand')

reports={'child':tables(native_json(CHILD/'report-raw.json'),'report'),
         'parent':tables(native_json(parent_run/'report-raw.json'),'report')}
check(set(reports['child'])==set(reports['parent'])=={'ProblemDescription','ResultSummary','SystemResults','StockTotalResults'},'report table set')
for arm,rep in reports.items():
 check(len(rows(rep['SystemResults']))==len(rows(rep['StockTotalResults']))==72,f'{arm} 72 half-hour bins')
 summary=rep['ResultSummary']
 for name,want in (('NREP',1),('RTILW',0),('RTIUP',36),('MSTF',1),('MSUF',1 if arm=='child' else 0)):
  check(near(value(summary,name),want),f'{arm} summary {name}')
 system,stock=rep['SystemResults'],rep['StockTotalResults']
 mission_end=34 if arm=='child' else 23.2498
 repair_start=34 if arm=='child' else 23.2498
 repair_end=34.5 if arm=='child' else 23.7498
 for i,(srow,krow) in enumerate(zip(rows(system),rows(stock))):
  s=i/2;e=s+.5
  sv={c['name']:srow[j] for j,c in enumerate(system['columns'])}
  kv={c['name']:krow[j] for j,c in enumerate(stock['columns'])}
  check(sv['STINT']==kv['STINT']==s and sv['ETINT']==kv['ETINT']==e,f'{arm} interval bin {i}')
  reserved=overlap(7,8,s,e)
  operating=overlap(8,mission_end,s,e)
  repair=overlap(repair_start,repair_end,s,e)
  ready=1-reserved-operating-repair
  for name,want in (('NSYRY',ready),('NSYMA',reserved+operating),('NSYMO',operating),('NSYMR',reserved),
                    ('NSYRP',repair),('NSYUA',repair),('NSYA',1-repair),('FTMO',operating),('STACC',operating),
                    ('NFAIL',int(s in (8.5,16.5))),('NREPT',2 if s==(34.5 if arm=='child' else 23.5) else 0),
                    ('NSYDT',int(s==(34 if arm=='child' else 23)))):
   check(near(sv[name],want),f'{arm} system {name} bin {i}')
  check((sv['SYDT'] is None) if s!=(34 if arm=='child' else 23) else near(sv['SYDT'],.5),f'{arm} down-event duration bin {i}')
  for name in ('NSYMC','NSYMP','NSYMT','NSYMS','NSYAL','NSYPM','NSYTP','NSYWR','NSYWI','NSYLA','NSYUH','NPMT','NDAM','NPMS','NROBT','NRCFG','STREQ','STF','STLOW','SYDTU','NSYSW','NPSTA','NPSUC'):
   check(sv[name]==0,f'{arm} system {name} zero bin {i}')
  check(kv['PNB']==1 and all((v is None or v==0) for name,v in kv.items() if name not in ('STINT','ETINT','PNB')),f'{arm} no stock movement bin {i}')
 check(near(value(system,'NSYRY',71),1),f'{arm} terminal ready1')
 check(near(sum(value(system,'NSYMO',i) for i in range(72))*.5,mission_end-8),f'{arm} integrated mission/system operating hours')
 check(near(sum(value(system,'NSYRP',i) for i in range(72))*.5,.5),f'{arm} integrated half-hour CM occupancy')
check(value(reports['child']['ResultSummary'],'MTMF')==1 and value(reports['parent']['ResultSummary'],'MTMF')<1,'summary success/abort metric contrast')

result={'schema':'simlox-g04-var03-independent-readonly/v1',
 'decision':'GO: bounded matched-seed 2-of-4 QTYPB/physical multiplicity outcome contrast',
 'passed':not failures,'checks_passed':checks-len(failures),'checks_total':checks,'failures':failures,
 'raw_seals':len(closure['raw']),'source_sha256':sha(source_path),'child_closure_sha256':sha(CHILD/'closure.json'),
 'parent_closure_sha256':sha(parent_closure),'child_model_log_sha256':sha(CHILD/'model.log'),
 'parent_model_log_sha256':sha(parent_run/'model.log'),'child_report_sha256':sha(CHILD/'report-raw.json'),
 'parent_report_sha256':sha(parent_run/'report-raw.json'),
 'observed':{'same_failure_samples':['POS-B h8.62763','POS-A h16.7498'],
             'parent':'2-of-3 abort h16.7498, return h23.2498, critical CM h23.2498-23.7498',
             'child':'2-of-4 mission succeeds h34, noncritical CM h34-34.5; terminal ready1',
             'stock':'no demand or backorder in either arm'},
 'limits':['Child changes physical POS-C QTYPM, RBD QTYPB and NBOP together; these are a controlled aligned multiplicity package, not independently isolated parameter effects.',
           'One model, seed, replication, two observed failures; no population reliability, arbitrary multiplicity, or all-branches-failed claim.',
           'No passive branch, switch delay, online maintenance, GUI RBD visual or cross-engine parity.']}
OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'passed':result['passed'],'checks_passed':result['checks_passed'],'checks_total':checks,'failures':failures,'output':str(OUT)}))
raise SystemExit(0 if not failures else 1)
