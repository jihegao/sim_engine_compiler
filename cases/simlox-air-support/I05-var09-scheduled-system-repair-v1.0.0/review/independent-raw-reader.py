from pathlib import Path
import json,hashlib,datetime,copy,re,math,os
R=Path('C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z/resume-20261009T221148Z');O=R/'var09-raw-review';C=Path.cwd()/'cases/simlox-air-support/I05-var09-scheduled-system-repair-v1.0.0';N=Path.cwd()/'tmp/i05-var09-native-v100-20261010-01';Q=C/'runs/i05-var09-system-repair-v100-ssh-20261010-01';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':str(p.resolve()),'bytes':p.stat().st_size,'sha256':sha(p)}
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
# Own previously reviewed independent derivation, not an author import. Stop before its evidence-writing section.
own=R/'var09-method-review/independent-method-diagnostic.py';code=own.read_text(encoding='utf-8-sig').split("out={'schema':")[0];ns={};exec(compile(code,str(own),'exec'),ns);equal=ns['equal'];read=ns['read'];expected_report={'report':{'tables':ns['future']}};expected_input=ns['expected'];parentlog=(ns['P']/'model.log').read_bytes();expected_lines=parentlog.splitlines(keepends=True)
for s in ns['sub']:
 i=s['physical_line_1based']-1;body=expected_lines[i].rstrip(b'\r\n');expected_lines[i]=s['child'].encode()+expected_lines[i][len(body):]
expected_log=b''.join(expected_lines)
inv=load(N/'invocation.json');cl=load(N/'closure.json');assert sha(N/'closure.json')=='caf4a016d0b5a811440143fc120cab96cb483cc4b7fd5f2eb0b8706a7b456bd9';assert sha(N/'invocation.json')=='47e1a8e27a25c36dce20fb4bf1524e56b9baa2c75c37fbc2345d9d0a19d575ed';assert cl['invocation_sha256']==sha(N/'invocation.json') and cl['error'] is None and cl['roundtrip_check_passed'] and cl['behavior_check_passed']
raw=[];origfiles=sorted(x for x in N.iterdir() if x.is_file());assert len(origfiles)==25
assert {p.name for p in Q.iterdir() if p.is_file()}=={p.name for p in origfiles}|{'run-summary.json'}
for p in origfiles:
 q=Q/p.name;assert p.read_bytes()==q.read_bytes();assert p.stat().st_file_attributes&1 and q.stat().st_file_attributes&1;raw.append({'original':pin(p),'recovered':pin(q),'both_readonly':True})
assert len(cl['raw'])==24 and 'closure.json' not in cl['raw']
for name,x in cl['raw'].items():p=N/name;assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
summary=load(Q/'run-summary.json');assert summary['closure_sha256']==sha(N/'closure.json') and summary['invocation_sha256']==sha(N/'invocation.json') and summary['raw_file_count']==24
m=load(C/'prelaunch-manifest-v100-run01.json');src=[]
for x in m['sources']:
 p=Path(x['path']);assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256'];assert cl['source_hashes_before'][x['key']]==cl['source_hashes_after'][x['key']]==inv['source_hashes_before'][x['key']]==x['sha256'];src.append({**x,'matched_current_invocation_closure_before_after':True})
