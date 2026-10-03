"""Independent read-only replay of G08.var06 nested passive leaf switching."""
import hashlib,json,math,re
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
CASES=CASE.parent
OUT=CASE/'review'/'independent-validation-2026-10-03.json'
RUNS={a:CASE/'runs'/f'g08-var06-{a}-v100-ssh-20261003-01' for a in ('instant','delay05')}
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
def tables(d,root):return {t['name']:t for t in d[root]['tables']}
def rows(t):return [r for i in t['instances'] for r in i['rows']]
def records(t):
 cols=[c['name'] for c in t['columns']]
 return [dict(zip(cols,r)) for r in rows(t)]
def near(a,b,tol=.0007):return isinstance(a,(int,float)) and math.isclose(a,b,abs_tol=tol)
def occ(a,b,start):return 2*max(0,min(b,start+.5)-max(a,start))
checks=0;failures=[]
def check(ok,label):
 global checks
 checks+=1
 if not ok:failures.append(label)

contract=native_json(CASE/'contract.json')
parent_file=CASES/contract['accepted_parent']['package']/'high-input.json'
parent_run=parent_file.parent/'runs'/contract['accepted_parent']['run_id']
donor_file=CASES/contract['schema_donor']['package']/'parallel-input.json'
parent=tables(native_json(parent_file),'model')
donor=tables(native_json(donor_file),'model')
diff=native_json(CASE/'exact-diff.json')
check(sha(parent_file)==contract['accepted_parent']['input_sha256'],'accepted NBREQ3 parent SHA')
check(sha(parent_run/'closure.json')==contract['accepted_parent']['native_closure_sha256'],
      'accepted NBREQ3 parent closure SHA')
check(sha(donor_file)==contract['schema_donor']['input_sha256'],'parallel schema donor SHA')
check(sha(CASE/'exact-diff.json')==contract['exact_diff_sha256'],'frozen exact diff SHA')
for key in ('exe','manual','dictionary'):
 check(sha(EXTERNAL[key])==contract['source'][f'{key}_sha256'],f'installed {key} SHA')
dictionary=EXTERNAL['dictionary'].read_text(encoding='utf-8-sig')
check('RBDParallel;5;TSWOV;' in dictionary and 'RBDParallel;6;ONLM;' in dictionary and
      'RBDTreeStructure;5;SBOPM;' in dictionary,'installed switch/tree-edge schema')

sources={};logs={};reports={};closures={}
delta_names={'ProblemDescription','MaterielPosition','MaterielStructure',
             'MaterielOperationalModes','RBDParallel','RBDParallelStructure','RBDTreeStructure'}
