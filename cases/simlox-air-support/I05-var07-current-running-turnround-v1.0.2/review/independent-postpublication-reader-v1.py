import json,re,hashlib,copy,datetime,subprocess
from pathlib import Path
W=Path('C:/Users/user/Documents/Codex/2026-10-09/i05-var08-pm-location')
C=W/'cases/simlox-air-support/I05-var07-current-running-turnround-v1.0.2'
J=Path('C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z/resume-20261010T114528Z')
O=W/'tmp/i05-var07-current-native-v102-20261010-01'
R=C/'runs/i05-var07-current-turnround-v102-ssh-20261010-01'
OUT=J/'var07-raw-review'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def parse(p):
 s=Path(p).read_text(encoding='utf-8-sig')
 # Native exporter trailing commas only, preserving string contents and rejecting duplicate keys/nonfinite.
 s=re.sub(r'("(?:[^"\\]|\\.)*")|,\s*(?=[}\]])',lambda m:m[1] if m[1] else '',s)
 def unique(items):
  d={}
  for k,v in items:
   assert k not in d,'duplicate key';d[k]=v
  return d
 return json.loads(s,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def same(a,b,path='$'):
 assert type(a)==type(b),('type',path,type(a),type(b))
 if isinstance(a,dict):
  assert list(a)==list(b),('keys/order',path)
  for k in a:same(a[k],b[k],path+'.'+k)
 elif isinstance(a,list):
  assert len(a)==len(b),('length',path)
  for i,(x,y) in enumerate(zip(a,b)):same(x,y,path+'['+str(i)+']')
 else:assert a==b,('value',path,a,b)
def patch_time(d):
 d=copy.deepcopy(d)
 ts=[x for x in d['model']['tables'] if x['name']=='ChangesMissionTurnround'];assert len(ts)==1
 t=ts[0];ix=[x['name'] for x in t['columns']].index('TIMEC');rs=t['instances'][0]['rows'];assert len(rs)==1 and rs[0][ix]==25.0;rs[0][ix]=23.7
 return d
checks={}
def check(name,f):f();checks[name]=True
contract=parse(C/'contract.json');parent=Path(parse(C/'parent-evidence-pins.json')['parent_run'])
assert sha(parent/'input.json')=='1dc116829e92845735440f6e7e49b0f1b768247b59af651538ae23db450a6619'
check('authored_input_only_TIMEC_delta',lambda:same(parse(C/'native-input.json'),patch_time(parse(parent/'input.json'))))
check('physical_input_frozen_bytes',lambda: same((O/'input.json').read_bytes(),(C/'native-input.json').read_bytes()))
raw=(O/'model.log').read_bytes();assert raw==(parent/'model.log').read_bytes()==(C/'expected-model-derived.log').read_bytes();assert len(raw.splitlines())==115 and raw.endswith(b'\r\n') and b'\n' not in raw.replace(b'\r\n',b'');assert b'Time: 23.7 ' not in raw
checks['full115_ordered_CRLF_parent_and_prospective_log']=True
report=parse(O/'report-raw.json');same(report,parse(parent/'report-raw.json'));same(report,parse(C/'expected-report-derived.json'));checks['full_report_types_metadata_parent_and_frozen_identity']=True
model=parse(O/'roundtrip-raw.json');same(model,patch_time(parse(parent/'roundtrip-raw.json')));same(model,parse(C/'expected-roundtrip-derived.json'));assert len(model['model']['tables'])==33;checks['full33_native_default_tables_only_TIMEC_delta']=True
# independent registered-start event ledger, never infer durations by counting completion markers.
active={};periods=[]
for line in raw.decode('ascii').splitlines():
 m=re.fullmatch(r'Time: ([0-9.]+)  system (preparation|turnround) task (\d+) on <TEACH-AIR-01,0> (started|completed)',line)
 if not m:continue
 clock=float(m[1]);key=(m[2],int(m[3]))
 if m[4]=='started':assert key not in active and key not in [x[0] for x in periods];active[key]=clock
 else:assert key in active;start=active.pop(key);assert clock>start;periods.append((key,start,clock))
assert not active
assert periods==[(('preparation',0),20.5,21.),(('turnround',1),23.5,24.5),(('preparation',2),24.5,25.),(('turnround',3),27.,28.5)]
for task,sub,start,dur in [(1,2,23.5,1),(3,5,27,1.5)]:assert raw.decode().splitlines().count(f'Time: {start:g}  subtask {sub} seqno 0 within system turnround task {task} on <TEACH-AIR-01,0> starts performing, planned to last for {dur:g} hours')==1
missionstarts=re.findall(r'Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d)> mission starting, duration: 2 ',raw.decode());missionends=re.findall(r'Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d)> mission completed: ',raw.decode());assert [(float(e[0])-float(s[0]),s[1],e[1]) for s,e in zip(missionstarts,missionends)]==[(2.,'0','0'),(2.,'1','1')]
tables={t['name']:t for t in report['report']['tables']};t=tables['SystemResults'];ix={v['name']:i for i,v in enumerate(t['columns'])};rows=t['instances'][0]['rows'];assert len(rows)==72 and len(tables['StockTotalResults']['instances'][0]['rows'])==72
for field,value in [('NSYMT',2.5),('NSYMP',1.),('NSYMO',4.)]:assert sum(r[ix[field]]*(r[ix['ETINT']]-r[ix['STINT']]) for r in rows)==value
assert all(r[ix['NSYDT']]==0 and r[ix['SYDT']] is None for r in rows);assert rows[-1][ix['ETINT']]==36 and rows[-1][ix['NSYRY']]==1
cells=sum(len(r) for t in tables.values() for ins in t['instances'] for r in ins['rows']);assert cells==4044;checks['start_registered_ledger_and_full72plus72_bins_endstate']=True
cl=parse(O/'closure.json');inv=parse(O/'invocation.json');manifest=parse(C/'prelaunch-manifest-v102-run01.json');assert sha(O/'invocation.json')==cl['invocation_sha256'];assert cl['error'] is None
assert len(manifest['sources'])==140;assert cl['source_hashes_before']==cl['source_hashes_after']==inv['source_hashes_before']
archived=J/'publication-index-512-before-var07.json'
index_roles={'scope:publication-index-v1.json','selected:'+str(W/'cases/simlox-air-support/publication-index-v1.json')}
# Role spellings in frozen manifest use Windows canonical separators.
index_roles={'scope:publication-index-v1.json','selected:'+str(W/'cases/simlox-air-support/publication-index-v1.json').replace('/','\\')}
seen=[]
for e in manifest['sources']:
 p=archived if e['key'] in index_roles else Path(e['path'])
 assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256']==cl['source_hashes_before'][e['key']],e['key']
 if e['key'] in index_roles:seen.append(e['key'])
assert set(seen)==index_roles and len(seen)==2
oldindex=parse(archived);liveindex=parse(W/'cases/simlox-air-support/publication-index-v1.json');entry=parse(C/'publication-entry.json')
for k in oldindex:
 if k!='entries':same(liveindex[k],oldindex[k])
assert list(oldindex)==list(liveindex)
same(liveindex['entries'][:-1],oldindex['entries']);same(liveindex['entries'][-1],entry)
assert len(oldindex['entries'])==512 and len(liveindex['entries'])==513 and len({e['case_id'] for e in liveindex['entries']})==107
checks['138_literal_plus2_exact_archival_roles_and_single513_append']=True
checks['all140_source_before_after_exact_literal_or_archived_pins']=True
assert inv['host_name']=='4700-3' and inv['session']['ps_major']==5 and inv['session']['session_id']==0 and inv['session']['ssh_connection'] and 'sshd.exe' in inv['session']['ssh_ancestors'];assert inv['queue_mutex']=='Global\\SimloxIssue18NativeQueue';assert inv['gui']['pid']==13340 and inv['gui']['session_id']==1 and inv['gui']['start_unix_ms']==1790590196826 and inv['gui']['responding'] and inv['gui']['wts_active_line']
assert inv['prelaunch_manifest_sha256']==sha(C/'prelaunch-manifest-v102-run01.json')
for field,f in [('contract_sha256','contract.json'),('method_manifest_sha256','method-source-manifest.json'),('independent_prelaunch_approval_sha256','review/independent-prelaunch-go.json')]:assert inv[field]==sha(C/f)
go=parse(C/'review/independent-prelaunch-go.json');pf=C/go['preflight_relative_path'];assert inv['preflight_sha256']==sha(pf)==go['preflight_sha256'];assert go['decision']=='GO_PRELAUNCH';assert parse(pf)['native_process_started'] is False
assert cl['steps']==parse(O/'steps.json');native=[s for s in cl['steps'] if s['name'] in ['import','export','calc','jsonreport']];assert [x['name'] for x in native]==['import','export','calc','jsonreport'];assert len(cl['steps'])==6
for i,s in enumerate(cl['steps']):
 assert s['exit_code']==0 and s['status']=='completed' and s['error'] is None and s['completed_utc']>s['started_utc']
 if i:assert s['started_utc']>=cl['steps'][i-1]['completed_utc']
 for stream in ['stdout','stderr']:assert sha(s[stream+'_path'])==s[stream+'_sha256'] and Path(s[stream+'_path']).stat().st_size==s[stream+'_bytes']
 assert s['gui_preserved'] is True
 if s['name'] in ['import','export','calc','jsonreport']:assert s['arguments']==next(p for p in inv['planned_commands'] if p['name']==s['name'])['arguments']
runner=(C/'run_native_ssh.ps1').read_text(encoding='utf-8-sig');assert 'Invoke-Captured' in runner and '-Wait' in runner and 'Assert-Guard $ancestry $prelaunch' in runner
checks['four_serial_natural_native_two_pure_and_exact_SSH_receipt_chain']=True
conv=(O/'run.log').read_bytes();lines=conv.decode('utf-8-sig').splitlines();assert len(lines)==17 and 'Errors: 0, Warnings: 2, Notes: 0' in lines[10];assert re.findall(r'warning #(\d+)',conv.decode())==['108','126'];assert conv.endswith(b'\r\n');assert cl['converter']['physical_lines']==17
checks['converter17_CRLF_zero_errors_warning108126']=True
phase=parse(J/'phase-var07-v102-native-author-pass.json');assert len(phase['readonly_original_recovered_pairs'])==25
for p in phase['readonly_original_recovered_pairs']:
 for k in ['original','recovered']:
  e=p[k];f=Path(e['path']);assert sha(f)==e['sha256'] and f.stat().st_size==e['bytes'];assert f.stat().st_file_attributes&1
 assert p['original']['sha256']==p['recovered']['sha256']
checks['25_literal_original_recovered_readonly_pairs']=True
for f in ['preserved-v100-static-no-go.json','preserved-v101-before-ssh-failure.json','preserved-v101-transport-no-go.json']:assert (C/f).is_file()
refs=subprocess.run(['git','ls-remote','origin','refs/heads/main','refs/heads/simlox/main'],cwd=W,capture_output=True,text=True,check=True).stdout;assert 'a1a44c72f64d754b711abe4095f1111f8a5ba896\trefs/heads/main' in refs
out={'schema':'issue18-independent-original-raw-acceptance/v1','decision':'GO_BOUNDED_POSTPUBLICATION_READONLY_REPLAY','reviewer':'/root/var07_current_raw_review','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run_id':inv['run_id'],'checks':checks,'original_closure_sha256':sha(O/'closure.json'),'original_invocation_sha256':sha(O/'invocation.json'),'replay_script_sha256':sha(__file__),'safety_sha256':sha(OUT/'safety.json'),'start_registered_periods':periods,'physical_log_lines':115,'typed_report_cells':4044,'native_default_tables':33,'source_roles':140,'readonly_pairs':25,'remote_refs':refs,'native_calls_by_reviewer':0,'whole_variant_pass':False,'DURND_NOPer_horizon_same_time_crossengine_performance_CI_GUI_wholeGoal':'NOT_PROVEN_OR_EXCLUDED','effective_nonGUI_denominator':None,'all_commands_terminal':True}
print(json.dumps(out,indent=2))