assert len(src)==len(cl['source_hashes_before'])==71
assert inv['host_name']=='4700-3' and inv['session']['session_id']==0 and inv['session']['ps_major']==5 and inv['session']['session_name'] is None and 'sshd.exe' in inv['session']['ssh_ancestors'];assert re.fullmatch(r'127\.0\.0\.1 \d+ 127\.0\.0\.1 22',inv['session']['ssh_connection']);assert inv['queue_mutex']=='Global\\SimloxIssue18NativeQueue';assert inv['gui']['pid']==13340 and inv['gui']['session_id']==1 and inv['gui']['start_unix_ms']==1790590196826 and inv['gui']['responding'];assert re.search(r'\s1\s+(运行中|Active)$',inv['gui']['wts_active_line'])
for field,p in [('contract_sha256',C/'contract.json'),('method_manifest_sha256',C/'method-source-manifest.json'),('prelaunch_manifest_sha256',C/'prelaunch-manifest-v100-run01.json'),('independent_prelaunch_approval_sha256',C/'review/independent-prelaunch-go.json'),('preflight_sha256',C/'review/preflight-ssh0-20261009T224009440Z.json'),('input_sha256',C/'native-input.json')]:assert inv[field]==sha(p)
steps=cl['steps'];assert equal(steps,load(N/'steps.json')) and [s['name'] for s in steps]==['import','export','check_import_export','calc','jsonreport','check_behavior'];native=[s for s in steps if s['name'] in ['import','export','calc','jsonreport']];assert len(native)==4 and len(set(s['child_pid'] for s in native))==4
for i,s in enumerate(steps):
 assert s['status']=='completed' and s['exit_code']==0 and s['error'] is None and s['gui_preserved'];assert s['started_utc']<s['completed_utc'];assert i==0 or steps[i-1]['completed_utc']<=s['started_utc']
 for key in ['stdout','stderr']:p=Path(s[key+'_path']);assert p.parent==N and sha(p)==s[key+'_sha256'] and p.stat().st_size==s[key+'_bytes']
 assert s['stderr_bytes']==0
actualin=read(N/'input.json');assert (N/'input.json').read_bytes()==(C/'native-input.json').read_bytes() and equal(actualin,expected_input)
roundtrip=read(N/'roundtrip-raw.json');rt={t['name']:t for t in roundtrip['model']['tables']};assert len(rt)==len(roundtrip['model']['tables']);auth={t['name']:t for t in actualin['model']['tables'] if any(i['rows'] for i in t['instances'])};assert len(auth)==15;modelcells=0
for name,t in auth.items():
 u=rt[name];assert equal(t['columns'],u['columns']);a=[r for ins in t['instances'] for r in ins['rows']];b=[r for ins in u['instances'] for r in ins['rows']];assert len(a)==len(b)
 for ar,br in zip(a,b):
  assert len(ar)==len(br)==len(t['columns'])
  for x,y,col in zip(ar,br,t['columns']):
   modelcells+=1
   if col['datatype']=='double' and x is not None:assert type(y) in [int,float] and math.isfinite(y) and x==y
   else:assert equal(x,y)
assert equal(auth['ChangesSystemRepair']['columns'],ns['cols']);assert auth['ChangesSystemRepair']['instances'][0]['rows'][0][0:2]==['TEACH-AIR-01','BASE-01']
parent_export=read(ns['P']/'roundtrip-raw.json');prt={t['name']:t for t in parent_export['model']['tables']};generated=sorted(set(rt)-set(auth));assert len(generated)==17
for name in generated:assert equal(rt[name],prt[name]),'generated default table drift: '+name
for name in ['Tasks','TaskBreakDown']:assert not any(ins['rows'] for ins in next(t for t in actualin['model']['tables'] if t['name']==name)['instances'])
assert len(rt)==32 and set(rt)==set(prt)|{'ChangesSystemRepair'}
assert 'Import completed!' in (N/'import.log').read_text() and 'Export completed!' in (N/'export.log').read_text();assert (N/'model.sxi').stat().st_size>4 and (N/'model.sxo').stat().st_size>4
conv=(N/'run.log').read_bytes();assert conv.endswith(b'\r\n') and b'\n' not in conv.replace(b'\r\n',b'');ls=conv.decode('utf-8-sig').splitlines();assert len(ls)==17
parentls=(ns['P']/'run.log').read_text().splitlines();timing=[11,13,15,16]
for i,(a,b) in enumerate(zip(parentls,ls)):
 if i in timing:assert re.fullmatch(re.escape(a.split(':')[0])+r': [0-9]+(?:\.[0-9]+)? secs\.',b)
 elif i in [1,2,5]:assert b==a.replace(str(ns['P']),str(N)).replace(ns['P'].as_posix(),N.as_posix())
 else:assert a==b
