import pathlib,json,re,copy,hashlib,datetime,os
W=pathlib.Path('C:/Users/user/Documents/Codex/2026-10-09/i05-var08-pm-location');J=pathlib.Path('C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z/resume-20261010T011849Z');C=W/'cases/simlox-air-support/I05-var14-current-later-turnround-v1.0.0';R=W/'tmp/i05-var14-native-v100-20261010-01';S=C/'runs/i05-var14-turnround-v100-ssh-20261010-01';O=J/'var14-raw-review';M=J/'var14-turnround-method-review'
def pin(p):p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def parse(p):
 text=pathlib.Path(p).read_bytes().decode('utf-8-sig');o=[];q=False;esc=False
 for i,ch in enumerate(text):
  if q:
   o.append(ch)
   if esc:esc=False
   elif ch=='\\':esc=True
   elif ch=='"':q=False
  elif ch=='"':q=True;o.append(ch)
  elif ch==',' and text[i+1:].lstrip().startswith((']', '}')):pass
  else:o.append(ch)
 return json.loads(''.join(o))
def strict(a,b):
 if type(a)!=type(b):raise ValueError('type')
 if isinstance(a,dict):
  if a.keys()!=b.keys():raise ValueError('keys')
  for k in a:strict(a[k],b[k])
 elif isinstance(a,list):
  if len(a)!=len(b):raise ValueError('len')
  for x,y in zip(a,b):strict(x,y)
 elif a!=b:raise ValueError('value')
closure=parse(R/'closure.json');assert pin(R/'closure.json')['sha256']=='44966fc918ca16082b73705c8ae85ae7dd93e5173930a38f71c2d91870b0cfe5';assert closure['error'] is None;assert closure['run_id']=='i05-var14-turnround-v100-ssh-20261010-01'
pairs=[]
for name,old in dict(closure['raw'],**{'closure.json':{k:pin(R/'closure.json')[k] for k in ['bytes','sha256']}}).items():
 a=pin(R/name);b=pin(S/name);assert a['sha256']==b['sha256']==old['sha256'] and a['bytes']==b['bytes']==old['bytes'];assert (R/name).stat().st_file_attributes&1 and (S/name).stat().st_file_attributes&1;pairs.append({'name':name,'original':a,'recovered':b,'both_readonly':True})
assert len(pairs)==25
manifest=parse(C/'prelaunch-manifest-v100-run01.json');src=[];before=closure['source_hashes_before'];after=closure['source_hashes_after'];assert before==after and len(before)==126
for old in manifest['sources']:
 new=pin(old['path']);assert new['bytes']==old['bytes'] and new['sha256']==old['sha256']==before[old['key']];src.append(dict(new,key=old['key']))
assert len(src)==126
invoke=parse(R/'invocation.json');assert pin(R/'invocation.json')['sha256']==closure['invocation_sha256'];assert invoke['host_name']=='4700-3' and invoke['session']['ps_major']==5 and invoke['session']['session_id']==0;assert invoke['session']['ssh_connection'] and invoke['session']['ssh_ancestors'].count('sshd.exe')>=1;assert invoke['queue_mutex']=='Global\\SimloxIssue18NativeQueue';assert invoke['gui']['pid']==13340 and invoke['gui']['session_id']==1 and invoke['gui']['start_unix_ms']==1790590196826 and invoke['gui']['responding']
assert invoke['prelaunch_manifest_sha256']==pin(C/'prelaunch-manifest-v100-run01.json')['sha256'];gates=[]
for name,sha in [('independent-method-go-v100.json','8ea36fb1db31f95c2ce619b45658e579677fe679c1441d638d64381bad2bfa3f'),('independent-prelaunch-go.json',invoke['independent_prelaunch_approval_sha256'])]:
 p=C/'review'/name;assert pin(p)['sha256']==sha;gates.append(pin(p));parse(p)