for arm,run in RUNS.items():
 source_file=CASE/f'{arm}-input.json'
 source=tables(native_json(source_file),'model');sources[arm]=source
 check(sha(source_file)==contract['input_sha256'][arm],f'{arm} source SHA')
 changed={name:{'before':parent.get(name),'after':source.get(name)}
          for name in parent.keys()|source.keys() if parent.get(name)!=source.get(name)}
 check(changed==diff['arms'][arm]['changed'] and set(changed)==delta_names,
       f'{arm} exact seven-table parent delta')
 for name in source:
  if name not in delta_names:check(source[name]==parent[name],f'{arm} unchanged {name}')
 for name in ('RBDParallel','RBDParallelStructure'):
  check(source[name]['columns']==donor[name]['columns'],f'{arm} donor {name} columns')
 check(source['FailureMode']==parent['FailureMode'] and source['CMLocation']==parent['CMLocation']
       and source['Control']==parent['Control'],f'{arm} fixed failure/CM/seed')
 check({r['MPID'] for r in records(source['MaterielPosition'])}==
       {'POS-A','POS-B','POS-C','POS-D','POS-E'},f'{arm} five physical positions')
 check({(r['MID'],r['MMID']) for r in records(source['MaterielStructure'])}>=
       {('POS-E','TEACH-AIR-01'),('TEACH-LRU-01','POS-E')},
       f'{arm} E healthy installed LRU')
 check(any(r['MID']=='POS-E' and r['OPMID']=='G04-OPS' for r in
           records(source['MaterielOperationalModes'])),f'{arm} E mode')
 check({r['MID'] for r in records(source['FailureMode'])}=={'POS-A','POS-B'},
       f'{arm} only A/B failure modes')
 tree=records(source['RBDTree'])[0]
 check(tree['NBREQ']==3 and tree['RBID']=='G08-TREE',f'{arm} parent NBREQ3 tree fixed')
 edges=records(source['RBDTreeStructure'])
 check({(e['MRBID'],e['SRBID']) for e in edges}==
       {('POS-A','G08-BE-PASSIVE'),('POS-A','POS-C'),('POS-A','POS-D')},
       f'{arm} nested parallel replaces B leaf only')
 check(all(e['RBID']=='G08-TREE' and e['QTYPM']==1 and e['MBOPM']=='G04-OPS' and
           e['SBOPM']==(None if e['SRBID']=='G08-BE-PASSIVE' else 'G04-OPS') for e in edges),
       f'{arm} nested edge omits SBOPM')
 parallel=records(source['RBDParallel'])
 check(len(parallel)==1 and parallel[0]['RBID']=='G08-BE-PASSIVE' and
       parallel[0]['NBREQ']==parallel[0]['NBOP']==1 and parallel[0]['ONLM']=='N' and
       near(parallel[0]['TSWOV'],0 if arm=='instant' else .5),
       f'{arm} passive parallel settings/TSWOV')
 check({(r['SRBID'],r['PRIO'],r['OPMID']) for r in
        records(source['RBDParallelStructure'])}==
       {('POS-B',1,'G04-OPS'),('POS-E',2,'G04-OPS')},
       f'{arm} B priority1 E priority2')

 inv=native_json(run/'invocation.json');cl=native_json(run/'closure.json');closures[arm]=cl
 check(sha(run/'invocation.json')==cl['invocation_sha256'],f'{arm} invocation seal')
 check(inv['run_id']==cl['run_id']==run.name,f'{arm} run identity')
 check(inv['execution_mode']=='session0_ssh_cli' and inv['session_id']==0 and
       'sshd.exe' in inv['ssh_ancestor_names'],f'{arm} SSH session0')
 check(inv['gui']['pid']==13340 and inv['gui']['session_id']==1 and
       inv['queue_mutex']==r'Global\SimloxIssue18NativeQueue',f'{arm} GUI/mutex')
 check(inv['prelife_log_option_before']==cl['prelife_log_option_after']=='NO',
       f'{arm} registry restoration')
 check(inv['source_hashes_before']==cl['source_hashes_before']==cl['source_hashes_after'],
       f'{arm} frozen source stability')
 paths={'input':source_file,'parent':parent_file,'parent_closure':parent_run/'closure.json',
        'schema_donor':donor_file,'contract':CASE/'contract.json','exact_diff':CASE/'exact-diff.json',
        'builder':CASE/'build.py','diff_builder':CASE/'describe_diff.py',
        'checker':CASE/'check_roundtrip.py','runner':CASE/'run_native_ssh.ps1',**EXTERNAL}
 for name,path in paths.items():check(sha(path)==cl['source_hashes_before'][name],
                                    f'{arm} source seal {name}')
 check(len(cl['raw'])==13,f'{arm} 13 raw seals')
 for name,meta in cl['raw'].items():
  path=run/name
  check(path.exists() and path.stat().st_size==meta['bytes'] and sha(path)==meta['sha256'],
        f'{arm} raw seal {name}')
 check(sha(run/'input.json')==sha(source_file),f'{arm} copied native input')
 steps=native_json(run/'steps.json')
 check([s['name'] for s in steps]==['import','export','calc','jsonreport','check_import_export'],
       f'{arm} five native steps')
 for s in steps:check(s['exit_code']==0 and s['status']=='completed' and s['gui_preserved'],
                    f'{arm} guarded {s["name"]}')
 check([s['arguments'] for s in steps[:4]]==[s['args'] for s in inv['planned_commands']],
       f'{arm} actual/planned CLI')
 check(cl['conversion']['errors']==0 and cl['conversion']['notes']==0 and
       cl['conversion']['warning_codes']==['108'],f'{arm} zero errors/reviewed warning')
 check(cl['sxo_bytes']>4 and cl['report_present'] and
       cl['native_outcome']=='zero_error_reviewed_warnings',f'{arm} usable output')
 check(not re.search(r'\berror\s*#',(run/'run.log').read_text(encoding='utf-8-sig'),re.I),
       f'{arm} no converter error text')
 exported=tables(native_json(run/'roundtrip-raw.json'),'model')
 populated=[name for name,t in source.items() if rows(t)]
 check(len(populated)==25,f'{arm} 25 populated tables')
 for name in populated:
  check(name in exported,f'{arm} exported {name}')
  if name in exported:
   check(source[name]['columns']==exported[name]['columns'],f'{arm} exact {name} columns')
   check(source[name]['instances']==exported[name]['instances'],f'{arm} exact {name} rows')
 logs[arm]=(run/'model.log').read_text(encoding='utf-8-sig')
 reports[arm]=tables(native_json(run/'report-raw.json'),'report')