assert cl['converter']['sha256']==sha(N/'run.log') and cl['converter']['warning_codes']==['108','126'] and cl['converter']['errors']==0
log=(N/'model.log').read_bytes();assert log==expected_log and len(log.splitlines())==128
text=log.decode().replace("\r\n","\n");starts=re.findall(r'^Time: ([\d.]+)  system DIRP task (\d+) on <TEACH-AIR-01,0> started$',text,re.M);ends=re.findall(r'^Time: ([\d.]+)  system DIRP task (\d+) on <TEACH-AIR-01,0> completed$',text,re.M);assert starts==[('10','0'),('34','1')] and ends==[('11.5','0'),('35.5','1')];periods=[{'start':float(s[0]),'end':float(e[0])} for s,e in zip(starts,ends)];assert re.findall(r'^Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added',text,re.M)==['9.8829','33.8602'];assert len(re.findall(r'^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:',text,re.M))==2;assert re.findall(r'^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:',text,re.M)==['22']
report=read(N/'report-raw.json');assert equal(report,expected_report);tables=report['report']['tables'];assert sum(len(r) for t in tables for ins in t['instances'] for r in ins['rows'])==4044
system=next(t for t in tables if t['name']=='SystemResults');cols=[c['name'] for c in system['columns']];rows=system['instances'][0]['rows'];values=[dict(zip(cols,r)) for r in rows];assert len(rows)==72
for v in values:
 starts_in=[p for p in periods if v['STINT']<=p['start']<v['ETINT']];assert type(v['NSYDT']) is int and v['NSYDT']==len(starts_in);assert equal(v['SYDT'],sum(p['end']-p['start'] for p in starts_in)/len(starts_in) if starts_in else None);assert type(v['SYDTU']) is int and v['SYDTU']==0
stock=next(t for t in tables if t['name']=='StockTotalResults');assert len(stock['instances'][0]['rows'])==72;sc=[c['name'] for c in stock['columns']];sv=[dict(zip(sc,r)) for r in stock['instances'][0]['rows']];sm=next(t for t in tables if t['name']=='ResultSummary');summarycells=dict(zip([c['name'] for c in sm['columns']],sm['instances'][0]['rows'][0]));metrics={'failures':sum(v['NFAIL'] for v in values),'repairs':sum(v['NREPT'] for v in values),'repair_aircraft_hours':sum(v['NSYRP']*(v['ETINT']-v['STINT']) for v in values),'downtime_periods':sum(v['NSYDT'] for v in values),'registered_downtime_hours':sum((v['SYDT'] or 0)*v['NSYDT'] for v in values),'terminal_ready':values[-1]['NSYRY'],'terminal_in_repair':values[-1]['NSYRP'],'MSUF':summarycells['MSUF'],'stock_totals':{n:sum(v[n] or 0 for v in sv) for n in ['NBO','NDD','NDR','NDP','NLD']}}
assert metrics=={'failures':2,'repairs':2,'repair_aircraft_hours':3.0,'downtime_periods':2,'registered_downtime_hours':3.0,'terminal_ready':1,'terminal_in_repair':0,'MSUF':0.3333333432674408,'stock_totals':{n:0 for n in ['NBO','NDD','NDR','NDP','NLD']}}
controls={};lines=log.splitlines(keepends=True)
for s in ns['sub']:
 i=s['physical_line_1based']-1;mut=list(lines);body=mut[i].rstrip(b'\r\n');mut[i]=s['parent'].encode()+mut[i][len(body):];controls['event_restore_'+str(i+1)]=b''.join(mut)!=expected_log
controls['log_extra_line']=log+b'EXTRA\r\n'!=expected_log;controls['log_ending_drift']=log.replace(b'\r\n',b'\n',1)!=expected_log;controls['parent_log_child_negative']=parentlog!=expected_log
for label,row,col,val in [('startSYDT',20,'SYDT',0.5),('continuationNSYDT',21,'NSYDT',1),('continuationSYDT',22,'SYDT',0.5),('secondNSYDT',68,'NSYDT',0),('completion',23,'NREPT',0),('occupancy',21,'NSYRP',0),('intfloat',0,'NSYRY',1.0)]:
 mut=copy.deepcopy(report);rr=next(t for t in mut['report']['tables'] if t['name']=='SystemResults')['instances'][0]['rows'];assert not equal(rr[row][cols.index(col)],val);rr[row][cols.index(col)]=val;controls[label]=not equal(mut,expected_report)