static=C/'review/independent-prelaunch-static-go.json';gates.append(pin(static));parse(static)
preflight=C/'review/preflight-ssh0-20261010T023853254Z.json';assert pin(preflight)['sha256']==invoke['preflight_sha256'];gates.append(pin(preflight));parse(preflight)
steps=closure['steps'];native=[s for s in steps if s['name'] in ['import','export','calc','jsonreport']];assert len(native)==4
for i,s in enumerate(steps):
 assert s['exit_code']==0 and s['status']=='completed' and s['error'] is None and s['gui_preserved'];assert s['started_utc']<s['completed_utc']
 if i:assert steps[i-1]['completed_utc']<=s['started_utc']
assert len(set(x['child_pid'] for x in native))==4
conv=(R/'run.log').read_bytes();assert len(conv.splitlines())==17 and conv.endswith(b'\r\n') and b'\n' not in conv.replace(b'\r\n',b'');assert re.findall(rb'warning #(\d+)',conv)==[b'108',b'126'];assert b'Input conversion completed. Errors: 0, Warnings: 2, Notes: 0\r\n' in conv;assert b'File: '+str(R/'model.sxi').replace('\\','/').encode()+b'\r\n' in conv
# Read independent predeclared oracles, not author code.
expected=parse(M/'own-prospective-report-v1.json');expectedlog=bytes.fromhex((M/'own-prospective-log-v1.hex').read_text().strip());actual=parse(R/'report-raw.json');strict(actual,expected);assert (R/'model.log').read_bytes()==expectedlog and len(expectedlog.splitlines())==125
method=parse(M/'independent-method-go-v2.json');assert method['own_report_pin']['sha256']==pin(M/'own-prospective-report-v1.json')['sha256'] and method['own_log_pin']['sha256']==pin(M/'own-prospective-log-v1.hex')['sha256']
selection=parse(J/'next-nongui-alternative-selection/alternative-selection-v1.json');parent=pathlib.Path(next(x['path'] for x in selection['parent_raw'] if pathlib.Path(x['path']).name=='roundtrip-raw.json'));model=parse(parent);model=copy.deepcopy(model);child=parse(C/'native-input.json');strict(child,parse(R/'input.json'));ct={x['name']:x for x in child['model']['tables']};description=ct['ProblemDescription']['instances'][0]['rows'][0][0]
for t in model['model']['tables']:
 if t['name']=='ProblemDescription':t['instances'][0]['rows'][0][0]=description
model['model']['tables'].append(copy.deepcopy(ct['ChangesTaskBreakDown']))
export=parse(R/'roundtrip-raw.json');a=copy.deepcopy(export);e=copy.deepcopy(model);at=a['model'].pop('tables');et=e['model'].pop('tables');strict(a,e);names=[t['name'] for t in at];assert len(names)==len(set(names))==33;assert [n for n in names if n!='ChangesTaskBreakDown']==[t['name'] for t in et[:-1]];by={t['name']:t for t in at}
for t in et:strict(t,by[t['name']])
# Independently parse actual activity periods and inventory/metrics.
periods={}
for line in expectedlog.decode('ascii').splitlines():
 m=re.fullmatch(r'Time: ([0-9.]+)  system turnround task (\d+) on .* (started|completed)',line)
 if m:
  k=(int(m[2]),m[3]);assert k not in periods;periods[k]=float(m[1])
assert periods=={(1,'started'):23.5,(1,'completed'):24.,(3,'started'):26.75,(3,'completed'):27.75}
ledger=[{'task':n,'start':periods[(n,'started')],'end':periods[(n,'completed')],'duration':periods[(n,'completed')]-periods[(n,'started')],'start_bin':int(periods[(n,'started')]*2)/2} for n in [1,3]]
ts={t['name']:t for t in actual['report']['tables']};sys=ts['SystemResults'];cols={x['name']:i for i,x in enumerate(sys['columns'])};rows=sys['instances'][0]['rows'];assert len(rows)==len(ts['StockTotalResults']['instances'][0]['rows'])==72;assert all(r[cols['SYDT']] is None and r[cols['NSYDT']]==0 for r in rows)
integrals={col:sum(r[cols[col]]*(r[cols['ETINT']]-r[cols['STINT']]) for r in rows) for col in ['NSYMT','NSYMP','NSYMO']};assert integrals=={'NSYMT':1.5,'NSYMP':1.,'NSYMO':4.};assert rows[-1][cols['NSYRY']]==1 and rows[-1][cols['NSYRP']]==0;assert sum(r[cols['NFAIL']]+r[cols['NDAM']] for r in rows)==0
assert b'Time: 26.75  subtask 6' in expectedlog and b'Time: 26.9167  subtask 6' in expectedlog;assert b'subtask 6 seqno 1 within system turnround task 3 on <TEACH-AIR-01,0> starts performing, planned to last for 0.166667 hours' in expectedlog;assert b'subtask 7 seqno 2 within system turnround task 3 on <TEACH-AIR-01,0> starts performing, planned to last for 0.833333 hours' in expectedlog
controls=[]
def validate(b,p):
 if b!=expectedlog:raise ValueError('bytes')
 strict(p,expected)