check({name for name in sources['instant'] if sources['instant'][name]!=sources['delay05'][name]}==
      {'ProblemDescription','RBDParallel'},'paired only TSWOV/description table contrast')
for name in sources['instant']:
 if name not in ('ProblemDescription','RBDParallel'):
  check(sources['instant'][name]==sources['delay05'][name],f'paired common {name}')
zero=records(sources['instant']['RBDParallel'])[0]
half=records(sources['delay05']['RBDParallel'])[0]
check({k:zero[k] for k in zero if k!='TSWOV'}=={k:half[k] for k in half if k!='TSWOV'}
      and zero['TSWOV']==0 and half['TSWOV']==.5,'pair isolated TSWOV 0/.5')

def event(arm,hour,fragment):
 return any(line.startswith(f'Time: {hour} ') and fragment in line for line in logs[arm].splitlines())
for arm in RUNS:
 sw_end=8.62763 if arm=='instant' else 9.12763
 a_fail=11.0942 if arm=='instant' else 11.5942
 ret=14.1884 if arm=='instant' else 15.1884
 cm_end=14.6884 if arm=='instant' else 15.6884
 log=logs[arm]
 check(event(arm,7,'mission allocates system: <TEACH-AIR-01,0>') and
       event(arm,8,'mission starting, duration: 26'),f'{arm} mission start')
 check(event(arm,8.62763,'[POS-B -> POS-E]>. switch over started. Will be finished at '+str(sw_end))
       and event(arm,sw_end,'[POS-B -> POS-E]>. Switch over stopped.'),
       f'{arm} explicit B-to-E switch timing')
 check(event(arm,8.62763,'noncritical CM failure mode added') and
       'Failure Mode: FM-POS-B on materiel: <POS-B,0>' in log,
       f'{arm} B failure noncritical')
 check(event(arm,a_fail,'critical CM failure mode added') and
       'Failure Mode: FM-POS-A on materiel: <POS-A,0>' in log and
       log.count('CM failure mode added')==2,f'{arm} A second critical')
 check(event(arm,a_fail,'mission aborted') and event(arm,ret,'aborted mission completed') and
       'mission success' not in log,f'{arm} abort/return')
 check('Failure Mode: FM-POS-E' not in log and 'Item demand arrives' not in log,
       f'{arm} E healthy and no stock demand')
 for task,fm in ((0,'FM-POS-B'),(1,'FM-POS-A')):
  label=f'system CM task {task} on <TEACH-AIR-01,0>'
  check(event(arm,ret,label+' started') and event(arm,ret,label+' FMID: '+fm) and
        event(arm,cm_end,label+' completed'),f'{arm} CM {task} identity/time')
 check(event(arm,cm_end,'systems ready: 1'),f'{arm} terminal ready event')