mut=copy.deepcopy(report);next(t for t in mut['report']['tables'] if t['name']=='SystemResults')['columns'][0]['key']=1;controls['metadata_boolint']=not equal(mut,expected_report)
for label,val in [('stockquantity',1),('stockboolalias',False)]:
 mut=copy.deepcopy(report);next(t for t in mut['report']['tables'] if t['name']=='StockTotalResults')['instances'][0]['rows'][0][sc.index('NBO')]=val;controls[label]=not equal(mut,expected_report)
assert all(controls.values())
post=load(O/'postrun-process-queue.json');assert post['queue_free'] and not post['queue_abandoned'];assert post['gui']==[{'pid':13340,'session':1,'start':1790590196826,'responding':True,'path':'C:\\Program Files\\Systecon\\SIMLOX\\Simlox.exe'}];assert len(post['processes'])==1 and post['processes'][0]['ProcessId']==13340
transport=list((C/'review').glob('transport-native-*/transport-receipt.json'));assert len(transport)==1;tr=load(transport[0]);assert tr['mode']=='native' and tr['exit_code']==0 and tr['error'] is None and tr['source_stability_error'] is None
for x in m['sources']:assert sha(Path(x['path']))==x['sha256']
out={'schema':'issue18-var09-independent-raw-acceptance/v100','decision':'GO_BOUNDED','reviewer':'/root/var09_source_review','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run_id':m['run_id'],'closure':pin(N/'closure.json'),'invocation':pin(N/'invocation.json'),'report':pin(N/'report-raw.json'),'event_log':pin(N/'model.log'),'original_recovered_raw25':raw,'closure_raw_map24_exact':True,'recovered_generated_summary_separate':pin(Q/'run-summary.json'),'source71_checks':src,'native_four_serial_steps':native,'SSH0_PS5_queue_provenance':inv['session'],'postrun_process_queue':pin(O/'postrun-process-queue.json'),'transport':pin(transport[0]),'authored_row_bearing_tables':15,'authored_cells_checked':modelcells,'generated_native_tables17_exact_parent_roundtrip':generated,'full_event_lines':128,'independently_derived_event_substitutions':20,'typed_report_cells':4044,'metadata_full_tree_exact':True,'system_bins':72,'stock_bins':72,'independent_ledger_periods_from_events':periods,'metrics':metrics,'negative_controls':controls,'negative_control_count':len(controls),'own_reader_derivation':pin(own),'author_reader_imported':False,'native_calls_by_reviewer':0,'parent_reruns':0,'publication_state':'not_published','scope':'OnlyonefixedD01scalarobject DIRPT0.5to1.5afterhour5, unchangedSURPT/fractions/distributions andexactobservednativecontext; no generalChangesSystemRepair/nativeRNG portability claim','excluded':['GUIfunctionality','fraction/distribution/SURPT/group/sametime/inprogress/TaskBreakDown/resourceprofiles','crossengine','performance','wholeI05var09/currentnonGUIIssuecompletion'],'later_gate':'Independentpublication/content/remote/merge reviewrequired; thisrawGOdoesnotpublish'}
E=O/'independent-raw-evidence-v100.json';E.write_text(json.dumps(out,indent=2),encoding='utf-8');A=C/'review/independent-raw-acceptance-v100.json';assert not A.exists();receipt={k:v for k,v in out.items() if k not in ['original_recovered_raw25','source71_checks','native_four_serial_steps']};receipt['detailed_evidence']=pin(E);receipt['original_raw_count']=25;receipt['closure_raw_count']=24;receipt['source_count']=71;A.write_bytes((json.dumps(receipt,indent=2)+'\n').encode());A.chmod(0o444);print(json.dumps({'approval':pin(A),'evidence':pin(E),'negativecontrols':len(controls),'modelcells':modelcells,'metrics':metrics},indent=2))