def neg(n,b,p):
 try:validate(b,p)
 except ValueError:controls.append({'name':n,'rejected':True})
 else:raise AssertionError('negative accepted')
neg('parentbehavior',pathlib.Path(next(x['path'] for x in selection['parent_raw'] if pathlib.Path(x['path']).name=='model.log')).read_bytes(),actual)
for n,x,y in [('currentduration',b'0.166667 hours',b'0.333333 hours'),('nextduration',b'0.833333 hours',b'0.333333 hours'),('finish',b'Time: 27.75',b'Time: 27.25'),('RNG',b'1e+010',b'2e+010')]:neg(n,expectedlog.replace(x,y,1),actual)
for n,col,val in [('fakeSYDT','SYDT',1.),('fakecount','NSYDT',1),('activity','NSYMT',.5),('tokentype','NSYMT',1.0)]:
 p=copy.deepcopy(actual);p['report']['tables'][2]['instances'][0]['rows'][54][cols[col]]=val;neg(n,expectedlog,p)
for ti in range(4):
 p=copy.deepcopy(actual);p['report']['tables'][ti]['columns'][0].pop('name');neg('metadata'+str(ti),expectedlog,p)
res={'schema':'issue18-independent-var14-raw-acceptance/v100','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'/root/var14_source_method_review','decision':'GO_BOUNDED','run_id':closure['run_id'],'reader_pin':pin(__file__),'original_recovered_readonly_pairs':pairs,'sources126_rehashed_current_before_after':src,'manifest_pin':pin(C/'prelaunch-manifest-v100-run01.json'),'gates':gates,'invocation_pin':pin(R/'invocation.json'),'native_stages':native,'converter':closure['converter'],'complete_physical_events':125,'exact_parent_substitutions':10,'full_typed_report_cells':4044,'System_bins':72,'Stock_bins':72,'all_export_tables':33,'all_parent32tables_plus6column2rowchange_strict':True,'activity_ledger':ledger,'integrals':integrals,'SYDT_null_NSYDT0_all_preserved':True,'controls':controls,'stock_full_unchanged':True,'Summary_full_unchanged':True,'terminal_ready':1,'RNG_resources_missions_initialplans_and_firstturnround_fullbytes_preserved':True,'accepted_scope':'One late currentTURN-STEPSSEQ1 retained1/6 andlaterSEQ2captured5/6 at26.8; lastturnround26.75–27.75. Both fullraw copies exact, no broaderdata-capture orclocklaw.','limits':['AllGUIfeaturevalidation/gatesexcluded','No wholevar14,allclocksemantics,broaderTIDSEQ/distributions/topology/same-time/resourcewaiting/seed/negativechange proof','No crossengine/performance/CI/overallcompletion claim','Independentrawreceipt is not publicationGO; remainingpublicationreview required'],'native_calls_by_reviewer':0,'accepted_parent_reruns':0,'whole_issue_complete':False,'completion_denominator':None,'no_in_flight_writes':True}
b=(json.dumps(res,ensure_ascii=False,indent=2)+'\n').encode();(O/'independent-raw-acceptance-v100.json').write_bytes(b);(C/'review/independent-raw-acceptance-v100.json').write_bytes(b);print(json.dumps(pin(O/'independent-raw-acceptance-v100.json')))
