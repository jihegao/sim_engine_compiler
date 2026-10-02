"""Independent read-only replay of positive and negative G03.var04 native evidence."""
import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
OUT = CASE / "review" / "independent-validation-2026-10-03.json"
RUNS = {
    "grandchild": CASE / "runs" / "g03-var04-grandchild-v100-ssh-20261003-01",
    "invalid-reference": CASE / "runs" / "g03-var04-invalid-reference-v100-ssh-20261003-01",
}
EXTERNAL = {
    "python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def native_json(path):
    data=path.read_text(encoding="utf-8-sig")
    result=[];quoted=False;escaped=False
    for i,char in enumerate(data):
        if quoted:
            result.append(char)
            if escaped: escaped=False
            elif char=="\\": escaped=True
            elif char=='"': quoted=False
        elif char=='"': result.append(char);quoted=True
        elif char==',':
            j=i+1
            while j<len(data) and data[j].isspace(): j+=1
            if j==len(data) or data[j] not in '}]': result.append(char)
        else: result.append(char)
    return json.loads(''.join(result))

def tables(doc,root): return {t['name']:t for t in doc[root]['tables']}
def rows(t): return [r for x in t['instances'] for r in x['rows']]
def field(t,name,index=0): return rows(t)[index][next(i for i,c in enumerate(t['columns']) if c['name']==name)]
checks=0;failures=[]
def check(condition,label):
    global checks
    checks+=1
    if not condition: failures.append(label)

contract=native_json(CASE/'contract.json')
parent_dir=CASES/contract['accepted_parent']['package']
parent_path=parent_dir/'native-input.json'
parent_closure=parent_dir/'runs'/contract['accepted_parent']['run_id']/'closure.json'
parent=tables(native_json(parent_path),'model')
diff=native_json(CASE/'exact-diff.json')
check(sha(parent_path)==contract['accepted_parent']['input_sha256'],'accepted parent input SHA')
check(sha(parent_closure)==contract['accepted_parent']['native_closure_sha256'],'accepted parent closure SHA')
check(sha(CASE/'exact-diff.json')==contract['exact_diff_sha256'],'frozen exact diff SHA')
for name in ('exe','manual','dictionary'):
    check(sha(EXTERNAL[name])==contract['source'][f'{name}_sha256'],f'installed {name} SHA')

sources={}
for arm in RUNS:
    path=CASE/f'{arm}-input.json'
    sources[arm]=tables(native_json(path),'model')
    check(sha(path)==contract['input_sha256'][arm],f'{arm} input SHA')
    change={name:{'before':parent.get(name),'after':sources[arm].get(name)} for name in parent.keys()|sources[arm].keys() if parent.get(name)!=sources[arm].get(name)}
    check(change==diff['arms'][arm]['changed'],f'{arm} exact parent table delta')
    check(set(change)=={'ProblemDescription','System','SystemDeployment','SystemRepair'},f'{arm} four changed tables')
    check(len(rows(sources[arm]['System']))==3 and len(rows(sources[arm]['SystemRepair']))==3,f'{arm} grandchild source rows')
    check(field(sources[arm]['System'],'BSID',1)=='TEACH-AIR-01',f'{arm} first BSID link')
    check(field(sources[arm]['System'],'BSID',2)==('TEACH-VAR-ADD' if arm=='grandchild' else 'TEACH-NO-SUCH'),f'{arm} second BSID reference')
    check(field(sources[arm]['SystemDeployment'],'SID')=='TEACH-VAR-GRAND' and field(sources[arm]['SystemDeployment'],'SID',1)=='TEACH-AIR-01',f'{arm} grandchild/base deployments')
check({name for name in sources['grandchild'] if sources['grandchild'][name]!=sources['invalid-reference'][name]}=={'System','ProblemDescription'},'arms differ only in System and description tables')
check(all(sources['grandchild'][name]==sources['invalid-reference'][name] for name in sources['grandchild'] if name not in ('System','ProblemDescription')),'pair unchanged business rows')
valid_system=rows(sources['grandchild']['System'])
invalid_system=rows(sources['invalid-reference']['System'])
bsid_index=next(i for i,c in enumerate(sources['grandchild']['System']['columns']) if c['name']=='BSID')
check(len(valid_system)==len(invalid_system)==3 and valid_system[:2]==invalid_system[:2] and
      all(valid_system[2][i]==invalid_system[2][i] for i in range(len(valid_system[2])) if i!=bsid_index),
      'pair System rows differ only grandchild BSID cell')

run_meta={}
for arm,run in RUNS.items():
    invocation=native_json(run/'invocation.json')
    closure=native_json(run/'closure.json')
    run_meta[arm]={'closure':closure,'invocation':invocation}
    check(sha(run/'invocation.json')==closure['invocation_sha256'],f'{arm} invocation SHA')
    check(invocation['run_id']==closure['run_id']==run.name,f'{arm} run ID')
    check(invocation['execution_mode']=='session0_ssh_cli' and invocation['session_id']==0 and 'sshd.exe' in invocation['ssh_ancestor_names'],f'{arm} SSH session0')
    check(invocation['gui']['pid']==13340 and invocation['gui']['session_id']==1 and invocation['queue_mutex']==r'Global\SimloxIssue18NativeQueue',f'{arm} GUI and mutex')
    check(invocation['prelife_log_option_before']==closure['prelife_log_option_after']=='NO',f'{arm} registry restored')
    check(invocation['source_hashes_before']==closure['source_hashes_before']==closure['source_hashes_after'],f'{arm} source stability')
    paths={'input':CASE/f'{arm}-input.json','parent':parent_path,'parent_closure':parent_closure,
           'contract':CASE/'contract.json','exact_diff':CASE/'exact-diff.json',
           'builder':CASE/'build.py','diff_builder':CASE/'describe_diff.py',
           'checker':CASE/'check_roundtrip.py','runner':CASE/'run_native_ssh.ps1',**EXTERNAL}
    for name,path in paths.items(): check(sha(path)==closure['source_hashes_before'][name],f'{arm} source seal {name}')
    expected_raw=13 if arm=='grandchild' else 9
    check(len(closure['raw'])==expected_raw,f'{arm} raw file count')
    for name,meta in closure['raw'].items():
        path=run/name
        check(path.exists() and path.stat().st_size==meta['bytes'] and sha(path)==meta['sha256'],f'{arm} raw seal {name}')
    check(sha(run/'input.json')==sha(CASE/f'{arm}-input.json'),f'{arm} run copied frozen source')
    steps=native_json(run/'steps.json')
    want=['import','export','calc','jsonreport','check_import_export'] if arm=='grandchild' else ['import','export','calc','check_import_export']
    check([s['name'] for s in steps]==want,f'{arm} guarded step names')
    for step in steps:
        check(step['exit_code']==0 and step['gui_preserved'] and step['status']==('diagnostic_converter_error' if arm=='invalid-reference' and step['name']=='calc' else 'completed'),f'{arm} step {step["name"]}')
    check([s['arguments'] for s in steps if 'arguments' in s]==[s['args'] for s in invocation['planned_commands'][:4 if arm=='grandchild' else 3]],f'{arm} CLI matches plan')
    exported=tables(native_json(run/'roundtrip-raw.json'),'model')
    populated=[name for name,t in sources[arm].items() if rows(t)]
    check(len(populated)==18,f'{arm} 18 row-containing tables')
    for name in populated:
        check(name in exported,f'{arm} exported table {name}')
        if name in exported:
            check(exported[name]['columns']==sources[arm][name]['columns'],f'{arm} exact columns {name}')
            check(exported[name]['instances']==sources[arm][name]['instances'],f'{arm} exact rows {name}')

positive=RUNS['grandchild']
negative=RUNS['invalid-reference']
pc=run_meta['grandchild']['closure'];nc=run_meta['invalid-reference']['closure']
check(pc['conversion']['errors']==0 and pc['conversion']['notes']==0 and pc['conversion']['warning_codes']==['108','2053'],'positive converter diagnostics')
check(pc['native_outcome']=='zero_error_reviewed_warnings' and pc['sxo_bytes']>4 and pc['report_present'],'positive usable SXO/report')
check(not re.search(r'\berror\s*#',(positive/'run.log').read_text(encoding='utf-8-sig'),re.I),'positive no numbered error')
check(nc['conversion']['errors']==1 and nc['conversion']['notes']==0 and nc['conversion']['error_codes']==['18'] and nc['conversion']['warning_codes']==['108','126','380'],'negative exact converter diagnostics')
negative_log=(negative/'run.log').read_text(encoding='utf-8-sig')
check('rec 3: (error #18) Unknown base system identifier (BSID):  TEACH-NO-SUCH' in negative_log,'negative BSID error text and row')
check(nc['native_outcome']=='converter_error_requires_review' and nc['sxo_bytes']==4 and not nc['report_present'],'negative unusable SXO')
check(not (negative/'model.log').exists() and not (negative/'report-raw.json').exists(),'negative has no simulated event or report')

log=(positive/'model.log').read_text(encoding='utf-8-sig')
def event(t,frag): return any(line.startswith(f'Time: {t} ') and frag in line for line in log.splitlines())
for mission,unit,system,start,end in (
    (0,'TEACH-UNIT','TEACH-VAR-GRAND,0',8,10),(1,'TEACH-BASE-UNIT','TEACH-AIR-01,1',8,10),
    (2,'TEACH-UNIT','TEACH-VAR-GRAND,0',20,22),(3,'TEACH-BASE-UNIT','TEACH-AIR-01,1',20,22),
    (4,'TEACH-UNIT','TEACH-VAR-GRAND,0',32,34),(5,'TEACH-BASE-UNIT','TEACH-AIR-01,1',32,34)):
    ident=f'<BASIC-MISSION,{unit},0,0,{mission}>'
    check(event(start,f'{ident} mission starting, duration: 2 : <{system}>'),f'mission {mission} correct system')
    check(event(end,f'{ident} '+('aborted mission completed' if mission==0 else 'mission completed')),f'mission {mission} completed/returned')
    if mission!=0: check(event(end,f'{ident} mission success'),f'mission {mission} success')
check(event(9.8829,'<TEACH-VAR-GRAND,0> critical random failure added') and event(9.8829,'<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted'),'grandchild failure and abort')
check('subitem failed: <TEACH-LRU-ADD,0,1> connection path: TEACH-VAR-GRAND - TEACH-VAR-GRAND - TEACH-LRU-ADD' in log,'inherited added LRU physical failure path')
check('<TEACH-AIR-01,1> critical random failure added' not in log and log.count('critical random failure added')==1,'base no failure and grandchild exactly one')
for t,frag in ((10,'Take replacement item <TEACH-LRU-ADD,0,0> from stock'),(10,'system SURP task 0 on <TEACH-VAR-GRAND,0> started'),
               (10.25,'Start repair of item <TEACH-LRU-ADD,0,1>'),(10.5,'system SURP task 0 on <TEACH-VAR-GRAND,0> completed'),
               (11.25,'item DIRP task 1 on <TEACH-LRU-ADD,0,1> completed'),(11.25,'Put back replacement item <TEACH-LRU-ADD,0,1> to stock')):
    check(event(t,frag),f'grandchild item event {t} {frag}')
check(event(34,'<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-VAR-GRAND,0>') and event(34,'<TEACH-BASE-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,1>'),'two terminal ready identities')

report=tables(native_json(positive/'report-raw.json'),'report')
parent_report=tables(native_json(parent_dir/'runs'/contract['accepted_parent']['run_id']/'report-raw.json'),'report')
check(set(report)=={'ProblemDescription','ResultSummary','SystemResults','StockTotalResults'},'positive report tables')
for name in ('ResultSummary','SystemResults','StockTotalResults'):
    check(report[name]==parent_report[name],f'{name} equals accepted separate-base/variant parent')
summary=report['ResultSummary']
for name,want in (('NREP',1),('RTILW',0),('RTIUP',36),('MTMF',1),('MSTF',1),('MSUF',5/6),('STMF',1)):
    check(abs(field(summary,name)-want)<.00001,f'summary {name}')
system,stock=report['SystemResults'],report['StockTotalResults']
sr,kr=rows(system),rows(stock)
check(len(sr)==len(kr)==72,'72 aligned report intervals')
for i,(srow,krow) in enumerate(zip(sr,kr)):
    s=i/2
    sv={c['name']:srow[j] for j,c in enumerate(system['columns'])}
    kv={c['name']:krow[j] for j,c in enumerate(stock['columns'])}
    check(sv['STINT']==kv['STINT']==s and sv['ETINT']==kv['ETINT']==s+.5,f'bin {i} time')
    mission=any(a<=s<b for a,b in ((8,10),(20,22),(32,34)))
    reserved=any(a<=s<b for a,b in ((7,8),(19,20),(31,32)))
    repair=s==10
    for name,want in (('NSYRY',0 if mission or reserved else (1 if repair else 2)),('NSYMA',2 if mission or reserved else 0),
                      ('NSYMO',2 if mission else 0),('NSYMR',2 if reserved else 0),('NSYRP',int(repair)),('NSYUA',int(repair)),
                      ('NSYA',1 if repair else 2),('FTMO',int(mission)),('STACC',2 if mission else 0),
                      ('NFAIL',int(s==9.5)),('NREPT',int(s==10.5)),('NSYDT',int(repair))):
        check(sv[name]==want,f'system {name} bin {i}')
    check((sv['SYDT'] is None) if not repair else sv['SYDT']==.5,f'system SYDT bin {i}')
    for name in ('NSYMC','NSYMP','NSYMT','NSYMS','NSYAL','NSYPM','NSYTP','NSYWR','NSYWI','NSYLA','NSYUH','NPMT','NDAM','NPMS','NROBT','NRCFG','STREQ','STF','STLOW','SYDTU','NSYSW','NPSTA','NPSUC'):
        check(sv[name]==0,f'system {name} zero bin {i}')
    check(kv['PNB']==1 and kv['NDF']==int(repair) and kv['NWT']==int(repair) and kv['NBO']==0,f'stock demand/BO bin {i}')
    for name in ('NDD','NDR','NDP','NLD'): check(kv[name]==0,f'stock {name} zero bin {i}')
    for name in ('ROS','ROST','WT','WTT'): check(kv[name]==(0 if repair else None),f'stock {name} no-wait bin {i}')
    check(kv['NBOU'] is None and kv['WTS'] is None,f'stock empty fields bin {i}')
check(field(system,'NSYRY',71)==2 and field(stock,'NBO',71)==0,'terminal ready2/no BO')

result={
    'schema':'simlox-g03-var04-independent-readonly/v1',
    'decision':'GO: bounded two-level BSID inherited-item path and undefined-BSID converter rejection',
    'passed':not failures,'checks_passed':checks-len(failures),'checks_total':checks,'failures':failures,
    'raw_seals':sum(len(run_meta[a]['closure']['raw']) for a in RUNS),
    'runs':{arm:{'input_sha256':sha(CASE/f'{arm}-input.json'),'closure_sha256':sha(run/'closure.json'),
                 'run_log_sha256':sha(run/'run.log'),'report_sha256':sha(run/'report-raw.json') if (run/'report-raw.json').exists() else None,
                 'raw_seals':len(run_meta[arm]['closure']['raw'])} for arm,run in RUNS.items()},
    'observed':{'grandchild':'TEACH-VAR-GRAND,0 inherited TEACH-LRU-ADD ID1 fails h9.8829; stock ID0 issue h10; SURP h10-10.5; ID1 repair h10.25-11.25; five of six missions succeed; terminal ready2',
                'invalid_reference':'System row 3 error #18 Unknown base system identifier TEACH-NO-SUCH; SXO 4 bytes and no behavioral report'},
    'limits':['One two-level BSID chain and one undefined reference, one seed/rep; no arbitrary-depth, cycles or frequency inference.',
              'Positive report is aggregate; per-unit and physical item attribution comes from the event log. The connection path names the deployed grandchild and added LRU but omits the intermediate variant, so second-level inheritance is source-bound.',
              'Negative run is converter rejection evidence only; no simulation behavior or general malformed-BSID taxonomy.',
              'No CBSID reconfiguration, GUI visual or cross-engine claim.'],
}
OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'passed':result['passed'],'checks_passed':result['checks_passed'],'checks_total':checks,'failures':failures,'output':str(OUT)}))
raise SystemExit(0 if not failures else 1)
