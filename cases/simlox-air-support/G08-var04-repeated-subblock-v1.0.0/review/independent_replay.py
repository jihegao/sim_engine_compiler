"""Independent read-only source and raw replay for G08.var04 QTYPM alignment."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
CASES=CASE.parent
OUT=CASE/'review'/'independent-validation-2026-10-03.json'
RUNS={'repeated':CASE/'runs'/'g08-var04-repeated-v100-ssh-20261003-01'}
EXTERNAL={
 'python':Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
 'exe':Path(r'C:\Program Files\Systecon\SIMLOX\Simlox.exe'),
 'manual':Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'),
 'dictionary':Path(r'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def native_json(p):
 data=p.read_text(encoding='utf-8-sig');out=[];quoted=escaped=False
 for i,c in enumerate(data):
  if quoted:
   out.append(c)
   if escaped:escaped=False
   elif c=='\\':escaped=True
   elif c=='"':quoted=False
  elif c=='"':out.append(c);quoted=True
  elif c==',':
   j=i+1
   while j<len(data) and data[j].isspace():j+=1
   if j==len(data) or data[j] not in '}]':out.append(c)
  else:out.append(c)
 return json.loads(''.join(out))
def tables(doc,root):return {t['name']:t for t in doc[root]['tables']}
def rows(t):return [r for i in t['instances'] for r in i['rows']]
def records(t):
 cols=[c['name'] for c in t['columns']]
 return [dict(zip(cols,r)) for r in rows(t)]
def near(a,b,tol=.0006):return isinstance(a,(int,float)) and math.isclose(a,b,abs_tol=tol)
def occupancy(a,b,start):return 2*max(0,min(b,start+.5)-max(a,start))
checks=0;failures=[]
def check(ok,label):
 global checks
 checks+=1
 if not ok:failures.append(label)

contract=native_json(CASE/'contract.json')
parent_dir=CASES/contract['accepted_parent']['package']
parent_file=parent_dir/'high-input.json'
parent_run=parent_dir/'runs'/contract['accepted_parent']['run_id']
parent=tables(native_json(parent_file),'model')
diff=native_json(CASE/'exact-diff.json')
check(sha(parent_file)==contract['accepted_parent']['input_sha256'],'accepted parent input SHA')
check(sha(parent_run/'closure.json')==contract['accepted_parent']['native_closure_sha256'],
      'accepted parent closure SHA')
check(sha(CASE/'exact-diff.json')==contract['exact_diff_sha256'],'frozen exact diff SHA')
for key in ('exe','manual','dictionary'):
 check(sha(EXTERNAL[key])==contract['source'][f'{key}_sha256'],f'installed {key} SHA')
dictionary=EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
tree_fields=[s.split(';')[2] for s in dictionary.splitlines() if s.startswith('RBDTree;')]
child_fields=[s.split(';')[2] for s in dictionary.splitlines() if s.startswith('RBDTreeStructure;')]
check(tree_fields==['RBID','DESCR','NBREQ','NOTE'],'dictionary tree schema')
check(child_fields==['RBID','MRBID','SRBID','MBOPM','SBOPM','QTYPM','NOTE'],
      'dictionary mother/child path schema')

sources={};closures={};logs={};reports={}
delta_names={'ProblemDescription','MaterielStructure','RBDTreeStructure'}
for arm,run in RUNS.items():
 source_file=CASE/'repeated-input.json'
 source=tables(native_json(source_file),'model');sources[arm]=source
 check(sha(source_file)==contract['input_sha256'],f'{arm} source SHA')
 changed={name:{'before':parent.get(name),'after':source.get(name)}
          for name in parent.keys()|source.keys() if parent.get(name)!=source.get(name)}
 check(changed==diff['changed'] and set(changed)==delta_names,
       f'{arm} exact three-table parent delta')
 for name in source:
  if name not in delta_names:check(source[name]==parent[name],f'{arm} fixed {name}')
 check(parent['FailureMode']==source['FailureMode'] and parent['CMLocation']==source['CMLocation']
       and parent['Control']==source['Control'],f'{arm} fixed failure/CM/seed')
 positions={r['MPID'] for r in records(source['MaterielPosition'])}
 check(positions=={'POS-A','POS-B','POS-C','POS-D'},f'{arm} four physical positions')
 material=records(source['MaterielStructure'])
 old_material=records(parent['MaterielStructure'])
 check(len(material)==len(old_material) and
       [(r['MID'],r['MMID'],r['QTYPM']) for r in material if r['MID']=='POS-C']==
       [('POS-C','TEACH-AIR-01',2)] and
       [(r['MID'],r['MMID'],r['QTYPM']) for r in old_material if r['MID']=='POS-C']==
       [('POS-C','TEACH-AIR-01',1)],f'{arm} physical C QTYPM 1-to-2')
 check({r['MID'] for r in records(source['FailureMode'])}=={'POS-A','POS-B'},
       f'{arm} only A/B failure modes')
 mode=records(source['MaterielOperationalModes'])
 check(mode[0]['RBID']=='G08-TREE' and {r['MID'] for r in mode[1:]}==positions,
       f'{arm} tree root and four G04-OPS positions')
 check('RBDParallel' not in source and 'RBDParallelStructure' not in source,
       f'{arm} no parallel RBD alternative')
 tree=records(source['RBDTree'])
 check(len(tree)==1 and tree[0]['RBID']=='G08-TREE' and tree[0]['NBREQ']==3,
       f'{arm} fixed NBREQ3 threshold')
 edges=records(source['RBDTreeStructure'])
 root='POS-A'
 leaves={'POS-B','POS-C','POS-D'}
 check(len(edges)==3 and {(e['MRBID'],e['SRBID']) for e in edges}==
       {(root,leaf) for leaf in leaves},f'{arm} common root and three leaves')
 check(all(e['RBID']=='G08-TREE' and e['MBOPM']==e['SBOPM']=='G04-OPS' and
           e['QTYPM']==(2 if e['SRBID']=='POS-C' else 1) for e in edges),
       f'{arm} aligned C tree QTYPM2, others1')
 check([(e['SRBID'],e['QTYPM']) for e in records(parent['RBDTreeStructure'])]==
       [('POS-B',1),('POS-C',1),('POS-D',1)],f'{arm} accepted parent all QTYPM1')
 def paths_alive(failed):
  return 0 if root in failed else sum(e['QTYPM'] for e in edges if e['SRBID'] not in failed)
 check(paths_alive({'POS-B'})==3,f'{arm} B loss leaves three aligned paths')
 check(paths_alive({'POS-A','POS-B'})==0,f'{arm} after B/A no functional paths')

 inv=native_json(run/'invocation.json');cl=native_json(run/'closure.json');closures[arm]=cl
 check(sha(run/'invocation.json')==cl['invocation_sha256'],f'{arm} invocation seal')
 check(inv['run_id']==cl['run_id']==run.name,f'{arm} run ID')
 check(inv['execution_mode']=='session0_ssh_cli' and inv['session_id']==0 and
       'sshd.exe' in inv['ssh_ancestor_names'],f'{arm} SSH session0')
 check(inv['gui']['pid']==13340 and inv['gui']['session_id']==1 and
       inv['queue_mutex']==r'Global\SimloxIssue18NativeQueue',f'{arm} GUI/mutex')
 check(inv['prelife_log_option_before']==cl['prelife_log_option_after']=='NO',
       f'{arm} registry restored')
 check(inv['source_hashes_before']==cl['source_hashes_before']==cl['source_hashes_after'],
       f'{arm} source stable before/after')
 paths={'input':source_file,'parent':parent_file,'parent_closure':parent_run/'closure.json',
        'contract':CASE/'contract.json','exact_diff':CASE/'exact-diff.json',
        'builder':CASE/'build.py','diff_builder':CASE/'describe_diff.py',
        'checker':CASE/'check_roundtrip.py','runner':CASE/'run_native_ssh.ps1',**EXTERNAL}
 for name,path in paths.items():check(sha(path)==cl['source_hashes_before'][name],
                                    f'{arm} source seal {name}')
 check(len(cl['raw'])==13,f'{arm} 13 raw seals')
 for name,meta in cl['raw'].items():
  path=run/name
  check(path.exists() and path.stat().st_size==meta['bytes'] and sha(path)==meta['sha256'],
        f'{arm} raw seal {name}')
 check(sha(run/'input.json')==sha(source_file),f'{arm} native source copy')
 steps=native_json(run/'steps.json')
 check([s['name'] for s in steps]==['import','export','calc','jsonreport','check_import_export'],
       f'{arm} five steps')
 for s in steps:check(s['exit_code']==0 and s['status']=='completed' and s['gui_preserved'],
                    f'{arm} guarded {s["name"]}')
 check([s['arguments'] for s in steps[:4]]==[s['args'] for s in inv['planned_commands']],
       f'{arm} planned CLI arguments')
 check(cl['conversion']['errors']==0 and cl['conversion']['notes']==0 and
       cl['conversion']['warning_codes']==['108'],f'{arm} zero errors/reviewed warning')
 check(cl['sxo_bytes']>4 and cl['report_present'] and
       cl['native_outcome']=='zero_error_reviewed_warnings',f'{arm} usable native results')
 check(not re.search(r'\berror\s*#',(run/'run.log').read_text(encoding='utf-8-sig'),re.I),
       f'{arm} no converter error text')
 exported=tables(native_json(run/'roundtrip-raw.json'),'model')
 populated=[name for name,t in source.items() if rows(t)]
 check(len(populated)==23,f'{arm} 23 populated tables')
 for name in populated:
  check(name in exported,f'{arm} exported {name}')
  if name in exported:
   check(source[name]['columns']==exported[name]['columns'],f'{arm} exact {name} columns')
   check(source[name]['instances']==exported[name]['instances'],f'{arm} exact {name} rows')
 logs[arm]=(run/'model.log').read_text(encoding='utf-8-sig')
 reports[arm]=tables(native_json(run/'report-raw.json'),'report')

def event(arm,hour,part):
 return any(s.startswith(f'Time: {hour} ') and part in s for s in logs[arm].splitlines())
for arm in RUNS:
 check(event(arm,7,'mission allocates system: <TEACH-AIR-01,0>') and
       event(arm,8,'mission starting, duration: 26'),f'{arm} mission h8 start')
 check(event(arm,8.62763,'CM failure mode added') and
       'Failure Mode: FM-POS-B on materiel: <POS-B,0>' in logs[arm],
       f'{arm} matched first B failure')
 check(all(f'Failure Mode: FM-POS-{x}' not in logs[arm] for x in 'CD'),
       f'{arm} C/D healthy in log')
 check('Item demand arrives' not in logs[arm],f'{arm} no stock demand')
check(event('repeated',8.62763,'noncritical CM failure mode added') and
      event('repeated',16.7498,'critical CM failure mode added') and
      'Failure Mode: FM-POS-A on materiel: <POS-A,0>' in logs['repeated'] and
      logs['repeated'].count('CM failure mode added')==2,
      'repeated C: B noncritical, A critical')
check(event('repeated',16.7498,'mission aborted') and
      event('repeated',23.2498,'aborted mission completed') and
      'mission success' not in logs['repeated'],'repeated abort/return')
parent_log=(parent_run/'model.log').read_text(encoding='utf-8-sig')
check('Time: 8.62763 <TEACH-AIR-01,0> critical CM failure mode added' in parent_log and
      'Time: 8.62763 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted' in parent_log,
      'accepted NBREQ3 parent B critical and aborts')
check('Time: 8.62763 <TEACH-AIR-01,0> noncritical CM failure mode added' in
      logs['repeated'],'matched B time and identity with changed severity')
for arm,start,end,failures_expected in (('repeated',23.2498,23.7498,('FM-POS-B','FM-POS-A')),):
 for task,fm in enumerate(failures_expected):
  label=f'system CM task {task} on <TEACH-AIR-01,0>'
  check(event(arm,start,label+' started') and event(arm,start,label+' FMID: '+fm) and
        event(arm,end,label+' completed'),f'{arm} CM {task} identity/time')
  check(f'< {label}, C, 0.5>' in logs[arm],f'{arm} CM {task} criticality')
 check(event(arm,end,'systems ready: 1'),f'{arm} terminal ready event')

for arm,rep in reports.items():
 check(set(rep)=={'ProblemDescription','ResultSummary','SystemResults','StockTotalResults'},
       f'{arm} report table set')
 summary=records(rep['ResultSummary'])[0]
 factor=.5865303874015808
 for name,want in (('NREP',1),('RTILW',0),('RTIUP',36),('MTMF',factor),
                   ('STMF',factor),('MSTF',1),('MSUF',0)):
  check(near(summary[name],want),f'{arm} summary {name}')
 for name in ('RSMTMF','RSMSTF','RSMSUF','RSSTMF'):
  check(summary[name]==0,f'{arm} one-rep precision {name}')
 sys=records(rep['SystemResults']);stock=records(rep['StockTotalResults'])
 check(len(sys)==len(stock)==72,f'{arm} 72 aligned bins')
 ret=23.2498
 repair_end=23.7498
 fail_times=(8.62763,16.7498)
 for i,(s,k) in enumerate(zip(sys,stock)):
  start=i*.5;end=start+.5
  check(s['STINT']==k['STINT']==start and s['ETINT']==k['ETINT']==end,
        f'{arm} aligned interval {i}')
  reserved=occupancy(7,8,start);flight=occupancy(8,ret,start)
  repair=occupancy(ret,repair_end,start)
  expected={'NSYRY':1-reserved-flight-repair,'NSYMA':reserved+flight,
            'NSYMO':flight,'NSYMR':reserved,'NSYRP':repair,'NSYUA':repair,
            'NSYA':1-repair,'FTMO':flight,'STACC':flight,
            'NFAIL':sum(start<=t<end for t in fail_times)}
  for name,want in expected.items():check(near(s[name],want),f'{arm} system {name} bin {i}')
  completion=47
  downtime=46
  check(s['NREPT']==(len(fail_times) if i==completion else 0),
        f'{arm} repair completions bin {i}')
  check(s['NSYDT']==(1 if i==downtime else 0),f'{arm} downtime marker bin {i}')
  check((near(s['SYDT'],.5) if i==downtime else s['SYDT'] is None),
        f'{arm} downtime duration bin {i}')
  for name in ('NSYMC','NSYMP','NSYMT','NSYMS','NSYAL','NSYPM','NSYTP',
               'NSYWR','NSYWI','NSYLA','NSYUH','NPMT','NDAM','NPMS',
               'NROBT','NRCFG','STREQ','STF','STLOW','SYDTU','NSYSW',
               'NPSTA','NPSUC'):
   check(s[name]==0,f'{arm} system {name} absent bin {i}')
  check(k['PNB']==1 and all(v is None or v==0 for name,v in k.items()
                            if name not in ('STINT','ETINT','PNB')),
        f'{arm} stock unchanged bin {i}')
 check(near(sys[-1]['NSYRY'],1),f'{arm} terminal ready report')
 check(near(sum(s['NSYMO'] for s in sys)*.5,ret-8),f'{arm} integrated operating hours')
 check(near(sum(s['NSYRP'] for s in sys)*.5,.5),f'{arm} integrated CM occupancy')

result={'schema':'simlox-g08-var04-independent-readonly/v1',
 'decision':'GO: bounded aligned physical/tree POS-C QTYPM2 contrast' if not failures else 'NO-GO: independent replay failed',
 'passed':not failures,'checks_passed':checks-len(failures),'checks_total':checks,
 'failures':failures,'raw_seals':sum(len(c['raw']) for c in closures.values()),
 'runs':{a:{'source_sha256':sha(CASE/'repeated-input.json'),
            'closure_sha256':sha(run/'closure.json'),
            'model_log_sha256':sha(run/'model.log'),
            'report_sha256':sha(run/'report-raw.json')} for a,run in RUNS.items()},
 'observed':{'parent':'NBREQ3 parent B h8.62763 critical and aborts',
             'child':'same B first h8.62763 noncritical; A h16.7498 critical abort, return h23.2498',
             'terminal':'two half-hour C system CM tasks, ready1 and no stock movement'},
 'limits':['Three remaining leaf paths after B are inferred from aligned physical/tree QTYPM2 for healthy POS-C; the log does not identify copies or paths.',
           'Both physical and RBDTreeStructure QTYPM changed together, so the effect of either field alone is not isolated.',
           'One A-root NBREQ3 topology, healthy C, fixed seed/replication. No arbitrary multiplicity, multi-root, other failure order, population or cross-engine claim.']}
OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'passed':result['passed'],'checks_passed':result['checks_passed'],
                  'checks_total':checks,'failures':failures,'output':str(OUT)}))
raise SystemExit(0 if not failures else 1)
