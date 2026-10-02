"""Independent read-only replay for G04.var06 assembly-owned RBD pair."""
import hashlib,json,math,re
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
CASES=CASE.parent
OUT=CASE/'review'/'independent-validation-2026-10-03.json'
RUNS={a:CASE/'runs'/f'g04-var06-assy-{a}-v100-ssh-20261003-01' for a in ('parallel','series')}
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
donor_dir=CASES/contract['schema_donor']['package']
donor_path=donor_dir/'series-input.json'
parent=tables(native_json(parent_path),'model')
donor=tables(native_json(donor_path),'model')
diff=native_json(CASE/'exact-diff.json')
check(sha(parent_path)==contract['accepted_parent']['input_sha256'],'accepted parent input SHA')
check(sha(parent_closure)==contract['accepted_parent']['native_closure_sha256'],'accepted parent closure SHA')
check(sha(donor_path)==contract['schema_donor']['input_sha256'],'schema donor input SHA')
check(sha(CASE/'exact-diff.json')==contract['exact_diff_sha256'],'frozen exact diff SHA')
for name in ('exe','manual','dictionary'):
 check(sha(EXTERNAL[name])==contract['source'][f'{name}_sha256'],f'installed {name} SHA')

sources={};logs={};reports={};closures={}
for arm,run in RUNS.items():
 path=CASE/f'{arm}-input.json';source=tables(native_json(path),'model');sources[arm]=source
 check(sha(path)==contract['input_sha256'][arm],f'{arm} frozen source SHA')
 changed={name:{'before':parent.get(name),'after':source.get(name)} for name in parent.keys()|source.keys() if parent.get(name)!=source.get(name)}
 check(changed==diff['arms'][arm]['changed'],f'{arm} exact parent delta')
 check(set(changed)=={'ProblemDescription','Item','MaterielStructure','MaterielOperationalModes','RBDParallel','RBDParallelStructure','RBDSeries','RBDSeriesStructure'},f'{arm} changed table set')
 for name in ('RBDSeries','RBDSeriesStructure'):
  check(source[name]['columns']==donor[name]['columns'],f'{arm} donor {name} schema')
 check(value(source['Item'],'IID',1)=='TEACH-ASSY-01' and value(source['Item'],'TYPE',1)=='ASSY',f'{arm} ASSY item type')
 check({(value(source['MaterielStructure'],'MID',i),value(source['MaterielStructure'],'MMID',i)) for i in range(len(rows(source['MaterielStructure'])))} >=
       {('TEACH-ASSY-01','TEACH-AIR-01'),('POS-A','TEACH-ASSY-01'),('POS-B','TEACH-ASSY-01'),('POS-C','TEACH-ASSY-01')},f'{arm} physical ASSY position structure')
 check({(value(source['RBDSeriesStructure'],'RBID',i),value(source['RBDSeriesStructure'],'SRBID',i)) for i in range(len(rows(source['RBDSeriesStructure'])))} >=
       {('G04-SYS-ROOT','TEACH-ASSY-01')},f'{arm} system root series contains ASSY')
 check(value(source['MaterielOperationalModes'],'RBID')=='G04-SYS-ROOT' and value(source['MaterielOperationalModes'],'RBID',1)==('G04-ASSY-PARALLEL' if arm=='parallel' else 'G04-ASSY-SERIES'),f'{arm} root and ASSY mode RBD')
 check(parent['FailureMode']==source['FailureMode'] and parent['CMLocation']==source['CMLocation'] and parent['Control']==source['Control'],f'{arm} failure/repair/seed fixed')
 inv=native_json(run/'invocation.json');closure=native_json(run/'closure.json');closures[arm]=closure
 check(sha(run/'invocation.json')==closure['invocation_sha256'],f'{arm} invocation SHA')
 check(inv['run_id']==closure['run_id']==run.name,f'{arm} run ID')
 check(inv['execution_mode']=='session0_ssh_cli' and inv['session_id']==0 and 'sshd.exe' in inv['ssh_ancestor_names'],f'{arm} session0 SSH')
 check(inv['gui']['pid']==13340 and inv['gui']['session_id']==1 and inv['queue_mutex']==r'Global\SimloxIssue18NativeQueue',f'{arm} GUI/mutex')
 check(inv['prelife_log_option_before']==closure['prelife_log_option_after']=='NO',f'{arm} registry restored')
 check(inv['source_hashes_before']==closure['source_hashes_before']==closure['source_hashes_after'],f'{arm} source stability')
 paths={'input':path,'parent':parent_path,'parent_closure':parent_closure,'schema_donor':donor_path,
        'contract':CASE/'contract.json','exact_diff':CASE/'exact-diff.json',
        'builder':CASE/'build.py','diff_builder':CASE/'describe_diff.py',
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
 check([s['arguments'] for s in steps[:4]]==[s['args'] for s in inv['planned_commands']],f'{arm} CLI argument match')
 check(closure['conversion']['errors']==0 and closure['conversion']['notes']==0 and closure['conversion']['warning_codes']==['108'],f'{arm} zero error/reviewed warning')
 check(closure['native_outcome']=='zero_error_reviewed_warnings' and closure['sxo_bytes']>4 and closure['report_present'],f'{arm} usable simulation output')
 check(not re.search(r'\berror\s*#',(run/'run.log').read_text(encoding='utf-8-sig'),re.I),f'{arm} no numbered native error')
 exported=tables(native_json(run/'roundtrip-raw.json'),'model')
 populated=[name for name,t in source.items() if rows(t)]
 check(len(populated)==(25 if arm=='parallel' else 23),f'{arm} authored populated table count')
 for name in populated:
  check(name in exported,f'{arm} exported {name}')
  if name in exported:
   check(exported[name]['columns']==source[name]['columns'],f'{arm} exact columns {name}')
   check(exported[name]['instances']==source[name]['instances'],f'{arm} exact rows {name}')
 logs[arm]=(run/'model.log').read_text(encoding='utf-8-sig')
 reports[arm]=tables(native_json(run/'report-raw.json'),'report')

check({name for name in sources['parallel'] if sources['parallel'][name]!=sources['series'][name]}==
      {'ProblemDescription','MaterielOperationalModes','RBDParallel','RBDParallelStructure','RBDSeries','RBDSeriesStructure'},'paired topology-only table contrast')
for name in sources['parallel']:
 if name not in ('ProblemDescription','MaterielOperationalModes','RBDParallel','RBDParallelStructure','RBDSeries','RBDSeriesStructure'):
  check(sources['parallel'][name]==sources['series'][name],f'paired common {name}')
check(value(sources['parallel']['RBDParallel'],'NBREQ')==1 and value(sources['parallel']['RBDParallel'],'NBOP')==3,'parallel ASSY active 1-of-3')
check({value(sources['parallel']['RBDParallelStructure'],'SRBID',i) for i in range(3)}=={'POS-A','POS-B','POS-C'},'parallel ASSY A/B/C RBD')
check(len(rows(sources['series']['RBDParallel']))==len(rows(sources['series']['RBDParallelStructure']))==0,'series arm no active parallel rows')
check({value(sources['series']['RBDSeriesStructure'],'SRBID',i) for i in range(1,4)}=={'POS-A','POS-B','POS-C'},'series ASSY requires A/B/C')

def event(arm,t,frag):return any(line.startswith(f'Time: {t} ') and frag in line for line in logs[arm].splitlines())
for arm in RUNS:
 check(event(arm,8,'mission starting, duration: 26 : <TEACH-AIR-01,0>'),f'{arm} 26-hour mission start')
 check(event(arm,8.62763,'CM failure mode added') and 'Failure Mode: FM-POS-B on materiel: <POS-B,0>' in logs[arm],f'{arm} matched first POS-B failure')
 check('connection path: TEACH-AIR-01 - TEACH-AIR-01 - TEACH-ASSY-01 - POS-B' in logs[arm],f'{arm} observed nested ASSY connection path')
 check('Item demand arrives' not in logs[arm] and 'Take replacement item' not in logs[arm],f'{arm} no item stock demand')
check(event('parallel',8.62763,'noncritical CM failure mode added') and event('parallel',16.7498,'noncritical CM failure mode added'),'parallel B/A noncritical')
check('Failure Mode: FM-POS-A on materiel: <POS-A,0>' in logs['parallel'] and logs['parallel'].count('CM failure mode added')==2,'parallel second A failure')
check(event('parallel',34,'mission success') and event('parallel',34,'mission completed: <TEACH-AIR-01,0>') and 'mission aborted' not in logs['parallel'],'parallel mission succeeds h34')
check(event('series',8.62763,'critical CM failure mode added') and event('series',8.62763,'mission aborted') and event('series',9.25527,'aborted mission completed'),'series first B critical/abort/return')
check('FM-POS-A' not in logs['series'] and logs['series'].count('CM failure mode added')==1,'series stops before A failure')
for arm,start,end,modes,crit in (('parallel',34,34.5,['FM-POS-B','FM-POS-A'],'NC'),('series',9.25527,9.75527,['FM-POS-B'],'C')):
 for task,mode in enumerate(modes):
  phrase=f'system CM task {task} on <TEACH-AIR-01,0>'
  check(event(arm,start,f'{phrase} started') and event(arm,start,f'{phrase} FMID: {mode}') and event(arm,end,f'{phrase} completed'),f'{arm} CM task {task} identity and half-hour')
  check(f'< {phrase}, {crit}, 0.5>' in logs[arm],f'{arm} CM task {task} criticality')
 check(event(arm,end,'systems ready: 1'),f'{arm} terminal ready')

for arm,rep in reports.items():
 check(set(rep)=={'ProblemDescription','ResultSummary','SystemResults','StockTotalResults'},f'{arm} report tables')
 summary=rep['ResultSummary']
 for name,want in (('NREP',1),('RTILW',0),('RTIUP',36),('MSTF',1),('MSUF',1 if arm=='parallel' else 0)):
  check(near(value(summary,name),want),f'{arm} summary {name}')
 check(near(value(summary,'MTMF'),1 if arm=='parallel' else .04827946424484253),f'{arm} summary MTMF')
 system,stock=rep['SystemResults'],rep['StockTotalResults']
 sr,kr=rows(system),rows(stock)
 check(len(sr)==len(kr)==72,f'{arm} 72 aligned bins')
 return_time=34 if arm=='parallel' else 9.25527
 repair_end=34.5 if arm=='parallel' else 9.75527
 fail_times=[8.62763]+([16.7498] if arm=='parallel' else [])
 for i,(srow,krow) in enumerate(zip(sr,kr)):
  s=i/2;e=s+.5
  sv={c['name']:srow[j] for j,c in enumerate(system['columns'])}
  kv={c['name']:krow[j] for j,c in enumerate(stock['columns'])}
  check(sv['STINT']==kv['STINT']==s and sv['ETINT']==kv['ETINT']==e,f'{arm} aligned interval {i}')
  reserved=overlap(7,8,s,e);operating=overlap(8,return_time,s,e);repair=overlap(return_time,repair_end,s,e)
  ready=1-reserved-operating-repair
  for name,want in (('NSYRY',ready),('NSYMA',reserved+operating),('NSYMO',operating),('NSYMR',reserved),
                    ('NSYRP',repair),('NSYUA',repair),('NSYA',1-repair),('FTMO',operating),('STACC',operating),
                    ('NFAIL',sum(s<=t<e for t in fail_times)),('NREPT',(2 if arm=='parallel' else 1) if s==(34.5 if arm=='parallel' else 9.5) else 0),
                    ('NSYDT',int(s==(34 if arm=='parallel' else 9)))):
   check(near(sv[name],want),f'{arm} system {name} bin {i}')
  check((sv['SYDT'] is None) if s!=(34 if arm=='parallel' else 9) else near(sv['SYDT'],.5),f'{arm} system SYDT bin {i}')
  for name in ('NSYMC','NSYMP','NSYMT','NSYMS','NSYAL','NSYPM','NSYTP','NSYWR','NSYWI','NSYLA','NSYUH','NPMT','NDAM','NPMS','NROBT','NRCFG','STREQ','STF','STLOW','SYDTU','NSYSW','NPSTA','NPSUC'):
   check(sv[name]==0,f'{arm} system {name} zero bin {i}')
  check(kv['PNB']==1 and all((v is None or v==0) for name,v in kv.items() if name not in ('STINT','ETINT','PNB')),f'{arm} stock zero movement bin {i}')
 check(near(value(system,'NSYRY',71),1),f'{arm} terminal ready report')
 check(near(sum(value(system,'NSYMO',i) for i in range(72))*.5,return_time-8),f'{arm} integrated mission operating hours')
 check(near(sum(value(system,'NSYRP',i) for i in range(72))*.5,.5),f'{arm} integrated parallel CM occupancy')

result={'schema':'simlox-g04-var06-independent-readonly/v1',
 'decision':'GO: bounded assembly-owned parallel versus series RBD outcome for matched first POS-B failure',
 'passed':not failures,'checks_passed':checks-len(failures),'checks_total':checks,'failures':failures,
 'raw_seals':sum(len(c['raw']) for c in closures.values()),
 'runs':{a:{'source_sha256':sha(CASE/f'{a}-input.json'),'closure_sha256':sha(RUNS[a]/'closure.json'),
            'model_log_sha256':sha(RUNS[a]/'model.log'),'report_sha256':sha(RUNS[a]/'report-raw.json')} for a in RUNS},
 'observed':{'matched_first_failure':'POS-B h8.62763, connection path includes TEACH-ASSY-01',
             'parallel':'B noncritical, A noncritical h16.7498, mission success h34, two NC CM tasks h34-34.5',
             'series':'B critical, abort h8.62763, return h9.25527, one C CM task h9.25527-9.75527',
             'terminal':'ready1 in both arms; no stock demand'},
 'limits':['One ASSY, one operating mode, one seed/rep and three positions; no general nesting truth table.',
           'Only the first POS-B failure is matched before paths diverge. The parallel arm has a later A failure because its mission continues.',
           'No ASSY failure or repair was configured; observed CM targets the deployed system at leaf-position FMID.',
           'No GUI RBD drawing or cross-engine equivalence claim.']}
OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'passed':result['passed'],'checks_passed':result['checks_passed'],'checks_total':checks,'failures':failures,'output':str(OUT)}))
raise SystemExit(0 if not failures else 1)
