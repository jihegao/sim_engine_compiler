"""Independent read-only replay of G04.var05 sealed positive pair."""
import hashlib,json,math,re
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
CASES=CASE.parent
OUT=CASE/'review'/'independent-validation-2026-10-03.json'
RUNS={a:CASE/'runs'/f'g04-var05-{a}-v100-ssh-20261003-01' for a in ('omitted','included')}
EXTERNAL={
 'python':Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
 'exe':Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
 'manual':Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
 'dictionary':Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def native_json(p):
 data=p.read_text(encoding='utf-8-sig');out=[];q=e=False
 for i,ch in enumerate(data):
  if q:
   out.append(ch)
   if e:e=False
   elif ch=='\\':e=True
   elif ch=='"':q=False
  elif ch=='"':out.append(ch);q=True
  elif ch==',':
   j=i+1
   while j<len(data) and data[j].isspace():j+=1
   if j==len(data) or data[j] not in '}]':out.append(ch)
  else:out.append(ch)
 return json.loads(''.join(out))
def tables(doc,root):return {t['name']:t for t in doc[root]['tables']}
def rows(t):return [r for x in t['instances'] for r in x['rows']]
def value(t,col,index=0):return rows(t)[index][next(i for i,c in enumerate(t['columns']) if c['name']==col)]
def near(a,b,tol=.0005):return isinstance(a,(int,float)) and math.isclose(a,b,abs_tol=tol)
def overlap(a,b,c,d):return max(0,min(b,d)-max(a,c))/(d-c)
checks=0;failures=[]
def check(ok,label):
 global checks
 checks+=1
 if not ok:failures.append(label)

contract=native_json(CASE/'contract.json')
parent_dir=CASES/contract['accepted_parent']['package']
parent_path=parent_dir/'one-input.json'
parent_closure=parent_dir/'runs'/contract['accepted_parent']['run_id']/'closure.json'
parent=tables(native_json(parent_path),'model')
diff=native_json(CASE/'exact-diff.json')
check(sha(parent_path)==contract['accepted_parent']['input_sha256'],'accepted parent input SHA')
check(sha(parent_closure)==contract['accepted_parent']['native_closure_sha256'],'accepted parent closure SHA')
check(sha(CASE/'exact-diff.json')==contract['exact_diff_sha256'],'frozen exact diff SHA')
for name in ('exe','manual','dictionary'):
 check(sha(EXTERNAL[name])==contract['source'][f'{name}_sha256'],f'installed {name} SHA')

sources={};logs={};reports={};closures={}
for arm,run in RUNS.items():
 path=CASE/f'{arm}-input.json'
 source=tables(native_json(path),'model')
 sources[arm]=source
 check(sha(path)==contract['input_sha256'][arm],f'{arm} source SHA')
 changed={name:{'before':parent.get(name),'after':source.get(name)} for name in parent.keys()|source.keys() if parent.get(name)!=source.get(name)}
 check(changed==diff['arms'][arm]['changed'],f'{arm} exact parent delta')
 common={'ProblemDescription','MaterielPosition','MaterielStructure','FailureMode','CMLocation','MaterielOperationalModes'}
 check(set(changed)==common|({'RBDParallel','RBDParallelStructure'} if arm=='included' else set()),f'{arm} changed table set')
 check(value(source['FailureMode'],'FMID',2)=='FM-POS-D' and value(source['FailureMode'],'FRQ',2)==1000000,f'{arm} positive POS-D failure mode')
 check(value(source['MaterielStructure'],'MID',3)=='POS-D' and value(source['MaterielStructure'],'QTYPM',3)==1,f'{arm} physical POS-D installed')
 check(value(source['RBDParallel'],'NBREQ')==1 and value(source['RBDParallel'],'NBOP')==(3 if arm=='omitted' else 4),f'{arm} RBD 1-of-N')
 rbd_ids=[value(source['RBDParallelStructure'],'SRBID',i) for i in range(len(rows(source['RBDParallelStructure'])))]
 check(rbd_ids==(['POS-A','POS-B','POS-C'] if arm=='omitted' else ['POS-A','POS-B','POS-C','POS-D']),f'{arm} RBD membership')
 inv=native_json(run/'invocation.json');closure=native_json(run/'closure.json');closures[arm]=closure
 check(sha(run/'invocation.json')==closure['invocation_sha256'],f'{arm} invocation seal')
 check(inv['run_id']==closure['run_id']==run.name,f'{arm} run identity')
 check(inv['execution_mode']=='session0_ssh_cli' and inv['session_id']==0 and 'sshd.exe' in inv['ssh_ancestor_names'],f'{arm} SSH session0')
 check(inv['gui']['pid']==13340 and inv['gui']['session_id']==1 and inv['queue_mutex']==r'Global\SimloxIssue18NativeQueue',f'{arm} GUI/mutex')
 check(inv['prelife_log_option_before']==closure['prelife_log_option_after']=='NO',f'{arm} registry restored')
 check(inv['source_hashes_before']==closure['source_hashes_before']==closure['source_hashes_after'],f'{arm} source continuity')
 paths={'input':path,'parent':parent_path,'parent_closure':parent_closure,'contract':CASE/'contract.json',
        'exact_diff':CASE/'exact-diff.json','builder':CASE/'build.py','diff_builder':CASE/'describe_diff.py',
        'checker':CASE/'check_roundtrip.py','runner':CASE/'run_native_ssh.ps1',**EXTERNAL}
 for name,file in paths.items():check(sha(file)==closure['source_hashes_before'][name],f'{arm} source seal {name}')
 check(len(closure['raw'])==13,f'{arm} 13 raw seals')
 for name,meta in closure['raw'].items():
  file=run/name
  check(file.exists() and file.stat().st_size==meta['bytes'] and sha(file)==meta['sha256'],f'{arm} raw seal {name}')
 check(sha(run/'input.json')==sha(path),f'{arm} native input copied source')
 steps=native_json(run/'steps.json')
 check([s['name'] for s in steps]==['import','export','calc','jsonreport','check_import_export'],f'{arm} five steps')
 for step in steps:check(step['exit_code']==0 and step['status']=='completed' and step['gui_preserved'],f'{arm} guarded {step["name"]}')
 check([s['arguments'] for s in steps[:4]]==[s['args'] for s in inv['planned_commands']],f'{arm} CLI planned arguments')
 check(closure['conversion']['errors']==0 and closure['conversion']['notes']==0 and closure['conversion']['warning_codes']==['108'],f'{arm} zero error/reviewed warning')
 check(closure['native_outcome']=='zero_error_reviewed_warnings' and closure['sxo_bytes']>4 and closure['report_present'],f'{arm} usable simulation outputs')
 check(not re.search(r'\berror\s*#',(run/'run.log').read_text(encoding='utf-8-sig'),re.I),f'{arm} no numbered converter error')
 exported=tables(native_json(run/'roundtrip-raw.json'),'model')
 populated=[name for name,t in source.items() if rows(t)]
 check(len(populated)==23,f'{arm} 23 authored row-containing tables')
 for name in populated:
  check(name in exported,f'{arm} exported {name}')
  if name in exported:
   check(exported[name]['columns']==source[name]['columns'],f'{arm} authored columns {name}')
   check(exported[name]['instances']==source[name]['instances'],f'{arm} authored rows {name}')
 logs[arm]=(run/'model.log').read_text(encoding='utf-8-sig')
 reports[arm]=tables(native_json(run/'report-raw.json'),'report')

check({name for name in sources['omitted'] if sources['omitted'][name]!=sources['included'][name]}=={'ProblemDescription','RBDParallel','RBDParallelStructure'},'paired difference limited to description and RBD inclusion')
for name in sources['omitted']:
 if name not in ('ProblemDescription','RBDParallel','RBDParallelStructure'):
  check(sources['omitted'][name]==sources['included'][name],f'paired unchanged {name}')
check(rows(sources['included']['RBDParallelStructure'])[:-1]==rows(sources['omitted']['RBDParallelStructure']) and value(sources['included']['RBDParallelStructure'],'SRBID',3)=='POS-D','included adds only POS-D RBD row')
def event(arm,t,frag):return any(line.startswith(f'Time: {t} ') and frag in line for line in logs[arm].splitlines())
for arm in RUNS:
 check(event(arm,8,'mission starting, duration: 26'),f'{arm} common mission starts h8')
 for t,mode,pos in ((8.2973,'FM-POS-B','POS-B'),(10.1716,'FM-POS-D','POS-D')):
  check(event(arm,t,'CM failure mode added'),f'{arm} matched failure {t}')
  check(f'Failure Mode: {mode} on materiel: <{pos},0>' in logs[arm],f'{arm} physical {mode}')
 check('Take replacement item' not in logs[arm] and 'Item demand arrives' not in logs[arm],f'{arm} no stock demand')
check(event('omitted',8.2973,'noncritical CM failure mode added') and event('omitted',10.1716,'critical CM failure mode added'),'omitted B noncritical then D critical')
check(event('omitted',10.1716,'mission aborted') and event('omitted',12.3433,'aborted mission completed'),'omitted abort/return')
check('FM-POS-A' not in logs['omitted'] and logs['omitted'].count('CM failure mode added')==2,'omitted stops before later A failure')
check(event('included',8.2973,'noncritical CM failure mode added') and event('included',10.1716,'noncritical CM failure mode added'),'included B and D noncritical')
check(event('included',13.1113,'noncritical CM failure mode added') and 'Failure Mode: FM-POS-A on materiel: <POS-A,0>' in logs['included'],'included later physical A failure')
check(event('included',34,'mission success') and event('included',34,'mission completed: <TEACH-AIR-01,0>') and 'mission aborted' not in logs['included'],'included success without abort')
for arm,start,end,tasks in (('omitted',12.3433,12.8433,[(1,'FM-POS-D','C'),(0,'FM-POS-B','NC')]),
                            ('included',34,34.5,[(0,'FM-POS-B','NC'),(1,'FM-POS-D','NC'),(2,'FM-POS-A','NC')])):
 for task,mode,crit in tasks:
  phrase=f'system CM task {task} on <TEACH-AIR-01,0>'
  check(event(arm,start,f'{phrase} started') and event(arm,start,f'{phrase} FMID: {mode}') and event(arm,end,f'{phrase} completed'),f'{arm} CM {task} identity/duration')
  check(f'< {phrase}, {crit}, 0.5>' in logs[arm],f'{arm} CM {task} criticality')
 check(event(arm,end,'systems ready: 1'),f'{arm} terminal ready')

for arm,rep in reports.items():
 check(set(rep)=={'ProblemDescription','ResultSummary','SystemResults','StockTotalResults'},f'{arm} report tables')
 summary=rep['ResultSummary']
 check(value(summary,'NREP')==1 and value(summary,'RTILW')==0 and value(summary,'RTIUP')==36 and value(summary,'MSTF')==1,f'{arm} summary horizon')
 check(near(value(summary,'MSUF'),0 if arm=='omitted' else 1),f'{arm} summary mission success factor')
 check(near(value(summary,'MTMF'),.16704952716827393 if arm=='omitted' else 1),f'{arm} summary MTMF')
 sys,stock=rep['SystemResults'],rep['StockTotalResults']
 sr,kr=rows(sys),rows(stock)
 check(len(sr)==len(kr)==72,f'{arm} 72 aligned bins')
 return_time=12.3433 if arm=='omitted' else 34
 repair_end=12.8433 if arm=='omitted' else 34.5
 fail_times=[8.2973,10.1716]+([] if arm=='omitted' else [13.1113])
 for i,(srow,krow) in enumerate(zip(sr,kr)):
  s=i/2;e=s+.5
  sv={c['name']:srow[j] for j,c in enumerate(sys['columns'])}
  kv={c['name']:krow[j] for j,c in enumerate(stock['columns'])}
  check(sv['STINT']==kv['STINT']==s and sv['ETINT']==kv['ETINT']==e,f'{arm} aligned interval {i}')
  reserved=overlap(7,8,s,e);operating=overlap(8,return_time,s,e);repair=overlap(return_time,repair_end,s,e)
  ready=1-reserved-operating-repair
  for name,want in (('NSYRY',ready),('NSYMA',reserved+operating),('NSYMO',operating),('NSYMR',reserved),
                    ('NSYRP',repair),('NSYUA',repair),('NSYA',1-repair),('FTMO',operating),('STACC',operating),
                    ('NFAIL',sum(s<=t<e for t in fail_times)),('NREPT',(2 if arm=='omitted' else 3) if s==(12.5 if arm=='omitted' else 34.5) else 0),
                    ('NSYDT',int(s==(12 if arm=='omitted' else 34)))):
   check(near(sv[name],want),f'{arm} SystemResults {name} bin {i}')
  check((sv['SYDT'] is None) if s!=(12 if arm=='omitted' else 34) else near(sv['SYDT'],.5),f'{arm} SystemResults SYDT bin {i}')
  for name in ('NSYMC','NSYMP','NSYMT','NSYMS','NSYAL','NSYPM','NSYTP','NSYWR','NSYWI','NSYLA','NSYUH','NPMT','NDAM','NPMS','NROBT','NRCFG','STREQ','STF','STLOW','SYDTU','NSYSW','NPSTA','NPSUC'):
   check(sv[name]==0,f'{arm} SystemResults {name} zero bin {i}')
  check(kv['PNB']==1 and all((v is None or v==0) for name,v in kv.items() if name not in ('STINT','ETINT','PNB')),f'{arm} StockTotalResults no-movement bin {i}')
 check(near(value(sys,'NSYRY',71),1),f'{arm} terminal ready report')
 check(near(sum(value(sys,'NSYMO',i) for i in range(72))*.5,return_time-8),f'{arm} integrated operating hours')
 check(near(sum(value(sys,'NSYRP',i) for i in range(72))*.5,.5),f'{arm} integrated parallel CM occupancy')

result={'schema':'simlox-g04-var05-independent-readonly/v1',
 'decision':'GO: bounded omitted POS-D critical series effect versus included active 1-of-4 path',
 'passed':not failures,'checks_passed':checks-len(failures),'checks_total':checks,'failures':failures,
 'raw_seals':sum(len(c['raw']) for c in closures.values()),
 'runs':{a:{'source_sha256':sha(CASE/f'{a}-input.json'),'closure_sha256':sha(RUNS[a]/'closure.json'),
            'model_log_sha256':sha(RUNS[a]/'model.log'),'report_sha256':sha(RUNS[a]/'report-raw.json')} for a in RUNS},
 'observed':{'matched_failures':['POS-B h8.2973','POS-D h10.1716'],
             'omitted':'D critical h10.1716, abort/return h12.3433, C+NC CM to12.8433; two failures',
             'included':'D noncritical h10.1716, later POS-A noncritical h13.1113, mission success h34, three NC CM to34.5',
             'terminal':'one system ready in each arm; no stock demand'},
 'limits':['One physical POS-D and one mission mode, one seed/rep; no general default-series truth table.',
           'Later A failure occurs only in included arm because omitted mission ended earlier; compare B/D matched prefix, not full path equality.',
           'Positive outcome binds POS-D RBD inclusion plus NBOP3-to-4 alignment; no independent NBOP-only claim.',
           'No arbitrary omitted level, GUI RBD visual or cross-engine behavior.']}
OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'passed':result['passed'],'checks_passed':result['checks_passed'],'checks_total':checks,'failures':failures,'output':str(OUT)}))
raise SystemExit(0 if not failures else 1)