for arm,rep in reports.items():
 check(set(rep)=={'ProblemDescription','ResultSummary','SystemResults','StockTotalResults'},
       f'{arm} report table set')
 summary=records(rep['ResultSummary'])[0]
 factor=.23801425099372864 if arm=='instant' else .27647578716278076
 stmf=.23801425099372864 if arm=='instant' else .2572450339794159
 for name,want in (('NREP',1),('RTILW',0),('RTIUP',36),('MTMF',factor),
                   ('STMF',stmf),('MSTF',1),('MSUF',0)):
  check(near(summary[name],want),f'{arm} summary {name}')
 for name in ('RSMTMF','RSMSTF','RSMSUF','RSSTMF'):
  check(summary[name]==0,f'{arm} one-rep precision {name}')
 system=records(rep['SystemResults']);stock=records(rep['StockTotalResults'])
 check(len(system)==len(stock)==72,f'{arm} 72 aligned bins')
 sw_start=8.62763;sw_end=8.62763 if arm=='instant' else 9.12763
 ret=14.1884 if arm=='instant' else 15.1884
 repair_end=14.6884 if arm=='instant' else 15.6884
 a_fail=11.0942 if arm=='instant' else 11.5942
 for i,(s,k) in enumerate(zip(system,stock)):
  start=i*.5;end=start+.5
  check(s['STINT']==k['STINT']==start and s['ETINT']==k['ETINT']==end,
        f'{arm} aligned interval {i}')
  reserved=occ(7,8,start);mission=occ(8,ret,start)
  switch=occ(sw_start,sw_end,start);operating=mission-switch
  repair=occ(ret,repair_end,start)
  expected={'NSYRY':1-reserved-mission-repair,'NSYMA':reserved+mission,
            'NSYMO':operating,'NSYMR':reserved,'NSYRP':repair,'NSYUA':repair,
            'NSYA':1-repair,'FTMO':operating,'STACC':operating,'NSYSW':switch,
            'NFAIL':int(start<=8.62763<end)+int(start<=a_fail<end)}
  for name,want in expected.items():check(near(s[name],want),f'{arm} system {name} bin {i}')
  completion=29 if arm=='instant' else 31
  downtime=28 if arm=='instant' else 30
  check(s['NREPT']==(2 if i==completion else 0),f'{arm} repair marker bin {i}')
  check(s['NSYDT']==(1 if i==downtime else 0),f'{arm} downtime marker bin {i}')
  check((near(s['SYDT'],.5) if i==downtime else s['SYDT'] is None),
        f'{arm} downtime duration bin {i}')
  for name in ('NSYMC','NSYMP','NSYMT','NSYMS','NSYAL','NSYPM','NSYTP',
               'NSYWR','NSYWI','NSYLA','NSYUH','NPMT','NDAM','NPMS',
               'NROBT','NRCFG','STREQ','STF','STLOW','SYDTU','NPSTA','NPSUC'):
   check(s[name]==0,f'{arm} system {name} absent bin {i}')
  check(k['PNB']==1 and all(v is None or v==0 for name,v in k.items()
                            if name not in ('STINT','ETINT','PNB')),
        f'{arm} stock unchanged bin {i}')
 check(near(system[-1]['NSYRY'],1),f'{arm} terminal ready report')
 check(near(sum(s['NSYSW'] for s in system)*.5,0 if arm=='instant' else .5),
       f'{arm} integrated switching time')
 check(near(sum(s['NSYRP'] for s in system)*.5,.5),f'{arm} integrated CM occupancy')
 check(near(sum(s['NSYMO'] for s in system)*.5,(ret-8)-(sw_end-sw_start)),
       f'{arm} integrated operating hours excluding switch')

result={'schema':'simlox-g08-var06-independent-readonly/v1',
 'decision':'GO: bounded nested passive B-to-E switch with TSWOV 0/.5' if not failures else
            'NO-GO: independent replay failed',
 'passed':not failures,'checks_passed':checks-len(failures),'checks_total':checks,
 'failures':failures,'raw_seals':sum(len(c['raw']) for c in closures.values()),
 'runs':{a:{'source_sha256':sha(CASE/f'{a}-input.json'),
            'closure_sha256':sha(run/'closure.json'),
            'model_log_sha256':sha(run/'model.log'),
            'report_sha256':sha(run/'report-raw.json')} for a,run in RUNS.items()},
 'observed':{'instant':'B-to-E switch starts/stops h8.62763; B NC; A critical h11.0942; return h14.1884',
             'delay05':'B-to-E switch h8.62763-9.12763; NSYSW .5h; A critical h11.5942; return h15.1884',
             'terminal':'two parallel half-hour system CM tasks, ready1, no stock movement in both'},
 'limits':['The B-to-E transition is explicitly logged, but internal nested tree path state is inferred from sealed source and mission criticality.',
           'One passive B/E leaf, one A-root NBREQ3 tree, TSWOV0/.5, one seed and replication; the shifted A/return times do not establish a general timing law.',
           'E never fails; no other nested types, priorities, online maintenance, GUI drawing, population or cross-engine claim.']}
OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'passed':result['passed'],'checks_passed':result['checks_passed'],
                  'checks_total':checks,'failures':failures,'output':str(OUT)}))
raise SystemExit(0 if not failures else 1)
